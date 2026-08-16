# Session Bootstrap Buffer Drain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Python and JavaScript session runtimes synchronized until bootstrap installation, recovery installation, or rollback has drained every applicable buffered envelope in canonical sequence order.

**Architecture:** Extend the existing runtime-owned bootstrap transaction instead of adding another queue. Installation restores the Host cursor, emits one activation action while ingress remains buffered, and drains contiguous envelopes through the same lifecycle/terminal reducer used by normal ingress; rollback uses the identical drain from its committed cursor. A real first gap still performs one Host bootstrap recovery, while a real repeated gap still fails closed.

**Tech Stack:** Python 3.8, threading conditions, pytest, JavaScript ES modules, Node.js test runner, shared JSON contract fixtures, GitHub Actions release partition.

---

## File Map

- `tests/fixtures/session_client_runtime/contract.json`: language-neutral event,
  bootstrap, reentrant-dispatch, recovery, and rollback scenarios.
- `tests/test_session_client_runtime_contract.py`: Python fixture transport and
  synchronous dispatch-injection harness.
- `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs`:
  JavaScript fixture transport and promise-aware dispatch-injection harness.
- `src/embedagent/frontend/runtime/session_client_runtime.py`: Python transaction,
  contiguous event reducer, recovery, rollback, and gated drain owner.
- `src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js`:
  browser-equivalent transaction and gated drain owner.
- `src/embedagent/frontend/gui/static/assets/app.js`: generated browser bundle.
- `tests/test_pre_release_architecture_guards.py`: mechanical guard against
  reintroducing clear-before-replay loops.
- `docs/platform/frontend-protocol.md`: durable cross-shell synchronization
  authority.
- `docs/current-status.md`: replace-in-place repository status after verification.
- `docs/archive/session-bootstrap-buffer-drain/`: closed spec/plan package after
  all repository-side gates pass.

### Task 1: Add Deterministic Cross-Language Failing Contracts

**Files:**
- Modify: `tests/fixtures/session_client_runtime/contract.json`
- Modify: `tests/test_session_client_runtime_contract.py:16-222`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs:51-214`

- [ ] **Step 1: Add cursor 5 and sequence 6 fixture records**

Add a `session_1_cursor_5` bootstrap by copying the existing session-1 bootstrap
shape and setting both `event_cursor` to 5 and snapshot status to `idle`. Add this
event under `events`:

```json
"session_1_sequence_6": {
  "schema_version": 1,
  "event_id": "event-1-6",
  "session_id": "session-1",
  "sequence": 6,
  "event_kind": "assistant.delta",
  "timestamp": "2026-08-13T00:00:06Z",
  "payload": {"text": "six"}
}
```

- [ ] **Step 2: Teach the Python fixture runner to inject events from dispatch**

In `_run_case`, replace `dispatch=actions.append` with a closure that records the
action first, then consumes one-shot `dispatch_injections` whose `match` fields
equal the observable action:

```python
    actions = []
    dispatch_injections = []
    runtime = None

    def dispatch(action):
        actions.append(action)
        observed = _observable(action)
        for injection in dispatch_injections:
            if injection["used"]:
                continue
            if all(observed.get(key) == value for key, value in injection["match"].items()):
                injection["used"] = True
                for event_name in injection["events"]:
                    runtime.on_session_event(_event(contract, event_name))

    runtime = SessionClientRuntime(dispatch=dispatch)
```

Before each operation, load its injection records without mutating the JSON
fixture:

```python
        dispatch_injections[:] = [
            {
                "match": dict(item["match"]),
                "events": list(item["events"]),
                "used": False,
            }
            for item in operation.get("dispatch_injections", [])
        ]
```

For `bootstrap_operation`, append an optional recovery response after the primary
response:

```python
            if operation.get("recovery_bootstrap"):
                port.responses.append(_bootstrap(contract, operation["recovery_bootstrap"]))
```

For `event` operations, arrange events that occur after recovery capture but before
the recovery response is returned:

```python
            recovery_events = list(operation.get("recovery_during_events", []))
            if recovery_events:
                port.during_bootstrap = lambda names=recovery_events: [
                    runtime.on_session_event(_event(contract, name)) for name in names
                ]
```

- [ ] **Step 3: Teach the JavaScript fixture runner the same injection schema**

Declare `dispatchInjections` and `dispatchPromises` before runtime construction.
Use this dispatch function:

```javascript
  let dispatchInjections = [];
  const dispatchPromises = [];
  runtime = new SessionClientRuntime({
    transport,
    dispatch(action) {
      assertDeeplyFrozen(action);
      actions.push(action);
      const observed = observable(action);
      for (const injection of dispatchInjections) {
        if (injection.used) continue;
        if (!Object.entries(injection.match).every(([key, value]) => observed[key] === value)) {
          continue;
        }
        injection.used = true;
        for (const eventName of injection.events) {
          dispatchPromises.push(
            runtime.acceptSessionEvent(clone(contract.events[eventName])),
          );
        }
      }
    },
  });
```

At the start of every operation, load one-shot injections:

```javascript
    dispatchInjections = (operation.dispatch_injections || []).map((item) => ({
      match: clone(item.match),
      events: [...item.events],
      used: false,
    }));
```

After invoking an operation, drain every promise, including promises appended by a
nested recovery activation:

```javascript
    while (dispatchPromises.length > 0) {
      await dispatchPromises.shift();
    }
```

Mirror the Python `recovery_bootstrap` queueing and set
`transport.duringBootstrap` from `recovery_during_events` before delivering an
`event` operation.

- [ ] **Step 4: Add the normal install drain case**

Add a shared case that starts from the existing approval wait, returns cursor 3
with event 4 buffered after capture, and injects event 5 from the interaction
activation dispatch:

```json
{
  "name": "activation_dispatch_cannot_overtake_buffered_event",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_1"},
    {"kind": "event", "event": "approval_requested"},
    {
      "kind": "bootstrap_operation",
      "operation": "interaction_response",
      "session_id": "session-1",
      "bootstrap": "session_1_cursor_3",
      "recovery_bootstrap": "session_1_cursor_5",
      "during_events": ["approval_resolved", "session_1_sequence_4"],
      "dispatch_injections": [
        {
          "match": {"kind": "session_activated", "reason": "interaction_response"},
          "events": ["session_1_sequence_5"]
        }
      ]
    }
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

- [ ] **Step 5: Add the recovery drain case**

Add a real first gap at sequence 4, event 5 during recovery capture, and event 6
from recovery activation dispatch:

```json
{
  "name": "recovery_dispatch_cannot_overtake_buffered_event",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_2"},
    {
      "kind": "event",
      "event": "session_1_sequence_4",
      "recovery_bootstrap": "session_1_cursor_4",
      "recovery_during_events": ["session_1_sequence_5"],
      "dispatch_injections": [
        {
          "match": {"kind": "session_activated", "reason": "recovery"},
          "events": ["session_1_sequence_6"]
        }
      ]
    }
  ],
  "actions": [
    {"kind": "session_activated", "session_id": "session-1", "cursor": 2, "generation": 1, "reason": "activate"},
    {"kind": "session_activated", "session_id": "session-1", "cursor": 4, "generation": 1, "reason": "recovery"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 5, "event_kind": "assistant.delta", "lifecycle": "ready"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 6, "event_kind": "assistant.delta", "lifecycle": "ready"}
  ],
  "final": {"session_id": "session-1", "cursor": 6, "generation": 1, "lifecycle": "ready", "terminal_status": "completed"}
}
```

- [ ] **Step 6: Add the rollback drain case**

Add a failed mode request that buffers events 2 and 3, injects event 4 while event
2 is dispatched, and queues cursor 4 only to make the current unwanted recovery
observable:

```json
{
  "name": "rollback_dispatch_cannot_overtake_buffered_event",
  "initial": {"lifecycle": "idle", "generation": 0, "cursor": 0},
  "operations": [
    {"kind": "activate", "session_id": "session-1", "bootstrap": "session_1_cursor_1"},
    {
      "kind": "bootstrap_operation",
      "operation": "mode",
      "session_id": "session-1",
      "request_error": "runtime_error",
      "recovery_bootstrap": "session_1_cursor_4",
      "during_events": ["session_1_sequence_2", "session_1_sequence_3"],
      "dispatch_injections": [
        {
          "match": {"kind": "session_event", "sequence": 2},
          "events": ["session_1_sequence_4"]
        }
      ],
      "expect_error": true
    }
  ],
  "actions": [
    {"kind": "session_activated", "session_id": "session-1", "cursor": 1, "generation": 1, "reason": "activate"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 2, "event_kind": "assistant.delta", "lifecycle": "ready"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 3, "event_kind": "assistant.delta", "lifecycle": "ready"},
    {"kind": "session_event", "session_id": "session-1", "sequence": 4, "event_kind": "session.finished", "lifecycle": "ready"}
  ],
  "final": {"session_id": "session-1", "cursor": 4, "generation": 2, "lifecycle": "ready", "terminal_status": "completed"}
}
```

- [ ] **Step 7: Run both contract suites and verify RED**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py
Push-Location src/embedagent/frontend/gui/webapp
npm test
Pop-Location
```

Expected: Python and JavaScript fail on the new case names. The normal case shows
an unexpected recovery, the recovery case emits `protocol_failed`, and the
rollback case recovers before its locally held event 3 is replayed. Do not change
expected actions to match current behavior.

### Task 2: Implement the Python Transaction-Gated Drain

**Files:**
- Modify: `src/embedagent/frontend/runtime/session_client_runtime.py:171-236`
- Modify: `src/embedagent/frontend/runtime/session_client_runtime.py:441-575`

- [ ] **Step 1: Extract the single contiguous-event reducer**

Add this method and use it from the contiguous branch of `on_session_event`:

```python
    def _accept_contiguous_event_locked(
        self,
        envelope: SessionEventEnvelope,
    ) -> RuntimeAction:
        self._event_cursor = envelope.sequence
        self._apply_event_lifecycle(envelope.event_kind)
        self._terminal_outcome = self._reduce_terminal_outcome(
            self._terminal_outcome,
            envelope,
        )
        self._condition.notify_all()
        return RuntimeAction(
            "session_event",
            {
                "event": envelope.to_dict(),
                "lifecycle": self._lifecycle,
                "generation": self._generation,
            },
        )
```

The normal ingress branch becomes:

```python
            else:
                action = self._accept_contiguous_event_locked(envelope)
```

- [ ] **Step 2: Add the ordered drain loop**

Add one private method used by install, recovery install, and rollback:

```python
    def _drain_buffered_events(self, generation: int, session_id: str) -> bool:
        while True:
            action = None  # type: Optional[RuntimeAction]
            recover = False
            fail = False
            with self._condition:
                if self._lifecycle == "closed" or generation != self._generation:
                    return False
                matching = sorted(
                    (
                        envelope
                        for envelope in self._buffered_events
                        if envelope.session_id == session_id
                    ),
                    key=lambda item: item.sequence,
                )
                pending = [
                    envelope
                    for envelope in matching
                    if envelope.sequence > self._event_cursor
                ]
                self._buffered_events = pending
                if not pending:
                    self._activating = False
                    self._recovering = False
                    self._transaction_baseline = None
                    self._condition.notify_all()
                    return True
                envelope = pending[0]
                if envelope.sequence != self._event_cursor + 1:
                    if self._recovery_attempted:
                        fail = True
                    else:
                        self._recovery_attempted = True
                        self._activating = False
                        self._recovering = True
                        recover = True
                else:
                    self._buffered_events = pending[1:]
                    action = self._accept_contiguous_event_locked(envelope)
            if fail:
                self._fail_generation(
                    generation,
                    session_id,
                    FailureRecord(
                        code="protocol_error",
                        message="session event sequence gap repeated after recovery",
                        retryable=False,
                        source="client_runtime",
                    ),
                )
                return True
            if recover:
                self._recover_generation(generation, session_id)
                return True
            if action is not None:
                self._dispatch_action(action)
```

This code deliberately dispatches outside the condition while leaving a
synchronization flag active. Reentrant ingress therefore appends to
`_buffered_events`, and the next loop iteration observes it.

- [ ] **Step 3: Keep install synchronized through activation dispatch and drain**

In `_install_bootstrap`, retain cursor-covered terminal reduction, but do not clear
`_activating`, `_recovering`, or `_transaction_baseline`. Replace the local replay
loop with:

```python
            self._buffered_events = [
                envelope
                for envelope in matching
                if envelope.sequence > bootstrap.event_cursor
            ]
            self._condition.notify_all()
        self._dispatch_action(
            RuntimeAction(
                "session_activated",
                {
                    "session_id": session_id,
                    "cursor": bootstrap.event_cursor,
                    "generation": generation,
                    "reason": str(reason or "activate"),
                    "bootstrap": bootstrap.to_dict(),
                },
            )
        )
        return self._drain_buffered_events(generation, session_id)
```

Delete the old `for envelope in buffered: self.on_session_event(envelope)` loop.

- [ ] **Step 4: Route rollback through the same drain**

Restore the committed baseline but keep activation buffering enabled until the
restored queue is empty:

```python
            self._active_session_id = baseline.active_session_id
            self._event_cursor = baseline.event_cursor
            self._lifecycle = baseline.lifecycle
            self._activating = True
            self._recovering = False
            self._recovery_attempted = baseline.recovery_attempted
            self._terminal_outcome = baseline.terminal_outcome
            self._buffered_events = [
                envelope
                for envelope in self._buffered_events
                if envelope.session_id == baseline.active_session_id
            ]
            self._condition.notify_all()
        self._drain_buffered_events(generation, baseline.active_session_id)
```

Delete the unlocked rollback replay loop and do not clear the transaction baseline
before the drain completes.

- [ ] **Step 5: Run Python focused tests and verify GREEN**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py tests/test_session_client_commands.py
```

Expected: all selected Python tests pass, including the three new shared cases and
the existing true repeated-gap terminal case.

### Task 3: Implement the Browser Transaction-Gated Drain

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js:280-378`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js:437-458`
- Modify: `src/embedagent/frontend/gui/static/assets/app.js`

- [ ] **Step 1: Extract the browser contiguous-event reducer**

Add this private method and call it from normal contiguous ingress:

```javascript
  #acceptContiguousEvent(event) {
    this.cursor = event.sequence;
    this.#applyEventLifecycle(event.event_kind);
    this.terminalOutcome = reduceTerminalOutcome(
      this.terminalOutcome,
      event,
      this.sessionId,
    );
    return {
      kind: "session_event",
      event,
      lifecycle: this.lifecycle,
      generation: this.generation,
    };
  }
```

The normal ingress path emits `this.#acceptContiguousEvent(event)` instead of
duplicating cursor, lifecycle, terminal, and action construction.

- [ ] **Step 2: Add the browser ordered drain loop**

Add the JavaScript equivalent of the Python helper:

```javascript
  async #drainBufferedEvents(generation, sessionId) {
    while (true) {
      if (this.lifecycle === "closed" || generation !== this.generation) return false;
      const pending = this.activationBuffer
        .filter((event) => event.session_id === sessionId && event.sequence > this.cursor)
        .sort((left, right) => left.sequence - right.sequence);
      this.activationBuffer = pending;
      if (pending.length === 0) {
        this.activating = false;
        this.recovering = false;
        this.transactionBaseline = null;
        return true;
      }
      const event = pending[0];
      if (event.sequence !== this.cursor + 1) {
        if (this.recoveryAttempted) {
          this.#failGeneration(
            generation,
            sessionId,
            failureFor(new ProtocolError("session event sequence gap repeated after recovery")),
          );
          return true;
        }
        this.recoveryAttempted = true;
        this.activating = false;
        this.recovering = true;
        await this.#recoverGeneration(generation, sessionId);
        return true;
      }
      this.activationBuffer = pending.slice(1);
      this.#emit(this.#acceptContiguousEvent(event));
    }
  }
```

Because `#emit` is synchronous, a dispatch callback can call the async ingress
method reentrantly; that method reaches the active buffer branch before its first
await and appends deterministically.

- [ ] **Step 3: Route browser install and rollback through the drain**

In `#installBootstrap`, preserve the active synchronization flags, keep only
matching events above the installed cursor, emit `session_activated`, and return:

```javascript
    return this.#drainBufferedEvents(generation, sessionId);
```

In `#rollbackBootstrapTransaction`, restore the baseline, set `activating = true`,
retain only baseline-session buffered events, and return:

```javascript
    return this.#drainBufferedEvents(generation, baseline.sessionId);
```

Delete both old `for ... acceptSessionEvent(...)` replay loops. Do not clear
`transactionBaseline` until the drain observes an empty queue.

- [ ] **Step 4: Run both focused suites and verify GREEN**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py tests/test_session_client_commands.py
Push-Location src/embedagent/frontend/gui/webapp
npm test
npm run build
Pop-Location
```

Expected: Python contract/command tests pass, all frontend helper checks pass, and
the frontend build exits 0.

- [ ] **Step 5: Confirm generated assets are the only mechanical output**

Run:

```powershell
git status --short
git diff --check
git diff --stat
```

Expected: only the shared fixture/runners, two runtime sources, and generated
`src/embedagent/frontend/gui/static/assets/app.js` are modified. There are no
whitespace errors.

- [ ] **Step 6: Commit the cross-runtime vertical slice**

```powershell
git add -- tests/fixtures/session_client_runtime/contract.json tests/test_session_client_runtime_contract.py src/embedagent/frontend/runtime/session_client_runtime.py src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js src/embedagent/frontend/gui/static/assets/app.js
git commit -m "fix: drain bootstrap events before readiness"
```

### Task 4: Guard And Document The Converged Boundary

**Files:**
- Modify: `tests/test_pre_release_architecture_guards.py:1018-1056`
- Modify: `docs/platform/frontend-protocol.md:31-58`

- [ ] **Step 1: Add a mechanical ownership guard**

Extend `test_gui_session_activation_bootstrap_is_session_runtime_owned` to read the
Python runtime as well and assert the shared drain boundary while rejecting the old
unlocked loops:

```python
    python_runtime_text = _read(
        ROOT / "src/embedagent/frontend/runtime/session_client_runtime.py"
    )
    assert "_drain_buffered_events" in python_runtime_text
    assert "#drainBufferedEvents" in runtime_text
    assert "for envelope in buffered:\n            self.on_session_event(envelope)" not in (
        python_runtime_text
    )
    assert "for (const event of buffered) await this.acceptSessionEvent(event)" not in (
        runtime_text
    )
```

- [ ] **Step 2: Verify the guard passes**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_pre_release_architecture_guards.py::test_gui_session_activation_bootstrap_is_session_runtime_owned
```

Expected: 1 passed.

- [ ] **Step 3: Update the durable frontend protocol authority**

Replace the bootstrap transaction paragraph with wording that states:

```markdown
两个 runtime 对每个 bootstrap-producing operation 都在请求 port/transport 前创建新 generation。事务同步状态覆盖 request、bootstrap install、`session_activated` dispatch 和 ordered buffer drain；在 drain 持锁观察到 applicable queue 为空前，canonical envelope 只入 generation buffer。安装以 Host `event_cursor` 为基线，cursor 已覆盖的 envelope 只参与 terminal outcome reduction，cursor 后的连续 envelope 由 runtime-owned drain 逐个推进唯一 live-event reducer。recovery install 与 request rollback 复用同一 drain boundary，因此新 envelope 不能越过待回放的前序 envelope。真实首 gap 仍只触发一次 recovery，真实 repeated gap 仍 fail closed。
```

Keep request rejection, malformed bootstrap, supersession, and close semantics in
the following sentences. Do not duplicate Host capture ownership from the next
paragraph.

- [ ] **Step 4: Run focused architecture and documentation tests**

Run:

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_documentation_navigation.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit the guard and durable authority**

```powershell
git add -- tests/test_pre_release_architecture_guards.py docs/platform/frontend-protocol.md
git commit -m "docs: codify transactional bootstrap drain"
```

### Task 5: Run Delivery Gates And Close The Slice

**Files:**
- Modify: `docs/current-status.md`
- Modify: `docs/superpowers/README.md`
- Modify: `docs/archive/README.md`
- Create: `docs/archive/session-bootstrap-buffer-drain/README.md`
- Move: `docs/superpowers/specs/2026-08-16-session-bootstrap-buffer-drain-design.md`
- Move: `docs/superpowers/plans/2026-08-16-session-bootstrap-buffer-drain.md`

- [ ] **Step 1: Run the exact remote failure and regular/release partitions**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestCliSmokeGate::test_cli_smoke_crosses_staged_launcher_for_both_flavors
uv run python scripts/test-suite.py full
uv run python scripts/test-suite.py release
```

Expected: the exact node passes; regular and release partitions report zero
failures. Record the exact pass/deselect counts for the final handoff.

- [ ] **Step 2: Run lint and frontend gates from fresh commands**

Run:

```powershell
uv run --locked python scripts/lint.py
Push-Location src/embedagent/frontend/gui/webapp
npm test
npm run build
Pop-Location
git diff --exit-code -- src/embedagent/frontend/gui/static/assets/app.js
```

Expected: Ruff and Black pass, frontend tests/build pass, and rebuilding produces
no uncommitted static-asset change.

- [ ] **Step 3: Build, inspect, and isolate-smoke all six distributions**

Run only the mandatory distribution builder:

```powershell
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: exactly six wheels, checker `ok: true`, and all isolated smoke scenarios
pass. Do not substitute `uv build --all-packages`.

- [ ] **Step 4: Update current status only after the gates pass**

Update the frontend runtime bullet in `docs/current-status.md` to say that request,
install, activation dispatch, recovery, rollback, and ordered drain are one runtime
transaction, with shared reentrant-dispatch coverage. Replace the verification date
with `2026-08-16`. Do not add a completion diary or CI chronology.

- [ ] **Step 5: Archive the completed temporary slice**

Run:

```powershell
New-Item -ItemType Directory -Force docs/archive/session-bootstrap-buffer-drain | Out-Null
git mv docs/superpowers/specs/2026-08-16-session-bootstrap-buffer-drain-design.md docs/archive/session-bootstrap-buffer-drain/
git mv docs/superpowers/plans/2026-08-16-session-bootstrap-buffer-drain.md docs/archive/session-bootstrap-buffer-drain/
```

Create `docs/archive/session-bootstrap-buffer-drain/README.md` with:

```markdown
# Session Bootstrap Buffer Drain Archive

This package records the completed 2026-08-16 frontend runtime buffer-drain slice.
Durable behavior is owned by `docs/platform/frontend-protocol.md` and rationale by
`docs/adrs/0007-unify-frontend-ports-and-client-runtime-contract.md`.

- `2026-08-16-session-bootstrap-buffer-drain-design.md`
- `2026-08-16-session-bootstrap-buffer-drain.md`
```

Remove the `Session Bootstrap Buffer Drain` section from
`docs/superpowers/README.md` and add `session-bootstrap-buffer-drain/` to the
alphabetized package list in `docs/archive/README.md`.

- [ ] **Step 6: Re-run closure checks after documentation moves**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_documentation_navigation.py tests/test_pre_release_architecture_guards.py
uv run --locked python scripts/lint.py
git diff --check
git status --short --branch
```

Expected: documentation and architecture tests pass, lint passes, diff check is
clean, and status contains only the planned status/archive/index changes.

- [ ] **Step 7: Commit closure documentation**

```powershell
git add -- docs/current-status.md docs/superpowers/README.md docs/archive/README.md docs/archive/session-bootstrap-buffer-drain
git commit -m "docs: close bootstrap buffer drain"
```

- [ ] **Step 8: Verify final branch state without claiming Windows 7 acceptance**

Run:

```powershell
git status --short --branch
git log -5 --oneline --decorate
git diff --stat origin/main...HEAD
```

Expected: the feature branch is clean and contains the design, implementation,
durable authority, and closure commits. Report repository-side verification only;
hosted Windows and local bundle checks do not satisfy clean-machine Windows 7
acceptance.
