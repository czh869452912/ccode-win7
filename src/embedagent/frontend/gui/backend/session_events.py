from __future__ import annotations

from typing import Any, Dict


_GUI_EVENT_KIND_MAP = {
    "turn_start": "turn.started",
    "turn_end": "transition.recorded",
    "step_start": "step.started",
    "step_end": "step.finished",
    "tool_started": "tool.started",
    "tool_finished": "tool.finished",
    "permission_required": "interaction.created",
    "user_input_required": "interaction.created",
    "session_finished": "session.finished",
    "session_error": "session.error",
}


def build_session_event(session_id: str, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(payload.get("_timeline_event") or {})
    event_payload = dict(payload)
    event_payload.pop("_timeline_event", None)
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
