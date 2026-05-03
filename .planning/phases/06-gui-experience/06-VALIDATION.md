---
phase: 6
slug: 06-gui-experience
status: completed
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-03
updated: 2026-05-03
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5 |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_gui_timeline_flat.py tests/test_gui_diff_view.py tests/test_gui_streaming.py -v` |
| **Full suite command** | `uv run pytest tests/ -m "not slow and not gui" -v` |
| **Estimated runtime** | ~8 seconds (quick), ~30 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_gui_timeline_flat.py tests/test_gui_diff_view.py tests/test_gui_streaming.py -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not slow and not gui" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 1 | GUI-01 | — | FlatTimelineView renders empty timeline | unit | `pytest tests/test_gui_timeline_flat.py::TestFlatTimelineView::test_empty_timeline_renders -v` | Yes | Green |
| 6-01-02 | 01 | 1 | GUI-01 | — | FlatTimelineView renders user item | unit | `pytest tests/test_gui_timeline_flat.py::TestFlatTimelineView::test_user_item_renders -v` | Yes | Green |
| 6-01-03 | 01 | 1 | GUI-01 | — | FlatTimelineView renders tool use item | unit | `pytest tests/test_gui_timeline_flat.py::TestFlatTimelineView::test_tool_use_item_renders -v` | Yes | Green |
| 6-01-04 | 01 | 1 | GUI-01 | — | FlatTimelineView renders tool result item | unit | `pytest tests/test_gui_timeline_flat.py::TestFlatTimelineView::test_tool_result_item_renders -v` | Yes | Green |
| 6-01-05 | 01 | 1 | GUI-01 | — | FlatTimelineView renders multiple items | unit | `pytest tests/test_gui_timeline_flat.py::TestFlatTimelineView::test_multiple_items_render -v` | Yes | Green |
| 6-02-01 | 02 | 2 | GUI-02 | — | DiffView renders empty diff | unit | `pytest tests/test_gui_diff_view.py::TestDiffView::test_empty_diff_renders -v` | Yes | Green |
| 6-02-02 | 02 | 2 | GUI-02 | — | DiffView renders simple diff | unit | `pytest tests/test_gui_diff_view.py::TestDiffView::test_simple_diff_renders -v` | Yes | Green |
| 6-02-03 | 02 | 2 | GUI-04 | — | DiffView detects language from extension | unit | `pytest tests/test_gui_diff_view.py::TestDiffView::test_diff_detects_language -v` | Yes | Green |
| 6-02-04 | 02 | 2 | GUI-02 | — | DiffView inline render works | unit | `pytest tests/test_gui_diff_view.py::TestDiffView::test_inline_render -v` | Yes | Green |
| 6-02-05 | 02 | 2 | GUI-04 | — | Theme colors differ dark/light | unit | `pytest tests/test_gui_diff_view.py::TestDiffView::test_theme_colors -v` | Yes | Green |
| 6-03-01 | 03 | 3 | GUI-03 | — | Command execution starts empty | unit | `pytest tests/test_gui_streaming.py::TestStreamingUpdates::test_command_execution_starts_empty -v` | Yes | Green |
| 6-03-02 | 03 | 3 | GUI-03 | — | Update command output appends chunks | unit | `pytest tests/test_gui_streaming.py::TestStreamingUpdates::test_update_command_output_appends -v` | Yes | Green |
| 6-03-03 | 03 | 3 | GUI-03 | — | Multiple chunks append correctly | unit | `pytest tests/test_gui_streaming.py::TestStreamingUpdates::test_multiple_chunks_append -v` | Yes | Green |
| 6-03-04 | 03 | 3 | GUI-03 | — | Mark command complete changes status | unit | `pytest tests/test_gui_streaming.py::TestStreamingUpdates::test_mark_command_complete -v` | Yes | Green |
| 6-03-05 | 03 | 3 | GUI-03 | — | Missing item update returns False | unit | `pytest tests/test_gui_streaming.py::TestStreamingUpdates::test_update_missing_item_returns_false -v` | Yes | Green |

*Status: Green = passing, Red = failing, Yellow = partial*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:

- [x] `tests/conftest.py` — shared fixtures exist
- [x] `pyproject.toml` — pytest configuration with markers
- [x] `tests/test_gui_timeline_flat.py` — flat timeline rendering tests
- [x] `tests/test_gui_diff_view.py` — diff view tests
- [x] `tests/test_gui_streaming.py` — streaming update tests

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
*Phase: 06-gui-experience*
*Validated: 2026-05-03*
