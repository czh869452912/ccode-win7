import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.tui.views.timeline import (
    ActivityTimelineView,
    format_activity_records,
)


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
