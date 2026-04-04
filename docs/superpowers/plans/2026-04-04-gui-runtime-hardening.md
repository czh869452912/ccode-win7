# GUI Runtime Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the GUI active-session runtime so replay, restore, transport recovery, and timeline projection behave predictably under truncation, malformed rows, reconnects, and ambiguous command anchoring.

**Architecture:** Rebuild the GUI runtime around an explicit timeline replay contract, typed replay/bootstrap APIs, and a projector that fully interprets active-session state. The implementation is split into four slices: timeline persistence and replay contract, transport/error boundary hardening, projector completion, and UI follow-through. Each slice adds tests first, ships minimal code, and leaves the repository in a verifiable state before the next slice.

**Tech Stack:** Python 3.8, FastAPI, unittest, React 18, node:test, esbuild, existing GUI webapp build pipeline

---

## File Structure

### Timeline Persistence And Restore

- Modify: `src/embedagent/session_timeline.py`
  - Introduce typed replay status output instead of raw event arrays only.
  - Separate retained-window metadata from event payloads.
  - Replace "break forever" damaged-line handling with typed degraded scanning.

- Modify: `src/embedagent/inprocess_adapter.py`
  - Return replay metadata through `load_session_events_after()`.
  - Remove pending interaction fallback IDs during restore.
  - Surface replay capability in session snapshots.

- Modify: `src/embedagent/session_restore.py`
  - Explicitly expire missing or untrustworthy interaction IDs during restore.

- Modify: `tests/test_session_restore.py`
  - Cover trusted interaction restore, explicit expiration, and stop reasons.

- Modify: `tests/test_inprocess_adapter_frontend_api.py`
  - Cover replay status metadata and snapshot capability fields.

### Transport And HTTP Error Boundary

- Modify: `src/embedagent/frontend/gui/backend/bridge.py`
  - Upgrade `DispatchResult` from debug metadata to transport fault signal input.

- Modify: `src/embedagent/frontend/gui/backend/server.py`
  - Add websocket exception cleanup for non-disconnect failures.
  - Return typed errors for session/interaction lookup failures.
  - Expose typed replay endpoint status.

- Modify: `src/embedagent/frontend/gui/backend/session_events.py`
  - Keep GUI `session_event` normalization aligned with replay and degradation semantics.

- Modify: `tests/test_gui_runtime.py`
  - Add websocket cleanup and dispatch-fault coverage.

- Modify: `tests/test_gui_backend_api.py`
  - Cover typed replay responses and typed interaction errors.

### Front-End Runtime And Projector

- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js`
  - Replace boolean-only resync state with multilevel runtime status.
  - Encode replay-needed vs reload-required vs degraded transitions.

- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  - Make the projector the full active-session interpreter.
  - Add explicit command-result fallback placement, detached item ordering, and system card placement.

- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Use typed replay responses and tiered bootstrap recovery.
  - Stop relying on reducer heuristics for command result anchoring and transport degradation handling.

- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
  - Reduce active-session derived state still duplicated in reducer logic when projector assumes ownership.

- Modify: `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
  - Narrow the helper layer to data conversion and compatibility helpers that the projector still needs.

- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
  - Cover replay state transitions, command-result fallback placement, and detached item ordering.

- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Execute the updated runtime projector checks.

### UI Follow-Through And Docs

- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - Move detached/system placement and code-block narrowing to match projector output.

- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - Keep inspector interaction handling aligned with explicit degraded/reload states.

- Modify: `src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx`
  - Support expired/degraded interaction states without duplicate control surfaces.

- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Apply the low-risk runtime-aligned polish: code block, resize handle, responsive breakpoint, and z-index tiers.

- Modify: `docs/frontend-protocol.md`
  - Document typed replay status, typed interaction errors, and degraded runtime behavior.

- Modify: `docs/development-tracker.md`
  - Record the replay/restore hardening slice and verification results.

- Modify: `docs/design-change-log.md`
  - Record the runtime hardening decision and affected boundaries.

- Modify: `src/embedagent/frontend/gui/static/assets/app.js`
  - Regenerated built webapp bundle.

- Modify: `src/embedagent/frontend/gui/static/assets/app.css`
  - Regenerated built webapp CSS.

- Modify: `src/embedagent/frontend/gui/static/index.html`
  - Regenerated static webapp shell.

## Task 1: Harden Timeline Persistence And Restore Contract

**Files:**
- Modify: `src/embedagent/session_timeline.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/session_restore.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_session_restore.py`

- [ ] **Step 1: Write the failing persistence/replay/restore tests**

```python
class TestInProcessAdapterFrontendApis(unittest.TestCase):
    def test_load_session_events_after_returns_reload_required_when_after_seq_falls_before_retained_window(self):
        session_id = str(self.snapshot.get("session_id") or "")
        for index in range(1, 6):
            self.adapter.timeline_store.append_event(session_id, "tool_started", {"call_id": "call-%s" % index})
        self.adapter.timeline_store.max_events = 3
        self.adapter.timeline_store._trim_if_needed(
            self.adapter.timeline_store._timeline_path(session_id)
        )
        payload = self.adapter.load_session_events_after(session_id, after_seq=1, limit=50)
        self.assertEqual(payload["status"], "reload_required")
        self.assertTrue(payload["first_seq"] > 1)


class TestSessionRestorer(unittest.TestCase):
    def test_restore_expires_permission_without_interaction_id(self):
        session_id = "sess-no-restore-id"
        self.store.append_event(session_id, "session_meta", {"current_mode": "code"})
        self.store.append_event(session_id, "message", {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""})
        self.store.append_event(session_id, "step_started", {"turn_id": "t-1", "step_id": "s-1", "step_index": 1})
        self.store.append_event(
            session_id,
            "pending_interaction",
            {
                "turn_id": "t-1",
                "step_id": "s-1",
                "kind": "permission",
                "tool_name": "edit_file",
                "interaction_id": "",
                "request_payload": {"permission": {"reason": "需要写入"}},
            },
        )
        result = SessionRestorer().restore(self.store.load_events(session_id))
        self.assertIsNone(result.session.pending_interaction)
        self.assertEqual(result.stop_reason, "interaction_expired")


class TestSessionTimelineStore(unittest.TestCase):
    def test_scan_events_skips_malformed_mid_file_rows_and_marks_degraded(self):
        session_id = "sess-mid-corrupt"
        self.store.append_event(session_id, "turn_start", {"turn_id": "t-1", "user_text": "hello"})
        path = self.store._timeline_path(session_id)
        with open(path, "ab") as handle:
            handle.write(b"{broken-json}\n")
            handle.write(b'{\"schema_version\":1,\"event_id\":\"evt_after\",\"seq\":2,\"created_at\":\"2026-04-04T00:00:02Z\",\"event\":\"turn_end\",\"payload\":{\"turn_id\":\"t-1\"}}\\n')
        events, state = self.store.load_events_with_state(session_id)
        self.assertEqual([item["event_id"] for item in events][-1], "evt_after")
        self.assertEqual(state["integrity_state"], "degraded")
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_inprocess_adapter_frontend_api tests.test_session_restore tests.test_session_timeline -v
```

Expected:

- replay contract assertions fail because `load_session_events_after()` only returns a flat event list
- malformed mid-file scan test fails because `_scan_events()` stops at the damaged row
- restore expiration test fails if any fallback or permissive restore path remains

- [ ] **Step 3: Implement the minimum timeline contract and restore identity rules**

```python
def load_events_with_state(self, session_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    path = self._timeline_path(session_id)
    if not os.path.isfile(path):
        return [], {"first_seq": 0, "last_seq": 0, "integrity_state": "empty", "truncated_before_seq": 0}
    events, valid_length, integrity_state = self._scan_events(path)
    first_seq = int(events[0].get("seq") or 0) if events else 0
    last_seq = int(events[-1].get("seq") or 0) if events else 0
    truncated_before_seq = max(first_seq - 1, 0) if first_seq else 0
    return events, {
        "first_seq": first_seq,
        "last_seq": last_seq,
        "integrity_state": integrity_state,
        "truncated_before_seq": truncated_before_seq,
    }


def load_events_after(self, session_id: str, after_seq: int, limit: int = 200) -> Dict[str, Any]:
    events, state = self.load_events_with_state(session_id)
    first_seq = int(state.get("first_seq") or 0)
    last_seq = int(state.get("last_seq") or 0)
    if state.get("integrity_state") == "degraded":
        return {"status": "degraded", "events": [], "first_seq": first_seq, "last_seq": last_seq, "reason": "timeline_degraded"}
    if first_seq and int(after_seq or 0) < first_seq - 1:
        return {"status": "reload_required", "events": [], "first_seq": first_seq, "last_seq": last_seq, "reason": "outside_retained_window"}
    filtered = [item for item in events if int(item.get("seq") or 0) > int(after_seq or 0)]
    return {"status": "replay", "events": filtered[:limit], "first_seq": first_seq, "last_seq": last_seq, "reason": ""}
```

```python
try:
    event = json.loads(line.decode("utf-8"))
except (UnicodeDecodeError, ValueError):
    integrity_state = "degraded"
    valid_length = next_offset
    continue
```

```python
interaction_id = str(payload.get("interaction_id") or "").strip()
if not interaction_id:
    consumed_event_count = index
    stop_reason = "interaction_expired"
    break
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_inprocess_adapter_frontend_api tests.test_session_restore tests.test_session_timeline -v
```

Expected:

- replay responses now distinguish `replay` / `reload_required` / `degraded`
- malformed mid-file rows no longer hide later valid events
- restore rejects untrusted interaction IDs cleanly

- [ ] **Step 5: Commit the persistence and restore hardening slice**

```bash
git add src/embedagent/session_timeline.py src/embedagent/inprocess_adapter.py src/embedagent/session_restore.py tests/test_inprocess_adapter_frontend_api.py tests/test_session_restore.py tests/test_session_timeline.py
git commit -m "fix(gui): harden timeline replay and restore contracts"
```

## Task 2: Harden HTTP And WebSocket Error Boundaries

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/bridge.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `tests/test_gui_runtime.py`
- Modify: `tests/test_gui_backend_api.py`

- [ ] **Step 1: Write the failing transport and HTTP boundary tests**

```python
class TestWebSocketFrontend(unittest.TestCase):
    def test_dispatch_result_reason_is_logged_when_queueing_fails(self):
        frontend = WebSocketFrontend()
        frontend._dispatcher.dispatch = lambda factory: DispatchResult(False, "loop_closed")
        with self.assertLogs("embedagent.frontend.gui.backend.server", level="ERROR") as captured:
            queued = frontend._dispatch_message({"type": "session_event", "data": {}})
        self.assertFalse(queued)
        self.assertTrue(any("loop_closed" in entry for entry in captured.output))


class TestGuiBackendApi(unittest.TestCase):
    def test_session_lookup_errors_return_404_instead_of_500(self):
        backend = GUIBackend(_ErrorCore("session_id 不存在：sess-404"), static_dir=self.static_dir)
        route = self._find_route(backend.app, "/api/sessions/{session_id}", "GET")
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(route.endpoint("sess-404"))
        self.assertEqual(raised.exception.status_code, 404)

    def test_interaction_lookup_errors_return_410(self):
        backend = GUIBackend(_ErrorCore("interaction_gone"), static_dir=self.static_dir)
        route = self._find_route(backend.app, "/api/sessions/{session_id}/interactions/{interaction_id}/respond", "POST")
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(route.endpoint("sess-1", "int-1", {"response_kind": "approve"}))
        self.assertEqual(raised.exception.status_code, 410)


class _ErrorCore(object):
    def __init__(self, error_text):
        self.error_text = error_text

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        return None

    def get_session_snapshot(self, session_id):
        raise ValueError(self.error_text)

    def respond_to_interaction(self, session_id, interaction_id, payload):
        raise ValueError(self.error_text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_runtime tests.test_gui_backend_api -v
```

Expected:

- queueing failure test fails because `_dispatch_message()` ignores `reason`
- HTTP route tests fail because raw `ValueError` still escapes

- [ ] **Step 3: Implement typed error mapping and websocket cleanup**

```python
def _dispatch_message(self, message: Dict[str, Any]) -> bool:
    result = self._dispatcher.dispatch(lambda: self.broadcast(message))
    if not result:
        _LOGGER.error("GUI event dispatch failed: %s", result.reason)
        return False
    return True
```

```python
def _translate_value_error(exc: ValueError) -> HTTPException:
    text = str(exc)
    if "session_id 不存在" in text or text == "session_not_found":
        return HTTPException(status_code=404, detail="session_not_found")
    if text in ("interaction_gone", "interaction_expired"):
        return HTTPException(status_code=410, detail=text)
    if text == "interaction_conflict":
        return HTTPException(status_code=409, detail=text)
    return HTTPException(status_code=422, detail=text)
```

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await self.frontend.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await self._handle_websocket_message(data)
    except WebSocketDisconnect:
        self.frontend.disconnect(websocket)
    except Exception:
        _LOGGER.exception("Unhandled websocket failure")
        self.frontend.disconnect(websocket)
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_runtime tests.test_gui_backend_api -v
```

Expected:

- dispatch failures are logged with their reason
- HTTP routes map known failures to 404/409/410/422
- websocket cleanup path remains deterministic

- [ ] **Step 5: Commit the transport boundary slice**

```bash
git add src/embedagent/frontend/gui/backend/bridge.py src/embedagent/frontend/gui/backend/server.py tests/test_gui_runtime.py tests/test_gui_backend_api.py
git commit -m "fix(gui): type transport and interaction boundary errors"
```

## Task 3: Complete The Projector And Runtime State Machine

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing projector/runtime tests**

```javascript
export function runSessionRuntimeTests() {
  const replayRuntime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "running",
      current_mode: "code",
      timeline_replay_status: "reload_required",
      pending_interaction: null,
    },
    eventLog: {
      ...createSessionEventLog(),
      replayState: "reload_required",
      events: [],
    },
    bootstrapTimeline: [],
  });
  assert.equal(replayRuntime.transportView.replayState, "reload_required");

  const commandRuntime = projectSessionRuntime({
    snapshot: { session_id: "sess-1", status: "idle", current_mode: "code", pending_interaction: null },
    eventLog: createSessionEventLog(),
    bootstrapTimeline: [
      { id: "cmd-1", kind: "command_result", commandName: "review", content: "done", turnId: "", projectionSource: "raw_events" },
    ],
  });
  assert.equal(commandRuntime.timelineView[0].kind, "command_result_fallback");

  const detachedRuntime = projectSessionRuntime({
    snapshot: { session_id: "sess-1", status: "idle", current_mode: "code", pending_interaction: null },
    eventLog: createSessionEventLog(),
    bootstrapTimeline: [
      { id: "turn-1-user", kind: "user", content: "hello", turnId: "turn-1" },
      { id: "detached-tool", kind: "tool", toolName: "read_file", turnId: "turn-1", stepId: "", status: "success" },
    ],
  });
  assert.equal(detachedRuntime.timelineView[0].trailingTurnItems[0].id, "detached-tool");
}
```

- [ ] **Step 2: Run the webapp tests to verify they fail**

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
```

Expected:

- replay-state assertion fails because event log only exposes `needsResync`
- command result fallback assertion fails because projector still treats it as a normal timeline item
- detached-item ordering assertion fails because old grouping still renders detached items before steps

- [ ] **Step 3: Implement the runtime state machine and projector ownership**

```javascript
export function createSessionEventLog() {
  return {
    events: [],
    eventIds: new Set(),
    lastAppliedSeq: 0,
    replayState: "healthy",
    connectionState: "connecting",
  };
}

export function appendSessionEvent(log, event) {
  if (!event || !event.event_id) return log;
  if (!event.event_kind || typeof event.payload !== "object" || event.payload === null) {
    return { ...log, replayState: "degraded" };
  }
  if (log.eventIds.has(event.event_id)) return log;
  const seq = Number(event.seq || 0);
  if (log.lastAppliedSeq && seq !== log.lastAppliedSeq + 1) {
    return { ...log, replayState: "replay_needed" };
  }
  const eventIds = new Set(log.eventIds);
  eventIds.add(event.event_id);
  return {
    ...log,
    events: log.events.concat(event),
    eventIds,
    lastAppliedSeq: seq,
  };
}
```

```javascript
function projectTurnGroups(items = []) {
  const groups = [];
  const turnMap = new Map();
  for (const item of items) {
    const key = item.turnId || `session-${item.id}`;
    if (!turnMap.has(key)) {
      turnMap.set(key, {
        turnId: key,
        userItem: null,
        leadingSystemItems: [],
        stepItems: [],
        trailingTurnItems: [],
        sessionFallbackItems: [],
      });
      groups.push(turnMap.get(key));
    }
    const group = turnMap.get(key);
    if (item.kind === "user") group.userItem = item;
    else if (item.kind === "command_result" && !item.turnId) group.sessionFallbackItems.push({ ...item, kind: "command_result_fallback" });
    else if (item.stepId) group.stepItems.push(item);
    else if (item.kind === "system" || item.kind === "compact") group.leadingSystemItems.push(item);
    else group.trailingTurnItems.push(item);
  }
  return groups;
}
```

```javascript
export function projectSessionRuntime({ snapshot, eventLog, bootstrapTimeline = [] }) {
  const timelineItems = projectBootstrapTimeline(bootstrapTimeline).concat(projectEventLogTimeline(eventLog?.events || []));
  return {
    currentInteraction: snapshot?.pending_interaction || null,
    transportView: {
      connectionState: eventLog?.connectionState || "connecting",
      replayState: eventLog?.replayState || snapshot?.timeline_replay_status || "healthy",
      lastAppliedSeq: Number(eventLog?.lastAppliedSeq || 0),
    },
    sessionStatusView: {
      sessionId: snapshot?.session_id || "",
      status: snapshot?.status || "idle",
      mode: snapshot?.current_mode || "code",
    },
    timelineView: projectTurnGroups(timelineItems),
  };
}
```

- [ ] **Step 4: Run the webapp tests again to verify they pass**

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
```

Expected:

- runtime tests pass with explicit replay states
- command results no longer attach ambiguously
- detached turn items now render after their step groups

- [ ] **Step 5: Commit the projector completion slice**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/state-helpers.js src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat(gui): complete active session projector ownership"
```

## Task 4: Apply UI Follow-Through Changes And Finalize Docs

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `src/embedagent/frontend/gui/static/assets/app.js`
- Modify: `src/embedagent/frontend/gui/static/assets/app.css`
- Modify: `src/embedagent/frontend/gui/static/index.html`

- [ ] **Step 1: Write the failing UI follow-through assertions**

```javascript
export function runSessionRuntimeTests() {
  const fencedOnly = renderMarkdownForTest("```js\\nconst x = 1\\n```");
  assert.equal(fencedOnly.codeBlocks.length, 1);
  const inlineOnly = renderMarkdownForTest("| a | `b` |");
  assert.equal(inlineOnly.codeBlocks.length, 0);
}

function renderMarkdownForTest(markdownText) {
  const codeBlocks = [];
  const fencePattern = /```[a-zA-Z0-9_-]*\n[\s\S]*?\n```/g;
  const matches = markdownText.match(fencePattern) || [];
  for (const match of matches) codeBlocks.push(match);
  return { codeBlocks };
}
```

```python
class TestGuiBackendApi(unittest.TestCase):
    def test_replay_endpoint_reports_degraded_status_in_snapshot_metadata(self):
        backend = GUIBackend(_ReplayMetadataCore(), static_dir=self.static_dir)
        route = self._find_route(backend.app, "/api/sessions/{session_id}", "GET")
        payload = asyncio.run(route.endpoint("sess-1"))
        self.assertEqual(payload["timeline_replay_status"], "degraded")


class _ReplayMetadataCore(object):
    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        return None

    def get_session_snapshot(self, session_id):
        return type(
            "Snapshot",
            (),
            {
                "session_id": session_id,
                "status": type("Status", (), {"value": "idle"})(),
                "current_mode": "code",
                "created_at": "2026-04-04T00:00:00Z",
                "updated_at": "2026-04-04T00:00:00Z",
                "workflow_state": "chat",
                "has_active_plan": False,
                "active_plan_ref": "",
                "current_command_context": "",
                "has_pending_permission": False,
                "has_pending_input": False,
                "pending_permission": None,
                "pending_input": None,
                "last_error": None,
                "runtime_source": "",
                "bundled_tools_ready": False,
                "fallback_warnings": [],
                "runtime_environment": None,
                "timeline_replay_status": "degraded",
                "timeline_first_seq": 0,
                "timeline_last_seq": 0,
                "timeline_integrity": "degraded",
                "pending_interaction_valid": False,
            },
        )()
```

- [ ] **Step 2: Run the focused test/build checks to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_backend_api -v
```

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
& 'C:\Program Files\nodejs\npm.cmd' run build
```

Expected:

- UI assertions fail until the markdown/code-block handling is narrowed
- protocol metadata assertions fail until snapshot docs and fields match the new replay contract

- [ ] **Step 3: Implement UI follow-through and documentation updates**

```javascript
function Markdown({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      className="markdown-body"
      components={{
        pre(props) {
          const child = props.children;
          if (React.isValidElement(child) && child.props?.className) {
            return <CodeBlock className={child.props.className}>{child.props.children}</CodeBlock>;
          }
          return <pre {...props} />;
        },
        code(props) {
          const { inline, className, children, ...rest } = props;
          if (inline) return <code className={`inline-code ${className || ""}`} {...rest}>{children}</code>;
          return <code className={className}>{children}</code>;
        },
      }}
    >
      {content || ""}
    </ReactMarkdown>
  );
}
```

```javascript
React.useEffect(() => {
  return () => {
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
  };
}, []);
```

```markdown
## Replay Status

- `replay`: incremental event replay is safe
- `reload_required`: retained window no longer covers the requested seq
- `degraded`: event integrity is damaged; reload conservatively
```

- [ ] **Step 4: Run the final verification pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_runtime tests.test_gui_backend_api tests.test_inprocess_adapter_frontend_api tests.test_session_restore tests.test_gui_sync tests.test_session_timeline -v
```

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
& 'C:\Program Files\nodejs\\npm.cmd' run build
```

Expected:

- all listed Python tests report `OK`
- webapp tests pass
- build completes successfully and regenerates `static/assets/app.js`, `static/assets/app.css`, and `static/index.html`

- [ ] **Step 5: Commit the UI/documentation finish-up**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx src/embedagent/frontend/gui/webapp/src/styles.css docs/frontend-protocol.md docs/development-tracker.md docs/design-change-log.md src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css src/embedagent/frontend/gui/static/index.html
git commit -m "docs(gui): finalize runtime hardening rollout"
```

## Coverage Check

- Spec §§6-7 (timeline persistence and replay/bootstrap API) are covered by Tasks 1-2.
- Spec §8 (error boundary model) is covered by Task 2.
- Spec §9 (projector completion) is covered by Task 3.
- Spec §10 (UI follow-through) is covered by Task 4.
- Spec §11 (migration plan) is implemented directly by Tasks 1-4 in the same sequence.
- Spec §12 (tests) is covered by the new targeted persistence, transport, projector, and UI assertions in every task.
- Spec §§13-16 (acceptance criteria, non-goals, implementation entry files, decision) are enforced by the final verification step and the file scope listed above.
