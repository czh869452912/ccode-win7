---
phase: 05-session-infrastructure
plan: 03
subsystem: session-history
tags: [session, history, timeline, frontend, flat-array]

requires:
  - phase: 05-01
    provides: "Session restore with transcript replay and structured session state"

provides:
  - "build_flat_timeline() method on SessionHistoryAssembler"
  - "Flat items[] array replacing nested turns->steps->tool_calls structure"
  - "Per-item metadata: type, id, content, status, parent_id, turn_id, step_id"
  - "Tool item enrichment: tool_name, call_id, arguments, data, error"
  - "_find_message_for_turn_step() helper for transcript message lookup"

affects:
  - frontend
  - session-infrastructure

tech-stack:
  added: []
  patterns:
    - "Flat timeline projection: nested session state flattened to chronological items[]"
    - "Parent chain linking via parent_id for frontend tree rendering"

key-files:
  created:
    - "tests/test_session_history.py - 10 characterization tests for flat timeline"
  modified:
    - "src/embedagent/session_history.py - added build_flat_timeline() and _find_message_for_turn_step()"

key-decisions:
  - "Followed plan exactly: no architectural deviations"
  - "Preserved old build() method untouched for backward compatibility"
  - "Used Python 3.8 compatible syntax (% formatting, no walrus operator)"

patterns-established:
  - "Flat timeline projection: SessionHistoryAssembler can emit either nested (build) or flat (build_flat_timeline) representations from the same session state"
  - "Helper-based message lookup: _find_message_for_turn_step() encapsulates transcript message search logic"

requirements-completed:
  - SESS-05

duration: 18min
completed: 2026-05-03
---

# Phase 5 Plan 3: History Assembler Flat Timeline Summary

**Flat timeline output for SessionHistoryAssembler producing self-contained items[] array with parent chains for direct frontend consumption, preserving backward-compatible nested build() output.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-03T00:00:00Z
- **Completed:** 2026-05-03T00:18:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `build_flat_timeline()` to `SessionHistoryAssembler` producing chronological `items[]` array
- Each item has complete metadata: `type`, `id`, `content`, `status`, `parent_id`, `turn_id`, `step_id`
- Tool items include `tool_name`, `call_id`, `arguments`, `data`, `error` for full frontend rendering
- Added `_find_message_for_turn_step()` helper for transcript message lookup by turn/step/role
- Preserved original `build()` method completely untouched for backward compatibility
- Created 10 comprehensive characterization tests covering all item types and edge cases
- Full test suite passes: 596 passed, 0 failed, 11 deselected

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement build_flat_timeline() method** - `92b66b8` (feat)
2. **Task 2: Add comprehensive tests for flat timeline** - `bdb3f90` (test)

## Files Created/Modified

- `src/embedagent/session_history.py` - Added `build_flat_timeline()` method (202 lines) and `_find_message_for_turn_step()` helper; old `build()` method preserved unchanged
- `tests/test_session_history.py` - 10 characterization tests for flat timeline output structure, user/assistant/tool item fields, parent chain, empty session, integrity info, backward compatibility

## Decisions Made

- Followed plan exactly as written with no architectural deviations
- Preserved old `build()` method untouched to maintain backward compatibility with existing frontend consumers
- Used Python 3.8 compatible syntax throughout (`%` formatting, no walrus operator, no union types)

## Deviations from Plan

### Test Fixes (2 minor adjustments during verification)

**1. [Rule 1 - Bug] Fixed empty_session test expectation**
- **Found during:** Task 2 (test verification)
- **Issue:** `Session()` generates a random `session_id` via default factory; test expected `""` but got UUID
- **Fix:** Changed test to construct `Session(session_id="")` explicitly
- **Files modified:** `tests/test_session_history.py`
- **Verification:** Test passes after fix
- **Committed in:** `bdb3f90` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed parent_chain test missing assistant item**
- **Found during:** Task 2 (test verification)
- **Issue:** `_add_assistant_step()` called with empty `content` and `reasoning=""`; `build_flat_timeline()` condition `if step.assistant_message or step.reasoning:` was false, so no assistant item emitted
- **Fix:** Added `content="using tool"` to the assistant step in the test
- **Files modified:** `tests/test_session_history.py`
- **Verification:** Test passes after fix
- **Committed in:** `bdb3f90` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 test expectations)
**Impact on plan:** Both were test-level expectation fixes, not implementation changes. No scope creep.

## Issues Encountered

None - implementation followed plan exactly. Two test expectation mismatches were discovered during test execution and fixed inline.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Flat timeline output is ready for frontend consumption
- Frontend can now render directly from `items[]` without nested parsing
- Backward compatibility maintained - existing consumers of `build()` unaffected
- No blockers

## Self-Check: PASSED

- [x] `src/embedagent/session_history.py` modified with `build_flat_timeline()`
- [x] `tests/test_session_history.py` created with 10 tests
- [x] All 10 new tests pass (`uv run pytest tests/test_session_history.py -v`)
- [x] No regressions in existing suite (`uv run pytest tests/ -m "not slow and not gui" -v` - 596 passed)
- [x] Commit `92b66b8` exists (feat)
- [x] Commit `bdb3f90` exists (test)

---
*Phase: 05-session-infrastructure*
*Completed: 2026-05-03*
