# GUI Terminal Runtime Controller Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract GUI terminal action orchestration from `App.jsx` into a frontend-only terminal runtime controller while preserving current terminal drawer and right-panel behavior.

**Architecture:** Add `webapp/src/app-runtime/terminal-controller.js` as an injected controller over existing terminal HTTP helpers and reducer actions. Keep terminal execution in the GUI backend service, keep terminal normalization in `terminal-state.js`, and reduce `App.jsx` to wiring plus render composition.

**Tech Stack:** React 18, Vite, plain JavaScript ES modules, Node-based webapp tests, existing FastAPI GUI backend tests, existing GUI visual harness.

---

## Execution Setup

Run implementation in a dedicated worktree so `main` stays reviewable while the slice is in flight.

```bash
git worktree add .worktrees/gui-terminal-runtime-controller-boundary -b codex/gui-terminal-runtime-controller-boundary main
cd .worktrees/gui-terminal-runtime-controller-boundary
```

Verify the worktree starts from the design and plan commits:

```bash
git status --short --branch
git log --oneline -3
```

Expected: clean worktree on `codex/gui-terminal-runtime-controller-boundary`, with the latest commits including this plan and `dda905f docs: design gui terminal runtime controller boundary`.

## File Structure

Create:

- `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
  - GUI-only terminal action controller.
  - Owns no terminal execution, no backend protocol, no reducer state.
  - Depends on injected `getState`, `dispatch`, `api`, and `nextTerminalId`.

- `src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs`
  - Unit tests for all controller actions with injected fake APIs.

Modify:

- `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Import and execute `runTerminalControllerTests`.
  - Add source-level boundary assertions for `terminal-controller.js` and `App.jsx`.

- `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Import `createTerminalController`.
  - Add `stateRef` and controller wiring.
  - Remove inline terminal action cluster.
  - Route bottom drawer, right-panel terminal, and command branches through the controller.

- `src/embedagent/frontend/gui/static/assets/app.js`
  - Refreshed by `npm run build`.

- `docs/modules/frontend-gui.md`
  - Document `app-runtime/terminal-controller.js`.

- `docs/development-tracker.md`
  - Add the completed slice summary.

- `docs/design-change-log.md`
  - Add a new change record for this terminal runtime controller boundary.

Do not modify:

- Agent Core modules under `src/embedagent/core/`.
- Terminal backend service or terminal backend routes.
- Permission policy, workflow package, provider, extension, transcript, runtime reducer, operation reducer, compaction reducer, or recovery reducer code.

---

### Task 1: Terminal Controller Module

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs`
- Create: `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing controller tests**

Create `src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs` with this content:

```js
import assert from "node:assert/strict";

import { createTerminalController } from "../src/app-runtime/terminal-controller.js";

const SESSION_NOTICE = "Open a session before using the terminal.";

function baseState(overrides = {}) {
  return {
    currentSessionId: "sess-1",
    terminal: {
      activeTerminalId: "term-1",
      terminalIds: ["term-1"],
      sessions: {
        "term-1": { terminalId: "term-1", buffer: "" },
      },
    },
    workbench: {
      rightPanel: {
        surfaces: [],
      },
    },
    ...overrides,
  };
}

function createHarness(options = {}) {
  let state = options.state || baseState();
  const actions = [];
  const apiCalls = [];
  const failures = options.failures || {};
  const snapshotFor = (terminalId) => ({
    session_id: state.currentSessionId,
    terminal_id: terminalId,
    status: "running",
    history: `history:${terminalId}`,
    sequence: 1,
    cols: 100,
    rows: 30,
  });
  const maybeFail = (name) => {
    if (failures[name]) {
      throw new Error(failures[name]);
    }
  };
  const api = {
    listTerminals: async (sessionId) => {
      apiCalls.push({ name: "listTerminals", args: [sessionId] });
      maybeFail("listTerminals");
      return { terminals: [{ session_id: sessionId, terminal_id: "term-1", status: "running" }] };
    },
    openTerminal: async (sessionId, terminalId, options) => {
      apiCalls.push({ name: "openTerminal", args: [sessionId, terminalId, options] });
      maybeFail("openTerminal");
      return { terminal: snapshotFor(terminalId) };
    },
    writeTerminal: async (sessionId, terminalId, text) => {
      apiCalls.push({ name: "writeTerminal", args: [sessionId, terminalId, text] });
      maybeFail("writeTerminal");
      return { ok: true };
    },
    clearTerminal: async (sessionId, terminalId) => {
      apiCalls.push({ name: "clearTerminal", args: [sessionId, terminalId] });
      maybeFail("clearTerminal");
      return { terminal: { ...snapshotFor(terminalId), history: "" } };
    },
    restartTerminal: async (sessionId, terminalId, options) => {
      apiCalls.push({ name: "restartTerminal", args: [sessionId, terminalId, options] });
      maybeFail("restartTerminal");
      return { terminal: { ...snapshotFor(terminalId), sequence: 2 } };
    },
    closeTerminal: async (sessionId, terminalId) => {
      apiCalls.push({ name: "closeTerminal", args: [sessionId, terminalId] });
      maybeFail("closeTerminal");
      return { ok: true };
    },
  };
  const controller = createTerminalController({
    getState: () => state,
    dispatch: (action) => actions.push(action),
    api,
    nextTerminalId: (ids) => `term-${ids.length + 1}`,
  });
  return {
    actions,
    apiCalls,
    controller,
    setState(nextState) {
      state = nextState;
    },
  };
}

function actionTypes(actions) {
  return actions.map((action) => action.type);
}

export async function runTerminalControllerTests() {
  {
    const harness = createHarness({ state: baseState({ currentSessionId: "" }) });
    const result = await harness.controller.ensureOpen();
    assert.equal(result, null);
    assert.deepEqual(harness.apiCalls, []);
    assert.deepEqual(harness.actions, [
      { type: "interaction_notice_set", notice: SESSION_NOTICE },
    ]);
  }

  {
    const harness = createHarness();
    const result = await harness.controller.ensureOpen();
    assert.equal(result, "term-1");
    assert.deepEqual(harness.apiCalls[0], {
      name: "openTerminal",
      args: ["sess-1", "term-1", { cols: 100, rows: 30 }],
    });
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_snapshot_loaded",
      "terminal_active_set",
      "workbench_surface_activated",
    ]);
    assert.deepEqual(harness.actions[2], {
      type: "workbench_surface_activated",
      placement: "bottom",
      kind: "terminal",
    });
  }

  {
    const harness = createHarness();
    const result = await harness.controller.openSession("term-2");
    assert.equal(result, "term-2");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_snapshot_loaded",
      "terminal_active_set",
    ]);
    assert.equal(harness.actions[1].terminalId, "term-2");
  }

  {
    const harness = createHarness();
    await harness.controller.refresh();
    assert.deepEqual(harness.apiCalls[0], { name: "listTerminals", args: ["sess-1"] });
    assert.deepEqual(harness.actions[0], {
      type: "terminal_summaries_loaded",
      terminals: [{ session_id: "sess-1", terminal_id: "term-1", status: "running" }],
    });
  }

  {
    const harness = createHarness({ failures: { listTerminals: "metadata unavailable" } });
    await harness.controller.refresh();
    assert.deepEqual(harness.apiCalls[0], { name: "listTerminals", args: ["sess-1"] });
    assert.deepEqual(harness.actions, []);
  }

  {
    const harness = createHarness();
    await harness.controller.sendTo("term-1", "dir\n");
    assert.deepEqual(harness.actions[0], { type: "terminal_active_set", terminalId: "term-1" });
    assert.deepEqual(harness.apiCalls[0], {
      name: "writeTerminal",
      args: ["sess-1", "term-1", "dir\n"],
    });
  }

  {
    const harness = createHarness({ failures: { writeTerminal: "pipe closed" } });
    await harness.controller.sendTo("term-1", "dir\n");
    assert.deepEqual(harness.actions.at(-1), {
      type: "interaction_notice_set",
      notice: "pipe closed",
    });
  }

  {
    const harness = createHarness();
    await harness.controller.clearById("term-1");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_active_set",
      "terminal_snapshot_loaded",
    ]);
    assert.deepEqual(harness.apiCalls[0], { name: "clearTerminal", args: ["sess-1", "term-1"] });
  }

  {
    const harness = createHarness();
    await harness.controller.restartById("term-1");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_active_set",
      "terminal_snapshot_loaded",
    ]);
    assert.deepEqual(harness.apiCalls[0], {
      name: "restartTerminal",
      args: ["sess-1", "term-1", { cols: 100, rows: 30 }],
    });
  }

  {
    const harness = createHarness();
    await harness.controller.closeActive();
    assert.deepEqual(harness.apiCalls[0], { name: "closeTerminal", args: ["sess-1", "term-1"] });
    assert.deepEqual(harness.actions[0], {
      type: "terminal_event",
      event: { type: "closed", session_id: "sess-1", terminal_id: "term-1" },
    });
  }

  {
    const harness = createHarness();
    await harness.controller.selectBottomDrawerKind("terminal");
    assert.equal(harness.apiCalls[0].name, "openTerminal");
    assert.equal(harness.actions.at(-1).kind, "terminal");
  }

  {
    const harness = createHarness();
    await harness.controller.selectBottomDrawerKind("run_output");
    assert.deepEqual(harness.apiCalls, []);
    assert.deepEqual(harness.actions[0], {
      type: "workbench_surface_activated",
      placement: "bottom",
      kind: "run_output",
    });
  }

  {
    const harness = createHarness({
      state: baseState({
        terminal: {
          activeTerminalId: "term-1",
          terminalIds: ["term-1"],
          sessions: { "term-1": { terminalId: "term-1" } },
        },
        workbench: {
          rightPanel: {
            surfaces: [
              {
                id: "right:terminal:term-2",
                kind: "terminal",
                terminalId: "term-2",
                terminalIds: ["term-2"],
                activeTerminalId: "term-2",
              },
            ],
          },
        },
      }),
    });
    const result = await harness.controller.openRightPanelSurface();
    assert.equal(result, "term-3");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_snapshot_loaded",
      "terminal_active_set",
      "workbench_surface_opened",
      "set_inspector",
    ]);
    assert.equal(harness.actions[2].kind, "terminal");
    assert.deepEqual(harness.actions[2].terminalIds, ["term-3"]);
    assert.deepEqual(harness.actions[3], { type: "set_inspector", value: "terminal" });
  }

  {
    const surface = { id: "right:terminal:term-1", kind: "terminal", terminalIds: ["term-1"] };
    const harness = createHarness();
    const result = await harness.controller.splitRightPanelSurface(surface, "vertical");
    assert.equal(result, "term-2");
    assert.deepEqual(harness.actions.at(-1), {
      type: "workbench_terminal_surface_split",
      placement: "right",
      surfaceId: "right:terminal:term-1",
      terminalId: "term-2",
      splitDirection: "vertical",
    });
  }

  {
    const surface = { id: "right:terminal:term-1", kind: "terminal" };
    const harness = createHarness();
    harness.controller.activateRightPanelPane(surface, "term-1");
    assert.deepEqual(harness.actions, [
      {
        type: "workbench_terminal_surface_terminal_activated",
        placement: "right",
        surfaceId: "right:terminal:term-1",
        terminalId: "term-1",
      },
      { type: "terminal_active_set", terminalId: "term-1" },
    ]);
  }

  {
    const surface = { id: "right:terminal:term-1", kind: "terminal" };
    const harness = createHarness();
    const result = await harness.controller.closeRightPanelPane(surface, "term-1");
    assert.equal(result, "term-1");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_event",
      "workbench_terminal_surface_terminal_closed",
    ]);
    assert.deepEqual(harness.actions[1], {
      type: "workbench_terminal_surface_terminal_closed",
      placement: "right",
      surfaceId: "right:terminal:term-1",
      terminalId: "term-1",
    });
  }
}
```

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```js
import { runTerminalControllerTests } from "./terminal-controller.test.mjs";
```

Add the import near the existing `runTerminalStateTests` import. Then call the test near the other terminal tests:

```js
  runTerminalStateTests();
  await runTerminalControllerTests();
```

- [ ] **Step 2: Run the webapp tests to verify the new test fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with a module resolution error for `../src/app-runtime/terminal-controller.js` or a missing `createTerminalController` export.

- [ ] **Step 3: Implement the terminal controller**

Create `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`:

```js
const TERMINAL_DIMENSIONS = Object.freeze({ cols: 100, rows: 30 });
const SESSION_NOTICE = "Open a session before using the terminal.";

function noop() {}

function readState(getState) {
  const state = typeof getState === "function" ? getState() : {};
  return state && typeof state === "object" ? state : {};
}

function readTerminalState(state) {
  return state.terminal || { activeTerminalId: "", terminalIds: [], sessions: {} };
}

function readSessionId(state) {
  return String(state.currentSessionId || "");
}

function readApi(deps, name) {
  const candidate = deps.api && deps.api[name];
  return typeof candidate === "function" ? candidate : null;
}

function noticeFromError(error, fallback) {
  return error && error.message ? error.message : fallback;
}

function dispatchNotice(dispatch, notice) {
  dispatch({ type: "interaction_notice_set", notice });
}

function normalizeTerminalId(terminalId) {
  return String(terminalId || "");
}

function uniqueStrings(values) {
  const seen = {};
  const result = [];
  for (const value of values) {
    const normalized = normalizeTerminalId(value);
    if (!normalized || seen[normalized]) continue;
    seen[normalized] = true;
    result.push(normalized);
  }
  return result;
}

function terminalIdsFromSurface(surface) {
  if (!surface || surface.kind !== "terminal") return [];
  if (Array.isArray(surface.terminalIds)) return surface.terminalIds;
  return [surface.terminalId];
}

function allKnownTerminalIds(state) {
  const terminal = readTerminalState(state);
  const surfaces = state.workbench?.rightPanel?.surfaces || [];
  const panelIds = surfaces.flatMap(terminalIdsFromSurface);
  return uniqueStrings([...(terminal.terminalIds || []), ...panelIds]);
}

function nextId(deps, ids) {
  if (typeof deps.nextTerminalId === "function") {
    return normalizeTerminalId(deps.nextTerminalId(ids));
  }
  return `terminal-${ids.length + 1}`;
}

export function createTerminalController(deps = {}) {
  const dispatch = typeof deps.dispatch === "function" ? deps.dispatch : noop;
  const getState = () => readState(deps.getState);

  function requireSession() {
    const state = getState();
    const sessionId = readSessionId(state);
    if (!sessionId) {
      dispatchNotice(dispatch, SESSION_NOTICE);
      return null;
    }
    return { state, sessionId };
  }

  async function ensureOpen(preferredId = "") {
    const context = requireSession();
    if (!context) return null;
    const terminal = readTerminalState(context.state);
    const terminalId =
      normalizeTerminalId(preferredId) ||
      normalizeTerminalId(terminal.activeTerminalId) ||
      nextId(deps, terminal.terminalIds || []);
    const openTerminal = readApi(deps, "openTerminal");
    if (!openTerminal || !terminalId) return null;
    try {
      const payload = await openTerminal(context.sessionId, terminalId, TERMINAL_DIMENSIONS);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      dispatch({ type: "terminal_active_set", terminalId });
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: "terminal" });
      return terminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, "Terminal failed to open."));
      return null;
    }
  }

  async function openSession(terminalId = "") {
    const context = requireSession();
    if (!context) return null;
    const terminal = readTerminalState(context.state);
    const targetTerminalId = normalizeTerminalId(terminalId) || nextId(deps, terminal.terminalIds || []);
    const openTerminal = readApi(deps, "openTerminal");
    if (!openTerminal || !targetTerminalId) return null;
    try {
      const payload = await openTerminal(context.sessionId, targetTerminalId, TERMINAL_DIMENSIONS);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, "Terminal failed to open."));
      return null;
    }
  }

  async function refresh() {
    const state = getState();
    const sessionId = readSessionId(state);
    if (!sessionId) return;
    const listTerminals = readApi(deps, "listTerminals");
    if (!listTerminals) return;
    try {
      const payload = await listTerminals(sessionId);
      dispatch({ type: "terminal_summaries_loaded", terminals: payload.terminals || [] });
    } catch (_) {
      return;
    }
  }

  async function sendTo(terminalId, text) {
    const state = getState();
    const sessionId = readSessionId(state);
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!sessionId || !targetTerminalId) return null;
    const writeTerminal = readApi(deps, "writeTerminal");
    if (!writeTerminal) return null;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      await writeTerminal(sessionId, targetTerminalId, text);
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, "Terminal write failed."));
      return null;
    }
  }

  async function sendActive(text) {
    const terminal = readTerminalState(getState());
    return sendTo(terminal.activeTerminalId, text);
  }

  async function clearById(terminalId) {
    const state = getState();
    const sessionId = readSessionId(state);
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!sessionId || !targetTerminalId) return null;
    const clearTerminal = readApi(deps, "clearTerminal");
    if (!clearTerminal) return null;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      const payload = await clearTerminal(sessionId, targetTerminalId);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, "Terminal clear failed."));
      return null;
    }
  }

  async function clearActive() {
    const terminal = readTerminalState(getState());
    return clearById(terminal.activeTerminalId);
  }

  async function restartById(terminalId) {
    const state = getState();
    const sessionId = readSessionId(state);
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!sessionId || !targetTerminalId) return null;
    const restartTerminal = readApi(deps, "restartTerminal");
    if (!restartTerminal) return null;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      const payload = await restartTerminal(sessionId, targetTerminalId, TERMINAL_DIMENSIONS);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, "Terminal restart failed."));
      return null;
    }
  }

  async function restartActive() {
    const terminal = readTerminalState(getState());
    return restartById(terminal.activeTerminalId);
  }

  async function closeActive() {
    const state = getState();
    const sessionId = readSessionId(state);
    const terminal = readTerminalState(state);
    const terminalId = normalizeTerminalId(terminal.activeTerminalId);
    if (!sessionId || !terminalId) return null;
    const closeTerminal = readApi(deps, "closeTerminal");
    if (!closeTerminal) return null;
    try {
      await closeTerminal(sessionId, terminalId);
      dispatch({
        type: "terminal_event",
        event: { type: "closed", session_id: sessionId, terminal_id: terminalId },
      });
      return terminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, "Terminal close failed."));
      return null;
    }
  }

  async function selectBottomDrawerKind(kind) {
    if (kind === "terminal") {
      return ensureOpen();
    }
    dispatch({ type: "workbench_surface_activated", placement: "bottom", kind });
    return kind;
  }

  async function openRightPanelSurface(preferredId = "") {
    const state = getState();
    const terminalId = normalizeTerminalId(preferredId) || nextId(deps, allKnownTerminalIds(state));
    const openedTerminalId = await openSession(terminalId);
    if (!openedTerminalId) return null;
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: "terminal",
      title: "Terminal",
      resourceId: openedTerminalId,
      terminalId: openedTerminalId,
      terminalIds: [openedTerminalId],
      activeTerminalId: openedTerminalId,
    });
    dispatch({ type: "set_inspector", value: "terminal" });
    return openedTerminalId;
  }

  async function splitRightPanelSurface(surface, splitDirection = "horizontal") {
    if (!surface || surface.kind !== "terminal") return null;
    const terminalId = nextId(deps, allKnownTerminalIds(getState()));
    const openedTerminalId = await openSession(terminalId);
    if (!openedTerminalId) return null;
    dispatch({
      type: "workbench_terminal_surface_split",
      placement: "right",
      surfaceId: surface.id,
      terminalId: openedTerminalId,
      splitDirection,
    });
    return openedTerminalId;
  }

  function activateRightPanelPane(surface, terminalId) {
    if (!surface || surface.kind !== "terminal") return null;
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!targetTerminalId) return null;
    dispatch({
      type: "workbench_terminal_surface_terminal_activated",
      placement: "right",
      surfaceId: surface.id,
      terminalId: targetTerminalId,
    });
    dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
    return targetTerminalId;
  }

  async function closeRightPanelPane(surface, terminalId) {
    if (!surface || surface.kind !== "terminal") return null;
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!targetTerminalId) return null;
    const context = requireSession();
    if (!context) return null;
    const closeTerminal = readApi(deps, "closeTerminal");
    if (!closeTerminal) return null;
    try {
      await closeTerminal(context.sessionId, targetTerminalId);
      dispatch({
        type: "terminal_event",
        event: { type: "closed", session_id: context.sessionId, terminal_id: targetTerminalId },
      });
      dispatch({
        type: "workbench_terminal_surface_terminal_closed",
        placement: "right",
        surfaceId: surface.id,
        terminalId: targetTerminalId,
      });
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, "Terminal close failed."));
      return null;
    }
  }

  return {
    ensureOpen,
    openSession,
    refresh,
    sendActive,
    sendTo,
    clearActive,
    clearById,
    restartActive,
    restartById,
    closeActive,
    selectBottomDrawerKind,
    openRightPanelSurface,
    splitRightPanelSurface,
    activateRightPanelPane,
    closeRightPanelPane,
  };
}
```

- [ ] **Step 4: Run tests and verify the controller passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 5: Commit the controller module**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test: cover gui terminal controller boundary"
```

Expected: commit succeeds and `git status --short` is clean.

---

### Task 2: App Wiring

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing source assertions for the App boundary**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, extend the existing `appSource` assertions. Replace the terminal-specific block currently expecting inline terminal function names with this stricter block:

```js
  assert.equal(appSource.includes("createTerminalController"), true);
  assert.equal(appSource.includes("stateRef.current = state"), true);
  assert.equal(appSource.includes("terminalController.ensureOpen"), true);
  assert.equal(appSource.includes("terminalController.openSession"), true);
  assert.equal(appSource.includes("terminalController.openRightPanelSurface"), true);
  assert.equal(appSource.includes("terminalController.splitRightPanelSurface"), true);
  assert.equal(appSource.includes("terminalController.closeRightPanelPane"), true);
  assert.equal(appSource.includes("async function ensureTerminalOpen"), false);
  assert.equal(appSource.includes("async function openTerminalSession"), false);
  assert.equal(appSource.includes("async function refreshTerminals"), false);
  assert.equal(appSource.includes("async function sendTerminalInput"), false);
  assert.equal(appSource.includes("async function sendTerminalInputTo"), false);
  assert.equal(appSource.includes("async function clearActiveTerminal"), false);
  assert.equal(appSource.includes("async function clearTerminalById"), false);
  assert.equal(appSource.includes("async function restartActiveTerminal"), false);
  assert.equal(appSource.includes("async function restartTerminalById"), false);
  assert.equal(appSource.includes("async function closeActiveTerminal"), false);
  assert.equal(appSource.includes("async function openRightPanelTerminalSurface"), false);
  assert.equal(appSource.includes("async function splitRightPanelTerminalSurface"), false);
  assert.equal(appSource.includes("function activateRightPanelTerminalPane"), false);
  assert.equal(appSource.includes("async function closeRightPanelTerminalPane"), false);
  assert.equal(appSource.includes("function allKnownTerminalIds"), false);
```

Keep the existing assertions for `AppSidebarLayout`, `WorkbenchHeader`, loader boundaries, workspace actions, source-control actions, file preview actions, and right-panel actions.

- [ ] **Step 2: Run tests and verify the source assertions fail**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `App.jsx` does not yet import `createTerminalController` and still defines inline terminal functions.

- [ ] **Step 3: Wire `App.jsx` to the controller**

Add this import near the other `app-runtime` imports in `src/embedagent/frontend/gui/webapp/src/App.jsx`:

```js
import { createTerminalController } from "./app-runtime/terminal-controller.js";
```

Add a state ref immediately after the existing refs:

```js
  const currentSessionIdRef = useRef("");
  const sessionEventLogRef = useRef(sessionEventLog);
  const stateRef = useRef(state);
  stateRef.current = state;
```

Create the controller after `interactionNotice` is defined:

```js
  const terminalController = useMemo(
    () =>
      createTerminalController({
        getState: () => stateRef.current,
        dispatch,
        api: {
          listTerminals,
          openTerminal,
          writeTerminal,
          clearTerminal,
          restartTerminal,
          closeTerminal,
        },
        nextTerminalId,
      }),
    [],
  );
```

Remove the complete inline function definitions for these terminal-specific helpers from `App.jsx`:

- `ensureTerminalOpen`
- `openTerminalSession`
- `refreshTerminals`
- `sendTerminalInput`
- `sendTerminalInputTo`
- `clearActiveTerminal`
- `clearTerminalById`
- `restartActiveTerminal`
- `restartTerminalById`
- `closeActiveTerminal`
- `selectBottomDrawerKind`
- `allKnownTerminalIds`
- `openRightPanelTerminalSurface`
- `splitRightPanelTerminalSurface`
- `activateRightPanelTerminalPane`
- `closeRightPanelTerminalPane`

Keep `rightPanelSurfaceTitle`, `normalizeFileSurfacePath`, `fileSurfaceTitle`, `openRightPanelSurface`, and file/source-control helpers.

Update `openRightPanelSurface` so terminal surfaces go through the controller:

```js
  function openRightPanelSurface(kind, title = "") {
    const surfaceKind = String(kind || "");
    if (surfaceKind === "file") return;
    if (surfaceKind === "terminal") {
      void terminalController.openRightPanelSurface();
      return;
    }
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: surfaceKind,
      title: rightPanelSurfaceTitle(surfaceKind, title),
      resourceId: surfaceKind === "diff" ? "current" : "",
    });
    dispatch({ type: "set_inspector", value: surfaceKind });
  }
```

Update terminal command routing:

```js
    if (command.drawer) {
      if (command.drawer === "terminal") {
        await terminalController.ensureOpen();
        return;
      }
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: command.drawer });
      return;
    }
```

Update right-panel terminal activation:

```js
            if (surface.kind === "terminal" && surface.activeTerminalId) {
              void terminalController.openSession(surface.activeTerminalId);
            }
```

Update `RightPanelSurfaceBody` terminal callbacks:

```jsx
            onTerminalNew={() => terminalController.openRightPanelSurface()}
            onTerminalSplit={() => terminalController.splitRightPanelSurface(activeRightPanelSurface)}
            onTerminalSplitVertical={() =>
              terminalController.splitRightPanelSurface(activeRightPanelSurface, "vertical")
            }
            onTerminalSelect={(terminalId) =>
              terminalController.activateRightPanelPane(activeRightPanelSurface, terminalId)
            }
            onTerminalSend={terminalController.sendTo}
            onTerminalClear={terminalController.clearById}
            onTerminalRestart={terminalController.restartById}
            onTerminalClose={(terminalId) =>
              terminalController.closeRightPanelPane(activeRightPanelSurface, terminalId)
            }
```

Update `BottomDrawer` terminal callbacks:

```jsx
          onKindSelect={(kind) => {
            void terminalController.selectBottomDrawerKind(kind);
          }}
          onTerminalNew={() => terminalController.ensureOpen(nextTerminalId(state.terminal.terminalIds))}
          onTerminalSelect={(terminalId) => dispatch({ type: "terminal_active_set", terminalId })}
          onTerminalSend={terminalController.sendActive}
          onTerminalClear={terminalController.clearActive}
          onTerminalRestart={terminalController.restartActive}
          onTerminalClose={terminalController.closeActive}
```

- [ ] **Step 4: Run tests and verify App wiring passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 5: Commit the App wiring**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "refactor: route gui terminal actions through controller"
```

Expected: commit succeeds and `git status --short` is clean.

---

### Task 3: Source Boundary Hardening

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add source assertions for the controller boundary**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, after the existing `sessionLoadersSource` and `visualDebugFixturesSource` assertions, add:

```js
  const terminalControllerSource = fs.readFileSync(
    webappSourcePath("app-runtime", "terminal-controller.js"),
    "utf8",
  );
  assert.equal(terminalControllerSource.includes("createTerminalController"), true);
  assert.equal(terminalControllerSource.includes("TERMINAL_DIMENSIONS"), true);
  assert.equal(terminalControllerSource.includes("Open a session before using the terminal."), true);
  assert.equal(terminalControllerSource.includes("workbench_surface_opened"), true);
  assert.equal(terminalControllerSource.includes("workbench_terminal_surface_split"), true);
  assert.equal(terminalControllerSource.includes("workbench_terminal_surface_terminal_closed"), true);
  assert.equal(terminalControllerSource.includes("fetch("), false);
  assert.equal(terminalControllerSource.includes("new WebSocket"), false);
  assert.equal(terminalControllerSource.includes("useEffect"), false);
  assert.equal(terminalControllerSource.includes("import React"), false);
  assert.equal(terminalControllerSource.includes("from \"../terminal/terminal-api"), false);
  assert.equal(terminalControllerSource.includes("from \"../terminal/terminal-state"), false);
  assert.equal(terminalControllerSource.includes("embedagent"), false);

  const terminalApiSource = fs.readFileSync(
    webappSourcePath("terminal", "terminal-api.js"),
    "utf8",
  );
  assert.equal(terminalApiSource.includes("/api/sessions/"), true);
  assert.equal(terminalApiSource.includes("fetch("), true);
```

- [ ] **Step 2: Run tests and verify assertions pass**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 3: Commit the boundary assertions**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test: assert gui terminal controller boundary"
```

Expected: commit succeeds and `git status --short` is clean.

---

### Task 4: Static Assets And Durable Docs

**Files:**
- Modify: `src/embedagent/frontend/gui/static/assets/app.js`
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Rebuild bundled GUI assets**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: PASS. The generated static bundle under `src/embedagent/frontend/gui/static/assets/` changes.

- [ ] **Step 2: Commit the refreshed static assets**

Run:

```bash
git add src/embedagent/frontend/gui/static/assets/app.js
git commit -m "build: refresh gui terminal controller assets"
```

Expected: commit succeeds. If `git status --short` shows no static asset changes, record that the build was deterministic and skip this commit.

- [ ] **Step 3: Update `docs/modules/frontend-gui.md`**

In `docs/modules/frontend-gui.md`, update the app-runtime responsibility bullet to include the terminal controller:

```markdown
- GUI app-runtime boundary for frontend-only socket effect derivation, session/app loader request orchestration, session bootstrap projection, terminal runtime action orchestration, and dev-only visual fixtures（`webapp/src/app-runtime/`）
```

In the `GUI App Runtime Boundary` section, replace the current paragraph with:

```markdown
`webapp/src/app-runtime/` owns frontend-only runtime interpretation helpers.
`session-loaders.js` owns private loader request vocabulary, loader request
execution against injected GUI callbacks, and session bootstrap projection from
the official `/api/sessions/{id}/bootstrap` payload. `socket-message-effects.js`
maps existing WebSocket messages into private webapp descriptors: reducer
actions, session event-log entries, and loader requests. `terminal-controller.js`
coordinates existing terminal API helpers and reducer actions for bottom-drawer
terminal actions plus right-panel terminal open/split/activate/close behavior.
`App.jsx` remains the executor of HTTP route calls, reducer dispatch, event-log
reset, session activation terminal summary loading, task/artifact refreshes,
and render composition in this slice. `visual-debug-fixtures.js` owns the
development-only `?visual_debug=1` fixtures used by the visual harness. This
boundary is not a backend protocol, not session-history truth, and does not
change Agent Core, workflow packages, permission policy, terminal execution,
source-control execution, provider configuration, extension loading, telemetry,
or runtime reducers.
```

- [ ] **Step 4: Update `docs/development-tracker.md`**

Add this section above the `GUI Session/App Loader Runtime Boundary` section:

```markdown
### 2026-06-18 - GUI Terminal Runtime Controller Boundary

- React webapp `webapp/src/app-runtime/terminal-controller.js` now owns GUI terminal action orchestration for bottom-drawer terminal actions and right-panel terminal open/split/activate/close behavior.
- `App.jsx` wires the controller through injected state, dispatch, terminal API helpers, and terminal id generation, while root render composition and command routing remain incremental follow-on work.
- Existing terminal HTTP helpers remain in `webapp/src/terminal/terminal-api.js`, and terminal snapshot/event normalization remains in `webapp/src/terminal/terminal-state.js`.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, terminal backend service, workflow package, permission policy, transcript, source-control, provider configuration, extension loading, telemetry, or runtime reducer semantics changed.
```

Update the header line to:

```markdown
> 更新日期：2026-06-18（GUI terminal runtime controller boundary）
```

- [ ] **Step 5: Update `docs/design-change-log.md`**

Add this record above `DC-173`:

```markdown
### DC-174

- 日期：2026-06-18
- 变更主题：GUI terminal runtime controller boundary
- 变更摘要：
  - React webapp 新增 `webapp/src/app-runtime/terminal-controller.js`，集中管理 GUI terminal action orchestration，包括 bottom drawer terminal open/send/clear/restart/close 和 right-panel terminal open/split/activate/close。
  - `App.jsx` 通过注入 state reader、dispatch、terminal API helpers 和 `nextTerminalId` 来装配 controller，不再承载大段 inline terminal action cluster。
  - Terminal HTTP route helpers 仍位于 `webapp/src/terminal/terminal-api.js`，terminal snapshot/event normalization 仍位于 `webapp/src/terminal/terminal-state.js`。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js`
  - `src/embedagent/frontend/gui/webapp/src/terminal/terminal-state.js`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/superpowers/specs/2026-06-18-gui-terminal-runtime-controller-boundary-design.md`
  - `docs/superpowers/plans/2026-06-18-gui-terminal-runtime-controller-boundary.md`
- 是否需要 ADR：否；该 controller 是 GUI app-shell implementation detail，不是 backend protocol、terminal execution owner、session-history truth 或 Agent Core extension API。
- 后续动作：
  - 可继续按相同模式规划 command router、source-control action controller 或 file preview controller 切片，让 `App.jsx` 进一步收敛为 composition shell。
```

- [ ] **Step 6: Run docs/source tests and commit docs**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

Commit:

```bash
git add docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record gui terminal controller boundary"
```

Expected: commit succeeds and `git status --short` is clean.

---

### Task 5: Full Verification

**Files:**
- No planned source changes.
- If verification exposes a defect, fix it in the narrowest file and rerun the failing command before continuing.

- [ ] **Step 1: Run the full webapp test suite**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS with `frontend helper checks passed`.

- [ ] **Step 2: Run the webapp production build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: PASS.

- [ ] **Step 3: Run focused GUI backend terminal/API tests**

Run from the repository root:

```bash
uv run pytest tests/test_gui_terminal_service.py tests/test_gui_terminal_api.py tests/test_gui_backend_api.py -q
```

Expected: PASS.

- [ ] **Step 4: Run rendered visual QA**

Run from the repository root:

```bash
node scripts/gui-visual-debug.mjs --scenario timeline,responsive --no-build --output "$env:TEMP\embedagent-gui-terminal-runtime-controller"
```

Expected: PASS with zero relevant console errors or warnings. The output summary should still show rich timeline rows and responsive right-panel checks.

- [ ] **Step 5: Inspect final diff boundaries**

Run:

```bash
git diff --stat main HEAD
git diff main HEAD -- src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

Expected:

- `App.jsx` imports and wires `createTerminalController`.
- `App.jsx` no longer defines the removed inline terminal action cluster.
- `terminal-controller.js` contains no `fetch(`, `new WebSocket`, React import, backend import, or Agent Core import.
- No Python Agent Core file changed.

- [ ] **Step 6: Final status check**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected: clean worktree on `codex/gui-terminal-runtime-controller-boundary`, with commits for controller tests/module, App wiring, boundary assertions, static assets if changed, and docs.

---

## Self-Review Checklist

- Spec coverage:
  - Controller module: Task 1.
  - `App.jsx` wiring and inline cluster removal: Task 2.
  - Boundary assertions: Task 3.
  - Static asset refresh and durable docs: Task 4.
  - Webapp, backend, build, and visual verification: Task 5.

- Scope check:
  - No task changes Agent Core.
  - No task changes terminal backend service or backend API routes.
  - No task introduces a dependency.
  - No task writes terminal output into transcript, workflow, telemetry, source-control, or reducer truth.

- Interface consistency:
  - Factory name: `createTerminalController`.
  - Controller methods: `ensureOpen`, `openSession`, `refresh`, `sendActive`, `sendTo`, `clearActive`, `clearById`, `restartActive`, `restartById`, `closeActive`, `selectBottomDrawerKind`, `openRightPanelSurface`, `splitRightPanelSurface`, `activateRightPanelPane`, `closeRightPanelPane`.
  - Injected APIs: `listTerminals`, `openTerminal`, `writeTerminal`, `clearTerminal`, `restartTerminal`, `closeTerminal`.
  - Existing reducer actions are unchanged.
