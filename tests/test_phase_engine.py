import os
import sys
import unittest

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

pytestmark = pytest.mark.harness


class PhaseEngineTests(unittest.TestCase):
    def test_understand_advances_when_contract_artifact_exists(self):
        from embedagent_workflow_cpp.contracts import ExecutionPhase
        from embedagent_workflow_cpp.phase_engine import advance_phase

        next_phase = advance_phase(
            ExecutionPhase.UNDERSTAND,
            {"contract_ready": True},
            "lite_spec_tdd",
        )
        self.assertEqual(next_phase.value, "contract")

    def test_nonzero_exit_does_not_force_phase_jump(self):
        from embedagent_workflow_cpp.contracts import ExecutionPhase
        from embedagent_workflow_cpp.phase_engine import advance_phase

        next_phase = advance_phase(
            ExecutionPhase.IMPLEMENT,
            {"last_command_failed": True},
            "lite_spec_tdd",
        )
        self.assertEqual(next_phase.value, "implement")

    def test_reproduce_advances_when_failing_evidence_exists(self):
        from embedagent_workflow_cpp.contracts import ExecutionPhase
        from embedagent_workflow_cpp.phase_engine import advance_phase

        next_phase = advance_phase(
            ExecutionPhase.REPRODUCE,
            {"failing_evidence_ready": True},
            "lite_spec_tdd",
        )
        self.assertEqual(next_phase.value, "isolate")

    def test_patch_advances_when_regression_result_ready(self):
        from embedagent_workflow_cpp.contracts import ExecutionPhase
        from embedagent_workflow_cpp.phase_engine import advance_phase

        next_phase = advance_phase(
            ExecutionPhase.PATCH,
            {"regression_result_ready": True},
            "lite_spec_tdd",
        )
        self.assertEqual(next_phase.value, "regression_check")

    def test_contract_advances_to_test_design_when_failing_evidence_is_ready(self):
        from embedagent_workflow_cpp.contracts import ExecutionPhase
        from embedagent_workflow_cpp.phase_engine import advance_phase

        next_phase = advance_phase(
            ExecutionPhase.CONTRACT,
            {"failing_evidence_ready": True},
            "full_spec_tdd",
        )
        self.assertEqual(next_phase.value, "test_design")

    def test_check_advances_to_repair_when_check_failed(self):
        from embedagent_workflow_cpp.contracts import ExecutionPhase
        from embedagent_workflow_cpp.phase_engine import advance_phase

        next_phase = advance_phase(
            ExecutionPhase.CHECK,
            {"check_result_ready": True, "check_passed": False},
            "full_spec_tdd",
        )
        self.assertEqual(next_phase.value, "repair")


if __name__ == "__main__":
    unittest.main()
