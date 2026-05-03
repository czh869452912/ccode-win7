---
phase: 5
slug: 05-session-infrastructure
status: completed
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-03
updated: 2026-05-03
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5 |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_transcript_store.py tests/test_session_restore.py tests/test_session_history.py -v` |
| **Full suite command** | `uv run pytest tests/test_transcript_store.py tests/test_session_restore.py tests/test_session_history.py tests/test_session_integration.py tests/test_session_performance.py tests/test_session_fault_injection.py -v` |
| **Estimated runtime** | ~15 seconds (quick), ~30 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_transcript_store.py tests/test_session_restore.py tests/test_session_history.py -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not slow and not gui" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | SESS-01 | T-05-01 | Schema v2 write with typed messages | unit | `pytest tests/test_transcript_store.py::TestTranscriptStore::test_append_event_schema_v2_format -v` | Yes | Green |
| 5-01-02 | 01 | 1 | SESS-01 | T-05-02 | Backward-compatible v1 transcript reading | unit | `pytest tests/test_transcript_store.py::TestTranscriptStore::test_load_events_normalizes_schema_v1 -v` | Yes | Green |
| 5-01-03 | 01 | 1 | SESS-01 | T-05-02 | Mixed v1/v2 events readable | unit | `pytest tests/test_transcript_store.py::TestTranscriptStore::test_mixed_schema_v1_and_v2_readable -v` | Yes | Green |
| 5-01-04 | 01 | 1 | SESS-02 | — | Parent message chain validation (valid) | unit | `pytest tests/test_transcript_store.py::TestTranscriptStore::test_validate_transcript_chain_valid -v` | Yes | Green |
| 5-01-05 | 01 | 1 | SESS-02 | — | Parent message chain detects breaks | unit | `pytest tests/test_transcript_store.py::TestTranscriptStore::test_validate_transcript_chain_broken -v` | Yes | Green |
| 5-01-06 | 01 | 1 | SESS-03 | T-05-01 | Lifecycle events emitted (best-effort, non-blocking) | integration | `pytest tests/test_transcript_store.py -v` | Yes | Green |
| 5-02-01 | 02 | 1 | SESS-04 | T-05-05 | Best-effort skips corrupted record | unit | `pytest tests/test_session_restore.py::TestSessionRestorer::test_best_effort_skips_corrupted_record -v` | Yes | Green |
| 5-02-02 | 02 | 1 | SESS-04 | T-05-05 | Best-effort skips multiple bad records | unit | `pytest tests/test_session_restore.py::TestSessionRestorer::test_best_effort_skips_multiple_bad_records -v` | Yes | Green |
| 5-02-03 | 02 | 1 | SESS-04 | T-05-06 | Best-effort continues after missing parent | unit | `pytest tests/test_session_restore.py::TestSessionRestorer::test_best_effort_continues_after_missing_parent -v` | Yes | Green |
| 5-02-04 | 02 | 1 | SESS-04 | — | Strict mode stops on first error | unit | `pytest tests/test_session_restore.py::TestSessionRestorer::test_strict_mode_stops_on_first_error -v` | Yes | Green |
| 5-02-05 | 02 | 1 | SESS-04 | — | Empty events raises in best-effort | unit | `pytest tests/test_session_restore.py::TestSessionRestorer::test_best_effort_empty_events_raises -v` | Yes | Green |
| 5-02-06 | 02 | 1 | SESS-04 | T-05-05 | Duplicate step ID skipped | unit | `pytest tests/test_session_restore.py::TestSessionRestorer::test_best_effort_duplicate_step_id_skipped -v` | Yes | Green |
| 5-02-07 | 02 | 1 | SESS-04 | T-05-06 | Skip reasons reported with metadata | unit | `pytest tests/test_session_restore.py::TestSessionRestorer::test_best_effort_reports_all_skip_reasons -v` | Yes | Green |
| 5-03-01 | 03 | 2 | SESS-05 | T-05-09 | Flat timeline returns items array | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_flat_timeline_returns_items_array -v` | Yes | Green |
| 5-03-02 | 03 | 2 | SESS-05 | T-05-09 | User item structure correct | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_flat_timeline_user_item_structure -v` | Yes | Green |
| 5-03-03 | 03 | 2 | SESS-05 | T-05-09 | Assistant item structure correct | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_flat_timeline_assistant_item_structure -v` | Yes | Green |
| 5-03-04 | 03 | 2 | SESS-05 | T-05-09 | Tool use item structure correct | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_flat_timeline_tool_use_item -v` | Yes | Green |
| 5-03-05 | 03 | 2 | SESS-05 | T-05-09 | Tool result item structure correct | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_flat_timeline_tool_result_item -v` | Yes | Green |
| 5-03-06 | 03 | 2 | SESS-05 | T-05-11 | Parent chain linking correct | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_flat_timeline_parent_chain -v` | Yes | Green |
| 5-03-07 | 03 | 2 | SESS-05 | — | Empty session returns empty items | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_flat_timeline_empty_session -v` | Yes | Green |
| 5-03-08 | 03 | 2 | SESS-05 | — | Integrity info passed through | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_flat_timeline_integrity_info -v` | Yes | Green |
| 5-03-09 | 03 | 2 | SESS-05 | — | Backward compatible with build() | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_flat_timeline_backward_compatible_with_build -v` | Yes | Green |
| 5-03-10 | 03 | 2 | SESS-05 | — | Old build() method unchanged | unit | `pytest tests/test_session_history.py::TestSessionHistoryAssemblerFlatTimeline::test_old_build_method_unchanged -v` | Yes | Green |
| 5-04-01 | 04 | 3 | SESS-01 | — | Schema v2 write and load roundtrip | integration | `pytest tests/test_session_integration.py::TestSessionIntegration::test_schema_v2_write_and_load_roundtrip -v` | Yes | Green |
| 5-04-02 | 04 | 3 | SESS-01 | — | Restore from schema v2 events | integration | `pytest tests/test_session_integration.py::TestSessionIntegration::test_restore_from_schema_v2_events -v` | Yes | Green |
| 5-04-03 | 04 | 3 | SESS-05 | — | Flat timeline from restored session | integration | `pytest tests/test_session_integration.py::TestSessionIntegration::test_flat_timeline_from_restored_session -v` | Yes | Green |
| 5-04-04 | 04 | 3 | SESS-04 | T-05-12 | Full pipeline with corruption handling | integration | `pytest tests/test_session_integration.py::TestSessionIntegration::test_full_pipeline_best_effort_with_corruption -v` | Yes | Green |
| 5-04-05 | 04 | 3 | SESS-02 | — | Parent chain validation on real transcript | integration | `pytest tests/test_session_integration.py::TestSessionIntegration::test_parent_chain_validation_on_real_transcript -v` | Yes | Green |
| 5-04-06 | 04 | 3 | SESS-02 | — | Chain detects break | integration | `pytest tests/test_session_integration.py::TestSessionIntegration::test_transcript_chain_detects_break -v` | Yes | Green |
| 5-04-07 | 04 | 3 | SESS-01 | — | Multiple tool calls in one step | integration | `pytest tests/test_session_integration.py::TestSessionIntegration::test_multiple_tool_calls_in_one_step -v` | Yes | Green |
| 5-04-08 | 04 | 3 | SESS-01 | — | Backward compatibility schema v1 restore | integration | `pytest tests/test_session_integration.py::TestSessionIntegration::test_backward_compatibility_schema_v1_restore -v` | Yes | Green |
| 5-04-09 | 04 | 3 | SESS-01 | — | Append performance 100 events | performance | `pytest tests/test_session_performance.py::TestSessionPerformance::test_append_performance_100_events -v` | Yes | Green |
| 5-04-10 | 04 | 3 | SESS-01 | — | Load performance 1000 events | performance | `pytest tests/test_session_performance.py::TestSessionPerformance::test_load_performance_1000_events -v` | Yes | Green |
| 5-04-11 | 04 | 3 | SESS-04 | — | Restore performance 1000 events | performance | `pytest tests/test_session_performance.py::TestSessionPerformance::test_restore_performance_1000_events -v` | Yes | Green |
| 5-04-12 | 04 | 3 | SESS-05 | — | Flat timeline performance 1000 items | performance | `pytest tests/test_session_performance.py::TestSessionPerformance::test_flat_timeline_performance_1000_items -v` | Yes | Green |
| 5-04-13 | 04 | 3 | SESS-04 | — | Large session memory usage | performance | `pytest tests/test_session_performance.py::TestSessionPerformance::test_large_session_memory_usage -v` | Yes | Green |
| 5-04-14 | 04 | 3 | SESS-04 | T-05-12 | Repair truncated JSON at end | fault | `pytest tests/test_session_fault_injection.py::TestSessionFaultInjection::test_repair_truncated_json_at_end -v` | Yes | Green |
| 5-04-15 | 04 | 3 | SESS-04 | T-05-13 | Repair corrupted middle record | fault | `pytest tests/test_session_fault_injection.py::TestSessionFaultInjection::test_repair_corrupted_middle_record -v` | Yes | Green |
| 5-04-16 | 04 | 3 | SESS-04 | T-05-13 | Restore with duplicate turn ID | fault | `pytest tests/test_session_fault_injection.py::TestSessionFaultInjection::test_restore_with_duplicate_turn_id -v` | Yes | Green |
| 5-04-17 | 04 | 3 | SESS-04 | — | Restore with missing parent in chain | fault | `pytest tests/test_session_fault_injection.py::TestSessionFaultInjection::test_restore_with_missing_parent_in_chain -v` | Yes | Green |
| 5-04-18 | 04 | 3 | SESS-04 | — | Restore with stale interaction | fault | `pytest tests/test_session_fault_injection.py::TestSessionFaultInjection::test_restore_with_stale_interaction -v` | Yes | Green |
| 5-04-19 | 04 | 3 | SESS-04 | — | Empty events raises | fault | `pytest tests/test_session_fault_injection.py::TestSessionFaultInjection::test_restore_empty_events_raises -v` | Yes | Green |
| 5-04-20 | 04 | 3 | SESS-04 | — | Strict mode fails fast | fault | `pytest tests/test_session_fault_injection.py::TestSessionFaultInjection::test_strict_mode_fails_fast -v` | Yes | Green |
| 5-04-21 | 04 | 3 | SESS-04 | T-05-12 | Corrupted transcript file loads valid prefix | fault | `pytest tests/test_session_fault_injection.py::TestSessionFaultInjection::test_corrupted_transcript_file_loads_valid_prefix -v` | Yes | Green |

*Status: Green = passing, Red = failing, Yellow = partial*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:

- [x] `tests/conftest.py` — shared fixtures exist
- [x] `pyproject.toml` — pytest configuration with markers
- [x] `tests/test_transcript_store.py` — schema v2 tests
- [x] `tests/test_session_restore.py` — best-effort restore tests
- [x] `tests/test_session_history.py` — flat timeline tests
- [x] `tests/test_session_integration.py` — end-to-end pipeline tests
- [x] `tests/test_session_performance.py` — performance benchmarks
- [x] `tests/test_session_fault_injection.py` — corruption resilience tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| *(none)* | | | |

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-03

---
*Phase: 05-session-infrastructure*
*Validated: 2026-05-03*
