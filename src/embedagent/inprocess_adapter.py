from __future__ import annotations  # noqa: I001

import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from embedagent.context import ContextManager
from embedagent.default_extensions import build_default_extension_set
from embedagent.harness import task_store
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
from embedagent.project_memory import ProjectMemoryStore
from embedagent.protocol import CommandResult, PermissionContextView, PlanSnapshot
from embedagent.session import Action, AssistantReply, Observation, Session
from embedagent.session_history import SessionHistoryAssembler
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
from embedagent.session_timeline import SessionTimelineStore
from embedagent.slash_commands import ParsedSlashCommand, SlashCommandRegistry, parse_slash_command
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


PermissionResolver = Callable[[Dict[str, Any]], bool]
UserInputResolver = Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class PermissionTicket:
    permission_id: str
    session_id: str
    tool_name: str
    category: str
    reason: str
    details: Dict[str, Any]
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "permission_id": self.permission_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "category": self.category,
            "reason": self.reason,
            "details": self.details,
            "turn_id": self.turn_id,
            "step_id": self.step_id,
            "step_index": self.step_index,
        }


@dataclass
class UserInputTicket:
    request_id: str
    session_id: str
    tool_name: str
    question: str
    options: List[Dict[str, Any]]
    details: Dict[str, Any]
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "question": self.question,
            "options": self.options,
            "details": self.details,
            "turn_id": self.turn_id,
            "step_id": self.step_id,
            "step_index": self.step_index,
        }


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
        max_turns: int = 8,
        permission_policy: Optional[PermissionPolicy] = None,
        summary_store: Optional[SessionSummaryStore] = None,
        project_memory_store: Optional[ProjectMemoryStore] = None,
        context_manager: Optional[ContextManager] = None,
        memory_maintenance: Optional[MemoryMaintenance] = None,
        timeline_store: Optional[SessionTimelineStore] = None,
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
        self.timeline_store = timeline_store or SessionTimelineStore(self.tools.workspace)
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
        initialize_modes(self.tools.workspace)
        self._sessions = {}  # type: Dict[str, ManagedSession]
        self._lock = threading.RLock()
        self._event_emitter = EventEmitter(self.timeline_store)
        self._workspace_files = WorkspaceFileService(
            self.tools.workspace,
            getattr(self.tools, "_ctx", None),
        )
        self._session_lifecycle = SessionLifecycleManager(
            session_store=self.summary_store,
            timeline_store=self.timeline_store,
            summary_store=self.summary_store,
            plan_store=self.plan_store,
            project_memory=self.project_memory_store,
            session_restorer=self.session_restorer,
            transcript_store=self.transcript_store,
        )

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
        self._persist_state(state)
        with self._lock:
            self._sessions[session.session_id] = state
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

    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._session_lifecycle.list_sessions(limit=limit)

    def get_session_snapshot(self, session_id: str) -> Dict[str, Any]:
        state = self._ensure_session_active(session_id)
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        runtime = runtime_lookup() if callable(runtime_lookup) else {}
        with state.lock:
            summary = self._read_summary_for_state(state)
            return self.snapshot_projector.build_snapshot(
                state,
                summary,
                runtime,
                pending_interaction=_pending_interaction_payload(state),
            )

    def get_workspace_snapshot(self) -> Dict[str, Any]:
        counts = self._count_workspace_items()
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        runtime = runtime_lookup() if callable(runtime_lookup) else {}
        recipes_payload = self.list_workspace_recipes()
        recipe_items = recipes_payload.get("items") if isinstance(recipes_payload, dict) else []
        git_status = self.tools.execute("git_status", {"path": "."})
        branch = ""
        dirty_count = 0
        modified_count = 0
        untracked_count = 0
        if git_status.success and isinstance(git_status.data, dict):
            branch = str(git_status.data.get("branch") or "")
            entries = git_status.data.get("entries") or []
            if isinstance(entries, list):
                dirty_count = len(entries)
                for item in entries:
                    if not isinstance(item, dict):
                        continue
                    status = str(item.get("status") or "").strip()
                    if "?" in status:
                        untracked_count += 1
                    elif status:
                        modified_count += 1
        return {
            "workspace": self.tools.workspace,
            "hosted": True,
            "git": {
                "available": bool(branch or git_status.success),
                "branch": branch,
                "dirty_count": dirty_count,
                "modified_count": modified_count,
                "untracked_count": untracked_count,
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

    def get_session_timeline(self, session_id: str, limit: int = 200) -> Dict[str, Any]:
        state = self._ensure_session_active(session_id)
        return {
            "session_id": state.session.session_id,
            "events": self.timeline_store.load_events(state.session.session_id, limit=limit),
            "latest_assistant_reply": self.timeline_store.latest_assistant_reply(
                state.session.session_id
            ),
        }

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
        session_id = state.session.session_id
        return {
            "snapshot": self.get_session_snapshot(session_id),
            "history": self.build_session_history(session_id),
            "plan": self.get_session_plan(session_id),
            "permission_context": self.get_permission_context(session_id),
            "replay": self.load_session_events_after(session_id, after_seq=0, limit=0),
        }

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
            tasks = task_store.load_task_items(self.tools.workspace, session_id)
        return {
            "count": len(tasks),
            "tasks": tasks,
            "path": task_store.relative_task_snapshot_path(session_id),
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

    def load_session_events_after(
        self, session_id: str, after_seq: int, limit: int = 200
    ) -> Dict[str, Any]:
        self._require_session(session_id)
        replay = self.timeline_store.load_events_after(session_id, after_seq, limit=limit)
        items = []
        for record in replay.get("events", []):
            items.append(
                {
                    "event_id": str(record.get("event_id") or ""),
                    "seq": int(record.get("seq") or 0),
                    "created_at": str(record.get("created_at") or ""),
                    "event_kind": str(record.get("event") or "").replace("_", "."),
                    "payload": dict(record.get("payload") or {}),
                }
            )
        return {
            "status": replay.get("status", "replay"),
            "events": items,
            "first_seq": int(replay.get("first_seq") or 0),
            "last_seq": int(replay.get("last_seq") or 0),
            "reason": str(replay.get("reason") or ""),
        }

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
        dispatch = self._dispatch_input(state, text, event_handler, permission_resolver)
        if dispatch.get("handled") and not dispatch.get("continue_with_text"):
            if command_turn_id:
                self._emit(
                    event_handler,
                    "turn_end",
                    session_id,
                    {
                        "turn_id": command_turn_id,
                        "final_text": "",
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
                state,
                text_to_run,
                stream,
                permission_resolver,
                user_input_resolver,
                event_handler,
                turn_id=command_turn_id or "",
                emit_turn_start=not bool(command_turn_id),
            )
            return self.get_session_snapshot(session_id)
        thread = threading.Thread(
            target=self._run_turn,
            args=(
                state,
                text_to_run,
                stream,
                permission_resolver,
                user_input_resolver,
                event_handler,
                command_turn_id or "",
                not bool(command_turn_id),
            ),
            name="embedagent-session-%s" % session_id[:8],
        )
        with state.lock:
            if state.active_thread is not None and state.active_thread.is_alive():
                raise RuntimeError("当前会话仍在运行中。")
            state.active_thread = thread
        thread.daemon = True
        thread.start()
        return self.get_session_snapshot(session_id)

    def _dispatch_input(
        self,
        state: ManagedSession,
        text: str,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        parsed = parse_slash_command(text)
        if parsed is None:
            return {"handled": False, "continue_with_text": text}
        spec = self.command_registry.get(parsed.name)
        if spec is None:
            self._emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name=parsed.name,
                    success=False,
                    message="未知命令：/%s" % parsed.name,
                    data={"raw_args": parsed.raw_args},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        with state.lock:
            state.current_command_context = parsed.name
            if parsed.name in ("plan", "review"):
                state.workflow_state = parsed.name
            else:
                state.workflow_state = "command"
            state.updated_at = _utc_now()
        handler = getattr(self, "_handle_command_%s" % parsed.name, None)
        if not callable(handler):
            self._emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name=parsed.name,
                    success=False,
                    message="命令尚未实现：/%s" % parsed.name,
                    data={"raw_args": parsed.raw_args},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        return handler(state, parsed, event_handler, permission_resolver)

    def _handle_command_help(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="help",
                success=True,
                message=self.command_registry.help_markdown(),
                data={"commands": [item.name for item in self.command_registry.specs()]},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_mode(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        if not parsed.args:
            self._emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name="mode",
                    success=True,
                    message="当前模式：`%s`" % state.current_mode,
                    data={"current_mode": state.current_mode},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        target_mode = require_mode(parsed.args[0])["slug"]
        remainder = ""
        if parsed.raw_args:
            parts = parsed.raw_args.split(None, 1)
            remainder = str(parts[1] or "").strip() if len(parts) > 1 else ""
        snapshot = self.set_session_mode(state.session.session_id, target_mode)
        message = "已切换到 `%s` 模式。" % target_mode
        if remainder:
            message += " 继续处理后续消息。"
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="mode",
                success=True,
                message=message,
                data={"current_mode": target_mode, "session_snapshot": snapshot},
            ),
        )
        return {"handled": True, "continue_with_text": remainder}

    def _handle_command_sessions(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        sessions = self.list_sessions(limit=10)
        lines = ["## Recent Sessions", ""]
        if not sessions:
            lines.append("当前没有可恢复会话。")
        else:
            for item in sessions:
                label = str(
                    item.get("user_goal")
                    or item.get("summary_text")
                    or item.get("session_id")
                    or ""
                )
                lines.append(
                    "- `%s` [%s] %s"
                    % (
                        str(item.get("session_id") or "")[:12],
                        str(item.get("current_mode") or "-"),
                        label[:96],
                    )
                )
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="sessions",
                success=True,
                message="\n".join(lines),
                data={"sessions": sessions},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_resume(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        reference = parsed.args[0] if parsed.args else "latest"
        mode = parsed.args[1] if len(parsed.args) > 1 else state.current_mode
        snapshot = self.resume_session(reference, mode, event_handler=event_handler)
        self._emit_command_result(
            event_handler,
            self._require_session(str(snapshot.get("session_id") or "")),
            CommandResult(
                command_name="resume",
                success=True,
                message="已恢复会话 `%s`。" % str(snapshot.get("session_id") or ""),
                data={
                    "session_snapshot": snapshot,
                    "switch_session_id": str(snapshot.get("session_id") or ""),
                },
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_workspace(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        payload = self.get_workspace_snapshot()
        git_payload = payload.get("git") if isinstance(payload.get("git"), dict) else {}
        tree_payload = payload.get("tree") if isinstance(payload.get("tree"), dict) else {}
        recipe_payload = payload.get("recipes") if isinstance(payload.get("recipes"), dict) else {}
        lines = [
            "## Workspace",
            "",
            "- path: `%s`" % payload.get("workspace", ""),
            "- branch: `%s`" % git_payload.get("branch", ""),
            "- dirty files: %s" % git_payload.get("dirty_count", 0),
            "- files: %s" % tree_payload.get("file_count", 0),
            "- dirs: %s" % tree_payload.get("dir_count", 0),
            "- recipes: %s" % int(recipe_payload.get("count") or 0),
        ]
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="workspace",
                success=True,
                message="\n".join(lines),
                data=payload,
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_recipes(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        payload = self.list_workspace_recipes()
        items = payload.get("items") or []
        lines = ["## Workspace Recipes", ""]
        if not items:
            lines.append("当前工作区没有可用 recipe。")
        else:
            for item in items:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "- `%s` [%s] %s"
                    % (
                        str(item.get("id") or ""),
                        str(item.get("tool_name") or ""),
                        str(item.get("label") or item.get("command") or ""),
                    )
                )
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="recipes",
                success=True,
                message="\n".join(lines),
                data=payload,
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_run(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        if not parsed.args:
            self._emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name="run",
                    success=False,
                    message="用法：`/run <recipe_id>`",
                    data={},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        recipe_id = str(parsed.args[0] or "").strip()
        target = str(parsed.args[1] or "").strip() if len(parsed.args) > 1 else ""
        profile = str(parsed.args[2] or "").strip() if len(parsed.args) > 2 else ""
        recipes_payload = self.list_workspace_recipes()
        recipe_items = recipes_payload.get("items") or []
        matched = None
        for item in recipe_items:
            if isinstance(item, dict) and str(item.get("id") or "") == recipe_id:
                matched = item
                break
        if matched is None:
            self._emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name="run",
                    success=False,
                    message="未找到 recipe：`%s`" % recipe_id,
                    data={"recipe_id": recipe_id},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        observation = self._execute_tool_from_command(
            state=state,
            command_text="/run %s" % parsed.raw_args,
            tool_name=str(matched.get("tool_name") or ""),
            arguments={"recipe_id": recipe_id, "target": target, "profile": profile},
            permission_resolver=permission_resolver,
            event_handler=event_handler,
        )
        success = bool(observation.success)
        message = (
            "已执行 recipe `%s`。" % recipe_id
            if success
            else "recipe `%s` 执行失败：%s" % (recipe_id, observation.error or "未知错误")
        )
        payload = dict(observation.data) if isinstance(observation.data, dict) else {}
        payload["recipe_id"] = recipe_id
        payload["tool_name"] = str(matched.get("tool_name") or "")
        payload["target"] = target
        payload["profile"] = profile
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="run",
                success=success,
                message=message,
                data=payload,
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_clear(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="clear",
                success=True,
                message="已请求前端清空当前时间线视图。",
                data={"clear_timeline": True},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_tasks(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        payload = self.list_tasks(session_id=state.session.session_id)
        lines = ["## Session Tasks", ""]
        tasks = payload.get("tasks") or []
        if not tasks:
            lines.append("当前会话暂无任务。")
        else:
            for item in tasks:
                if not isinstance(item, dict):
                    continue
                prefix = "[x]" if item.get("done") else "[ ]"
                lines.append("- %s %s" % (prefix, str(item.get("content") or "")))
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="tasks",
                success=True,
                message="\n".join(lines),
                data=payload,
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_artifacts(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        items = self.list_artifacts(limit=20)
        lines = ["## Recent Artifacts", ""]
        if not items:
            lines.append("暂无工件。")
        else:
            for item in items:
                lines.append(
                    "- `%s` (%s)"
                    % (
                        str(item.get("path") or ""),
                        str(item.get("tool_name") or item.get("kind") or ""),
                    )
                )
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="artifacts",
                success=True,
                message="\n".join(lines),
                data={"items": items},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_diff(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        observation = self.tools.execute("git_diff", {"path": ".", "scope": "working"})
        diff_text = ""
        file_count = 0
        if observation.success and isinstance(observation.data, dict):
            diff_text = str(observation.data.get("diff") or "")
            file_count = int(observation.data.get("file_count") or 0)
        if not observation.success:
            message = "无法读取 Git diff：%s" % (observation.error or "未知错误")
        elif not diff_text:
            message = "当前工作区没有未提交 diff。"
        else:
            message = "## Git Diff\n\n- changed files: %s" % file_count
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="diff",
                success=observation.success,
                message=message,
                data=observation.data if isinstance(observation.data, dict) else {},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_permissions(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        context = self.get_permission_context(state.session.session_id)
        lines = [
            "## Permission Context",
            "",
            "- rules path: `%s`" % context.rules_path,
            "- remembered categories: %s" % (", ".join(context.remembered_categories) or "(none)"),
            "- rule count: %s" % len(context.rules),
        ]
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="permissions",
                success=True,
                message="\n".join(lines),
                data={
                    "session_id": context.session_id,
                    "rules_path": context.rules_path,
                    "categories": context.categories,
                    "rules": context.rules,
                    "remembered_categories": context.remembered_categories,
                    "auto_approve_all": context.auto_approve_all,
                    "auto_approve_writes": context.auto_approve_writes,
                    "auto_approve_commands": context.auto_approve_commands,
                },
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_plan(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        current = self.plan_store.load(state.session.session_id)
        if parsed.raw_args:
            summary = parsed.raw_args.splitlines()[0][:120]
            current = self.plan_store.save(
                state.session.session_id,
                title="Current Plan",
                content=parsed.raw_args,
                workflow_state="plan",
                summary=summary,
            )
            with state.lock:
                state.workflow_state = "plan"
                state.active_plan_ref = current.path
                state.updated_at = _utc_now()
            self._emit_plan_updated(event_handler, state, current)
            self._emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name="plan",
                    success=True,
                    message="已更新当前计划。",
                    data={"plan": self._plan_to_dict(current)},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        if current is None:
            current = self.plan_store.save(
                state.session.session_id,
                title="Current Plan",
                content="## Summary\n\n- \n\n## Steps\n\n1. \n\n## Tests\n\n- \n\n## Assumptions\n\n- ",
                workflow_state="plan",
                summary="Current Plan",
            )
            with state.lock:
                state.workflow_state = "plan"
                state.active_plan_ref = current.path
        self._emit_plan_updated(event_handler, state, current)
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="plan",
                success=True,
                message=current.content,
                data={"plan": self._plan_to_dict(current)},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_review(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        events = self.timeline_store.load_events(state.session.session_id, limit=400)
        review = self._build_review_payload(events)
        lines = self._review_markdown_lines(review)
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="review",
                success=True,
                message="\n".join(lines),
                data={
                    "review": review,
                },
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _execute_tool_from_command(
        self,
        state: ManagedSession,
        command_text: str,
        tool_name: str,
        arguments: Dict[str, Any],
        permission_resolver: Optional[PermissionResolver],
        event_handler: Optional[EventHandler],
    ) -> Observation:
        action = Action(
            name=tool_name,
            arguments=dict(arguments),
            call_id="cmd-%s" % uuid.uuid4().hex[:10],
        )
        turn_id = state.current_command_turn_id
        with state.lock:
            state.status = "running"
            state.updated_at = _utc_now()
        self._notify_status(event_handler, state)
        current_step = {"step_id": "", "step_index": 0}

        def on_step_start(step_id: str, step_index: int) -> None:
            current_step["step_id"] = step_id
            current_step["step_index"] = step_index
            with state.lock:
                state.current_command_step_id = step_id
                state.current_command_step_index = step_index
            self._emit(
                event_handler,
                "step_start",
                state.session.session_id,
                {"turn_id": turn_id, "step_id": step_id, "step_index": step_index},
            )

        def on_step_finish(step_index: int, reply: AssistantReply, status: str) -> None:
            self._emit(
                event_handler,
                "step_end",
                state.session.session_id,
                {
                    "turn_id": turn_id,
                    "step_id": current_step["step_id"],
                    "step_index": step_index,
                    "assistant_text": reply.content or "",
                    "finish_reason": reply.finish_reason or "",
                    "status": status,
                },
            )

        def on_tool_start(start_action: Action) -> None:
            payload = {
                "tool_name": start_action.name,
                "arguments": start_action.arguments,
                "call_id": start_action.call_id,
                "turn_id": turn_id,
                "step_id": current_step["step_id"],
                "step_index": current_step["step_index"],
            }
            payload.update(self._tool_event_metadata(start_action.name))
            self._emit(event_handler, "tool_started", state.session.session_id, payload)

        def on_tool_finish(finished_action: Action, observation: Observation) -> None:
            payload = {
                "tool_name": finished_action.name,
                "success": observation.success,
                "error": observation.error,
                "data": observation.data,
                "call_id": finished_action.call_id,
                "turn_id": turn_id,
                "step_id": current_step["step_id"],
                "step_index": current_step["step_index"],
            }
            payload.update(self._tool_event_metadata(finished_action.name))
            self._emit_with_snapshot(event_handler, "tool_finished", state, payload)

        def permission_handler(request: PermissionRequest) -> Optional[bool]:
            ticket = self._create_permission_ticket(
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
                self._clear_pending_permission(state)
                return approved
            with state.lock:
                state.status = "waiting_permission"
                state.pending_event = threading.Event()
            return None

        result, observation = state.engine.submit_command_turn(
            user_text=command_text,
            action=action,
            initial_mode=state.current_mode,
            workflow_state=state.workflow_state,
            session=state.session,
            turn_id=turn_id,
            stop_event=state.stop_event,
            on_tool_start=on_tool_start,
            on_tool_finish=on_tool_finish,
            on_step_start=on_step_start,
            on_step_finish=on_step_finish,
            permission_handler=permission_handler,
            user_input_handler=None,
        )
        state.session = result.session
        if (
            result.transition.reason in ("permission_wait", "user_input_wait")
            and permission_resolver is None
        ):
            with state.lock:
                event = state.pending_event
            if event is not None:
                event.wait()
            approved = False
            with state.lock:
                approved = bool(state.pending_result)
                state.pending_event = None
                state.pending_result = None
                state.status = "running"
            resumed = state.engine.resume_interaction(
                session=state.session,
                initial_mode=state.current_mode,
                interaction_resolution={"approved": approved},
                workflow_state=state.workflow_state,
                stream=False,
                stop_event=state.stop_event,
                on_tool_start=on_tool_start,
                on_tool_finish=on_tool_finish,
                on_step_start=on_step_start,
                on_step_finish=on_step_finish,
                permission_handler=permission_handler,
                user_input_handler=None,
            )
            state.session = resumed.session
            result = resumed
            self._clear_pending_permission(state)
            if state.session.turns and state.session.turns[-1].observations:
                observation = state.session.turns[-1].observations[-1]
            else:
                observation = Observation(
                    tool_name=tool_name,
                    success=False,
                    error="用户拒绝执行该 recipe。",
                    data={"error_kind": "permission_denied"},
                )
        if result.transition.next_mode:
            state.current_mode = result.transition.next_mode
        self._refresh_harness_state(state)
        with state.lock:
            state.status = "idle"
            state.updated_at = _utc_now()
            state.current_command_step_id = current_step["step_id"]
            state.current_command_step_index = current_step["step_index"]
        self._emit(
            event_handler,
            "turn_end",
            state.session.session_id,
            {
                "turn_id": turn_id,
                "final_text": "",
                "termination_reason": result.transition.reason,
                "turns_used": result.turns_used,
                "max_turns": self.max_turns,
                "error": result.transition.message or "",
            },
        )
        self._persist_state(state)
        self._notify_status(event_handler, state)
        return observation

    def _build_review_payload(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        findings = []  # type: List[Dict[str, Any]]
        saw_verify = False
        saw_tests = False
        sections = {
            "diagnostics": [],
            "tests": [],
            "coverage": [],
            "quality": [],
            "git": [],
        }  # type: Dict[str, List[Dict[str, Any]]]
        for record in events:
            if record.get("event") != "tool_finished":
                continue
            payload = record.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            tool_name = str(payload.get("tool_name") or "")
            success = bool(payload.get("success"))
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            review_kind = self._review_kind(tool_name, data)
            if review_kind in ("build", "diagnostic", "test", "coverage", "quality"):
                saw_verify = True
            if review_kind == "test":
                saw_tests = True
            self._append_review_section(sections, tool_name, success, payload, data)
            finding = self._review_finding_from_tool(tool_name, success, payload, data)
            if finding is not None:
                findings.append(finding)
        diff_observation = self.tools.execute("git_diff", {"path": ".", "scope": "working"})
        diff_data = diff_observation.data if isinstance(diff_observation.data, dict) else {}
        diff_file_count = int(diff_data.get("file_count") or 0)
        sections["git"].append(
            {
                "kind": "git_diff",
                "available": bool(diff_observation.success),
                "error": diff_observation.error or "",
                "file_count": diff_file_count,
                "line_count": int(diff_data.get("line_count") or 0),
                "diff_preview": str(diff_data.get("diff") or ""),
                "diff_stored_path": str(diff_data.get("diff_stored_path") or ""),
                "diff_char_count": int(diff_data.get("diff_char_count") or 0),
            }
        )
        if diff_observation.success and diff_file_count > 0 and not saw_verify:
            findings.append(
                {
                    "id": "verify-missing",
                    "priority": 2,
                    "severity": "medium",
                    "title": "Missing verification evidence",
                    "body": "工作区存在 %s 个改动文件，但最近没有看到完整 verify 证据。"
                    % diff_file_count,
                    "evidence": [
                        {"type": "git_diff", "file_count": diff_file_count},
                    ],
                }
            )
        if saw_verify and not saw_tests:
            findings.append(
                {
                    "id": "tests-missing",
                    "priority": 2,
                    "severity": "medium",
                    "title": "No recent test execution",
                    "body": "最近的验证证据里没有测试 recipe 结果，测试覆盖存在缺口。",
                    "evidence": [
                        {"type": "verify_gap", "tool_name": "run_recipe", "recipe_action": "test"}
                    ],
                }
            )
        findings.sort(
            key=lambda item: (int(item.get("priority") or 99), str(item.get("title") or ""))
        )
        no_findings = not findings
        residual_risks = []
        if no_findings:
            residual_risks.append("需要在真实工程和 Win7 目标环境上再次执行完整 verify。")
        elif not saw_verify:
            residual_risks.append("当前结论缺少完整 verify 证据，只能视为阶段性审查。")
        return {
            "summary": "发现 %s 条问题。" % len(findings) if findings else "未发现明确阻塞项。",
            "findings": findings,
            "residual_risks": residual_risks,
            "no_findings": no_findings,
            "diff_file_count": diff_file_count,
            "verify_evidence_present": saw_verify,
            "tests_seen": saw_tests,
            "sections": sections,
        }

    def _append_review_section(
        self,
        sections: Dict[str, List[Dict[str, Any]]],
        tool_name: str,
        success: bool,
        payload: Dict[str, Any],
        data: Dict[str, Any],
    ) -> None:
        review_kind = self._review_kind(tool_name, data)
        if review_kind in ("build", "diagnostic"):
            diagnostics = (
                data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
            )
            sections["diagnostics"].append(
                {
                    "tool_name": tool_name,
                    "review_kind": review_kind,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "error_count": int(data.get("error_count") or 0),
                    "warning_count": int(data.get("warning_count") or 0),
                    "diagnostics": diagnostics[:10],
                }
            )
            return
        if review_kind == "test":
            summary = data.get("test_summary") if isinstance(data.get("test_summary"), dict) else {}
            sections["tests"].append(
                {
                    "tool_name": tool_name,
                    "review_kind": review_kind,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "summary": summary,
                }
            )
            return
        if review_kind == "coverage":
            summary = (
                data.get("coverage_summary")
                if isinstance(data.get("coverage_summary"), dict)
                else {}
            )
            sections["coverage"].append(
                {
                    "tool_name": tool_name,
                    "review_kind": review_kind,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "summary": summary,
                }
            )
            return
        if review_kind == "quality":
            sections["quality"].append(
                {
                    "tool_name": tool_name,
                    "review_kind": review_kind,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "passed": bool(data.get("passed")),
                    "reasons": list(data.get("reasons") or []),
                }
            )

    def _review_finding_from_tool(
        self,
        tool_name: str,
        success: bool,
        payload: Dict[str, Any],
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        review_kind = self._review_kind(tool_name, data)
        if review_kind == "build" and not success:
            detail = self._review_primary_detail(data, payload.get("error"))
            return {
                "id": "build-failed-%s" % str(payload.get("call_id") or tool_name),
                "priority": 1,
                "severity": "high",
                "title": "Build failed",
                "body": detail,
                "evidence": [
                    {
                        "type": "tool_failure",
                        "tool_name": tool_name,
                        "call_id": payload.get("call_id"),
                    }
                ],
            }
        if review_kind == "test":
            summary = data.get("test_summary") if isinstance(data.get("test_summary"), dict) else {}
            failures = int(summary.get("failed") or data.get("test_failures") or 0)
            if (not success) or failures > 0:
                return {
                    "id": "tests-failed-%s" % str(payload.get("call_id") or tool_name),
                    "priority": 1,
                    "severity": "high",
                    "title": "Tests failing",
                    "body": "最近一次测试 recipe 报告了 %s 个失败测试。" % failures,
                    "evidence": [
                        {
                            "type": "test_summary",
                            "tool_name": tool_name,
                            "recipe_action": "test",
                            "failed": failures,
                        }
                    ],
                }
        if review_kind == "diagnostic":
            error_count = int(data.get("error_count") or 0)
            warning_count = int(data.get("warning_count") or 0)
            if (not success) or error_count > 0 or warning_count > 0:
                return {
                    "id": "%s-issues-%s" % (tool_name, str(payload.get("call_id") or tool_name)),
                    "priority": 2,
                    "severity": "medium",
                    "title": "%s reported diagnostics" % tool_name,
                    "body": "%s 返回 error=%s, warning=%s。"
                    % (tool_name, error_count, warning_count),
                    "evidence": [
                        {
                            "type": "diagnostics",
                            "tool_name": tool_name,
                            "error_count": error_count,
                            "warning_count": warning_count,
                        }
                    ],
                }
        if review_kind == "coverage":
            summary = (
                data.get("coverage_summary")
                if isinstance(data.get("coverage_summary"), dict)
                else {}
            )
            line_coverage = summary.get("line_coverage")
            if line_coverage is not None and float(line_coverage) < 80.0:
                return {
                    "id": "coverage-low-%s" % str(payload.get("call_id") or tool_name),
                    "priority": 2,
                    "severity": "medium",
                    "title": "Coverage below expected floor",
                    "body": "最近一次覆盖率结果显示 line coverage 为 %.2f%%，低于 80%% 经验阈值。"
                    % float(line_coverage),
                    "evidence": [
                        {
                            "type": "coverage",
                            "tool_name": tool_name,
                            "line_coverage": float(line_coverage),
                        }
                    ],
                }
        if review_kind == "quality" and not bool(data.get("passed", success)):
            reasons = data.get("reasons") if isinstance(data.get("reasons"), list) else []
            body = (
                "；".join([str(item) for item in reasons if str(item or "").strip()])
                or "质量门未通过。"
            )
            return {
                "id": "quality-gate-failed-%s" % str(payload.get("call_id") or tool_name),
                "priority": 1,
                "severity": "high",
                "title": "Quality gate failed",
                "body": body,
                "evidence": [{"type": "quality_gate", "tool_name": tool_name, "reasons": reasons}],
            }
        return None

    def _review_kind(self, tool_name: str, data: Dict[str, Any]) -> str:
        if tool_name == "run_recipe":
            action = str(data.get("recipe_action") or "").strip().lower()
            if action in ("configure", "build"):
                return "build"
            if action == "test" or isinstance(data.get("test_summary"), dict):
                return "test"
            if action == "coverage" or isinstance(data.get("coverage_summary"), dict):
                return "coverage"
            if action in ("tidy", "analyze"):
                return "diagnostic"
            if isinstance(data.get("diagnostics"), list):
                return "diagnostic"
            return ""
        if tool_name == "report_quality_v2":
            return "quality"
        return ""

    def _review_primary_detail(self, data: Dict[str, Any], fallback: Any) -> str:
        diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
        if diagnostics:
            first = diagnostics[0] if isinstance(diagnostics[0], dict) else {}
            return "%s:%s:%s %s" % (
                first.get("file") or "?",
                first.get("line") or 1,
                first.get("column") or 1,
                first.get("message") or (fallback or "编译失败。"),
            )
        return str(fallback or "编译失败。")

    def _review_markdown_lines(self, review: Dict[str, Any]) -> List[str]:
        lines = ["## Review Findings", ""]
        findings = review.get("findings") if isinstance(review.get("findings"), list) else []
        if findings:
            for item in findings:
                lines.append(
                    "- [%s/P%s] **%s**: %s"
                    % (
                        str(item.get("severity") or "info"),
                        str(item.get("priority") or "-"),
                        str(item.get("title") or "Finding"),
                        str(item.get("body") or ""),
                    )
                )
        else:
            lines.append("- 未发现明确阻塞项。")
        residual = (
            review.get("residual_risks") if isinstance(review.get("residual_risks"), list) else []
        )
        if residual:
            lines.extend(["", "## Residual Risks", ""])
            for item in residual:
                lines.append("- %s" % str(item or ""))
        return lines

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
            "runtime_source": str(runtime.get("runtime_source") or ""),
            "resolved_tool_roots": dict(runtime.get("resolved_tool_roots") or {}),
            "fallback_warnings": list(runtime.get("fallback_warnings") or []),
        }

    def _emit_command_result(
        self,
        event_handler: Optional[EventHandler],
        state: ManagedSession,
        result: CommandResult,
    ) -> None:
        state.engine.record_command_result(
            state.session,
            user_text=state.current_command_text,
            command_name=result.command_name,
            success=result.success,
            message=result.message,
            data=result.data if isinstance(result.data, dict) else {},
            turn_id=result.turn_id or state.current_command_turn_id,
            step_id=result.step_id or state.current_command_step_id,
            step_index=result.step_index or state.current_command_step_index,
        )
        payload = {
            "command_name": result.command_name,
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "turn_id": result.turn_id or state.current_command_turn_id,
            "step_id": result.step_id or state.current_command_step_id,
            "step_index": result.step_index or state.current_command_step_index,
        }
        self._emit_with_snapshot(event_handler, "command_result", state, payload)

    def _wait_for_command_resolution(
        self, session_id: str, timeout_s: float = 3.0
    ) -> Dict[str, Any]:
        deadline = time.time() + max(timeout_s, 0.1)
        snapshot = self.get_session_snapshot(session_id)
        while time.time() < deadline:
            snapshot = self.get_session_snapshot(session_id)
            if (
                not bool(snapshot.get("pending_interaction_valid"))
                and snapshot.get("status") != "waiting_permission"
                and snapshot.get("status") != "waiting_user_input"
            ):
                return snapshot
            state = self._require_session(session_id)
            with state.lock:
                active = state.active_thread
            if active is not None and not active.is_alive():
                return snapshot
            time.sleep(0.05)
        return snapshot

    def _emit_plan_updated(
        self,
        event_handler: Optional[EventHandler],
        state: ManagedSession,
        plan: PlanSnapshot,
    ) -> None:
        self._emit_with_snapshot(
            event_handler,
            "plan_updated",
            state,
            {"plan": self._plan_to_dict(plan)},
        )

    def _plan_to_dict(self, plan: PlanSnapshot) -> Dict[str, Any]:
        return {
            "session_id": plan.session_id,
            "title": plan.title,
            "content": plan.content,
            "updated_at": plan.updated_at,
            "workflow_state": plan.workflow_state,
            "path": plan.path,
            "summary": plan.summary,
        }

    def approve_permission(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        command_wait = False
        with state.lock:
            if (
                state.pending_permission is None
                or state.pending_permission.permission_id != permission_id
            ):
                raise ValueError("未找到待批准的权限请求。")
            if state.pending_event is not None:
                state.pending_result = True
                state.pending_event.set()
                command_wait = True
        if command_wait:
            return self._wait_for_command_resolution(session_id)
        self._run_turn_v2(state, "", True, None, None, self.event_handler, {"approved": True}, True)
        return self.get_session_snapshot(session_id)

    def reject_permission(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        command_wait = False
        with state.lock:
            if (
                state.pending_permission is None
                or state.pending_permission.permission_id != permission_id
            ):
                raise ValueError("未找到待拒绝的权限请求。")
            if state.pending_event is not None:
                state.pending_result = False
                state.pending_event.set()
                command_wait = True
        if command_wait:
            return self._wait_for_command_resolution(session_id)
        self._run_turn_v2(
            state, "", True, None, None, self.event_handler, {"approved": False}, True
        )
        return self.get_session_snapshot(session_id)

    def reply_user_input(
        self,
        session_id: str,
        request_id: str,
        answer: str,
        selected_index: Optional[int] = None,
        selected_mode: str = "",
        selected_option_text: str = "",
    ) -> Dict[str, Any]:
        state = self._require_session(session_id)
        command_wait = False
        with state.lock:
            if (
                state.pending_user_input is None
                or state.pending_user_input.request_id != request_id
            ):
                raise ValueError("未找到待处理的用户问题。")
            if state.pending_user_event is not None:
                state.pending_user_response = UserInputResponse(
                    answer=str(answer or ""),
                    selected_index=selected_index,
                    selected_mode=str(selected_mode or ""),
                    selected_option_text=str(selected_option_text or ""),
                )
                state.pending_user_event.set()
                command_wait = True
        if command_wait:
            snapshot = self._wait_for_command_resolution(session_id)
            self._notify_status(None, state)
            return snapshot
        self._run_turn_v2(
            state,
            "",
            True,
            None,
            None,
            self.event_handler,
            {
                "answer": str(answer or ""),
                "selected_index": selected_index,
                "selected_mode": str(selected_mode or ""),
                "selected_option_text": str(selected_option_text or ""),
            },
            True,
        )
        snapshot = self.get_session_snapshot(session_id)
        self._notify_status(None, state)
        return snapshot

    def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        state = self._require_session(session_id)
        kind = str((payload or {}).get("response_kind") or "").strip()
        with state.lock:
            if (
                state.pending_permission is not None
                and state.pending_permission.permission_id == interaction_id
            ):
                pass
            elif (
                state.pending_user_input is not None
                and state.pending_user_input.request_id == interaction_id
            ):
                pass
            else:
                raise ValueError("未找到待处理的交互请求。")
        if (
            state.pending_permission is not None
            and state.pending_permission.permission_id == interaction_id
        ):
            if kind == "approve":
                self.approve_permission(session_id, interaction_id)
            else:
                self.reject_permission(session_id, interaction_id)
        else:
            self.reply_user_input(
                session_id,
                interaction_id,
                str((payload or {}).get("answer") or ""),
                selected_index=(payload or {}).get("selected_index"),
                selected_mode=str((payload or {}).get("selected_mode") or ""),
                selected_option_text=str((payload or {}).get("selected_option_text") or ""),
            )
        return {
            "session_id": session_id,
            "interaction_id": interaction_id,
            "status": "resolved",
            "snapshot": self.get_session_snapshot(session_id),
        }

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
        turn_id: str = "",
        emit_turn_start: bool = True,
    ) -> None:
        return self._run_turn_v2(
            state=state,
            text=text,
            stream=stream,
            permission_resolver=permission_resolver,
            user_input_resolver=user_input_resolver,
            event_handler=event_handler,
            turn_id=turn_id,
            emit_turn_start=emit_turn_start,
        )

    def _run_turn_v2(
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
            if not bool(getattr(result, "compacted", False)):
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
            ticket = self._create_permission_ticket(
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
                self._clear_pending_permission(state)
                return approved
            with state.lock:
                state.status = "waiting_permission"
            return None

        def user_input_handler(request: UserInputRequest) -> Optional[UserInputResponse]:
            ticket = self._create_user_input_ticket(
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
                self._clear_pending_user_input(state)
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

    def _create_permission_ticket(
        self,
        state: ManagedSession,
        request: PermissionRequest,
        turn_id: str = "",
        step_id: str = "",
        step_index: int = 0,
    ) -> PermissionTicket:
        ticket = PermissionTicket(
            permission_id="perm_%s" % uuid.uuid4().hex[:8],
            session_id=state.session.session_id,
            tool_name=request.tool_name,
            category=request.category,
            reason=request.reason,
            details=request.details,
            turn_id=turn_id,
            step_id=step_id,
            step_index=step_index,
        )
        with state.lock:
            state.pending_permission = ticket
            state.pending_result = None
            state.updated_at = _utc_now()
        return ticket

    def _create_user_input_ticket(
        self,
        state: ManagedSession,
        request: UserInputRequest,
        turn_id: str = "",
        step_id: str = "",
        step_index: int = 0,
    ) -> UserInputTicket:
        ticket = UserInputTicket(
            request_id="ask_%s" % uuid.uuid4().hex[:8],
            session_id=state.session.session_id,
            tool_name=request.tool_name,
            question=request.question,
            options=[
                {"index": item.index, "text": item.text, "mode": item.mode}
                for item in request.options
            ],
            details=request.details,
            turn_id=turn_id,
            step_id=step_id,
            step_index=step_index,
        )
        with state.lock:
            state.pending_user_input = ticket
            state.pending_user_response = None
            state.updated_at = _utc_now()
        return ticket

    def _clear_pending_permission(self, state: ManagedSession) -> None:
        with state.lock:
            state.pending_permission = None
            state.pending_event = None
            state.pending_result = None
            if state.status != "error":
                state.status = "running"
            state.updated_at = _utc_now()

    def _clear_pending_user_input(self, state: ManagedSession) -> None:
        with state.lock:
            state.pending_user_input = None
            state.pending_user_event = None
            state.pending_user_response = None
            if state.status != "error":
                state.status = "running"
            state.updated_at = _utc_now()

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
