# Frontend Event Publication Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make frontend event state observable only after its runtime action is delivered, while removing bootstrap-only synchronization debt and silent Host sink loss.

**Architecture:** Python and JavaScript client runtimes each use one synchronization phase and one ordered event queue. A live event is staged, dispatched outside the runtime lock, and only then commits cursor, lifecycle, and terminal outcome; ingress during dispatch is queued. Host keeps the only sequence/capture cursor and propagates unexpected sink failure instead of acknowledging it silently.

**Tech Stack:** Python 3.8, `threading.Condition`, pytest, stdlib protocol DTOs, JavaScript ES modules, Node test runner, GitHub Actions Windows release partition.

---

## File Structure

- Modify `tests/test_session_client_commands.py`: deterministic threaded publication-order RED test and dispatch-failure coverage.
- Modify `src/embedagent/frontend/runtime/session_client_runtime.py`: Python synchronization phase, event queue, staged event transition, delivery commit, and structured dispatch failure.
- Modify `tests/test_cli_chat.py`: real runtime/CLI permission scheduling regression.
- Modify `tests/fixtures/session_client_runtime/contract.json`: cross-language publication-time observation case.
- Modify `tests/test_session_client_runtime_contract.py`: Python fixture observation support and retired-shape assertions.
- Modify `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs`: JavaScript fixture observation support.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js`: JavaScript staged publication and synchronization cleanup.
- Modify `packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py`: propagate bound sink exceptions.
- Modify `tests/test_services.py` and `tests/test_characterization.py`: Host sink failure contract.
- Modify `tests/test_pre_release_architecture_guards.py`: enforce the converged runtime shape and reject retired fields.
- Modify `docs/platform/frontend-protocol.md`, `docs/platform/protocol.md`, and `docs/platform/frontend-tui.md`: durable publication contract.
- Modify `docs/current-status.md` and `docs/implementation-roadmap.md`: replace current blocker state after verification.
- Create `docs/archive/frontend-event-publication-convergence/README.md` and move this spec/plan there at closure.

### Task 1: Prove The Python Publication Boundary

**Files:**
- Modify: `tests/test_session_client_commands.py`

- [ ] **Step 1: Write the failing threaded test**

Add a dispatch callback that blocks only for an `approval.requested` `session_event`, starts
`runtime.on_session_event(...)` on a worker, and observes the runtime before releasing dispatch:

```python
def test_terminal_outcome_is_published_only_after_event_action_delivery():
    dispatch_entered = threading.Event()
    release_dispatch = threading.Event()
    delivered = []

    def dispatch(action):
        if action.kind == "session_event":
            dispatch_entered.set()
            assert release_dispatch.wait(1.0)
        delivered.append(action.kind)

    runtime, _port = _runtime_with_dispatch(dispatch)
    worker = threading.Thread(
        target=runtime.on_session_event,
        args=(_event("approval.requested", APPROVAL_PAYLOAD),),
    )
    worker.start()
    assert dispatch_entered.wait(1.0)

    during = runtime.wait_for_terminal(timeout_s=0).to_dict()
    assert during["status"] == "timeout"
    assert runtime.event_cursor == 1
    assert runtime.lifecycle == "ready"
    assert delivered == ["session_activated"]

    release_dispatch.set()
    worker.join(1.0)
    assert not worker.is_alive()
    assert runtime.wait_for_terminal(timeout_s=0).to_dict()["status"] == "blocked"
```

- [ ] **Step 2: Run the exact test and verify RED**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py::test_terminal_outcome_is_published_only_after_event_action_delivery
```

Expected: FAIL because current code returns `blocked`, cursor 2, and
`waiting_interaction` before dispatch is released.

- [ ] **Step 3: Commit the RED test**

```powershell
git add tests/test_session_client_commands.py
git commit -m "test: expose event publication ordering race"
```

### Task 2: Converge The Python Runtime Publication State Machine

**Files:**
- Modify: `src/embedagent/frontend/runtime/session_client_runtime.py`
- Modify: `tests/test_session_client_commands.py`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Replace private synchronization shapes**

Define private phase constants and replace `_activating`, `_recovering`, and
`_buffered_events` with:

```python
_SYNC_IDLE = "idle"
_SYNC_BOOTSTRAP = "bootstrap"
_SYNC_RECOVERY = "recovery"
_SYNC_PUBLICATION = "publication"

self._sync_phase = _SYNC_IDLE
self._event_queue = []  # type: List[SessionEventEnvelope]
```

All bootstrap begin/install/rollback/close paths must set or clear the phase as one state,
and architecture guards must reject the retired field names.

- [ ] **Step 2: Stage rather than immediately commit a contiguous event**

Replace `_accept_contiguous_event_locked` with a pure candidate builder returning an
immutable internal transition containing the generation, envelope, next lifecycle, next
terminal outcome, and `RuntimeAction`. It must not update public cursor, lifecycle, or
terminal state.

- [ ] **Step 3: Make the queue drain the sole live-event publisher**

`on_session_event` validates/filter events, appends applicable ingress, claims
`_SYNC_PUBLICATION` only from idle, then invokes the drain outside the condition. The drain:

```text
select contiguous candidate under condition
dispatch action outside condition
commit candidate under condition if generation is current
notify waiters
repeat
```

Ingress during bootstrap, recovery, or publication appends and returns. Gap recovery and
rollback re-enter the same drain. Do not add sleeps, retries, or shell callbacks.

- [ ] **Step 4: Make runtime dispatch failure terminal and bounded**

Catch `OSError`, `RuntimeError`, `TypeError`, and `ValueError` from a session action callback.
Do not commit the candidate envelope. Fail the current generation with a generic
`FailureRecord(code="protocol_error", source="client_runtime")`, clear the queue, release
waiters, and avoid recursively redispatching through the callback that failed.

- [ ] **Step 5: Run focused Python tests and verify GREEN**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py
uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py
uv run python scripts/test-suite.py tdd tests/test_cli_run.py
```

Expected: all selected tests pass, including the threaded RED test.

- [ ] **Step 6: Commit the Python runtime convergence**

```powershell
git add src/embedagent/frontend/runtime/session_client_runtime.py tests/test_session_client_commands.py tests/test_pre_release_architecture_guards.py
git commit -m "fix: commit frontend events after action delivery"
```

### Task 3: Prove The Real CLI Permission Flow

**Files:**
- Modify: `tests/test_cli_chat.py`

- [ ] **Step 1: Add a real-runtime gated CLI test**

Use `SessionClientRuntime`, a focused in-process `FrontendSessionPort` fixture, and real
`CliChat`. Gate the `approval.requested` action in a worker while scripted input contains
`permission smoke\n1\n/exit\n`. Assert that before releasing dispatch the port has only one
user submission. After release, assert exit code 0, the approval prompt is rendered, `1` is
sent through `respond_to_interaction`, and it is never submitted as a second user turn.

- [ ] **Step 2: Run the exact CLI test**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_cli_chat.py::test_chat_waits_for_interaction_action_delivery_before_reading_choice
```

Expected: PASS against the converged runtime. Reverting Task 2 must make this test reproduce
exit code 4 or a second submission.

- [ ] **Step 3: Run all CLI runtime tests**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_cli_chat.py
uv run python scripts/test-suite.py tdd tests/test_cli_run.py
uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py
```

Expected: all pass.

- [ ] **Step 4: Commit the CLI regression**

```powershell
git add tests/test_cli_chat.py
git commit -m "test: cover cli interaction publication ordering"
```

### Task 4: Align The Shared Contract And JavaScript Runtime

**Files:**
- Modify: `tests/fixtures/session_client_runtime/contract.json`
- Modify: `tests/test_session_client_runtime_contract.py`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js`
- Modify: `src/embedagent/frontend/gui/static/`

- [ ] **Step 1: Add a cross-language publication observation fixture**

Add a case that starts at cursor 1, dispatches `approval_requested`, observes during that
action that cursor/lifecycle/terminal still equal the prior committed state, injects the next
contiguous event reentrantly, and expects ordered actions plus the final committed state.

- [ ] **Step 2: Extend both harnesses and verify RED in JavaScript**

Python dispatch observations use `event_cursor`, `lifecycle`, and non-blocking terminal status.
JavaScript observations use `cursor`, `lifecycle`, and `terminalOutcome`. Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_runtime_contract.py
Set-Location src/embedagent/frontend/gui/webapp
npm test
```

Expected before JavaScript implementation: Python passes after Task 2; JavaScript fails because
cursor/lifecycle/terminal are mutated before `dispatch` returns.

- [ ] **Step 3: Implement the JavaScript publication transaction**

Replace `activating`, `recovering`, and `activationBuffer` with `syncPhase` and `eventQueue`.
Make `acceptSessionEvent` enqueue and await the sole drain. Derive a candidate transition,
dispatch its frozen action, then commit state. Reentrant async acceptance queues behind the
current publication. Bootstrap/recovery/rollback reuse the same queue and drain.

- [ ] **Step 4: Run frontend tests and build static assets**

Run from `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
npm run build
```

Expected: all frontend tests pass and generated files under
`src/embedagent/frontend/gui/static/` are updated.

- [ ] **Step 5: Commit cross-runtime convergence**

```powershell
git add tests/fixtures/session_client_runtime/contract.json tests/test_session_client_runtime_contract.py src/embedagent/frontend/gui/webapp/test/session-client-runtime-contract.test.mjs src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js src/embedagent/frontend/gui/static
git commit -m "refactor: converge frontend event publication runtimes"
```

### Task 5: Remove Silent Host Sink Loss

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py`
- Modify: `tests/test_services.py`
- Modify: `tests/test_characterization.py`

- [ ] **Step 1: Change the existing sink-exception test to require propagation**

Replace the isolation assertion with:

```python
with self.assertRaisesRegex(RuntimeError, "boom"):
    emitter.emit("test_event", "sess1", {"key": "value"})
```

Add an assertion that `current_cursor("sess1")` remains semantically unusable as a successful
delivery signal by requiring the exception to reach the caller; no retry or alternate cursor is
introduced.

- [ ] **Step 2: Run the focused Host tests and verify RED**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_services.py
uv run python scripts/test-suite.py tdd tests/test_characterization.py
```

Expected: the changed tests fail because `EventEmitter.emit` currently logs and suppresses the
sink exception.

- [ ] **Step 3: Remove exception suppression from `EventEmitter.emit`**

Keep the per-session encoder scope and direct sink call, but delete the try/except and logger
dependency. Runtime-backed sinks already turn renderer dispatch failures into structured runtime
failure in Task 2.

- [ ] **Step 4: Re-run Host tests and commit**

Run the two focused files again; expected all pass. Then:

```powershell
git add packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py tests/test_services.py tests/test_characterization.py
git commit -m "refactor: propagate frontend sink failures"
```

### Task 6: Durable Documentation, Full Verification, And Closure

**Files:**
- Modify: `docs/platform/frontend-protocol.md`
- Modify: `docs/platform/protocol.md`
- Modify: `docs/platform/frontend-tui.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/superpowers/README.md`
- Move: `docs/superpowers/specs/2026-08-16-frontend-event-publication-convergence-design.md`
- Move: `docs/superpowers/plans/2026-08-16-frontend-event-publication-convergence.md`
- Create: `docs/archive/frontend-event-publication-convergence/README.md`

- [ ] **Step 1: Run architecture, regular, release, and lint gates**

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run python scripts/test-suite.py release
uv run --locked python scripts/lint.py
```

Expected: every command exits 0.

- [ ] **Step 2: Run frontend gates**

From `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
npm run build
```

Expected: both commands exit 0 and committed static assets match the source build.

- [ ] **Step 3: Run staged launcher and distribution gates**

```powershell
uv run pytest tests/test_packaging_control_plane.py::TestCliSmokeGate::test_cli_smoke_crosses_staged_launcher_for_both_flavors -v
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: the two-flavor staged CLI smoke and all six-wheel gates pass.

- [ ] **Step 4: Synchronize durable truth and archive the slice**

Document the delivered-before-committed event rule, one synchronization phase/queue, and sink
failure propagation in the owning platform documents. Replace current status/roadmap text rather
than appending a diary. Move the approved spec and this plan to
`docs/archive/frontend-event-publication-convergence/`, create its index, and remove the active
slice entry.

- [ ] **Step 5: Run documentation and repository hygiene checks**

```powershell
uv run --locked python scripts/lint.py
git diff --check
git status --short
```

Expected: lint and diff checks pass; status contains only intended closure changes before commit.

- [ ] **Step 6: Commit closure**

```powershell
git add docs src/embedagent/frontend/gui/static
git commit -m "docs: close frontend event publication convergence"
```

