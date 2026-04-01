import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "scripts" / "package-lib.ps1"
CONFIG = ROOT / "scripts" / "package.config.json"
EXPORT_SCRIPT = ROOT / "scripts" / "export-dependencies.py"
CHECK_SCRIPT = ROOT / "scripts" / "check-bundle-dependencies.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate-offline-bundle.ps1"
PACKAGE_SCRIPT = ROOT / "scripts" / "package.ps1"


def _powershell_exe():
    candidates = [
        Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("No PowerShell executable found for packaging tests.")


def run_pwsh(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_powershell_exe(), "-NoProfile", "-Command", command],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


class TestPackageFoundation(unittest.TestCase):
    def test_config_exposes_dev_and_release_profiles(self):
        result = run_pwsh(
            ". '{lib}'; "
            "$cfg = Read-PackageConfig -Path '{config}'; "
            "[ordered]@{{default_profile=$cfg.default_profile; profiles=@($cfg.profiles.PSObject.Properties.Name)}} "
            "| ConvertTo-Json -Compress".format(
                lib=str(LIB).replace("\\", "\\\\"),
                config=str(CONFIG).replace("\\", "\\\\"),
            )
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["default_profile"], "dev")
        self.assertEqual(sorted(payload["profiles"]), ["dev", "release"])

    def test_release_report_maps_success_to_ready(self):
        result = run_pwsh(
            ". '{lib}'; "
            "$report = New-PackageReport -Command 'release' -Profile 'release'; "
            "Add-StageResult -Report ([ref]$report) -Name 'verify' -Status 'pass' -ExitCode 0 -Summary @{{validator='ok'}}; "
            "Complete-PackageReport -Report ([ref]$report); "
            "$report | ConvertTo-Json -Depth 8 -Compress".format(
                lib=str(LIB).replace("\\", "\\\\"),
            )
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["final_status"], "READY")


class TestStageJsonReports(unittest.TestCase):
    def test_dependency_checker_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            report_path = bundle_root / "dependency-report.json"
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), str(bundle_root), "--json-report", str(report_path)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["bundle_root"], str(bundle_root))
            self.assertTrue(payload["checks"])
            self.assertEqual(payload["checks"][0]["name"], "Python Runtime")
            self.assertFalse(payload["checks"][0]["ok"])

    def test_dependency_checker_autodetect_failure_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            report_path = temp_root / "dependency-report.json"
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), "--json-report", str(report_path)],
                cwd=str(temp_root),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["bundle_root"], "")
            self.assertEqual(payload["checks"], [])
            self.assertIn("Cannot find bundle root", payload["error"])

    def test_export_verify_only_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_root = Path(tmp)
            site_packages = export_root / "site-packages"
            site_packages.mkdir()
            for name in [
                "prompt_toolkit",
                "rich",
                "webview",
                "fastapi",
                "uvicorn",
                "websockets",
                "starlette",
                "pydantic",
                "anyio",
                "click",
                "h11",
                "idna",
                "sniffio",
                "typing_extensions",
            ]:
                (site_packages / name).mkdir()
            report_path = export_root / "export-report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT_SCRIPT),
                    "--output-dir",
                    str(export_root),
                    "--verify-only",
                    "--json-report",
                    str(report_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["mode"], "verify-only")
            self.assertEqual(payload["site_packages_root"], str(site_packages))
            self.assertEqual(payload["missing_packages"], [])

    def test_validate_offline_bundle_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "bundle"
            sources_root = Path(tmp) / "sources"
            bundle_root.mkdir()
            sources_root.mkdir()
            json_path = Path(tmp) / "validate-report.json"
            result = subprocess.run(
                [
                    _powershell_exe(),
                    "-NoProfile",
                    "-File",
                    str(VALIDATE_SCRIPT),
                    "-BundleRoot",
                    str(bundle_root),
                    "-SourcesRoot",
                    str(sources_root),
                    "-ZipPath",
                    str(Path(tmp) / "bundle.zip"),
                    "-SkipDynamicChecks",
                    "-JsonOutputPath",
                    str(json_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["skip_dynamic_checks"], True)
            self.assertEqual(payload["bundle_root"], str(bundle_root))
            self.assertEqual(payload["sources_root"], str(sources_root))
            self.assertEqual(payload["fail_count"], 0)
            self.assertTrue(isinstance(payload["results"], list))

    def test_export_failure_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            report_path = temp_root / "export-failure-report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT_SCRIPT),
                    "--output-dir",
                    str(temp_root / "out"),
                    "--project-root",
                    str(temp_root / "missing-project"),
                    "--json-report",
                    str(report_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(report_path.exists())
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["mode"], "export")
            self.assertEqual(payload["output_dir"], str(temp_root / "out"))
            self.assertIn("error", payload)


class TestPackageDoctor(unittest.TestCase):
    def test_package_doctor_emits_json_summary(self):
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "doctor",
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "doctor")
        self.assertEqual(payload["command_status"], "READY")
        self.assertIsNone(payload["final_status"])
        self.assertIn("doctor_checks", payload)
        self.assertTrue(payload["doctor_checks"])
        config_checks = [check for check in payload["doctor_checks"] if check.get("name") == "config"]
        self.assertEqual(len(config_checks), 1)
        self.assertTrue(config_checks[0]["ok"])
        self.assertIn("package.config.json", config_checks[0]["path"])

    def test_package_doctor_fails_for_missing_config(self):
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "doctor",
                "-Config",
                "scripts/does-not-exist.json",
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "doctor")
        self.assertEqual(payload["command_status"], "NOT_READY")
        self.assertIsNone(payload["final_status"])
        self.assertTrue(payload["blocking_issues"])
        self.assertIn("Package config not found", payload["blocking_issues"][0])

    def test_package_non_doctor_command_fails_before_config_load(self):
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "deps",
                "-Config",
                "scripts/does-not-exist.json",
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "deps")
        self.assertEqual(payload["command_status"], "NOT_READY")
        self.assertIsNone(payload["final_status"])
        self.assertTrue(payload["blocking_issues"])
        self.assertIn("Not implemented yet: deps", payload["blocking_issues"][0])
        self.assertNotIn("Package config not found", payload["blocking_issues"][0])


if __name__ == "__main__":
    unittest.main()
