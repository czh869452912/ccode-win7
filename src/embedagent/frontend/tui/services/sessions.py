from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from embedagent.harness import task_store


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
        try:
            return self.adapter.submit_user_message(
                session_id,
                text,
                stream=True,
                wait=False,
                permission_resolver=None,
                user_input_resolver=None,
                event_handler=event_handler,
            )
        except TypeError:
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

    def reply_user_input(
        self,
        session_id: str,
        request_id: str,
        answer: str,
        selected_index=None,
        selected_mode: str = "",
        selected_option_text: str = "",
    ) -> Dict[str, Any]:
        return self.adapter.reply_user_input(
            session_id,
            request_id,
            answer,
            selected_index=selected_index,
            selected_mode=selected_mode,
            selected_option_text=selected_option_text,
        )

    def load_summary(self, summary_ref: str) -> Optional[Dict[str, Any]]:
        store = getattr(self.adapter, "summary_store", None)
        if store is None or not summary_ref:
            return None
        try:
            return store.load_summary(summary_ref)
        except (OSError, ValueError, TypeError):
            return None

    def list_tasks(self, session_id: str = "") -> Dict[str, Any]:
        method = getattr(self.adapter, "list_tasks", None)
        if callable(method):
            return method(session_id=session_id)
        tasks_path = task_store.task_snapshot_path(self.workspace, session_id) if session_id else ""
        if not os.path.isfile(tasks_path):
            return {
                "count": 0,
                "tasks": [],
                "path": task_store.relative_task_snapshot_path(session_id) if session_id else "",
                "session_id": session_id,
            }
        try:
            with open(tasks_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError, ValueError):
            payload = []
        if isinstance(payload, dict):
            tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
        else:
            tasks = payload if isinstance(payload, list) else []
        return {
            "count": len(tasks),
            "tasks": tasks,
            "path": task_store.relative_task_snapshot_path(session_id) if session_id else "",
            "session_id": session_id,
        }
