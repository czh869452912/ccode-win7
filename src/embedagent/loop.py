from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable, Optional, Tuple

from embedagent.context import ContextManager
from embedagent.guard import LoopGuard
from embedagent.llm import ModelClientError, OpenAICompatibleClient
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.interaction import (
    ModeSwitchProposal,
    UserInputOption,
    UserInputRequest,
    UserInputResponse,
    ask_user_schema,
    build_user_input_request,
    propose_mode_switch_schema,
)
from embedagent.modes import (
    DEFAULT_MODE,
    allowed_tools_for,
    build_system_prompt,
    is_path_writable,
    is_tool_allowed,
    mode_names,
    require_mode,
)
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.project_memory import ProjectMemoryStore
from embedagent.query_engine import QueryEngine, to_loop_result
from embedagent.session import Action, LoopResult, Observation, Session
from embedagent.session_store import SessionSummaryStore
from embedagent.tools import ToolRuntime
from embedagent.tools._base import ToolError
from embedagent.workspace_profile import build_workspace_profile_message

_LOG = logging.getLogger(__name__)

# Transient HTTP status codes that warrant an LLM retry.
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_LLM_MAX_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0  # seconds


class AgentLoop(object):
    def __init__(
        self,
        client: OpenAICompatibleClient,
        tools: ToolRuntime,
        max_turns: int = 8,
        permission_policy: Optional[PermissionPolicy] = None,
        context_manager: Optional[ContextManager] = None,
        summary_store: Optional[SessionSummaryStore] = None,
        project_memory_store: Optional[ProjectMemoryStore] = None,
        memory_maintenance: Optional[MemoryMaintenance] = None,
        maintenance_interval: int = 4,
    ) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.permission_policy = permission_policy or PermissionPolicy(
            auto_approve_all=True
        )
        self.project_memory_store = project_memory_store or ProjectMemoryStore(self.tools.workspace)
        self.context_manager = context_manager or ContextManager(project_memory=self.project_memory_store)
        self.summary_store = summary_store or SessionSummaryStore(self.tools.workspace)
        self.memory_maintenance = memory_maintenance or MemoryMaintenance(
            artifact_store=self.tools.artifact_store,
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
        )
        self.maintenance_interval = maintenance_interval if maintenance_interval > 0 else 1
        self._maintenance_counter = 0

    def run(
        self,
        user_text: str,
        stream: bool = True,
        initial_mode: str = DEFAULT_MODE,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[
            Callable[[Action, Observation], None]
        ] = None,
        permission_handler: Optional[
            Callable[[PermissionRequest], bool]
        ] = None,
        user_input_handler: Optional[
            Callable[[UserInputRequest], Optional[UserInputResponse]]
        ] = None,
        on_context_result: Optional[Callable[[object], None]] = None,
        on_step_start: Optional[Callable[[int], None]] = None,
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]] = None,
        session: Optional[Session] = None,
        stop_event: Optional[threading.Event] = None,
        workflow_state: str = "chat",
    ) -> LoopResult:
        engine = QueryEngine(
            client=self.client,
            tools=self.tools,
            max_turns=self.max_turns,
            permission_policy=self.permission_policy,
            context_manager=self.context_manager,
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
            memory_maintenance=self.memory_maintenance,
            maintenance_interval=self.maintenance_interval,
        )
        result = engine.submit_turn(
            user_text=user_text,
            stream=stream,
            initial_mode=initial_mode,
            workflow_state=workflow_state,
            on_text_delta=on_text_delta,
            on_reasoning_delta=on_reasoning_delta,
            on_tool_start=on_tool_start,
            on_tool_finish=on_tool_finish,
            permission_handler=permission_handler,
            user_input_handler=user_input_handler,
            on_context_result=on_context_result,
            on_step_start=on_step_start,
            on_step_finish=on_step_finish,
            session=session,
            stop_event=stop_event,
        )
        return to_loop_result(result)

    def _legacy_run(
        self,
        user_text: str,
        stream: bool = True,
        initial_mode: str = DEFAULT_MODE,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[
            Callable[[Action, Observation], None]
        ] = None,
        permission_handler: Optional[
            Callable[[PermissionRequest], bool]
        ] = None,
        user_input_handler: Optional[
            Callable[[UserInputRequest], Optional[UserInputResponse]]
        ] = None,
        on_context_result: Optional[Callable[[object], None]] = None,
        on_step_start: Optional[Callable[[int], None]] = None,
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]] = None,
        session: Optional[Session] = None,
        stop_event: Optional[threading.Event] = None,
        workflow_state: str = "chat",
    ) -> LoopResult:
        current_mode = require_mode(initial_mode)["slug"]
        if session is None:
            session = Session()
            session.add_system_message(
                build_workspace_profile_message(self.tools.workspace, session.session_id)
            )
            session.add_system_message(
                build_system_prompt(
                    current_mode,
                    getattr(self.tools, "app_config", None),
                    getattr(self.tools, "workspace", ""),
                )
            )
        session.add_user_message(user_text)
        self._persist_summary(session, current_mode)
        final_text = ""
        loop_guard = LoopGuard()
        turns_used = 0
        for turn_index in range(self.max_turns):
            step_index = turn_index + 1
            # ---- cancellation check ----
            if stop_event is not None and stop_event.is_set():
                self._persist_summary(session, current_mode)
                return LoopResult(
                    final_text=final_text,
                    session=session,
                    termination_reason="cancelled",
                    turns_used=turns_used,
                )
            tool_schemas = self._schemas_for_mode(current_mode, workflow_state)
            context_result = self.context_manager.build_messages(session, current_mode)
            if on_context_result is not None:
                on_context_result(context_result)
            self._persist_summary(session, current_mode, context_result)
            if on_step_start is not None:
                on_step_start(step_index)
            # ---- LLM call with retry ----
            reply = self._call_llm_with_retry(
                context_result.messages,
                tool_schemas,
                stream=stream,
                on_text_delta=on_text_delta,
                on_reasoning_delta=on_reasoning_delta,
            )
            session.add_assistant_reply(reply)
            self._persist_summary(session, current_mode, context_result)
            final_text = reply.content
            turns_used = turn_index + 1
            if not reply.actions:
                if on_step_finish is not None:
                    on_step_finish(step_index, reply, "completed")
                self._persist_summary(session, current_mode)
                self._maybe_maintain_memory(force=True)
                return LoopResult(
                    final_text=final_text,
                    session=session,
                    termination_reason="completed",
                    turns_used=turns_used,
                )
            for action in reply.actions:
                # ---- cancellation check inside tool loop ----
                if stop_event is not None and stop_event.is_set():
                    if on_step_finish is not None:
                        on_step_finish(step_index, reply, "cancelled")
                    self._persist_summary(session, current_mode)
                    return LoopResult(
                        final_text=final_text,
                        session=session,
                        termination_reason="cancelled",
                        turns_used=turns_used,
                    )
                if loop_guard.should_block(action):
                    observation = loop_guard.blocked_observation(action)
                    session.add_observation(action, observation)
                    if on_step_finish is not None:
                        on_step_finish(step_index, reply, "guard")
                    self._persist_summary(session, current_mode)
                    if on_tool_finish:
                        on_tool_finish(action, observation)
                    return LoopResult(
                        final_text=final_text,
                        session=session,
                        termination_reason="guard",
                        error=loop_guard.stop_reason(),
                        turns_used=turns_used,
                    )
                if on_tool_start:
                    on_tool_start(action)
                observation, current_mode = self._execute_action(
                    action=action,
                    current_mode=current_mode,
                    session=session,
                    permission_handler=permission_handler,
                    user_input_handler=user_input_handler,
                )
                session.add_observation(action, observation)
                self._persist_summary(session, current_mode)
                if on_tool_finish:
                    on_tool_finish(action, observation)
                loop_guard.record(action, observation)
                # ---- recovery hint injection before hard stop ----
                if loop_guard.consecutive_failures >= 2 and not loop_guard.should_stop():
                    hint = (
                        "警告：已连续失败 %d 次（最近工具：%s，错误：%s）。"
                        "请重新评估方案，考虑换一种工具或路径，或用 ask_user 向用户求助。"
                    ) % (
                        loop_guard.consecutive_failures,
                        action.name,
                        (observation.error or "未知错误")[:120],
                    )
                    session.add_system_message(hint)
                if loop_guard.should_stop():
                    if on_step_finish is not None:
                        on_step_finish(step_index, reply, "guard")
                    self._persist_summary(session, current_mode)
                    return LoopResult(
                        final_text=final_text,
                        session=session,
                        termination_reason="guard",
                        error=loop_guard.stop_reason(),
                        turns_used=turns_used,
                    )
            if on_step_finish is not None:
                on_step_finish(step_index, reply, "tool_calls")
        self._persist_summary(session, current_mode)
        return LoopResult(
            final_text=final_text,
            session=session,
            termination_reason="max_turns",
            error="超过最大迭代次数（%d），主循环已停止。" % self.max_turns,
            turns_used=turns_used,
        )

    def _call_llm_with_retry(
        self,
        messages: list,
        tool_schemas: list,
        stream: bool,
        on_text_delta: Optional[Callable[[str], None]],
        on_reasoning_delta: Optional[Callable[[str], None]],
    ):
        """Call the LLM with exponential back-off retry on transient errors."""
        last_exc = None
        for attempt in range(_LLM_MAX_RETRIES):
            try:
                if stream:
                    return self.client.stream(
                        messages,
                        tools=tool_schemas,
                        on_text_delta=on_text_delta,
                        on_reasoning_delta=on_reasoning_delta,
                    )
                else:
                    reply = self.client.generate(messages, tools=tool_schemas)
                    if on_reasoning_delta and reply.reasoning_content:
                        on_reasoning_delta(reply.reasoning_content)
                    if on_text_delta and reply.content:
                        on_text_delta(reply.content)
                    return reply
            except ModelClientError as exc:
                last_exc = exc
                error_text = str(exc)
                is_retryable = any(
                    str(code) in error_text for code in _RETRYABLE_HTTP_CODES
                )
                if not is_retryable or attempt >= _LLM_MAX_RETRIES - 1:
                    raise
                delay = _LLM_RETRY_BASE_DELAY * (2 ** attempt)
                _LOG.warning(
                    "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, _LLM_MAX_RETRIES, delay, exc,
                )
                time.sleep(delay)
        raise last_exc  # type: ignore[misc]

    # Number of recent turns to keep fully in memory; older turns are stubbed.
    _SESSION_ARCHIVE_KEEP_TURNS = 30

    def _persist_summary(
        self,
        session: Session,
        current_mode: str,
        context_result: Optional[object] = None,
    ) -> None:
        summary_ref = None
        try:
            summary_ref = self.summary_store.persist(session, current_mode, context_result)
        except OSError as exc:
            _LOG.warning("session summary persist failed: %s", exc)
        except Exception as exc:
            _LOG.error("unexpected error in persist_summary: %s", exc, exc_info=True)
        try:
            self.project_memory_store.refresh(session, current_mode, summary_ref)
        except Exception as exc:
            _LOG.warning("project memory refresh failed: %s", exc)
        # Bound in-memory message growth for long sessions.
        try:
            session.trim_old_observations(self._SESSION_ARCHIVE_KEEP_TURNS)
        except Exception as exc:
            _LOG.warning("session trim failed: %s", exc)
        self._maybe_maintain_memory()

    def _maybe_maintain_memory(self, force: bool = False) -> None:
        self._maintenance_counter += 1
        if not force and self._maintenance_counter < self.maintenance_interval:
            return
        self._maintenance_counter = 0
        try:
            self.memory_maintenance.run()
        except Exception as exc:
            _LOG.warning("memory maintenance failed: %s", exc)

    def _schemas_for_mode(self, mode_name: str, workflow_state: str = "chat"):
        allowed = set(allowed_tools_for(mode_name))
        schemas = []
        runtime_schemas = getattr(self.tools, "schemas_for", None)
        if callable(runtime_schemas):
            schemas.extend(runtime_schemas(mode_name, workflow_state=workflow_state, tool_names=list(allowed)))
        else:
            for item in self.tools.schemas():
                name = item.get("function", {}).get("name", "")
                if name in allowed:
                    schemas.append(item)
        if "ask_user" in allowed:
            schemas.append(ask_user_schema())
        schemas.append(propose_mode_switch_schema())
        return schemas

    def _execute_action(
        self,
        action: Action,
        current_mode: str,
        session: Session,
        permission_handler: Optional[Callable[[PermissionRequest], bool]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
    ) -> Tuple[Observation, str]:
        runtime_action = action
        if action.name == "manage_todos" and not action.arguments.get("session_id"):
            runtime_action = Action(
                name=action.name,
                arguments=dict(action.arguments, session_id=session.session_id),
                call_id=action.call_id,
                raw_arguments=action.raw_arguments,
            )
        if action.name == "propose_mode_switch":
            return self._handle_propose_mode_switch(action, current_mode, session, user_input_handler)
        if not is_tool_allowed(current_mode, action.name):
            observation = self._failure_observation(
                tool_name=action.name,
                error="当前模式 %s 不允许调用工具 %s。" % (current_mode, action.name),
                error_kind="mode_tool_blocked",
                retryable=False,
                blocked_by=current_mode,
                suggested_next_step=self._suggest_for_mode_tool_block(current_mode),
                extra_data={
                    "mode": current_mode,
                    "allowed_tools": allowed_tools_for(current_mode),
                    "requested_tool": action.name,
                },
            )
            return observation, current_mode
        if action.name == "ask_user":
            return self._handle_ask_user(action, current_mode, session, user_input_handler)
        if action.name in ("edit_file", "write_file"):
            path = str(runtime_action.arguments.get("path") or "")
            if not path:
                observation = self._failure_observation(
                    tool_name=action.name,
                    error="%s 缺少 path 参数。" % action.name,
                    error_kind="invalid_arguments",
                    retryable=False,
                    blocked_by="arguments",
                    suggested_next_step="补充一个相对于工作区的 path 参数。",
                    extra_data={"mode": current_mode},
                )
                return observation, current_mode
            normalized_path = path.replace("\\", "/")
            if not is_path_writable(
                current_mode,
                normalized_path,
                getattr(self.tools, "app_config", None),
            ):
                observation = self._failure_observation(
                    tool_name=action.name,
                    error="当前模式 %s 不允许修改 %s。" % (current_mode, normalized_path),
                    error_kind="mode_path_blocked",
                    retryable=False,
                    blocked_by=current_mode,
                    suggested_next_step=self._suggest_for_mode_path_block(
                        current_mode,
                        normalized_path,
                    ),
                    extra_data={
                        "mode": current_mode,
                        "path": normalized_path,
                    },
                )
                return observation, current_mode
            if action.name == "edit_file":
                try:
                    resolved_path = self.tools._ctx.resolve_path(
                        normalized_path,
                        allow_missing=True,
                    )
                except ToolError as exc:
                    observation = self._failure_observation(
                        tool_name=action.name,
                        error=str(exc),
                        error_kind="path_invalid",
                        retryable=False,
                        blocked_by="workspace",
                        suggested_next_step="改用工作区内的相对路径。",
                        extra_data={"mode": current_mode, "path": normalized_path},
                    )
                    return observation, current_mode
                if not resolved_path or not self._path_exists(resolved_path):
                    observation = self._failure_observation(
                        tool_name=action.name,
                        error="目标文件不存在，edit_file 只能修改已存在的文件。",
                        error_kind="file_missing",
                        retryable=False,
                        blocked_by="filesystem",
                        suggested_next_step="若要新建文件，请改用 write_file；若要修改现有文件，请先确认路径。",
                        extra_data={"mode": current_mode, "path": normalized_path},
                    )
                    return observation, current_mode
        decision = self.permission_policy.evaluate(runtime_action)
        if decision.outcome == "deny":
            observation = self._failure_observation(
                tool_name=action.name,
                error=decision.error or "权限规则拒绝该操作。",
                error_kind="permission_denied",
                retryable=False,
                blocked_by="permission_policy",
                suggested_next_step="修改权限规则，或由用户手动放行后重试。",
                extra_data={
                    "permission_required": True,
                    "category": decision.details.get("category"),
                    "reason": decision.details.get("rule_reason") or decision.error,
                    "details": decision.details,
                    "permission_decision": "deny",
                },
            )
            return observation, current_mode
        request = decision.request
        if request is not None:
            approved = permission_handler(request) if permission_handler else False
            if not approved:
                observation = self._failure_observation(
                    tool_name=action.name,
                    error="操作未获批准，已跳过执行。",
                    error_kind="permission_denied",
                    retryable=False,
                    blocked_by="user_confirmation",
                    suggested_next_step="等待用户批准，或改为不需要该权限的方案。",
                    extra_data={
                        "permission_required": True,
                        "category": request.category,
                        "reason": request.reason,
                        "details": request.details,
                        "permission_decision": "ask",
                    },
                )
                return observation, current_mode
        observation = self.tools.execute(runtime_action.name, runtime_action.arguments)
        return observation, current_mode

    def _handle_ask_user(
        self,
        action: Action,
        current_mode: str,
        session: Session,
        user_input_handler: Optional[
            Callable[[UserInputRequest], Optional[UserInputResponse]]
        ],
    ) -> Tuple[Observation, str]:
        request = build_user_input_request(action.arguments)
        if not request.question:
            return self._failure_observation(
                tool_name="ask_user",
                error="ask_user 缺少 question 参数。",
                error_kind="invalid_arguments",
                retryable=False,
                blocked_by="arguments",
                suggested_next_step="补充一个明确、具体的问题。",
                extra_data={},
            ), current_mode
        if len(request.options) < 2:
            return self._failure_observation(
                tool_name="ask_user",
                error="ask_user 至少需要 2 个建议选项。",
                error_kind="invalid_arguments",
                retryable=False,
                blocked_by="arguments",
                suggested_next_step="补充 2 到 4 个清晰选项。",
                extra_data=request.details,
            ), current_mode
        if user_input_handler is None:
            return self._failure_observation(
                tool_name="ask_user",
                error="当前运行环境无法处理 ask_user。",
                error_kind="user_input_unavailable",
                retryable=False,
                blocked_by="runtime",
                suggested_next_step="在支持用户交互的前端中运行，或改用最终文本向用户提问。",
                extra_data=request.details,
            ), current_mode
        response = user_input_handler(request)
        if response is None or not str(response.answer or "").strip():
            return self._failure_observation(
                tool_name="ask_user",
                error="未收到有效的用户回答。",
                error_kind="user_input_unavailable",
                retryable=False,
                blocked_by="user_input",
                suggested_next_step="重新向用户提问，或在最终回复中请求用户确认。",
                extra_data=request.details,
            ), current_mode
        selected_mode = str(response.selected_mode or "").strip()
        next_mode = current_mode
        mode_changed = False
        if selected_mode:
            try:
                require_mode(selected_mode)
            except ValueError:
                selected_mode = ""
            else:
                if selected_mode != current_mode:
                    next_mode = selected_mode
                    mode_changed = True
                    session.add_system_message(
                        build_system_prompt(
                            selected_mode,
                            getattr(self.tools, "app_config", None),
                            getattr(self.tools, "workspace", ""),
                        )
                    )
        observation = Observation(
            tool_name="ask_user",
            success=True,
            error=None,
            data={
                "question": request.question,
                "options": request.details.get("options") or [],
                "answer": str(response.answer or "").strip(),
                "selected_index": response.selected_index,
                "selected_option_text": response.selected_option_text,
                "selected_mode": selected_mode,
                "mode_changed": mode_changed,
            },
        )
        return observation, next_mode

    def _failure_observation(
        self,
        tool_name: str,
        error: str,
        error_kind: str,
        retryable: bool,
        blocked_by: str,
        suggested_next_step: str,
        extra_data: Optional[dict] = None,
    ) -> Observation:
        data = {
            "error_kind": error_kind,
            "retryable": retryable,
            "blocked_by": blocked_by,
            "suggested_next_step": suggested_next_step,
        }
        if extra_data:
            data.update(extra_data)
        return Observation(
            tool_name=tool_name,
            success=False,
            error=error,
            data=data,
        )

    def _suggest_for_mode_tool_block(self, current_mode: str) -> str:
        if current_mode == "orchestra":
            return "请在当前模式内重新规划步骤，或切到拥有该工具的下游模式。"
        if "ask_user" in allowed_tools_for(current_mode):
            return "若下一步需要改变方向，请先用 ask_user 询问用户；否则请在最终回复中建议用户使用 /mode。"
        return "当前模式不能自动切换；请在回复中说明建议，并等待用户显式使用 /mode。"

    def _suggest_for_mode_path_block(self, current_mode: str, path: str) -> str:
        if current_mode == "spec":
            return "spec 模式只写文档；若工作区没有文档目录，可改为 docs/%s 之类的文档路径。" % path.rsplit("/", 1)[-1]
        if current_mode == "orchestra":
            return "orchestra 负责协调，不直接落文件；请切到合适的下游模式。"
        if "ask_user" in allowed_tools_for(current_mode):
            return "若确实需要修改该路径，请先用 ask_user 让用户确认路径或模式。"
        return "请改用当前模式允许的文件类型，或在回复中建议用户切到更合适的模式。"

    def _handle_propose_mode_switch(
        self,
        action: Action,
        current_mode: str,
        session: Session,
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
    ) -> Tuple[Observation, str]:
        target_mode = str(action.arguments.get("target_mode") or "").strip()
        reason = str(action.arguments.get("reason") or "").strip()
        if not target_mode:
            return self._failure_observation(
                tool_name="propose_mode_switch",
                error="propose_mode_switch 缺少 target_mode 参数。",
                error_kind="invalid_arguments",
                retryable=False,
                blocked_by="arguments",
                suggested_next_step="补充 target_mode 参数（如 code, debug, verify）。",
                extra_data={},
            ), current_mode
        resolved = str(require_mode(target_mode)["slug"])
        if user_input_handler is None:
            return self._failure_observation(
                tool_name="propose_mode_switch",
                error="当前运行环境无法处理 propose_mode_switch。",
                error_kind="user_input_unavailable",
                retryable=False,
                blocked_by="runtime",
                suggested_next_step="在支持用户交互的前端中运行。",
                extra_data={"target_mode": resolved},
            ), current_mode
        request = UserInputRequest(
            tool_name="propose_mode_switch",
            question=reason or ("建议切换到 %s 模式。" % resolved),
            options=[
                UserInputOption(index=1, text="确认：切换到 %s 模式" % resolved, mode=resolved),
                UserInputOption(index=2, text="取消：保持当前模式", mode=""),
            ],
            details={"target_mode": resolved, "reason": reason},
        )
        response = user_input_handler(request)
        if response is None or not str(response.answer or "").strip():
            return self._failure_observation(
                tool_name="propose_mode_switch",
                error="未收到有效的模式切换响应。",
                error_kind="user_input_unavailable",
                retryable=False,
                blocked_by="user_input",
                suggested_next_step="重新提议模式切换，或在最终回复中说明建议。",
                extra_data={"target_mode": resolved},
            ), current_mode
        selected_mode = str(response.selected_mode or "").strip()
        next_mode = current_mode
        mode_changed = False
        if selected_mode and selected_mode != current_mode:
            next_mode = selected_mode
            mode_changed = True
            session.add_system_message(
                build_system_prompt(
                    selected_mode,
                    getattr(self.tools, "app_config", None),
                    getattr(self.tools, "workspace", ""),
                )
            )
        observation = Observation(
            tool_name="propose_mode_switch",
            success=True,
            error=None,
            data={
                "target_mode": resolved,
                "reason": reason,
                "confirmed": mode_changed,
                "mode_changed": mode_changed,
                "current_mode": next_mode,
                "selected_mode": selected_mode if mode_changed else "",
            },
        )
        return observation, next_mode

    def _path_exists(self, path: str) -> bool:
        return bool(path) and os.path.exists(path)
