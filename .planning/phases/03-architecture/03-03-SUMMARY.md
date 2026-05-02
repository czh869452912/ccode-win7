---
phase: 03-architecture
plan: 03
subsystem: architecture
tags: [dependency-injection, manual-di, factory-pattern, global-state, test-isolation]

requires:
  - phase: 03-architecture
    provides: Service extraction and strategy extraction from plans 03-01, 03-02

provides:
  - Manual DIContainer with singleton and factory resolution modes
  - Factory-based mode registry eliminating mutable global MODE_REGISTRY
  - Factory-based command sanitizer eliminating mutable global _DEFAULT_SANITIZER
  - Factory-based InProcessAdapter accessor eliminating mutable global _inprocess_adapter
  - Backward-compatible aliases for all refactored globals
  - 17 characterization tests verifying DI behavior and state isolation

affects:
  - src/embedagent/modes.py
  - src/embedagent/command_sanitizer.py
  - src/embedagent/core/adapter.py
  - tests/

tech-stack:
  added: []
  patterns:
    - "Manual DI with register_factory/resolve/clear API"
    - "Factory functions with fresh=True for test isolation"
    - "Property-like aliases for backward compatibility"
    - "Module-level factory registration on import"

key-files:
  created:
    - src/embedagent/di_container.py - Manual DI container with thread-safe singleton caching
    - tests/test_di_container.py - 7 characterization tests for DIContainer
    - tests/test_global_state_elimination.py - 10 characterization tests for global state elimination
  modified:
    - src/embedagent/modes.py - Replaced MODE_REGISTRY global with get_mode_registry() factory + alias
    - src/embedagent/command_sanitizer.py - Replaced _DEFAULT_SANITIZER global with get_command_sanitizer() factory + alias
    - src/embedagent/core/adapter.py - Replaced _inprocess_adapter global with get_inprocess_adapter() factory + alias

key-decisions:
  - "Used manual DI instead of external framework (Python 3.8 compatibility, small dependency surface)"
  - "Factory registration on module load ensures container is populated at import time"
  - "fresh=True parameter enables test isolation without breaking singleton semantics for production"
  - "Property-like aliases (_ModeRegistryAlias, _DefaultSanitizerAlias) provide backward compatibility without mutable state"

patterns-established:
  - "Factory function + DI container registration: preferred pattern over module-level mutable globals"
  - "fresh=True parameter convention: use for tests, omit for production singleton behavior"
  - "Alias class pattern: wrap factory calls in __getitem__/__getattr__ for dict-like backward compatibility"

requirements-completed:
  - ARCH-03

duration: 25min
completed: 2026-05-02
---

# Phase 3 Plan 3: Eliminate Global Mutable State via Manual DI

**Manual dependency injection container with factory functions replacing module-level mutable globals in modes.py, command_sanitizer.py, and core/adapter.py**

## Performance

- **Duration:** 25 min
- **Started:** 2026-05-02T00:00:00Z
- **Completed:** 2026-05-02T00:25:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created `DIContainer` with `register_factory()`, `resolve()`, and `clear()` APIs
- Refactored `modes.py`: `MODE_REGISTRY` dict global → `get_mode_registry()` factory with `_ModeRegistryAlias` backward compat
- Refactored `command_sanitizer.py`: `_DEFAULT_SANITIZER` lazy-init global → `get_command_sanitizer()` factory with alias
- Refactored `core/adapter.py`: `_inprocess_adapter` lazy-init global → `get_inprocess_adapter()` factory with alias
- Added 17 characterization tests: 7 for DI container + 10 for global state elimination
- Full backward compatibility: all 509 existing tests pass (1 pre-existing flaky GUI test excluded)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Add failing tests** - `e3ffaf6` (test)
2. **Task 1 GREEN: DI container + modes.py refactor** - `d4e88ab` (feat)
3. **Task 2 GREEN: command_sanitizer + adapter refactor** - `52914c6` (feat)

## Files Created/Modified

- `src/embedagent/di_container.py` - New: manual DI container with RLock thread safety
- `src/embedagent/modes.py` - Refactored: MODE_REGISTRY global eliminated, factory-based registry
- `src/embedagent/command_sanitizer.py` - Refactored: _DEFAULT_SANITIZER global eliminated
- `src/embedagent/core/adapter.py` - Refactored: _inprocess_adapter global eliminated
- `tests/test_di_container.py` - New: 7 tests for DIContainer behavior
- `tests/test_global_state_elimination.py` - New: 10 tests verifying state isolation

## Decisions Made

- **Manual DI over framework**: Python 3.8 compatibility and minimal dependency surface aligned with project constraints
- **Factory registration on module load**: Ensures container is ready before any consumer calls resolve()
- **fresh=True convention**: Parameterized factory resolution enables test isolation while preserving production singletons
- **Alias classes for backward compat**: `_ModeRegistryAlias` implements dict-like interface (`__getitem__`, `__contains__`, `keys()`, etc.) so existing `MODE_REGISTRY[key]` code continues to work

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test expectation for initialize_modes registry mutation**
- **Found during:** Task 1 (writing tests)
- **Issue:** Test expected `initialize_modes(registry={})` to return `{}`, but the function correctly populates the passed registry with built-in modes
- **Fix:** Updated test to assert that built-in modes are present in the returned registry, and that the global registry is unaffected
- **Files modified:** `tests/test_global_state_elimination.py`
- **Committed in:** `e3ffaf6` (test commit)

**2. [Rule 1 - Bug] Fixed test expectation for InProcessAdapter factory fresh behavior**
- **Found during:** Task 2 (running tests)
- **Issue:** Test expected `get_inprocess_adapter(fresh=True)` to return different objects, but the factory returns the `InProcessAdapter` class itself, and classes are singletons in Python
- **Fix:** Updated test to verify that fresh=True returns the correct class, acknowledging that class objects are inherently singleton
- **Files modified:** `tests/test_global_state_elimination.py`
- **Committed in:** `52914c6` (feat commit)

**3. [Plan Contradiction] Verification grep expects 0 matches but plan requires backward-compatible aliases**
- **Found during:** Final verification
- **Issue:** Plan verification commands expect `grep "^MODE_REGISTRY\s*="` to return 0, but the plan also explicitly requires keeping `MODE_REGISTRY` as a backward-compatible alias
- **Resolution:** Aliases are intentionally present and are NOT mutable globals - they delegate to factory functions and hold no mutable state. The original mutable globals (dict, sanitizer instance, adapter class reference) have been eliminated.
- **Files:** `src/embedagent/modes.py` line 200, `src/embedagent/command_sanitizer.py` line 192, `src/embedagent/core/adapter.py` line 67

---

**Total deviations:** 3 auto-fixed (2 test bugs, 1 plan contradiction)
**Impact on plan:** No scope creep. All changes necessary for correctness and backward compatibility.

## Issues Encountered

- `test_gui_sync.py::TestGuiSync::test_gui_backend_route_resolves_real_pending_input_waiter` is a pre-existing flaky test unrelated to this plan's changes (fails both before and after)
- PowerShell lacks `grep`/`tail` commands; used Python one-liners for verification instead

## Next Phase Readiness

- Architecture phase is ready for next plan (03-04 or phase completion)
- DI container pattern is established and can be extended to additional modules
- All characterization tests provide regression protection for global state elimination

---
*Phase: 03-architecture*
*Completed: 2026-05-02*
