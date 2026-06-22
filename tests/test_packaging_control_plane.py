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
RUNTIME_CONTRACT = ROOT / "scripts" / "offline-runtime-contract.json"
MOCK_CONFIG = ROOT / "tests" / "fixtures" / "package" / "mock-config.json"


def _powershell_exe():
    candidates = [
        Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe",
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


@unittest.skipIf(sys.platform != "win32", "Windows-only: requires PowerShell")
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


@unittest.skipIf(sys.platform != "win32", "Windows-only: requires PowerShell")
class TestGuiFrontendAssets(unittest.TestCase):
    def test_gui_frontend_asset_status_requires_katex_css(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            static_root = project_root / "src" / "embedagent" / "frontend" / "gui" / "static"
            assets_root = static_root / "assets"
            assets_root.mkdir(parents=True)
            (static_root / "index.html").write_text("<html></html>", encoding="utf-8")
            (assets_root / "app.js").write_text("console.log('ok')", encoding="utf-8")
            (assets_root / "app.css").write_text("body{}", encoding="utf-8")
            result = run_pwsh(
                ". '{lib}'; "
                "$status = Get-GuiFrontendAssetStatus -ProjectRoot '{project_root}'; "
                "$status | ConvertTo-Json -Depth 6 -Compress".format(
                    lib=str(LIB).replace("\\", "\\\\"),
                    project_root=str(project_root).replace("\\", "\\\\"),
                )
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("katex.min.css", payload["missing"])

    def test_ensure_gui_frontend_assets_accepts_complete_prebuilt_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            static_root = project_root / "src" / "embedagent" / "frontend" / "gui" / "static"
            assets_root = static_root / "assets"
            katex_root = assets_root / "katex"
            katex_root.mkdir(parents=True)
            (static_root / "index.html").write_text("<html></html>", encoding="utf-8")
            (assets_root / "app.js").write_text("console.log('ok')", encoding="utf-8")
            (assets_root / "app.css").write_text("body{}", encoding="utf-8")
            (katex_root / "katex.min.css").write_text("/* katex */", encoding="utf-8")
            result = run_pwsh(
                ". '{lib}'; "
                "$status = Ensure-GuiFrontendAssets -ProjectRoot '{project_root}'; "
                "$status | ConvertTo-Json -Depth 6 -Compress".format(
                    lib=str(LIB).replace("\\", "\\\\"),
                    project_root=str(project_root).replace("\\", "\\\\"),
                )
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["mode"], "prebuilt")

    def test_gui_bundle_asset_status_checks_staging_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "bundle"
            static_root = bundle_root / "app" / "embedagent" / "frontend" / "gui" / "static"
            assets_root = static_root / "assets"
            assets_root.mkdir(parents=True)
            (static_root / "index.html").write_text("<html></html>", encoding="utf-8")
            (assets_root / "app.js").write_text("console.log('ok')", encoding="utf-8")
            (assets_root / "app.css").write_text("body{}", encoding="utf-8")
            result = run_pwsh(
                ". '{lib}'; "
                "$status = Get-GuiBundleAssetStatus -BundleRoot '{bundle_root}'; "
                "$status | ConvertTo-Json -Depth 6 -Compress".format(
                    lib=str(LIB).replace("\\", "\\\\"),
                    bundle_root=str(bundle_root).replace("\\", "\\\\"),
                )
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("katex.min.css", payload["missing"])

    def test_prepare_offline_stages_active_packaging_docs(self):
        script = (ROOT / "scripts" / "prepare-offline.ps1").read_text(encoding="utf-8")
        expected_sources = [
            "docs\\guides\\configuration-guide.md",
            "docs\\guides\\win7-preflight-checklist.md",
            "docs\\guides\\intranet-deployment.md",
            "docs\\guides\\win7-gui-validation.md",
        ]

        missing = [path for path in expected_sources if path not in script]
        self.assertEqual(missing, [])


class TestRuntimeBundleContract(unittest.TestCase):
    def test_runtime_contract_lists_managed_tools(self):
        payload = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], 1)
        tool_ids = [item["id"] for item in payload["required_tools"]]
        self.assertEqual(tool_ids, ["python", "git", "rg", "ctags", "llvm"])
        for item in payload["required_tools"]:
            self.assertTrue(item["component"])
            self.assertTrue(item["category"])
            self.assertTrue(item.get("paths") or item.get("alternatives"))

    def test_runtime_contract_lists_current_llvm_children(self):
        payload = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))
        llvm = [item for item in payload["required_tools"] if item["id"] == "llvm"][0]
        child_paths = [child["path"] for child in llvm["children"]]

        self.assertEqual(
            child_paths,
            [
                "bin/llvm/bin/clang.exe",
                "bin/llvm/bin/clang++.exe",
                "bin/llvm/bin/clang-cl.exe",
                "bin/llvm/bin/clang-tidy.exe",
                "bin/llvm/bin/clang-analyzer.bat",
                "bin/llvm/bin/llvm-profdata.exe",
                "bin/llvm/bin/llvm-cov.exe",
            ],
        )


class TestPrepareOfflineContract(unittest.TestCase):
    def _script_text(self):
        return (ROOT / "scripts" / "prepare-offline.ps1").read_text(encoding="utf-8")

    def test_package_config_exposes_gui_launcher_build_tool(self):
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))

        self.assertIn("gui_launcher_build_root", payload["paths"])
        self.assertEqual(
            payload["tooling"]["build_gui_launcher"],
            "scripts/build-gui-launcher.ps1",
        )
        self.assertTrue(payload["profiles"]["dev"]["run_gui_launcher_build"])
        self.assertTrue(payload["profiles"]["release"]["run_gui_launcher_build"])

    def test_prepare_offline_uses_current_default_mode(self):
        script = self._script_text()
        self.assertNotIn('"default_mode": "code"', script)
        self.assertIn('"default_mode": "explore"', script)
        self.assertNotIn('"max_turns": 8', script)
        self.assertIn('"max_turns": null', script)

    def test_prepare_offline_stages_real_c_workspace_template(self):
        script = self._script_text()
        self.assertNotIn("This directory is a placeholder", script)
        self.assertIn("data\\workspace-template\\main.c", script)
        self.assertIn("data\\workspace-template\\README.md", script)
        self.assertIn("int main(void)", script)

    def test_prepare_offline_contract_mentions_native_gui_launcher_component(self):
        script = self._script_text()

        self.assertIn("GuiLauncherExePath", script)
        self.assertIn("gui_launcher_exe", script)
        self.assertIn("EmbedAgent.exe", script)
        self.assertIn("embedagent-gui.exe", script)


@unittest.skipIf(sys.platform != "win32", "Windows-only: requires PowerShell")
class TestStageJsonReports(unittest.TestCase):
    def test_dependency_checker_writes_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            report_path = bundle_root / "dependency-report.json"
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

    def test_dependency_checker_autodetect_requires_strong_bundle_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            incomplete_root = temp_root / "incomplete-bundle"
            (incomplete_root / "runtime" / "python").mkdir(parents=True)
            report_path = temp_root / "dependency-report.json"
            result = subprocess.run(
                [sys.executable, str(CHECK_SCRIPT), "--json-report", str(report_path)],
                cwd=str(incomplete_root),
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

    def test_dependency_checker_reports_runtime_contract_missing_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            (bundle_root / "app" / "embedagent").mkdir(parents=True)
            (bundle_root / "runtime" / "python").mkdir(parents=True)
            (bundle_root / "bin").mkdir()
            report_path = bundle_root / "dependency-report.json"
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
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            external = [item for item in payload["checks"] if item["name"] == "External Tools"][0]
            self.assertFalse(external["ok"])
            self.assertTrue(any("runtime_tool.git" in error for error in external["errors"]))
            self.assertTrue(any("runtime_tool.llvm.clang" in error for error in external["errors"]))
            self.assertEqual(payload["runtime_contract"]["schema_version"], 1)

    def test_dependency_checker_accepts_runtime_contract_complete_mock_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            for path in [
                "app/embedagent/__init__.py",
                "runtime/python/python.exe",
                "runtime/site-packages/embedagent/__init__.py",
                "runtime/site-packages/prompt_toolkit/__init__.py",
                "runtime/site-packages/rich/__init__.py",
                "runtime/site-packages/webview/__init__.py",
                "runtime/site-packages/fastapi/__init__.py",
                "runtime/site-packages/uvicorn/__init__.py",
                "runtime/site-packages/websockets/__init__.py",
                "runtime/site-packages/starlette/__init__.py",
                "runtime/site-packages/pydantic/__init__.py",
                "runtime/site-packages/anyio/__init__.py",
                "runtime/site-packages/sniffio/__init__.py",
                "runtime/site-packages/h11/__init__.py",
                "runtime/site-packages/idna/__init__.py",
                "runtime/site-packages/click/__init__.py",
                "runtime/site-packages/typing_extensions.py",
                "runtime/site-packages/colorama/__init__.py",
                "runtime/site-packages/pygments/__init__.py",
                "runtime/site-packages/wcwidth/__init__.py",
                "runtime/site-packages/extra_a/__init__.py",
                "runtime/site-packages/extra_b/__init__.py",
                "runtime/site-packages/extra_c/__init__.py",
                "bin/git/cmd/git.exe",
                "bin/rg/rg.exe",
                "bin/ctags/ctags.exe",
                "bin/llvm/bin/clang.exe",
                "bin/llvm/bin/clang++.exe",
                "bin/llvm/bin/clang-cl.exe",
                "bin/llvm/bin/clang-tidy.exe",
                "bin/llvm/bin/clang-analyzer.bat",
                "bin/llvm/bin/llvm-profdata.exe",
                "bin/llvm/bin/llvm-cov.exe",
                "EmbedAgent.exe",
                "embedagent-gui.exe",
                "embedagent.cmd",
                "embedagent-tui.cmd",
                "embedagent-gui.cmd",
                "config/config.json",
                "config/config.json.template",
                "config/permission-rules.json",
                "docs/configuration-guide.md",
                "docs/win7-preflight-checklist.md",
                "docs/intranet-deployment.md",
                "app/embedagent/frontend/gui/static/index.html",
                "app/embedagent/frontend/gui/static/assets/app.js",
                "manifests/bundle-manifest.json",
            ]:
                target = bundle_root / Path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("{}", encoding="ascii")
            (bundle_root / "manifests" / "bundle-manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "artifact_name": "mock",
                        "components": [],
                    }
                ),
                encoding="ascii",
            )
            report_path = bundle_root / "dependency-report.json"
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
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])

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

    def test_validate_offline_bundle_fails_strict_for_missing_runtime_contract_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "bundle"
            sources_root = Path(tmp) / "sources"
            (bundle_root / "app" / "embedagent").mkdir(parents=True)
            (bundle_root / "runtime" / "python").mkdir(parents=True)
            (bundle_root / "bin" / "llvm" / "bin").mkdir(parents=True)
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
                    "-RequireComplete",
                    "-JsonOutputPath",
                    str(json_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            result_codes = [item["code"] for item in payload["results"]]
            self.assertIn("runtime_tool.git", result_codes)
            self.assertIn("runtime_tool.llvm.clang", result_codes)

    def test_validate_offline_bundle_flags_missing_native_gui_launcher_in_strict_mode(self):
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
                    "-RequireComplete",
                    "-JsonOutputPath",
                    str(json_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            result_codes = [item["code"] for item in payload["results"]]
            self.assertIn("bundle.launcher.gui_exe_user", result_codes)
            self.assertIn("bundle.launcher.gui_exe_cli", result_codes)

    def test_validate_offline_bundle_passes_static_runtime_contract_for_mock_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "bundle"
            sources_root = Path(tmp) / "sources"
            for path in [
                "app/embedagent/__init__.py",
                "runtime/python/python.exe",
                "bin/git/cmd/git.exe",
                "bin/rg/rg.exe",
                "bin/ctags/ctags.exe",
                "bin/llvm/bin/clang.exe",
                "bin/llvm/bin/clang++.exe",
                "bin/llvm/bin/clang-cl.exe",
                "bin/llvm/bin/clang-tidy.exe",
                "bin/llvm/bin/clang-analyzer.bat",
                "bin/llvm/bin/llvm-profdata.exe",
                "bin/llvm/bin/llvm-cov.exe",
            ]:
                target = bundle_root / Path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("stub", encoding="ascii")
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
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            result_codes = [item["code"] for item in payload["results"]]
            self.assertIn("runtime_tool.python", result_codes)
            self.assertIn("runtime_tool.git", result_codes)
            self.assertIn("runtime_tool.llvm.clang_tidy", result_codes)
            self.assertEqual(payload["runtime_contract"]["schema_version"], 1)

    def test_validate_offline_bundle_flags_gui_launcher_contract_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "bundle"
            sources_root = Path(tmp) / "sources"
            bundle_root.mkdir()
            sources_root.mkdir()
            (bundle_root / "embedagent-gui.cmd").write_text(
                '@echo off\nset "BUNDLE_ROOT=%~dp0"\n',
                encoding="ascii",
            )
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
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertFalse(payload["ok"])
            result_codes = [item["code"] for item in payload["results"]]
            self.assertIn("bundle.launcher.gui_contract", result_codes)

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


@unittest.skipIf(sys.platform != "win32", "Windows-only: requires PowerShell")
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
        config_checks = [
            check for check in payload["doctor_checks"] if check.get("name") == "config"
        ]
        self.assertEqual(len(config_checks), 1)
        self.assertTrue(config_checks[0]["ok"])
        self.assertIn("package.config.json", config_checks[0]["path"])
        npm_checks = [
            check for check in payload["doctor_checks"] if check.get("name") == "runtime:npm"
        ]
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


@unittest.skipIf(sys.platform != "win32", "Windows-only: requires PowerShell")
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
