import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.tui.controller import TerminalController
from embedagent.frontend.tui.state import TerminalState
from embedagent.frontend.tui.views.inspector import build_inspector_text


class FakeRuntime(object):
    def __init__(self):
        self.dispatch = None

    def activate_session(self, session_id, reason="activate"):
        bootstrap = {
            "snapshot": {"session_id": session_id, "status": "idle"},
            "history": {
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
            },
        }
        self.dispatch({"type": "session_activated", "bootstrap": bootstrap})
        return bootstrap


class FakeOwner(object):
    def __init__(self):
        self.state = TerminalState(workspace=".", initial_mode="explore")
        self.state.session.current_session_id = "session-1"
        self.runtime = FakeRuntime()
        self.refresh_count = 0

    def refresh_views(self):
        self.refresh_count += 1


def test_refresh_session_projection_formats_bootstrap_activities():
    owner = FakeOwner()
    controller = TerminalController(owner)
    owner.runtime.dispatch = controller.on_runtime_action

    controller.refresh_session_projection()

    assert owner.state.timeline.lines == [
        "user> Inspect parser",
        "assistant> Parser inspected.",
    ]
    assert owner.state.timeline.stream_text == ""
    assert controller.latest_assistant_reply == "Parser inspected."


def test_inspector_summarizes_turn_experience_from_snapshot():
    state = TerminalState(workspace=".", initial_mode="build")
    state.session.current_snapshot = {
        "session_id": "session-1",
        "current_mode": "build",
        "status": "idle",
        "turn_experience": {
            "status": "blocked",
            "completed": [{"kind": "file_created", "path": "README.md"}],
            "unverified": [
                {
                    "kind": "validation_missing",
                    "message": "Created files have not been validated.",
                }
            ],
            "next_steps": ["Run validation for the changed files."],
        },
    }

    text = build_inspector_text(state, {}, "")

    assert "Turn Experience" in text
    assert "- done: file_created README.md" in text
    assert "- unverified: validation_missing Created files have not been validated." in text
    assert "- next: Run validation for the changed files." in text
