import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class HarnessRunnerDebugTests(unittest.TestCase):
    def test_runner_builds_debug_mode_units(self):
        from embedagent.harness.runner import HarnessRunner

        runner = HarnessRunner()
        units = runner.build_mode_units("debug", [])
        self.assertTrue(any("Mode: debug" in item for item in units))
        self.assertTrue(any("lite_spec_tdd" in item for item in units))


if __name__ == "__main__":
    unittest.main()
