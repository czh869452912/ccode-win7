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



if __name__ == "__main__":
    unittest.main()
