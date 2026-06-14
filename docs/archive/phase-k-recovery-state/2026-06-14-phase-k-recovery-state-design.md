# Phase K Recovery State Design

## Reader And Outcome

This design is for engineers changing restore, resume, session diagnostics, or frontend session snapshots.

After reading it, the engineer should know how recovery markers become replayable Agent Core state without making frontend replay, timeline logs, or one-off adapter fields into durable truth.

## Problem

EmbedAgent can already stop restore at a self-consistent transcript prefix and expose `restore_stop_reason`, consumed event count, transcript event count, operation diagnostics, runtime configuration, and compaction state.

That is useful for one resumed session, but it is not yet Pi-like durable recovery state. Pi treats recovery markers as durable session state: the log should explain not only that restore degraded once, but also when a restore attempt happened, what prefix was trusted, why replay stopped, which reducers were projected, and whether the hosted session is now operating from a partial replay.

Current gaps:

- restore diagnostics are adapter/session fields, not reducer-backed state
- session snapshots cannot show a history of recovery attempts
- there is no durable `recovery_marker` event family
- future agents cannot distinguish "healthy restore never needed recovery" from "recovery happened and produced a trusted prefix"
- restore-related diagnostics are not aligned with the Phase A/H/J reducer pattern

## Goals

- Add a transcript-backed `RecoveryStateReducer`.
- Emit safe `recovery_marker` events after hosted resume attempts.
- Expose reducer-backed `recovery_state` in restore results, managed sessions, protocol snapshots, and session snapshots.
- Keep `restore_stop_reason` and consumed/transcript counts as compatibility summary fields.
- Make recovery state diagnostic/read-model state only.
- Keep Python 3.8 compatibility and avoid new dependencies.
- Preserve current restore behavior, including best-effort and stop-at-prefix semantics.

## Non-Goals

- Do not change transcript validation or restore stop rules.
- Do not automatically repair damaged transcript tails beyond existing `TranscriptStore` behavior.
- Do not retry tool calls from recovery state.
- Do not make frontend replay authoritative.
- Do not make recovery state drive mode selection, tool activation, permission policy, context selection, extension loading, or workflow state.
- Do not add online telemetry or external observability services.

## Design Alternatives

### Option A: Extend `ManagedSession` Fields Only

Keep adding restore diagnostics to `ManagedSession` and snapshots.

This is small, but it keeps recovery as live adapter state. It does not give future restores or agents a durable session-log explanation of recovery attempts.

### Option B: Add `RecoveryStateReducer` And `recovery_marker`

Emit a safe `recovery_marker` event after hosted resume and reduce transcript events into a serializable read model.

This is the recommended option. It matches Phase A/H/J, keeps recovery observable after restart, and does not change restore mechanics.

### Option C: Rewrite Restore Around A Unified SessionLog Reducer

Replace the current `SessionRestorer` replay loop with a complete reducer registry.

This is the long-term direction, but it is too broad for Phase K. It would mix restore behavior changes with diagnostic state work.

## Chosen Design

Phase K uses Option B.

Add `src/embedagent/recovery_state.py` with:

- `RecoveryMarkerRecord`
- `RecoveryState`
- `RecoveryStateReducer`

The reducer consumes transcript events with type `recovery_marker`. It validates safe fields, deduplicates by `marker_id`, records malformed/duplicate diagnostics, and exposes latest marker plus aggregate counts.

## Event Payload Shape

`recovery_marker` is a diagnostic event emitted by hosted resume paths after restore has produced a trusted session prefix.

Payload:

- `marker_id`
- `created_at`
- `reason`
- `status`
  - `clean`
  - `partial`
  - `degraded`
- `current_mode`
- `trusted_event_count`
- `transcript_event_count`
- `stop_reason`
- `skipped_count`
- `skip_reasons`
- `operation_summary`
  - `total_count`
  - `started_count`
  - `finished_count`
  - `interrupted_count`
- `compaction_summary`
  - `boundary_count`
  - `latest_boundary_id`
- `runtime_summary`
  - `active_tool_count`
  - `resource_revision`
  - `model_profile_name`
- `metadata`

The event must not contain prompts, full messages, raw tool outputs, file contents, API keys, or extension code.

## Status Semantics

- `clean`: consumed event count equals transcript event count and `stop_reason` is empty
- `partial`: a restore stop reason exists but a trusted prefix was recovered
- `degraded`: transcript was missing or no trusted prefix could be recovered in hosted paths

Phase K emits markers only after successful `SessionRestorer.restore(...)` calls in hosted resume. Existing missing-transcript handling remains unchanged unless a hosted path already materializes a degraded snapshot.

## Snapshot Projection

`ManagedSession` gains `recovery_state`.

`InProcessAdapter` refreshes it from transcript events in the same snapshot/session lifecycle paths as runtime config and compaction state.

`SessionSnapshotProjector` exposes `recovery_state`.

`src/embedagent/protocol.SessionSnapshot` and `src/embedagent/core.adapter` preserve the field for frontend shells.

Frontend shells may display this for restore/debug visibility, but must not use it as execution policy.

## Restore

`SessionRestorer` reduces recovery markers from the consumed transcript prefix and exposes `SessionRestoreResult.recovery_state`.

When `InProcessAdapter.resume_session(...)` emits a new `recovery_marker`, it refreshes `ManagedSession.recovery_state` from the full transcript so the snapshot includes the marker for the just-completed resume attempt.

## Testing

Add focused tests for:

- reducer serializes a structured recovery marker
- reducer deduplicates duplicate `marker_id` and records diagnostics
- reducer accepts empty/no-marker transcripts
- `SessionRestorer` exposes reducer-backed recovery state from existing marker events
- `InProcessAdapter.resume_session(...)` appends a `recovery_marker` and session snapshots expose `recovery_state`
- protocol/core snapshot conversion preserves `recovery_state`

## Documentation

Update active source-of-truth docs to state Phase K is complete after implementation:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`
- `docs/pi-inspired-agent-core-blueprint.md`

Archive this design and the implementation plan under `docs/archive/phase-k-recovery-state/` when complete.

## Acceptance Criteria

- `recovery_marker` events carry safe restore/reducer metadata.
- `RecoveryStateReducer` is the only durable recovery read model.
- Restore results and session snapshots expose `recovery_state`.
- Existing restore behavior remains unchanged.
- Focused tests, harness tests, fast tests, ruff, black, and diff check pass.
