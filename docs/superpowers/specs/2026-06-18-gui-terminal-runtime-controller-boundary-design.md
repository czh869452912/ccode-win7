# GUI Terminal Runtime Controller Boundary Design

## Goal

Move the GUI one step closer to the `reference/t3code` frontend architecture by extracting terminal action orchestration from `App.jsx` into a GUI-only runtime controller boundary.

This slice should keep Agent Core small and independent. Terminal execution remains a GUI app-shell hosted surface backed by the existing terminal backend service and HTTP routes. The new frontend controller only coordinates existing GUI terminal API calls, reducer actions, bottom-drawer activation, and right-panel terminal surface actions.

## Current Baseline

The GUI already has:

- `webapp/src/terminal/terminal-api.js` for terminal HTTP route helpers.
- `webapp/src/terminal/terminal-state.js` for terminal snapshot/event normalization and reducer state.
- `components/workbench/BottomDrawer.jsx` for the terminal drawer UI.
- `components/workbench/RightPanelTerminalSurface.jsx` for grouped right-panel terminal panes.
- `app-runtime/session-loaders.js` and `app-runtime/socket-message-effects.js` for frontend-only app/session runtime boundaries.

However, `App.jsx` still owns the terminal orchestration cluster:

- `ensureTerminalOpen`
- `openTerminalSession`
- `refreshTerminals`
- `sendTerminalInput` and `sendTerminalInputTo`
- `clearActiveTerminal` and `clearTerminalById`
- `restartActiveTerminal` and `restartTerminalById`
- `closeActiveTerminal`
- bottom drawer terminal selection
- right-panel terminal open, split, activate, and close actions
- terminal-related command routing branches

This keeps root render composition coupled to app-shell terminal behavior and makes future T3-style terminal UX work harder to test without touching unrelated session, socket, source-control, file preview, or render code.

## Reference Findings

The relevant T3code lesson is terminal state and terminal UI orchestration separation:

- `reference/t3code/apps/web/src/terminalUiStateStore.ts` keeps terminal UI state actions such as open, height, split, new terminal, ensure terminal, active terminal, close, and reconcile terminal ids outside root component rendering.
- `reference/t3code/packages/client-runtime/src/terminalSessionState.ts` keeps terminal session metadata, buffers, attach events, snapshots, close/error/restart handling, and invalidation in a runtime manager.
- T3's terminal client runtime is separate from the agent kernel. The frontend owns display/session read models and action orchestration; the backend/runtime owns actual terminal execution.

EmbedAgent should copy this separation in a smaller dependency-free form that fits the current React/Vite webapp, WebView2 109, Windows 7, offline deployment, and no-runtime-Node constraints.

## Product Principles

1. Agent Core remains small, Pi-like, and independent from GUI terminal display and app-shell orchestration.
2. The GUI terminal is app-shell hosted display/control state, not workflow truth.
3. Terminal buffers remain ephemeral GUI display state.
4. Terminal output must not be written to `transcript.jsonl`, telemetry, workflow state, source-control checkpoints, runtime reducers, or permission reducer truth.
5. The terminal backend remains Windows 7-compatible Python stdlib subprocess pipes, not a PTY stack.
6. No dependency may be added on ConPTY, `node-pty`, `pywinpty`, `pexpect`, Electron, runtime Node, Docker, WSL, VS Code, online services, or external control planes.
7. This slice must not introduce source-control mutation, remote terminal providers, or hidden network behavior.
8. The controller is a frontend implementation detail, not a backend protocol or Agent Core extension boundary.

## Scope

### In Scope

- Add a GUI-only terminal controller module under `src/embedagent/frontend/gui/webapp/src/app-runtime/`.
- Move terminal action orchestration out of `App.jsx` into a factory with injected dependencies.
- Keep existing terminal HTTP helpers in `webapp/src/terminal/terminal-api.js`.
- Keep existing terminal reducer normalization in `webapp/src/terminal/terminal-state.js`.
- Keep `App.jsx` as the root composition layer that wires state, dispatch, API helpers, and controller callbacks.
- Preserve current terminal API behavior and current reducer action shapes.
- Preserve bottom drawer terminal activation behavior.
- Preserve right-panel terminal surface behavior: open, split, activate pane, close pane.
- Add focused webapp tests for controller behavior and source-level boundary assertions.
- Update GUI docs and changelog after implementation.

### Out Of Scope

- Agent Core changes.
- Backend API or protocol changes.
- Terminal backend service changes.
- Permission policy changes.
- Transcript, workflow, provider, extension, runtime reducer, operation reducer, compaction reducer, or recovery reducer changes.
- Adding a new state management dependency.
- Replacing terminal rendering components.
- Implementing a real PTY.
- Implementing remote terminal sessions.
- Implementing source-control mutations, staging, commit, push, pull, or checkpoints.
- Fully extracting command routing, source-control actions, file preview actions, WebSocket lifecycle, or all render composition from `App.jsx`.

## Recommended Approach

Use a narrow frontend runtime controller with injected state, dispatch, APIs, id generation, and surface helpers.

### Option A: Keep Terminal Actions Inline In `App.jsx`

Pros:

- Smallest immediate diff.
- No new module surface.

Cons:

- Keeps a large app-shell terminal cluster in the root component.
- Makes terminal behavior hard to test without rendering the full app.
- Slows future T3 terminal parity work.

### Option B: Extract A GUI Terminal Runtime Controller

Create `app-runtime/terminal-controller.js`. The controller receives existing dependencies from `App.jsx` and exposes terminal actions for the bottom drawer, right panel, and command handlers.

Pros:

- Low risk and easy to test with injected fakes.
- Shrinks `App.jsx` without changing backend or Agent Core contracts.
- Matches the T3 direction of keeping terminal UI/session orchestration outside root rendering.
- Creates a repeatable controller pattern for future source-control and command-router slices.

Cons:

- `App.jsx` still owns command routing and passes controller actions into components.
- A later slice is still needed to move command routing out of the root component.

### Option C: Full Terminal UI State Rewrite

Introduce a persistent terminal UI store similar to T3's `terminalUiStateStore.ts`, then refactor bottom drawer and right-panel terminal components around that store.

Pros:

- Could converge closer to T3's final shape.

Cons:

- Larger blast radius.
- Higher visual and interaction regression risk.
- Likely requires broader component changes and persistence decisions.
- Too large for the next safe architecture slice.

Recommendation: use Option B.

## Architecture

### `app-runtime/terminal-controller.js`

This module should be GUI frontend-only. It should not import React, open WebSockets, call `fetch` directly, use DOM APIs, import Agent Core/backend Python concepts, or mutate globals.

It should expose a factory:

```js
export function createTerminalController(deps) {
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

The dependency object should be explicit and small:

- `getState()` returns the current reducer state.
- `dispatch(action)` dispatches existing reducer actions.
- `api` contains existing terminal API functions: `listTerminals`, `openTerminal`, `writeTerminal`, `clearTerminal`, `restartTerminal`, and `closeTerminal`.
- `nextTerminalId(ids)` generates the next terminal id.
- optional `surfaceTitle(kind, fallback)` or equivalent helper remains injected if needed.

The controller should use only existing reducer actions:

- `interaction_notice_set`
- `terminal_summaries_loaded`
- `terminal_snapshot_loaded`
- `terminal_active_set`
- `terminal_event`
- `workbench_surface_activated`
- `workbench_surface_opened`
- `workbench_terminal_surface_split`
- `workbench_terminal_surface_terminal_activated`
- `workbench_terminal_surface_terminal_closed`
- `set_inspector`

The controller should preserve the existing terminal dimensions used by `App.jsx` for open/restart requests: `{ cols: 100, rows: 30 }`.

### `App.jsx`

After this slice, `App.jsx` should:

- import `createTerminalController`
- construct a controller with existing API helpers, `dispatch`, `getState`, and `nextTerminalId`
- pass controller actions into bottom drawer, right-panel terminal surface, command handlers, and effects
- retain root render composition
- retain command routing for this slice, but call controller methods for terminal branches
- no longer define the large terminal action function cluster inline

`App.jsx` may keep small local helpers that are not terminal-specific or that belong to generic right-panel surface title/path behavior.

### Existing Terminal Modules

`terminal-api.js` remains the concrete HTTP helper boundary. The controller should call these helpers through injection rather than importing them directly if practical, so tests can run without browser fetch.

`terminal-state.js` remains the reducer read-model boundary for terminal snapshots and events. This slice should not change its normalization rules unless a small compatibility bug is discovered during tests.

`BottomDrawer.jsx` and `RightPanelTerminalSurface.jsx` remain display components. They receive callbacks and terminal state; they do not call backend APIs directly.

## Data Flow

1. `App.jsx` creates the terminal controller with injected dependencies.
2. UI events or command routing call controller methods.
3. The controller reads the latest reducer state through `getState()`.
4. The controller calls existing injected terminal API helpers when needed.
5. The controller dispatches existing reducer actions.
6. Terminal WebSocket events continue to enter through existing socket handling and `terminal-state.js`.
7. Components render from existing reducer state.

The controller never owns terminal execution truth, session history truth, workflow state, permission decisions, or source-control behavior.

## Error Handling

- If there is no active session, terminal actions that need a session dispatch the current notice: `Open a session before using the terminal.`
- Open failures dispatch `Terminal failed to open.`
- Write failures dispatch `Terminal write failed.`
- Clear failures dispatch `Terminal clear failed.`
- Restart failures dispatch `Terminal restart failed.`
- Close failures dispatch `Terminal close failed.`
- Refresh failures remain quiet and dispatch empty summaries only where current behavior already does so.
- Missing or blank terminal ids are ignored for id-scoped actions.
- Closing a right-panel terminal pane dispatches both the terminal close event and the workbench pane close action only after the backend close succeeds.
- Unknown bottom drawer kinds activate the bottom drawer normally; `terminal` routes through `ensureOpen()`.

## Testing Strategy

### Webapp Unit Tests

Add `test/terminal-controller.test.mjs` covering:

- `ensureOpen()` without a current session dispatches the existing notice.
- `ensureOpen()` opens the active or next terminal id, dispatches snapshot, active terminal, and bottom drawer activation actions.
- `openSession(id)` returns the opened id and dispatches snapshot plus active terminal.
- `refresh()` loads terminal summaries when a session exists and quietly ignores API failures.
- `sendTo(id, text)` sets the active terminal and calls the write API.
- `clearById(id)` and `restartById(id)` dispatch snapshot updates from API responses.
- `closeActive()` calls the close API and dispatches the existing `closed` terminal event shape.
- `selectBottomDrawerKind("terminal")` routes through `ensureOpen()`.
- `openRightPanelSurface()` opens a terminal and dispatches `workbench_surface_opened` plus `set_inspector`.
- `splitRightPanelSurface(surface, direction)` opens a new terminal and dispatches the split action.
- `activateRightPanelPane(surface, id)` updates both the surface active terminal and global active terminal.
- `closeRightPanelPane(surface, id)` closes the backend terminal and dispatches both terminal and surface close actions.
- API errors map to the existing interaction notices.

### Source-Level Boundary Tests

Extend existing source assertions so:

- `terminal-controller.js` does not contain `fetch(`, `new WebSocket`, `useEffect`, React imports, or backend/Core imports.
- `App.jsx` imports `createTerminalController`.
- `App.jsx` no longer defines the old inline terminal action cluster.
- `terminal-api.js` remains the only frontend module with concrete terminal HTTP route fetches.

### Existing Webapp Verification

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

### Focused Backend GUI Tests

Run from the repository root:

```bash
uv run pytest tests/test_gui_terminal_service.py tests/test_gui_terminal_api.py tests/test_gui_backend_api.py -q
```

### Rendered Visual QA

Run the visual harness:

```bash
node scripts/gui-visual-debug.mjs --scenario timeline,responsive --no-build --output "$env:TEMP\embedagent-gui-terminal-runtime-controller"
```

If a local browser runtime or app server is unavailable, record the blocker and keep unit/build/backend verification explicit.

## Documentation

After implementation, update durable docs:

- `docs/modules/frontend-gui.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

Docs should state:

- `app-runtime/terminal-controller.js` is a GUI-only runtime controller boundary.
- It coordinates existing terminal API helpers and reducer actions.
- Terminal execution remains owned by the GUI terminal backend service.
- Terminal display buffers remain ephemeral GUI state.
- No Agent Core, backend protocol, permission policy, workflow package, transcript, source-control, provider configuration, extension loading, telemetry, or runtime reducer behavior changed.

## Risks And Mitigations

### Risk: The Controller Becomes A Second Terminal Protocol

Mitigation: keep it private to the webapp source tree, use existing API helpers, use existing reducer actions, and document it as GUI implementation detail only.

### Risk: Terminal Interaction Regresses During Extraction

Mitigation: keep route helpers and reducer state unchanged, extract only action orchestration, and cover all existing terminal actions with injected unit tests.

### Risk: Right-Panel Terminal Group Behavior Changes

Mitigation: preserve the current reducer action names and payloads for open, split, activate, and close; verify with visual responsive harness.

### Risk: `App.jsx` Still Has Too Much Command Logic

Mitigation: treat command-router extraction as a later slice. This slice succeeds if terminal orchestration is isolated and tested.

## Success Criteria

- `app-runtime/terminal-controller.js` owns terminal action orchestration.
- `App.jsx` wires the controller and no longer defines the large terminal function cluster inline.
- Existing terminal API route helpers remain in `terminal-api.js`.
- Existing terminal reducer normalization remains in `terminal-state.js`.
- Bottom drawer terminal behavior is preserved.
- Right-panel terminal open/split/activate/close behavior is preserved.
- Webapp unit tests pass.
- Webapp build passes.
- Focused terminal/backend GUI tests pass.
- Visual timeline/responsive harness passes or any local harness blocker is documented.
- Static GUI assets are rebuilt if implementation changes bundled webapp output.
- No Agent Core, backend protocol, terminal backend service, permission policy, workflow package, transcript truth, source-control behavior, provider configuration, extension loading, telemetry, or runtime reducer changes are made.
