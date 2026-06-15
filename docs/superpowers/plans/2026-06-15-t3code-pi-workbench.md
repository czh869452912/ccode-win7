# T3code Pi Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a T3code-inspired GUI/TUI Agent workbench shell while preserving Pi-style Agent Core decoupling, Windows 7 compatibility, offline operation, and the current C/C++ workflow contracts.

**Architecture:** Add a small frontend-only workbench contract for surfaces, commands, keybindings, layout state, and command-palette state. Migrate the GUI toward a T3code-style shell around existing backend/read-model data, then make the TUI an isomorphic keyboard-first shell using the same command IDs and surface names without moving workflow, permission, tool, extension, or history policy into frontends.

**Tech Stack:** Python 3.8, prompt_toolkit, React 18, Vite/esbuild targeting chrome109, existing FastAPI/WebSocket/pywebview backend, existing offline bundle and WebView2 109 constraints.

---

## Scope Check

This plan covers one product program because the GUI and TUI need one shared shell vocabulary. The work is split into independently testable slices:

- Tasks 1-2 create pure GUI shell contracts with Node tests.
- Tasks 3-5 migrate the GUI shell layout, right-panel surfaces, bottom drawer, command palette, and composer interactions.
- Tasks 6-7 add the TUI workbench command/surface state and Pi-style overlays with Python tests.
- Task 8 updates source-of-truth docs and runs compatibility gates.

Agent Core remains unchanged unless a task explicitly updates documentation that describes frontend boundaries.

## Compatibility Rules

- Keep GUI build target at `chrome109`; do not add browser APIs outside Chrome 109 without transpilation already provided by Vite/esbuild.
- Do not add Electron, remote relay processes, runtime Node requirements, CDN assets, Docker, WSL, VS Code, or online services.
- Do not add runtime dependencies absent from `pyproject.toml` or `src/embedagent/frontend/gui/webapp/package.json`.
- Keep Python code compatible with `>=3.8,<3.9`: no walrus operator, no `match`, no built-in generic types such as `list[str]`, no `dict | dict`.
- Keep frontends as shells: UI state may select visible surfaces and commands, but tool activation, permissions, mode changes, transcript history, and workflow state stay behind existing protocol/Core boundaries.
- Copy T3code's product shape and frontend architecture model. Direct source-code reuse from `reference/t3code` must preserve MIT license attribution in the changed file header or in `docs/design-change-log.md`.

## File Structure

### GUI Workbench Contract

- Create `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - Pure workbench surface state reducer.
  - Right-panel and bottom-drawer surface constants.
  - No React imports, no network calls, no backend policy.
- Create `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - Stable command IDs, labels, command groups, and command visibility metadata.
  - Slash-command links are metadata only.
- Create `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
  - Default keybinding rules and a small resolver for keyboard events.
  - No persistence and no browser storage in this slice.
- Create `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - Node assertion tests for surface reducer, command registry, and keybinding resolver.
- Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Import and run the new workbench tests.
- Modify `src/embedagent/frontend/gui/webapp/src/store.js`
  - Add `workbench` to `initialState`.
  - Add reducer cases that delegate to the workbench reducer.

### GUI Components

- Create `src/embedagent/frontend/gui/webapp/src/components/workbench/AppSidebarLayout.jsx`
  - Top-level header/sidebar/main/right-panel/bottom-drawer layout.
  - Receives already-rendered slots; owns no backend data.
- Create `src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx`
  - Header controls for mode/status/session/turns/refresh/language/panel toggles.
- Create `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  - T3code-style right-panel tab strip backed by workbench surface constants.
- Create `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
  - Optional bottom surface for run output, terminal-like logs, and long diagnostics.
- Create `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx`
  - Keyboard-driven command selector.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Wire existing `Sidebar`, `Timeline`, `Inspector`, and `Composer` through the workbench shell.
  - Wire command palette actions to existing callbacks.
- Modify `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - Import right-panel surface definitions instead of keeping a private tab list.
  - Keep existing panel bodies.
- Modify `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - Add command-palette and drawer entry points while preserving slash hints and send/stop behavior.
- Modify `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Add workbench layout, palette, right-panel, and drawer styles.

### TUI Workbench Contract

- Create `src/embedagent/frontend/tui/workbench.py`
  - Python 3.8 dataclasses for surfaces, commands, keybindings, and command-palette state.
  - Shared command IDs matching the GUI command registry.
- Create `src/embedagent/frontend/tui/views/command_palette.py`
  - Pure formatted-text rendering for command palette content.
- Modify `src/embedagent/frontend/tui/state.py`
  - Add `WorkbenchState` to `TerminalState`.
- Modify `src/embedagent/frontend/tui/reducer.py`
  - Add reducer helpers for opening/closing surfaces and command palette selection.
- Modify `src/embedagent/frontend/tui/commands.py`
  - Source slash command names from the workbench command registry.
- Modify `src/embedagent/frontend/tui/completion.py`
  - Keep slash completion behavior while reading names from the updated command registry.
- Modify `src/embedagent/frontend/tui/controller.py`
  - Dispatch command-palette and surface commands without changing service calls.
- Modify `src/embedagent/frontend/tui/layout.py`
  - Add Pi-style overlay container for command palette and keep raw-console fallback.
- Modify `src/embedagent/frontend/tui/views/header.py`
  - Show active surface and overlay state in the second status line.
- Modify `src/embedagent/frontend/tui/views/composer.py`
  - Keep pending permission/input prompts and add surface-aware shell hint text through state.
- Modify `tests/test_terminal_frontend.py`
  - Add tests for workbench command IDs, slash names, surface state, and command-palette rendering.

### Documentation

- Modify `docs/frontend-protocol.md`
  - Document workbench shell state as frontend-local state, not protocol policy.
- Modify `docs/modules/frontend-gui.md`
  - Document GUI workbench architecture, WebView2 109 constraint, and static rebuild flow.
- Modify `docs/modules/frontend-tui.md`
  - Document Pi-style keyboard shell model, overlays, and raw-console fallback.
- Modify `docs/development-tracker.md`
  - Record the completed implementation slices.
- Modify `docs/design-change-log.md`
  - Record T3code/Pi design adoption and any MIT attribution if source code is copied.
- Modify `docs/implementation-roadmap.md`
  - Reflect the new frontend workbench program and remaining polish gates.

---

### Task 1: GUI Workbench Surface State

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Create: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`

- [ ] **Step 1: Write the failing surface tests**

Create `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs` with this content:

```javascript
import assert from "node:assert/strict";

import {
  BOTTOM_DRAWER_SURFACES,
  RIGHT_PANEL_SURFACES,
  activateSurface,
  closeSurface,
  createWorkbenchState,
  openSurface,
  reduceWorkbenchState,
} from "../src/workbench/surfaces.js";

export function runWorkbenchStateTests() {
  assert.equal(RIGHT_PANEL_SURFACES.includes("tasks"), true);
  assert.equal(RIGHT_PANEL_SURFACES.includes("preview"), true);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("run_output"), true);

  const initial = createWorkbenchState();
  assert.equal(initial.rightPanel.open, true);
  assert.equal(initial.rightPanel.activeKind, "tasks");
  assert.equal(initial.bottomDrawer.open, false);

  const withPreview = openSurface(initial, {
    sessionId: "sess-1",
    placement: "right",
    kind: "preview",
    title: "README.md",
    resourceId: "README.md",
  });
  assert.notEqual(withPreview, initial);
  assert.equal(withPreview.rightPanel.open, true);
  assert.equal(withPreview.rightPanel.activeKind, "preview");
  assert.equal(withPreview.surfacesBySession["sess-1"].right.length, 1);
  assert.equal(withPreview.surfacesBySession["sess-1"].right[0].resourceId, "README.md");

  const withRunOutput = openSurface(withPreview, {
    sessionId: "sess-1",
    placement: "bottom",
    kind: "run_output",
    title: "Build Output",
  });
  assert.equal(withRunOutput.bottomDrawer.open, true);
  assert.equal(withRunOutput.bottomDrawer.activeKind, "run_output");
  assert.equal(withRunOutput.surfacesBySession["sess-1"].bottom[0].kind, "run_output");

  const activated = activateSurface(withRunOutput, {
    placement: "right",
    kind: "tasks",
  });
  assert.equal(activated.rightPanel.activeKind, "tasks");

  const closed = closeSurface(withRunOutput, {
    placement: "right",
    kind: "preview",
    resourceId: "README.md",
  });
  assert.equal(closed.surfacesBySession["sess-1"].right.length, 0);
  assert.equal(closed.rightPanel.activeKind, "tasks");

  const reduced = reduceWorkbenchState(initial, {
    type: "workbench_surface_opened",
    sessionId: "sess-2",
    placement: "right",
    kind: "runtime",
    title: "Runtime",
  });
  assert.equal(reduced.rightPanel.activeKind, "runtime");
  assert.equal(reduced.surfacesBySession["sess-2"].right[0].kind, "runtime");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with a module resolution error for `../src/workbench/surfaces.js`.

- [ ] **Step 3: Implement the surface reducer**

Create `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js` with this content:

```javascript
export const RIGHT_PANEL_SURFACES = [
  "interaction",
  "tasks",
  "plan",
  "artifacts",
  "run",
  "problems",
  "review",
  "permissions",
  "runtime",
  "preview",
  "log",
];

export const BOTTOM_DRAWER_SURFACES = ["terminal", "run_output", "logs"];

const DEFAULT_SESSION_KEY = "__global__";

function normalizeSessionId(sessionId) {
  const value = String(sessionId || "").trim();
  return value || DEFAULT_SESSION_KEY;
}

function normalizePlacement(placement) {
  return placement === "bottom" ? "bottom" : "right";
}

function defaultActiveKind(placement) {
  return placement === "bottom" ? "run_output" : "tasks";
}

function allowedKinds(placement) {
  return placement === "bottom" ? BOTTOM_DRAWER_SURFACES : RIGHT_PANEL_SURFACES;
}

function makeSurface(input) {
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  return {
    id: `${placement}:${kind}:${String((input && input.resourceId) || "")}`,
    placement,
    kind,
    title: String((input && input.title) || kind),
    resourceId: String((input && input.resourceId) || ""),
  };
}

function emptySessionSurfaces() {
  return {
    right: [],
    bottom: [],
  };
}

function sessionSurfaces(state, sessionId) {
  const key = normalizeSessionId(sessionId);
  return state.surfacesBySession[key] || emptySessionSurfaces();
}

function upsertSurface(items, nextSurface) {
  const existingIndex = items.findIndex((item) => item.id === nextSurface.id);
  if (existingIndex < 0) {
    return items.concat(nextSurface);
  }
  return items.map((item, index) => (index === existingIndex ? nextSurface : item));
}

function removeSurface(items, surface) {
  return items.filter((item) => item.id !== surface.id);
}

export function createWorkbenchState() {
  return {
    sidebar: {
      activeSection: "threads",
      projectSection: "files",
    },
    rightPanel: {
      open: true,
      activeKind: "tasks",
      width: 320,
    },
    bottomDrawer: {
      open: false,
      activeKind: "run_output",
      height: 220,
    },
    commandPalette: {
      open: false,
      query: "",
      selectedIndex: 0,
    },
    layout: {
      density: "compact",
      narrow: false,
    },
    surfacesBySession: {},
  };
}

export function getSessionSurfaces(state, sessionId) {
  return sessionSurfaces(state || createWorkbenchState(), sessionId);
}

export function openSurface(state, input) {
  const current = state || createWorkbenchState();
  const surface = makeSurface(input || {});
  const placement = normalizePlacement(surface.placement);
  if (!allowedKinds(placement).includes(surface.kind)) {
    return current;
  }
  const key = normalizeSessionId(input && input.sessionId);
  const existing = sessionSurfaces(current, key);
  const nextSessionSurfaces = {
    ...existing,
    [placement]: upsertSurface(existing[placement], surface),
  };
  return {
    ...current,
    surfacesBySession: {
      ...current.surfacesBySession,
      [key]: nextSessionSurfaces,
    },
    rightPanel:
      placement === "right"
        ? { ...current.rightPanel, open: true, activeKind: surface.kind }
        : current.rightPanel,
    bottomDrawer:
      placement === "bottom"
        ? { ...current.bottomDrawer, open: true, activeKind: surface.kind }
        : current.bottomDrawer,
  };
}

export function activateSurface(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  if (!allowedKinds(placement).includes(kind)) {
    return current;
  }
  if (placement === "bottom") {
    return {
      ...current,
      bottomDrawer: { ...current.bottomDrawer, open: true, activeKind: kind },
    };
  }
  return {
    ...current,
    rightPanel: { ...current.rightPanel, open: true, activeKind: kind },
  };
}

export function closeSurface(state, input) {
  const current = state || createWorkbenchState();
  const surface = makeSurface(input || {});
  const placement = normalizePlacement(surface.placement);
  const key = normalizeSessionId(input && input.sessionId);
  const existing = sessionSurfaces(current, key);
  const nextItems = removeSurface(existing[placement], surface);
  const nextSessionSurfaces = {
    ...existing,
    [placement]: nextItems,
  };
  const nextState = {
    ...current,
    surfacesBySession: {
      ...current.surfacesBySession,
      [key]: nextSessionSurfaces,
    },
  };
  if (placement === "bottom") {
    return {
      ...nextState,
      bottomDrawer: {
        ...nextState.bottomDrawer,
        open: nextItems.length > 0,
        activeKind: nextItems.length > 0 ? nextItems[0].kind : defaultActiveKind(placement),
      },
    };
  }
  return {
    ...nextState,
    rightPanel: {
      ...nextState.rightPanel,
      activeKind: nextItems.length > 0 ? nextItems[0].kind : defaultActiveKind(placement),
    },
  };
}

export function reduceWorkbenchState(state, action) {
  const current = state || createWorkbenchState();
  switch (action.type) {
    case "workbench_surface_opened":
      return openSurface(current, action);
    case "workbench_surface_activated":
      return activateSurface(current, action);
    case "workbench_surface_closed":
      return closeSurface(current, action);
    case "workbench_command_palette_opened":
      return {
        ...current,
        commandPalette: { ...current.commandPalette, open: true, query: "", selectedIndex: 0 },
      };
    case "workbench_command_palette_closed":
      return {
        ...current,
        commandPalette: { ...current.commandPalette, open: false, query: "", selectedIndex: 0 },
      };
    case "workbench_command_palette_query_changed":
      return {
        ...current,
        commandPalette: {
          ...current.commandPalette,
          query: String(action.query || ""),
          selectedIndex: 0,
        },
      };
    case "workbench_right_panel_toggled":
      return {
        ...current,
        rightPanel: { ...current.rightPanel, open: !current.rightPanel.open },
      };
    case "workbench_bottom_drawer_toggled":
      return {
        ...current,
        bottomDrawer: { ...current.bottomDrawer, open: !current.bottomDrawer.open },
      };
    default:
      return current;
  }
}
```

- [ ] **Step 4: Wire the tests into the existing Node runner**

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
import { runWorkbenchStateTests } from "./workbench-state.test.mjs";
```

Call the test function near the end of `main()` before `runSessionRuntimeTests()`:

```javascript
  runWorkbenchStateTests();
  runSessionRuntimeTests();
```

- [ ] **Step 5: Wire the reducer into GUI state**

Modify `src/embedagent/frontend/gui/webapp/src/store.js`:

```javascript
import { createWorkbenchState, reduceWorkbenchState } from "./workbench/surfaces.js";
```

Add this field to `initialState`:

```javascript
  workbench: createWorkbenchState(),
```

Add these reducer cases before the `default` case:

```javascript
    case "workbench_surface_opened":
    case "workbench_surface_activated":
    case "workbench_surface_closed":
    case "workbench_command_palette_opened":
    case "workbench_command_palette_closed":
    case "workbench_command_palette_query_changed":
    case "workbench_right_panel_toggled":
    case "workbench_bottom_drawer_toggled":
      return { ...state, workbench: reduceWorkbenchState(state.workbench, action) };
```

- [ ] **Step 6: Run tests to verify green**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS and output includes `frontend helper checks passed`.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/src/store.js
git commit -m "feat: add gui workbench surface state"
```

Expected: commit succeeds with only the listed files staged.

### Task 2: GUI Command Registry And Keybindings

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Create: `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`

- [ ] **Step 1: Extend the failing workbench tests**

Append these imports to `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`:

```javascript
import {
  COMMAND_GROUPS,
  WORKBENCH_COMMANDS,
  commandById,
  visibleCommands,
} from "../src/workbench/commands.js";
import {
  DEFAULT_KEYBINDINGS,
  eventToKey,
  resolveKeybinding,
} from "../src/workbench/keybindings.js";
```

Append these assertions inside `runWorkbenchStateTests()`:

```javascript
  assert.equal(COMMAND_GROUPS.includes("session"), true);
  assert.equal(COMMAND_GROUPS.includes("surface"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "surface.tasks"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id.includes("code")), false);
  assert.equal(commandById("message.send").slash, "");

  const visibleWhenIdle = visibleCommands({ hasSession: true, isRunning: false });
  assert.equal(visibleWhenIdle.some((item) => item.id === "message.send"), true);
  assert.equal(visibleWhenIdle.some((item) => item.id === "message.stop"), false);

  const visibleWhenRunning = visibleCommands({ hasSession: true, isRunning: true });
  assert.equal(visibleWhenRunning.some((item) => item.id === "message.stop"), true);

  const syntheticEvent = {
    key: "k",
    ctrlKey: true,
    metaKey: false,
    altKey: false,
    shiftKey: false,
  };
  assert.equal(eventToKey(syntheticEvent), "mod+k");
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+k"), true);

  const command = resolveKeybinding(DEFAULT_KEYBINDINGS, "mod+k", {
    paletteOpen: false,
    isRunning: false,
  });
  assert.equal(command.id, "palette.open");

  const blocked = resolveKeybinding(DEFAULT_KEYBINDINGS, "enter", {
    paletteOpen: false,
    composerFocused: false,
  });
  assert.equal(blocked, null);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with module resolution errors for `commands.js` and `keybindings.js`.

- [ ] **Step 3: Implement the command registry**

Create `src/embedagent/frontend/gui/webapp/src/workbench/commands.js` with this content:

```javascript
export const COMMAND_GROUPS = [
  "session",
  "message",
  "mode",
  "surface",
  "workspace",
  "workflow",
  "view",
];

export const WORKBENCH_COMMANDS = [
  { id: "session.new", group: "session", label: "New Session", slash: "/new", visibleWhen: "always" },
  { id: "session.refresh", group: "session", label: "Refresh Sessions", slash: "/sessions", visibleWhen: "always" },
  { id: "session.resume", group: "session", label: "Resume Session", slash: "/resume", visibleWhen: "always" },
  { id: "message.send", group: "message", label: "Send Message", slash: "", visibleWhen: "composer_ready" },
  { id: "message.stop", group: "message", label: "Stop Running Turn", slash: "", visibleWhen: "running" },
  { id: "mode.explore", group: "mode", label: "Mode: Explore", slash: "/mode explore", visibleWhen: "has_session" },
  { id: "mode.spec", group: "mode", label: "Mode: Spec", slash: "/mode spec", visibleWhen: "has_session" },
  { id: "mode.build", group: "mode", label: "Mode: Build", slash: "/mode build", visibleWhen: "has_session" },
  { id: "mode.debug", group: "mode", label: "Mode: Debug", slash: "/mode debug", visibleWhen: "has_session" },
  { id: "mode.verify", group: "mode", label: "Mode: Verify", slash: "/mode verify", visibleWhen: "has_session" },
  { id: "surface.interaction", group: "surface", label: "Open Interaction", slash: "", surface: "interaction", visibleWhen: "always" },
  { id: "surface.tasks", group: "surface", label: "Open Tasks", slash: "/tasks", surface: "tasks", visibleWhen: "always" },
  { id: "surface.plan", group: "surface", label: "Open Plan", slash: "/plan", surface: "plan", visibleWhen: "always" },
  { id: "surface.artifacts", group: "surface", label: "Open Artifacts", slash: "/artifacts", surface: "artifacts", visibleWhen: "always" },
  { id: "surface.run", group: "surface", label: "Open Run", slash: "/recipes", surface: "run", visibleWhen: "always" },
  { id: "surface.problems", group: "surface", label: "Open Problems", slash: "", surface: "problems", visibleWhen: "always" },
  { id: "surface.review", group: "surface", label: "Open Review", slash: "/review", surface: "review", visibleWhen: "always" },
  { id: "surface.permissions", group: "surface", label: "Open Permissions", slash: "/permissions", surface: "permissions", visibleWhen: "has_session" },
  { id: "surface.runtime", group: "surface", label: "Open Runtime", slash: "/snapshot", surface: "runtime", visibleWhen: "has_session" },
  { id: "surface.preview", group: "surface", label: "Open Preview", slash: "", surface: "preview", visibleWhen: "always" },
  { id: "surface.log", group: "surface", label: "Open Log", slash: "", surface: "log", visibleWhen: "always" },
  { id: "drawer.run_output", group: "surface", label: "Toggle Run Output", slash: "", drawer: "run_output", visibleWhen: "always" },
  { id: "workspace.files", group: "workspace", label: "Open Files", slash: "/workspace", visibleWhen: "always" },
  { id: "workflow.diff", group: "workflow", label: "Review Diff", slash: "/diff", visibleWhen: "has_session" },
  { id: "view.toggle_right_panel", group: "view", label: "Toggle Right Panel", slash: "", visibleWhen: "always" },
  { id: "view.toggle_bottom_drawer", group: "view", label: "Toggle Bottom Drawer", slash: "", visibleWhen: "always" },
  { id: "palette.open", group: "view", label: "Open Command Palette", slash: "", visibleWhen: "always" },
  { id: "palette.close", group: "view", label: "Close Command Palette", slash: "", visibleWhen: "palette_open" },
];

export function commandById(id) {
  return WORKBENCH_COMMANDS.find((item) => item.id === id) || null;
}

function isVisible(command, context) {
  const view = context || {};
  switch (command.visibleWhen) {
    case "always":
      return true;
    case "has_session":
      return Boolean(view.hasSession);
    case "running":
      return Boolean(view.isRunning);
    case "composer_ready":
      return !view.isRunning;
    case "palette_open":
      return Boolean(view.paletteOpen);
    default:
      return false;
  }
}

export function visibleCommands(context) {
  return WORKBENCH_COMMANDS.filter((command) => isVisible(command, context || {}));
}
```

- [ ] **Step 4: Implement keybinding resolution**

Create `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js` with this content:

```javascript
import { commandById } from "./commands.js";

export const DEFAULT_KEYBINDINGS = [
  { key: "mod+k", commandId: "palette.open", when: "not_palette" },
  { key: "escape", commandId: "palette.close", when: "palette" },
  { key: "escape", commandId: "message.stop", when: "running" },
  { key: "mod+b", commandId: "view.toggle_right_panel", when: "always" },
  { key: "mod+j", commandId: "view.toggle_bottom_drawer", when: "always" },
  { key: "mod+1", commandId: "surface.tasks", when: "always" },
  { key: "mod+2", commandId: "surface.plan", when: "always" },
  { key: "mod+3", commandId: "surface.preview", when: "always" },
  { key: "mod+enter", commandId: "message.send", when: "composer" },
];

function normalizeKeyName(key) {
  const value = String(key || "").toLowerCase();
  if (value === " ") return "space";
  if (value === "esc") return "escape";
  if (value === "control") return "ctrl";
  return value;
}

export function eventToKey(event) {
  const parts = [];
  if (event.ctrlKey || event.metaKey) parts.push("mod");
  if (event.altKey) parts.push("alt");
  if (event.shiftKey) parts.push("shift");
  parts.push(normalizeKeyName(event.key));
  return parts.join("+");
}

function matchesWhen(rule, context) {
  const view = context || {};
  switch (rule || "always") {
    case "always":
      return true;
    case "palette":
      return Boolean(view.paletteOpen);
    case "not_palette":
      return !view.paletteOpen;
    case "running":
      return Boolean(view.isRunning);
    case "composer":
      return Boolean(view.composerFocused);
    default:
      return false;
  }
}

export function resolveKeybinding(bindings, key, context) {
  const normalizedKey = String(key || "").toLowerCase();
  const match = (bindings || []).find(
    (binding) => binding.key === normalizedKey && matchesWhen(binding.when, context || {}),
  );
  if (!match) return null;
  return commandById(match.commandId);
}
```

- [ ] **Step 5: Run tests to verify green**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS and output includes `frontend helper checks passed`.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/workbench/commands.js src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs
git commit -m "feat: add gui workbench commands"
```

Expected: commit succeeds with only the listed files staged.

### Task 3: GUI T3-Style Workbench Shell Layout

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/AppSidebarLayout.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add static source checks before the layout exists**

Append these checks near the existing source-string checks in `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
  const appSource = fs.readFileSync(
    path.resolve("src", "embedagent", "frontend", "gui", "webapp", "src", "App.jsx"),
    "utf8",
  );
  assert.equal(appSource.includes("AppSidebarLayout"), true);
  assert.equal(appSource.includes("WorkbenchHeader"), true);

  const workbenchHeaderSource = fs.readFileSync(
    path.resolve(
      "src",
      "embedagent",
      "frontend",
      "gui",
      "webapp",
      "src",
      "components",
      "workbench",
      "WorkbenchHeader.jsx",
    ),
    "utf8",
  );
  assert.equal(workbenchHeaderSource.includes("mode-code"), false);
  assert.equal(workbenchHeaderSource.includes("mode-build"), true);

  const appSidebarLayoutSource = fs.readFileSync(
    path.resolve(
      "src",
      "embedagent",
      "frontend",
      "gui",
      "webapp",
      "src",
      "components",
      "workbench",
      "AppSidebarLayout.jsx",
    ),
    "utf8",
  );
  assert.equal(appSidebarLayoutSource.includes("workbench-layout"), true);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `App.jsx` does not import `AppSidebarLayout`.

- [ ] **Step 3: Create the slotted layout component**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/AppSidebarLayout.jsx` with this content:

```javascript
import React from "react";

export default function AppSidebarLayout({
  header,
  sidebar,
  main,
  rightPanel,
  bottomDrawer,
  rightPanelOpen,
  bottomDrawerOpen,
  onResizeSidebar,
  onResizeRightPanel,
}) {
  return (
    <div
      className={`workbench-layout${rightPanelOpen ? " right-open" : " right-closed"}${
        bottomDrawerOpen ? " drawer-open" : ""
      }`}
      data-testid="workbench-layout"
    >
      <div className="workbench-header-slot">{header}</div>
      <div className="workbench-body">
        <div className="workbench-sidebar-slot">{sidebar}</div>
        <div
          className="resize-handle"
          onPointerDown={onResizeSidebar}
          aria-hidden="true"
        />
        <div className="workbench-center">
          <div className="workbench-main-slot">{main}</div>
          {bottomDrawerOpen ? (
            <div className="workbench-bottom-slot">{bottomDrawer}</div>
          ) : null}
        </div>
        <div
          className="resize-handle"
          onPointerDown={onResizeRightPanel}
          aria-hidden="true"
        />
        {rightPanelOpen ? (
          <div className="workbench-right-slot">{rightPanel}</div>
        ) : (
          <div className="workbench-right-collapsed" aria-hidden="true" />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create the workbench header**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx` with this content:

```javascript
import React from "react";
import { t } from "../../strings.js";

export default function WorkbenchHeader({
  lang,
  currentMode,
  currentStatus,
  currentSessionId,
  turnsUsed,
  maxTurns,
  rightPanelOpen,
  bottomDrawerOpen,
  onRefresh,
  onToggleLang,
  onToggleRightPanel,
  onToggleBottomDrawer,
  onOpenPalette,
}) {
  return (
    <header className="app-header workbench-header" data-testid="workbench-header">
      <span className="app-logo">EmbedAgent</span>
      <span className={`mode-badge mode-${currentMode}`}>{currentMode}</span>
      <div className="header-right">
        <span className={`status-dot ${currentStatus}`} title={currentStatus} />
        <span
          className={`status-label ${
            currentStatus === "idle" ? "idle" : currentStatus === "error" ? "error" : ""
          }`}
        >
          {currentStatus}
        </span>
        {currentSessionId ? (
          <span className="meta-text">{currentSessionId.slice(0, 8)}</span>
        ) : null}
        {turnsUsed > 0 ? (
          <span className="meta-text">turns {turnsUsed}/{maxTurns}</span>
        ) : null}
        <button className="ghost" onClick={onOpenPalette} data-testid="open-command-palette">
          Cmd
        </button>
        <button className="ghost" onClick={onRefresh} aria-label={t("header.refresh", lang)} data-testid="refresh-sessions">
          {t("header.refresh", lang)}
        </button>
        <button
          className="ghost lang-toggle"
          onClick={onToggleLang}
          aria-label="Toggle language"
          data-testid="lang-toggle"
        >
          {t("lang.toggle", lang)}
        </button>
        <button
          className={`ghost drawer-toggle${bottomDrawerOpen ? " active" : ""}`}
          onClick={onToggleBottomDrawer}
          aria-pressed={bottomDrawerOpen}
          title="Toggle run output"
          data-testid="drawer-toggle"
        >
          Run
        </button>
        <button
          className={`ghost inspector-toggle${rightPanelOpen ? " active" : ""}`}
          onClick={onToggleRightPanel}
          title={t("header.toggleInspector", lang)}
          aria-pressed={rightPanelOpen}
          data-testid="inspector-toggle"
        >
          Panel
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 5: Wire `App.jsx` imports**

Add these imports to `src/embedagent/frontend/gui/webapp/src/App.jsx`:

```javascript
import AppSidebarLayout from "./components/workbench/AppSidebarLayout.jsx";
import WorkbenchHeader from "./components/workbench/WorkbenchHeader.jsx";
```

- [ ] **Step 6: Replace the top-level render layout in `App.jsx`**

Inside the return block, replace the `<div className="app-shell">...</div>` wrapper with this slot-based shell. Keep the existing `Sidebar`, `Timeline`, `Composer`, and `Inspector` props exactly as they are in the current file.

```javascript
    <AppSidebarLayout
      header={
        <WorkbenchHeader
          lang={state.lang}
          currentMode={currentMode}
          currentStatus={currentStatus}
          currentSessionId={state.currentSessionId}
          turnsUsed={state.turnsUsed}
          maxTurns={state.maxTurns}
          rightPanelOpen={state.workbench.rightPanel.open}
          bottomDrawerOpen={state.workbench.bottomDrawer.open}
          onRefresh={loadSessions}
          onToggleLang={() => dispatch({ type: "set_lang", value: state.lang === "en" ? "zh" : "en" })}
          onToggleRightPanel={() => dispatch({ type: "workbench_right_panel_toggled" })}
          onToggleBottomDrawer={() => dispatch({ type: "workbench_bottom_drawer_toggled" })}
          onOpenPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
        />
      }
      sidebar={
        <Sidebar
          sidebarTab={state.sidebarTab}
          sessions={sessionCards}
          currentSessionId={state.currentSessionId}
          fileTree={state.fileTree}
          treeHeight={treeHeight}
          currentMode={currentMode}
          onTabChange={(v) => dispatch({ type: "set_sidebar", value: v })}
          onLoadSession={loadSession}
          onCreateSession={createSession}
          onOpenFile={openFile}
          onLoadFileChildren={loadFileChildren}
        />
      }
      main={
        <main className="main-chat">
          <Timeline
            ref={timelineRef}
            timeline={runtimeState.timelineView}
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
          />
          <Composer
            value={state.composer}
            onChange={(v) => dispatch({ type: "set_composer", value: v })}
            onSend={sendMessage}
            onStop={cancelSession}
            isRunning={currentStatus === "running" || currentStatus === "waiting_user_input"}
            currentMode={currentMode}
            commandHints={SLASH_COMMAND_HINTS}
          />
        </main>
      }
      rightPanel={
        <Inspector
          inspectorTab={state.inspectorTab}
          tasks={state.tasks}
          artifacts={state.artifacts}
          plan={state.plan}
          review={state.review}
          recipes={state.recipes}
          timeline={runtimeState.timelineItems}
          currentInteraction={runtimeState.currentInteraction}
          interactionNotice={interactionNotice}
          permissionContext={state.permissionContext}
          preview={state.preview}
          snapshot={state.snapshot}
          userAnswer={userAnswer}
          eventLog={state.eventLog}
          onTabChange={(v) => {
            dispatch({ type: "set_inspector", value: v });
            dispatch({ type: "workbench_surface_activated", placement: "right", kind: v });
          }}
          onOpenArtifact={openArtifact}
          onOpenReviewEvidence={openReviewEvidence}
          onRunRecipe={runRecipe}
          onUserAnswerChange={setUserAnswer}
          onRespondInteraction={respondToInteraction}
        />
      }
      bottomDrawer={
        <div className="workbench-drawer-empty" data-testid="workbench-drawer">
          Run output and long diagnostics
        </div>
      }
      rightPanelOpen={state.workbench.rightPanel.open}
      bottomDrawerOpen={state.workbench.bottomDrawer.open}
      onResizeSidebar={(e) => startResize(e, "--sidebar-w-raw", RESIZE_RIGHT)}
      onResizeRightPanel={(e) => startResize(e, "--inspector-w-raw", RESIZE_LEFT)}
    />
```

- [ ] **Step 7: Add shell CSS**

Append this CSS to `src/embedagent/frontend/gui/webapp/src/styles.css`:

```css
.workbench-layout {
  display: grid;
  grid-template-rows: var(--header-h) 1fr;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-canvas);
}

.workbench-header-slot {
  min-width: 0;
}

.workbench-body {
  display: grid;
  grid-template-columns: clamp(180px, var(--sidebar-w-raw), 380px) 4px minmax(0, 1fr) 4px clamp(220px, var(--inspector-w-raw), 520px);
  min-height: 0;
  overflow: hidden;
}

.workbench-layout.right-closed .workbench-body {
  grid-template-columns: clamp(180px, var(--sidebar-w-raw), 380px) 4px minmax(0, 1fr) 4px 0;
}

.workbench-sidebar-slot,
.workbench-main-slot,
.workbench-right-slot {
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.workbench-center {
  display: grid;
  grid-template-rows: minmax(0, 1fr);
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.workbench-layout.drawer-open .workbench-center {
  grid-template-rows: minmax(0, 1fr) 220px;
}

.workbench-bottom-slot {
  min-height: 0;
  border-top: 1px solid var(--border-default);
  background: var(--bg-default);
  overflow: auto;
}

.workbench-right-collapsed {
  background: var(--bg-default);
  border-left: 1px solid var(--bg-subtle);
}

.workbench-drawer-empty {
  height: 100%;
  padding: var(--sp-3);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 11px;
}

.drawer-toggle.active {
  color: var(--color-success);
  border-color: var(--color-success);
}
```

- [ ] **Step 8: Run GUI tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both commands PASS. The build output keeps the existing `dist`/static asset flow and does not report unsupported syntax for the `chrome109` target.

- [ ] **Step 9: Commit**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/AppSidebarLayout.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static
git commit -m "feat: add gui workbench shell layout"
```

Expected: commit succeeds. Include rebuilt GUI static assets only when `npm run build` changed `src/embedagent/frontend/gui/static`.

### Task 4: GUI Right Panel Surfaces And Bottom Drawer

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add static checks for right-panel source ownership**

Append these checks to `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
  const rightPanelTabsSource = fs.readFileSync(
    path.resolve(
      "src",
      "embedagent",
      "frontend",
      "gui",
      "webapp",
      "src",
      "components",
      "workbench",
      "RightPanelTabs.jsx",
    ),
    "utf8",
  );
  assert.equal(rightPanelTabsSource.includes("RIGHT_PANEL_SURFACES"), true);
  assert.equal(rightPanelTabsSource.includes("todos"), false);

  const bottomDrawerSource = fs.readFileSync(
    path.resolve(
      "src",
      "embedagent",
      "frontend",
      "gui",
      "webapp",
      "src",
      "components",
      "workbench",
      "BottomDrawer.jsx",
    ),
    "utf8",
  );
  assert.equal(bottomDrawerSource.includes("run_output"), true);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `RightPanelTabs.jsx` does not exist.

- [ ] **Step 3: Create `RightPanelTabs.jsx`**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx` with this content:

```javascript
import React from "react";
import { RIGHT_PANEL_SURFACES } from "../../workbench/surfaces.js";

const LABELS = {
  interaction: "Ask",
  tasks: "Tasks",
  plan: "Plan",
  artifacts: "Artifacts",
  run: "Run",
  problems: "Problems",
  review: "Review",
  permissions: "Permissions",
  runtime: "Runtime",
  preview: "Preview",
  log: "Log",
};

export default function RightPanelTabs({
  activeKind,
  counts,
  onSelect,
  children,
}) {
  const badges = counts || {};
  return (
    <aside className="right-panel" role="complementary" aria-label="Right panel" data-testid="right-panel">
      <div className="right-panel-tabs" role="tablist">
        {RIGHT_PANEL_SURFACES.map((kind) => (
          <button
            key={kind}
            type="button"
            role="tab"
            aria-selected={activeKind === kind}
            className={`right-panel-tab${activeKind === kind ? " active" : ""}`}
            onClick={() => onSelect(kind)}
            data-testid={`right-panel-tab--${kind}`}
          >
            <span>{LABELS[kind] || kind}</span>
            {badges[kind] > 0 ? <span className="tab-badge">{badges[kind]}</span> : null}
          </button>
        ))}
      </div>
      <div className="right-panel-body">{children}</div>
    </aside>
  );
}
```

- [ ] **Step 4: Create `BottomDrawer.jsx`**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx` with this content:

```javascript
import React from "react";

export default function BottomDrawer({
  activeKind,
  eventLog,
  terminationReason,
  terminationMessage,
}) {
  const entries = Array.isArray(eventLog) ? eventLog.slice(-80) : [];
  return (
    <section className="bottom-drawer" aria-label="Bottom drawer" data-testid="bottom-drawer">
      <div className="bottom-drawer-tabs" role="tablist">
        <button className={`bottom-drawer-tab${activeKind === "run_output" ? " active" : ""}`} type="button">
          Run Output
        </button>
        <button className={`bottom-drawer-tab${activeKind === "logs" ? " active" : ""}`} type="button">
          Logs
        </button>
      </div>
      <div className="bottom-drawer-body">
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
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Move tab ownership into `RightPanelTabs`**

Modify `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`:

1. Import `RIGHT_PANEL_SURFACES`.

```javascript
import { RIGHT_PANEL_SURFACES } from "../workbench/surfaces.js";
```

2. Replace the private `ALL_TABS` declaration with:

```javascript
const ALL_TABS = RIGHT_PANEL_SURFACES;
```

3. Keep `InspectorTabs` and existing body panels intact for this slice.

- [ ] **Step 6: Wire right-panel and drawer in `App.jsx`**

Add imports:

```javascript
import BottomDrawer from "./components/workbench/BottomDrawer.jsx";
import RightPanelTabs from "./components/workbench/RightPanelTabs.jsx";
```

Replace the `rightPanel={...}` slot from Task 3 with:

```javascript
      rightPanel={
        <RightPanelTabs
          activeKind={state.inspectorTab}
          counts={{
            interaction: runtimeState.currentInteraction || interactionNotice ? 1 : 0,
            tasks: state.tasks.length,
            artifacts: state.artifacts.length,
          }}
          onSelect={(kind) => {
            dispatch({ type: "set_inspector", value: kind });
            dispatch({ type: "workbench_surface_activated", placement: "right", kind });
          }}
        >
          <Inspector
            inspectorTab={state.inspectorTab}
            tasks={state.tasks}
            artifacts={state.artifacts}
            plan={state.plan}
            review={state.review}
            recipes={state.recipes}
            timeline={runtimeState.timelineItems}
            currentInteraction={runtimeState.currentInteraction}
            interactionNotice={interactionNotice}
            permissionContext={state.permissionContext}
            preview={state.preview}
            snapshot={state.snapshot}
            userAnswer={userAnswer}
            eventLog={state.eventLog}
            onTabChange={(v) => {
              dispatch({ type: "set_inspector", value: v });
              dispatch({ type: "workbench_surface_activated", placement: "right", kind: v });
            }}
            onOpenArtifact={openArtifact}
            onOpenReviewEvidence={openReviewEvidence}
            onRunRecipe={runRecipe}
            onUserAnswerChange={setUserAnswer}
            onRespondInteraction={respondToInteraction}
          />
        </RightPanelTabs>
      }
```

Replace the `bottomDrawer={...}` slot with:

```javascript
      bottomDrawer={
        <BottomDrawer
          activeKind={state.workbench.bottomDrawer.activeKind}
          eventLog={state.eventLog}
          terminationReason={state.terminationDisplayReason || state.terminationReason}
          terminationMessage={state.terminationMessage}
        />
      }
```

- [ ] **Step 7: Add panel and drawer CSS**

Append this CSS to `src/embedagent/frontend/gui/webapp/src/styles.css`:

```css
.right-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  background: var(--bg-default);
  border-left: 1px solid var(--bg-subtle);
}

.right-panel-tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  min-height: 34px;
  overflow-x: auto;
  border-bottom: 1px solid var(--border-default);
  padding: 0 var(--sp-2);
}

.right-panel-tab {
  height: 32px;
  padding: 0 8px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  cursor: pointer;
  white-space: nowrap;
}

.right-panel-tab:hover {
  color: var(--text-secondary);
}

.right-panel-tab.active {
  color: var(--color-success);
  border-bottom-color: var(--color-success);
}

.right-panel-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.right-panel-body .inspector {
  border-left: 0;
}

.right-panel-body .inspector-tabs {
  display: none;
}

.bottom-drawer {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: var(--bg-default);
}

.bottom-drawer-tabs {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  border-bottom: 1px solid var(--border-default);
  padding: 0 var(--sp-2);
  height: 30px;
  flex-shrink: 0;
}

.bottom-drawer-tab {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  height: 30px;
}

.bottom-drawer-tab.active {
  color: var(--color-success);
  border-bottom-color: var(--color-success);
}

.bottom-drawer-body {
  flex: 1;
  overflow: auto;
  padding: var(--sp-2) var(--sp-3);
  font-family: var(--font-mono);
  font-size: 10px;
}

.drawer-line {
  display: flex;
  gap: var(--sp-2);
  padding: 2px 0;
  color: var(--text-secondary);
  border-bottom: 1px solid rgba(139, 148, 158, 0.12);
}

.drawer-line.muted {
  color: var(--text-muted);
}

.drawer-label {
  color: var(--color-info);
  min-width: 120px;
}
```

- [ ] **Step 8: Run GUI tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both commands PASS. The source-string checks confirm `todos` and `mode-code` are absent from the new surface code.

- [ ] **Step 9: Commit**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static
git commit -m "feat: add gui workbench surfaces"
```

Expected: commit succeeds. Include rebuilt GUI static assets only when `npm run build` changed `src/embedagent/frontend/gui/static`.

### Task 5: GUI Command Palette And Composer Entry Points

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add static and pure command checks**

Append these checks to `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```javascript
  const commandPaletteSource = fs.readFileSync(
    path.resolve(
      "src",
      "embedagent",
      "frontend",
      "gui",
      "webapp",
      "src",
      "components",
      "workbench",
      "CommandPalette.jsx",
    ),
    "utf8",
  );
  assert.equal(commandPaletteSource.includes("visibleCommands"), true);
  assert.equal(commandPaletteSource.includes("cmd-palette"), true);

  const composerSource = fs.readFileSync(
    path.resolve("src", "embedagent", "frontend", "gui", "webapp", "src", "components", "Composer.jsx"),
    "utf8",
  );
  assert.equal(composerSource.includes("onOpenCommandPalette"), true);
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `CommandPalette.jsx` does not exist.

- [ ] **Step 3: Create `CommandPalette.jsx`**

Create `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx` with this content:

```javascript
import React from "react";
import { visibleCommands } from "../../workbench/commands.js";

function matchesQuery(command, query) {
  const normalized = String(query || "").trim().toLowerCase();
  if (!normalized) return true;
  return (
    command.id.toLowerCase().includes(normalized) ||
    command.label.toLowerCase().includes(normalized) ||
    command.group.toLowerCase().includes(normalized) ||
    String(command.slash || "").toLowerCase().includes(normalized)
  );
}

export default function CommandPalette({
  open,
  query,
  selectedIndex,
  context,
  onQueryChange,
  onClose,
  onSelect,
}) {
  if (!open) return null;
  const commands = visibleCommands(context || {}).filter((command) => matchesQuery(command, query));
  const selected = Math.max(0, Math.min(selectedIndex || 0, Math.max(commands.length - 1, 0)));
  return (
    <div className="cmd-palette-backdrop" role="presentation" onMouseDown={onClose}>
      <div className="cmd-palette" role="dialog" aria-label="Command palette" onMouseDown={(event) => event.stopPropagation()}>
        <input
          className="cmd-palette-input"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          autoFocus
          aria-label="Command search"
          data-testid="command-palette-input"
        />
        <div className="cmd-palette-list" role="listbox">
          {commands.map((command, index) => (
            <button
              key={command.id}
              type="button"
              className={`cmd-palette-item${index === selected ? " active" : ""}`}
              onClick={() => onSelect(command)}
              role="option"
              aria-selected={index === selected}
              data-testid={`command-palette-item--${command.id}`}
            >
              <span className="cmd-palette-title">{command.label}</span>
              <span className="cmd-palette-meta">{command.slash || command.id}</span>
            </button>
          ))}
          {commands.length === 0 ? (
            <div className="cmd-palette-empty">No matching command</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add composer palette entry point**

Modify `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`.

Add `onOpenCommandPalette` to the props:

```javascript
  onOpenCommandPalette,
```

Add this button before the send/stop button inside `.composer-inner`:

```javascript
        <button
          className="composer-tool"
          type="button"
          onClick={onOpenCommandPalette}
          aria-label="Open command palette"
          disabled={isRunning}
          data-testid="composer-command-palette"
        >
          /
        </button>
```

- [ ] **Step 5: Wire command execution in `App.jsx`**

Add imports:

```javascript
import CommandPalette from "./components/workbench/CommandPalette.jsx";
import { commandById } from "./workbench/commands.js";
import { DEFAULT_KEYBINDINGS, eventToKey, resolveKeybinding } from "./workbench/keybindings.js";
```

Add this function inside `App()`:

```javascript
  async function executeWorkbenchCommand(command) {
    if (!command) return;
    if (command.id === "palette.open") {
      dispatch({ type: "workbench_command_palette_opened" });
      return;
    }
    if (command.id === "palette.close") {
      dispatch({ type: "workbench_command_palette_closed" });
      return;
    }
    if (command.id === "session.new") {
      await createSession(currentMode);
      return;
    }
    if (command.id === "session.refresh") {
      await loadSessions();
      return;
    }
    if (command.id === "message.send") {
      await sendMessage();
      return;
    }
    if (command.id === "message.stop") {
      await cancelSession();
      return;
    }
    if (command.id === "view.toggle_right_panel") {
      dispatch({ type: "workbench_right_panel_toggled" });
      return;
    }
    if (command.id === "view.toggle_bottom_drawer") {
      dispatch({ type: "workbench_bottom_drawer_toggled" });
      return;
    }
    if (command.surface) {
      dispatch({ type: "set_inspector", value: command.surface });
      dispatch({ type: "workbench_surface_activated", placement: "right", kind: command.surface });
      return;
    }
    if (command.drawer) {
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: command.drawer });
      return;
    }
    if (command.slash) {
      await submitText(command.slash);
    }
  }
```

Add this keydown effect in `App()`:

```javascript
  useEffect(() => {
    function onWorkbenchKeyDown(event) {
      const command = resolveKeybinding(DEFAULT_KEYBINDINGS, eventToKey(event), {
        paletteOpen: state.workbench.commandPalette.open,
        isRunning: currentStatus === "running" || currentStatus === "waiting_user_input",
        composerFocused: document.activeElement?.dataset?.testid === "composer-input",
      });
      if (!command) return;
      event.preventDefault();
      void executeWorkbenchCommand(command);
    }
    window.addEventListener("keydown", onWorkbenchKeyDown);
    return () => window.removeEventListener("keydown", onWorkbenchKeyDown);
  }, [state.workbench.commandPalette.open, currentStatus, state.composer, state.currentSessionId]);
```

Pass `onOpenCommandPalette` into `Composer`:

```javascript
            onOpenCommandPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
```

Render `CommandPalette` as the last child inside `LangContext.Provider`:

```javascript
    <CommandPalette
      open={state.workbench.commandPalette.open}
      query={state.workbench.commandPalette.query}
      selectedIndex={state.workbench.commandPalette.selectedIndex}
      context={{
        hasSession: Boolean(state.currentSessionId),
        isRunning: currentStatus === "running" || currentStatus === "waiting_user_input",
        paletteOpen: state.workbench.commandPalette.open,
      }}
      onQueryChange={(query) => dispatch({ type: "workbench_command_palette_query_changed", query })}
      onClose={() => dispatch({ type: "workbench_command_palette_closed" })}
      onSelect={(command) => {
        dispatch({ type: "workbench_command_palette_closed" });
        void executeWorkbenchCommand(commandById(command.id));
      }}
    />
```

- [ ] **Step 6: Add command palette CSS**

Append this CSS to `src/embedagent/frontend/gui/webapp/src/styles.css`:

```css
.composer-tool {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  cursor: pointer;
}

.composer-tool:hover {
  color: var(--text-primary);
  border-color: var(--border-focus);
}

.cmd-palette-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(1, 4, 9, 0.42);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
}

.cmd-palette {
  width: min(680px, calc(100vw - 32px));
  max-height: min(520px, calc(100vh - 96px));
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-default);
  border-radius: var(--r-md);
  background: var(--bg-default);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.35);
  overflow: hidden;
}

.cmd-palette-input {
  height: 42px;
  border: 0;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-default);
  color: var(--text-primary);
  padding: 0 var(--sp-3);
  font-size: 14px;
  outline: none;
}

.cmd-palette-list {
  overflow: auto;
  padding: var(--sp-2);
}

.cmd-palette-item {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--sp-3);
  align-items: center;
  min-height: 34px;
  border: 1px solid transparent;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  padding: 0 var(--sp-2);
  cursor: pointer;
}

.cmd-palette-item:hover,
.cmd-palette-item.active {
  border-color: var(--border-focus);
  background: var(--bg-subtle);
  color: var(--text-primary);
}

.cmd-palette-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cmd-palette-meta {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.cmd-palette-empty {
  color: var(--text-muted);
  padding: var(--sp-3);
  font-family: var(--font-mono);
  font-size: 11px;
}
```

- [ ] **Step 7: Run GUI tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both commands PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/components/Composer.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static
git commit -m "feat: add gui command palette"
```

Expected: commit succeeds. Include rebuilt GUI static assets only when `npm run build` changed `src/embedagent/frontend/gui/static`.

### Task 6: TUI Workbench Command And Surface State

**Files:**
- Create: `src/embedagent/frontend/tui/workbench.py`
- Modify: `src/embedagent/frontend/tui/state.py`
- Modify: `src/embedagent/frontend/tui/reducer.py`
- Modify: `src/embedagent/frontend/tui/commands.py`
- Modify: `src/embedagent/frontend/tui/completion.py`
- Modify: `tests/test_terminal_frontend.py`

- [ ] **Step 1: Write failing TUI workbench tests**

Append this test code to `tests/test_terminal_frontend.py`:

```python
def test_tui_workbench_commands_and_surfaces():
    from embedagent.frontend.tui.workbench import (
        RIGHT_PANEL_SURFACES,
        WorkbenchState,
        command_by_id,
        open_surface,
        slash_command_names,
    )

    assert "tasks" in RIGHT_PANEL_SURFACES
    assert "preview" in RIGHT_PANEL_SURFACES
    assert command_by_id("surface.tasks").slash == "/tasks"
    assert command_by_id("message.send").slash == ""
    assert "code" not in [item.slash.lstrip("/") for item in slash_command_names()]

    state = WorkbenchState()
    assert state.right_panel_open is True
    assert state.active_surface == "tasks"
    next_state = open_surface(state, "preview")
    assert next_state is not state
    assert next_state.active_surface == "preview"
    assert next_state.right_panel_open is True
```

Append this test near the existing completer tests:

```python
def test_tui_slash_completion_uses_workbench_registry():
    from embedagent.frontend.tui.commands import command_names

    names = command_names()
    assert "tasks" in names
    assert "artifacts" in names
    assert "code" not in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_terminal_frontend.py::test_tui_workbench_commands_and_surfaces tests/test_terminal_frontend.py::test_tui_slash_completion_uses_workbench_registry -v
```

Expected: FAIL because `embedagent.frontend.tui.workbench` does not exist.

- [ ] **Step 3: Implement TUI workbench contract**

Create `src/embedagent/frontend/tui/workbench.py` with this content:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


RIGHT_PANEL_SURFACES = [
    "interaction",
    "tasks",
    "plan",
    "artifacts",
    "run",
    "problems",
    "review",
    "permissions",
    "runtime",
    "preview",
    "log",
]

BOTTOM_DRAWER_SURFACES = ["terminal", "run_output", "logs"]


@dataclass(frozen=True)
class WorkbenchCommand:
    id: str
    label: str
    group: str
    slash: str = ""
    surface: str = ""
    drawer: str = ""


WORKBENCH_COMMANDS = [
    WorkbenchCommand("session.new", "New Session", "session", "/new"),
    WorkbenchCommand("session.refresh", "Refresh Sessions", "session", "/sessions"),
    WorkbenchCommand("session.resume", "Resume Session", "session", "/resume"),
    WorkbenchCommand("message.send", "Send Message", "message"),
    WorkbenchCommand("message.stop", "Stop Running Turn", "message"),
    WorkbenchCommand("mode.explore", "Mode: Explore", "mode", "/mode explore"),
    WorkbenchCommand("mode.spec", "Mode: Spec", "mode", "/mode spec"),
    WorkbenchCommand("mode.build", "Mode: Build", "mode", "/mode build"),
    WorkbenchCommand("mode.debug", "Mode: Debug", "mode", "/mode debug"),
    WorkbenchCommand("mode.verify", "Mode: Verify", "mode", "/mode verify"),
    WorkbenchCommand("surface.interaction", "Open Interaction", "surface", "", "interaction"),
    WorkbenchCommand("surface.tasks", "Open Tasks", "surface", "/tasks", "tasks"),
    WorkbenchCommand("surface.plan", "Open Plan", "surface", "/plan", "plan"),
    WorkbenchCommand("surface.artifacts", "Open Artifacts", "surface", "/artifacts", "artifacts"),
    WorkbenchCommand("surface.run", "Open Run", "surface", "", "run"),
    WorkbenchCommand("surface.problems", "Open Problems", "surface", "", "problems"),
    WorkbenchCommand("surface.review", "Open Review", "surface", "/review", "review"),
    WorkbenchCommand("surface.permissions", "Open Permissions", "surface", "/permissions", "permissions"),
    WorkbenchCommand("surface.runtime", "Open Runtime", "surface", "/snapshot", "runtime"),
    WorkbenchCommand("surface.preview", "Open Preview", "surface", "", "preview"),
    WorkbenchCommand("surface.log", "Open Log", "surface", "", "log"),
    WorkbenchCommand("drawer.run_output", "Toggle Run Output", "surface", "", "", "run_output"),
    WorkbenchCommand("workspace.files", "Open Files", "workspace", "/workspace"),
    WorkbenchCommand("workflow.diff", "Review Diff", "workflow", "/diff"),
    WorkbenchCommand("view.toggle_right_panel", "Toggle Right Panel", "view"),
    WorkbenchCommand("view.toggle_bottom_drawer", "Toggle Bottom Drawer", "view"),
    WorkbenchCommand("palette.open", "Open Command Palette", "view", "/palette"),
    WorkbenchCommand("palette.close", "Close Command Palette", "view"),
    WorkbenchCommand("snapshot", "Show Snapshot", "session", "/snapshot"),
    WorkbenchCommand("close", "Close Auxiliary View", "view", "/close"),
    WorkbenchCommand("artifact.open", "Open Artifact", "workspace", "/artifact"),
    WorkbenchCommand("file.open", "Open File Preview", "workspace", "/open"),
    WorkbenchCommand("file.edit", "Edit File", "workspace", "/edit"),
    WorkbenchCommand("file.save", "Save File", "workspace", "/save"),
    WorkbenchCommand("explorer.open", "Open Explorer", "workspace", "/explorer"),
    WorkbenchCommand("inspector.open", "Open Inspector", "surface", "/inspector"),
    WorkbenchCommand("timeline.follow", "Toggle Follow Output", "view", "/follow"),
    WorkbenchCommand("help", "Help", "view", "/help"),
    WorkbenchCommand("quit", "Quit", "view", "/quit"),
]


@dataclass
class CommandPaletteState:
    open: bool = False
    query: str = ""
    selected_index: int = 0


@dataclass
class WorkbenchState:
    right_panel_open: bool = True
    bottom_drawer_open: bool = False
    active_surface: str = "tasks"
    active_drawer: str = "run_output"
    command_palette: CommandPaletteState = field(default_factory=CommandPaletteState)


def command_by_id(command_id: str) -> WorkbenchCommand:
    for command in WORKBENCH_COMMANDS:
        if command.id == command_id:
            return command
    return WorkbenchCommand("", "", "")


def slash_command_names() -> List[WorkbenchCommand]:
    values = []
    seen = set()
    for command in WORKBENCH_COMMANDS:
        if not command.slash:
            continue
        name = command.slash.strip().split()[0].lstrip("/")
        if name in seen:
            continue
        seen.add(name)
        values.append(WorkbenchCommand(command.id, command.label, command.group, "/" + name, command.surface, command.drawer))
    return values


def slash_name_strings() -> List[str]:
    return [item.slash.lstrip("/") for item in slash_command_names()]


def visible_palette_commands(query: str = "") -> List[WorkbenchCommand]:
    normalized = (query or "").strip().lower()
    if not normalized:
        return list(WORKBENCH_COMMANDS)
    matches = []
    for command in WORKBENCH_COMMANDS:
        haystack = " ".join([command.id, command.label, command.group, command.slash]).lower()
        if normalized in haystack:
            matches.append(command)
    return matches


def open_surface(state: WorkbenchState, surface: str) -> WorkbenchState:
    if surface not in RIGHT_PANEL_SURFACES:
        return state
    return WorkbenchState(
        right_panel_open=True,
        bottom_drawer_open=state.bottom_drawer_open,
        active_surface=surface,
        active_drawer=state.active_drawer,
        command_palette=state.command_palette,
    )


def open_drawer(state: WorkbenchState, drawer: str) -> WorkbenchState:
    if drawer not in BOTTOM_DRAWER_SURFACES:
        return state
    return WorkbenchState(
        right_panel_open=state.right_panel_open,
        bottom_drawer_open=True,
        active_surface=state.active_surface,
        active_drawer=drawer,
        command_palette=state.command_palette,
    )


def open_palette(state: WorkbenchState) -> WorkbenchState:
    palette = CommandPaletteState(open=True, query="", selected_index=0)
    return WorkbenchState(
        right_panel_open=state.right_panel_open,
        bottom_drawer_open=state.bottom_drawer_open,
        active_surface=state.active_surface,
        active_drawer=state.active_drawer,
        command_palette=palette,
    )


def close_palette(state: WorkbenchState) -> WorkbenchState:
    palette = CommandPaletteState(open=False, query="", selected_index=0)
    return WorkbenchState(
        right_panel_open=state.right_panel_open,
        bottom_drawer_open=state.bottom_drawer_open,
        active_surface=state.active_surface,
        active_drawer=state.active_drawer,
        command_palette=palette,
    )
```

- [ ] **Step 4: Add workbench state to terminal state**

Modify `src/embedagent/frontend/tui/state.py`:

```python
from embedagent.frontend.tui.workbench import WorkbenchState
```

Add this field to `TerminalState`:

```python
    workbench: WorkbenchState = field(default_factory=WorkbenchState)
```

- [ ] **Step 5: Source slash command names from workbench registry**

Modify `src/embedagent/frontend/tui/commands.py`:

```python
from embedagent.frontend.tui.workbench import slash_name_strings
```

Replace the body of `command_names()` with:

```python
def command_names() -> List[str]:
    return slash_name_strings()
```

Keep `ParsedCommand` and `parse_command` unchanged.

- [ ] **Step 6: Add reducer helpers**

Add this import near the top of `src/embedagent/frontend/tui/reducer.py` with the existing imports:

```python
from embedagent.frontend.tui.workbench import close_palette, open_drawer, open_palette, open_surface
```

Append these helpers to `src/embedagent/frontend/tui/reducer.py`:

```python


def set_workbench_surface(state: TerminalState, surface: str) -> None:
    state.workbench = open_surface(state.workbench, surface)
    state.inspector.tab = surface


def set_workbench_drawer(state: TerminalState, drawer: str) -> None:
    state.workbench = open_drawer(state.workbench, drawer)


def show_command_palette(state: TerminalState) -> None:
    state.workbench = open_palette(state.workbench)


def hide_command_palette(state: TerminalState) -> None:
    state.workbench = close_palette(state.workbench)
```

- [ ] **Step 7: Run TUI tests to verify green**

Run:

```bash
uv run pytest tests/test_terminal_frontend.py::test_tui_workbench_commands_and_surfaces tests/test_terminal_frontend.py::test_tui_slash_completion_uses_workbench_registry -v
```

Expected: PASS.

- [ ] **Step 8: Run the full terminal frontend test**

Run:

```bash
uv run pytest tests/test_terminal_frontend.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```bash
git add src/embedagent/frontend/tui/workbench.py src/embedagent/frontend/tui/state.py src/embedagent/frontend/tui/reducer.py src/embedagent/frontend/tui/commands.py src/embedagent/frontend/tui/completion.py tests/test_terminal_frontend.py
git commit -m "feat: add tui workbench state"
```

Expected: commit succeeds with only the listed files staged.

### Task 7: TUI Pi-Style Command Palette Overlay

**Files:**
- Create: `src/embedagent/frontend/tui/views/command_palette.py`
- Modify: `src/embedagent/frontend/tui/views/__init__.py`
- Modify: `src/embedagent/frontend/tui/layout.py`
- Modify: `src/embedagent/frontend/tui/controller.py`
- Modify: `src/embedagent/frontend/tui/views/header.py`
- Modify: `tests/test_terminal_frontend.py`

- [ ] **Step 1: Write failing overlay rendering tests**

Append this test code to `tests/test_terminal_frontend.py`:

```python
def test_tui_command_palette_rendering_filters_commands():
    from embedagent.frontend.tui.state import TerminalState
    from embedagent.frontend.tui.views.command_palette import build_command_palette_text

    state = TerminalState(workspace=".", initial_mode="explore")
    state.workbench.command_palette.open = True
    state.workbench.command_palette.query = "tasks"
    text = build_command_palette_text(state)
    assert "Open Tasks" in text
    assert "/tasks" in text
    assert "Mode: Build" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_terminal_frontend.py::test_tui_command_palette_rendering_filters_commands -v
```

Expected: FAIL because `views.command_palette` does not exist.

- [ ] **Step 3: Create command palette view**

Create `src/embedagent/frontend/tui/views/command_palette.py` with this content:

```python
from __future__ import annotations

from embedagent.frontend.tui.state import TerminalState
from embedagent.frontend.tui.workbench import visible_palette_commands


def build_command_palette_text(state: TerminalState) -> str:
    palette = state.workbench.command_palette
    if not palette.open:
        return ""
    commands = visible_palette_commands(palette.query)
    lines = [
        " Command Palette",
        " query: %s" % (palette.query or ""),
        "",
    ]
    if not commands:
        lines.append(" No matching command")
        return "\n".join(lines)
    selected = max(0, min(palette.selected_index, len(commands) - 1))
    for index, command in enumerate(commands[:12]):
        marker = ">" if index == selected else " "
        slash = command.slash or command.id
        lines.append("%s %-24s %s" % (marker, command.label[:24], slash))
    return "\n".join(lines)
```

- [ ] **Step 4: Export the view**

Modify `src/embedagent/frontend/tui/views/__init__.py`:

```python
from embedagent.frontend.tui.views.command_palette import build_command_palette_text
```

- [ ] **Step 5: Add overlay text area to layout**

Modify `src/embedagent/frontend/tui/layout.py` imports:

```python
from prompt_toolkit.layout.containers import ConditionalContainer, Float, FloatContainer, Window
```

Add this `TextArea` in `TerminalLayout.__init__` after `self.inspector`:

```python
        self.command_palette = TextArea(
            read_only=True,
            focusable=True,
            width=72,
            height=16,
            scrollbar=True,
            wrap_lines=False,
        )
```

In `_build_layout()`, assign the existing `Layout(HSplit(...))` content to `base_layout_content`, then return a `Layout` around a `FloatContainer`:

```python
        base_layout_content = HSplit(
            [
                header_window,
                Window(height=1, char=self.owner.theme.horizontal),
                body,
                Window(height=1, char=self.owner.theme.horizontal),
                self.composer,
            ]
        )
        return Layout(
            FloatContainer(
                content=base_layout_content,
                floats=[
                    Float(
                        content=ConditionalContainer(
                            content=self.command_palette,
                            filter=Condition(lambda: self.owner.state.workbench.command_palette.open),
                        ),
                        top=3,
                        left=8,
                    )
                ],
            )
        )
```

Add keybindings in `_build_key_bindings()`:

```python
        @bindings.add("c-k")
        def _(event):
            self.owner.controller.open_command_palette()

        @bindings.add("escape", filter=Condition(lambda: self.owner.state.workbench.command_palette.open))
        def _(event):
            self.owner.controller.close_command_palette()
```

- [ ] **Step 6: Wire controller methods**

Modify `src/embedagent/frontend/tui/controller.py`:

```python
from embedagent.frontend.tui.workbench import command_by_id
```

Add these methods to `TerminalController`:

```python
    def open_command_palette(self) -> None:
        reducer.show_command_palette(self.owner.state)
        self.owner.refresh_views()

    def close_command_palette(self) -> None:
        reducer.hide_command_palette(self.owner.state)
        self.owner.refresh_views()

    def execute_workbench_command(self, command_id: str) -> None:
        command = command_by_id(command_id)
        if not command.id:
            return
        if command.surface:
            reducer.set_workbench_surface(self.owner.state, command.surface)
            self.refresh_inspector(command.surface)
            self.owner.refresh_views()
            return
        if command.drawer:
            reducer.set_workbench_drawer(self.owner.state, command.drawer)
            self.owner.refresh_views()
            return
        if command.slash:
            self.handle_command(command.slash)
```

In `handle_command`, add a branch after `help`:

```python
        if name == "palette":
            self.open_command_palette()
            return
```

- [ ] **Step 7: Refresh overlay text**

Modify `src/embedagent/frontend/tui/app.py` imports:

```python
    build_command_palette_text,
```

Add this line to `TerminalApp.refresh_views()` before `self.application.invalidate()`:

```python
        self.layout.command_palette.text = build_command_palette_text(self.state)
```

- [ ] **Step 8: Show surface state in the header**

Modify the `second_line` string in `src/embedagent/frontend/tui/views/header.py`:

```python
    second_line = "host=%s  explorer=%s  surface=%s  main=%s  branch=%s  dirty=%s" % (
        state.capability.host_mode,
        state.explorer.tab,
        state.workbench.active_surface,
        state.main_view,
        branch,
        dirty,
    )
```

Append this after the existing `follow=off` block:

```python
    if state.workbench.command_palette.open:
        second_line += "  palette=open"
```

- [ ] **Step 9: Run TUI tests**

Run:

```bash
uv run pytest tests/test_terminal_frontend.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

Run:

```bash
git add src/embedagent/frontend/tui/views/command_palette.py src/embedagent/frontend/tui/views/__init__.py src/embedagent/frontend/tui/layout.py src/embedagent/frontend/tui/controller.py src/embedagent/frontend/tui/app.py src/embedagent/frontend/tui/views/header.py tests/test_terminal_frontend.py
git commit -m "feat: add tui command palette overlay"
```

Expected: commit succeeds with only the listed files staged.

### Task 8: Documentation, Build, And Compatibility Gates

**Files:**
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/modules/frontend-tui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/implementation-roadmap.md`

- [ ] **Step 1: Update frontend protocol documentation**

In `docs/frontend-protocol.md`, add this section under the frontend state/protocol boundary discussion:

```markdown
### Workbench Shell State

GUI and TUI may keep local workbench shell state for sidebar selection,
right-panel surfaces, bottom drawers, command-palette query, keybindings, and
layout density. This state is not session-history truth and is not an
activation or permission policy.

Frontend shell state must not decide tool visibility, execute tools, approve
permissions, change durable modes, infer transcript history, load extensions,
or mutate workflow state. Those decisions remain owned by Agent Core,
ExtensionManager, PermissionPolicy, SessionHistoryAssembler, and the existing
session/bootstrap protocol.
```

- [ ] **Step 2: Update GUI module documentation**

In `docs/modules/frontend-gui.md`, add this section:

```markdown
## Workbench Shell

The GUI shell is a T3code-inspired workbench composed of a thread/project
sidebar, central Agent timeline, rich composer, thread-scoped right-panel
surfaces, optional bottom drawer, command palette, and keybinding resolver.

The workbench contract lives under
`src/embedagent/frontend/gui/webapp/src/workbench/` and is frontend-local. It
consumes existing backend snapshots, bootstrap history, runtime projections,
task projections, permission context, artifacts, file trees, recipes, and tool
catalog read models. It does not own workflow policy, permission decisions,
tool activation, transcript history, extension loading, or provider behavior.

The webapp build continues to target `chrome109` for bundled WebView2 Fixed
Version 109 and Windows 7 compatibility. GUI runtime deployment must remain
offline and must not require Electron, CDN assets, runtime Node, Docker, WSL,
VS Code, or external online services.
```

- [ ] **Step 3: Update TUI module documentation**

In `docs/modules/frontend-tui.md`, add this section:

```markdown
## Workbench Shell

The TUI mirrors the GUI workbench vocabulary using prompt_toolkit: shared
command IDs, slash names, right-panel surfaces, bottom-drawer names, command
palette state, and keyboard-first overlays.

The TUI remains usable in raw console and low-color hosts. Pi-inspired
overlays and selectors are implemented as prompt_toolkit layout surfaces over
the existing reducer/controller/service boundaries. They do not change Agent
Core policy, workflow package ownership, tool activation, permission rules, or
session-history truth.
```

- [ ] **Step 4: Update tracker and changelog**

Add an entry to `docs/development-tracker.md`:

```markdown
## 2026-06-15 - T3code/Pi Workbench Shell

- Added frontend-local workbench shell contracts for GUI surfaces, commands,
  keybindings, command palette, right panel, and bottom drawer.
- Migrated GUI layout toward a T3code-style Agent workbench while preserving
  existing protocol/Core boundaries.
- Added TUI workbench command/surface state and Pi-style command palette
  overlay without changing Agent Core workflow policy.
```

Add an entry to `docs/design-change-log.md`:

```markdown
## 2026-06-15 - T3code-Inspired Pi-Bounded Workbench

Adopted T3code's workbench product shape for frontend shell interaction:
thread/project sidebar, central Agent timeline, rich composer,
thread-scoped right-panel surfaces, optional bottom drawer, command palette,
and keybinding rules.

Preserved Pi-style decoupling by keeping this state frontend-local and
read-model driven. Agent Core, ExtensionManager, PermissionPolicy,
SessionHistoryAssembler, workflow packages, transcript history, and tool
runtime policy remain authoritative.
```

If source code was copied from `reference/t3code`, append this exact attribution sentence to the same changelog entry:

```markdown
Selected frontend shell code was adapted from `reference/t3code`, licensed
under MIT; adapted files retain project-local ownership and offline
compatibility constraints.
```

- [ ] **Step 5: Update roadmap**

In `docs/implementation-roadmap.md`, add this item to the frontend or near-term section:

```markdown
- Continue polishing the T3code/Pi workbench shell with real Win7 WebView2 109
  smoke validation, narrow-width GUI layout validation, TUI raw-console
  validation, and C/C++ workflow task/run surface refinement.
```

- [ ] **Step 6: Run JavaScript tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both commands PASS.

- [ ] **Step 7: Run focused Python tests**

Run:

```bash
uv run pytest tests/test_terminal_frontend.py tests/test_gui_runtime.py tests/test_gui_backend_api.py -v
```

Expected: PASS.

- [ ] **Step 8: Run fast non-GUI test suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS.

- [ ] **Step 9: Run lint checks**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
```

Expected: both commands PASS.

- [ ] **Step 10: Run local GUI smoke**

Run this command in one terminal:

```bash
uv run python -m embedagent.frontend.gui.launcher D:\Project\coding_agent --host 127.0.0.1 --port 52341 --mode explore --model smoke-model --base-url http://127.0.0.1:8000/v1 --api-key smoke --headless
```

Open this URL in the in-app browser:

```text
http://127.0.0.1:52341/
```

Expected: the page loads with the workbench header, left sidebar, central Agent timeline/composer, right-panel tabs, and no blank screen. The browser console has no React render exception. Stop the headless GUI process with Ctrl+C after the check.

- [ ] **Step 11: Commit documentation and verification updates**

Run:

```bash
git add docs/frontend-protocol.md docs/modules/frontend-gui.md docs/modules/frontend-tui.md docs/development-tracker.md docs/design-change-log.md docs/implementation-roadmap.md src/embedagent/frontend/gui/static
git commit -m "docs: document t3code pi workbench"
```

Expected: commit succeeds. Include rebuilt GUI static assets only when `npm run build` changed `src/embedagent/frontend/gui/static`.

## Final Verification Matrix

Run these commands before declaring the implementation complete:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd D:\Project\coding_agent
uv run pytest tests/test_terminal_frontend.py tests/test_gui_runtime.py tests/test_gui_backend_api.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run ruff check src/ tests/
uv run black --check src/ tests/
```

Expected:

- JavaScript tests pass and print `frontend helper checks passed`.
- GUI webapp build succeeds with the existing `chrome109` target.
- TUI and GUI backend tests pass.
- Fast non-GUI Python suite passes.
- Ruff and Black checks pass.
- Local browser smoke loads `http://127.0.0.1:52341/` without a blank page.

## Review Checklist

- GUI and TUI use the same command IDs for shared shell actions.
- Workbench state is local UI state only.
- No frontend code imports Agent Core, harness internals, workflow package internals, permission policy internals, or transcript reducers.
- No new runtime dependency is added.
- No `todos`, `mode-code`, or first-class `code` mode vocabulary is introduced.
- No command or keybinding bypasses `/mode`, permission responses, or existing protocol calls.
- No WebView2, static build, or offline bundle assumption is weakened.
