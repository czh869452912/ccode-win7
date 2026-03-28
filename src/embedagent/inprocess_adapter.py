from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from embedagent.context import ContextManager
from embedagent.llm import OpenAICompatibleClient
from embedagent.loop import AgentLoop
from embedagent.memory_maintenance import MemoryMaintenance
from embedagent.modes import DEFAULT_MODE, build_system_prompt, require_mode
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import Action, Observation, Session
from embedagent.session_store import SessionSummaryStore
from embedagent.tools import ToolRuntime


EventHandler = Callable[[str, str, Dict[str, Any]], None]
PermissionResolver = Callable[[Dict[str, Any]], bool]


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
class ManagedSession:
    session: Session
    current_mode: str
    status: str = "idle"
    summary_ref: str = ""
    updated_at: str = field(default_factory=_utc_now)
    last_error: Optional[str] = None
    pending_permission: Optional[PermissionTicket] = None
    pending_event: Optional[threading.Event] = None
    pending_result: Optional[bool] = None
    active_thread: Optional[threading.Thread] = None
    resume_summary: Optional[Dict[str, Any]] = None
    last_assistant_message: str = ""
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
        maintenance_interval: int = 4,
        event_handler: Optional[EventHandler] = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.permission_policy = permission_policy or PermissionPolicy(auto_approve_all=True)
        self.summary_store = summary_store or SessionSummaryStore(self.tools.workspace)
        self.project_memory_store = project_memory_store or ProjectMemoryStore(self.tools.workspace)
        self.context_manager = context_manager or ContextManager(project_memory=self.project_memory_store)
        self.memory_maintenance = memory_maintenance or MemoryMaintenance(
            artifact_store=self.tools.artifact_store,
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
        )
        self.maintenance_interval = maintenance_interval if maintenance_interval > 0 else 1
        self.event_handler = event_handler
        self._sessions = {}  # type: Dict[str, ManagedSession]
        self._lock = threading.RLock()

    def create_session(
        self,
        mode: str = DEFAULT_MODE,
        event_handler: Optional[EventHandler] = None,
    ) -> Dict[str, Any]:
        current_mode = require_mode(mode)["slug"]
        session = Session()
        session.add_system_message(build_system_prompt(current_mode))
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
        session = self.summary_store.create_resumed_session(summary, current_mode)
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
                "last_error": state.last_error,
            }
            return payload

    def submit_user_message(
        self,
        session_id: str,
        text: str,
        stream: bool = True,
        wait: bool = True,
        permission_resolver: Optional[PermissionResolver] = None,
        event_handler: Optional[EventHandler] = None,
    ) -> Dict[str, Any]:
        state = self._require_session(session_id)
        payload = {
            "text": text,
            "stream": stream,
        }
        self._emit(event_handler, "turn_started", session_id, payload)
        if wait:
            self._run_turn(state, text, stream, permission_resolver, event_handler)
            return self.get_session_snapshot(session_id)
        thread = threading.Thread(
            target=self._run_turn,
            args=(state, text, stream, permission_resolver, event_handler),
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

    def set_session_mode(self, session_id: str, mode: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        current_mode = require_mode(mode)["slug"]
        with state.lock:
            state.session.add_system_message(build_system_prompt(current_mode))
            state.current_mode = current_mode
        self._persist_state(state)
        return self.get_session_snapshot(session_id)

    def cancel_session(self, session_id: str) -> Dict[str, Any]:
        state = self._require_session(session_id)
        with state.lock:
            if state.pending_permission is not None and state.pending_event is not None:
                state.pending_result = False
                state.pending_event.set()
            state.status = "idle"
        return self.get_session_snapshot(session_id)

    def _run_turn(
        self,
        state: ManagedSession,
        text: str,
        stream: bool,
        permission_resolver: Optional[PermissionResolver],
        event_handler: Optional[EventHandler],
    ) -> None:
        session_id = state.session.session_id
        with state.lock:
            state.status = "running"
            state.last_error = None
            state.pending_permission = None
            state.pending_event = None
            state.pending_result = None
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

        try:
            final_text, session = loop.run(
                user_text=text,
                stream=stream,
                initial_mode=state.current_mode,
                on_text_delta=on_text_delta,
                on_tool_start=on_tool_start,
                on_tool_finish=on_tool_finish,
                on_context_result=on_context_result,
                permission_handler=on_permission_request,
                session=state.session,
            )
        except Exception as exc:
            with state.lock:
                state.status = "error"
                state.last_error = str(exc)
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

    def _clear_pending_permission(self, state: ManagedSession) -> None:
        with state.lock:
            state.pending_permission = None
            state.pending_event = None
            state.pending_result = None
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
        handler = event_handler or self.event_handler
        if handler is None:
            return
        handler(event_name, session_id, payload)
