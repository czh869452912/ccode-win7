# GUI Terminal Bottom Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a T3 Code-style thread-scoped terminal bottom drawer to the GUI without weakening Windows 7, offline, Python 3.8, or Agent Core separation constraints.

**Architecture:** The GUI backend owns an in-memory terminal service that uses Python stdlib subprocess pipes and workspace-bound cwd validation. The frontend owns drawer UI state and terminal display reducers, while Agent Core remains uninvolved: terminal output is not transcript truth, not tool execution, not telemetry, and not workflow state.

**Tech Stack:** Python 3.8 stdlib (`subprocess`, `threading`, `os`, `sys`, `time`), existing FastAPI GUI backend, existing GUI WebSocket frontend, React 18 with plain CSS and existing webapp test runner.

---

## File Structure

- Create `src/embedagent/frontend/gui/backend/terminal_service.py`
  - In-memory terminal registry, subprocess/fake-process abstraction, snapshots, summaries, events, cwd validation, shutdown.
- Modify `src/embedagent/frontend/gui/backend/server.py`
  - Instantiate `TerminalService`, expose terminal routes, broadcast `terminal_event`, shut terminals down with app host.
- Modify `src/embedagent/frontend/gui/backend/app_shell.py`
  - Advertise terminal capability and bottom drawer surface limits.
- Create `tests/test_gui_terminal_service.py`
  - Pure backend service tests with fake process factory for deterministic behavior.
- Create `tests/test_gui_terminal_api.py`
  - FastAPI route tests for terminal open/snapshot/write/clear/close and workspace errors.
- Modify `tests/test_gui_app_shell.py`
  - Capability contract includes terminal limitation metadata.
- Create `src/embedagent/frontend/gui/webapp/src/terminal/terminal-labels.js`
  - `getTerminalLabel`, `resolveTerminalSessionLabel`, `nextTerminalId`.
- Create `src/embedagent/frontend/gui/webapp/src/terminal/terminal-state.js`
  - Normalize snapshots/summaries/events and reduce terminal session state.
- Create `src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js`
  - Small fetch wrappers for terminal HTTP routes.
- Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
  - Render terminal surface when `activeKind === "terminal"`, keep existing run output/log behavior.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Wire WebSocket terminal events, terminal drawer open/attach/create/write/clear/restart/close actions.
- Modify `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - Add `drawer.terminal` command.
- Modify `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - Keep `terminal` as an allowed bottom surface and ensure tests lock it.
- Modify `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - Normalize `capabilities.terminal`.
- Create `src/embedagent/frontend/gui/webapp/test/terminal-state.test.mjs`
  - Frontend pure terminal model tests.
- Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Register terminal tests.
- Modify `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - Assert terminal drawer command/surface.
- Modify `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - Assert terminal capabilities normalize.
- Modify `src/embedagent/frontend/gui/webapp/src/styles.css`
  - T3 Code-like terminal tabs, toolbar, buffer, input row, compact states.
- Modify generated static assets under `src/embedagent/frontend/gui/static/` after `npm run build`.
- Update docs at the end:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`

---

### Task 1: Backend Terminal Service

**Files:**
- Create: `src/embedagent/frontend/gui/backend/terminal_service.py`
- Test: `tests/test_gui_terminal_service.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_gui_terminal_service.py`:

```python
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.terminal_service import TerminalService


class FakeStdin(object):
    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, data):
        self.writes.append(data)

    def flush(self):
        return None

    def close(self):
        self.closed = True


class FakePipe(object):
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def readline(self):
        if self._chunks:
            return self._chunks.pop(0)
        return b""

    def close(self):
        return None


class FakeProcess(object):
    def __init__(self, pid=123, stdout=None, stderr=None):
        self.pid = pid
        self.stdin = FakeStdin()
        self.stdout = FakePipe(stdout or [])
        self.stderr = FakePipe(stderr or [])
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -1


class FakeProcessFactory(object):
    def __init__(self, stdout_sequences=None):
        self.calls = []
        self.processes = []
        self.stdout_sequences = list(stdout_sequences or [[b"hello from terminal\n"]])

    def __call__(self, command, cwd, env):
        stdout = self.stdout_sequences.pop(0) if self.stdout_sequences else []
        process = FakeProcess(stdout=stdout)
        self.calls.append((command, cwd, env))
        self.processes.append(process)
        return process


class TerminalServiceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-terminal-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        self.events = []

    def service(self, factory=None):
        return TerminalService(
            workspace_root=self.workspace,
            process_factory=factory or FakeProcessFactory(),
            event_sink=self.events.append,
            shell_resolver=lambda: ["cmd.exe"],
            reader_join_timeout=0.2,
        )

    def test_open_or_attach_captures_output_and_returns_snapshot(self):
        factory = FakeProcessFactory()
        service = self.service(factory)

        snapshot = service.open_or_attach("sess-1", "term-1", cwd="", cols=80, rows=24)
        service.wait_for_idle("sess-1", "term-1", timeout=1.0)

        refreshed = service.snapshot("sess-1", "term-1")
        self.assertEqual(snapshot["session_id"], "sess-1")
        self.assertEqual(snapshot["terminal_id"], "term-1")
        self.assertEqual(snapshot["status"], "running")
        self.assertEqual(refreshed["history"], "hello from terminal\n")
        self.assertEqual(refreshed["capabilities"]["pty"], False)
        self.assertEqual(refreshed["capabilities"]["resize"], False)
        self.assertEqual(factory.calls[0][1], os.path.realpath(self.workspace))
        self.assertTrue(any(event["type"] == "output" for event in self.events))

    def test_client_chosen_terminal_ids_are_validated(self):
        service = self.service()

        with self.assertRaises(ValueError) as raised:
            service.open_or_attach("sess-1", "   ")

        self.assertEqual(str(raised.exception), "invalid_terminal_id")

    def test_cwd_must_stay_inside_workspace(self):
        service = self.service()
        outside = os.path.dirname(os.path.realpath(self.workspace))

        with self.assertRaises(ValueError) as raised:
            service.open_or_attach("sess-1", "term-1", cwd=outside)

        self.assertEqual(str(raised.exception), "terminal_cwd_outside_workspace")

    def test_write_clear_resize_close_and_shutdown(self):
        factory = FakeProcessFactory()
        service = self.service(factory)
        service.open_or_attach("sess-1", "term-1")
        service.write("sess-1", "term-1", "echo hi\n")

        self.assertEqual(factory.processes[0].stdin.writes, ["echo hi\n"])

        cleared = service.clear("sess-1", "term-1")
        self.assertEqual(cleared["history"], "")
        resized = service.resize("sess-1", "term-1", cols=120, rows=40)
        self.assertEqual(resized["cols"], 120)
        self.assertEqual(resized["rows"], 40)
        self.assertEqual(resized["capabilities"]["resize"], False)

        closed = service.close("sess-1", "term-1")
        self.assertEqual(closed["status"], "closed")
        self.assertTrue(factory.processes[0].terminated)

        with self.assertRaises(ValueError) as raised:
            service.write("sess-1", "term-1", "again\n")
        self.assertEqual(str(raised.exception), "terminal_not_found")

    def test_restart_reuses_terminal_id_and_resets_history(self):
        factory = FakeProcessFactory(stdout_sequences=[[b"first\n"], []])
        service = self.service(factory)
        service.open_or_attach("sess-1", "term-1")
        service.wait_for_idle("sess-1", "term-1", timeout=1.0)

        restarted = service.restart("sess-1", "term-1", cwd="", cols=90, rows=30)
        service.wait_for_idle("sess-1", "term-1", timeout=1.0)

        self.assertEqual(restarted["terminal_id"], "term-1")
        self.assertEqual(service.snapshot("sess-1", "term-1")["history"], "")
        self.assertEqual(restarted["cols"], 90)
        self.assertEqual(len(factory.processes), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_gui_terminal_service.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'embedagent.frontend.gui.backend.terminal_service'`.

- [ ] **Step 3: Implement `terminal_service.py`**

Create `src/embedagent/frontend/gui/backend/terminal_service.py`:

```python
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
        with self._lock:
            records = []
            for current_session_id, terminals in self._sessions.items():
                if session_id is not None and current_session_id != self._normalize_session_id(session_id):
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
        return self._start(normalized_session_id, normalized_terminal_id, cwd, cols, rows, reset=True)

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
        event = None
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
        snapshot = self._start(normalized_session_id, normalized_terminal_id, cwd, cols, rows, reset=True)
        self._emit({"type": "restarted", "session_id": normalized_session_id, "terminal_id": normalized_terminal_id, "sequence": snapshot["sequence"], "snapshot": snapshot})
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

    def _start(self, session_id: str, terminal_id: str, cwd: str, cols: int, rows: int, reset: bool) -> Dict[str, Any]:
        resolved_cwd = self._resolve_cwd(cwd)
        command = list(self.shell_resolver())
        if not command:
            raise ValueError("terminal_shell_unavailable")
        env = os.environ.copy()
        now = _utc_now()
        process = self.process_factory(command, resolved_cwd, env)
        state = {
            "session_id": session_id,
            "terminal_id": terminal_id,
            "cwd": resolved_cwd,
            "status": STATUS_RUNNING,
            "pid": getattr(process, "pid", None),
            "process": process,
            "history": "",
            "exit_code": None,
            "label": self._default_label(terminal_id),
            "updated_at": now,
            "sequence": 0,
            "cols": self._normalize_dimension(cols, 80, 1, 1000),
            "rows": self._normalize_dimension(rows, 24, 1, 500),
            "reader_threads": [],
        }
        with self._lock:
            self._sessions.setdefault(session_id, {})[terminal_id] = state
            snapshot = self._snapshot_locked(state)
            started_event = self._event_locked(state, "started", {"snapshot": snapshot})
        self._emit(started_event)
        self._start_reader_threads(state)
        return snapshot

    def _start_reader_threads(self, state: Dict[str, Any]) -> None:
        process = state["process"]
        threads = []
        for pipe_name in ("stdout", "stderr"):
            pipe = getattr(process, pipe_name, None)
            if pipe is None:
                continue
            thread = threading.Thread(
                target=self._read_pipe,
                args=(state["session_id"], state["terminal_id"], pipe),
                name="embedagent-terminal-%s-%s" % (state["terminal_id"], pipe_name),
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)
        with self._lock:
            current = self._get_state_locked(state["session_id"], state["terminal_id"])
            if current is not None:
                current["reader_threads"] = threads

    def _read_pipe(self, session_id: str, terminal_id: str, pipe: Any) -> None:
        while True:
            chunk = pipe.readline()
            if not chunk:
                break
            if isinstance(chunk, bytes):
                text = chunk.decode("utf-8", "replace")
            else:
                text = str(chunk)
            self._append_output(session_id, terminal_id, text)
        with self._lock:
            state = self._get_state_locked(session_id, terminal_id)
            if state is None:
                return
            process = state["process"]
            code = process.poll()
            if code is not None:
                state["status"] = STATUS_EXITED
                state["exit_code"] = int(code)
                state["sequence"] += 1
                state["updated_at"] = _utc_now()
                event = self._event_locked(state, "exited", {"exit_code": state["exit_code"]})
            else:
                event = None
        if event is not None:
            self._emit(event)

    def _append_output(self, session_id: str, terminal_id: str, text: str) -> None:
        with self._lock:
            state = self._get_state_locked(session_id, terminal_id)
            if state is None:
                return
            state["history"] = self._trim_history(state["history"] + text)
            state["sequence"] += 1
            state["updated_at"] = _utc_now()
            event = self._event_locked(state, "output", {"data": text})
        self._emit(event)

    def _trim_history(self, text: str) -> str:
        data = text.encode("utf-8", "replace")
        if len(data) <= self.max_history_bytes:
            return text
        return data[-self.max_history_bytes :].decode("utf-8", "replace")

    def _resolve_cwd(self, cwd: str) -> str:
        value = str(cwd or "").strip()
        if not value:
            candidate = self.workspace_root
        elif os.path.isabs(value):
            candidate = value
        else:
            candidate = os.path.join(self.workspace_root, value)
        real = os.path.realpath(candidate)
        if not self._is_inside_workspace(real):
            raise ValueError("terminal_cwd_outside_workspace")
        if not os.path.exists(real):
            raise ValueError("terminal_cwd_not_found")
        if not os.path.isdir(real):
            raise ValueError("terminal_cwd_not_directory")
        return real

    def _is_inside_workspace(self, path: str) -> bool:
        try:
            common = os.path.commonpath([self.workspace_root, os.path.realpath(path)])
        except ValueError:
            return False
        return os.path.normcase(common) == os.path.normcase(self.workspace_root)

    def _normalize_session_id(self, session_id: str) -> str:
        value = str(session_id or "").strip()
        if not value:
            raise ValueError("invalid_session_id")
        return value

    def _normalize_terminal_id(self, terminal_id: str) -> str:
        value = str(terminal_id or "").strip()
        if not value or not TERMINAL_ID_RE.match(value):
            raise ValueError("invalid_terminal_id")
        return value

    def _normalize_dimension(self, value: int, fallback: int, minimum: int, maximum: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = fallback
        return max(minimum, min(maximum, number))

    def _get_state_locked(self, session_id: str, terminal_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(str(session_id or "").strip(), {}).get(str(terminal_id or "").strip())

    def _require_state_locked(self, session_id: str, terminal_id: str) -> Dict[str, Any]:
        normalized_session_id = self._normalize_session_id(session_id)
        normalized_terminal_id = self._normalize_terminal_id(terminal_id)
        state = self._get_state_locked(normalized_session_id, normalized_terminal_id)
        if state is None:
            raise ValueError("terminal_not_found")
        return state

    def _terminate_state_locked(self, state: Dict[str, Any]) -> None:
        process = state.get("process")
        if process is None:
            return
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        stdin = getattr(process, "stdin", None)
        if stdin is not None:
            try:
                stdin.close()
            except Exception:
                pass

    def _default_label(self, terminal_id: str) -> str:
        match = re.match(r"^term(?:inal)?-(\d+)$", terminal_id, re.I)
        if match:
            return "Terminal %s" % match.group(1)
        return terminal_id

    def _capabilities(self) -> Dict[str, Any]:
        return {"stdin": True, "resize": False, "pty": False}

    def _summary_locked(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "session_id": state["session_id"],
            "terminal_id": state["terminal_id"],
            "cwd": state["cwd"],
            "status": state["status"],
            "pid": state["pid"],
            "exit_code": state["exit_code"],
            "label": state["label"],
            "updated_at": state["updated_at"],
            "capabilities": self._capabilities(),
        }

    def _snapshot_locked(self, state: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._summary_locked(state)
        payload.update(
            {
                "history": state["history"],
                "sequence": state["sequence"],
                "cols": state["cols"],
                "rows": state["rows"],
            }
        )
        return payload

    def _event_locked(
        self,
        state: Dict[str, Any],
        event_type: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "type": event_type,
            "session_id": state["session_id"],
            "terminal_id": state["terminal_id"],
            "sequence": state["sequence"],
        }
        if extra:
            payload.update(extra)
        return payload

    def _emit(self, event: Optional[Dict[str, Any]]) -> None:
        if event is None or self.event_sink is None:
            return
        try:
            self.event_sink(dict(event))
        except Exception:
            return
```

- [ ] **Step 4: Run service tests**

Run:

```bash
uv run pytest tests/test_gui_terminal_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/embedagent/frontend/gui/backend/terminal_service.py tests/test_gui_terminal_service.py
git commit -m "gui: add terminal service"
```

---

### Task 2: Backend Routes, Broadcast, And Capabilities

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/gui/backend/app_shell.py`
- Test: `tests/test_gui_terminal_api.py`
- Test: `tests/test_gui_app_shell.py`

- [ ] **Step 1: Write failing API and app-shell tests**

Create `tests/test_gui_terminal_api.py`:

```python
import os
import shutil
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.app_host import GUIAppHost
from embedagent.frontend.gui.backend.server import GUIBackend
from embedagent.frontend.gui.backend.terminal_service import TerminalService
from embedagent.frontend.gui.backend.workspace_registry import WorkspaceRegistry


class FakeFrontend(object):
    def __init__(self):
        self.messages = []

    def _dispatch_message(self, message):
        self.messages.append(message)
        return True


class FakeCore(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.frontend = None

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        return None

    def list_sessions(self, limit=10):
        return []

    def get_workspace_snapshot(self):
        return {"path": self.workspace}


class FakeTerminalService(object):
    def __init__(self):
        self.calls = []
        self.events = []

    def set_event_sink(self, sink):
        self.sink = sink

    def list_sessions(self, session_id=None):
        self.calls.append(("list", session_id))
        return [
            {
                "session_id": session_id or "sess-1",
                "terminal_id": "term-1",
                "cwd": "D:/workspace",
                "status": "running",
                "pid": 123,
                "exit_code": None,
                "label": "Terminal 1",
                "updated_at": "2026-06-17T00:00:00Z",
                "capabilities": {"stdin": True, "resize": False, "pty": False},
            }
        ]

    def open_or_attach(self, session_id, terminal_id, cwd="", cols=80, rows=24):
        self.calls.append(("open", session_id, terminal_id, cwd, cols, rows))
        event = {
            "type": "output",
            "session_id": session_id,
            "terminal_id": terminal_id,
            "sequence": 1,
            "data": "hello\n",
        }
        self.sink(event)
        return {
            "session_id": session_id,
            "terminal_id": terminal_id,
            "cwd": "D:/workspace",
            "status": "running",
            "pid": 123,
            "history": "",
            "exit_code": None,
            "label": "Terminal 1",
            "updated_at": "2026-06-17T00:00:00Z",
            "sequence": 0,
            "cols": cols,
            "rows": rows,
            "capabilities": {"stdin": True, "resize": False, "pty": False},
        }

    def snapshot(self, session_id, terminal_id):
        self.calls.append(("snapshot", session_id, terminal_id))
        return self.open_or_attach(session_id, terminal_id)

    def write(self, session_id, terminal_id, data):
        self.calls.append(("write", session_id, terminal_id, data))
        return {"status": "ok"}

    def clear(self, session_id, terminal_id):
        self.calls.append(("clear", session_id, terminal_id))
        return {"history": ""}

    def restart(self, session_id, terminal_id, cwd="", cols=80, rows=24):
        self.calls.append(("restart", session_id, terminal_id, cwd, cols, rows))
        return self.open_or_attach(session_id, terminal_id, cwd=cwd, cols=cols, rows=rows)

    def resize(self, session_id, terminal_id, cols, rows):
        self.calls.append(("resize", session_id, terminal_id, cols, rows))
        return {"cols": cols, "rows": rows, "capabilities": {"resize": False, "pty": False}}

    def close(self, session_id, terminal_id=""):
        self.calls.append(("close", session_id, terminal_id))
        return {"session_id": session_id, "terminal_id": terminal_id, "status": "closed"}

    def shutdown(self):
        self.calls.append(("shutdown",))


class GuiTerminalApiTests(unittest.TestCase):
    def make_backend(self, workspace, terminal_service):
        def factory(path):
            return FakeCore(path)

        registry = WorkspaceRegistry(storage_path=os.path.join(workspace, "workspaces.json"))
        host = GUIAppHost(core_factory=factory, registry=registry)
        backend = GUIBackend(
            app_host=host,
            terminal_service=terminal_service,
        )
        frontend = FakeFrontend()
        backend.frontend._dispatch_message = frontend._dispatch_message
        backend.app_shell.open_workspace_path(workspace)
        return backend, frontend

    def test_terminal_routes_call_service_and_broadcast_events(self):
        with tempfile.TemporaryDirectory() as workspace:
            terminal = FakeTerminalService()
            backend, frontend = self.make_backend(workspace, terminal)
            client = TestClient(backend.app)

            opened = client.post(
                "/api/sessions/sess-1/terminals/term-1/open",
                json={"cwd": "", "cols": 100, "rows": 30},
            )
            self.assertEqual(opened.status_code, 200)
            self.assertEqual(opened.json()["terminal"]["terminal_id"], "term-1")
            self.assertEqual(opened.json()["terminal"]["capabilities"]["pty"], False)

            listed = client.get("/api/sessions/sess-1/terminals")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(listed.json()["terminals"][0]["terminal_id"], "term-1")

            written = client.post(
                "/api/sessions/sess-1/terminals/term-1/write",
                json={"data": "echo hi\n"},
            )
            self.assertEqual(written.status_code, 200)

            closed = client.post("/api/sessions/sess-1/terminals/term-1/close")
            self.assertEqual(closed.status_code, 200)
            self.assertEqual(closed.json()["terminal"]["status"], "closed")
            self.assertTrue(any(message["type"] == "terminal_event" for message in frontend.messages))
            self.assertIn(("write", "sess-1", "term-1", "echo hi\n"), terminal.calls)

    def test_terminal_routes_require_active_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            terminal = FakeTerminalService()
            registry = WorkspaceRegistry(storage_path=os.path.join(workspace, "workspaces.json"))
            host = GUIAppHost(core_factory=lambda path: FakeCore(path), registry=registry)
            backend = GUIBackend(app_host=host, terminal_service=terminal)
            client = TestClient(backend.app)

            response = client.post("/api/sessions/sess-1/terminals/term-1/open", json={})

            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"], "no_active_workspace")

    def test_terminal_value_errors_map_to_http_status(self):
        class ErrorTerminal(FakeTerminalService):
            def open_or_attach(self, *args, **kwargs):
                raise ValueError("terminal_cwd_outside_workspace")

            def write(self, *args, **kwargs):
                raise ValueError("terminal_not_found")

        with tempfile.TemporaryDirectory() as workspace:
            backend, _frontend = self.make_backend(workspace, ErrorTerminal())
            client = TestClient(backend.app)

            bad_cwd = client.post("/api/sessions/sess-1/terminals/term-1/open", json={})
            missing = client.post(
                "/api/sessions/sess-1/terminals/term-1/write",
                json={"data": "x"},
            )

            self.assertEqual(bad_cwd.status_code, 422)
            self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
```

Modify `tests/test_gui_app_shell.py` inside `test_bootstrap_without_workspace_includes_shell_fields`:

```python
        self.assertEqual(
            payload["capabilities"]["terminal"],
            {
                "enabled": True,
                "pty": False,
                "resize": False,
                "history_persistent": False,
                "max_buffer_bytes": 131072,
            },
        )
        self.assertIn("terminal", payload["capabilities"]["surfaces"]["bottom_drawer"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_gui_terminal_api.py tests/test_gui_app_shell.py -v
```

Expected: FAIL because `GUIBackend` does not accept `terminal_service`, routes are missing, and app-shell terminal capabilities are absent.

- [ ] **Step 3: Add capability metadata**

Modify `src/embedagent/frontend/gui/backend/app_shell.py` in `_capabilities()` so `surfaces` includes `bottom_drawer`, and add `terminal`:

```python
            "surfaces": {
                "right_panel": ["settings", "diagnostics"],
                "bottom_drawer": ["terminal", "run_output", "logs"],
            },
            "terminal": {
                "enabled": True,
                "pty": False,
                "resize": False,
                "history_persistent": False,
                "max_buffer_bytes": 131072,
            },
```

Keep `thread_lifecycle` unchanged.

- [ ] **Step 4: Wire `TerminalService` into `GUIBackend`**

Modify imports in `src/embedagent/frontend/gui/backend/server.py`:

```python
from embedagent.frontend.gui.backend.terminal_service import TerminalService
```

Modify `GUIBackend.__init__` signature to accept:

```python
        terminal_service: Optional[Any] = None,
```

After `self.app_shell = ...`, create:

```python
        self.terminal_service = terminal_service
        self._terminal_service_injected = terminal_service is not None
        self._terminal_workspace_path = ""
        if self.terminal_service is None:
            self.terminal_service = None
        elif hasattr(self.terminal_service, "set_event_sink"):
            self.terminal_service.set_event_sink(self._emit_terminal_event)
```

Add a helper method:

```python
    def _terminal(self) -> Any:
        self._require_core()
        host_state = self.app_host.bootstrap()
        active_workspace = (
            host_state.get("active_workspace") if isinstance(host_state, dict) else None
        )
        workspace_path = ""
        if isinstance(active_workspace, dict):
            workspace_path = str(active_workspace.get("path") or "")
        if not workspace_path:
            raise HTTPException(status_code=409, detail="no_active_workspace")
        if (
            self.terminal_service is not None
            and not self._terminal_service_injected
            and self._terminal_workspace_path
            and os.path.realpath(workspace_path) != self._terminal_workspace_path
        ):
            self.terminal_service.shutdown()
            self.terminal_service = None
        if self.terminal_service is None:
            self._terminal_workspace_path = os.path.realpath(workspace_path)
            self.terminal_service = TerminalService(
                workspace_root=workspace_path,
                event_sink=self._emit_terminal_event,
            )
        return self.terminal_service

    def _emit_terminal_event(self, event: Dict[str, Any]) -> None:
        self.frontend._dispatch_message({"type": "terminal_event", "data": {"event": dict(event)}})
```
Also add `import os` at the top of `server.py` if it is not already imported.

In the FastAPI lifespan shutdown, call:

```python
            if self.terminal_service is not None:
                self.terminal_service.shutdown()
```

- [ ] **Step 5: Add terminal route error mapper**

Add near `_thread_lifecycle_http_error`:

```python
def _terminal_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "terminal_failed"
    if detail == "terminal_not_found":
        return HTTPException(status_code=404, detail=detail)
    if detail == "terminal_not_running":
        return HTTPException(status_code=409, detail=detail)
    if detail in (
        "invalid_session_id",
        "invalid_terminal_id",
        "terminal_write_empty",
        "terminal_write_too_large",
        "terminal_cwd_outside_workspace",
        "terminal_cwd_not_found",
        "terminal_cwd_not_directory",
        "terminal_shell_unavailable",
    ):
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail)
```

- [ ] **Step 6: Add terminal routes**

Inside `_create_app`, after thread lifecycle routes and before message routes, add:

```python
        @app.get("/api/sessions/{session_id}/terminals")
        async def list_session_terminals(session_id: str):
            terminal = self._terminal()
            return {"terminals": terminal.list_sessions(session_id)}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/open")
        async def open_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
            terminal = self._terminal()
            try:
                snapshot = terminal.open_or_attach(
                    session_id,
                    terminal_id,
                    cwd=str(request.get("cwd") or ""),
                    cols=int(request.get("cols") or 80),
                    rows=int(request.get("rows") or 24),
                )
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.get("/api/sessions/{session_id}/terminals/{terminal_id}/snapshot")
        async def get_terminal_snapshot(session_id: str, terminal_id: str):
            terminal = self._terminal()
            try:
                snapshot = terminal.snapshot(session_id, terminal_id)
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/write")
        async def write_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
            terminal = self._terminal()
            try:
                snapshot = terminal.write(session_id, terminal_id, str(request.get("data") or ""))
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/clear")
        async def clear_terminal(session_id: str, terminal_id: str):
            terminal = self._terminal()
            try:
                snapshot = terminal.clear(session_id, terminal_id)
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/restart")
        async def restart_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
            terminal = self._terminal()
            try:
                snapshot = terminal.restart(
                    session_id,
                    terminal_id,
                    cwd=str(request.get("cwd") or ""),
                    cols=int(request.get("cols") or 80),
                    rows=int(request.get("rows") or 24),
                )
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/resize")
        async def resize_terminal(session_id: str, terminal_id: str, request: Dict[str, Any]):
            terminal = self._terminal()
            try:
                snapshot = terminal.resize(
                    session_id,
                    terminal_id,
                    cols=int(request.get("cols") or 80),
                    rows=int(request.get("rows") or 24),
                )
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}

        @app.post("/api/sessions/{session_id}/terminals/{terminal_id}/close")
        async def close_terminal(session_id: str, terminal_id: str):
            terminal = self._terminal()
            try:
                snapshot = terminal.close(session_id, terminal_id)
            except ValueError as exc:
                raise _terminal_http_error(exc)
            return {"terminal": snapshot}
```

- [ ] **Step 7: Run backend API tests**

Run:

```bash
uv run pytest tests/test_gui_terminal_api.py tests/test_gui_app_shell.py tests/test_gui_backend_api.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/gui/backend/app_shell.py tests/test_gui_terminal_api.py tests/test_gui_app_shell.py
git commit -m "gui: expose terminal api"
```

---

### Task 3: Frontend Terminal Model, API, And Capabilities

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/terminal/terminal-labels.js`
- Create: `src/embedagent/frontend/gui/webapp/src/terminal/terminal-state.js`
- Create: `src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js`
- Create: `src/embedagent/frontend/gui/webapp/test/terminal-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`

- [ ] **Step 1: Write failing frontend model tests**

Create `src/embedagent/frontend/gui/webapp/test/terminal-state.test.mjs`:

```js
import assert from "node:assert/strict";

import {
  getTerminalLabel,
  nextTerminalId,
  resolveTerminalSessionLabel,
} from "../src/terminal/terminal-labels.js";
import {
  applyTerminalEvent,
  createTerminalState,
  normalizeTerminalSnapshot,
  normalizeTerminalSummary,
  reduceTerminalState,
} from "../src/terminal/terminal-state.js";

export function runTerminalStateTests() {
  assert.equal(getTerminalLabel("term-1"), "Terminal 1");
  assert.equal(getTerminalLabel("terminal-12"), "Terminal 12");
  assert.equal(getTerminalLabel("custom"), "custom");
  assert.equal(resolveTerminalSessionLabel("term-2", { label: "npm test" }), "npm test");
  assert.equal(resolveTerminalSessionLabel("term-2", { label: "   " }), "Terminal 2");
  assert.equal(nextTerminalId([]), "term-1");
  assert.equal(nextTerminalId(["term-1", "term-3"]), "term-2");

  const summary = normalizeTerminalSummary({
    session_id: "sess-1",
    terminal_id: "term-1",
    cwd: "D:/demo",
    status: "running",
    pid: 123,
    label: "Terminal 1",
    updated_at: "2026-06-17T00:00:00Z",
    capabilities: { stdin: true, resize: false, pty: false },
  });
  assert.equal(summary.sessionId, "sess-1");
  assert.equal(summary.terminalId, "term-1");
  assert.equal(summary.capabilities.pty, false);

  const snapshot = normalizeTerminalSnapshot({
    ...summary,
    session_id: "sess-1",
    terminal_id: "term-1",
    history: "hello",
    sequence: 1,
  });
  assert.equal(snapshot.history, "hello");
  assert.equal(snapshot.sequence, 1);

  let state = createTerminalState({ maxBufferChars: 12 });
  state = reduceTerminalState(state, {
    type: "terminal_snapshot_loaded",
    snapshot,
  });
  assert.equal(state.activeTerminalId, "term-1");
  assert.equal(state.sessions["term-1"].buffer, "hello");

  state = applyTerminalEvent(state, {
    type: "output",
    session_id: "sess-1",
    terminal_id: "term-1",
    sequence: 2,
    data: " world and more",
  });
  assert.equal(state.sessions["term-1"].buffer, "ld and more");

  state = applyTerminalEvent(state, {
    type: "cleared",
    session_id: "sess-1",
    terminal_id: "term-1",
    sequence: 3,
  });
  assert.equal(state.sessions["term-1"].buffer, "");

  state = applyTerminalEvent(state, {
    type: "closed",
    session_id: "sess-1",
    terminal_id: "term-1",
    sequence: 4,
  });
  assert.equal(state.sessions["term-1"], undefined);
  assert.equal(state.activeTerminalId, "");
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```js
import { runTerminalStateTests } from "./terminal-state.test.mjs";
```

Call it in `main()` near other frontend helper tests:

```js
  runTerminalStateTests();
```

Modify `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs` to assert terminal capabilities:

```js
  assert.equal(state.capabilities.terminal.enabled, true);
  assert.equal(state.capabilities.terminal.pty, false);
  assert.equal(state.capabilities.terminal.resize, false);
```

Modify `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`:

```js
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("terminal"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "drawer.terminal"), true);
```

- [ ] **Step 2: Run frontend tests to verify they fail**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because terminal modules and capability normalization are missing.

- [ ] **Step 3: Add terminal labels module**

Create `src/embedagent/frontend/gui/webapp/src/terminal/terminal-labels.js`:

```js
export function getTerminalLabel(terminalId) {
  const id = String(terminalId || "").trim();
  const match = /^term(?:inal)?-(\d+)$/i.exec(id);
  if (match) return `Terminal ${match[1]}`;
  return id || "Terminal";
}

export function resolveTerminalSessionLabel(terminalId, summary) {
  const label = String((summary && summary.label) || "").trim();
  return label || getTerminalLabel(terminalId);
}

export function nextTerminalId(existingTerminalIds) {
  const used = new Set((existingTerminalIds || []).map((item) => String(item || "").trim()).filter(Boolean));
  let index = 1;
  while (used.has(`term-${index}`)) index += 1;
  return `term-${index}`;
}
```

- [ ] **Step 4: Add terminal state reducer**

Create `src/embedagent/frontend/gui/webapp/src/terminal/terminal-state.js`:

```js
import { resolveTerminalSessionLabel } from "./terminal-labels.js";

const DEFAULT_MAX_BUFFER_CHARS = 128 * 1024;

function normalizeCapabilities(input = {}) {
  return {
    stdin: input.stdin !== false,
    resize: input.resize === true,
    pty: input.pty === true,
  };
}

function trimBuffer(text, maxBufferChars) {
  const value = String(text || "");
  const limit = Number(maxBufferChars || DEFAULT_MAX_BUFFER_CHARS);
  if (value.length <= limit) return value;
  return value.slice(value.length - limit);
}

export function normalizeTerminalSummary(input = {}) {
  const terminalId = String(input.terminal_id || input.terminalId || "");
  return {
    sessionId: String(input.session_id || input.sessionId || ""),
    terminalId,
    cwd: String(input.cwd || ""),
    status: String(input.status || "closed"),
    pid: input.pid == null ? null : Number(input.pid),
    exitCode: input.exit_code == null && input.exitCode == null ? null : Number(input.exit_code ?? input.exitCode),
    label: resolveTerminalSessionLabel(terminalId, input),
    updatedAt: String(input.updated_at || input.updatedAt || ""),
    capabilities: normalizeCapabilities(input.capabilities || {}),
  };
}

export function normalizeTerminalSnapshot(input = {}) {
  return {
    ...normalizeTerminalSummary(input),
    history: String(input.history || ""),
    sequence: Number(input.sequence || 0),
    cols: Number(input.cols || 80),
    rows: Number(input.rows || 24),
  };
}

export function createTerminalState(options = {}) {
  return {
    activeTerminalId: "",
    terminalIds: [],
    sessions: {},
    maxBufferChars: Number(options.maxBufferChars || DEFAULT_MAX_BUFFER_CHARS),
    lastError: "",
  };
}

function upsertSnapshot(state, snapshot) {
  const normalized = normalizeTerminalSnapshot(snapshot);
  if (!normalized.terminalId) return state;
  const terminalIds = state.terminalIds.includes(normalized.terminalId)
    ? state.terminalIds
    : state.terminalIds.concat(normalized.terminalId);
  return {
    ...state,
    terminalIds,
    activeTerminalId: state.activeTerminalId || normalized.terminalId,
    sessions: {
      ...state.sessions,
      [normalized.terminalId]: {
        ...normalized,
        buffer: trimBuffer(normalized.history, state.maxBufferChars),
        error: "",
      },
    },
    lastError: "",
  };
}

function removeTerminal(state, terminalId) {
  const sessions = { ...state.sessions };
  delete sessions[terminalId];
  const terminalIds = state.terminalIds.filter((id) => id !== terminalId);
  return {
    ...state,
    terminalIds,
    activeTerminalId:
      state.activeTerminalId === terminalId ? terminalIds[0] || "" : state.activeTerminalId,
    sessions,
  };
}

export function applyTerminalEvent(state, rawEvent) {
  const current = state || createTerminalState();
  const event = rawEvent && rawEvent.event ? rawEvent.event : rawEvent || {};
  const terminalId = String(event.terminal_id || event.terminalId || "");
  if (event.type === "snapshot" || event.type === "started" || event.type === "restarted") {
    return upsertSnapshot(current, event.snapshot || event);
  }
  if (event.type === "closed") {
    return removeTerminal(current, terminalId);
  }
  const existing = current.sessions[terminalId];
  if (!existing) return current;
  if (event.type === "output") {
    return {
      ...current,
      sessions: {
        ...current.sessions,
        [terminalId]: {
          ...existing,
          buffer: trimBuffer(existing.buffer + String(event.data || ""), current.maxBufferChars),
          sequence: Number(event.sequence || existing.sequence || 0),
          status: "running",
        },
      },
    };
  }
  if (event.type === "cleared") {
    return {
      ...current,
      sessions: {
        ...current.sessions,
        [terminalId]: { ...existing, buffer: "", history: "", sequence: Number(event.sequence || existing.sequence || 0) },
      },
    };
  }
  if (event.type === "exited") {
    return {
      ...current,
      sessions: {
        ...current.sessions,
        [terminalId]: {
          ...existing,
          status: "exited",
          exitCode: event.exit_code == null && event.exitCode == null ? existing.exitCode : Number(event.exit_code ?? event.exitCode),
          sequence: Number(event.sequence || existing.sequence || 0),
        },
      },
    };
  }
  if (event.type === "error") {
    return {
      ...current,
      lastError: String(event.message || "terminal_error"),
      sessions: {
        ...current.sessions,
        [terminalId]: { ...existing, status: "error", error: String(event.message || "terminal_error") },
      },
    };
  }
  return current;
}

export function reduceTerminalState(state, action) {
  const current = state || createTerminalState();
  switch (action.type) {
    case "terminal_snapshot_loaded":
      return upsertSnapshot(current, action.snapshot || {});
    case "terminal_summaries_loaded": {
      const next = (action.terminals || []).reduce((acc, item) => {
        const summary = normalizeTerminalSummary(item);
        if (!summary.terminalId) return acc;
        return {
          ...acc,
          terminalIds: acc.terminalIds.includes(summary.terminalId)
            ? acc.terminalIds
            : acc.terminalIds.concat(summary.terminalId),
          sessions: {
            ...acc.sessions,
            [summary.terminalId]: {
              ...(acc.sessions[summary.terminalId] || {}),
              ...summary,
              buffer: (acc.sessions[summary.terminalId] || {}).buffer || "",
            },
          },
        };
      }, current);
      return {
        ...next,
        activeTerminalId: next.activeTerminalId || next.terminalIds[0] || "",
      };
    }
    case "terminal_event":
      return applyTerminalEvent(current, action.event || {});
    case "terminal_active_set":
      return current.terminalIds.includes(action.terminalId)
        ? { ...current, activeTerminalId: action.terminalId }
        : current;
    default:
      return current;
  }
}
```

- [ ] **Step 5: Add terminal API wrapper**

Create `src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js`:

```js
async function parseJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || response.statusText || "terminal_request_failed";
    throw new Error(String(detail));
  }
  return payload;
}

export async function listTerminals(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/terminals`);
  return parseJson(response);
}

export async function openTerminal(sessionId, terminalId, options = {}) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/open`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options),
    },
  );
  return parseJson(response);
}

export async function writeTerminal(sessionId, terminalId, data) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/write`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data }),
    },
  );
  return parseJson(response);
}

export async function clearTerminal(sessionId, terminalId) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/clear`,
    { method: "POST" },
  );
  return parseJson(response);
}

export async function restartTerminal(sessionId, terminalId, options = {}) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/restart`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options),
    },
  );
  return parseJson(response);
}

export async function closeTerminal(sessionId, terminalId) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/close`,
    { method: "POST" },
  );
  return parseJson(response);
}
```

- [ ] **Step 6: Normalize terminal capabilities**

Modify `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`:

```js
function normalizeTerminalCapability(input = {}) {
  const value = input.terminal && typeof input.terminal === "object" ? input.terminal : {};
  return {
    enabled: value.enabled === true,
    pty: value.pty === true,
    resize: value.resize === true,
    historyPersistent: value.history_persistent === true || value.historyPersistent === true,
    maxBufferBytes: Number(value.max_buffer_bytes || value.maxBufferBytes || 0),
  };
}
```

In `normalizeAppCapabilities`, add:

```js
    terminal: normalizeTerminalCapability(input),
```

- [ ] **Step 7: Add terminal drawer command**

Modify `src/embedagent/frontend/gui/webapp/src/workbench/commands.js` after `drawer.run_output`:

```js
  { id: "drawer.terminal", group: "surface", label: "Open Terminal", slash: "", drawer: "terminal", visibleWhen: "has_session" },
```

- [ ] **Step 8: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 9: Commit Task 3**

```bash
git add src/embedagent/frontend/gui/webapp/src/terminal src/embedagent/frontend/gui/webapp/src/app-shell/model.js src/embedagent/frontend/gui/webapp/src/workbench/commands.js src/embedagent/frontend/gui/webapp/test/terminal-state.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs
git commit -m "gui: add terminal frontend model"
```

---

### Task 4: Terminal Drawer UI And App Wiring

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add terminal state to root store**

Modify `src/embedagent/frontend/gui/webapp/src/store.js` imports:

```js
import { createTerminalState, reduceTerminalState } from "./terminal/terminal-state.js";
```

Add to `initialState`:

```js
  terminal: createTerminalState(),
```

Add reducer cases:

```js
    case "terminal_snapshot_loaded":
    case "terminal_summaries_loaded":
    case "terminal_event":
    case "terminal_active_set":
      return { ...state, terminal: reduceTerminalState(state.terminal, action) };
```

In `workspace_switched`, ensure terminal resets by relying on `resetWorkspaceScopedState`; if `resetWorkspaceScopedState` does not reset unknown fields, modify `src/embedagent/frontend/gui/webapp/src/app-workspaces.js` so terminal returns `createTerminalState()`.

- [ ] **Step 2: Add terminal imports and helper actions in `App.jsx`**

Modify imports in `App.jsx`:

```js
import {
  clearTerminal,
  closeTerminal,
  listTerminals,
  openTerminal,
  restartTerminal,
  writeTerminal,
} from "./terminal/terminal-api.js";
import { nextTerminalId } from "./terminal/terminal-labels.js";
```

Add helper functions near other async actions:

```js
  async function ensureTerminalOpen(preferredId = "") {
    if (!state.currentSessionId) {
      dispatch({ type: "interaction_notice_set", notice: "Open a session before using the terminal." });
      return;
    }
    const terminalId = preferredId || state.terminal.activeTerminalId || nextTerminalId(state.terminal.terminalIds);
    try {
      const payload = await openTerminal(state.currentSessionId, terminalId, { cols: 100, rows: 30 });
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      dispatch({ type: "terminal_active_set", terminalId });
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: "terminal" });
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal failed to open." });
    }
  }

  async function refreshTerminals() {
    if (!state.currentSessionId) return;
    try {
      const payload = await listTerminals(state.currentSessionId);
      dispatch({ type: "terminal_summaries_loaded", terminals: payload.terminals || [] });
    } catch (_) {
      return;
    }
  }

  async function sendTerminalInput(text) {
    const terminalId = state.terminal.activeTerminalId;
    if (!state.currentSessionId || !terminalId) return;
    try {
      await writeTerminal(state.currentSessionId, terminalId, text);
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal write failed." });
    }
  }

  async function clearActiveTerminal() {
    const terminalId = state.terminal.activeTerminalId;
    if (!state.currentSessionId || !terminalId) return;
    const payload = await clearTerminal(state.currentSessionId, terminalId);
    dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
  }

  async function restartActiveTerminal() {
    const terminalId = state.terminal.activeTerminalId;
    if (!state.currentSessionId || !terminalId) return;
    const payload = await restartTerminal(state.currentSessionId, terminalId, { cols: 100, rows: 30 });
    dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
  }

  async function closeActiveTerminal() {
    const terminalId = state.terminal.activeTerminalId;
    if (!state.currentSessionId || !terminalId) return;
    await closeTerminal(state.currentSessionId, terminalId);
    dispatch({ type: "terminal_event", event: { type: "closed", session_id: state.currentSessionId, terminal_id: terminalId } });
  }
```

- [ ] **Step 3: Handle WebSocket terminal events**

In `handleSocketMessage(type, data)` before `session_event`:

```js
    if (type === "terminal_event") {
      dispatch({ type: "terminal_event", event: data?.event || data || {} });
      return;
    }
```

- [ ] **Step 4: Ensure terminal command opens terminal drawer**

In `executeWorkbenchCommand(command)`, when command has `drawer`, the existing code activates the bottom surface. Add a special case before generic drawer activation:

```js
    if (command.drawer === "terminal") {
      await ensureTerminalOpen();
      return;
    }
```

Also when the bottom drawer is toggled directly to terminal from UI, the `BottomDrawer` create action will call `ensureTerminalOpen`.

- [ ] **Step 5: Render terminal surface in `BottomDrawer.jsx`**

Replace `BottomDrawer.jsx` with a component that keeps existing run output behavior and adds terminal UI:

```jsx
import React, { useState } from "react";

function RunOutputDrawer({ eventLog, terminationReason, terminationMessage }) {
  const entries = Array.isArray(eventLog) ? eventLog.slice(-80) : [];
  return (
    <>
      {terminationReason ? (
        <div className="drawer-line">
          reason={terminationReason} {terminationMessage || ""}
        </div>
      ) : null}
      {entries.length > 0 ? (
        entries.map((entry) => (
          <div className="drawer-line" key={`${entry.ts}-${entry.label}`}>
            <span className="drawer-label">{entry.label}</span>
            <span>{entry.detail || ""}</span>
          </div>
        ))
      ) : (
        <div className="drawer-line muted">No run output yet.</div>
      )}
    </>
  );
}

function TerminalSurface({ terminal, onNew, onSelect, onSend, onClear, onRestart, onClose }) {
  const [draft, setDraft] = useState("");
  const active = terminal.sessions[terminal.activeTerminalId] || null;
  const terminalIds = terminal.terminalIds || [];
  return (
    <div className="terminal-drawer-surface" data-testid="terminal-drawer">
      <div className="terminal-tabbar">
        {terminalIds.map((terminalId) => {
          const item = terminal.sessions[terminalId] || { label: terminalId, status: "closed" };
          return (
            <button
              key={terminalId}
              className={`terminal-tab${terminalId === terminal.activeTerminalId ? " active" : ""}`}
              type="button"
              onClick={() => onSelect(terminalId)}
            >
              <span>{item.label || terminalId}</span>
              <span className={`terminal-status-dot ${item.status || "closed"}`} />
            </button>
          );
        })}
        <button className="terminal-icon-button" type="button" title="New terminal" onClick={onNew}>
          +
        </button>
      </div>
      <div className="terminal-toolbar">
        <span>{active ? active.cwd : "No terminal"}</span>
        <span>{active ? active.status : "closed"}</span>
        <button type="button" title="Clear terminal" onClick={onClear} disabled={!active}>
          Clear
        </button>
        <button type="button" title="Restart terminal" onClick={onRestart} disabled={!active}>
          Restart
        </button>
        <button type="button" title="Close terminal" onClick={onClose} disabled={!active}>
          Close
        </button>
      </div>
      <pre className="terminal-buffer">{active ? active.buffer || "" : "Open a terminal to start."}</pre>
      <form
        className="terminal-input-row"
        onSubmit={(event) => {
          event.preventDefault();
          const text = draft;
          if (!text.trim()) return;
          setDraft("");
          onSend(`${text}\n`);
        }}
      >
        <span>&gt;</span>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type a command"
          disabled={!active || active.status === "closed"}
        />
      </form>
    </div>
  );
}

export default function BottomDrawer({
  activeKind,
  eventLog,
  terminationReason,
  terminationMessage,
  terminal,
  onTerminalNew,
  onTerminalSelect,
  onTerminalSend,
  onTerminalClear,
  onTerminalRestart,
  onTerminalClose,
}) {
  return (
    <section className="bottom-drawer" aria-label="Bottom drawer" data-testid="bottom-drawer">
      <div className="bottom-drawer-tabs" role="tablist">
        <button className={`bottom-drawer-tab${activeKind === "terminal" ? " active" : ""}`} type="button">
          Terminal
        </button>
        <button className={`bottom-drawer-tab${activeKind === "run_output" ? " active" : ""}`} type="button">
          Run Output
        </button>
        <button className={`bottom-drawer-tab${activeKind === "logs" ? " active" : ""}`} type="button">
          Logs
        </button>
      </div>
      <div className="bottom-drawer-body">
        {activeKind === "terminal" ? (
          <TerminalSurface
            terminal={terminal}
            onNew={onTerminalNew}
            onSelect={onTerminalSelect}
            onSend={onTerminalSend}
            onClear={onTerminalClear}
            onRestart={onTerminalRestart}
            onClose={onTerminalClose}
          />
        ) : (
          <RunOutputDrawer
            eventLog={eventLog}
            terminationReason={terminationReason}
            terminationMessage={terminationMessage}
          />
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 6: Pass terminal props from `App.jsx`**

Modify the `BottomDrawer` call:

```jsx
        <BottomDrawer
          activeKind={state.workbench.bottomDrawer.activeKind}
          eventLog={state.eventLog}
          terminationReason={state.terminationDisplayReason || state.terminationReason}
          terminationMessage={state.terminationMessage}
          terminal={state.terminal}
          onTerminalNew={() => ensureTerminalOpen(nextTerminalId(state.terminal.terminalIds))}
          onTerminalSelect={(terminalId) => dispatch({ type: "terminal_active_set", terminalId })}
          onTerminalSend={sendTerminalInput}
          onTerminalClear={clearActiveTerminal}
          onTerminalRestart={restartActiveTerminal}
          onTerminalClose={closeActiveTerminal}
        />
```

- [ ] **Step 7: Add terminal styles**

Append to `src/embedagent/frontend/gui/webapp/src/styles.css` near bottom drawer styles:

```css
.terminal-drawer-surface {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  min-height: 0;
  height: 100%;
  color: var(--text-primary);
}

.terminal-tabbar,
.terminal-toolbar,
.terminal-input-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.terminal-tabbar {
  min-height: 32px;
  border-bottom: 1px solid var(--border-subtle);
}

.terminal-tab,
.terminal-icon-button,
.terminal-toolbar button {
  height: 26px;
  border: 1px solid var(--border-subtle);
  background: var(--surface-muted);
  color: var(--text-secondary);
  border-radius: 6px;
}

.terminal-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 9px;
}

.terminal-tab.active {
  color: var(--text-primary);
  background: var(--surface-elevated);
  border-color: var(--border-strong);
}

.terminal-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--text-muted);
}

.terminal-status-dot.running,
.terminal-status-dot.starting {
  background: var(--success);
}

.terminal-status-dot.error {
  background: var(--danger);
}

.terminal-toolbar {
  min-height: 30px;
  justify-content: flex-end;
  color: var(--text-muted);
  font-size: 12px;
  border-bottom: 1px solid var(--border-subtle);
}

.terminal-toolbar span:first-child {
  margin-right: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.terminal-buffer {
  min-height: 0;
  margin: 0;
  padding: 10px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  color: var(--text-primary);
  background: var(--surface-base);
}

.terminal-input-row {
  min-height: 34px;
  border-top: 1px solid var(--border-subtle);
  color: var(--text-muted);
}

.terminal-input-row input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text-primary);
  font: inherit;
  font-family: var(--font-mono);
}
```

If variable names differ, use existing CSS tokens from `styles.css` rather than introducing a new one-note palette.

- [ ] **Step 8: Run frontend tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both PASS.

- [ ] **Step 9: Commit Task 4**

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/app-workspaces.js src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/static
git commit -m "gui: wire terminal bottom drawer"
```

---

### Task 5: Docs, Archive Readiness, And Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/modules/frontend-gui.md`

- [ ] **Step 1: Update active docs with terminal boundary**

Add concise terminal boundary language:

- GUI terminal is app-shell hosted, not Agent Core.
- It uses Win7-compatible stdlib subprocess pipes.
- It is not a full PTY.
- It does not write transcript, telemetry, source-control checkpoints, or workflow state.
- No new runtime dependencies are introduced.

Concrete locations:

- `README.md`: add one bullet near official GUI app-shell/thread lifecycle bullets.
- `AGENTS.md`: add frontend/protocol policy paragraph.
- `docs/overall-solution-architecture.md`: add terminal paragraph under Frontend Layer.
- `docs/frontend-protocol.md`: add terminal HTTP/event contract under GUI app-shell state and HTTP API surface.
- `docs/modules/frontend-gui.md`: add terminal bottom drawer responsibility and test entry.
- `docs/implementation-roadmap.md`: move terminal from future gap to recent GUI app-shell work.
- `docs/development-tracker.md`: add dated current-stage entry.
- `docs/design-change-log.md`: add a new DC entry.

- [ ] **Step 2: Run focused verification**

Run:

```bash
uv run pytest tests/test_gui_terminal_service.py tests/test_gui_terminal_api.py tests/test_gui_backend_api.py tests/test_gui_app_shell.py -v
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: all PASS.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check src/embedagent/frontend/gui/backend tests/test_gui_terminal_service.py tests/test_gui_terminal_api.py tests/test_gui_backend_api.py tests/test_gui_app_shell.py
```

Expected: `All checks passed!`.

- [ ] **Step 4: Run broader fast suite**

Run from repo root:

```bash
$env:TEMP='D:\Project\coding_agent\.worktrees\gui-terminal-bottom-drawer\.venv\pytest-tmp'
$env:TMP='D:\Project\coding_agent\.worktrees\gui-terminal-bottom-drawer\.venv\pytest-tmp'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS with all selected tests passing.

- [ ] **Step 5: Check architecture boundary diff**

Run:

```bash
git diff -- src/embedagent/query_engine.py src/embedagent/agent_loop.py src/embedagent/agent_tool_action_service.py src/embedagent/extensions.py src/embedagent/permissions.py
```

Expected: no output.

- [ ] **Step 6: Commit Task 5**

```bash
git add README.md AGENTS.md docs src/embedagent/frontend/gui/static
git commit -m "docs: document gui terminal boundary"
```

---

## Final Verification Checklist

- [ ] Backend terminal service tests pass.
- [ ] Backend terminal API tests pass.
- [ ] Existing GUI backend/app-shell tests pass.
- [ ] Frontend helper tests pass.
- [ ] Webapp build passes and static assets are refreshed.
- [ ] Ruff passes on touched backend/test Python files.
- [ ] Fast non-slow/non-gui suite passes.
- [ ] No changes to Agent Core execution/permission/extension files.
- [ ] `git status --short` is clean.

After all tasks complete, use `superpowers:verification-before-completion`, then use `superpowers:finishing-a-development-branch`.
