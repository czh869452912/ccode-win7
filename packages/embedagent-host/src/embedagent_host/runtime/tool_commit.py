from __future__ import annotations

import logging
import threading
import time
from copy import deepcopy
from typing import Any, Dict, Optional

from embedagent_core.session import Observation
from embedagent_core.tool_contracts import PreparedToolObservation

_LOG = logging.getLogger(__name__)


class ToolCommitCoordinator(object):
    def __init__(self, tool_result_store, projection_db) -> None:
        self._tool_result_store = tool_result_store
        self._projection_db = projection_db
        self._lock = threading.Lock()
        self._inline_text_limit = 1600

    def _inline_preview(self, value: str) -> str:
        if len(value) <= self._inline_text_limit:
            return value
        return (
            value[: self._inline_text_limit]
            + "\n...[tool result truncated: persistence unavailable]"
        )

    def _record_storage_warning(
        self,
        data: Dict[str, Any],
        field_name: str,
        value: str,
        exc: Exception,
    ) -> None:
        warnings = data.get("tool_result_storage_warnings")
        if not isinstance(warnings, list):
            warnings = []
        warnings.append(
            {
                "field_name": field_name,
                "error": str(exc),
            }
        )
        data["tool_result_storage_warnings"] = warnings[:8]
        preview = self._inline_preview(value)
        data[field_name + "_preview"] = preview
        data[field_name] = preview

    def _materialize_text(
        self,
        session_id: str,
        action,
        data: Dict[str, Any],
        field_name: str,
    ) -> Optional[Dict[str, str]]:
        value = data.get(field_name)
        if not isinstance(value, str) or len(value) <= self._inline_text_limit:
            return None
        try:
            stored = self._tool_result_store.write_text(
                session_id,
                action.call_id,
                field_name,
                value,
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            _LOG.warning(
                "tool result persistence failed for %s/%s (%s): %s",
                action.name,
                action.call_id,
                field_name,
                exc,
            )
            self._record_storage_warning(data, field_name, value, exc)
            return None
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

    def materialize(
        self,
        session_id: str,
        action,
        raw_observation: Observation,
    ) -> PreparedToolObservation:
        projection_updates = []  # type: List[Dict[str, Any]]
        with self._lock:
            data = (
                deepcopy(raw_observation.data)
                if isinstance(raw_observation.data, dict)
                else raw_observation.data
            )
            observation = Observation(
                raw_observation.tool_name,
                raw_observation.success,
                raw_observation.error,
                data,
            )
            replacements = []  # type: List[Dict[str, str]]
            if isinstance(observation.data, dict):
                for field_name in ("content", "stdout", "stderr", "diff"):
                    item = self._materialize_text(
                        session_id,
                        action,
                        observation.data,
                        field_name,
                    )
                    if item is not None:
                        replacements.append(item)
            finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            for item in replacements:
                preview = observation.data.get(item["field_name"] + "_preview", "")
                projection_updates.append(
                    {
                        "session_id": session_id,
                        "tool_call_id": action.call_id,
                        "message_id": "",
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
        return PreparedToolObservation(
            observation=observation,
            replacements=replacements,
            commit_token={"projection_updates": projection_updates},
        )

    def finalize(self, commit_token: Any) -> None:
        token = commit_token if isinstance(commit_token, dict) else {}
        for payload in list(token.get("projection_updates") or []):
            try:
                self._projection_db.upsert_tool_result_projection(**payload)
            except (OSError, ValueError, TypeError):
                pass
