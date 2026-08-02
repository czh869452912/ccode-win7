import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.guard import ProgressGuard
from embedagent_core.session import Action, Observation


class TestProgressGuard(unittest.TestCase):
    def test_non_retryable_failure_blocks_repeat_early(self):
        guard = ProgressGuard()
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

    def test_truncated_provider_actions_do_not_count_as_tool_failures(self):
        guard = ProgressGuard()
        observation = Observation(
            tool_name="read_file",
            success=False,
            error="provider output ended before tool arguments were complete",
            data={
                "retryable": True,
                "error_kind": "truncated_tool_arguments",
            },
        )
        first = Action("read_file", {"path": "a.c"}, "call-a")
        second = Action("read_file", {"path": "b.c"}, "call-b")

        guard.record(first, observation)
        guard.record(second, observation)

        self.assertFalse(guard.should_stop())
        self.assertFalse(guard.should_block(second))


if __name__ == "__main__":
    unittest.main()
