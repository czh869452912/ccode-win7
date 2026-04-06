import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class HarnessRunnerVerifyTests(unittest.TestCase):
    def test_runner_builds_verify_units(self):
        from embedagent.harness.runner import HarnessRunner

        runner = HarnessRunner()
        units = runner.build_mode_units("verify", [])
        self.assertTrue(any("Mode: verify" in item for item in units))
        self.assertTrue(any("select_recipe" in item for item in units))


if __name__ == "__main__":
    unittest.main()
