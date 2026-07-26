import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_protocol import SessionEventEnvelope

from embedagent.frontend.tui.frontend_adapter import TUIFrontend
from embedagent.frontend.tui.state import TerminalState
from embedagent.frontend.tui.views.timeline import (
    ActivityTimelineView,
    format_activity_records,
)


class _FakeApp(object):
    def __init__(self):
        self.state = TerminalState(workspace=".", initial_mode="build")
        self.refresh_count = 0

    def refresh_views(self):
        self.refresh_count += 1


def _event(kind, payload, sequence=1):
    return SessionEventEnvelope(1, "evt-%s" % sequence, "session-1", sequence, kind, "now", payload)


def test_empty_activities_render():
    view = ActivityTimelineView()
    view.update({"activities": []})

    result = view.render()

    assert result is not None


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


def test_activity_records_format_reasoning_interaction_and_compact():
    lines = format_activity_records(
        [
            {
                "kind": "reasoning",
                "id": "step-1",
                "content": "Inspecting build failure",
                "status": "completed",
            },
            {
                "kind": "interaction",
                "id": "permission-1",
                "content": "Allow write_file?",
                "status": "pending",
            },
            {
                "kind": "compact",
                "id": "compact-1",
                "content": "Older context summarized.",
                "status": "completed",
            },
        ]
    )

    assert lines == [
        "thinking> Inspecting build failure",
        "interaction [pending] Allow write_file?",
        "compact> Older context summarized.",
    ]


def test_tui_consumes_canonical_tool_events_and_failure_record():
    app = _FakeApp()
    frontend = TUIFrontend(app)

    frontend.on_session_event(
        _event(
            "tool.started",
            {"tool_name": "edit_file", "arguments": {"path": "missing.c", "_label": "Edit"}},
        )
    )
    frontend.on_session_event(
        _event(
            "tool.finished",
            {
                "tool_name": "edit_file",
                "success": False,
                "data": {"error_kind": "path_missing"},
                "failure": {"code": "path_missing", "message": "not found"},
            },
            sequence=2,
        )
    )

    assert app.state.timeline.lines == [
        "[tool] edit_file {'path': 'missing.c'}",
        "[observation] edit_file success=False kind=path_missing error=not found",
    ]
    assert app.refresh_count == 2


def test_tui_renders_one_error_line_for_one_session_error_event():
    app = _FakeApp()
    frontend = TUIFrontend(app)

    frontend.on_session_event(
        _event(
            "session.error",
            {
                "error": "provider failed",
                "session_snapshot": {
                    "session_id": "session-1",
                    "status": "error",
                    "last_error": "provider failed",
                    "pending_interaction_valid": False,
                },
            },
        )
    )

    assert app.state.timeline.lines == ["[error] provider failed"]
    assert app.state.session.last_error == "provider failed"
