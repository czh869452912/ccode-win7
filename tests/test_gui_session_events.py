import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.session_events import build_session_event


class GuiSessionEventTests(unittest.TestCase):
    def test_permission_required_projects_approval_requested_activity(self):
        message = build_session_event(
            "sess-1",
            "permission_required",
            {
                "permission_id": "perm-1",
                "turn_id": "turn-1",
                "tool_name": "edit_file",
                "reason": "Edit src/demo.c",
            },
        )

        data = message["data"]

        self.assertEqual(data["event_kind"], "approval.requested")
        self.assertEqual(data["payload"]["request_id"], "perm-1")
        self.assertEqual(data["payload"]["interaction_id"], "perm-1")
        self.assertEqual(data["payload"]["turn_id"], "turn-1")

    def test_user_input_required_projects_user_input_requested_activity(self):
        message = build_session_event(
            "sess-1",
            "user_input_required",
            {
                "interaction_id": "ask-1",
                "turn_id": "turn-1",
                "question": "Continue?",
            },
        )

        data = message["data"]

        self.assertEqual(data["event_kind"], "user-input.requested")
        self.assertEqual(data["payload"]["request_id"], "ask-1")
        self.assertEqual(data["payload"]["interaction_id"], "ask-1")


if __name__ == "__main__":
    unittest.main()
