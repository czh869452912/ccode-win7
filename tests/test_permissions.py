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

    def test_metadata_category_lookup_controls_dynamic_tool_permission(self):
        policy = PermissionPolicy(
            auto_approve_all=False,
            workspace="D:\\workspace",
            category_lookup=lambda name: "shell_exec" if name == "dynamic_shell" else "",
        )

        decision = policy.evaluate(Action("dynamic_shell", {"command": "echo hello"}, "call-shell"))

        self.assertEqual(decision.outcome, "ask")
        self.assertEqual(decision.request.category, "shell_exec")
        self.assertEqual(decision.details.get("category"), "shell_exec")

    def test_set_category_lookup_supports_late_tool_runtime_binding(self):
        policy = PermissionPolicy(auto_approve_all=False, workspace="D:\\workspace")
        policy.set_category_lookup(
            lambda name: "workspace_write" if name == "dynamic_write" else ""
        )

        decision = policy.evaluate(Action("dynamic_write", {"path": "generated.txt"}, "call-write"))

        self.assertEqual(decision.outcome, "ask")
        self.assertEqual(decision.request.category, "workspace_write")
        self.assertEqual(decision.details.get("path"), "generated.txt")

    def test_invalid_metadata_category_falls_back_to_other(self):
        policy = PermissionPolicy(
            auto_approve_all=False,
            workspace="D:\\workspace",
            category_lookup=lambda name: "not_real",
        )

        decision = policy.evaluate(Action("dynamic_unknown", {}, "call-unknown"))

        self.assertEqual(decision.outcome, "allow")
        self.assertEqual(decision.details.get("category"), "other")

    def test_dynamic_network_tool_requires_permission(self):
        policy = PermissionPolicy(
            auto_approve_all=False,
            workspace="D:\\workspace",
            category_lookup=lambda name: "network" if name == "intranet_fetch" else "",
        )

        decision = policy.evaluate(
            Action("intranet_fetch", {"url": "https://git.internal/api"}, "call-network")
        )

        self.assertEqual(decision.outcome, "ask")
        self.assertEqual(decision.request.category, "network")
        self.assertEqual(decision.details.get("category"), "network")
        self.assertIn("network", decision.details.get("explanation"))

    def test_dynamic_telemetry_tool_requires_permission(self):
        policy = PermissionPolicy(
            auto_approve_all=False,
            workspace="D:\\workspace",
            category_lookup=lambda name: "telemetry" if name == "flush_telemetry" else "",
        )

        decision = policy.evaluate(Action("flush_telemetry", {}, "call-telemetry"))

        self.assertEqual(decision.outcome, "ask")
        self.assertEqual(decision.request.category, "telemetry")
        self.assertEqual(decision.details.get("category"), "telemetry")

    def test_auto_approve_commands_does_not_allow_network_or_telemetry(self):
        policy = PermissionPolicy(
            auto_approve_all=False,
            auto_approve_commands=True,
            workspace="D:\\workspace",
            category_lookup=lambda name: {
                "intranet_fetch": "network",
                "flush_telemetry": "telemetry",
            }.get(name, ""),
        )

        network = policy.evaluate(Action("intranet_fetch", {}, "call-network"))
        telemetry = policy.evaluate(Action("flush_telemetry", {}, "call-telemetry"))

        self.assertEqual(network.outcome, "ask")
        self.assertEqual(telemetry.outcome, "ask")

    def test_permission_context_includes_network_and_telemetry_categories(self):
        policy = PermissionPolicy(auto_approve_all=False, workspace="D:\\workspace")

        view = policy.build_context_view(session_id="session-1")

        self.assertIn("network", view.categories)
        self.assertIn("telemetry", view.categories)


if __name__ == "__main__":
    unittest.main()
