from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


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
        return events, valid_length
