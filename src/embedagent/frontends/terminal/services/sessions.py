from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


class SessionService(object):
    def __init__(self, adapter, workspace: str, session_limit: int = 10) -> None:
        self.adapter = adapter
        self.workspace = workspace
        self.session_limit = session_limit

    def create_session(self, mode: str, event_handler=None) -> Dict[str, Any]:
        return self.adapter.create_session(mode, event_handler=event_handler)

    def resume_session(self, reference: str, mode: str, event_handler=None) -> Dict[str, Any]:
        return self.adapter.resume_session(reference, mode, event_handler=event_handler)

    def list_sessions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.adapter.list_sessions(limit=limit or self.session_limit)

    def set_mode(self, session_id: str, mode: str) -> Dict[str, Any]:
        return self.adapter.set_session_mode(session_id, mode)

    def submit(self, session_id: str, text: str, event_handler=None) -> Dict[str, Any]:
        return self.adapter.submit_user_message(
            session_id,
            text,
            stream=True,
            wait=False,
            permission_resolver=None,
            event_handler=event_handler,
        )

    def approve(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        return self.adapter.approve_permission(session_id, permission_id)

    def reject(self, session_id: str, permission_id: str) -> Dict[str, Any]:
        return self.adapter.reject_permission(session_id, permission_id)

    def load_summary(self, summary_ref: str) -> Optional[Dict[str, Any]]:
        store = getattr(self.adapter, "summary_store", None)
        if store is None or not summary_ref:
            return None
        try:
            return store.load_summary(summary_ref)
        except Exception:
            return None

    def list_todos(self) -> Dict[str, Any]:
        method = getattr(self.adapter, "list_todos", None)
        if callable(method):
            return method()
        todos_path = os.path.join(self.workspace, ".embedagent", "todos.json")
        if not os.path.isfile(todos_path):
            return {"count": 0, "todos": [], "path": ".embedagent/todos.json"}
        try:
            with open(todos_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            payload = []
        todos = payload if isinstance(payload, list) else []
        return {"count": len(todos), "todos": todos, "path": ".embedagent/todos.json"}
