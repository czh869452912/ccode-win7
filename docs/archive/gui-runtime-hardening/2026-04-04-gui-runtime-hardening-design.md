# GUI Runtime Hardening For Replay, Restore, And Projection Consistency

> Date: 2026-04-04
> Status: Approved design baseline
> Scope: Follow-on hardening slice for the GUI active-session runtime after the first event-sourced rollout

## 1. Goal

EmbedAgent GUI will move from "first-generation event-sourced runtime" to a hardened active-session runtime with explicit replay, degradation, and projection contracts.

The target outcome is:

- the GUI timeline event log becomes replayable and degradable by contract rather than by best effort
- reconnect and `after_seq` replay become explicit state transitions instead of optimistic retries
- pending interactions are restored only when their identity is trustworthy; otherwise they expire explicitly
- HTTP and WebSocket boundaries return typed failure modes instead of leaking raw exceptions or silent drift
- the front-end projector becomes the full active-session interpreter instead of sharing responsibility with ad hoc reducer logic

This direction is chosen because the post-merge review showed that the first event-sourced slice fixed important issues, but left the most dangerous failure chain unresolved:

- timeline truncation
- seq-gap replay
- damaged-line scanning
- restore identity drift
- partial projector ownership

## 2. Confirmed Problem Statement

The follow-up audit input is documented in [`docs/issues/gui-timeline-issues-post-review-build-verified.md`](../../issues/gui-timeline-issues-post-review-build-verified.md). After code inspection against the current `main`, the still-real problems collapse into three root-cause clusters.

### 2.1 Timeline Persistence / Replay / Restore Is Not Contractual

The current GUI event log still has implicit semantics:

- `session_timeline.py` trims by dropping the head of the file
- write-path failures such as `os.fsync` / disk-full are not yet part of the contract
- `_scan_events()` stops at the first malformed line and discards all following valid events
- `load_events_after()` is built on a truncated tail window and cannot distinguish "replay possible" from "window lost"
- `resume_session()` still fabricates fallback interaction IDs such as `perm-resume` / `ask-resume`
- transcript/timeline restore failures can still surface as brittle or misleading pending state
- missing transcript/timeline sources can still abort resume instead of degrading explicitly

This creates the most dangerous live failure chain:

1. old seq values fall out of the retained window
2. reconnect asks for `after_seq`
3. returned events skip a seq range
4. the front end flags `needsResync`
5. replay repeats or collapses into degraded behavior without a formal contract

### 2.2 HTTP / WebSocket Failure Boundaries Are Still Incomplete

The current runtime still leaks or hides failures:

- `server.py` only catches `WebSocketDisconnect` in the websocket endpoint
- `ValueError` from adapter/session lookup still escapes many HTTP endpoints as 500
- `DispatchResult.reason` exists, but dispatch failures are not yet promoted into a transport fault model
- `fetchJson()` is still a thin helper, and `loadSession()` still lets non-critical requests poison the whole bootstrap

This means the runtime still does not cleanly distinguish:

- session missing
- interaction gone
- replay unavailable
- transport degraded
- malformed payload

### 2.3 The Front-End Projector Is Still Only Partial

The current projector improved interaction handling, but it is not yet the only interpreter of active-session state:

- command result turn anchoring can still fall back to ambiguous heuristics
- `groupByTurn()` still renders non-step detached items before step groups
- context/system card placement still depends on legacy grouping behavior
- `CodeBlock` handling and copy-state timing are still owned by component-local logic without stronger projection boundaries
- session switch debug log state is still managed outside the active-session runtime model

The result is a mixed architecture:

- event log + projector own part of the truth
- reducer patching and legacy grouping still own another part

That hybrid state is the main reason the review still reports substantial P0/P1 problems.

## 3. Explicit Decisions For This Design

The following decisions were confirmed during brainstorming and are part of the design contract:

1. this slice is allowed to change timeline persistence and replay semantics, not just front-end UI
2. the solution must remain structural and contract-driven, not a bundle of local patches
3. the first event-sourced rollout is treated as a foundation, not a finished target architecture
4. old GUI timeline projection data still does not require compatibility preservation

## 4. Design Principles

The implementation must preserve these rules:

- Windows 7 compatibility remains mandatory
- Python 3.8 compatibility remains mandatory
- Agent Core remains the product truth source
- GUI runtime may keep a dedicated event log, but its replay guarantees must be explicit
- replay failure must be typed and visible, never inferred from missing rows
- write-path failure must be typed and visible, never silently swallowed
- restore must never fabricate an actionable interaction identity
- restored interaction validity includes both identity and freshness, not ID presence alone
- the front-end projector must become the only interpreter of active-session runtime state
- typed degradation is preferred over optimistic hidden failure

## 5. Scope Boundary

### 5.1 In Scope

- `session_timeline.py` retention, scan, replay, and integrity semantics
- GUI replay and bootstrap HTTP contracts
- websocket error cleanup and transport fault surfacing
- interaction restore identity rules
- projector ownership of timeline/runtime/interaction state
- active-session UI ordering and projection fixes that naturally fall out of the runtime redesign

### 5.2 Out Of Scope

- a full visual redesign of the GUI shell
- a complete rewrite of transcript persistence across the entire product
- browser automation or external online sync
- broad CSS-only cleanup unrelated to runtime integrity
- changing the core product truth away from transcript/session state

## 6. Target Timeline Persistence Contract

### 6.1 Timeline Event Log Role

The GUI timeline file is redefined as:

- a GUI-specific event log
- windowed, not permanent truth
- replay-capable only when its own integrity contract says so

It is not:

- a lossy cache with invisible truncation side effects
- a second transcript truth source
- a file that the front end must interpret heuristically

### 6.2 Window Metadata Is First-Class

The timeline store must explicitly expose:

- `first_seq`
- `last_seq`
- `truncated_before_seq`
- `integrity_state`

This metadata may live in a companion file or be derived and returned with replay responses, but it must become part of the contract.

The front end must be able to answer:

- is the requested `after_seq` still in the retained window?
- did truncation happen before the requested seq?
- is the log continuous enough for replay?

### 6.3 Head Truncation Must Be Detectable

If the store keeps only the last `N` events, truncation is allowed only when the replay API can explicitly say:

- the missing prefix is gone
- incremental replay is no longer possible
- the client must perform a full reload

Silent loss of earlier seq values is not acceptable.

### 6.4 Write-Path Failure Must Degrade Explicitly

The timeline store must treat write-path failures as contract-level state, not incidental exceptions.

Examples include:

- `OSError` from `handle.write(...)`
- `OSError` from `handle.flush()`
- `OSError` from `os.fsync(...)`
- disk-full and permission problems

Required behavior:

- capture and log the failure
- mark timeline integrity or runtime replay capability as degraded
- avoid silently pretending the event was durably recorded

The system may drop the event if durable write is impossible, but it must not hide that fact.

### 6.5 Mid-File Damage Must Not Discard The Rest Of The Session

`_scan_events()` must no longer treat one malformed line as "stop reading the rest forever".

The new behavior must be:

- skip malformed lines
- retain later valid events when possible
- surface integrity degradation
- prevent "continuous replay" claims when continuity is no longer provable

The key principle is:

- preserve salvageable data
- admit degraded integrity
- never pretend continuity that does not exist

### 6.6 Replay Is A Typed Outcome

`load_events_after(after_seq)` must not merely return an array. It must return one of:

1. `replay`
   - the requested seq is within the retained continuous window
   - returned events may be appended incrementally

2. `reload_required`
   - the requested seq is older than the retained window
   - the client must perform full bootstrap instead of replay

3. `degraded`
   - the store has integrity damage or a gap that prevents trusted replay
   - the client must enter degraded recovery and reload conservatively

### 6.7 Restore Identity And Freshness Rules

Pending interactions are restored only when the original `interaction_id` is present and trusted, and when the interaction is still fresh enough to be actionable.

If `interaction_id` is missing or the interaction is stale:

- the pending interaction must not be restored as actionable state
- restore should emit or surface explicit expiration/degradation
- fallback IDs such as `perm-resume` and `ask-resume` are removed

The system must prefer "expired and visible" over "fake but clickable".

The design intentionally treats interaction freshness as part of trust, because the back-end waiter may already have timed out even if an old ID still exists in persisted state.

### 6.8 Missing Transcript / Timeline Source Recovery

If transcript or timeline inputs required for GUI resume/bootstrap are missing or unreadable, the system must not fail with a raw exception.

Allowed degraded outcomes:

- summary-assisted degraded bootstrap
- empty replay window with explicit `transcript_missing` or `timeline_missing`
- session snapshot that clearly marks restore/replay as degraded

Disallowed outcome:

- a hard failure that aborts GUI resume while hiding the reason from the front end

## 7. Replay / Bootstrap API Contract

### 7.1 WebSocket Responsibility

WebSocket is the real-time incremental channel only.

It may:

- push `session_event`
- push lightweight state changes

It may not:

- act as the historical replay source
- hide errors by dropping connection state silently

### 7.2 Replay Endpoint

`GET /api/sessions/{session_id}/events?after_seq=N` must return a structured replay result:

```json
{
  "session_id": "sess_xxx",
  "status": "replay",
  "first_seq": 120,
  "last_seq": 168,
  "reason": "",
  "events": []
}
```

`status` values:

- `replay`
- `reload_required`
- `degraded`

### 7.3 Bootstrap Snapshot Must Advertise Replay Capability

`GET /api/sessions/{session_id}` must expose GUI runtime metadata such as:

- `timeline_replay_status`
- `timeline_first_seq`
- `timeline_last_seq`
- `timeline_integrity`
- `pending_interaction_valid`

This lets the front end enter the correct initial runtime mode without guessing.

### 7.4 Interaction Response Endpoint Must Return Typed Errors

`POST /api/sessions/{session_id}/interactions/{interaction_id}/respond` must distinguish:

- `404 session_not_found`
- `404 interaction_not_found`
- `409 interaction_conflict`
- `410 interaction_expired`
- `422 invalid_interaction_payload`

The front end must not have to infer "expired" from a generic 500 or free-form error string.

### 7.5 Reconnect Backoff State Must Be Bounded

Reconnect state is part of transport health and must remain bounded.

Required behavior:

- exponential backoff may be used
- retry counters must have a hard cap
- delay must remain clamped

The runtime must not allow retry bookkeeping to grow without bound during long-lived disconnections.

## 8. HTTP / WebSocket Error Boundary Model

### 8.1 WebSocket Endpoint Cleanup

The websocket endpoint must catch:

- `WebSocketDisconnect`
- runtime receive/parse errors
- handler exceptions

And for all of them:

- log with context
- ensure `disconnect(websocket)` is called
- surface transport degradation where appropriate

### 8.2 Dispatch Failures Are Transport Faults

`DispatchResult.reason` is no longer just diagnostic metadata.

If enqueue fails because:

- no loop is bound
- loop is closed

the GUI runtime must treat that as a transport fault, not a no-op.

### 8.3 Fetch Must Become Typed Recovery

`fetchJson()` and session bootstrap helpers must distinguish:

- recoverable non-critical panel failures
- session bootstrap failure
- replay failure
- interaction conflict/expiry

`loadSession()` must stop using one all-or-nothing path for snapshot, timeline, plan, and permissions.

The minimum rule is:

- snapshot + timeline are critical
- plan + permissions are secondary
- secondary failures must degrade panels, not destroy the whole session load

## 9. Front-End Projector Completion

### 9.1 Projector Becomes The Full Active-Session Interpreter

The projector must interpret:

- user / assistant / reasoning / tool / transitions
- interaction requested / resolved / expired
- command result anchoring
- detached turn-level items
- session degradation state
- termination state

Reducer logic must stop hand-maintaining these as parallel truths.

### 9.2 Command Result Anchoring

The new anchoring order is:

1. explicit backend `turn_id`
2. local command anchor recorded when the command is issued
3. explicit fallback system-level rendering

The system may not silently attach command results to "latest pending user turn" when the link is ambiguous.

Wrong placement is worse than visible fallback.

### 9.3 Detached Item Ordering

Non-step items must be partitioned into:

- `leadingSystemItems`
- `stepItems`
- `trailingTurnItems`
- `sessionFallbackItems`

Detached turn items must no longer render above all step groups by default.

### 9.4 Resync State Is Multilevel

Replace the single boolean model with:

- `healthy`
- `replay_needed`
- `reload_required`
- `degraded`

The front end then maps these states to:

- continue
- replay
- full bootstrap reload
- conservative degraded display

### 9.5 Session-Scoped Debug State

Session switch must fully reset session-scoped runtime state, including:

- runtime event log
- debug/event log
- current interaction
- transport health for that session

The GUI may keep shell-level UI state, but active-session state must not bleed between sessions.

## 10. UI Follow-Through Changes

These are not standalone bugfixes; they follow from the runtime redesign.

### 10.1 Timeline Placement

The projector should directly decide where:

- compact cards
- system cards
- interaction history cards

appear in relation to steps and turn summaries.

This replaces the current fragile `groupByTurn()` fallback behavior.

### 10.2 Code Block Narrowing

`CodeBlock` should only be used for real fenced blocks, not any non-inline code node.

The renderer contract must narrow to intentional code blocks.

### 10.3 Copy Timer Cleanup

`CodeBlock` copy feedback must clean up timers on unmount.

This is a small component fix, but it belongs in this slice because the component boundary is already being touched.

### 10.4 CSS Structural Polish

Once runtime placement stabilizes, the slice may include:

- z-index layering tiers
- better resize hit area
- responsive breakpoints
- overflow cleanup

These are lower priority and should only be done after runtime correctness is secure.

## 11. Migration Plan

### Phase 1: Timeline Store Contract Hardening

Deliverables:

- explicit replay status contract
- detectable truncation semantics
- non-terminal malformed-line scan behavior
- removal of restore fallback interaction IDs

### Phase 2: Transport And HTTP Boundary Hardening

Deliverables:

- websocket endpoint exception cleanup
- typed replay endpoint
- typed interaction response errors
- bootstrap request tiering and panel-level degradation

### Phase 3: Projector Completion

Deliverables:

- full active-session projection contract
- command result anchor hardening
- detached item placement fix
- multilevel resync states

### Phase 4: UI Follow-Through

Deliverables:

- CodeBlock narrowing and timer cleanup
- compact/system placement cleanup
- session-scoped debug state reset
- optional low-risk CSS polish from the review list

## 12. Tests

### 12.1 New Required Tests

1. replay status differentiation
   - `replay` vs `reload_required` vs `degraded`

2. truncated window detection
   - `after_seq` older than retained window returns `reload_required`

3. malformed mid-file scan survival
   - later valid events are still visible, but integrity becomes degraded

4. restore expiration on missing interaction ID
   - no actionable pending interaction is restored

5. write-path degradation on `OSError`
   - append failure is logged and runtime integrity is marked degraded

6. transcript/timeline source missing recovery
   - resume/bootstrap degrades explicitly instead of throwing raw exceptions

7. websocket endpoint cleanup on non-disconnect exceptions
   - connection is removed and error is logged

8. typed interaction response errors
   - session missing / interaction expired / invalid payload are distinct

9. interaction freshness expiry
   - timed-out pending interactions are surfaced as expired, not actionable

10. projector command result fallback placement
   - ambiguous command results become explicit fallback cards, not misattached turn children

11. detached item ordering
   - turn-level detached items render after steps rather than before them

### 12.2 Existing Tests To Extend

- [`tests/test_gui_runtime.py`](../../tests/test_gui_runtime.py)
- [`tests/test_gui_backend_api.py`](../../tests/test_gui_backend_api.py)
- [`tests/test_inprocess_adapter_frontend_api.py`](../../tests/test_inprocess_adapter_frontend_api.py)
- [`tests/test_session_restore.py`](../../tests/test_session_restore.py)
- [`src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`](../../src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs)
- [`src/embedagent/frontend/gui/webapp/test/run-tests.mjs`](../../src/embedagent/frontend/gui/webapp/test/run-tests.mjs)

## 13. Acceptance Criteria

This design is complete when all of the following are true:

- GUI replay can explicitly say replay vs reload-required vs degraded
- timeline truncation can no longer silently trigger endless seq-gap resync loops
- malformed mid-file timeline rows no longer hide all later valid events
- timeline write-path failures no longer disappear silently
- restore never fabricates a pending interaction ID
- missing transcript/timeline inputs degrade explicitly instead of aborting GUI resume with a raw exception
- restored interactions cannot remain actionable solely because an old ID exists
- websocket endpoint cleans up and logs non-disconnect failures
- HTTP routes no longer surface common session/interaction lookup problems as generic 500s
- reconnect retry bookkeeping is bounded
- the projector owns command result anchoring and detached item placement
- Timeline and Inspector read from one coherent active-session runtime model

## 14. Non-Goals For This Slice

This design does not require:

- rewriting the full transcript truth model
- a new GUI visual system
- replacing the whole store/reducer layer at once
- solving every low-priority CSS issue before runtime correctness is done

## 15. Implementation Entry Files

The first implementation round should start from:

- [`src/embedagent/session_timeline.py`](../../src/embedagent/session_timeline.py)
- [`src/embedagent/inprocess_adapter.py`](../../src/embedagent/inprocess_adapter.py)
- [`src/embedagent/session_restore.py`](../../src/embedagent/session_restore.py)
- [`src/embedagent/frontend/gui/backend/server.py`](../../src/embedagent/frontend/gui/backend/server.py)
- [`src/embedagent/frontend/gui/backend/bridge.py`](../../src/embedagent/frontend/gui/backend/bridge.py)
- [`src/embedagent/frontend/gui/webapp/src/App.jsx`](../../src/embedagent/frontend/gui/webapp/src/App.jsx)
- [`src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js`](../../src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js)
- [`src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`](../../src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js)
- [`src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`](../../src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx)
- [`tests/test_gui_runtime.py`](../../tests/test_gui_runtime.py)
- [`tests/test_gui_backend_api.py`](../../tests/test_gui_backend_api.py)
- [`tests/test_session_restore.py`](../../tests/test_session_restore.py)

## 16. Decision

EmbedAgent GUI will harden its event-sourced active-session runtime around explicit replay, degradation, and projection contracts.

The current first-generation rollout is treated as a necessary foundation, but not yet the final target architecture for replay safety and projection ownership.
