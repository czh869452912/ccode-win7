import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.session import (
    Action,
    AssistantReply,
    Observation,
    Session,
)
from embedagent_host.runtime.session_history import SessionHistoryAssembler


class TestSessionHistoryAssemblerActivities(unittest.TestCase):
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

    def test_history_returns_activities_array(self):
        self._add_user_turn("hello")
        result = self.assembler.build(self.session, "live", "healthy")
        self.assertIn("activities", result)
        self.assertIsInstance(result["activities"], list)
        self.assertNotIn("items", result)

    def test_user_activity_structure(self):
        self._add_user_turn("test message")
        result = self.assembler.build(self.session, "live", "healthy")
        activities = result["activities"]
        self.assertTrue(len(activities) >= 1)
        user_activity = activities[0]
        self.assertEqual(user_activity["kind"], "user")
        self.assertEqual(user_activity["content"], "test message")
        self.assertEqual(user_activity["status"], "completed")
        self.assertIn("id", user_activity)
        self.assertIn("turn_id", user_activity)
        self.assertIn("projection_source", user_activity)

    def test_assistant_activity_structure(self):
        turn = self._add_user_turn("hello")
        self._add_assistant_step(turn, content="hi there", reasoning="thinking")
        result = self.assembler.build(self.session, "live", "healthy")
        activities = result["activities"]
        assistant_items = [i for i in activities if i["kind"] == "assistant"]
        reasoning_items = [i for i in activities if i["kind"] == "reasoning"]
        self.assertEqual(len(assistant_items), 1)
        self.assertEqual(len(reasoning_items), 1)
        item = assistant_items[0]
        self.assertEqual(item["content"], "hi there")
        self.assertIn("status", item)
        self.assertIn("turn_id", item)
        self.assertIn("step_id", item)
        self.assertEqual(reasoning_items[0]["content"], "thinking")

    def test_pending_tool_activity(self):
        turn = self._add_user_turn("read file")
        self._add_assistant_step(
            turn,
            actions=[Action(name="read_file", arguments={"path": "test.txt"}, call_id="call-1")],
        )
        result = self.assembler.build(self.session, "live", "healthy")
        activities = result["activities"]
        tool_items = [i for i in activities if i["kind"] == "tool"]
        self.assertEqual(len(tool_items), 1)
        item = tool_items[0]
        self.assertEqual(item["tool_name"], "read_file")
        self.assertEqual(item["call_id"], "call-1")
        self.assertEqual(item["arguments"], {"path": "test.txt"})
        self.assertEqual(item["status"], "running")
        self.assertIsNone(item["data"])

    def test_completed_tool_activity(self):
        turn = self._add_user_turn("read file")
        step = self._add_assistant_step(
            turn,
            actions=[Action(name="read_file", arguments={"path": "test.txt"}, call_id="call-1")],
        )
        self._add_tool_result(turn, step, "read_file", "call-1", success=True, data="file content")
        result = self.assembler.build(self.session, "live", "healthy")
        activities = result["activities"]
        tool_items = [i for i in activities if i["kind"] == "tool"]
        self.assertEqual(len(tool_items), 1)
        item = tool_items[0]
        self.assertEqual(item["status"], "success")
        self.assertEqual(item["data"], "file content")
        self.assertEqual(item["tool_name"], "read_file")
        self.assertEqual(item["call_id"], "call-1")

    def test_multiple_tool_calls_have_distinct_tool_activities(self):
        turn = self._add_user_turn("test")
        step = self._add_assistant_step(
            turn,
            content="using tools",
            actions=[
                Action(name="tool", arguments={"path": "a"}, call_id="c1"),
                Action(name="tool", arguments={"path": "b"}, call_id="c2"),
            ],
        )
        self._add_tool_result(turn, step, "tool", "c1", success=True, data="ok-a")
        self._add_tool_result(turn, step, "tool", "c2", success=False, error="bad-b")
        result = self.assembler.build(self.session, "live", "healthy")
        tool_items = [i for i in result["activities"] if i["kind"] == "tool"]

        self.assertEqual([i["call_id"] for i in tool_items], ["c1", "c2"])
        self.assertEqual([i["status"] for i in tool_items], ["success", "error"])
        self.assertEqual(tool_items[0]["data"], "ok-a")
        self.assertEqual(tool_items[1]["error"], "bad-b")

    def test_empty_session(self):
        result = self.assembler.build(Session(session_id=""), "live", "healthy")
        self.assertEqual(result["activities"], [])
        self.assertEqual(result["session_id"], "")

    def test_history_integrity_info(self):
        self._add_user_turn("test")
        result = self.assembler.build(
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

    def test_build_keeps_nested_history_and_activity_read_model(self):
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

        self.assertIn("turns", result)
        self.assertIn("steps", result["turns"][0])
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
