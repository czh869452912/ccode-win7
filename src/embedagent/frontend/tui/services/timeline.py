from __future__ import annotations

from typing import Any, Dict


class TimelineService(object):
    def __init__(self, adapter) -> None:
        self.adapter = adapter

    def load(self, session_id: str, limit: int = 240) -> Dict[str, Any]:
        method = getattr(self.adapter, "get_session_timeline", None)
        if callable(method) and session_id:
            try:
                return method(session_id, limit=limit)
            except Exception:
                pass
        return {"session_id": session_id, "events": [], "latest_assistant_reply": ""}
