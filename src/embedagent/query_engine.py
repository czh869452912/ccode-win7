from __future__ import annotations  # noqa: I001

import logging
import os
import threading
import time
import uuid
from copy import deepcopy
from typing import Any, Callable, Dict, Optional, Tuple

from embedagent.context import ContextManager
from embedagent.guard import LoopGuard
from embedagent.interaction import (
    UserInputRequest,
    UserInputResponse,
    ask_user_schema,
    build_user_input_request,
    propose_mode_switch_schema,
)
from embedagent.llm import ModelClientError, OpenAICompatibleClient
from embedagent.strategies.context_compaction_engine import ContextCompactionEngine
from embedagent.strategies.execution_tracer import ExecutionTracer, TraceEventType
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper
from embedagent.strategies.turn_orchestrator import TurnOrchestrator
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.modes import DEFAULT_MODE, build_system_prompt, is_path_writable, require_mode
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import (
    Action,
    AssistantReply,
    ContextAssemblyResult,
    InteractionCheckpoint,
    LoopResult,
    LoopTransition,
    Observation,
    PendingInteraction,
    QueryTurnResult,
    Session,
    ToolPresentationSnapshot,
)
from embedagent.session_store import SessionSummaryStore
from embedagent.tool_commit import ToolCommitCoordinator
from embedagent.tool_execution import StreamingToolExecutor, partition_tool_actions
from embedagent.tools import ToolRuntime
from embedagent.tools._base import ToolError
from embedagent.transcript_store import TranscriptStore
from embedagent.workspace_intelligence import WorkspaceIntelligenceBroker
from embedagent.workspace_profile import build_workspace_profile_message

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
        transcript_store: Optional[TranscriptStore] = None,
        tracer: Optional[ExecutionTracer] = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.permission_policy = permission_policy or PermissionPolicy(auto_approve_all=True)
        self.project_memory_store = project_memory_store or ProjectMemoryStore(self.tools.workspace)
        self.context_manager = context_manager or ContextManager(
            project_memory=self.project_memory_store
        )
        self.summary_store = summary_store or SessionSummaryStore(self.tools.workspace)
        self.memory_maintenance = memory_maintenance or MemoryMaintenance(
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
            tool_result_store=self.tools.tool_result_store,
        )
        self.maintenance_interval = maintenance_interval if maintenance_interval > 0 else 1
        self.intelligence_broker = intelligence_broker or WorkspaceIntelligenceBroker()
        self.max_parallel_tools = max(1, int(max_parallel_tools or 1))
        self.transcript_store = transcript_store or TranscriptStore(self.tools.workspace)
        self.tracer = tracer
        self._compaction = ContextCompactionEngine(
            context_manager=self.context_manager,
            max_tokens=8000,
            reserve_tokens=1000,
        )
        self._llm_wrapper = LLMClientRetryWrapper(
            client=client,
            max_retries=_LLM_MAX_RETRIES,
            base_delay=_LLM_RETRY_BASE_DELAY,
        )
        self._session_lock = threading.RLock()
        self.tool_commit = ToolCommitCoordinator(
            self.tools.tool_result_store,
            self.tools.projection_db,
            self.transcript_store,
        )
        self._maintenance_counter = 0
        self._turn_orchestrator = TurnOrchestrator(
            llm_wrapper=self._llm_wrapper,
            tools=self.tools,
            permission_policy=self.permission_policy,
            max_parallel_tools=self.max_parallel_tools,
            tracer=self.tracer,
        )
        self._internal_stop_event = threading.Event()

    def run(
        self,
        user_text: str = "",
        session: Optional[Any] = None,
        initial_mode: str = DEFAULT_MODE,
        workflow_state: str = "chat",
        stream: bool = True,
        **kwargs: Any,
    ) -> QueryTurnResult:
        """High-level entry point that manages multi-turn execution."""
        self._internal_stop_event.clear()
        return self.submit_user_turn(
            user_text=user_text,
            stream=stream,
            initial_mode=initial_mode,
            workflow_state=workflow_state,
            session=session,
            stop_event=self._internal_stop_event,
            **kwargs,
        )

    def stop(self) -> None:
        """Signal the current run() to stop at the earliest opportunity."""
        self._internal_stop_event.set()

    def _session_guard(self):
        return self._session_lock

    def _append_transcript_event(
        self, session: Session, event_type: str, payload: Dict[str, Any], schema_version: int = 1
    ) -> None:
        if self.transcript_store is None:
            return
        self.transcript_store.append_event(session.session_id, event_type, payload, schema_version=schema_version)

    def _emit_lifecycle_event(
        self, session: Session, event_type: str, payload: Dict[str, Any]
    ) -> None:
        """Emit a schema_v2 lifecycle event; failures are logged but not blocking."""
        try:
            self._append_transcript_event(session, event_type, payload, schema_version=2)
        except (OSError, ValueError, TypeError) as exc:  # pragma: no cover
            _LOG.warning("lifecycle event emission failed (%s): %s", event_type, exc)

    def _append_message_event(self, session: Session, payload: Dict[str, Any]) -> None:
        self._append_transcript_event(session, "message", payload)

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
            for message in list(getattr(session, "messages", []) or []):
                self._append_message_event(session, self._message_event_payload(message))
            for boundary in list(getattr(session, "compact_boundaries", []) or []):
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
                        "metadata": dict(getattr(boundary, "metadata", {}) or {}),
                    },
                )

    def _run_harness_mode(
        self, current_mode: str, session: Optional[Session] = None, workflow_state: str = "chat"
    ) -> Tuple[str, Any]:
        del session
        if str(current_mode or "") not in ("build", "debug", "verify"):
            return current_mode, None
        return current_mode, self.tools.describe_mode(current_mode, workflow_state=workflow_state)

    def _allowed_tools_for_mode(self, mode_name: str, workflow_state: str = "chat") -> set:
        return set(self.tools.allowed_tool_names(mode_name, workflow_state=workflow_state))

    def _append_harness_messages(self, session: Session, harness_context: Any) -> None:
        if harness_context is None:
            return
        existing = False
        for message in list(session.messages):
            if message.role != "system" or message.kind != "harness_prompt":
                continue
            metadata = dict(getattr(message, "metadata", {}) or {})
            if str(metadata.get("mode_name") or "") != str(harness_context.mode_name or ""):
                continue
            if str(metadata.get("discipline_label") or "") != str(
                harness_context.discipline_label or ""
            ):
                continue
            existing = True
            break
        if existing:
            return
        for index, content in enumerate(list(getattr(harness_context, "prompt_units", []) or [])):
            harness_message = session.add_system_message(
                content,
                kind="harness_prompt",
                metadata={
                    "mode_name": str(harness_context.mode_name or ""),
                    "discipline_label": str(harness_context.discipline_label or ""),
                    "pack_name": str(harness_context.pack_name or ""),
                    "unit_index": index,
                },
            )
            self._append_message_event(
                session,
                {
                    "role": harness_message.role,
                    "content": harness_message.content,
                    "message_id": harness_message.message_id,
                    "parent_message_id": harness_message.parent_message_id,
                    "turn_id": harness_message.turn_id,
                    "step_id": harness_message.step_id,
                    "kind": harness_message.kind,
                    "metadata": dict(harness_message.metadata),
                    "replaced_by_refs": list(harness_message.replaced_by_refs),
                },
            )

    def initialize_session(
        self, session: Session, initial_mode: str, workflow_state: str = "chat"
    ) -> str:
        current_mode = require_mode(initial_mode)["slug"]
        current_mode, harness_context = self._run_harness_mode(
            current_mode, session, workflow_state=workflow_state
        )
        if session.messages:
            self._ensure_transcript_bootstrap(session, current_mode)
            with self._session_guard():
                self._append_harness_messages(session, harness_context)
            return current_mode
        with self._session_guard():
            profile_message = session.add_system_message(
                build_workspace_profile_message(self.tools.workspace, session.session_id)
            )
            system_message = session.add_system_message(
                build_system_prompt(
                    current_mode, getattr(self.tools, "app_config", None), self.tools.workspace
                )
            )
            self._append_transcript_event(
                session,
                "session_meta",
                {
                    "current_mode": current_mode,
                    "started_at": session.started_at,
                    "workspace": self.tools.workspace,
                },
            )
            for message in (profile_message, system_message):
                self._append_message_event(
                    session,
                    {
                        "role": message.role,
                        "content": message.content,
                        "message_id": message.message_id,
                        "parent_message_id": message.parent_message_id,
                        "turn_id": message.turn_id,
                        "step_id": message.step_id,
                        "kind": message.kind,
                        "metadata": dict(message.metadata),
                        "replaced_by_refs": list(message.replaced_by_refs),
                    },
                )
            self._append_harness_messages(session, harness_context)
        return current_mode

    def apply_mode(self, session: Session, next_mode: str, workflow_state: str = "chat") -> str:
        current_mode = require_mode(next_mode)["slug"]
        current_mode, harness_context = self._run_harness_mode(
            current_mode, session, workflow_state=workflow_state
        )
        with self._session_guard():
            mode_message = session.add_system_message(
                build_system_prompt(
                    current_mode, getattr(self.tools, "app_config", None), self.tools.workspace
                )
            )
            self._append_message_event(
                session,
                {
                    "role": mode_message.role,
                    "content": mode_message.content,
                    "message_id": mode_message.message_id,
                    "parent_message_id": mode_message.parent_message_id,
                    "turn_id": mode_message.turn_id,
                    "step_id": mode_message.step_id,
                    "kind": mode_message.kind,
                    "metadata": dict(mode_message.metadata),
                    "replaced_by_refs": list(mode_message.replaced_by_refs),
                },
            )
            self._append_harness_messages(session, harness_context)
        return current_mode

    def _record_transition(self, session: Session, transition: LoopTransition) -> None:
        with self._session_guard():
            step_id = session.current_step().step_id if session.current_step() is not None else ""
            turn_id = session.turns[-1].turn_id if session.turns else ""
            if transition.pending_interaction is not None:
                self._append_transcript_event(
                    session,
                    "pending_interaction",
                    {
                        "turn_id": turn_id,
                        "step_id": step_id,
                        "kind": transition.pending_interaction.kind,
                        "tool_name": transition.pending_interaction.tool_name,
                        "interaction_id": transition.pending_interaction.interaction_id,
                        "request_payload": dict(transition.pending_interaction.request_payload),
                    },
                )
            self._append_transcript_event(
                session,
                "loop_transition",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "reason": transition.reason,
                    "message": transition.message,
                    "next_mode": transition.next_mode,
                    "turns_used": transition.turns_used,
                    "metadata": dict(transition.metadata),
                },
            )
            session.record_transition(transition)

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
                turn = session.add_user_message(
                    user_text or ("/%s" % command_name),
                    turn_id=command_turn_id,
                )
                user_message = session.messages[turn.message_end_index]
                self._append_message_event(
                    session,
                    {
                        "role": user_message.role,
                        "content": user_message.content,
                        "message_id": user_message.message_id,
                        "parent_message_id": user_message.parent_message_id,
                        "turn_id": user_message.turn_id,
                        "step_id": user_message.step_id,
                        "kind": user_message.kind,
                        "metadata": dict(user_message.metadata),
                        "replaced_by_refs": list(user_message.replaced_by_refs),
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

    def _interaction_checkpoint_payload(
        self,
        session: Session,
        action: Action,
        pending: PendingInteraction,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step = session.current_step()
        step_id = step.step_id if step is not None else ""
        payload = InteractionCheckpoint(
            action={
                "name": action.name,
                "arguments": dict(action.arguments),
                "call_id": action.call_id,
            },
            turn_id=turn_id,
            step_id=step_id,
            interaction_id=pending.interaction_id,
            kind=pending.kind,
            request_data=dict(request_data or {}),
        ).to_dict()
        return payload

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

    def _discarded_observation(self, tool_name: str) -> Observation:
        return Observation(
            tool_name=tool_name,
            success=False,
            error="tool execution discarded",
            data={
                "error_kind": "discarded",
                "retryable": False,
                "synthetic": True,
            },
        )

    def _is_interrupted_observation(self, observation: Observation) -> bool:
        return bool(
            isinstance(observation.data, dict)
            and str(observation.data.get("error_kind") or "") == "interrupted"
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
        with self._session_guard():
            tool_message_id = "m-" + uuid.uuid4().hex[:12]
            parent_message_id = session.last_message_id()
            finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            turn_id = session.turns[-1].turn_id if session.turns else ""
            try:
                committed = self.tool_commit.commit(
                    session,
                    action,
                    observation,
                    current_mode,
                    turn_id=turn_id,
                    step_id=step_id,
                    message_id=tool_message_id,
                    parent_message_id=parent_message_id,
                    finished_at=finished_at,
                )
            except (OSError, ValueError, TypeError) as exc:
                _LOG.warning(
                    "tool commit failed for %s/%s; falling back to in-memory pairing: %s",
                    action.name,
                    action.call_id,
                    exc,
                )
                committed = self._fallback_committed_observation(observation, exc)
            session.add_observation(
                action,
                committed,
                message_id=tool_message_id,
                parent_message_id=parent_message_id,
                turn_id=turn_id,
                step_id=step_id,
                finished_at=finished_at,
            )
        self._persist_summary(session, current_mode, assembly)
        if on_tool_finish is not None:
            on_tool_finish(action, committed)
        return committed

    def _fallback_committed_observation(
        self,
        observation: Observation,
        exc: Exception,
    ) -> Observation:
        data = deepcopy(observation.data)
        if isinstance(data, dict):
            warnings = data.get("tool_result_commit_warnings")
            if not isinstance(warnings, list):
                warnings = []
            warnings.append({"error": str(exc)})
            data["tool_result_commit_warnings"] = warnings[:8]
        return Observation(
            observation.tool_name,
            observation.success,
            observation.error,
            data,
        )

    def submit_user_turn(
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
        current_mode = self.initialize_session(session, initial_mode, workflow_state=workflow_state)

        turn_id = getattr(session, "current_turn_id", "") or "t-" + uuid.uuid4().hex[:12]
        session_id = getattr(session, "session_id", "") or ""

        if self.tracer is not None:
            self.tracer.record(
                TraceEventType.TURN_START,
                session_id,
                turn_id,
                data={"mode": current_mode, "workflow_state": workflow_state},
            )

        if user_text:
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
                session.add_user_message(
                    user_text,
                    turn_id=turn_id,
                    message_id=message_id,
                    parent_message_id=parent_message_id,
                )
        try:
            result = self._run_loop(
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
            if self.tracer is not None:
                self.tracer.record(
                    TraceEventType.TURN_END,
                    session_id,
                    turn_id,
                    data={"transition_reason": getattr(result.transition, "reason", "")},
                )
                self.tracer.flush()
            return result
        except BaseException as exc:
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
        current_mode = self.initialize_session(session, initial_mode, workflow_state=workflow_state)
        with self._session_guard():
            command_turn_id = str(turn_id or ("t-" + uuid.uuid4().hex[:12]))
            if user_text:
                message_id = "m-" + uuid.uuid4().hex[:12]
                parent_message_id = session.last_message_id()
                self._append_message_event(
                    session,
                    {
                        "role": "user",
                        "content": user_text,
                        "message_id": message_id,
                        "parent_message_id": parent_message_id,
                        "turn_id": command_turn_id,
                        "step_id": "",
                    },
                )
                session.add_user_message(
                    user_text,
                    turn_id=command_turn_id,
                    message_id=message_id,
                    parent_message_id=parent_message_id,
                )
            step = session.begin_step()
            step_id = step.step_id
            step_index = step.step_index
            presentation = self._tool_presentation_snapshot(action.name)
            self._append_transcript_event(
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
            record = session._find_tool_call(action.call_id)
            if record is None:
                session.record_tool_call(action, presentation)
            else:
                record.presentation = presentation
        if on_step_start is not None:
            on_step_start(step_id, step_index)
        assembly = self._build_context(session, current_mode, workflow_state)
        if on_context_result is not None:
            on_context_result(assembly)
        reply = AssistantReply(content="", actions=[action], finish_reason="tool_calls")
        interrupted = bool(stop_event is not None and stop_event.is_set())
        if on_tool_start is not None:
            on_tool_start(action)
        if interrupted:
            observation = self._interrupted_observation(action.name)
            result = QueryTurnResult(
                "",
                session,
                LoopTransition(
                    reason="aborted",
                    message="tool execution interrupted",
                    next_mode=current_mode,
                    turns_used=1,
                ),
                turns_used=1,
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
            self._record_transition(session, result.transition)
            self._persist_summary(session, current_mode, assembly)
            if on_step_finish is not None:
                on_step_finish(step_index, reply, "aborted")
            return result, committed
        observation, current_mode, suspended = self._execute_action(
            session,
            action,
            current_mode,
            workflow_state,
            permission_handler,
            user_input_handler,
            stop_event=stop_event,
        )
        if suspended is not None:
            self._persist_summary(session, current_mode, assembly)
            if on_step_finish is not None:
                on_step_finish(step_index, reply, suspended.transition.reason)
            return suspended, None
        committed = self._record_tool_observation(
            session,
            action,
            observation,
            current_mode,
            assembly,
            step_id,
            on_tool_finish,
        )
        transition = LoopTransition(
            reason="completed", message="command finished", next_mode=current_mode, turns_used=1
        )
        self._record_transition(session, transition)
        self._persist_summary(session, current_mode, assembly)
        if on_step_finish is not None:
            on_step_finish(step_index, reply, "completed")
        return QueryTurnResult("", session, transition, turns_used=1), committed

    def resume_interaction(
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
        on_step_start: Optional[Callable[[str, int], None]] = None,
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]] = None,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]] = None,
        user_input_handler: Optional[
            Callable[[UserInputRequest], Optional[UserInputResponse]]
        ] = None,
    ) -> QueryTurnResult:
        current_mode = require_mode(initial_mode)["slug"]
        with self._session_guard():
            self._append_harness_messages(
                session,
                self.tools.describe_mode(current_mode, workflow_state=workflow_state),
            )
        with self._session_guard():
            pending = session.pending_interaction
        if pending is None:
            transition = LoopTransition(reason="completed", message="no pending interaction")
            self._record_transition(session, transition)
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
        on_step_start: Optional[Callable[[str, int], None]],
        on_step_finish: Optional[Callable[[int, AssistantReply, str], None]],
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
    ) -> QueryTurnResult:
        final_text = ""
        loop_guard = LoopGuard()
        turns_used = 0
        for turn_index in range(self.max_turns):
            if stop_event is not None and stop_event.is_set():
                transition = LoopTransition(
                    reason="aborted", message="stop_event set", turns_used=turns_used
                )
                self._record_transition(session, transition)
                return QueryTurnResult(final_text, session, transition, turns_used)
            step_index = turn_index + 1
            step_id = "s-" + uuid.uuid4().hex[:12]
            with self._session_guard():
                self._append_transcript_event(
                    session,
                    "step_started",
                    {
                        "turn_id": session.turns[-1].turn_id if session.turns else "",
                        "step_id": step_id,
                        "step_index": step_index,
                    },
                )
                session.begin_step(step_id=step_id)
            if on_step_start is not None:
                on_step_start(step_id, step_index)
            force_compact = False
            compact_retry_used = False
            compact_boundary_recorded = False
            while True:
                assembly = self._build_context(
                    session, current_mode, workflow_state, force_compact=force_compact
                )
                with self._session_guard():
                    session.record_context_snapshot(
                        {
                            "mode_name": current_mode,
                            "pipeline_steps": list(assembly.pipeline_steps),
                            "analysis": dict(assembly.analysis),
                            "approx_tokens": assembly.approx_tokens,
                            "summary_message": assembly.summary_message,
                        }
                    )
                    self._append_transcript_event(
                        session,
                        "context_snapshot",
                        {
                            "mode_name": current_mode,
                            "pipeline_steps": list(assembly.pipeline_steps),
                            "analysis": dict(assembly.analysis),
                            "approx_tokens": assembly.approx_tokens,
                            "summary_message": assembly.summary_message,
                        },
                    )
                    for replacement in assembly.replacements:
                        session.record_content_replacement(dict(replacement))
                        self._append_transcript_event(
                            session,
                            "content_replacement",
                            dict(replacement),
                        )
                if on_context_result is not None:
                    on_context_result(assembly)
                self._persist_summary(session, current_mode, assembly)
                try:
                    reply = self._call_llm_with_retry(
                        assembly.messages,
                        self._schemas_for_mode(current_mode, workflow_state),
                        stream,
                        on_text_delta,
                        on_reasoning_delta,
                    )
                    break
                except ModelClientError as exc:
                    if compact_retry_used or not self._should_retry_with_compact(exc):
                        raise
                    compact_retry_used = True
                    force_compact = True
                    compact_boundary_recorded = (
                        self._maybe_record_compact_boundary(session, current_mode, assembly)
                        or compact_boundary_recorded
                    )
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
                    self._record_transition(session, transition)
                    continue
            with self._session_guard():
                assistant_message_id = "m-" + uuid.uuid4().hex[:12]
                parent_message_id = session.last_message_id()
                self._append_message_event(
                    session,
                    {
                        "role": "assistant",
                        "content": reply.content,
                        "message_id": assistant_message_id,
                        "parent_message_id": parent_message_id,
                        "turn_id": session.turns[-1].turn_id if session.turns else "",
                        "step_id": step_id,
                        "actions": [
                            {
                                "name": action.name,
                                "arguments": dict(action.arguments),
                                "call_id": action.call_id,
                            }
                            for action in reply.actions
                        ],
                        "reasoning_content": reply.reasoning_content,
                        "finish_reason": reply.finish_reason,
                    },
                )
                session.add_assistant_reply(
                    reply,
                    message_id=assistant_message_id,
                    parent_message_id=parent_message_id,
                    turn_id=session.turns[-1].turn_id if session.turns else "",
                    step_id=step_id,
                )
                for action in reply.actions:
                    presentation = self._tool_presentation_snapshot(action.name)
                    self._append_transcript_event(
                        session,
                        "tool_call",
                        {
                            "turn_id": session.turns[-1].turn_id if session.turns else "",
                            "step_id": step_id,
                            "call_id": action.call_id,
                            "tool_name": action.name,
                            "arguments": dict(action.arguments),
                            "status": "pending",
                            "presentation": presentation.to_dict(),
                        },
                    )
                    record = session._find_tool_call(action.call_id)
                    if record is not None:
                        record.presentation = presentation
            final_text = reply.content
            turns_used = step_index
            if not reply.actions:
                transition = LoopTransition(
                    reason="completed",
                    message="assistant finished",
                    next_mode=current_mode,
                    turns_used=turns_used,
                )
                self._record_transition(session, transition)
                self._persist_summary(session, current_mode, assembly)
                if not compact_boundary_recorded:
                    self._maybe_record_compact_boundary(session, current_mode, assembly)
                self._maybe_maintain_memory(True)
                if on_step_finish is not None:
                    on_step_finish(step_index, reply, "completed")
                return QueryTurnResult(final_text, session, transition, turns_used)
            executor = StreamingToolExecutor(
                lambda action: self.tools.execute_with_interrupt(
                    action.name, action.arguments, stop_event
                ),
                self.max_parallel_tools,
                cancel_event=stop_event,
            )
            discard_remaining_batches = False
            for batch in partition_tool_actions(
                reply.actions,
                self.tools.tool_capabilities,
            ):
                if discard_remaining_batches:
                    for action in batch.actions:
                        observation = self._discarded_observation(action.name)
                        self._record_tool_observation(
                            session,
                            action,
                            observation,
                            current_mode,
                            assembly,
                            step_id,
                            on_tool_finish,
                        )
                        loop_guard.record(action, observation)
                    continue
                if not batch.parallel:
                    for action in batch.actions:
                        if on_tool_start is not None:
                            on_tool_start(action)
                        self._emit_lifecycle_event(
                            session,
                            "tool_use",
                            {
                                "role": "tool_use",
                                "tool_name": action.name,
                                "call_id": action.call_id,
                                "arguments": dict(action.arguments),
                                "message_id": "m-tool-use-" + uuid.uuid4().hex[:12],
                                "parent_message_id": session.last_message_id(),
                                "turn_id": session.turns[-1].turn_id if session.turns else "",
                                "step_id": session.current_step().step_id if session.current_step() else "",
                                "status": "started",
                            },
                        )
                        interrupted = bool(stop_event is not None and stop_event.is_set())
                        suspended = None
                        if interrupted:
                            observation = self._interrupted_observation(action.name)
                        else:
                            observation, current_mode, suspended = self._execute_action(
                                session,
                                action,
                                current_mode,
                                workflow_state,
                                permission_handler,
                                user_input_handler,
                                stop_event=stop_event,
                            )
                            if suspended is not None:
                                self._persist_summary(session, current_mode, assembly)
                                if on_step_finish is not None:
                                    on_step_finish(step_index, reply, suspended.transition.reason)
                                return suspended
                            if (
                                stop_event is not None
                                and stop_event.is_set()
                                and not self._is_interrupted_observation(observation)
                            ):
                                interrupted = True
                                observation = self._interrupted_observation(action.name)
                        self._emit_lifecycle_event(
                            session,
                            "command_execution",
                            {
                                "role": "command_execution",
                                "call_id": action.call_id,
                                "tool_name": action.name,
                                "output_chunk": str(observation.data) if observation.data else "",
                                "message_id": "m-cmd-" + uuid.uuid4().hex[:12],
                                "parent_message_id": session.last_message_id(),
                                "turn_id": session.turns[-1].turn_id if session.turns else "",
                                "step_id": session.current_step().step_id if session.current_step() else "",
                                "status": "updated",
                            },
                        )
                        self._record_tool_observation(
                            session,
                            action,
                            observation,
                            current_mode,
                            assembly,
                            step_id,
                            on_tool_finish,
                        )
                        loop_guard.record(action, observation)
                        if interrupted:
                            transition = LoopTransition(
                                reason="aborted",
                                message="tool execution interrupted",
                                turns_used=turns_used,
                            )
                            self._record_transition(session, transition)
                            if on_step_finish is not None:
                                on_step_finish(step_index, reply, "aborted")
                            return QueryTurnResult(final_text, session, transition, turns_used)
                        if loop_guard.should_block(action) or loop_guard.should_stop():
                            transition = LoopTransition(
                                reason="guard_stop",
                                message=loop_guard.stop_reason(),
                                turns_used=turns_used,
                            )
                            self._record_transition(session, transition)
                            if on_step_finish is not None:
                                on_step_finish(step_index, reply, "guard_stop")
                            return QueryTurnResult(final_text, session, transition, turns_used)
                    continue
                batch_interrupted = False
                batch_discarded = False
                for update in executor.run_batch(batch):
                    if update.phase == "start":
                        if on_tool_start is not None:
                            on_tool_start(update.action)
                        self._emit_lifecycle_event(
                            session,
                            "tool_use",
                            {
                                "role": "tool_use",
                                "tool_name": update.action.name,
                                "call_id": update.action.call_id,
                                "arguments": dict(update.action.arguments),
                                "message_id": "m-tool-use-" + uuid.uuid4().hex[:12],
                                "parent_message_id": session.last_message_id(),
                                "turn_id": session.turns[-1].turn_id if session.turns else "",
                                "step_id": session.current_step().step_id if session.current_step() else "",
                                "status": "started",
                            },
                        )
                        if stop_event is not None and stop_event.is_set():
                            batch_interrupted = True
                            executor.discard()
                        continue
                    suspended = None
                    if batch_interrupted or (stop_event is not None and stop_event.is_set()):
                        batch_interrupted = True
                        if (
                            update.observation is not None
                            and isinstance(update.observation.data, dict)
                            and update.observation.data.get("error_kind") == "discarded"
                        ):
                            observation = update.observation
                        else:
                            observation = self._interrupted_observation(update.action.name)
                    else:
                        observation, current_mode, suspended = self._execute_action(
                            session,
                            update.action,
                            current_mode,
                            workflow_state,
                            permission_handler,
                            user_input_handler,
                            update.observation,
                            stop_event=stop_event,
                        )
                        if suspended is not None:
                            self._persist_summary(session, current_mode, assembly)
                            if on_step_finish is not None:
                                on_step_finish(step_index, reply, suspended.transition.reason)
                            return suspended
                        if (
                            stop_event is not None
                            and stop_event.is_set()
                            and not self._is_interrupted_observation(observation)
                        ):
                            batch_interrupted = True
                            executor.discard()
                            observation = self._interrupted_observation(update.action.name)
                    self._emit_lifecycle_event(
                        session,
                        "command_execution",
                        {
                            "role": "command_execution",
                            "call_id": update.action.call_id,
                            "tool_name": update.action.name,
                            "output_chunk": str(observation.data) if observation.data else "",
                            "message_id": "m-cmd-" + uuid.uuid4().hex[:12],
                            "parent_message_id": session.last_message_id(),
                            "turn_id": session.turns[-1].turn_id if session.turns else "",
                            "step_id": session.current_step().step_id if session.current_step() else "",
                            "status": "updated",
                        },
                    )
                    if (
                        isinstance(observation.data, dict)
                        and observation.data.get("error_kind") == "discarded"
                    ):
                        batch_discarded = True
                    self._record_tool_observation(
                        session,
                        update.action,
                        observation,
                        current_mode,
                        assembly,
                        step_id,
                        on_tool_finish,
                    )
                    loop_guard.record(update.action, observation)
                    if batch_interrupted:
                        continue
                    if loop_guard.should_block(update.action) or loop_guard.should_stop():
                        transition = LoopTransition(
                            reason="guard_stop",
                            message=loop_guard.stop_reason(),
                            turns_used=turns_used,
                        )
                        self._record_transition(session, transition)
                        if on_step_finish is not None:
                            on_step_finish(step_index, reply, "guard_stop")
                        return QueryTurnResult(final_text, session, transition, turns_used)
                if batch_interrupted:
                    transition = LoopTransition(
                        reason="aborted",
                        message="tool execution interrupted",
                        turns_used=turns_used,
                    )
                    self._record_transition(session, transition)
                    if on_step_finish is not None:
                        on_step_finish(step_index, reply, "aborted")
                    return QueryTurnResult(final_text, session, transition, turns_used)
                if batch_discarded:
                    discard_remaining_batches = True
            if on_step_finish is not None:
                on_step_finish(step_index, reply, "tool_calls")
        transition = LoopTransition(
            reason="max_turns", message="超过最大迭代次数", turns_used=turns_used
        )
        self._record_transition(session, transition)
        return QueryTurnResult(final_text, session, transition, turns_used)

    def _build_context(
        self, session: Session, mode_name: str, workflow_state: str, force_compact: bool = False
    ) -> ContextAssemblyResult:
        with self._session_guard():
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
        schemas = list(self.tools.schemas_for_mode(mode_name, workflow_state=workflow_state))
        names = set(item.get("function", {}).get("name", "") for item in schemas)
        if (
            "ask_user" in self._allowed_tools_for_mode(mode_name, workflow_state=workflow_state)
            and "ask_user" not in names
        ):
            schemas.append(ask_user_schema())
            names.add("ask_user")
        if "propose_mode_switch" not in names:
            schemas.append(propose_mode_switch_schema())
        return schemas

    def _execute_action(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
        precomputed_observation: Optional[Observation] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> Tuple[Observation, str, Optional[QueryTurnResult]]:
        runtime_action = action
        if action.name not in self._allowed_tools_for_mode(
            current_mode, workflow_state=workflow_state
        ) and action.name not in ("ask_user", "propose_mode_switch"):
            return (
                self._failure_observation(
                    action.name,
                    "当前模式 %s 不允许调用工具 %s。" % (current_mode, action.name),
                    "mode_tool_blocked",
                    False,
                    current_mode,
                    "请改用当前模式允许的工具。",
                ),
                current_mode,
                None,
            )
        if action.name == "task_status":
            mode_context = self.tools.describe_mode(current_mode, workflow_state=workflow_state)
            summary = ""
            phase = ""
            discipline = ""
            task_items = []
            if mode_context is not None:
                summary = str(getattr(mode_context, "task_summary", "") or "")
                phase = str(getattr(mode_context, "current_phase", "") or "")
                discipline = str(getattr(mode_context, "discipline_label", "") or "")
                task_items = list(getattr(mode_context, "task_items", []) or [])
            if not summary:
                summary = "in_progress %s" % current_mode
            observation = Observation(
                tool_name="task_status",
                success=True,
                error=None,
                data={
                    "summary": summary,
                    "preview": [line for line in summary.splitlines() if line],
                    "returned_count": len([line for line in summary.splitlines() if line]),
                    "total_count": len([line for line in summary.splitlines() if line]),
                    "has_more": False,
                    "next_offset": 0,
                    "result_ref": "",
                    "current_mode": current_mode,
                    "current_phase": phase,
                    "discipline_profile": discipline,
                    "tasks": task_items,
                },
            )
            return observation, current_mode, None
        if action.name == "ask_user":
            request = build_user_input_request(action.arguments)
            response = user_input_handler(request) if user_input_handler is not None else None
            if response is None:
                request_payload = {
                    "tool_name": request.tool_name,
                    "question": request.question,
                    "options": [
                        {"index": item.index, "text": item.text, "mode": item.mode}
                        for item in request.options
                    ],
                    "details": dict(request.details),
                }
                pending = PendingInteraction(
                    kind="user_input",
                    tool_name="ask_user",
                )
                pending.request_payload = self._interaction_checkpoint_payload(
                    session,
                    action,
                    pending,
                    request_data={"request": request_payload},
                )
                pending.request_payload["request"] = request_payload
                transition = LoopTransition(
                    "user_input_wait", request.question, pending, current_mode
                )
                self._record_transition(session, transition)
                return (
                    self._failure_observation(
                        "ask_user",
                        "waiting user input",
                        "pending_interaction",
                        False,
                        "user_input",
                        "等待用户回答。",
                        {"pending": True},
                    ),
                    current_mode,
                    QueryTurnResult("", session, transition, pending_interaction=pending),
                )
            observation, next_mode = self._build_user_input_observation(
                session, current_mode, request, response, workflow_state=workflow_state
            )
            return observation, next_mode, None
        if action.name == "propose_mode_switch":
            response = (
                user_input_handler(
                    UserInputRequest(
                        "propose_mode_switch",
                        str(action.arguments.get("reason") or ""),
                        [],
                        {"target_mode": str(action.arguments.get("target_mode") or "")},
                    )
                )
                if user_input_handler is not None
                else None
            )
            if response is None:
                pending = PendingInteraction(
                    kind="user_input",
                    tool_name="propose_mode_switch",
                )
                pending.request_payload = self._interaction_checkpoint_payload(
                    session,
                    action,
                    pending,
                    request_data={
                        "request": {
                            "tool_name": "propose_mode_switch",
                            "question": str(action.arguments.get("reason") or ""),
                            "options": [],
                            "details": {
                                "target_mode": str(action.arguments.get("target_mode") or "")
                            },
                        }
                    },
                )
                transition = LoopTransition(
                    "user_input_wait",
                    str(action.arguments.get("reason") or ""),
                    pending,
                    current_mode,
                )
                self._record_transition(session, transition)
                return (
                    self._failure_observation(
                        action.name,
                        "waiting user input",
                        "pending_interaction",
                        False,
                        "user_input",
                        "等待用户回答。",
                        {"pending": True},
                    ),
                    current_mode,
                    QueryTurnResult("", session, transition, pending_interaction=pending),
                )
            target_mode = str(
                response.selected_mode or action.arguments.get("target_mode") or ""
            ).strip()
            if target_mode:
                target_mode = str(require_mode(target_mode)["slug"])
                if target_mode != current_mode:
                    with self._session_guard():
                        mode_message = session.add_system_message(
                            build_system_prompt(
                                target_mode,
                                getattr(self.tools, "app_config", None),
                                getattr(self.tools, "workspace", ""),
                            )
                        )
                        self._append_message_event(
                            session,
                            {
                                "role": mode_message.role,
                                "content": mode_message.content,
                                "message_id": mode_message.message_id,
                                "parent_message_id": mode_message.parent_message_id,
                                "turn_id": mode_message.turn_id,
                                "step_id": mode_message.step_id,
                                "kind": mode_message.kind,
                                "metadata": dict(mode_message.metadata),
                                "replaced_by_refs": list(mode_message.replaced_by_refs),
                            },
                        )
                        self._append_harness_messages(
                            session,
                            self.tools.describe_mode(target_mode, workflow_state=workflow_state),
                        )
                    current_mode = target_mode
            return (
                Observation(
                    "propose_mode_switch",
                    True,
                    None,
                    {"selected_mode": target_mode, "mode_changed": bool(target_mode)},
                ),
                current_mode,
                None,
            )
        decision = self.permission_policy.evaluate(runtime_action)
        if decision.outcome == "deny":
            self._emit_lifecycle_event(
                session,
                "interaction",
                {
                    "role": "interaction",
                    "tool_name": action.name,
                    "call_id": action.call_id,
                    "message_id": "m-reject-" + uuid.uuid4().hex[:12],
                    "parent_message_id": session.last_message_id(),
                    "turn_id": session.turns[-1].turn_id if session.turns else "",
                    "step_id": session.current_step().step_id if session.current_step() else "",
                    "status": "rejected",
                    "reason": "permission_denied",
                },
            )
            return (
                self._failure_observation(
                    action.name,
                    decision.error or "权限规则拒绝该操作。",
                    "permission_denied",
                    False,
                    "permission_policy",
                    "修改权限规则，或由用户手动放行后重试。",
                    {"permission_required": True, "permission_decision": "deny"},
                ),
                current_mode,
                None,
            )
        if decision.request is not None:
            approved = (
                permission_handler(decision.request) if permission_handler is not None else None
            )
            if approved is None:
                permission_payload = {
                    "tool_name": decision.request.tool_name,
                    "category": decision.request.category,
                    "reason": decision.request.reason,
                    "details": dict(decision.request.details),
                }
                pending = PendingInteraction(
                    kind="permission",
                    tool_name=action.name,
                )
                pending.request_payload = self._interaction_checkpoint_payload(
                    session,
                    action,
                    pending,
                    request_data={"permission": permission_payload},
                )
                pending.request_payload["permission"] = permission_payload
                transition = LoopTransition(
                    "permission_wait", decision.request.reason, pending, current_mode
                )
                self._record_transition(session, transition)
                return (
                    self._failure_observation(
                        action.name,
                        "waiting permission",
                        "pending_interaction",
                        False,
                        "permission",
                        "等待用户批准。",
                        {"pending": True},
                    ),
                    current_mode,
                    QueryTurnResult("", session, transition, pending_interaction=pending),
                )
            if not approved:
                self._emit_lifecycle_event(
                    session,
                    "interaction",
                    {
                        "role": "interaction",
                        "tool_name": action.name,
                        "call_id": action.call_id,
                        "message_id": "m-reject-" + uuid.uuid4().hex[:12],
                        "parent_message_id": session.last_message_id(),
                        "turn_id": session.turns[-1].turn_id if session.turns else "",
                        "step_id": session.current_step().step_id if session.current_step() else "",
                        "status": "rejected",
                        "reason": "permission_denied",
                    },
                )
                return (
                    self._failure_observation(
                        action.name,
                        "操作未获批准，已跳过执行。",
                        "permission_denied",
                        False,
                        "user_confirmation",
                        "等待用户批准，或改为不需要该权限的方案。",
                        {"permission_required": True, "permission_decision": "deny"},
                    ),
                    current_mode,
                    None,
                )
        if action.name in ("edit_file", "write_file"):
            path = str(runtime_action.arguments.get("path") or "")
            if not path:
                return (
                    self._failure_observation(
                        action.name,
                        "%s 缺少 path 参数。" % action.name,
                        "invalid_arguments",
                        False,
                        "arguments",
                        "补充一个相对于工作区的 path 参数。",
                    ),
                    current_mode,
                    None,
                )
            if not is_path_writable(
                current_mode, path.replace("\\", "/"), getattr(self.tools, "app_config", None)
            ):
                return (
                    self._failure_observation(
                        action.name,
                        "当前模式 %s 不允许修改 %s。" % (current_mode, path.replace("\\", "/")),
                        "mode_path_blocked",
                        False,
                        current_mode,
                        "请改用当前模式允许的文件类型，或切换模式。",
                    ),
                    current_mode,
                    None,
                )
            if action.name == "edit_file":
                try:
                    resolved_path = self.tools._ctx.resolve_path(
                        path.replace("\\", "/"), allow_missing=True
                    )
                except ToolError as exc:
                    return (
                        self._failure_observation(
                            action.name,
                            str(exc),
                            "path_invalid",
                            False,
                            "workspace",
                            "改用工作区内的相对路径。",
                        ),
                        current_mode,
                        None,
                    )
                if not resolved_path or not os.path.exists(resolved_path):
                    return (
                        self._failure_observation(
                            action.name,
                            "目标文件不存在，edit_file 只能修改已存在的文件。",
                            "file_missing",
                            False,
                            "filesystem",
                            "若要新建文件，请改用 write_file。",
                        ),
                        current_mode,
                        None,
                    )
        return (
            precomputed_observation
            or self.tools.execute_with_interrupt(
                runtime_action.name, runtime_action.arguments, stop_event
            ),
            current_mode,
            None,
        )

    def _build_user_input_observation(
        self,
        session: Session,
        current_mode: str,
        request: UserInputRequest,
        response: UserInputResponse,
        workflow_state: str = "chat",
    ) -> Tuple[Observation, str]:
        selected_mode = str(response.selected_mode or "").strip()
        next_mode = current_mode
        mode_changed = False
        if selected_mode:
            selected_mode = str(require_mode(selected_mode)["slug"])
            if selected_mode != current_mode:
                next_mode = selected_mode
                mode_changed = True
                with self._session_guard():
                    mode_message = session.add_system_message(
                        build_system_prompt(
                            selected_mode,
                            getattr(self.tools, "app_config", None),
                            getattr(self.tools, "workspace", ""),
                        )
                    )
                    self._append_message_event(
                        session,
                        {
                            "role": mode_message.role,
                            "content": mode_message.content,
                            "message_id": mode_message.message_id,
                            "parent_message_id": mode_message.parent_message_id,
                            "turn_id": mode_message.turn_id,
                            "step_id": mode_message.step_id,
                            "kind": mode_message.kind,
                            "metadata": dict(mode_message.metadata),
                            "replaced_by_refs": list(mode_message.replaced_by_refs),
                        },
                    )
                    self._append_harness_messages(
                        session,
                        self.tools.describe_mode(selected_mode, workflow_state=workflow_state),
                    )
        return (
            Observation(
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
            ),
            next_mode,
        )

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
            self._append_transcript_event(
                session,
                "pending_resolution",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "interaction_id": pending.interaction_id,
                    "kind": pending.kind,
                    "tool_name": pending.tool_name,
                    "resolution_payload": dict(resolution or {}),
                },
            )
            session.resolve_pending_interaction(resolution)
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
        if pending.kind == "permission":
            approved = bool(resolution.get("approved"))
            if approved:
                observation, current_mode, suspended = self._execute_action(
                    session,
                    action,
                    current_mode,
                    workflow_state,
                    permission_handler=lambda request: True,
                    user_input_handler=None,
                )
                if suspended is not None:
                    raise RuntimeError("permission resume unexpectedly re-suspended")
            else:
                observation = self._failure_observation(
                    action.name,
                    "操作未获批准，已跳过执行。",
                    "permission_denied",
                    False,
                    "user_confirmation",
                    "等待用户批准，或改为不需要该权限的方案。",
                )
        else:
            req = (
                pending.request_payload.get("request")
                if isinstance(pending.request_payload, dict)
                else {}
            )
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
            observation, current_mode = self._build_user_input_observation(
                session,
                current_mode,
                request,
                response,
                workflow_state=workflow_state,
            )
        with self._session_guard():
            tool_message_id = "m-" + uuid.uuid4().hex[:12]
            parent_message_id = session.last_message_id()
            finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._append_transcript_event(
                session,
                "tool_result",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "call_id": action.call_id,
                    "tool_name": action.name,
                    "arguments": dict(action.arguments),
                    "message_id": tool_message_id,
                    "parent_message_id": parent_message_id,
                    "finished_at": finished_at,
                    "observation": observation.to_dict(),
                },
            )
            session.add_observation(
                action,
                observation,
                message_id=tool_message_id,
                parent_message_id=parent_message_id,
                turn_id=turn_id,
                step_id=step_id,
                finished_at=finished_at,
            )
        if on_tool_finish is not None:
            on_tool_finish(action, observation)
        return current_mode

    def _call_llm_with_retry(
        self,
        messages: list,
        tool_schemas: list,
        stream: bool,
        on_text_delta: Optional[Callable[[str], None]],
        on_reasoning_delta: Optional[Callable[[str], None]],
    ) -> AssistantReply:
        return self._llm_wrapper.call_with_retry(
            messages=messages,
            tools=tool_schemas,
            stream=stream,
            on_text_delta=on_text_delta,
            on_reasoning_delta=on_reasoning_delta,
        )

    def _persist_summary(
        self, session: Session, current_mode: str, assembly: Optional[ContextAssemblyResult] = None
    ) -> None:
        with self._session_guard():
            summary_ref = None
            try:
                summary_ref = self.summary_store.persist(session, current_mode, assembly)
            except (OSError, ValueError, TypeError) as exc:
                _LOG.warning("session summary persist failed: %s", exc)
            try:
                self.project_memory_store.refresh(session, current_mode, summary_ref)
            except (OSError, ValueError, TypeError) as exc:
                _LOG.warning("project memory refresh failed: %s", exc)
            try:
                session.trim_old_observations(30)
            except (ValueError, TypeError) as exc:
                _LOG.warning("session trim failed: %s", exc)
        self._maybe_maintain_memory()

    def _maybe_record_compact_boundary(
        self, session: Session, current_mode: str, assembly: ContextAssemblyResult
    ) -> bool:
        if not assembly.compacted or not assembly.summary_message or assembly.summarized_turns <= 0:
            return False
        with self._session_guard():
            compacted_turn_count = max(0, len(session.turns) - assembly.recent_turns)
            latest = session.latest_compact_boundary()
            if latest is not None and latest.compacted_turn_count == compacted_turn_count:
                return False
            preserved_head_message_id, preserved_tail_message_id = (
                session.preserved_segment_message_ids(assembly.recent_turns)
            )
            boundary = session.add_compact_boundary(
                assembly.summary_message,
                compacted_turn_count,
                current_mode,
                {
                    "approx_tokens": assembly.approx_tokens,
                    "replacements": len(assembly.replacements),
                    "pipeline_steps": list(assembly.pipeline_steps),
                },
                preserved_head_message_id=preserved_head_message_id,
                preserved_tail_message_id=preserved_tail_message_id,
            )
            self._append_transcript_event(
                session,
                "compact_boundary",
                {
                    "boundary_id": boundary.boundary_id,
                    "summary_text": boundary.summary_text,
                    "compacted_turn_count": boundary.compacted_turn_count,
                    "created_at": boundary.created_at,
                    "mode_name": boundary.mode_name,
                    "preserved_head_message_id": boundary.preserved_head_message_id,
                    "preserved_tail_message_id": boundary.preserved_tail_message_id,
                    "metadata": dict(boundary.metadata),
                },
            )
            return True

    def _maybe_maintain_memory(self, force: bool = False) -> None:
        self._maintenance_counter += 1
        if not force and self._maintenance_counter < self.maintenance_interval:
            return
        self._maintenance_counter = 0
        try:
            self.memory_maintenance.run()
        except (RuntimeError, ValueError, TypeError) as exc:
            _LOG.warning("memory maintenance failed: %s", exc)

    def _failure_observation(
        self,
        tool_name: str,
        error: str,
        error_kind: str,
        retryable: bool,
        blocked_by: str,
        suggested_next_step: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Observation:
        data = {
            "error_kind": error_kind,
            "retryable": retryable,
            "blocked_by": blocked_by,
            "suggested_next_step": suggested_next_step,
        }
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
