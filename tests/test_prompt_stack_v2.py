import os
import sys
import unittest

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

pytestmark = pytest.mark.harness


class PromptStackV2Tests(unittest.TestCase):
    def test_build_messages_returns_three_sections(self):
        from embedagent.workflow_packages.c_cpp.prompt_stack import build_prompt_units

        units = build_prompt_units(
            base_prompt="base",
            mode_name="build",
            discipline_label="lite_spec_tdd",
            checklist_lines=["[ ] contract", "[ ] implement"],
            tool_prompt_lines=["Use read_file first."],
            runtime_nudges=["Last recipe failed."],
        )
        self.assertEqual(len(units), 3)
        self.assertIn("lite_spec_tdd", units[1])
        self.assertIn("Last recipe failed.", units[2])


if __name__ == "__main__":
    unittest.main()
