# Session Bootstrap Transaction Convergence

> Status: `design-approved`
> Date: `2026-08-16`
> Owners: frontend runtime maintainers
> Governing decision: `docs/adrs/0007-unify-frontend-ports-and-client-runtime-contract.md`

## Problem

Remote CI run 153 failed the staged minimal CLI permission scenario with
`chat_permission_exit_4_protocol_error`. The same test and repeated local bundle
scenarios pass, so the failure is scheduling-dependent rather than a stable
packaging or permission-policy defect.

The Python and JavaScript session runtimes both have a bootstrap transaction gap.
Activation begins a new generation before requesting a bootstrap, but operations
that return a bootstrap currently request first and install later. During that
interval, live envelopes are still accepted by the old generation. Installing the
returned bootstrap then rewinds the cursor to its captured value and loses the
runtime's knowledge that those envelopes were already dispatched.

A deterministic probe demonstrated the defect:

1. An interaction response returned a bootstrap with cursor 3.
2. Event 4 arrived after Host captured that bootstrap and before the client installed it.
3. The old generation dispatched event 4.
4. The returned bootstrap installed cursor 3 into a new generation.
5. Event 5 appeared to contain a gap and caused an unnecessary recovery.

Host already captures the projection and cursor under the per-session event
publication boundary. The defect is therefore in client transaction ownership,
not Host event publication.

## Design Goals

- Make every bootstrap-producing operation atomic from the frontend runtime's
  observable perspective.
- Keep Python and JavaScript runtimes conformant through the same shared fixtures.
- Preserve one canonical `SessionEventEnvelope` stream and Host bootstrap cursor.
- Remove the Python terminal-identity workaround and the GUI's split
  request-then-install flow.
- Preserve Core, Host, protocol DTO, and distribution boundaries.
- Turn the CI race into deterministic contract coverage instead of relying on
  timing stress.

## Non-Goals

- Changing session truth, history persistence, or Host event sequencing.
- Adding an acknowledgement protocol, client/Host synchronization handshake, or
  another frontend runtime abstraction.
- Adding compatibility aliases for the current pre-release client API.
- Treating hosted CI as Windows 7 release evidence.

## Considered Approaches

### Runtime-Owned Bootstrap Transaction

The runtime begins a generation before invoking transport or port work, buffers
concurrent envelopes, validates the returned bootstrap, installs its cursor, and
replays the remaining continuous envelopes. This applies to both languages and
all bootstrap-producing operations.

This is the selected approach. It fixes the ownership error at the existing
frontend synchronization boundary without changing durable truth or wire DTOs.

### Mutation Acknowledgement Followed By Activation

Each mutation would return only an acknowledgement and the runtime would fetch a
new bootstrap separately. This makes sequencing explicit but changes the port and
HTTP contracts, adds round trips, and creates a larger migration surface than the
defect requires.

### Host/Client Installation Handshake

Host would hold or annotate events until the client acknowledged bootstrap
installation. This couples Host publication to transient client state and risks a
second synchronization truth. It conflicts with the current Host/frontend
boundary and is rejected.

## Runtime Transaction Model

Both runtime implementations use one internal transaction primitive with the same
observable phases:

```text
begin generation
  -> mark activating
  -> request bootstrap-producing operation
  -> buffer concurrent envelopes
  -> validate returned bootstrap
  -> install projection and cursor
  -> discard buffered sequence <= cursor
  -> replay continuous buffered envelopes
  -> ready or one bounded recovery
```

Beginning a transaction increments `generation`, records the most recent committed
runtime state as its rollback baseline, clears the current terminal outcome, resets
recovery state, and starts an activation buffer. The transaction token is the new
generation. A response may install only while its token is current and the runtime
is open.

If a newer transaction supersedes one already in flight, it inherits the earlier
transaction's committed rollback baseline and buffered envelopes. It never records
the superseded `activating` state as a rollback target. The context exists only for
the lifetime of the active transaction and is not a session projection or durable
truth source.

The active session is known before `activate`, `set mode`, `cancel`, and
`respond to interaction`; `create` and aliases such as `resume latest` may not know
the canonical session ID until the response arrives. While any transaction is
active, canonical envelopes are buffered without dispatch. Successful installation
keeps only envelopes matching the validated bootstrap session ID. Rollback keeps
only envelopes matching the committed baseline session. This filtering supports
both unknown targets and superseding activation without losing events needed by a
rollback.

Installation uses the bootstrap's `event_cursor` as the generation baseline.
Buffered envelopes are sorted, envelopes at or below that cursor are discarded,
and later envelopes are fed through the normal sequence path. Cursor-covered
envelopes are not dispatched again, but they still pass through the terminal
outcome reducer before removal. This is necessary because bootstrap projection
contains session state but does not replace the CLI/TUI terminal outcome channel.
The normal sequence path remains the only place that advances the cursor or
dispatches a live event.

## Operation Ownership

Python `SessionClientRuntime` routes `activate_session`, `create_session`,
`resume_session`, `set_session_mode`, `respond_to_interaction`, and
`cancel_session` through the transaction primitive. Fork continues to activate
the returned thread through the same primitive.

JavaScript `SessionClientRuntime` exposes corresponding high-level operations and
owns each transport request through bootstrap installation. Browser controllers
invoke those runtime operations; they no longer compose direct protocol mutations
with a later `installSessionBootstrap` call. The public after-the-fact installation
entry point is removed because it cannot close the race by construction.

Transport-specific user feedback remains in browser controllers. The runtime owns
ordering and projection synchronization, while controllers continue to own notices,
logs, and view actions.

## Terminal Outcome Semantics

A new bootstrap transaction clears the previous terminal outcome before the
request. Terminal state is reduced from ordered canonical event evidence:
interaction-request events set `blocked`, interaction-finish events clear that
blocked outcome, and session finish/error events set their structured terminal
outcome. Both runtimes use this reducer for normal live events and for buffered
events already covered by the returned cursor.

Cursor-covered buffered events affect terminal state but are not dispatched as
duplicate `session_event` actions. Events after the bootstrap cursor go through the
normal sequence path, which both dispatches them and applies the same reducer. This
removes the need to compare `RuntimeAction` object identities across the request
boundary without losing a finish event represented by the returned bootstrap.

If a request fails and the transaction rolls back, the prior terminal outcome is
restored before buffered events for the prior active session are replayed. A
replayed terminal event may then replace it through normal event semantics.

The `_RESET_TERMINAL` sentinel, `discard_terminal` parameter, and identity-based
retention branch are deleted.

## Failure And Concurrency Semantics

| Condition | Required behavior |
|---|---|
| Request rejects before a valid bootstrap is returned | Restore prior synchronization state, replay applicable buffered events from the prior cursor, and propagate the request error to the caller. |
| Response contains an invalid bootstrap | Fail the current generation with structured `protocol_failed`; do not restore a projection that may now be stale. |
| A newer transaction supersedes the request | Ignore the stale completion; it must not install, fail, or overwrite the newer generation. |
| Runtime closes during the request | Ignore the completion and retain `closed`. |
| Buffered events are at or below the bootstrap cursor | Reduce terminal state, then discard them without duplicate dispatch. |
| Buffered events are continuous after the bootstrap cursor | Replay them without recovery. |
| A real sequence gap remains after installation | Perform at most one recovery for that generation. A repeated gap fails deterministically. |

Rollback retains the incremented generation so completions from abandoned
operations remain stale. It restores the committed session, cursor, lifecycle,
recovery flags, and terminal outcome, then replays only buffered events belonging
to that session. A superseding transaction inherits that same committed baseline,
so its failure cannot restore an orphaned `activating` state. This preserves
existing browser handling of expected request errors, including interaction
conflicts, without teaching the transport-neutral runtime about HTTP status codes.

## Shared Contract Coverage

`tests/fixtures/session_client_runtime/contract.json` is extended with public
bootstrap-producing operations and request-time event injection. Both language
harnesses consume the same cases and assert observable actions plus final runtime
state.

Required shared cases are:

- bootstrap cursor 3, event 4 during the request, then event 5 after installation;
  final cursor 5 and zero recovery actions;
- an event already represented by the returned cursor is discarded exactly once;
- a terminal event during interaction response that is covered by the returned
  cursor becomes the new terminal state without duplicate dispatch or identity
  retention;
- request rejection restores the previous session and replays its buffered events;
- a failed superseding request restores the last committed state rather than an
  abandoned `activating` state;
- malformed bootstrap fails the current generation;
- a stale completion cannot overwrite a newer generation;
- unknown-session create retains only events matching the returned session;
- close during a request prevents later installation.

Python-specific tests continue to cover blocking `wait_for_terminal`. Browser
controller tests verify that create, mode, cancel, and interaction response use
runtime-owned transactions while retaining existing UI error handling. Architecture
guards reject reintroduction of direct controller-side bootstrap installation.

The staged CLI permission smoke remains a release-level regression test, but it is
not the primary proof of the race fix.

## Documentation And Delivery

Implementation updates `docs/platform/frontend-protocol.md` to state explicitly
that every bootstrap-producing operation begins its generation before making the
request. `docs/current-status.md` is replaced in place when verification completes.
No new ADR is needed because this work enforces ADR-0007 rather than changing its
decision.

Verification must include:

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run --locked python scripts/lint.py
```

From `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
npm run build
```

Because the observed failure crosses the staged launcher, verification also runs
the six-wheel build, check, and isolated smoke commands plus the exact minimal CLI
permission scenario. Generated GUI assets are committed when webapp source changes.

## Acceptance Criteria

- Python and JavaScript pass the same returned-bootstrap concurrency fixtures.
- No bootstrap-producing public path requests first and starts activation later.
- The deterministic cursor 3/4/5 scenario performs no recovery and ends at cursor 5.
- Python and JavaScript derive terminal state from ordered event evidence, including
  buffered events covered by the returned cursor.
- Python no longer contains terminal identity comparison or its sentinel.
- Browser controllers no longer call protocol mutation plus after-the-fact install.
- Existing interaction conflict behavior remains user-visible and recoverable.
- Architecture, full Python, lint, webapp test/build, distribution, and staged CLI
  gates pass.
- Durable authorities are synchronized and this temporary spec and its execution
  plan are archived when all repository-side acceptance conditions close.
