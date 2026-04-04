from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple

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
        self._append_locks = {}  # type: Dict[str, threading.RLock]
        self._append_locks_guard = threading.RLock()

    def append_event(self, session_id: str, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not session_id or event_name == "assistant_delta":
            return {}
        path = self._timeline_path(session_id)
        directory = os.path.dirname(path)
        append_lock = self._lock_for_path(path)
        with append_lock:
            if not os.path.isdir(directory):
                os.makedirs(directory)
            self._repair_tail(path)
            record = {
                "schema_version": 1,
                "event_id": "evt_%s" % uuid.uuid4().hex[:10],
                "seq": self._next_seq(path),
                "created_at": _utc_now(),
                "event": event_name,
                "payload": self.sanitizer.sanitize_jsonable(dict(payload)),
            }
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._trim_if_needed(path)
            return record

    def load_events(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        path = self._timeline_path(session_id)
        if not os.path.isfile(path):
            return []
        items, _ = self._scan_events(path)
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

    def _next_seq(self, path: str) -> int:
        if not os.path.isfile(path):
            return 1
        events, _ = self._scan_events(path)
        if not events:
            return 1
        return int(events[-1].get("seq") or 0) + 1

    def _lock_for_path(self, path: str) -> threading.RLock:
        normalized = os.path.realpath(path)
        with self._append_locks_guard:
            lock = self._append_locks.get(normalized)
            if lock is None:
                lock = threading.RLock()
                self._append_locks[normalized] = lock
            return lock

    def _repair_tail(self, path: str) -> None:
        if not os.path.isfile(path):
            return
        _, valid_length = self._scan_events(path)
        try:
            file_size = os.path.getsize(path)
        except OSError:
            return
        if valid_length >= file_size:
            return
        with open(path, "rb+") as handle:
            handle.truncate(valid_length)

    def _scan_events(self, path: str) -> Tuple[List[Dict[str, Any]], int]:
        events = []
        last_seq = 0
        valid_length = 0
        with open(path, "rb") as handle:
            while True:
                raw_line = handle.readline()
                if not raw_line:
                    break
                next_offset = handle.tell()
                line = raw_line.strip()
                if not line:
                    valid_length = next_offset
                    continue
                try:
                    event = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    break
                if not isinstance(event, dict):
                    break
                if "seq" in event:
                    try:
                        seq = int(event.get("seq") or 0)
                    except (TypeError, ValueError):
                        break
                    if seq <= 0:
                        break
                    if last_seq and seq != last_seq + 1:
                        break
                else:
                    seq = last_seq + 1 if last_seq else 1
                    event = dict(event)
                    event["seq"] = seq
                events.append(event)
                last_seq = seq
                valid_length = next_offset
        return events, valid_length
