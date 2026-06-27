from __future__ import annotations  # noqa: I001

import logging
import threading
import time
import uuid
from copy import deepcopy
from typing import Any, Callable, Dict, Optional, Tuple

from embedagent.agent_extension_host import AgentExtensionHost
from embedagent.agent_kernel import AgentKernel
from embedagent.agent_lifecycle import AgentLifecycleJournal
from embedagent.agent_loop import AgentLoop
from embedagent.agent_tool_action_service import AgentToolActionService
from embedagent.compacted_history import CompactedHistoryReducer
from embedagent.compaction_journal import CompactionJournal
from embedagent.context import ContextManager
from embedagent.context_window import ContextWindowState
from embedagent.extensions import (
    ExtensionContext,
    ExtensionManager,
    WorkflowEvent,
)
from embedagent.interaction import (
    UserInputRequest,
    UserInputResponse,
)
from embedagent.llm import ModelClientError, OpenAICompatibleClient
from embedagent.strategies.execution_tracer import ExecutionTracer, TraceEventType
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.modes import (
    DEFAULT_MODE,
    build_system_prompt,
    allowed_tools_for,
    parse_mode_command,
    parse_natural_language_mode_switch,
    require_mode,
)
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.prompt_assembly_service import PromptAssemblyService
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import (
    Action,
    AssistantReply,
    ContextAssemblyResult,
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
from embedagent.tools import ToolRuntime
from embedagent.transcript_store import TranscriptStore
from embedagent.turn_snapshot import TurnSnapshot
from embedagent.turn_snapshot_service import TurnSnapshotService
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
_OPERATION_RUNTIME_ERRORS = (OSError, RuntimeError, ValueError, TypeError, KeyError, AttributeError)


class QueryEngine(object):
    def __init__(
        self,
        client: OpenAICompatibleClient,
        tools: ToolRuntime,
        max_turns: Optional[int] = None,
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
        extension_manager: Optional[ExtensionManager] = None,
        runtime_config_provider: Optional[Callable[[Session], Dict[str, Any]]] = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.permission_policy = permission_policy or PermissionPolicy(auto_approve_all=True)
        self.project_memory_store = project_memory_store or ProjectMemoryStore(self.tools.workspace)
        self.context_manager = context_manager or ContextManager(
            project_memory=self.project_memory_store
        )
        self._compaction_journal = CompactionJournal()
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
        self._runtime_config_provider = runtime_config_provider
        self.extension_host = AgentExtensionHost(
            manager=extension_manager or ExtensionManager(),
            tools=self.tools,
            permission_policy=self.permission_policy,
            mode_allowed_tools=allowed_tools_for,
        )
        self.extension_manager = self.extension_host.manager
        self.extension_manager.register_context_reducers(self.context_manager.reducers)
        category_setter = getattr(self.permission_policy, "set_category_lookup", None)
        if callable(category_setter):
            category_setter(self._tool_permission_category)
        self._session_lock = threading.RLock()
        self.lifecycle = AgentLifecycleJournal(
            append_event=self._append_transcript_event,
            session_guard=self._session_guard,
        )
        self._action_service = AgentToolActionService(
            tools=self.tools,
            permission_policy=self.permission_policy,
            extension_host=self.extension_host,
            app_config_provider=lambda: getattr(self.tools, "app_config", None),
            failure_observation_factory=self._failure_observation,
            permission_pending_handler=self._build_permission_pending_result,
            permission_rejected_handler=self._record_permission_rejection,
            user_input_pending_handler=self._build_user_input_pending_result,
            user_input_response_handler=self._build_user_input_observation,
            lifecycle=self.lifecycle,
        )
        self._llm_wrapper = LLMClientRetryWrapper(
            client=client,
            max_retries=_LLM_MAX_RETRIES,
            base_delay=_LLM_RETRY_BASE_DELAY,
        )
        self._turn_snapshots = TurnSnapshotService()
        self._prompt_assembly = PromptAssemblyService()
        self._last_turn_snapshot = None  # type: Optional[TurnSnapshot]
        self.kernel = AgentKernel(lifecycle=self.lifecycle)
        self.tool_commit = ToolCommitCoordinator(
            self.tools.tool_result_store,
            self.tools.projection_db,
            self.transcript_store,
        )
        self._maintenance_counter = 0
        self._agent_loop = AgentLoop(
            max_turns=self.max_turns,
            max_parallel_tools=self.max_parallel_tools,
            tool_capabilities=getattr(self.tools, "tool_capabilities", None),
            session_guard=self._session_guard,
            append_transcript_event=self._append_transcript_event,
            append_message_event=self._append_message_event,
            emit_operation_started=self._emit_operation_started,
            emit_lifecycle_event=self._emit_lifecycle_event,
            emit_step_finished=self._emit_step_finished,
            turn_id=self._turn_id,
            record_transition=self._record_transition,
            build_context_operation=self._build_context_operation,
            record_context_snapshot_operation=self._record_context_snapshot_operation,
            persist_summary=self._persist_summary,
            extension_host=self.extension_host,
            call_provider_operation=self._call_provider_operation,
            should_retry_with_compact=self._should_retry_with_compact,
            maybe_record_compact_boundary=self._maybe_record_compact_boundary,
            maybe_maintain_memory=self._maybe_maintain_memory,
            classify_assistant_turn=self.classify_assistant_turn,
            tool_presentation_snapshot=self._tool_presentation_snapshot,
            action_service=self._action_service,
            record_tool_observation=self._record_tool_observation,
            discarded_observation=self._discarded_observation,
            interrupted_observation=self._interrupted_observation,
            is_interrupted_observation=self._is_interrupted_observation,
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

    def last_turn_snapshot(self) -> Optional[TurnSnapshot]:
        return self._last_turn_snapshot

    def _session_guard(self):
        return self._session_lock

    def _append_transcript_event(
        self, session: Session, event_type: str, payload: Dict[str, Any], schema_version: int = 1
    ) -> None:
        if self.transcript_store is None:
            return
        self.transcript_store.append_event(
            session.session_id, event_type, payload, schema_version=schema_version
        )

    def _emit_lifecycle_event(
        self, session: Session, event_type: str, payload: Dict[str, Any]
    ) -> None:
        self.lifecycle.emit_lifecycle_event(session, event_type, payload)

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

    def _emit_operation_finished(
        self,
        session: Session,
        operation_id: str,
        kind: str = "",
        turn_id: str = "",
        step_id: str = "",
        tool_call_id: str = "",
        finished_at: str = "",
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.lifecycle.emit_operation_finished(
            session,
            operation_id,
            kind=kind,
            turn_id=turn_id,
            step_id=step_id,
            tool_call_id=tool_call_id,
            finished_at=finished_at,
            result=result,
        )

    def _emit_operation_interrupted(
        self,
        session: Session,
        operation_id: str,
        kind: str = "",
        turn_id: str = "",
        step_id: str = "",
        tool_call_id: str = "",
        reason: str = "",
        finished_at: str = "",
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.lifecycle.emit_operation_interrupted(
            session,
            operation_id,
            kind=kind,
            turn_id=turn_id,
            step_id=step_id,
            tool_call_id=tool_call_id,
            reason=reason,
            finished_at=finished_at,
            result=result,
        )

    def _turn_id(self, session: Session) -> str:
        return self.lifecycle.turn_id(session)

    def _context_operation_metadata(
        self, mode_name: str, workflow_state: str, force_compact: bool
    ) -> Dict[str, Any]:
        return self.lifecycle.context_operation_metadata(mode_name, workflow_state, force_compact)

    def _context_operation_result(self, assembly: ContextAssemblyResult) -> Dict[str, Any]:
        return self.lifecycle.context_operation_result(assembly)

    def _context_snapshot_payload(
        self, current_mode: str, assembly: ContextAssemblyResult
    ) -> Dict[str, Any]:
        return self.lifecycle.context_snapshot_payload(current_mode, assembly)

    def _record_context_snapshot_operation(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        turn_id: str,
        step_id: str,
        operation_id: str,
        assembly: ContextAssemblyResult,
    ) -> None:
        snapshot = self._context_snapshot_payload(current_mode, assembly)
        self._emit_operation_started(
            session,
            operation_id,
            "context_snapshot",
            turn_id=turn_id,
            step_id=step_id,
            parent_operation_id="context:%s" % step_id if step_id else "",
            metadata={
                "mode_name": current_mode,
                "workflow_state": workflow_state,
            },
        )
        session.record_context_snapshot(snapshot)
        self._append_transcript_event(session, "context_snapshot", snapshot)
        self._emit_operation_finished(
            session,
            operation_id,
            kind="context_snapshot",
            turn_id=turn_id,
            step_id=step_id,
            result=snapshot,
        )

    def _provider_operation_result(self, reply: AssistantReply) -> Dict[str, Any]:
        return {
            "finish_reason": reply.finish_reason,
            "action_count": len(reply.actions),
            "content_length": len(reply.content or ""),
            "reasoning_length": len(reply.reasoning_content or ""),
        }

    def _emit_turn_started(
        self,
        session: Session,
        turn_id: str,
        current_mode: str,
        workflow_state: str,
        source: str,
    ) -> None:
        self.lifecycle.emit_turn_started(session, turn_id, current_mode, workflow_state, source)

    def _emit_turn_finished(
        self,
        session: Session,
        turn_id: str,
        transition: LoopTransition,
        current_mode: str,
        workflow_state: str,
    ) -> None:
        self.lifecycle.emit_turn_finished(
            session, turn_id, transition, current_mode, workflow_state
        )

    def _emit_turn_interrupted(
        self,
        session: Session,
        turn_id: str,
        reason: str,
        current_mode: str,
        workflow_state: str,
        error: str = "",
    ) -> None:
        self.lifecycle.emit_turn_interrupted(
            session, turn_id, reason, current_mode, workflow_state, error=error
        )

    def _pending_operation_metadata(self, pending: PendingInteraction) -> Dict[str, Any]:
        return self.lifecycle.pending_operation_metadata(pending)

    def _emit_pending_started(
        self,
        session: Session,
        pending: PendingInteraction,
        turn_id: str,
        step_id: str,
    ) -> None:
        self.lifecycle.emit_pending_started(session, pending, turn_id, step_id)

    def _emit_pending_finished(
        self,
        session: Session,
        pending: PendingInteraction,
        turn_id: str,
        step_id: str,
        resolution_status: str,
    ) -> None:
        self.lifecycle.emit_pending_finished(session, pending, turn_id, step_id, resolution_status)

    def _emit_step_finished(
        self,
        session: Session,
        turn_id: str,
        step_id: str,
        reason: str,
        message: str = "",
        turns_used: int = 0,
    ) -> None:
        self.lifecycle.emit_step_finished(
            session,
            turn_id,
            step_id,
            reason,
            message=message,
            turns_used=turns_used,
        )

    def _emit_step_interrupted(
        self,
        session: Session,
        turn_id: str,
        step_id: str,
        reason: str,
        message: str = "",
        turns_used: int = 0,
    ) -> None:
        self.lifecycle.emit_step_interrupted(
            session,
            turn_id,
            step_id,
            reason,
            message=message,
            turns_used=turns_used,
        )

    def _build_context_operation(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        force_compact: bool,
        turn_id: str,
        step_id: str,
        operation_id: str,
    ) -> ContextAssemblyResult:
        self._emit_operation_started(
            session,
            operation_id,
            "context_assembly",
            turn_id=turn_id,
            step_id=step_id,
            parent_operation_id="step:%s" % step_id if step_id else "",
            metadata=self._context_operation_metadata(current_mode, workflow_state, force_compact),
        )
        try:
            assembly = self._build_context(
                session, current_mode, workflow_state, force_compact=force_compact
            )
        except _OPERATION_RUNTIME_ERRORS as exc:
            self._emit_operation_interrupted(
                session,
                operation_id,
                kind="context_assembly",
                turn_id=turn_id,
                step_id=step_id,
                reason="context_assembly_error",
                result={"error": str(exc)},
            )
            raise
        self._emit_operation_finished(
            session,
            operation_id,
            kind="context_assembly",
            turn_id=turn_id,
            step_id=step_id,
            result=self._context_operation_result(assembly),
        )
        return assembly

    def _call_provider_operation(
        self,
        session: Session,
        operation_id: str,
        turn_id: str,
        step_id: str,
        current_mode: str,
        workflow_state: str,
        messages: list,
        tool_schemas: list,
        stream: bool,
        on_text_delta: Optional[Callable[[str], None]],
        on_reasoning_delta: Optional[Callable[[str], None]],
    ) -> AssistantReply:
        snapshot = self._turn_snapshots.build_provider_snapshot(
            session=session,
            turn_id=turn_id,
            step_id=step_id,
            mode_name=current_mode,
            workflow_state=workflow_state,
            messages=messages,
            tool_schemas=tool_schemas,
            tools=self.tools,
            client=self.client,
            transcript_store=self.transcript_store,
            runtime_config_provider=self._runtime_config_provider,
        )
        self._last_turn_snapshot = snapshot
        snapshot_metadata = self._turn_snapshots.metadata(snapshot)
        self._emit_operation_started(
            session,
            operation_id,
            "provider_request",
            turn_id=turn_id,
            step_id=step_id,
            parent_operation_id="step:%s" % step_id if step_id else "",
            retryable=True,
            metadata={
                "mode_name": current_mode,
                "workflow_state": workflow_state,
                "message_count": len(snapshot.messages),
                "tool_schema_count": len(snapshot.tool_schemas),
                "stream": bool(stream),
                "turn_snapshot": snapshot_metadata,
            },
        )
        try:
            reply = self._call_llm_with_retry(
                snapshot.messages,
                snapshot.tool_schemas,
                stream,
                on_text_delta,
                on_reasoning_delta,
            )
        except ModelClientError as exc:
            self._emit_operation_interrupted(
                session,
                operation_id,
                kind="provider_request",
                turn_id=turn_id,
                step_id=step_id,
                reason="model_client_error",
                result={"error": str(exc)},
            )
            raise
        except _OPERATION_RUNTIME_ERRORS as exc:
            self._emit_operation_interrupted(
                session,
                operation_id,
                kind="provider_request",
                turn_id=turn_id,
                step_id=step_id,
                reason="provider_request_error",
                result={"error": str(exc)},
            )
            raise
        self._emit_operation_finished(
            session,
            operation_id,
            kind="provider_request",
            turn_id=turn_id,
            step_id=step_id,
            result=dict(
                self._provider_operation_result(reply),
                turn_snapshot=snapshot_metadata,
            ),
        )
        return reply

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
                self._append_message_event(session, self._message_event_payload(message))
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

    def _should_inject_workflow_prompt(self, user_text: str, current_mode: str) -> bool:
        return self.extension_host.should_inject_workflow(user_text, current_mode)

    def _tool_permission_category(self, tool_name: str) -> str:
        lookup = getattr(self.tools, "tool_catalog_entry", None)
        if not callable(lookup):
            return ""
        entry = lookup(tool_name) or {}
        if not isinstance(entry, dict):
            return ""
        return str(entry.get("permission_category") or "")

    def _extension_context(self, session: Session) -> ExtensionContext:
        return self.extension_host.context_for(session)

    def _workflow_event(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        **metadata: Any,
    ) -> WorkflowEvent:
        return self.extension_host.workflow_event(
            session,
            current_mode,
            workflow_state,
            **metadata,
        )

    def _ensure_extension_tools_registered(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        reason: str = "turn",
    ) -> None:
        self.extension_host.register_tools(session, current_mode, workflow_state, reason=reason)

    def _append_workflow_prompt_messages(self, session: Session, workflow_prompt: Any) -> None:
        def append_event(message: Any) -> None:
            self._append_message_event(
                session,
                self._prompt_assembly.message_event_payload(message),
            )

        self._prompt_assembly.append_workflow_prompt_messages(
            workflow_prompt,
            session.messages,
            session.add_system_message,
            on_message=append_event,
        )

    def _build_system_prompt(self, mode_name: str) -> str:
        resources = {}
        local_resources = getattr(self.tools, "local_resources", None)
        if callable(local_resources):
            resources = local_resources()
        return build_system_prompt(
            mode_name,
            getattr(self.tools, "app_config", None),
            getattr(self.tools, "workspace", ""),
            local_resources=resources,
        )

    def initialize_session(
        self, session: Session, initial_mode: str, workflow_state: str = "chat", user_text: str = ""
    ) -> str:
        current_mode = require_mode(initial_mode)["slug"]
        self._ensure_extension_tools_registered(
            session,
            current_mode,
            workflow_state,
            reason="session_start",
        )
        if self._should_inject_workflow_prompt(user_text, current_mode):
            workflow_prompt = self.extension_host.describe_prompt(
                current_mode, workflow_state=workflow_state, session=session
            )
        else:
            workflow_prompt = None
        if session.messages:
            self._ensure_transcript_bootstrap(session, current_mode)
            with self._session_guard():
                self._append_workflow_prompt_messages(session, workflow_prompt)
            return current_mode
        with self._session_guard():
            profile_message = session.add_system_message(
                build_workspace_profile_message(self.tools.workspace, session.session_id)
            )
            system_message = session.add_system_message(self._build_system_prompt(current_mode))
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
            self._append_workflow_prompt_messages(session, workflow_prompt)
        return current_mode

    def apply_mode(
        self, session: Session, next_mode: str, workflow_state: str = "chat", user_text: str = ""
    ) -> str:
        current_mode = require_mode(next_mode)["slug"]
        if self._should_inject_workflow_prompt(user_text, current_mode):
            workflow_prompt = self.extension_host.describe_prompt(
                current_mode, workflow_state=workflow_state, session=session
            )
        else:
            workflow_prompt = None
        with self._session_guard():
            mode_message = session.add_system_message(self._build_system_prompt(current_mode))
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
            self._append_workflow_prompt_messages(session, workflow_prompt)
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

    def _parse_mode_switch_request(
        self, user_text: str, fallback_mode: str
    ) -> Tuple[str, str, bool]:
        mode_name, remainder, switched = parse_mode_command(user_text, fallback_mode=fallback_mode)
        if switched:
            return mode_name, remainder, True
        return parse_natural_language_mode_switch(user_text, fallback_mode=fallback_mode)

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
            session.add_user_message(
                user_text,
                turn_id=turn_id,
                message_id=message_id,
                parent_message_id=parent_message_id,
            )

    def _finish_mode_switch_turn(
        self,
        session: Session,
        turn_id: str,
        source_mode: str,
        target_mode: str,
    ) -> QueryTurnResult:
        applied_mode = require_mode(target_mode)["slug"]
        message_text = "已切换到 `%s` 模式。" % applied_mode
        reply = AssistantReply(content=message_text, actions=[], finish_reason="mode_changed")
        with self._session_guard():
            step = session.begin_step()
            step_id = step.step_id
            self._append_transcript_event(
                session,
                "step_started",
                {
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "step_index": step.step_index,
                },
            )
            self._emit_operation_started(
                session,
                "step:%s" % step_id,
                "agent_step",
                turn_id=turn_id,
                step_id=step_id,
                metadata={"step_index": step.step_index},
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
            session.add_assistant_reply(
                reply,
                message_id=message_id,
                parent_message_id=parent_message_id,
                turn_id=turn_id,
                step_id=step_id,
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

    def _interaction_checkpoint_payload(
        self,
        session: Session,
        action: Action,
        pending: PendingInteraction,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.kernel.interaction_checkpoint_payload(
            session,
            action,
            pending,
            request_data=dict(request_data or {}),
        )

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
            operation_result = {
                "success": committed.success,
                "error": committed.error,
                "error_kind": (
                    committed.data.get("error_kind") if isinstance(committed.data, dict) else ""
                ),
            }
            if self._is_interrupted_observation(committed) or (
                isinstance(committed.data, dict)
                and str(committed.data.get("error_kind") or "") == "discarded"
            ):
                self._emit_operation_interrupted(
                    session,
                    "tool:%s" % action.call_id,
                    kind="tool_call",
                    turn_id=turn_id,
                    step_id=step_id,
                    tool_call_id=action.call_id,
                    reason=str(operation_result.get("error_kind") or "tool_interrupted"),
                    finished_at=finished_at,
                    result=operation_result,
                )
            else:
                self._emit_operation_finished(
                    session,
                    "tool:%s" % action.call_id,
                    kind="tool_call",
                    turn_id=turn_id,
                    step_id=step_id,
                    tool_call_id=action.call_id,
                    finished_at=finished_at,
                    result=operation_result,
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
        session_was_empty = not bool(session.messages)
        original_user_text = user_text
        source_mode = require_mode(initial_mode)["slug"]
        target_mode, routed_user_text, mode_switched = self._parse_mode_switch_request(
            user_text,
            source_mode,
        )
        current_mode = require_mode(target_mode if mode_switched else source_mode)["slug"]
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
        try:
            result = self._agent_loop.run(
                session=session,
                current_mode=current_mode,
                workflow_state=workflow_state,
                stream=stream,
                stop_event=stop_event,
                on_text_delta=on_text_delta,
                on_reasoning_delta=on_reasoning_delta,
                on_tool_start=on_tool_start,
                on_tool_finish=on_tool_finish,
                on_context_result=on_context_result,
                on_step_start=on_step_start,
                on_step_finish=on_step_finish,
                permission_handler=permission_handler,
                user_input_handler=user_input_handler,
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
            self._emit_operation_started(
                session,
                "step:%s" % step_id,
                "agent_step",
                turn_id=command_turn_id,
                step_id=step_id,
                metadata={"step_index": step_index},
            )
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
            record = session._find_tool_call(action.call_id)
            if record is None:
                session.record_tool_call(action, presentation)
            else:
                record.presentation = presentation
        if on_step_start is not None:
            on_step_start(step_id, step_index)
        assembly = self._build_context_operation(
            session,
            current_mode,
            workflow_state,
            False,
            command_turn_id,
            step_id,
            "context:%s:1" % step_id,
        )
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
            turn_frame.finish(result.transition)
            return result, committed
        observation, current_mode, suspended = self._action_service.execute_action(
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
            turn_frame.finish(suspended.transition)
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
        turn_frame.finish(transition)
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
        resume_turn_id = self._turn_id(session) or ("t-" + uuid.uuid4().hex[:12])
        turn_frame = self.kernel.begin_turn(
            session, resume_turn_id, current_mode, workflow_state, "resume"
        )
        with self._session_guard():
            self._append_workflow_prompt_messages(
                session,
                self.extension_host.describe_prompt(
                    current_mode, workflow_state=workflow_state, session=session
                ),
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
        try:
            result = self._agent_loop.run(
                session=session,
                current_mode=current_mode,
                workflow_state=workflow_state,
                stream=stream,
                stop_event=stop_event,
                on_text_delta=on_text_delta,
                on_reasoning_delta=on_reasoning_delta,
                on_tool_start=on_tool_start,
                on_tool_finish=on_tool_finish,
                on_context_result=on_context_result,
                on_step_start=on_step_start,
                on_step_finish=on_step_finish,
                permission_handler=permission_handler,
                user_input_handler=user_input_handler,
            )
        except BaseException as exc:
            turn_frame.interrupt("resume_error", error=str(exc))
            raise
        turn_frame.finish(result.transition)
        return result

    def classify_assistant_turn(self, reply, session=None) -> str:
        """Classify one provider reply for loop continuation decisions."""

        del session
        if reply.actions:
            return "tool_calls"
        if str(reply.content or "").strip():
            return "final_message"
        return "empty_noop"

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
            assembly = build
        else:
            assembly = ContextAssemblyResult(
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
                plan=getattr(build, "plan", None),
            )
        return self.extension_host.apply_context_patch(
            session,
            mode_name,
            workflow_state,
            assembly,
            force_compact=force_compact,
        )

    def _should_retry_with_compact(self, exc: ModelClientError) -> bool:
        text = str(exc or "").lower()
        if not text:
            return False
        for marker in _COMPACT_RETRY_ERROR_MARKERS:
            if marker in text:
                return True
        return False

    def _record_permission_rejection(self, session: Session, action: Action) -> None:
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

    def _build_permission_pending_result(
        self,
        session: Session,
        action: Action,
        request: PermissionRequest,
        current_mode: str,
    ) -> QueryTurnResult:
        permission_payload = {
            "tool_name": request.tool_name,
            "category": request.category,
            "reason": request.reason,
            "details": dict(request.details),
        }
        pending, transition = self.kernel.record_pending_permission(
            session,
            action,
            permission_payload,
            current_mode,
        )
        return QueryTurnResult("", session, transition, pending_interaction=pending)

    def _build_user_input_pending_result(
        self,
        session: Session,
        action: Action,
        request: UserInputRequest,
        current_mode: str,
    ) -> QueryTurnResult:
        request_payload = {
            "tool_name": request.tool_name,
            "question": request.question,
            "options": [
                {"index": item.index, "text": item.text, "mode": item.mode}
                for item in request.options
            ],
            "details": dict(request.details),
        }
        pending, transition = self.kernel.record_pending_user_input(
            session,
            action,
            request.tool_name,
            request_payload,
            request.question,
            current_mode,
        )
        return QueryTurnResult("", session, transition, pending_interaction=pending)

    def _build_user_input_observation(
        self,
        session: Session,
        current_mode: str,
        request: UserInputRequest,
        response: UserInputResponse,
        workflow_state: str = "chat",
        tool_name: str = "ask_user",
    ) -> Tuple[Observation, str]:
        request_tool_name = tool_name or request.tool_name or "ask_user"
        selected_mode = str(response.selected_mode or "").strip()
        if not selected_mode and request_tool_name == "propose_mode_switch":
            selected_mode = str(request.details.get("target_mode") or "").strip()
        next_mode = current_mode
        mode_changed = False
        if selected_mode:
            selected_mode = str(require_mode(selected_mode)["slug"])
            if selected_mode != current_mode:
                next_mode = selected_mode
                mode_changed = True
                with self._session_guard():
                    mode_message = session.add_system_message(
                        self._build_system_prompt(selected_mode)
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
                    self._append_workflow_prompt_messages(
                        session,
                        self.extension_host.describe_prompt(
                            selected_mode, workflow_state=workflow_state, session=session
                        ),
                    )
        return (
            Observation(
                request_tool_name,
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
            self.kernel.resolve_pending_interaction(session, pending, resolution)
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
                observation, current_mode, suspended = self._action_service.execute_action(
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
            response = UserInputResponse(
                answer=str(resolution.get("answer") or ""),
                selected_index=resolution.get("selected_index"),
                selected_mode=str(resolution.get("selected_mode") or ""),
                selected_option_text=str(resolution.get("selected_option_text") or ""),
            )
            observation, current_mode, suspended = self._action_service.execute_action(
                session,
                action,
                current_mode,
                workflow_state,
                permission_handler=None,
                user_input_handler=lambda request: response,
            )
            if suspended is not None:
                raise RuntimeError("user input resume unexpectedly re-suspended")
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
            self._emit_operation_finished(
                session,
                "tool:%s" % action.call_id,
                kind="tool_call",
                turn_id=turn_id,
                step_id=step_id,
                tool_call_id=action.call_id,
                finished_at=finished_at,
                result={
                    "success": observation.success,
                    "error": observation.error,
                    "error_kind": (
                        observation.data.get("error_kind")
                        if isinstance(observation.data, dict)
                        else ""
                    ),
                },
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
            window_state = ContextWindowState.from_pipeline_steps(
                list(getattr(assembly, "pipeline_steps", []) or []),
                len(getattr(session, "compact_boundaries", []) or []),
            )
            metadata = {
                "approx_tokens": assembly.approx_tokens,
                "replacements": len(assembly.replacements),
                "pipeline_steps": list(assembly.pipeline_steps),
            }
            plan = getattr(assembly, "plan", None)
            plan_metadata = getattr(plan, "to_boundary_metadata", None)
            if callable(plan_metadata):
                metadata.update(dict(plan_metadata()))
            metadata = window_state.extend_metadata(metadata)
            boundary = session.add_compact_boundary(
                assembly.summary_message,
                compacted_turn_count,
                current_mode,
                metadata,
                preserved_head_message_id=preserved_head_message_id,
                preserved_tail_message_id=preserved_tail_message_id,
            )
            plan_payload = {}
            plan_payload_fields = getattr(plan, "to_boundary_payload_fields", None)
            if callable(plan_payload_fields):
                plan_payload = dict(plan_payload_fields())
            compaction_payloads = self._compaction_journal.build_payloads(
                boundary,
                assembly,
                window_state,
                plan_payload,
            )
            self._append_transcript_event(
                session,
                "compact_boundary",
                compaction_payloads["compact_boundary"],
            )
            compacted_history_state = CompactedHistoryReducer().reduce(
                [
                    {
                        "type": "compacted_history",
                        "payload": compaction_payloads["compacted_history"],
                    }
                ]
            )
            checkpoint = compacted_history_state.latest_checkpoint
            if checkpoint is not None:
                session.record_compacted_history(checkpoint)
                self._append_transcript_event(
                    session,
                    "compacted_history",
                    compaction_payloads["compacted_history"],
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
