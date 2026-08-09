import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "scripts" / "package-lib.ps1"
CONFIG = ROOT / "scripts" / "package.config.json"
EXPORT_SCRIPT = ROOT / "scripts" / "export-dependencies.py"
CHECK_SCRIPT = ROOT / "scripts" / "check-bundle-dependencies.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate-offline-bundle.ps1"
PACKAGE_SCRIPT = ROOT / "scripts" / "package.ps1"
RUNTIME_CONTRACT = ROOT / "scripts" / "offline-runtime-contract.json"
MOCK_CONFIG = ROOT / "tests" / "fixtures" / "package" / "mock-config.json"


def _write_export_bundle_plan(root, feature_ids=("gui", "tui")):
    payload = {
        "schema_version": 1,
        "flavor_id": "tests",
        "python_feature_ids": list(feature_ids),
        "project_distribution_ids": [
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-host",
            "embedagent-composition",
            "embedagent-workflow-cpp",
            "embedagent",
        ],
    }
    path = Path(root) / "bundle-plan.json"
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="ascii")
    return path


def _write_isolated_mock_config(root, dynamic=False):
    config = json.loads(MOCK_CONFIG.read_text(encoding="utf-8"))
    config["metadata"] = {"config_origin": "fixture"}
    config["paths"]["reports_root"] = str(root / "reports")
    config["paths"]["build_root"] = str(root / "build")
    config["paths"]["site_packages_export_root"] = str(root / "export")
    config["paths"]["site_packages_root"] = str(root / "export" / "site-packages")
    config["paths"]["gui_launcher_build_root"] = str(root / "launcher")
    config["paths"]["dist_bundle_root"] = str(root / "build" / "offline-dist" / "mock-artifact")
    if dynamic:
        config["profiles"]["release"]["run_dynamic_checks"] = True
    path = root / "mock-config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _load_python_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROJECT_PACKAGE_LAYOUTS = (
    ("embedagent_core", "embedagent_core-0.1.0.dist-info"),
    ("embedagent_protocol", "embedagent_protocol-0.1.0.dist-info"),
    ("embedagent_host", "embedagent_host-0.1.0.dist-info"),
    ("embedagent_composition", "embedagent_composition-0.1.0.dist-info"),
    ("embedagent_workflow_cpp", "embedagent_workflow_cpp-0.1.0.dist-info"),
)


def _write_project_distribution_layout(bundle):
    site_packages = bundle / "runtime" / "site-packages"
    (bundle / "app" / "embedagent").mkdir(parents=True)
    product_metadata = site_packages / "embedagent-0.1.0.dist-info" / "METADATA"
    product_metadata.parent.mkdir(parents=True)
    product_metadata.write_text("Name: embedagent\nVersion: 0.1.0\n", encoding="ascii")
    for import_name, dist_info_name in PROJECT_PACKAGE_LAYOUTS:
        (site_packages / import_name).mkdir(parents=True)
        metadata = site_packages / dist_info_name / "METADATA"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(
            "Name: {0}\nVersion: 0.1.0\n".format(import_name.replace("_", "-")),
            encoding="ascii",
        )
    return site_packages


def _write_valid_site_packages_layout(bundle):
    site_packages = _write_project_distribution_layout(bundle)
    for import_name in (
        "prompt_toolkit",
        "rich",
        "webview",
        "fastapi",
        "uvicorn",
        "websockets",
        "starlette",
        "pydantic",
        "anyio",
        "sniffio",
        "h11",
        "idna",
        "click",
        "colorama",
        "pygments",
        "wcwidth",
    ):
        (site_packages / import_name).mkdir()
    (site_packages / "typing_extensions.py").write_text("", encoding="ascii")
    return site_packages


def _write_checker_wheelhouse(root):
    layouts = (
        ("embedagent-core", "embedagent_core"),
        ("embedagent-protocol", "embedagent_protocol"),
        ("embedagent-host", "embedagent_host"),
        ("embedagent-composition", "embedagent_composition"),
        ("embedagent-workflow-cpp", "embedagent_workflow_cpp"),
        ("embedagent", "embedagent"),
    )
    dependencies = {
        "embedagent-workflow-cpp": ("embedagent-core ==0.1.0",),
        "embedagent-host": (
            "embedagent-core ==0.1.0",
            "embedagent-protocol ==0.1.0",
        ),
        "embedagent": (
            "embedagent-core ==0.1.0",
            "embedagent-protocol ==0.1.0",
            "embedagent-host ==0.1.0",
            "embedagent-composition ==0.1.0",
            "embedagent-workflow-cpp ==0.1.0",
        ),
    }
    names = []
    for distribution, package_name in layouts:
        wheel_name = "%s-0.1.0-py3-none-any.whl" % distribution.replace("-", "_")
        if distribution == "embedagent":
            wheel_name = "embedagent-0.1.0-py3-none-any.whl"
        dist_info = "%s-0.1.0.dist-info" % distribution.replace("-", "_")
        metadata = "Metadata-Version: 2.1\nName: {0}\nVersion: 0.1.0\n".format(distribution)
        metadata += "".join(
            "Requires-Dist: {0}\n".format(item) for item in dependencies.get(distribution, ())
        )
        with zipfile.ZipFile(str(root / wheel_name), "w") as wheel:
            wheel.writestr(package_name + "/__init__.py", b"")
            wheel.writestr(dist_info + "/METADATA", metadata.encode("ascii"))
        names.append(wheel_name)
    return names


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
            "[ordered]@{{default_profile=$cfg.default_profile; default_flavor=$cfg.default_flavor; profiles=@($cfg.profiles.PSObject.Properties.Name)}} "
            "| ConvertTo-Json -Compress".format(
                lib=str(LIB).replace("\\", "\\\\"),
                config=str(CONFIG).replace("\\", "\\\\"),
            )
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["default_profile"], "dev")
        self.assertEqual(payload["default_flavor"], "cpp-desktop")
        self.assertEqual(sorted(payload["profiles"]), ["dev", "release"])

    def test_profile_and_flavor_are_orthogonal(self):
        result = run_pwsh(
            ". '{lib}'; "
            "$cfg = Read-PackageConfig -Path '{config}'; "
            "$ctx = New-PackageContext -ProjectRoot '{root}' -Config $cfg "
            "-ConfigPath '{config}' -Command 'doctor' -RequestedProfile 'release' "
            "-RequestedFlavor 'minimal-cli' -BundleRoot '' -OutputRoot '' "
            "-ArtifactName '' -AllowDownload $false -NoZip $false -Strict $false; "
            "[ordered]@{{profile=$ctx.profile; flavor=$ctx.flavor; plan=$ctx.bundle_plan.flavor_id}} "
            "| ConvertTo-Json -Compress".format(
                lib=str(LIB).replace("\\", "\\\\"),
                config=str(CONFIG).replace("\\", "\\\\"),
                root=str(ROOT).replace("\\", "\\\\"),
            )
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "profile": "release",
                "flavor": "minimal-cli",
                "plan": "minimal-cli",
            },
        )

    def test_unknown_flavor_fails_before_build_root_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = json.loads(MOCK_CONFIG.read_text(encoding="utf-8"))
            config["paths"]["reports_root"] = str(root / "reports")
            config["paths"]["build_root"] = str(root / "build")
            config_path = root / "package.config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            result = run_pwsh(
                ". '{lib}'; "
                "$cfg = Read-PackageConfig -Path '{config}'; "
                "New-PackageContext -ProjectRoot '{root}' -Config $cfg "
                "-ConfigPath '{config}' -Command 'doctor' -RequestedProfile 'dev' "
                "-RequestedFlavor 'missing' -BundleRoot '' -OutputRoot '' "
                "-ArtifactName '' -AllowDownload $false -NoZip $false -Strict $false".format(
                    lib=str(LIB).replace("\\", "\\\\"),
                    config=str(config_path).replace("\\", "\\\\"),
                    root=str(ROOT).replace("\\", "\\\\"),
                )
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown_bundle_recipe", result.stderr)
            self.assertFalse((root / "build").exists())

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

    def test_stage_results_include_timing_metadata(self):
        result = run_pwsh(
            ". '{lib}'; "
            "$report = New-PackageReport -Command 'release' -Profile 'release'; "
            "Add-StageResult -Report ([ref]$report) -Name 'prepare' -Status 'pass' -ExitCode 0 -Summary @{{script='mock'}}; "
            "$report.stages[0] | ConvertTo-Json -Depth 8 -Compress".format(
                lib=str(LIB).replace("\\", "\\\\"),
            )
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["name"], "prepare")
        self.assertIn("started_at", payload)
        self.assertIn("finished_at", payload)
        self.assertIn("duration_ms", payload)
        self.assertIsInstance(payload["duration_ms"], int)
        self.assertGreaterEqual(payload["duration_ms"], 0)

    def test_powershell_stage_invocation_avoids_start_process_wait(self):
        script = LIB.read_text(encoding="utf-8")

        self.assertNotIn("Start-Process", script)
        self.assertNotIn("-Wait -PassThru", script)

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

        self.assertEqual(payload["schema_version"], 2)
        tools = [
            tool
            for component in payload["runtime_components"]
            for tool in component.get("managed_tools") or []
        ]
        tool_ids = [item["id"] for item in tools]
        self.assertEqual(tool_ids, ["python", "git", "bash", "rg", "ctags", "llvm"])
        for item in tools:
            self.assertTrue(item["category"])
            self.assertTrue(item.get("paths") or item.get("alternatives"))

    def test_runtime_contract_declares_release_gates(self):
        payload = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))
        gates = payload.get("release_gates") or []
        gate_ids = [item["id"] for item in gates]

        self.assertEqual(
            gate_ids,
            [
                "runtime_contract",
                "win7_cli_smoke",
                "cpp_smoke_workspace",
                "gui_headless_smoke",
                "win7_windowed_gui_smoke",
            ],
        )
        cpp_gate = [item for item in gates if item["id"] == "cpp_smoke_workspace"][0]
        self.assertEqual(cpp_gate["script"], "tools/validation/validate-cpp-smoke.py")
        self.assertEqual(cpp_gate["workspace"], "data/workspace-template")
        self.assertEqual(cpp_gate["required_tool"], "clang")
        self.assertFalse(cpp_gate["allow_system_tool_fallback"])

        win7_gate = [item for item in gates if item["id"] == "win7_windowed_gui_smoke"][0]
        self.assertTrue(win7_gate["manual_on_win7"])
        self.assertEqual(win7_gate["webview2_fixed_runtime_major"], 109)
        self.assertEqual(win7_gate["expected_renderer"], "edgechromium")
        self.assertEqual(win7_gate["expected_runtime_source"], "bundle")

    def test_runtime_contract_lists_current_llvm_children(self):
        payload = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))
        llvm_component = [item for item in payload["runtime_components"] if item["id"] == "llvm"][0]
        llvm = llvm_component["managed_tools"][0]
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

    def test_package_config_uses_plan_compiler_instead_of_stage_selectors(self):
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["tooling"]["compile_bundle_plan"],
            "scripts/compile-bundle-plan.py",
        )
        retired = {
            "required_assets",
            "required_project_distributions",
            "run_frontend_build",
            "run_gui_launcher_build",
        }
        for profile in payload["profiles"].values():
            self.assertFalse(retired.intersection(profile))

    def test_prepare_offline_uses_current_default_mode(self):
        script = self._script_text()
        self.assertNotIn('"default_mode": "code"', script)
        self.assertIn('"default_mode": "explore"', script)
        self.assertNotIn('"max_turns": 8', script)
        self.assertNotIn('"max_turns": null', script)

    def test_prepare_offline_stages_real_c_workspace_template(self):
        script = self._script_text()
        self.assertNotIn("This directory is a placeholder", script)
        self.assertIn("data\\workspace-template\\main.c", script)
        self.assertIn("data\\workspace-template\\README.md", script)
        self.assertIn("int main(void)", script)

    def test_prepare_offline_stages_cpp_smoke_validator(self):
        script = self._script_text()
        self.assertIn("scripts\\validate-cpp-smoke.py", script)
        self.assertIn("tools\\validation\\validate-cpp-smoke.py", script)
        self.assertIn("validate-cpp-smoke.cmd", script)

    def test_prepare_offline_contract_mentions_native_gui_launcher_component(self):
        script = self._script_text()

        self.assertIn("GuiLauncherExePath", script)
        self.assertIn("gui_launcher_exe", script)
        self.assertIn("EmbedAgent.exe", script)
        self.assertIn("embedagent-gui.exe", script)

    def test_prepare_offline_stages_product_from_installed_distribution(self):
        script = self._script_text()

        self.assertIn("installedAppRoot", script)
        self.assertIn("runtime\\site-packages", script)
        self.assertIn("app\\embedagent", script)
        self.assertIn("frontend\\gui\\static", script)
        self.assertIn("duplicateProductPackage", script)
        self.assertIn("runtime\\site-packages\\embedagent", script)
        self.assertNotIn("$sourceAppRoot = Join-Path $projectRoot 'src\\embedagent'", script)


class TestPythonDistributionPackagingContract(unittest.TestCase):
    VERIFIED_WHEEL_NAMES = [
        "embedagent_core-0.1.0-py3-none-any.whl",
        "embedagent_protocol-0.1.0-py3-none-any.whl",
        "embedagent_host-0.1.0-py3-none-any.whl",
        "embedagent_composition-0.1.0-py3-none-any.whl",
        "embedagent_workflow_cpp-0.1.0-py3-none-any.whl",
        "embedagent-0.1.0-py3-none-any.whl",
    ]

    def _copy_verified_wheels(self, source, destination):
        quoted_names = ",".join("'{0}'".format(name) for name in self.VERIFIED_WHEEL_NAMES)
        return run_pwsh(
            ". '{lib}'; "
            "$copied = @(Copy-VerifiedPythonWheels -SourceRoot '{source}' "
            "-DestinationRoot '{destination}' -WheelNames @({names})); "
            "$copied | ConvertTo-Json -Compress".format(
                lib=str(LIB).replace("\\", "\\\\"),
                source=str(source).replace("\\", "\\\\"),
                destination=str(destination).replace("\\", "\\\\"),
                names=quoted_names,
            )
        )

    def _publish_verified_wheels(self, source, destination):
        quoted_names = ",".join("'{0}'".format(name) for name in self.VERIFIED_WHEEL_NAMES)
        return run_pwsh(
            ". '{lib}'; "
            "$published = @(Publish-VerifiedPythonWheels -SourceRoot '{source}' "
            "-DestinationRoot '{destination}' -WheelNames @({names}) "
            "-PythonPath '{python}' -CheckerPath '{checker}'); "
            "$published | ConvertTo-Json -Compress".format(
                lib=str(LIB).replace("\\", "\\\\"),
                source=str(source).replace("\\", "\\\\"),
                destination=str(destination).replace("\\", "\\\\"),
                names=quoted_names,
                python=str(Path(sys.executable)).replace("\\", "\\\\"),
                checker=str(ROOT / "scripts" / "check-python-distributions.py").replace(
                    "\\", "\\\\"
                ),
            )
        )

    def test_dependency_export_builds_and_installs_workspace_wheels_offline(self):
        script = EXPORT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("--no-emit-workspace", script)
        self.assertIn("build-python-distributions.py", script)
        self.assertIn("--no-index", script)
        self.assertIn("--find-links", script)
        for name in (
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-host",
            "embedagent-composition",
            "embedagent-workflow-cpp",
            "embedagent",
        ):
            self.assertIn(name, script)

    def test_make_ci_runs_complete_test_partitions_before_bundle_validation(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("test:\n\tuv run python scripts/test-suite.py pre-push", makefile)
        self.assertIn("test-full:\n\tuv run python scripts/test-suite.py full", makefile)
        self.assertIn("test-release:\n\tuv run python scripts/test-suite.py release", makefile)
        self.assertIn(
            "test-performance:\n\tuv run python scripts/test-suite.py performance", makefile
        )
        self.assertIn("test-audit:\n\tuv run python scripts/test-suite.py audit", makefile)
        self.assertIn("python-distributions-check: python-distributions-build", makefile)
        self.assertIn("python-distributions-smoke: python-distributions-check", makefile)
        self.assertIn("offline-bundle-contract: python-distributions-smoke", makefile)
        self.assertIn(
            "ci: lint test-audit test-full test-release test-performance smoke "
            "offline-bundle-contract",
            makefile,
        )

    def test_frontend_native_rollup_dependency_is_optional(self):
        webapp = ROOT / "src" / "embedagent" / "frontend" / "gui" / "webapp"
        package = json.loads((webapp / "package.json").read_text(encoding="utf-8"))
        package_lock = json.loads((webapp / "package-lock.json").read_text(encoding="utf-8"))
        dependency = "@rollup/rollup-win32-x64-msvc"

        self.assertNotIn(dependency, package.get("devDependencies", {}))
        self.assertEqual(package.get("optionalDependencies", {}).get(dependency), "^4.60.1")

        lock_root = package_lock["packages"][""]
        self.assertNotIn(dependency, lock_root.get("devDependencies", {}))
        self.assertEqual(lock_root.get("optionalDependencies", {}).get(dependency), "^4.60.1")

        native_package = package_lock["packages"]["node_modules/" + dependency]
        self.assertIs(native_package.get("optional"), True)
        self.assertEqual(native_package.get("os"), ["win32"])
        self.assertEqual(native_package.get("cpu"), ["x64"])

    def test_frontend_ci_runs_required_linux_and_windows_matrix(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        frontend = workflow.split("  frontend:\n", 1)[1].split("  smoke:\n", 1)[0]

        self.assertIn(
            "strategy:\n"
            "      fail-fast: false\n"
            "      matrix:\n"
            "        os: [ubuntu-latest, windows-latest]",
            frontend,
        )
        self.assertIn("runs-on: ${{ matrix.os }}", frontend)
        for command in (
            "run: npm ci",
            "run: npm test",
            "run: npm run build",
            "run: git diff --exit-code -- src/embedagent/frontend/gui/static",
        ):
            self.assertIn(command, frontend)
        self.assertNotIn("continue-on-error:", frontend)

    def test_ci_workspace_jobs_provision_uv_and_share_offline_build_cache(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("name: Install uv", workflow)
        self.assertIn("UV_CACHE_DIR: ${{ github.workspace }}\\.uv-cache", workflow)
        self.assertIn("uv sync --locked --python python", workflow)
        self.assertIn("python scripts/test-suite.py audit", workflow)
        self.assertIn("python scripts/test-suite.py full --coverage", workflow)
        self.assertIn("python scripts/test-suite.py performance", workflow)
        self.assertIn("python scripts/test-suite.py release", workflow)
        self.assertIn("npm test", workflow)
        self.assertIn("npm run build", workflow)
        self.assertNotIn("--cov=src/embedagent", workflow)
        smoke = workflow.split("  smoke:\n", 1)[1].split("  windows-packaging:\n", 1)[0]
        self.assertIn("name: Install uv", smoke)

    def test_bundle_build_archives_the_exact_checked_python_wheelhouse(self):
        script = (ROOT / "scripts" / "build-offline-bundle.ps1").read_text(encoding="utf-8")

        self.assertIn("site-packages-export\\wheels", script)
        self.assertIn("python-wheels", script)
        self.assertIn("check-python-distributions.py", script)
        self.assertIn("verified_wheels", script)
        self.assertIn("Publish-VerifiedPythonWheels", script)
        self.assertNotIn(
            "Copy-BundleTree -Source $pythonWheelsSourceRoot -Destination $pythonWheelsArchiveRoot",
            script,
        )

    def test_bundle_dependency_gate_requires_all_split_project_packages(self):
        script = CHECK_SCRIPT.read_text(encoding="utf-8")

        for package in (
            "embedagent_core",
            "embedagent_protocol",
            "embedagent_host",
            "embedagent_composition",
            "embedagent_workflow_cpp",
        ):
            self.assertIn('"{0}"'.format(package), script)
            self.assertIn('"{0}-0.1.0.dist-info"'.format(package), script)

    @unittest.skipIf(sys.platform != "win32", "Windows-only: requires PowerShell")
    def test_verified_wheel_archive_ignores_unverified_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            verified = self.VERIFIED_WHEEL_NAMES
            for name in verified + ["extra_pkg-1.0.0-py3-none-any.whl"]:
                (source / name).write_text(name, encoding="ascii")
            result = self._copy_verified_wheels(source, destination)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), verified)
            self.assertEqual(sorted(path.name for path in destination.iterdir()), sorted(verified))

    @unittest.skipIf(sys.platform != "win32", "Windows-only: requires PowerShell")
    def test_atomic_wheel_publish_rechecks_copied_bytes_before_replacing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "python-wheels"
            source.mkdir()
            destination.mkdir()
            marker = destination / "keep.txt"
            marker.write_text("keep", encoding="ascii")
            names = _write_checker_wheelhouse(source)
            initial = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "check-python-distributions.py"),
                    "--dist-dir",
                    str(source),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(initial.returncode, 0, initial.stdout + initial.stderr)
            self.assertEqual(names, self.VERIFIED_WHEEL_NAMES)
            (source / names[0]).write_bytes(b"replaced after initial check")

            result = self._publish_verified_wheels(source, destination)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("copied Python wheelhouse failed validation", result.stderr)
            self.assertEqual(marker.read_text(encoding="ascii"), "keep")
            self.assertEqual([path.name for path in destination.iterdir()], ["keep.txt"])
            self.assertEqual(list(root.glob(".python-wheels.tmp.*")), [])

    @unittest.skipIf(sys.platform != "win32", "Windows-only: requires PowerShell")
    def test_atomic_wheel_publish_publishes_only_rechecked_temp_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "python-wheels"
            source.mkdir()
            names = _write_checker_wheelhouse(source)

            result = self._publish_verified_wheels(source, destination)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), names)
            self.assertEqual(sorted(path.name for path in destination.iterdir()), sorted(names))
            self.assertEqual(list(root.glob(".python-wheels.tmp.*")), [])

    @unittest.skipIf(sys.platform != "win32", "Windows-only reparse-point contract")
    def test_atomic_wheel_publish_rejects_final_destination_junction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination_target = root / "destination-target"
            destination = root / "python-wheels"
            source.mkdir()
            destination_target.mkdir()
            _write_checker_wheelhouse(source)
            marker = destination_target / "keep.txt"
            marker.write_text("keep", encoding="ascii")
            create_result = run_pwsh(
                "New-Item -ItemType Junction -Path '{junction}' -Target '{target}' | Out-Null".format(
                    junction=str(destination).replace("\\", "\\\\"),
                    target=str(destination_target).replace("\\", "\\\\"),
                )
            )
            if create_result.returncode != 0:
                self.skipTest("Windows directory junction creation is unavailable")
            try:
                result = self._publish_verified_wheels(source, destination)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("destination must not be a reparse point", result.stderr)
                self.assertEqual(marker.read_text(encoding="ascii"), "keep")
            finally:
                os.rmdir(str(destination))

    @unittest.skipIf(sys.platform != "win32", "Windows-only reparse-point contract")
    def test_verified_wheel_archive_rejects_file_symlink_before_touching_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "destination"
            outside = root / "outside.whl"
            source.mkdir()
            destination.mkdir()
            marker = destination / "keep.txt"
            marker.write_text("keep", encoding="ascii")
            outside.write_text("outside", encoding="ascii")
            for name in self.VERIFIED_WHEEL_NAMES[:-1]:
                (source / name).write_text(name, encoding="ascii")
            link = source / self.VERIFIED_WHEEL_NAMES[-1]
            try:
                os.symlink(str(outside), str(link))
            except OSError as exc:
                if getattr(exc, "winerror", None) in (5, 1314):
                    self.skipTest("Windows file symlink privilege is unavailable")
                raise

            result = self._copy_verified_wheels(source, destination)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("reparse point", result.stderr.lower())
            self.assertEqual(marker.read_text(encoding="ascii"), "keep")
            self.assertEqual([path.name for path in destination.iterdir()], ["keep.txt"])

    @unittest.skipIf(sys.platform != "win32", "Windows-only reparse-point contract")
    def test_verified_wheel_archive_rejects_source_junction_before_touching_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_source = root / "real-source"
            junction = root / "source-junction"
            destination = root / "destination"
            real_source.mkdir()
            destination.mkdir()
            marker = destination / "keep.txt"
            marker.write_text("keep", encoding="ascii")
            for name in self.VERIFIED_WHEEL_NAMES:
                (real_source / name).write_text(name, encoding="ascii")
            create_result = run_pwsh(
                "New-Item -ItemType Junction -Path '{junction}' -Target '{target}' | Out-Null".format(
                    junction=str(junction).replace("\\", "\\\\"),
                    target=str(real_source).replace("\\", "\\\\"),
                )
            )
            if create_result.returncode != 0:
                self.skipTest("Windows directory junction creation is unavailable")
            try:
                result = self._copy_verified_wheels(junction, destination)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("reparse point", result.stderr.lower())
                self.assertEqual(marker.read_text(encoding="ascii"), "keep")
                self.assertEqual([path.name for path in destination.iterdir()], ["keep.txt"])
            finally:
                os.rmdir(str(junction))

    def test_split_project_packages_require_import_tree_and_dist_info(self):
        for import_name, dist_info_name in PROJECT_PACKAGE_LAYOUTS:
            with self.subTest(import_name=import_name, missing="import_tree"):
                with tempfile.TemporaryDirectory() as tmp:
                    bundle = Path(tmp)
                    site_packages = _write_project_distribution_layout(bundle)
                    shutil.rmtree(site_packages / import_name)
                    checker = _load_python_module(CHECK_SCRIPT, "bundle_checker_import_tree")
                    _ok, errors = checker.check_site_packages(bundle)
                    self.assertIn("Missing project import package: {0}".format(import_name), errors)

            with self.subTest(import_name=import_name, missing="dist_info"):
                with tempfile.TemporaryDirectory() as tmp:
                    bundle = Path(tmp)
                    site_packages = _write_project_distribution_layout(bundle)
                    shutil.rmtree(site_packages / dist_info_name)
                    checker = _load_python_module(CHECK_SCRIPT, "bundle_checker_dist_info")
                    _ok, errors = checker.check_site_packages(bundle)
                    self.assertIn(
                        "Missing project distribution metadata: {0}".format(dist_info_name),
                        errors,
                    )

    def test_product_requires_app_import_tree_and_runtime_dist_info(self):
        checker = _load_python_module(CHECK_SCRIPT, "bundle_checker_product")
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            _write_project_distribution_layout(bundle)
            shutil.rmtree(bundle / "app" / "embedagent")
            _ok, errors = checker.check_site_packages(bundle)
            self.assertIn("Missing product import package: app/embedagent", errors)

        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            site_packages = _write_project_distribution_layout(bundle)
            shutil.rmtree(site_packages / "embedagent-0.1.0.dist-info")
            _ok, errors = checker.check_site_packages(bundle)
            self.assertIn(
                "Missing project distribution metadata: embedagent-0.1.0.dist-info",
                errors,
            )

    def test_product_import_tree_must_not_be_duplicated_in_runtime_site_packages(self):
        checker = _load_python_module(CHECK_SCRIPT, "bundle_checker_duplicate_product")
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            site_packages = _write_valid_site_packages_layout(bundle)
            ok, errors = checker.check_site_packages(bundle)
            self.assertTrue(ok, errors)
            self.assertEqual(errors, [])

            (site_packages / "embedagent").mkdir()
            ok, errors = checker.check_site_packages(bundle)

            self.assertFalse(ok)
            self.assertEqual(
                errors,
                [
                    "Duplicate product import package: "
                    "runtime/site-packages/embedagent; use app/embedagent only"
                ],
            )


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
            self.assertEqual(payload["runtime_contract"]["schema_version"], 2)

    def test_dependency_checker_accepts_runtime_contract_complete_mock_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            for path in [
                "app/embedagent/__init__.py",
                "runtime/python/python.exe",
                "runtime/site-packages/embedagent-0.1.0.dist-info/METADATA",
                "runtime/site-packages/embedagent_core/__init__.py",
                "runtime/site-packages/embedagent_core-0.1.0.dist-info/METADATA",
                "runtime/site-packages/embedagent_protocol/__init__.py",
                "runtime/site-packages/embedagent_protocol-0.1.0.dist-info/METADATA",
                "runtime/site-packages/embedagent_host/__init__.py",
                "runtime/site-packages/embedagent_host-0.1.0.dist-info/METADATA",
                "runtime/site-packages/embedagent_composition/__init__.py",
                "runtime/site-packages/embedagent_composition-0.1.0.dist-info/METADATA",
                "runtime/site-packages/embedagent_workflow_cpp/__init__.py",
                "runtime/site-packages/embedagent_workflow_cpp-0.1.0.dist-info/METADATA",
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
                "bin/git/bin/bash.exe",
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
                "validate-gui-smoke.cmd",
                "validate-cpp-smoke.cmd",
                "validate-cli-smoke.cmd",
                "config/config.json",
                "config/config.json.template",
                "config/permission-rules.json",
                "docs/configuration-guide.md",
                "docs/win7-preflight-checklist.md",
                "docs/intranet-deployment.md",
                "app/embedagent/frontend/gui/static/index.html",
                "app/embedagent/frontend/gui/static/assets/app.js",
                "tools/validation/validate-gui-smoke.py",
                "tools/validation/validate-cpp-smoke.py",
                "tools/validation/validate-cli-smoke.py",
                "data/workspace-template/main.c",
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
            bundle_plan = _write_export_bundle_plan(export_root)
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
                "embedagent_core",
                "embedagent_protocol",
                "embedagent_host",
                "embedagent_composition",
                "embedagent_workflow_cpp",
                "embedagent",
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
                    "--bundle-plan",
                    str(bundle_plan),
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
            self.assertEqual(payload["runtime_contract"]["schema_version"], 2)

    def test_validate_offline_bundle_flags_missing_cpp_smoke_assets_in_strict_mode(self):
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
            self.assertIn("release_gate.cpp_smoke_workspace.script", result_codes)
            self.assertIn("release_gate.cpp_smoke_workspace.workspace", result_codes)
            self.assertIn("release_gate.cpp_smoke_workspace.launcher", result_codes)

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
            bundle_plan = _write_export_bundle_plan(temp_root, ())
            report_path = temp_root / "export-failure-report.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT_SCRIPT),
                    "--output-dir",
                    str(temp_root / "out"),
                    "--project-root",
                    str(temp_root / "missing-project"),
                    "--bundle-plan",
                    str(bundle_plan),
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
        tmp_dir = tempfile.TemporaryDirectory()
        config_path = _write_isolated_mock_config(Path(tmp_dir.name))
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "release",
                "-Config",
                str(config_path),
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
        self.assertEqual(
            stage_names,
            [
                "deps",
                "frontend_build",
                "gui_launcher_build",
                "prepare",
                "build",
                "verify",
            ],
        )
        stage_statuses = [stage["status"] for stage in payload["stages"]]
        self.assertEqual(stage_statuses, ["pass"] * 6)
        for stage in payload["stages"]:
            self.assertIn("started_at", stage)
            self.assertIn("finished_at", stage)
            self.assertIn("duration_ms", stage)
            self.assertGreaterEqual(stage["duration_ms"], 0)
        verify_summary = payload["stages"][-1]["summary"]
        self.assertTrue(verify_summary["validate_report"])
        self.assertTrue(verify_summary["dependency_report"])

    def test_package_release_honors_dynamic_check_profile(self):
        env = os.environ.copy()
        env["EMBEDAGENT_PYTHON"] = sys.executable
        validate_payload = None
        with tempfile.TemporaryDirectory() as tmp:
            config_path = _write_isolated_mock_config(Path(tmp), dynamic=True)

            result = subprocess.run(
                [
                    _powershell_exe(),
                    "-NoProfile",
                    "-File",
                    str(PACKAGE_SCRIPT),
                    "release",
                    "-Config",
                    str(config_path),
                    "-Json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            verify_summary = payload["stages"][-1]["summary"]
            validate_report = Path(verify_summary["validate_report"])
            validate_payload = json.loads(validate_report.read_text(encoding="utf-8"))
        self.assertFalse(validate_payload["skip_dynamic_checks"])

    def test_mock_desktop_release_includes_gui_build_stages(self):
        env = os.environ.copy()
        env["EMBEDAGENT_PYTHON"] = sys.executable
        tmp_dir = tempfile.TemporaryDirectory()
        config_path = _write_isolated_mock_config(Path(tmp_dir.name))
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "release",
                "-Config",
                str(config_path),
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=env,
        )
        payload = json.loads(result.stdout)
        stage_names = [stage["name"] for stage in payload.get("stages", [])]
        self.assertIn("frontend_build", stage_names)
        self.assertIn("gui_launcher_build", stage_names)
        tmp_dir.cleanup()

    def test_mock_minimal_release_omits_gui_build_stages(self):
        env = os.environ.copy()
        env["EMBEDAGENT_PYTHON"] = sys.executable
        tmp_dir = tempfile.TemporaryDirectory()
        config_path = _write_isolated_mock_config(Path(tmp_dir.name))
        result = subprocess.run(
            [
                _powershell_exe(),
                "-NoProfile",
                "-File",
                str(PACKAGE_SCRIPT),
                "release",
                "-Flavor",
                "minimal-cli",
                "-Config",
                str(config_path),
                "-Json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        stage_names = [stage["name"] for stage in payload.get("stages", [])]
        self.assertNotIn("frontend_build", stage_names)
        self.assertNotIn("gui_launcher_build", stage_names)
        tmp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
