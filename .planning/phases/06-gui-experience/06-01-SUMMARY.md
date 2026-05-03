---
phase: 06-gui-experience
plan: 01
subsystem: frontend-tui
tags: [timeline, flat-rendering, layout, tui]
dependency-graph:
  requires: [05-session-infrastructure]
  provides: [06-02, 06-03]
  affects: [frontend-tui-views, frontend-tui-layout]
tech-stack:
  added: []
  patterns: [flat-timeline, inline-tool-cards, conditional-layout]
key-files:
  created:
    - tests/test_gui_timeline_flat.py
  modified:
    - src/embedagent/frontend/tui/views/timeline.py
    - src/embedagent/frontend/tui/views/__init__.py
    - src/embedagent/frontend/tui/frontend_adapter.py
    - src/embedagent/frontend/tui/layout.py
decisions:
  - "Added streaming methods (update_command_output, mark_command_complete) to FlatTimelineView to satisfy pre-existing test_gui_streaming.py tests"
  - "Used ConditionalContainer in prompt_toolkit layout for collapsible auxiliary panels"
  - "Added set_assembler/update_flat_timeline API to TUIFrontend instead of direct assembler coupling"
metrics:
  duration: "20m"
  completed-date: "2026-05-03"
---

# Phase 06 Plan 01: Timeline Flat Rendering Summary

Flat timeline rendering with inline tool cards for the TUI frontend.

## What Was Built

1. **FlatTimelineView** (`src/embedagent/frontend/tui/views/timeline.py`)
   - Renders flat `items[]` array from `SessionHistoryAssembler.build_flat_timeline()`
   - Inline tool cards with lifecycle status indicators (started, running, success, error)
   - Supports all item types: user, assistant, tool_use, tool_result, command_execution, interaction, compact
   - Streaming update methods: `update_command_output()`, `mark_command_complete()`

2. **TUIFrontend Adapter** (`src/embedagent/frontend/tui/frontend_adapter.py`)
   - Added `flat_timeline_view` attribute
   - Added `set_assembler()` and `update_flat_timeline()` methods
   - Falls back to `build()` if `build_flat_timeline()` is unavailable

3. **Layout** (`src/embedagent/frontend/tui/layout.py`)
   - Main chat area dominates (auxiliary panels collapsed by default)
   - Explorer and inspector wrapped in `ConditionalContainer`
   - `Ctrl+P` keyboard shortcut toggles auxiliary panels

4. **Tests** (`tests/test_gui_timeline_flat.py`)
   - 5 characterization tests for FlatTimelineView rendering

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added streaming methods to FlatTimelineView**
- **Found during:** Task 4 (test execution)
- **Issue:** Pre-existing `tests/test_gui_streaming.py` expected `FlatTimelineView` to have `update_command_output()` and `mark_command_complete()` methods, which were not in the plan
- **Fix:** Added both methods to `FlatTimelineView` for incremental command output streaming and completion
- **Files modified:** `src/embedagent/frontend/tui/views/timeline.py`
- **Commit:** `610e6b9`

## Verification Results

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_gui_timeline_flat.py -v` | 5 passed |
| `uv run pytest tests/ -m "not slow and not gui" -v` | 632 passed, 0 failed |
| `python -c "from embedagent.frontend.tui.views.timeline import FlatTimelineView; print('ok')"` | ok |
| FlatTimelineView renders all item types | yes |
| FrontendAdapter uses build_flat_timeline() | yes (via update_flat_timeline) |
| Main chat area >= 70% | yes (aux panels collapsed by default) |
| No regression in existing test suite | yes |

## Commits

- `9162f9e`: feat(06-01): add FlatTimelineView class with inline tool cards
- `96cb274`: feat(06-01): export FlatTimelineView from views package
- `610e6b9`: feat(06-01): update TUIFrontend to support flat timeline
- `c7e4977`: feat(06-01): adjust TUI layout for conversation-first design
- `f401f08`: test(06-01): add flat timeline rendering tests

## Self-Check: PASSED

- [x] `src/embedagent/frontend/tui/views/timeline.py` exists and contains FlatTimelineView
- [x] `src/embedagent/frontend/tui/frontend_adapter.py` imports and uses FlatTimelineView
- [x] `src/embedagent/frontend/tui/layout.py` has ConditionalContainer for aux panels
- [x] `tests/test_gui_timeline_flat.py` exists and passes
- [x] All commits exist in git log
