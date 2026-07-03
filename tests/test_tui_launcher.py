import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from embedagent.frontend.tui import launcher as tui_launcher


class TestTuiLauncher(unittest.TestCase):
    def test_launch_tui_uses_hosted_runtime_factory(self):
        runtime = MagicMock()
        with tempfile.TemporaryDirectory() as workspace:
            real_workspace = os.path.realpath(workspace)
            with patch(
                "embedagent.frontend.tui.launcher.resolve_launch_config",
                return_value=MagicMock(workspace=real_workspace),
            ) as resolve_config, patch(
                "embedagent.frontend.tui.launcher.create_hosted_runtime",
                return_value=runtime,
            ) as create_runtime, patch(
                "embedagent.frontend.tui.launcher.run_tui",
                return_value=0,
            ) as run_tui:
                exit_code = tui_launcher.launch_tui(
                    workspace=workspace,
                    max_turns=3,
                    agent_application_id="tests.python",
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(resolve_config.call_args.args[0], real_workspace)
        self.assertEqual(resolve_config.call_args.kwargs["overrides"].max_turns, 3)
        self.assertEqual(
            resolve_config.call_args.kwargs["overrides"].agent_application_id,
            "tests.python",
        )
        create_runtime.assert_called_once()
        self.assertIs(run_tui.call_args.kwargs["session_host"], runtime.session_host)

    def test_tui_bootstrap_architecture_guard_blocks_direct_runtime_construction(self):
        with open("src/embedagent/frontend/tui/bootstrap.py", "r", encoding="utf-8") as fh:
            text = fh.read()
        blocked = [
            "OpenAICompatibleClient(",
            "ToolRuntime(",
            "ContextManager(",
            "PermissionPolicy(",
            "InProcessAdapter(",
            "load_config(",
        ]
        for needle in blocked:
            self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
