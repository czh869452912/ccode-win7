# Phase 02 Plan 03: Streaming Build Execution Tool Summary

**One-liner:** Added `run_subprocess_streaming` helper and `run_build` tool, enabling real-time C/C++ build execution with concurrent stdout/stderr capture, progress callbacks, and diagnostic parsing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add streaming subprocess helper to _base.py | 9e5ae49 | `src/embedagent/tools/_base.py` |
| 2 | Create run_build tool in compile_ops.py | 85c519b | `src/embedagent/tools/compile_ops.py` |
| 3 | Register run_build and verify integration | f7ee260 | `src/embedagent/tools/runtime.py`, `tests/test_tools_package.py` |

## Deviations from Plan

**None** — plan executed exactly as written.

## Key Decisions

1. **Threading-based concurrency:** Used `threading.Thread` for concurrent stdout/stderr reading instead of asyncio, ensuring Python 3.8 compatibility and avoiding event loop conflicts with the existing synchronous tool architecture.
2. **Progress callback design:** The callback receives structured payloads with `kind` ("stdout" / "stderr" / "status"), `line`, `timestamp_ms`, and periodic status updates every 2 seconds including `elapsed_ms`, `lines_stdout`, `lines_stderr`, and `pid`.
3. **run_build tool defaults:** Default `diagnostic=true` for automatic compiler diagnostic parsing; default `timeout_sec=120` (DEFAULT_BUILD_TIMEOUT_SEC) suitable for compilation workloads; managed tool rewriting applied automatically.
4. **Progress accumulation in observation:** `run_build` accumulates all progress callbacks into `streaming_progress` (capped at 1000 entries) and includes `streaming_progress_count` in the observation data for frontend consumption.
5. **Python 3.8 compatibility:** No walrus operator, no union types, no match statement. Used `typing` module generics and `# type:` comments throughout.

## Files Created

- None (all modifications to existing files)

## Files Modified

- `src/embedagent/tools/_base.py` — Added `run_subprocess_streaming` method with threaded stdout/stderr readers, progress callbacks, timeout/interrupt handling, and output truncation
- `src/embedagent/tools/compile_ops.py` — Added `_run_build` handler and `run_build` `ToolDefinition` with streaming execution, diagnostic parsing, and managed tool integration
- `src/embedagent/tools/runtime.py` — Added `run_build` to `_DEFAULT_TOOL_METADATA` with `permission_category: shell_exec`, mode visibility for `build`/`debug`/`verify`, and `interrupt_behavior: cancel`
- `tests/test_tools_package.py` — Updated expected tool count (18 → 19), added `run_build` to expected official tools, added 4 execution tests (returns observation, requires command, parses diagnostics, catalog metadata)

## Verification Results

- **Unit tests:** 57/57 passed in targeted test files (`tests/test_tools_package.py`, `tests/test_tools_v2_runtime.py`, `tests/test_tool_execution.py`)
- **Full test suite:** 422/423 passed (1 pre-existing GUI sync test failure unrelated to this change)
- **Lint:** `ruff check` passed on all changed files
- **Format:** `black` auto-applied and verified
- **Python compatibility:** 3.8.10 (no 3.9+ syntax used)

## Metrics

- **Duration:** ~18 minutes
- **Completed:** 2026-05-02
- **Files touched:** 4
- **Tests added:** 4 new test cases

## Self-Check: PASSED

- [x] `src/embedagent/tools/_base.py` contains `run_subprocess_streaming`
- [x] `src/embedagent/tools/compile_ops.py` contains `run_build` tool
- [x] `src/embedagent/tools/runtime.py` registers `run_build` metadata
- [x] Commit `9e5ae49` exists
- [x] Commit `85c519b` exists
- [x] Commit `f7ee260` exists
- [x] All relevant tests pass
- [x] Lint passes
- [x] No new failures introduced (1 pre-existing GUI sync failure)
