from __future__ import annotations

from typing import Any, Dict


class TimelineService(object):
    def __init__(self, adapter) -> None:
        self.adapter = adapter

    def load(self, session_id: str, limit: int = 240) -> Dict[str, Any]:
        del limit
        method = getattr(self.adapter, "get_session_bootstrap", None)
        if callable(method) and session_id:
            try:
                payload = method(session_id)
                history = dict(payload.get("history") or {})
                history.setdefault("session_id", session_id)
                return history
            except (OSError, ValueError, TypeError, KeyError):
                pass
        return {
            "session_id": session_id,
            "items": [],
            "turns": [],
            "current_interaction": None,
            "integrity": {"status": "unavailable"},
        }
