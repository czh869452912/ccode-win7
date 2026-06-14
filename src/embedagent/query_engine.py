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
from embedagent.context import ContextManager
from embedagent.extensions import (
    ExtensionContext,
    ExtensionManager,
    WorkflowEvent,
)
from embedagent.interaction import (
    UserInputRequest,
    UserInputResponse,
    build_user_input_request,
)
from embedagent.llm import ModelClientError, OpenAICompatibleClient
from embedagent.strategies.context_compaction_engine import ContextCompactionEngine
from embedagent.strategies.execution_tracer import ExecutionTracer, TraceEventType
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper
from embedagent.strategies.turn_orchestrator import TurnOrchestrator
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.modes import (
    DEFAULT_MODE,
    build_system_prompt,
    allowed_tools_for,
    require_mode,
)
from embedagent.permissions import PermissionPolicy, PermissionRequest
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
        extension_manager: Optional[ExtensionManager] = None,
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
        self.extension_host = AgentExtensionHost(
            manager=extension_manager or ExtensionManager(),
            tools=self.tools,
            permission_policy=self.permission_policy,
            mode_allowed_tools=allowed_tools_for,
        )
        self.extension_manager = self.extension_host.manager
        category_setter = getattr(self.permission_policy, "set_category_lookup", None)
        if callable(category_setter):
            category_setter(self._tool_permission_category)
        self._action_service = AgentToolActionService(
            tools=self.tools,
            permission_policy=self.permission_policy,
            extension_host=self.extension_host,
            app_config_provider=lambda: getattr(self.tools, "app_config", None),
            failure_observation_factory=self._failure_observation,
            permission_pending_handler=self._build_permission_pending_result,
            permission_rejected_handler=self._record_permission_rejection,
        )
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
        self.lifecycle = AgentLifecycleJournal(
            append_event=self._append_transcript_event,
            session_guard=self._session_guard,
        )
        self.kernel = AgentKernel(lifecycle=self.lifecycle)
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
            allowed_tool_names=self._allowed_tools_for_mode,
        )
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
            schemas_for_active_tools=self._schemas_for_active_tools,
            call_provider_operation=self._call_provider_operation,
            should_retry_with_compact=self._should_retry_with_compact,
            maybe_record_compact_boundary=self._maybe_record_compact_boundary,
            maybe_maintain_memory=self._maybe_maintain_memory,
            is_completion_signal=self._is_completion_signal,
            tool_presentation_snapshot=self._tool_presentation_snapshot,
            execute_parallel_tool_action=self._execute_parallel_tool_action,
            execute_action=self._execute_action,
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

    def _workflow_patch_snapshot(self, session: Session) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        workflow_root = getattr(session, "workflow_state", {}) or {}
        workflow = {}
        metadata = {}
        if isinstance(workflow_root, dict):
            workflow = dict(workflow_root.get("workflow") or {})
            extensions = workflow_root.get("extensions") or {}
            if isinstance(extensions, dict):
                metadata = dict(extensions.get("last_workflow_patch") or {})
        return workflow, metadata

    def _workflow_patch_payload(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        turn_id: str,
        step_id: str,
        tool_call_id: str,
    ) -> Dict[str, Any]:
        workflow, metadata = self._workflow_patch_snapshot(session)
        return {
            "turn_id": turn_id,
            "step_id": step_id,
            "tool_call_id": tool_call_id,
            "mode_name": current_mode,
            "workflow_state_name": workflow_state,
            "workflow": workflow,
            "metadata": metadata,
        }

    def _workflow_patch_changed(
        self,
        before_workflow: Dict[str, Any],
        before_metadata: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> bool:
        workflow = dict(payload.get("workflow") or {})
        metadata = dict(payload.get("metadata") or {})
        return bool(workflow or metadata) and (
            workflow != before_workflow or metadata != before_metadata
        )

    def _persist_workflow_patch(self, session: Session, payload: Dict[str, Any]) -> None:
        turn_id = str(payload.get("turn_id") or "")
        step_id = str(payload.get("step_id") or "")
        tool_call_id = str(payload.get("tool_call_id") or "")
        operation_id = "workflow_patch:%s:%s" % (step_id or "session", tool_call_id or "patch")
        self._emit_operation_started(
            session,
            operation_id,
            "workflow_patch",
            turn_id=turn_id,
            step_id=step_id,
            tool_call_id=tool_call_id,
            parent_operation_id="tool:%s" % tool_call_id if tool_call_id else "",
            metadata={
                "mode_name": str(payload.get("mode_name") or ""),
                "workflow_state_name": str(payload.get("workflow_state_name") or ""),
            },
        )
        self._append_transcript_event(session, "workflow_patch", dict(payload), schema_version=2)
        self._emit_operation_finished(
            session,
            operation_id,
            kind="workflow_patch",
            turn_id=turn_id,
            step_id=step_id,
            tool_call_id=tool_call_id,
            result={
                "workflow": dict(payload.get("workflow") or {}),
                "metadata": dict(payload.get("metadata") or {}),
            },
        )

    def _capture_workflow_patch_if_changed(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        before_workflow: Dict[str, Any],
        before_metadata: Dict[str, Any],
    ) -> None:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step_id = session.current_step().step_id if session.current_step() is not None else ""
        payload = self._workflow_patch_payload(
            session,
            current_mode,
            workflow_state,
            turn_id,
            step_id,
            action.call_id,
        )
        if self._workflow_patch_changed(before_workflow, before_metadata, payload):
            self._persist_workflow_patch(session, payload)

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
                "message_count": len(messages),
                "tool_schema_count": len(tool_schemas),
                "stream": bool(stream),
            },
        )
        try:
            reply = self._call_llm_with_retry(
                messages,
                tool_schemas,
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
            result=self._provider_operation_result(reply),
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

    def _should_inject_harness(self, user_text: str, current_mode: str) -> bool:
        return self.extension_host.should_inject_workflow(user_text, current_mode)

    def _allowed_tools_for_mode(self, mode_name: str, workflow_state: str = "chat") -> set:
        return set(self.extension_host.allowed_tool_names(mode_name, workflow_state=workflow_state))

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

    def _append_harness_messages(self, session: Session, harness_prompt: Any) -> None:
        if harness_prompt is None:
            return
        existing = False
        for message in list(session.messages):
            if message.role != "system" or message.kind != "harness_prompt":
                continue
            metadata = dict(getattr(message, "metadata", {}) or {})
            if str(metadata.get("mode_name") or "") != str(harness_prompt.mode_name or ""):
                continue
            if str(metadata.get("discipline_label") or "") != str(
                harness_prompt.discipline_label or ""
            ):
                continue
            existing = True
            break
        if existing:
            return
        for index, content in enumerate(list(getattr(harness_prompt, "prompt_units", []) or [])):
            harness_message = session.add_system_message(
                content,
                kind="harness_prompt",
                metadata={
                    "mode_name": str(harness_prompt.mode_name or ""),
                    "discipline_label": str(harness_prompt.discipline_label or ""),
                    "pack_name": str(harness_prompt.pack_name or ""),
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
        self, session: Session, initial_mode: str, workflow_state: str = "chat", user_text: str = ""
    ) -> str:
        current_mode = require_mode(initial_mode)["slug"]
        self._ensure_extension_tools_registered(
            session,
            current_mode,
            workflow_state,
            reason="session_start",
        )
        if self._should_inject_harness(user_text, current_mode):
            harness_prompt = self.extension_host.describe_prompt(
                current_mode, workflow_state=workflow_state, session=session
            )
        else:
            harness_prompt = None
        if session.messages:
            self._ensure_transcript_bootstrap(session, current_mode)
            with self._session_guard():
                self._append_harness_messages(session, harness_prompt)
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
            self._append_harness_messages(session, harness_prompt)
        return current_mode

    def apply_mode(
        self, session: Session, next_mode: str, workflow_state: str = "chat", user_text: str = ""
    ) -> str:
        current_mode = require_mode(next_mode)["slug"]
        if self._should_inject_harness(user_text, current_mode):
            harness_prompt = self.extension_host.describe_prompt(
                current_mode, workflow_state=workflow_state, session=session
            )
        else:
            harness_prompt = None
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
            self._append_harness_messages(session, harness_prompt)
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
        current_mode = self.initialize_session(
            session, initial_mode, workflow_state=workflow_state, user_text=user_text
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
            self._append_harness_messages(
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
        except BaseException as exc:
            turn_frame.interrupt("resume_error", error=str(exc))
            raise
        turn_frame.finish(result.transition)
        return result

    def _is_completion_signal(self, reply, session) -> bool:
        """Detect if agent is signaling task completion.

        Signals:
        - finish_reason == "completed" or "stop"
        - No tool calls requested
        - Content contains completion markers
        """
        if reply.finish_reason in ("completed", "stop"):
            return True
        if not reply.actions:
            return True
        return False

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
        return self._agent_loop.run(
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

    def _schemas_for_active_tools(self, mode_name: str, workflow_state: str) -> list:
        return self.extension_host.schemas_for_active_tools(mode_name, workflow_state)

    def _prepare_extension_tool_call(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
    ) -> Tuple[Optional[Observation], Action]:
        return self._action_service.prepare_extension_tool_call(
            session,
            action,
            current_mode,
            workflow_state,
        )

    def _execute_parallel_tool_action(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        stop_event: Optional[threading.Event],
    ) -> Observation:
        return self._action_service.execute_parallel_tool_action(
            session,
            action,
            current_mode,
            workflow_state,
            stop_event,
        )

    def _is_extension_blocked_observation(self, observation: Optional[Observation]) -> bool:
        return self._action_service.is_extension_blocked_observation(observation)

    def _is_interactive_precomputed_skip(self, observation: Optional[Observation]) -> bool:
        return self._action_service.is_interactive_precomputed_skip(observation)

    def _apply_extension_tool_result_patch(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        observation: Observation,
    ) -> Observation:
        before_workflow, before_metadata = self._workflow_patch_snapshot(session)
        patched = self._action_service.apply_extension_tool_result_patch(
            session,
            action,
            current_mode,
            workflow_state,
            observation,
        )
        self._capture_workflow_patch_if_changed(
            session,
            action,
            current_mode,
            workflow_state,
            before_workflow,
            before_metadata,
        )
        return patched

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
        if action.name not in ("ask_user", "propose_mode_switch"):
            before_workflow, before_metadata = self._workflow_patch_snapshot(session)
            result = self._action_service.execute_action(
                session,
                action,
                current_mode,
                workflow_state,
                permission_handler,
                user_input_handler,
                precomputed_observation=precomputed_observation,
                stop_event=stop_event,
            )
            self._capture_workflow_patch_if_changed(
                session,
                action,
                current_mode,
                workflow_state,
                before_workflow,
                before_metadata,
            )
            return result
        runtime_action = action
        if precomputed_observation is not None and not self._is_interactive_precomputed_skip(
            precomputed_observation
        ):
            if self._is_extension_blocked_observation(precomputed_observation):
                return precomputed_observation, current_mode, None
            observation = self._apply_extension_tool_result_patch(
                session,
                action,
                current_mode,
                workflow_state,
                precomputed_observation,
            )
            return observation, current_mode, None
        blocked_observation, runtime_action = self._prepare_extension_tool_call(
            session,
            action,
            current_mode,
            workflow_state,
        )
        if blocked_observation is not None:
            return blocked_observation, current_mode, None
        if action.name == "ask_user":
            request = build_user_input_request(runtime_action.arguments)
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
                pending, transition = self.kernel.record_pending_user_input(
                    session,
                    action,
                    "ask_user",
                    request_payload,
                    request.question,
                    current_mode,
                )
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
                        str(runtime_action.arguments.get("reason") or ""),
                        [],
                        {"target_mode": str(runtime_action.arguments.get("target_mode") or "")},
                    )
                )
                if user_input_handler is not None
                else None
            )
            if response is None:
                request_payload = {
                    "tool_name": "propose_mode_switch",
                    "question": str(runtime_action.arguments.get("reason") or ""),
                    "options": [],
                    "details": {
                        "target_mode": str(runtime_action.arguments.get("target_mode") or "")
                    },
                }
                pending, transition = self.kernel.record_pending_user_input(
                    session,
                    action,
                    "propose_mode_switch",
                    request_payload,
                    str(runtime_action.arguments.get("reason") or ""),
                    current_mode,
                )
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
                response.selected_mode or runtime_action.arguments.get("target_mode") or ""
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
                            self.extension_host.describe_prompt(
                                target_mode, workflow_state=workflow_state, session=session
                            ),
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
                        self.extension_host.describe_prompt(
                            selected_mode, workflow_state=workflow_state, session=session
                        ),
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
