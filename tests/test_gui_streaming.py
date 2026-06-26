import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.tui.views.timeline import (
    ActivityTimelineView,
    format_observation_line,
)


def test_activity_view_renders_stream_safe_tool_activity():
    view = ActivityTimelineView()
    view.update(
        {
            "activities": [
                {
                    "kind": "tool",
                    "id": "tool-cmd1",
                    "tool_name": "bash",
                    "content": "cmd=pytest exit=0",
                    "status": "success",
                    "turn_id": "t1",
                }
            ]
        }
    )

    result = view.render()

    assert result is not None


def test_tool_observation_line_summarizes_command_result():
    line = format_observation_line(
        {
            "tool_name": "bash",
            "success": True,
            "data": {
                "command": "uv run pytest tests/test_gui_streaming.py -q",
                "exit_code": 0,
            },
            "error": "",
        }
    )

    assert line == (
        "[observation] bash success=True "
        "cmd=uv run pytest tests/test_gui_streaming.py -q exit=0"
    )


def test_tool_observation_line_summarizes_error_result():
    line = format_observation_line(
        {
            "tool_name": "bash",
            "success": False,
            "data": {"exit_code": 1, "error_count": 2},
            "error": "compile failed",
        }
    )

    assert line == (
        "[observation] bash success=False exit=1 errors=2 error=compile failed"
    )
