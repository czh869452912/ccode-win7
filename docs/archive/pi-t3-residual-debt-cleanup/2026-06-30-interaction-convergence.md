# Interaction Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify hosted pending interaction truth, make session-scoped permission remember affect permission decisions, and align the GUI composer/pending interaction surface with the T3-style architecture without preserving pre-release compatibility paths.

**Architecture:** Agent Core/hosted services own pending interaction lifecycle, ids, cancellation, and remembered permission categories. GUI consumes only `snapshot.pending_interaction` for visible pending interaction state; raw WebSocket interaction messages may wake blocking paths and current request transport, but must not become renderer display state. Composer behavior mirrors T3's editor surface using a Win7-compatible lightweight textarea autosize rather than adding new runtime dependencies.

**Tech Stack:** Python 3.8, FastAPI backend routes, React webapp, Node test runner, pytest.

---

## File Structure

- `src/embedagent/hosted_interaction_service.py`: Canonical creation/resolution of permission and user-input tickets, including session pending ids and remember payload handling.
- `src/embedagent/inprocess_adapter.py`: Session snapshot projection, permission remember scope, cancel snapshot behavior, and permission handler integration.
- `src/embedagent/permissions.py`: Session remembered categories become permission evaluation input without adding a second policy engine.
- `src/embedagent/frontend/gui/backend/routes_sessions.py`: Interaction/cancel routes return Core-owned snapshots and stop owning remember side effects.
- `src/embedagent/frontend/gui/webapp/src/store.js`: Remove renderer-owned root pending permission/userInput display state.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`: Stop projecting raw interaction request messages into display state.
- `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`: Add lightweight autosize behavior and keep pending interaction rendering tied to snapshot.
- `src/embedagent/frontend/gui/webapp/src/components/PermissionModal.jsx`: Delete stale modal.
- `src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx` and `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`: Either reuse the composer interaction model or remove duplicate response UI so only one pending response surface owns actions.
- Tests:
  - `tests/test_inprocess_adapter_frontend_api.py`
  - `tests/test_gui_backend_api.py`
  - `tests/test_permissions.py`
  - `tests/test_pre_release_architecture_guards.py`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`

## Tasks

### Task 1: Canonical Pending Interaction Ids

**Files:**
- Modify: `src/embedagent/hosted_interaction_service.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] Write failing tests proving permission and ask_user snapshots expose the same `interaction_id` accepted by `respond_to_interaction()`.
- [ ] Run targeted pytest tests and verify they fail because current ids or pending records do not match.
- [ ] Change `HostedInteractionService.create_permission_ticket()` and `create_user_input_ticket()` so both create/update `Session.pending_interaction` with the ticket id as `interaction_id`.
- [ ] Ensure restored session pending interaction still rebuilds matching tickets in `InProcessAdapter`.
- [ ] Run targeted pytest tests and verify they pass.

### Task 2: Permission Remember Affects Decisions

**Files:**
- Modify: `src/embedagent/permissions.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/hosted_interaction_service.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_sessions.py`
- Test: `tests/test_permissions.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`
- Test: `tests/test_gui_backend_api.py`

- [ ] Write failing tests showing remembered session categories allow the next matching category without prompting.
- [ ] Write failing backend route test showing remember is passed through the unified interaction response and the route no longer owns a separate remember call.
- [ ] Run targeted pytest tests and verify they fail for the expected missing behavior.
- [ ] Add a session remembered category input to permission evaluation without changing project rule semantics.
- [ ] Move remember handling into `HostedInteractionService.respond_to_interaction()` / adapter state before the turn resumes.
- [ ] Remove GUI route remember side effect.
- [ ] Run targeted pytest tests and verify they pass.

### Task 3: Cancel Returns Canonical Snapshot

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_sessions.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-controller.js`
- Test: `tests/test_gui_backend_api.py`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] Write failing tests showing cancel route returns a serialized snapshot and frontend applies it.
- [ ] Run targeted backend/frontend tests and verify they fail.
- [ ] Return `serialize_session_snapshot(core.cancel_session(...))` from the cancel route.
- [ ] Dispatch `session_snapshot` in `cancelSession()` when a snapshot is returned.
- [ ] Run targeted backend/frontend tests and verify they pass.

### Task 4: GUI Single Interaction Truth

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- Modify/Delete: `src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx`
- Delete: `src/embedagent/frontend/gui/webapp/src/components/PermissionModal.jsx`
- Test: `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Test: `tests/test_pre_release_architecture_guards.py`

- [ ] Write failing frontend tests/guards proving raw `permission_request` and `user_input_request` do not write visible pending state and stale modal/root state are absent.
- [ ] Run frontend tests/guards and verify they fail.
- [ ] Remove root `permission`, `userInput`, and raw request display reducer branches from `store.js`.
- [ ] Change socket effects to request session snapshot reload or log only, without creating display pending state.
- [ ] Delete `PermissionModal.jsx`.
- [ ] Remove duplicate action-capable inspector interaction UI or make it read-only from the same normalized snapshot model.
- [ ] Run frontend tests/guards and verify they pass.

### Task 5: T3-Style Composer Autosize

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] Write failing frontend test/source guard proving composer input has autosize behavior and scrolls after max height.
- [ ] Run frontend tests and verify failure.
- [ ] Add a Win7/WebView2-safe autosize effect using `scrollHeight`, a max-height constant, and `overflowY` switching.
- [ ] Keep Enter/Shift+Enter behavior unchanged.
- [ ] Run frontend tests and verify they pass.

### Task 6: Static Assets and Gates

**Files:**
- Modify generated GUI static assets under `src/embedagent/frontend/gui/static/` only through `npm run build`.

- [ ] Run `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`.
- [ ] Run `uv run pytest tests/ -m "not slow and not gui" -v`.
- [ ] Run `uv run --locked python scripts/lint.py`.
- [ ] From `src/embedagent/frontend/gui/webapp`, run `npm test`.
- [ ] From `src/embedagent/frontend/gui/webapp`, run `npm run build`.
- [ ] Review `git diff` and ensure no unrelated generated/static/user config changes are included.
