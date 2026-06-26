import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.session import (
    Action,
    AssistantReply,
    Observation,
    Session,
)
from embedagent.session_history import SessionHistoryAssembler


class TestSessionHistoryAssemblerFlatHistory(unittest.TestCase):
    def setUp(self):
        self.assembler = SessionHistoryAssembler()
        self.session = Session(session_id="sess-test")

    def _add_user_turn(self, content, turn_id=""):
        return self.session.add_user_message(content, turn_id=turn_id)

    def _add_assistant_step(self, turn, content="", actions=None, reasoning=""):
        step = self.session.begin_step(reasoning=reasoning)
        reply = AssistantReply(content=content, actions=actions or [])
        self.session.add_assistant_reply(
            reply,
            turn_id=turn.turn_id,
            step_id=step.step_id,
        )
        return step

    def _add_tool_result(self, turn, step, tool_name, call_id, success=True, data=None, error=""):
        action = Action(name=tool_name, arguments={}, call_id=call_id)
        observation = Observation(tool_name=tool_name, success=success, error=error, data=data)
        self.session.add_observation(
            action,
            observation,
            turn_id=turn.turn_id,
            step_id=step.step_id,
        )

    def test_flat_history_returns_items_array(self):
        self._add_user_turn("hello")
        result = self.assembler.build_flat_history(self.session, "live", "healthy")
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)

    def test_flat_history_user_item_structure(self):
        self._add_user_turn("test message")
        result = self.assembler.build_flat_history(self.session, "live", "healthy")
        items = result["items"]
        self.assertTrue(len(items) >= 1)
        user_item = items[0]
        self.assertEqual(user_item["type"], "user")
        self.assertEqual(user_item["content"], "test message")
        self.assertEqual(user_item["status"], "completed")
        self.assertIn("id", user_item)
        self.assertIn("parent_id", user_item)
        self.assertIn("turn_id", user_item)

    def test_flat_history_assistant_item_structure(self):
        turn = self._add_user_turn("hello")
        self._add_assistant_step(turn, content="hi there", reasoning="thinking")
        result = self.assembler.build_flat_history(self.session, "live", "healthy")
        items = result["items"]
        assistant_items = [i for i in items if i["type"] == "assistant"]
        self.assertEqual(len(assistant_items), 1)
        item = assistant_items[0]
        self.assertEqual(item["content"], "hi there")
        self.assertEqual(item["reasoning"], "thinking")
        self.assertIn("status", item)
        self.assertIn("turn_id", item)
        self.assertIn("step_id", item)

    def test_flat_history_tool_use_item(self):
        turn = self._add_user_turn("read file")
        self._add_assistant_step(
            turn,
            actions=[Action(name="read_file", arguments={"path": "test.txt"}, call_id="call-1")],
        )
        result = self.assembler.build_flat_history(self.session, "live", "healthy")
        items = result["items"]
        tool_items = [i for i in items if i["type"] == "tool_use"]
        self.assertEqual(len(tool_items), 1)
        item = tool_items[0]
        self.assertEqual(item["tool_name"], "read_file")
        self.assertEqual(item["call_id"], "call-1")
        self.assertEqual(item["arguments"], {"path": "test.txt"})
        self.assertEqual(item["status"], "started")

    def test_flat_history_tool_result_item(self):
        turn = self._add_user_turn("read file")
        step = self._add_assistant_step(
            turn,
            actions=[Action(name="read_file", arguments={"path": "test.txt"}, call_id="call-1")],
        )
        self._add_tool_result(turn, step, "read_file", "call-1", success=True, data="file content")
        result = self.assembler.build_flat_history(self.session, "live", "healthy")
        items = result["items"]
        result_items = [i for i in items if i["type"] == "tool_result"]
        self.assertEqual(len(result_items), 1)
        item = result_items[0]
        self.assertEqual(item["status"], "success")
        self.assertEqual(item["data"], "file content")
        self.assertEqual(item["tool_name"], "read_file")
        self.assertEqual(item["call_id"], "call-1")

    def test_flat_history_parent_chain(self):
        turn = self._add_user_turn("test")
        step = self._add_assistant_step(
            turn,
            content="using tool",
            actions=[Action(name="tool", arguments={}, call_id="c1")],
        )
        self._add_tool_result(turn, step, "tool", "c1", success=True, data="ok")
        result = self.assembler.build_flat_history(self.session, "live", "healthy")
        items = result["items"]

        # Find items
        tool_use = [i for i in items if i["type"] == "tool_use"][0]
        tool_result = [i for i in items if i["type"] == "tool_result"][0]

        # Parent chain: tool_use -> tool_result
        self.assertEqual(tool_result["parent_id"], tool_use["id"])

    def test_flat_history_empty_session(self):
        result = self.assembler.build_flat_history(Session(session_id=""), "live", "healthy")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["session_id"], "")

    def test_flat_history_integrity_info(self):
        self._add_user_turn("test")
        result = self.assembler.build_flat_history(
            self.session,
            "restored",
            "degraded",
            restore_stop_reason="tail_corruption",
            consumed_event_count=5,
            transcript_event_count=10,
        )
        integrity = result["integrity"]
        self.assertEqual(integrity["status"], "degraded")
        self.assertEqual(integrity["restore_stop_reason"], "tail_corruption")
        self.assertEqual(integrity["consumed_event_count"], 5)
        self.assertEqual(integrity["transcript_event_count"], 10)

    def test_flat_history_matches_nested_history_identity(self):
        turn = self._add_user_turn("test")
        step = self._add_assistant_step(
            turn,
            actions=[Action(name="tool", arguments={}, call_id="c1")],
        )
        self._add_tool_result(turn, step, "tool", "c1", success=True, data="ok")

        flat_result = self.assembler.build_flat_history(self.session, "live", "healthy")
        nested_result = self.assembler.build(self.session, "live", "healthy")

        self.assertIn("items", flat_result)
        self.assertIn("turns", nested_result)
        self.assertEqual(flat_result["session_id"], nested_result["session_id"])

    def test_old_build_method_unchanged(self):
        """Verify old build() still produces nested structure."""
        turn = self._add_user_turn("test")
        self._add_assistant_step(turn, content="reply")

        result = self.assembler.build(self.session, "live", "healthy")
        self.assertIn("turns", result)
        self.assertIsInstance(result["turns"], list)
        if result["turns"]:
            self.assertIn("steps", result["turns"][0])

    def test_build_includes_t3_activity_read_model(self):
        turn = self._add_user_turn("Inspect parser", turn_id="turn-activity")
        step = self._add_assistant_step(
            turn,
            content="Parser inspected.",
            reasoning="Read parser entry point",
            actions=[
                Action(
                    name="read_file",
                    arguments={"path": "src/parser.c"},
                    call_id="call-activity",
                )
            ],
        )
        self._add_tool_result(
            turn,
            step,
            "read_file",
            "call-activity",
            success=True,
            data={"path": "src/parser.c"},
        )

        result = self.assembler.build(self.session, "session_state", "healthy")

        self.assertIn("activities", result)
        activities = result["activities"]
        self.assertEqual(
            [item["kind"] for item in activities], ["user", "reasoning", "tool", "assistant"]
        )
        self.assertEqual(activities[0]["content"], "Inspect parser")
        self.assertEqual(activities[0]["turn_id"], "turn-activity")
        self.assertEqual(activities[1]["content"], "Read parser entry point")
        self.assertEqual(activities[1]["step_id"], step.step_id)
        self.assertEqual(activities[2]["tool_name"], "read_file")
        self.assertEqual(activities[2]["call_id"], "call-activity")
        self.assertEqual(activities[2]["status"], "success")
        self.assertEqual(activities[3]["content"], "Parser inspected.")


if __name__ == "__main__":
    unittest.main()
