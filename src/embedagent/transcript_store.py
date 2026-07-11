from __future__ import annotations

import json
import os
import stat
import threading
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from embedagent_core.session_log import SessionLeaseConflict, normalize_session_id

_PROCESS_LEASE_GUARD = threading.RLock()
_PROCESS_LEASE_PATHS = set()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _path_is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath(
            (_canonical_path(path), _canonical_path(root))
        ) == _canonical_path(root)
    except ValueError:
        return False


class TranscriptStore(object):
    def __init__(
        self,
        workspace: str,
        relative_root: str = ".embedagent/memory/sessions",
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.realpath(os.path.join(self.workspace, *self.relative_root.split("/")))
        if not _path_is_within(self.root, self.workspace):
            raise ValueError("session root is invalid")
        self._append_locks = {}  # type: Dict[str, threading.RLock]
        self._append_locks_guard = threading.RLock()
        self._scan_cache = {}  # type: Dict[str, Tuple[List[Dict[str, Any]], int, int]]

    @contextmanager
    def acquire_lease(self, session_id: str) -> Any:
        normalized_session_id = normalize_session_id(session_id)
        transcript_path = self.resolve_transcript_path(normalized_session_id)
        lease_key = _canonical_path(transcript_path)
        with _PROCESS_LEASE_GUARD:
            if lease_key in _PROCESS_LEASE_PATHS:
                raise SessionLeaseConflict(
                    "session log lease is already held: %s" % normalized_session_id
                )
            _PROCESS_LEASE_PATHS.add(lease_key)
        file_handle = None
        try:
            file_handle = self._acquire_file_lease(transcript_path, normalized_session_id)
            yield
        finally:
            try:
                if file_handle is not None:
                    self._release_file_lease(file_handle)
            finally:
                with _PROCESS_LEASE_GUARD:
                    _PROCESS_LEASE_PATHS.discard(lease_key)

    def resolve_session_dir(self, session_id: str) -> str:
        normalized_session_id = normalize_session_id(session_id)
        candidate = os.path.realpath(os.path.join(self.root, normalized_session_id))
        if not _path_is_within(candidate, self.root):
            raise ValueError("session_id is invalid")
        return candidate

    def resolve_transcript_path(self, session_id: str) -> str:
        normalized_session_id = normalize_session_id(session_id)
        path = os.path.realpath(
            os.path.join(self.resolve_session_dir(normalized_session_id), "transcript.jsonl")
        )
        if not _path_is_within(path, self.root):
            raise ValueError("session_id is invalid")
        return path

    def resolve_transcript_reference(self, reference: str) -> str:
        if not isinstance(reference, str):
            raise ValueError("transcript reference is invalid")
        raw = reference.strip()
        if not raw:
            raise ValueError("transcript reference is required")
        try:
            return self.resolve_transcript_path(raw)
        except ValueError:
            pass
        candidate = raw if os.path.isabs(raw) else os.path.join(self.workspace, raw)
        path = os.path.realpath(candidate)
        if not _path_is_within(path, self.root):
            raise ValueError("transcript reference is invalid")
        relative_path = os.path.relpath(path, self.root)
        parts = relative_path.split(os.sep)
        if len(parts) != 2 or parts[1].lower() != "transcript.jsonl":
            raise ValueError("transcript reference is invalid")
        try:
            canonical_session_id = normalize_session_id(parts[0])
        except ValueError:
            raise ValueError("transcript reference is invalid")
        if parts[0] != canonical_session_id:
            raise ValueError("transcript reference is invalid")
        return path

    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        event_id: str = "",
        ts: str = "",
        schema_version: int = 2,
    ) -> Dict[str, Any]:
        if schema_version != 2:
            raise ValueError("transcript events must use schema_version 2")
        normalized_session_id = normalize_session_id(session_id)
        stored_payload = deepcopy(payload or {})
        path = self.resolve_transcript_path(normalized_session_id)
        directory = os.path.dirname(path)
        append_lock = self._lock_for_path(path)
        with append_lock:
            if not os.path.isdir(directory):
                os.makedirs(directory)
            self._repair_tail(path)
            seq = self._next_seq(path)
            event = {
                "schema_version": 2,
                "session_id": normalized_session_id,
                "event_id": event_id or ("evt-" + uuid.uuid4().hex[:12]),
                "seq": seq,
                "ts": ts or _utc_now(),
                "type": event_type,
                "parent_message_id": stored_payload.get("parent_message_id", ""),
                "payload": stored_payload,
            }
            line = json.dumps(event, ensure_ascii=False, sort_keys=True)
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            normalized = _canonical_path(path)
            cached_events, valid_length, file_size = self._scan_cache.get(normalized, ([], 0, 0))
            updated_events = list(cached_events)
            updated_events.append(deepcopy(event))
            written_size = len((line + "\n").encode("utf-8"))
            self._scan_cache[normalized] = (
                updated_events,
                valid_length + written_size,
                file_size + written_size,
            )
            return deepcopy(event)

    def load_events(self, session_id: str) -> List[Dict[str, Any]]:
        normalized_session_id = normalize_session_id(session_id)
        path = self.resolve_transcript_path(normalized_session_id)
        if not os.path.isfile(path):
            raise ValueError("transcript not found: %s" % normalized_session_id)
        events, _ = self._scan_events(path)
        return deepcopy(events)

    def load_events_from_reference(self, reference: str) -> List[Dict[str, Any]]:
        path = self.resolve_transcript_reference(reference)
        if not os.path.isfile(path):
            raise ValueError("transcript not found")
        events, _ = self._scan_events(path)
        return deepcopy(events)

    def transcript_exists(self, session_id: str) -> bool:
        try:
            normalized_session_id = normalize_session_id(session_id)
        except ValueError:
            return False
        path = self.resolve_transcript_path(normalized_session_id)
        return os.path.isfile(path)

    def _next_seq(self, path: str) -> int:
        normalized = _canonical_path(path)
        cached = self._scan_cache.get(normalized)
        if cached is not None:
            events, _, _ = cached
            if not events:
                return 1
            return int(events[-1].get("seq") or 0) + 1
        if not os.path.isfile(path):
            return 1
        try:
            events = self.load_events_from_reference(path)
        except ValueError:
            return 1
        if not events:
            return 1
        return int(events[-1].get("seq") or 0) + 1

    def _lock_for_path(self, path: str) -> threading.RLock:
        normalized = _canonical_path(path)
        with self._append_locks_guard:
            lock = self._append_locks.get(normalized)
            if lock is None:
                lock = threading.RLock()
                self._append_locks[normalized] = lock
            return lock

    def _acquire_file_lease(self, transcript_path: str, session_id: str) -> Any:
        lease_path = transcript_path + ".lease"
        self._validate_lease_sidecar(lease_path, require_exists=False)
        if os.name != "nt":
            return None
        import msvcrt

        directory = os.path.dirname(transcript_path)
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        file_descriptor = os.open(
            lease_path,
            os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0),
            0o600,
        )
        handle = os.fdopen(file_descriptor, "r+b", buffering=0)
        try:
            sidecar_stat = self._validate_lease_sidecar(lease_path, require_exists=True)
            handle_stat = os.fstat(handle.fileno())
            if sidecar_stat is None or (
                handle_stat.st_dev,
                handle_stat.st_ino,
            ) != (
                sidecar_stat.st_dev,
                sidecar_stat.st_ino,
            ):
                raise SessionLeaseConflict("session log lease path is unsafe")
            if handle_stat.st_size == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except SessionLeaseConflict:
            handle.close()
            raise
        except OSError:
            handle.close()
            raise SessionLeaseConflict("session log lease is already held: %s" % session_id)
        return handle

    def _validate_lease_sidecar(self, path: str, require_exists: bool) -> Any:
        if not _path_is_within(path, self.root):
            raise SessionLeaseConflict("session log lease path is unsafe")
        try:
            path_stat = os.lstat(path)
        except FileNotFoundError:
            if require_exists:
                raise SessionLeaseConflict("session log lease path is unsafe")
            return None
        except OSError:
            raise SessionLeaseConflict("session log lease path is unsafe")
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        file_attributes = int(getattr(path_stat, "st_file_attributes", 0) or 0)
        if os.path.islink(path) or bool(file_attributes & reparse_flag):
            raise SessionLeaseConflict("session log lease path is unsafe")
        if int(getattr(path_stat, "st_nlink", 1) or 1) != 1:
            raise SessionLeaseConflict("session log lease path is unsafe")
        if not _path_is_within(os.path.realpath(path), self.root):
            raise SessionLeaseConflict("session log lease path is unsafe")
        return path_stat

    def _release_file_lease(self, handle: Any) -> None:
        import msvcrt

        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        finally:
            handle.close()

    def _repair_tail(self, path: str) -> None:
        if not os.path.isfile(path):
            return
        normalized = _canonical_path(path)
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
        self._scan_cache[normalized] = (deepcopy(events), valid_length, valid_length)

    def validate_transcript_chain(self, reference: str) -> Dict[str, Any]:
        """Validate parent chain integrity of a transcript.

        Returns {"valid": bool, "breaks": [{"index": int, "reason": str}]}
        """
        try:
            events = self.load_events(reference)
        except ValueError:
            return {"valid": False, "breaks": [{"index": -1, "reason": "transcript_not_found"}]}

        message_events = [
            e
            for e in events
            if e.get("type")
            in ("user", "assistant", "tool_use", "tool_result", "command_execution", "file_change")
        ]

        seen_ids: set = set()
        breaks = []

        for index, event in enumerate(message_events):
            payload = dict(event.get("payload") or {})
            msg_id = payload.get("message_id", "")
            parent_id = event.get("parent_message_id", "") or payload.get("parent_message_id", "")

            if index == 0 and parent_id:
                breaks.append({"index": index, "reason": "first_message_has_parent"})
            elif index > 0 and not parent_id:
                breaks.append({"index": index, "reason": "missing_parent"})
            elif index > 0 and parent_id and parent_id not in seen_ids:
                breaks.append({"index": index, "reason": "parent_not_found:%s" % parent_id})

            if msg_id:
                seen_ids.add(msg_id)

        return {"valid": len(breaks) == 0, "breaks": breaks}

    def _scan_events(self, path: str) -> Tuple[List[Dict[str, Any]], int]:
        normalized = _canonical_path(path)
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
                if event.get("schema_version") != 2:
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
        self._scan_cache[normalized] = (deepcopy(events), valid_length, file_size)
        return events, valid_length
