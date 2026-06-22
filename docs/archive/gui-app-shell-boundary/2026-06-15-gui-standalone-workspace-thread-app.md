# GUI Standalone Workspace Thread App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone GUI app shell where users can add, switch, and manage local workspaces and their agent threads inside the GUI.

**Architecture:** Add a small GUI app host around the existing workspace-bound `AgentCoreAdapter`. The host owns a local workspace registry and a single active core slot; existing session/file/task APIs continue to target the active workspace. The frontend gains app bootstrap state, a T3-style workspace/thread sidebar, a no-workspace state, and visual-debug coverage for app-level switching.

**Tech Stack:** Python 3.8, FastAPI, pywebview, React/Vite JavaScript, node:test helper tests, Playwright-based visual debug runner.

---

## Scope And File Map

**Create**
- `src/embedagent/frontend/gui/backend/workspace_registry.py`: local JSON registry for recent workspaces.
- `src/embedagent/frontend/gui/backend/app_host.py`: active workspace/core slot and app bootstrap operations.
- `tests/test_gui_workspace_registry.py`: registry unit tests.
- `tests/test_gui_app_host.py`: app host and app route tests.
- `tests/test_gui_launcher_app_mode.py`: launcher no-workspace parsing tests.
- `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`: frontend workspace state helpers.
- `src/embedagent/frontend/gui/webapp/test/app-workspaces.test.mjs`: frontend helper tests.
- `src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx`: no-workspace first screen.

**Modify**
- `src/embedagent/frontend/gui/backend/server.py`: route all workspace-bound APIs through the app host and add `/api/app/*`.
- `src/embedagent/frontend/gui/launcher.py`: allow no-workspace startup and initialize `GUIAppHost`.
- `src/embedagent/frontend/gui/webapp/src/store.js`: app bootstrap/workspace actions and workspace-scoped reset.
- `src/embedagent/frontend/gui/webapp/src/App.jsx`: app bootstrap, workspace activation, workspace change handling.
- `src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx`: T3-style workspace/thread navigation.
- `src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx`: active workspace display.
- `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`: workspace commands.
- `src/embedagent/frontend/gui/webapp/src/strings.js`: user-facing labels for workspace/thread.
- `src/embedagent/frontend/gui/webapp/src/styles.css`: compact workspace/thread sidebar styling and no-workspace state.
- `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`: include new frontend workspace tests and source checks.
- `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`: command palette checks.
- `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`: app scenario checks.
- `scripts/gui-visual-debug.mjs`: app-management visual scenario and optional workspace launch args.

**Do not modify**
- Agent Core architecture, workflow package boundaries, mode registry, or task graph internals.
- Backend durable session vocabulary. GUI can label sessions as Threads, but APIs remain session-based in this slice.

---

## Task 1: Workspace Registry

**Files:**
- Create: `src/embedagent/frontend/gui/backend/workspace_registry.py`
- Create: `tests/test_gui_workspace_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `tests/test_gui_workspace_registry.py`:

```python
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.workspace_registry import (
    WorkspaceRegistry,
    canonical_workspace_path,
    workspace_id_for_path,
)


class TestGuiWorkspaceRegistry(unittest.TestCase):
    def test_workspace_id_is_stable_for_canonical_path(self):
        with tempfile.TemporaryDirectory() as root:
            nested = os.path.join(root, ".", "demo")
            os.mkdir(os.path.join(root, "demo"))
            self.assertEqual(
                workspace_id_for_path(nested),
                workspace_id_for_path(os.path.realpath(os.path.join(root, "demo"))),
            )

    def test_upsert_lists_existing_workspace_with_label_and_timestamp(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            registry = WorkspaceRegistry(
                storage_path=storage,
                clock=lambda: "2026-06-15T10:00:00Z",
            )

            record = registry.upsert_path(workspace)
            records = registry.list_workspaces()

        self.assertEqual(record["id"], workspace_id_for_path(workspace))
        self.assertEqual(record["path"], canonical_workspace_path(workspace))
        self.assertEqual(record["label"], "project-a")
        self.assertEqual(record["created_at"], "2026-06-15T10:00:00Z")
        self.assertEqual(record["last_opened_at"], "2026-06-15T10:00:00Z")
        self.assertEqual(records[0]["exists"], True)

    def test_upsert_existing_workspace_preserves_created_at_and_updates_last_opened(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            ticks = iter(["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"])
            registry = WorkspaceRegistry(storage_path=storage, clock=lambda: next(ticks))

            first = registry.upsert_path(workspace)
            second = registry.upsert_path(workspace, label="Renamed")

        self.assertEqual(first["created_at"], "2026-06-15T10:00:00Z")
        self.assertEqual(second["created_at"], "2026-06-15T10:00:00Z")
        self.assertEqual(second["last_opened_at"], "2026-06-15T11:00:00Z")
        self.assertEqual(second["label"], "Renamed")

    def test_remove_deletes_registry_entry_without_touching_workspace_files(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            marker = os.path.join(workspace, "README.md")
            with open(marker, "w", encoding="utf-8") as handle:
                handle.write("kept")
            registry = WorkspaceRegistry(storage_path=storage)
            record = registry.upsert_path(workspace)

            removed = registry.remove(record["id"])
            self.assertEqual(removed, True)
            self.assertTrue(os.path.exists(marker))
            self.assertEqual(registry.list_workspaces(), [])

    def test_missing_workspace_is_listed_with_exists_false(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            registry = WorkspaceRegistry(storage_path=storage)
            record = registry.upsert_path(workspace)
            os.rmdir(workspace)

            records = registry.list_workspaces()

        self.assertEqual(records[0]["id"], record["id"])
        self.assertEqual(records[0]["exists"], False)

    def test_corrupt_registry_file_recovers_to_empty_list(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            with open(storage, "w", encoding="utf-8") as handle:
                handle.write("{")
            registry = WorkspaceRegistry(storage_path=storage)

            self.assertEqual(registry.list_workspaces(), [])
            registry.upsert_path(root)

            with open(storage, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        self.assertEqual(payload["version"], 1)
        self.assertEqual(len(payload["workspaces"]), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the registry tests and verify failure**

Run:

```bash
uv run pytest tests/test_gui_workspace_registry.py -q
```

Expected: import failure for `embedagent.frontend.gui.backend.workspace_registry`.

- [ ] **Step 3: Implement the registry module**

Create `src/embedagent/frontend/gui/backend/workspace_registry.py`:

```python
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


def _utc_now_string() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_app_home() -> str:
    override = os.environ.get("EMBEDAGENT_GUI_APP_HOME", "").strip()
    if override:
        return os.path.realpath(override)
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return os.path.realpath(os.path.join(appdata, "EmbedAgent", "gui"))
    return os.path.realpath(os.path.join(os.path.expanduser("~"), ".embedagent", "gui"))


def canonical_workspace_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("workspace_path_required")
    return os.path.realpath(os.path.abspath(raw))


def workspace_id_for_path(path: str) -> str:
    canonical = os.path.normcase(canonical_workspace_path(path))
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    return "ws-" + digest[:16]


class WorkspaceRegistry(object):
    def __init__(
        self,
        storage_path: Optional[str] = None,
        clock: Optional[Callable[[], str]] = None,
    ) -> None:
        self.storage_path = os.path.realpath(
            storage_path or os.path.join(default_app_home(), "workspaces.json")
        )
        self._clock = clock or _utc_now_string

    def _read_payload(self) -> Dict[str, Any]:
        if not os.path.isfile(self.storage_path):
            return {"version": 1, "workspaces": []}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError, TypeError):
            return {"version": 1, "workspaces": []}
        if not isinstance(payload, dict):
            return {"version": 1, "workspaces": []}
        workspaces = payload.get("workspaces")
        if not isinstance(workspaces, list):
            workspaces = []
        return {"version": 1, "workspaces": workspaces}

    def _write_payload(self, payload: Dict[str, Any]) -> None:
        parent = os.path.dirname(self.storage_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(self.storage_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)

    def _with_exists(self, record: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(record)
        item["exists"] = os.path.isdir(str(item.get("path") or ""))
        return item

    def list_workspaces(self) -> List[Dict[str, Any]]:
        payload = self._read_payload()
        records = []
        for item in payload.get("workspaces", []):
            if not isinstance(item, dict):
                continue
            workspace_id = str(item.get("id") or "").strip()
            path = str(item.get("path") or "").strip()
            if not workspace_id or not path:
                continue
            records.append(self._with_exists(item))
        records.sort(key=lambda item: str(item.get("last_opened_at") or ""), reverse=True)
        return records

    def get(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        wanted = str(workspace_id or "").strip()
        for record in self.list_workspaces():
            if record.get("id") == wanted:
                return record
        return None

    def upsert_path(self, path: str, label: str = "") -> Dict[str, Any]:
        canonical = canonical_workspace_path(path)
        if not os.path.isdir(canonical):
            raise ValueError("workspace_not_found")
        workspace_id = workspace_id_for_path(canonical)
        now = self._clock()
        payload = self._read_payload()
        workspaces = []
        existing = None
        for item in payload.get("workspaces", []):
            if isinstance(item, dict) and item.get("id") == workspace_id:
                existing = item
            elif isinstance(item, dict):
                workspaces.append(item)
        next_record = {
            "id": workspace_id,
            "path": canonical,
            "label": str(label or "").strip() or os.path.basename(canonical) or canonical,
            "created_at": str((existing or {}).get("created_at") or now),
            "last_opened_at": now,
        }
        workspaces.append(next_record)
        self._write_payload({"version": 1, "workspaces": workspaces})
        return self._with_exists(next_record)

    def mark_opened(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        payload = self._read_payload()
        now = self._clock()
        found = None
        workspaces = []
        for item in payload.get("workspaces", []):
            if not isinstance(item, dict):
                continue
            if item.get("id") == workspace_id:
                updated = dict(item)
                updated["last_opened_at"] = now
                found = updated
                workspaces.append(updated)
            else:
                workspaces.append(item)
        if found is None:
            return None
        self._write_payload({"version": 1, "workspaces": workspaces})
        return self._with_exists(found)

    def remove(self, workspace_id: str) -> bool:
        wanted = str(workspace_id or "").strip()
        payload = self._read_payload()
        kept = []
        removed = False
        for item in payload.get("workspaces", []):
            if isinstance(item, dict) and item.get("id") == wanted:
                removed = True
                continue
            if isinstance(item, dict):
                kept.append(item)
        self._write_payload({"version": 1, "workspaces": kept})
        return removed
```

- [ ] **Step 4: Run registry tests and verify pass**

Run:

```bash
uv run pytest tests/test_gui_workspace_registry.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit registry slice**

```bash
git add src/embedagent/frontend/gui/backend/workspace_registry.py tests/test_gui_workspace_registry.py
git commit -m "feat(gui): add workspace registry"
```

---

## Task 2: GUI App Host And App Routes

**Files:**
- Create: `src/embedagent/frontend/gui/backend/app_host.py`
- Create: `tests/test_gui_app_host.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Test: `tests/test_gui_backend_api.py`

- [ ] **Step 1: Write failing app host and route tests**

Create `tests/test_gui_app_host.py`:

```python
import asyncio
import os
import sys
import tempfile
import unittest

from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.app_host import GUIAppHost
from embedagent.frontend.gui.backend.server import GUIBackend
from embedagent.frontend.gui.backend.workspace_registry import WorkspaceRegistry


class _FakeCore(object):
    def __init__(self, workspace):
        self.workspace = workspace
        self.frontend = None
        self.shutdown_calls = 0

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        self.shutdown_calls += 1

    def list_sessions(self, limit=10):
        return [
            {
                "session_id": "sess-" + os.path.basename(self.workspace),
                "current_mode": "explore",
                "updated_at": "2026-06-15T10:00:00Z",
            }
        ]

    def get_workspace_snapshot(self):
        return {"path": self.workspace}


def _route(app, path, method):
    for item in app.routes:
        if getattr(item, "path", "") == path and method in getattr(item, "methods", set()):
            return item
    raise AssertionError("route not found: %s %s" % (method, path))


class TestGuiAppHost(unittest.TestCase):
    def _backend(self, registry, created):
        def factory(path):
            core = _FakeCore(path)
            created.append(core)
            return core

        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            host = GUIAppHost(core_factory=factory, registry=registry)
            backend = GUIBackend(core=None, static_dir=static_dir, app_host=host)
            return backend, host

    def test_bootstrap_without_active_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            created = []
            backend, host = self._backend(registry, created)
            route = _route(backend.app, "/api/app/bootstrap", "GET")

            payload = asyncio.run(route.endpoint())

        self.assertEqual(payload["has_active_workspace"], False)
        self.assertEqual(payload["active_workspace"], None)
        self.assertEqual(payload["workspaces"], [])
        self.assertEqual(created, [])
        self.assertIs(host.current_core(), None)

    def test_workspace_bound_route_returns_409_without_active_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            backend, host = self._backend(registry, [])
            route = _route(backend.app, "/api/sessions", "GET")

            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route.endpoint(10))

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, "no_active_workspace")
        self.assertIs(host.current_core(), None)

    def test_open_workspace_activates_core_and_registers_frontend(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            created = []
            backend, host = self._backend(registry, created)
            route = _route(backend.app, "/api/app/workspaces", "POST")

            payload = asyncio.run(route.endpoint({"path": workspace}))

        self.assertEqual(payload["active_workspace"]["path"], os.path.realpath(workspace))
        self.assertEqual(len(created), 1)
        self.assertIs(created[0].frontend, backend.frontend)
        self.assertIs(host.current_core(), created[0])

    def test_activating_second_workspace_shuts_down_first_core(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            first = os.path.join(root, "first")
            second = os.path.join(root, "second")
            os.mkdir(first)
            os.mkdir(second)
            created = []
            backend, host = self._backend(registry, created)
            open_route = _route(backend.app, "/api/app/workspaces", "POST")

            asyncio.run(open_route.endpoint({"path": first}))
            asyncio.run(open_route.endpoint({"path": second}))

        self.assertEqual(len(created), 2)
        self.assertEqual(created[0].shutdown_calls, 1)
        self.assertEqual(created[1].shutdown_calls, 0)
        self.assertIs(host.current_core(), created[1])

    def test_remove_workspace_only_updates_registry(self):
        with tempfile.TemporaryDirectory() as root:
            registry = WorkspaceRegistry(storage_path=os.path.join(root, "workspaces.json"))
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            created = []
            backend, host = self._backend(registry, created)
            open_route = _route(backend.app, "/api/app/workspaces", "POST")
            delete_route = _route(backend.app, "/api/app/workspaces/{workspace_id}", "DELETE")
            opened = asyncio.run(open_route.endpoint({"path": workspace}))

            payload = asyncio.run(delete_route.endpoint(opened["active_workspace"]["id"]))

        self.assertEqual(payload["removed"], True)
        self.assertEqual(payload["workspaces"], [])
        self.assertTrue(os.path.isdir(workspace))
        self.assertEqual(created[0].shutdown_calls, 1)
        self.assertIs(host.current_core(), None)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run app host tests and verify failure**

Run:

```bash
uv run pytest tests/test_gui_app_host.py -q
```

Expected: import or constructor failure because `GUIAppHost` and `GUIBackend(app_host=...)` do not exist.

- [ ] **Step 3: Implement app host**

Create `src/embedagent/frontend/gui/backend/app_host.py`:

```python
from __future__ import annotations

import os
import threading
from typing import Any, Callable, Dict, Optional

from embedagent.protocol import CoreInterface

from .workspace_registry import WorkspaceRegistry, canonical_workspace_path


class NoActiveWorkspaceError(Exception):
    pass


class GUIAppHost(object):
    def __init__(
        self,
        core_factory: Callable[[str], CoreInterface],
        registry: Optional[WorkspaceRegistry] = None,
    ) -> None:
        self._core_factory = core_factory
        self._registry = registry or WorkspaceRegistry()
        self._lock = threading.RLock()
        self._frontend = None
        self._active_core = None  # type: Optional[CoreInterface]
        self._active_workspace = None  # type: Optional[Dict[str, Any]]
        self._last_error = ""

    def bind_frontend(self, frontend: Any) -> None:
        with self._lock:
            self._frontend = frontend
            if self._active_core is not None:
                self._active_core.register_frontend(frontend)

    def current_core(self) -> Optional[CoreInterface]:
        with self._lock:
            return self._active_core

    def require_core(self) -> CoreInterface:
        core = self.current_core()
        if core is None:
            raise NoActiveWorkspaceError("no_active_workspace")
        return core

    def bootstrap(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "workspaces": self._registry.list_workspaces(),
                "active_workspace": dict(self._active_workspace) if self._active_workspace else None,
                "has_active_workspace": self._active_core is not None,
                "last_error": self._last_error,
            }

    def list_workspaces(self) -> Dict[str, Any]:
        payload = self.bootstrap()
        return {
            "workspaces": payload["workspaces"],
            "active_workspace": payload["active_workspace"],
        }

    def open_workspace_path(self, path: str, label: str = "") -> Dict[str, Any]:
        record = self._registry.upsert_path(path, label=label)
        return self.activate_workspace(record["id"])

    def activate_workspace(self, workspace_id: str) -> Dict[str, Any]:
        with self._lock:
            record = self._registry.get(workspace_id)
            if record is None:
                raise ValueError("workspace_not_found")
            path = canonical_workspace_path(record["path"])
            if not os.path.isdir(path):
                raise ValueError("workspace_not_found")
            if self._active_workspace and self._active_workspace.get("id") == record["id"]:
                refreshed = self._registry.mark_opened(record["id"]) or record
                self._active_workspace = refreshed
                return self.bootstrap()
            previous = self._active_core
            try:
                next_core = self._core_factory(path)
                if self._frontend is not None:
                    next_core.register_frontend(self._frontend)
            except Exception as exc:
                self._last_error = str(exc)
                raise
            if previous is not None:
                previous.shutdown()
            refreshed = self._registry.mark_opened(record["id"]) or record
            self._active_core = next_core
            self._active_workspace = refreshed
            self._last_error = ""
            self._broadcast_workspace_changed()
            return self.bootstrap()

    def remove_workspace(self, workspace_id: str) -> Dict[str, Any]:
        with self._lock:
            active_removed = bool(
                self._active_workspace and self._active_workspace.get("id") == workspace_id
            )
            removed = self._registry.remove(workspace_id)
            if active_removed:
                if self._active_core is not None:
                    self._active_core.shutdown()
                self._active_core = None
                self._active_workspace = None
                self._broadcast_workspace_changed()
            payload = self.bootstrap()
            payload["removed"] = removed
            return payload

    def shutdown(self) -> None:
        with self._lock:
            core = self._active_core
            self._active_core = None
            self._active_workspace = None
        if core is not None:
            core.shutdown()

    def _broadcast_workspace_changed(self) -> None:
        frontend = self._frontend
        dispatch = getattr(frontend, "_dispatch_message", None)
        if callable(dispatch):
            dispatch({"type": "workspace_changed", "data": self.bootstrap()})


class SingleWorkspaceAppHost(object):
    def __init__(self, core: CoreInterface) -> None:
        self._core = core

    def bind_frontend(self, frontend: Any) -> None:
        self._core.register_frontend(frontend)

    def current_core(self) -> Optional[CoreInterface]:
        return self._core

    def require_core(self) -> CoreInterface:
        return self._core

    def bootstrap(self) -> Dict[str, Any]:
        workspace = None
        try:
            snapshot = self._core.get_workspace_snapshot()
            path = snapshot.get("path") if isinstance(snapshot, dict) else getattr(snapshot, "path", "")
            if path:
                workspace = {
                    "id": "active",
                    "path": path,
                    "label": os.path.basename(path) or path,
                    "exists": os.path.isdir(path),
                    "created_at": "",
                    "last_opened_at": "",
                }
        except (OSError, ValueError, TypeError, AttributeError):
            workspace = None
        return {
            "workspaces": [workspace] if workspace else [],
            "active_workspace": workspace,
            "has_active_workspace": True,
            "last_error": "",
        }

    def list_workspaces(self) -> Dict[str, Any]:
        payload = self.bootstrap()
        return {
            "workspaces": payload["workspaces"],
            "active_workspace": payload["active_workspace"],
        }

    def open_workspace_path(self, path: str, label: str = "") -> Dict[str, Any]:
        raise ValueError("workspace_switch_unavailable")

    def activate_workspace(self, workspace_id: str) -> Dict[str, Any]:
        raise ValueError("workspace_switch_unavailable")

    def remove_workspace(self, workspace_id: str) -> Dict[str, Any]:
        raise ValueError("workspace_switch_unavailable")

    def shutdown(self) -> None:
        self._core.shutdown()
```

- [ ] **Step 4: Refactor GUIBackend to use app host**

Modify `src/embedagent/frontend/gui/backend/server.py`:

1. Add imports:

```python
from embedagent.frontend.gui.backend.app_host import (
    GUIAppHost,
    NoActiveWorkspaceError,
    SingleWorkspaceAppHost,
)
```

2. Replace the constructor with this shape:

```python
class GUIBackend:
    """GUI 后端服务"""

    def __init__(
        self,
        core: Optional[CoreInterface] = None,
        static_dir: str = "",
        app_host: Optional[GUIAppHost] = None,
    ):
        if app_host is None and core is None:
            raise ValueError("core_or_app_host_required")
        self.static_dir = static_dir
        self.frontend = WebSocketFrontend()
        self.app_host = app_host if app_host is not None else SingleWorkspaceAppHost(core)
        self.app_host.bind_frontend(self.frontend)
        self.app = self._create_app()
        self._current_session_id: Optional[str] = None
```

3. Add a core accessor below `_call_core`:

```python
    def _require_core(self) -> CoreInterface:
        try:
            return self.app_host.require_core()
        except NoActiveWorkspaceError:
            raise HTTPException(status_code=409, detail="no_active_workspace")
```

4. Change lifespan shutdown:

```python
            self.app_host.shutdown()
```

5. Add app routes before `/api/sessions`:

```python
        @app.get("/api/app/bootstrap")
        async def get_app_bootstrap():
            return self.app_host.bootstrap()

        @app.get("/api/app/workspaces")
        async def list_app_workspaces():
            return self.app_host.list_workspaces()

        @app.post("/api/app/workspaces")
        async def open_app_workspace(request: Dict[str, Any]):
            path = str(request.get("path") or "").strip()
            label = str(request.get("label") or "").strip()
            if not path:
                raise HTTPException(status_code=422, detail="workspace_path_required")
            try:
                return self.app_host.open_workspace_path(path, label=label)
            except ValueError as exc:
                detail = str(exc or "").strip() or "workspace_open_failed"
                status = 404 if detail == "workspace_not_found" else 422
                raise HTTPException(status_code=status, detail=detail)

        @app.post("/api/app/workspaces/{workspace_id}/activate")
        async def activate_app_workspace(workspace_id: str):
            try:
                return self.app_host.activate_workspace(workspace_id)
            except ValueError as exc:
                detail = str(exc or "").strip() or "workspace_activate_failed"
                status = 404 if detail == "workspace_not_found" else 422
                raise HTTPException(status_code=status, detail=detail)

        @app.delete("/api/app/workspaces/{workspace_id}")
        async def remove_app_workspace(workspace_id: str):
            return self.app_host.remove_workspace(workspace_id)
```

6. In every workspace-bound route, fetch the active core before calling it. The
   routes that must use `core = self._require_core()` are:

- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/bootstrap`
- `POST /api/sessions`
- `POST /api/sessions/{session_id}/resume`
- `POST /api/sessions/{session_id}/message`
- `POST /api/sessions/{session_id}/cancel`
- `POST /api/sessions/{session_id}/mode`
- `POST /api/sessions/{session_id}/interactions/{interaction_id}/respond`
- `GET /api/workspace`
- `GET /api/workspace/recipes`
- `POST /api/sessions/{session_id}/resources/reload`
- `GET /api/tool-catalog`
- `GET /api/sessions/{session_id}/plan`
- `GET /api/sessions/{session_id}/permissions`
- `GET /api/sessions/{session_id}/events`
- `GET /api/files`
- `GET /api/files/tree`
- `GET /api/files/{path:path}`
- `POST /api/files/{path:path}`
- `POST /api/diff`
- `GET /api/tasks`
- `GET /api/artifacts`
- `GET /api/artifacts/{reference:path}`

The first route should look like this:

```python
        @app.get("/api/sessions")
        async def list_sessions(limit: int = 10):
            core = self._require_core()
            return {"sessions": core.list_sessions(limit)}
```

7. In `_handle_websocket_message`, replace direct `self.core` access with:

```python
        try:
            core = self._require_core()
        except HTTPException:
            return
```

Use `core` for `remember_permission_category` calls.

- [ ] **Step 5: Run app host and existing backend tests**

Run:

```bash
uv run pytest tests/test_gui_app_host.py tests/test_gui_backend_api.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit app host slice**

```bash
git add src/embedagent/frontend/gui/backend/app_host.py src/embedagent/frontend/gui/backend/server.py tests/test_gui_app_host.py tests/test_gui_backend_api.py
git commit -m "feat(gui): add app host workspace routes"
```

---

## Task 3: Launcher No-Workspace Startup

**Files:**
- Modify: `src/embedagent/frontend/gui/launcher.py`
- Create: `tests/test_gui_launcher_app_mode.py`

- [ ] **Step 1: Write failing launcher helper tests**

Create `tests/test_gui_launcher_app_mode.py`:

```python
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.launcher import _resolve_initial_workspace


class TestGuiLauncherAppMode(unittest.TestCase):
    def test_no_workspace_arguments_return_empty_string(self):
        self.assertEqual(_resolve_initial_workspace("", ""), "")

    def test_workspace_argument_is_canonicalized(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = os.path.join(root, "project")
            os.mkdir(workspace)

            resolved = _resolve_initial_workspace(workspace, "")

        self.assertEqual(resolved, os.path.realpath(os.path.abspath(workspace)))

    def test_workspace_option_takes_precedence(self):
        with tempfile.TemporaryDirectory() as root:
            positional = os.path.join(root, "positional")
            option = os.path.join(root, "option")
            os.mkdir(positional)
            os.mkdir(option)

            resolved = _resolve_initial_workspace(option, positional)

        self.assertEqual(resolved, os.path.realpath(os.path.abspath(option)))

    def test_missing_explicit_workspace_raises_value_error(self):
        with tempfile.TemporaryDirectory() as root:
            missing = os.path.join(root, "missing")
            with self.assertRaises(ValueError) as raised:
                _resolve_initial_workspace(missing, "")

        self.assertIn("Workspace not found", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run launcher tests and verify failure**

Run:

```bash
uv run pytest tests/test_gui_launcher_app_mode.py -q
```

Expected: import failure for `_resolve_initial_workspace`.

- [ ] **Step 3: Add launcher helper and app host startup**

Modify `src/embedagent/frontend/gui/launcher.py`:

1. Add helper near `create_core`:

```python
def _resolve_initial_workspace(workspace_option: str = "", workspace_arg: str = "") -> str:
    raw = str(workspace_option or workspace_arg or "").strip()
    if not raw:
        return ""
    workspace = os.path.realpath(os.path.abspath(raw))
    if not os.path.isdir(workspace):
        raise ValueError("Workspace not found: %s" % workspace)
    return workspace
```

2. Change `launch_gui` signature:

```python
def launch_gui(
    workspace: str = "",
```

3. Replace eager core creation with app host creation:

```python
    runtime_config = {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "timeout": timeout,
        "max_turns": max_turns,
        "approve_all": approve_all,
        "approve_writes": approve_writes,
        "approve_commands": approve_commands,
        "permission_rules": permission_rules,
    }

    static_dir = os.path.join(os.path.dirname(__file__), "static")

    from embedagent.frontend.gui.backend.app_host import GUIAppHost
    from embedagent.frontend.gui.backend.server import GUIBackend

    def core_factory(path: str):
        _LOGGER.info("Initializing Agent Core for workspace: %s", path)
        return create_core(path, runtime_config)

    app_host = GUIAppHost(core_factory=core_factory)
    backend = GUIBackend(core=None, static_dir=static_dir, app_host=app_host)
    if workspace:
        app_host.open_workspace_path(workspace)
```

4. Change `finally` cleanup to:

```python
    finally:
        _LOGGER.info("Shutting down...")
        app_host.shutdown()
```

5. Change window title:

```python
        window_title = (
            "EmbedAgent - %s" % os.path.basename(workspace)
            if workspace
            else "EmbedAgent"
        )
```

6. Change `main` workspace resolution:

```python
    try:
        workspace = _resolve_initial_workspace(args.workspace_option, args.workspace)
    except ValueError as exc:
        _LOGGER.error(str(exc))
        return 1
```

Remove the fallback to `os.getcwd()`.

- [ ] **Step 4: Run launcher and backend tests**

Run:

```bash
uv run pytest tests/test_gui_launcher_app_mode.py tests/test_gui_app_host.py tests/test_gui_backend_api.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit launcher slice**

```bash
git add src/embedagent/frontend/gui/launcher.py tests/test_gui_launcher_app_mode.py
git commit -m "feat(gui): allow standalone app startup"
```

---

## Task 4: Frontend Workspace State Helpers

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`
- Create: `src/embedagent/frontend/gui/webapp/test/app-workspaces.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing frontend workspace helper tests**

Create `src/embedagent/frontend/gui/webapp/test/app-workspaces.test.mjs`:

```javascript
import assert from "node:assert/strict";

import {
  canSwitchWorkspace,
  normalizeAppBootstrap,
  normalizeWorkspaceRecord,
  resetWorkspaceScopedState,
} from "../src/app-workspaces.js";

export function runAppWorkspaceTests() {
  const workspace = normalizeWorkspaceRecord({
    id: "ws-1",
    path: "D:/work/demo",
    label: "",
    exists: true,
    created_at: "2026-06-15T10:00:00Z",
    last_opened_at: "2026-06-15T11:00:00Z",
  });
  assert.equal(workspace.id, "ws-1");
  assert.equal(workspace.label, "demo");
  assert.equal(workspace.exists, true);

  const bootstrap = normalizeAppBootstrap({
    workspaces: [workspace],
    active_workspace: workspace,
    has_active_workspace: true,
    last_error: "",
  });
  assert.equal(bootstrap.workspaces.length, 1);
  assert.equal(bootstrap.activeWorkspace.id, "ws-1");
  assert.equal(bootstrap.hasActiveWorkspace, true);

  const idleSwitch = canSwitchWorkspace({
    snapshot: { status: "idle", pending_interaction_valid: false },
  });
  assert.equal(idleSwitch.allowed, true);

  const runningSwitch = canSwitchWorkspace({
    snapshot: { status: "running", pending_interaction_valid: false },
  });
  assert.equal(runningSwitch.allowed, false);
  assert.equal(runningSwitch.reason, "active_thread");

  const pendingSwitch = canSwitchWorkspace({
    snapshot: {
      status: "waiting_user_input",
      pending_interaction_valid: true,
      pending_interaction: { interaction_id: "ask-1" },
    },
  });
  assert.equal(pendingSwitch.allowed, false);
  assert.equal(pendingSwitch.reason, "pending_interaction");

  const reset = resetWorkspaceScopedState({
    sessions: [{ session_id: "sess-1" }],
    currentSessionId: "sess-1",
    snapshot: { session_id: "sess-1" },
    timeline: [{ id: "row-1" }],
    tasks: [{ id: 1 }],
    artifacts: [{ id: "a" }],
    recipes: [{ id: "r" }],
    preview: { title: "README.md" },
    diffSurface: { title: "Diff" },
    fileTree: [{ id: "src" }],
    permissionContext: { session_id: "sess-1" },
    eventLog: [{ label: "old" }],
    activeTurnId: "turn-1",
  });
  assert.deepEqual(reset.sessions, []);
  assert.equal(reset.currentSessionId, "");
  assert.equal(reset.snapshot, null);
  assert.deepEqual(reset.timeline, []);
  assert.deepEqual(reset.tasks, []);
  assert.deepEqual(reset.artifacts, []);
  assert.deepEqual(reset.recipes, []);
  assert.equal(reset.preview, null);
  assert.equal(reset.diffSurface, null);
  assert.deepEqual(reset.fileTree, []);
  assert.equal(reset.permissionContext, null);
  assert.deepEqual(reset.eventLog, []);
  assert.equal(reset.activeTurnId, "");
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runAppWorkspaceTests } from "./app-workspaces.test.mjs";
```

Call it before source-file checks:

```javascript
  runAppWorkspaceTests();
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: import failure for `../src/app-workspaces.js`.

- [ ] **Step 3: Implement workspace helpers**

Create `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`:

```javascript
function basename(path) {
  const text = String(path || "").replace(/\\/g, "/");
  const parts = text.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : text;
}

export function normalizeWorkspaceRecord(input = {}) {
  const path = String(input.path || "");
  const label = String(input.label || "").trim() || basename(path) || path || "Workspace";
  return {
    id: String(input.id || ""),
    path,
    label,
    exists: input.exists !== false,
    created_at: String(input.created_at || ""),
    last_opened_at: String(input.last_opened_at || ""),
  };
}

export function normalizeAppBootstrap(payload = {}) {
  const workspaces = Array.isArray(payload.workspaces)
    ? payload.workspaces.map(normalizeWorkspaceRecord).filter((item) => item.id)
    : [];
  const activeWorkspace = payload.active_workspace
    ? normalizeWorkspaceRecord(payload.active_workspace)
    : null;
  return {
    workspaces,
    activeWorkspace: activeWorkspace && activeWorkspace.id ? activeWorkspace : null,
    hasActiveWorkspace: Boolean(payload.has_active_workspace && activeWorkspace),
    lastError: String(payload.last_error || ""),
  };
}

export function canSwitchWorkspace(state = {}) {
  const snapshot = state.snapshot || {};
  const status = String(snapshot.status || "");
  if (snapshot.pending_interaction_valid && snapshot.pending_interaction) {
    return { allowed: false, reason: "pending_interaction" };
  }
  if (status === "running" || status === "waiting_permission" || status === "waiting_user_input") {
    return { allowed: false, reason: "active_thread" };
  }
  return { allowed: true, reason: "" };
}

export function resetWorkspaceScopedState(state = {}) {
  return {
    ...state,
    sessions: [],
    currentSessionId: "",
    snapshot: null,
    timeline: [],
    streamingAssistantId: "",
    streamingReasoningId: "",
    thinkingActive: false,
    permission: null,
    userInput: null,
    interactionNotice: null,
    tasks: [],
    artifacts: [],
    plan: null,
    review: null,
    recipes: [],
    permissionContext: null,
    preview: null,
    diffSurface: null,
    fileTree: [],
    toolCatalog: {},
    eventLog: [],
    terminationReason: "",
    terminationDisplayReason: "",
    terminationMessage: "",
    turnsUsed: 0,
    activeTurnId: "",
    activeStepId: "",
    activeStepIndex: 0,
    historyIntegrity: null,
  };
}
```

- [ ] **Step 4: Run frontend helper tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: all frontend helper tests pass.

- [ ] **Step 5: Commit helper slice**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-workspaces.js src/embedagent/frontend/gui/webapp/test/app-workspaces.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat(gui): add workspace state helpers"
```

---

## Task 5: Frontend App Bootstrap And Workspace Activation

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing reducer/source checks**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, add reducer checks after the existing `initialState` assertion:

```javascript
  assert.equal(initialState.app.bootstrapLoaded, false);
  assert.equal(initialState.app.hasActiveWorkspace, false);
  assert.equal(initialState.app.activeWorkspace, null);

  const appLoadedState = reducer(initialState, {
    type: "app_bootstrap_loaded",
    bootstrap: {
      workspaces: [
        {
          id: "ws-1",
          path: "D:/work/demo",
          label: "demo",
          exists: true,
          created_at: "",
          last_opened_at: "",
        },
      ],
      activeWorkspace: {
        id: "ws-1",
        path: "D:/work/demo",
        label: "demo",
        exists: true,
        created_at: "",
        last_opened_at: "",
      },
      hasActiveWorkspace: true,
      lastError: "",
    },
  });
  assert.equal(appLoadedState.app.bootstrapLoaded, true);
  assert.equal(appLoadedState.app.activeWorkspace.id, "ws-1");
  assert.equal(appLoadedState.app.hasActiveWorkspace, true);

  const switchedWorkspaceState = reducer(
    {
      ...appLoadedState,
      currentSessionId: "sess-old",
      sessions: [{ session_id: "sess-old" }],
      timeline: [{ id: "row-old" }],
      fileTree: [{ id: "src" }],
    },
    {
      type: "workspace_switched",
      bootstrap: {
        workspaces: [],
        activeWorkspace: null,
        hasActiveWorkspace: false,
        lastError: "",
      },
    },
  );
  assert.equal(switchedWorkspaceState.currentSessionId, "");
  assert.deepEqual(switchedWorkspaceState.sessions, []);
  assert.deepEqual(switchedWorkspaceState.timeline, []);
  assert.deepEqual(switchedWorkspaceState.fileTree, []);
  assert.equal(switchedWorkspaceState.app.hasActiveWorkspace, false);
```

Add source checks near the existing `appSource` assertions:

```javascript
  assert.equal(appSource.includes("loadAppBootstrap"), true);
  assert.equal(appSource.includes("openWorkspace"), true);
  assert.equal(appSource.includes("activateWorkspace"), true);
  assert.equal(appSource.includes("workspace_changed"), true);
  assert.equal(appSource.includes("no_active_workspace"), true);
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: failure because `initialState.app` and app bootstrap actions are not present.

- [ ] **Step 3: Extend store state and reducer**

Modify `src/embedagent/frontend/gui/webapp/src/store.js`:

1. Add import:

```javascript
import { normalizeAppBootstrap, resetWorkspaceScopedState } from "./app-workspaces.js";
```

2. Add this field to `initialState`:

```javascript
  app: {
    bootstrapLoaded: false,
    workspaces: [],
    activeWorkspace: null,
    hasActiveWorkspace: false,
    workspacePathInput: "",
    workspaceError: "",
    activatingWorkspace: false,
  },
```

3. Add reducer cases before session cases:

```javascript
    case "app_bootstrap_loaded": {
      const bootstrap = normalizeAppBootstrap(action.bootstrap || {});
      return {
        ...state,
        app: {
          ...state.app,
          bootstrapLoaded: true,
          workspaces: bootstrap.workspaces,
          activeWorkspace: bootstrap.activeWorkspace,
          hasActiveWorkspace: bootstrap.hasActiveWorkspace,
          workspaceError: bootstrap.lastError || "",
          activatingWorkspace: false,
        },
      };
    }
    case "workspace_path_changed":
      return {
        ...state,
        app: {
          ...state.app,
          workspacePathInput: action.value || "",
          workspaceError: "",
        },
      };
    case "workspace_activation_started":
      return {
        ...state,
        app: {
          ...state.app,
          activatingWorkspace: true,
          workspaceError: "",
        },
      };
    case "workspace_activation_failed":
      return {
        ...state,
        app: {
          ...state.app,
          activatingWorkspace: false,
          workspaceError: action.error || "workspace_open_failed",
        },
      };
    case "workspace_switched": {
      const bootstrap = normalizeAppBootstrap(action.bootstrap || {});
      const reset = resetWorkspaceScopedState(state);
      return {
        ...reset,
        app: {
          ...reset.app,
          bootstrapLoaded: true,
          workspaces: bootstrap.workspaces,
          activeWorkspace: bootstrap.activeWorkspace,
          hasActiveWorkspace: bootstrap.hasActiveWorkspace,
          workspacePathInput: "",
          workspaceError: bootstrap.lastError || "",
          activatingWorkspace: false,
        },
      };
    }
```

- [ ] **Step 4: Refactor App.jsx data loading**

Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`:

1. Import helper:

```javascript
import { canSwitchWorkspace, normalizeAppBootstrap } from "./app-workspaces.js";
```

2. Replace the initial data-load effect with:

```javascript
  useEffect(() => {
    loadAppBootstrap();
  }, []);
```

3. Add app bootstrap functions above `loadSessions`:

```javascript
  async function loadAppBootstrap() {
    const payload = await fetchJson("/api/app/bootstrap");
    const bootstrap = normalizeAppBootstrap(payload || {});
    dispatch({ type: "app_bootstrap_loaded", bootstrap });
    if (bootstrap.hasActiveWorkspace) {
      await loadActiveWorkspaceData("");
    }
    return bootstrap;
  }

  async function loadActiveWorkspaceData(sessionId = state.currentSessionId || "") {
    await Promise.all([
      loadSessions(),
      loadArtifacts(),
      loadTasks(sessionId || ""),
      loadFileChildren("."),
      loadToolCatalog(),
      loadWorkspaceRecipes(),
    ]);
  }

  function workspaceErrorFrom(error) {
    return String(error?.detail || error?.message || "workspace_open_failed");
  }

  async function openWorkspace(path) {
    const targetPath = String(path || state.app.workspacePathInput || "").trim();
    if (!targetPath) {
      dispatch({ type: "workspace_activation_failed", error: "workspace_path_required" });
      return;
    }
    const switchState = canSwitchWorkspace(state);
    if (!switchState.allowed) {
      dispatch({ type: "workspace_activation_failed", error: switchState.reason });
      return;
    }
    dispatch({ type: "workspace_activation_started" });
    try {
      const payload = await fetchJson("/api/app/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: targetPath }),
      });
      const bootstrap = normalizeAppBootstrap(payload || {});
      dispatch({ type: "workspace_switched", bootstrap });
      if (bootstrap.hasActiveWorkspace) {
        await loadActiveWorkspaceData("");
      }
    } catch (error) {
      dispatch({ type: "workspace_activation_failed", error: workspaceErrorFrom(error) });
    }
  }

  async function activateWorkspace(workspaceId) {
    const switchState = canSwitchWorkspace(state);
    if (!switchState.allowed) {
      dispatch({ type: "workspace_activation_failed", error: switchState.reason });
      return;
    }
    dispatch({ type: "workspace_activation_started" });
    try {
      const payload = await fetchJson(
        `/api/app/workspaces/${encodeURIComponent(workspaceId)}/activate`,
        { method: "POST" },
      );
      const bootstrap = normalizeAppBootstrap(payload || {});
      dispatch({ type: "workspace_switched", bootstrap });
      if (bootstrap.hasActiveWorkspace) {
        await loadActiveWorkspaceData("");
      }
    } catch (error) {
      dispatch({ type: "workspace_activation_failed", error: workspaceErrorFrom(error) });
    }
  }

  async function removeWorkspace(workspaceId) {
    const payload = await fetchJson(`/api/app/workspaces/${encodeURIComponent(workspaceId)}`, {
      method: "DELETE",
    });
    const bootstrap = normalizeAppBootstrap(payload || {});
    dispatch({ type: "workspace_switched", bootstrap });
    if (bootstrap.hasActiveWorkspace) {
      await loadActiveWorkspaceData("");
    }
  }
```

4. Update `fetchJson` so `detail` can be non-string:

```javascript
      const detail = typeof payload?.detail === "string" ? payload.detail : JSON.stringify(payload?.detail || "");
      const error = new Error(detail || `HTTP ${res.status}`);
      error.status = res.status;
      error.detail = detail;
```

5. In `handleSocketMessage`, add:

```javascript
    if (type === "workspace_changed") {
      const bootstrap = normalizeAppBootstrap(data || {});
      dispatch({ type: "workspace_switched", bootstrap });
      if (bootstrap.hasActiveWorkspace) {
        void loadActiveWorkspaceData("");
      }
      return;
    }
```

6. In `submitText`, guard no active workspace:

```javascript
    if (!state.app.hasActiveWorkspace) {
      dispatch({ type: "workspace_activation_failed", error: "no_active_workspace" });
      return;
    }
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: reducer and source checks pass.

- [ ] **Step 6: Commit frontend bootstrap slice**

```bash
git add src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat(gui): load app workspace bootstrap"
```

---

## Task 6: T3-Style Workspace And Thread Sidebar

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/strings.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing source checks for UI contract**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, add source checks:

```javascript
  const noWorkspaceSource = fs.readFileSync(
    webappSourcePath("components", "NoWorkspaceState.jsx"),
    "utf8",
  );
  assert.equal(noWorkspaceSource.includes('data-testid="no-workspace-state"'), true);
  assert.equal(noWorkspaceSource.includes('data-testid="workspace-path-input"'), true);
  assert.equal(noWorkspaceSource.includes('data-testid="open-workspace-button"'), true);

  const sidebarSource = fs.readFileSync(
    webappSourcePath("components", "Sidebar.jsx"),
    "utf8",
  );
  assert.equal(sidebarSource.includes('data-testid="workspace-switcher"'), true);
  assert.equal(sidebarSource.includes('data-testid="workspace-row--'), true);
  assert.equal(sidebarSource.includes('data-testid="thread-list"'), true);
  assert.equal(sidebarSource.includes("Threads"), true);
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: missing `NoWorkspaceState.jsx` and sidebar source checks fail.

- [ ] **Step 3: Create NoWorkspaceState component**

Create `src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx`:

```javascript
import React from "react";

export default function NoWorkspaceState({
  value,
  error,
  activating,
  workspaces = [],
  onChange,
  onOpen,
  onActivate,
}) {
  return (
    <section className="no-workspace" data-testid="no-workspace-state">
      <div className="no-workspace-inner">
        <div className="no-workspace-title">Open a workspace</div>
        <div className="no-workspace-subtitle">
          Select a local project folder to start managing threads.
        </div>
        <form
          className="workspace-open-form"
          onSubmit={(event) => {
            event.preventDefault();
            onOpen(value);
          }}
        >
          <input
            data-testid="workspace-path-input"
            className="workspace-path-input"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="D:\\work\\my-c-project"
            spellCheck={false}
          />
          <button
            data-testid="open-workspace-button"
            className="primary"
            type="submit"
            disabled={activating}
          >
            Open
          </button>
        </form>
        {error ? <div className="workspace-error">{error}</div> : null}
        {workspaces.length > 0 ? (
          <div className="recent-workspaces">
            <div className="recent-workspaces-title">Recent workspaces</div>
            {workspaces.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                className="recent-workspace-row"
                disabled={!workspace.exists || activating}
                onClick={() => onActivate(workspace.id)}
              >
                <span>{workspace.label}</span>
                <small>{workspace.path}</small>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Replace Sidebar with workspace/thread hierarchy**

Modify `src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx`:

1. Add props:

```javascript
  app,
  workspacePathInput,
  onWorkspacePathChange,
  onOpenWorkspace,
  onActivateWorkspace,
  onRemoveWorkspace,
```

2. Render a workspace switcher after the brand:

```javascript
      <div className="workspace-switcher" data-testid="workspace-switcher">
        <div className="workspace-current">
          <span className="workspace-current-label">
            {app?.activeWorkspace?.label || "No workspace"}
          </span>
          <span className="workspace-current-path">
            {app?.activeWorkspace?.path || "Open a local project"}
          </span>
        </div>
        <form
          className="workspace-mini-form"
          onSubmit={(event) => {
            event.preventDefault();
            onOpenWorkspace(workspacePathInput);
          }}
        >
          <input
            data-testid="sidebar-workspace-path-input"
            value={workspacePathInput}
            onChange={(event) => onWorkspacePathChange(event.target.value)}
            placeholder="Workspace path"
            spellCheck={false}
          />
          <button type="submit" disabled={app?.activatingWorkspace}>Open</button>
        </form>
        {app?.workspaceError ? (
          <div className="workspace-error compact">{app.workspaceError}</div>
        ) : null}
        <div className="workspace-list">
          {(app?.workspaces || []).map((workspace) => (
            <div
              key={workspace.id}
              className={`workspace-row ${app?.activeWorkspace?.id === workspace.id ? "active" : ""}`}
              data-testid={`workspace-row--${workspace.id}`}
            >
              <button
                type="button"
                disabled={!workspace.exists || app?.activatingWorkspace}
                onClick={() => onActivateWorkspace(workspace.id)}
              >
                <span>{workspace.label}</span>
                <small>{workspace.exists ? workspace.path : "Missing path"}</small>
              </button>
              <button
                type="button"
                className="workspace-remove"
                aria-label={`Remove ${workspace.label}`}
                onClick={() => onRemoveWorkspace(workspace.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>
```

3. Change the chats tab label to `Threads` and thread list marker:

```javascript
        <button
          role="tab"
          aria-selected={sidebarTab === "chats"}
          className={`sidebar-tab${sidebarTab === "chats" ? " active" : ""}`}
          onClick={() => onTabChange("chats")}
          data-testid="sidebar-tab--threads"
        >
          Threads
        </button>
```

4. Change the list container:

```javascript
          <div className="thread-list" role="list" data-testid="thread-list">
```

5. Keep existing `data-testid="new-session-btn"` compatibility by adding a
   second hidden-free marker inside the same button:

```jsx
          <button
            className="primary wide"
            onClick={() => onCreateSession(currentMode)}
            data-testid="new-session-btn"
          >
            <span data-testid="new-thread-btn">New Thread</span>
          </button>
```

- [ ] **Step 5: Wire NoWorkspaceState and Sidebar props in App.jsx**

Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`:

1. Add import:

```javascript
import NoWorkspaceState from "./components/NoWorkspaceState.jsx";
```

2. Pass app props to `Sidebar`:

```javascript
          app={state.app}
          workspacePathInput={state.app.workspacePathInput}
          onWorkspacePathChange={(value) => dispatch({ type: "workspace_path_changed", value })}
          onOpenWorkspace={openWorkspace}
          onActivateWorkspace={activateWorkspace}
          onRemoveWorkspace={removeWorkspace}
```

3. Replace `main={...}` with conditional main:

```javascript
      main={
        state.app.hasActiveWorkspace ? (
          <main className="main-chat">
            <Timeline
              ref={timelineRef}
              timeline={runtimeState.timelineView}
              rows={runtimeState.t3TimelineRows}
              toolCatalog={state.toolCatalog}
              historyIntegrity={state.historyIntegrity}
              thinkingActive={state.thinkingActive}
              streamingReasoningId={state.streamingReasoningId}
              terminationReason={state.terminationReason}
              terminationDisplayReason={state.terminationDisplayReason}
              terminationMessage={state.terminationMessage}
              turnsUsed={state.turnsUsed}
              maxTurns={state.maxTurns}
              onScroll={handleTimelineScroll}
              onOpenDiff={openDiffSurface}
            />
            <Composer
              value={state.composer}
              onChange={(value) => dispatch({ type: "set_composer", value })}
              onSend={sendMessage}
              onStop={cancelSession}
              isRunning={currentStatus === "running" || currentStatus === "waiting_user_input"}
              currentMode={currentMode}
              commandHints={SLASH_COMMAND_HINTS}
              onOpenCommandPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
              interaction={runtimeState.currentInteraction}
              interactionNotice={interactionNotice}
              answerValue={userAnswer}
              onAnswerChange={setUserAnswer}
              onRespondInteraction={respondToInteraction}
            />
          </main>
        ) : (
          <NoWorkspaceState
            value={state.app.workspacePathInput}
            error={state.app.workspaceError}
            activating={state.app.activatingWorkspace}
            workspaces={state.app.workspaces}
            onChange={(value) => dispatch({ type: "workspace_path_changed", value })}
            onOpen={openWorkspace}
            onActivate={activateWorkspace}
          />
        )
      }
```

- [ ] **Step 6: Show active workspace in header**

Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx`:

1. Add prop:

```javascript
  activeWorkspace,
```

2. Render a compact label near the mode/status cluster:

```javascript
      {activeWorkspace ? (
        <span className="workspace-header-label" title={activeWorkspace.path}>
          {activeWorkspace.label}
        </span>
      ) : null}
```

3. Pass it from `App.jsx`:

```javascript
          activeWorkspace={state.app.activeWorkspace}
```

- [ ] **Step 7: Add CSS for compact app navigation**

Append to `src/embedagent/frontend/gui/webapp/src/styles.css`:

```css
.workspace-switcher {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 10px 12px;
  border-bottom: 1px solid var(--border);
}

.workspace-current {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.workspace-current-label,
.workspace-row span,
.recent-workspace-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-current-path,
.workspace-row small,
.recent-workspace-row small {
  overflow: hidden;
  color: var(--muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-mini-form,
.workspace-open-form {
  display: flex;
  gap: 8px;
  min-width: 0;
}

.workspace-mini-form input,
.workspace-path-input {
  min-width: 0;
  flex: 1;
}

.workspace-list,
.recent-workspaces {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.workspace-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px;
  align-items: center;
  gap: 4px;
}

.workspace-row > button:first-child,
.recent-workspace-row {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: stretch;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}

.workspace-row.active > button:first-child {
  color: var(--text);
  font-weight: 600;
}

.workspace-remove {
  width: 24px;
  height: 24px;
}

.workspace-error {
  color: var(--danger);
  font-size: 12px;
}

.workspace-error.compact {
  line-height: 1.3;
}

.no-workspace {
  display: grid;
  min-height: 100%;
  place-items: center;
  padding: 24px;
}

.no-workspace-inner {
  width: min(560px, 100%);
}

.no-workspace-title {
  font-size: 22px;
  font-weight: 650;
}

.no-workspace-subtitle {
  margin-top: 6px;
  color: var(--muted);
}

.workspace-header-label {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

- [ ] **Step 8: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: all tests pass.

- [ ] **Step 9: Commit UI slice**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx src/embedagent/frontend/gui/webapp/src/strings.js src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat(gui): add workspace thread app shell"
```

---

## Task 7: Workspace Commands

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`

- [ ] **Step 1: Add failing command tests**

Modify `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`:

```javascript
  assert.equal(COMMAND_GROUPS.includes("workspace"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.open"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.refresh"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.remove_current"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "thread.new"), true);
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: workspace command assertions fail.

- [ ] **Step 3: Add workspace commands**

Modify `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`:

1. Add `"workspace"` to `COMMAND_GROUPS`.

2. Add command entries:

```javascript
  {
    id: "workspace.open",
    group: "workspace",
    title: "Open Workspace",
    keywords: ["project", "folder"],
  },
  {
    id: "workspace.refresh",
    group: "workspace",
    title: "Refresh Workspaces",
    keywords: ["reload", "recent"],
  },
  {
    id: "workspace.remove_current",
    group: "workspace",
    title: "Remove Current Workspace From Recents",
    keywords: ["forget", "recent"],
  },
  {
    id: "thread.new",
    group: "session",
    title: "New Thread",
    keywords: ["session", "chat"],
  },
```

3. In `visibleCommands`, hide `workspace.remove_current` when `context.hasWorkspace` is false:

```javascript
    if (item.id === "workspace.remove_current" && !context.hasWorkspace) return false;
```

- [ ] **Step 4: Handle commands in App.jsx**

Modify `executeWorkbenchCommand` in `src/embedagent/frontend/gui/webapp/src/App.jsx`:

```javascript
    if (command.id === "workspace.open") {
      dispatch({ type: "set_sidebar", value: "chats" });
      window.setTimeout(() => {
        document.querySelector('[data-testid="sidebar-workspace-path-input"]')?.focus();
      }, 0);
      return;
    }
    if (command.id === "workspace.refresh") {
      await loadAppBootstrap();
      return;
    }
    if (command.id === "workspace.remove_current") {
      if (state.app.activeWorkspace?.id) {
        await removeWorkspace(state.app.activeWorkspace.id);
      }
      return;
    }
    if (command.id === "thread.new") {
      await createSession(currentMode);
      return;
    }
```

Update `CommandPalette` context:

```javascript
        hasWorkspace: Boolean(state.app.hasActiveWorkspace),
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: all tests pass.

- [ ] **Step 6: Commit command slice**

```bash
git add src/embedagent/frontend/gui/webapp/src/workbench/commands.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs
git commit -m "feat(gui): add workspace commands"
```

---

## Task 8: App Visual Debug Scenario

**Files:**
- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`

- [ ] **Step 1: Add failing visual runner tests**

Modify `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`:

```javascript
  assert.deepEqual(runner.parseScenarioList("all"), ["app", "load", "chat", "diff", "responsive"]);
  assert.deepEqual(runner.parseScenarioList("app"), ["app"]);
  assert.deepEqual(runner.parseScenarioList("load,app"), ["app", "load"]);
```

Add launch config check:

```javascript
  const appLaunch = runner.buildGuiLaunchConfig({
    repoRoot: "C:/repo",
    workspace: "",
    port: 54321,
    mode: "build",
    baseUrl: "http://127.0.0.1:45678/v1",
    model: "visual-debug-model",
    timeout: 9,
    maxTurns: 3,
    bundleRoot: "",
    python: "C:/python/python.exe",
  });
  assert.equal(appLaunch.args.includes("--workspace"), false);
```

- [ ] **Step 2: Run frontend tests and verify failure**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: parse scenario assertion fails.

- [ ] **Step 3: Add app scenario support**

Modify `scripts/gui-visual-debug.mjs`:

1. Change scenarios:

```javascript
export const SCENARIOS = ["load", "chat", "diff", "responsive", "app"];
```

2. Update `parseScenarioList` so any mixed app run starts with app activation:

```javascript
  const unique = Array.from(new Set(scenarios));
  if (unique.includes("app")) {
    return ["app", ...unique.filter((item) => item !== "app")];
  }
  return unique;
```

3. Change `buildGuiLaunchConfig` args construction:

```javascript
  const args = ["-m", "embedagent.frontend.gui.launcher"];
  if (workspace) {
    args.push("--workspace", workspace);
  }
  args.push(
    "--mode",
    mode,
    "--model",
    model,
    "--base-url",
    baseUrl,
    "--port",
    String(port),
    "--timeout",
    String(timeout),
    "--max-turns",
    String(maxTurns),
    "--headless",
    "--auto-close-seconds",
    "300",
  );
```

Return `args` instead of the current literal array.

4. Add app scenario runner:

```javascript
async function runAppScenario(page, options) {
  const first = options.appWorkspaceA;
  const second = options.appWorkspaceB;
  await page.waitForSelector('[data-testid="no-workspace-state"]', { timeout: 10000 });
  await page.fill('[data-testid="workspace-path-input"]', first);
  await page.click('[data-testid="open-workspace-button"]');
  await page.waitForSelector('[data-testid="workbench-layout"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="workspace-switcher"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="thread-list"]', { timeout: 10000 });
  await page.fill('[data-testid="sidebar-workspace-path-input"]', second);
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    (expectedPath) => document.body.innerText.includes(expectedPath),
    second,
    { timeout: 10000 },
  );
  const staleSessionSelected = await page.locator(".thread-card.selected").count();
  return {
    openedFirstWorkspace: true,
    switchedSecondWorkspace: true,
    staleSessionSelected,
  };
}
```

5. In `runScenarios`, add:

```javascript
      } else if (scenario === "app") {
        results.app = await runAppScenario(page, options);
```

6. In `runVisualDebug`, create separate app workspaces and launch without a workspace when the app scenario is present:

```javascript
  const scenarios = parseScenarioList(options.scenario);
  const appWorkspaceA = createWorkspace(
    path.join(os.tmpdir(), `embedagent-gui-app-a-${Date.now()}`),
  );
  const appWorkspaceB = scenarios.includes("diff")
    ? createDiffWorkspace(
        path.join(os.tmpdir(), `embedagent-gui-app-b-${Date.now()}`),
        resolveGitExecutable({ bundleRoot: options.bundleRoot }),
      )
    : createWorkspace(path.join(os.tmpdir(), `embedagent-gui-app-b-${Date.now()}`));
  const launchWorkspace = scenarios.includes("app") ? "" : workspace;
```

Use `launchWorkspace` in `buildGuiLaunchConfig`. When `app` is mixed with
`diff`, the app scenario ends on the second workspace, which is prepared as the
diff workspace so later `diff` checks still see `demo.c`.

Include the app workspaces in the summary:

```javascript
    appWorkspaces: {
      first: appWorkspaceA,
      second: appWorkspaceB,
    },
```

Pass them into `runScenarios`:

```javascript
    const run = await runScenarios(
      { ...options, port, appWorkspaceA, appWorkspaceB },
      repoRoot,
      outputDir,
    );
```

7. Update help:

```text
  --scenario load|chat|diff|responsive|app|all
```

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: all tests pass.

- [ ] **Step 5: Run app visual debug**

Run from repo root:

```bash
npm --prefix src/embedagent/frontend/gui/webapp run build
node scripts/gui-visual-debug.mjs --scenario app --output build/gui-visual-app --no-build
```

Expected:
- summary JSON contains `"app"` under `results`
- at least one screenshot path is listed
- `console.count` is `0`

- [ ] **Step 6: Commit visual debug slice**

```bash
git add scripts/gui-visual-debug.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs
git commit -m "test(gui): add app workspace visual scenario"
```

---

## Task 9: Full Verification And Static Asset Build

**Files:**
- Modify: `src/embedagent/frontend/gui/static/assets/app.css`
- Modify: `src/embedagent/frontend/gui/static/assets/app.js`

- [ ] **Step 1: Build static frontend assets**

Run:

```bash
npm --prefix src/embedagent/frontend/gui/webapp run build
```

Expected: static assets under `src/embedagent/frontend/gui/static/assets/` update.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: all frontend helper tests pass.

- [ ] **Step 3: Run focused backend tests**

Run:

```bash
uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q
```

Expected: all focused GUI backend tests pass.

- [ ] **Step 4: Run fast non-GUI test suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run visual debug scenarios**

Run:

```bash
node scripts/gui-visual-debug.mjs --scenario app,load,chat,responsive --output build/gui-visual-standalone --no-build
```

Expected:
- app scenario validates no-workspace and workspace switch states
- load scenario validates workbench layout
- chat scenario gets the fake model reply
- responsive scenario produces screenshots for configured viewports
- console warning/error count is `0`

If a prepared diff workspace and bundled git are available, also run:

```bash
node scripts/gui-visual-debug.mjs --scenario diff --output build/gui-visual-diff --no-build
```

Expected: diff panel shows `demo.c` and the changed `return 1` line.

- [ ] **Step 6: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 7: Commit final built assets and verification adjustments**

```bash
git add src/embedagent/frontend/gui/static/assets/app.css src/embedagent/frontend/gui/static/assets/app.js
git status --short
git commit -m "build(gui): refresh standalone app assets"
```

If `git status --short` shows additional intentional files from earlier tasks, include them in the same commit only when they are part of this feature.

---

## Final Review Checklist

- [ ] `python -m embedagent.frontend.gui.launcher --headless --port 0 --model visual-debug-model --base-url http://127.0.0.1:1/v1` starts the app shell far enough to serve `/`.
- [ ] Launching without `--workspace` does not attempt to create `AgentCoreAdapter`.
- [ ] Launching with `--workspace PATH` still activates that workspace automatically.
- [ ] `/api/app/bootstrap` works with and without an active workspace.
- [ ] `/api/sessions` returns `409 no_active_workspace` before activation and normal session data after activation.
- [ ] Workspace switching shuts down the previous core exactly once.
- [ ] Frontend displays `NoWorkspaceState` before activation.
- [ ] Sidebar shows current workspace, recent workspaces, thread rows, and file tree for the active workspace.
- [ ] Running/pending thread state blocks workspace switching in the frontend.
- [ ] Visual debug captures app state screenshots without console warnings/errors.
- [ ] No new runtime dependency breaks Windows 7, offline deployment, or Python 3.8 syntax constraints.
