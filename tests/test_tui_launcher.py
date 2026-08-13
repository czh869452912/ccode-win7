import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from embedagent_protocol import ShellDescriptor

from embedagent.frontend.tui import launcher as tui_launcher


class TestTuiLauncher(unittest.TestCase):
    def test_tui_rejects_unplanned_shell_before_runtime_construction(self):
        policy = MagicMock()
        policy.require_shell.side_effect = ValueError(
            "tui is not included in bundle flavor minimal-cli"
        )
        with tempfile.TemporaryDirectory() as workspace, patch(
            "embedagent.frontend.tui.launcher.load_current_bundle_policy",
            return_value=policy,
        ), patch("embedagent.frontend.tui.launcher.resolve_launch_config") as resolve_config:
            with self.assertRaisesRegex(ValueError, "not included in bundle flavor"):
                tui_launcher.launch_tui(workspace=workspace)

        policy.require_shell.assert_called_once_with("tui")
        resolve_config.assert_not_called()

    def test_launch_tui_uses_hosted_runtime_factory(self):
        runtime = MagicMock()
        runtime.session_host.get_session_capabilities.return_value = {}
        descriptor = ShellDescriptor()
        application_registry = MagicMock()
        application_registry.record_by_id.return_value.application_id = "tests.python"
        compiler = MagicMock(return_value=descriptor)
        with tempfile.TemporaryDirectory() as workspace:
            real_workspace = os.path.realpath(workspace)
            with patch(
                "embedagent.frontend.tui.launcher.resolve_launch_config",
                return_value=MagicMock(
                    workspace=real_workspace, agent_application_id="tests.python"
                ),
            ) as resolve_config, patch(
                "embedagent.frontend.tui.launcher.create_hosted_runtime",
                return_value=runtime,
            ) as create_runtime, patch(
                "embedagent.frontend.tui.launcher.product_agent_application_registry",
                return_value=application_registry,
            ), patch(
                "embedagent.frontend.tui.launcher.product_shell_compiler",
                return_value=compiler,
            ), patch(
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
        compiler.assert_called_once_with("tests.python", {})
        self.assertIs(run_tui.call_args.kwargs["shell_descriptor"], descriptor)
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
        self.assertIn(
            "TerminalRuntime(session_host, shell_descriptor, dispatch=action_dispatch)", text
        )
        self.assertIn("runtime=runtime", text)
        self.assertNotIn("session_host.adapter", text)

        with open("src/embedagent/frontend/tui/app.py", "r", encoding="utf-8") as fh:
            app_text = fh.read()
        self.assertIn("self.runtime = runtime", app_text)
        self.assertNotIn("self.adapter", app_text)
        self.assertNotIn("SessionService", app_text)
        self.assertNotIn("TimelineService", app_text)
        self.assertNotIn("WorkspaceService", app_text)

    def test_shell_launchers_delegate_configuration_loading(self):
        paths = (
            "src/embedagent/cli.py",
            "src/embedagent/frontend/tui/launcher.py",
            "src/embedagent/frontend/gui/launcher.py",
        )
        for path in paths:
            with self.subTest(path=path), open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
            self.assertNotIn("from embedagent.config import load_config", source)
            self.assertNotIn("load_config(", source)


if __name__ == "__main__":
    unittest.main()
