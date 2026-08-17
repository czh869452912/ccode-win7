import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = ROOT / "scripts" / "package.ps1"
MOCK_CONFIG = ROOT / "tests" / "fixtures" / "package" / "mock-config.json"


def _script(name):
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def _powershell_exe():
    candidates = (
        Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe",
    )
    return next(str(candidate) for candidate in candidates if candidate.exists())


def _run_fixture_release(tmp_path, flavor):
    config = json.loads(MOCK_CONFIG.read_text(encoding="utf-8"))
    config["metadata"] = {"config_origin": "fixture"}
    config["paths"]["reports_root"] = str(tmp_path / "reports")
    config["paths"]["build_root"] = str(tmp_path / "build")
    config["paths"]["site_packages_export_root"] = str(tmp_path / "export")
    config["paths"]["site_packages_root"] = str(tmp_path / "export" / "site-packages")
    config["paths"]["gui_launcher_build_root"] = str(tmp_path / "launcher")
    config["paths"]["dist_bundle_root"] = str(tmp_path / "build" / "offline-dist")
    config_path = tmp_path / "mock-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    env = os.environ.copy()
    env["EMBEDAGENT_PYTHON"] = sys.executable
    result = subprocess.run(
        [
            _powershell_exe(),
            "-NoProfile",
            "-File",
            str(PACKAGE_SCRIPT),
            "release",
            "-Flavor",
            flavor,
            "-Config",
            str(config_path),
            "-Json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    bundle_root = Path(report["artifact_root"])
    manifest_path = bundle_root / "manifests" / "bundle-manifest.json"
    return bundle_root, json.loads(manifest_path.read_text(encoding="ascii"))


def _compile_plan(tmp_path, flavor="minimal-cli"):
    output_dir = tmp_path / "plan"
    report_path = tmp_path / "plan-report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "compile-bundle-plan.py"),
            "--flavor",
            flavor,
            "--target",
            "win7-x64-portable",
            "--assurance",
            "release",
            "--runtime-contract",
            str(ROOT / "scripts" / "offline-runtime-contract.json"),
            "--asset-manifest",
            str(ROOT / "scripts" / "offline-assets.json"),
            "--output-dir",
            str(output_dir),
            "--json-report",
            str(report_path),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return output_dir / "bundle-plan.json"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only PowerShell contract")
@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda plan: plan.pop("gate_ids"), "missing required array: gate_ids"),
        (lambda plan: plan["shell_ids"].append("unknown"), "unknown shell id"),
            (
                lambda plan: plan["project_distribution_ids"].clear(),
                "project distributions must be non-empty",
            ),
    ),
)
def test_bundle_plan_reader_fails_closed(tmp_path, mutation, message):
    plan_path = _compile_plan(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="ascii"))
    mutation(plan)
    plan_path.write_text(json.dumps(plan, sort_keys=True, separators=(",", ":")), encoding="ascii")
    plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    command = (
        ". '{0}'; Read-VerifiedBundlePlan -ProjectRoot '{1}' "
        "-BundlePlanPath '{2}' -BundlePlanSha256 '{3}'"
    ).format(
        str(ROOT / "scripts" / "package-lib.ps1"),
        str(ROOT),
        str(plan_path),
        plan_hash,
    )
    result = subprocess.run(
        [_powershell_exe(), "-NoProfile", "-Command", command],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode != 0
    assert message.lower() in (result.stdout + result.stderr).lower()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only packaging fixture")
def test_minimal_fixture_assembly_stages_only_planned_content(tmp_path):
    bundle_root, manifest = _run_fixture_release(tmp_path, "minimal-cli")

    assert manifest["flavor_id"] == "minimal-cli"
    assert manifest["shell_ids"] == ["cli"]
    assert manifest["allowed_agent_application_ids"] == ["embedagent.generic"]
    assert "gui-command" not in manifest["staged_launcher_ids"]
    assert "cpp-smoke" not in manifest["staged_launcher_ids"]
    assert "webview2_fixed_runtime_x64" not in manifest["resolved_asset_ids"]
    for relative_path in (
        "embedagent-tui.cmd",
        "embedagent-gui.cmd",
        "EmbedAgent.exe",
        "embedagent-gui.exe",
        "validate-cpp-smoke.cmd",
        "validate-gui-smoke.cmd",
        "runtime/webview2-fixed-runtime",
        "bin/llvm",
        "data/workspace-template",
    ):
        assert not (bundle_root / relative_path).exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only packaging fixture")
def test_desktop_fixture_assembly_preserves_full_desktop_contract(tmp_path):
    bundle_root, manifest = _run_fixture_release(tmp_path, "cpp-desktop")

    assert manifest["shell_ids"] == ["cli", "tui", "gui"]
    assert {
        "cli",
        "tui",
        "gui-command",
        "gui-native-user",
        "gui-native-cli",
        "cli-smoke",
        "cpp-smoke",
        "gui-smoke",
    } == set(manifest["staged_launcher_ids"])
    assert "webview2_fixed_runtime_x64" in manifest["resolved_asset_ids"]
    assert "llvm" in manifest["runtime_component_ids"]
    assert "cpp_smoke_workspace" in manifest["gate_ids"]
    for relative_path in (
        "embedagent.cmd",
        "embedagent-tui.cmd",
        "embedagent-gui.cmd",
        "EmbedAgent.exe",
        "embedagent-gui.exe",
        "validate-cli-smoke.cmd",
        "validate-cpp-smoke.cmd",
        "validate-gui-smoke.cmd",
        "runtime/webview2-fixed-runtime/msedgewebview2.exe",
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
        "data/workspace-template/main.c",
    ):
        assert (bundle_root / relative_path).exists(), relative_path


def test_prepare_contract_is_wheel_installed_only():
    script = _script("prepare-offline.ps1")

    assert "build\\offline-cache\\site-packages-export\\site-packages" in script
    assert "installedAppRoot" in script
    assert "source_mode = 'wheel-installed'" in script
    assert "project_wheels" in script
    assert "wheel_hashes" in script
    assert "identity_path" in script
    assert "src\\embedagent" not in script


def test_prepare_rejects_duplicate_product_distribution():
    script = _script("prepare-offline.ps1")

    assert "duplicateProductPackage" in script
    assert "duplicate product package" in script.lower()
    assert "dist-info" in script.lower()


def test_bundle_build_carries_identity_and_stage_reports():
    script = _script("build-offline-bundle.ps1")

    for marker in (
        "release-identity.json",
        "target-report.schema.json",
        "checker-report.json",
        "deps-report.json",
        "project_wheels",
        "wheel_hashes",
        "bundle_plan_sha256",
        "agent_lock_sha256",
        "gate_ids",
        "source_mode",
    ):
        assert marker in script


def test_bundle_validator_enforces_release_identity_and_artifact_hashes():
    script = _script("validate-offline-bundle.ps1")

    for marker in (
        "release-identity.json",
        "project_wheels",
        "wheel_hashes",
        "source_mode",
        "bundle_sha256",
        "zip_sha256",
        "duplicate",
    ):
        assert marker in script
