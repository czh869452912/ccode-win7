import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.tui.controller import TerminalController
from embedagent.frontend.tui.state import TerminalState


class FakeTimelineService(object):
    def load(self, session_id, limit=240):
        return {
            "session_id": session_id,
            "activities": [
                {
                    "kind": "user",
                    "content": "Inspect parser",
                    "status": "completed",
                },
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
