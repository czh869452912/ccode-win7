import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.launcher import _resolve_initial_workspace


class TestGuiLauncherAppMode(unittest.TestCase):
    def test_gui_rejects_unplanned_shell_before_dependency_checks(self):
        policy = MagicMock()
        policy.require_shell.side_effect = ValueError(
            "gui is not included in bundle flavor minimal-cli"
        )
        with patch(
            "embedagent.frontend.gui.launcher.load_current_bundle_policy",
            return_value=policy,
        ), patch("embedagent.frontend.gui.launcher.check_dependencies") as dependencies:
            with self.assertRaisesRegex(ValueError, "not included in bundle flavor"):
                from embedagent.frontend.gui.launcher import launch_gui

                launch_gui()

        policy.require_shell.assert_called_once_with("gui")
        dependencies.assert_not_called()

    def test_no_workspace_arguments_return_empty_string(self):
        self.assertEqual(_resolve_initial_workspace("", ""), "")

    def test_workspace_argument_is_canonicalized(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = os.path.join(root, "project")
            os.mkdir(workspace)

            resolved = _resolve_initial_workspace(workspace, "")

        self.assertEqual(resolved, os.path.abspath(workspace))

    def test_workspace_option_takes_precedence(self):
        with tempfile.TemporaryDirectory() as root:
            positional = os.path.join(root, "positional")
            option = os.path.join(root, "option")
            os.mkdir(positional)
            os.mkdir(option)

            resolved = _resolve_initial_workspace(option, positional)

        self.assertEqual(resolved, os.path.abspath(option))

    def test_missing_explicit_workspace_raises_value_error(self):
        with tempfile.TemporaryDirectory() as root:
            missing = os.path.join(root, "missing")
            with self.assertRaises(ValueError) as raised:
                _resolve_initial_workspace(missing, "")

        self.assertIn("Workspace not found", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
