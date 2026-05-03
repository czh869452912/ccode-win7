---
phase: 07-harness-refactor
plan: 01
subsystem: harness

tags:
  - permission-contract
  - mode-system
  - harness-injection
  - task-graph

requires: []

provides:
  - PermissionContract dataclass for mode permission modeling
  - Conditional harness context injection based on user intent
  - TaskGraph.is_empty() and from_user_request() APIs
  - 9 characterization tests for mode contract behavior

affects:
  - query-engine
  - mode-system
  - harness-runner

tech-stack:
  added: []
  patterns:
    - "Mode as permission contract instead of workflow track"
    - "Explicit work request detection before harness injection"
    - "Task graph creation gated by user intent"

key-files:
  created:
    - tests/test_harness_mode_contract.py
  modified:
    - src/embedagent/modes.py
    - src/embedagent/query_engine.py
    - src/embedagent/harness/task_graph.py
    - tests/test_query_engine_build_full_spec.py
    - tests/test_query_engine_build_lite.py
    - tests/test_query_engine_refactor.py
    - tests/test_query_engine_verify_slice.py

key-decisions:
  - "Verify mode excluded from harness injection (read-only mode, no workflow trigger)"
  - "Existing tests updated to match conditional harness behavior rather than changing implementation"
  - "Task graph creation added to submit_user_turn as secondary gate beyond harness context injection"

requirements-completed:
  - HARN-01

duration: 35min
completed: 2026-05-03
---

# Phase 7 Plan 1: Mode Permission Contract Summary

**Mode system refactored from workflow-track-based to permission-contract-based with conditional harness injection gated by explicit work request detection**

## Performance

- **Duration:** 35 min
- **Started:** 2026-05-03T00:00:00Z
- **Completed:** 2026-05-03T00:35:00Z
- **Tasks:** 4
- **Files modified:** 8

## Accomplishments

- Added `PermissionContract` dataclass to `modes.py` with `allows_tool()`, `requires_permission()`, and `is_path_writable()` methods
- Defined `MODE_CONTRACTS` for all 5 official modes (explore, spec, build, debug, verify) with read-only flags and permission-required tools
- Added `get_mode_contract()` with fallback to explore for unknown modes
- Implemented `_should_inject_harness()` in `QueryEngine` that detects explicit work requests via keyword matching and chat pattern exclusion
- Updated `initialize_session()` and `apply_mode()` to conditionally inject harness context only when user text indicates work
- Updated `submit_user_turn()` to create `TaskGraph` only on explicit work requests
- Added `is_empty()` and `from_user_request()` class methods to `TaskGraph`
- Created 9 passing characterization tests for permission contract and harness injection logic
- Updated 5 existing tests to match new conditional harness behavior

## Task Commits

All tasks committed as a single atomic commit:

1. **Task 1-4: Mode permission contract** - `33b5f24` (feat)

## Files Created/Modified

- `src/embedagent/modes.py` - Added `PermissionContract`, `MODE_CONTRACTS`, `get_mode_contract()`
- `src/embedagent/query_engine.py` - Added `_should_inject_harness()`, conditional harness injection in `initialize_session()`/`apply_mode()`/`submit_user_turn()`
- `src/embedagent/harness/task_graph.py` - Added `is_empty()` and `from_user_request()` class methods
- `tests/test_harness_mode_contract.py` - 9 characterization tests (new file)
- `tests/test_query_engine_refactor.py` - Updated harness injection test to pass work-request user_text
- `tests/test_query_engine_build_lite.py` - Updated session creation test for new conditional behavior
- `tests/test_query_engine_verify_slice.py` - Updated verify mode tests for no harness injection
- `tests/test_query_engine_build_full_spec.py` - Updated user_text to include work indicator

## Decisions Made

- Verify mode excluded from harness injection per plan specification (read-only quality mode, no workflow trigger)
- Existing tests updated to match new conditional behavior rather than changing implementation to satisfy old assertions
- `initialize_session()` and `apply_mode()` accept optional `user_text` parameter (backward compatible via default empty string)

## Deviations from Plan

None - plan executed as written. One adaptation: existing tests that asserted unconditional harness injection were updated to match the new conditional behavior, which is the intended semantic change of this plan.

## Issues Encountered

- 5 existing tests failed after implementation because they asserted unconditional harness context injection
- Resolution: Updated tests to either pass explicit work-request user_text (to trigger harness) or assert absence of harness context (for read-only modes and casual chat)

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- [x] `src/embedagent/modes.py` contains `PermissionContract`
- [x] `src/embedagent/query_engine.py` contains `_should_inject_harness`
- [x] `src/embedagent/harness/task_graph.py` contains `is_empty` and `from_user_request`
- [x] `tests/test_harness_mode_contract.py` exists with 9 tests
- [x] Commit `33b5f24` exists
- [x] All 641 tests pass (9 new + 632 existing, 11 deselected)

## Next Phase Readiness

- Mode permission contract foundation is solid
- Conditional harness injection enables safe mode entry without workflow triggers
- Ready for downstream harness refactor phases

---
*Phase: 07-harness-refactor*
*Completed: 2026-05-03*
