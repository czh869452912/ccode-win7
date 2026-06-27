# Pi/T3 Residual Debt Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove residual pre-release architecture debt that still encourages Pi/T3 divergence, without adding compatibility scaffolding.

**Architecture:** The cleanup is deletion-oriented. Old contracts are removed or reframed as guards, Agent responsibilities move to explicit hosted/core services, and GUI responsibilities move toward T3-style focused runtime controllers and stores.

**Tech Stack:** Python 3.8, pytest, FastAPI backend, React/Vite frontend, Node-based webapp tests, existing project docs and guard tests.

---

## Task 1: Replace Legacy Tool Execution Gravity With Catalog Guards

**Files:**
- Modify: `tests/test_tools_package.py`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Verify: `src/embedagent/tools/runtime.py`

- [x] **Step 1: Write the failing guard**

Add a guard that forbids tests from asserting executable behavior for removed legacy task tools. The guard should scan active test files and allow only explicit catalog-exclusion strings.

Suggested test body:

```python
def test_no_legacy_task_tool_execution_contract_in_tests():
    offenders = []
    for path in (ROOT / "tests").glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        forbidden = (
            'execute("manage_todos"',
            "execute('manage_todos'",
            '"tool_name", "manage_todos"',
            "'tool_name', 'manage_todos'",
        )
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))
    assert offenders == []
```

- [x] **Step 2: Run the guard and confirm it fails**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py::test_no_legacy_task_tool_execution_contract_in_tests -v
```

Expected: FAIL pointing at `tests/test_tools_package.py`.

- [x] **Step 3: Remove the executable legacy assertion**

Delete the test that calls `ToolRuntime.execute("manage_todos", ...)`. Keep the existing catalog/schema exclusion test that verifies the tool is not exposed.

- [x] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_tools_package.py -v
```

Expected: PASS.

## Task 2: Reframe Compatibility Tests As Boundary Tests

**Files:**
- Rename or modify: `tests/test_backward_compatibility.py`
- Verify: `tests/test_architecture.py`

- [x] **Step 1: Rename the test intent**

Rename the file to `tests/test_current_architecture_boundaries.py` or change its module docstring and class names if the team does not want a file rename.

Use this module docstring:

```python
"""Boundary tests for the current pre-release architecture.

The project does not preserve pre-release compatibility. These tests protect
current public construction paths and verify that stale aliases remain absent.
"""
```

- [x] **Step 2: Remove compatibility wording**

Rename classes:

```python
class TestPublicImports(object):
    pass

class TestInProcessAdapterBoundaries(object):
    pass

class TestQueryEngineBoundaries(object):
    pass
```

Keep assertions that protect current accessors and removed aliases. Do not add assertions that old APIs still work.

- [x] **Step 3: Run the renamed or modified file**

Run:

```bash
uv run pytest tests/test_current_architecture_boundaries.py -v
```

If the file is not renamed, run:

```bash
uv run pytest tests/test_backward_compatibility.py -v
```

Expected: PASS.

## Task 3: Move Interaction Resolution Activity To Backend-Owned Session Events

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/gui/backend/session_events.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
- Modify: `tests/test_gui_backend_api.py`

- [x] **Step 1: Add a backend test for resolved interaction events**

Add a test that posts to the interaction response route and asserts the backend emits a `session_event` with `event_kind == "interaction.resolved"` after a resolved permission or user input.

The fake frontend can inspect `frontend.messages` already used by GUI backend tests.

- [x] **Step 2: Make the test fail**

Run:

```bash
uv run pytest tests/test_gui_backend_api.py -k interaction -v
```

Expected: FAIL because the backend currently returns the snapshot but does not emit `interaction.resolved`.

- [x] **Step 3: Emit backend-owned resolution**

In the interaction response route, after the response is accepted and before returning, call the same session-event bridge used for Core turn events.

The emitted payload must be limited to these safe display fields:

```python
{
    "session_id": session_id,
    "interaction_id": interaction_id,
    "kind": str(request.get("kind") or ""),
    "decision": request.get("decision"),
    "answer": str(request.get("answer") or ""),
    "selected_option_text": str(request.get("selected_option_text") or ""),
}
```

Ensure `session_events.py` maps `interaction_resolved` to `interaction.resolved`, or emit the final event kind directly through the existing fallback mapping.

- [x] **Step 4: Remove frontend-synthesized transport event**

Delete the block in `App.jsx` that calls `appendSessionTransportEvent(...)` with `event_kind: "interaction.resolved"` after a response. The handler should still dispatch `session_snapshot`, clear local permission/input state, clear the draft answer, and log the response.

- [x] **Step 5: Update socket effect tests**

Add or update webapp tests so `session_event` with `event_kind: "interaction.resolved"` flows through `transportEvents`, while raw `permission_request` and `user_input_request` still only drive blocking UI actions.

- [x] **Step 6: Run focused GUI and backend tests**

Run:

```bash
uv run pytest tests/test_gui_backend_api.py tests/test_gui_runtime.py -v
cd src/embedagent/frontend/gui/webapp && npm test
```

Expected: PASS.

## Task 4: Extract Session And Thread Runtime Controllers From App.jsx

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-controller.js`
- Create: `src/embedagent/frontend/gui/webapp/src/app-runtime/thread-lifecycle-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [x] **Step 1: Add source-shape guard**

Add a webapp source test that fails while `App.jsx` directly defines all of these functions:

```js
[
  "async function createSession",
  "async function renameThread",
  "async function archiveThread",
  "async function forkThread",
  "async function setMode",
  "async function cancelSession",
  "async function submitText",
]
```

Expected: the test fails before extraction.

- [x] **Step 2: Create `session-controller.js`**

Move session creation, mode changes, cancel, and text submission into a factory that receives dependencies:

```js
export function createSessionController({
  fetchJson,
  dispatch,
  normalizeSessionPayload,
  createRuntimeSessionTransport,
  replaceSessionTransport,
  getCurrentSessionId,
  getCurrentMode,
  hasActiveWorkspace,
  loadSessions,
  loadTasks,
  loadPermissionContext,
  loadSession,
}) {
  async function createSession(mode) {
    const payload = await fetchJson(`/api/sessions?mode=${encodeURIComponent(mode)}`, {
      method: "POST",
    });
    const snapshot = normalizeSessionPayload(payload);
    dispatch({ type: "session_activated", sessionId: snapshot.session_id, snapshot, timeline: [] });
    replaceSessionTransport(createRuntimeSessionTransport());
    await Promise.all([
      loadSessions(),
      loadTasks(snapshot.session_id),
      loadPermissionContext(snapshot.session_id),
    ]);
    return snapshot.session_id;
  }

  async function setMode(mode) {
    dispatch({ type: "mode_requested", mode });
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    await loadSession(sessionId);
  }

  async function cancelSession() {
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    dispatch({ type: "stream_completed" });
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/cancel`, {
      method: "POST",
    });
  }

  async function submitText(rawText) {
    const text = (rawText || "").trim();
    if (!text) return;
    if (!hasActiveWorkspace()) {
      dispatch({ type: "workspace_activation_failed", error: "no_active_workspace" });
      return;
    }
    dispatch({ type: "stream_completed" });
    dispatch({ type: "local_user_message", text });
    let sessionId = getCurrentSessionId();
    if (!sessionId) sessionId = await createSession(getCurrentMode());
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  }

  return { createSession, setMode, cancelSession, submitText };
}
```

Do not let the controller import React.

- [x] **Step 3: Create `thread-lifecycle-controller.js`**

Move rename/archive/fork logic into a dependency-injected controller:

```js
export function createThreadLifecycleController({
  fetchJson,
  dispatch,
  loadSessions,
  loadSession,
  getThreadSessions,
  prompt,
  confirm,
}) {
  async function renameThread(sessionId) {
    const current = getThreadSessions().find((item) => item.session_id === sessionId) || {};
    const initialTitle = current.thread?.title || current.title || current.user_goal || "";
    const title = prompt("Rename thread", initialTitle);
    if (title === null) return;
    const normalizedTitle = String(title || "").trim();
    if (!normalizedTitle) {
      dispatch({
        type: "interaction_notice_set",
        notice: {
          kind: "thread_lifecycle",
          title: "Rename failed",
          body: "Thread title cannot be empty.",
        },
      });
      return;
    }
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: normalizedTitle }),
    });
    await loadSessions();
  }

  async function archiveThread(sessionId) {
    if (!confirm("Archive this thread?")) return;
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/archive`, { method: "POST" });
    await loadSessions();
    dispatch({
      type: "interaction_notice_set",
      notice: {
        kind: "thread_lifecycle",
        title: "Thread archived",
        body: "The thread was archived and hidden from the normal thread list.",
      },
    });
  }

  async function forkThread(sessionId) {
    const title = prompt("Fork thread title", "");
    if (title === null) return;
    const payload = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/fork`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: String(title || "").trim() }),
    });
    await loadSessions();
    if (payload.session_id) await loadSession(payload.session_id);
  }

  async function handleThreadLifecycleAction(actionId, sessionId) {
    try {
      if (actionId === "rename") return await renameThread(sessionId);
      if (actionId === "archive") return await archiveThread(sessionId);
      if (actionId === "fork") return await forkThread(sessionId);
    } catch (error) {
      dispatch({
        type: "interaction_notice_set",
        notice: {
          kind: "thread_lifecycle",
          title: "Thread action failed",
          body: error?.message || String(error || "thread_lifecycle_failed"),
        },
      });
    }
  }

  return { renameThread, archiveThread, forkThread, handleThreadLifecycleAction };
}
```

- [x] **Step 4: Wire App.jsx as composition root**

Instantiate both controllers with `useMemo`. Replace local function bodies with controller calls. Keep render behavior unchanged.

- [x] **Step 5: Run webapp tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

Expected: PASS and the source-shape guard passes.

## Task 5: Extract Workbench Command And Surface Controllers

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/app-runtime/workbench-command-controller.js`
- Create: `src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [x] **Step 1: Guard against command ladder growth**

Add a source test that fails if `App.jsx` contains more than two direct `if (command.id === "...")` cases. The two-case allowance is only for palette open/close during the migration; remove the allowance once command execution is fully delegated.

- [x] **Step 2: Move right-panel opening**

Create `right-panel-controller.js` with helpers for:

- singleton surfaces
- terminal surface delegation
- file surface title/path normalization
- surface title resolution

- [x] **Step 3: Move workbench command execution**

Create `workbench-command-controller.js` with `executeWorkbenchCommand(command)`. It receives callbacks for session, workspace, message, preview, terminal, and surface actions. Preserve the current command effects:

- palette open/close dispatches command-palette actions
- `session.new` and `thread.new` create a session
- `session.refresh` reloads sessions
- workspace commands open, refresh, or remove the active workspace
- app/surface commands open the correct right-panel surface
- message commands send or stop the current message
- view commands toggle right panel and bottom drawer
- drawer commands activate terminal or bottom drawer surfaces
- slash commands submit their slash text through the session controller

- [x] **Step 4: Wire App.jsx**

Replace the command ladder with:

```js
await workbenchCommandController.execute(command);
```

- [x] **Step 5: Run webapp tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

Expected: PASS.

## Task 6: Move Session Activity Mutation Out Of Root Store

**Files:**
- Create or modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [x] **Step 1: Add reducer ownership tests**

Add unit tests for activity reducer actions:

- `local_user_message`
- `turn_started`
- `assistant_delta`
- `reasoning_delta`
- `tool_started`
- `tool_finished`
- `step_ended`
- `context_compacted`
- `session_error`
- `stream_completed`

- [x] **Step 2: Extract activity reducer**

Move timeline mutation helpers and streaming ids into `activity-reducer.js`.

Use this activity state shape:

```js
export function createActivityState() {
  return {
    timeline: [],
    streamingAssistantId: "",
    streamingReasoningId: "",
    thinkingActive: false,
    activeTurnId: "",
    activeStepId: "",
    activeStepIndex: 0,
    terminationReason: "",
    terminationDisplayReason: "",
    terminationMessage: "",
    turnsUsed: 0,
    maxTurns: null,
  };
}

export function reduceActivityState(state, action) {
  switch (action.type) {
    // moved cases
    default:
      return state;
  }
}
```

- [x] **Step 3: Delegate from root store**

Root store should call `reduceActivityState` for activity action families and merge the returned state. Avoid keeping duplicated activity fields in separate owners.

- [x] **Step 4: Add source guard**

Guard that `store.js` no longer contains direct cases for `assistant_delta`, `tool_started`, and `tool_finished`.

- [x] **Step 5: Run webapp tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp && npm test
```

Expected: PASS.

## Task 7: Split GUI Backend Route Registration By Boundary

**Files:**
- Create: `src/embedagent/frontend/gui/backend/routes_app.py`
- Create: `src/embedagent/frontend/gui/backend/routes_sessions.py`
- Create: `src/embedagent/frontend/gui/backend/routes_terminal.py`
- Create: `src/embedagent/frontend/gui/backend/routes_source_control.py`
- Create: `src/embedagent/frontend/gui/backend/routes_preview.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `tests/test_gui_backend_api.py`
- Modify: `tests/test_gui_terminal_api.py`
- Modify: `tests/test_gui_source_control_api.py`

- [ ] **Step 1: Add route registration guard**

Add a guard test that counts route decorators in `server.py` and fails if HTTP route registration remains concentrated there after this slice. Allow only root/static/websocket/bootstrap wiring.

- [ ] **Step 2: Move app-shell routes**

Move `/api/app/bootstrap`, workspace registry routes, and app-level preview external route into `routes_app.py`.

- [ ] **Step 3: Move session/core routes**

Move session list/create/snapshot/bootstrap/message/cancel/mode/resources/plan/permissions/tasks/artifacts/file routes into `routes_sessions.py`.

- [ ] **Step 4: Move surface routes**

Move terminal, source-control, and preview route families into their own route modules. Keep existing URL paths and HTTP behavior unchanged.

- [ ] **Step 5: Keep server.py as composition**

`server.py` should own `GUIBackend`, `WebSocketFrontend`, shared serializers if still needed, and calls like:

```python
register_app_routes(app, backend)
register_session_routes(app, backend)
register_terminal_routes(app, backend)
register_source_control_routes(app, backend)
register_preview_routes(app, backend)
```

- [ ] **Step 6: Run GUI backend tests**

Run:

```bash
uv run pytest tests/test_gui_backend_api.py tests/test_gui_terminal_api.py tests/test_gui_source_control_api.py -v
```

Expected: PASS.

## Task 8: Extract Hosted Adapter Command And Interaction Services

**Files:**
- Create: `src/embedagent/hosted_command_service.py`
- Create: `src/embedagent/hosted_interaction_service.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_review_command.py`

- [ ] **Step 1: Characterize current behavior**

Add tests around:

- slash command dispatch for `/run`, `/tasks`, `/resources reload`, `/review`
- permission response routing
- user input response routing
- command result emission with turn and step anchors

- [ ] **Step 2: Move command execution helpers**

Move slash-command command execution and command-result emission that does not belong to Agent Core into `HostedCommandService`.

The adapter should call:

```python
self.command_service.dispatch(text, state)
```

The service result should contain enough information for the adapter to persist state and emit command results without calling back into adapter-private command helpers.

- [ ] **Step 3: Move interaction glue**

Move approve/reject/reply/respond glue into `HostedInteractionService`. Keep actual tool-action resume inside existing Agent action pipeline.

- [ ] **Step 4: Delete adapter methods after migration**

Do not keep private forwarding wrappers unless tests need them for an active public API. Update tests to target the new service where appropriate.

- [ ] **Step 5: Run focused adapter tests**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py tests/test_review_command.py -v
```

Expected: PASS.

## Task 9: Extract QueryEngine Snapshot And Compaction Helpers

**Files:**
- Create: `src/embedagent/compaction_journal.py`
- Modify: `src/embedagent/turn_snapshot_service.py`
- Modify: `src/embedagent/prompt_assembly_service.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_query_engine_refactor.py`
- Modify: `tests/test_turn_snapshot.py`
- Modify: `tests/test_compacted_history.py`
- Modify: `tests/test_compaction_state.py`

- [ ] **Step 1: Add size/ownership guard**

Add a guard that fails if `QueryEngine` contains direct helper names for compaction payload assembly after extraction:

```python
for token in (
    "_compaction_token_counts",
    "_compaction_message_counts",
    "_compaction_file_activity",
    "_compaction_evidence_refs",
    "_compacted_history_payload",
):
    assert token not in source
```

- [ ] **Step 2: Move provider snapshot metadata**

Move runtime config, capability, prompt-unit, and context-stat snapshot helpers into `TurnSnapshotService` if they are not already owned there.

- [ ] **Step 3: Move workflow prompt appending**

Move workflow prompt append/dedupe helpers into `PromptAssemblyService`.

- [ ] **Step 4: Create compaction journal helper**

Create a helper that accepts session, context assembly result, summaries, and IDs, then returns safe `compact_boundary` and `compacted_history` payloads.

- [ ] **Step 5: Delete moved QueryEngine helpers**

Update QueryEngine to call the service/helper. Remove the private helpers from QueryEngine in the same slice.

- [ ] **Step 6: Run focused core tests**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py tests/test_turn_snapshot.py tests/test_compacted_history.py tests/test_compaction_state.py -v
```

Expected: PASS.

## Task 10: Final Documentation Sync And Regression

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/modules/agent-core.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Sync durable conclusions**

Update active docs only after implementation slices land. Keep old terms only in explicit historical or forbidden contexts.

- [ ] **Step 2: Archive slice-local docs**

Move this plan and the matching design doc under an appropriate `docs/archive/` folder after global docs are synchronized.

- [ ] **Step 3: Run local verification**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
uv run pytest tests/ -m harness -v
uv run --locked python scripts/lint.py
cd src/embedagent/frontend/gui/webapp && npm test
```

Expected: all selected checks pass.

- [ ] **Step 4: Rebuild GUI static assets if webapp source changed**

Run the existing webapp build command from `package.json`, then verify generated assets are updated intentionally.

- [ ] **Step 5: Record remaining release evidence**

Do not claim release readiness until clean Windows 7 WebView2 GUI smoke and broader real C/C++ workflow validation are recorded.
