from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from embedagent.persistence_sanitize import sanitize_jsonable

_LOGGER = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        self._append_locks = {}  # type: Dict[str, threading.RLock]
        self._append_locks_guard = threading.RLock()
        self._scan_cache = {}  # type: Dict[str, Tuple[List[Dict[str, Any]], int, str, int]]

    def append_event(
        self, session_id: str, event_name: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
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
                "payload": sanitize_jsonable(dict(payload)),
            }
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                handle.write(line)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError as exc:
                    _LOGGER.error("timeline append fsync failed: %s", exc)
                    record["integrity_state"] = "degraded"
                    return record
            normalized = os.path.realpath(path)
            cached_events, valid_length, integrity_state, file_size = self._scan_cache.get(
                normalized, ([], 0, "healthy", 0)
            )
            updated_events = list(cached_events)
            updated_events.append(record)
            written_size = len(line.encode("utf-8"))
            self._scan_cache[normalized] = (
                updated_events,
                valid_length + written_size,
                integrity_state,
                file_size + written_size,
            )
            self._trim_if_needed(path)
            return record

    def load_events(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        path = self._timeline_path(session_id)
        if not os.path.isfile(path):
            return []
        items, _, _ = self._scan_events(path)
        if limit <= 0:
            return items
        return items[-limit:]

    def load_events_with_state(
        self, session_id: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        path = self._timeline_path(session_id)
        if not os.path.isfile(path):
            return [], {
                "first_seq": 0,
                "last_seq": 0,
                "integrity_state": "empty",
                "truncated_before_seq": 0,
            }
        events, _, integrity_state = self._scan_events(path)
        first_seq = int(events[0].get("seq") or 0) if events else 0
        last_seq = int(events[-1].get("seq") or 0) if events else 0
        truncated_before_seq = max(first_seq - 1, 0) if first_seq else 0
        return events, {
            "first_seq": first_seq,
            "last_seq": last_seq,
            "integrity_state": integrity_state,
            "truncated_before_seq": truncated_before_seq,
        }

    def load_events_after(
        self, session_id: str, after_seq: int, limit: int = 200
    ) -> Dict[str, Any]:
        events, state = self.load_events_with_state(session_id)
        first_seq = int(state.get("first_seq") or 0)
        last_seq = int(state.get("last_seq") or 0)
        if state.get("integrity_state") == "degraded":
            return {
                "status": "degraded",
                "events": [],
                "first_seq": first_seq,
                "last_seq": last_seq,
                "reason": "timeline_degraded",
            }
        if first_seq and int(after_seq or 0) < first_seq - 1:
            return {
                "status": "reload_required",
                "events": [],
                "first_seq": first_seq,
                "last_seq": last_seq,
                "reason": "outside_retained_window",
            }
        filtered = [item for item in events if int(item.get("seq") or 0) > int(after_seq or 0)]
        if limit > 0:
            filtered = filtered[:limit]
        return {
            "status": "replay",
            "events": filtered,
            "first_seq": first_seq,
            "last_seq": last_seq,
            "reason": "",
        }

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
        trimmed_lines = lines[-self.max_events :]
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(trimmed_lines)
        self._scan_cache.pop(os.path.realpath(path), None)
        events, valid_length, integrity_state = self._scan_events(path)
        self._scan_cache[os.path.realpath(path)] = (
            events,
            valid_length,
            integrity_state,
            os.path.getsize(path),
        )

    def _next_seq(self, path: str) -> int:
        normalized = os.path.realpath(path)
        cached = self._scan_cache.get(normalized)
        if cached is not None:
            events, _, _, _ = cached
            if not events:
                return 1
            return int(events[-1].get("seq") or 0) + 1
        if not os.path.isfile(path):
            return 1
        events, _, _ = self._scan_events(path)
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
        normalized = os.path.realpath(path)
        cached = self._scan_cache.get(normalized)
        file_size = os.path.getsize(path)
        if cached is not None and cached[3] == file_size:
            events, valid_length, integrity_state = list(cached[0]), cached[1], cached[2]
        else:
            events, valid_length, integrity_state = self._scan_events(path)
        if valid_length >= file_size:
            return
        with open(path, "rb+") as handle:
            handle.truncate(valid_length)
        self._scan_cache[normalized] = (events, valid_length, integrity_state, valid_length)

    def _scan_events(self, path: str) -> Tuple[List[Dict[str, Any]], int, str]:
        normalized = os.path.realpath(path)
        cached = self._scan_cache.get(normalized)
        try:
            file_size = os.path.getsize(path)
        except OSError:
            file_size = 0
        if cached is not None and cached[3] == file_size:
            events, valid_length, integrity_state = cached[0], cached[1], cached[2]
            return list(events), valid_length, integrity_state
        events = []
        last_seq = 0
        valid_length = 0
        integrity_state = "healthy"
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
                    integrity_state = "degraded"
                    valid_length = next_offset
                    continue
                if not isinstance(event, dict):
                    integrity_state = "degraded"
                    valid_length = next_offset
                    continue
                if "seq" in event:
                    try:
                        seq = int(event.get("seq") or 0)
                    except (TypeError, ValueError):
                        integrity_state = "degraded"
                        valid_length = next_offset
                        continue
                    if seq <= 0:
                        integrity_state = "degraded"
                        valid_length = next_offset
                        continue
                    if last_seq and seq != last_seq + 1:
                        integrity_state = "degraded"
                else:
                    seq = last_seq + 1 if last_seq else 1
                    event = dict(event)
                    event["seq"] = seq
                events.append(event)
                last_seq = seq
                valid_length = next_offset
        self._scan_cache[normalized] = (list(events), valid_length, integrity_state, file_size)
        return events, valid_length, integrity_state
