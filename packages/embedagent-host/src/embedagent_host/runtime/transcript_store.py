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
        if os.name == "nt" and not os.path.isdir(self.workspace):
            raise ValueError("workspace is invalid")
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.realpath(os.path.join(self.workspace, *self.relative_root.split("/")))
        if not _path_is_within(self.root, self.workspace):
            raise ValueError("session root is invalid")
        self._lease_root_identity = _canonical_path(self.root)
        self._append_locks = {}  # type: Dict[str, threading.RLock]
        self._append_locks_guard = threading.RLock()
        self._scan_cache = {}  # type: Dict[str, Tuple[List[Dict[str, Any]], int, Any]]

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
        intended = os.path.abspath(
            os.path.join(self.resolve_session_dir(normalized_session_id), "transcript.jsonl")
        )
        path = os.path.realpath(intended)
        if os.path.normcase(intended) != os.path.normcase(path) or not _path_is_within(
            path,
            self.root,
        ):
            raise ValueError("session_id is invalid")
        try:
            path_stat = os.lstat(path)
        except FileNotFoundError:
            path_stat = None
        except OSError:
            raise ValueError("session_id is invalid")
        if path_stat is not None and int(getattr(path_stat, "st_nlink", 1) or 1) != 1:
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

    def session_id_for_reference(self, reference: str) -> str:
        path = self.resolve_transcript_reference(reference)
        session_dir_name = os.path.basename(os.path.dirname(path))
        return normalize_session_id(session_dir_name)

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
        append_lock = self._lock_for_path(path)
        with append_lock:
            with self._open_transcript(path, create=True) as opened:
                handle, file_identity = opened
                events, valid_length = self._scan_events_handle(
                    path,
                    handle,
                    file_identity,
                )
                file_size = os.fstat(handle.fileno()).st_size
                if valid_length < file_size:
                    handle.truncate(valid_length)
                seq = int(events[-1].get("seq") or 0) + 1 if events else 1
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
                encoded_line = (line + "\n").encode("utf-8")
                handle.seek(0, os.SEEK_END)
                handle.write(encoded_line)
                handle.flush()
                os.fsync(handle.fileno())
                post_write_stat = os.fstat(handle.fileno())
                cache_version = self._cache_version(handle, post_write_stat, file_identity)
                updated_events = list(events)
                updated_events.append(deepcopy(event))
                updated_size = int(post_write_stat.st_size)
                self._scan_cache[_canonical_path(path)] = (
                    updated_events,
                    updated_size,
                    cache_version,
                )
                return deepcopy(event)

    def load_events(self, session_id: str) -> List[Dict[str, Any]]:
        normalized_session_id = normalize_session_id(session_id)
        path = self.resolve_transcript_path(normalized_session_id)
        try:
            with self._open_transcript(path, create=False) as opened:
                handle, file_identity = opened
                events, _ = self._scan_events_handle(path, handle, file_identity)
        except FileNotFoundError:
            raise ValueError("transcript not found: %s" % normalized_session_id)
        return deepcopy(events)

    def load_events_from_reference(self, reference: str) -> List[Dict[str, Any]]:
        path = self.resolve_transcript_reference(reference)
        try:
            with self._open_transcript(path, create=False) as opened:
                handle, file_identity = opened
                events, _ = self._scan_events_handle(path, handle, file_identity)
        except FileNotFoundError:
            raise ValueError("transcript not found")
        return deepcopy(events)

    def transcript_exists(self, session_id: str) -> bool:
        try:
            normalized_session_id = normalize_session_id(session_id)
            path = self.resolve_transcript_path(normalized_session_id)
            with self._open_transcript(path, create=False):
                return True
        except (FileNotFoundError, ValueError):
            return False

    @contextmanager
    def _open_transcript(self, path: str, create: bool) -> Any:
        if os.name == "nt":
            with self._open_windows_transcript(path, create) as opened:
                yield opened
            return

        directory = os.path.dirname(path)
        if create and not os.path.isdir(directory):
            os.makedirs(directory)
        mode = "r+b" if create else "rb"
        try:
            handle = open(path, mode)
        except FileNotFoundError:
            if not create:
                raise
            handle = open(path, "w+b")
        try:
            handle_stat = os.fstat(handle.fileno())
            if int(getattr(handle_stat, "st_nlink", 1) or 1) != 1:
                raise ValueError("session_id is invalid")
            yield handle, (int(handle_stat.st_dev), int(handle_stat.st_ino))
        finally:
            handle.close()

    @contextmanager
    def _open_windows_transcript(self, path: str, create: bool) -> Any:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        class ByHandleFileInformation(ctypes.Structure):
            _fields_ = (
                ("dwFileAttributes", wintypes.DWORD),
                ("ftCreationTime", wintypes.FILETIME),
                ("ftLastAccessTime", wintypes.FILETIME),
                ("ftLastWriteTime", wintypes.FILETIME),
                ("dwVolumeSerialNumber", wintypes.DWORD),
                ("nFileSizeHigh", wintypes.DWORD),
                ("nFileSizeLow", wintypes.DWORD),
                ("nNumberOfLinks", wintypes.DWORD),
                ("nFileIndexHigh", wintypes.DWORD),
                ("nFileIndexLow", wintypes.DWORD),
            )

        generic_read = 0x80000000
        generic_write = 0x40000000
        file_read_attributes = 0x00000080
        file_share_read_write = 0x00000001 | 0x00000002
        open_existing = 3
        open_always = 4
        file_attribute_reparse_point = 0x00000400
        file_flag_backup_semantics = 0x02000000
        file_flag_open_reparse_point = 0x00200000
        invalid_handle_value = ctypes.c_void_p(-1).value

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        create_file.restype = wintypes.HANDLE
        get_file_information = kernel32.GetFileInformationByHandle
        get_file_information.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(ByHandleFileInformation),
        )
        get_file_information.restype = wintypes.BOOL
        get_final_path = kernel32.GetFinalPathNameByHandleW
        get_final_path.argtypes = (
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        )
        get_final_path.restype = wintypes.DWORD
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL

        def open_native(target: str, access: int, disposition: int, flags: int) -> Any:
            native_handle = create_file(
                target,
                access,
                file_share_read_write,
                None,
                disposition,
                flags,
                None,
            )
            if native_handle == invalid_handle_value:
                error_code = ctypes.get_last_error()
                if error_code in (2, 3):
                    raise FileNotFoundError(target)
                raise ValueError("session_id is invalid")
            return native_handle

        def final_handle_path(native_handle: Any) -> str:
            buffer = ctypes.create_unicode_buffer(32768)
            length = get_final_path(native_handle, buffer, len(buffer), 0)
            if not length or length >= len(buffer):
                raise ValueError("session_id is invalid")
            final_path = buffer.value
            if final_path.startswith("\\\\?\\UNC\\"):
                final_path = "\\\\" + final_path[8:]
            elif final_path.startswith("\\\\?\\"):
                final_path = final_path[4:]
            return os.path.normcase(os.path.abspath(final_path))

        def validate_handle(
            native_handle: Any,
            intended_path: str,
            require_single_link: bool,
        ) -> Any:
            information = ByHandleFileInformation()
            if not get_file_information(native_handle, ctypes.byref(information)):
                raise ValueError("session_id is invalid")
            if int(information.dwFileAttributes) & file_attribute_reparse_point:
                raise ValueError("session_id is invalid")
            if require_single_link and int(information.nNumberOfLinks) != 1:
                raise ValueError("session_id is invalid")
            intended_identity = os.path.normcase(os.path.abspath(intended_path))
            if final_handle_path(native_handle) != intended_identity:
                raise ValueError("session_id is invalid")
            return (
                int(information.dwVolumeSerialNumber),
                int(information.nFileIndexHigh),
                int(information.nFileIndexLow),
            )

        workspace_handle = None
        root_component_handles = []
        session_handle = None
        transcript_handle = None
        python_handle = None
        file_descriptor = None
        session_dir = os.path.dirname(path)
        try:
            workspace_handle = open_native(
                self.workspace,
                file_read_attributes,
                open_existing,
                file_flag_backup_semantics | file_flag_open_reparse_point,
            )
            validate_handle(workspace_handle, self.workspace, False)

            current_path = self.workspace
            root_parts = [part for part in self.relative_root.split("/") if part and part != "."]
            if not root_parts or any(part == ".." for part in root_parts):
                raise ValueError("session root is invalid")
            for root_part in root_parts:
                current_path = os.path.abspath(os.path.join(current_path, root_part))
                if create:
                    try:
                        os.mkdir(current_path)
                    except FileExistsError:
                        pass
                component_handle = open_native(
                    current_path,
                    file_read_attributes,
                    open_existing,
                    file_flag_backup_semantics | file_flag_open_reparse_point,
                )
                root_component_handles.append(component_handle)
                validate_handle(component_handle, current_path, False)
            if os.path.normcase(current_path) != os.path.normcase(self.root):
                raise ValueError("session root is invalid")

            if create:
                try:
                    os.mkdir(session_dir)
                except FileExistsError:
                    pass
            session_handle = open_native(
                session_dir,
                file_read_attributes,
                open_existing,
                file_flag_backup_semantics | file_flag_open_reparse_point,
            )
            validate_handle(session_handle, session_dir, False)

            transcript_handle = open_native(
                path,
                generic_read | (generic_write if create else 0),
                open_always if create else open_existing,
                file_flag_open_reparse_point,
            )
            file_identity = validate_handle(transcript_handle, path, True)
            descriptor_flags = os.O_RDWR if create else os.O_RDONLY
            descriptor_flags |= getattr(os, "O_BINARY", 0)
            file_descriptor = msvcrt.open_osfhandle(transcript_handle, descriptor_flags)
            transcript_handle = None
            python_handle = os.fdopen(
                file_descriptor,
                "r+b" if create else "rb",
                buffering=0,
            )
            file_descriptor = None
            yield python_handle, file_identity
        finally:
            if python_handle is not None:
                python_handle.close()
            elif file_descriptor is not None:
                os.close(file_descriptor)
            elif transcript_handle is not None:
                close_handle(transcript_handle)
            if session_handle is not None:
                close_handle(session_handle)
            for component_handle in reversed(root_component_handles):
                close_handle(component_handle)
            if workspace_handle is not None:
                close_handle(workspace_handle)

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

    def _scan_events_handle(
        self,
        path: str,
        handle: Any,
        file_identity: Any,
    ) -> Tuple[List[Dict[str, Any]], int]:
        normalized = _canonical_path(path)
        cached = self._scan_cache.get(normalized)
        handle_stat = os.fstat(handle.fileno())
        cache_version = self._cache_version(handle, handle_stat, file_identity)
        if cache_version is not None and cached is not None and cached[2] == cache_version:
            return list(cached[0]), cached[1]
        events = []
        last_seq = 0
        valid_length = 0
        handle.seek(0)
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
        final_stat = os.fstat(handle.fileno())
        final_version = self._cache_version(handle, final_stat, file_identity)
        self._scan_cache[normalized] = (
            deepcopy(events),
            valid_length,
            final_version,
        )
        return events, valid_length

    def _cache_version(self, handle: Any, handle_stat: Any, file_identity: Any) -> Any:
        if os.name == "nt":
            change_token = self._windows_change_token(handle)
            if change_token is None:
                return None
            return (int(handle_stat.st_size), change_token, file_identity)
        modified_ns = getattr(handle_stat, "st_mtime_ns", None)
        changed_ns = getattr(handle_stat, "st_ctime_ns", None)
        if modified_ns is None or changed_ns is None:
            return None
        return (
            int(handle_stat.st_size),
            int(modified_ns),
            int(changed_ns),
            file_identity,
        )

    @staticmethod
    def _windows_change_token(handle: Any) -> Any:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        class FileBasicInformation(ctypes.Structure):
            _fields_ = (
                ("CreationTime", ctypes.c_longlong),
                ("LastAccessTime", ctypes.c_longlong),
                ("LastWriteTime", ctypes.c_longlong),
                ("ChangeTime", ctypes.c_longlong),
                ("FileAttributes", wintypes.DWORD),
            )

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        try:
            get_volume_information = kernel32.GetVolumeInformationByHandleW
        except AttributeError:
            return None
        get_volume_information.argtypes = (
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            wintypes.DWORD,
        )
        get_volume_information.restype = wintypes.BOOL
        get_file_information = kernel32.GetFileInformationByHandleEx
        get_file_information.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        get_file_information.restype = wintypes.BOOL
        information = FileBasicInformation()
        try:
            native_handle = msvcrt.get_osfhandle(handle.fileno())
            filesystem_name = ctypes.create_unicode_buffer(32)
            volume_name = ctypes.create_unicode_buffer(261)
            serial_number = wintypes.DWORD()
            maximum_component_length = wintypes.DWORD()
            filesystem_flags = wintypes.DWORD()
            volume_succeeded = get_volume_information(
                native_handle,
                volume_name,
                len(volume_name),
                ctypes.byref(serial_number),
                ctypes.byref(maximum_component_length),
                ctypes.byref(filesystem_flags),
                filesystem_name,
                len(filesystem_name),
            )
            if not volume_succeeded or filesystem_name.value.upper() != "NTFS":
                return None
            succeeded = get_file_information(
                native_handle,
                0,
                ctypes.byref(information),
                ctypes.sizeof(information),
            )
        except (AttributeError, OSError, OverflowError, TypeError, ValueError):
            return None
        if not succeeded or not information.LastWriteTime or not information.ChangeTime:
            return None
        return (int(information.LastWriteTime), int(information.ChangeTime))
