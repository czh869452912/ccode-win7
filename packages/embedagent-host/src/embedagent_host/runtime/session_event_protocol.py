from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from embedagent_protocol import FailureRecord, SessionEventEnvelope

_EVENT_KIND_MAP = {
    "turn_start": "turn.started",
    "turn_started": "turn.started",
    "turn_end": "transition.recorded",
    "turn_finished": "transition.recorded",
    "step_start": "step.started",
    "step_started": "step.started",
    "step_end": "step.finished",
    "step_finished": "step.finished",
    "tool_started": "tool.started",
    "tool_finished": "tool.finished",
    "permission_required": "approval.requested",
    "permission_resolved": "approval.resolved",
    "permission_response_failed": "approval.response.failed",
    "user_input_required": "user-input.requested",
    "user_input_resolved": "user-input.resolved",
    "user_input_response_failed": "user-input.response.failed",
    "session_finished": "session.finished",
    "session_error": "session.error",
}

_INTERACTION_EVENT_NAMES = {
    "permission_required",
    "permission_resolved",
    "permission_response_failed",
    "user_input_required",
    "user_input_resolved",
    "user_input_response_failed",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _interaction_payload(event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    if event_name not in _INTERACTION_EVENT_NAMES:
        return data
    permission = data.get("permission") if isinstance(data.get("permission"), dict) else {}
    request = data.get("request") if isinstance(data.get("request"), dict) else {}
    user_input = data.get("user_input") if isinstance(data.get("user_input"), dict) else {}
    request_id = (
        data.get("request_id")
        or data.get("permission_id")
        or data.get("interaction_id")
        or permission.get("permission_id")
        or permission.get("request_id")
        or request.get("request_id")
        or request.get("permission_id")
        or user_input.get("request_id")
        or user_input.get("interaction_id")
        or data.get("id")
        or ""
    )
    data["request_id"] = str(request_id)
    data["interaction_id"] = str(data.get("interaction_id") or request_id)
    data["turn_id"] = str(data.get("turn_id") or "")
    for key in ("tool_name", "category", "reason", "details", "question", "questions"):
        for container in (permission, request, user_input):
            if key not in data and key in container:
                data[key] = container.get(key)
    return data


def _failed_tool_payload(event_kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    if event_kind != "tool.finished" or bool(data.get("success")):
        return data
    observation_data = data.get("data") if isinstance(data.get("data"), dict) else {}
    data["failure"] = FailureRecord(
        code=str(observation_data.get("error_kind") or "tool_failed"),
        message=str(data.get("error") or ""),
        retryable=bool(observation_data.get("retryable")),
        source=str(data.get("tool_name") or "tool"),
    ).to_dict()
    return data


class SessionEventEncoder(object):
    def __init__(self) -> None:
        self._locks_guard = threading.Lock()
        self._session_locks = {}  # type: Dict[str, threading.RLock]
        self._sequences = {}  # type: Dict[str, int]

    def session_scope(self, session_id: str) -> threading.RLock:
        resolved_session_id = str(session_id or "")
        with self._locks_guard:
            lock = self._session_locks.get(resolved_session_id)
            if lock is None:
                lock = threading.RLock()
                self._session_locks[resolved_session_id] = lock
        return lock

    def current_sequence(self, session_id: str) -> int:
        resolved_session_id = str(session_id or "")
        with self.session_scope(resolved_session_id):
            return int(self._sequences.get(resolved_session_id, 0) or 0)

    def encode(
        self,
        session_id: str,
        event_name: str,
        payload: Mapping[str, Any],
    ) -> SessionEventEnvelope:
        if not isinstance(payload, Mapping):
            raise TypeError("session event payload must be a mapping")
        data = dict(payload)
        resolved_session_id = str(session_id or data.get("session_id") or "").strip()
        event_name = str(event_name or "").strip()
        event_kind = _EVENT_KIND_MAP.get(event_name, event_name.replace("_", "."))
        data = _interaction_payload(event_name, data)
        data = _failed_tool_payload(event_kind, data)
        with self.session_scope(resolved_session_id):
            sequence = int(self._sequences.get(resolved_session_id, 0) or 0) + 1
            self._sequences[resolved_session_id] = sequence
        return SessionEventEnvelope(
            schema_version=1,
            event_id="evt-" + uuid.uuid4().hex[:12],
            session_id=resolved_session_id,
            sequence=sequence,
            event_kind=event_kind,
            timestamp=_utc_now(),
            payload=data,
        )
