from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
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


def _request_kind_for_category(category: str) -> str:
    value = str(category or "").strip()
    if value == "read":
        return "file-read"
    if value in ("workspace_write", "git_write"):
        return "file-change"
    return "command"


def _option_payload(index: Any, text: Any, mode: Any = "") -> Dict[str, Any]:
    label = str(text or "")
    return {
        "label": label,
        "description": label,
        "value": label,
        "index": index,
        "mode": str(mode or ""),
    }


def _questions_for_request(request: UserInputRequest) -> Dict[str, Any]:
    options = []
    for item in request.options:
        options.append(_option_payload(item.index, item.text, item.mode))
    return {
        "questions": [
            {
                "id": "answer",
                "question": request.question,
                "options": options,
                "multi_select": False,
            }
        ],
        "details": _public_details(request.details),
    }


def _questions_from_request_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    options = []
    for index, item in enumerate(list(payload.get("options") or []), start=1):
        if not isinstance(item, dict):
            continue
        option_index = item.get("index")
        if option_index is None:
            option_index = index
        options.append(
            _option_payload(
                option_index,
                item.get("label") or item.get("text") or item.get("value") or "",
                item.get("mode") or "",
            )
        )
    details = dict(payload.get("details") or {})
    return {
        "questions": [
            {
                "id": "answer",
                "question": str(payload.get("question") or ""),
                "options": options,
                "multi_select": False,
            }
        ],
        "details": _public_details(details),
    }


@dataclass
class HostedPendingInteraction:
    interaction_id: str
    kind: str
    session_id: str
    tool_name: str
    payload: Dict[str, Any]
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "interaction_id": self.interaction_id,
            "kind": self.kind,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "turn_id": self.turn_id,
            "step_id": self.step_id,
            "step_index": self.step_index,
            "created_at": self.created_at,
        }
        result.update(dict(self.payload or {}))
        return result

    @property
    def permission_id(self) -> str:
        return self.interaction_id

    @property
    def request_id(self) -> str:
        return self.interaction_id

    @property
    def category(self) -> str:
        return str((self.payload or {}).get("category") or "")

    @property
    def reason(self) -> str:
        return str((self.payload or {}).get("reason") or "")

    @property
    def details(self) -> Dict[str, Any]:
        return dict((self.payload or {}).get("details") or {})

    @property
    def question(self) -> str:
        questions = list((self.payload or {}).get("questions") or [])
        first = questions[0] if questions and isinstance(questions[0], dict) else {}
        return str(first.get("question") or "")

    @property
    def options(self) -> Any:
        questions = list((self.payload or {}).get("questions") or [])
        first = questions[0] if questions and isinstance(questions[0], dict) else {}
        return list(first.get("options") or [])


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
    ) -> HostedPendingInteraction:
        permission_id = "perm_%s" % uuid.uuid4().hex[:8]
        request.details[_INTERACTION_ID_DETAIL_KEY] = permission_id
        ticket = HostedPendingInteraction(
            interaction_id=permission_id,
            kind="permission",
            session_id=state.session.session_id,
            tool_name=request.tool_name,
            payload={
                "category": request.category,
                "reason": request.reason,
                "details": _public_details(request.details),
                "request_kind": _request_kind_for_category(request.category),
            },
            turn_id=turn_id,
            step_id=step_id,
            step_index=step_index,
        )
        with state.lock:
            state.pending_interaction = ticket
            state.pending_response = None
            state.updated_at = _utc_now()
        return ticket

    def create_user_input_ticket(
        self,
        state: ManagedSession,
        request: UserInputRequest,
        turn_id: str = "",
        step_id: str = "",
        step_index: int = 0,
    ) -> HostedPendingInteraction:
        request_id = "ask_%s" % uuid.uuid4().hex[:8]
        request.details[_INTERACTION_ID_DETAIL_KEY] = request_id
        ticket = HostedPendingInteraction(
            interaction_id=request_id,
            kind="user_input",
            session_id=state.session.session_id,
            tool_name=request.tool_name,
            payload=_questions_for_request(request),
            turn_id=turn_id,
            step_id=step_id,
            step_index=step_index,
        )
        with state.lock:
            state.pending_interaction = ticket
            state.pending_response = None
            state.updated_at = _utc_now()
        return ticket

    def clear_pending_interaction(self, state: ManagedSession) -> None:
        with state.lock:
            state.pending_interaction = None
            state.pending_event = None
            state.pending_response = None
            if state.status != "error":
                state.status = "running"
            state.updated_at = _utc_now()

    def rebuild_pending_ticket_from_core(self, state: ManagedSession, pending: Any) -> bool:
        interaction_id = str(getattr(pending, "interaction_id", "") or "").strip()
        kind = str(getattr(pending, "kind", "") or "").strip()
        if not interaction_id:
            return False
        request_payload = dict(getattr(pending, "request_payload", {}) or {})
        if kind == "permission":
            permission_payload = dict(request_payload.get("permission") or {})
            payload = {
                "category": str(permission_payload.get("category") or ""),
                "reason": str(permission_payload.get("reason") or ""),
                "details": _public_details(dict(permission_payload.get("details") or {})),
                "request_kind": _request_kind_for_category(
                    str(permission_payload.get("category") or "")
                ),
            }
        elif kind == "user_input":
            payload = _questions_from_request_payload(dict(request_payload.get("request") or {}))
        else:
            return False
        ticket = HostedPendingInteraction(
            interaction_id=interaction_id,
            kind=kind,
            session_id=state.session.session_id,
            tool_name=str(getattr(pending, "tool_name", "") or ""),
            payload=payload,
            created_at=str(getattr(pending, "created_at", "") or _utc_now()),
        )
        with state.lock:
            state.pending_interaction = ticket
            state.pending_response = None
            state.pending_event = None
            state.updated_at = _utc_now()
        return True

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
            pending = state.pending_interaction
            if pending is None or pending.kind != "user_input" or pending.request_id != request_id:
                raise ValueError("未找到待处理的用户问题。")
            if state.pending_event is not None:
                state.pending_response = {
                    "user_input": UserInputResponse(
                        answer=str(answer or ""),
                        selected_index=selected_index,
                        selected_mode=str(selected_mode or ""),
                        selected_option_text=str(selected_option_text or ""),
                    )
                }
                state.pending_event.set()
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
            pending = state.pending_interaction
            if pending is None or pending.interaction_id != interaction_id:
                raise ValueError("未找到待处理的交互请求。")
            pending_kind = pending.kind
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
            pending = state.pending_interaction
            if (
                pending is None
                or pending.kind != "permission"
                or pending.permission_id != permission_id
            ):
                if approved:
                    raise ValueError("未找到待批准的权限请求。")
                raise ValueError("未找到待拒绝的权限请求。")
            if state.pending_event is not None:
                state.pending_response = {"approved": bool(approved)}
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
