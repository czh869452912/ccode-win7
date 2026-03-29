import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.guard import LoopGuard
from embedagent.session import Action, Observation


class TestLoopGuard(unittest.TestCase):
    def test_non_retryable_failure_blocks_repeat_early(self):
        guard = LoopGuard()
        action = Action(name="edit_file", arguments={"path": "demo.txt"}, call_id="call-1")
        observation = Observation(
            tool_name="edit_file",
            success=False,
            error="blocked",
            data={"retryable": False, "error_kind": "mode_path_blocked"},
        )
        guard.record(action, observation)
        self.assertTrue(guard.should_block(action))
        blocked = guard.blocked_observation(action)
        self.assertFalse(blocked.data["retryable"])


if __name__ == "__main__":
    unittest.main()
