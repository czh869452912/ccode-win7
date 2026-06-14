# Phase J Structured Compaction State Design

## Reader And Outcome

This design is for engineers changing Agent Core session durability, context assembly, or restore behavior.

After reading it, the engineer should be able to implement Phase J without turning compaction into a second history source or changing the current compression algorithm.

## Problem

EmbedAgent already records `compact_boundary` events and restores them into live `Session.compact_boundaries`. That is enough to resume safely, but it is not yet Pi-like durable state.

The current boundary mostly records a summary string, compacted turn count, preserved message ids, and a small metadata bag. It does not provide a stable reducer-backed projection that explains:

- which message segment was preserved
- tokens/characters before and after compaction
- summarized/recent turn counts
- file activity observed in compacted context
- evidence/result references that survived as external artifacts
- whether an extension contributed the summary
- whether restore saw an interrupted or malformed compaction state

## Goals

- Add a structured `CompactionStateReducer` over transcript events.
- Keep `compact_boundary` as the durable event type; add safe structured fields to its payload.
- Expose reducer-backed `compaction_state` in managed session snapshots.
- Keep `Session.compact_boundaries` as live compatibility state for context assembly.
- Preserve current compaction behavior and context selection semantics.
- Keep payloads safe: no full prompt bodies, no raw file contents, no raw tool outputs, no credentials.
- Keep Python 3.8 compatibility and avoid new dependencies.

## Non-Goals

- Do not rewrite the context compaction algorithm.
- Do not add online model summarization or remote compaction services.
- Do not make frontend compaction state authoritative.
- Do not make project extensions execute during compaction.
- Do not replace `ContextManager` policy in this phase.

## Design Alternatives

### Option A: Extend `Session.compact_boundaries` Only

Add more fields to the live `CompactBoundary` dataclass and keep restore as the only source of projection.

This is small, but it keeps compaction as live mutable session state instead of durable reducer state. It does not move toward Pi's "session log as all durable agent state" design.

### Option B: Add A Dedicated `CompactionStateReducer`

Keep emitting `compact_boundary`, enrich the payload, and reduce transcript events into a serializable read model. Session snapshots can expose that reducer output, while live `Session.compact_boundaries` remains compatibility state.

This is the recommended option. It is a deep module with a small surface, aligns with Phase A/H patterns, and does not force a risky context rewrite.

### Option C: Replace Compaction With A New Session Tree

Introduce branch/tree compaction state and migrate context assembly to read from that tree.

This is closer to Pi's full session tree direction, but it is too large for one safe slice. It would mix algorithm changes, restore changes, and frontend changes.

## Chosen Design

Phase J uses Option B.

Add `src/embedagent/compaction_state.py` with:

- `CompactionBoundaryRecord`
- `CompactionState`
- `CompactionStateReducer`

The reducer consumes schema v1/v2 transcript events with type `compact_boundary`. It validates safe fields, deduplicates by `boundary_id`, records malformed events as diagnostics, and exposes latest boundary plus aggregate counters.

## Event Payload Shape

`compact_boundary` keeps existing fields and adds optional structured fields:

- `boundary_id`
- `summary_text`
- `compacted_turn_count`
- `created_at`
- `mode_name`
- `preserved_head_message_id`
- `preserved_tail_message_id`
- `metadata`
- `token_counts`
  - `approx_before`
  - `approx_after`
- `message_counts`
  - `before`
  - `after`
  - `summarized_turns`
  - `recent_turns`
- `file_activity`
  - `read_files`
  - `modified_files`
- `evidence_refs`
- `extension_summary`

All fields are best-effort diagnostics. Restore must tolerate old events that lack the new fields.

## File Activity

Phase J derives file activity from existing safe context analysis and replacement metadata:

- `read_files` comes from `assembly.analysis.top_hot_files[*].path`
- `modified_files` is empty in this phase unless already present in future metadata
- `evidence_refs` comes from `assembly.replacements[*].stored_refs`

This keeps Phase J safe and avoids parsing raw tool output.

## Snapshot Projection

`ManagedSession` gains `compaction_state`.

`InProcessAdapter` refreshes it from the transcript in the same places it refreshes runtime config:

- session creation
- resource reload / snapshot refresh paths that already load transcript state
- resume

`SessionSnapshotProjector` exposes `compaction_state` as diagnostic/read-model state. Frontends may display it, but must not use it as execution policy.

## Restore

`SessionRestorer` continues to rebuild live `Session.compact_boundaries` for context compatibility.

The new reducer runs independently over the validated consumed transcript prefix. Malformed compaction events that stop restore still remain visible in restore diagnostics, while reducer diagnostics explain skipped malformed/duplicate boundary records.

## Testing

Add focused tests for:

- reducer serializes a structured boundary and latest record
- reducer accepts legacy compact boundary payloads
- reducer deduplicates duplicate `boundary_id` and records diagnostics
- QueryEngine emits structured compaction payload fields
- InProcessAdapter snapshots expose reducer-backed `compaction_state`
- restore projects reducer-backed compaction state from transcript events

## Documentation

Update active source-of-truth docs to state Phase J is complete after implementation:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/frontend-protocol.md`
- `docs/pi-inspired-agent-core-blueprint.md`

Archive this design and the implementation plan under `docs/archive/phase-j-structured-compaction/` when complete.

## Acceptance Criteria

- `compact_boundary` events carry structured safe metadata.
- `CompactionStateReducer` is the only durable compaction read model.
- Session snapshots expose `compaction_state`.
- Existing context compaction behavior remains unchanged.
- Old compact boundary events remain restorable.
- Focused tests, harness tests, fast tests, ruff, black, and diff check pass.
