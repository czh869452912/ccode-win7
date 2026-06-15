import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.launcher import _resolve_initial_workspace


class TestGuiLauncherAppMode(unittest.TestCase):
    def test_no_workspace_arguments_return_empty_string(self):
        self.assertEqual(_resolve_initial_workspace("", ""), "")

    def test_workspace_argument_is_canonicalized(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = os.path.join(root, "project")
            os.mkdir(workspace)

            resolved = _resolve_initial_workspace(workspace, "")

        self.assertEqual(resolved, os.path.realpath(os.path.abspath(workspace)))

    def test_workspace_option_takes_precedence(self):
        with tempfile.TemporaryDirectory() as root:
            positional = os.path.join(root, "positional")
            option = os.path.join(root, "option")
            os.mkdir(positional)
            os.mkdir(option)

            resolved = _resolve_initial_workspace(option, positional)

        self.assertEqual(resolved, os.path.realpath(os.path.abspath(option)))

    def test_missing_explicit_workspace_raises_value_error(self):
        with tempfile.TemporaryDirectory() as root:
            missing = os.path.join(root, "missing")
            with self.assertRaises(ValueError) as raised:
                _resolve_initial_workspace(missing, "")

        self.assertIn("Workspace not found", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
