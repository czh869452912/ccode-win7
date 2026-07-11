from __future__ import annotations

import hashlib
import json
import os
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
        self._lease_root_identity = _canonical_path(self.root)
        self._append_locks = {}  # type: Dict[str, threading.RLock]
        self._append_locks_guard = threading.RLock()
        self._scan_cache = {}  # type: Dict[str, Tuple[List[Dict[str, Any]], int, int]]

    @contextmanager
    def acquire_lease(self, session_id: str) -> Any:
        normalized_session_id = normalize_session_id(session_id)
        lease_identity = self._lease_identity(normalized_session_id)
        with _PROCESS_LEASE_GUARD:
            if lease_identity in _PROCESS_LEASE_PATHS:
                raise SessionLeaseConflict(
                    "session log lease is already held: %s" % normalized_session_id
                )
            _PROCESS_LEASE_PATHS.add(lease_identity)
        mutex_handle = None
        try:
            mutex_handle = self._acquire_windows_mutex(
                lease_identity,
                normalized_session_id,
            )
            yield
        finally:
            try:
                if mutex_handle is not None:
                    self._release_windows_mutex(mutex_handle)
            finally:
                with _PROCESS_LEASE_GUARD:
                    _PROCESS_LEASE_PATHS.discard(lease_identity)

    def _lease_identity(self, normalized_session_id: str) -> str:
        material = "%s:%s%s" % (
            len(self._lease_root_identity),
            self._lease_root_identity,
            normalized_session_id,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def resolve_session_dir(self, session_id: str) -> str:
        normalized_session_id = normalize_session_id(session_id)
        intended = os.path.abspath(os.path.join(self.root, normalized_session_id))
        candidate = os.path.realpath(intended)
        if os.path.normcase(intended) != os.path.normcase(candidate) or not _path_is_within(
            candidate,
            self.root,
        ):
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

    def _acquire_windows_mutex(self, lease_identity: str, session_id: str) -> Any:
        if os.name != "nt":
            return None
        import ctypes
        from ctypes import wintypes

        wait_object_0 = 0x00000000
        wait_abandoned = 0x00000080
        wait_timeout = 0x00000102
        mutex_name = "Local\\EmbedAgent.SessionLease." + lease_identity
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        create_mutex.restype = wintypes.HANDLE
        wait_for_single_object = kernel32.WaitForSingleObject
        wait_for_single_object.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        wait_for_single_object.restype = wintypes.DWORD
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL

        handle = create_mutex(None, False, mutex_name)
        if not handle:
            raise SessionLeaseConflict("session mutex acquisition failed")
        acquired = False
        try:
            wait_result = wait_for_single_object(handle, 0)
            if wait_result in (wait_object_0, wait_abandoned):
                acquired = True
                return handle
            if wait_result == wait_timeout:
                raise SessionLeaseConflict("session log lease is already held: %s" % session_id)
            raise SessionLeaseConflict("session mutex acquisition failed")
        finally:
            if not acquired:
                close_handle(handle)

    def _release_windows_mutex(self, handle: Any) -> None:
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        release_mutex = kernel32.ReleaseMutex
        release_mutex.argtypes = (wintypes.HANDLE,)
        release_mutex.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL

        release_succeeded = False
        try:
            release_succeeded = bool(release_mutex(handle))
        finally:
            close_succeeded = bool(close_handle(handle))
        if not release_succeeded:
            raise SessionLeaseConflict("session mutex release failed")
        if not close_succeeded:
            raise SessionLeaseConflict("session mutex close failed")

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
