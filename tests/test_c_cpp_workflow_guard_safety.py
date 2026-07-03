import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent_core.guard import ProgressGuard
from embedagent_core.session import Action, Observation


class TestProgressGuard(unittest.TestCase):
    def setUp(self):
        self.guard = ProgressGuard()

    def test_repeated_no_progress_action_blocked(self):
        action = Action(name="read_file", arguments={"path": "README.md"}, call_id="c1")
        obs = Observation(
            tool_name="read_file",
            success=True,
            error=None,
            data={"path": "README.md", "content": "same"},
        )

        for _ in range(3):
            self.guard.record(action, obs)

        self.assertTrue(self.guard.should_block(action))
        self.assertEqual(self.guard.stop_reason(), "repeated no-progress action")

    def test_same_tool_with_different_progress_not_blocked(self):
        actions = [
            Action(
                name="write_file", arguments={"path": "README.md", "content": "a"}, call_id="c1"
            ),
            Action(
                name="write_file", arguments={"path": "src/main.c", "content": "b"}, call_id="c2"
            ),
            Action(
                name="write_file",
                arguments={"path": "tests/test_demo.py", "content": "c"},
                call_id="c3",
            ),
        ]
        observations = [
            Observation(
                tool_name="write_file",
                success=True,
                error=None,
                data={"path": "README.md", "created": True},
            ),
            Observation(
                tool_name="write_file",
                success=True,
                error=None,
                data={"path": "src/main.c", "created": True},
            ),
            Observation(
                tool_name="write_file",
                success=True,
                error=None,
                data={"path": "tests/test_demo.py", "created": True},
            ),
        ]

        for action, observation in zip(actions, observations):
            self.guard.record(action, observation)

        self.assertFalse(self.guard.should_block(actions[-1]))

    def test_diagnostic_command_failures_do_not_hard_stop(self):
        action = Action(name="bash", arguments={"command": "exit 1"}, call_id="c1")
        fail_obs = Observation(
            tool_name="bash",
            success=False,
            error="failed",
            data={
                "command": "exit 1",
                "exit_code": 1,
                "error_kind": "command_failed",
                "outcome_class": "diagnostic_failure",
                "retryable": False,
            },
        )

        self.guard.record(action, fail_obs)
        self.guard.record(action, fail_obs)

        self.assertFalse(self.guard.should_stop())
        self.assertFalse(self.guard.should_block(action))

    def test_distinct_diagnostic_commands_are_progress(self):
        for index, command in enumerate(("exit 1", "exit 2", "exit 3"), 1):
            self.guard.record(
                Action(name="bash", arguments={"command": command}, call_id="c%s" % index),
                Observation(
                    tool_name="bash",
                    success=False,
                    error="failed",
                    data={
                        "command": command,
                        "exit_code": index,
                        "error_kind": "command_failed",
                        "outcome_class": "diagnostic_failure",
                        "retryable": False,
                    },
                ),
            )

        self.assertFalse(
            self.guard.should_block(
                Action(name="bash", arguments={"command": "exit 3"}, call_id="c3")
            )
        )

    def test_diagnostic_grep_failures_do_not_hard_stop(self):
        action = Action(
            name="grep_text", arguments={"path": "missing", "pattern": "x"}, call_id="c1"
        )
        fail_obs = Observation(
            tool_name="grep_text",
            success=False,
            error="路径不存在：missing",
            data={
                "error_kind": "path_not_found",
                "outcome_class": "diagnostic_failure",
                "retryable": False,
            },
        )

        self.guard.record(action, fail_obs)
        self.guard.record(action, fail_obs)

        self.assertFalse(self.guard.should_stop())
        self.assertFalse(self.guard.should_block(action))

    def test_non_diagnostic_timeout_still_counts_as_failure(self):
        action = Action(name="read_file", arguments={"path": "README.md"}, call_id="c1")
        fail_obs = Observation(
            tool_name="read_file",
            success=False,
            error="timed out",
            data={"error_kind": "timeout", "retryable": False},
        )

        self.guard.record(action, fail_obs)
        self.guard.record(action, fail_obs)

        self.assertTrue(self.guard.should_stop())

    def test_success_resets_failure_count(self):
        action = Action(name="bash", arguments={"command": "exit 1"}, call_id="c1")
        fail_obs = Observation(tool_name="bash", success=False, error="failed", data=None)
        success_obs = Observation(
            tool_name="bash", success=True, error=None, data={"command": "echo ok"}
        )

        self.guard.record(action, fail_obs)
        self.guard.record(action, success_obs)
        self.guard.record(action, fail_obs)

        self.assertFalse(self.guard.should_stop())

    def test_user_override_allows_continue(self):
        action = Action(name="read_file", arguments={"path": "README.md"}, call_id="c1")
        obs = Observation(
            tool_name="read_file",
            success=True,
            error=None,
            data={"path": "README.md", "content": "same"},
        )

        for _ in range(3):
            self.guard.record(action, obs)

        self.assertTrue(self.guard.should_block(action))

        self.guard.user_override()
        self.assertFalse(self.guard.should_block(action))


if __name__ == "__main__":
    unittest.main()
