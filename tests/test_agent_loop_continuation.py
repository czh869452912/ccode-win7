import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.agent_loop_continuation import (
    CONTINUATION_ABORT,
    CONTINUATION_CONTINUE,
    CONTINUATION_STOP,
    AgentLoopContinuationFacts,
    DefaultAgentLoopContinuationPolicy,
)


class TestAgentLoopContinuationPolicy(unittest.TestCase):
    def test_completion_signal_stops_normally(self):
        policy = DefaultAgentLoopContinuationPolicy()

        decision = policy.decide_after_step(
            AgentLoopContinuationFacts(
                step_index=1,
                turns_used=1,
                mode_name="build",
                workflow_state="chat",
                completion_signal=True,
            )
        )

        self.assertEqual(decision.kind, CONTINUATION_STOP)
        self.assertEqual(decision.reason, "completed")
        self.assertEqual(decision.message, "agent signaled completion")
        self.assertEqual(decision.next_mode, "build")

    def test_tool_step_continues_before_safety_limit(self):
        policy = DefaultAgentLoopContinuationPolicy()

        decision = policy.decide_after_step(
            AgentLoopContinuationFacts(
                step_index=3,
                turns_used=3,
                mode_name="build",
                workflow_state="chat",
                has_tool_calls=True,
                safety_limit=8,
                safety_limit_reached=False,
            )
        )

        self.assertEqual(decision.kind, CONTINUATION_CONTINUE)
        self.assertEqual(decision.reason, "")

    def test_explicit_safety_limit_uses_max_turns_compatibility_reason(self):
        policy = DefaultAgentLoopContinuationPolicy()

        decision = policy.decide_after_step(
            AgentLoopContinuationFacts(
                step_index=1,
                turns_used=1,
                mode_name="build",
                workflow_state="chat",
                safety_limit=1,
                safety_limit_reached=True,
            )
        )

        self.assertEqual(decision.kind, CONTINUATION_STOP)
        self.assertEqual(decision.reason, "max_turns")
        self.assertEqual(
            decision.message,
            "reached loop safety limit without completion signal",
        )
        self.assertEqual(decision.metadata["loop_safety_limit"], 1)
        self.assertEqual(decision.metadata["turns_used"], 1)

    def test_stop_event_aborts(self):
        policy = DefaultAgentLoopContinuationPolicy()

        decision = policy.decide_after_step(
            AgentLoopContinuationFacts(
                step_index=0,
                turns_used=0,
                mode_name="build",
                workflow_state="chat",
                stop_event_set=True,
            )
        )

        self.assertEqual(decision.kind, CONTINUATION_ABORT)
        self.assertEqual(decision.reason, "aborted")
        self.assertEqual(decision.message, "stop_event set")


if __name__ == "__main__":
    unittest.main()
