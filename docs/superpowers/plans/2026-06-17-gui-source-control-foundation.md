# GUI Source Control Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a T3 Code-style, GUI-hosted, read-only local source-control changes surface for the active workspace.

**Architecture:** The GUI backend owns a workspace-bound `SourceControlService` that invokes only read-only Git commands through the bundled/workspace MinGit path. The frontend owns source-control display state and opens the existing Diff right-panel for selected files; Agent Core, transcript truth, workflow truth, permission policy, runtime reducers, checkpoint state, and remote providers remain uninvolved.

**Tech Stack:** Python 3.8 stdlib (`os`, `subprocess`, `time`, `re`), existing FastAPI GUI backend, React 18, existing plain CSS, existing diff2html-backed `DiffPanel`, existing webapp Node test runner.

---

## File Structure

- Create `src/embedagent/frontend/gui/backend/source_control_service.py`
  - Workspace-bound read-only Git service, command runner, porcelain parser, local provider detection, per-file diff payloads.
- Modify `src/embedagent/frontend/gui/backend/server.py`
  - Inject/lazily create `SourceControlService`, expose app-level source-control routes, map errors.
- Modify `src/embedagent/frontend/gui/backend/app_shell.py`
  - Advertise `source_control` capability and right-panel surface metadata.
- Create `tests/test_gui_source_control_service.py`
  - Pure service tests with fake command runner.
- Create `tests/test_gui_source_control_api.py`
  - Direct FastAPI route endpoint tests with fake service and active-workspace host.
- Modify `tests/test_gui_app_shell.py`
  - Lock source-control capability metadata.
- Create `src/embedagent/frontend/gui/webapp/src/source-control/source-control-state.js`
  - Normalize status/diff payloads and reduce frontend-local source-control state.
- Create `src/embedagent/frontend/gui/webapp/src/source-control/source-control-api.js`
  - Fetch wrappers for status, refresh, and diff routes.
- Create `src/embedagent/frontend/gui/webapp/src/source-control/source-control-presentation.js`
  - Group files and format status/provider labels.
- Create `src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx`
  - T3 Code-like local changes panel.
- Modify `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - Normalize `capabilities.source_control`.
- Modify `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - Add `source_control` to right-panel surfaces.
- Modify `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - Add command palette entry for source control.
- Modify `src/embedagent/frontend/gui/webapp/src/store.js`
  - Add `sourceControl` state and reducer action delegation.
- Modify `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`
  - Reset source-control state on workspace switch.
- Modify `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - Render `SourceControlPanel` when `inspectorTab === "source_control"`.
- Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  - Add tab label for source control.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Wire status loading, refresh, diff selection, command execution, and workspace events.
- Create `src/embedagent/frontend/gui/webapp/test/source-control-state.test.mjs`
  - Frontend pure state and presentation tests.
- Modify frontend tests:
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/app-workspaces.test.mjs`
- Modify `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Compact source-control panel styling.
- Rebuild generated static assets under `src/embedagent/frontend/gui/static/` after frontend changes.
- Update source-of-truth docs and archive this slice after implementation:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`

---

### Task 1: Backend Source-Control Service

**Files:**
- Create: `tests/test_gui_source_control_service.py`
- Create: `src/embedagent/frontend/gui/backend/source_control_service.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_gui_source_control_service.py` with these test helpers and cases:

```python
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.source_control_service import SourceControlService


class FakeRunner(object):
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    def __call__(self, command, cwd, timeout_sec, max_output_bytes, env):
        self.calls.append((list(command), cwd, timeout_sec, max_output_bytes, dict(env or {})))
        if self.responses:
            return dict(self.responses.pop(0))
        return {"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False, "truncated": False}


class SourceControlServiceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-source-control-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))

    def service(self, responses):
        return SourceControlService(
            workspace_root=self.workspace,
            git_executable="git.exe",
            command_runner=FakeRunner(responses),
        )

    def test_git_unavailable_returns_safe_status(self):
        service = SourceControlService(
            workspace_root=self.workspace,
            git_executable="",
            command_runner=FakeRunner(),
        )

        status = service.status()

        self.assertEqual(status["git_available"], False)
        self.assertEqual(status["is_repo"], False)
        self.assertEqual(status["counts"]["total"], 0)
        self.assertEqual(status["files"], [])

    def test_not_a_repo_is_not_fatal(self):
        service = self.service([
            {"exit_code": 128, "stdout": "", "stderr": "fatal: not a git repository", "timed_out": False, "truncated": False},
        ])

        status = service.status()

        self.assertEqual(status["git_available"], True)
        self.assertEqual(status["is_repo"], False)
        self.assertEqual(status["diagnostics"]["warnings"], ["not_a_repo"])

    def test_status_parses_changed_files_and_counts(self):
        service = self.service([
            {"exit_code": 0, "stdout": "## main...origin/main\n M src/main.c\nA  include/api.h\n?? notes.txt\nUU conflict.c\n", "stderr": "", "timed_out": False, "truncated": False},
            {"exit_code": 0, "stdout": "abcdef1\n", "stderr": "", "timed_out": False, "truncated": False},
            {"exit_code": 0, "stdout": "https://github.com/example/demo.git\n", "stderr": "", "timed_out": False, "truncated": False},
            {"exit_code": 0, "stdout": "12\t3\tsrc/main.c\n5\t0\tinclude/api.h\n-\t-\tnotes.txt\n", "stderr": "", "timed_out": False, "truncated": False},
        ])

        status = service.status()

        self.assertEqual(status["is_repo"], True)
        self.assertEqual(status["branch"], "main")
        self.assertEqual(status["head"], "abcdef1")
        self.assertEqual(status["provider"]["kind"], "github")
        self.assertEqual(status["counts"]["unstaged"], 1)
        self.assertEqual(status["counts"]["staged"], 1)
        self.assertEqual(status["counts"]["untracked"], 1)
        self.assertEqual(status["counts"]["conflicted"], 1)
        self.assertEqual(status["counts"]["total"], 4)
        self.assertEqual(status["files"][0]["path"], "src/main.c")
        self.assertEqual(status["files"][0]["group"], "unstaged")
        self.assertEqual(status["files"][0]["insertions"], 12)
        self.assertEqual(status["files"][0]["deletions"], 3)

    def test_diff_rejects_workspace_escape_and_invalid_scope(self):
        service = self.service([])

        with self.assertRaises(ValueError) as raised:
            service.diff("../outside.c")
        self.assertEqual(str(raised.exception), "path_outside_workspace")

        with self.assertRaises(ValueError) as raised:
            service.diff("src/main.c", scope="remote")
        self.assertEqual(str(raised.exception), "invalid_diff_scope")

    def test_diff_returns_payload(self):
        service = self.service([
            {"exit_code": 0, "stdout": "diff --git a/src/main.c b/src/main.c\n--- a/src/main.c\n+++ b/src/main.c\n@@ -1 +1 @@\n-old\n+new\n", "stderr": "", "timed_out": False, "truncated": False},
        ])

        payload = service.diff("src/main.c", scope="unstaged")

        self.assertEqual(payload["available"], True)
        self.assertEqual(payload["path"], "src/main.c")
        self.assertEqual(payload["scope"], "unstaged")
        self.assertEqual(payload["file_count"], 1)
        self.assertEqual(payload["line_count"], 6)
        self.assertIn("diff --git", payload["diff"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_gui_source_control_service.py -v
```

Expected: FAIL because `embedagent.frontend.gui.backend.source_control_service` does not exist.

- [ ] **Step 3: Implement `source_control_service.py`**

Create `src/embedagent/frontend/gui/backend/source_control_service.py` with these concrete behaviors:

- Define constants:
  - `STATUS_TIMEOUT_SEC = 5`
  - `DIFF_TIMEOUT_SEC = 10`
  - `MAX_STATUS_OUTPUT_BYTES = 512 * 1024`
  - `MAX_DIFF_OUTPUT_BYTES = 1024 * 1024`
  - `ALLOWED_DIFF_SCOPES = ("unstaged", "staged")`
- Define `_utc_now()` with `time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())`.
- Define `default_command_runner(command, cwd, timeout_sec, max_output_bytes, env)` using `subprocess.Popen(..., shell=False, universal_newlines=True, encoding="utf-8", errors="replace")`, `communicate(timeout=timeout_sec)`, timeout kill, and output truncation.
- Define `SourceControlService.__init__(workspace_root, git_executable=None, command_runner=None, env_builder=None, runtime_source="")`.
- Resolve `self.workspace_root = os.path.realpath(workspace_root)`.
- If `git_executable` is not supplied, use a private `_resolve_git_executable()` that checks:
  - `%EMBEDAGENT_BUNDLE_ROOT%/bin/git/cmd/git.exe`
  - `%EMBEDAGENT_BUNDLE_ROOT%/bin/git/bin/git.exe`
  - `<workspace>/bin/git/cmd/git.exe`
  - `<workspace>/bin/git/bin/git.exe`
  - `"git"` only when `EMBEDAGENT_ALLOW_SYSTEM_TOOL_FALLBACK` is truthy.
- Implement `_resolve_path(path, allow_missing=True)` with the same realpath/normcase workspace containment rule used by `ToolContext`.
- Implement `_run_git(args, timeout_sec, max_output_bytes)` to call the runner with `[self.git_executable, "-C", self.workspace_root] + args`.
- Implement `status()` using only:
  - `git status --short --branch`
  - `git rev-parse --short HEAD`
  - `git remote get-url origin`
  - `git diff --numstat`
  - `git diff --cached --numstat`
- Implement `diff(path, scope="unstaged")` using only:
  - `git diff -- <path>` for unstaged
  - `git diff --cached -- <path>` for staged
- Return `git_available: false` when Git is missing instead of raising.
- Return `is_repo: false` when status stderr contains `not a git repository`.
- Raise `ValueError("path_outside_workspace")` for path escape.
- Raise `ValueError("invalid_diff_scope")` for unsupported scope.
- Parse status lines into staged, unstaged, untracked, and conflicted groups.
- Parse numstat lines into insertion/deletion maps, treating `-` as binary.
- Detect local provider from remote URL hosts for github/gitlab/azure-devops/bitbucket/unknown without network calls.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_gui_source_control_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit backend service**

Run:

```bash
git add src/embedagent/frontend/gui/backend/source_control_service.py tests/test_gui_source_control_service.py
git commit -m "gui: add source control service"
```

---

### Task 2: Backend Routes And App-Shell Capability

**Files:**
- Create: `tests/test_gui_source_control_api.py`
- Modify: `tests/test_gui_app_shell.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/gui/backend/app_shell.py`

- [ ] **Step 1: Write failing API and app-shell tests**

Create `tests/test_gui_source_control_api.py`:

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


def route(app, path, method):
    for item in app.routes:
        if getattr(item, "path", "") == path and method in getattr(item, "methods", set()):
            return item
    raise AssertionError("route not found: %s %s" % (method, path))


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


class FakeSourceControlService(object):
    def __init__(self):
        self.calls = []

    def status(self):
        self.calls.append(("status",))
        return {
            "workspace_root": "D:/workspace",
            "git_available": True,
            "is_repo": True,
            "branch": "main",
            "files": [],
            "counts": {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0, "total": 0},
        }

    def diff(self, path, scope="unstaged"):
        self.calls.append(("diff", path, scope))
        return {
            "workspace_root": "D:/workspace",
            "path": path,
            "scope": scope,
            "available": True,
            "binary": False,
            "diff": "diff --git a/%s b/%s\n" % (path, path),
            "file_count": 1,
            "line_count": 1,
            "truncated": False,
            "reason": "",
        }


class GuiSourceControlApiTests(unittest.TestCase):
    def make_backend(self, workspace, service):
        static_dir = os.path.join(workspace, "static")
        os.mkdir(static_dir)
        with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
            handle.write("<html><body>ok</body></html>")
        registry = WorkspaceRegistry(storage_path=os.path.join(workspace, "workspaces.json"))
        host = GUIAppHost(core_factory=lambda path: FakeCore(path), registry=registry)
        backend = GUIBackend(
            app_host=host,
            static_dir=static_dir,
            source_control_service=service,
        )
        backend.app_shell.open_workspace_path(workspace)
        return backend

    def test_routes_call_source_control_service(self):
        with tempfile.TemporaryDirectory() as workspace:
            service = FakeSourceControlService()
            backend = self.make_backend(workspace, service)

            status = asyncio.run(
                route(backend.app, "/api/app/source-control/status", "GET").endpoint()
            )
            self.assertEqual(status["source_control"]["branch"], "main")

            refreshed = asyncio.run(
                route(backend.app, "/api/app/source-control/refresh", "POST").endpoint()
            )
            self.assertEqual(refreshed["source_control"]["is_repo"], True)

            diff = asyncio.run(
                route(backend.app, "/api/app/source-control/diff", "GET").endpoint(
                    path="src/main.c",
                    scope="staged",
                )
            )
            self.assertEqual(diff["diff"]["path"], "src/main.c")
            self.assertIn(("diff", "src/main.c", "staged"), service.calls)

    def test_routes_require_active_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            static_dir = os.path.join(workspace, "static")
            os.mkdir(static_dir)
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            registry = WorkspaceRegistry(storage_path=os.path.join(workspace, "workspaces.json"))
            host = GUIAppHost(core_factory=lambda path: FakeCore(path), registry=registry)
            backend = GUIBackend(
                app_host=host,
                static_dir=static_dir,
                source_control_service=FakeSourceControlService(),
            )

            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route(backend.app, "/api/app/source-control/status", "GET").endpoint())

            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(raised.exception.detail, "no_active_workspace")

    def test_error_mapping_for_invalid_diff(self):
        class FailingService(FakeSourceControlService):
            def diff(self, path, scope="unstaged"):
                raise ValueError("invalid_diff_scope")

        with tempfile.TemporaryDirectory() as workspace:
            backend = self.make_backend(workspace, FailingService())

            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    route(backend.app, "/api/app/source-control/diff", "GET").endpoint(
                        path="src/main.c",
                        scope="remote",
                    )
                )

            self.assertEqual(raised.exception.status_code, 422)
            self.assertEqual(raised.exception.detail, "invalid_diff_scope")
```

Modify `tests/test_gui_app_shell.py` in `test_bootstrap_without_workspace_includes_shell_fields`:

```python
self.assertIn("source_control", payload["capabilities"]["surfaces"]["right_panel"])
self.assertEqual(
    payload["capabilities"]["source_control"],
    {
        "enabled": True,
        "vcs": ["git"],
        "read_only": True,
        "remote_providers": False,
        "network": False,
        "checkpoints": False,
        "requires_active_workspace": True,
    },
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_gui_source_control_api.py tests/test_gui_app_shell.py -v
```

Expected: FAIL because `GUIBackend` lacks `source_control_service`, routes, and capability metadata.

- [ ] **Step 3: Implement backend wiring**

Modify `src/embedagent/frontend/gui/backend/app_shell.py`:

- Add `"source_control"` to `capabilities["surfaces"]["right_panel"]`.
- Add:

```python
"source_control": {
    "enabled": True,
    "vcs": ["git"],
    "read_only": True,
    "remote_providers": False,
    "network": False,
    "checkpoints": False,
    "requires_active_workspace": True,
},
```

Modify `src/embedagent/frontend/gui/backend/server.py`:

- Import `SourceControlService`.
- Add `source_control_service=None` to `GUIBackend.__init__`.
- Store `_source_control_service`, `_source_control_workspace_root`, and `_injected_source_control_service`.
- Add `_source_control()` that:
  - calls `self._require_core()` to require active workspace
  - reads active workspace path from `core.workspace`
  - reuses injected service when provided
  - lazily creates `SourceControlService(workspace_root=workspace)` when workspace changes
- Add `_source_control_http_error(exc)`:
  - `invalid_diff_scope` and `path_outside_workspace` -> 422
  - everything else -> 422 `source_control_failed` unless already `HTTPException`
- Add routes:
  - `GET /api/app/source-control/status`
  - `POST /api/app/source-control/refresh`
  - `GET /api/app/source-control/diff`
- Return payload keys exactly:
  - `{"source_control": service.status()}`
  - `{"diff": service.diff(path, scope=scope)}`

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_gui_source_control_api.py tests/test_gui_app_shell.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit backend routes and capability**

Run:

```bash
git add src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/gui/backend/app_shell.py tests/test_gui_source_control_api.py tests/test_gui_app_shell.py
git commit -m "gui: add source control backend routes"
```

---

### Task 3: Frontend Capability, Commands, And Workbench Surface

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`

- [ ] **Step 1: Write failing frontend metadata tests**

Update `app-shell-model.test.mjs`:

```js
assert.equal(initial.capabilities.sourceControl.enabled, false);
assert.equal(initial.capabilities.sourceControl.readOnly, true);
```

Inside the bootstrap fixture capabilities, add:

```js
source_control: {
  enabled: true,
  vcs: ["git"],
  read_only: true,
  remote_providers: false,
  network: false,
  checkpoints: false,
  requires_active_workspace: true,
},
```

Then assert:

```js
assert.equal(bootstrap.capabilities.surfaces.rightPanel.includes("source_control"), true);
assert.equal(bootstrap.capabilities.sourceControl.enabled, true);
assert.deepEqual(bootstrap.capabilities.sourceControl.vcs, ["git"]);
assert.equal(bootstrap.capabilities.sourceControl.readOnly, true);
assert.equal(bootstrap.capabilities.sourceControl.remoteProviders, false);
assert.equal(bootstrap.capabilities.sourceControl.network, false);
assert.equal(bootstrap.capabilities.sourceControl.checkpoints, false);
assert.equal(bootstrap.capabilities.sourceControl.requiresActiveWorkspace, true);
```

Update `workbench-state.test.mjs` to assert:

```js
assert.equal(RIGHT_PANEL_SURFACES.includes("source_control"), true);
assert.equal(commandById("surface.source_control").surface, "source_control");
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

Expected: FAIL because source-control frontend metadata is not normalized and the command does not exist.

- [ ] **Step 3: Implement capability and command metadata**

Modify `app-shell/model.js`:

- Add `normalizeSourceControlCapability(input = {})`.
- Read `input.source_control` or `input.sourceControl`.
- Return:

```js
{
  enabled: value.enabled === true,
  vcs: Array.isArray(value.vcs) ? value.vcs.map(String) : [],
  readOnly: value.read_only !== false && value.readOnly !== false,
  remoteProviders: value.remote_providers === true || value.remoteProviders === true,
  network: value.network === true,
  checkpoints: value.checkpoints === true,
  requiresActiveWorkspace:
    value.requires_active_workspace === true || value.requiresActiveWorkspace === true,
}
```

- Add `sourceControl: normalizeSourceControlCapability(input)` to `normalizeAppCapabilities`.

Modify `workbench/surfaces.js`:

- Insert `"source_control"` into `RIGHT_PANEL_SURFACES` near `diff`.

Modify `workbench/commands.js`:

- Add:

```js
{ id: "surface.source_control", group: "surface", label: "Open Source Control", slash: "", surface: "source_control", visibleWhen: "always", keywords: ["git", "changes", "diff"] },
```

Modify `RightPanelTabs.jsx`:

- Add `source_control: "Source"` to `LABELS`.

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

Expected: PASS.

- [ ] **Step 5: Commit frontend metadata**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/app-shell/model.js src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js src/embedagent/frontend/gui/webapp/src/workbench/commands.js src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs
git commit -m "gui: add source control frontend metadata"
```

---

### Task 4: Frontend Source-Control State And API

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/source-control/source-control-state.js`
- Create: `src/embedagent/frontend/gui/webapp/src/source-control/source-control-api.js`
- Create: `src/embedagent/frontend/gui/webapp/src/source-control/source-control-presentation.js`
- Create: `src/embedagent/frontend/gui/webapp/test/source-control-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/app-workspaces.test.mjs`

- [ ] **Step 1: Write failing state tests**

Create `webapp/test/source-control-state.test.mjs`:

```js
import assert from "node:assert/strict";

import {
  createSourceControlState,
  groupSourceControlFiles,
  normalizeSourceControlDiff,
  normalizeSourceControlStatus,
  reduceSourceControlState,
} from "../src/source-control/source-control-state.js";
import {
  fileStatusLabel,
  providerLabel,
} from "../src/source-control/source-control-presentation.js";

export function runSourceControlStateTests() {
  const initial = createSourceControlState();
  assert.equal(initial.status, "idle");
  assert.equal(initial.data.gitAvailable, false);
  assert.equal(initial.selectedPath, "");

  const normalized = normalizeSourceControlStatus({
    git_available: true,
    is_repo: true,
    branch: "main",
    provider: { kind: "github", name: "GitHub", base_url: "https://github.com" },
    counts: { staged: 1, unstaged: 1, untracked: 1, conflicted: 0, total: 3 },
    files: [
      { path: "src/main.c", group: "unstaged", status: "modified", insertions: 2, deletions: 1, diff_scopes: ["unstaged"] },
      { path: "include/api.h", group: "staged", status: "added", insertions: 5, deletions: 0, diff_scopes: ["staged"] },
      { path: "notes.txt", group: "untracked", status: "untracked", insertions: 0, deletions: 0, diff_scopes: [] },
    ],
  });
  assert.equal(normalized.gitAvailable, true);
  assert.equal(normalized.isRepo, true);
  assert.equal(normalized.branch, "main");
  assert.equal(normalized.provider.kind, "github");
  assert.equal(normalized.counts.total, 3);
  assert.equal(normalized.files[0].path, "src/main.c");

  const grouped = groupSourceControlFiles(normalized.files);
  assert.equal(grouped.unstaged[0].path, "src/main.c");
  assert.equal(grouped.staged[0].path, "include/api.h");
  assert.equal(grouped.untracked[0].path, "notes.txt");
  assert.equal(grouped.conflicted.length, 0);

  let state = reduceSourceControlState(initial, { type: "source_control_load_started" });
  assert.equal(state.status, "loading");
  state = reduceSourceControlState(state, {
    type: "source_control_status_loaded",
    status: normalized,
  });
  assert.equal(state.status, "ready");
  assert.equal(state.selectedPath, "src/main.c");
  state = reduceSourceControlState(state, {
    type: "source_control_file_selected",
    path: "include/api.h",
    scope: "staged",
  });
  assert.equal(state.selectedPath, "include/api.h");
  assert.equal(state.selectedScope, "staged");

  const diff = normalizeSourceControlDiff({
    path: "include/api.h",
    scope: "staged",
    available: true,
    binary: false,
    diff: "diff --git a/include/api.h b/include/api.h\n",
    file_count: 1,
    line_count: 1,
    truncated: false,
    reason: "",
  });
  state = reduceSourceControlState(state, {
    type: "source_control_diff_loaded",
    diff,
  });
  assert.equal(state.diff.path, "include/api.h");
  assert.equal(state.diff.available, true);

  assert.equal(fileStatusLabel({ status: "modified" }), "M");
  assert.equal(providerLabel(normalized.provider), "GitHub");
}
```

Update `run-tests.mjs`:

```js
import { runSourceControlStateTests } from "./source-control-state.test.mjs";
```

and call `runSourceControlStateTests();` with the other model tests.

Update `app-workspaces.test.mjs` so a workspace reset clears `sourceControl` back to idle.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

Expected: FAIL because `source-control` modules do not exist.

- [ ] **Step 3: Implement source-control state modules**

Create `source-control/source-control-state.js`:

- `createSourceControlState()` returns:

```js
{
  status: "idle",
  error: "",
  data: normalizeSourceControlStatus({}),
  selectedPath: "",
  selectedScope: "unstaged",
  diffStatus: "idle",
  diffError: "",
  diff: normalizeSourceControlDiff({}),
}
```

- `normalizeSourceControlStatus(payload)` converts snake_case to camelCase and defaults missing data.
- `normalizeSourceControlFile(file)` keeps `path`, `displayPath`, `status`, `indexStatus`, `worktreeStatus`, `group`, `insertions`, `deletions`, `binary`, `diffScopes`.
- `groupSourceControlFiles(files)` returns `{ staged: [], unstaged: [], untracked: [], conflicted: [] }`.
- `normalizeSourceControlDiff(payload)` returns `available`, `binary`, `diff`, `fileCount`, `lineCount`, `truncated`, `reason`.
- `reduceSourceControlState(state, action)` handles:
  - `source_control_load_started`
  - `source_control_status_loaded`
  - `source_control_load_failed`
  - `source_control_file_selected`
  - `source_control_diff_started`
  - `source_control_diff_loaded`
  - `source_control_diff_failed`
  - `source_control_reset`

Create `source-control/source-control-presentation.js`:

- `providerLabel(provider)` returns provider name, provider kind, or `"Local Git"`.
- `fileStatusLabel(file)` maps `modified -> M`, `added -> A`, `deleted -> D`, `renamed -> R`, `untracked -> U`, `conflicted -> C`.
- `groupLabel(group)` maps groups to `Staged`, `Changes`, `Untracked`, `Conflicts`.

Create `source-control/source-control-api.js`:

```js
import { fetchJson } from "../api.js";

export function fetchSourceControlStatus() {
  return fetchJson("/api/app/source-control/status");
}

export function refreshSourceControlStatus() {
  return fetchJson("/api/app/source-control/refresh", { method: "POST" });
}

export function fetchSourceControlDiff(path, scope = "unstaged") {
  const query = new URLSearchParams({ path: String(path || ""), scope: String(scope || "unstaged") });
  return fetchJson(`/api/app/source-control/diff?${query.toString()}`);
}
```

Modify `store.js`:

- Import `createSourceControlState` and `reduceSourceControlState`.
- Add `sourceControl: createSourceControlState()` to `initialState`.
- Delegate all `source_control_*` actions to `reduceSourceControlState`.

Modify `app-workspaces.js`:

- Import `createSourceControlState`.
- Add `sourceControl: createSourceControlState()` to `resetWorkspaceScopedState`.

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

Expected: PASS.

- [ ] **Step 5: Commit frontend state**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/source-control src/embedagent/frontend/gui/webapp/test/source-control-state.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/app-workspaces.js src/embedagent/frontend/gui/webapp/test/app-workspaces.test.mjs
git commit -m "gui: add source control frontend model"
```

---

### Task 5: Source-Control Panel UI And App Wiring

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify generated static assets under `src/embedagent/frontend/gui/static/`

- [ ] **Step 1: Implement panel component**

Create `components/source-control/SourceControlPanel.jsx` with:

- Header showing branch/provider/runtime state.
- Refresh button.
- Empty states for:
  - loading
  - git unavailable
  - not a repo
  - clean tree
  - error
- Grouped file sections from `groupSourceControlFiles`.
- File buttons with:
  - status label from `fileStatusLabel`
  - path
  - `+insertions` and `-deletions`
  - active class when selected
- Props:

```js
export default function SourceControlPanel({
  sourceControl,
  onRefresh,
  onSelectFile,
})
```

- On file click, call `onSelectFile(file, file.diffScopes?.[0] || "unstaged")`.

- [ ] **Step 2: Wire Inspector**

Modify `Inspector.jsx`:

- Import `SourceControlPanel`.
- Add props:
  - `sourceControl`
  - `onRefreshSourceControl`
  - `onSelectSourceControlFile`
- Render:

```jsx
{inspectorTab === "source_control" && (
  <SourceControlPanel
    sourceControl={sourceControl}
    onRefresh={onRefreshSourceControl}
    onSelectFile={onSelectSourceControlFile}
  />
)}
```

- [ ] **Step 3: Wire App data loading and commands**

Modify `App.jsx`:

- Import source-control API helpers.
- Add `loadSourceControlStatus(refresh = false)`:
  - dispatch `source_control_load_started`
  - call `refreshSourceControlStatus()` when `refresh` is true, otherwise `fetchSourceControlStatus()`
  - dispatch `source_control_status_loaded` with `payload.source_control`
  - dispatch `source_control_load_failed` with message on error
- Add `openSourceControlFile(file, scope)`:
  - dispatch selected file action
  - dispatch diff started
  - fetch diff
  - dispatch diff loaded
  - if available and has diff text, dispatch `diff_surface_opened` using `createDiffSurfaceState({ title: "Git Diff: " + file.path, diff: payload.diff.diff, source: "source-control", filePath: file.path })`
  - set inspector to `diff`
  - if unavailable, keep source-control selected and dispatch diff failed with reason
- On `workspace_changed`, after workspace switch, call `loadSourceControlStatus()` when active workspace exists.
- On initial app bootstrap with active workspace, call `loadSourceControlStatus()`.
- In `executeWorkbenchCommand`, when command id is `surface.source_control`:
  - set inspector to `source_control`
  - activate right surface
  - call `loadSourceControlStatus()`
- Pass new props to `Inspector`.

- [ ] **Step 4: Add CSS**

Modify `styles.css` with classes:

- `.source-control-panel`
- `.source-control-header`
- `.source-control-meta`
- `.source-control-actions`
- `.source-control-group`
- `.source-control-group-title`
- `.source-control-file`
- `.source-control-file.active`
- `.source-control-status`
- `.source-control-path`
- `.source-control-stats`

Use existing neutral tokens only. Keep border radius at `var(--r-sm)` or less for compact controls. Do not introduce gradient/orb decoration or a new one-hue palette.

- [ ] **Step 5: Build frontend assets**

Run:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
cd src/embedagent/frontend/gui/webapp && npm run build
```

Expected: both PASS and generated static assets update if build output changes.

- [ ] **Step 6: Commit UI wiring**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/source-control src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/static
git commit -m "gui: wire source control surface"
```

---

### Task 6: Documentation And Slice Archive

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/modules/frontend-gui.md`
- Move: `docs/superpowers/specs/2026-06-17-gui-source-control-foundation-design.md`
- Move: `docs/superpowers/plans/2026-06-17-gui-source-control-foundation.md`
- Create: `docs/archive/gui-source-control-foundation/`

- [ ] **Step 1: Update source-of-truth docs**

Document these facts consistently:

- GUI source control is an app-shell hosted, active-workspace surface.
- It is read-only and local-only in this slice.
- It uses bundled/workspace MinGit through a GUI backend service.
- It does not write transcript history, workflow state, telemetry, permission state, runtime reducers, provider config, extension loading, or checkpoint truth.
- It does not implement remote providers, push/pull, PR/MR/change-request, staging, commit, or checkpoint mutation.
- Win7/offline/Python 3.8 constraints remain unchanged.

- [ ] **Step 2: Update frontend protocol docs**

Add app-level routes:

```text
GET /api/app/source-control/status
POST /api/app/source-control/refresh
GET /api/app/source-control/diff?path=<path>&scope=<scope>
```

Add capability metadata shape for `source_control`.

- [ ] **Step 3: Archive slice docs**

Create:

```text
docs/archive/gui-source-control-foundation/
```

Move:

```text
docs/superpowers/specs/2026-06-17-gui-source-control-foundation-design.md
docs/superpowers/plans/2026-06-17-gui-source-control-foundation.md
```

into the archive directory after docs are synchronized.

- [ ] **Step 4: Commit docs**

Run:

```bash
git add README.md AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md docs/frontend-protocol.md docs/modules/frontend-gui.md docs/archive/gui-source-control-foundation docs/superpowers
git commit -m "docs: document gui source control boundary"
```

---

### Task 7: Final Verification And Boundary Audit

**Files:**
- No planned source edits.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
uv run pytest tests/test_gui_source_control_service.py tests/test_gui_source_control_api.py tests/test_gui_app_shell.py -v
```

Expected: PASS.

- [ ] **Step 2: Run lint**

Run:

```bash
uv run ruff check src/embedagent/frontend/gui/backend/source_control_service.py src/embedagent/frontend/gui/backend/server.py tests/test_gui_source_control_service.py tests/test_gui_source_control_api.py tests/test_gui_app_shell.py
```

Expected: PASS.

- [ ] **Step 3: Run frontend checks**

Run:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
cd src/embedagent/frontend/gui/webapp && npm run build
```

Expected: PASS.

- [ ] **Step 4: Run fast pytest suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS.

- [ ] **Step 5: Audit Agent Core boundary**

Run:

```bash
git diff --name-only 26ca7c7...HEAD -- src/embedagent/query_engine.py src/embedagent/agent_loop.py src/embedagent/agent_tool_action_service.py src/embedagent/extensions.py src/embedagent/permissions.py
```

Expected: no output.

- [ ] **Step 6: Audit dependency and Win7 constraints**

Run:

```bash
git diff -- pyproject.toml uv.lock package.json src/embedagent/frontend/gui/webapp/package.json scripts/offline-runtime-contract.json
```

Expected: no dependency additions. `scripts/offline-runtime-contract.json` remains unchanged because Git is already a bundled runtime tool.

- [ ] **Step 7: Final status**

Run:

```bash
git status --short
git log --oneline -8
```

Expected: worktree clean after all commits. Log includes service, backend routes, frontend metadata, frontend model, UI wiring, and docs commits.

