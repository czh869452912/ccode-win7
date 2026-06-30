from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from embedagent.interaction import UserInputRequest, UserInputResponse
from embedagent.permissions import PermissionRequest
from embedagent.session_runtime import ManagedSession

EventHandler = Callable[[str, str, Dict[str, Any]], None]
UserInputResolver = Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]
_INTERACTION_ID_DETAIL_KEY = "_interaction_id"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _public_details(details: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(details or {})
    payload.pop(_INTERACTION_ID_DETAIL_KEY, None)
    return payload


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
    options: Any
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


class HostedInteractionService(object):
    """Hosted GUI/TUI interaction glue around the core resume pipeline."""

    def __init__(
        self,
        require_session: Callable[[str], ManagedSession],
        run_turn: Callable[..., None],
        get_session_snapshot: Callable[[str], Dict[str, Any]],
        notify_status: Callable[[Optional[EventHandler], ManagedSession], None],
        default_event_handler: Callable[[], Optional[EventHandler]],
    ) -> None:
        self._require_session = require_session
        self._run_turn = run_turn
        self._get_session_snapshot = get_session_snapshot
        self._notify_status = notify_status
        self._default_event_handler = default_event_handler

    def create_permission_ticket(
        self,
        state: ManagedSession,
        request: PermissionRequest,
        turn_id: str = "",
        step_id: str = "",
        step_index: int = 0,
    ) -> PermissionTicket:
        permission_id = "perm_%s" % uuid.uuid4().hex[:8]
        request.details[_INTERACTION_ID_DETAIL_KEY] = permission_id
        ticket = PermissionTicket(
            permission_id=permission_id,
            session_id=state.session.session_id,
            tool_name=request.tool_name,
            category=request.category,
            reason=request.reason,
            details=_public_details(request.details),
            turn_id=turn_id,
            step_id=step_id,
            step_index=step_index,
        )
        with state.lock:
            state.pending_permission = ticket
            state.pending_result = None
            state.updated_at = _utc_now()
        return ticket

    def create_user_input_ticket(
        self,
        state: ManagedSession,
        request: UserInputRequest,
        turn_id: str = "",
        step_id: str = "",
        step_index: int = 0,
    ) -> UserInputTicket:
        request_id = "ask_%s" % uuid.uuid4().hex[:8]
        request.details[_INTERACTION_ID_DETAIL_KEY] = request_id
        ticket = UserInputTicket(
            request_id=request_id,
            session_id=state.session.session_id,
            tool_name=request.tool_name,
            question=request.question,
            options=[
                {"index": item.index, "text": item.text, "mode": item.mode}
                for item in request.options
            ],
            details=_public_details(request.details),
            turn_id=turn_id,
            step_id=step_id,
            step_index=step_index,
        )
        with state.lock:
            state.pending_user_input = ticket
            state.pending_user_response = None
            state.updated_at = _utc_now()
        return ticket

    def clear_pending_permission(self, state: ManagedSession) -> None:
        with state.lock:
            state.pending_permission = None
            state.pending_event = None
            state.pending_result = None
            if state.status != "error":
                state.status = "running"
            state.updated_at = _utc_now()

    def clear_pending_user_input(self, state: ManagedSession) -> None:
        with state.lock:
            state.pending_user_input = None
            state.pending_user_event = None
            state.pending_user_response = None
            if state.status != "error":
                state.status = "running"
            state.updated_at = _utc_now()

    def approve_permission(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        return self._resolve_permission(session_id, permission_id, approved=True)

    def reject_permission(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        return self._resolve_permission(session_id, permission_id, approved=False)

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
            snapshot = self.wait_for_command_resolution(session_id)
            self._notify_status(None, state)
            return snapshot
        self._run_turn(
            state=state,
            text="",
            stream=True,
            permission_resolver=None,
            user_input_resolver=None,
            event_handler=self._default_event_handler(),
            interaction_resolution={
                "answer": str(answer or ""),
                "selected_index": selected_index,
                "selected_mode": str(selected_mode or ""),
                "selected_option_text": str(selected_option_text or ""),
            },
            resume_pending=True,
        )
        snapshot = self._get_session_snapshot(session_id)
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
                pending_kind = "permission"
            elif (
                state.pending_user_input is not None
                and state.pending_user_input.request_id == interaction_id
            ):
                pending_kind = "user_input"
            else:
                raise ValueError("未找到待处理的交互请求。")
        if pending_kind == "permission":
            if kind == "approve" and bool((payload or {}).get("remember")):
                category = str((payload or {}).get("category") or "").strip()
                if category:
                    with state.lock:
                        state.remembered_permission_categories.add(category)
                        state.updated_at = _utc_now()
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
            "snapshot": self._get_session_snapshot(session_id),
        }

    def wait_for_command_resolution(
        self, session_id: str, timeout_s: float = 3.0
    ) -> Dict[str, Any]:
        deadline = time.time() + max(timeout_s, 0.1)
        snapshot = self._get_session_snapshot(session_id)
        while time.time() < deadline:
            snapshot = self._get_session_snapshot(session_id)
            if (
                not bool(snapshot.get("pending_interaction_valid"))
                and snapshot.get("status") != "waiting_permission"
                and snapshot.get("status") != "waiting_user_input"
                and snapshot.get("status") != "running"
            ):
                return snapshot
            state = self._require_session(session_id)
            with state.lock:
                active = state.active_thread
            if active is not None and not active.is_alive():
                return self._get_session_snapshot(session_id)
            time.sleep(0.05)
        return snapshot

    def _resolve_permission(
        self, session_id: str, permission_id: str, approved: bool
    ) -> Dict[str, Any]:
        state = self._require_session(session_id)
        command_wait = False
        with state.lock:
            if (
                state.pending_permission is None
                or state.pending_permission.permission_id != permission_id
            ):
                if approved:
                    raise ValueError("未找到待批准的权限请求。")
                raise ValueError("未找到待拒绝的权限请求。")
            if state.pending_event is not None:
                state.pending_result = bool(approved)
                state.pending_event.set()
                command_wait = True
        if command_wait:
            return self.wait_for_command_resolution(session_id)
        self._run_turn(
            state=state,
            text="",
            stream=True,
            permission_resolver=None,
            user_input_resolver=None,
            event_handler=self._default_event_handler(),
            interaction_resolution={"approved": bool(approved)},
            resume_pending=True,
        )
        return self._get_session_snapshot(session_id)
