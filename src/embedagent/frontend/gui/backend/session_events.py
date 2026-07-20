from __future__ import annotations

from typing import Any, Dict

_GUI_EVENT_KIND_MAP = {
    "turn_start": "turn.started",
    "turn_end": "transition.recorded",
    "step_start": "step.started",
    "step_end": "step.finished",
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


def build_session_event(
    session_id: str, event_name: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    metadata = dict(payload.get("_session_event") or {})
    event_payload = dict(payload)
    event_payload.pop("_session_event", None)
    event_payload = _interaction_payload(event_name, event_payload)
    return {
        "type": "session_event",
        "data": {
            "session_id": str(session_id or event_payload.get("session_id") or ""),
            "event_id": str(metadata.get("event_id") or ""),
            "seq": int(metadata.get("seq") or 0),
            "created_at": str(metadata.get("created_at") or ""),
            "event_kind": _GUI_EVENT_KIND_MAP.get(event_name, event_name.replace("_", ".")),
            "payload": event_payload,
        },
    }
