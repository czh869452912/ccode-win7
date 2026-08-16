# Frontend Event Publication Convergence Design

> Status: `design-approved`
> Date: `2026-08-16`
> Owners: frontend runtime and Host protocol maintainers
> Governing decision: `docs/adrs/0007-unify-frontend-ports-and-client-runtime-contract.md`

## Problem

The staged Windows CLI permission smoke can observe a blocked terminal outcome before the
corresponding `approval.requested` runtime action reaches the CLI. The CLI then consumes the
already-buffered choice as a new user message and eventually exits with `protocol_error`.

The ordering defect is in the client runtime publication boundary. Python currently reduces a
canonical event, stores its terminal outcome, and wakes condition waiters before dispatching the
event action outside the condition lock. Event dispatch is therefore presentation work that
happens after state is already externally observable instead of being part of the same commit.

A deterministic threaded probe observed `blocked` while the event action was still undelivered.
A CLI probe then consumed `permission smoke` and `1` as two user turns, never rendered the
permission prompt, and reproduced exit code 4 with `protocol_error`.

The existing tests do not protect this boundary. The CLI fake dispatches an interaction action
before making its terminal result visible, which is the desired order rather than the production
order. Shared runtime fixtures cover reentrant bootstrap installation but do not observe runtime
state while a normal live action is being dispatched.

## Goals

- Make runtime action delivery part of the client event commit rather than a callback after it.
- Publish cursor, lifecycle, and terminal outcome together only after successful action delivery.
- Serialize concurrent and reentrant live ingress through one ordered event queue.
- Use the same observable publication contract in Python and JavaScript runtimes.
- Make dispatch failure explicit and terminal instead of allowing silent cursor advancement.
- Delete bootstrap-specific synchronization debt that no longer describes the general boundary.
- Preserve one Host sequence, one bootstrap cursor, and one client reducer without adding an
  acknowledgement DTO or parallel session truth.

## Non-Goals

- No compatibility layer for the current private runtime fields or ordering.
- No retry, delay, polling, or input-side workaround in CLI or TUI.
- No second Host/client sequence, durable delivery ledger, or transport handshake.
- No change to Core session truth, transcript semantics, or permission policy.
- No weakening of gap recovery, offline delivery, Python 3.8, or Windows 7 requirements.

## Considered Approaches

### Shell-Side Coordination

CLI could wait briefly for `_active_interaction` after receiving `blocked`. This would preserve
two independently visible truths, duplicate synchronization in each shell, and leave TUI and
future clients exposed. It is rejected.

### Dispatch While Holding The Runtime Condition

The runtime could invoke renderer callbacks before releasing its condition lock. This orders the
current CLI path but allows renderer reentrancy to mutate the runtime inside a partially applied
transition and can deadlock non-reentrant consumers. It is rejected.

### Runtime-Owned Publication Transaction

The runtime stages the next event transition, dispatches its immutable `RuntimeAction` outside the
condition lock while ingress remains queued, then commits cursor, lifecycle, and terminal outcome
under the condition and wakes waiters. This is selected because it creates one observable commit
without putting arbitrary shell code under the runtime lock.

## Selected Runtime Contract

Both client runtimes use one synchronization phase and one event queue. The phase is one of idle,
bootstrap, recovery, or publication; separate `activating`, `recovering`, and dispatch-window
booleans are not retained.

Normal event publication is:

```text
enqueue canonical envelope
  -> select the next contiguous envelope
  -> derive candidate cursor/lifecycle/terminal state without publishing it
  -> dispatch immutable session_event action outside the runtime lock
  -> commit the candidate state under the runtime lock
  -> notify terminal waiters
  -> repeat until the queue is empty
  -> return to idle atomically
```

While any action is being delivered, concurrent or reentrant ingress only appends to the queue.
The drain is the sole consumer, so a later event cannot overtake the action for the event that
made it contiguous. Public state remains at the last delivered event until dispatch returns.

Bootstrap, recovery, and rollback reuse the same queue. A valid bootstrap stages its cursor,
projection-derived lifecycle, and cursor-covered terminal evidence; `session_activated` is
delivered before that terminal evidence becomes observable. Events above the bootstrap cursor are
then published by the same ordered drain. A request rollback restores the previously committed
baseline and drains only applicable events for that session.

The first real gap still performs one recovery. A repeated gap still fails the generation. No
additional tolerance or retry is introduced.

## Dispatch Failure

Shell dispatch is an executable part of publication, not logging. If a runtime action callback
raises, the active generation becomes failed with a credential-free `protocol_error` sourced from
`client_runtime`; the candidate cursor and terminal outcome are not committed as successfully
delivered. Waiters are released with that structured failure. A best-effort `protocol_failed`
action may be delivered only when it is not the action path that just failed.

`EventEmitter` no longer logs and suppresses an in-process sink exception after advancing the Host
sequence. Runtime-backed sinks contain renderer failures as structured runtime failure, while an
unexpected generic sink failure propagates to its emitting operation. This removes the state in
which Host capture can cover an event that the bound sink silently rejected.

## Cross-Runtime Conformance

Python and JavaScript retain transport-specific implementations but share these observations:

- during `session_event` dispatch, public cursor, lifecycle, and terminal outcome still describe
  the preceding delivered event;
- a reentrant next envelope is queued and delivered only after the current action commits;
- interaction request action delivery precedes visibility of its `blocked` outcome;
- activation action delivery precedes visibility of cursor-covered terminal evidence;
- dispatch failure cannot be followed by normal delivery in the same generation.

The JavaScript event loop does not have a condition waiter, but synchronous dispatch reentrancy can
observe the same partial state. It therefore uses the same staged transition and queue semantics
rather than relying on single-thread scheduling.

## Deletions And Ownership Cleanup

- Replace Python `_activating`, `_recovering`, and `_buffered_events` with one synchronization
  phase and one general event queue.
- Replace JavaScript `activating`, `recovering`, and `activationBuffer` with the equivalent single
  phase and queue.
- Remove direct live-event mutation helpers whose names imply that reduction is committed before
  action delivery.
- Remove architecture guards and fixtures that assert the retired private shapes.
- Keep CLI and TUI as `RuntimeAction` consumers; they do not gain waits, locks, retries, or local
  interaction truth.
- Keep Host as the sole sequence and capture owner; no delivery cursor is added to protocol DTOs.

## Verification Design

The first RED test uses the real Python `SessionClientRuntime`. A dispatch callback blocks on a
thread barrier while another thread calls `wait_for_terminal(timeout_s=0)`. The required result
during dispatch is `timeout`, the previous cursor/lifecycle, and no published terminal outcome.
Current code returns `blocked`, proving the test catches the defect.

A real `CliChat` plus `SessionClientRuntime` test gates `approval.requested` dispatch and supplies
`permission smoke`, `1`, and `/exit`. The choice must not be submitted as a second user message,
the prompt must render, and the response must use `respond_to_interaction`.

The shared JSON contract adds publication-time observations and reentrant normal-event delivery.
Both language harnesses assert the same pre-commit state and final action order. Host tests assert
that sink exceptions propagate rather than being logged and discarded.

Repository verification includes architecture guards, the full Python partition, release
partition, lint, frontend tests/build, the exact staged two-flavor CLI smoke, and six-wheel
build/check/smoke. No hosted CI result substitutes for Windows 7 acceptance evidence.

## Acceptance Criteria

- A waiter cannot observe `blocked`, completed, or failed terminal state before its action is
  delivered.
- The staged permission choice cannot be interpreted as a new user turn under the gated schedule.
- Normal, bootstrap, recovery, and rollback paths use one event queue and one publication drain.
- Python and JavaScript expose the same state during action dispatch and the same final order.
- Runtime dispatch failure produces one structured terminal failure without committing the
  candidate event.
- Host no longer silently acknowledges a sink exception through its capture cursor.
- Retired private flags, bootstrap-only buffer names, guards, and tests are deleted rather than
  aliased.
- Durable protocol documentation is updated and this slice is archived after all repository-side
  gates pass.
