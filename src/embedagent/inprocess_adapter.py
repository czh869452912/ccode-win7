from __future__ import annotations

import difflib
import io
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from embedagent.context import ContextManager
from embedagent.interaction import UserInputRequest, UserInputResponse
from embedagent.llm import OpenAICompatibleClient
from embedagent.loop import AgentLoop
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.modes import DEFAULT_MODE, build_system_prompt, initialize_modes, require_mode
from embedagent.plan_store import PlanStore
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.protocol import CommandResult, PermissionContextView, PlanSnapshot
from embedagent.project_memory import ProjectMemoryStore
from embedagent.query_engine import QueryEngine
from embedagent.session_restore import SessionRestoreResult, SessionRestorer
from embedagent.session import Action, AssistantReply, Observation, Session
from embedagent.session_store import SessionSummaryStore
from embedagent.session_timeline import SessionTimelineStore
from embedagent.slash_commands import ParsedSlashCommand, SlashCommandRegistry, parse_slash_command
from embedagent.transcript_store import TranscriptStore
from embedagent import todos as todo_store
from embedagent.tools import ToolRuntime
from embedagent.tools._base import SKIP_DIR_NAMES
from embedagent.workspace_profile import build_workspace_profile_message


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
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class PermissionTicket:
    permission_id: str
    session_id: str
    tool_name: str
    category: str
    reason: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "permission_id": self.permission_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "category": self.category,
            "reason": self.reason,
            "details": self.details,
        }


@dataclass
class UserInputTicket:
    request_id: str
    session_id: str
    tool_name: str
    question: str
    options: List[Dict[str, Any]]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "question": self.question,
            "options": self.options,
            "details": self.details,
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
        }
    return None


@dataclass
class ManagedSession:
    session: Session
    current_mode: str
    status: str = "idle"
    workflow_state: str = "chat"
    active_plan_ref: str = ""
    current_command_context: str = ""
    summary_ref: str = ""
    updated_at: str = field(default_factory=_utc_now)
    last_error: Optional[str] = None
    pending_permission: Optional[PermissionTicket] = None
    pending_user_input: Optional[UserInputTicket] = None
    pending_event: Optional[threading.Event] = None
    pending_result: Optional[bool] = None
    pending_user_event: Optional[threading.Event] = None
    pending_user_response: Optional[UserInputResponse] = None
    active_thread: Optional[threading.Thread] = None
    resume_summary: Optional[Dict[str, Any]] = None
    last_assistant_message: str = ""
    restore_stop_reason: str = ""
    restore_consumed_event_count: int = 0
    restore_transcript_event_count: int = 0
    remembered_permission_categories: Set[str] = field(default_factory=set)
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class InProcessAdapter(object):
    def __init__(
        self,
        client: OpenAICompatibleClient,
        tools: ToolRuntime,
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
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.permission_policy = permission_policy or PermissionPolicy(auto_approve_all=True)
        self.summary_store = summary_store or SessionSummaryStore(self.tools.workspace)
        self.timeline_store = timeline_store or SessionTimelineStore(self.tools.workspace)
        self.project_memory_store = project_memory_store or ProjectMemoryStore(self.tools.workspace)
        self.context_manager = context_manager or ContextManager(project_memory=self.project_memory_store)
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
        initialize_modes(self.tools.workspace)
        self._sessions = {}  # type: Dict[str, ManagedSession]
        self._lock = threading.RLock()

    def create_session(
        self,
        mode: str = DEFAULT_MODE,
        event_handler: Optional[EventHandler] = None,
    ) -> Dict[str, Any]:
        current_mode = require_mode(mode)["slug"]
        session = Session()
        todo_store.ensure_session_todos(self.tools.workspace, session.session_id, seed_from_legacy=False)
        profile_message = session.add_system_message(build_workspace_profile_message(self.tools.workspace, session.session_id))
        mode_message = session.add_system_message(
            build_system_prompt(current_mode, getattr(self.tools, "app_config", None), self.tools.workspace)
        )
        self.transcript_store.append_event(
            session.session_id,
            "session_meta",
            {
                "current_mode": current_mode,
                "started_at": session.started_at,
                "workspace": self.tools.workspace,
            },
        )
        for message in (profile_message, mode_message):
            self.transcript_store.append_event(
                session.session_id,
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
        plan = self.plan_store.load(session.session_id)
        state = ManagedSession(
            session=session,
            current_mode=current_mode,
            active_plan_ref=plan.path if plan is not None else "",
            workflow_state="plan" if plan is not None else "chat",
        )
        self._persist_state(state)
        with self._lock:
            self._sessions[session.session_id] = state
        snapshot = self.get_session_snapshot(session.session_id)
        self._emit(event_handler, "session_created", session.session_id, {"session_snapshot": snapshot})
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
        current_mode = require_mode(
            mode
            or restored.current_mode
            or DEFAULT_MODE
        )["slug"]
        session = restored.session
        todo_store.ensure_session_todos(
            self.tools.workspace,
            session.session_id,
            seed_from_legacy=True,
        )
        summary_ref = ""
        try:
            summary_ref = self.summary_store.persist(session, current_mode)
        except Exception:
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
        if session.pending_interaction is not None:
            if session.pending_interaction.kind == "permission":
                state.status = "waiting_permission"
                permission_payload = dict(session.pending_interaction.request_payload.get("permission") or {})
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
                request_payload = dict(session.pending_interaction.request_payload.get("request") or {})
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

    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.summary_store.list_summaries(limit=limit)

    def get_session_snapshot(self, session_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        runtime = runtime_lookup() if callable(runtime_lookup) else {}
        with state.lock:
            summary = self._read_summary_for_state(state)
            updated_at = str((summary or {}).get("updated_at") or state.updated_at)
            recent_transitions = _normalize_recent_transitions(list((summary or {}).get("recent_transitions") or []))
            payload = {
                "session_id": state.session.session_id,
                "status": state.status,
                "current_mode": state.current_mode,
                "started_at": str((summary or {}).get("started_at") or state.session.started_at),
                "updated_at": updated_at,
                "workflow_state": state.workflow_state,
                "has_active_plan": bool(state.active_plan_ref),
                "active_plan_ref": state.active_plan_ref,
                "current_command_context": state.current_command_context,
                "last_user_message": str((summary or {}).get("latest_user_message") or ""),
                "last_assistant_message": str((summary or {}).get("assistant_last_reply") or state.last_assistant_message or ""),
                "summary_text": str((summary or {}).get("summary_text") or ""),
                "user_goal": str((summary or {}).get("user_goal") or ""),
                "summary_ref": str((summary or {}).get("summary_ref") or state.summary_ref or ""),
                "compact_summary_text": str((summary or {}).get("compact_summary_text") or ""),
                "context_analysis": dict((summary or {}).get("context_analysis") or {}),
                "compact_boundary_count": len(getattr(state.session, "compact_boundaries", []) or []),
                "workspace_intelligence": list((summary or {}).get("workspace_intelligence") or []),
                "context_pipeline_steps": list((summary or {}).get("context_pipeline_steps") or []),
                "last_transition_reason": str((summary or {}).get("last_transition_reason") or ""),
                "last_transition_message": str((summary or {}).get("last_transition_message") or ""),
                "last_transition_display_reason": _display_transition_reason(str((summary or {}).get("last_transition_reason") or "")),
                "recent_transition_reasons": list((summary or {}).get("recent_transition_reasons") or []),
                "recent_transitions": recent_transitions,
                "compact_retry_count": int((summary or {}).get("compact_retry_count") or 0),
                "has_pending_permission": state.pending_permission is not None,
                "pending_permission": state.pending_permission.to_dict() if state.pending_permission else None,
                "has_pending_user_input": state.pending_user_input is not None,
                "pending_user_input": state.pending_user_input.to_dict() if state.pending_user_input else None,
                "pending_interaction": _pending_interaction_payload(state),
                "last_error": state.last_error,
                "restore_stop_reason": state.restore_stop_reason,
                "restore_consumed_event_count": state.restore_consumed_event_count,
                "restore_transcript_event_count": state.restore_transcript_event_count,
                "timeline_replay_status": "degraded" if state.restore_stop_reason == "transcript_missing" else "replay",
                "timeline_first_seq": 0,
                "timeline_last_seq": 0,
                "timeline_integrity": "degraded" if state.restore_stop_reason == "transcript_missing" else "healthy",
                "pending_interaction_valid": bool(state.pending_permission or state.pending_user_input),
                "runtime_source": str(runtime.get("runtime_source") or ""),
                "bundled_tools_ready": bool(runtime.get("bundled_tools_ready")),
                "fallback_warnings": list(runtime.get("fallback_warnings") or []),
                "runtime_environment": runtime,
            }
            return payload

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
        root = self._resolve_workspace_candidate(path, allow_missing=False)
        if not os.path.isdir(root):
            raise ValueError("路径不是目录：%s" % path)
        items = []  # type: List[Dict[str, Any]]
        truncated = [False]

        def walk(current_path: str, depth: int) -> None:
            if truncated[0]:
                return
            try:
                names = sorted(os.listdir(current_path), key=lambda item: item.lower())
            except OSError:
                return
            directories = []
            files = []
            for name in names:
                absolute = os.path.join(current_path, name)
                if os.path.isdir(absolute):
                    if name in SKIP_DIR_NAMES:
                        continue
                    directories.append((name, absolute))
                else:
                    files.append((name, absolute))
            for name, absolute in directories + files:
                items.append(
                    {
                        "path": self._relative_path(absolute),
                        "name": name,
                        "kind": "dir" if os.path.isdir(absolute) else "file",
                        "depth": depth,
                    }
                )
                if len(items) >= limit:
                    truncated[0] = True
                    return
                if os.path.isdir(absolute) and depth < max_depth:
                    walk(absolute, depth + 1)

        walk(root, 0)
        return {
            "root": self._relative_path(root),
            "max_depth": max_depth,
            "limit": limit,
            "truncated": truncated[0],
            "items": items,
        }

    def list_workspace_children(
        self,
        path: str = ".",
        limit: int = 200,
    ) -> Dict[str, Any]:
        root = self._resolve_workspace_candidate(path, allow_missing=False)
        if not os.path.isdir(root):
            raise ValueError("路径不是目录：%s" % path)
        items = []  # type: List[Dict[str, Any]]
        try:
            names = sorted(os.listdir(root), key=lambda item: item.lower())
        except OSError:
            names = []
        for name in names:
            absolute = os.path.join(root, name)
            if os.path.isdir(absolute) and name in SKIP_DIR_NAMES:
                continue
            kind = "dir" if os.path.isdir(absolute) else "file"
            items.append(
                {
                    "path": self._relative_path(absolute),
                    "name": name,
                    "kind": kind,
                    "has_children": self._directory_has_visible_children(absolute) if kind == "dir" else False,
                }
            )
            if len(items) >= limit:
                break
        return {"root": self._relative_path(root), "limit": limit, "items": items}

    def read_workspace_file(self, path: str) -> Dict[str, Any]:
        candidate = self._resolve_workspace_candidate(path, allow_missing=False)
        if not os.path.isfile(candidate):
            raise ValueError("只能读取文件，不能读取目录。")
        content, newline, encoding = self.tools._ctx.read_text(candidate)
        return {
            "path": self._relative_path(candidate),
            "encoding": encoding,
            "newline": newline,
            "char_count": len(content),
            "line_count": content.count("\n") + (1 if content else 0),
            "truncated": False,
            "content": content,
        }

    def write_workspace_file(self, path: str, content: str) -> Dict[str, Any]:
        candidate = self._resolve_workspace_candidate(path, allow_missing=True)
        existed = os.path.isfile(candidate)
        if os.path.isdir(candidate):
            raise ValueError("不能把目录当作文件写入：%s" % path)
        parent = os.path.dirname(candidate)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        newline = "\n"
        encoding = "utf-8"
        old_content = ""
        if existed:
            old_content, newline, encoding = self.tools._ctx.read_text(candidate)
        serialized = str(content or "")
        self.tools._ctx.write_text(candidate, serialized, newline, encoding)
        diff_text = "".join(
            difflib.unified_diff(
                old_content.splitlines(True),
                serialized.splitlines(True),
                fromfile=self._relative_path(candidate),
                tofile=self._relative_path(candidate),
                lineterm="",
            )
        )
        return {
            "path": self._relative_path(candidate),
            "created": not existed,
            "encoding": encoding,
            "newline": newline,
            "char_count": len(serialized),
            "line_count": serialized.count("\n") + (1 if serialized else 0),
            "diff_preview": diff_text,
        }

    def get_session_timeline(self, session_id: str, limit: int = 200) -> Dict[str, Any]:
        state = self._require_session(session_id)
        return {
            "session_id": state.session.session_id,
            "events": self.timeline_store.load_events(state.session.session_id, limit=limit),
            "latest_assistant_reply": self.timeline_store.latest_assistant_reply(state.session.session_id),
        }

    def build_structured_timeline(self, session_id: str, limit: int = 200) -> Dict[str, Any]:
        """Return timeline as structured Turn list, aggregated from raw events.

        Falls back to raw events format for old sessions without turn_start events.
        """
        def make_transition_item(event_name: str, payload: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "kind": event_name,
                "display_reason": _display_transition_reason(event_name),
                "message": str(payload.get("message") or payload.get("reason") or ""),
                "created_at": record.get("created_at", ""),
                "metadata": dict(payload),
            }

        state = self._require_session(session_id)
        raw_events = self.timeline_store.load_events(state.session.session_id, limit=limit)
        has_turn_start = any(r.get("event") == "turn_start" for r in raw_events)
        if not has_turn_start:
            return {
                "session_id": state.session.session_id,
                "projection_source": "raw_events",
                "events": raw_events,
                "turns": [],
            }
        has_step_start = any(r.get("event") == "step_start" for r in raw_events)
        if has_step_start:
            turns = []
            current_turn = None  # type: Optional[Dict[str, Any]]
            current_step = None  # type: Optional[Dict[str, Any]]
            tool_index = {}  # type: Dict[str, int]
            for record in raw_events:
                event = record.get("event")
                payload = record.get("payload") or {}
                if event == "turn_start":
                    current_turn = {
                        "turn_id": payload.get("turn_id", ""),
                        "user_text": payload.get("user_text", ""),
                        "projection_kind": "step_events",
                        "steps": [],
                        "transitions": [],
                        "status": "in_progress",
                    }
                    current_step = None
                    tool_index = {}
                    turns.append(current_turn)
                elif event == "step_start" and current_turn is not None:
                    current_step = {
                        "step_id": payload.get("step_id", ""),
                        "step_index": int(payload.get("step_index") or 0),
                        "reasoning": "",
                        "assistant_text": "",
                        "projection_kind": "recorded_step",
                        "synthetic": False,
                        "tool_calls": [],
                        "transitions": [],
                        "status": "in_progress",
                    }
                    tool_index = {}
                    current_turn["steps"].append(current_step)
                elif event == "reasoning_delta" and current_step is not None:
                    current_step["reasoning"] += payload.get("text", "")
                elif event in ("compact_retry", "context_compacted", "mode_changed", "permission_required", "user_input_required") and current_turn is not None:
                    transition_item = make_transition_item(event, payload, record)
                    current_turn["transitions"].append(dict(transition_item))
                    if current_step is not None:
                        current_step["transitions"].append(dict(transition_item))
                    if event == "permission_required":
                        current_turn["status"] = "waiting_permission"
                        if current_step is not None and current_step.get("status") == "in_progress":
                            current_step["status"] = "waiting_permission"
                    elif event == "user_input_required":
                        current_turn["status"] = "waiting_user_input"
                        if current_step is not None and current_step.get("status") == "in_progress":
                            current_step["status"] = "waiting_user_input"
                elif event == "tool_started" and current_step is not None:
                    call_id = payload.get("call_id") or record.get("event_id", "")
                    tool_call = {
                        "call_id": call_id,
                        "tool_name": payload.get("tool_name", ""),
                        "tool_label": payload.get("tool_label", payload.get("tool_name", "")),
                        "arguments": payload.get("arguments") or {},
                        "status": "running",
                        "data": None,
                        "error": "",
                        "permission_category": payload.get("permission_category", ""),
                        "supports_diff_preview": bool(payload.get("supports_diff_preview", False)),
                        "runtime_source": payload.get("runtime_source", ""),
                        "resolved_tool_roots": payload.get("resolved_tool_roots") or {},
                    }
                    tool_index[call_id] = len(current_step["tool_calls"])
                    current_step["tool_calls"].append(tool_call)
                elif event == "tool_finished" and current_step is not None:
                    call_id = payload.get("call_id") or record.get("event_id", "")
                    idx = tool_index.get(call_id)
                    update = {
                        "status": "success" if payload.get("success") else "error",
                        "data": payload.get("data"),
                        "error": payload.get("error") or "",
                        "tool_label": payload.get("tool_label", payload.get("tool_name", "")),
                        "permission_category": payload.get("permission_category", ""),
                        "supports_diff_preview": bool(payload.get("supports_diff_preview", False)),
                        "runtime_source": payload.get("runtime_source", ""),
                        "resolved_tool_roots": payload.get("resolved_tool_roots") or {},
                    }
                    if idx is not None:
                        current_step["tool_calls"][idx].update(update)
                    else:
                        current_step["tool_calls"].append(
                            dict(
                                call_id=call_id,
                                tool_name=payload.get("tool_name", ""),
                                tool_label=payload.get("tool_label", payload.get("tool_name", "")),
                                arguments={},
                                **update
                            )
                        )
                elif event == "step_end" and current_step is not None:
                    if payload.get("assistant_text") is not None:
                        current_step["assistant_text"] = payload.get("assistant_text") or ""
                    current_step["status"] = payload.get("status") or "completed"
                elif event == "turn_end" and current_turn is not None:
                    termination_reason = str(payload.get("termination_reason") or "completed")
                    current_turn["status"] = termination_reason
                    if termination_reason and termination_reason != "completed":
                        transition_item = {
                            "kind": termination_reason,
                            "display_reason": _display_transition_reason(termination_reason),
                            "message": str(payload.get("error") or payload.get("message") or ""),
                            "created_at": record.get("created_at", ""),
                            "metadata": dict(payload),
                        }
                        current_turn["transitions"].append(dict(transition_item))
                        if current_step is not None:
                            if current_step.get("status") in ("in_progress", "tool_calls", "completed"):
                                current_step["status"] = termination_reason
                            current_step["transitions"].append(dict(transition_item))
            return {
                "session_id": state.session.session_id,
                "projection_source": "step_events",
                "events": raw_events,
                "turns": turns,
            }
        turns = []
        current_turn = None  # type: Optional[Dict[str, Any]]
        tool_index = {}  # type: Dict[str, int]
        for record in raw_events:
            event = record.get("event")
            payload = record.get("payload") or {}
            if event == "turn_start":
                current_turn = {
                    "turn_id": payload.get("turn_id", ""),
                    "user_text": payload.get("user_text", ""),
                    "reasoning": "",
                    "tool_calls": [],
                    "assistant_text": "",
                    "projection_kind": "turn_events",
                    "transitions": [],
                    "status": "in_progress",
                    "steps": [],
                }
                tool_index = {}
                turns.append(current_turn)
            elif event == "reasoning_delta" and current_turn is not None:
                current_turn["reasoning"] += payload.get("text", "")
            elif event in ("compact_retry", "context_compacted", "mode_changed", "permission_required", "user_input_required") and current_turn is not None:
                current_turn["transitions"].append(make_transition_item(event, payload, record))
                if event == "permission_required":
                    current_turn["status"] = "waiting_permission"
                elif event == "user_input_required":
                    current_turn["status"] = "waiting_user_input"
            elif event == "tool_started" and current_turn is not None:
                call_id = payload.get("call_id") or record.get("event_id", "")
                tool_call = {
                    "call_id": call_id,
                    "tool_name": payload.get("tool_name", ""),
                    "tool_label": payload.get("tool_label", payload.get("tool_name", "")),
                    "arguments": payload.get("arguments") or {},
                    "status": "running",
                    "data": None,
                    "error": "",
                    "permission_category": payload.get("permission_category", ""),
                    "supports_diff_preview": bool(payload.get("supports_diff_preview", False)),
                }
                tool_index[call_id] = len(current_turn["tool_calls"])
                current_turn["tool_calls"].append(tool_call)
            elif event == "tool_finished" and current_turn is not None:
                call_id = payload.get("call_id") or record.get("event_id", "")
                idx = tool_index.get(call_id)
                update = {
                    "status": "success" if payload.get("success") else "error",
                    "data": payload.get("data"),
                    "error": payload.get("error") or "",
                    "tool_label": payload.get("tool_label", payload.get("tool_name", "")),
                    "permission_category": payload.get("permission_category", ""),
                    "supports_diff_preview": bool(payload.get("supports_diff_preview", False)),
                }
                if idx is not None:
                    current_turn["tool_calls"][idx].update(update)
                else:
                    current_turn["tool_calls"].append(dict(
                        call_id=call_id,
                        tool_name=payload.get("tool_name", ""),
                        tool_label=payload.get("tool_label", payload.get("tool_name", "")),
                        arguments={},
                        **update,
                    ))
            elif event == "turn_end" and current_turn is not None:
                termination_reason = str(payload.get("termination_reason") or "completed")
                current_turn["assistant_text"] = payload.get("final_text") or ""
                current_turn["status"] = termination_reason
                if termination_reason and termination_reason != "completed":
                    current_turn["transitions"].append({
                        "kind": termination_reason,
                        "display_reason": _display_transition_reason(termination_reason),
                        "message": str(payload.get("error") or payload.get("message") or ""),
                        "created_at": record.get("created_at", ""),
                        "metadata": dict(payload),
                    })
        for turn in turns:
            turn["steps"] = [
                {
                    "step_id": "%s-step-1" % (turn.get("turn_id") or "legacy"),
                    "step_index": 1,
                    "reasoning": turn.get("reasoning") or "",
                    "assistant_text": turn.get("assistant_text") or "",
                    "projection_kind": "synthetic_single_step",
                    "synthetic": True,
                    "tool_calls": list(turn.get("tool_calls") or []),
                    "transitions": list(turn.get("transitions") or []),
                    "status": turn.get("status") or "completed",
                }
            ]
        return {
            "session_id": state.session.session_id,
            "projection_source": "turn_events",
            "events": raw_events,
            "turns": turns,
        }

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

    def list_todos(self, session_id: str = "") -> Dict[str, Any]:
        todos = todo_store.load_todos(self.tools.workspace, session_id=session_id)
        return {
            "count": len(todos),
            "todos": todos,
            "path": todo_store.relative_todos_path(session_id),
            "session_id": session_id,
        }

    def get_session_plan(self, session_id: str) -> Optional[PlanSnapshot]:
        state = self._require_session(session_id)
        return self.plan_store.load(state.session.session_id)

    def get_permission_context(self, session_id: str) -> PermissionContextView:
        state = self._require_session(session_id)
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
            return method()
        return []

    def load_session_events_after(self, session_id: str, after_seq: int, limit: int = 200) -> Dict[str, Any]:
        self._require_session(session_id)
        replay = self.timeline_store.load_events_after(session_id, after_seq, limit=limit)
        items = []
        for record in replay.get("events", []):
            items.append({
                "event_id": str(record.get("event_id") or ""),
                "seq": int(record.get("seq") or 0),
                "created_at": str(record.get("created_at") or ""),
                "event_kind": str(record.get("event") or "").replace("_", "."),
                "payload": dict(record.get("payload") or {}),
            })
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
        dispatch = self._dispatch_input(state, text, event_handler, permission_resolver)
        if dispatch.get("handled") and not dispatch.get("continue_with_text"):
            return self.get_session_snapshot(session_id)
        text_to_run = str(dispatch.get("continue_with_text") or text)
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
            )
            return self.get_session_snapshot(session_id)
        thread = threading.Thread(
            target=self._run_turn,
            args=(state, text_to_run, stream, permission_resolver, user_input_resolver, event_handler),
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
                label = str(item.get("user_goal") or item.get("summary_text") or item.get("session_id") or "")
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
                data={"session_snapshot": snapshot, "switch_session_id": str(snapshot.get("session_id") or "")},
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
            tool_name=str(matched.get("tool_name") or ""),
            arguments={"recipe_id": recipe_id, "target": target, "profile": profile},
            permission_resolver=permission_resolver,
            event_handler=event_handler,
        )
        success = bool(observation.success)
        message = "已执行 recipe `%s`。" % recipe_id if success else "recipe `%s` 执行失败：%s" % (recipe_id, observation.error or "未知错误")
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

    def _handle_command_todos(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        payload = self.list_todos(session_id=state.session.session_id)
        lines = ["## Session Todos", ""]
        todos = payload.get("todos") or []
        if not todos:
            lines.append("当前会话暂无待办。")
        else:
            for item in todos:
                if not isinstance(item, dict):
                    continue
                prefix = "[x]" if item.get("done") else "[ ]"
                lines.append("- %s %s" % (prefix, str(item.get("content") or "")))
        self._emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="todos",
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
                lines.append("- `%s` (%s)" % (str(item.get("path") or ""), str(item.get("tool_name") or item.get("kind") or "")))
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
        decision = self.permission_policy.evaluate(action)
        with state.lock:
            state.status = "running"
            state.updated_at = _utc_now()
        self._notify_status(event_handler, state)
        if decision.outcome == "deny":
            with state.lock:
                state.status = "idle"
            self._notify_status(event_handler, state)
            return Observation(tool_name=tool_name, success=False, error=decision.error or "权限拒绝该操作。", data={"error_kind": "permission_denied"})
        if decision.outcome == "ask" and decision.request is not None:
            ticket = self._create_permission_ticket(state, decision.request)
            with state.lock:
                state.status = "waiting_permission"
                state.pending_event = threading.Event()
            self._emit_with_snapshot(
                event_handler,
                "permission_required",
                state,
                {"permission": ticket.to_dict()},
            )
            self._notify_status(event_handler, state)
            if permission_resolver is not None:
                approved = bool(permission_resolver(ticket.to_dict()))
                self._clear_pending_permission(state)
                self._notify_status(event_handler, state)
            else:
                with state.lock:
                    event = state.pending_event
                event.wait()
                with state.lock:
                    approved = bool(state.pending_result)
                self._clear_pending_permission(state)
                self._notify_status(event_handler, state)
            if not approved:
                with state.lock:
                    state.status = "idle"
                self._notify_status(event_handler, state)
                return Observation(tool_name=tool_name, success=False, error="用户拒绝执行该 recipe。", data={"error_kind": "permission_denied"})
        payload = {
            "tool_name": tool_name,
            "arguments": dict(arguments),
            "call_id": action.call_id,
        }
        payload.update(self._tool_event_metadata(tool_name))
        self._emit(event_handler, "tool_started", state.session.session_id, payload)
        observation = self.tools.execute(tool_name, dict(arguments))
        self._emit_with_snapshot(
            event_handler,
            "tool_finished",
            state,
            {
                "tool_name": tool_name,
                "success": observation.success,
                "error": observation.error,
                "data": observation.data,
                "call_id": action.call_id,
                **self._tool_event_metadata(tool_name),
            },
        )
        with state.lock:
            state.status = "idle"
            state.updated_at = _utc_now()
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
            if tool_name in ("compile_project", "run_tests", "run_clang_tidy", "run_clang_analyzer", "collect_coverage", "report_quality"):
                saw_verify = True
            if tool_name == "run_tests":
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
                    "body": "工作区存在 %s 个改动文件，但最近没有看到完整 verify 证据。" % diff_file_count,
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
                    "body": "最近的验证证据里没有 `run_tests` 结果，测试覆盖存在缺口。",
                    "evidence": [{"type": "verify_gap", "tool_name": "run_tests"}],
                }
            )
        findings.sort(key=lambda item: (int(item.get("priority") or 99), str(item.get("title") or "")))
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
        if tool_name == "compile_project":
            diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
            sections["diagnostics"].append(
                {
                    "tool_name": tool_name,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "error_count": int(data.get("error_count") or 0),
                    "warning_count": int(data.get("warning_count") or 0),
                    "diagnostics": diagnostics[:10],
                }
            )
            return
        if tool_name in ("run_clang_tidy", "run_clang_analyzer"):
            diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
            sections["diagnostics"].append(
                {
                    "tool_name": tool_name,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "error_count": int(data.get("error_count") or 0),
                    "warning_count": int(data.get("warning_count") or 0),
                    "diagnostics": diagnostics[:10],
                }
            )
            return
        if tool_name == "run_tests":
            summary = data.get("test_summary") if isinstance(data.get("test_summary"), dict) else {}
            sections["tests"].append(
                {
                    "tool_name": tool_name,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "summary": summary,
                }
            )
            return
        if tool_name == "collect_coverage":
            summary = data.get("coverage_summary") if isinstance(data.get("coverage_summary"), dict) else {}
            sections["coverage"].append(
                {
                    "tool_name": tool_name,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "summary": summary,
                }
            )
            return
        if tool_name == "report_quality":
            sections["quality"].append(
                {
                    "tool_name": tool_name,
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
        if tool_name == "compile_project" and not success:
            detail = self._review_primary_detail(data, payload.get("error"))
            return {
                "id": "build-failed-%s" % str(payload.get("call_id") or tool_name),
                "priority": 1,
                "severity": "high",
                "title": "Build failed",
                "body": detail,
                "evidence": [{"type": "tool_failure", "tool_name": tool_name, "call_id": payload.get("call_id")}],
            }
        if tool_name == "run_tests":
            summary = data.get("test_summary") if isinstance(data.get("test_summary"), dict) else {}
            failures = int(summary.get("failed") or data.get("test_failures") or 0)
            if (not success) or failures > 0:
                return {
                    "id": "tests-failed-%s" % str(payload.get("call_id") or tool_name),
                    "priority": 1,
                    "severity": "high",
                    "title": "Tests failing",
                    "body": "最近一次 `run_tests` 报告了 %s 个失败测试。" % failures,
                    "evidence": [{"type": "test_summary", "tool_name": tool_name, "failed": failures}],
                }
        if tool_name in ("run_clang_tidy", "run_clang_analyzer"):
            error_count = int(data.get("error_count") or 0)
            warning_count = int(data.get("warning_count") or 0)
            if (not success) or error_count > 0 or warning_count > 0:
                return {
                    "id": "%s-issues-%s" % (tool_name, str(payload.get("call_id") or tool_name)),
                    "priority": 2,
                    "severity": "medium",
                    "title": "%s reported diagnostics" % tool_name,
                    "body": "%s 返回 error=%s, warning=%s。" % (tool_name, error_count, warning_count),
                    "evidence": [{"type": "diagnostics", "tool_name": tool_name, "error_count": error_count, "warning_count": warning_count}],
                }
        if tool_name == "collect_coverage":
            summary = data.get("coverage_summary") if isinstance(data.get("coverage_summary"), dict) else {}
            line_coverage = summary.get("line_coverage")
            if line_coverage is not None and float(line_coverage) < 80.0:
                return {
                    "id": "coverage-low-%s" % str(payload.get("call_id") or tool_name),
                    "priority": 2,
                    "severity": "medium",
                    "title": "Coverage below expected floor",
                    "body": "最近一次覆盖率结果显示 line coverage 为 %.2f%%，低于 80%% 经验阈值。" % float(line_coverage),
                    "evidence": [{"type": "coverage", "tool_name": tool_name, "line_coverage": float(line_coverage)}],
                }
        if tool_name == "report_quality" and not success:
            reasons = data.get("reasons") if isinstance(data.get("reasons"), list) else []
            body = "；".join([str(item) for item in reasons if str(item or "").strip()]) or "质量门未通过。"
            return {
                "id": "quality-gate-failed-%s" % str(payload.get("call_id") or tool_name),
                "priority": 1,
                "severity": "high",
                "title": "Quality gate failed",
                "body": body,
                "evidence": [{"type": "quality_gate", "tool_name": tool_name, "reasons": reasons}],
            }
        return None

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
        residual = review.get("residual_risks") if isinstance(review.get("residual_risks"), list) else []
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
        payload = {
            "command_name": result.command_name,
            "success": result.success,
            "message": result.message,
            "data": result.data,
        }
        self._emit_with_snapshot(event_handler, "command_result", state, payload)

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
        with state.lock:
            if state.pending_permission is None or state.pending_permission.permission_id != permission_id:
                raise ValueError("未找到待批准的权限请求。")
            if state.pending_event is not None:
                state.pending_result = True
                state.pending_event.set()
                return self.get_session_snapshot(session_id)
        self._run_turn_v2(state, "", True, None, None, self.event_handler, {"approved": True}, True)
        return self.get_session_snapshot(session_id)

    def reject_permission(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        with state.lock:
            if state.pending_permission is None or state.pending_permission.permission_id != permission_id:
                raise ValueError("未找到待拒绝的权限请求。")
            if state.pending_event is not None:
                state.pending_result = False
                state.pending_event.set()
                return self.get_session_snapshot(session_id)
        self._run_turn_v2(state, "", True, None, None, self.event_handler, {"approved": False}, True)
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
        with state.lock:
            if state.pending_user_input is None or state.pending_user_input.request_id != request_id:
                raise ValueError("未找到待处理的用户问题。")
            if state.pending_user_event is not None:
                state.pending_user_response = UserInputResponse(
                    answer=str(answer or ""),
                    selected_index=selected_index,
                    selected_mode=str(selected_mode or ""),
                    selected_option_text=str(selected_option_text or ""),
                )
                state.pending_user_event.set()
                snapshot = self.get_session_snapshot(session_id)
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
            if state.pending_permission is not None and state.pending_permission.permission_id == interaction_id:
                pass
            elif state.pending_user_input is not None and state.pending_user_input.request_id == interaction_id:
                pass
            else:
                raise ValueError("未找到待处理的交互请求。")
        if state.pending_permission is not None and state.pending_permission.permission_id == interaction_id:
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
            state.session.add_system_message(
                build_system_prompt(current_mode, getattr(self.tools, "app_config", None), self.tools.workspace)
            )
            state.current_mode = current_mode
        self._persist_state(state)
        snapshot = self.get_session_snapshot(session_id)
        self._emit(self.event_handler, "mode_changed", session_id, {"mode": current_mode, "session_snapshot": snapshot})
        self._notify_status(None, state)
        return snapshot

    def cancel_session(self, session_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        with state.lock:
            state.stop_event.set()
            has_active_thread = bool(state.active_thread is not None and state.active_thread.is_alive())
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
    ) -> None:
        return self._run_turn_v2(
            state=state,
            text=text,
            stream=stream,
            permission_resolver=permission_resolver,
            user_input_resolver=user_input_resolver,
            event_handler=event_handler,
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
    ) -> None:
        session_id = state.session.session_id
        turn_id = "t-" + uuid.uuid4().hex[:12]
        with state.lock:
            state.status = "running"
            state.last_error = None
            state.updated_at = _utc_now()
            state.pending_permission = None
            state.pending_user_input = None
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
            transcript_store=self.transcript_store,
            session_lock=state.lock,
        )
        current_step = {"step_id": "", "step_index": 0}
        thinking_state = {"active": False}

        def set_thinking(active: bool, reason: str) -> None:
            if thinking_state["active"] == active:
                return
            thinking_state["active"] = active
            self._emit_with_snapshot(event_handler, "thinking_state", state, {"active": active, "reason": reason})

        def on_text_delta(delta: str) -> None:
            set_thinking(False, "assistant_text")
            self._emit(event_handler, "assistant_delta", session_id, {"text": delta, "turn_id": turn_id, "step_id": current_step["step_id"], "step_index": current_step["step_index"]})

        def on_reasoning_delta(delta: str) -> None:
            self._emit(event_handler, "reasoning_delta", session_id, {"text": delta, "turn_id": turn_id, "step_id": current_step["step_id"], "step_index": current_step["step_index"]})

        def on_step_start(step_index: int) -> None:
            current_step["step_id"] = "s-" + uuid.uuid4().hex[:12]
            current_step["step_index"] = step_index
            set_thinking(True, "step_started")
            self._emit(event_handler, "step_start", session_id, {"turn_id": turn_id, "step_id": current_step["step_id"], "step_index": step_index})

        def on_step_finish(step_index: int, reply: AssistantReply, status: str) -> None:
            set_thinking(False, "step_finished")
            self._emit(event_handler, "step_end", session_id, {"turn_id": turn_id, "step_id": current_step["step_id"], "step_index": step_index, "assistant_text": reply.content or "", "finish_reason": reply.finish_reason or "", "status": status})

        def on_tool_start(action: Action) -> None:
            set_thinking(False, "tool_start")
            payload = {"tool_name": action.name, "arguments": action.arguments, "call_id": action.call_id, "turn_id": turn_id, "step_id": current_step["step_id"], "step_index": current_step["step_index"]}
            payload.update(self._tool_event_metadata(action.name))
            self._emit(event_handler, "tool_started", session_id, payload)

        def on_tool_finish(action: Action, observation: Observation) -> None:
            payload = {"tool_name": action.name, "success": observation.success, "error": observation.error, "data": observation.data, "call_id": action.call_id, "turn_id": turn_id, "step_id": current_step["step_id"], "step_index": current_step["step_index"]}
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
                        "recent_turns": getattr(getattr(result, "stats", None), "recent_turns", None),
                        "summarized_turns": getattr(getattr(result, "stats", None), "summarized_turns", None),
                        "approx_tokens_after": getattr(getattr(result, "budget", None), "input_tokens", None),
                        "pipeline_steps": pipeline_steps,
                    },
                )
            if not bool(getattr(result, "compacted", False)):
                return
            self._emit_with_snapshot(event_handler, "context_compacted", state, {"recent_turns": getattr(getattr(result, "stats", None), "recent_turns", None), "summarized_turns": getattr(getattr(result, "stats", None), "summarized_turns", None), "approx_tokens_after": getattr(getattr(result, "budget", None), "input_tokens", None), "analysis": getattr(result, "analysis", {})})

        def permission_handler(request: PermissionRequest) -> Optional[bool]:
            ticket = self._create_permission_ticket(state, request)
            self._emit_with_snapshot(event_handler, "permission_required", state, {"permission": ticket.to_dict(), "turn_id": turn_id, "step_id": current_step["step_id"], "step_index": current_step["step_index"]})
            self._notify_status(event_handler, state)
            if permission_resolver is not None:
                approved = bool(permission_resolver(ticket.to_dict()))
                self._clear_pending_permission(state)
                return approved
            with state.lock:
                state.status = "waiting_permission"
            return None

        def user_input_handler(request: UserInputRequest) -> Optional[UserInputResponse]:
            ticket = self._create_user_input_ticket(state, request)
            self._emit_with_snapshot(event_handler, "user_input_required", state, {"user_input": ticket.to_dict(), "turn_id": turn_id, "step_id": current_step["step_id"], "step_index": current_step["step_index"]})
            self._notify_status(event_handler, state)
            if user_input_resolver is not None:
                payload = user_input_resolver(ticket.to_dict()) or {}
                self._clear_pending_user_input(state)
                return UserInputResponse(answer=str(payload.get("answer") or ""), selected_index=payload.get("selected_index"), selected_mode=str(payload.get("selected_mode") or ""), selected_option_text=str(payload.get("selected_option_text") or ""))
            with state.lock:
                state.status = "waiting_user_input"
            return None

        try:
            self._emit(event_handler, "turn_start", session_id, {"turn_id": turn_id, "user_text": text})
            set_thinking(True, "turn_started")
            if resume_pending:
                result = engine.resume_pending(
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
                result = engine.submit_turn(
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
        except Exception as exc:
            set_thinking(False, "session_error")
            with state.lock:
                is_worker_thread = threading.current_thread() is state.active_thread
                state.status = "error"
                state.last_error = str(exc)
                state.active_thread = None
                state.updated_at = _utc_now()
            self._emit_with_snapshot(event_handler, "session_error", state, {"error": str(exc), "phase": "loop"})
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
            state.status = "idle"
            state.active_thread = None
            state.updated_at = _utc_now()
        self._emit(event_handler, "turn_end", session_id, {"turn_id": turn_id, "final_text": result.final_text, "termination_reason": result.transition.reason, "turns_used": result.turns_used, "max_turns": self.max_turns, "error": result.transition.message or ""})
        self._persist_state(state)
        set_thinking(False, "session_finished")
        snapshot = self.get_session_snapshot(session_id)
        self._emit(event_handler, "session_finished", session_id, {"final_text": result.final_text, "session_snapshot": snapshot, "termination_reason": result.transition.reason, "turns_used": result.turns_used, "max_turns": self.max_turns, "error": result.transition.message or ""})
        self._notify_status(event_handler, state)
        return

    def _persist_state(self, state: ManagedSession) -> None:
        try:
            summary_ref = self.summary_store.persist(state.session, state.current_mode)
        except Exception:
            summary_ref = ""
        else:
            try:
                self.project_memory_store.refresh(state.session, state.current_mode, summary_ref)
            except Exception:
                pass
        with state.lock:
            state.summary_ref = summary_ref or state.summary_ref
            state.updated_at = _utc_now()

    def _create_permission_ticket(self, state: ManagedSession, request: PermissionRequest) -> PermissionTicket:
        ticket = PermissionTicket(
            permission_id="perm_%s" % uuid.uuid4().hex[:8],
            session_id=state.session.session_id,
            tool_name=request.tool_name,
            category=request.category,
            reason=request.reason,
            details=request.details,
        )
        with state.lock:
            state.pending_permission = ticket
            state.pending_result = None
            state.updated_at = _utc_now()
        return ticket

    def _create_user_input_ticket(self, state: ManagedSession, request: UserInputRequest) -> UserInputTicket:
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
        for turn in reversed(session.turns):
            if turn.assistant_message:
                return str(turn.assistant_message)
        return ""

    def _read_summary_for_state(self, state: ManagedSession) -> Optional[Dict[str, Any]]:
        if state.summary_ref or state.session.turns:
            try:
                summary = self.summary_store.load_summary(state.session.session_id)
            except ValueError:
                summary = None
            if summary is not None:
                return summary
        return state.resume_summary

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
        try:
            self.timeline_store.append_event(session_id, event_name, payload)
        except Exception:
            pass
        handler = event_handler or self.event_handler
        if handler is None:
            return
        handler(event_name, session_id, payload)

    def _emit_with_snapshot(
        self,
        event_handler: Optional[EventHandler],
        event_name: str,
        state: ManagedSession,
        payload: Dict[str, Any],
    ) -> None:
        data = dict(payload)
        data["session_snapshot"] = self.get_session_snapshot(state.session.session_id)
        self._emit(event_handler, event_name, state.session.session_id, data)

    def _notify_status(
        self,
        event_handler: Optional[EventHandler],
        state: ManagedSession,
    ) -> None:
        handler = event_handler or self.event_handler
        if handler is None:
            return
        handler(
            "session_status",
            state.session.session_id,
            {"session_snapshot": self.get_session_snapshot(state.session.session_id)},
        )

    def _resolve_workspace_candidate(self, path: str, allow_missing: bool) -> str:
        raw = (path or "").strip()
        if not raw:
            raise ValueError("路径不能为空。")
        candidate = raw if os.path.isabs(raw) else os.path.join(self.tools.workspace, raw)
        resolved = os.path.realpath(candidate)
        workspace_norm = os.path.normcase(self.tools.workspace)
        resolved_norm = os.path.normcase(resolved)
        if not (
            resolved_norm == workspace_norm
            or resolved_norm.startswith(workspace_norm + os.sep)
        ):
            raise ValueError("路径超出当前工作区。")
        if not allow_missing and not os.path.exists(resolved):
            raise ValueError("路径不存在：%s" % path)
        return resolved

    def _relative_path(self, path: str) -> str:
        relative = os.path.relpath(path, self.tools.workspace)
        if relative == ".":
            return "."
        return relative.replace(os.sep, "/")

    def _count_workspace_items(self) -> Dict[str, int]:
        file_count = 0
        dir_count = 0
        for current_root, dir_names, file_names in os.walk(self.tools.workspace):
            dir_names[:] = [name for name in dir_names if name not in SKIP_DIR_NAMES]
            dir_count += len(dir_names)
            file_count += len(file_names)
        return {"file_count": file_count, "dir_count": dir_count}

    def _directory_has_visible_children(self, path: str) -> bool:
        try:
            names = os.listdir(path)
        except OSError:
            return False
        for name in names:
            if name in SKIP_DIR_NAMES:
                continue
            return True
        return False

    def _detect_newline(self, path: str) -> str:
        with io.open(path, "rb") as handle:
            sample = handle.read(4096)
        if b"\r\n" in sample:
            return "\r\n"
        if b"\r" in sample:
            return "\r"
        return "\n"






