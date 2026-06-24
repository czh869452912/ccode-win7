import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.guard import LoopGuard
from embedagent.session import Action, Observation


class TestLoopGuard(unittest.TestCase):
    def setUp(self):
        self.guard = LoopGuard()

    def test_repeated_tool_calls_blocked(self):
        action = Action(name="read_file", arguments={}, call_id="c1")
        obs = Observation(tool_name="read_file", success=True, error=None, data="ok")

        # Record same tool 3 times
        for _ in range(3):
            self.guard.record(action, obs)

        self.assertTrue(self.guard.should_block(action))

    def test_different_tools_not_blocked(self):
        action1 = Action(name="read_file", arguments={}, call_id="c1")
        action2 = Action(name="list_dir", arguments={}, call_id="c2")
        obs = Observation(tool_name="read_file", success=True, error=None, data="ok")

        self.guard.record(action1, obs)
        self.guard.record(action2, obs)
        self.guard.record(action1, obs)

        self.assertFalse(self.guard.should_block(action1))

    def test_consecutive_failures_stop(self):
        action = Action(name="bash", arguments={}, call_id="c1")
        fail_obs = Observation(tool_name="bash", success=False, error="failed", data=None)

        self.guard.record(action, fail_obs)
        self.guard.record(action, fail_obs)

        self.assertTrue(self.guard.should_stop())

    def test_success_resets_failure_count(self):
        action = Action(name="bash", arguments={}, call_id="c1")
        fail_obs = Observation(tool_name="bash", success=False, error="failed", data=None)
        success_obs = Observation(tool_name="bash", success=True, error=None, data="ok")

        self.guard.record(action, fail_obs)
        self.guard.record(action, success_obs)
        self.guard.record(action, fail_obs)

        self.assertFalse(self.guard.should_stop())

    def test_user_override_allows_continue(self):
        action = Action(name="read_file", arguments={}, call_id="c1")
        obs = Observation(tool_name="read_file", success=True, error=None, data="ok")

        for _ in range(3):
            self.guard.record(action, obs)

        self.assertTrue(self.guard.should_block(action))

        self.guard.user_override()
        self.assertFalse(self.guard.should_block(action))


if __name__ == "__main__":
    unittest.main()
