import hashlib
import json
import os
import shutil
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
MOCK_CONFIG = ROOT / "tests" / "fixtures" / "package" / "mock-config.json"


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
        encoding="utf-8",
        errors="replace",
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

    def test_python_stage_resolution_prefers_project_relative_venv(self):
        project_root = ROOT / "build" / "test-tmp" / "python-resolution"
        shutil.rmtree(project_root, ignore_errors=True)
        project_root.mkdir(parents=True, exist_ok=True)
        try:
            python_exe = project_root / ".venv" / "Scripts" / "python.exe"
            python_exe.parent.mkdir(parents=True)
            python_exe.write_text("", encoding="utf-8")

            result = run_pwsh(
                ". '{lib}'; "
                "$resolved = Resolve-PackagePythonPath -ProjectRoot '{project_root}'; "
                "$resolved | ConvertTo-Json -Compress".format(
                    lib=str(LIB).replace("\\", "\\\\"),
                    project_root=str(project_root).replace("\\", "\\\\"),
                )
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload, str(python_exe))
        finally:
            shutil.rmtree(project_root, ignore_errors=True)

    def test_python_stage_resolution_does_not_fallback_to_path_python(self):
        project_root = ROOT / "build" / "test-tmp" / "python-resolution-missing"
        shutil.rmtree(project_root, ignore_errors=True)
        project_root.mkdir(parents=True, exist_ok=True)
        try:
            result = run_pwsh(
                "$env:EMBEDAGENT_PYTHON = ''; "
                ". '{lib}'; "
                "Resolve-PackagePythonPath -ProjectRoot '{project_root}'".format(
                    lib=str(LIB).replace("\\", "\\\\"),
                    project_root=str(project_root).replace("\\", "\\\\"),
                )
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Expected project virtualenv", result.stderr)
        finally:
            shutil.rmtree(project_root, ignore_errors=True)


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

    def test_dependency_checker_tolerates_gbk_console(self):
        test_root = ROOT / "build" / "test-tmp" / "dependency-check-gbk"
        shutil.rmtree(test_root, ignore_errors=True)
        test_root.mkdir(parents=True, exist_ok=True)
        try:
            bundle_root = test_root / "bundle"
            bundle_root.mkdir()
            report_path = test_root / "dependency-report.json"
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "gbk"
            result = subprocess.run(
                [
                    sys.executable,
                    str(CHECK_SCRIPT),
                    str(bundle_root),
                    "--json-report",
                    str(report_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            self.assertNotIn("UnicodeEncodeError", result.stderr)
            self.assertTrue(report_path.exists())
        finally:
            shutil.rmtree(test_root, ignore_errors=True)

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

    def test_validate_offline_bundle_accepts_single_line_checksums(self):
        test_root = ROOT / "build" / "test-tmp" / "validate-single-checksum"
        shutil.rmtree(test_root, ignore_errors=True)
        test_root.mkdir(parents=True, exist_ok=True)
        try:
            bundle_root = test_root / "bundle"
            sources_root = test_root / "sources"
            bundle_root.mkdir()
            sources_root.mkdir()
            payload_file = sources_root / "assets-manifest.json"
            payload_file.write_text("{}", encoding="utf-8")
            payload_hash = hashlib.sha256(payload_file.read_bytes()).hexdigest()
            (sources_root / "checksums.txt").write_text(
                "{0} *assets-manifest.json\n".format(payload_hash),
                encoding="ascii",
            )
            json_path = test_root / "validate-report.json"
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
                    str(test_root / "bundle.zip"),
                    "-SkipDynamicChecks",
                    "-JsonOutputPath",
                    str(json_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            result_codes = [item["code"] for item in payload["results"]]
            self.assertIn("sources.checksums.ok", result_codes)
        finally:
            shutil.rmtree(test_root, ignore_errors=True)

    def test_validate_offline_bundle_accepts_multi_line_checksums(self):
        test_root = ROOT / "build" / "test-tmp" / "validate-multi-checksum"
        shutil.rmtree(test_root, ignore_errors=True)
        test_root.mkdir(parents=True, exist_ok=True)
        try:
            bundle_root = test_root / "bundle"
            sources_root = test_root / "sources"
            manifest_root = bundle_root / "manifests"
            manifest_root.mkdir(parents=True)
            sources_root.mkdir()

            payload_a = bundle_root / "alpha.txt"
            payload_b = bundle_root / "beta.txt"
            payload_a.write_text("alpha", encoding="utf-8")
            payload_b.write_text("beta", encoding="utf-8")
            manifest_root.joinpath("checksums.txt").write_text(
                "{0} *alpha.txt\n{1} *beta.txt\n".format(
                    hashlib.sha256(payload_a.read_bytes()).hexdigest(),
                    hashlib.sha256(payload_b.read_bytes()).hexdigest(),
                ),
                encoding="ascii",
            )
            json_path = test_root / "validate-report.json"
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
                    str(test_root / "bundle.zip"),
                    "-SkipDynamicChecks",
                    "-JsonOutputPath",
                    str(json_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            result_codes = [item["code"] for item in payload["results"]]
            self.assertIn("bundle.checksums.ok", result_codes)
            self.assertNotIn("bundle.checksums.format", result_codes)
        finally:
            shutil.rmtree(test_root, ignore_errors=True)

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
        npm_checks = [check for check in payload["doctor_checks"] if check.get("name") == "runtime:npm"]
        self.assertEqual(len(npm_checks), 1)

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

    def test_package_non_doctor_command_reports_missing_config(self):
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
        self.assertIn("Package config not found", payload["blocking_issues"][0])


class TestPackageOrchestration(unittest.TestCase):
    def test_package_verify_returns_not_ready_for_missing_bundle(self):
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "verify",
                "-BundleRoot",
                "build/does-not-exist",
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "verify")
        self.assertEqual(payload["command_status"], "completed")
        self.assertEqual(payload["final_status"], "NOT_READY")
        self.assertTrue(payload["report_path"])
        self.assertTrue(Path(payload["report_path"]).exists())
        self.assertTrue(payload["stages"])
        verify_stage = payload["stages"][-1]
        self.assertEqual(verify_stage["name"], "verify")
        self.assertEqual(verify_stage["status"], "fail")
        self.assertEqual(verify_stage["summary"]["reason"], "bundle_root_missing")
        self.assertTrue(payload["blocking_issues"])

    def test_package_release_with_mock_stages_returns_ready(self):
        env = os.environ.copy()
        env["EMBEDAGENT_PYTHON"] = sys.executable
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "release",
                "-Config",
                str(MOCK_CONFIG),
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "release")
        self.assertEqual(payload["command_status"], "completed")
        self.assertEqual(payload["final_status"], "READY")
        self.assertTrue(payload["report_path"])
        report_path = Path(payload["report_path"])
        self.assertTrue(report_path.exists())
        latest_path = report_path.parent / "latest.json"
        self.assertTrue(latest_path.exists())
        stage_names = [stage["name"] for stage in payload["stages"]]
        self.assertEqual(stage_names, ["deps", "prepare", "build", "verify"])
        stage_statuses = [stage["status"] for stage in payload["stages"]]
        self.assertEqual(stage_statuses, ["pass", "pass", "pass", "pass"])
        verify_summary = payload["stages"][-1]["summary"]
        self.assertTrue(verify_summary["validate_report"])
        self.assertTrue(verify_summary["dependency_report"])

    def test_mock_release_does_not_inject_frontend_build_stage(self):
        env = os.environ.copy()
        env["EMBEDAGENT_PYTHON"] = sys.executable
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "release",
                "-Config",
                str(MOCK_CONFIG),
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=env,
        )
        payload = json.loads(result.stdout)
        stage_names = [stage["name"] for stage in payload.get("stages", [])]
        self.assertNotIn("frontend_build", stage_names)


if __name__ == "__main__":
    unittest.main()
