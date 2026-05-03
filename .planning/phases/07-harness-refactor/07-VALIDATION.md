---
phase: 7
slug: 07-harness-refactor
status: completed
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-03
updated: 2026-05-03
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5 |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_harness_mode_contract.py tests/test_harness_completion_signal.py tests/test_harness_guard_safety.py -v` |
| **Full suite command** | `uv run pytest tests/ -m "not slow and not gui" -v` |
| **Estimated runtime** | ~8 seconds (quick), ~30 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_harness_mode_contract.py tests/test_harness_completion_signal.py tests/test_harness_guard_safety.py -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not slow and not gui" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 1 | HARN-01 | — | Explore mode is read-only | unit | `pytest tests/test_harness_mode_contract.py::TestPermissionContract::test_explore_is_read_only -v` | Yes | Green |
| 7-01-02 | 01 | 1 | HARN-01 | — | Build mode allows write | unit | `pytest tests/test_harness_mode_contract.py::TestPermissionContract::test_build_allows_write -v` | Yes | Green |
| 7-01-03 | 01 | 1 | HARN-01 | — | Build mode allows edit | unit | `pytest tests/test_harness_mode_contract.py::TestPermissionContract::test_build_allows_edit -v` | Yes | Green |
| 7-01-04 | 01 | 1 | HARN-01 | — | Verify mode is read-only | unit | `pytest tests/test_harness_mode_contract.py::TestPermissionContract::test_verify_is_read_only -v` | Yes | Green |
| 7-01-05 | 01 | 1 | HARN-01 | — | Debug requires permission for edit | unit | `pytest tests/test_harness_mode_contract.py::TestPermissionContract::test_debug_requires_permission_for_edit -v` | Yes | Green |
| 7-01-06 | 01 | 1 | HARN-01 | — | Unknown mode defaults to explore | unit | `pytest tests/test_harness_mode_contract.py::TestPermissionContract::test_unknown_mode_defaults_to_explore -v` | Yes | Green |
| 7-01-07 | 01 | 1 | HARN-01 | — | Chat does not trigger harness | unit | `pytest tests/test_harness_mode_contract.py::TestHarnessInjection::test_chat_does_not_trigger_harness -v` | Yes | Green |
| 7-01-08 | 01 | 1 | HARN-01 | — | Work request triggers harness | unit | `pytest tests/test_harness_mode_contract.py::TestHarnessInjection::test_work_request_triggers_harness -v` | Yes | Green |
| 7-01-09 | 01 | 1 | HARN-01 | — | Explore never triggers harness | unit | `pytest tests/test_harness_mode_contract.py::TestHarnessInjection::test_explore_never_triggers_harness -v` | Yes | Green |
| 7-02-01 | 02 | 2 | HARN-02 | — | Stop reason signals completion | unit | `pytest tests/test_harness_completion_signal.py::TestCompletionSignal::test_stop_reason_signals_completion -v` | Yes | Green |
| 7-02-02 | 02 | 2 | HARN-02 | — | Completed reason signals completion | unit | `pytest tests/test_harness_completion_signal.py::TestCompletionSignal::test_completed_reason_signals_completion -v` | Yes | Green |
| 7-02-03 | 02 | 2 | HARN-02 | — | Tool calls do not signal completion | unit | `pytest tests/test_harness_completion_signal.py::TestCompletionSignal::test_tool_calls_no_completion -v` | Yes | Green |
| 7-02-04 | 02 | 2 | HARN-02 | — | No actions signals completion | unit | `pytest tests/test_harness_completion_signal.py::TestCompletionSignal::test_no_actions_signals_completion -v` | Yes | Green |
| 7-03-01 | 03 | 3 | HARN-03 | — | Repeated tool calls blocked | unit | `pytest tests/test_harness_guard_safety.py::TestLoopGuard::test_repeated_tool_calls_blocked -v` | Yes | Green |
| 7-03-02 | 03 | 3 | HARN-03 | — | Different tools not blocked | unit | `pytest tests/test_harness_guard_safety.py::TestLoopGuard::test_different_tools_not_blocked -v` | Yes | Green |
| 7-03-03 | 03 | 3 | HARN-03 | — | Consecutive failures stop | unit | `pytest tests/test_harness_guard_safety.py::TestLoopGuard::test_consecutive_failures_stop -v` | Yes | Green |
| 7-03-04 | 03 | 3 | HARN-03 | — | Success resets failure count | unit | `pytest tests/test_harness_guard_safety.py::TestLoopGuard::test_success_resets_failure_count -v` | Yes | Green |
| 7-03-05 | 03 | 3 | HARN-03 | — | User override allows continue | unit | `pytest tests/test_harness_guard_safety.py::TestLoopGuard::test_user_override_allows_continue -v` | Yes | Green |

*Status: Green = passing, Red = failing, Yellow = partial*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:

- [x] `tests/conftest.py` — shared fixtures exist
- [x] `pyproject.toml` — pytest configuration with markers
- [x] `tests/test_harness_mode_contract.py` — permission contract tests
- [x] `tests/test_harness_completion_signal.py` — completion signal tests
- [x] `tests/test_harness_guard_safety.py` — guard safety tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| *(none)* | | | |

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-03

---
*Phase: 07-harness-refactor*
*Validated: 2026-05-03*
