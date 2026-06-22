# GUI App Runtime Controller Boundary Design

## Goal

Move the GUI closer to the `reference/t3code` frontend architecture by creating a frontend-only runtime controller boundary around app/session orchestration effects, without adding complexity to Agent Core.

The first implementation slice should make `App.jsx` less responsible for interpreting runtime messages and hosting development fixtures. It should not rewrite the full GUI shell. It should establish a small, testable pattern that later slices can extend for bootstrap loaders, terminal surfaces, source-control surfaces, and command routing.

## Current Baseline

The GUI has already moved toward a T3 Code-style workbench, but `App.jsx` still carries too many responsibilities:

- app bootstrap and active-workspace refresh orchestration
- session list, session bootstrap, task, artifact, permission, recipe, file-tree, and source-control loaders
- WebSocket connection lifecycle and message interpretation
- live session event projection into reducer actions
- visual debug fixture construction and hook installation
- terminal and right-panel surface handlers
- command palette actions, resize behavior, and render composition

The latest timeline slice improved the display read model, but the root component is still the place where unrelated runtime concerns meet. This makes future T3 parity work harder to test and increases the temptation to push display concerns into backend or Agent Core contracts.

## Reference Findings

The useful lesson from `reference/t3code` is the frontend architecture boundary, not a dependency set or a full product clone:

- `reference/t3code/apps/web/src/store.ts` separates thread/session/read-model state from component rendering.
- `reference/t3code/apps/web/src/orchestrationEventEffects.ts` maps orchestration event batches into explicit frontend effects.
- `reference/t3code/apps/web/src/uiStateStore.ts`, `threadSelectionStore.ts`, and related stores keep UI state frontend-local.
- T3's frontend accepts backend/runtime events, derives local read models and effects, and keeps components focused on composition and display.

This repository should apply the same boundary in a smaller form that fits the offline, Windows 7, and low-dependency product constraints.

## Product Principles

1. Agent Core remains small, Pi-like, and independent from GUI display concerns.
2. GUI runtime effects are frontend app-shell behavior, not protocol truth.
3. `transcript.jsonl -> Session -> SessionHistoryAssembler -> /api/sessions/{id}/bootstrap` remains durable session-history truth.
4. `timeline.jsonl` remains transport/replay infrastructure only.
5. No new runtime dependency may weaken offline deployment or Windows 7 support.
6. Development-only visual fixtures must not become product protocol.
7. The first slice should reduce coupling and create a repeatable boundary, not perform a full `App.jsx` rewrite.

## Scope

### In Scope

- Add `src/embedagent/frontend/gui/webapp/src/app-runtime/` as a GUI-only runtime boundary.
- Extract visual debug fixture builders and hook installation from `App.jsx` into `app-runtime/visual-debug-fixtures.js`.
- Extract WebSocket message interpretation from `App.jsx` into a pure effect-derivation module, `app-runtime/socket-message-effects.js`.
- Keep actual HTTP loaders and reducer dispatch ownership in `App.jsx` for this first slice, but execute socket-derived effect descriptors through a small local adapter.
- Add focused webapp tests for fixture contracts and socket message effect mapping.
- Keep the existing WebSocket connection helper and lifecycle behavior intact.
- Keep rich timeline behavior and responsive shell behavior from the previous slice intact.
- Update GUI documentation and progress docs after implementation.

### Out Of Scope

- Agent Core changes.
- Backend API or protocol changes.
- Permission policy, tool execution, workflow package, transcript, runtime reducer, operation reducer, compaction reducer, or recovery reducer changes.
- Replacing the whole GUI state model.
- Introducing Zustand, TanStack Query, Electron, runtime Node, or other T3 dependencies.
- Moving terminal execution, source-control execution, or file preview behavior into Agent Core.
- Full extraction of every loader from `App.jsx`.
- Source-control mutations, remote providers, push, pull, staging, commit, or checkpoint mutation.

## Recommended Approach

Use a narrow frontend-local runtime boundary with pure derivation functions and explicit effect descriptors.

### Option A: Keep Patching `App.jsx`

Pros:

- Smallest immediate diff.
- No new module structure.

Cons:

- Keeps runtime interpretation, fixture setup, and rendering composition tangled.
- Does not move the architecture toward T3's separation.
- Makes future GUI parity changes harder to test.

### Option B: Narrow Runtime Boundary

Add `app-runtime` modules for socket effect derivation and visual debug fixtures, while leaving loader execution in `App.jsx` for now.

Pros:

- Establishes the architectural boundary with limited risk.
- Keeps pure message interpretation testable without React or a browser.
- Shrinks `App.jsx` without a broad rewrite.
- Preserves current backend and Agent Core contracts.

Cons:

- `App.jsx` still owns many loaders after this slice.
- A later slice is needed to move more runtime orchestration into hooks/controllers.

### Option C: Full App Runtime Rewrite

Move bootstrap, loader orchestration, WebSocket handling, terminal state, source-control state, and command routing into a new controller layer in one change.

Pros:

- Could produce the cleanest final shape faster.

Cons:

- Too much blast radius.
- Hard to review and verify.
- Higher risk of regressing active workspace, terminal, source-control, and timeline behavior together.

Recommendation: use Option B.

## Architecture

### `app-runtime/socket-message-effects.js`

This module should be pure. It should not import React, open WebSockets, call `fetch`, mutate global state, or know about DOM APIs.

It should expose a function such as:

```js
deriveSocketMessageEffects({ type, data, currentSessionId })
```

The return value should use this private webapp descriptor shape:

```js
{
  actions: [],
  eventLogEntries: [],
  loaderRequests: []
}
```

Each `actions` item is an existing reducer action object. Each `eventLogEntries` item is an existing GUI event-log entry object. Each `loaderRequests` item is a plain object with a `name` field and optional arguments, using only this first-slice request vocabulary:

- `load_app_bootstrap`
- `load_active_workspace_data`
- `load_sessions`
- `load_session`
- `load_tasks`
- `load_artifacts`
- `load_permission_context`
- `load_file_children`

`App.jsx` remains responsible for executing those descriptors through existing functions such as `loadSessions`, `loadTasks`, `loadArtifacts`, `loadPermissionContext`, `loadFileChildren`, `loadSession`, and `loadActiveWorkspaceData`.

The module should cover the same WebSocket message cases that `App.jsx` handles today. Unknown message types should produce an empty effect result.

### `app-runtime/visual-debug-fixtures.js`

This module should own development-only fixture construction:

- timeline fixture state
- interaction fixture state
- thread lifecycle fixture state
- visual debug hook installation and cleanup helper

It should keep fixtures deterministic and local to the webapp. It must not call backend APIs, write session history, or affect production behavior unless `visual_debug=1` is present.

`App.jsx` should pass the small set of callbacks needed for fixture installation instead of embedding the fixture bodies inline.

### `App.jsx`

After this slice, `App.jsx` should remain the root composition component:

- initialize app bootstrap
- connect WebSocket using the existing lifecycle helper
- execute socket-derived effect descriptors
- own existing async loader functions for now
- pass projected runtime state into workbench components
- host terminal and right-panel handlers until later slices extract them

This keeps the first slice incremental while still changing the architecture direction.

### Future Runtime Controller Slices

This design intentionally leaves room for later slices:

- extract app/session/bootstrap loaders into a controller hook or loader module
- isolate terminal group state and source-control surface state further
- split command palette routing from render composition
- continue shrinking `App.jsx` toward a shell composition component

Those are follow-up slices, not acceptance criteria for this one.

## Data Flow

1. The GUI receives app bootstrap and session bootstrap through existing HTTP APIs.
2. The GUI receives live events through the existing WebSocket connection.
3. The WebSocket lifecycle code parses each message and calls `deriveSocketMessageEffects(...)`.
4. `App.jsx` executes the returned plain effect descriptors:
   - dispatch reducer actions
   - append event-log entries
   - invoke existing loader functions
   - guard current-session refreshes by session id
5. Existing frontend read models project runtime state into the timeline, right panel, terminal drawer, and app shell.
6. No socket effect writes transcript history, changes permission policy, or updates Agent Core state directly.

## Error Handling

- Unknown socket message types return no effects.
- Malformed socket payloads should be treated defensively and should not throw from the pure derivation module.
- Loader failures keep the existing behavior owned by the loader functions.
- WebSocket reconnect and close behavior stay in the existing lifecycle code.
- Visual debug fixture installation should no-op when `window` is unavailable or `visual_debug=1` is absent.
- Fixture cleanup should remove only the debug hook it installed.

## Testing Strategy

### Webapp Unit Tests

Add tests for `socket-message-effects.js`:

- workspace lifecycle messages trigger active workspace/session refresh descriptors.
- session snapshot messages trigger current-session state updates and relevant loader descriptors.
- timeline/session events append event-log entries only for the active session when appropriate.
- task, artifact, permission, and file-tree messages map to the same refresh behavior currently handled in `App.jsx`.
- unknown or malformed messages produce empty effects without throwing.

Add tests for `visual-debug-fixtures.js`:

- timeline fixture contains rich T3 timeline material, including reasoning/thinking-style content.
- interaction fixture contains pending interaction material.
- thread lifecycle fixture includes rename, fork, archive, and session-list material.
- debug hook installation is gated by `visual_debug=1`.

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
uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q
```

### Rendered Visual QA

Run the existing visual harness after build:

```bash
node scripts/gui-visual-debug.mjs --scenario timeline,responsive --no-build --output "$env:TEMP\embedagent-gui-app-runtime-controller"
```

If a local browser runtime or app server is unavailable, record the blocker and keep unit/build/backend verification explicit.

## Documentation

Update durable docs after implementation:

- `docs/modules/frontend-gui.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

The docs should state:

- `app-runtime` is a GUI app-shell boundary.
- Socket effect derivation is frontend-local and does not define session-history truth.
- Visual debug fixtures are development-only.
- No Agent Core, workflow package, permission policy, or backend protocol semantics changed.

## Risks And Mitigations

### Risk: Effect Descriptors Become A Second Protocol

Mitigation: keep descriptors private to the webapp source tree, avoid exporting them through backend APIs, and document them as GUI implementation details.

### Risk: Socket Behavior Regresses During Extraction

Mitigation: preserve the current message cases, add unit tests for the mapping, and keep loader execution in `App.jsx` for the first slice.

### Risk: Fixture Extraction Hides Visual Debug Behavior

Mitigation: add fixture contract tests and keep the `visual_debug=1` gate explicit.

### Risk: The Slice Does Not Shrink `App.jsx` Enough

Mitigation: measure success by establishing the boundary and removing the highest-churn runtime interpretation and fixture bodies first. Loader/controller extraction becomes the next slice once this boundary is proven.

## Success Criteria

- `App.jsx` delegates WebSocket message interpretation to `app-runtime/socket-message-effects.js`.
- `App.jsx` delegates visual debug fixture construction and hook installation to `app-runtime/visual-debug-fixtures.js`.
- Socket effect derivation is covered by unit tests and does not import React or backend code.
- Visual debug fixtures are covered by unit tests and remain gated behind `visual_debug=1`.
- Existing rich timeline and responsive behavior still pass webapp tests and visual smoke checks.
- Webapp tests pass.
- Webapp build passes.
- Focused GUI backend tests pass.
- Static GUI assets are rebuilt if required by the existing build process.
- No Agent Core, backend protocol, permission, workflow, or reducer change is needed.
