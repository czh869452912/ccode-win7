import os
import unittest


class TestGuiSmokeContract(unittest.TestCase):
    def _script_text(self):
        root = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
        path = os.path.join(root, "scripts", "validate-gui-smoke.py")
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_smoke_script_uses_current_task_contract(self):
        text = self._script_text()
        self.assertNotIn("manage_todos", text)
        self.assertNotIn("/api/todos", text)
        self.assertNotIn("mode=code", text)
        self.assertIn("/api/tasks", text)


if __name__ == "__main__":
    unittest.main()
