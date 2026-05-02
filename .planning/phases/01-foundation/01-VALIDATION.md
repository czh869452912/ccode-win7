---
phase: 1
slug: 01-foundation
status: completed
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-02
updated: 2026-05-02
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5 |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -m "not slow and not gui" -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (quick), ~60 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -m "not slow and not gui" -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not slow and not gui" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | HYGN-01 | T-01-01 | Timestamp format preserved (ISO 8601 Z suffix) | unit | `pytest tests/test_timestamp_characterization.py -v` | Yes | Green |
| 1-01-02 | 01 | 1 | HYGN-01 | T-01-01 | Zero utcnow() calls in src/ | integration | `pytest tests/test_hygn_01_datetime_cleanup.py -v` | Yes | Green |
| 1-01-03 | 01 | 1 | HYGN-01 | T-01-01 | Timezone import in all modified files | unit | `pytest tests/test_hygn_01_datetime_cleanup.py::TestNoDeprecatedDatetime::test_timezone_imported_in_modified_files -v` | Yes | Green |
| 1-02-01 | 02 | 2 | HYGN-02 | T-01-03 | Exception behavior preserved (missing file handling) | unit | `pytest tests/test_exception_characterization.py -v` | Yes | Green |
| 1-02-02 | 02 | 2 | HYGN-02 | T-01-03 | Zero bare except blocks in src/ | integration | `pytest tests/test_hygn_02_exception_cleanup.py -v` | Yes | Green |
| 1-02-03 | 02 | 2 | HYGN-02 | T-01-03 | Specific exception types used in all modified files | unit | `pytest tests/test_hygn_02_exception_cleanup.py::TestNoBareExceptBlocks::test_files_use_specific_exceptions -v` | Yes | Green |
| 1-03-01 | 03 | 3 | HYGN-03 | — | pytest config has warning filters | unit | `pytest tests/test_hygn_03_warning_cleanup.py::TestNoDeprecationWarnings::test_pytest_config_has_warning_filters -v` | Yes | Green |
| 1-03-02 | 03 | 3 | HYGN-03 | — | No deprecated utcnow() in test files | unit | `pytest tests/test_hygn_03_warning_cleanup.py::TestNoDeprecationWarnings::test_no_utcnnow_in_characterization_tests -v` | Yes | Green |

*Status: Green = passing, Red = failing, Yellow = partial*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:

- [x] `tests/conftest.py` — shared fixtures exist
- [x] `pyproject.toml` — pytest configuration with markers
- [x] `tests/test_timestamp_characterization.py` — stubs for HYGN-01
- [x] `tests/test_exception_characterization.py` — stubs for HYGN-02
- [x] `tests/test_hygn_01_datetime_cleanup.py` — regression guard for HYGN-01
- [x] `tests/test_hygn_02_exception_cleanup.py` — regression guard for HYGN-02
- [x] `tests/test_hygn_03_warning_cleanup.py` — regression guard for HYGN-03

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| *(none)* | | | |

All phase behaviors have automated verification.

---

## Validation Audit 2026-05-02

| Metric | Count |
|--------|-------|
| Gaps found | 19 bare except blocks in files not covered by Plan 02 |
| Resolved | 19 (all fixed during validation) |
| Escalated | 0 |

**Notes:**
- Plan 02 originally fixed 25 bare except blocks across 16 files
- Validation audit discovered 19 additional bare except blocks in unmodified files
- All 19 were fixed to achieve full HYGN-02 compliance
- Added RuntimeError to tool_commit.py exception handlers after test failure revealed gap

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-02

---
*Phase: 01-foundation*
*Validated: 2026-05-02*
