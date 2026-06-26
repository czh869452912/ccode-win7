import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.config import AppConfig
from embedagent.frontend.tui import launcher as tui_launcher


class TestTuiLauncher(unittest.TestCase):
    def test_launch_tui_ignores_persistent_max_turns_config(self):
        app_config = AppConfig(
            base_url="http://internal/v1",
            api_key="sk-internal",
            model="qwen3.5-coder",
            timeout=45,
            max_turns=8,
        )
        with tempfile.TemporaryDirectory() as workspace:
            with patch(
                "embedagent.frontend.tui.launcher.load_config", return_value=app_config
            ), patch("embedagent.frontend.tui.launcher.run_tui", return_value=0) as run_tui:
                exit_code = tui_launcher.launch_tui(workspace=workspace)

        self.assertEqual(exit_code, 0)
        self.assertIsNone(run_tui.call_args.kwargs["max_turns"])

    def test_launch_tui_accepts_explicit_runtime_safety_limit(self):
        app_config = AppConfig(
            base_url="http://internal/v1",
            api_key="sk-internal",
            model="qwen3.5-coder",
            timeout=45,
            max_turns=8,
        )
        with tempfile.TemporaryDirectory() as workspace:
            with patch(
                "embedagent.frontend.tui.launcher.load_config", return_value=app_config
            ), patch("embedagent.frontend.tui.launcher.run_tui", return_value=0) as run_tui:
                exit_code = tui_launcher.launch_tui(workspace=workspace, max_turns=3)

        self.assertEqual(exit_code, 0)
        self.assertEqual(run_tui.call_args.kwargs["max_turns"], 3)


if __name__ == "__main__":
    unittest.main()
