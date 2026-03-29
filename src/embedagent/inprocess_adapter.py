from __future__ import annotations

import difflib
import io
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from embedagent.context import ContextManager
from embedagent.interaction import UserInputRequest, UserInputResponse
from embedagent.llm import OpenAICompatibleClient
from embedagent.loop import AgentLoop
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.modes import DEFAULT_MODE, build_system_prompt, initialize_modes, require_mode
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import Action, Observation, Session
from embedagent.session_store import SessionSummaryStore
from embedagent.session_timeline import SessionTimelineStore
from embedagent.tools import ToolRuntime
from embedagent.tools._base import SKIP_DIR_NAMES
from embedagent.workspace_profile import build_workspace_profile_message


EventHandler = Callable[[str, str, Dict[str, Any]], None]
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


@dataclass
class ManagedSession:
    session: Session
    current_mode: str
    status: str = "idle"
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
            artifact_store=self.tools.artifact_store,
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
        )
        self.maintenance_interval = maintenance_interval if maintenance_interval > 0 else 1
        self.event_handler = event_handler
        initialize_modes(self.tools.workspace)
        self.workspace_profile_message = build_workspace_profile_message(self.tools.workspace)
        self._sessions = {}  # type: Dict[str, ManagedSession]
        self._lock = threading.RLock()

    def create_session(
        self,
        mode: str = DEFAULT_MODE,
        event_handler: Optional[EventHandler] = None,
    ) -> Dict[str, Any]:
        current_mode = require_mode(mode)["slug"]
        session = Session()
        session.add_system_message(self.workspace_profile_message)
        session.add_system_message(
            build_system_prompt(current_mode, getattr(self.tools, "app_config", None))
        )
        state = ManagedSession(session=session, current_mode=current_mode)
        self._persist_state(state)
        with self._lock:
            self._sessions[session.session_id] = state
        snapshot = self.get_session_snapshot(session.session_id)
        self._emit(event_handler, "session_created", session.session_id, {"session_snapshot": snapshot})
        return snapshot

    def resume_session(
        self,
        reference: str,
        mode: str = "",
        event_handler: Optional[EventHandler] = None,
    ) -> Dict[str, Any]:
        summary = self.summary_store.load_summary(reference)
        current_mode = require_mode(mode or str(summary.get("current_mode") or DEFAULT_MODE))["slug"]
        session = self.summary_store.create_resumed_session(
            summary,
            current_mode,
            config=getattr(self.tools, "app_config", None),
        )
        state = ManagedSession(
            session=session,
            current_mode=current_mode,
            summary_ref=str(summary.get("summary_ref") or ""),
            updated_at=str(summary.get("updated_at") or _utc_now()),
            resume_summary=summary,
            last_assistant_message=str(summary.get("assistant_last_reply") or ""),
        )
        with self._lock:
            self._sessions[session.session_id] = state
        snapshot = self.get_session_snapshot(session.session_id)
        self._emit(
            event_handler,
            "session_resumed",
            session.session_id,
            {"session_snapshot": snapshot, "resume_ref": snapshot.get("summary_ref")},
        )
        return snapshot

    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.summary_store.list_summaries(limit=limit)

    def get_session_snapshot(self, session_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        with state.lock:
            summary = self._read_summary_for_state(state)
            updated_at = str((summary or {}).get("updated_at") or state.updated_at)
            payload = {
                "session_id": state.session.session_id,
                "status": state.status,
                "current_mode": state.current_mode,
                "started_at": str((summary or {}).get("started_at") or state.session.started_at),
                "updated_at": updated_at,
                "last_user_message": str((summary or {}).get("latest_user_message") or ""),
                "last_assistant_message": str((summary or {}).get("assistant_last_reply") or state.last_assistant_message or ""),
                "summary_ref": str((summary or {}).get("summary_ref") or state.summary_ref or ""),
                "has_pending_permission": state.pending_permission is not None,
                "pending_permission": state.pending_permission.to_dict() if state.pending_permission else None,
                "has_pending_user_input": state.pending_user_input is not None,
                "pending_user_input": state.pending_user_input.to_dict() if state.pending_user_input else None,
                "last_error": state.last_error,
            }
            return payload

    def get_workspace_snapshot(self) -> Dict[str, Any]:
        counts = self._count_workspace_items()
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

    def list_artifacts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.tools.artifact_store.list_artifacts(limit=limit)

    def read_artifact(self, reference: str) -> Dict[str, Any]:
        return self.tools.artifact_store.read_artifact(reference)

    def list_todos(self) -> Dict[str, Any]:
        todos_path = os.path.join(self.tools.workspace, ".embedagent", "todos.json")
        if not os.path.isfile(todos_path):
            return {"count": 0, "todos": [], "path": ".embedagent/todos.json"}
        with open(todos_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        todos = data if isinstance(data, list) else []
        return {
            "count": len(todos),
            "todos": todos,
            "path": ".embedagent/todos.json",
        }

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
        payload = {
            "text": text,
            "stream": stream,
        }
        self._emit(event_handler, "turn_started", session_id, payload)
        if wait:
            self._run_turn(
                state,
                text,
                stream,
                permission_resolver,
                user_input_resolver,
                event_handler,
            )
            return self.get_session_snapshot(session_id)
        thread = threading.Thread(
            target=self._run_turn,
            args=(state, text, stream, permission_resolver, user_input_resolver, event_handler),
            name="embedagent-session-%s" % session_id[:8],
        )
        with state.lock:
            if state.active_thread is not None and state.active_thread.is_alive():
                raise RuntimeError("当前会话仍在运行中。")
            state.active_thread = thread
        thread.daemon = True
        thread.start()
        return self.get_session_snapshot(session_id)

    def approve_permission(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        with state.lock:
            if state.pending_permission is None or state.pending_permission.permission_id != permission_id:
                raise ValueError("未找到待批准的权限请求。")
            if state.pending_event is None:
                raise ValueError("当前权限请求不支持异步批准。")
            state.pending_result = True
            state.pending_event.set()
        return self.get_session_snapshot(session_id)

    def reject_permission(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        with state.lock:
            if state.pending_permission is None or state.pending_permission.permission_id != permission_id:
                raise ValueError("未找到待拒绝的权限请求。")
            if state.pending_event is None:
                raise ValueError("当前权限请求不支持异步拒绝。")
            state.pending_result = False
            state.pending_event.set()
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
            if state.pending_user_event is None:
                raise ValueError("当前用户问题不支持异步回答。")
            state.pending_user_response = UserInputResponse(
                answer=str(answer or ""),
                selected_index=selected_index,
                selected_mode=str(selected_mode or ""),
                selected_option_text=str(selected_option_text or ""),
            )
            state.pending_user_event.set()
        return self.get_session_snapshot(session_id)

    def set_session_mode(self, session_id: str, mode: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        current_mode = require_mode(mode)["slug"]
        with state.lock:
            state.session.add_system_message(
                build_system_prompt(current_mode, getattr(self.tools, "app_config", None))
            )
            state.current_mode = current_mode
        self._persist_state(state)
        return self.get_session_snapshot(session_id)

    def cancel_session(self, session_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        with state.lock:
            if state.pending_permission is not None and state.pending_event is not None:
                state.pending_result = False
                state.pending_event.set()
            if state.pending_user_input is not None and state.pending_user_event is not None:
                state.pending_user_response = UserInputResponse(answer="")
                state.pending_user_event.set()
            state.status = "idle"
        return self.get_session_snapshot(session_id)

    def _run_turn(
        self,
        state: ManagedSession,
        text: str,
        stream: bool,
        permission_resolver: Optional[PermissionResolver],
        user_input_resolver: Optional[UserInputResolver],
        event_handler: Optional[EventHandler],
    ) -> None:
        session_id = state.session.session_id
        with state.lock:
            state.status = "running"
            state.last_error = None
            state.pending_permission = None
            state.pending_event = None
            state.pending_result = None
            state.pending_user_input = None
            state.pending_user_event = None
            state.pending_user_response = None
        loop = AgentLoop(
            client=self.client,
            tools=self.tools,
            max_turns=self.max_turns,
            permission_policy=self.permission_policy,
            context_manager=self.context_manager,
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
            memory_maintenance=self.memory_maintenance,
            maintenance_interval=self.maintenance_interval,
        )

        def on_text_delta(delta: str) -> None:
            self._emit(event_handler, "assistant_delta", session_id, {"text": delta})

        def on_tool_start(action: Action) -> None:
            self._emit(
                event_handler,
                "tool_started",
                session_id,
                {"tool_name": action.name, "arguments": action.arguments},
            )

        def on_tool_finish(action: Action, observation: Observation) -> None:
            with state.lock:
                if (
                    observation.success
                    and isinstance(observation.data, dict)
                    and action.name == "switch_mode"
                    and observation.data.get("to_mode")
                ):
                    state.current_mode = str(observation.data.get("to_mode") or state.current_mode)
                if (
                    observation.success
                    and isinstance(observation.data, dict)
                    and action.name == "ask_user"
                    and observation.data.get("selected_mode")
                ):
                    state.current_mode = str(observation.data.get("selected_mode") or state.current_mode)
            self._emit(
                event_handler,
                "tool_finished",
                session_id,
                {
                    "tool_name": action.name,
                    "success": observation.success,
                    "error": observation.error,
                    "data": observation.data,
                },
            )

        def on_context_result(result: object) -> None:
            stats = getattr(result, "stats", None)
            budget = getattr(result, "budget", None)
            compacted = bool(getattr(result, "compacted", False))
            if not compacted:
                return
            self._emit(
                event_handler,
                "context_compacted",
                session_id,
                {
                    "recent_turns": getattr(stats, "recent_turns", None),
                    "summarized_turns": getattr(stats, "summarized_turns", None),
                    "project_memory_included": getattr(stats, "project_memory_included", None),
                    "approx_tokens_after": getattr(budget, "input_tokens", None),
                },
            )

        def on_permission_request(request: PermissionRequest) -> bool:
            ticket = self._create_permission_ticket(state, request)
            self._emit(event_handler, "permission_required", session_id, {"permission": ticket.to_dict()})
            if permission_resolver is not None:
                approved = permission_resolver(ticket.to_dict())
                self._clear_pending_permission(state)
                return bool(approved)
            event = threading.Event()
            with state.lock:
                state.status = "waiting_permission"
                state.pending_event = event
            event.wait()
            with state.lock:
                approved = bool(state.pending_result)
                state.status = "running"
            self._clear_pending_permission(state)
            return approved

        def on_user_input_request(request: UserInputRequest) -> Optional[UserInputResponse]:
            ticket = self._create_user_input_ticket(state, request)
            self._emit(event_handler, "user_input_required", session_id, {"user_input": ticket.to_dict()})
            if user_input_resolver is not None:
                payload = user_input_resolver(ticket.to_dict()) or {}
                response = UserInputResponse(
                    answer=str(payload.get("answer") or ""),
                    selected_index=payload.get("selected_index"),
                    selected_mode=str(payload.get("selected_mode") or ""),
                    selected_option_text=str(payload.get("selected_option_text") or ""),
                )
                self._clear_pending_user_input(state)
                return response
            event = threading.Event()
            with state.lock:
                state.status = "waiting_user_input"
                state.pending_user_event = event
            event.wait()
            with state.lock:
                response = state.pending_user_response
                state.status = "running"
            self._clear_pending_user_input(state)
            return response

        try:
            loop_result = loop.run(
                user_text=text,
                stream=stream,
                initial_mode=state.current_mode,
                on_text_delta=on_text_delta,
                on_tool_start=on_tool_start,
                on_tool_finish=on_tool_finish,
                on_context_result=on_context_result,
                permission_handler=on_permission_request,
                user_input_handler=on_user_input_request,
                session=state.session,
                stop_event=state.stop_event,
            )
            final_text = loop_result.final_text
            session = loop_result.session
        except Exception as exc:
            with state.lock:
                state.status = "error"
                state.last_error = str(exc)
                state.pending_permission = None
                state.pending_event = None
                state.pending_result = None
                state.pending_user_input = None
                state.pending_user_event = None
                state.pending_user_response = None
                state.updated_at = _utc_now()
                state.active_thread = None
            self._emit(event_handler, "session_error", session_id, {"error": str(exc), "phase": "loop"})
            if threading.current_thread() is state.active_thread:
                return
            raise
        try:
            summary = self.summary_store.load_summary(state.session.session_id)
        except ValueError:
            summary = None
        with state.lock:
            state.session = session
            state.last_assistant_message = final_text
            state.current_mode = str((summary or {}).get("current_mode") or state.current_mode)
            state.summary_ref = str((summary or {}).get("summary_ref") or state.summary_ref)
            state.updated_at = str((summary or {}).get("updated_at") or _utc_now())
            state.pending_permission = None
            state.pending_event = None
            state.pending_result = None
            state.pending_user_input = None
            state.pending_user_event = None
            state.pending_user_response = None
            state.status = "idle"
            state.active_thread = None
        snapshot = self.get_session_snapshot(session_id)
        self._emit(event_handler, "session_finished", session_id, {"final_text": final_text, "session_snapshot": snapshot})

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

    def _detect_newline(self, path: str) -> str:
        with io.open(path, "rb") as handle:
            sample = handle.read(4096)
        if b"\r\n" in sample:
            return "\r\n"
        if b"\r" in sample:
            return "\r"
        return "\n"






