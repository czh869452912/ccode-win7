# GUI Agent Bridge Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reviewed GUI-to-Agent bridge gaps while keeping GUI app-shell state separate from Agent Core policy.

**Architecture:** Extend existing GUI backend serialization rather than inventing a new protocol layer. Remove the unused direct file write surface by rejecting it at the backend route. Keep legacy WebSocket permission response compatible for resolving waiters, but gate remembered permission mutation by matching session identity.

**Tech Stack:** Python 3.8, FastAPI route handlers, unittest/pytest, React webapp tests.

---

### Task 1: Snapshot Diagnostics Serialization

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `tests/test_gui_backend_api.py`

- [x] **Step 1: Write failing backend test**

Add a test that returns diagnostic fields from fake core bootstrap and asserts the `/api/sessions/{id}/bootstrap` route keeps them in `snapshot`.

- [x] **Step 2: Run red test**

Run: `uv run pytest tests/test_gui_backend_api.py::TestGuiBackendApi::test_bootstrap_snapshot_preserves_agent_diagnostics -v`

Expected: FAIL because fields such as `compaction_state` or `recent_transitions` are absent.

- [x] **Step 3: Implement serializer pass-through**

Update `_serialize_session_snapshot()` to include the diagnostic/read-model fields already present in `SessionSnapshot` and `AgentCoreAdapter`.

- [x] **Step 4: Run green test**

Run: `uv run pytest tests/test_gui_backend_api.py::TestGuiBackendApi::test_bootstrap_snapshot_preserves_agent_diagnostics -v`

Expected: PASS.

### Task 2: Disable Direct GUI File Writes

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `tests/test_gui_backend_api.py`

- [x] **Step 1: Write failing backend test**

Add a fake core with `write_file()` call capture. Assert `POST /api/files/{path}` raises HTTP 405 and the fake core method is not called.

- [x] **Step 2: Run red test**

Run: `uv run pytest tests/test_gui_backend_api.py::TestGuiBackendApi::test_file_write_route_is_disabled_until_manual_editor_contract -v`

Expected: FAIL because current route calls core write.

- [x] **Step 3: Reject write route**

Change the route to raise `HTTPException(status_code=405, detail="file_write_disabled")`.

- [x] **Step 4: Run green test**

Run: `uv run pytest tests/test_gui_backend_api.py::TestGuiBackendApi::test_file_write_route_is_disabled_until_manual_editor_contract -v`

Expected: PASS.

### Task 3: Gate Legacy WebSocket Permission Remembering

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `tests/test_gui_runtime.py`

- [x] **Step 1: Write failing runtime tests**

Add tests around `_handle_websocket_message()`:
- no `session_id` means remembered permission category is not persisted;
- matching `session_id` persists the remembered category.

- [x] **Step 2: Run red tests**

Run: `uv run pytest tests/test_gui_runtime.py::TestWebSocketFrontend -v`

Expected: FAIL for the new no-session-id guard.

- [x] **Step 3: Implement session-id gate**

In `_handle_websocket_message()`, require payload `session_id` to match `_current_session_id` before calling `remember_permission_category`.

- [x] **Step 4: Run green tests**

Run: `uv run pytest tests/test_gui_runtime.py::TestWebSocketFrontend -v`

Expected: PASS.

### Task 4: Final Verification And Commit

**Files:**
- Modify: docs/spec and plan status if needed.

- [x] **Step 1: Run frontend tests**

Run: `npm test` in `src/embedagent/frontend/gui/webapp`.

Expected: PASS.

- [x] **Step 2: Run focused Python tests**

Run: `uv run pytest tests/test_gui_backend_api.py tests/test_gui_runtime.py tests/test_inprocess_adapter_frontend_api.py -v`.

Expected: PASS.

- [x] **Step 3: Check git status**

Run: `git status --short`.

Expected: only intentional source/test/doc changes.

- [ ] **Step 4: Commit**

Commit message: `fix: tighten GUI agent bridge contracts`.
