from __future__ import annotations  # noqa: I001

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from embedagent.capabilities import (
    command_capability_descriptors,
    command_capability_payload,
    model_profile_capability_descriptor,
    workflow_package_capability_descriptors,
)
from embedagent.compaction_state import CompactionStateReducer
from embedagent.context import ContextManager
from embedagent.default_extensions import build_default_extension_set
from embedagent.extensions import ExtensionContext, ToolRegistrationEvent
from embedagent.interaction import UserInputRequest, UserInputResponse
from embedagent.llm import OpenAICompatibleClient
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.modes import (
    DEFAULT_MODE,
    allowed_tools_for,
    initialize_modes,
    mode_names,
    require_mode,
)
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.plan_store import PlanStore
from embedagent.project_extensions import load_project_extensions
from embedagent.project_memory import ProjectMemoryStore
from embedagent.protocol import PermissionContextView, PlanSnapshot
from embedagent.recovery_state import RecoveryStateReducer
from embedagent.hosted_command_service import HostedCommandService
from embedagent.hosted_interaction_service import (
    HostedInteractionService,
    PermissionTicket,
    UserInputTicket,
)
from embedagent.runtime_capability_service import RuntimeCapabilityService
from embedagent.runtime_config import RuntimeConfigReducer
from embedagent.session import (
    Action,
    AssistantReply,
    LoopTransition,
    Observation,
    Session,
    TurnOutcome,
)
from embedagent.session_bootstrap_service import SessionBootstrapService
from embedagent.session_history import SessionHistoryAssembler
from embedagent.session_operation_log import OperationLogReducer, operation_diagnostics
from embedagent.session_projector import SessionSnapshotProjector
from embedagent.session_restore import SessionRestorer
from embedagent.session_runtime import ManagedSession
from embedagent.session_store import SessionSummaryStore
from embedagent.services import (
    EventEmitter,
    SessionLifecycleManager,
    WorkspaceFileService,
)
from embedagent.query_engine import QueryEngine
from embedagent.skill_index import build_skill_index
from embedagent.slash_commands import (
    SlashCommandRegistry,
    parse_slash_command,
    resource_command_specs,
)
from embedagent.tools import ToolRuntime
from embedagent.transcript_store import TranscriptStore

EventHandler = Callable[[str, str, Dict[str, Any]], None]


def _display_transition_reason(reason: str) -> str:
    value = str(reason or "").strip()
    mapping = {
        "aborted": "cancelled",
        "guard_stop": "guard",
        "permission_wait": "waiting_permission",
        "permission_required": "waiting_permission",
        "user_input_wait": "waiting_user_input",
        "user_input_required": "waiting_user_input",
    }
    return mapping.get(value, value)


def _normalize_recent_transitions(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        reason = str(entry.get("reason") or entry.get("kind") or "").strip()
        if reason and not str(entry.get("display_reason") or "").strip():
            entry["display_reason"] = _display_transition_reason(reason)
        normalized.append(entry)
    return normalized


def _stable_names(names: Any) -> List[str]:
    if not isinstance(names, list):
        return []
    result = []
    seen = set()
    for name in names:
        text = str(name or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return sorted(result)


def _should_emit_context_compacted(result: object) -> bool:
    if not bool(getattr(result, "compacted", False)):
        return False
    pipeline_steps = list(getattr(result, "pipeline_steps", []) or [])
    return bool(
        "auto_compact_threshold" in pipeline_steps or "reactive_compact_retry" in pipeline_steps
    )


PermissionResolver = Callable[[Dict[str, Any]], bool]
UserInputResolver = Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _pending_interaction_payload(state: "ManagedSession") -> Optional[Dict[str, Any]]:
    if state.pending_permission is not None:
        return {
            "interaction_id": state.pending_permission.permission_id,
            "session_id": state.pending_permission.session_id,
            "kind": "permission",
            "tool_name": state.pending_permission.tool_name,
            "category": state.pending_permission.category,
            "reason": state.pending_permission.reason,
            "details": dict(state.pending_permission.details),
            "turn_id": state.pending_permission.turn_id,
            "step_id": state.pending_permission.step_id,
            "step_index": state.pending_permission.step_index,
        }
    if state.pending_user_input is not None:
        return {
            "interaction_id": state.pending_user_input.request_id,
            "session_id": state.pending_user_input.session_id,
            "kind": "user_input",
            "tool_name": state.pending_user_input.tool_name,
            "question": state.pending_user_input.question,
            "options": list(state.pending_user_input.options),
            "details": dict(state.pending_user_input.details),
            "turn_id": state.pending_user_input.turn_id,
            "step_id": state.pending_user_input.step_id,
            "step_index": state.pending_user_input.step_index,
        }
    return None


class InProcessAdapter(object):
    def __init__(
        self,
        client: Optional[OpenAICompatibleClient] = None,
        tools: Optional[ToolRuntime] = None,
        max_turns: Optional[int] = None,
        permission_policy: Optional[PermissionPolicy] = None,
        summary_store: Optional[SessionSummaryStore] = None,
        project_memory_store: Optional[ProjectMemoryStore] = None,
        context_manager: Optional[ContextManager] = None,
        memory_maintenance: Optional[MemoryMaintenance] = None,
        maintenance_interval: int = 4,
        event_handler: Optional[EventHandler] = None,
    ) -> None:
        if tools is None:
            tools = ToolRuntime(os.getcwd())
        if client is None:
            client = OpenAICompatibleClient(
                base_url="http://localhost",
                api_key="",
                model="default-model",
            )
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.permission_policy = permission_policy or PermissionPolicy(auto_approve_all=True)
        self.summary_store = summary_store or SessionSummaryStore(self.tools.workspace)
        self.project_memory_store = project_memory_store or ProjectMemoryStore(self.tools.workspace)
        self.context_manager = context_manager or ContextManager(
            project_memory=self.project_memory_store
        )
        self.memory_maintenance = memory_maintenance or MemoryMaintenance(
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
            tool_result_store=self.tools.tool_result_store,
        )
        self.maintenance_interval = maintenance_interval if maintenance_interval > 0 else 1
        self.event_handler = event_handler
        self.plan_store = PlanStore(self.tools.workspace)
        self.command_registry = SlashCommandRegistry()
        self.transcript_store = TranscriptStore(self.tools.workspace)
        self.session_restorer = SessionRestorer()
        self.snapshot_projector = SessionSnapshotProjector()
        default_extensions = build_default_extension_set(self.tools)
        self.harness_workflow = default_extensions.harness_workflow
        self.extension_manager = default_extensions.manager
        self.extension_manager.register_context_reducers(self.context_manager.reducers)
        self.project_extension_state = self._load_project_extensions()
        category_setter = getattr(self.permission_policy, "set_category_lookup", None)
        if callable(category_setter):
            category_setter(self._tool_permission_category)
        initialize_modes(self.tools.workspace)
        self._sessions = {}  # type: Dict[str, ManagedSession]
        self._lock = threading.RLock()
        self._event_emitter = EventEmitter()
        self._workspace_files = WorkspaceFileService(
            self.tools.workspace,
            getattr(self.tools, "_ctx", None),
        )
        self._session_lifecycle = SessionLifecycleManager(
            session_store=self.summary_store,
            summary_store=self.summary_store,
            plan_store=self.plan_store,
            project_memory=self.project_memory_store,
            session_restorer=self.session_restorer,
            transcript_store=self.transcript_store,
        )
        self._bootstrap_service = SessionBootstrapService(
            snapshot_loader=self.get_session_snapshot,
            history_loader=self.build_session_history,
            plan_loader=self.get_session_plan,
            permission_context_loader=self.get_permission_context,
            capability_loader=self.get_session_capabilities,
        )
        self._runtime_capabilities = RuntimeCapabilityService(
            descriptor_loader=self._capability_descriptors,
            model_descriptor_loader=lambda: model_profile_capability_descriptor(self.client),
            workflow_manifest_loader=self._workflow_package_capability_descriptors,
        )
        self.interaction_service = HostedInteractionService(
            require_session=self._require_session,
            run_turn=self._run_turn,
            get_session_snapshot=lambda session_id: self.get_session_snapshot(session_id),
            notify_status=self._notify_status,
            default_event_handler=lambda: self.event_handler,
        )
        self.command_service = HostedCommandService(
            tools=self.tools,
            command_registry=self.command_registry,
            plan_store=self.plan_store,
            max_turns=self.max_turns,
            require_session=self._require_session,
            set_session_mode=self.set_session_mode,
            resume_session=self.resume_session,
            list_sessions=self.list_sessions,
            get_workspace_snapshot=self.get_workspace_snapshot,
            list_workspace_recipes=self.list_workspace_recipes,
            reload_resources=self.reload_resources,
            list_tasks=self.list_tasks,
            list_artifacts=self.list_artifacts,
            get_permission_context=self.get_permission_context,
            emit=self._emit,
            emit_with_snapshot=self._emit_with_snapshot,
            notify_status=self._notify_status,
            persist_state=self._persist_state,
            refresh_harness_state=self._refresh_harness_state,
            tool_event_metadata=self._tool_event_metadata,
            create_permission_ticket=self.interaction_service.create_permission_ticket,
            clear_pending_permission=self.interaction_service.clear_pending_permission,
        )

    def _load_project_extensions(self) -> Dict[str, Any]:
        payload = load_project_extensions(self.tools.workspace)
        loaded_extensions = list(payload.get("loaded_extensions") or [])
        for extension in loaded_extensions:
            self.extension_manager.register(extension)
        self.extension_manager.register_context_reducers(self.context_manager.reducers)
        self._record_project_extension_diagnostics(payload)
        return self._sanitize_project_extension_state(payload)

    def _record_project_extension_diagnostics(self, payload: Dict[str, Any]) -> None:
        record = getattr(self.extension_manager, "record_diagnostic", None)
        if not callable(record):
            return
        for item in list(payload.get("diagnostics") or []):
            if not isinstance(item, dict):
                continue
            record(
                str(item.get("extension_id") or ""),
                str(item.get("event") or "load_project_extension"),
                str(item.get("error") or ""),
                severity=str(item.get("severity") or "error"),
                source=str(item.get("source") or "project"),
                metadata=dict(item.get("metadata") or {}),
            )

    def _sanitize_project_extension_state(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "workspace": str(payload.get("workspace") or self.tools.workspace),
            "counts": dict(payload.get("counts") or {}),
            "extensions": [dict(item) for item in list(payload.get("extensions") or [])],
            "diagnostics": [dict(item) for item in list(payload.get("diagnostics") or [])],
        }

    def _project_extension_snapshot_state(self) -> Dict[str, Any]:
        return {
            "state": {
                "counts": dict(self.project_extension_state.get("counts") or {}),
                "extensions": [
                    dict(item)
                    for item in list(self.project_extension_state.get("extensions") or [])
                ],
                "diagnostics": [
                    dict(item)
                    for item in list(self.project_extension_state.get("diagnostics") or [])
                ],
            }
        }

    def _apply_project_extension_state(self, state: ManagedSession) -> None:
        extensions = state.session.workflow_state.setdefault("extensions", {})
        extensions["project_extensions"] = self._project_extension_snapshot_state()

    def _build_engine(self) -> QueryEngine:
        return QueryEngine(
            client=self.client,
            tools=self.tools,
            max_turns=self.max_turns,
            permission_policy=self.permission_policy,
            context_manager=self.context_manager,
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
            memory_maintenance=self.memory_maintenance,
            maintenance_interval=self.maintenance_interval,
            transcript_store=self.transcript_store,
            extension_manager=self.extension_manager,
        )

    def capability_snapshot(self) -> Dict[str, Any]:
        return self._runtime_capabilities.snapshot()

    def get_session_capabilities(self, session_id: str = "") -> Dict[str, Any]:
        del session_id
        self._ensure_extension_tools_registered(reason="capabilities")
        return command_capability_payload(self.capability_snapshot())

    def _capability_descriptors(self) -> List[Any]:
        descriptors = []
        runtime_capabilities = getattr(self.tools, "capability_descriptors", None)
        if callable(runtime_capabilities):
            descriptors.extend(runtime_capabilities())
        descriptors.extend(
            command_capability_descriptors(
                self.command_registry,
                extra_specs=resource_command_specs(self.tools.local_resources()),
            )
        )
        return descriptors

    def _workflow_package_capability_descriptors(self) -> List[Any]:
        package_manifests = getattr(self.extension_manager, "package_manifests", None)
        if callable(package_manifests):
            return workflow_package_capability_descriptors(package_manifests())
        return []

    def _registered_tool_names_from_snapshot(self, snapshot: Dict[str, Any]) -> List[str]:
        return self._runtime_capabilities.registered_tool_names(snapshot)

    def _active_tool_names_for_state(self, state: ManagedSession) -> List[str]:
        names = self.extension_manager.allowed_tool_names(
            state.current_mode,
            workflow_state=state.workflow_state,
            fallback=set(allowed_tools_for(state.current_mode)),
        )
        return _stable_names(list(names))

    def _runtime_config_payload(
        self,
        reason: str,
        active_tool_names: Optional[List[str]] = None,
        resource_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        capability_snapshot = self.capability_snapshot()
        model_descriptor = model_profile_capability_descriptor(self.client)
        payload = {
            "reason": str(reason or ""),
            "model_profile": {
                "name": model_descriptor.name,
                "source_type": model_descriptor.source_type,
                "source_id": model_descriptor.source_id,
                "metadata": dict(model_descriptor.metadata or {}),
            },
            "active_tool_names": _stable_names(active_tool_names),
            "registered_tool_names": self._registered_tool_names_from_snapshot(capability_snapshot),
            "capability_counts": dict(capability_snapshot.get("counts") or {}),
        }
        if isinstance(resource_payload, dict) and "revision" in resource_payload:
            payload["resource_revision"] = self._resource_event_payload(resource_payload)
        return payload

    def _append_runtime_configured(
        self,
        state: ManagedSession,
        reason: str,
        active_tool_names: Optional[List[str]] = None,
        resource_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.transcript_store.append_event(
            state.session.session_id,
            "runtime_configured",
            self._runtime_config_payload(
                reason,
                active_tool_names=active_tool_names or self._active_tool_names_for_state(state),
                resource_payload=resource_payload,
            ),
        )

    def _refresh_runtime_config(self, state: ManagedSession) -> None:
        try:
            events = self.transcript_store.load_events(state.session.session_id)
        except (OSError, ValueError, TypeError):
            return
        state.runtime_config = RuntimeConfigReducer().reduce(events).to_dict()

    def _refresh_compaction_state(self, state: ManagedSession) -> None:
        try:
            events = self.transcript_store.load_events(state.session.session_id)
        except (OSError, ValueError, TypeError):
            return
        state.compaction_state = CompactionStateReducer().reduce(events).to_dict()

    def _refresh_recovery_state(self, state: ManagedSession) -> None:
        try:
            events = self.transcript_store.load_events(state.session.session_id)
        except (OSError, ValueError, TypeError):
            return
        state.recovery_state = RecoveryStateReducer().reduce(events).to_dict()

    def _runtime_summary_for_recovery(self, runtime_config: Dict[str, Any]) -> Dict[str, Any]:
        resource_revision = runtime_config.get("resource_revision")
        if not isinstance(resource_revision, dict):
            resource_revision = {}
        model_profile = runtime_config.get("model_profile")
        if not isinstance(model_profile, dict):
            model_profile = {}
        return {
            "active_tool_count": len(list(runtime_config.get("active_tool_names") or [])),
            "resource_revision": int(resource_revision.get("revision") or 0),
            "model_profile_name": str(model_profile.get("name") or ""),
        }

    def _append_recovery_marker(
        self,
        state: ManagedSession,
        restored: Any,
        current_mode: str,
        runtime_config: Dict[str, Any],
    ) -> None:
        consumed = int(getattr(restored, "consumed_event_count", 0) or 0)
        total = int(getattr(restored, "transcript_event_count", 0) or 0)
        stop_reason = str(getattr(restored, "stop_reason", "") or "")
        status = "clean" if not stop_reason and consumed == total else "partial"
        operation_summary = operation_diagnostics(restored.operation_state)
        compaction_summary = restored.compaction_state.to_dict()
        self.transcript_store.append_event(
            state.session.session_id,
            "recovery_marker",
            {
                "marker_id": "recovery-%s" % uuid.uuid4().hex,
                "created_at": _utc_now(),
                "reason": "resume",
                "status": status,
                "current_mode": current_mode,
                "trusted_event_count": consumed,
                "transcript_event_count": total,
                "stop_reason": stop_reason,
                "skipped_count": int(getattr(restored, "skipped_count", 0) or 0),
                "skip_reasons": list(getattr(restored, "skip_reasons", []) or []),
                "operation_summary": {
                    "total_count": int(operation_summary.get("total_count") or 0),
                    "started_count": int(operation_summary.get("started_count") or 0),
                    "finished_count": int(operation_summary.get("finished_count") or 0),
                    "interrupted_count": int(operation_summary.get("interrupted_count") or 0),
                },
                "compaction_summary": {
                    "boundary_count": int(compaction_summary.get("boundary_count") or 0),
                    "latest_boundary_id": str(compaction_summary.get("latest_boundary_id") or ""),
                },
                "runtime_summary": self._runtime_summary_for_recovery(runtime_config),
                "metadata": {"source": "resume_session"},
            },
        )

    def _tool_permission_category(self, tool_name: str) -> str:
        lookup = getattr(self.tools, "tool_catalog_entry", None)
        if not callable(lookup):
            return ""
        entry = lookup(tool_name) or {}
        if not isinstance(entry, dict):
            return ""
        return str(entry.get("permission_category") or "")

    def _ensure_extension_tools_registered(
        self,
        reason: str = "catalog",
        mode_name: str = "",
        workflow_state: str = "chat",
    ) -> None:
        runtime_snapshot = {}
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        if callable(runtime_lookup):
            runtime_snapshot = runtime_lookup()
        self.extension_manager.register_tools(
            ToolRegistrationEvent(
                current_mode=str(mode_name or ""),
                workflow_state_name=str(workflow_state or "chat"),
                reason=str(reason or "catalog"),
            ),
            ExtensionContext(
                workspace=str(getattr(self.tools, "workspace", "") or ""),
                runtime_environment=dict(runtime_snapshot or {}),
                tool_registry=self.tools,
                permission_policy=self.permission_policy,
            ),
        )

    def _extension_resource_paths(self, reason: str) -> Dict[str, List[str]]:
        result = self.extension_manager.discover_resources(
            self.tools.workspace,
            reason=str(reason or "reload"),
        )
        return {
            "skill_paths": list(getattr(result, "skill_paths", []) or []),
            "prompt_paths": list(getattr(result, "prompt_paths", []) or []),
            "recipe_paths": list(getattr(result, "recipe_paths", []) or []),
        }

    def _resource_event_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "reason": str(payload.get("reason") or ""),
            "counts": dict(payload.get("counts") or {}),
            "resource_paths": dict(payload.get("resource_paths") or {}),
            "diagnostics": list(payload.get("diagnostics") or []),
        }

    def reload_resources(self, session_id: str = "", reason: str = "reload") -> Dict[str, Any]:
        normalized_reason = str(reason or "reload")
        paths = self._extension_resource_paths(normalized_reason)
        reload_method = getattr(self.tools, "reload_resources", None)
        if not callable(reload_method):
            payload = {
                "workspace": self.tools.workspace,
                "reason": normalized_reason,
                "resource_paths": paths,
                "counts": {"skills": 0, "prompts": 0, "recipes": 0, "diagnostics": 1},
                "skills": [],
                "prompts": [],
                "recipes": [],
                "diagnostics": [
                    {
                        "kind": "runtime",
                        "path": "",
                        "error": "tool runtime does not support resource reload",
                    }
                ],
            }
        else:
            payload = reload_method(
                skill_paths=paths["skill_paths"],
                prompt_paths=paths["prompt_paths"],
                recipe_paths=paths["recipe_paths"],
                reason=normalized_reason,
            )
        session_ref = str(session_id or "").strip()
        if session_ref:
            state = self._ensure_session_active(session_ref)
            event_payload = self._resource_event_payload(payload)
            self.transcript_store.append_event(
                state.session.session_id,
                "resource_discovered",
                event_payload,
            )
            self.transcript_store.append_event(
                state.session.session_id,
                "resource_reloaded",
                event_payload,
            )
            self._append_runtime_configured(
                state,
                normalized_reason,
                resource_payload=payload,
            )
            with state.lock:
                extensions = state.session.workflow_state.setdefault("extensions", {})
                extensions["local_resources"] = {
                    "state": {
                        "counts": dict(payload.get("counts") or {}),
                        "resource_paths": dict(payload.get("resource_paths") or {}),
                        "diagnostics": list(payload.get("diagnostics") or []),
                    }
                }
                self._refresh_local_skills_prompt_locked(
                    state,
                    payload,
                    normalized_reason,
                )
                self._refresh_runtime_config(state)
                self._refresh_compaction_state(state)
                self._refresh_recovery_state(state)
                state.updated_at = _utc_now()
        return dict(payload or {})

    def _refresh_local_skills_prompt_locked(
        self,
        state: ManagedSession,
        payload: Dict[str, Any],
        reason: str,
    ) -> None:
        prompt = build_skill_index(payload).prompt_text()
        state.session.messages = [
            message
            for message in state.session.messages
            if not (message.role == "system" and message.kind == "local_skills_prompt")
        ]
        if not prompt:
            return
        message = state.session.add_system_message(
            "## Local Skills\n" + prompt,
            kind="local_skills_prompt",
            metadata={
                "reason": str(reason or ""),
                "resource_revision": int((payload.get("counts") or {}).get("skills") or 0),
            },
        )
        self._append_transcript_message_event(state.session.session_id, message)

    def _append_transcript_message_event(self, session_id: str, message: Any) -> None:
        self.transcript_store.append_event(
            session_id,
            "message",
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

    def _refresh_harness_state(self, state: ManagedSession) -> None:
        observations = state.session.turns[-1].observations if state.session.turns else []
        self.harness_workflow.refresh_managed_session(
            state,
            self.tools.workspace,
            observations=observations,
        )

    def create_session(
        self,
        mode: str = DEFAULT_MODE,
        event_handler: Optional[EventHandler] = None,
    ) -> Dict[str, Any]:
        current_mode = require_mode(mode)["slug"]
        session = Session()
        plan = self.plan_store.load(session.session_id)
        state = ManagedSession(
            session=session,
            current_mode=current_mode,
            active_plan_ref=plan.path if plan is not None else "",
            workflow_state="plan" if plan is not None else "chat",
        )
        state.engine = self._build_engine()
        state.current_mode = state.engine.initialize_session(
            session,
            current_mode,
            workflow_state=state.workflow_state,
        )
        with self._lock:
            self._sessions[session.session_id] = state
        with state.lock:
            self._apply_project_extension_state(state)
            state.updated_at = _utc_now()
        self.reload_resources(session_id=session.session_id, reason="session_start")
        with state.lock:
            self._refresh_runtime_config(state)
            self._refresh_compaction_state(state)
            self._refresh_recovery_state(state)
        self._persist_state(state)
        snapshot = self.get_session_snapshot(session.session_id)
        self._emit(
            event_handler, "session_created", session.session_id, {"session_snapshot": snapshot}
        )
        self._notify_status(event_handler, state)
        return snapshot

    def resume_session(
        self,
        reference: str,
        mode: str = "",
        event_handler: Optional[EventHandler] = None,
    ) -> Dict[str, Any]:
        transcript_path = self.summary_store.resolve_transcript_path(reference)
        events = self.transcript_store.load_events(transcript_path)
        restored = self.session_restorer.restore(events)
        current_mode = require_mode(mode or restored.current_mode or DEFAULT_MODE)["slug"]
        session = restored.session
        summary_ref = ""
        try:
            summary_ref = self.summary_store.persist(session, current_mode)
        except (OSError, ValueError, TypeError):
            summary_ref = ""
        state = ManagedSession(
            session=session,
            current_mode=current_mode,
            summary_ref=summary_ref,
            updated_at=_utc_now(),
            resume_summary=None,
            last_assistant_message=self._last_assistant_from_session(session),
            restore_stop_reason=str(restored.stop_reason or ""),
            restore_consumed_event_count=int(restored.consumed_event_count or 0),
            restore_transcript_event_count=int(restored.transcript_event_count or 0),
            operation_diagnostics=operation_diagnostics(restored.operation_state),
            compaction_state=restored.compaction_state.to_dict(),
            recovery_state=restored.recovery_state.to_dict(),
            runtime_config=RuntimeConfigReducer()
            .reduce(events[: int(restored.consumed_event_count or 0)])
            .to_dict(),
        )
        state.engine = self._build_engine()
        state.current_mode = state.engine.initialize_session(
            session,
            current_mode,
            workflow_state=state.workflow_state,
        )
        if session.pending_interaction is not None:
            if session.pending_interaction.kind == "permission":
                state.status = "waiting_permission"
                permission_payload = dict(
                    session.pending_interaction.request_payload.get("permission") or {}
                )
                interaction_id = str(session.pending_interaction.interaction_id or "").strip()
                if interaction_id:
                    state.pending_permission = PermissionTicket(
                        permission_id=interaction_id,
                        session_id=session.session_id,
                        tool_name=session.pending_interaction.tool_name,
                        category=str(permission_payload.get("category") or ""),
                        reason=str(permission_payload.get("reason") or ""),
                        details=dict(permission_payload.get("details") or {}),
                    )
                else:
                    state.status = "idle"
            elif session.pending_interaction.kind == "user_input":
                state.status = "waiting_user_input"
                request_payload = dict(
                    session.pending_interaction.request_payload.get("request") or {}
                )
                interaction_id = str(session.pending_interaction.interaction_id or "").strip()
                if interaction_id:
                    state.pending_user_input = UserInputTicket(
                        request_id=interaction_id,
                        session_id=session.session_id,
                        tool_name=session.pending_interaction.tool_name,
                        question=str(request_payload.get("question") or ""),
                        options=list(request_payload.get("options") or []),
                        details=dict(request_payload.get("details") or {}),
                    )
                else:
                    state.status = "idle"
        plan = self.plan_store.load(session.session_id)
        if plan is not None:
            state.active_plan_ref = plan.path
            state.workflow_state = "plan"
        self._refresh_harness_state(state)
        with self._lock:
            self._sessions[session.session_id] = state
        with state.lock:
            self._apply_project_extension_state(state)
            self._append_recovery_marker(state, restored, current_mode, state.runtime_config)
            self._refresh_runtime_config(state)
            self._refresh_compaction_state(state)
            self._refresh_recovery_state(state)
            state.updated_at = _utc_now()
        snapshot = self.get_session_snapshot(session.session_id)
        self._emit(
            event_handler,
            "session_resumed",
            session.session_id,
            {"session_snapshot": snapshot, "resume_ref": snapshot.get("summary_ref")},
        )
        self._notify_status(event_handler, state)
        return snapshot

    def _ensure_session_active(self, reference: str, mode: str = "") -> ManagedSession:
        with self._lock:
            state = self._sessions.get(reference)
        if state is not None:
            return state
        snapshot = self.resume_session(reference, mode or DEFAULT_MODE)
        session_id = str(snapshot.get("session_id") or "")
        return self._require_session(session_id)

    def list_sessions(
        self,
        limit: int = 10,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        return self._session_lifecycle.list_sessions(
            limit=limit,
            include_archived=include_archived,
        )

    def rename_session(self, session_id: str, title: str) -> Dict[str, Any]:
        return self._session_lifecycle.rename_session(session_id, title)

    def archive_session(self, session_id: str) -> Dict[str, Any]:
        return self._session_lifecycle.archive_session(session_id)

    def fork_session(self, session_id: str, title: str = "") -> Dict[str, Any]:
        return self._session_lifecycle.fork_session(session_id, title=title)

    def get_session_snapshot(self, session_id: str) -> Dict[str, Any]:
        state = self._ensure_session_active(session_id)
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        runtime = runtime_lookup() if callable(runtime_lookup) else {}
        with state.lock:
            self._refresh_operation_diagnostics(state)
            self._refresh_runtime_config(state)
            self._refresh_compaction_state(state)
            self._refresh_recovery_state(state)
            summary = self._read_summary_for_state(state)
            return self.snapshot_projector.build_snapshot(
                state,
                summary,
                runtime,
                pending_interaction=_pending_interaction_payload(state),
                extension_diagnostics=self.extension_manager.diagnostics(),
            )

    def _refresh_operation_diagnostics(self, state: ManagedSession) -> None:
        try:
            events = self.transcript_store.load_events(state.session.session_id)
        except (OSError, ValueError, TypeError):
            return
        operation_state = OperationLogReducer(close_unfinished=False).reduce(events)
        state.operation_diagnostics = operation_diagnostics(operation_state)

    def get_workspace_snapshot(self) -> Dict[str, Any]:
        counts = self._count_workspace_items()
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        runtime = runtime_lookup() if callable(runtime_lookup) else {}
        recipes_payload = self.list_workspace_recipes()
        recipe_items = recipes_payload.get("items") if isinstance(recipes_payload, dict) else []
        return {
            "workspace": self.tools.workspace,
            "hosted": True,
            "git": {
                "available": False,
                "branch": "",
                "dirty_count": 0,
                "modified_count": 0,
                "untracked_count": 0,
            },
            "tree": counts,
            "runtime_environment": runtime,
            "recipes": {
                "count": len(recipe_items or []),
                "items": recipe_items or [],
            },
        }

    def list_workspace_tree(
        self,
        path: str = ".",
        max_depth: int = 3,
        limit: int = 200,
    ) -> Dict[str, Any]:
        return self._workspace_files.list_tree(path, max_depth=max_depth, limit=limit)

    def list_workspace_children(
        self,
        path: str = ".",
        limit: int = 200,
    ) -> Dict[str, Any]:
        return self._workspace_files.list_directory(path, limit=limit)

    def read_workspace_file(self, path: str) -> Dict[str, Any]:
        return self._workspace_files.read_file(path)

    def write_workspace_file(self, path: str, content: str) -> Dict[str, Any]:
        return self._workspace_files.write_file(path, content)

    def build_session_history(self, reference: str, mode: str = "") -> Dict[str, Any]:
        try:
            state = self._ensure_session_active(reference, mode)
        except ValueError as exc:
            return {
                "session_id": str(reference or ""),
                "history_source": "transcript_restore",
                "turns": [],
                "current_interaction": None,
                "integrity": {
                    "status": "unavailable",
                    "restore_stop_reason": self._history_unavailable_reason(exc),
                    "consumed_event_count": 0,
                    "transcript_event_count": 0,
                },
            }
        assembler = SessionHistoryAssembler(
            tool_catalog_lookup=getattr(self.tools, "tool_catalog_entry", None),
            runtime_snapshot_lookup=getattr(self.tools, "runtime_environment_snapshot", None),
        )
        integrity_status = "healthy"
        history_source = "session_state"
        if int(state.restore_transcript_event_count or 0) > 0:
            history_source = "transcript_restore"
            if str(state.restore_stop_reason or "").strip():
                integrity_status = "partial"
        return assembler.build(
            state.session,
            history_source=history_source,
            integrity_status=integrity_status,
            restore_stop_reason=str(state.restore_stop_reason or ""),
            consumed_event_count=int(state.restore_consumed_event_count or 0),
            transcript_event_count=int(state.restore_transcript_event_count or 0),
        )

    def get_session_bootstrap(self, reference: str, mode: str = "") -> Dict[str, Any]:
        state = self._ensure_session_active(reference, mode)
        return self._bootstrap_service.build(state.session.session_id)

    def _history_unavailable_reason(self, exc: Exception) -> str:
        message = str(exc or "").strip().lower()
        if "transcript not found" in message or "empty transcript" in message:
            return "transcript_missing"
        return str(exc or "history_unavailable")

    def list_artifacts(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = self.tools.projection_db.list_tool_results(limit=limit)
        result = []
        for item in items:
            result.append(
                {
                    "path": item["stored_path"],
                    "tool_name": item["tool_name"],
                    "field_name": item["field_name"],
                    "created_at": item["created_at"],
                    "preview_text": item["preview_text"],
                    "byte_count": item["byte_count"],
                    "kind": item["content_kind"],
                }
            )
        return result

    def read_artifact(self, reference: str) -> Dict[str, Any]:
        absolute_path = self.tools.tool_result_store.resolve_existing_path(reference)
        with open(absolute_path, "r", encoding="utf-8") as handle:
            content = handle.read()
        kind = "json" if absolute_path.lower().endswith(".json") else "text"
        return {"path": reference, "kind": kind, "content": content}

    def list_tasks(self, session_id: str = "") -> Dict[str, Any]:
        if not session_id:
            return {
                "count": 0,
                "tasks": [],
                "path": "",
                "session_id": session_id,
            }
        stored_payload = self.extension_manager.load_session_tasks(self.tools.workspace, session_id)
        state = None
        with self._lock:
            state = self._sessions.get(session_id)
        if state is not None:
            session_workflow = getattr(state.session, "workflow_state", {}) or {}
            workflow = {}
            if isinstance(session_workflow, dict):
                workflow = dict(session_workflow.get("workflow") or {})
            tasks = list(workflow.get("items") or [])
        else:
            return stored_payload
        return {
            "count": len(tasks),
            "tasks": tasks,
            "path": str(stored_payload.get("path") or ""),
            "session_id": session_id,
        }

    def get_session_plan(self, session_id: str) -> Optional[PlanSnapshot]:
        state = self._ensure_session_active(session_id)
        return self.plan_store.load(state.session.session_id)

    def get_permission_context(self, session_id: str) -> PermissionContextView:
        state = self._ensure_session_active(session_id)
        remembered = sorted(state.remembered_permission_categories)
        return self.permission_policy.build_context_view(
            session_id=state.session.session_id,
            remembered_categories=remembered,
        )

    def remember_permission_category(self, session_id: str, category: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        normalized = str(category or "").strip()
        if not normalized:
            return self.get_session_snapshot(session_id)
        with state.lock:
            state.remembered_permission_categories.add(normalized)
            state.updated_at = _utc_now()
        return self.get_session_snapshot(session_id)

    def get_tool_catalog(self) -> List[Dict[str, Any]]:
        self._ensure_extension_tools_registered(reason="catalog")
        method = getattr(self.tools, "catalog_entries", None)
        if callable(method):
            allowed = set()
            for mode_name in mode_names():
                allowed.update(
                    self.extension_manager.allowed_tool_names(
                        mode_name,
                        workflow_state="chat",
                        fallback=set(allowed_tools_for(mode_name)),
                    )
                )
            items = []
            for entry in method():
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("name") or "") not in allowed:
                    continue
                items.append(entry)
            return items
        return []

    def list_workspace_recipes(self) -> Dict[str, Any]:
        method = getattr(self.tools, "workspace_recipes", None)
        if callable(method):
            return method()
        return {"workspace": self.tools.workspace, "items": []}

    def submit_user_message(
        self,
        session_id: str,
        text: str,
        stream: bool = True,
        wait: bool = True,
        permission_resolver: Optional[PermissionResolver] = None,
        user_input_resolver: Optional[UserInputResolver] = None,
        event_handler: Optional[EventHandler] = None,
    ) -> Dict[str, Any]:
        state = self._require_session(session_id)
        parsed_command = parse_slash_command(text)
        command_turn_id = "t-" + uuid.uuid4().hex[:12] if parsed_command is not None else ""
        with state.lock:
            state.current_command_text = text if parsed_command is not None else ""
            state.current_command_turn_id = command_turn_id
            state.current_command_step_id = ""
            state.current_command_step_index = 0
        if command_turn_id:
            self._emit(
                event_handler,
                "turn_start",
                session_id,
                {"turn_id": command_turn_id, "user_text": text},
            )
        dispatch = self.command_service.dispatch(state, text, event_handler, permission_resolver)
        if dispatch.get("handled") and not dispatch.get("continue_with_text"):
            if command_turn_id:
                self._emit(
                    event_handler,
                    "turn_end",
                    session_id,
                    {
                        "turn_id": command_turn_id,
                        "final_text": "",
                        "outcome": TurnOutcome.from_transition(
                            LoopTransition(reason="completed")
                        ).to_dict(),
                        "termination_reason": "completed",
                        "turns_used": 0,
                        "max_turns": self.max_turns,
                        "error": "",
                    },
                )
            with state.lock:
                state.current_command_text = ""
                state.current_command_turn_id = ""
                state.current_command_step_id = ""
                state.current_command_step_index = 0
            return self.get_session_snapshot(session_id)
        text_to_run = str(dispatch.get("continue_with_text") or text)
        with state.lock:
            state.current_command_text = ""
            state.current_command_turn_id = ""
            state.current_command_step_id = ""
            state.current_command_step_index = 0
        with state.lock:
            state.status = "running"
            state.last_error = None
            state.current_command_context = ""
            if state.workflow_state != "plan":
                state.workflow_state = "chat"
            state.updated_at = _utc_now()
        payload = {
            "text": text_to_run,
            "stream": stream,
            "turn_id": command_turn_id,
        }
        self._emit_with_snapshot(event_handler, "turn_started", state, payload)
        self._notify_status(event_handler, state)
        if wait:
            self._run_turn(
                state=state,
                text=text_to_run,
                stream=stream,
                permission_resolver=permission_resolver,
                user_input_resolver=user_input_resolver,
                event_handler=event_handler,
                turn_id=command_turn_id or "",
                emit_turn_start=not bool(command_turn_id),
            )
            return self.get_session_snapshot(session_id)
        thread = threading.Thread(
            target=self._run_turn,
            kwargs={
                "state": state,
                "text": text_to_run,
                "stream": stream,
                "permission_resolver": permission_resolver,
                "user_input_resolver": user_input_resolver,
                "event_handler": event_handler,
                "turn_id": command_turn_id or "",
                "emit_turn_start": not bool(command_turn_id),
            },
            name="embedagent-session-%s" % session_id[:8],
        )
        with state.lock:
            if state.active_thread is not None and state.active_thread.is_alive():
                raise RuntimeError("当前会话仍在运行中。")
            state.active_thread = thread
        thread.daemon = True
        thread.start()
        return self.get_session_snapshot(session_id)

    def _tool_event_metadata(self, tool_name: str) -> Dict[str, Any]:
        lookup = getattr(self.tools, "tool_catalog_entry", None)
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        if not callable(lookup):
            return {}
        entry = lookup(tool_name) or {}
        if not isinstance(entry, dict):
            return {}
        runtime = runtime_lookup() if callable(runtime_lookup) else {}
        return {
            "tool_label": entry.get("user_label") or tool_name,
            "permission_category": entry.get("permission_category") or "",
            "supports_diff_preview": bool(entry.get("supports_diff_preview")),
            "progress_renderer_key": entry.get("progress_renderer_key") or "",
            "result_renderer_key": entry.get("result_renderer_key") or "",
            "read_model_invalidations": list(entry.get("read_model_invalidations") or []),
            "source_type": entry.get("source_type") or "",
            "source_id": entry.get("source_id") or "",
            "runtime_source": str(runtime.get("runtime_source") or ""),
            "resolved_tool_roots": dict(runtime.get("resolved_tool_roots") or {}),
            "fallback_warnings": list(runtime.get("fallback_warnings") or []),
        }

    def approve_permission(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        return self.interaction_service.approve_permission(session_id, permission_id)

    def reject_permission(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        return self.interaction_service.reject_permission(session_id, permission_id)

    def reply_user_input(
        self,
        session_id: str,
        request_id: str,
        answer: str,
        selected_index: Optional[int] = None,
        selected_mode: str = "",
        selected_option_text: str = "",
    ) -> Dict[str, Any]:
        return self.interaction_service.reply_user_input(
            session_id,
            request_id,
            answer,
            selected_index=selected_index,
            selected_mode=selected_mode,
            selected_option_text=selected_option_text,
        )

    def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self.interaction_service.respond_to_interaction(
            session_id,
            interaction_id,
            payload,
        )

    def set_session_mode(self, session_id: str, mode: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        current_mode = require_mode(mode)["slug"]
        with state.lock:
            state.current_mode = state.engine.apply_mode(
                state.session,
                current_mode,
                workflow_state=state.workflow_state,
            )
            self._refresh_harness_state(state)
        self._persist_state(state)
        snapshot = self.get_session_snapshot(session_id)
        self._emit(
            self.event_handler,
            "mode_changed",
            session_id,
            {"mode": current_mode, "session_snapshot": snapshot},
        )
        self._notify_status(None, state)
        return snapshot

    def cancel_session(self, session_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        with state.lock:
            state.stop_event.set()
            has_active_thread = bool(
                state.active_thread is not None and state.active_thread.is_alive()
            )
            if state.pending_permission is not None and state.pending_event is not None:
                state.pending_result = False
                state.pending_event.set()
            if state.pending_user_input is not None and state.pending_user_event is not None:
                state.pending_user_response = UserInputResponse(answer="")
                state.pending_user_event.set()
            if state.status != "error":
                state.status = "running" if has_active_thread else "idle"
        snapshot = self.get_session_snapshot(session_id)
        self._notify_status(None, state)
        return snapshot

    def _run_turn(
        self,
        state: ManagedSession,
        text: str,
        stream: bool,
        permission_resolver: Optional[PermissionResolver],
        user_input_resolver: Optional[UserInputResolver],
        event_handler: Optional[EventHandler],
        interaction_resolution: Optional[Dict[str, Any]] = None,
        resume_pending: bool = False,
        turn_id: str = "",
        emit_turn_start: bool = True,
    ) -> None:
        session_id = state.session.session_id
        turn_id = turn_id or ("t-" + uuid.uuid4().hex[:12])
        with state.lock:
            state.status = "running"
            state.last_error = None
            state.updated_at = _utc_now()
            state.pending_permission = None
            state.pending_user_input = None
            state.restore_stop_reason = ""
            state.restore_consumed_event_count = 0
            state.restore_transcript_event_count = 0
        engine = state.engine
        current_step = {"step_id": "", "step_index": 0}
        thinking_state = {"active": False}

        def set_thinking(active: bool, reason: str) -> None:
            if thinking_state["active"] == active:
                return
            thinking_state["active"] = active
            self._emit_with_snapshot(
                event_handler, "thinking_state", state, {"active": active, "reason": reason}
            )

        def on_text_delta(delta: str) -> None:
            set_thinking(False, "assistant_text")
            self._emit(
                event_handler,
                "assistant_delta",
                session_id,
                {
                    "text": delta,
                    "turn_id": turn_id,
                    "step_id": current_step["step_id"],
                    "step_index": current_step["step_index"],
                },
            )

        def on_reasoning_delta(delta: str) -> None:
            self._emit(
                event_handler,
                "reasoning_delta",
                session_id,
                {
                    "text": delta,
                    "turn_id": turn_id,
                    "step_id": current_step["step_id"],
                    "step_index": current_step["step_index"],
                },
            )

        def on_step_start(step_id: str, step_index: int) -> None:
            current_step["step_id"] = step_id
            current_step["step_index"] = step_index
            set_thinking(True, "step_started")
            self._emit(
                event_handler,
                "step_start",
                session_id,
                {"turn_id": turn_id, "step_id": step_id, "step_index": step_index},
            )

        def on_step_finish(step_index: int, reply: AssistantReply, status: str) -> None:
            set_thinking(False, "step_finished")
            self._emit(
                event_handler,
                "step_end",
                session_id,
                {
                    "turn_id": turn_id,
                    "step_id": current_step["step_id"],
                    "step_index": step_index,
                    "assistant_text": reply.content or "",
                    "finish_reason": reply.finish_reason or "",
                    "status": status,
                },
            )

        def on_tool_start(action: Action) -> None:
            set_thinking(False, "tool_start")
            payload = {
                "tool_name": action.name,
                "arguments": action.arguments,
                "call_id": action.call_id,
                "turn_id": turn_id,
                "step_id": current_step["step_id"],
                "step_index": current_step["step_index"],
            }
            payload.update(self._tool_event_metadata(action.name))
            self._emit(event_handler, "tool_started", session_id, payload)

        def on_tool_finish(action: Action, observation: Observation) -> None:
            payload = {
                "tool_name": action.name,
                "success": observation.success,
                "error": observation.error,
                "data": observation.data,
                "call_id": action.call_id,
                "turn_id": turn_id,
                "step_id": current_step["step_id"],
                "step_index": current_step["step_index"],
            }
            payload.update(self._tool_event_metadata(action.name))
            self._emit_with_snapshot(event_handler, "tool_finished", state, payload)

        def on_context_result(result: object) -> None:
            pipeline_steps = list(getattr(result, "pipeline_steps", []) or [])
            if "reactive_compact_retry" in pipeline_steps:
                self._emit_with_snapshot(
                    event_handler,
                    "compact_retry",
                    state,
                    {
                        "turn_id": turn_id,
                        "step_id": current_step["step_id"],
                        "step_index": current_step["step_index"],
                        "recent_turns": getattr(
                            getattr(result, "stats", None), "recent_turns", None
                        ),
                        "summarized_turns": getattr(
                            getattr(result, "stats", None), "summarized_turns", None
                        ),
                        "approx_tokens_after": getattr(
                            getattr(result, "budget", None), "input_tokens", None
                        ),
                        "pipeline_steps": pipeline_steps,
                    },
                )
            if not _should_emit_context_compacted(result):
                return
            self._emit_with_snapshot(
                event_handler,
                "context_compacted",
                state,
                {
                    "turn_id": turn_id,
                    "step_id": current_step["step_id"],
                    "step_index": current_step["step_index"],
                    "recent_turns": getattr(getattr(result, "stats", None), "recent_turns", None),
                    "summarized_turns": getattr(
                        getattr(result, "stats", None), "summarized_turns", None
                    ),
                    "approx_tokens_after": getattr(
                        getattr(result, "budget", None), "input_tokens", None
                    ),
                    "analysis": getattr(result, "analysis", {}),
                },
            )

        def permission_handler(request: PermissionRequest) -> Optional[bool]:
            ticket = self.interaction_service.create_permission_ticket(
                state,
                request,
                turn_id=turn_id,
                step_id=current_step["step_id"],
                step_index=current_step["step_index"],
            )
            self._emit_with_snapshot(
                event_handler,
                "permission_required",
                state,
                {
                    "permission": ticket.to_dict(),
                    "turn_id": ticket.turn_id,
                    "step_id": ticket.step_id,
                    "step_index": ticket.step_index,
                },
            )
            self._notify_status(event_handler, state)
            if permission_resolver is not None:
                approved = bool(permission_resolver(ticket.to_dict()))
                self.interaction_service.clear_pending_permission(state)
                return approved
            with state.lock:
                state.status = "waiting_permission"
            return None

        def user_input_handler(request: UserInputRequest) -> Optional[UserInputResponse]:
            ticket = self.interaction_service.create_user_input_ticket(
                state,
                request,
                turn_id=turn_id,
                step_id=current_step["step_id"],
                step_index=current_step["step_index"],
            )
            self._emit_with_snapshot(
                event_handler,
                "user_input_required",
                state,
                {
                    "user_input": ticket.to_dict(),
                    "turn_id": ticket.turn_id,
                    "step_id": ticket.step_id,
                    "step_index": ticket.step_index,
                },
            )
            self._notify_status(event_handler, state)
            if user_input_resolver is not None:
                payload = user_input_resolver(ticket.to_dict()) or {}
                self.interaction_service.clear_pending_user_input(state)
                return UserInputResponse(
                    answer=str(payload.get("answer") or ""),
                    selected_index=payload.get("selected_index"),
                    selected_mode=str(payload.get("selected_mode") or ""),
                    selected_option_text=str(payload.get("selected_option_text") or ""),
                )
            with state.lock:
                state.status = "waiting_user_input"
            return None

        try:
            if emit_turn_start:
                self._emit(
                    event_handler, "turn_start", session_id, {"turn_id": turn_id, "user_text": text}
                )
            set_thinking(True, "turn_started")
            if resume_pending:
                result = engine.resume_interaction(
                    session=state.session,
                    initial_mode=state.current_mode,
                    interaction_resolution=interaction_resolution,
                    workflow_state=state.workflow_state,
                    stream=stream,
                    stop_event=state.stop_event,
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
            else:
                result = engine.submit_user_turn(
                    user_text=text,
                    stream=stream,
                    initial_mode=state.current_mode,
                    workflow_state=state.workflow_state,
                    session=state.session,
                    stop_event=state.stop_event,
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
        except (RuntimeError, ValueError, TypeError) as exc:
            set_thinking(False, "session_error")
            with state.lock:
                is_worker_thread = threading.current_thread() is state.active_thread
                state.status = "error"
                state.last_error = str(exc)
                state.active_thread = None
                state.updated_at = _utc_now()
            self._emit_with_snapshot(
                event_handler,
                "session_error",
                state,
                {
                    "error": str(exc),
                    "phase": "loop",
                    "turn_id": turn_id,
                    "step_id": current_step["step_id"],
                    "step_index": current_step["step_index"],
                },
            )
            self._notify_status(event_handler, state)
            if is_worker_thread:
                return
            raise
        state.session = result.session
        if result.transition.reason in ("permission_wait", "user_input_wait"):
            set_thinking(False, result.transition.reason)
            with state.lock:
                state.updated_at = _utc_now()
                state.active_thread = None
            return
        with state.lock:
            state.last_assistant_message = result.final_text
            if result.transition.next_mode:
                state.current_mode = result.transition.next_mode
            self._refresh_harness_state(state)
            state.status = "idle"
            state.active_thread = None
            state.updated_at = _utc_now()
        self._emit(
            event_handler,
            "turn_end",
            session_id,
            {
                "turn_id": turn_id,
                "final_text": result.final_text,
                "outcome": result.outcome.to_dict(),
                "termination_reason": result.transition.reason,
                "turns_used": result.turns_used,
                "max_turns": self.max_turns,
                "error": result.transition.message or "",
            },
        )
        self._persist_state(state)
        set_thinking(False, "session_finished")
        snapshot = self.get_session_snapshot(session_id)
        self._emit(
            event_handler,
            "session_finished",
            session_id,
            {
                "final_text": result.final_text,
                "session_snapshot": snapshot,
                "outcome": result.outcome.to_dict(),
                "termination_reason": result.transition.reason,
                "turns_used": result.turns_used,
                "max_turns": self.max_turns,
                "error": result.transition.message or "",
            },
        )
        self._notify_status(event_handler, state)
        return

    def _persist_state(self, state: ManagedSession) -> None:
        self._session_lifecycle.persist_state(state.session, state.current_mode, state)

    def _last_assistant_from_session(self, session: Session) -> str:
        return self._session_lifecycle._last_assistant_from_session(session)

    def _read_summary_for_state(self, state: ManagedSession) -> Optional[Dict[str, Any]]:
        return self._session_lifecycle.read_summary_for_state(state)

    def _require_session(self, session_id: str) -> ManagedSession:
        with self._lock:
            state = self._sessions.get(session_id)
        if state is None:
            raise ValueError("session_id 不存在：%s" % session_id)
        return state

    def _emit(
        self,
        event_handler: Optional[EventHandler],
        event_name: str,
        session_id: str,
        payload: Dict[str, Any],
    ) -> None:
        self._event_emitter.emit(
            event_handler or self.event_handler,
            event_name,
            session_id,
            payload,
        )

    def _emit_with_snapshot(
        self,
        event_handler: Optional[EventHandler],
        event_name: str,
        state: ManagedSession,
        payload: Dict[str, Any],
    ) -> None:
        self._event_emitter.emit_with_snapshot(
            event_handler or self.event_handler,
            event_name,
            state.session.session_id,
            payload,
            lambda: self.get_session_snapshot(state.session.session_id),
        )

    def _notify_status(
        self,
        event_handler: Optional[EventHandler],
        state: ManagedSession,
    ) -> None:
        self._event_emitter.notify_status(
            event_handler or self.event_handler,
            state.session.session_id,
            lambda: self.get_session_snapshot(state.session.session_id),
        )

    def _resolve_workspace_candidate(self, path: str, allow_missing: bool) -> str:
        return self._workspace_files.resolve_path(path, allow_missing=allow_missing)

    def _relative_path(self, path: str) -> str:
        return self._workspace_files.relative_path(path)

    def _count_workspace_items(self) -> Dict[str, int]:
        return self._workspace_files.count_items()

    def _directory_has_visible_children(self, path: str) -> bool:
        return self._workspace_files._directory_has_visible_children(path)

    def _detect_newline(self, path: str) -> str:
        return self._workspace_files._detect_newline(path)
