from __future__ import annotations

from typing import Callable, Optional, Tuple

from embedagent.llm import OpenAICompatibleClient
from embedagent.modes import (
    DEFAULT_MODE,
    allowed_tools_for,
    build_system_prompt,
    is_path_writable,
    is_tool_allowed,
    mode_names,
    require_mode,
    switch_mode_schema,
)
from embedagent.session import Action, Observation, Session
from embedagent.tools import ToolRuntime


class AgentLoop(object):
    def __init__(
        self,
        client: OpenAICompatibleClient,
        tools: ToolRuntime,
        max_turns: int = 8,
    ) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns

    def run(
        self,
        user_text: str,
        stream: bool = True,
        initial_mode: str = DEFAULT_MODE,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[
            Callable[[Action, Observation], None]
        ] = None,
    ) -> Tuple[str, Session]:
        current_mode = require_mode(initial_mode)["slug"]
        session = Session()
        session.add_system_message(build_system_prompt(current_mode))
        session.add_user_message(user_text)
        final_text = ""
        for _ in range(self.max_turns):
            tool_schemas = self._schemas_for_mode(current_mode)
            if stream:
                reply = self.client.stream(
                    session.api_messages(),
                    tools=tool_schemas,
                    on_text_delta=on_text_delta,
                )
            else:
                reply = self.client.generate(
                    session.api_messages(),
                    tools=tool_schemas,
                )
                if on_text_delta and reply.content:
                    on_text_delta(reply.content)
            session.add_assistant_reply(reply)
            final_text = reply.content
            if not reply.actions:
                return final_text, session
            for action in reply.actions:
                if on_tool_start:
                    on_tool_start(action)
                observation, current_mode = self._execute_action(
                    action=action,
                    current_mode=current_mode,
                    session=session,
                )
                session.add_observation(action, observation)
                if on_tool_finish:
                    on_tool_finish(action, observation)
        raise RuntimeError("超过最大迭代次数，主循环已停止。")

    def _schemas_for_mode(self, mode_name: str):
        allowed = set(allowed_tools_for(mode_name))
        schemas = []
        for item in self.tools.schemas():
            name = item.get("function", {}).get("name", "")
            if name in allowed:
                schemas.append(item)
        if "switch_mode" in allowed:
            schemas.append(switch_mode_schema())
        return schemas

    def _execute_action(
        self,
        action: Action,
        current_mode: str,
        session: Session,
    ) -> Tuple[Observation, str]:
        if action.name == "switch_mode":
            return self._handle_switch_mode(action, current_mode, session)
        if not is_tool_allowed(current_mode, action.name):
            observation = Observation(
                tool_name=action.name,
                success=False,
                error="当前模式 %s 不允许调用工具 %s。" % (current_mode, action.name),
                data={
                    "mode": current_mode,
                    "allowed_tools": allowed_tools_for(current_mode),
                    "requested_tool": action.name,
                },
            )
            return observation, current_mode
        if action.name == "edit_file":
            path = str(action.arguments.get("path") or "")
            if not path:
                observation = Observation(
                    tool_name=action.name,
                    success=False,
                    error="edit_file 缺少 path 参数。",
                    data={"mode": current_mode},
                )
                return observation, current_mode
            normalized_path = path.replace("\\", "/")
            if not is_path_writable(current_mode, normalized_path):
                observation = Observation(
                    tool_name=action.name,
                    success=False,
                    error="当前模式 %s 不允许修改 %s。" % (current_mode, normalized_path),
                    data={
                        "mode": current_mode,
                        "path": normalized_path,
                    },
                )
                return observation, current_mode
        observation = self.tools.execute(action.name, action.arguments)
        return observation, current_mode

    def _handle_switch_mode(
        self,
        action: Action,
        current_mode: str,
        session: Session,
    ) -> Tuple[Observation, str]:
        target = str(action.arguments.get("target") or "").strip()
        if not target:
            observation = Observation(
                tool_name="switch_mode",
                success=False,
                error="switch_mode 缺少 target 参数。",
                data={"mode": current_mode, "available_modes": mode_names()},
            )
            return observation, current_mode
        try:
            require_mode(target)
        except ValueError as exc:
            observation = Observation(
                tool_name="switch_mode",
                success=False,
                error=str(exc),
                data={"mode": current_mode, "available_modes": mode_names()},
            )
            return observation, current_mode
        session.add_system_message(build_system_prompt(target))
        observation = Observation(
            tool_name="switch_mode",
            success=True,
            error=None,
            data={
                "from_mode": current_mode,
                "to_mode": target,
                "allowed_tools": allowed_tools_for(target),
            },
        )
        return observation, target
