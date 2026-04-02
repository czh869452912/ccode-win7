from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from embedagent.context import ContextManager
from embedagent.guard import LoopGuard
from embedagent.interaction import UserInputRequest, UserInputResponse, ask_user_schema, build_user_input_request, propose_mode_switch_schema
from embedagent.llm import ModelClientError, OpenAICompatibleClient
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.modes import DEFAULT_MODE, allowed_tools_for, build_system_prompt, is_path_writable, is_tool_allowed, require_mode
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import Action, AssistantReply, ContextAssemblyResult, LoopResult, LoopTransition, Observation, PendingInteraction, QueryTurnResult, Session
from embedagent.session_store import SessionSummaryStore
from embedagent.tool_execution import StreamingToolExecutor, partition_tool_actions
from embedagent.tools import ToolRuntime
from embedagent.tools._base import ToolError
from embedagent.workspace_intelligence import WorkspaceIntelligenceBroker

_LOG = logging.getLogger(__name__)
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_LLM_MAX_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0
_COMPACT_RETRY_ERROR_MARKERS = (
    "context length",
    "maximum context",
    "prompt is too long",
    "prompt too long",
    "max tokens",
    "too many tokens",
    "上下文",
    "超出上下文",
)


class QueryEngine(object):
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
        intelligence_broker: Optional[WorkspaceIntelligenceBroker] = None,
        max_parallel_tools: int = 3,
    ) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.permission_policy = permission_policy or PermissionPolicy(auto_approve_all=True)
        self.project_memory_store = project_memory_store or ProjectMemoryStore(self.tools.workspace)
        self.context_manager = context_manager or ContextManager(project_memory=self.project_memory_store)
        self.summary_store = summary_store or SessionSummaryStore(self.tools.workspace)
        self.memory_maintenance = memory_maintenance or MemoryMaintenance(
            artifact_store=self.tools.artifact_store,
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
        )
        self.maintenance_interval = maintenance_interval if maintenance_interval > 0 else 1
        self.intelligence_broker = intelligence_broker or WorkspaceIntelligenceBroker()
        self.max_parallel_tools = max(1, int(max_parallel_tools or 1))
        self._maintenance_counter = 0

    def submit_turn(
        self,
        user_text: str,
        stream: bool = True,
        initial_mode: str = DEFAULT_MODE,
        workflow_state: str = "chat",
        session: Optional[Session] = None,
        stop_event: Optional[threading.Event] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[Callable[[Action, Observation], None]] = None,
        on_context_result: Optional[Callable[[ContextAssemblyResult], None]] = None,
        on_step_start: Optional[Callable[[int], None]] = None,
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]] = None,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]] = None,
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]] = None,
    ) -> QueryTurnResult:
        current_mode = require_mode(initial_mode)["slug"]
        if session is None:
            session = Session()
            session.add_system_message(build_system_prompt(current_mode, getattr(self.tools, "app_config", None), self.tools.workspace))
        if user_text:
            session.add_user_message(user_text)
        return self._run_loop(
            session,
            current_mode,
            workflow_state,
            stream,
            stop_event,
            on_text_delta,
            on_reasoning_delta,
            on_tool_start,
            on_tool_finish,
            on_context_result,
            on_step_start,
            on_step_finish,
            permission_handler,
            user_input_handler,
        )

    def resume_pending(
        self,
        session: Session,
        initial_mode: str,
        interaction_resolution: Optional[Dict[str, Any]] = None,
        workflow_state: str = "chat",
        stream: bool = True,
        stop_event: Optional[threading.Event] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[Callable[[Action, Observation], None]] = None,
        on_context_result: Optional[Callable[[ContextAssemblyResult], None]] = None,
        on_step_start: Optional[Callable[[int], None]] = None,
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]] = None,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]] = None,
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]] = None,
    ) -> QueryTurnResult:
        current_mode = require_mode(initial_mode)["slug"]
        pending = session.pending_interaction
        if pending is None:
            transition = LoopTransition(reason="completed", message="no pending interaction")
            session.record_transition(transition)
            return QueryTurnResult("", session, transition)
        current_mode = self._resume_interaction(
            session,
            pending,
            current_mode,
            dict(interaction_resolution or {}),
            on_tool_start,
            on_tool_finish,
        )
        return self._run_loop(
            session,
            current_mode,
            workflow_state,
            stream,
            stop_event,
            on_text_delta,
            on_reasoning_delta,
            on_tool_start,
            on_tool_finish,
            on_context_result,
            on_step_start,
            on_step_finish,
            permission_handler,
            user_input_handler,
        )

    def _run_loop(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        stream: bool,
        stop_event: Optional[threading.Event],
        on_text_delta: Optional[Callable[[str], None]],
        on_reasoning_delta: Optional[Callable[[str], None]],
        on_tool_start: Optional[Callable[[Action], None]],
        on_tool_finish: Optional[Callable[[Action, Observation], None]],
        on_context_result: Optional[Callable[[ContextAssemblyResult], None]],
        on_step_start: Optional[Callable[[int], None]],
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]],
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
    ) -> QueryTurnResult:
        final_text = ""
        loop_guard = LoopGuard()
        turns_used = 0
        for turn_index in range(self.max_turns):
            if stop_event is not None and stop_event.is_set():
                transition = LoopTransition(reason="aborted", message="stop_event set", turns_used=turns_used)
                session.record_transition(transition)
                return QueryTurnResult(final_text, session, transition, turns_used)
            step_index = turn_index + 1
            session.begin_step()
            if on_step_start is not None:
                on_step_start(step_index)
            force_compact = False
            compact_retry_used = False
            while True:
                assembly = self._build_context(session, current_mode, workflow_state, force_compact=force_compact)
                if on_context_result is not None:
                    on_context_result(assembly)
                self._persist_summary(session, current_mode, assembly)
                try:
                    reply = self._call_llm_with_retry(assembly.messages, self._schemas_for_mode(current_mode, workflow_state), stream, on_text_delta, on_reasoning_delta)
                    break
                except ModelClientError as exc:
                    if compact_retry_used or not self._should_retry_with_compact(exc):
                        raise
                    compact_retry_used = True
                    force_compact = True
                    self._maybe_record_compact_boundary(session, current_mode, assembly)
                    transition = LoopTransition(
                        reason="compact_retry",
                        message=str(exc),
                        next_mode=current_mode,
                        turns_used=turns_used,
                        metadata={
                            "source_mode": current_mode,
                            "retry_mode": "compact",
                            "error": str(exc),
                            "approx_tokens_before": assembly.approx_tokens,
                            "pipeline_steps": list(assembly.pipeline_steps),
                        },
                    )
                    session.record_transition(transition)
                    continue
            session.add_assistant_reply(reply)
            final_text = reply.content
            turns_used = step_index
            if not reply.actions:
                transition = LoopTransition(reason="completed", message="assistant finished", next_mode=current_mode, turns_used=turns_used)
                session.record_transition(transition)
                self._persist_summary(session, current_mode, assembly)
                self._maybe_record_compact_boundary(session, current_mode, assembly)
                self._maybe_maintain_memory(True)
                if on_step_finish is not None:
                    on_step_finish(step_index, reply, "completed")
                return QueryTurnResult(final_text, session, transition, turns_used)
            executor = StreamingToolExecutor(lambda action: self.tools.execute(action.name, action.arguments), self.max_parallel_tools)
            for batch in partition_tool_actions(reply.actions, self.tools.tool_capabilities):
                if not batch.parallel:
                    for action in batch.actions:
                        session.record_tool_call(action)
                        if on_tool_start is not None:
                            on_tool_start(action)
                        observation, current_mode, suspended = self._execute_action(
                            session,
                            action,
                            current_mode,
                            permission_handler,
                            user_input_handler,
                        )
                        if suspended is not None:
                            self._persist_summary(session, current_mode, assembly)
                            if on_step_finish is not None:
                                on_step_finish(step_index, reply, suspended.transition.reason)
                            return suspended
                        session.add_observation(action, observation)
                        self._persist_summary(session, current_mode, assembly)
                        if on_tool_finish is not None:
                            on_tool_finish(action, observation)
                        loop_guard.record(action, observation)
                        if loop_guard.should_block(action) or loop_guard.should_stop():
                            transition = LoopTransition(reason="guard_stop", message=loop_guard.stop_reason(), turns_used=turns_used)
                            session.record_transition(transition)
                            if on_step_finish is not None:
                                on_step_finish(step_index, reply, "guard_stop")
                            return QueryTurnResult(final_text, session, transition, turns_used)
                    continue
                for update in executor.run_batch(batch):
                    if update.phase == "start":
                        session.record_tool_call(update.action)
                        if on_tool_start is not None:
                            on_tool_start(update.action)
                        continue
                    observation, current_mode, suspended = self._execute_action(
                        session,
                        update.action,
                        current_mode,
                        permission_handler,
                        user_input_handler,
                        update.observation,
                    )
                    if suspended is not None:
                        self._persist_summary(session, current_mode, assembly)
                        if on_step_finish is not None:
                            on_step_finish(step_index, reply, suspended.transition.reason)
                        return suspended
                    session.add_observation(update.action, observation)
                    self._persist_summary(session, current_mode, assembly)
                    if on_tool_finish is not None:
                        on_tool_finish(update.action, observation)
                    loop_guard.record(update.action, observation)
                    if loop_guard.should_block(update.action) or loop_guard.should_stop():
                        transition = LoopTransition(reason="guard_stop", message=loop_guard.stop_reason(), turns_used=turns_used)
                        session.record_transition(transition)
                        if on_step_finish is not None:
                            on_step_finish(step_index, reply, "guard_stop")
                        return QueryTurnResult(final_text, session, transition, turns_used)
            if on_step_finish is not None:
                on_step_finish(step_index, reply, "tool_calls")
        transition = LoopTransition(reason="max_turns", message="超过最大迭代次数", turns_used=turns_used)
        session.record_transition(transition)
        return QueryTurnResult(final_text, session, transition, turns_used)

    def _build_context(self, session: Session, mode_name: str, workflow_state: str, force_compact: bool = False) -> ContextAssemblyResult:
        build = self.context_manager.build_messages(
            session,
            mode_name,
            tools=self.tools,
            workflow_state=workflow_state,
            intelligence_broker=self.intelligence_broker,
            force_compact=force_compact,
        )
        if isinstance(build, ContextAssemblyResult):
            return build
        return ContextAssemblyResult(
            messages=build.messages,
            used_chars=build.used_chars,
            approx_tokens=build.approx_tokens,
            compacted=build.compacted,
            summarized_turns=build.summarized_turns,
            recent_turns=build.recent_turns,
            policy=build.policy,
            budget=build.budget,
            stats=build.stats,
            summary_message=getattr(build, "summary_message", ""),
            intelligence_sections=getattr(build, "intelligence_sections", []),
            analysis=getattr(build, "analysis", {}),
            replacements=getattr(build, "replacements", []),
            pipeline_steps=getattr(build, "pipeline_steps", []),
        )

    def _should_retry_with_compact(self, exc: ModelClientError) -> bool:
        text = str(exc or "").lower()
        if not text:
            return False
        for marker in _COMPACT_RETRY_ERROR_MARKERS:
            if marker in text:
                return True
        return False

    def _schemas_for_mode(self, mode_name: str, workflow_state: str) -> list:
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
        session: Session,
        action: Action,
        current_mode: str,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
        precomputed_observation: Optional[Observation] = None,
    ) -> Tuple[Observation, str, Optional[QueryTurnResult]]:
        runtime_action = action
        if action.name == "manage_todos" and not action.arguments.get("session_id"):
            runtime_action = Action(action.name, dict(action.arguments, session_id=session.session_id), action.call_id, action.raw_arguments)
        if not is_tool_allowed(current_mode, action.name) and action.name not in ("ask_user", "propose_mode_switch"):
            return self._failure_observation(action.name, "当前模式 %s 不允许调用工具 %s。" % (current_mode, action.name), "mode_tool_blocked", False, current_mode, "请改用当前模式允许的工具。"), current_mode, None
        if action.name == "ask_user":
            request = build_user_input_request(action.arguments)
            response = user_input_handler(request) if user_input_handler is not None else None
            if response is None:
                pending = PendingInteraction(
                    kind="user_input",
                    tool_name="ask_user",
                    request_payload={
                        "action": {"name": action.name, "arguments": dict(action.arguments), "call_id": action.call_id},
                        "request": {
                            "tool_name": request.tool_name,
                            "question": request.question,
                            "options": [{"index": item.index, "text": item.text, "mode": item.mode} for item in request.options],
                            "details": dict(request.details),
                        },
                    },
                )
                transition = LoopTransition("user_input_wait", request.question, pending, current_mode)
                session.record_transition(transition)
                return self._failure_observation("ask_user", "waiting user input", "pending_interaction", False, "user_input", "等待用户回答。", {"pending": True}), current_mode, QueryTurnResult("", session, transition, pending_interaction=pending)
            observation, next_mode = self._build_user_input_observation(session, current_mode, request, response)
            return observation, next_mode, None
        if action.name == "propose_mode_switch":
            response = user_input_handler(
                UserInputRequest("propose_mode_switch", str(action.arguments.get("reason") or ""), [], {"target_mode": str(action.arguments.get("target_mode") or "")})
            ) if user_input_handler is not None else None
            if response is None:
                pending = PendingInteraction(
                    kind="user_input",
                    tool_name="propose_mode_switch",
                    request_payload={"action": {"name": action.name, "arguments": dict(action.arguments), "call_id": action.call_id}},
                )
                transition = LoopTransition("user_input_wait", str(action.arguments.get("reason") or ""), pending, current_mode)
                session.record_transition(transition)
                return self._failure_observation(action.name, "waiting user input", "pending_interaction", False, "user_input", "等待用户回答。", {"pending": True}), current_mode, QueryTurnResult("", session, transition, pending_interaction=pending)
            target_mode = str(response.selected_mode or action.arguments.get("target_mode") or "").strip()
            if target_mode:
                target_mode = str(require_mode(target_mode)["slug"])
                if target_mode != current_mode:
                    session.add_system_message(build_system_prompt(target_mode, getattr(self.tools, "app_config", None), getattr(self.tools, "workspace", "")))
                    current_mode = target_mode
            return Observation("propose_mode_switch", True, None, {"selected_mode": target_mode, "mode_changed": bool(target_mode)}), current_mode, None
        decision = self.permission_policy.evaluate(runtime_action)
        if decision.outcome == "deny":
            return self._failure_observation(action.name, decision.error or "权限规则拒绝该操作。", "permission_denied", False, "permission_policy", "修改权限规则，或由用户手动放行后重试。", {"permission_required": True, "permission_decision": "deny"}), current_mode, None
        if decision.request is not None:
            approved = permission_handler(decision.request) if permission_handler is not None else None
            if approved is None:
                pending = PendingInteraction(
                    kind="permission",
                    tool_name=action.name,
                    request_payload={
                        "action": {"name": action.name, "arguments": dict(runtime_action.arguments), "call_id": runtime_action.call_id},
                        "permission": {"tool_name": decision.request.tool_name, "category": decision.request.category, "reason": decision.request.reason, "details": dict(decision.request.details)},
                    },
                )
                transition = LoopTransition("permission_wait", decision.request.reason, pending, current_mode)
                session.record_transition(transition)
                return self._failure_observation(action.name, "waiting permission", "pending_interaction", False, "permission", "等待用户批准。", {"pending": True}), current_mode, QueryTurnResult("", session, transition, pending_interaction=pending)
            if not approved:
                return self._failure_observation(action.name, "操作未获批准，已跳过执行。", "permission_denied", False, "user_confirmation", "等待用户批准，或改为不需要该权限的方案。", {"permission_required": True, "permission_decision": "deny"}), current_mode, None
        if action.name in ("edit_file", "write_file"):
            path = str(runtime_action.arguments.get("path") or "")
            if not path:
                return self._failure_observation(action.name, "%s 缺少 path 参数。" % action.name, "invalid_arguments", False, "arguments", "补充一个相对于工作区的 path 参数。"), current_mode, None
            if not is_path_writable(current_mode, path.replace("\\", "/"), getattr(self.tools, "app_config", None)):
                return self._failure_observation(action.name, "当前模式 %s 不允许修改 %s。" % (current_mode, path.replace("\\", "/")), "mode_path_blocked", False, current_mode, "请改用当前模式允许的文件类型，或切换模式。"), current_mode, None
            if action.name == "edit_file":
                try:
                    resolved_path = self.tools._ctx.resolve_path(path.replace("\\", "/"), allow_missing=True)
                except ToolError as exc:
                    return self._failure_observation(action.name, str(exc), "path_invalid", False, "workspace", "改用工作区内的相对路径。"), current_mode, None
                if not resolved_path or not os.path.exists(resolved_path):
                    return self._failure_observation(action.name, "目标文件不存在，edit_file 只能修改已存在的文件。", "file_missing", False, "filesystem", "若要新建文件，请改用 write_file。"), current_mode, None
        return precomputed_observation or self.tools.execute(runtime_action.name, runtime_action.arguments), current_mode, None

    def _build_user_input_observation(self, session: Session, current_mode: str, request: UserInputRequest, response: UserInputResponse) -> Tuple[Observation, str]:
        selected_mode = str(response.selected_mode or "").strip()
        next_mode = current_mode
        mode_changed = False
        if selected_mode:
            selected_mode = str(require_mode(selected_mode)["slug"])
            if selected_mode != current_mode:
                next_mode = selected_mode
                mode_changed = True
                session.add_system_message(build_system_prompt(selected_mode, getattr(self.tools, "app_config", None), getattr(self.tools, "workspace", "")))
        return Observation(
            "ask_user",
            True,
            None,
            {
                "question": request.question,
                "answer": str(response.answer or "").strip(),
                "selected_index": response.selected_index,
                "selected_option_text": response.selected_option_text,
                "selected_mode": selected_mode,
                "mode_changed": mode_changed,
            },
        ), next_mode

    def _resume_interaction(
        self,
        session: Session,
        pending: PendingInteraction,
        current_mode: str,
        resolution: Dict[str, Any],
        on_tool_start: Optional[Callable[[Action], None]],
        on_tool_finish: Optional[Callable[[Action, Observation], None]],
    ) -> str:
        session.resolve_pending_interaction(resolution)
        action_payload = pending.request_payload.get("action") if isinstance(pending.request_payload, dict) else {}
        action = Action(
            name=str(action_payload.get("name") or pending.tool_name),
            arguments=dict(action_payload.get("arguments") or {}),
            call_id=str(action_payload.get("call_id") or ("call-" + pending.interaction_id)),
        )
        if on_tool_start is not None:
            on_tool_start(action)
        if pending.kind == "permission":
            approved = bool(resolution.get("approved"))
            observation = self.tools.execute(action.name, action.arguments) if approved else self._failure_observation(action.name, "操作未获批准，已跳过执行。", "permission_denied", False, "user_confirmation", "等待用户批准，或改为不需要该权限的方案。")
        else:
            req = pending.request_payload.get("request") if isinstance(pending.request_payload, dict) else {}
            request = UserInputRequest(
                tool_name=str(req.get("tool_name") or pending.tool_name),
                question=str(req.get("question") or ""),
                options=[],
                details=dict(req.get("details") or {}),
            )
            response = UserInputResponse(
                answer=str(resolution.get("answer") or ""),
                selected_index=resolution.get("selected_index"),
                selected_mode=str(resolution.get("selected_mode") or ""),
                selected_option_text=str(resolution.get("selected_option_text") or ""),
            )
            observation, current_mode = self._build_user_input_observation(session, current_mode, request, response)
        session.add_observation(action, observation)
        if on_tool_finish is not None:
            on_tool_finish(action, observation)
        return current_mode

    def _call_llm_with_retry(self, messages: list, tool_schemas: list, stream: bool, on_text_delta: Optional[Callable[[str], None]], on_reasoning_delta: Optional[Callable[[str], None]]) -> AssistantReply:
        last_exc = None
        for attempt in range(_LLM_MAX_RETRIES):
            try:
                if stream:
                    return self.client.stream(messages, tools=tool_schemas, on_text_delta=on_text_delta, on_reasoning_delta=on_reasoning_delta)
                reply = self.client.generate(messages, tools=tool_schemas)
                if on_reasoning_delta and reply.reasoning_content:
                    on_reasoning_delta(reply.reasoning_content)
                if on_text_delta and reply.content:
                    on_text_delta(reply.content)
                return reply
            except ModelClientError as exc:
                last_exc = exc
                if not any(str(code) in str(exc) for code in _RETRYABLE_HTTP_CODES) or attempt >= _LLM_MAX_RETRIES - 1:
                    raise
                delay = _LLM_RETRY_BASE_DELAY * (2 ** attempt)
                _LOG.warning("LLM call failed (attempt %d/%d), retrying in %.1fs: %s", attempt + 1, _LLM_MAX_RETRIES, delay, exc)
                time.sleep(delay)
        raise last_exc  # type: ignore[misc]

    def _persist_summary(self, session: Session, current_mode: str, assembly: Optional[ContextAssemblyResult] = None) -> None:
        summary_ref = None
        try:
            summary_ref = self.summary_store.persist(session, current_mode, assembly)
        except Exception as exc:
            _LOG.warning("session summary persist failed: %s", exc)
        try:
            self.project_memory_store.refresh(session, current_mode, summary_ref)
        except Exception as exc:
            _LOG.warning("project memory refresh failed: %s", exc)
        try:
            session.trim_old_observations(30)
        except Exception as exc:
            _LOG.warning("session trim failed: %s", exc)
        self._maybe_maintain_memory()

    def _maybe_record_compact_boundary(self, session: Session, current_mode: str, assembly: ContextAssemblyResult) -> None:
        if not assembly.compacted or not assembly.summary_message or assembly.summarized_turns <= 0:
            return
        compacted_turn_count = max(0, len(session.turns) - assembly.recent_turns)
        latest = session.latest_compact_boundary()
        if latest is not None and latest.compacted_turn_count == compacted_turn_count:
            return
        session.add_compact_boundary(
            assembly.summary_message,
            compacted_turn_count,
            current_mode,
            {
                "approx_tokens": assembly.approx_tokens,
                "replacements": len(assembly.replacements),
                "pipeline_steps": list(assembly.pipeline_steps),
            },
        )

    def _maybe_maintain_memory(self, force: bool = False) -> None:
        self._maintenance_counter += 1
        if not force and self._maintenance_counter < self.maintenance_interval:
            return
        self._maintenance_counter = 0
        try:
            self.memory_maintenance.run()
        except Exception as exc:
            _LOG.warning("memory maintenance failed: %s", exc)

    def _failure_observation(self, tool_name: str, error: str, error_kind: str, retryable: bool, blocked_by: str, suggested_next_step: str, extra_data: Optional[Dict[str, Any]] = None) -> Observation:
        data = {"error_kind": error_kind, "retryable": retryable, "blocked_by": blocked_by, "suggested_next_step": suggested_next_step}
        if extra_data:
            data.update(extra_data)
        return Observation(tool_name, False, error, data)


def to_loop_result(result: QueryTurnResult) -> LoopResult:
    mapping = {
        "completed": "completed",
        "aborted": "cancelled",
        "guard_stop": "guard",
        "max_turns": "max_turns",
        "permission_wait": "completed",
        "user_input_wait": "completed",
    }
    return LoopResult(
        final_text=result.final_text,
        session=result.session,
        termination_reason=mapping.get(result.transition.reason, "error"),
        error=result.transition.message or None,
        turns_used=result.turns_used,
    )
