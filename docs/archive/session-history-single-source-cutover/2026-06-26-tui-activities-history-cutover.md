# TUI Activities History Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Each task must start with focused failing checks, then implementation, then focused verification, then one commit.

**Goal:** Remove the remaining TUI flat-history item projection and make the TUI consume the same `SessionHistoryAssembler.build(...).activities` read model that the GUI receives through `GET /api/sessions/{id}/bootstrap`.

**Architecture:** `transcript.jsonl`, `Session` / `session.turns`, `SessionHistoryAssembler.build()`, and the session bootstrap payload remain the only session-history line. TUI rendering becomes another consumer of `history.activities`; it does not own a second `items` stream, mutate command items in place, or call `build_flat_history()`.

**Tech Stack:** Python 3.8, pytest, existing Rich-compatible TUI rendering helpers, existing session bootstrap adapter contract.

## Review Findings Driving This Plan

- `src/embedagent/frontend/tui/services/timeline.py` already returns session bootstrap `history` when `get_session_bootstrap()` is available. That history contains `activities`, not `events`.
- `src/embedagent/frontend/tui/controller.py` `reload_timeline()` only reads `payload["events"]`, so restored/bootstrap history from the official path can be ignored by the TUI display.
- `src/embedagent/session_history.py` still exposes `build_flat_history()`, a second history serializer that duplicates turn/message/tool traversal and returns old `items`.
- `src/embedagent/frontend/tui/frontend_adapter.py`, `src/embedagent/frontend/tui/views/timeline.py`, `tests/test_gui_timeline_flat.py`, and `tests/test_gui_streaming.py` keep the old flat timeline shape alive after the GUI has moved to bootstrap activities.

## Ground Rules

- Do not add compatibility shims for old `items` history.
- Do not add a fallback that infers history from timeline/event streams.
- Do not rename the product display concept away from timeline unless a broader UI design slice decides that; this plan removes the old data contract, not every UI label.
- Keep Python 3.8 syntax only.
- Do not touch generated GUI static assets unless webapp source changes; this plan is TUI/core/docs only.
- Each task below ends with a commit before the next task starts.

## Target Contract

`TimelineService.load(session_id)` returns a dictionary shaped like:

```python
{
    "session_id": session_id,
    "history_source": "live",
    "turns": [...],
    "activities": [
        {
            "kind": "user" | "reasoning" | "tool" | "assistant" | "interaction" | "compact",
            "id": "...",
            "content": "...",
            "status": "...",
            "turn_id": "...",
            "step_id": "...",
        }
    ],
    "current_interaction": None,
    "integrity": {"status": "healthy"},
}
```

TUI display code may format `activities` into local `TimelineState.lines`, but no active source should depend on:

- `SessionHistoryAssembler.build_flat_history`
- `FlatTimelineView`
- `flat_timeline`
- history-level `items`
- in-place `item.updated` / `item.completed` command mutation paths

## Task 1 - Add Activity Timeline Rendering

**Risk:** Low  
**Commit message:** `Use activities for TUI timeline rendering`

### Failing Checks First

Update `tests/test_gui_timeline_flat.py` to describe the new activity renderer instead of the old flat item view:

```python
from embedagent.frontend.tui.views.timeline import (
    ActivityTimelineView,
    format_activity_records,
)


def test_empty_activities_render():
    view = ActivityTimelineView()
    view.update({"activities": []})
    assert view.render() is not None


def test_activity_records_format_user_tool_and_assistant():
    lines = format_activity_records(
        [
            {
                "kind": "user",
                "id": "m1",
                "content": "Read file",
                "status": "completed",
                "turn_id": "t1",
            },
            {
                "kind": "tool",
                "id": "tool-c1",
                "tool_name": "read_file",
                "call_id": "c1",
                "content": "src/main.c",
                "status": "success",
                "turn_id": "t1",
            },
            {
                "kind": "assistant",
                "id": "m2",
                "content": "Done.",
                "status": "completed",
                "turn_id": "t1",
            },
        ]
    )

    assert lines == [
        "user> Read file",
        "tool read_file [success] src/main.c",
        "assistant> Done.",
    ]
```

Update `tests/test_exception_characterization.py` so the timeline service fallback no longer exposes old `items`:

```python
result = TimelineService(adapter).load("", limit=10)
assert result["activities"] == []
assert "items" not in result
assert result["integrity"]["status"] == "unavailable"
```

Run:

```bash
uv run pytest tests/test_gui_timeline_flat.py tests/test_exception_characterization.py -q
```

### Implementation

In `src/embedagent/frontend/tui/views/timeline.py`, replace the flat item view with an activity view:

```python
class ActivityTimelineView(object):
    def __init__(self, console=None) -> None:
        self.console = console
        self._activities = []

    def update(self, data):
        self._activities = list(data.get("activities") or [])

    def render(self):
        return "\n".join(format_activity_records(self._activities))
```

Add a formatter that consumes `kind`, not old `type`:

```python
def format_activity_records(records):
    lines = []
    for record in records:
        if not isinstance(record, dict):
            continue
        kind = str(record.get("kind") or "")
        content = str(record.get("content") or "")
        status = str(record.get("status") or "")
        if kind == "user":
            lines.append("user> %s" % content)
        elif kind == "assistant":
            lines.append("assistant> %s" % content)
        elif kind == "reasoning":
            lines.append("thinking> %s" % content)
        elif kind == "tool":
            tool_name = str(record.get("tool_name") or "tool")
            suffix = (" " + content) if content else ""
            lines.append("tool %s [%s]%s" % (tool_name, status or "unknown", suffix))
        elif kind == "interaction":
            lines.append("interaction [%s] %s" % (status or "pending", content))
        elif kind == "compact":
            lines.append("compact> %s" % content)
    return lines
```

In `src/embedagent/frontend/tui/services/timeline.py`, make the fallback match the target contract:

```python
return {
    "session_id": session_id,
    "history_source": "unavailable",
    "turns": [],
    "activities": [],
    "current_interaction": None,
    "integrity": {"status": "unavailable"},
}
```

Update `src/embedagent/frontend/tui/views/__init__.py` exports from `FlatTimelineView` to `ActivityTimelineView` and `format_activity_records`.

### Verification

```bash
uv run pytest tests/test_gui_timeline_flat.py tests/test_exception_characterization.py -q
uv run pytest tests/test_gui_streaming.py -q
```

If `tests/test_gui_streaming.py` is still tied to old mutable flat items, leave it failing for Task 2 and do not claim this task complete.

## Task 2 - Switch TUI Controller and Adapter Off Flat Items

**Risk:** Medium  
**Commit message:** `Route TUI timeline through bootstrap activities`

### Failing Checks First

Add a focused controller test, for example `tests/test_tui_timeline_activities.py`:

```python
from embedagent.frontend.tui.controller import TerminalController
from embedagent.frontend.tui.state import TerminalState


class FakeTimelineService(object):
    def load(self, session_id, limit=240):
        return {
            "session_id": session_id,
            "activities": [
                {"kind": "user", "content": "Inspect parser", "status": "completed"},
                {
                    "kind": "assistant",
                    "content": "Parser inspected.",
                    "status": "completed",
                },
            ],
            "latest_assistant_reply": "Parser inspected.",
            "integrity": {"status": "healthy"},
        }


class FakeOwner(object):
    def __init__(self):
        self.state = TerminalState(workspace=".", initial_mode="explore")
        self.state.session.current_session_id = "session-1"
        self.timeline_service = FakeTimelineService()


def test_reload_timeline_formats_bootstrap_activities():
    owner = FakeOwner()
    controller = TerminalController(owner)

    controller.reload_timeline()

    assert owner.state.timeline.lines == [
        "user> Inspect parser",
        "assistant> Parser inspected.",
    ]
    assert owner.state.timeline.stream_text == ""
    assert controller.latest_assistant_reply == "Parser inspected."
```

Run:

```bash
uv run pytest tests/test_tui_timeline_activities.py -q
```

### Implementation

In `src/embedagent/frontend/tui/controller.py`, import and use `format_activity_records`:

```python
from embedagent.frontend.tui.views.timeline import (
    format_activity_records,
    format_context_line,
    format_observation_line,
)
```

Update `reload_timeline()`:

```python
activities = payload.get("activities") or []
if activities:
    self.owner.state.timeline.lines = format_activity_records(activities)
    self.owner.state.timeline.stream_text = ""
    reducer.trim_timeline(self.owner.state)
```

In `src/embedagent/frontend/tui/frontend_adapter.py`, remove:

- `flat_timeline_view`
- `_current_timeline`
- `get_timeline_data()`
- `update_flat_timeline()`
- `handle_item_updated()`
- `handle_item_completed()`

If any live callback still uses `item.updated` / `item.completed`, route it through existing line-oriented TUI event handling or delete it if it is only test scaffolding.

Rewrite or delete `tests/test_gui_streaming.py`; the TUI no longer has a mutable command-item model. Keep coverage on the official live-line helpers by asserting `format_observation_line()` and controller event handling where appropriate.

### Verification

```bash
uv run pytest tests/test_tui_timeline_activities.py tests/test_gui_timeline_flat.py tests/test_gui_streaming.py -q
rg -n "get_timeline_data|update_flat_timeline|flat_timeline|item\\.updated|item\\.completed" src tests --glob "!docs/archive/**" --glob "!src/embedagent/frontend/gui/static/**"
```

The `rg` command must return no active source/test matches except archive or changelog text added by this slice.

## Task 3 - Delete `build_flat_history()`

**Risk:** Medium  
**Commit message:** `Delete flat session history serializer`

### Failing Checks First

Convert `tests/test_session_history.py`, `tests/test_session_integration.py`, and `tests/test_session_performance.py` to call:

```python
history = self.assembler.build(session, "live", "healthy")
activities = history["activities"]
```

Representative expectation changes:

```python
assert [item["kind"] for item in activities] == ["user", "reasoning", "tool", "assistant"]
assert activities[0]["content"] == "Inspect parser"
assert activities[2]["tool_name"] == "read_file"
assert activities[2]["status"] == "success"
```

For performance coverage, preserve the intent but measure `build()`:

```python
history = self.assembler.build(result.session, "restored", "healthy")
assert len(history["activities"]) >= expected_minimum
```

Run:

```bash
uv run pytest tests/test_session_history.py tests/test_session_integration.py tests/test_session_performance.py -q
```

### Implementation

Remove `SessionHistoryAssembler.build_flat_history()` entirely from `src/embedagent/session_history.py`.

Do not replace it with a wrapper around `build()`. This product has not shipped and old internal state does not need compatibility preservation.

### Verification

```bash
uv run pytest tests/test_session_history.py tests/test_session_integration.py tests/test_session_performance.py -q
rg -n "build_flat_history" src tests docs --glob "!docs/archive/**" --glob "!docs/superpowers/plans/**"
```

The only acceptable active match is this implementation plan until the plan is archived.

## Task 4 - Add Architecture Guards and Sync Docs

**Risk:** Low  
**Commit message:** `Guard TUI activity history contract`

### Failing Checks First

Add guard coverage to `tests/test_pre_release_architecture_guards.py`:

```python
def test_no_tui_flat_history_projection_contract():
    active_files = [
        ROOT / "src/embedagent/session_history.py",
        ROOT / "src/embedagent/frontend/tui/frontend_adapter.py",
        ROOT / "src/embedagent/frontend/tui/services/timeline.py",
        ROOT / "src/embedagent/frontend/tui/views/timeline.py",
        ROOT / "src/embedagent/frontend/tui/views/__init__.py",
    ]
    forbidden = [
        "build_flat_history",
        "FlatTimelineView",
        "flat_timeline",
        "item.updated",
        "item.completed",
        '"items": []',
    ]
    for path in active_files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, "%s still contains %s" % (path, token)
```

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py -q
```

### Documentation Updates

Synchronize the durable conclusion into active docs:

- `AGENTS.md`: TUI history display consumes session bootstrap `history.activities`; flat item history is not a supported product contract.
- `docs/overall-solution-architecture.md`: mention TUI as a bootstrap-activities consumer beside GUI.
- `docs/frontend-protocol.md`: document `history.activities` as the display read model; remove or avoid any active `items` timeline shape.
- `docs/development-tracker.md`: record the completed TUI cutover.
- `docs/design-change-log.md`: add a dated note that the old TUI flat history serializer was deleted.

### Verification

```bash
uv run pytest tests/test_pre_release_architecture_guards.py -q
rg -n "FlatTimelineView|build_flat_history|flat_timeline|history-level items|timeline items" AGENTS.md docs src tests --glob "!docs/archive/**" --glob "!docs/superpowers/plans/**" --glob "!src/embedagent/frontend/gui/static/**"
```

Active docs should describe only the activities contract. Archive docs and this plan may retain historical references until archived.

## Final Verification

After all tasks and commits:

```bash
uv run pytest tests/test_gui_timeline_flat.py tests/test_gui_streaming.py tests/test_tui_timeline_activities.py -q
uv run pytest tests/test_session_history.py tests/test_session_integration.py tests/test_session_performance.py -q
uv run pytest tests/test_pre_release_architecture_guards.py -q
uv run pytest tests/ -m "not slow and not gui" -q
uv run --locked python scripts/lint.py
git diff --check
```

No webapp build is required unless a later implementation touches `src/embedagent/frontend/gui/webapp/src/`.

## Done Criteria

- `TerminalController.reload_timeline()` renders `history.activities` from session bootstrap.
- TUI has no active `FlatTimelineView` or flat `items` history path.
- `SessionHistoryAssembler.build()` is the only active history serializer.
- Tests no longer call `build_flat_history()`.
- Architecture guards prevent reintroducing the old TUI flat-history contract.
- Active docs name the TUI as a consumer of the shared bootstrap activities contract.
