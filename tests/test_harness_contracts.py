import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class HarnessContractsTests(unittest.TestCase):
    def test_build_mode_defaults_to_lite_spec_tdd(self):
        from embedagent.harness.registry import build_default_registry

        registry = build_default_registry()
        self.assertEqual(
            registry["build"].default_discipline.value,
            "lite_spec_tdd",
        )

    def test_build_mode_has_expected_lite_track(self):
        from embedagent.harness.registry import build_default_registry

        registry = build_default_registry()
        self.assertEqual(
            [phase.value for phase in registry["build"].lite_track],
            ["understand", "contract", "implement", "check", "handoff"],
        )

    def test_verify_mode_is_readonly(self):
        from embedagent.harness.registry import build_default_registry

        registry = build_default_registry()
        self.assertTrue(registry["verify"].readonly_mode)

    def test_debug_mode_defaults_to_lite_spec_tdd(self):
        from embedagent.harness.registry import build_default_registry

        registry = build_default_registry()
        self.assertEqual(
            registry["debug"].default_discipline.value,
            "lite_spec_tdd",
        )

    def test_debug_mode_has_expected_lite_track(self):
        from embedagent.harness.registry import build_default_registry

        registry = build_default_registry()
        self.assertEqual(
            [phase.value for phase in registry["debug"].lite_track],
            ["reproduce", "isolate", "patch", "regression_check", "handoff"],
        )


if __name__ == "__main__":
    unittest.main()
