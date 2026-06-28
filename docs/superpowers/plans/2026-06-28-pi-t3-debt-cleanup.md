# Pi/T3 Pre-Release Debt Cleanup Plan

> **For Administrator:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan step-by-step.

**Goal:** Continue the pre-release debt cleanup without compatibility scaffolding. GUI code moves toward T3-style focused runtime and contract modules; Agent Core stays Pi-style minimal, explicit, and extension-boundary driven. Each task below is executed, verified, and committed separately.

**Constraints:**
- Preserve Windows 7, offline deployment, and Python 3.8 compatibility.
- Do not add compatibility paths for old internal session, timeline, GUI reducer, or extension-hook shapes.
- Do not modify `uv.lock` manually.
- Keep test files under `tests/`.
- Use deletion/replacement over adapter shims when the repository has no shipped state to preserve.

## Task 0: Record The Execution Plan

**Files**
- `docs/superpowers/plans/2026-06-28-pi-t3-debt-cleanup.md`

**Steps**
1. Add this plan.
2. Run `git diff --check`.
3. Commit with `docs: plan pi t3 debt cleanup`.

## Task 1: Move GUI Backend Contracts Out Of `server.py`

**Problem**
`server.py` is the FastAPI composition root, but route modules import private serializer and HTTP error helpers from it. This makes route families depend on the app shell and keeps protocol payload shaping in the wrong place.

**Target Design**
- `server.py` keeps app/static/websocket/bootstrap composition.
- Route modules import pure payload serialization from a backend contract module.
- Route modules import HTTP exception mapping from a backend HTTP error module.
- Architecture guard prevents route modules from importing private helpers from `server.py`.

**Files**
- Add `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Add `src/embedagent/frontend/gui/backend/http_errors.py`
- Update `src/embedagent/frontend/gui/backend/server.py`
- Update `src/embedagent/frontend/gui/backend/routes_app.py`
- Update `src/embedagent/frontend/gui/backend/routes_preview.py`
- Update `src/embedagent/frontend/gui/backend/routes_sessions.py`
- Update `src/embedagent/frontend/gui/backend/routes_source_control.py`
- Update `src/embedagent/frontend/gui/backend/routes_terminal.py`
- Update `tests/test_pre_release_architecture_guards.py`

**TDD**
1. Add `test_gui_backend_route_modules_do_not_import_server_helpers`.
2. Run:
   `uv run pytest tests/test_pre_release_architecture_guards.py::test_gui_backend_route_modules_do_not_import_server_helpers -v`
3. Confirm it fails because `routes_*` imports from `backend.server`.
4. Move helpers and update imports.
5. Run:
   `uv run pytest tests/test_pre_release_architecture_guards.py::test_gui_backend_route_modules_do_not_import_server_helpers -v`
   `uv run pytest tests/test_gui_backend_api.py tests/test_gui_runtime.py -v`
   `uv run --locked python scripts/lint.py`
6. Commit with `gui: split backend route contracts from server`.

## Task 2: Converge Pending Interaction Protocol

**Problem**
The active protocol still exposes compatibility names such as `pending_input`, `pending_user_input`, `has_pending_input`, and `has_pending_user_input` around the newer `pending_interaction` model. That keeps frontend/backend coupling ambiguous.

**Target Design**
- Session bootstrap and snapshots expose one pending interaction model.
- Permission and user-input display derives from backend-owned `session_event` activity plus `pending_interaction`.
- No compatibility aliases remain in active protocol, adapter snapshots, GUI serializers, or architecture docs.

**Files**
- `src/embedagent/protocol/__init__.py`
- `src/embedagent/core/adapter.py`
- `src/embedagent/inprocess_adapter.py`
- `src/embedagent/session_projector.py`
- `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- GUI runtime modules that read pending input state
- Related tests under `tests/`

**TDD**
1. Add an architecture guard that active source has no `pending_user_input`, `pending_input`, `has_pending_user_input`, or `has_pending_input` protocol fields outside explicit migration tests.
2. Add/update snapshot serializer tests to assert `pending_interaction` is the only pending interaction payload.
3. Run the guard and focused protocol tests; confirm red.
4. Remove aliases and update frontend reads.
5. Run:
   `uv run pytest tests/test_pre_release_architecture_guards.py -v`
   `uv run pytest tests/test_gui_backend_api.py tests/test_gui_runtime.py tests/test_protocol_contracts.py -v`
   `uv run --locked python scripts/lint.py`
6. Commit with `core: converge pending interaction protocol`.

## Task 3: Use One Core-Owned Interaction Response Path

**Problem**
`routes_sessions.py` still tries a GUI websocket waiter first and falls back to Core response handling. The renderer needs transport state, but interaction lifecycle truth should be owned by Core/HostedInteractionService.

**Target Design**
- HTTP interaction responses call one backend/Core interaction service path.
- WebSocket raw request messages only drive the blocking UI and transport response.
- Durable/display activity enters the renderer through backend-owned `session_event` messages.
- Manual route-level `interaction_resolved` synthesis is removed unless emitted from the shared service boundary.

**Files**
- `src/embedagent/frontend/gui/backend/routes_sessions.py`
- `src/embedagent/frontend/gui/backend/server.py`
- `src/embedagent/frontend/gui/backend/session_events.py`
- `src/embedagent/inprocess_adapter.py`
- Tests covering permission/user-input response resolution

**TDD**
1. Add a route-level test that a response to an active interaction invokes only the Core adapter response path.
2. Add/update a websocket test that raw request messages do not create durable interaction activity directly.
3. Confirm red against the current dual path.
4. Route HTTP responses through the single Core path and keep WebSocket as transport.
5. Run:
   `uv run pytest tests/test_gui_backend_api.py tests/test_gui_websocket.py tests/test_hosted_interactions.py -v`
   `uv run --locked python scripts/lint.py`
6. Commit with `gui: route interaction responses through core lifecycle`.

## Task 4: Rename GUI Runtime History Internals To Activity

**Problem**
The official durable history source is `history.activities`, but GUI loader/reducer internals still call the active data `timeline`. The visual timeline can keep UI names; runtime state should not look like a second history source.

**Target Design**
- Loader state uses `activityItems` or `threadActivity`.
- Activity reducer receives activities, not timeline records.
- T3 grouping remains under `activity-state.js`.
- CSS class names and visible timeline UI terms can remain if they describe presentation only.

**Files**
- `src/embedagent/frontend/gui/webapp/src/session-runtime/session-loaders.js`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js`
- `src/embedagent/frontend/gui/webapp/src/App.jsx`
- GUI tests

**TDD**
1. Add a frontend architecture test that active runtime modules do not expose `timeline` as a state source.
2. Confirm red.
3. Rename runtime variables/actions while keeping rendered behavior stable.
4. Run from `src/embedagent/frontend/gui/webapp`:
   `npm test`
   `npm run build`
5. Run:
   `uv run pytest tests/test_pre_release_architecture_guards.py -v`
6. Commit with `gui: rename runtime history state to activity`.

## Task 5: Extract T3-Style App Runtime Controllers

**Problem**
`App.jsx` still owns too many controller responsibilities: session loading, workspace APIs, socket message effects, interaction response plumbing, right-panel file actions, source control, and preview orchestration.

**Target Design**
- `App.jsx` composes focused hooks/controllers.
- Existing focused modules own state transitions:
  - `session-runtime/thread-state.js`
  - `session-runtime/activity-state.js`
  - `session-runtime/run-output-state.js`
  - `session-runtime/session-transport-state.js`
  - `app-runtime/session-transport-controller.js`
  - `app-runtime/session-activation-controller.js`
  - `composer/composer-state.js`
- New controllers are added only where they remove real root-level coupling.

**Files**
- `src/embedagent/frontend/gui/webapp/src/App.jsx`
- `src/embedagent/frontend/gui/webapp/src/app-runtime/*.js`
- `src/embedagent/frontend/gui/webapp/src/session-runtime/*.js`
- `src/embedagent/frontend/gui/webapp/src/workspace/*.js` if a focused workspace controller is needed

**TDD**
1. Add or update frontend tests for session activation, interaction response, and socket effect behavior.
2. Extract one controller at a time, keeping public props stable.
3. Run from `src/embedagent/frontend/gui/webapp`:
   `npm test`
   `npm run build`
4. Commit with `gui: extract app runtime controllers`.

## Task 6: Move Workflow Prompt Appending Behind The Core Boundary

**Problem**
`QueryEngine` still has private workflow prompt helper ownership that docs say belongs behind prompt assembly / snapshot services.

**Target Design**
- `QueryEngine` remains a session facade and transcript owner.
- Prompt unit assembly and workflow prompt appending live in the prompt assembly boundary.
- `TurnSnapshotService` consumes already assembled prompt units and projected active tool schemas.
- Architecture guard prevents reintroducing private `QueryEngine` forwarding wrappers named in AGENTS.md.

**Files**
- `src/embedagent/query_engine.py`
- Prompt assembly / turn snapshot service modules
- `tests/test_current_architecture_boundaries.py`
- Focused QueryEngine tests

**TDD**
1. Add a guard for `_append_workflow_prompt_messages`, `_prompt_units_for_snapshot`, and related private wrapper names.
2. Confirm red.
3. Move ownership to the existing service boundary and update tests.
4. Run:
   `uv run pytest tests/test_current_architecture_boundaries.py tests/test_query_engine*.py -v`
   `uv run pytest tests/ -m "not slow and not gui" -v`
   `uv run --locked python scripts/lint.py`
5. Commit with `core: move workflow prompt assembly out of query engine`.
