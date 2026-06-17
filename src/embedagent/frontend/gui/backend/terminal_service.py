from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

TERMINAL_HISTORY_LIMIT = 128 * 1024
TERMINAL_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
STATUS_STARTING = "starting"
STATUS_RUNNING = "running"
STATUS_EXITED = "exited"
STATUS_ERROR = "error"
STATUS_CLOSED = "closed"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def default_shell_command() -> List[str]:
    if sys.platform == "win32":
        comspec = os.environ.get("COMSPEC", "").strip()
        if comspec and os.path.isfile(comspec):
            return [comspec]
        return ["cmd.exe"]
    shell = os.environ.get("SHELL", "").strip()
    if shell and os.path.isfile(shell):
        return [shell]
    return ["/bin/sh"]


def default_process_factory(command: List[str], cwd: str, env: Dict[str, str]):
    return subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
        shell=False,
    )


class TerminalService(object):
    def __init__(
        self,
        workspace_root: str,
        process_factory: Optional[Callable[[List[str], str, Dict[str, str]], Any]] = None,
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        shell_resolver: Optional[Callable[[], List[str]]] = None,
        max_history_bytes: int = TERMINAL_HISTORY_LIMIT,
        reader_join_timeout: float = 1.0,
    ) -> None:
        self.workspace_root = os.path.realpath(workspace_root)
        self.process_factory = process_factory or default_process_factory
        self.event_sink = event_sink
        self.shell_resolver = shell_resolver or default_shell_command
        self.max_history_bytes = max(1024, int(max_history_bytes or TERMINAL_HISTORY_LIMIT))
        self.reader_join_timeout = max(0.0, float(reader_join_timeout or 0.0))
        self._lock = threading.RLock()
        self._sessions = {}  # type: Dict[str, Dict[str, Dict[str, Any]]]

    def set_event_sink(self, event_sink: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        with self._lock:
            self.event_sink = event_sink

    def list_sessions(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        normalized_session_id = None
        if session_id is not None:
            normalized_session_id = self._normalize_session_id(session_id)
        with self._lock:
            records = []
            for current_session_id, terminals in self._sessions.items():
                if normalized_session_id is not None and current_session_id != normalized_session_id:
                    continue
                for state in terminals.values():
                    records.append(self._summary_locked(state))
            records.sort(key=lambda item: (item["session_id"], item["terminal_id"]))
            return records

    def open_or_attach(
        self,
        session_id: str,
        terminal_id: str,
        cwd: str = "",
        cols: int = 80,
        rows: int = 24,
    ) -> Dict[str, Any]:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_terminal_id = self._normalize_terminal_id(terminal_id)
        with self._lock:
            existing = self._get_state_locked(normalized_session_id, normalized_terminal_id)
            if existing is not None and existing["status"] != STATUS_CLOSED:
                return self._snapshot_locked(existing)
        return self._start(normalized_session_id, normalized_terminal_id, cwd, cols, rows)

    def snapshot(self, session_id: str, terminal_id: str) -> Dict[str, Any]:
        with self._lock:
            state = self._require_state_locked(session_id, terminal_id)
            return self._snapshot_locked(state)

    def write(self, session_id: str, terminal_id: str, data: str) -> Dict[str, Any]:
        text = str(data or "")
        if not text:
            raise ValueError("terminal_write_empty")
        if len(text) > 65536:
            raise ValueError("terminal_write_too_large")
        with self._lock:
            state = self._require_state_locked(session_id, terminal_id)
            if state["status"] not in (STATUS_STARTING, STATUS_RUNNING):
                raise ValueError("terminal_not_running")
            process = state["process"]
            stdin = getattr(process, "stdin", None)
            if stdin is None:
                raise ValueError("terminal_not_running")
            try:
                stdin.write(text)
            except TypeError:
                stdin.write(text.encode("utf-8", "replace"))
            stdin.flush()
            state["updated_at"] = _utc_now()
            return self._snapshot_locked(state)

    def clear(self, session_id: str, terminal_id: str) -> Dict[str, Any]:
        with self._lock:
            state = self._require_state_locked(session_id, terminal_id)
            state["history"] = ""
            state["sequence"] += 1
            state["updated_at"] = _utc_now()
            event = self._event_locked(state, "cleared")
            snapshot = self._snapshot_locked(state)
        self._emit(event)
        return snapshot

    def resize(self, session_id: str, terminal_id: str, cols: int, rows: int) -> Dict[str, Any]:
        with self._lock:
            state = self._require_state_locked(session_id, terminal_id)
            state["cols"] = self._normalize_dimension(cols, 80, 1, 1000)
            state["rows"] = self._normalize_dimension(rows, 24, 1, 500)
            state["sequence"] += 1
            state["updated_at"] = _utc_now()
            event = self._event_locked(state, "resized")
            snapshot = self._snapshot_locked(state)
        self._emit(event)
        return snapshot

    def restart(
        self,
        session_id: str,
        terminal_id: str,
        cwd: str = "",
        cols: int = 80,
        rows: int = 24,
    ) -> Dict[str, Any]:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_terminal_id = self._normalize_terminal_id(terminal_id)
        with self._lock:
            state = self._get_state_locked(normalized_session_id, normalized_terminal_id)
            if state is not None:
                self._terminate_state_locked(state)
                state["history"] = ""
                state["status"] = STATUS_CLOSED
        snapshot = self._start(normalized_session_id, normalized_terminal_id, cwd, cols, rows)
        self._emit(
            {
                "type": "restarted",
                "session_id": normalized_session_id,
                "terminal_id": normalized_terminal_id,
                "sequence": snapshot["sequence"],
                "snapshot": snapshot,
            }
        )
        return snapshot

    def close(self, session_id: str, terminal_id: str = "") -> Dict[str, Any]:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_terminal_id = str(terminal_id or "").strip()
        closed = None
        events = []
        with self._lock:
            terminals = self._sessions.get(normalized_session_id, {})
            target_ids = [normalized_terminal_id] if normalized_terminal_id else list(terminals.keys())
            for target_id in target_ids:
                state = terminals.get(target_id)
                if state is None:
                    if normalized_terminal_id:
                        raise ValueError("terminal_not_found")
                    continue
                self._terminate_state_locked(state)
                state["status"] = STATUS_CLOSED
                state["pid"] = None
                state["sequence"] += 1
                state["updated_at"] = _utc_now()
                closed = self._snapshot_locked(state)
                events.append(self._event_locked(state, "closed"))
                terminals.pop(target_id, None)
            if not terminals:
                self._sessions.pop(normalized_session_id, None)
        for event in events:
            self._emit(event)
        if closed is None:
            return {"session_id": normalized_session_id, "terminal_id": "", "status": STATUS_CLOSED}
        return closed

    def shutdown(self) -> None:
        with self._lock:
            session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            self.close(session_id)

    def wait_for_idle(self, session_id: str, terminal_id: str, timeout: float = 1.0) -> None:
        deadline = time.time() + max(0.0, timeout)
        while time.time() < deadline:
            with self._lock:
                state = self._get_state_locked(session_id, terminal_id)
                threads = list((state or {}).get("reader_threads") or [])
            alive = [thread for thread in threads if thread.is_alive()]
            if not alive:
                return
            for thread in alive:
                thread.join(min(0.05, max(0.0, deadline - time.time())))

    def _start(
        self,
        session_id: str,
        terminal_id: str,
        cwd: str,
        cols: int,
        rows: int,
    ) -> Dict[str, Any]:
        resolved_cwd = self._resolve_cwd(cwd)
        command = list(self.shell_resolver())
        if not command:
            raise ValueError("terminal_shell_unavailable")
        env = os.environ.copy()
        env["EMBEDAGENT_TERMINAL"] = "1"
        now = _utc_now()
        try:
            process = self.process_factory(command, resolved_cwd, env)
        except OSError as exc:
            raise ValueError("terminal_start_failed: %s" % exc)
        with self._lock:
            terminals = self._sessions.setdefault(session_id, {})
            state = {
                "session_id": session_id,
                "terminal_id": terminal_id,
                "label": terminal_id,
                "cwd": resolved_cwd,
                "command": command,
                "process": process,
                "pid": getattr(process, "pid", None),
                "status": STATUS_RUNNING,
                "exit_code": None,
                "history": "",
                "sequence": 0,
                "cols": self._normalize_dimension(cols, 80, 1, 1000),
                "rows": self._normalize_dimension(rows, 24, 1, 500),
                "created_at": now,
                "updated_at": now,
                "reader_threads": [],
            }
            terminals[terminal_id] = state
            started_event = self._event_locked(state, "started")
            snapshot = self._snapshot_locked(state)
        self._start_readers(state)
        self._emit(started_event)
        return snapshot

    def _start_readers(self, state: Dict[str, Any]) -> None:
        process = state["process"]
        readers = [
            ("stdout", getattr(process, "stdout", None)),
            ("stderr", getattr(process, "stderr", None)),
        ]
        threads = []
        for stream_name, pipe in readers:
            if pipe is None:
                continue
            thread = threading.Thread(target=self._read_pipe, args=(state, stream_name, pipe))
            thread.daemon = True
            thread.start()
            threads.append(thread)
        with self._lock:
            state["reader_threads"] = threads

    def _read_pipe(self, state: Dict[str, Any], stream_name: str, pipe: Any) -> None:
        while True:
            try:
                chunk = pipe.readline()
            except (OSError, ValueError):
                break
            if not chunk:
                break
            text = self._decode_chunk(chunk)
            if not text:
                continue
            with self._lock:
                if state["status"] == STATUS_CLOSED:
                    break
                state["history"] = self._trim_history(state["history"] + text)
                state["sequence"] += 1
                state["updated_at"] = _utc_now()
                event = self._event_locked(state, "output", stream=stream_name, chunk=text)
            self._emit(event)
        try:
            pipe.close()
        except (OSError, ValueError, AttributeError):
            pass
        process = state["process"]
        exit_code = process.poll()
        if exit_code is not None:
            with self._lock:
                if state["status"] != STATUS_CLOSED:
                    state["status"] = STATUS_EXITED
                    state["exit_code"] = exit_code
                    state["updated_at"] = _utc_now()
                    state["sequence"] += 1
                    event = self._event_locked(state, "exited")
                else:
                    event = None
            if event is not None:
                self._emit(event)

    def _terminate_state_locked(self, state: Dict[str, Any]) -> None:
        process = state.get("process")
        if process is None:
            return
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1.0)
            except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError):
                try:
                    process.kill()
                    process.wait(timeout=1.0)
                except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError):
                    pass
        state["exit_code"] = process.poll()
        stdin = getattr(process, "stdin", None)
        if stdin is not None:
            try:
                stdin.close()
            except (OSError, ValueError, AttributeError):
                pass

    def _event_locked(
        self,
        state: Dict[str, Any],
        event_type: str,
        stream: str = "",
        chunk: str = "",
    ) -> Dict[str, Any]:
        event = {
            "type": event_type,
            "session_id": state["session_id"],
            "terminal_id": state["terminal_id"],
            "sequence": state["sequence"],
            "status": state["status"],
            "timestamp": state["updated_at"],
        }
        if stream:
            event["stream"] = stream
        if chunk:
            event["chunk"] = chunk
        if event_type in ("started", "cleared", "resized", "closed", "exited"):
            event["snapshot"] = self._snapshot_locked(state)
        return event

    def _snapshot_locked(self, state: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = self._summary_locked(state)
        snapshot.update(
            {
                "history": state["history"],
                "command": list(state["command"]),
            }
        )
        return snapshot

    def _summary_locked(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "session_id": state["session_id"],
            "terminal_id": state["terminal_id"],
            "label": state["label"],
            "cwd": state["cwd"],
            "pid": state["pid"],
            "status": state["status"],
            "exit_code": state["exit_code"],
            "sequence": state["sequence"],
            "cols": state["cols"],
            "rows": state["rows"],
            "created_at": state["created_at"],
            "updated_at": state["updated_at"],
            "capabilities": self._capabilities(),
        }

    def _capabilities(self) -> Dict[str, Any]:
        return {
            "pty": False,
            "resize": False,
            "history_persistent": False,
            "max_buffer_bytes": self.max_history_bytes,
        }

    def _emit(self, event: Optional[Dict[str, Any]]) -> None:
        if event is None:
            return
        with self._lock:
            sink = self.event_sink
        if sink is not None:
            sink(event)

    def _require_state_locked(self, session_id: str, terminal_id: str) -> Dict[str, Any]:
        state = self._get_state_locked(session_id, terminal_id)
        if state is None:
            raise ValueError("terminal_not_found")
        return state

    def _get_state_locked(self, session_id: str, terminal_id: str) -> Optional[Dict[str, Any]]:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_terminal_id = self._normalize_terminal_id(terminal_id)
        return self._sessions.get(normalized_session_id, {}).get(normalized_terminal_id)

    def _normalize_session_id(self, session_id: str) -> str:
        value = str(session_id or "").strip()
        if not value:
            raise ValueError("invalid_session_id")
        return value

    def _normalize_terminal_id(self, terminal_id: str) -> str:
        value = str(terminal_id or "").strip()
        if not value or TERMINAL_ID_RE.match(value) is None:
            raise ValueError("invalid_terminal_id")
        return value

    def _resolve_cwd(self, cwd: str) -> str:
        if cwd:
            candidate = cwd if os.path.isabs(cwd) else os.path.join(self.workspace_root, cwd)
        else:
            candidate = self.workspace_root
        resolved = os.path.realpath(candidate)
        if not self._is_inside_workspace(resolved):
            raise ValueError("terminal_cwd_outside_workspace")
        if not os.path.isdir(resolved):
            raise ValueError("terminal_cwd_not_found")
        return resolved

    def _is_inside_workspace(self, path: str) -> bool:
        workspace = os.path.normcase(os.path.realpath(self.workspace_root))
        candidate = os.path.normcase(os.path.realpath(path))
        if candidate == workspace:
            return True
        return candidate.startswith(workspace + os.sep)

    def _normalize_dimension(self, value: int, default: int, minimum: int, maximum: int) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = default
        if numeric < minimum:
            return minimum
        if numeric > maximum:
            return maximum
        return numeric

    def _trim_history(self, text: str) -> str:
        encoded = text.encode("utf-8", "replace")
        if len(encoded) <= self.max_history_bytes:
            return text
        trimmed = encoded[-self.max_history_bytes :]
        return trimmed.decode("utf-8", "ignore")

    def _decode_chunk(self, chunk: Any) -> str:
        if isinstance(chunk, bytes):
            return chunk.decode("utf-8", "replace")
        return str(chunk)
