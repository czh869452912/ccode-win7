# Session Bootstrap Buffer Drain

> Status: `design-approved`
> Date: `2026-08-16`
> Owners: frontend runtime maintainers
> Governing decision: `docs/adrs/0007-unify-frontend-ports-and-client-runtime-contract.md`

## Problem

Remote CI run `31931877411` failed the Windows release partition at
`TestCliSmokeGate.test_cli_smoke_crosses_staged_launcher_for_both_flavors`.
The other six jobs passed, and the release partition ended with 157 passed tests
and one failure. The failure remained
`chat_permission_exit_4_protocol_error`, even after bootstrap-producing requests
were moved inside runtime-owned transactions.

The earlier change closed the request-to-install gap, but installation and
rollback still end synchronization before their buffered envelopes are replayed.
Both runtimes currently expose this order:

```text
install bootstrap cursor
  -> clear activating/recovering
  -> dispatch session_activated
  -> replay buffered envelopes through normal ingress
```

A live envelope can therefore enter normal ingress after synchronization is
cleared and before an older buffered envelope is replayed. The later envelope
appears to contain a sequence gap and starts recovery. Recovery installs through
the same clear-before-replay path, so a second valid interleaving is classified
as a repeated post-recovery gap and permanently fails the generation.

A deterministic probe reproduced the CI outcome without timing sleeps:

1. Interaction installation captured cursor 2 with buffered event 3.
2. The `session_activated` dispatch synchronously delivered event 4 before event
   3 was replayed, which started recovery.
3. Recovery captured cursor 4 and buffered event 5.
4. Recovery activation synchronously delivered event 6 before event 5 was
   replayed.
5. The runtime emitted `protocol_failed` with `session event sequence gap repeated
   after recovery` and stopped at cursor 4.

Host is not the source of the gap. `EventEmitter.capture` and `EventEmitter.emit`
already share the per-session encoder lock, so a captured Host cursor and emitted
sequence are serialized. The defect remains entirely in frontend queue-drain
ownership.

## Goals

- Keep bootstrap installation, recovery installation, and request rollback in a
  synchronization state until all applicable buffered envelopes are drained.
- Preserve the Host bootstrap cursor and canonical `SessionEventEnvelope` stream
  as the only ordering truth.
- Preserve strict contiguous sequence validation, one bounded recovery, and
  deterministic failure for a real repeated gap.
- Keep Python and JavaScript runtime behavior conformant.
- Replace timing stress with deterministic reentrant-dispatch contract coverage.

## Non-Goals

- Changing Host event encoding, capture locking, bootstrap DTOs, or port methods.
- Adding acknowledgements, retries, sleeps, sequence-gap tolerance, or CI reruns.
- Introducing a second event queue outside `SessionClientRuntime`.
- Changing CLI interaction, permission, or terminal-result policy.
- Treating hosted Windows CI as Windows 7 release acceptance.

## Considered Approaches

### Transaction-Gated Ordered Drain

Keep the current runtime-owned buffer, but retain `activating` or `recovering`
through activation dispatch and ordered replay. Incoming envelopes continue to
append to that buffer. The runtime leaves synchronization only when it observes an
empty applicable queue while holding its condition/transaction lock.

This is selected. It closes the race at the existing ownership boundary and does
not introduce another scheduler or truth source.

### Dedicated Runtime Event Pump

Put bootstrap operations, ingress, and action dispatch on a dedicated serial
executor. This can provide a stronger global execution model, but it changes the
Python thread contract and the browser scheduling model, expands shutdown and
error handling, and is disproportionate to this defect.

### Additional Recovery Or Gap Tolerance

Permit multiple recoveries or ignore a later envelope until missing sequences
arrive. This hides a client ordering defect, weakens fail-closed protocol behavior,
and makes a real missing event harder to detect. It is rejected.

## Selected Runtime Contract

Bootstrap installation has two separate phases owned by one generation:

```text
capture phase
  -> validate bootstrap
  -> install projection and cursor
  -> reduce cursor-covered buffered terminal evidence

drain phase
  -> dispatch session_activated
  -> accept the next contiguous buffered envelope
  -> dispatch its session_event action
  -> repeat while live ingress continues to buffer
  -> atomically leave synchronization when the queue is empty
```

While either phase is active, `on_session_event` only appends envelopes to the
generation buffer. It cannot advance the cursor, start recovery, or dispatch an
event independently. The drain path is the sole temporary consumer of that
buffer.

The drain processes envelopes in sequence order. Envelopes at or below the
installed cursor are not dispatched again; cursor-covered events present at
capture time still reduce terminal outcome as required by the existing contract.
Each envelope above the cursor advances the normal lifecycle and terminal
reducers exactly once and produces the same `session_event` action as normal live
ingress.

Action dispatch remains outside the runtime condition lock. Synchronization stays
active during that dispatch, so reentrant or concurrent ingress can only append to
the queue. After every action, the drain reacquires the lock and selects the next
contiguous envelope. When no applicable envelope remains, it clears the
synchronization flags, transaction baseline, and buffer atomically. An envelope
arriving after that atomic transition sees the already advanced cursor and enters
the normal live path.

## Recovery And Rollback

If the lowest buffered sequence above the cursor is not `cursor + 1`, the drain
uses the existing recovery policy. The first real gap changes the same generation
to recovering and requests one bootstrap. Recovery installation uses the identical
gated drain contract. A repeated gap after recovery still emits structured
`protocol_failed`; the fix does not add another attempt.

A request failure restores the committed baseline while retaining synchronization.
Only buffered envelopes for the restored session are eligible, and they are
drained from the restored cursor through the same ordered path before rollback is
complete. A superseded or closed generation still drops late work without changing
the newer state.

The install, recovery, and rollback paths share one private ordered-drain mechanism
rather than maintaining separate replay loops. This removes the duplicated
clear-before-replay behavior that caused the defect.

## Cross-Runtime Conformance

Python `SessionClientRuntime` and browser `SessionClientRuntime` retain their
existing public APIs. Their internal synchronization state and observable action
order must remain equivalent:

- one activation action for each successfully installed bootstrap;
- no duplicate action for cursor-covered envelopes;
- contiguous buffered actions dispatched in sequence order;
- events received during action dispatch appended and drained before readiness;
- one recovery for the first real gap and fail-closed behavior for a repeated gap;
- rollback drains only the committed session's applicable envelopes.

The shared JSON contract gains two reentrant dispatch scenarios. A normal install
case starts at cursor 2 with buffered event 3 and injects event 4 from the
interaction activation callback; it must drain to cursor 4 without recovery. A
recovery case first presents a real event 4 gap at cursor 2, captures recovery at
cursor 4 with event 5 buffered after capture, and injects event 6 from the recovery
activation callback; it must drain to cursor 6 after exactly one recovery. Both
language harnesses use runtime dispatch callbacks, so the tests deterministically
cover both windows without sleeps. Focused language tests may cover thread-specific
blocking and rollback coordination, but they must not define divergent ordering
semantics.

## Error Handling

- Invalid bootstrap data still fails the active generation immediately.
- A dispatch callback exception retains the existing dispatch contract; this slice
  does not add callback exception suppression.
- A true initial gap still performs one recovery.
- A true repeated gap still reports `protocol_error` and wakes terminal waiters.
- Close or supersession during dispatch/drain stops the old generation without
  clearing state owned by the new generation.

## Verification

The red/green loop starts with the deterministic install and recovery interleavings
described above. Current code performs an unnecessary recovery in the first case
and emits `protocol_failed` in the second. After implementation, both runtimes must
finish the first case at cursor 4 with no recovery, then finish the second at cursor
6 with one recovery, events 5 and 6 dispatched in order, and no protocol failure.

Repository verification includes:

```powershell
uv run python scripts/test-suite.py tdd tests/test_session_client_commands.py
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run python scripts/test-suite.py release
uv run --locked python scripts/lint.py
```

From `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
npm run build
```

The exact staged launcher regression and six-distribution build/check/smoke gates
also run. Generated GUI static assets are committed if the browser runtime changes
their content.

## Acceptance Criteria

- The deterministic install interleaving reaches cursor 4 without recovery in both
  runtimes.
- The deterministic recovery interleaving reaches cursor 6 after one recovery and
  without `protocol_failed` in both runtimes.
- Synchronization remains active through activation dispatch and buffered replay.
- Rollback uses the same ordered-drain boundary instead of a separate unlocked
  replay loop.
- Cursor-covered envelopes remain deduplicated while terminal evidence is retained.
- A true repeated gap remains fail-closed.
- Python and JavaScript pass the same reentrant-dispatch fixture.
- The original Windows release test, regular suite, release suite, architecture
  guards, lint, frontend tests/build, and distribution gates pass.
- Durable frontend protocol documentation is updated and this temporary slice is
  archived after all repository-side conditions close.
