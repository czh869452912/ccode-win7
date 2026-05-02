## Summary

**Phase 3: Architecture**
**Goal:** Maintainable codebase with clear component boundaries and no global state
**Status:** Verified ✓

This phase extracts monolithic classes into focused services and strategies, eliminates global mutable state via manual dependency injection, and adds comprehensive characterization and backward compatibility tests. InProcessAdapter is refactored into 4 services behind a thin facade, QueryEngine into 3 strategies, and module-level globals are replaced with factory functions and a DI container.

## Changes

### Plan 03-01: Extract InProcessAdapter Services
Extracted 4 focused services from 2,446-line InProcessAdapter (reduced to 2,138 lines) with 13 characterization tests.

**Key files:**
- `src/embedagent/services/__init__.py` (new)
- `src/embedagent/services/event_emitter.py` (new)
- `src/embedagent/services/harness_state_synchronizer.py` (new)
- `src/embedagent/services/session_lifecycle.py` (new)
- `src/embedagent/services/workspace_file_service.py` (new)
- `src/embedagent/inprocess_adapter.py` (modified — delegates to services)
- `tests/test_services.py` (new — 13 tests)

### Plan 03-02: Extract QueryEngine Strategies
Extracted 3 strategies from QueryEngine with 17 characterization tests and backward-compatible API.

**Key files:**
- `src/embedagent/strategies/__init__.py` (new)
- `src/embedagent/strategies/llm_retry_wrapper.py` (new)
- `src/embedagent/strategies/context_compaction_engine.py` (new)
- `src/embedagent/strategies/turn_orchestrator.py` (new)
- `src/embedagent/query_engine.py` (modified — integrates strategies)
- `tests/test_strategies.py` (new — 14 tests)
- `tests/test_query_engine_orchestrator.py` (new — 3 compat tests)

### Plan 03-03: Eliminate Global Mutable State
Manual DI container with factory functions replacing globals in modes.py, command_sanitizer.py, and core/adapter.py. 17 characterization tests.

**Key files:**
- `src/embedagent/di_container.py` (new)
- `src/embedagent/modes.py` (modified — factory-based registry)
- `src/embedagent/command_sanitizer.py` (modified — factory-based sanitizer)
- `src/embedagent/core/adapter.py` (modified — factory-based adapter)
- `tests/test_di_container.py` (new — 7 tests)
- `tests/test_global_state_elimination.py` (new — 10 tests)

### Plan 03-04: Characterization Tests and Backward Compatibility
37 tests (14 characterization + 23 backward compatibility) with isolated DI fixtures and architecture documentation.

**Key files:**
- `tests/test_characterization.py` (new — 14 tests)
- `tests/test_backward_compatibility.py` (new — 23 tests)
- `tests/conftest.py` (modified — fresh_container fixture)
- `docs/architecture-refactor.md` (new)

## Requirements Addressed

- ARCH-01: InProcessAdapter extracted into focused services (SessionLifecycle, EventEmitter, WorkspaceFileService, HarnessStateSynchronizer)
- ARCH-02: QueryEngine extracted into strategies (LLMClientRetryWrapper, ContextCompactionEngine, TurnOrchestrator)
- ARCH-03: Global mutable state eliminated via dependency injection (MODE_REGISTRY, _DEFAULT_SANITIZER, _inprocess_adapter)
- ARCH-04: Characterization tests exist for all extracted components preventing regression
- ARCH-05: All existing public APIs remain backward compatible

## Verification

- [x] Automated verification: 546 passed, 1 failed (pre-existing GUI sync failure unrelated to this change)
- [x] New tests: 81 characterization/backward-compatibility tests all passing
- [x] Backward compatibility: All imports and instantiation patterns preserved
- [x] No new deprecation warnings or bare except blocks introduced
- [x] UAT: 7/8 tests passed, 1 gap fixed during quick task

## Key Decisions

1. **Facade pattern:** InProcessAdapter delegates to services rather than full extraction to preserve deeply interdependent turn execution logic
2. **Strategy pattern:** QueryEngine integrates separable concerns (retry, compaction, turn orchestration) while keeping session management in orchestrator
3. **Manual DI:** No external framework (Python 3.8 constraint); factory registration on module load with `fresh=True` for test isolation
4. **Backward compatibility:** Property-like aliases provide dict-like access to refactored globals without breaking existing code
5. **Constructor injection:** Services receive dependencies via constructors for testability

## Architecture Overview

```
InProcessAdapter (facade)
├── SessionLifecycleManager
├── EventEmitter
├── WorkspaceFileService
└── HarnessStateSynchronizer

QueryEngine (orchestrator)
├── LLMClientRetryWrapper
├── ContextCompactionEngine
└── TurnOrchestrator

DIContainer (manual)
├── mode_registry → get_mode_registry()
├── command_sanitizer → get_command_sanitizer()
└── inprocess_adapter → get_inprocess_adapter()
```
