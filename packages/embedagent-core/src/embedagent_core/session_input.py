from __future__ import annotations  # noqa: I001

import logging
import threading
from contextlib import contextmanager
import uuid
from typing import Any, Callable, Dict, Optional, Tuple

from embedagent_core.agent_effects import (
    AssembleContextEffect,
    ExecuteToolBatchEffect,
    InteractionSuspended,
    ToolBatchCompleted,
)
from embedagent_core.agent_extension_host import AgentExtensionHost
from embedagent_core.agent_kernel import AgentKernel
from embedagent_core.agent_lifecycle import AgentLifecycleJournal
from embedagent_core.agent_loop import AgentLoop
from embedagent_core.agent_tool_action_service import (
    AgentToolActionService,
)
from embedagent_core.compaction_journal import CompactionJournal
from embedagent_core.interaction import (
    UserInputRequest,
    UserInputResponse,
)
from embedagent_core.strategies.execution_tracer import ExecutionTracer, TraceEventType
from embedagent_core.permissions import PermissionPolicy, PermissionRequest
from embedagent_core.policies import (
    DenyWritePathPolicy,
    EmptyModeToolPolicy,
    ModeRuntimePolicy,
    ModeToolPolicy,
    NeutralModeRuntimePolicy,
    WritePathPolicy,
)
from embedagent_core.ports import (
    ContextAssemblerPort,
    NoopContextAssembler,
    NoopSessionProjection,
    SessionProjectionPort,
)
from embedagent_core.prompt_assembly_service import PromptAssemblyService
from embedagent_core.provider_step_service import ProviderStepService
from embedagent_core.session import (
    Action,
    AssistantReply,
    ContextAssemblyResult,
    LoopTransition,
    Observation,
    PendingInteraction,
    QueryTurnResult,
    Session,
    ToolPresentationSnapshot,
)
from embedagent_core.session_log import InMemorySessionLog, SessionLogPort
from embedagent_core.session_journal import EventIntent, SessionJournal
from embedagent_core.session_reducer import (
    SessionReducerContext,
)
from embedagent_core.tool_contracts import ToolRuntimePort
from embedagent_core.turn_snapshot import TurnSnapshot

_LOG = logging.getLogger(__name__)
_OPERATION_RUNTIME_ERRORS = (OSError, RuntimeError, ValueError, TypeError, KeyError, AttributeError)


class SessionEventCommitter(object):
    """Bind one reducer context while committing events for a session transaction."""

    _MESSAGE_EVENT_TYPES = ("message", "user", "assistant", "system", "tool", "tool_result")

    def __init__(self, session_log: SessionLogPort, journal: SessionJournal) -> None:
        self._session_log = session_log
        self._journal = journal
        self._local = threading.local()
        self._lock = threading.RLock()
        self._durable_message_ids = {}  # type: Dict[str, set]

    @contextmanager
    def bind(self, reduction_context: SessionReducerContext):
        previous = getattr(self._local, "reduction_context", None)
        self._local.reduction_context = reduction_context
        try:
            yield
        finally:
            if previous is None:
                del self._local.reduction_context
            else:
                self._local.reduction_context = previous

    def reduction_context(self) -> SessionReducerContext:
        context = getattr(self._local, "reduction_context", None)
        if context is None:
            raise RuntimeError("session reduction context is not bound")
        return context

    def guard(self):
        return self._lock

    def append_raw(
        self,
        session: Session,
        event_type: str,
        payload: Dict[str, Any],
        schema_version: int = 2,
    ) -> None:
        event_payload, durable_ids = self._prepare_message_payload(session, event_type, payload)
        self._session_log.append_event(
            session.session_id,
            event_type,
            event_payload,
            schema_version=schema_version,
        )
        self._remember_message_id(event_type, event_payload, durable_ids)

    def commit(
        self,
        session: Session,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        event_payload, durable_ids = self._prepare_message_payload(session, event_type, payload)
        result = self._journal.commit(
            session,
            self.reduction_context(),
            (EventIntent(event_type, event_payload),),
        )
        self._remember_message_id(event_type, event_payload, durable_ids)
        return result.events[-1]

    def _prepare_message_payload(self, session, event_type, payload):
        event_payload = dict(payload or {})
        durable_ids = set()
        if event_type in self._MESSAGE_EVENT_TYPES:
            durable_ids = self._durable_ids_for(session)
            parent_message_id = str(event_payload.get("parent_message_id") or "")
            if parent_message_id and parent_message_id not in durable_ids:
                event_payload["parent_message_id"] = self._durable_parent_message_id(
                    session, parent_message_id, durable_ids
                )
        return event_payload, durable_ids

    def _remember_message_id(self, event_type, payload, durable_ids):
        if event_type not in self._MESSAGE_EVENT_TYPES:
            return
        message_id = str(payload.get("message_id") or "")
        if message_id:
            durable_ids.add(message_id)

    def _durable_ids_for(self, session: Session) -> set:
        session_id = str(session.session_id or "")
        cached = self._durable_message_ids.get(session_id)
        if cached is not None:
            return cached
        message_ids = set()
        if self._session_log.transcript_exists(session_id):
            for event in self._session_log.load_events(session_id):
                if str(event.get("type") or "") not in self._MESSAGE_EVENT_TYPES:
                    continue
                message_id = str(dict(event.get("payload") or {}).get("message_id") or "")
                if message_id:
                    message_ids.add(message_id)
        self._durable_message_ids[session_id] = message_ids
        return message_ids

    def _durable_parent_message_id(self, session, parent_message_id, durable_ids):
        candidate = str(parent_message_id or "")
        visited = set()
        while candidate and candidate not in visited:
            if candidate in durable_ids:
                return candidate
            visited.add(candidate)
            message = next(
                (
                    item
                    for item in session.messages
                    if str(getattr(item, "message_id", "") or "") == candidate
                ),
                None,
            )
            if message is None:
                return ""
            candidate = str(getattr(message, "parent_message_id", "") or "")
        return ""


class SessionInputDispatcher(object):
    def __init__(
        self,
        tools: ToolRuntimePort,
        event_committer: SessionEventCommitter,
        lifecycle: AgentLifecycleJournal,
        kernel: AgentKernel,
        agent_loop: AgentLoop,
        provider_steps: ProviderStepService,
        action_service: AgentToolActionService,
        extension_host: AgentExtensionHost,
        prompt_assembly: PromptAssemblyService,
        max_turns: Optional[int] = None,
        permission_policy: Optional[PermissionPolicy] = None,
        context_manager: Optional[ContextAssemblerPort] = None,
        session_projection: Optional[SessionProjectionPort] = None,
        max_parallel_tools: int = 3,
        transcript_store: Optional[SessionLogPort] = None,
        tracer: Optional[ExecutionTracer] = None,
        mode_tool_policy: Optional[ModeToolPolicy] = None,
        write_path_policy: Optional[WritePathPolicy] = None,
        mode_runtime_policy: Optional[ModeRuntimePolicy] = None,
    ) -> None:
        self.tools = tools
        self.max_turns = max_turns
        self.permission_policy = permission_policy or PermissionPolicy()
        self.context_manager = context_manager or NoopContextAssembler()
        self.session_projection = session_projection or NoopSessionProjection()
        self._compaction_journal = CompactionJournal()
        self.max_parallel_tools = max(1, int(max_parallel_tools or 1))
        self.transcript_store = transcript_store or InMemorySessionLog()
        self.tracer = tracer
        self._mode_tool_policy = mode_tool_policy or EmptyModeToolPolicy()
        self._write_path_policy = write_path_policy or DenyWritePathPolicy()
        self._mode_runtime_policy = mode_runtime_policy or NeutralModeRuntimePolicy()
        self._event_committer = event_committer
        self.lifecycle = lifecycle
        self.kernel = kernel
        self._agent_loop = agent_loop
        self._provider_steps = provider_steps
        self._action_service = action_service
        self.extension_host = extension_host
        self.extension_manager = self.extension_host.manager
        self._prompt_assembly = prompt_assembly

    def last_turn_snapshot(self) -> Optional[TurnSnapshot]:
        return self._provider_steps.last_snapshot()

    @property
    def _reduction_context(self) -> SessionReducerContext:
        return self._event_committer.reduction_context()

    def _session_guard(self):
        return self._event_committer.guard()

    def _append_transcript_event(
        self, session: Session, event_type: str, payload: Dict[str, Any], schema_version: int = 2
    ) -> None:
        self._event_committer.append_raw(session, event_type, payload, schema_version)

    def _commit_session_event(
        self,
        session: Session,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._event_committer.commit(session, event_type, payload)

    def _emit_operation_started(
        self,
        session: Session,
        operation_id: str,
        kind: str,
        turn_id: str = "",
        step_id: str = "",
        tool_call_id: str = "",
        parent_operation_id: str = "",
        retryable: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.lifecycle.emit_operation_started(
            session,
            operation_id,
            kind,
            turn_id=turn_id,
            step_id=step_id,
            tool_call_id=tool_call_id,
            parent_operation_id=parent_operation_id,
            retryable=retryable,
            metadata=metadata,
        )

    def _turn_id(self, session: Session) -> str:
        return self.lifecycle.turn_id(session)

    def _append_message_event(self, session: Session, payload: Dict[str, Any]) -> None:
        event_type = str(payload.get("role") or "message")
        self._commit_session_event(session, event_type, payload)

    def _tool_presentation_snapshot(self, tool_name: str) -> ToolPresentationSnapshot:
        lookup = getattr(self.tools, "tool_catalog_entry", None)
        if not callable(lookup):
            return ToolPresentationSnapshot(tool_label=tool_name)
        entry = lookup(tool_name) or {}
        if not isinstance(entry, dict):
            return ToolPresentationSnapshot(tool_label=tool_name)
        return ToolPresentationSnapshot(
            tool_label=str(entry.get("user_label") or tool_name),
            permission_category=str(entry.get("permission_category") or ""),
            supports_diff_preview=bool(entry.get("supports_diff_preview")),
            progress_renderer_key=str(entry.get("progress_renderer_key") or "default"),
            result_renderer_key=str(entry.get("result_renderer_key") or "default"),
        )

    def _message_event_payload(self, message: Any) -> Dict[str, Any]:
        payload = {
            "role": str(getattr(message, "role", "") or ""),
            "content": str(getattr(message, "content", "") or ""),
            "message_id": str(getattr(message, "message_id", "") or ""),
            "parent_message_id": str(getattr(message, "parent_message_id", "") or ""),
            "turn_id": str(getattr(message, "turn_id", "") or ""),
            "step_id": str(getattr(message, "step_id", "") or ""),
            "kind": str(getattr(message, "kind", "message") or "message"),
            "metadata": dict(getattr(message, "metadata", {}) or {}),
            "replaced_by_refs": list(getattr(message, "replaced_by_refs", []) or []),
        }
        name = str(getattr(message, "name", "") or "")
        if name:
            payload["tool_name"] = name
        tool_call_id = str(getattr(message, "tool_call_id", "") or "")
        if tool_call_id:
            payload["tool_call_id"] = tool_call_id
        actions = []
        for action in list(getattr(message, "action_calls", []) or []):
            actions.append(
                {
                    "name": str(getattr(action, "name", "") or ""),
                    "arguments": dict(getattr(action, "arguments", {}) or {}),
                    "call_id": str(getattr(action, "call_id", "") or ""),
                }
            )
        if actions:
            payload["actions"] = actions
        reasoning_content = str(getattr(message, "reasoning_content", "") or "")
        if reasoning_content:
            payload["reasoning_content"] = reasoning_content
        return payload

    def _ensure_transcript_bootstrap(self, session: Session, current_mode: str) -> None:
        if self.transcript_store is None:
            return
        if self.transcript_store.transcript_exists(session.session_id):
            return
        with self._session_guard():
            self._append_transcript_event(
                session,
                "session_meta",
                {
                    "current_mode": current_mode,
                    "started_at": session.started_at,
                    "workspace": self.tools.workspace,
                },
            )
            step_records = {}
            for turn in list(getattr(session, "turns", []) or []):
                turn_id = str(getattr(turn, "turn_id", "") or "")
                for step in list(getattr(turn, "steps", []) or []):
                    step_id = str(getattr(step, "step_id", "") or "")
                    if not step_id:
                        continue
                    step_records[(turn_id, step_id)] = {
                        "turn_id": turn_id,
                        "step_id": step_id,
                        "step_index": int(getattr(step, "step_index", 0) or 0),
                        "reasoning": str(getattr(step, "reasoning", "") or ""),
                    }
            emitted_steps = set()
            for message in list(getattr(session, "messages", []) or []):
                message_turn_id = str(getattr(message, "turn_id", "") or "")
                message_step_id = str(getattr(message, "step_id", "") or "")
                step_key = (message_turn_id, message_step_id)
                if message_step_id and step_key not in emitted_steps:
                    self._append_transcript_event(
                        session,
                        "step_started",
                        step_records.get(
                            step_key,
                            {
                                "turn_id": message_turn_id,
                                "step_id": message_step_id,
                                "step_index": 0,
                                "reasoning": "",
                            },
                        ),
                    )
                    emitted_steps.add(step_key)
                payload = self._message_event_payload(message)
                self._append_transcript_event(
                    session, str(payload.get("role") or "message"), payload
                )
            for boundary in list(getattr(session, "compact_boundaries", []) or []):
                boundary_metadata = dict(getattr(boundary, "metadata", {}) or {})
                self._append_transcript_event(
                    session,
                    "compact_boundary",
                    {
                        "boundary_id": str(getattr(boundary, "boundary_id", "") or ""),
                        "summary_text": str(getattr(boundary, "summary_text", "") or ""),
                        "compacted_turn_count": int(
                            getattr(boundary, "compacted_turn_count", 0) or 0
                        ),
                        "created_at": str(getattr(boundary, "created_at", "") or ""),
                        "mode_name": str(getattr(boundary, "mode_name", "") or ""),
                        "preserved_head_message_id": str(
                            getattr(boundary, "preserved_head_message_id", "") or ""
                        ),
                        "preserved_tail_message_id": str(
                            getattr(boundary, "preserved_tail_message_id", "") or ""
                        ),
                        "trigger": str(boundary_metadata.get("trigger") or ""),
                        "phase": str(boundary_metadata.get("phase") or ""),
                        "context_window_generation": int(
                            boundary_metadata.get("context_window_generation") or 0
                        ),
                        "metadata": boundary_metadata,
                    },
                )

    def _ensure_extension_tools_registered(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        reason: str = "turn",
    ) -> None:
        self.extension_host.register_tools(session, current_mode, workflow_state, reason=reason)

    def _build_system_prompt(self, mode_name: str) -> str:
        resources = {}
        local_resources = getattr(self.tools, "local_resources", None)
        if callable(local_resources):
            resources = local_resources()
        return self._mode_runtime_policy.build_system_prompt(
            mode_name,
            getattr(self.tools, "app_config", None),
            getattr(self.tools, "workspace", ""),
            local_resources=resources,
        )

    def _require_mode_slug(self, mode_name: str) -> str:
        mode = self._mode_runtime_policy.require_mode(
            str(mode_name or self._mode_runtime_policy.default_mode())
        )
        return str(mode.get("slug") or mode_name or self._mode_runtime_policy.default_mode())

    def _system_message_event_payload(
        self,
        session: Session,
        content: str,
        kind: str = "message",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        current_step = session.current_step()
        return {
            "role": "system",
            "content": str(content or ""),
            "message_id": "m-" + uuid.uuid4().hex[:12],
            "parent_message_id": session.last_message_id(),
            "turn_id": session.turns[-1].turn_id if session.turns else "",
            "step_id": current_step.step_id if current_step is not None else "",
            "kind": str(kind or "message"),
            "metadata": dict(metadata or {}),
            "replaced_by_refs": [],
        }

    def initialize_session(
        self, session: Session, initial_mode: str, workflow_state: str = "", user_text: str = ""
    ) -> str:
        current_mode = self._require_mode_slug(initial_mode)
        self._reduction_context.current_mode = current_mode
        self._ensure_extension_tools_registered(
            session,
            current_mode,
            workflow_state,
            reason="session_start",
        )
        if session.messages:
            self._ensure_transcript_bootstrap(session, current_mode)
            with self._session_guard():
                self._prompt_assembly.append_described_workflow_prompt(
                    self.extension_host,
                    session,
                    current_mode,
                    workflow_state,
                    lambda payload: self._append_message_event(session, payload),
                    user_text=user_text,
                )
            return current_mode
        with self._session_guard():
            self._commit_session_event(
                session,
                "session_meta",
                {
                    "current_mode": current_mode,
                    "started_at": session.started_at,
                    "workspace": self.tools.workspace,
                },
            )
            for initial_text in self.context_manager.initial_system_messages(
                session,
                current_mode,
                workflow_state,
            ):
                if str(initial_text or "").strip():
                    self._append_message_event(
                        session,
                        self._system_message_event_payload(session, initial_text),
                    )
            system_prompt = self._build_system_prompt(current_mode)
            if str(system_prompt or "").strip():
                self._append_message_event(
                    session,
                    self._system_message_event_payload(session, system_prompt),
                )
            self._prompt_assembly.append_described_workflow_prompt(
                self.extension_host,
                session,
                current_mode,
                workflow_state,
                lambda payload: self._append_message_event(session, payload),
                user_text=user_text,
            )
        return current_mode

    def apply_mode(
        self, session: Session, next_mode: str, workflow_state: str = "", user_text: str = ""
    ) -> str:
        current_mode = self._require_mode_slug(next_mode)
        self._reduction_context.current_mode = current_mode
        with self._session_guard():
            mode_prompt = self._build_system_prompt(current_mode)
            if str(mode_prompt or "").strip():
                self._append_message_event(
                    session,
                    self._system_message_event_payload(session, mode_prompt),
                )
            self._prompt_assembly.append_described_workflow_prompt(
                self.extension_host,
                session,
                current_mode,
                workflow_state,
                lambda payload: self._append_message_event(session, payload),
                user_text=user_text,
            )
        return current_mode

    def _record_transition(self, session: Session, transition: LoopTransition) -> None:
        self.lifecycle.record_transition(session, transition)

    def record_command_result(
        self,
        session: Session,
        user_text: str,
        command_name: str,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        turn_id: str = "",
        step_id: str = "",
        step_index: int = 0,
    ) -> None:
        command_turn_id = str(turn_id or "").strip()
        with self._session_guard():
            if command_turn_id and (
                not session.turns or str(session.turns[-1].turn_id or "") != command_turn_id
            ):
                self._append_message_event(
                    session,
                    {
                        "role": "user",
                        "content": user_text or ("/%s" % command_name),
                        "message_id": "m-" + uuid.uuid4().hex[:12],
                        "parent_message_id": session.last_message_id(),
                        "turn_id": command_turn_id,
                        "step_id": "",
                    },
                )
            transition = LoopTransition(
                reason="command_result",
                message=str(message or ""),
                metadata={
                    "command_name": str(command_name or ""),
                    "success": bool(success),
                    "data": dict(data or {}),
                    "turn_id": command_turn_id,
                    "step_id": str(step_id or ""),
                    "step_index": int(step_index or 0),
                },
            )
        self._record_transition(session, transition)

    def _parse_mode_switch_request(
        self, user_text: str, fallback_mode: str
    ) -> Tuple[str, str, bool]:
        return self._mode_runtime_policy.parse_mode_switch_request(user_text, fallback_mode)

    def _append_user_turn_message(self, session: Session, user_text: str, turn_id: str) -> None:
        with self._session_guard():
            message_id = "m-" + uuid.uuid4().hex[:12]
            parent_message_id = session.last_message_id()
            self._append_message_event(
                session,
                {
                    "role": "user",
                    "content": user_text,
                    "message_id": message_id,
                    "parent_message_id": parent_message_id,
                    "turn_id": turn_id,
                    "step_id": "",
                },
            )

    def _finish_mode_switch_turn(
        self,
        session: Session,
        turn_id: str,
        source_mode: str,
        target_mode: str,
    ) -> QueryTurnResult:
        applied_mode = self._require_mode_slug(target_mode)
        message_text = "已切换到 `%s` 模式。" % applied_mode
        reply = AssistantReply(content=message_text, actions=[], finish_reason="mode_changed")
        with self._session_guard():
            step_id = "s-" + uuid.uuid4().hex[:12]
            step_index = len(session.turns[-1].steps) + 1 if session.turns else 1
            self._commit_session_event(
                session,
                "step_started",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "step_index": step_index,
                },
            )
            self._emit_operation_started(
                session,
                "step:%s" % step_id,
                "agent_step",
                turn_id=turn_id,
                step_id=step_id,
                metadata={"step_index": step_index},
            )
            message_id = "m-" + uuid.uuid4().hex[:12]
            parent_message_id = session.last_message_id()
            self._append_message_event(
                session,
                {
                    "role": "assistant",
                    "content": reply.content,
                    "message_id": message_id,
                    "parent_message_id": parent_message_id,
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "actions": [],
                    "reasoning_content": "",
                    "finish_reason": reply.finish_reason,
                },
            )
        transition = LoopTransition(
            reason="mode_changed",
            message=message_text,
            next_mode=applied_mode,
            turns_used=1,
            metadata={
                "source_mode": source_mode,
                "target_mode": applied_mode,
                "command": "mode",
            },
        )
        self._record_transition(session, transition)
        self._persist_summary(session, applied_mode)
        return QueryTurnResult(message_text, session, transition, turns_used=1)

    def _interrupted_observation(self, tool_name: str) -> Observation:
        return Observation(
            tool_name=tool_name,
            success=False,
            error="tool execution interrupted",
            data={
                "error_kind": "interrupted",
                "retryable": False,
                "blocked_by": "user_cancelled",
                "suggested_next_step": "用户取消了当前会话；如需继续，请恢复会话或重新提交请求。",
                "synthetic": True,
            },
        )

    def _record_tool_observation(
        self,
        session: Session,
        action: Action,
        observation: Observation,
        current_mode: str,
        assembly: ContextAssemblyResult,
        step_id: str,
        on_tool_finish: Optional[Callable[[Action, Observation], None]],
    ) -> Observation:
        del step_id
        self._persist_summary(session, current_mode, assembly)
        if on_tool_finish is not None:
            on_tool_finish(action, observation)
        return observation

    def submit_user_turn(
        self,
        user_text: str,
        stream: bool = True,
        initial_mode: str = "",
        workflow_state: str = "",
        session: Optional[Session] = None,
        stop_event: Optional[threading.Event] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[Callable[[Action, Observation], None]] = None,
        on_context_result: Optional[Callable[[ContextAssemblyResult], None]] = None,
        on_step_start: Optional[Callable[[str, int], None]] = None,
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]] = None,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]] = None,
        user_input_handler: Optional[
            Callable[[UserInputRequest], Optional[UserInputResponse]]
        ] = None,
    ) -> QueryTurnResult:
        if session is None:
            with self._session_guard():
                session = Session()
        session_was_empty = not bool(session.messages)
        original_user_text = user_text
        source_mode = self._require_mode_slug(initial_mode)
        target_mode, routed_user_text, mode_switched = self._parse_mode_switch_request(
            user_text,
            source_mode,
        )
        current_mode = self._require_mode_slug(target_mode if mode_switched else source_mode)
        user_text = routed_user_text if mode_switched else user_text
        initialization_user_text = user_text
        if mode_switched and not session_was_empty:
            initialization_user_text = ""
        current_mode = self.initialize_session(
            session, current_mode, workflow_state=workflow_state, user_text=initialization_user_text
        )

        self.extension_host.initialize_workflow_state(
            session,
            user_text=user_text,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )

        turn_id = getattr(session, "current_turn_id", "") or "t-" + uuid.uuid4().hex[:12]
        session_id = getattr(session, "session_id", "") or ""
        turn_frame = self.kernel.begin_turn(session, turn_id, current_mode, workflow_state, "user")

        if self.tracer is not None:
            self.tracer.record(
                TraceEventType.TURN_START,
                session_id,
                turn_id,
                data={"mode": current_mode, "workflow_state": workflow_state},
            )

        if mode_switched and not session_was_empty:
            current_mode = self.apply_mode(
                session,
                current_mode,
                workflow_state=workflow_state,
                user_text=user_text,
            )
            self.extension_host.initialize_workflow_state(
                session,
                user_text=user_text,
                current_mode=current_mode,
                workflow_state=workflow_state,
            )
        visible_user_text = original_user_text if mode_switched and not user_text else user_text
        if visible_user_text:
            self._append_user_turn_message(session, visible_user_text, turn_id)
        if mode_switched:
            if not user_text:
                result = self._finish_mode_switch_turn(
                    session,
                    turn_id,
                    source_mode,
                    current_mode,
                )
                if self.tracer is not None:
                    self.tracer.record(
                        TraceEventType.TURN_END,
                        session_id,
                        turn_id,
                        data={"transition_reason": getattr(result.transition, "reason", "")},
                    )
                    self.tracer.flush()
                turn_frame.finish(result.transition)
                return result
        last_assembly = []

        def capture_context_result(assembly):
            last_assembly[:] = [assembly]
            if on_context_result is not None:
                on_context_result(assembly)

        try:
            result = self._agent_loop.run(
                session=session,
                reduction_context=self._reduction_context,
                turn_id=turn_id,
                current_mode=current_mode,
                workflow_state=workflow_state,
                source="user",
                stream=stream,
                cancel=stop_event,
                max_turns=self.max_turns,
                max_parallel_tools=self.max_parallel_tools,
                on_text_delta=on_text_delta,
                on_reasoning_delta=on_reasoning_delta,
                on_tool_start=on_tool_start,
                on_tool_finish=on_tool_finish,
                on_context_result=capture_context_result,
                on_step_start=on_step_start,
                on_step_finish=on_step_finish,
                permission_handler=permission_handler,
                user_input_handler=user_input_handler,
            )
            self._persist_summary(
                session,
                result.transition.next_mode or current_mode,
                last_assembly[-1] if last_assembly else None,
            )
            if self.tracer is not None:
                self.tracer.record(
                    TraceEventType.TURN_END,
                    session_id,
                    turn_id,
                    data={"transition_reason": getattr(result.transition, "reason", "")},
                )
                self.tracer.flush()
            turn_frame.finish(result.transition)
            return result
        except BaseException as exc:
            turn_frame.interrupt("turn_error", error=str(exc))
            if self.tracer is not None:
                self.tracer.record(
                    TraceEventType.ERROR,
                    session_id,
                    turn_id,
                    data={"error_type": type(exc).__name__, "error_message": str(exc)},
                )
                self.tracer.flush()
            raise

    def submit_command_turn(
        self,
        user_text: str,
        action: Action,
        initial_mode: str,
        workflow_state: str = "command",
        session: Optional[Session] = None,
        turn_id: str = "",
        stop_event: Optional[threading.Event] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[Callable[[Action, Observation], None]] = None,
        on_context_result: Optional[Callable[[ContextAssemblyResult], None]] = None,
        on_step_start: Optional[Callable[[str, int], None]] = None,
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]] = None,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]] = None,
        user_input_handler: Optional[
            Callable[[UserInputRequest], Optional[UserInputResponse]]
        ] = None,
    ) -> Tuple[QueryTurnResult, Optional[Observation]]:
        if session is None:
            with self._session_guard():
                session = Session()
        current_mode = self.initialize_session(
            session, initial_mode, workflow_state=workflow_state, user_text=user_text
        )
        command_turn_id = str(turn_id or ("t-" + uuid.uuid4().hex[:12]))
        turn_frame = self.kernel.begin_turn(
            session, command_turn_id, current_mode, workflow_state, "command"
        )
        with self._session_guard():
            if not session.turns or session.turns[-1].turn_id != command_turn_id:
                message_id = "m-" + uuid.uuid4().hex[:12]
                parent_message_id = session.last_message_id()
                self._append_message_event(
                    session,
                    {
                        "role": "user",
                        "content": user_text or ("/%s" % action.name),
                        "message_id": message_id,
                        "parent_message_id": parent_message_id,
                        "turn_id": command_turn_id,
                        "step_id": "",
                    },
                )
            step_id = "s-" + uuid.uuid4().hex[:12]
            step_index = len(session.turns[-1].steps) + 1
            self._commit_session_event(
                session,
                "step_started",
                {
                    "turn_id": command_turn_id,
                    "step_id": step_id,
                    "step_index": step_index,
                },
            )
            self._emit_operation_started(
                session,
                "step:%s" % step_id,
                "agent_step",
                turn_id=command_turn_id,
                step_id=step_id,
                metadata={"step_index": step_index},
            )
            presentation = self._tool_presentation_snapshot(action.name)
            self._commit_session_event(
                session,
                "tool_call",
                {
                    "turn_id": command_turn_id,
                    "step_id": step_id,
                    "call_id": action.call_id,
                    "tool_name": action.name,
                    "arguments": dict(action.arguments),
                    "status": "pending",
                    "presentation": presentation.to_dict(),
                },
            )
            self._emit_operation_started(
                session,
                "tool:%s" % action.call_id,
                "tool_call",
                turn_id=command_turn_id,
                step_id=step_id,
                tool_call_id=action.call_id,
                parent_operation_id="step:%s" % step_id,
                metadata={
                    "tool_name": action.name,
                    "arguments": dict(action.arguments),
                    "presentation": presentation.to_dict(),
                },
            )
        if on_step_start is not None:
            on_step_start(step_id, step_index)
        context_operation_id = "context:%s:1" % step_id
        self._emit_operation_started(
            session,
            context_operation_id,
            "context_assembly",
            turn_id=command_turn_id,
            step_id=step_id,
            parent_operation_id="step:%s" % step_id,
            metadata={
                "mode_name": current_mode,
                "workflow_state": workflow_state,
                "force_compact": False,
            },
        )
        with self._session_guard():
            context_result = self._provider_steps.assemble_context(
                AssembleContextEffect(
                    context_operation_id,
                    command_turn_id,
                    step_id,
                    current_mode,
                    workflow_state,
                ),
                session,
            )
        with self._session_guard():
            for event in context_result.events:
                self._commit_session_event(session, event.event_type, dict(event.payload))
        assembly = context_result.assembly
        if on_context_result is not None:
            on_context_result(assembly)
        reply = AssistantReply(content="", actions=[action], finish_reason="tool_calls")
        interrupted = bool(stop_event is not None and stop_event.is_set())
        if on_tool_start is not None:
            on_tool_start(action)
        precomputed_observation = (
            self._interrupted_observation(action.name) if interrupted else None
        )
        tool_result = self._action_service.execute(
            ExecuteToolBatchEffect(
                "tools:%s" % action.call_id,
                (action,),
                current_mode,
                workflow_state,
            ),
            session,
            permission_handler=permission_handler,
            user_input_handler=user_input_handler,
            precomputed_observations=(precomputed_observation,),
            stop_event=stop_event,
        )
        with self._session_guard():
            for event in tool_result.events:
                self._commit_session_event(session, event.event_type, dict(event.payload))
        self._action_service.finalize(tuple(tool_result.commit_tokens or ()))
        if isinstance(tool_result, InteractionSuspended):
            pending = session.pending_interaction or tool_result.pending
            reason = "permission_wait" if pending.kind == "permission" else "user_input_wait"
            transition = LoopTransition(
                reason=reason,
                pending_interaction=pending,
                next_mode=current_mode,
                turns_used=1,
            )
            self._record_transition(session, transition)
            result = QueryTurnResult("", session, transition, pending_interaction=pending)
            self._persist_summary(session, current_mode, assembly)
            if on_step_finish is not None:
                on_step_finish(step_index, reply, transition.reason)
            turn_frame.finish(transition)
            return result, None
        if not isinstance(tool_result, ToolBatchCompleted):
            raise TypeError("unsupported tool effect result")
        observation = tool_result.observations[0]
        current_mode = self._apply_tool_selected_mode(
            session, current_mode, workflow_state, observation
        )
        committed = self._record_tool_observation(
            session,
            action,
            observation,
            current_mode,
            assembly,
            step_id,
            on_tool_finish,
        )
        if interrupted:
            transition = LoopTransition(
                reason="aborted",
                message="tool execution interrupted",
                next_mode=current_mode,
                turns_used=1,
            )
            self._record_transition(session, transition)
            self._persist_summary(session, current_mode, assembly)
            if on_step_finish is not None:
                on_step_finish(step_index, reply, "aborted")
            turn_frame.finish(transition)
            return (
                QueryTurnResult("", session, transition, turns_used=1),
                committed,
            )
        transition = LoopTransition(
            reason="completed", message="command finished", next_mode=current_mode, turns_used=1
        )
        self._record_transition(session, transition)
        self._persist_summary(session, current_mode, assembly)
        if on_step_finish is not None:
            on_step_finish(step_index, reply, "completed")
        turn_frame.finish(transition)
        return QueryTurnResult("", session, transition, turns_used=1), committed

    def resume_interaction(
        self,
        session: Session,
        initial_mode: str,
        interaction_resolution: Optional[Dict[str, Any]] = None,
        workflow_state: str = "",
        stream: bool = True,
        stop_event: Optional[threading.Event] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[Callable[[Action, Observation], None]] = None,
        on_context_result: Optional[Callable[[ContextAssemblyResult], None]] = None,
        on_step_start: Optional[Callable[[str, int], None]] = None,
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]] = None,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]] = None,
        user_input_handler: Optional[
            Callable[[UserInputRequest], Optional[UserInputResponse]]
        ] = None,
    ) -> QueryTurnResult:
        current_mode = self._require_mode_slug(initial_mode)
        resume_turn_id = self._turn_id(session) or ("t-" + uuid.uuid4().hex[:12])
        turn_frame = self.kernel.begin_turn(
            session, resume_turn_id, current_mode, workflow_state, "resume"
        )
        with self._session_guard():
            self._prompt_assembly.append_described_workflow_prompt(
                self.extension_host,
                session,
                current_mode,
                workflow_state,
                lambda payload: self._append_message_event(session, payload),
                force=True,
            )
        with self._session_guard():
            pending = session.pending_interaction
        if pending is None:
            transition = LoopTransition(reason="completed", message="no pending interaction")
            self._record_transition(session, transition)
            turn_frame.finish(transition)
            return QueryTurnResult("", session, transition)
        current_mode = self._resume_interaction(
            session,
            pending,
            current_mode,
            workflow_state,
            dict(interaction_resolution or {}),
            on_tool_start,
            on_tool_finish,
        )
        last_assembly = []

        def capture_context_result(assembly):
            last_assembly[:] = [assembly]
            if on_context_result is not None:
                on_context_result(assembly)

        try:
            result = self._agent_loop.run(
                session=session,
                reduction_context=self._reduction_context,
                turn_id=resume_turn_id,
                current_mode=current_mode,
                workflow_state=workflow_state,
                source="resume",
                stream=stream,
                cancel=stop_event,
                max_turns=self.max_turns,
                max_parallel_tools=self.max_parallel_tools,
                on_text_delta=on_text_delta,
                on_reasoning_delta=on_reasoning_delta,
                on_tool_start=on_tool_start,
                on_tool_finish=on_tool_finish,
                on_context_result=capture_context_result,
                on_step_start=on_step_start,
                on_step_finish=on_step_finish,
                permission_handler=permission_handler,
                user_input_handler=user_input_handler,
            )
            self._persist_summary(
                session,
                result.transition.next_mode or current_mode,
                last_assembly[-1] if last_assembly else None,
            )
        except BaseException as exc:
            turn_frame.interrupt("resume_error", error=str(exc))
            raise
        turn_frame.finish(result.transition)
        return result

    def _apply_tool_selected_mode(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        observation: Observation,
    ) -> str:
        if not isinstance(observation.data, dict) or not observation.data.get("mode_changed"):
            return current_mode
        selected_mode = self._require_mode_slug(
            str(observation.data.get("selected_mode") or current_mode)
        )
        if selected_mode == current_mode:
            return current_mode
        with self._session_guard():
            mode_prompt = self._build_system_prompt(selected_mode)
            if str(mode_prompt or "").strip():
                self._append_message_event(
                    session,
                    self._system_message_event_payload(session, mode_prompt),
                )
            self._prompt_assembly.append_described_workflow_prompt(
                self.extension_host,
                session,
                selected_mode,
                workflow_state,
                lambda payload: self._append_message_event(session, payload),
                force=True,
            )
        return selected_mode

    def _resume_interaction(
        self,
        session: Session,
        pending: PendingInteraction,
        current_mode: str,
        workflow_state: str,
        resolution: Dict[str, Any],
        on_tool_start: Optional[Callable[[Action], None]],
        on_tool_finish: Optional[Callable[[Action, Observation], None]],
    ) -> str:
        with self._session_guard():
            turn_id = session.turns[-1].turn_id if session.turns else ""
            step_id = session.current_step().step_id if session.current_step() is not None else ""
            intent = self.kernel.resolve_pending_interaction(session, pending, resolution)
            self._commit_session_event(session, intent.event_type, intent.payload)
            self.lifecycle.emit_pending_finished(
                session,
                pending,
                turn_id,
                step_id,
                "resolved",
            )
        action_payload = (
            pending.request_payload.get("action")
            if isinstance(pending.request_payload, dict)
            else {}
        )
        action = Action(
            name=str(action_payload.get("name") or pending.tool_name),
            arguments=dict(action_payload.get("arguments") or {}),
            call_id=str(action_payload.get("call_id") or ("call-" + pending.interaction_id)),
        )
        if on_tool_start is not None:
            on_tool_start(action)
        permission_callback = None
        user_input_callback = None
        if pending.kind == "permission":
            approved = bool(resolution.get("approved"))

            def resolved_permission(request):
                del request
                return approved

            permission_callback = resolved_permission
        else:
            response = UserInputResponse(
                answer=str(resolution.get("answer") or ""),
                selected_index=resolution.get("selected_index"),
                selected_mode=str(resolution.get("selected_mode") or ""),
                selected_option_text=str(resolution.get("selected_option_text") or ""),
            )

            def resolved_user_input(request):
                del request
                return response

            user_input_callback = resolved_user_input
        tool_result = self._action_service.execute(
            ExecuteToolBatchEffect(
                "tools:%s" % action.call_id,
                (action,),
                current_mode,
                workflow_state,
            ),
            session,
            permission_handler=permission_callback,
            user_input_handler=user_input_callback,
        )
        if isinstance(tool_result, InteractionSuspended):
            raise RuntimeError("interaction resume unexpectedly re-suspended")
        if not isinstance(tool_result, ToolBatchCompleted):
            raise TypeError("unsupported tool effect result")
        with self._session_guard():
            for event in tool_result.events:
                self._commit_session_event(session, event.event_type, dict(event.payload))
        self._action_service.finalize(tuple(tool_result.commit_tokens or ()))
        observation = tool_result.observations[0]
        current_mode = self._apply_tool_selected_mode(
            session, current_mode, workflow_state, observation
        )
        if on_tool_finish is not None:
            on_tool_finish(action, observation)
        return current_mode

    def _persist_summary(
        self, session: Session, current_mode: str, assembly: Optional[ContextAssemblyResult] = None
    ) -> None:
        with self._session_guard():
            try:
                self.session_projection.refresh(session, current_mode, assembly)
            except (OSError, ValueError, TypeError) as exc:
                _LOG.warning("session projection refresh failed: %s", exc)
            try:
                session.trim_old_observations(30)
            except (ValueError, TypeError) as exc:
                _LOG.warning("session trim failed: %s", exc)
