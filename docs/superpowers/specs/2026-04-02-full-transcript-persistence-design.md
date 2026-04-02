# Full Transcript Persistence For Resume Consistency

> Date: 2026-04-02
> Status: Approved design baseline
> Scope: Context/Loop refactor line, focused on resume consistency

## 1. Goal

EmbedAgent will move from "summary-driven resume" to "full transcript persistence + state reconstruction".

The target outcome is:

- `transcript` becomes the only session truth source
- `summary.json` and `index.json` become derived projections
- resume restores real session state instead of starting a fresh session with a synthetic resume message

This direction is chosen to align with the long-term goal of learning from Claude Code style implementations and converging toward the stronger design, not patching the current summary-based path.

## 2. Current Problem

The current resume flow is implemented around [`SessionSummaryStore.create_resumed_session()`](/D:/Claude-project/ccode-win7/src/embedagent/session_store.py), which:

- loads `summary.json`
- creates a new `Session`
- injects a resume summary as a new system message
- appends the current mode system prompt

This is sufficient for a lightweight "continue from summary" flow, but it is not a true resume. The following state is either lost or only weakly approximated:

- exact `TranscriptMessage` history
- `Turn` / `AgentStepState` topology
- `ToolCallRecord` linkage by `call_id`
- `CompactBoundary` history
- pending interaction waiting state
- tool-result replacement state
- context assembly state used before suspension or shutdown

As a result, `resume consistency` is currently the weakest part of the Query/Context redesign line.

## 3. Design Principles

The implementation must preserve these rules:

- Windows 7 compatibility remains mandatory
- Python 3.8 compatibility remains mandatory
- append-only durable storage is preferred over complex mutable state files
- GUI/TUI remain projections, not state truth sources
- summaries are allowed to drift or be regenerated; transcripts are not
- pending interactions must be resumable without being flattened into prose

## 4. Target Model

### 4.1 Truth vs Projection

Session persistence is split into two layers:

1. Truth layer
   - `.embedagent/memory/sessions/<session_id>/transcript.jsonl`
   - append-only event stream
   - authoritative source for restore/replay

2. Projection layer
   - `summary.json`
   - `index.json`
   - future snapshot/cache files
   - derived from transcript for UI, listing, preview, and fast inspection

If projections are missing or stale, the system must still be able to resume from transcript alone.

### 4.2 Resume Semantics

Resume means:

1. load transcript events
2. rebuild `Session` state by replay
3. regenerate projections as needed
4. continue execution from reconstructed state

Resume does not mean:

- create a new session shell around a prose summary
- approximate prior state from a few summary fields

## 5. Transcript Schema

Transcript storage uses append-only JSONL. Each line is one event with a shared envelope:

```json
{
  "schema_version": 1,
  "session_id": "abc123",
  "event_id": "evt-001",
  "seq": 1,
  "ts": "2026-04-02T10:00:00Z",
  "type": "message",
  "payload": {}
}
```

### 5.1 Required Event Types

The first supported event types are:

- `session_meta`
- `message`
- `step_started`
- `tool_call`
- `tool_result`
- `loop_transition`
- `pending_interaction`
- `pending_resolution`
- `compact_boundary`
- `content_replacement`
- `context_snapshot`

### 5.2 Event Responsibilities

Each event type has a narrow contract:

- `session_meta`
  - session/workspace metadata
  - initial mode
  - transcript path or project-dir metadata when needed

- `message`
  - system/user/assistant/tool transcript message
  - preserves `message_id`, `turn_id`, `step_id`
  - assistant payload includes `actions`, `reasoning_content`, `finish_reason`
  - tool payload includes `tool_call_id`, `tool_name`, `replaced_by_refs`

- `step_started`
  - records `turn_id`, `step_id`, `step_index`

- `tool_call`
  - records `call_id`, `tool_name`, `arguments`, `status`

- `tool_result`
  - records `call_id`, `observation`, `finished_at`

- `loop_transition`
  - records `reason`, `message`, `next_mode`, `metadata`

- `pending_interaction`
  - records permission or user-input request payload

- `pending_resolution`
  - records approval, rejection, or user choice payload

- `compact_boundary`
  - records compact summary and boundary metadata

- `content_replacement`
  - records the exact replacement string shown to the model
  - records target tool/message identity and linked artifact refs

- `context_snapshot`
  - records context-pipeline metadata needed for reconstruction and debugging
  - does not attempt to persist a full rendered prompt

### 5.3 Why `content_replacement` Is First-Class

`artifact_ref` alone is not enough for stable resume. Replacement behavior must not change just because:

- preview formatting changes
- truncation rules change
- file path rendering changes
- budget policies are adjusted later

Therefore the transcript must persist the exact replacement text the model saw, not just the artifact pointer.

## 6. State Reconstruction Rules

Resume replay is implemented as deterministic event application, not ad hoc summary merging.

### 6.1 Required Reconstructed State

The replay layer must reconstruct:

- `Session`
- `Turn`
- `AgentStepState`
- `ToolCallRecord`
- `TranscriptMessage`
- `CompactBoundary`
- `PendingInteraction`

The following identities must remain stable across resume:

- `message_id`
- `turn_id`
- `step_id`
- `call_id`
- `boundary_id`

### 6.2 States That Must Be Restored Exactly

- pending waiting state
- compact boundary history
- tool-call to tool-result linkage
- transition history
- mode history as represented by system prompt or transition events
- replacement metadata and replay state

### 6.3 States That May Be Recomputed

- `summary_text`
- `recent_transition_reasons`
- `workspace_intelligence` projection
- `context_analysis`
- timeline and snapshot display aggregates

### 6.4 Replay Contract

Replay must stay simple:

- `message` mutates transcript only
- `tool_call` creates or updates tool-call state only
- `tool_result` completes an existing tool call by `call_id`
- `pending_interaction` sets waiting state
- `pending_resolution` resolves the waiting state
- `compact_boundary` appends a boundary record
- `session_meta` updates session metadata only

Future features like interrupt/retry/synthetic results should extend the event model instead of bypassing it.

## 7. Write Path Rules

### 7.1 Ordering

For every state mutation:

1. build event
2. append to `transcript.jsonl`
3. `flush()` and `fsync()`
4. apply event to in-memory session state
5. refresh derived projections

This keeps transcript ahead of projection and prevents "summary says it happened, transcript does not" drift.

### 7.2 Crash Tolerance

Read path must tolerate a damaged tail:

- require monotonic `seq`
- ignore an incomplete or malformed final line
- keep earlier valid events recoverable

This is especially important for Windows 7 portable/offline usage where sudden process death must not invalidate the whole session.

## 8. Component Changes

### 8.1 New Components

- `src/embedagent/transcript_store.py`
  - append/load transcript events
  - handle JSONL IO, seq validation, damaged-tail tolerance

- `src/embedagent/session_restore.py`
  - replay transcript into `Session`
  - rebuild pending interaction, compact boundaries, tool-call state, and replacements

### 8.2 Existing Components To Change

- [`src/embedagent/query_engine.py`](/D:/Claude-project/ccode-win7/src/embedagent/query_engine.py)
  - emit transcript events during loop execution

- [`src/embedagent/inprocess_adapter.py`](/D:/Claude-project/ccode-win7/src/embedagent/inprocess_adapter.py)
  - switch `resume_session()` to transcript-based restore

- [`src/embedagent/session_store.py`](/D:/Claude-project/ccode-win7/src/embedagent/session_store.py)
  - reduce responsibility to summary/index generation and loading helpers
  - stop acting as the truth source for resume

- [`src/embedagent/session.py`](/D:/Claude-project/ccode-win7/src/embedagent/session.py)
  - ensure state objects are replay-friendly and stable under persistence/reconstruction

- [`src/embedagent/context.py`](/D:/Claude-project/ccode-win7/src/embedagent/context.py)
  - restore content replacement and compact-boundary semantics from replayed state

## 9. Migration Plan

### Phase 1: Transcript Dual-Write

Add transcript persistence while keeping current summary behavior.

Deliverables:

- transcript file created for active sessions
- event append for core loop/session mutations
- no resume behavior change yet

### Phase 2: Session Replay

Build read/replay support from transcript into `Session`.

Deliverables:

- transcript can reconstruct `Session` topology
- restored session can regenerate snapshot/timeline/summary

### Phase 3: Resume Switch-Over

Move adapter/CLI/TUI/GUI resume flow to transcript truth.

Deliverables:

- `resume_session()` restores from transcript
- `summary.json` is no longer required for a valid resume

### Phase 4: Old Semantic Cleanup

Remove remaining summary-only truth assumptions.

Deliverables:

- summary becomes projection-only
- code paths depending on synthetic summary resume are removed or isolated

## 10. Tests

### 10.1 New Required Regression Tests

1. exact topology replay
   - resume preserves `turn_id`, `step_id`, `call_id`, `message_id`

2. replacement replay consistency
   - replacement state after resume matches pre-resume behavior

3. compact retry resume
   - compact boundary and retry transitions survive restore

4. interrupted tail tolerance
   - malformed last JSONL line does not break restore

5. resume and continue execution
   - resumed session appends new events to the same transcript correctly

6. projection rebuild from transcript
   - deleting `summary.json` still allows restore and projection rebuild

### 10.2 Existing Tests To Extend

- [`tests/test_query_engine_refactor.py`](/D:/Claude-project/ccode-win7/tests/test_query_engine_refactor.py)
- [`tests/test_inprocess_adapter_frontend_api.py`](/D:/Claude-project/ccode-win7/tests/test_inprocess_adapter_frontend_api.py)

## 11. Acceptance Criteria

This design is complete when all of the following are true:

- resume no longer depends on `summary.json` as the truth source
- pending interactions survive restore as real waiting state
- compact boundaries survive restore without being flattened into prose
- replacement state survives restore without recomputing different replacement strings
- transcript with a damaged final line can still be restored
- snapshot/timeline/summary can be rebuilt from transcript alone

## 12. Non-Goals For This Slice

This design does not yet require:

- full multi-agent persistence
- remote/bridge transcript unification
- SQLite-backed transcript storage
- large-scale compression of transcript history

These may build on the same event model later, but they are not part of this slice.

## 13. Implementation Entry Files

The first implementation round should start from:

- [`src/embedagent/query_engine.py`](/D:/Claude-project/ccode-win7/src/embedagent/query_engine.py)
- [`src/embedagent/inprocess_adapter.py`](/D:/Claude-project/ccode-win7/src/embedagent/inprocess_adapter.py)
- [`src/embedagent/session_store.py`](/D:/Claude-project/ccode-win7/src/embedagent/session_store.py)
- [`src/embedagent/session.py`](/D:/Claude-project/ccode-win7/src/embedagent/session.py)
- [`tests/test_query_engine_refactor.py`](/D:/Claude-project/ccode-win7/tests/test_query_engine_refactor.py)
- [`tests/test_inprocess_adapter_frontend_api.py`](/D:/Claude-project/ccode-win7/tests/test_inprocess_adapter_frontend_api.py)

## 14. Decision

EmbedAgent will adopt full transcript persistence for session truth and transcript replay for resume consistency.

The current summary-driven resume path is treated as an interim compatibility layer and not the target architecture.
