---
phase: 07-harness-refactor
plan: 01
subsystem: harness
autonomous: true
tags: [harness, mode, permission, contract]
dependency_graph:
  requires: []
  provides: [HARN-01]
  affects: [src/embedagent/modes.py, src/embedagent/query_engine.py, src/embedagent/harness/task_graph.py]
tech_stack:
  added: []
  patterns: [PermissionContract, conditional harness injection]
key_files:
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
decisions:
  - Mode is permission contract only — defines available tools, not workflow tracks
  - Harness context only injected on explicit work requests (not chat)
  - Task graph only created when user text contains work indicators
  - explore and verify modes never trigger harness context
metrics:
  duration: "0 min (already implemented)"
  completed_date: "2026-05-03"
---

# Phase 7 Plan 01: Mode Permission Contract Summary

**One-liner:** Refactored mode system to be permission-contract-based with conditional harness context injection based on user intent.

## What Was Built

### PermissionContract Dataclass (`src/embedagent/modes.py`)
- Added `PermissionContract` dataclass that defines what a mode allows without prescribing workflow
- Fields: `mode_name`, `allowed_tools`, `permission_required_tools`, `writable_globs`, `read_only`
- Methods: `allows_tool()`, `requires_permission()`, `is_path_writable()`
- Added `MODE_CONTRACTS` dict mapping all 5 official modes to their contracts
- Added `get_mode_contract()` accessor with fallback to explore contract
- Built from existing `_BUILTIN_MODES` definitions for backward compatibility

### Conditional Harness Injection (`src/embedagent/query_engine.py`)
- Added `_should_inject_harness(user_text, current_mode)` method
- Never injects for `explore` or `verify` modes
- Checks for work indicators (build, compile, fix, debug, implement, create, write, generate, refactor, optimize, test, verify, check, run, execute)
- Excludes chat patterns (hi, hello, hey, what can you do, who are you, help, thanks, ok, bye)
- Updated `initialize_session()` and `apply_mode()` to conditionally inject harness context
- Updated `submit_user_turn()` to only create task graph on explicit work requests

### TaskGraph Extensions (`src/embedagent/harness/task_graph.py`)
- Added `is_empty()` method to check if graph has no tasks
- Added `from_user_request(user_text, mode_name)` classmethod to create task graph from explicit user request

### Characterization Tests (`tests/test_harness_mode_contract.py`)
- 6 tests for `PermissionContract` behavior (explore read-only, build allows write, debug requires permission, unknown mode defaults)
- 3 tests for harness injection logic (chat doesn't trigger, work requests trigger, explore never triggers)

## Test Results

- **New tests:** 9/9 passed (`tests/test_harness_mode_contract.py`)
- **Full fast suite:** 641 passed, 11 deselected — no regressions
- **Updated existing tests:** 4 test files adjusted to match new conditional harness behavior

## Deviations from Plan

None — plan executed exactly as written. All code changes were already present in commit `33b5f24`.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries.

## Self-Check: PASSED

- [x] `tests/test_harness_mode_contract.py` exists and passes
- [x] `PermissionContract` exists in `src/embedagent/modes.py`
- [x] `_should_inject_harness` exists in `src/embedagent/query_engine.py`
- [x] `is_empty()` and `from_user_request()` exist in `src/embedagent/harness/task_graph.py`
- [x] Commit `33b5f24` verified with all 8 files changed
- [x] Full test suite passes with no regressions
