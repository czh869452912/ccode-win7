import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class HarnessRunnerTaskGraphTests(unittest.TestCase):
    def test_runner_builds_full_spec_units_with_task_summary(self):
        from embedagent.harness.runner import HarnessRunner

        runner = HarnessRunner()
        units = runner.build_mode_units("build", [], discipline_override="full_spec_tdd")
        self.assertTrue(any("full_spec_tdd" in item for item in units))
        self.assertTrue(any("Tasks:" in item for item in units))


if __name__ == "__main__":
    unittest.main()
