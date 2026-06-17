# GUI App Shell Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a T3 Code-style GUI-local app shell boundary that owns app bootstrap, workspace registry projection, host/runtime diagnostics, app-level settings, and app-level commands without moving Agent Core responsibilities into the GUI.

**Architecture:** Introduce a small `AppShellService` behind the existing GUI backend. It wraps `GUIAppHost` and exposes a credential-free app-shell read model. Frontend state moves from ad hoc `app` fields to pure app-shell normalization/reducer helpers. Agent Core remains the authority for sessions, transcript history, workflow state, modes, tools, permissions, provider snapshots, and extension execution.

**Tech Stack:** Python 3.8, FastAPI, pywebview host diagnostics, React 18, Vite/Node ESM tests, existing GUI source-contract tests.

---

## Boundary Contract

The first app-shell payload shape is:

```json
{
  "app": {
    "shell_version": 1,
    "product_name": "EmbedAgent",
    "protocol": "gui_app_shell_v1"
  },
  "workspaces": [],
  "active_workspace": null,
  "has_active_workspace": false,
  "diagnostics": {
    "host": {},
    "runtime": {},
    "renderer": {},
    "workspace_registry": {},
    "active_core": {}
  },
  "capabilities": {
    "app_commands": ["app.settings", "app.diagnostics", "app.reload"],
    "workspace_commands": ["workspace.open", "workspace.refresh", "workspace.remove_current"],
    "surfaces": {
      "right_panel": ["settings", "diagnostics"]
    }
  },
  "settings": {
    "confirm_workspace_switch": true,
    "show_diagnostics_badge": true
  },
  "last_error": ""
}
```

Rules:

- `AppShellService` may call `GUIAppHost` and inspect safe host/runtime metadata.
- `AppShellService` must not call workspace-bound session/history APIs.
- The payload must not include API keys, prompt bodies, source files, raw tool outputs, permission payload secrets, or transcript entries.
- App-level settings in this slice are frontend-local defaults; they do not become Agent Core runtime policy.
- Workspace switching still clears workspace-scoped frontend state through the existing root-store reset behavior.

---

## File Structure

**Create**

- `src/embedagent/frontend/gui/backend/app_shell.py`
- `tests/test_gui_app_shell.py`
- `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
- `src/embedagent/frontend/gui/webapp/src/app-shell/reducer.js`
- `src/embedagent/frontend/gui/webapp/src/app-shell/commands.js`
- `src/embedagent/frontend/gui/webapp/src/app-shell/diagnostics.js`
- `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`

**Modify**

- `src/embedagent/frontend/gui/backend/server.py`
- `src/embedagent/frontend/gui/launcher.py`
- `tests/test_gui_app_host.py`
- `tests/test_gui_backend_api.py`
- `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`
- `src/embedagent/frontend/gui/webapp/src/store.js`
- `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
- `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- `src/embedagent/frontend/gui/webapp/src/App.jsx`
- `src/embedagent/frontend/gui/webapp/src/strings.js`
- `src/embedagent/frontend/gui/webapp/src/styles.css`
- `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
- `docs/frontend-protocol.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

**Do Not Modify**

- `src/embedagent/query_engine.py`
- `src/embedagent/inprocess_adapter.py`
- `src/embedagent/agent_loop.py`
- `src/embedagent/agent_tool_action_service.py`
- `src/embedagent/extensions.py`
- Harness workflow package ownership, mode registry access, permission policy, or transcript reducers.

---

## Task 1: Backend App-Shell Read Model

**Files:**

- Create: `src/embedagent/frontend/gui/backend/app_shell.py`
- Create: `tests/test_gui_app_shell.py`

- [ ] **Step 1: Write failing backend service tests**

Create `tests/test_gui_app_shell.py` with focused `unittest` cases:

- `test_bootstrap_without_workspace_includes_shell_fields`
- `test_open_workspace_returns_app_shell_payload_and_binds_core`
- `test_removed_workspace_payload_keeps_shell_fields`
- `test_bootstrap_excludes_session_history_and_secret_fields`

Test assertions:

- `payload["app"]["shell_version"] == 1`
- `payload["app"]["protocol"] == "gui_app_shell_v1"`
- `payload["capabilities"]["app_commands"]` includes `app.settings`, `app.diagnostics`, and `app.reload`
- `payload["capabilities"]["surfaces"]["right_panel"]` includes `settings` and `diagnostics`
- `payload["diagnostics"]` includes `host`, `runtime`, `renderer`, `workspace_registry`, and `active_core`
- no serialized text contains `api_key`, `sk-`, `prompt`, `transcript`, `tool_output`, or fake secret values
- opening a workspace still creates exactly one core and registers the frontend through `GUIAppHost`

Run to confirm failure:

```bash
uv run pytest tests/test_gui_app_shell.py -v
```

- [ ] **Step 2: Implement `AppShellService`**

Create `src/embedagent/frontend/gui/backend/app_shell.py`.

Required implementation details:

- Keep Python 3.8 syntax only.
- Define `APP_SHELL_VERSION = 1`.
- Define a small secret-key denylist such as `api_key`, `authorization`, `token`, `secret`, `password`, and `key`.
- Add `_safe_mapping(value)` that recursively copies dict/list/scalar values while dropping denylisted keys.
- Add `AppShellService.__init__(self, app_host, host_diagnostics=None, settings=None)`.
- Add methods:
  - `bootstrap(self) -> Dict[str, Any]`
  - `list_workspaces(self) -> Dict[str, Any]`
  - `open_workspace_path(self, path: str, label: str = "") -> Dict[str, Any]`
  - `activate_workspace(self, workspace_id: str) -> Dict[str, Any]`
  - `remove_workspace(self, workspace_id: str) -> Dict[str, Any]`
- App/workspace methods delegate to `GUIAppHost`, then return a full app-shell payload.
- Preserve existing workspace-host behavior by using `GUIAppHost` as the only workspace/core owner.

Payload helpers:

- `_base_payload(self, raw=None, last_error="")`
- `_app_metadata(self)`
- `_capabilities(self)`
- `_settings(self)`
- `_diagnostics(self)`

Diagnostics should include only safe local read-model data:

- host platform/headless/debug if provided
- runtime source/path presence if provided, with paths allowed but secrets removed
- renderer metadata if provided
- workspace registry count and active workspace id/path if available from `GUIAppHost.bootstrap()`
- active core present flag, not core internals

- [ ] **Step 3: Verify backend service tests**

```bash
uv run pytest tests/test_gui_app_shell.py -v
```

- [ ] **Step 4: Commit Task 1**

```bash
git status --short
git add src/embedagent/frontend/gui/backend/app_shell.py tests/test_gui_app_shell.py
git commit -m "gui: add app shell read model"
```

---

## Task 2: Route GUI App Bootstrap Through AppShellService

**Files:**

- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/gui/launcher.py`
- Modify: `tests/test_gui_app_host.py`
- Modify: `tests/test_gui_backend_api.py`
- Modify: `tests/test_gui_app_shell.py`

- [ ] **Step 1: Extend route tests before implementation**

Add or update tests so existing `/api/app/*` route expectations include app-shell fields:

- `/api/app/bootstrap` returns `app`, `diagnostics`, `capabilities`, and `settings`.
- `/api/app/workspaces` returns the same app-shell envelope, not only a raw workspace list.
- `POST /api/app/workspaces`, `POST /api/app/workspaces/{workspace_id}/activate`, and `DELETE /api/app/workspaces/{workspace_id}` preserve existing workspace activation semantics while returning the envelope.
- Workspace-bound routes such as `/api/sessions` still return `409 no_active_workspace` when there is no active workspace.

Run expected failures:

```bash
uv run pytest tests/test_gui_app_shell.py tests/test_gui_app_host.py tests/test_gui_backend_api.py -v
```

- [ ] **Step 2: Wire `GUIBackend` to `AppShellService`**

In `src/embedagent/frontend/gui/backend/server.py`:

- Import `AppShellService`.
- Extend `GUIBackend.__init__` with optional `host_diagnostics: Optional[Dict[str, Any]] = None`.
- After `self.app_host.bind_frontend(...)`, create:

```python
self.app_shell = AppShellService(
    self.app_host,
    host_diagnostics=host_diagnostics or {},
)
```

- Update app routes:
  - `GET /api/app/bootstrap` -> `self.app_shell.bootstrap()`
  - `GET /api/app/workspaces` -> `self.app_shell.list_workspaces()`
  - `POST /api/app/workspaces` -> `self.app_shell.open_workspace_path(path, label=label)`
  - `POST /api/app/workspaces/{workspace_id}/activate` -> `self.app_shell.activate_workspace(workspace_id)`
  - `DELETE /api/app/workspaces/{workspace_id}` -> `self.app_shell.remove_workspace(workspace_id)`
- Preserve current `ValueError` to `HTTPException` mapping for workspace route failures.

- [ ] **Step 3: Pass host diagnostics from launcher**

In `src/embedagent/frontend/gui/launcher.py`:

- Build a safe `host_diagnostics` dict after `runtime_info` is known.
- Include:
  - `host`: platform, headless, debug, server host, server port
  - `runtime`: existing `runtime_info`
  - `renderer`: renderer metadata once detected
- Because renderer detection currently happens after backend construction, use one mutable dict and update it after `_detect_windows_renderer()`:

```python
host_diagnostics = {
    "host": {
        "platform": sys.platform,
        "headless": bool(headless),
        "debug": bool(debug),
        "server_host": host,
        "server_port": int(port),
    },
    "runtime": runtime_info,
    "renderer": {},
}
backend = GUIBackend(
    core=None,
    static_dir=static_dir,
    app_host=app_host,
    host_diagnostics=host_diagnostics,
)
...
renderer_info = _detect_windows_renderer()
renderer_info.update(runtime_info)
host_diagnostics["renderer"] = renderer_info
```

The service must sanitize this mutable dict at serialization time.

- [ ] **Step 4: Verify route behavior**

```bash
uv run pytest tests/test_gui_app_shell.py tests/test_gui_app_host.py tests/test_gui_backend_api.py -v
```

- [ ] **Step 5: Commit Task 2**

```bash
git status --short
git add src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/gui/launcher.py tests/test_gui_app_shell.py tests/test_gui_app_host.py tests/test_gui_backend_api.py
git commit -m "gui: expose app shell bootstrap"
```

---

## Task 3: Frontend App-Shell Model And Reducer Helpers

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
- Create: `src/embedagent/frontend/gui/webapp/src/app-shell/reducer.js`
- Create: `src/embedagent/frontend/gui/webapp/src/app-shell/diagnostics.js`
- Create: `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/app-workspaces.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing frontend model tests**

Create `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs` with tests for:

- `createAppShellState()` returns defaults for app metadata, settings, capabilities, diagnostics, workspace status, and loading flags.
- `normalizeAppBootstrap(payload)` accepts snake_case backend keys and returns camelCase frontend state.
- `normalizeAppBootstrap(payload)` sanitizes denylisted diagnostic keys.
- `reduceAppShellState(state, { type: "app_shell_bootstrap_loaded", bootstrap })` updates only app-shell state.
- `reduceAppShellState(state, { type: "app_shell_settings_changed", patch })` merges known settings and ignores unknown keys.
- `resetAppShellWorkspaceState(state)` clears active workspace flags but preserves settings/capabilities/diagnostics.
- `formatDiagnosticsRows(diagnostics)` returns stable key/value rows grouped by host/runtime/renderer/workspace/core.

Update `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` to import and run the new tests.

Run expected failure:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

- [ ] **Step 2: Implement `app-shell/model.js`**

Required exports:

- `createAppShellState()`
- `normalizeWorkspaceRecord(input = {})`
- `normalizeAppBootstrap(payload = {})`
- `normalizeAppSettings(input = {})`
- `normalizeAppCapabilities(input = {})`
- `normalizeAppDiagnostics(input = {})`

Implementation notes:

- Move the existing basename/workspace normalization from `app-workspaces.js` into this module.
- Keep JS plain ESM; no new dependencies.
- Use a frontend denylist matching backend secret key intent.
- Return stable defaults when backend payloads are missing fields.
- Keep backend names (`active_workspace`, `has_active_workspace`) converted to frontend names (`activeWorkspace`, `hasActiveWorkspace`) only inside frontend model state.

- [ ] **Step 3: Implement `app-shell/reducer.js`**

Required exports:

- `reduceAppShellState(state, action)`
- `resetAppShellWorkspaceState(state)`

Handle these action types:

- `app_shell_bootstrap_loaded`
- `app_shell_workspace_path_changed`
- `app_shell_workspace_activation_started`
- `app_shell_workspace_activation_failed`
- `app_shell_workspace_switched`
- `app_shell_settings_changed`

Important boundary:

- `resetAppShellWorkspaceState` operates only on the app-shell object.
- The root-store workspace reset remains in `app-workspaces.js`, because it clears sessions, timeline, permissions, tasks, artifacts, and other workspace-scoped GUI state.

- [ ] **Step 4: Implement `app-shell/diagnostics.js`**

Required export:

- `formatDiagnosticsRows(diagnostics)`

Rules:

- Return rows shaped as `{ group, key, label, value }`.
- Flatten only simple safe values.
- Render arrays as comma-separated values and objects as compact JSON strings.
- Keep row ordering stable for source tests and predictable UI rendering.

- [ ] **Step 5: Convert `app-workspaces.js` into compatibility glue**

In `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`:

- Re-export `normalizeWorkspaceRecord` and `normalizeAppBootstrap` from `./app-shell/model.js`.
- Keep `canSwitchWorkspace(state)` locally because it inspects root session state.
- Keep `resetWorkspaceScopedState(state)` locally and preserve the existing behavior that clears workspace-scoped root fields.
- Do not make `resetWorkspaceScopedState` a thin alias to the app-shell reducer.

- [ ] **Step 6: Verify frontend model tests**

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

- [ ] **Step 7: Commit Task 3**

```bash
git status --short
git add src/embedagent/frontend/gui/webapp/src/app-shell src/embedagent/frontend/gui/webapp/src/app-workspaces.js src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs src/embedagent/frontend/gui/webapp/test/app-workspaces.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: add frontend app shell model"
```

---

## Task 4: Wire App-Shell State Into Store And Commands

**Files:**

- Create: `src/embedagent/frontend/gui/webapp/src/app-shell/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing store and command tests**

Update frontend tests to assert:

- `initialState.app` is produced by `createAppShellState()`.
- Existing reducer actions still work through compatibility names:
  - `app_bootstrap_loaded`
  - `workspace_path_changed`
  - `workspace_activation_started`
  - `workspace_activation_failed`
  - `workspace_switched`
- New reducer actions work directly:
  - `app_shell_bootstrap_loaded`
  - `app_shell_settings_changed`
- `workspace_switched` still clears root workspace-scoped state.
- App-shell settings survive a workspace switch unless bootstrap payload replaces them.
- `RIGHT_PANEL_SURFACES` includes `settings` and `diagnostics`.
- `COMMAND_GROUPS` includes `app`.
- `WORKBENCH_COMMANDS` includes `app.settings`, `app.diagnostics`, and `app.reload`.
- App commands are visible without an active session.
- `mod+,` is bound to `app.settings`.

Run expected failure:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

- [ ] **Step 2: Implement app command descriptors**

Create `src/embedagent/frontend/gui/webapp/src/app-shell/commands.js`.

Required exports:

- `APP_COMMANDS`
- `isAppCommand(id)`

Descriptors:

- `app.settings`, group `app`, label `Open Settings`, no slash, visible when `always`
- `app.diagnostics`, group `app`, label `Open Diagnostics`, no slash, visible when `always`
- `app.reload`, group `app`, label `Reload App Shell`, no slash, visible when `always`

- [ ] **Step 3: Merge app commands into workbench commands**

In `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`:

- Import `APP_COMMANDS`.
- Add `app` to `COMMAND_GROUPS`.
- Add `...APP_COMMANDS` to `WORKBENCH_COMMANDS`.
- Keep all existing command IDs and visibility behavior.

In `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`:

- Add `mod+,` for `app.settings`.

In `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`:

- Add `settings` and `diagnostics` to `RIGHT_PANEL_SURFACES`.

- [ ] **Step 4: Route root store app actions through the app-shell reducer**

In `src/embedagent/frontend/gui/webapp/src/store.js`:

- Import `createAppShellState` and `reduceAppShellState`.
- Replace the inline `initialState.app` literal with `createAppShellState()`.
- For legacy UI action names, translate to app-shell action names:
  - `app_bootstrap_loaded` -> `app_shell_bootstrap_loaded`
  - `workspace_path_changed` -> `app_shell_workspace_path_changed`
  - `workspace_activation_started` -> `app_shell_workspace_activation_started`
  - `workspace_activation_failed` -> `app_shell_workspace_activation_failed`
  - `workspace_switched` -> use root `resetWorkspaceScopedState(state)`, then reduce `reset.app` with `app_shell_workspace_switched`
- Add direct case `app_shell_settings_changed`.
- Preserve existing behavior for sessions, timeline, tasks, interactions, and workbench surfaces.

- [ ] **Step 5: Verify frontend command/store tests**

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

- [ ] **Step 6: Commit Task 4**

```bash
git status --short
git add src/embedagent/frontend/gui/webapp/src/app-shell/commands.js src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/workbench/commands.js src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: wire app shell commands"
```

---

## Task 5: Settings And Diagnostics Surfaces

**Files:**

- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/strings.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing source-contract tests**

Update `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` to assert:

- `Inspector.jsx` contains `SettingsPanel` and `DiagnosticsPanel`.
- `Inspector.jsx` imports `formatDiagnosticsRows`.
- `Inspector.jsx` accepts `appShell` and `onAppSettingsChange`.
- `RightPanelTabs.jsx` labels `settings` and `diagnostics`.
- `App.jsx` handles `app.settings`, `app.diagnostics`, and `app.reload` in `executeWorkbenchCommand`.
- `App.jsx` passes `state.app` into `Inspector`.
- `styles.css` contains app settings and diagnostics classes.

Run expected failure:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

- [ ] **Step 2: Add right-panel tab labels**

In `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`:

- Add labels for `settings` and `diagnostics`.
- Keep labels compact to preserve existing right-panel density.

- [ ] **Step 3: Add settings and diagnostics panels**

In `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`:

- Import `formatDiagnosticsRows`.
- Add props:
  - `appShell`
  - `onAppSettingsChange`
- Add branches:
  - `{inspectorTab === "settings" && <SettingsPanel ... />}`
  - `{inspectorTab === "diagnostics" && <DiagnosticsPanel ... />}`
- `SettingsPanel` should expose two checkboxes:
  - `confirm_workspace_switch`
  - `show_diagnostics_badge`
- Checkbox changes dispatch a small patch through `onAppSettingsChange`.
- `DiagnosticsPanel` should render formatted diagnostics rows and capability chips.
- Do not add instructional prose blocks; keep it as a utilitarian app settings/diagnostics surface.

- [ ] **Step 4: Wire app command execution**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`:

- Import `isAppCommand` if useful.
- In `executeWorkbenchCommand(command)`, handle app commands before generic surface commands:
  - `app.settings` opens right panel `settings`
  - `app.diagnostics` opens right panel `diagnostics`
  - `app.reload` calls existing app bootstrap loader path and dispatches `app_bootstrap_loaded`
- Pass `appShell={state.app}` and `onAppSettingsChange={(patch) => dispatch({ type: "app_shell_settings_changed", patch })}` to `Inspector`.
- Include app command capabilities in command-palette context only as read-model metadata; do not make capability metadata an execution policy.

- [ ] **Step 5: Add strings and CSS**

In `src/embedagent/frontend/gui/webapp/src/strings.js`:

- Add compact labels for settings, diagnostics, host, runtime, renderer, workspace registry, and active core.

In `src/embedagent/frontend/gui/webapp/src/styles.css`:

- Add styles for:
  - `.app-settings-grid`
  - `.app-setting-row`
  - `.app-setting-check`
  - `.diagnostics-table`
  - `.diagnostics-row`
  - `.diagnostics-group`
  - `.diagnostics-key`
  - `.diagnostics-value`
  - `.rule-chip.muted`
- Keep cards shallow and avoid nested card styling.

- [ ] **Step 6: Verify frontend UI tests**

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

- [ ] **Step 7: Commit Task 5**

```bash
git status --short
git add src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/strings.js src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: add app settings diagnostics surfaces"
```

---

## Task 6: Documentation, Build Assets, And Full Verification

**Files:**

- Modify: `docs/frontend-protocol.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Possibly modify generated GUI static assets under `src/embedagent/frontend/gui/static/` after `npm run build`

- [ ] **Step 1: Update source-of-truth docs**

Update `docs/frontend-protocol.md`:

- Add a `GUI App-Shell State` section.
- Document `/api/app/bootstrap` as the single app activation bootstrap contract.
- Document the app-shell payload fields.
- State that `/api/sessions/{id}/bootstrap` remains the only session activation bootstrap contract.
- State that GUI app-shell settings are frontend-local unless later promoted by a documented backend contract.

Update `docs/overall-solution-architecture.md`:

- Add the GUI app shell as a replaceable frontend/host boundary.
- Reaffirm Agent Core ownership over sessions, workflow state, tools, permissions, transcript reducers, and extension execution.

Update `docs/implementation-roadmap.md` and `docs/development-tracker.md`:

- Mark this as the first T3 Code-style app-shell boundary slice.
- Leave terminal/source-control/checkpoint as future slices.

Update `docs/design-change-log.md`:

- Add a dated entry for the app-shell boundary and its non-Core ownership.

- [ ] **Step 2: Run targeted backend verification**

```bash
uv run pytest tests/test_gui_app_shell.py tests/test_gui_app_host.py tests/test_gui_backend_api.py -v
```

- [ ] **Step 3: Run frontend verification**

```bash
cd src/embedagent/frontend/gui/webapp && npm test
cd src/embedagent/frontend/gui/webapp && npm run build
```

- [ ] **Step 4: Run fast repository verification**

```bash
uv run pytest tests/ -m "not slow and not gui" -v
uv run ruff check src/embedagent/frontend/gui/backend tests/test_gui_app_shell.py tests/test_gui_app_host.py tests/test_gui_backend_api.py
```

- [ ] **Step 5: Verify Agent Core stayed untouched**

```bash
git diff -- src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py src/embedagent/agent_loop.py src/embedagent/agent_tool_action_service.py src/embedagent/extensions.py
```

Expected output: no diff.

- [ ] **Step 6: Commit final docs/build integration**

```bash
git status --short
git add docs/frontend-protocol.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md src/embedagent/frontend/gui/static
git commit -m "docs: document gui app shell boundary"
```

---

## Final Review Checklist

- [ ] Backend app bootstrap exposes a complete app-shell payload.
- [ ] Workspace app routes return the app-shell envelope while preserving current workspace activation semantics.
- [ ] Frontend app-shell normalization and reducer are pure and independently tested.
- [ ] Root-store workspace reset still clears session/workflow UI state.
- [ ] App-level commands exist separately from session/workflow commands.
- [ ] Settings and diagnostics panels render without requiring an active session.
- [ ] No Agent Core session/history/workflow/tool/permission ownership moved into GUI.
- [ ] Docs describe the new boundary and explicitly keep terminal/source-control/checkpoint as later slices.
- [ ] All verification commands in Task 6 have passed or have a recorded reason if an environment dependency is missing.

