import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.query_engine import QueryEngine
from embedagent_core.session import Action, AssistantReply


class TestCompletionSignal(unittest.TestCase):
    def setUp(self):
        # Mock QueryEngine for testing
        self.engine = QueryEngine.__new__(QueryEngine)
        self.engine.max_turns = 8

    def test_stop_reason_signals_completion(self):
        reply = AssistantReply(content="Done", actions=[], finish_reason="stop")
        self.assertEqual(self.engine.classify_assistant_turn(reply), "final_message")

    def test_completed_reason_signals_completion(self):
        reply = AssistantReply(content="Done", actions=[], finish_reason="completed")
        self.assertEqual(self.engine.classify_assistant_turn(reply), "final_message")

    def test_tool_calls_no_completion(self):
        reply = AssistantReply(
            content="Let me check",
            actions=[Action(name="read_file", arguments={}, call_id="c1")],
            finish_reason="tool_calls",
        )
        self.assertEqual(self.engine.classify_assistant_turn(reply), "tool_calls")

    def test_no_actions_signals_completion(self):
        reply = AssistantReply(content="All done", actions=[], finish_reason="stop")
        self.assertEqual(self.engine.classify_assistant_turn(reply), "final_message")

    def test_empty_stop_without_actions_is_not_completion(self):
        reply = AssistantReply(content="", actions=[], finish_reason="stop")
        self.assertEqual(self.engine.classify_assistant_turn(reply), "empty_noop")

    def test_query_engine_does_not_expose_loop_compatibility_wrappers(self):
        self.assertFalse(hasattr(QueryEngine, "_is_completion_signal"))
        self.assertFalse(hasattr(QueryEngine, "_run_loop"))

    def test_classifies_visible_no_tool_reply_as_final_message(self):
        reply = AssistantReply(content="Done", actions=[], finish_reason="stop")
        self.assertEqual(self.engine.classify_assistant_turn(reply), "final_message")

    def test_classifies_tool_reply_as_tool_calls(self):
        reply = AssistantReply(
            content="",
            actions=[Action(name="read_file", arguments={}, call_id="c1")],
            finish_reason="tool_calls",
        )
        self.assertEqual(self.engine.classify_assistant_turn(reply), "tool_calls")

    def test_classifies_empty_no_tool_reply_as_empty_noop(self):
        reply = AssistantReply(content="   ", actions=[], finish_reason="stop")
        self.assertEqual(self.engine.classify_assistant_turn(reply), "empty_noop")


if __name__ == "__main__":
    unittest.main()
