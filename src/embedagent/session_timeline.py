from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from embedagent.artifacts import ArtifactStore


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class SessionTimelineStore(object):
    def __init__(
        self,
        workspace: str,
        relative_root: str = ".embedagent/memory/sessions",
        max_events: int = 2000,
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.join(self.workspace, *self.relative_root.split("/"))
        self.max_events = max_events
        self.sanitizer = ArtifactStore(self.workspace)

    def append_event(self, session_id: str, event_name: str, payload: Dict[str, Any]) -> None:
        if not session_id or event_name == "assistant_delta":
            return
        path = self._timeline_path(session_id)
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        record = {
            "schema_version": 1,
            "event_id": "evt_%s" % uuid.uuid4().hex[:10],
            "created_at": _utc_now(),
            "event": event_name,
            "payload": self.sanitizer.sanitize_jsonable(dict(payload)),
        }
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        self._trim_if_needed(path)

    def load_events(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        path = self._timeline_path(session_id)
        if not os.path.isfile(path):
            return []
        items = []
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except ValueError:
                    continue
                if isinstance(payload, dict):
                    items.append(payload)
        if limit <= 0:
            return items
        return items[-limit:]

    def latest_assistant_reply(self, session_id: str) -> str:
        for item in reversed(self.load_events(session_id, limit=self.max_events)):
            if item.get("event") != "session_finished":
                continue
            payload = item.get("payload")
            if not isinstance(payload, dict):
                continue
            text = str(payload.get("final_text") or "").strip()
            if text:
                return text
        return ""

    def _timeline_path(self, session_id: str) -> str:
        return os.path.join(self.root, session_id, "timeline.jsonl")

    def _trim_if_needed(self, path: str) -> None:
        if self.max_events <= 0 or not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        if len(lines) <= self.max_events:
            return
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(lines[-self.max_events :])
