# Event-Sourced GUI Session Runtime For Timeline And Interaction Consistency

> Date: 2026-04-04
> Status: Approved design baseline
> Scope: GUI active-session runtime, focused on timeline, pending interaction, transport recovery, and resume consistency

## 1. Goal

EmbedAgent GUI will move from "mixed local state + snapshot state + timeline side effects" to an event-sourced active-session runtime.

The target outcome is:

- the active GUI session page uses one append-only event log as its UI truth source
- `permission` and `user_input` are unified into a single `interaction` domain model
- Inspector becomes the only interactive entry point for pending approvals and user answers
- Timeline becomes a pure projection of session history instead of a second control plane
- WebSocket and HTTP become complementary transport layers with explicit recovery semantics instead of competing truth sources

This direction is chosen because the confirmed GUI issues are primarily architectural consistency problems, not isolated rendering bugs. The design intentionally favors a structural improvement over patch-style fixes.

## 2. Confirmed Problem Statement

The audit input is documented in [`docs/issues/gui-timeline-issues-final.md`](../../issues/gui-timeline-issues-final.md). After code inspection, the problems that matter for this slice collapse into five root causes:

1. the same runtime fact is represented by multiple truth sources
   - `snapshot.pending_*`
   - timeline activity cards
   - reducer-local state such as `permission`, `userInput`, `activeTurnId`, `streamingAssistantId`

2. the same user action is exposed through multiple control surfaces
   - Timeline inline `PermissionCard`
   - Inspector `PermissionPrompt`

3. transport assumptions are optimistic instead of recoverable
   - missing `socket.onerror`
   - unguarded `JSON.parse`
   - fetch failures propagate without a unified policy
   - dispatcher failures can drop events without surfacing a recovery path

4. session restore semantics are unstable for pending interactions
   - fallback IDs such as `perm-resume` break identity continuity
   - restore can produce a front-end visible pending prompt that does not map to a real back-end waiter

5. timeline projection and live reducer updates are partially duplicated
   - cold-start projection and live WebSocket handling do not share one deterministic projector
   - step, turn, reasoning, tool, and pending interaction state can drift apart

The most important conclusion is:

- the current problems are not mainly caused by bad JSX or missing conditionals
- they come from a session runtime model that lets multiple layers infer and mutate overlapping state

## 3. Explicit Decisions For This Design

The following decisions were confirmed during brainstorming and are part of the design contract:

1. this slice prioritizes structural repair of the active GUI session chain over broad issue-list coverage
2. front-end and back-end GUI contracts may change when needed to close the consistency gaps
3. old GUI timeline projection data does not need compatibility preservation
4. the redesign focuses on the active session page state core, not a full GUI visual rewrite

These decisions intentionally allow a cleaner cut than the existing compatibility path would.

## 4. Design Principles

The implementation must preserve these rules:

- Windows 7 compatibility remains mandatory
- Python 3.8 compatibility remains mandatory
- the Agent Core remains the product core; GUI is still a projection layer
- transcript and session state remain product truth at the core level
- the GUI runtime may define its own event log as UI truth, but not as product-wide truth
- the active session runtime must be deterministic: full replay and incremental replay must converge to the same UI view
- pending interactions must have stable identities or be explicitly expired; synthetic fallback IDs are not allowed
- transport faults must trigger recovery or degradation, never silent best-effort drift

## 5. Scope Boundary

### 5.1 In Scope

- active session Timeline / Inspector / Composer state coordination
- GUI transport handling for session events
- pending permission and ask-user interaction handling
- session bootstrap, resync, and restore behavior as seen by GUI
- structured timeline projection rules
- GUI-facing error mapping and degraded-state handling
- regression tests for projector, transport, interaction, and restore behavior

### 5.2 Out Of Scope

- full visual redesign of the application shell
- wholesale rewrite of all GUI panels
- changing transcript truth architecture for the whole product
- backward compatibility with old GUI timeline cache/projection artifacts
- global CSS cleanup unrelated to the active session runtime
- introducing browser automation or remote multi-agent session orchestration

## 6. Target Runtime Model

### 6.1 Truth Layers

This slice introduces two clearly separated truth layers:

1. Core truth
   - existing session/transcript/runtime state inside Agent Core
   - unchanged as the product-level truth source

2. GUI active-session truth
   - a per-session append-only GUI event log built from normalized `session_event` envelopes
   - authoritative for current GUI page projection

The GUI must stop treating `snapshot`, timeline items, and reducer-local fields as independent truths.

### 6.2 Snapshot Role

`GET /api/sessions/{id}` is redefined as bootstrap and recovery input only.

It is allowed to do three things:

1. initialize a session view on first open
2. re-anchor the session after transport faults or reconnects
3. provide the currently pending interaction and runtime summary for correction

It is not allowed to become a second live state machine that competes with the event log.

### 6.3 Timeline Role

Timeline becomes a pure historical projection.

It may show:

- user turns
- agent steps
- reasoning
- tool execution
- interaction creation and resolution
- compact / guard / cancellation / terminal transitions

It may not own current approval or input controls.

### 6.4 Interaction Role

`permission` and `user_input` are unified into one domain object:

- `interaction.kind = permission | user_input | mode_switch_proposal`
- each interaction has one stable `interaction_id`
- each interaction can be `pending`, `resolved`, `expired`, or `cancelled`

Inspector is the only place where a pending interaction can be answered.
Timeline only shows the interaction request and its outcome.

## 7. GUI Event Envelope

The GUI WebSocket stream will be normalized to one standard message shape:

```json
{
  "type": "session_event",
  "data": {
    "session_id": "sess_xxx",
    "event_id": "evt_xxx",
    "seq": 123,
    "created_at": "2026-04-04T12:34:56Z",
    "event_kind": "interaction.created",
    "payload": {}
  }
}
```

### 7.1 Envelope Rules

- `session_id` is required
- `event_id` is required and stable
- `seq` is required and monotonic per session
- `event_kind` is required and must be from a bounded GUI event vocabulary
- `payload` is always an object, even when empty

### 7.2 Required Event Kinds

The first GUI event vocabulary for this slice is:

- `session.bootstrap`
- `turn.started`
- `step.started`
- `step.reasoning_delta`
- `tool.started`
- `tool.finished`
- `interaction.created`
- `interaction.resolved`
- `interaction.expired`
- `transition.recorded`
- `session.finished`
- `session.error`
- `transport.degraded`

The mapper layer may derive these from existing core callbacks, but the GUI consumes only the normalized vocabulary.

### 7.3 Ordering Rules

- the GUI only applies events in increasing `seq`
- duplicate `seq` or duplicate `event_id` is ignored if already applied
- a gap in `seq` marks the session `needsResync`
- malformed event payloads also mark `needsResync`

The GUI must prefer deterministic recovery over speculative local repair.

## 8. Front-End Architecture

### 8.1 State Layers

The current active-session state is replaced by four layers:

1. `SessionEventLogStore`
   - stores append-only per-session GUI events
   - stores `lastAppliedSeq`, `connectionState`, `needsResync`

2. `SessionProjector`
   - pure projection from event log + bootstrap snapshot into UI read models

3. `SessionCommands`
   - sends message, cancel, interaction response, resync request
   - does not directly mutate projected state

4. `UI Components`
   - render read models only

### 8.2 Reducer Rules

The front-end reducer stops storing derived runtime facts such as:

- `permission`
- `userInput`
- `activeTurnId`
- `activeStepId`
- `streamingAssistantId`
- `streamingReasoningId`

These values become projector outputs, not reducer-owned truths.

### 8.3 Read Models

The projector must produce at least:

- `timelineView`
- `currentInteraction`
- `sessionStatusView`
- `transportView`
- `inspectorView`
- `composerView`

The same event sequence must always produce the same read models.

### 8.4 Projection Contract

The projector must support two equivalent modes:

1. full replay from bootstrap + historical events
2. incremental replay from the last applied event

The results must match.

This requirement eliminates the current split between:

- cold-start `loadSession()` projection
- live WebSocket reducer patching

### 8.5 Interaction Projection Rules

When `interaction.created` arrives:

- `currentInteraction` becomes that interaction if no newer pending interaction supersedes it
- Timeline gets a historical request item
- Inspector shows the interactive prompt

When `interaction.resolved` arrives:

- `currentInteraction` is cleared if it matches the resolved ID
- Timeline gets or updates a historical resolution item
- Inspector no longer offers controls for that interaction

When `interaction.expired` arrives:

- any matching pending interaction is cleared
- Timeline records explicit expiration
- UI is not allowed to silently keep the old prompt visible

### 8.6 Component Boundary Changes

The active session page keeps the current shell layout, but the component responsibilities change:

- `App.jsx`
  - owns transport lifecycle and session switching
  - does not hand-build timeline state

- `Timeline.jsx`
  - renders `timelineView`
  - no inline pending-interaction controls

- `Inspector.jsx`
  - renders `currentInteraction`, permission context, runtime summary, preview, and other tabs
  - the only interactive location for pending approvals and answers

- `Composer.jsx`
  - reads projected session/transport state to determine send availability

## 9. Interaction Command Model

### 9.1 Unified Response Command

All GUI interaction responses are normalized to one command:

```json
{
  "interaction_id": "int_xxx",
  "session_id": "sess_xxx",
  "response_kind": "approve",
  "decision": true,
  "remember": false,
  "answer": "",
  "selected_index": null,
  "selected_mode": "",
  "client_request_id": "cli_xxx"
}
```

Not every field is used for every interaction kind, but the command envelope is unified.

### 9.2 Idempotency Rules

The back-end must treat `interaction_id + client_request_id` as an idempotency key.

This solves:

- rapid double-click approve/deny
- retry after transport uncertainty
- duplicate submission after reconnect

If an interaction is already resolved or expired, the back-end returns a structured conflict or gone response instead of silently ignoring the request.

### 9.3 Inspector-Only Control Rule

Only Inspector may send interaction responses.

Timeline may display:

- request summary
- resolution summary
- expired/cancelled notice

Timeline may not expose current decision buttons or editable input areas for active interactions.

## 10. Transport And Recovery Model

### 10.1 WebSocket Responsibilities

WebSocket is the low-latency incremental event channel.

It must:

- emit normalized `session_event` envelopes
- surface `onerror`
- never allow `JSON.parse` failure to crash the active page runtime
- trigger reconnect and resync flow when event integrity cannot be trusted

### 10.2 HTTP Responsibilities

HTTP is the recovery and bootstrap channel.

It must provide:

- session bootstrap
- structured timeline bootstrap
- event replay or diff fetch after `seq`
- interaction response endpoint with structured errors

### 10.3 Reconnect Model

The front-end stores:

- `lastAppliedSeq`
- `connectionState`
- `needsResync`

Reconnect flow is:

1. reconnect transport
2. request events after `lastAppliedSeq`
3. if diff replay succeeds, continue incrementally
4. if diff replay fails, reload bootstrap + timeline and rebuild from scratch

### 10.4 Failure Triggers For Resync

Any of the following set `needsResync = true`:

- WebSocket parse error
- unknown critical event shape
- `seq` gap
- conflicting interaction lifecycle
- explicit `transport.degraded`

### 10.5 Error Mapping

GUI back-end routes must return explicit status categories:

- `404 session_not_found`
- `409 interaction_conflict`
- `410 interaction_gone`
- `422 malformed_event_or_request`
- `503 transport_unavailable`

The front-end must handle these deterministically rather than through ad hoc exception strings.

## 11. Back-End Architecture Changes

### 11.1 GUI Event Mapper

A GUI-specific mapper layer will sit between core callbacks and GUI transport.

Responsibilities:

- normalize existing callback payloads into GUI event vocabulary
- assign stable GUI `event_kind`
- pass through `session_id`, `event_id`, `seq`, `payload`
- ensure interaction events use stable `interaction_id`

This keeps GUI protocol evolution decoupled from internal callback naming drift.

### 11.2 Stable Interaction Identity

Pending interaction restore rules are tightened:

- restore may only use a real persisted interaction ID
- synthetic fallback IDs such as `perm-resume` and `ask-resume` are removed
- if a valid ID cannot be restored, the back-end emits `interaction.expired`

The system must prefer explicit invalidation over fake continuity.

### 11.3 Session Timeline Store Expectations

Because GUI active-session truth depends on ordered events, timeline/event persistence becomes first-class operational state.

Required behavior:

- append failures must be observable
- damaged tails may be repaired, but not silently hidden from diagnostics
- disk or fsync failures should mark the session or transport as degraded
- bootstrap/replay endpoints must fail explicitly if event integrity cannot be trusted

### 11.4 Dispatcher Expectations

`ThreadsafeAsyncDispatcher.dispatch()` failure must no longer be an invisible bool that callers ignore.

Failure to enqueue a GUI event must:

- be logged
- be surfaced as transport degradation
- trigger recovery behavior where applicable

## 12. Restore And Degraded-State Semantics

### 12.1 Restore Contract

For GUI purposes, restore must guarantee one of two outcomes:

1. real pending interaction restored with its original stable ID
2. pending interaction explicitly expired and removed from the actionable UI

There is no third path where the UI keeps an actionable prompt backed by a fabricated ID.

### 12.2 Degraded Mode

If the GUI cannot trust the event stream or replay state, it may enter degraded mode.

Degraded mode means:

- current session remains visible
- Timeline can show best-known projection
- pending interactions are not shown as actionable unless verified
- Inspector shows recovery or degraded-state notice
- transport/runtime/log panels expose the failure reason

### 12.3 Summary Dependency Reduction

GUI bootstrap and restore must not depend on `summary.json` being intact in order to represent active-session truth.

Summary remains useful as a derived view, but not as a required truth source for active interaction state.

## 13. Migration Plan

### Phase 1: Event Contract And Projector Skeleton

Deliverables:

- normalized GUI event envelope
- front-end event log store
- first projector version
- Timeline converted to read-model rendering only
- Inspector converted to the only active interaction control surface

### Phase 2: Transport Recovery

Deliverables:

- WebSocket `onerror`
- JSON parse guards
- fetch error normalization
- reconnect + replay-after-seq flow
- structured back-end error mapping

### Phase 3: Restore And Interaction Identity

Deliverables:

- stable interaction restore path
- removal of fallback resume IDs
- expired interaction handling
- degraded-mode projection and notices

### Phase 4: Follow-On High-Value UX Cleanup

Deliverables:

- projector-driven step aggregation cleanup
- context/compact card placement fixes aligned with new projection rules
- code block interaction cleanup that naturally fits the new runtime
- remaining event-log/session-switch cleanup

## 14. Tests

### 14.1 New Required Tests

1. projector determinism
   - full replay and incremental replay produce the same read models

2. interaction single-entry semantics
   - active interaction is only actionable through Inspector projection
   - Timeline records request and resolution only

3. duplicate interaction response idempotency
   - repeated responses with the same `client_request_id` do not double-resolve

4. seq-gap recovery
   - a missing event sequence forces `needsResync`

5. malformed event handling
   - parse or schema failure does not crash the session page and leads to recovery

6. restore with real interaction ID
   - restored interaction remains actionable only when the original ID is valid

7. restore without valid interaction ID
   - the system emits expiration and clears actionable state

8. dispatcher failure visibility
   - event enqueue failure becomes observable and recoverable

### 14.2 Existing Tests To Extend

- [`tests/test_gui_runtime.py`](../../tests/test_gui_runtime.py)
- [`tests/test_inprocess_adapter_frontend_api.py`](../../tests/test_inprocess_adapter_frontend_api.py)
- any new front-end state/projector test module added under the GUI webapp test area

## 15. Acceptance Criteria

This design is complete when all of the following are true:

- the active GUI session page no longer depends on overlapping truth sources for pending interaction state
- Timeline no longer provides active approval/input controls
- Inspector is the single interactive entry point for pending interactions
- cold-start and live-update session views are produced by one deterministic projector
- WebSocket and HTTP have explicit bootstrap, replay, and recovery roles
- malformed transport data does not crash the front-end runtime
- session restore never fabricates pending interaction IDs
- event loss or ordering faults trigger resync or degraded mode instead of silent drift

## 16. Non-Goals For This Slice

This design does not require:

- a full rewrite of all GUI components
- a new visual design system
- compatibility migration for legacy GUI timeline cache data
- changing the product-wide transcript truth model
- solving every CSS-level P2 issue in the audit document

## 17. Implementation Entry Files

The first implementation round should start from:

- [`src/embedagent/frontend/gui/backend/server.py`](../../src/embedagent/frontend/gui/backend/server.py)
- [`src/embedagent/frontend/gui/backend/bridge.py`](../../src/embedagent/frontend/gui/backend/bridge.py)
- [`src/embedagent/inprocess_adapter.py`](../../src/embedagent/inprocess_adapter.py)
- [`src/embedagent/session_timeline.py`](../../src/embedagent/session_timeline.py)
- [`src/embedagent/frontend/gui/webapp/src/App.jsx`](../../src/embedagent/frontend/gui/webapp/src/App.jsx)
- [`src/embedagent/frontend/gui/webapp/src/store.js`](../../src/embedagent/frontend/gui/webapp/src/store.js)
- [`src/embedagent/frontend/gui/webapp/src/state-helpers.js`](../../src/embedagent/frontend/gui/webapp/src/state-helpers.js)
- [`src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`](../../src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx)
- [`src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`](../../src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx)
- [`tests/test_gui_runtime.py`](../../tests/test_gui_runtime.py)
- [`tests/test_inprocess_adapter_frontend_api.py`](../../tests/test_inprocess_adapter_frontend_api.py)

## 18. Decision

EmbedAgent GUI will adopt an event-sourced active-session runtime for Timeline and pending interaction consistency.

The current mixed model of:

- snapshot-derived pending state
- reducer-local pending state
- timeline-embedded action cards

is treated as an interim architecture and not the target design.
