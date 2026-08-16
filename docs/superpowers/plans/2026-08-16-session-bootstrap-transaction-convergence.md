# Session Bootstrap Transaction Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Python and JavaScript bootstrap-producing client operation own one generation from before the request through cursor installation, while deriving terminal state from canonical event evidence and removing the request-then-install race.

**Architecture:** Keep Host, Core, `FrontendSessionPort`, and wire DTOs unchanged. Add one short-lived bootstrap transaction context inside each existing `SessionClientRuntime`; it buffers live envelopes, installs or rolls back against a committed synchronization baseline, and reconciles terminal outcome without duplicate event dispatch. Browser controllers delegate bootstrap-producing requests to the JavaScript runtime, and shared JSON fixtures enforce the same observable state machine in both languages.

**Tech Stack:** Python 3.8, `pytest`, stdlib threading/dataclasses, JavaScript ES modules, Node test harness, Vite/esbuild, existing six-wheel and PowerShell release tooling.

---

## File Map

- Modify `src/embedagent/frontend/runtime/session_client_runtime.py`: own Python bootstrap transactions, rollback, buffered event filtering, and terminal reduction.
- Modify `tests/test_session_client_commands.py`: deterministic Python race, terminal, rollback, and public-operation tests.
- Modify `tests/fixtures/session_client_runtime/contract.json`: cross-language returned-bootstrap and terminal evidence cases.
- Modify `tests/test_session_client_runtime_contract.py`: drive the new logical fixture operations through `FrontendSessionPort`.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js`: own browser transport requests, bootstrap transactions, rollback, and terminal reduction.
- Modify `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs`: drive the same logical fixture operations through browser transport.
- Modify `src/embedagent/frontend/gui/webapp/src/app-runtime/session-controller.js`: use runtime-owned create/mode/cancel operations.
- Modify `src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js`: use runtime-owned interaction response while retaining notice behavior.
- Modify `src/embedagent/frontend/gui/webapp/src/app-runtime/browser-app-runtime.js`: inject the runtime into the two controllers and remove after-the-fact installation wiring.
- Modify `src/embedagent/frontend/gui/webapp/test/session-controller.test.mjs`: enforce session controller/runtime ownership.
- Modify `src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs`: enforce interaction controller/runtime ownership and conflict reload.
- Modify `tests/test_pre_release_architecture_guards.py`: mechanically reject `installSessionBootstrap` and direct mutation ownership in controllers.
- Modify `docs/platform/frontend-protocol.md`: make all bootstrap-producing transactions explicit in the owning authority.
- Modify `docs/current-status.md`: replace the frontend convergence status after all gates pass.
- Regenerate `src/embedagent/frontend/gui/static/`: commit the webapp build produced from changed sources.
- Move the completed spec and plan to `docs/archive/session-bootstrap-transaction-convergence/` after repository-side acceptance closes.

### Task 1: Make Python Interaction Response One Bootstrap Transaction

**Files:**
- Modify: `tests/test_session_client_commands.py:79-104,289-335`
- Modify: `src/embedagent/frontend/runtime/session_client_runtime.py:24-190,435-645`

- [ ] **Step 1: Write the deterministic cursor regression test**

Add a port that models Host capturing cursor 3, followed by event 4 arriving before the response is installed:

```python
class CursorInterleavingInteractionPort(FakeSessionPort):
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime

    def respond_to_interaction(self, session_id, interaction_id, payload):
        del session_id, interaction_id, payload
        self.runtime.on_session_event(
            _event(
                "approval.resolved",
                {"interaction_id": "approval-1", "request_id": "approval-1"},
                sequence=3,
            )
        )
        captured = _bootstrap(cursor=3)
        self.runtime.on_session_event(
            _event(
                "session.finished",
                {
                    "final_text": "done",
                    "outcome": {"kind": "completed", "reason": "completed"},
                },
                sequence=4,
            )
        )
        return captured
```

Add the regression:

```python
def test_interaction_response_does_not_rewind_cursor_after_captured_bootstrap():
    actions = []
    runtime = SessionClientRuntime(dispatch=actions.append)
    port = CursorInterleavingInteractionPort(runtime)
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    runtime.on_session_event(
        _event(
            "approval.requested",
            {"interaction_id": "approval-1", "request_id": "approval-1"},
            sequence=2,
        )
    )

    runtime.respond_to_interaction("session-1", "approval-1", {"decision": "accept"})

    result = runtime.wait_for_terminal(timeout_s=0).to_dict()
    assert result["status"] == "completed"
    assert result["final_text"] == "done"
    assert runtime.event_cursor == 4
    assert [
        action.to_dict()["reason"]
        for action in actions
        if action.kind == "session_activated"
    ] == ["activate", "interaction_response"]
```

- [ ] **Step 2: Run the regression and verify the old cursor rewind**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py::test_interaction_response_does_not_rewind_cursor_after_captured_bootstrap
```

Expected: FAIL because `runtime.event_cursor` is 3 after `_install_returned_bootstrap` starts its generation too late.

- [ ] **Step 3: Add the Python transaction state and terminal reducer**

In `session_client_runtime.py`, import `dataclass` and define the short-lived synchronization baseline. Keep Python 3.8-compatible annotations:

```python
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class _RuntimeBaseline:
    active_session_id: str
    event_cursor: int
    lifecycle: str
    recovery_attempted: bool
    terminal_outcome: Optional[RuntimeAction]
```

Add `self._transaction_baseline = None  # type: Optional[_RuntimeBaseline]` in `__init__`. Replace terminal assignment in `on_session_event` with an ordered reducer:

```python
def _reduce_terminal_outcome(
    self,
    current: Optional[RuntimeAction],
    envelope: SessionEventEnvelope,
) -> Optional[RuntimeAction]:
    if envelope.event_kind in _INTERACTION_FINISH_EVENTS:
        return None
    terminal = self._terminal_from_event(envelope)
    return terminal if terminal is not None else current
```

Use it after accepting a continuous event:

```python
self._terminal_outcome = self._reduce_terminal_outcome(
    self._terminal_outcome,
    envelope,
)
```

Add these transaction helpers. An in-flight successor inherits the last committed baseline and existing buffer; activation buffers envelopes before session filtering:

```python
def _begin_bootstrap_transaction(self, target_session_id: str) -> int:
    with self._condition:
        self._assert_operable()
        if self._transaction_baseline is None:
            self._transaction_baseline = _RuntimeBaseline(
                active_session_id=self._active_session_id,
                event_cursor=self._event_cursor,
                lifecycle=self._lifecycle,
                recovery_attempted=self._recovery_attempted,
                terminal_outcome=self._terminal_outcome,
            )
        self._generation += 1
        generation = self._generation
        self._active_session_id = str(target_session_id or "")
        self._event_cursor = 0
        self._lifecycle = "activating"
        self._activating = True
        self._recovering = False
        self._recovery_attempted = False
        self._terminal_outcome = None
        self._condition.notify_all()
        return generation

def _rollback_bootstrap_transaction(self, generation: int) -> None:
    with self._condition:
        if self._lifecycle == "closed" or generation != self._generation:
            return
        baseline = self._transaction_baseline
        if baseline is None:
            return
        buffered = sorted(self._buffered_events, key=lambda item: item.sequence)
        self._active_session_id = baseline.active_session_id
        self._event_cursor = baseline.event_cursor
        self._lifecycle = baseline.lifecycle
        self._activating = False
        self._recovering = False
        self._recovery_attempted = baseline.recovery_attempted
        self._terminal_outcome = baseline.terminal_outcome
        self._buffered_events = []
        self._transaction_baseline = None
        self._condition.notify_all()
    for envelope in buffered:
        if envelope.session_id == baseline.active_session_id:
            self.on_session_event(envelope)
```

Change the start of `on_session_event` so transaction buffering precedes session filtering:

```python
if self._lifecycle in ("closed", "failed"):
    return
if self._activating:
    self._buffered_events.append(envelope)
    return
if envelope.session_id != self._active_session_id:
    return
if self._recovering:
    self._buffered_events.append(envelope)
    return
```

Change `_install_bootstrap` to filter by canonical session, reduce terminal state from cursor-covered evidence, clear the transaction baseline, and replay only later events:

```python
matching = sorted(
    (
        envelope
        for envelope in self._buffered_events
        if envelope.session_id == session_id
    ),
    key=lambda item: item.sequence,
)
terminal_outcome = None  # type: Optional[RuntimeAction]
for envelope in matching:
    if envelope.sequence <= bootstrap.event_cursor:
        terminal_outcome = self._reduce_terminal_outcome(
            terminal_outcome,
            envelope,
        )
self._event_cursor = bootstrap.event_cursor
self._lifecycle = self._bootstrap_lifecycle(bootstrap)
self._terminal_outcome = terminal_outcome
self._activating = False
self._recovering = False
self._buffered_events = []
self._transaction_baseline = None
buffered = [
    envelope for envelope in matching if envelope.sequence > bootstrap.event_cursor
]
```

Remove the `terminal_outcome` parameter from `_install_bootstrap`; transaction evidence is now its only terminal input. Clear `_transaction_baseline` in `_install_bootstrap`, `_fail_generation`, and `close` so no completed or failed transaction context survives.

Start `respond_to_interaction` with `_begin_bootstrap_transaction(session_id)` before calling the port. On a port exception, call `_rollback_bootstrap_transaction(generation)` and re-raise. Validate and install the returned bootstrap in the same generation. Do not use `discard_terminal`.

- [ ] **Step 4: Run focused Python terminal and interaction tests**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py
```

Expected: PASS, including the cursor 3/4 regression, covered-cursor terminal test, old-blocked clearing test, and structured terminal tests.

- [ ] **Step 5: Commit the Python interaction slice**

```powershell
git add tests/test_session_client_commands.py src/embedagent/frontend/runtime/session_client_runtime.py
git commit -m "fix: make interaction bootstrap transactional"
```

### Task 2: Converge Every Python Bootstrap-Producing Operation

**Files:**
- Modify: `tests/test_session_client_commands.py`
- Modify: `src/embedagent/frontend/runtime/session_client_runtime.py:142-171,337-384,609-645`

- [ ] **Step 1: Add pre-request generation, rollback, and supersession tests**

Add a mutation port that records runtime state while the port call is in progress:

```python
class InspectingMutationPort(FakeSessionPort):
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime
        self.observed = []
        self.error = None
        self.during_request = None

    def get_session_bootstrap(self, reference, mode=""):
        del mode
        cursor = 1 if reference == "session-1" else 2
        return _bootstrap(session_id=reference, cursor=cursor)

    def _response(self, session_id="session-1"):
        self.observed.append((self.runtime.lifecycle, self.runtime.generation))
        callback, self.during_request = self.during_request, None
        if callback is not None:
            callback()
        if self.error is not None:
            raise self.error
        return _bootstrap(session_id=session_id, cursor=2)

    def create_session(self, mode):
        del mode
        return self._response("session-2")

    def resume_session(self, reference, mode):
        del reference, mode
        return self._response()

    def set_session_mode(self, session_id, mode):
        del mode
        return self._response(session_id)

    def cancel_session(self, session_id):
        return self._response(session_id)
```

Add the public-operation assertion:

```python
@pytest.mark.parametrize(
    "invoke",
    (
        lambda runtime: runtime.create_session("debug"),
        lambda runtime: runtime.resume_session("latest", "debug"),
        lambda runtime: runtime.set_session_mode("session-1", "verify"),
        lambda runtime: runtime.cancel_session("session-1"),
    ),
)
def test_bootstrap_operations_begin_generation_before_port_request(invoke):
    runtime = SessionClientRuntime()
    port = InspectingMutationPort(runtime)
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    port.observed = []

    invoke(runtime)

    assert port.observed == [("activating", 2)]
```

Add request rollback with an event arriving inside the failed request:

```python
def test_failed_bootstrap_request_rolls_back_and_replays_buffered_event():
    runtime = SessionClientRuntime()
    port = InspectingMutationPort(runtime)
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    port.error = RuntimeError("request failed")
    port.during_request = lambda: runtime.on_session_event(
        _event("assistant.delta", {"text": "two"}, sequence=2)
    )

    with pytest.raises(RuntimeError, match="request failed"):
        runtime.set_session_mode("session-1", "verify")

    assert runtime.active_session_id == "session-1"
    assert runtime.event_cursor == 2
    assert runtime.lifecycle == "ready"
    assert runtime.generation == 2
```

Add supersession:

```python
def test_stale_returned_bootstrap_cannot_overwrite_nested_activation():
    runtime = SessionClientRuntime()
    port = InspectingMutationPort(runtime)
    runtime.bind_session_port(port)
    runtime.activate_session("session-1")
    port.during_request = lambda: runtime.activate_session("session-2")

    with pytest.raises(RuntimeError, match="bootstrap_transaction_superseded"):
        runtime.set_session_mode("session-1", "verify")

    assert runtime.active_session_id == "session-2"
    assert runtime.event_cursor == 2
    assert runtime.generation == 3
```

- [ ] **Step 2: Run the new Python operation tests and verify failure**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py
```

Expected: FAIL because create/resume/mode/cancel still call the port before beginning a generation, and stale returned bootstraps can overwrite a nested activation.

- [ ] **Step 3: Route all public methods through one helper and delete the workaround**

Add a single helper with the request callback fully enclosed by the transaction:

```python
def _run_bootstrap_transaction(
    self,
    target_session_id: str,
    reason: str,
    request: Callable[[], SessionBootstrap],
) -> SessionBootstrap:
    generation = self._begin_bootstrap_transaction(target_session_id)
    try:
        bootstrap = request()
    except (OSError, RuntimeError, TypeError, ValueError):
        self._rollback_bootstrap_transaction(generation)
        raise
    try:
        session_id = target_session_id or _required_session_id(bootstrap.thread.id)
        self._validate_bootstrap(bootstrap, session_id)
    except (AttributeError, TypeError, ValueError) as exc:
        self._fail_generation(generation, target_session_id, _failure_for_error(exc))
        raise
    if not self._install_bootstrap(generation, session_id, bootstrap, reason):
        raise RuntimeError("bootstrap_transaction_superseded")
    return bootstrap
```

Make `activate_session` preflight operability outside its error-conversion block, then call the same helper. This preserves `runtime_closed` for direct calls while retaining `Optional[SessionBootstrap]` for request/validation/supersession failures:

```python
session_id = _required_session_id(reference)
with self._condition:
    self._assert_operable()
    port = self._require_session_port()
try:
    return self._run_bootstrap_transaction(
        session_id,
        reason,
        lambda: port.get_session_bootstrap(session_id, mode),
    )
except (OSError, RuntimeError, TypeError, ValueError):
    return None
```

Route the returned-bootstrap methods as follows:

```python
return self._run_bootstrap_transaction(
    "",
    "create",
    lambda: port.create_session(str(mode or "")),
)
```

```python
return self._run_bootstrap_transaction(
    "",
    "resume",
    lambda: port.resume_session(str(reference or ""), str(mode or "")),
)
```

```python
selected_session_id = _required_session_id(session_id)
return self._run_bootstrap_transaction(
    selected_session_id,
    "mode_changed",
    lambda: port.set_session_mode(selected_session_id, str(mode or "")),
)
```

Use the same known-session pattern for interaction response and cancel. Make `activate_session` catch the helper's expected request, validation, and supersession errors and return `None`, retaining its existing public contract; returned-bootstrap mutation methods propagate their existing request errors and `bootstrap_transaction_superseded`. Delete `_RESET_TERMINAL`, `_install_returned_bootstrap`, its `discard_terminal` argument, and every identity comparison. Keep mutation return annotations as `SessionBootstrap`, so CLI code never dereferences an optional bootstrap.

- [ ] **Step 4: Run Python runtime, CLI, and TUI focused tests**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py tests/test_session_client_runtime_contract.py tests/test_cli_chat.py tests/test_cli_run.py tests/test_cli_sessions.py tests/test_tui_runtime.py
```

Expected: PASS.

- [ ] **Step 5: Prove the old Python debt is gone**

Run:

```powershell
rg -n "_RESET_TERMINAL|discard_terminal|_install_returned_bootstrap|observed_terminal is" src/embedagent/frontend/runtime/session_client_runtime.py tests
```

Expected: no matches.

- [ ] **Step 6: Commit the complete Python transaction path**

```powershell
git add tests/test_session_client_commands.py src/embedagent/frontend/runtime/session_client_runtime.py
git commit -m "refactor: converge python bootstrap operations"
```

### Task 3: Add the Same Transaction Contract to JavaScript Runtime

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js`

- [ ] **Step 1: Add direct JavaScript race and rollback tests**

Inside `runSessionClientRuntimeContractTests`, add this direct regression before promoting it into the shared fixture:

```javascript
const actions = [];
const transport = new FixtureTransport();
const runtime = new SessionClientRuntime({ transport, dispatch: (action) => actions.push(action) });
transport.responses.push(contract.bootstraps.session_1_cursor_1);
await runtime.activateSession("session-1");
await runtime.acceptSessionEvent(clone(contract.events.approval_requested));

const cursor3 = clone(contract.bootstraps.session_1_cursor_2);
cursor3.event_cursor = 3;
transport.respondToInteraction = async () => {
  await runtime.acceptSessionEvent(clone(contract.events.approval_resolved));
  await runtime.acceptSessionEvent({
    schema_version: 1,
    event_id: "session-finished-4",
    session_id: "session-1",
    sequence: 4,
    event_kind: "session.finished",
    timestamp: "2026-08-13T00:00:04Z",
    payload: {
      final_text: "done",
      outcome: { kind: "completed", reason: "completed" },
    },
  });
  return cursor3;
};

await runtime.respondToInteraction("session-1", "approval-1", { decision: "accept" });
await runtime.acceptSessionEvent(clone(contract.events.session_1_sequence_5));

assert.equal(runtime.cursor, 5);
assert.equal(runtime.lifecycle, "ready");
assert.equal(runtime.terminalOutcome.status, "completed");
assert.equal(
  actions.filter((action) => action.reason === "recovery").length,
  0,
);
```

Add request rollback:

```javascript
const rollbackTransport = new FixtureTransport();
const rollbackRuntime = new SessionClientRuntime({ transport: rollbackTransport });
rollbackTransport.responses.push(contract.bootstraps.session_1_cursor_1);
await rollbackRuntime.activateSession("session-1");
rollbackTransport.setSessionMode = async () => {
  await rollbackRuntime.acceptSessionEvent(clone(contract.events.session_1_sequence_2));
  throw new Error("request failed");
};

await assert.rejects(
  () => rollbackRuntime.setSessionMode("session-1", "verify"),
  /request failed/,
);
assert.equal(rollbackRuntime.sessionId, "session-1");
assert.equal(rollbackRuntime.cursor, 2);
assert.equal(rollbackRuntime.lifecycle, "ready");
assert.equal(rollbackRuntime.generation, 2);
```

Add stale completion suppression:

```javascript
const staleTransport = new FixtureTransport();
const staleRuntime = new SessionClientRuntime({ transport: staleTransport });
staleTransport.responses.push(contract.bootstraps.session_1_cursor_1);
await staleRuntime.activateSession("session-1");
staleTransport.setSessionMode = async () => {
  staleTransport.responses.push(contract.bootstraps.session_2_cursor_0);
  await staleRuntime.activateSession("session-2");
  return clone(contract.bootstraps.session_1_cursor_2);
};

assert.equal(await staleRuntime.setSessionMode("session-1", "verify"), null);
assert.equal(staleRuntime.sessionId, "session-2");
assert.equal(staleRuntime.cursor, 0);
assert.equal(staleRuntime.generation, 3);
```

- [ ] **Step 2: Run the webapp tests and verify the missing runtime methods**

Run from `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
```

Expected: FAIL because `respondToInteraction`, `setSessionMode`, `cancelSession`, and `createSession` are not owned by `SessionClientRuntime`, and JavaScript has no terminal reducer.

- [ ] **Step 3: Implement JavaScript transaction and terminal helpers**

Add `terminalOutcome` and `transactionBaseline` fields in the constructor. Implement the same ordered terminal reducer shape used by Python:

```javascript
function reduceTerminalOutcome(current, event, sessionId) {
  if (INTERACTION_FINISH_EVENTS.has(event.event_kind)) return null;
  if (INTERACTION_REQUEST_EVENTS.has(event.event_kind)) {
    return frozenCopy({
      kind: "terminal_outcome",
      session_id: sessionId,
      status: "blocked",
      final_text: "",
      outcome: {},
      failure: {
        code: "interaction_required",
        message: "session interaction is required",
        retryable: false,
        source: "session",
      },
    });
  }
  if (event.event_kind === "session.error") {
    return frozenCopy({
      kind: "terminal_outcome",
      session_id: sessionId,
      status: "failed",
      final_text: "",
      outcome: {},
      failure: record(event.payload?.failure)
        ? event.payload.failure
        : failureFor(new ProtocolError("session.error did not contain a valid failure")),
    });
  }
  if (event.event_kind !== "session.finished") return current;
  const outcome = record(event.payload?.outcome) ? event.payload.outcome : {};
  const reason = String(outcome.reason || event.payload?.termination_reason || "");
  const status =
    outcome.kind === "completed" || outcome.is_success === true
      ? "completed"
      : outcome.kind === "cancelled" || reason === "aborted" || reason === "cancelled"
        ? "cancelled"
        : outcome.kind === "blocked"
          ? "blocked"
          : "failed";
  const failureCode =
    status === "blocked"
      ? "interaction_required"
      : status === "cancelled"
        ? "cancelled"
        : "runtime_error";
  const defaultMessage =
    status === "blocked"
      ? "session is blocked"
      : status === "cancelled"
        ? "session was cancelled"
        : "session failed";
  return frozenCopy({
    kind: "terminal_outcome",
    session_id: sessionId,
    status,
    final_text: String(event.payload?.final_text || ""),
    outcome,
    failure: status === "completed" ? null : {
      code: failureCode,
      message: String(outcome.message || defaultMessage),
      retryable: false,
      source: "session",
    },
  });
}
```

Add the transaction helpers:

```javascript
#beginBootstrapTransaction(targetSessionId) {
  this.#assertOperable();
  if (!this.transactionBaseline) {
    this.transactionBaseline = Object.freeze({
      sessionId: this.sessionId,
      cursor: this.cursor,
      lifecycle: this.lifecycle,
      recoveryAttempted: this.recoveryAttempted,
      terminalOutcome: this.terminalOutcome,
    });
  }
  this.generation += 1;
  this.sessionId = String(targetSessionId || "");
  this.cursor = 0;
  this.lifecycle = "activating";
  this.activating = true;
  this.recovering = false;
  this.recoveryAttempted = false;
  this.terminalOutcome = null;
  return this.generation;
}

async #rollbackBootstrapTransaction(generation) {
  if (this.lifecycle === "closed" || generation !== this.generation) return false;
  const baseline = this.transactionBaseline;
  if (!baseline) return false;
  const buffered = this.activationBuffer.slice().sort((left, right) => left.sequence - right.sequence);
  this.sessionId = baseline.sessionId;
  this.cursor = baseline.cursor;
  this.lifecycle = baseline.lifecycle;
  this.activating = false;
  this.recovering = false;
  this.recoveryAttempted = baseline.recoveryAttempted;
  this.terminalOutcome = baseline.terminalOutcome;
  this.activationBuffer = [];
  this.transactionBaseline = null;
  for (const event of buffered) {
    if (event.session_id === baseline.sessionId) await this.acceptSessionEvent(event);
  }
  return true;
}

async #runBootstrapTransaction(targetSessionId, reason, request) {
  const generation = this.#beginBootstrapTransaction(targetSessionId);
  let value;
  try {
    value = await request();
  } catch (error) {
    await this.#rollbackBootstrapTransaction(generation);
    throw error;
  }
  let sessionId;
  let bootstrap;
  try {
    sessionId = targetSessionId || requiredSessionId(value?.thread?.id);
    bootstrap = validateBootstrap(value, sessionId);
  } catch (error) {
    this.#failGeneration(generation, String(targetSessionId || ""), failureFor(error));
    throw error;
  }
  return (await this.#installBootstrap(generation, sessionId, bootstrap, reason))
    ? bootstrap
    : null;
}
```

Set `transactionBaseline = null` after a successful install, generation failure, and close. Make `lifecycleForBootstrap` return `failed` for snapshot status `error` or `failed`, and make `#applyEventLifecycle` return to `ready` for `session.finished`.

On generation failure, set terminal state from the same structured failure rather than leaving a stale terminal:

```javascript
this.terminalOutcome = frozenCopy({
  kind: "terminal_outcome",
  session_id: sessionId,
  status: "failed",
  final_text: "",
  outcome: {},
  failure,
});
```

While `activating`, buffer a frozen canonical envelope before checking `session_id`. During install, filter to the validated session, reduce terminal outcome across matching events with `sequence <= event_cursor`, and feed only later events through `acceptSessionEvent`.

Use this installation split:

```javascript
const matching = this.activationBuffer
  .filter((event) => event.session_id === sessionId)
  .sort((left, right) => left.sequence - right.sequence);
let terminalOutcome = null;
for (const event of matching) {
  if (event.sequence <= bootstrap.event_cursor) {
    terminalOutcome = reduceTerminalOutcome(terminalOutcome, event, sessionId);
  }
}
this.cursor = bootstrap.event_cursor;
this.lifecycle = lifecycleForBootstrap(bootstrap);
this.terminalOutcome = terminalOutcome;
this.activating = false;
this.recovering = false;
this.activationBuffer = [];
this.transactionBaseline = null;
const buffered = matching.filter((event) => event.sequence > bootstrap.event_cursor);
```

After emitting `session_activated`, pass `buffered` through `acceptSessionEvent`. On the normal continuous-event path, assign:

```javascript
this.terminalOutcome = reduceTerminalOutcome(
  this.terminalOutcome,
  event,
  this.sessionId,
);
```

- [ ] **Step 4: Add public browser runtime operations and remove after-the-fact install**

Add these public methods:

```javascript
async createSession(mode = "", options = {}) {
  return this.#runBootstrapTransaction(
    "",
    "create",
    () => this.transport.createSession(String(mode || ""), options),
  );
}

async setSessionMode(sessionId, mode, options = {}) {
  const selected = requiredSessionId(sessionId);
  return this.#runBootstrapTransaction(
    selected,
    "mode_changed",
    () => this.transport.setSessionMode(selected, String(mode || ""), options),
  );
}

async cancelSession(sessionId, options = {}) {
  const selected = requiredSessionId(sessionId);
  return this.#runBootstrapTransaction(
    selected,
    "cancel",
    () => this.transport.cancelSession(selected, options),
  );
}

async respondToInteraction(sessionId, interactionId, payload, options = {}) {
  const selected = requiredSessionId(sessionId);
  return this.#runBootstrapTransaction(
    selected,
    "interaction_response",
    () => this.transport.respondToInteraction(
      selected,
      String(interactionId || ""),
      payload || {},
      options,
    ),
  );
}
```

Make `activateSession` delegate to the same primitive while preflighting outside the catch so calls after close still reject:

```javascript
async activateSession(reference, options = {}) {
  this.#assertOperable();
  const sessionId = requiredSessionId(reference);
  try {
    return await this.#runBootstrapTransaction(
      sessionId,
      options.reason || "activate",
      () => this.transport.loadSessionBootstrap(sessionId, options),
    );
  } catch {
    return null;
  }
}
```

Delete public `installSessionBootstrap` completely. Keep recovery within the current generation and keep `close()` authoritative over late completions.

- [ ] **Step 5: Run the focused webapp runtime suite**

Run from `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
```

Expected: PASS, with no recovery action in the deterministic cursor 3/4/5 case.

- [ ] **Step 6: Commit the JavaScript runtime slice**

```powershell
git add src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs
git commit -m "fix: make browser bootstrap operations transactional"
```

### Task 4: Move Browser Controllers Behind the Runtime Boundary

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/session-controller.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs`
- Modify: `tests/test_pre_release_architecture_guards.py:1018-1038`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/session-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/browser-app-runtime.js:202-210,282-291,377-386`

- [ ] **Step 1: Rewrite controller tests around a runtime facade**

In `session-controller.test.mjs`, replace protocol mutation fakes and `installSessionBootstrap` with:

```javascript
const sessionRuntime = {
  async createSession(mode) {
    calls.push(["createSession", mode]);
    return bootstrap("sess-new", mode || "agent-default");
  },
  async setSessionMode(sessionId, mode) {
    calls.push(["setSessionMode", sessionId, mode]);
    return bootstrap(sessionId, mode);
  },
  async cancelSession(sessionId) {
    calls.push(["cancelSession", sessionId]);
    return bootstrap(sessionId);
  },
};
```

Keep `protocol.sendSessionMessage` as the only session-controller protocol mutation. Assert create/mode/cancel call the runtime and no installed-bootstrap list exists.

In `interaction-response-controller.test.mjs`, inject:

```javascript
sessionRuntime: {
  respondToInteraction: async (sessionId, interactionId, response) => {
    calls.push({ sessionId, interactionId, response });
    return pendingResponse.promise;
  },
},
```

For the 410 case, make the runtime method throw the same error and retain the existing `loadSession`, notice, log, and duplicate-submit assertions.

Add architecture assertions:

```python
assert "installSessionBootstrap" not in runtime_text
assert "installSessionBootstrap" not in browser_text
assert "installSessionBootstrap" not in session_controller_text
assert "installSessionBootstrap" not in interaction_controller_text
assert "sessionRuntime.createSession" in session_controller_text
assert "sessionRuntime.respondToInteraction" in interaction_controller_text
```

- [ ] **Step 2: Run controller and architecture tests and verify failure**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_pre_release_architecture_guards.py::test_gui_session_activation_bootstrap_is_session_runtime_owned
```

Then, from `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
```

Expected: FAIL because controllers and `BrowserAppRuntime` still expose `installSessionBootstrap` and perform protocol mutation before runtime installation.

- [ ] **Step 3: Rewire session and interaction controllers**

Change `createSessionController` to require `sessionRuntime.createSession`, `setSessionMode`, and `cancelSession`; retain only `protocol.sendSessionMessage`. The command bodies become:

```javascript
async function createSession(mode) {
  const bootstrap = await sessionRuntime.createSession(String(mode || "").trim());
  await loadSessions();
  return String(bootstrap?.thread?.id || "");
}

async function setMode(mode) {
  dispatch({ type: "mode_requested", mode });
  const sessionId = getCurrentSessionId();
  if (sessionId) await sessionRuntime.setSessionMode(sessionId, mode);
}

async function cancelSession() {
  const sessionId = getCurrentSessionId();
  if (!sessionId) return;
  dispatch({ type: "stream_completed" });
  await sessionRuntime.cancelSession(sessionId);
}
```

Change `createInteractionResponseController` to bind the runtime method:

```javascript
const respond =
  sessionRuntime && typeof sessionRuntime.respondToInteraction === "function"
    ? sessionRuntime.respondToInteraction.bind(sessionRuntime)
    : null;
```

The successful request branch becomes:

```javascript
const response = await respond(sessionId, interactionId, payload || {});
if (!response?.thread?.id) throw new Error("invalid_session_bootstrap_response");
send({
  type: "log_event",
  label: "interaction_response",
  detail: interactionLogDetail(interaction, payload || {}),
});
return response;
```

Remove the `installSessionBootstrap` argument and local installer. Keep the existing 409/410 reload, notice, log, and duplicate-submit branches unchanged.

In `browser-app-runtime.js`, delete the `installSessionBootstrap` wrapper and pass `sessionRuntime` to both controllers. Continue passing `protocol` to the session controller only for `sendSessionMessage`.

- [ ] **Step 4: Run focused controller and boundary tests**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_pre_release_architecture_guards.py::test_gui_session_activation_bootstrap_is_session_runtime_owned
```

From `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
```

Expected: PASS.

- [ ] **Step 5: Commit the controller boundary convergence**

```powershell
git add tests/test_pre_release_architecture_guards.py src/embedagent/frontend/gui/webapp/src/app-runtime/browser-app-runtime.js src/embedagent/frontend/gui/webapp/src/app-runtime/session-controller.js src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js src/embedagent/frontend/gui/webapp/test/session-controller.test.mjs src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs
git commit -m "refactor: move bootstrap mutations into browser runtime"
```

### Task 5: Promote Returned-Bootstrap Semantics to the Shared Contract

**Files:**
- Modify: `tests/fixtures/session_client_runtime/contract.json`
- Modify: `tests/test_session_client_runtime_contract.py:16-36,81-128`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs:39-120`

- [ ] **Step 1: Add shared bootstrap, event, operation, and final-state fixtures**

Duplicate the complete `session_1_cursor_2` object as `session_1_cursor_3` and `session_1_cursor_4`, changing only `event_cursor` to 3 and 4. Add these complete event values; `session_1_sequence_5` already exists:

```json
"session_1_sequence_4": {
  "schema_version": 1,
  "event_id": "event-1-4-finished",
  "session_id": "session-1",
  "sequence": 4,
  "event_kind": "session.finished",
  "timestamp": "2026-08-13T00:00:04Z",
  "payload": {
    "final_text": "done",
    "outcome": {"kind": "completed", "reason": "completed"}
  }
},
"session_2_sequence_1": {
  "schema_version": 1,
  "event_id": "event-2-1",
  "session_id": "session-2",
  "sequence": 1,
  "event_kind": "assistant.delta",
  "timestamp": "2026-08-13T00:00:01Z",
  "payload": {"text": "new session"}
}
```

Use logical `bootstrap_operation` cases with operation names `interaction_response`, `create`, `mode`, and `cancel`; the harness mappings below are the only language-specific names.

The primary regression case must be exactly:

```json
{
  "name": "returned_bootstrap_buffers_post_capture_event",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_1"},
    {"kind": "event", "event": "approval_requested"},
    {
      "kind": "bootstrap_operation",
      "operation": "interaction_response",
      "session_id": "session-1",
      "bootstrap": "session_1_cursor_3",
      "during_events": ["approval_resolved", "session_1_sequence_4"]
    },
    {"kind": "event", "event": "session_1_sequence_5"}
  ],
  "actions": [
    {"kind": "session_activated", "session_id": "session-1", "cursor": 1, "generation": 1, "reason": "activate"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 2, "event_kind": "approval.requested", "lifecycle": "waiting_interaction"},
    {"kind": "session_activated", "session_id": "session-1", "cursor": 3, "generation": 2, "reason": "interaction_response"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 4, "event_kind": "session.finished", "lifecycle": "ready"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 5, "event_kind": "assistant.delta", "lifecycle": "ready"}
  ],
  "final": {"session_id": "session-1", "cursor": 5, "generation": 2, "lifecycle": "ready", "terminal_status": "completed"}
}
```

Add the remaining cases exactly as follows. The harness control keys are deliberately transport-neutral:

```json
{
  "name": "cursor_covered_terminal_reduces_without_duplicate_dispatch",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_1"},
    {"kind": "event", "event": "approval_requested"},
    {
      "kind": "bootstrap_operation",
      "operation": "interaction_response",
      "session_id": "session-1",
      "bootstrap": "session_1_cursor_4",
      "during_events": ["approval_resolved", "session_1_sequence_4"]
    }
  ],
  "actions": [
    {"kind": "session_activated", "session_id": "session-1", "cursor": 1, "generation": 1, "reason": "activate"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 2, "event_kind": "approval.requested", "lifecycle": "waiting_interaction"},
    {"kind": "session_activated", "session_id": "session-1", "cursor": 4, "generation": 2, "reason": "interaction_response"}
  ],
  "final": {"session_id": "session-1", "cursor": 4, "generation": 2, "lifecycle": "ready", "terminal_status": "completed"}
},
{
  "name": "request_error_rolls_back_and_replays_committed_session",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_1"},
    {
      "kind": "bootstrap_operation",
      "operation": "mode",
      "session_id": "session-1",
      "request_error": "runtime_error",
      "during_events": ["session_1_sequence_2"],
      "expect_error": true
    }
  ],
  "actions": [
    {"kind": "session_activated", "session_id": "session-1", "cursor": 1, "generation": 1, "reason": "activate"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 2, "event_kind": "assistant.delta", "lifecycle": "ready"}
  ],
  "final": {"session_id": "session-1", "cursor": 2, "generation": 2, "lifecycle": "ready", "terminal_status": null}
},
{
  "name": "failed_superseding_activation_restores_committed_baseline",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_1"},
    {
      "kind": "bootstrap_operation",
      "operation": "mode",
      "session_id": "session-1",
      "bootstrap": "session_1_cursor_2",
      "during_activation": {"session_id": "session-2", "request_error": "runtime_error"},
      "expect_stale": true
    }
  ],
  "actions": [
    {"kind": "session_activated", "session_id": "session-1", "cursor": 1, "generation": 1, "reason": "activate"}
  ],
  "final": {"session_id": "session-1", "cursor": 1, "generation": 3, "lifecycle": "ready", "terminal_status": null}
},
{
  "name": "unknown_create_filters_buffer_to_returned_session",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_1"},
    {
      "kind": "bootstrap_operation",
      "operation": "create",
      "bootstrap": "session_2_cursor_0",
      "during_events": ["session_1_sequence_2", "session_2_sequence_1"]
    }
  ],
  "actions": [
    {"kind": "session_activated", "session_id": "session-1", "cursor": 1, "generation": 1, "reason": "activate"},
    {"kind": "session_activated", "session_id": "session-2", "cursor": 0, "generation": 2, "reason": "create"},
    {"kind": "session_event", "session_id": "session-2", "sequence": 1, "event_kind": "assistant.delta", "lifecycle": "ready"}
  ],
  "final": {"session_id": "session-2", "cursor": 1, "generation": 2, "lifecycle": "ready", "terminal_status": null}
},
{
  "name": "malformed_returned_bootstrap_fails_generation",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_1"},
    {
      "kind": "bootstrap_operation_raw",
      "operation": "mode",
      "session_id": "session-1",
      "bootstrap": "schema_mismatch",
      "expect_error": true
    }
  ],
  "actions": [
    {"kind": "session_activated", "session_id": "session-1", "cursor": 1, "generation": 1, "reason": "activate"},
    {"kind": "protocol_failed", "session_id": "session-1", "generation": 2, "code": "protocol_error"}
  ],
  "final": {"session_id": "session-1", "cursor": 0, "generation": 2, "lifecycle": "failed", "terminal_status": "failed"}
},
{
  "name": "close_during_returned_bootstrap_ignores_completion",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_1"},
    {
      "kind": "bootstrap_operation",
      "operation": "cancel",
      "session_id": "session-1",
      "bootstrap": "session_1_cursor_2",
      "during_close": true,
      "expect_stale": true
    }
  ],
  "actions": [
    {"kind": "session_activated", "session_id": "session-1", "cursor": 1, "generation": 1, "reason": "activate"},
    {"kind": "runtime_closed"}
  ],
  "final": {"session_id": "session-1", "cursor": 0, "generation": 3, "lifecycle": "closed", "terminal_status": null}
}
```

- [ ] **Step 2: Run both contract suites and verify unknown operations fail**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py
```

From `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
```

Expected: both FAIL with an unknown `bootstrap_operation` fixture operation.

- [ ] **Step 3: Extend the Python fixture port and dispatcher**

Give `FakeSessionPort` one response function and implement the port methods without duplicating scheduling behavior:

```python
def _take_response(self, operation):
    self.bootstrap_calls.append(operation)
    response = self.responses.pop(0)
    callback, self.during_bootstrap = self.during_bootstrap, None
    if callback is not None:
        callback()
    if isinstance(response, BaseException):
        raise response
    return response

def create_session(self, mode):
    del mode
    return self._take_response("create")

def set_session_mode(self, session_id, mode):
    del session_id, mode
    return self._take_response("mode")

def cancel_session(self, session_id):
    del session_id
    return self._take_response("cancel")

def respond_to_interaction(self, session_id, interaction_id, payload):
    del session_id, interaction_id, payload
    return self._take_response("interaction_response")
```

Map logical fixture operations explicitly:

```python
if operation["operation"] == "interaction_response":
    runtime.respond_to_interaction(
        operation["session_id"],
        "interaction-1",
        {"decision": "accept"},
    )
elif operation["operation"] == "create":
    runtime.create_session("build")
elif operation["operation"] == "mode":
    runtime.set_session_mode(operation["session_id"], "verify")
elif operation["operation"] == "cancel":
    runtime.cancel_session(operation["session_id"])
else:
    raise AssertionError("unknown bootstrap operation: %s" % operation["operation"])
```

Wrap that mapping in a zero-argument `invoke` function and enforce declared outcomes:

```python
if operation.get("expect_error"):
    with pytest.raises(FrontendPortError):
        invoke()
elif operation.get("expect_stale"):
    with pytest.raises(RuntimeError, match="bootstrap_transaction_superseded"):
        invoke()
else:
    invoke()
```

Build the callback and queued response before invoking the operation:

```python
if operation.get("request_error"):
    response = FrontendPortError(
        FailureRecord(
            code=operation["request_error"],
            message="request failed",
            retryable=False,
            source="session",
        )
    )
else:
    strict = kind != "bootstrap_operation_raw"
    response = _bootstrap(contract, operation["bootstrap"], strict=strict)
port.responses.append(response)

def during_request():
    for event_name in operation.get("during_events", []):
        runtime.on_session_event(_event(contract, event_name))
    nested = operation.get("during_activation")
    if nested:
        port.responses.append(
            FrontendPortError(
                FailureRecord(
                    code=nested["request_error"],
                    message="nested activation failed",
                    retryable=False,
                    source="session",
                )
            )
        )
        runtime.activate_session(nested["session_id"])
    if operation.get("during_close"):
        runtime.close()

if operation.get("during_events") or operation.get("during_activation") or operation.get("during_close"):
    port.during_bootstrap = during_request
```

Catch `FrontendPortError` only when `expect_error` is true, and catch `RuntimeError("bootstrap_transaction_superseded")` only when `expect_stale` is true.

Assert optional final state, deriving Python terminal status with:

```python
terminal = runtime._terminal_outcome  # contract-only inspection of transient state
actual_terminal = terminal.to_dict()["status"] if terminal is not None else None
```

- [ ] **Step 4: Extend the JavaScript fixture transport and dispatcher**

Give `FixtureTransport` the same response/callback helper and methods:

```javascript
async takeResponse() {
  const response = this.responses.shift();
  const callback = this.duringBootstrap;
  this.duringBootstrap = null;
  if (callback) await callback();
  if (response instanceof Error) throw response;
  return clone(response);
}

async loadSessionBootstrap() {
  return this.takeResponse();
}

async createSession() {
  return this.takeResponse();
}

async setSessionMode() {
  return this.takeResponse();
}

async cancelSession() {
  return this.takeResponse();
}

async respondToInteraction() {
  return this.takeResponse();
}
```

Configure each fixture operation with:

```javascript
const response = operation.request_error
  ? Object.assign(new Error("request failed"), { code: operation.request_error })
  : contract.bootstraps[operation.bootstrap];
transport.responses.push(response);
transport.duringBootstrap = async () => {
  for (const eventName of operation.during_events || []) {
    await runtime.acceptSessionEvent(clone(contract.events[eventName]));
  }
  if (operation.during_activation) {
    const nested = operation.during_activation;
    transport.responses.push(
      Object.assign(new Error("nested activation failed"), { code: nested.request_error }),
    );
    await runtime.activateSession(nested.session_id);
  }
  if (operation.during_close) runtime.close();
};
```

Set `duringBootstrap` only when one of those controls exists. Map operations with:

```javascript
const invoke = () => {
  if (operation.operation === "interaction_response") {
    return runtime.respondToInteraction(
      operation.session_id,
      "interaction-1",
      { decision: "accept" },
    );
  }
  if (operation.operation === "create") return runtime.createSession("build");
  if (operation.operation === "mode") {
    return runtime.setSessionMode(operation.session_id, "verify");
  }
  if (operation.operation === "cancel") {
    return runtime.cancelSession(operation.session_id);
  }
  throw new Error(`unknown bootstrap operation:${operation.operation}`);
};

if (operation.expect_error) {
  await assert.rejects(invoke);
} else if (operation.expect_stale) {
  assert.equal(await invoke(), null);
} else {
  await invoke();
}
```

Assert final state with:

```javascript
assert.deepEqual(
  {
    session_id: runtime.sessionId,
    cursor: runtime.cursor,
    generation: runtime.generation,
    lifecycle: runtime.lifecycle,
    terminal_status: runtime.terminalOutcome?.status || null,
  },
  testCase.final,
  `${testCase.name}:final`,
);
```

- [ ] **Step 5: Run both contract suites**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py tests/test_session_client_commands.py
```

From `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
```

Expected: PASS in both languages; the primary case contains no `session_activated` action with reason `recovery`.

- [ ] **Step 6: Commit the shared contract**

```powershell
git add tests/fixtures/session_client_runtime/contract.json tests/test_session_client_runtime_contract.py src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs
git commit -m "test: share returned bootstrap transaction contract"
```

### Task 6: Synchronize the Frontend Authority and Generated GUI

**Files:**
- Modify: `docs/platform/frontend-protocol.md:31,52-56,70`
- Regenerate: `src/embedagent/frontend/gui/static/`

- [ ] **Step 1: Update the owning frontend protocol authority**

Replace the bootstrap ordering paragraph with a mechanically explicit contract:

```markdown
两个 runtime 对每个 bootstrap-producing operation 都在请求 port/transport 前创建新 generation；这包括 activate、create/resume、mode、cancel 和 interaction response。事务期间 canonical envelope 只进入 generation buffer，不直接分发。安装以 Host `event_cursor` 为基线：cursor 已覆盖的 envelope 只参与 terminal outcome reduction，不重复分发；cursor 之后的连续 envelope 经唯一 live-event path 回放。请求失败回滚到最近 committed synchronization baseline，invalid bootstrap 使当前 generation 失败，late completion 不能覆盖新 generation 或 closed runtime。
```

Keep the authority explicit that the baseline is transient client synchronization state, not durable session truth, and that Host's publication boundary is unchanged.

- [ ] **Step 2: Build and test the webapp**

From `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
npm run build
```

Expected: both commands exit 0; the build updates committed assets under `src/embedagent/frontend/gui/static/`.

- [ ] **Step 3: Run architecture guards**

Run:

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit authority and generated assets**

```powershell
git add docs/platform/frontend-protocol.md src/embedagent/frontend/gui/static
git commit -m "docs: codify bootstrap transaction ownership"
```

### Task 7: Run Delivery Gates and Close the Active Slice

**Files:**
- Modify: `docs/current-status.md:20`
- Modify: `docs/superpowers/README.md`
- Create: `docs/archive/session-bootstrap-transaction-convergence/README.md`
- Move: `docs/superpowers/specs/2026-08-16-session-bootstrap-transaction-design.md`
- Move: `docs/superpowers/plans/2026-08-16-session-bootstrap-transaction-convergence.md`

- [ ] **Step 1: Run the exact staged CLI regression**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestCliSmokeGate::test_cli_smoke_crosses_staged_launcher_for_both_flavors
```

Expected: PASS for both minimal and full staged launcher flavors with no `chat_permission_exit_4_protocol_error`.

- [ ] **Step 2: Run required Python and lint gates**

Run:

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run --locked python scripts/lint.py
```

Expected: all commands exit 0.

- [ ] **Step 3: Build, inspect, and isolated-smoke all six wheels**

Run:

```powershell
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: exactly six distributions are built, checker reports no ownership/dependency defect, and wheel-only isolated smoke passes with network resolution disabled.

- [ ] **Step 4: Run package preflight and release assembly**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release
```

Expected: both commands exit 0. Record repository-side `TARGET_READY` evidence only; do not claim Windows 7 acceptance without a clean-machine evidence report.

- [ ] **Step 5: Replace current status and create the archive index**

In `docs/current-status.md`, replace the frontend runtime bullet with current verified truth:

```markdown
- CLI 与 TUI 共用 Python `SessionClientRuntime`；GUI 使用 browser-only JavaScript `SessionClientRuntime`。两种实现通过同一 JSON fixture 验证 activation、returned-bootstrap transaction、cursor、recovery、interaction、terminal evidence、generation 和 close。所有 bootstrap-producing operation 都在请求前开启 generation，controller 不拥有 bootstrap 安装，frontend runtime 不拥有 durable session truth。
```

Create `docs/archive/session-bootstrap-transaction-convergence/README.md`:

```markdown
# Session Bootstrap Transaction Convergence Archive

This package records the completed 2026-08-16 frontend runtime convergence slice.
Durable behavior is owned by `docs/platform/frontend-protocol.md` and rationale by
`docs/adrs/0007-unify-frontend-ports-and-client-runtime-contract.md`.

- `2026-08-16-session-bootstrap-transaction-design.md`
- `2026-08-16-session-bootstrap-transaction-convergence.md`
```

- [ ] **Step 6: Archive the closed spec and plan**

Run:

```powershell
New-Item -ItemType Directory -Force docs/archive/session-bootstrap-transaction-convergence | Out-Null
git mv docs/superpowers/specs/2026-08-16-session-bootstrap-transaction-design.md docs/archive/session-bootstrap-transaction-convergence/2026-08-16-session-bootstrap-transaction-design.md
git mv docs/superpowers/plans/2026-08-16-session-bootstrap-transaction-convergence.md docs/archive/session-bootstrap-transaction-convergence/2026-08-16-session-bootstrap-transaction-convergence.md
```

Remove the `Session Bootstrap Transaction Convergence` entry from `docs/superpowers/README.md`. Do not change the independent Windows 7 acceptance handoff.

- [ ] **Step 7: Verify documentation links and clean status**

Run:

```powershell
rg -n "session-bootstrap-transaction" docs
git diff --check
git status --short
```

Expected: references resolve to the archive or durable authority, `git diff --check` is silent, and status lists only the intended status/archive changes.

- [ ] **Step 8: Commit slice closure**

```powershell
git add docs/current-status.md docs/superpowers/README.md docs/archive/session-bootstrap-transaction-convergence
git commit -m "docs: close bootstrap transaction convergence"
```

After a user-controlled push, observe the corresponding remote CI run. A green hosted run confirms the repository regression is fixed but still does not constitute Windows 7 delivery acceptance.
