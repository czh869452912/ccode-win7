import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.permissions import (
    READ_TOOLS,
    TOOLCHAIN_EXEC_TOOLS,
    WORKSPACE_WRITE_TOOLS,
    PermissionPolicy,
)
from embedagent.session import Action


class TestPermissionPolicy(unittest.TestCase):
    def test_task_status_is_treated_as_read(self):
        policy = PermissionPolicy(auto_approve_all=False, workspace="D:\\workspace")

        decision = policy.evaluate(Action("task_status", {}, "call-list"))

        self.assertEqual(decision.outcome, "allow")
        self.assertEqual(decision.details.get("category"), "read")

    def test_run_recipe_rule_can_match_recipe_alias(self):
        policy = PermissionPolicy(auto_approve_all=False, workspace="D:\\workspace")
        policy.rules = policy._load_rules_from_items(
            [
                {
                    "decision": "allow",
                    "tool": "run_recipe",
                    "recipe": "cmake.build.default",
                    "reason": "trusted build recipe",
                }
            ]
        )

        decision = policy.evaluate(
            Action("run_recipe", {"recipe_id": "cmake.build.default"}, "call-run")
        )

        self.assertEqual(decision.outcome, "allow")

    def test_permission_details_include_stable_explanation_sections(self):
        policy = PermissionPolicy(auto_approve_all=False, workspace="D:\\workspace")

        decision = policy.evaluate(
            Action("run_recipe", {"recipe_id": "cmake.test.default"}, "call-run")
        )

        self.assertEqual(decision.outcome, "ask")
        explanation = str(decision.details.get("explanation") or "")
        self.assertIn("[请求]", explanation)
        self.assertIn("[风险]", explanation)
        self.assertIn("[规则]", explanation)
        self.assertIn("cmake.test.default", explanation)

    def test_official_permission_sets_exclude_legacy_tool_names(self):
        self.assertNotIn("list_files", READ_TOOLS)
        self.assertNotIn("search_text", READ_TOOLS)
        self.assertNotIn("report_quality", READ_TOOLS)
        self.assertNotIn("manage_todos", WORKSPACE_WRITE_TOOLS)
        self.assertNotIn("compile_project", TOOLCHAIN_EXEC_TOOLS)
        self.assertNotIn("run_tests", TOOLCHAIN_EXEC_TOOLS)


if __name__ == "__main__":
    unittest.main()
