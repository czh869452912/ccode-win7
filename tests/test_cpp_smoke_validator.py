import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-cpp-smoke.py"


class TestCppSmokeValidator(unittest.TestCase):
    def test_missing_bundled_clang_fails_without_system_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle_root = root / "bundle"
            workspace = bundle_root / "data" / "workspace-template"
            workspace.mkdir(parents=True)
            (workspace / "main.c").write_text("int main(void) { return 0; }\n", encoding="ascii")
            report_path = root / "report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--bundle-root",
                    str(bundle_root),
                    "--workspace",
                    str(workspace),
                    "--json-report",
                    str(report_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["runtime_source"], "missing")
            self.assertIn("system fallback is disabled", payload["error"])

    def test_compiles_with_explicit_clang_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "main.c").write_text("int main(void) { return 0; }\n", encoding="ascii")
            fake_clang = root / "fake-clang.cmd"
            fake_clang.write_text(
                "\n".join(
                    [
                        "@echo off",
                        'if "%1"=="--version" (',
                        "  echo fake clang 109",
                        "  exit /b 0",
                        ")",
                        "set OUT=",
                        ":loop",
                        'if "%1"=="" goto done',
                        'if "%1"=="-o" (',
                        "  set OUT=%2",
                        "  shift",
                        ")",
                        "shift",
                        "goto loop",
                        ":done",
                        'if "%OUT%"=="" exit /b 2',
                        'echo object > "%OUT%"',
                        "exit /b 0",
                    ]
                )
                + "\n",
                encoding="ascii",
            )
            report_path = root / "report.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--workspace",
                    str(workspace),
                    "--clang",
                    str(fake_clang),
                    "--json-report",
                    str(report_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["runtime_source"], "override")
            self.assertTrue(Path(payload["object_path"]).exists())


if __name__ == "__main__":
    unittest.main()
