from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from embedagent_core.interaction import UserInputRequest, UserInputResponse
from embedagent_core.permissions import PermissionRequest

from embedagent_host.runtime.session_event_protocol import SessionEventHandler
from embedagent_host.runtime.session_runtime import ManagedSession

UserInputResolver = Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]
_INTERACTION_ID_DETAIL_KEY = "_interaction_id"
_PERMISSION_DECISIONS = set(["accept", "acceptForSession", "decline", "cancel"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _public_details(details: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(details or {})
    payload.pop(_INTERACTION_ID_DETAIL_KEY, None)
    return payload


def _invalid_response() -> ValueError:
    return ValueError("invalid_interaction_response")


def _answer_from_payload(payload: Dict[str, Any]) -> str:
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        raise _invalid_response()
    if "answer" in answers:
        return str(answers.get("answer") or "")
    if answers:
        first_key = sorted(answers.keys())[0]
        return str(answers.get(first_key) or "")
    raise _invalid_response()


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


def _response_for_answer(ticket: "HostedPendingInteraction", answer: str) -> UserInputResponse:
    questions = ticket.payload.get("questions") or []
    options = []
    if questions and isinstance(questions[0], dict):
        options = list(questions[0].get("options") or [])
    for item in options:
        if not isinstance(item, dict):
            continue
        option_values = set(
            str(value or "")
            for value in (item.get("label"), item.get("text"), item.get("value"))
            if str(value or "")
        )
        if answer in option_values:
            return UserInputResponse(
                answer=answer,
                selected_index=item.get("index"),
                selected_mode=str(item.get("mode") or ""),
                selected_option_text=str(item.get("label") or answer),
            )
    return UserInputResponse(answer=answer)


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
    """Hosted GUI/TUI interaction glue around the core resume pipeline.

    Pending-interaction resume runs on a managed worker thread registered as
    ``state.active_thread`` so callers (HTTP handlers, the TUI input loop)
    return immediately; live progress keeps flowing through session events.
    """

    def __init__(
        self,
        require_session: Callable[[str], ManagedSession],
        run_turn: Callable[..., None],
        get_session_snapshot: Callable[[str], Dict[str, Any]],
        notify_status: Callable[[Optional[SessionEventHandler], ManagedSession], None],
        default_event_handler: Callable[[], Optional[SessionEventHandler]],
        emit_event: Optional[
            Callable[[Optional[SessionEventHandler], str, str, Dict[str, Any]], None]
        ] = None,
    ) -> None:
        self._require_session = require_session
        self._run_turn = run_turn
        self._get_session_snapshot = get_session_snapshot
        self._notify_status = notify_status
        self._default_event_handler = default_event_handler
        self._emit_event = emit_event

    def _emit_resolution_event(
        self, state: ManagedSession, ticket: HostedPendingInteraction
    ) -> None:
        if self._emit_event is None:
            return
        with state.lock:
            had_pending_event = state.pending_event is not None
        event_name = "permission_resolved" if ticket.kind == "permission" else "user_input_resolved"
        self._emit_event(
            self._default_event_handler(),
            event_name,
            state.session.session_id,
            {
                "interaction_id": ticket.interaction_id,
                "request_id": ticket.interaction_id,
                "turn_id": ticket.turn_id,
                "status": "accepted",
                "pending_event": had_pending_event,
            },
        )

    def _emit_resume_lifecycle_event(
        self,
        state: ManagedSession,
        ticket: HostedPendingInteraction,
        phase: str,
        lease_wait_ms: int = 0,
        error_kind: str = "",
    ) -> None:
        if self._emit_event is None:
            return
        self._emit_event(
            self._default_event_handler(),
            "interaction_resume_%s" % phase,
            state.session.session_id,
            {
                "interaction_id": ticket.interaction_id,
                "turn_id": ticket.turn_id,
                "kind": ticket.kind,
                "phase": phase,
                "lease_wait_ms": max(int(lease_wait_ms), 0),
                "error_kind": str(error_kind or ""),
            },
        )

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
            state.pending_resolution_claim_id = ""
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
            state.pending_resolution_claim_id = ""
            state.pending_response = None
            state.updated_at = _utc_now()
        return ticket

    def clear_pending_interaction(self, state: ManagedSession) -> None:
        with state.lock:
            state.pending_interaction = None
            state.pending_resolution_claim_id = ""
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
            state.pending_resolution_claim_id = ""
            state.pending_response = None
            state.pending_event = None
            state.updated_at = _utc_now()
        return True

    def _claim_pending_interaction(
        self,
        state: ManagedSession,
        ticket: HostedPendingInteraction,
    ) -> Optional[threading.Event]:
        with state.lock:
            if state.pending_resolution_claim_id:
                raise ValueError("interaction_conflict")
            pending = state.pending_interaction
            if pending is None:
                raise ValueError("interaction_expired")
            if pending.interaction_id != ticket.interaction_id:
                raise ValueError("interaction_conflict")
            state.pending_resolution_claim_id = ticket.interaction_id
            event = state.pending_event
            state.pending_interaction = None
            state.status = "running"
            state.updated_at = _utc_now()
            return event

    def respond_to_interaction(
        self,
        session_id: str,
        interaction_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        state = self._require_session(session_id)
        payload = dict(payload or {})
        with state.lock:
            ticket = state.pending_interaction
            if ticket is None:
                raise ValueError("interaction_expired")
            if ticket.interaction_id != interaction_id:
                raise ValueError("interaction_conflict")
            pending_kind = ticket.kind
        if pending_kind == "permission":
            decision = str(payload.get("decision") or "").strip()
            if decision not in _PERMISSION_DECISIONS:
                raise _invalid_response()
            return self._respond_to_permission_decision(
                state,
                ticket,
                decision,
            )
        if pending_kind == "user_input":
            answer = _answer_from_payload(payload)
            response = _response_for_answer(ticket, answer)
            return self._respond_to_user_input(
                state,
                ticket,
                response,
            )
        raise _invalid_response()

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

    def _wait_for_active_submit_release(self, state: ManagedSession) -> None:
        deadline = time.time() + 5.0
        current = threading.current_thread()
        while time.time() < deadline:
            with state.lock:
                active = state.active_thread
            if active is None or active is current or not active.is_alive():
                return
            active.join(min(0.05, max(0.01, deadline - time.time())))
        raise RuntimeError("interaction submit is still active")

    def _accepted_response(
        self, state: ManagedSession, ticket: HostedPendingInteraction
    ) -> Dict[str, Any]:
        return {
            "session_id": state.session.session_id,
            "interaction_id": ticket.interaction_id,
            "status": "accepted",
            "snapshot": None,
        }

    def _run_resume_coordinator(
        self,
        state: ManagedSession,
        ticket: HostedPendingInteraction,
        interaction_resolution: Dict[str, Any],
    ) -> None:
        wait_started = time.perf_counter()
        try:
            self._wait_for_active_submit_release(state)
            lease_wait_ms = int((time.perf_counter() - wait_started) * 1000)
            with state.lock:
                if state.pending_resolution_claim_id != ticket.interaction_id:
                    return
                active = state.active_thread
                if (
                    active is not None
                    and active is not threading.current_thread()
                    and active.is_alive()
                ):
                    raise RuntimeError("interaction submit is still active")
                state.active_thread = threading.current_thread()
                state.active_thread_is_worker = True
                state.status = "running"
                state.updated_at = _utc_now()
            self._emit_resume_lifecycle_event(
                state,
                ticket,
                "started",
                lease_wait_ms=lease_wait_ms,
            )
            self._run_turn(
                state=state,
                text="",
                stream=True,
                permission_resolver=None,
                user_input_resolver=None,
                event_handler=self._default_event_handler(),
                interaction_resolution=dict(interaction_resolution or {}),
                resume_pending=True,
            )
            self._emit_resume_lifecycle_event(
                state,
                ticket,
                "finished",
                lease_wait_ms=lease_wait_ms,
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            self._emit_resume_lifecycle_event(
                state,
                ticket,
                "failed",
                lease_wait_ms=int((time.perf_counter() - wait_started) * 1000),
                error_kind=type(exc).__name__,
            )
            with state.lock:
                if state.active_thread is threading.current_thread():
                    state.status = "error"
                    state.last_error = str(exc)
                    state.active_thread = None
                    state.active_thread_is_worker = False
                    state.updated_at = _utc_now()
            self._notify_status(None, state)
        finally:
            with state.lock:
                if state.resume_thread is threading.current_thread():
                    state.resume_thread = None

    def _start_resume_worker(
        self,
        state: ManagedSession,
        ticket: HostedPendingInteraction,
        interaction_resolution: Dict[str, Any],
    ) -> threading.Thread:
        worker = threading.Thread(
            target=self._run_resume_coordinator,
            kwargs={
                "state": state,
                "ticket": ticket,
                "interaction_resolution": dict(interaction_resolution or {}),
            },
            name="embedagent-session-resume-%s" % state.session.session_id[:8],
        )
        worker.daemon = True
        with state.lock:
            active = state.active_thread
            state.resume_thread = worker
            if active is None or not active.is_alive():
                state.active_thread = worker
                state.active_thread_is_worker = True
            state.status = "running"
            state.updated_at = _utc_now()
        try:
            worker.start()
        except (OSError, RuntimeError):
            with state.lock:
                if state.resume_thread is worker:
                    state.resume_thread = None
                    if state.active_thread is worker:
                        state.active_thread = None
                        state.active_thread_is_worker = False
                    state.pending_resolution_claim_id = ""
                    state.pending_interaction = ticket
                    state.status = (
                        "waiting_permission"
                        if ticket.kind == "permission"
                        else "waiting_user_input"
                    )
                    state.updated_at = _utc_now()
            raise
        return worker

    def _respond_to_permission_decision(
        self,
        state: ManagedSession,
        ticket: HostedPendingInteraction,
        decision: str,
    ) -> Dict[str, Any]:
        approved = decision in ("accept", "acceptForSession")
        event = self._claim_pending_interaction(state, ticket)
        if decision == "acceptForSession":
            category = str(ticket.payload.get("category") or "").strip()
            if category:
                with state.lock:
                    state.remembered_permission_categories.add(category)
                    state.updated_at = _utc_now()
        command_wait = False
        with state.lock:
            if decision == "cancel":
                state.stop_event.set()
                state.pending_response = {"cancelled": True, "approved": False}
            else:
                state.pending_response = {"approved": bool(approved)}
            if event is not None:
                event.set()
                command_wait = True
        if command_wait:
            self._emit_resolution_event(state, ticket)
            self._notify_status(None, state)
            return self._accepted_response(state, ticket)
        if decision == "cancel":
            with state.lock:
                state.stop_event.set()
            self._start_resume_worker(
                state,
                ticket,
                interaction_resolution={"approved": False, "cancelled": True},
            )
            self._emit_resolution_event(state, ticket)
            self._notify_status(None, state)
            return self._accepted_response(state, ticket)
        self._start_resume_worker(
            state,
            ticket,
            interaction_resolution={"approved": bool(approved)},
        )
        self._emit_resolution_event(state, ticket)
        self._notify_status(None, state)
        return self._accepted_response(state, ticket)

    def _respond_to_user_input(
        self,
        state: ManagedSession,
        ticket: HostedPendingInteraction,
        response: UserInputResponse,
    ) -> Dict[str, Any]:
        event = self._claim_pending_interaction(state, ticket)
        command_wait = False
        with state.lock:
            if event is not None:
                state.pending_response = {"user_input": response}
                event.set()
                command_wait = True
        if command_wait:
            self._emit_resolution_event(state, ticket)
            self._notify_status(None, state)
            return self._accepted_response(state, ticket)
        self._start_resume_worker(
            state,
            ticket,
            interaction_resolution={
                "answer": str(response.answer or ""),
                "selected_index": response.selected_index,
                "selected_mode": str(response.selected_mode or ""),
                "selected_option_text": str(response.selected_option_text or ""),
            },
        )
        self._emit_resolution_event(state, ticket)
        self._notify_status(None, state)
        return self._accepted_response(state, ticket)
