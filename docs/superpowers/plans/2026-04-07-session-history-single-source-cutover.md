# Session History Single-Source Cutover Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current split session-history model with one official history pipeline so GUI session activation, session resume, and long-session replay all read from the same canonical structured state.

**Architecture:** Treat `transcript.jsonl` as the only durable session-history truth, materialize it into `Session`/`session.turns`, and generate GUI history from that materialized state through one dedicated history assembler. Treat `timeline.jsonl` as transport/replay infrastructure only, not as a database and not as a source for rebuilding historical turns.

**Tech Stack:** Python 3.8, existing `Session` / `SessionRestorer` / `TranscriptStore`, FastAPI GUI backend, React GUI frontend.

---

## 1. Problem Statement

The current GUI session-history path is architecturally unsound:

- `build_structured_timeline()` in [inprocess_adapter.py](/D:/Project/coding_agent/src/embedagent/inprocess_adapter.py#L676) rebuilds turns from `timeline.jsonl`.
- `timeline.jsonl` is a replay log with a default read window of 200 events in [session_timeline.py](/D:/Project/coding_agent/src/embedagent/session_timeline.py#L65).
- The same file is aggressively trimmed in [session_timeline.py](/D:/Project/coding_agent/src/embedagent/session_timeline.py#L140), so old structural events are permanently deleted.
- The product already has a stronger recovery pipeline: `transcript.jsonl -> SessionRestorer -> Session/turns`, centered in [session_restore.py](/D:/Project/coding_agent/src/embedagent/session_restore.py#L28).

This creates a split-brain architecture:

- Runtime truth and resume truth come from transcript/materialized session state.
- GUI historical truth comes from a lossy replay log.

Because the GUI activation flow in [App.jsx](/D:/Project/coding_agent/src/embedagent/frontend/gui/webapp/src/App.jsx#L176) treats `/timeline` as bootstrap history, the system can display:

- full raw fallback even when `session.turns` is intact
- only the tail of a session instead of full session history
- different history results for the same session depending on replay-window shape

This is not a frontend bug. It is a backend data-ownership failure.

## 2. Non-Goals

This cutover intentionally does not support:

- legacy timeline reconstruction paths
- raw fallback as a normal recovery mechanism
- dual history sources
- compatibility layers that keep `timeline.jsonl` as a structured-history source
- development-time parallel implementations

If a session cannot be restored from transcript at all, that is a real history failure and should surface as such.
If transcript yields a valid historical prefix but restore stops early, the product should return partial structured history plus integrity diagnostics, not raw fallback.

## 3. Official Final-State Model

### 3.1 Durable Truth

`transcript.jsonl` is the only durable source of session history.

Its role:

- durable append-only record for replayable session history
- source for restoring inactive sessions
- source for integrity validation

It is not optional. It is the historical ledger.

### 3.2 Live Materialized Truth

`Session` is the only live structured session object.

Its role:

- current in-memory execution state
- current `turns`, `steps`, `tool_calls`, `transitions`, `pending_interaction`
- immediate source for active-session history serialization

`session.turns` is not a UI cache. It is the canonical structured projection of transcript for a live session.

### 3.3 Transport Replay Log

`timeline.jsonl` becomes transport-only infrastructure.

Its role:

- websocket reconnect replay
- sequence-number continuity
- short-term recovery after connection gaps
- debugging of transport delivery

It must not be used to rebuild historical turns.

### 3.4 GUI History View

GUI history comes from one source only:

- active session: serialize current materialized `Session`
- inactive session: restore transcript into `Session`, then serialize that `Session`

There is no second path.

## 4. Required Architectural Decisions

### 4.1 Delete `build_structured_timeline()` as a Replay-Log Parser

The current logic in [inprocess_adapter.py](/D:/Project/coding_agent/src/embedagent/inprocess_adapter.py#L676) must be replaced, not tuned.

Do not:

- increase `limit`
- weaken `has_turn_start`
- keep raw replay parsing as a fallback
- preserve `turn_events` / `raw_events` reconstruction modes as official behavior

The replacement should be a dedicated history serializer operating on `Session`.

### 4.2 Introduce One History Assembler

Add a dedicated component with a single responsibility:

- convert `Session` into GUI history DTOs

Recommended location:

- create [session_history.py](/D:/Project/coding_agent/src/embedagent/session_history.py)

Responsibilities:

- serialize turns, steps, tool calls, transitions, compact boundaries, and interaction anchors
- enrich tool history from durable presentation metadata first, then from current tool catalog/runtime fallback
- provide a stable history API contract independent of transport logs

This assembler must be the only backend path that produces GUI history.

### 4.3 Stop Encoding History Provenance as Projection Fallback

The current response shape uses `projection_source` to reflect parser behavior:

- `step_events`
- `turn_events`
- `raw_events`

That vocabulary is an artifact of a broken implementation.

Final-state behavior should instead model actual history origin:

- `session_state`
- `transcript_restore`

Or omit source entirely from normal UI flows and keep it only as internal diagnostics.

`raw fallback` must not remain a first-class GUI state.

### 4.4 Replace Split Session Activation with a Single Bootstrap Contract

Current GUI activation fetches snapshot and timeline separately in [App.jsx](/D:/Project/coding_agent/src/embedagent/frontend/gui/webapp/src/App.jsx#L176).

That allows split-brain activation:

- snapshot from one state
- timeline from another state
- plan and permissions from yet more calls

Final-state design should provide one bootstrap endpoint:

- `GET /api/sessions/{id}/bootstrap`

Response should include:

- `snapshot`
- `history`
- `plan`
- `permission_context`
- replay transport metadata

This endpoint should auto-activate the session if it is not currently materialized.

### 4.5 Auto-Hydrate Sessions on Read

The GUI should not need a separate concept of:

- active in-memory session
- resumable stored session

From the GUI's perspective, opening a session means:

- if session is materialized, use it
- otherwise restore it from transcript and materialize it

This logic belongs in adapter/core, not in GUI heuristics.

Make this concrete in the adapter layer:

- add `def _ensure_session_active(self, reference: str, mode: str = "") -> ManagedSession:`
- if `reference` is already in `self._sessions`, return it
- otherwise call `resume_session(reference, mode or DEFAULT_MODE)` and then return the newly materialized `ManagedSession`

All structured read-model entry points must go through this helper:

- `get_session_snapshot`
- structured history bootstrap / history serialization
- `get_session_plan`
- `get_permission_context`
- any future `open_session` / `bootstrap_session` API

## 5. Data Model Strategy

### 5.1 Keep Core Session Model Focused on Execution Truth

Do not turn `ToolCallRecord` into a dumping ground for frontend-only decoration.

Keep core fields centered on execution truth:

- identity
- arguments
- timestamps
- status
- observation
- progress

At the same time, historical rendering needs a small amount of immutable presentation metadata.
That data should be modeled deliberately, not smuggled in as ad-hoc UI fields.

### 5.2 Snapshot Immutable Historical Presentation Metadata

Introduce a narrow `ToolPresentationSnapshot` concept for history, persisted with tool-call history and materialized into session state.

This snapshot should cover stable, historically meaningful presentation semantics:

- `tool_label`
- `permission_category`
- `supports_diff_preview`
- `progress_renderer_key`
- `result_renderer_key`

These fields are part of how the tool invocation is meant to be interpreted in history, and should not drift when the runtime catalog changes later.

### 5.3 Keep Volatile Runtime Metadata Out of Historical Tool Identity

Fields such as:

- `runtime_source`
- `resolved_tool_roots`
- `fallback_warnings`

are runtime/debug metadata, not stable historical identity.

They should be exposed through:

- current runtime environment snapshot
- bootstrap/session diagnostics
- optional debug sections in the history payload

They should not be required for rendering core historical tool entries.

### 5.4 Serializer Resolution Order for Tool Metadata

When serializing tool calls for history, resolve display metadata in this order:

1. persisted `ToolPresentationSnapshot`
2. current tool catalog entry
3. safe hardcoded fallback

Required fallback behavior:

- `tool_label = tool_name`
- `permission_category = ""`
- `supports_diff_preview = False`
- `progress_renderer_key = "default"`
- `result_renderer_key = "default"`

This prevents restored history from breaking if a tool catalog entry disappears, is renamed, or changes shape during development.

### 5.5 Only Persist More Data if It Is Execution Truth or Stable Historical Contract

Persist additional transcript fields only when they are necessary to reconstruct actual history semantics.

Good candidates:

- explicit step status when not inferable
- durable compact-boundary metadata
- pending-interaction identity and resolution events
- immutable tool presentation snapshot

Bad candidates:

- frontend-only badge variants
- temporary transport-state details
- ephemeral connection status

## 6. API Contract Shape

### 6.1 New History DTO

Define one official DTO for GUI history.

Recommended top-level shape:

```json
{
  "session_id": "string",
  "history_source": "session_state",
  "turns": [],
  "current_interaction": null,
  "integrity": {
    "status": "healthy",
    "restore_stop_reason": ""
  }
}
```

Turn shape should contain:

- `turn_id`
- `user_text`
- `steps`
- `transitions`
- `status`

Step shape should contain:

- `step_id`
- `step_index`
- `reasoning`
- `assistant_text`
- `tool_calls`
- `transitions`
- `status`

Tool call shape should contain:

- execution truth from session state
- stable historical presentation metadata
- optional runtime/debug enrichment that can safely disappear without corrupting history

### 6.2 No Raw Event History Endpoint for GUI Bootstrap

Keep `/api/sessions/{id}/events` for transport replay only.

Do not let GUI bootstrap derive turn history from it.

### 6.3 Explicit Integrity Model

Transcript restore is not binary. The system already has two real outcomes:

- full restore
- valid prefix restore with a non-empty `restore_stop_reason`

The official history contract should expose that explicitly:

- `integrity.status = "healthy"` when all transcript events are consumed
- `integrity.status = "partial"` when a valid historical prefix is restored but restore stops early
- `integrity.status = "unavailable"` when transcript is missing, unreadable, or cannot produce a usable root session

The DTO should also carry:

- `restore_stop_reason`
- `consumed_event_count`
- `transcript_event_count`

Behavior rules:

- `partial` returns recovered structured turns and interactions up to the safe prefix
- `unavailable` returns no structured history and an explicit failure payload
- neither case may silently degrade into raw event rendering

The GUI should show:

- a structured-history integrity banner for `partial`
- an explicit session-history unavailable state for `unavailable`

not:

- raw fallback

## 7. Frontend Final-State Behavior

### 7.1 Bootstrap History Is Structured Only

On session activation:

- fetch one bootstrap payload
- populate snapshot, history, plan, permissions from that payload

`timelineFromEvents()` should not be used for normal session activation.

### 7.2 Transport Events Only Extend Live Runtime

Realtime websocket / replay events remain useful, but only for:

- appending live updates after bootstrap
- restoring missed live updates after reconnect
- reflecting interaction delivery state

They should not be reinterpreted as authoritative historical turns.

### 7.3 Remove Raw Fallback UI

Delete the raw-fallback presentation path in:

- [state-helpers.js](/D:/Project/coding_agent/src/embedagent/frontend/gui/webapp/src/state-helpers.js)
- [Timeline.jsx](/D:/Project/coding_agent/src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx)

If history bootstrap fails, show an explicit session-history error card instead.

### 7.4 Keep Runtime Projector, Narrow Its Scope

The runtime projector in [projector.js](/D:/Project/coding_agent/src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js) is directionally correct.

Its scope should become:

- merge structured bootstrap history with live interaction/replay overlays

Its scope should not include:

- compensating for broken bootstrap history
- inventing historical grouping from replay logs

### 7.5 Make Bootstrap-to-Live Merge Idempotent

The main idempotence boundary for live turn/step/tool updates is not the projector. It is the frontend reducer and session event log pipeline.

The final design must explicitly assign merge responsibilities:

- `bootstrap history` owns the initial structured turn list
- websocket/replay stream owns incremental live updates
- reducer/state update logic in [store.js](/D:/Project/coding_agent/src/embedagent/frontend/gui/webapp/src/store.js) must upsert by stable identity instead of blindly appending equivalent items

Stable merge keys:

- `turn_id`
- `step_id`
- `call_id`
- transport `event_id` / `seq` for replay bookkeeping

Required invariant:

- receiving a delayed `step_end` / `tool_finished` after bootstrap must update the existing step/tool item, not duplicate it

## 8. Persistence and Recovery Implications

### 8.1 Transcript Must Be Considered Product-Critical

Because transcript becomes the sole durable truth, quality requirements rise:

- tail repair remains required
- sequence continuity remains required
- restore validation remains required

The existing `TranscriptStore` and `SessionRestorer` are already the right backbone.

Important nuance:

- `TranscriptStore` already gives the system a valid prefix on damaged tails
- `SessionRestorer` already returns partial materialization plus `stop_reason`

The cutover should formalize those behaviors into the official history integrity model rather than introducing a second, unrelated fallback mechanism.

### 8.2 Timeline Trim Becomes Harmless

Once GUI history no longer depends on `timeline.jsonl`:

- trim policy can stay bounded
- replay window can stay short
- old replay events can disappear without corrupting session history

That is the correct property for a transport log.

### 8.3 Optional Future Optimization

If transcript restore cost grows for very large sessions, add a derived cache:

- `history.json`
- or sqlite history projection

But make it explicitly derived from transcript and replaceable on demand.

Never make the cache a second truth source.

### 8.4 Performance Budget and Escalation Rule

Phase 1 must define and measure a concrete bootstrap budget.

Recommended acceptance targets on target development hardware:

- 500-turn session bootstrap under 200 ms
- 1000-turn session bootstrap under 500 ms

If these targets are missed:

- first profile restore + assemble separately
- only then decide whether to add a derived history cache or pagination

## 9. Recommended Module Changes

### 9.1 Add

- [session_history.py](/D:/Project/coding_agent/src/embedagent/session_history.py)
- history DTO tests in [tests](/D:/Project/coding_agent/tests)

### 9.2 Replace

- replace replay-log parsing in [inprocess_adapter.py](/D:/Project/coding_agent/src/embedagent/inprocess_adapter.py#L676)

### 9.3 Extend

- adapter/core session-open flow so inactive sessions auto-restore on access via `_ensure_session_active`
- GUI backend with one bootstrap endpoint in [server.py](/D:/Project/coding_agent/src/embedagent/frontend/gui/backend/server.py)
- frontend activation flow in [App.jsx](/D:/Project/coding_agent/src/embedagent/frontend/gui/webapp/src/App.jsx)
- reducer/state merge logic in [store.js](/D:/Project/coding_agent/src/embedagent/frontend/gui/webapp/src/store.js) for idempotent bootstrap-to-live updates

### 9.4 Delete

- raw fallback history path
- `turn_events` synthetic projection path as an official code path
- any code that treats replay logs as historical storage

## 10. Implementation Order

### Phase 1: Backend History Unification

- define the final history DTO
- implement `SessionHistoryAssembler`
- replace `build_structured_timeline()` internals to use materialized `Session`
- add `_ensure_session_active()` and route structured read paths through it
- formalize `healthy` / `partial` / `unavailable` integrity states
- snapshot immutable tool presentation metadata in durable history

Deliverable:

- one backend history path for active and resumed sessions

### Phase 2: Bootstrap Contract Cutover

- add `/api/sessions/{id}/bootstrap`
- return snapshot, history, plan, permission context, replay state together
- switch GUI activation to bootstrap-only

Deliverable:

- activation no longer races across multiple endpoints

### Phase 3: Frontend Cleanup

- remove raw fallback badges and notices
- narrow `timelineFromEvents()` to transport/debug-only use or delete it entirely
- keep runtime projector for live overlays only
- make reducer updates idempotent across bootstrap + live replay boundaries

Deliverable:

- GUI shows only structured session history or explicit failure

### Phase 4: Dead-Path Deletion

- delete replay-log-based structured history parsing
- delete tests that preserve old fallback behavior
- update architecture docs to reflect the single-source model

Deliverable:

- no dual-path session-history architecture remains

## 11. Verification Requirements

The final implementation must prove all of the following:

- long sessions do not lose historical turns in GUI bootstrap
- event replay gaps trigger bootstrap reload, not raw fallback
- resumed sessions and active sessions produce identical structured history
- trimming `timeline.jsonl` does not affect historical turn rendering
- transcript prefix restore surfaces explicit `partial` integrity rather than full failure or raw fallback
- transcript unavailability surfaces explicit session-history failure
- interaction state survives bootstrap and live replay coherently
- missing tool catalog entries do not break restored history rendering
- bootstrap plus delayed live events remains idempotent
- bootstrap meets the agreed performance budget or triggers explicit optimization work

Required focused tests:

- adapter tests for active-session history serialization
- adapter tests for inactive-session auto-restore and serialization
- regression tests reproducing the 200-event window failure
- regression tests reproducing timeline trim after intact transcript
- regression tests for partial restore with non-empty `restore_stop_reason`
- regression tests for missing tool catalog metadata fallback
- frontend runtime tests for bootstrap + live replay merge
- focused frontend reducer tests for delayed `step_end` / `tool_finished` upsert behavior

## 12. Documentation Updates Required During Implementation

This cutover changes official architecture and must update, in the same implementation change:

- [README.md](/D:/Project/coding_agent/README.md)
- [AGENTS.md](/D:/Project/coding_agent/AGENTS.md)
- [docs/overall-solution-architecture.md](/D:/Project/coding_agent/docs/overall-solution-architecture.md)
- [docs/frontend-protocol.md](/D:/Project/coding_agent/docs/frontend-protocol.md)
- [docs/agent-harness-v2.md](/D:/Project/coding_agent/docs/agent-harness-v2.md)
- [docs/tool-contracts.md](/D:/Project/coding_agent/docs/tool-contracts.md)
- [docs/development-tracker.md](/D:/Project/coding_agent/docs/development-tracker.md)
- [docs/design-change-log.md](/D:/Project/coding_agent/docs/design-change-log.md)

## 13. Final Recommendation

The repository should adopt this explicit rule:

> Session history is reconstructed from transcript-backed session state only. Replay logs are transport infrastructure and must never be used as historical truth.

That single decision removes the current raw-fallback defect, removes long-session truncation bugs, aligns GUI activation with session resume, and gives the product a scalable base for pagination, multi-client viewing, remote session transport, and future offline auditing.
