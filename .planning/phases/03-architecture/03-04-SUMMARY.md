---
phase: 03-architecture
plan: 04
subsystem: testing
tags: [characterization-tests, backward-compatibility, pytest, test-fixtures, architecture-documentation]

# Dependency graph
requires:
  - phase: 03-architecture
    plan: 01
    provides: "Extracted services from InProcessAdapter"
  - phase: 03-architecture
    plan: 02
    provides: "Extracted strategies from QueryEngine"
  - phase: 03-architecture
    plan: 03
    provides: "DI container and factory-based global state elimination"

provides:
  - 14 characterization tests for extracted components
  - 23 backward compatibility tests for public API stability
  - fresh_container pytest fixture for isolated DI state
  - Architecture documentation at docs/architecture-refactor.md

affects:
  - tests/test_characterization.py
  - tests/test_backward_compatibility.py
  - tests/conftest.py
  - docs/architecture-refactor.md
  - src/embedagent/__init__.py

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Characterization tests: capture current behavior to detect regression"
    - "fresh_container fixture: monkeypatch DI container for test isolation"
    - "Backward compatibility verification via import and instantiation tests"

key-files:
  created:
    - tests/test_characterization.py
    - tests/test_backward_compatibility.py
    - docs/architecture-refactor.md
  modified:
    - tests/conftest.py
    - src/embedagent/__init__.py

key-decisions:
  - "Adapted plan test code to match actual API signatures rather than adding stub methods"
  - "Characterization tests use MagicMock for external dependencies (client, tools)"
  - "Documented actual architecture state rather than target state from plan"

patterns-established:
  - "fresh_container fixture for test isolation via DI container monkeypatching"
  - "Characterization test pattern: verify extracted components are properly wired"
  - "Backward compat test pattern: verify imports, instantiation, and method existence"

requirements-completed:
  - ARCH-04
  - ARCH-05

# Metrics
duration: 9min
completed: 2026-05-02
---

# Phase 03 Plan 04: Characterization Tests and Backward Compatibility Summary

**37 new tests (14 characterization + 23 backward compatibility) with isolated DI fixtures and architecture documentation covering all Phase 3 extracted components**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-02T20:32:51Z
- **Completed:** 2026-05-02T20:42:42Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

1. **Characterization tests** (`tests/test_characterization.py`) — 14 tests covering:
   - QueryEngine constructor signature and public methods (run, stop)
   - InProcessAdapter service delegation (_session_lifecycle, _event_emitter, _workspace_files, _harness_sync)
   - QueryEngine strategy wiring (_llm_wrapper, _compaction, _turn_orchestrator)
   - EventEmitter handler invocation and exception isolation
   - WorkspaceFileService path traversal rejection
   - LLMClientRetryWrapper retry on server error and max retries exhaustion

2. **Backward compatibility tests** (`tests/test_backward_compatibility.py`) — 23 tests covering:
   - Public imports from all embedagent submodules
   - InProcessAdapter instantiation and method existence
   - QueryEngine instantiation and method existence
   - Modes API (mode_names, require_mode, initialize_modes, allowed_tools_for)
   - Global state isolation (fresh=True for registry, DI container, sanitizer, adapter)
   - MODE_REGISTRY backward-compatible alias

3. **Test fixtures** (`tests/conftest.py`) — Added:
   - `fresh_container`: Isolated DI container with monkeypatched default
   - `mock_session_store`, `mock_timeline_store`, `mock_transcript_store`

4. **Architecture documentation** (`docs/architecture-refactor.md`) — Documents:
   - Service extraction from InProcessAdapter (Plan 03-01)
   - Strategy extraction from QueryEngine (Plan 03-02)
   - Global state elimination via DI (Plan 03-03)
   - Test coverage summary
   - Backward compatibility guarantees
   - Migration guide for test authors and component authors

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Characterization tests** — `4aac9f5` (test)
2. **Task 1 GREEN: Test fixtures** — `46ad82a` (feat)
3. **Task 2 RED: Backward compatibility tests** — `9273e05` (test)
4. **Task 2 GREEN: Architecture docs and init** — `38e427c` (feat)

## Files Created/Modified

- `tests/test_characterization.py` — 14 characterization tests for extracted components
- `tests/test_backward_compatibility.py` — 23 backward compatibility tests
- `tests/conftest.py` — Added fresh_container and mock store fixtures
- `docs/architecture-refactor.md` — Architecture documentation for Phase 3 refactor
- `src/embedagent/__init__.py` — Updated docstring for public API

## Decisions Made

- **Adapted tests to actual API rather than adding stubs:** The plan's backward compatibility tests expected `InProcessAdapter()` with no args and methods `restore_session`/`add_event_handler` that don't exist. Instead of adding stub methods that would misrepresent the API, tests were adapted to use mocked dependencies and test actual methods.
- **Characterization tests document actual state:** Tests verify the architecture as it exists after Plans 03-01 through 03-03, not a target state. This provides genuine regression protection.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed EventEmitter.emit test signature**
- **Found during:** Task 1 (writing characterization tests)
- **Issue:** Plan's test called `emitter.emit("test_event", "sess-1", payload)` with 3 args, but actual API signature is `emit(event_handler, event_name, session_id, payload)` requiring 4 positional args
- **Fix:** Updated tests to pass `None` as first argument for no explicit handler
- **Files modified:** `tests/test_characterization.py`
- **Verification:** `test_emit_calls_handlers` and `test_handler_exception_isolated` pass
- **Committed in:** `4aac9f5`

**2. [Rule 1 - Bug] Fixed ModelClientError instantiation in retry tests**
- **Found during:** Task 1 (running characterization tests)
- **Issue:** Plan's test used `ModelClientError("msg", status_code=500)` but `ModelClientError` is a plain `Exception` subclass that doesn't accept `status_code` keyword
- **Fix:** Changed to `ModelClientError("HTTP 500: ...")` using string messages containing retryable HTTP codes
- **Files modified:** `tests/test_characterization.py`
- **Verification:** `test_retry_on_server_error` and `test_max_retries_exhausted` pass
- **Committed in:** `46ad82a`

**3. [Rule 1 - Bug] Fixed WorkspaceFileService path existence test**
- **Found during:** Task 1 (running characterization tests)
- **Issue:** `test_resolve_accepts_subpath` called `resolve_path("subdir/file.txt")` on non-existent path, but the service raises ValueError for missing paths unless `allow_missing=True`
- **Fix:** Added `allow_missing=True` parameter to the test call
- **Files modified:** `tests/test_characterization.py`
- **Verification:** `test_resolve_accepts_subpath` passes
- **Committed in:** `46ad82a`

**4. [Rule 3 - Blocking] Added missing QueryEngine mock dependency**
- **Found during:** Task 1 (running characterization tests)
- **Issue:** `test_query_engine_has_strategies` failed because `QueryEngine.__init__` accesses `tools.projection_db` which wasn't mocked
- **Fix:** Added `tools.projection_db = MagicMock()` to the test setup
- **Files modified:** `tests/test_characterization.py`
- **Verification:** `test_query_engine_has_strategies` passes
- **Committed in:** `46ad82a`

**5. [Rule 1 - Bug] Corrected LLM retry call count expectation**
- **Found during:** Task 1 (running characterization tests)
- **Issue:** Plan expected `call_count == 3` (initial + 2 retries) but `LLMClientRetryWrapper` with `max_retries=2` makes exactly 2 attempts total (range(2)), not 3
- **Fix:** Updated assertion to expect 2 calls
- **Files modified:** `tests/test_characterization.py`
- **Verification:** `test_max_retries_exhausted` passes
- **Committed in:** `46ad82a`

**6. [Plan Adaptation] Removed tests for non-existent InProcessAdapter methods**
- **Found during:** Task 2 (writing backward compatibility tests)
- **Issue:** Plan's tests expected `restore_session` and `add_event_handler` methods on `InProcessAdapter` which don't exist in the current codebase
- **Fix:** Removed those tests and replaced with tests for actual methods (`list_sessions`, `_event_emitter`). Added test for `submit_user_turn` on QueryEngine.
- **Files modified:** `tests/test_backward_compatibility.py`
- **Verification:** All 23 backward compatibility tests pass
- **Committed in:** `9273e05`

**7. [Plan Adaptation] Adapted no-args constructor test to use mocked dependencies**
- **Found during:** Task 2 (writing backward compatibility tests)
- **Issue:** Plan's test expected `InProcessAdapter()` with no args, but constructor requires `client` and `tools`
- **Fix:** Test uses mocked `OpenAICompatibleClient` and `ToolRuntime` to instantiate adapter, verifying the same backward compatibility intent
- **Files modified:** `tests/test_backward_compatibility.py`
- **Verification:** `test_can_instantiate_with_required_args` passes
- **Committed in:** `9273e05`

---

**Total deviations:** 7 auto-fixed (4 test bugs, 1 blocking, 2 plan adaptations)
**Impact on plan:** All fixes necessary for tests to match actual API behavior. No production code changes needed — characterization tests document existing state accurately.

## Issues Encountered

- Pre-existing flaky test `test_gui_sync.py::TestGuiSync::test_gui_backend_route_resolves_real_pending_input_waiter` fails both before and after this plan's changes (unrelated)
- Plan test code contained several API signature mismatches that required adaptation during execution

## Known Stubs

None — all tests verify actual behavior of existing code.

## Next Phase Readiness

- Phase 3 architecture refactor is complete with comprehensive test coverage
- 37 new tests provide regression protection for all extracted components
- Architecture documentation documents the new structure for future developers
- Full test suite: 546 passing, 1 pre-existing flaky failure
- Ready for Phase 4 (framework improvements)

---
*Phase: 03-architecture*
*Completed: 2026-05-02*
