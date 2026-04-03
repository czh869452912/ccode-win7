import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.permissions import PermissionPolicy
from embedagent.session import Action


class TestPermissionPolicy(unittest.TestCase):
    def test_manage_todos_list_is_treated_as_read(self):
        policy = PermissionPolicy(auto_approve_all=False, workspace="D:\\workspace")

        decision = policy.evaluate(Action("manage_todos", {"action": "list"}, "call-list"))

        self.assertEqual(decision.outcome, "allow")
        self.assertEqual(decision.details.get("category"), "read")

    def test_manage_todos_mutation_still_requires_workspace_write_permission(self):
        policy = PermissionPolicy(auto_approve_all=False, workspace="D:\\workspace")

        decision = policy.evaluate(
            Action("manage_todos", {"action": "add", "content": "demo"}, "call-add")
        )

        self.assertEqual(decision.outcome, "ask")
        self.assertIsNotNone(decision.request)
        self.assertEqual(decision.request.category, "workspace_write")


if __name__ == "__main__":
    unittest.main()
