import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class RuleSchemaV2Tests(unittest.TestCase):
    def test_permission_explanation_has_stable_sections(self):
        from embedagent.permissions_v2.explainer import build_permission_explanation

        text = build_permission_explanation(
            tool_name="Edit",
            args_summary="src/main.c",
            risk_category="code_write",
            trigger_reason="file write requires confirmation",
            rule_source="default",
            scope_text="src/main.c",
            memory_scope="session",
        )
        self.assertIn("[请求]", text)
        self.assertIn("[风险]", text)
        self.assertIn("[记忆]", text)


if __name__ == "__main__":
    unittest.main()
