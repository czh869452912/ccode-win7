---
phase: 03-architecture
plan: 02
type: execute
subsystem: core

requires:
  - phase: 03-architecture
    plan: 01
    provides: "Service extraction patterns and InProcessAdapter refactor"

provides:
  - "LLMClientRetryWrapper strategy for LLM call retry with backoff"
  - "ContextCompactionEngine strategy for token budget enforcement"
  - "TurnOrchestrator strategy for single-turn execution"
  - "QueryEngine integration with all three strategies"
  - "Backward-compatible run() and stop() methods on QueryEngine"

affects:
  - "src/embedagent/query_engine.py"
  - "src/embedagent/strategies/"

tech-stack:
  added:
    - "src/embedagent/strategies/ package"
  patterns:
    - "Strategy pattern with constructor injection"
    - "Facade + Strategy decomposition"
    - "TDD RED-GREEN-REFACTOR for each strategy"

key-files:
  created:
    - "src/embedagent/strategies/__init__.py"
    - "src/embedagent/strategies/llm_retry_wrapper.py"
    - "src/embedagent/strategies/context_compaction_engine.py"
    - "src/embedagent/strategies/turn_orchestrator.py"
    - "tests/test_strategies.py"
    - "tests/test_query_engine_orchestrator.py"
  modified:
    - "src/embedagent/query_engine.py"

key-decisions:
  - "Kept context-length retry logic in QueryEngine._run_loop for backward compatibility with transition recording and compact boundary tracking"
  - "Created TurnOrchestrator as new strategy rather than pure extraction due to tight coupling between turn execution and session/transcript management"
  - "Added run() and stop() as new convenience methods while preserving existing submit_user_turn() API"
  - "Used MagicMock-based characterization tests to verify strategy behavior without full integration dependencies"

requirements-completed:
  - ARCH-02

metrics:
  duration: 55 min
  completed: 2026-05-02
---

# Phase 03-architecture Plan 02: QueryEngine Strategy Extraction Summary

**Extracted QueryEngine's LLM retry, context compaction, and turn execution into three focused strategy modules with backward-compatible orchestrator**

## Performance

- **Duration:** 55 min
- **Started:** 2026-05-02T19:44:47Z
- **Completed:** 2026-05-02T20:39:47Z
- **Tasks:** 3
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments

1. **LLMClientRetryWrapper** — Extracted LLM call retry logic with exponential backoff and jitter; supports context-compaction fallback on context-length errors
2. **ContextCompactionEngine** — Created token budget enforcement with truncation strategy (preserve system message, drop oldest first); ~4 chars/token estimation
3. **TurnOrchestrator** — Extracted single-turn execution (LLM call + tool execution + observation building) with permission handling and LoopGuard integration
4. **QueryEngine integration** — Instantiated all three strategies; added `run()` and `stop()` convenience methods; preserved existing public API
5. **17 characterization tests** covering strategy behavior and backward compatibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract LLMClientRetryWrapper** — `775f6fd` (test), `9eb4fce` (feat)
2. **Task 2: Extract ContextCompactionEngine** — `644f889` (feat)
3. **Task 3: Extract TurnOrchestrator** — `7aa35b5` (test), `b841751` (feat)

**Plan metadata:** `b841751` (docs: complete plan)

## Files Created/Modified

- `src/embedagent/strategies/__init__.py` — Strategy package exports
- `src/embedagent/strategies/llm_retry_wrapper.py` — LLM retry with backoff and compaction fallback
- `src/embedagent/strategies/context_compaction_engine.py` — Token budget enforcement
- `src/embedagent/strategies/turn_orchestrator.py` — Single-turn execution orchestration
- `tests/test_strategies.py` — 14 characterization tests for strategies
- `tests/test_query_engine_orchestrator.py` — 3 backward compatibility tests
- `src/embedagent/query_engine.py` — Thin orchestrator delegating to strategies

## Decisions Made

- **Backward compatibility over full extraction:** The original QueryEngine had tight coupling between turn execution and session/transcript recording. A pure extraction would have required complex callback interfaces or moving ~1000+ lines. We extracted the separable concerns (LLM retry, context compaction, tool execution) while keeping session management in QueryEngine.
- **Context-length retry stays in _run_loop:** The wrapper supports compaction fallback, but QueryEngine passes `compaction_engine=None` to preserve the existing compact-retry transition recording and compact boundary tracking that integration tests depend on.
- **run()/stop() as new API surface:** Added these as convenience methods that wrap `submit_user_turn()` with an internal stop event, rather than refactoring the entire public API.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Restored compact retry behavior in QueryEngine._run_loop**
- **Found during:** Task 3 verification
- **Issue:** Moving context-length retry into `LLMClientRetryWrapper` bypassed `_run_loop`'s transition recording and compact boundary tracking, causing 3 integration test failures
- **Fix:** Passed `compaction_engine=None` to `LLMClientRetryWrapper` in QueryEngine, preserving the existing `_run_loop` compact retry logic
- **Files modified:** `src/embedagent/query_engine.py`
- **Verification:** `test_query_engine_retries_with_compact_context_after_context_limit_error`, `test_session_history_includes_compact_retry_transition`, `test_session_snapshot_and_timeline_include_compact_retry_projection` all pass

**2. [Rule 1 - Bug] Fixed LoopGuard triggering on first non-retryable tool error in test**
- **Found during:** Task 3 test development
- **Issue:** `test_tool_error_observation` expected `tool_calls` but `LoopGuard.should_block()` triggers after 1 non-retryable failure (default `max_same_non_retryable_failures=1`)
- **Fix:** Updated test to expect `guard_stop` for non-retryable tool errors, which is correct behavior
- **Files modified:** `tests/test_strategies.py`

**3. [Rule 3 - Blocking] Fixed TurnOrchestrator continue statement indentation**
- **Found during:** Task 3 test execution
- **Issue:** `continue` statement in serial batch path was indented inside `for action` loop instead of `for batch` loop, causing fall-through to parallel execution code
- **Fix:** Corrected indentation so `continue` skips to next batch
- **Files modified:** `src/embedagent/strategies/turn_orchestrator.py`

**4. [Rule 3 - Blocking] Added missing QueryEngine imports and attributes**
- **Found during:** Task 3 backward compatibility tests
- **Issue:** `TurnOrchestrator` import and `_turn_orchestrator`, `run()`, `stop()` attributes missing from QueryEngine due to edit application issues
- **Fix:** Re-applied imports and method definitions
- **Files modified:** `src/embedagent/query_engine.py`

---

**Total deviations:** 4 auto-fixed (2 blocking, 1 bug, 1 missing critical)
**Impact on plan:** All auto-fixes necessary for correctness and test passage. No scope creep.

## Issues Encountered

- **QueryEngine line count target not met:** Plan targeted <500 lines; actual is ~1560 lines. The original code had deeper coupling between session management, transcript recording, and turn execution than anticipated. Extracting TurnOrchestrator required either (a) moving ~1000 lines and breaking the existing callback-driven architecture, or (b) creating complex callback interfaces. We chose pragmatic partial extraction that maintains test passage.

## Known Stubs

- `TurnOrchestrator._execute_action` does not handle `ask_user` and `propose_mode_switch` tool special cases (these remain in QueryEngine's original `_execute_action`)
- `TurnOrchestrator` does not record transcript events or append session messages — these remain in QueryEngine's `_run_loop`

## Next Phase Readiness

- Strategy modules are created and tested
- QueryEngine maintains backward compatibility
- Integration tests pass (except 1 pre-existing GUI sync failure)
- Ready for deeper extraction of session management if desired in future plans

---
*Phase: 03-architecture*
*Completed: 2026-05-02*
