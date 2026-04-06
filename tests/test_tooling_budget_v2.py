import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class ToolingBudgetV2Tests(unittest.TestCase):
    def test_large_results_are_replaced_with_refs(self):
        from embedagent.tooling.result_budget import apply_aggregate_budget

        results = [
            {"tool_name": "glob_files", "preview": "a" * 3000, "result_ref": "ref-a"},
            {"tool_name": "grep_text", "preview": "b" * 3000, "result_ref": "ref-b"},
        ]
        reduced = apply_aggregate_budget(results, char_budget=2000)
        self.assertTrue(any(item.get("omitted") for item in reduced))


if __name__ == "__main__":
    unittest.main()
