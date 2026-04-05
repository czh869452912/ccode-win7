from __future__ import annotations

import threading
import time
from copy import deepcopy
from typing import Any, Dict, List, Optional

from embedagent.session import Observation, Session


class ToolCommitCoordinator(object):
    def __init__(self, tool_result_store, projection_db, transcript_store) -> None:
        self._tool_result_store = tool_result_store
        self._projection_db = projection_db
        self._transcript_store = transcript_store
        self._lock = threading.Lock()
        self._inline_text_limit = 1600

    def _materialize_text(
        self,
        session: Session,
        action,
        data: Dict[str, Any],
        field_name: str,
    ) -> Optional[Dict[str, str]]:
        value = data.get(field_name)
        if not isinstance(value, str) or len(value) <= self._inline_text_limit:
            return None
        stored = self._tool_result_store.write_text(
            session.session_id,
            action.call_id,
            field_name,
            value,
        )
        data[field_name + "_stored_path"] = stored.relative_path
        data[field_name + "_preview"] = stored.preview_text
        data[field_name] = stored.preview_text
        return {
            "field_name": field_name,
            "stored_path": stored.relative_path,
            "replacement_text": "Tool result replaced: %s %s -> %s"
            % (
                action.name,
                data.get("path") or action.arguments.get("path") or "",
                stored.relative_path,
            ),
        }

    def commit(
        self,
        session: Session,
        action,
        raw_observation: Observation,
        current_mode: str,
        turn_id: str = "",
        step_id: str = "",
        message_id: str = "",
        parent_message_id: str = "",
        finished_at: str = "",
    ) -> Observation:
        del current_mode
        projection_updates = []  # type: List[Dict[str, Any]]
        with self._lock:
            data = (
                deepcopy(raw_observation.data)
                if isinstance(raw_observation.data, dict)
                else raw_observation.data
            )
            committed = Observation(
                raw_observation.tool_name,
                raw_observation.success,
                raw_observation.error,
                data,
            )
            replacements = []  # type: List[Dict[str, str]]
            if isinstance(committed.data, dict):
                for field_name in ("content", "stdout", "stderr", "diff"):
                    item = self._materialize_text(
                        session,
                        action,
                        committed.data,
                        field_name,
                    )
                    if item is not None:
                        replacements.append(item)
            finished_at = finished_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._transcript_store.append_event(
                session.session_id,
                "tool_result",
                {
                    "turn_id": turn_id or (session.turns[-1].turn_id if session.turns else ""),
                    "step_id": step_id or (session.current_step().step_id if session.current_step() is not None else ""),
                    "call_id": action.call_id,
                    "tool_name": action.name,
                    "message_id": message_id,
                    "parent_message_id": parent_message_id,
                    "finished_at": finished_at,
                    "observation": committed.to_dict(),
                },
            )
            if replacements:
                payload = {
                    "message_id": message_id,
                    "tool_call_id": action.call_id,
                    "tool_name": action.name,
                    "replacements": replacements,
                }
                self._transcript_store.append_event(
                    session.session_id,
                    "content_replacement",
                    payload,
                )
                session.record_content_replacement(payload)
                for item in replacements:
                    preview = committed.data.get(item["field_name"] + "_preview", "")
                    projection_updates.append(
                        {
                            "session_id": session.session_id,
                            "tool_call_id": action.call_id,
                            "message_id": message_id,
                            "tool_name": action.name,
                            "field_name": item["field_name"],
                            "stored_path": item["stored_path"],
                            "preview_text": preview,
                            "byte_count": len(preview.encode("utf-8")),
                            "line_count": preview.count("\n") + (1 if preview else 0),
                            "content_kind": "text",
                            "created_at": finished_at,
                        }
                    )
        for payload in projection_updates:
            try:
                self._projection_db.upsert_tool_result_projection(**payload)
            except Exception:
                pass
        return committed
