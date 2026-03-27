from __future__ import annotations

import ast
import json
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable, Dict, Iterable, List, Optional

from embedagent.session import Action, AssistantReply


class ModelClientError(Exception):
    pass


class OpenAICompatibleClient(object):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        temperature: Optional[float] = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url 不能为空。")
        if not model:
            raise ValueError("model 不能为空。")
        self.endpoint = self._build_endpoint(base_url)
        self.api_key = api_key or ""
        self.model = model
        self.timeout = timeout
        self.temperature = temperature

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AssistantReply:
        payload = self._request(self._build_payload(messages, tools, stream=False))
        return self._parse_completion(payload)

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
    ) -> AssistantReply:
        return self._stream_request(
            self._build_payload(messages, tools, stream=True),
            on_text_delta=on_text_delta,
        )

    def _build_endpoint(self, base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return normalized + "/chat/completions"

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        stream: bool,
    ) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if tools:
            payload["tools"] = tools
        return payload

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = "Bearer %s" % self.api_key
        return headers

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
            raw_body = response.read()
        except urllib.error.HTTPError as exc:
            raise ModelClientError(self._format_http_error(exc))
        except urllib.error.URLError as exc:
            raise ModelClientError("模型服务不可用：%s" % exc)
        try:
            return json.loads(raw_body.decode("utf-8"))
        except ValueError as exc:
            raise ModelClientError("模型返回了无效 JSON：%s" % exc)

    def _stream_request(
        self,
        payload: Dict[str, Any],
        on_text_delta: Optional[Callable[[str], None]],
    ) -> AssistantReply:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            raise ModelClientError(self._format_http_error(exc))
        except urllib.error.URLError as exc:
            raise ModelClientError("模型服务不可用：%s" % exc)

        content_parts = []
        reasoning_parts = []
        tool_buffers = {}
        finish_reason = None
        for event_data in self._iter_sse_events(response):
            if event_data == "[DONE]":
                break
            try:
                payload_item = json.loads(event_data)
            except ValueError:
                continue
            choices = payload_item.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            text = self._normalize_content(delta.get("content"))
            if text:
                content_parts.append(text)
                if on_text_delta is not None:
                    on_text_delta(text)
            reasoning_text = self._normalize_content(delta.get("reasoning_content"))
            if reasoning_text:
                reasoning_parts.append(reasoning_text)
            self._merge_stream_tool_calls(tool_buffers, delta)
            if choice.get("finish_reason"):
                finish_reason = choice.get("finish_reason")
        actions = self._finalize_stream_tool_calls(tool_buffers)
        return AssistantReply(
            content="".join(content_parts),
            actions=actions,
            finish_reason=finish_reason,
            reasoning_content="".join(reasoning_parts),
        )

    def _iter_sse_events(self, response: Any) -> Iterable[str]:
        buffer_lines = []
        for raw_line in response:
            line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
            if not line:
                if buffer_lines:
                    yield "".join(buffer_lines)
                    buffer_lines = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                buffer_lines.append(line[5:].lstrip())
        if buffer_lines:
            yield "".join(buffer_lines)

    def _parse_completion(self, payload: Dict[str, Any]) -> AssistantReply:
        if payload.get("choices"):
            return self._parse_chat_completion(payload)
        if payload.get("output"):
            return self._parse_responses_payload(payload)
        raise ModelClientError("无法识别模型响应格式。")

    def _parse_chat_completion(self, payload: Dict[str, Any]) -> AssistantReply:
        choices = payload.get("choices") or []
        if not choices:
            raise ModelClientError("模型未返回任何候选结果。")
        choice = choices[0]
        message = choice.get("message") or {}
        actions = self._parse_tool_calls(
            message.get("tool_calls"),
            message.get("function_call"),
        )
        return AssistantReply(
            content=self._normalize_content(message.get("content")),
            actions=actions,
            finish_reason=choice.get("finish_reason"),
            reasoning_content=self._normalize_content(
                message.get("reasoning_content")
            ),
        )

    def _parse_responses_payload(self, payload: Dict[str, Any]) -> AssistantReply:
        content_parts = []
        actions = []
        for item in payload.get("output") or []:
            item_type = item.get("type")
            if item_type == "message":
                content_parts.append(self._normalize_content(item.get("content")))
                continue
            if item_type == "function_call":
                raw_arguments = item.get("arguments") or "{}"
                actions.append(
                    Action(
                        name=item.get("name") or "",
                        arguments=self._parse_arguments(raw_arguments),
                        call_id=item.get("call_id") or uuid.uuid4().hex,
                        raw_arguments=raw_arguments,
                    )
                )
        return AssistantReply(content="".join(content_parts), actions=actions)

    def _normalize_content(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks = []
            for item in content:
                if isinstance(item, str):
                    chunks.append(item)
                    continue
                if isinstance(item, dict):
                    if "text" in item and isinstance(item["text"], str):
                        chunks.append(item["text"])
                    elif item.get("type") == "output_text":
                        chunks.append(str(item.get("text", "")))
                else:
                    chunks.append(str(item))
            return "".join(chunks)
        if isinstance(content, dict) and "text" in content:
            return str(content["text"])
        return str(content)

    def _parse_tool_calls(
        self,
        tool_calls: Optional[List[Dict[str, Any]]],
        function_call: Optional[Dict[str, Any]],
    ) -> List[Action]:
        actions = []
        for item in tool_calls or []:
            function_data = item.get("function") or {}
            raw_arguments = function_data.get("arguments") or "{}"
            actions.append(
                Action(
                    name=function_data.get("name") or "",
                    arguments=self._parse_arguments(raw_arguments),
                    call_id=item.get("id") or uuid.uuid4().hex,
                    raw_arguments=raw_arguments,
                )
            )
        if function_call:
            raw_arguments = function_call.get("arguments") or "{}"
            actions.append(
                Action(
                    name=function_call.get("name") or "",
                    arguments=self._parse_arguments(raw_arguments),
                    call_id=uuid.uuid4().hex,
                    raw_arguments=raw_arguments,
                )
            )
        return actions

    def _merge_stream_tool_calls(
        self,
        buffers: Dict[int, Dict[str, Any]],
        delta: Dict[str, Any],
    ) -> None:
        for tool_call in delta.get("tool_calls") or []:
            index = tool_call.get("index", 0)
            buffer_item = buffers.setdefault(
                index,
                {"id": None, "name": None, "arguments": []},
            )
            if tool_call.get("id"):
                buffer_item["id"] = tool_call["id"]
            function_data = tool_call.get("function") or {}
            if function_data.get("name"):
                buffer_item["name"] = function_data["name"]
            if function_data.get("arguments"):
                buffer_item["arguments"].append(function_data["arguments"])
        function_call = delta.get("function_call")
        if function_call:
            buffer_item = buffers.setdefault(
                0,
                {"id": None, "name": None, "arguments": []},
            )
            if function_call.get("name"):
                buffer_item["name"] = function_call["name"]
            if function_call.get("arguments"):
                buffer_item["arguments"].append(function_call["arguments"])

    def _finalize_stream_tool_calls(
        self,
        buffers: Dict[int, Dict[str, Any]],
    ) -> List[Action]:
        actions = []
        for index in sorted(buffers):
            item = buffers[index]
            raw_arguments = "".join(item["arguments"]) or "{}"
            actions.append(
                Action(
                    name=item.get("name") or "",
                    arguments=self._parse_arguments(raw_arguments),
                    call_id=item.get("id") or uuid.uuid4().hex,
                    raw_arguments=raw_arguments,
                )
            )
        return actions

    def _parse_arguments(self, raw_arguments: str) -> Dict[str, Any]:
        text = (raw_arguments or "").strip()
        if not text:
            return {}
        if text.startswith("```"):
            lines = [line for line in text.splitlines() if not line.startswith("```")]
            text = "\n".join(lines).strip()
        try:
            parsed = json.loads(text)
        except ValueError:
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                raise ModelClientError("工具参数不是有效 JSON：%s" % text)
        if not isinstance(parsed, dict):
            raise ModelClientError("工具参数必须解析为对象。")
        return parsed

    def _format_http_error(self, exc: urllib.error.HTTPError) -> str:
        raw_body = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw_body)
        except ValueError:
            payload = {}
        error_message = ""
        if isinstance(payload.get("error"), dict):
            error_message = payload["error"].get("message", "")
        elif isinstance(payload.get("error"), str):
            error_message = payload.get("error", "")
        if not error_message:
            error_message = raw_body or exc.reason
        return "模型请求失败（HTTP %s）：%s" % (exc.code, error_message)
