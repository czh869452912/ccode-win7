from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TranscriptStore(object):
    def __init__(
        self,
        workspace: str,
        relative_root: str = ".embedagent/memory/sessions",
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.join(self.workspace, *self.relative_root.split("/"))
        self._append_locks = {}  # type: Dict[str, threading.RLock]
        self._append_locks_guard = threading.RLock()
        self._scan_cache = {}  # type: Dict[str, Tuple[List[Dict[str, Any]], int, int]]

    def resolve_session_dir(self, session_id: str) -> str:
        if not session_id:
            raise ValueError("session_id is required")
        return os.path.join(self.root, session_id)

    def resolve_transcript_path(self, reference: str) -> str:
        raw = str(reference or "").strip()
        if not raw:
            raise ValueError("transcript reference is required")
        if raw.endswith(".jsonl"):
            candidate = raw if os.path.isabs(raw) else os.path.join(self.workspace, raw)
            return os.path.realpath(candidate)
        return os.path.join(self.resolve_session_dir(raw), "transcript.jsonl")

    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        event_id: str = "",
        ts: str = "",
    ) -> Dict[str, Any]:
        path = self.resolve_transcript_path(session_id)
        directory = os.path.dirname(path)
        append_lock = self._lock_for_path(path)
        with append_lock:
            if not os.path.isdir(directory):
                os.makedirs(directory)
            self._repair_tail(path)
            seq = self._next_seq(path)
            event = {
                "schema_version": 1,
                "session_id": session_id,
                "event_id": event_id or ("evt-" + uuid.uuid4().hex[:12]),
                "seq": seq,
                "ts": ts or _utc_now(),
                "type": event_type,
                "payload": dict(payload or {}),
            }
            line = json.dumps(event, ensure_ascii=False, sort_keys=True)
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            normalized = os.path.realpath(path)
            cached_events, valid_length, file_size = self._scan_cache.get(normalized, ([], 0, 0))
            updated_events = list(cached_events)
            updated_events.append(event)
            written_size = len((line + "\n").encode("utf-8"))
            self._scan_cache[normalized] = (updated_events, valid_length + written_size, file_size + written_size)
            return event

    def load_events(self, reference: str) -> List[Dict[str, Any]]:
        path = self.resolve_transcript_path(reference)
        if not os.path.isfile(path):
            raise ValueError("transcript not found: %s" % reference)
        events, _ = self._scan_events(path)
        return events

    def transcript_exists(self, reference: str) -> bool:
        try:
            path = self.resolve_transcript_path(reference)
        except ValueError:
            return False
        return os.path.isfile(path)

    def _next_seq(self, path: str) -> int:
        normalized = os.path.realpath(path)
        cached = self._scan_cache.get(normalized)
        if cached is not None:
            events, _, _ = cached
            if not events:
                return 1
            return int(events[-1].get("seq") or 0) + 1
        if not os.path.isfile(path):
            return 1
        try:
            events = self.load_events(path)
        except ValueError:
            return 1
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
        if cached is not None and cached[2] == file_size:
            events, valid_length = list(cached[0]), cached[1]
        else:
            events, valid_length = self._scan_events(path)
        if valid_length >= file_size:
            return
        with open(path, "rb+") as handle:
            handle.truncate(valid_length)
        self._scan_cache[normalized] = (events, valid_length, valid_length)

    def _scan_events(self, path: str) -> Tuple[List[Dict[str, Any]], int]:
        normalized = os.path.realpath(path)
        cached = self._scan_cache.get(normalized)
        try:
            file_size = os.path.getsize(path)
        except OSError:
            file_size = 0
        if cached is not None and cached[2] == file_size:
            return list(cached[0]), cached[1]
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
                    text = line.decode("utf-8")
                    event = json.loads(text)
                except (UnicodeDecodeError, ValueError):
                    break
                if not isinstance(event, dict):
                    break
                try:
                    seq = int(event.get("seq") or 0)
                except (TypeError, ValueError):
                    break
                if seq != last_seq + 1:
                    break
                events.append(event)
                last_seq = seq
                valid_length = next_offset
        self._scan_cache[normalized] = (list(events), valid_length, file_size)
        return events, valid_length
