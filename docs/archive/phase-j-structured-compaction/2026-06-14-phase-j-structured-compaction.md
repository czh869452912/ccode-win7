# Phase J Structured Compaction State Implementation Plan

## Objective

Implement Phase J by turning compact boundaries into a reducer-backed diagnostic state:

- keep `compact_boundary` as the transcript event
- enrich emitted payloads with safe structured compaction metadata
- add `CompactionStateReducer`
- expose `compaction_state` through restore, managed sessions, and snapshots
- keep current context compaction behavior unchanged

## Constraints

- Python 3.8 syntax only.
- No new runtime dependencies.
- No raw prompt bodies, file contents, tool output, credentials, or extension code execution in compaction metadata.
- `Session.compact_boundaries` stays live compatibility state; `CompactionStateReducer` is the durable read model.

## Task 1: Reducer Tests

Add `tests/test_compaction_state.py`.

Tests:

- `test_reducer_projects_structured_boundary`
  - Given a `compact_boundary` event with structured fields.
  - Assert latest boundary, counts, file activity, evidence refs, and diagnostics.
  - Assert `to_dict()` is JSON-serializable.
- `test_reducer_accepts_legacy_boundary_payload`
  - Given a compact boundary with only old fields and `metadata.approx_tokens`.
  - Assert fallback token/message counts are populated.
- `test_reducer_deduplicates_boundary_id`
  - Given two events with the same `boundary_id`.
  - Assert only the first boundary is retained and diagnostics record the duplicate.

Run:

```bash
uv run pytest tests/test_compaction_state.py -v
```

Expected first result: fail because `embedagent.compaction_state` does not exist.

## Task 2: Reducer Implementation

Add `src/embedagent/compaction_state.py`.

Implementation:

- `CompactionBoundaryRecord`
- `CompactionState`
- `CompactionStateReducer`

Reducer behavior:

- consume only `compact_boundary` events
- require a non-empty `boundary_id`; malformed records become diagnostics
- dedupe duplicate `boundary_id`; keep first record
- preserve safe structured fields
- fallback old payloads:
  - `metadata.approx_tokens` -> `token_counts.approx_after`
  - `compacted_turn_count` -> `message_counts.summarized_turns`
- return stable dictionaries with latest boundary, all boundaries, aggregate counts, and diagnostics

Run:

```bash
uv run pytest tests/test_compaction_state.py -v
```

## Task 3: Structured Compact Boundary Emission

Update `src/embedagent/query_engine.py`.

Add small helpers used by `_maybe_record_compact_boundary()`:

- token counts from `assembly.stats` and `assembly.approx_tokens`
- message counts from `assembly.stats`, `assembly.messages`, `assembly.summarized_turns`, and `assembly.recent_turns`
- file activity from `assembly.analysis.top_hot_files[*].path`
- evidence refs from `assembly.replacements[*].stored_refs`

Update `tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_persists_compact_boundary_event_for_restore` to assert:

- `token_counts.approx_after`
- `message_counts.summarized_turns`
- `message_counts.recent_turns`
- `file_activity.read_files`
- `evidence_refs`
- restored `compaction_state`

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_persists_compact_boundary_event_for_restore -v
```

## Task 4: Restore And Runtime Projection

Update:

- `src/embedagent/session_restore.py`
- `src/embedagent/session_runtime.py`
- `src/embedagent/session_projector.py`
- `src/embedagent/inprocess_adapter.py`

Implementation:

- add `compaction_state` to `SessionRestoreResult`
- reduce over `events[:consumed_event_count]`
- add `ManagedSession.compaction_state`
- refresh `ManagedSession.compaction_state` anywhere runtime config is refreshed for snapshots/session lifecycle
- expose `compaction_state` in `SessionSnapshotProjector`

Tests:

- add restore assertion in `tests/test_session_restore.py`
- add snapshot assertion in `tests/test_inprocess_adapter_frontend_api.py`

Run focused tests:

```bash
uv run pytest tests/test_session_restore.py::TestSessionRestorer::test_restore_projects_compaction_state tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApi::test_session_snapshot_includes_context_analysis_fields -v
```

## Task 5: Documentation

Update active docs:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/frontend-protocol.md`
- `docs/pi-inspired-agent-core-blueprint.md`

Archive Phase J working docs:

- move design and plan to `docs/archive/phase-j-structured-compaction/`

## Task 6: Verification

Run:

```bash
uv run pytest tests/test_compaction_state.py tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_persists_compact_boundary_event_for_restore tests/test_session_restore.py::TestSessionRestorer::test_restore_projects_compaction_state tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApi::test_session_snapshot_includes_context_analysis_fields -v
uv run pytest tests/ -m harness -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run ruff check src/ tests/
uv run black --check src/ tests/
git diff --check
```

## Task 7: Commit And Integrate

Commit implementation:

```bash
git add src tests docs AGENTS.md README.md
git commit -m "feat: add structured compaction state"
```

Merge back to `main` after verification.
