# Frontend Transport Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make session bootstrap, live event ordering, gap recovery, session switching, and transport shutdown lossless and deterministic for every frontend shell.

**Architecture:** Host owns a per-session synchronization boundary shared by event publication and bootstrap cursor capture. GUI installs bootstrap projection plus `event_cursor` as one generation, buffers live envelopes during activation/recovery, and ignores stale work; the WebSocket owner also owns every retry timer and cancellation handle. TUI consumes the same cursor contract in the later strict-protocol plan, so this plan changes no presentation behavior.

**Tech Stack:** Python 3.8, `embedagent-host`, `embedagent-protocol`, FastAPI payload serializers, React 18 JavaScript runtime, Node test runner, pytest.

---

## Preconditions And File Responsibilities

This plan implements Stage 1 of `docs/superpowers/specs/2026-08-03-frontend-shell-convergence-design.md`. It has no dependency on later frontend plans and must merge before strict protocol authority begins.

- `packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py`: per-session sequence allocation and synchronized cursor reads.
- `packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py`: the only publication/capture synchronization boundary.
- `packages/embedagent-host/src/embedagent_host/runtime/session_bootstrap_service.py`: bootstrap projection assembly; it must not invent a cursor.
- `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`: obtains bootstrap through the event emitter's synchronized capture API.
- `src/embedagent/frontend/gui/backend/protocol_payloads.py`: forwards the Host cursor without renumbering.
- `src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js`: pure event-ordering and buffering state machine.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js`: socket, retry timer, recovery generation, and close ownership.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js`: atomic bootstrap/cursor installation for a selected session.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-effect-executor.js`: applies only events accepted by the active transport generation.

The lock order is always event-stream scope before projection loaders. Code inside bootstrap loaders must never call back into event publication. Event handlers receive the already allocated envelope while the same event-stream scope is held, so bootstrap is either entirely before or entirely after publication.

### Task 1: Add A Synchronized Host Cursor Contract

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py`
- Test: `tests/test_session_event_protocol.py`

- [ ] **Step 1: Write failing encoder and emitter concurrency tests**

Add tests that assert independent cursors and that a capture cannot interleave with an event publication:

```python
def test_event_emitter_capture_returns_projection_and_current_cursor_atomically():
    emitter = EventEmitter()
    received = []
    emitter.add_handler(None, received.append)
    emitter.emit(None, "turn_start", "s-1", {"turn_id": "turn-1"})

    captured = emitter.capture("s-1", lambda: {"snapshot": {"status": "idle"}})

    assert captured["event_cursor"] == 1
    assert captured["snapshot"] == {"status": "idle"}


def test_event_emitter_capture_excludes_publication_blocked_behind_capture():
    emitter = EventEmitter()
    entered = threading.Event()
    release = threading.Event()
    published = []

    def load_projection():
        entered.set()
        assert release.wait(1.0)
        return {"snapshot": {"status": "running"}}

    capture_thread = threading.Thread(
        target=lambda: published.append(emitter.capture("s-1", load_projection))
    )
    capture_thread.start()
    assert entered.wait(1.0)
    event_thread = threading.Thread(
        target=lambda: emitter.emit(None, "turn_start", "s-1", {"turn_id": "turn-1"})
    )
    event_thread.start()
    release.set()
    capture_thread.join(1.0)
    event_thread.join(1.0)

    assert published[0]["event_cursor"] == 0
    assert emitter.current_cursor("s-1") == 1
```

Import `threading` at the top of the test file.

- [ ] **Step 2: Run the focused tests and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_session_event_protocol.py`

Expected: FAIL because `EventEmitter.capture` and `EventEmitter.current_cursor` do not exist.

- [ ] **Step 3: Implement per-session re-entrant stream scopes**

Use a guard only to create session locks, and use each session lock for allocation, publication, and capture:

```python
class SessionEventEncoder(object):
    def __init__(self) -> None:
        self._locks_guard = threading.Lock()
        self._session_locks = {}  # type: Dict[str, threading.RLock]
        self._sequences = {}  # type: Dict[str, int]

    def session_scope(self, session_id: str):
        resolved = str(session_id or "")
        with self._locks_guard:
            lock = self._session_locks.get(resolved)
            if lock is None:
                lock = threading.RLock()
                self._session_locks[resolved] = lock
        return lock

    def current_sequence(self, session_id: str) -> int:
        resolved = str(session_id or "")
        with self.session_scope(resolved):
            return int(self._sequences.get(resolved, 0) or 0)
```

Change `encode()` to allocate under `with self.session_scope(resolved_session_id):`. In `EventEmitter`, hold the same scope across envelope creation and handler dispatch, then add:

```python
def current_cursor(self, session_id: str) -> int:
    return self._encoder.current_sequence(session_id)

def capture(
    self,
    session_id: str,
    projection_loader: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    with self._encoder.session_scope(session_id):
        payload = dict(projection_loader() or {})
        payload["event_cursor"] = self._encoder.current_sequence(session_id)
        return payload
```

Do not expose the encoder or let bootstrap services maintain a second sequence counter.

- [ ] **Step 4: Run the focused tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_session_event_protocol.py`

Expected: PASS for all event protocol tests.

- [ ] **Step 5: Commit the Host stream boundary**

```bash
git add packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py tests/test_session_event_protocol.py
git commit -m "fix: synchronize session event cursors"
```

### Task 2: Capture Bootstrap Through The Host Stream Boundary

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`
- Test: `tests/test_gui_protocol_projection.py`

- [ ] **Step 1: Add failing bootstrap cursor tests**

Extend the existing bootstrap contract tests:

```python
def test_bootstrap_payload_includes_current_live_event_cursor(self):
    session_id = str(self.snapshot.get("session_id") or "")
    self.adapter._event_emitter.emit(None, "turn_start", session_id, {"turn_id": "turn-1"})

    payload = self.adapter.get_session_bootstrap(session_id)

    self.assertEqual(payload["event_cursor"], 1)
```

In `tests/test_gui_protocol_projection.py`, pass `"event_cursor": 7` into `serialize_session_bootstrap()` and assert `payload["event_cursor"] == 7`. Also assert a missing cursor serializes as `0`, never `None` or a fabricated non-zero value.

- [ ] **Step 2: Run both test files and verify the red state**

Run: `uv run python scripts/test-suite.py tdd tests/test_inprocess_adapter_frontend_api.py tests/test_gui_protocol_projection.py`

Expected: FAIL because the cursor is absent from Host and GUI bootstrap payloads.

- [ ] **Step 3: Route bootstrap assembly through `EventEmitter.capture`**

Keep `SessionBootstrapService.build()` focused on projection assembly. Change the adapter boundary to:

```python
def get_session_bootstrap(self, reference: str, mode: str = "") -> Dict[str, Any]:
    state = self._ensure_session_active(reference, mode)
    return self._event_emitter.capture(
        state.session_id,
        lambda: self._bootstrap_service.build(state.session_id),
    )
```

In `serialize_session_bootstrap()`, copy and validate the cursor:

```python
event_cursor = int(data.get("event_cursor", 0) or 0)
if event_cursor < 0:
    raise ValueError("event_cursor must be non-negative")
result["event_cursor"] = event_cursor
```

Do not read a private encoder field in the adapter or serializer.

- [ ] **Step 4: Run the focused tests and verify the green state**

Run: `uv run python scripts/test-suite.py tdd tests/test_inprocess_adapter_frontend_api.py tests/test_gui_protocol_projection.py`

Expected: PASS for the bootstrap tests, including cursor `0` for sessions with no published live events.

- [ ] **Step 5: Commit the bootstrap cursor contract**

```bash
git add packages/embedagent-host/src/embedagent_host/inprocess_adapter.py src/embedagent/frontend/gui/backend/protocol_payloads.py tests/test_inprocess_adapter_frontend_api.py tests/test_gui_protocol_projection.py
git commit -m "feat: include live cursor in session bootstrap"
```

### Task 3: Replace GUI Event Ordering With A Buffered State Machine

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing pure state-machine assertions**

Add assertions for bootstrap buffering, duplicate removal, gap detection, and session isolation:

```javascript
let state = createSessionTransportState({ sessionId: "s-1", phase: "buffering" });
state = bufferSessionTransportEvent(state, envelope("s-1", 3, "evt-3"));
state = bufferSessionTransportEvent(state, envelope("s-1", 2, "evt-2"));
state = bufferSessionTransportEvent(state, envelope("s-2", 4, "other"));
const installed = installSessionTransportBootstrap(state, {
  sessionId: "s-1",
  generation: state.generation,
  eventCursor: 1,
});

assert.equal(installed.state.phase, "live");
assert.equal(installed.state.lastAppliedSeq, 3);
assert.deepEqual(installed.applied.map((item) => item.sequence), [2, 3]);
assert.equal(installed.state.bufferedEvents.length, 0);
```

Add a second case where the buffer contains sequences `2` and `4`; installation must return `reloadState: "reload_required"`, apply only `2`, and retain `4` for recovery.

- [ ] **Step 2: Run the webapp tests and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because `bufferSessionTransportEvent` and `installSessionTransportBootstrap` are undefined.

- [ ] **Step 3: Implement one pure transport state shape**

Use this canonical in-memory shape:

```javascript
export function createSessionTransportState(options = {}) {
  return {
    sessionId: String(options.sessionId || ""),
    generation: Number(options.generation || 0),
    phase: options.phase || "idle",
    bufferedEvents: [],
    events: [],
    eventIds: new Set(),
    lastAppliedSeq: Number(options.eventCursor || 0),
    reloadState: normalizeReloadState(options.reloadState),
    connectionState: options.connectionState || "connecting",
  };
}
```

Change `applySessionTransportEvent()` so `sequence <= lastAppliedSeq` returns `{ accepted: false, reason: "stale_sequence" }` without changing reload state, while `sequence !== lastAppliedSeq + 1` returns `sequence_gap` even when the installed cursor is `0`. Add direct tests proving sequence `3` after cursor `0` is a gap and a late sequence `2` after cursor `3` is harmlessly stale.

Implement `beginSessionTransportBootstrap`, `bufferSessionTransportEvent`, and `installSessionTransportBootstrap`. Installation must sort by sequence, discard `sequence <= eventCursor`, reject non-selected sessions, deduplicate by `event_id`, and reuse `applySessionTransportEvent()` for every post-cursor envelope. Return `{ state, applied, stale }` so effect execution never derives ordering a second time.

- [ ] **Step 4: Run the webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS, including the new out-of-order buffer and gap cases.

- [ ] **Step 5: Commit the pure transport state machine**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "fix: buffer session events around bootstrap"
```

### Task 4: Make Activation And Recovery Generation-Safe

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-effect-executor.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-activation-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-transport-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/socket-effect-executor.test.mjs`

- [ ] **Step 1: Add failing recovery and stale-generation tests**

Use deferred promises to prove that the newest activation wins:

```javascript
const first = deferred();
const second = deferred();
const load = createSessionActivationController(harness.deps({
  loadSessionBootstrap: (sessionId) => sessionId === "s-1" ? first.promise : second.promise,
}));
const firstLoad = load("s-1");
const secondLoad = load("s-2");
second.resolve(bootstrap("s-2", 8));
first.resolve(bootstrap("s-1", 4));
await Promise.all([firstLoad, secondLoad]);

assert.equal(harness.activatedSessionId(), "s-2");
assert.equal(harness.transport().lastAppliedSeq, 8);
```

Add a recovery test that starts at cursor `1`, receives sequence `3`, reloads a bootstrap with cursor `2`, and then accepts buffered sequence `3` without entering another recovery. Add a socket-effect test asserting actions for an unaccepted transport event are not dispatched.

- [ ] **Step 2: Run the four focused JavaScript test modules and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because activation has no generation and recovery reinstalls the old cursor.

- [ ] **Step 3: Install bootstrap and buffered envelopes as one generation**

Make `deriveSessionActivation()` return `eventCursor`:

```javascript
return {
  sessionId,
  eventCursor: Number(safePayload.event_cursor || 0),
  snapshot,
  activities: normalizeHistoryActivities(history.activities || []),
  historyIntegrity: history.integrity || null,
  plan: safePayload.plan || null,
  capabilities: normalizeCommandCapabilities(safePayload.capabilities || {}),
};
```

The activation controller must call `beginBootstrap(sessionId)`, await `loadSessionBootstrap(sessionId, { signal })`, verify the generation is still active, dispatch the projection, call `installBootstrap({ sessionId, generation, eventCursor })`, then dispatch only the returned post-cursor envelopes. A stale promise returns `{ stale: true }` and performs no dispatch.

The transport controller's `recover()` must use that same activation function. Delete the assignment that restores `state.lastAppliedSeq`; the installed bootstrap cursor is authoritative.

- [ ] **Step 4: Serialize recovery and suppress duplicate reloads**

Store one `recoveryPromise` per active generation:

```javascript
function recover(sessionId) {
  if (recoveryPromise) return recoveryPromise;
  recoveryPromise = Promise.resolve(activateSession(sessionId, { reason: "gap" }))
    .finally(() => {
      recoveryPromise = null;
    });
  return recoveryPromise;
}
```

`socket-effect-executor.js` must ask the controller to buffer/apply the envelope and must start at most one recovery. Remove its direct `loadSession` fallback, because that would create a second recovery path.

- [ ] **Step 5: Run the webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS; the next event after recovery is accepted, stale session bootstrap is ignored, and repeated gap events share one recovery promise.

- [ ] **Step 6: Commit generation-safe recovery**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js src/embedagent/frontend/gui/webapp/src/app-runtime/socket-effect-executor.js src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs src/embedagent/frontend/gui/webapp/test/session-activation-controller.test.mjs src/embedagent/frontend/gui/webapp/test/session-transport-controller.test.mjs src/embedagent/frontend/gui/webapp/test/socket-effect-executor.test.mjs
git commit -m "fix: make session recovery generation safe"
```

### Task 5: Give The Socket Owner Complete Shutdown Semantics

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-transport-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/websocket-lifecycle.test.mjs`

- [ ] **Step 1: Add failing timer and callback cancellation tests**

Use a fake clock with both timer methods:

```javascript
const clock = {
  callbacks: new Map(),
  nextId: 1,
  setTimeout(callback) {
    const id = this.nextId++;
    this.callbacks.set(id, callback);
    return id;
  },
  clearTimeout(id) {
    this.callbacks.delete(id);
  },
};
```

Assert that `close()` clears a scheduled retry, aborts the active bootstrap, increments the controller token, and leaves socket count unchanged even if an old `onclose`, `onopen`, or saved timer callback is invoked afterward.

- [ ] **Step 2: Run the focused controller test and verify the red state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: FAIL because the scheduled timer survives `close()`.

- [ ] **Step 3: Implement idempotent close ownership**

Track `retryTimerId`, `closed`, and the active abort controller. Before every reconnect, clear the stored timer id. In `close()` perform this order:

```javascript
closed = true;
manualClose = true;
token += 1;
if (retryTimerId !== null) clock.clearTimeout(retryTimerId);
retryTimerId = null;
abortActiveBootstrap();
const activeSocket = socket;
socket = null;
if (activeSocket) {
  activeSocket.onopen = null;
  activeSocket.onmessage = null;
  activeSocket.onerror = null;
  activeSocket.onclose = null;
  activeSocket.close();
}
```

`connect()` and every socket callback must return immediately when `closed` or when its captured token is stale. Calling `connect()` after `close()` is a no-op; construction of a new controller is the only restart path.

- [ ] **Step 4: Run the webapp tests and verify the green state**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS with no socket created by stale callbacks.

- [ ] **Step 5: Commit transport shutdown semantics**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js src/embedagent/frontend/gui/webapp/test/session-transport-controller.test.mjs src/embedagent/frontend/gui/webapp/test/websocket-lifecycle.test.mjs
git commit -m "fix: cancel closed frontend transports"
```

### Task 6: Lock In The Stage And Run Required Gates

**Files:**
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `docs/platform/frontend-protocol.md`
- Modify: `docs/platform/frontend-gui.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Generated: `src/embedagent/frontend/gui/static/*`

- [ ] **Step 1: Add architecture assertions for one cursor and one recovery path**

Add source guards that require `event_cursor` in Host bootstrap and forbid the retired recovery assignment and fallback:

```python
assert 'lastAppliedSeq: Number(state?.lastAppliedSeq' not in transport_controller
assert 'typeof loadSession === "function"' not in socket_effect_executor
assert 'payload["event_cursor"]' in protocol_payloads
```

Also assert `session-transport-controller.js` contains `clearTimeout` and that its `close()` invalidates the active token.

- [ ] **Step 2: Run architecture guards**

Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`

Expected: PASS.

- [ ] **Step 3: Update active authorities in place**

Document `event_cursor`, buffered activation/recovery, generation cancellation, and close semantics in the two owning platform documents. In current status, replace the Stage 1 blocker with the next open Stage 2 blocker; do not append a completion diary.

- [ ] **Step 4: Build and commit generated GUI assets**

Run from `src/embedagent/frontend/gui/webapp`: `npm test`

Expected: PASS.

Run from `src/embedagent/frontend/gui/webapp`: `npm run build`

Expected: exit code 0 and refreshed assets under `src/embedagent/frontend/gui/static/`.

- [ ] **Step 5: Run the complete required repository gates**

Run: `uv run python scripts/test-suite.py full`

Expected: PASS.

Run: `uv run --locked python scripts/lint.py`

Expected: PASS with no lint changes required.

- [ ] **Step 6: Verify no stale transport debt remains**

Run: `rg -n "lastAppliedSeq: Number\(state|void loadSession\(|setTimeout\(connect" src/embedagent/frontend/gui/webapp/src`

Expected: no matches.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 7: Commit Stage 1**

```bash
git add tests/test_pre_release_architecture_guards.py docs/platform/frontend-protocol.md docs/platform/frontend-gui.md docs/current-status.md docs/implementation-roadmap.md src/embedagent/frontend/gui/static
git commit -m "docs: establish frontend transport contract"
```

## Stage Exit Criteria

- Bootstrap carries a non-negative Host-owned `event_cursor` captured under the event publication boundary.
- Events received during activation or recovery are buffered and drained strictly after the installed cursor.
- A sequence gap causes exactly one recovery, and the first contiguous event after recovery is accepted.
- A rapid session switch cannot install stale projection, cursor, events, terminal summaries, or callbacks.
- `close()` owns and cancels socket callbacks, retry timers, bootstrap work, and buffered work.
- Focused tests, architecture guards, full Python tests, lint, webapp tests, and webapp build all pass.
