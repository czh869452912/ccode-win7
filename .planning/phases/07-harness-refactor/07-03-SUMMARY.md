---
phase: 07-harness-refactor
plan: 03
subsystem: harness

tags:
  - guard
  - loop-guard
  - safety
  - runaway-loop
  - user-override

requires:
  - 07-01
  - 07-02

provides:
  - LoopGuard with repeated tool call detection
  - Consecutive failure tracking with configurable threshold
  - User override mechanism for guard decisions

affects:
  - guard
  - query-engine

tech-stack:
  added: []
  patterns:
    - "Repeated tool call history for runaway loop detection"
    - "User override flag to bypass guard decisions"
    - "Parallel batch guard exemption for legitimate parallel usage"

key-files:
  created:
    - tests/test_harness_guard_safety.py
  modified:
    - src/embedagent/guard.py
    - src/embedagent/query_engine.py

key-decisions:
  - "Repeated tool call guard tracks tool_call_history separately from failure tracking"
  - "Default max_consecutive_failures lowered from 3 to 2 for faster failure detection"
  - "Parallel batches exempt from should_block() to avoid blocking legitimate parallel reads"
  - "User override disables both should_block() and should_stop()"

requirements-completed:
  - HARN-03

duration: 20min
completed: 2026-05-03
---

# Phase 7 Plan 3: Guard-Based Safety Summary

**Enhanced LoopGuard detects runaway loops and consecutive failures while allowing user override**

## Performance

- **Duration:** 20 min
- **Started:** 2026-05-03T00:20:00Z
- **Completed:** 2026-05-03T00:40:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Enhanced LoopGuard with runaway loop detection:
  - Added `tool_call_history` tracking all executed tool names
  - `should_block()` detects when the same tool is called `max_repeated_tool_calls` (default 3) times consecutively
  - Fixed `should_block()` to check repeated tool calls BEFORE the `last_failed_action_key` early return
- Added consecutive failure tracking:
  - Default `max_consecutive_failures` changed from 3 to 2 for faster failure detection
  - `failure_count` tracks total failures (resets on success)
  - `should_stop()` uses `failure_count` threshold
- Added user override mechanism:
  - `user_override()` method sets `_user_override = True`
  - When overridden, both `should_block()` and `should_stop()` return False
- Fixed parallel batch interaction:
  - In query engine's parallel batch loop, removed `should_block()` check during batch execution
  - Prevents legitimate parallel tool usage (e.g., 3 parallel file reads) from triggering false guard stops
  - `should_stop()` (consecutive failures) still checked during parallel batches
- Created 5 passing tests for guard safety behavior

## Task Commits

1. **Task 1-2: Completion signal and guard safety** - `3bdd671` (feat)

## Files Created/Modified

- `src/embedagent/guard.py` - Enhanced LoopGuard with repeated tool calls, consecutive failures, user override
- `src/embedagent/query_engine.py` - Skip should_block() during parallel batch execution
- `tests/test_harness_guard_safety.py` - 5 tests for guard safety behavior (new file)

## Decisions Made

- Repeated tool call guard moved before the `last_failed_action_key` early return so successful repeated calls are also detected
- Default `max_consecutive_failures=2` provides faster protection without being overly aggressive
- Parallel batches exempt from `should_block()` because parallel identical tool calls are legitimate (reading multiple files)
- Guard's `stop_reason()` reports "repeated tool calls: {name}" for runaway loops

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Parallel batches falsely trigger repeated tool call guard**
- **Found during:** Task 2 (running full test suite)
- **Issue:** 3 parallel `read_file` calls in a single batch triggered `should_block()`, causing 2 existing tests to fail with `guard_stop` instead of `completed`
- **Fix:** In query engine's parallel batch loop, removed `should_block()` check during batch execution. `should_stop()` (consecutive failures) is still checked. Runaway loops with parallel batches are still caught on subsequent turns/batches.
- **Files modified:** `src/embedagent/query_engine.py`

**2. [Rule 2 - Auto-add] should_block() early return blocked runaway loop detection for successful calls**
- **Found during:** Task 2 (running guard safety tests)
- **Issue:** `should_block()` had `if not self.last_failed_action_key: return False` before the repeated tool call check, so successful repeated calls were never blocked
- **Fix:** Moved repeated tool call check to the top of `should_block()`, before the early return
- **Files modified:** `src/embedagent/guard.py`

## Issues Encountered

- 2 existing tests (`test_query_engine_keeps_discarded_parallel_results_out_of_guard_stop`, `test_query_engine_discards_later_batches_after_parallel_discard`) failed after adding repeated tool call guard
- Resolution: Modified query engine to skip `should_block()` during parallel batch execution

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- [x] `src/embedagent/guard.py` contains enhanced `LoopGuard` with `tool_call_history`
- [x] `src/embedagent/guard.py` contains `user_override()` method
- [x] `tests/test_harness_guard_safety.py` exists with 5 tests
- [x] Commit `3bdd671` exists
- [x] All 650 tests pass (5 new + 4 completion signal + 641 existing, 11 deselected)

## Next Phase Readiness

- Guard system now protects against runaway loops and consecutive failures
- User override provides escape hatch for legitimate repeated operations
- Ready for integration with frontend guard UI

---
*Phase: 07-harness-refactor*
*Completed: 2026-05-03*
