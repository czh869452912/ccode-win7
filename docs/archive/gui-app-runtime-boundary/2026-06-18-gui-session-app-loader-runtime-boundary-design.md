# GUI Session/App Loader Runtime Boundary Design

## Goal

Move the GUI one step closer to the `reference/t3code` frontend architecture by extracting app/session loader orchestration from `App.jsx` into a GUI-only runtime boundary.

This slice should continue the direction established by `app-runtime/socket-message-effects.js`: frontend runtime interpretation and app-shell orchestration become small, testable modules, while Agent Core remains Pi-like, small, and independent from GUI display or loader concerns.

## Current Baseline

The previous GUI runtime slice created `webapp/src/app-runtime/` for pure WebSocket effect derivation and development-only visual fixtures. `App.jsx` now delegates socket message interpretation, but it still owns a large amount of runtime orchestration:

- `fetchJson` response parsing and HTTP error translation
- app bootstrap loading
- active-workspace refresh orchestration
- session list loading
- session bootstrap activation
- task, artifact, permission, tool catalog, recipe, and file-tree loaders
- loader request execution for socket-derived effects
- session activation side effects such as event-log reset, terminal summary loading, and task/artifact refresh

`App.jsx` is still about 1,400 lines and remains the place where render composition, WebSocket handling, app/session loading, workspace switching, command actions, terminal actions, source-control actions, and right-panel/file-preview behavior meet.

That shape slows down the next T3code parity slices because each UI improvement risks touching unrelated loader behavior. It also increases the temptation to push GUI convenience state into backend or Agent Core contracts. This slice should reduce that pressure by giving app/session loader orchestration its own frontend boundary.

## Reference Findings

The relevant T3code lesson is architectural separation, not dependency adoption:

- `reference/t3code/packages/client-runtime/src/threadDetailState.ts` keeps thread detail loading, stream application, retention, and invalidation in a runtime manager rather than a root component.
- `reference/t3code/packages/client-runtime/src/shellSnapshotState.ts` keeps shell snapshot synchronization and stream event application behind a small manager.
- `reference/t3code/apps/web/src/session-logic.ts` derives thread/session UI read models from runtime state without making components own backend orchestration directly.
- T3code's frontend runtime is not the agent kernel. It is a client-side orchestration layer over shell/thread data.

EmbedAgent should copy that separation in a smaller, dependency-free form that fits the current React/Vite webapp, WebView2 109, Windows 7, offline, and no-runtime-Node constraints.

## Product Principles

1. Agent Core must remain small, Pi-like, and extensible through existing Core boundaries, not GUI loader convenience paths.
2. GUI app/session loader orchestration is app-shell behavior, not protocol truth.
3. `GET /api/app/bootstrap` remains app-shell bootstrap only.
4. `GET /api/sessions/{id}/bootstrap` remains the GUI activation bootstrap for session history.
5. `transcript.jsonl -> Session -> SessionHistoryAssembler -> /api/sessions/{id}/bootstrap` remains durable session-history truth.
6. `timeline.jsonl` remains transport/replay infrastructure only.
7. No new runtime dependency may weaken offline deployment, WebView2 109, or Windows 7 support.
8. The slice must not introduce a frontend-owned workflow, permission, provider, extension, runtime reducer, operation reducer, compaction reducer, or recovery policy.

## Scope

### In Scope

- Add a GUI-only loader/controller module under `src/embedagent/frontend/gui/webapp/src/app-runtime/`.
- Move private loader request vocabulary and request execution helpers out of `App.jsx`.
- Keep `socket-message-effects.js` pure and update it to share loader request constants from the new boundary.
- Introduce a small loader executor factory that receives existing callbacks from `App.jsx` and executes known loader requests defensively.
- Introduce a session bootstrap projection helper for turning `/api/sessions/{id}/bootstrap` payloads into existing reducer-ready state.
- Keep HTTP fetching and concrete backend routes in the GUI frontend only; do not move them into Agent Core.
- Keep terminal summary loading as an injected session-activation side effect, because terminal state is GUI-local app-shell state.
- Add focused webapp tests for loader request execution and session bootstrap projection.
- Keep current socket effect behavior and visual debug fixtures intact.
- Update slice-local docs and, after implementation, durable GUI docs and changelog.

### Out Of Scope

- Agent Core changes.
- Backend API or protocol changes.
- Permission policy changes.
- Tool execution or workflow package changes.
- Runtime, operation, compaction, or recovery reducer changes.
- Session-history truth changes.
- Replacing the whole GUI state model or adding a new state library.
- Introducing Zustand, Effect, TanStack Query, Electron, runtime Node, remote services, or online dependencies.
- Moving terminal execution, source-control execution, file preview, or right-panel surface behavior into Agent Core.
- Source-control mutations, checkpoint mutation, staging, commit, push, pull, or remote provider work.
- Full extraction of command routing, terminal actions, source-control actions, or right-panel rendering from `App.jsx`.

## Recommended Approach

Use a narrow GUI runtime loader boundary with injected effects and pure projection helpers.

### Option A: Keep Loaders Inline In `App.jsx`

Pros:

- Smallest immediate diff.
- No new module surface.

Cons:

- Keeps `App.jsx` as the crossroad for unrelated concerns.
- Makes the previous socket effect boundary less useful because loader descriptors still terminate in root-component branching.
- Slows future T3 timeline, composer, and right-panel parity work.

### Option B: Extract Loader Request Executor And Session Bootstrap Projection

Create a small `app-runtime/session-loaders.js` module that owns private loader request constants, request execution, and session bootstrap projection. `App.jsx` still owns the actual fetch calls and dispatch callbacks, but the branching and projection details move into a focused frontend runtime file.

Pros:

- Low risk and easy to test.
- Extends the existing `app-runtime` architecture without a broad rewrite.
- Keeps concrete route calls and GUI side effects injected from `App.jsx`.
- Gives future slices a place to continue moving session/app orchestration.
- Preserves Agent Core and backend protocol unchanged.

Cons:

- `App.jsx` will still own many action handlers after this slice.
- More extraction slices are needed before `App.jsx` becomes mostly composition.

### Option C: Full App Runtime Controller Rewrite

Move fetch calls, WebSocket lifecycle, command routing, terminal/source-control orchestration, file preview loading, and right-panel behavior into a controller layer in one change.

Pros:

- Could reach a cleaner final architecture faster.

Cons:

- Too much blast radius.
- Hard to review, test, and visually verify in one slice.
- Higher chance of regressing workspace/session activation, terminal, source-control, and timeline behavior together.

Recommendation: use Option B.

## Architecture

### `app-runtime/session-loaders.js`

This module should be GUI frontend-only. It should not import React, open WebSockets, mutate global state, call backend APIs directly, or know about DOM APIs.

It should own the private loader request vocabulary:

```js
export const LOADER_REQUESTS = Object.freeze({
  LOAD_APP_BOOTSTRAP: "load_app_bootstrap",
  LOAD_ACTIVE_WORKSPACE_DATA: "load_active_workspace_data",
  LOAD_SESSIONS: "load_sessions",
  LOAD_SESSION: "load_session",
  LOAD_TASKS: "load_tasks",
  LOAD_ARTIFACTS: "load_artifacts",
  LOAD_PERMISSION_CONTEXT: "load_permission_context",
  LOAD_FILE_CHILDREN: "load_file_children",
});
```

It should expose an executor factory:

```js
export function createLoaderRequestExecutor(loaders) {
  return function executeLoaderRequest(request = {}) {
    // Dispatch known private request names to injected loader callbacks.
  };
}
```

The executor should:

- ignore unknown request names
- require `sessionId` for session-scoped loaders that need it
- default file-tree refresh paths to `.`
- avoid throwing when an optional callback is absent
- return promises so callers can `await` in tests or fire-and-forget in socket effect execution

This file should also expose a pure session bootstrap helper:

```js
export function deriveSessionActivation(payload, sessionId, options = {}) {
  // Return existing reducer-ready snapshot, timeline, history integrity,
  // plan, and permission context values.
}
```

The helper should normalize the session snapshot through the existing `normalizeSessionPayload(...)` helper and turn structured history into the existing timeline shape through `timelineFromTurns(...)`. It should not fetch terminal summaries or tasks/artifacts; those remain injected side effects owned by the loader caller.

### `app-runtime/socket-message-effects.js`

This module should import `LOADER_REQUESTS` from `session-loaders.js` instead of owning a second copy.

It should remain pure:

- no React imports
- no `fetch`
- no `new WebSocket`
- no DOM globals
- no backend or Agent Core imports

Socket-derived loader requests stay private webapp descriptors. They do not become protocol messages.

### `App.jsx`

After this slice, `App.jsx` should still be the root composition component, but loader branching should be reduced:

- `App.jsx` keeps `fetchJson` and concrete API calls.
- `App.jsx` creates an executor via `createLoaderRequestExecutor(...)`.
- `App.jsx` calls `deriveSessionActivation(...)` inside `loadSession(...)` before dispatching existing reducer actions.
- `executeSocketEffects(...)` calls the injected executor instead of containing its own loader switch.
- Existing terminal summary loading remains inside `loadSession(...)` or an injected activation side effect because terminal state is GUI-local display state.

This is intentionally incremental. Command routing, terminal action helpers, source-control helpers, and file preview loading can be extracted later.

## Data Flow

1. `App.jsx` loads app bootstrap through existing HTTP APIs.
2. `App.jsx` loads session bootstrap through existing HTTP APIs.
3. `deriveSessionActivation(...)` converts session bootstrap payload into reducer-ready frontend state.
4. `App.jsx` dispatches existing reducer actions and resets the GUI event log as it does today.
5. WebSocket messages are interpreted by `deriveSocketMessageEffects(...)`.
6. Socket effect descriptors carry `loaderRequests`.
7. `executeSocketEffects(...)` passes those descriptors to the executor created by `createLoaderRequestExecutor(...)`.
8. The executor calls injected loader callbacks; it never owns session truth or backend protocol.

## Error Handling

- Unknown loader request names resolve without side effects.
- Missing required `sessionId` values for session-scoped loaders resolve without side effects.
- Missing optional loader callbacks resolve without side effects.
- File-tree loader requests default to path `.`.
- Session bootstrap projection treats absent payload sections as empty objects or empty lists.
- Existing loader functions keep their current HTTP error behavior.
- WebSocket reconnect and recovery behavior remain unchanged.
- Terminal summary loading failures keep the existing fallback to empty terminal summaries.

## Testing Strategy

### Webapp Unit Tests

Add `test/session-loaders.test.mjs` covering:

- known loader request names call the expected injected callback
- unknown requests do nothing
- session-scoped requests without `sessionId` do nothing
- file-tree requests default to `.`
- `load_active_workspace_data` passes `sessionId` and `assumeWorkspace`
- `deriveSessionActivation(...)` normalizes snapshots, structured history, plan, permission context, and history integrity
- projection uses the existing `history_source` value as timeline projection source

Update existing socket effect tests to import `LOADER_REQUESTS` through the shared loader module and verify the socket module no longer defines a separate loader vocabulary.

### Source-Level Boundary Tests

Extend existing source assertions so:

- `socket-message-effects.js` imports `LOADER_REQUESTS` from `session-loaders.js`
- `session-loaders.js` does not include `fetch(`, `new WebSocket`, `useEffect`, or React imports
- `App.jsx` imports `createLoaderRequestExecutor` and `deriveSessionActivation`
- `App.jsx` no longer contains the old inline loader request switch

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

Run the visual harness:

```bash
node scripts/gui-visual-debug.mjs --scenario timeline,responsive --no-build --output "$env:TEMP\embedagent-gui-session-app-loader-runtime"
```

If a local browser runtime or app server is unavailable, record the blocker and keep unit/build/backend verification explicit.

## Documentation

After implementation, update durable docs:

- `docs/modules/frontend-gui.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

Docs should state:

- `app-runtime/session-loaders.js` is a GUI-only runtime boundary.
- Loader request descriptors are private webapp implementation details.
- Session bootstrap projection remains a frontend projection over the official `/api/sessions/{id}/bootstrap` contract.
- No Agent Core, workflow package, permission policy, backend protocol, transcript, terminal execution, source-control execution, provider configuration, extension loading, or runtime reducer behavior changed.

## Risks And Mitigations

### Risk: Loader Descriptors Become A Second Protocol

Mitigation: keep descriptors private to `webapp/src/app-runtime/`, never expose them through backend APIs, and document them as GUI implementation details.

### Risk: Session Activation Regresses During Extraction

Mitigation: keep actual fetch calls in `App.jsx`, extract only projection and request execution branching, and add tests around session bootstrap payload conversion.

### Risk: Socket Effects And Loader Requests Drift

Mitigation: make `socket-message-effects.js` import `LOADER_REQUESTS` from `session-loaders.js` so there is one private vocabulary.

### Risk: The Slice Does Not Fully Solve `App.jsx` Size

Mitigation: treat this as an architecture slice. Success is a smaller, tested runtime boundary that future slices can extend, not a full root-component rewrite.

## Success Criteria

- `app-runtime/session-loaders.js` owns loader request constants, loader request execution, and session activation projection.
- `socket-message-effects.js` imports the shared loader request vocabulary instead of defining its own.
- `App.jsx` uses the loader executor and session activation projection.
- The old inline loader request switch is removed from `App.jsx`.
- Existing HTTP route calls and dispatch side effects remain GUI frontend-owned.
- Webapp tests pass.
- Webapp build passes.
- Focused GUI backend tests pass.
- Visual timeline/responsive harness passes or any local harness blocker is documented.
- Static GUI assets are rebuilt if the implementation changes bundled webapp output.
- No Agent Core, backend protocol, workflow package, permission policy, transcript truth, terminal execution, source-control execution, provider configuration, extension loading, or runtime reducer changes are made.
