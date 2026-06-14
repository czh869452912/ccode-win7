import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.query_engine import QueryEngine
from embedagent.session import AssistantReply, Session


class TestCompletionSignal(unittest.TestCase):
    def setUp(self):
        # Mock QueryEngine for testing
        self.engine = QueryEngine.__new__(QueryEngine)
        self.engine.max_turns = 8

    def test_stop_reason_signals_completion(self):
        reply = AssistantReply(content="Done", actions=[], finish_reason="stop")
        session = Session()
        self.assertTrue(self.engine._is_completion_signal(reply, session))

    def test_completed_reason_signals_completion(self):
        reply = AssistantReply(content="Done", actions=[], finish_reason="completed")
        session = Session()
        self.assertTrue(self.engine._is_completion_signal(reply, session))

    def test_tool_calls_no_completion(self):
        from embedagent.session import Action

        reply = AssistantReply(
            content="Let me check",
            actions=[Action(name="read_file", arguments={}, call_id="c1")],
            finish_reason="tool_calls",
        )
        session = Session()
        self.assertFalse(self.engine._is_completion_signal(reply, session))

    def test_no_actions_signals_completion(self):
        reply = AssistantReply(content="All done", actions=[], finish_reason="stop")
        session = Session()
        self.assertTrue(self.engine._is_completion_signal(reply, session))


if __name__ == "__main__":
    unittest.main()
