import importlib.util
import os
import tempfile
import unittest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))


def _load_smoke_script():
    path = os.path.join(ROOT, "scripts", "validate-gui-smoke.py")
    spec = importlib.util.spec_from_file_location("gui_smoke_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestGuiSmokeContract(unittest.TestCase):
    def _script_text(self):
        path = os.path.join(ROOT, "scripts", "validate-gui-smoke.py")
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def _visual_script_text(self):
        path = os.path.join(ROOT, "scripts", "gui-visual-debug.mjs")
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_smoke_launcher_uses_workspace_scoped_app_home(self):
        smoke = _load_smoke_script()
        with tempfile.TemporaryDirectory() as root:
            bundle_root = os.path.join(root, "bundle")
            workspace = os.path.join(root, "workspace")
            os.makedirs(bundle_root)
            os.makedirs(workspace)
            with open(os.path.join(bundle_root, "embedagent-gui.cmd"), "w") as handle:
                handle.write("")

            launch = smoke._build_command(bundle_root, workspace, 18080, 18081)

            self.assertEqual(
                launch["env"]["EMBEDAGENT_GUI_APP_HOME"],
                os.path.join(workspace, ".embedagent-gui-home"),
            )

    def test_smoke_exercises_current_session_event_protocol(self):
        text = self._script_text()
        self.assertIn('"session_event"', text)
        self.assertIn('"transition.recorded"', text)
        self.assertIn("/interactions/%s/respond", text)
        for retired_branch in (
            'if msg_type == "stream_delta"',
            'if msg_type == "tool_start"',
            'if msg_type == "tool_finish"',
            'if msg_type == "command_result"',
            'if msg_type == "permission_request"',
            'if msg_type == "user_input_request"',
            'if msg_type == "session_status"',
        ):
            self.assertNotIn(retired_branch, text)

    def test_fixed_webview2_path_version_detection(self):
        smoke = _load_smoke_script()
        versioned_path = os.path.join("bundle", "109.0.1518.78")
        self.assertEqual(smoke._detect_webview2_runtime_major(versioned_path), 109)

    def test_smoke_fake_provider_does_not_match_task_as_ask(self):
        smoke = _load_smoke_script()
        self.assertEqual(
            smoke.FakeOpenAIHandler._tool_call_for_text("task smoke")["name"], "task_status"
        )

    def test_smoke_fake_provider_uses_official_bash_tool(self):
        text = self._script_text()
        self.assertIn('"name": "bash"', text)
        self.assertNotIn('"name": "run_command"', text)

    def test_smoke_script_uses_current_task_contract(self):
        text = self._script_text()
        self.assertNotIn("manage" + "_to" + "dos", text)
        self.assertNotIn("/api/" + "to" + "dos", text)
        self.assertNotIn("mode=code", text)
        self.assertNotIn("/api/tasks", text)
        self.assertIn("/api/sessions/%s/bootstrap", text)

    def test_smoke_script_prefers_native_bundle_gui_launcher(self):
        text = self._script_text()

        self.assertIn('"embedagent-gui.exe"', text)
        self.assertIn('"embedagent-gui.cmd"', text)
        self.assertLess(text.index('"embedagent-gui.exe"'), text.index('"embedagent-gui.cmd"'))

    def test_bundle_smoke_requires_fixed_webview2_runtime(self):
        text = self._script_text()

        self.assertIn("--require-fixed-webview2", text)
        self.assertIn("runtime\\webview2-fixed-runtime\\msedgewebview2.exe", text)
        self.assertIn('"runtime_major"', text)
        self.assertIn('"expected_runtime_major"', text)

    def test_smoke_script_exposes_structured_diagnostics(self):
        text = self._script_text()

        for marker in (
            "--json-report",
            "--diagnostic-dir",
            "--startup-timeout",
            "/api/app/bootstrap",
            "launcher_exit",
            "http_timeout",
            "app_bootstrap_failure",
            "protocol_failure",
            "model_failure",
            "renderer_failure",
            "cleanup_failure",
        ):
            self.assertIn(marker, text)

    def test_visual_smoke_covers_minimal_shell_and_optional_contributions(self):
        text = self._visual_script_text()

        for scenario in (
            "empty",
            "session",
            "streaming",
            "tool",
            "interaction",
            "commands",
            "recovery",
            "narrow",
            "optional-terminal",
            "optional-diff",
        ):
            self.assertIn('"%s"' % scenario, text)
        for marker in (
            "[data-agent-shell]",
            "[data-session-timeline]",
            "[data-session-composer]",
            "elementsFromPoint",
            "documentWidth",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
