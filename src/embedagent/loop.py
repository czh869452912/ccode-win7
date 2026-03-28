from __future__ import annotations

from typing import Callable, Optional, Tuple

from embedagent.context import ContextManager
from embedagent.guard import LoopGuard
from embedagent.llm import OpenAICompatibleClient
from embedagent.memory_maintenance import MemoryMaintenance
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
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import Action, Observation, Session
from embedagent.session_store import SessionSummaryStore
from embedagent.tools import ToolRuntime


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
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[
            Callable[[Action, Observation], None]
        ] = None,
        permission_handler: Optional[
            Callable[[PermissionRequest], bool]
        ] = None,
        on_context_result: Optional[Callable[[object], None]] = None,
        session: Optional[Session] = None,
    ) -> Tuple[str, Session]:
        current_mode = require_mode(initial_mode)["slug"]
        if session is None:
            session = Session()
            session.add_system_message(build_system_prompt(current_mode))
        session.add_user_message(user_text)
        self._persist_summary(session, current_mode)
        final_text = ""
        loop_guard = LoopGuard()
        for _ in range(self.max_turns):
            tool_schemas = self._schemas_for_mode(current_mode)
            context_result = self.context_manager.build_messages(session, current_mode)
            if on_context_result is not None:
                on_context_result(context_result)
            self._persist_summary(session, current_mode, context_result)
            if stream:
                reply = self.client.stream(
                    context_result.messages,
                    tools=tool_schemas,
                    on_text_delta=on_text_delta,
                )
            else:
                reply = self.client.generate(
                    context_result.messages,
                    tools=tool_schemas,
                )
                if on_text_delta and reply.content:
                    on_text_delta(reply.content)
            session.add_assistant_reply(reply)
            self._persist_summary(session, current_mode, context_result)
            final_text = reply.content
            if not reply.actions:
                self._persist_summary(session, current_mode)
                self._maybe_maintain_memory(force=True)
                return final_text, session
            for action in reply.actions:
                if loop_guard.should_block(action):
                    observation = loop_guard.blocked_observation(action)
                    session.add_observation(action, observation)
                    self._persist_summary(session, current_mode)
                    if on_tool_finish:
                        on_tool_finish(action, observation)
                    raise RuntimeError(loop_guard.stop_reason())
                if on_tool_start:
                    on_tool_start(action)
                observation, current_mode = self._execute_action(
                    action=action,
                    current_mode=current_mode,
                    session=session,
                    permission_handler=permission_handler,
                )
                session.add_observation(action, observation)
                self._persist_summary(session, current_mode)
                if on_tool_finish:
                    on_tool_finish(action, observation)
                loop_guard.record(action, observation)
                if loop_guard.should_stop():
                    raise RuntimeError(loop_guard.stop_reason())
        raise RuntimeError("超过最大迭代次数，主循环已停止。")

    def _persist_summary(
        self,
        session: Session,
        current_mode: str,
        context_result: Optional[object] = None,
    ) -> None:
        summary_ref = None
        try:
            summary_ref = self.summary_store.persist(session, current_mode, context_result)
        except Exception:
            summary_ref = None
        try:
            self.project_memory_store.refresh(session, current_mode, summary_ref)
        except Exception:
            return
        self._maybe_maintain_memory()

    def _maybe_maintain_memory(self, force: bool = False) -> None:
        self._maintenance_counter += 1
        if not force and self._maintenance_counter < self.maintenance_interval:
            return
        self._maintenance_counter = 0
        try:
            self.memory_maintenance.run()
        except Exception:
            return

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
        permission_handler: Optional[Callable[[PermissionRequest], bool]],
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
        decision = self.permission_policy.evaluate(action)
        if decision.outcome == "deny":
            observation = Observation(
                tool_name=action.name,
                success=False,
                error=decision.error or "权限规则拒绝该操作。",
                data={
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
                observation = Observation(
                    tool_name=action.name,
                    success=False,
                    error="操作未获批准，已跳过执行。",
                    data={
                        "permission_required": True,
                        "category": request.category,
                        "reason": request.reason,
                        "details": request.details,
                        "permission_decision": "ask",
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
