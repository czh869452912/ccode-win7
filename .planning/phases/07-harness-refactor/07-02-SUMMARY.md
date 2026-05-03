---
phase: 07-harness-refactor
plan: 02
subsystem: harness

tags:
  - completion-signal
  - max-turns
  - query-engine

requires:
  - 07-01

provides:
  - Completion signal detection via _is_completion_signal()
  - Soft max_turns limit (guard rail, not hard stop)
  - finish_reason-based completion recognition

affects:
  - query-engine
  - loop-termination

tech-stack:
  added: []
  patterns:
    - "Agent self-assesses completion via finish_reason"
    - "max_turns as soft guard rail"

key-files:
  created:
    - tests/test_harness_completion_signal.py
  modified:
    - src/embedagent/query_engine.py

key-decisions:
  - "Completion signal checks finish_reason in ('completed', 'stop') or empty actions"
  - "Existing no-actions check generalized to _is_completion_signal() for future extensibility"
  - "max_turns transition message changed to English for consistency"

requirements-completed:
  - HARN-02

duration: 20min
completed: 2026-05-03
---

# Phase 7 Plan 2: Completion Signal Summary

**Agent completion signal detection with soft max_turns limit — agent finishes naturally when work is done rather than hitting an arbitrary turn ceiling**

## Performance

- **Duration:** 20 min
- **Started:** 2026-05-03T00:00:00Z
- **Completed:** 2026-05-03T00:20:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `_is_completion_signal()` to QueryEngine that detects completion via:
  - `finish_reason in ("completed", "stop")`
  - No tool calls requested (`not reply.actions`)
- Updated `_run_loop()` to use `_is_completion_signal()` instead of bare `not reply.actions` check
- Made max_turns a soft limit: loop ends early on completion signal; max_turns only enforced when no signal detected
- Updated max_turns transition message from Chinese to English: "reached max turns without completion signal"
- Created 4 passing tests for completion signal behavior

## Task Commits

1. **Task 1-2: Completion signal and guard safety** - `3bdd671` (feat)

## Files Created/Modified

- `src/embedagent/query_engine.py` - Added `_is_completion_signal()`, updated completion check, updated max_turns message
- `tests/test_harness_completion_signal.py` - 4 tests for completion signal detection (new file)

## Decisions Made

- `_is_completion_signal()` is a dedicated method for future extensibility (can add content-based markers later)
- Existing `not reply.actions` behavior preserved as fallback within `_is_completion_signal()`
- Transition messages standardized to English for consistency with rest of codebase

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

- None.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- [x] `src/embedagent/query_engine.py` contains `_is_completion_signal`
- [x] `tests/test_harness_completion_signal.py` exists with 4 tests
- [x] Commit `3bdd671` exists
- [x] All 650 tests pass (4 new + 646 existing, 11 deselected)

## Next Phase Readiness

- Completion signal enables agent-driven termination
- Ready for guard-based safety enhancements

---
*Phase: 07-harness-refactor*
*Completed: 2026-05-03*
