import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts" / "package.config.json"
PACKAGE_SCRIPT = ROOT / "scripts" / "package.ps1"


def _powershell_exe():
    candidates = (
        Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("PowerShell is required for package doctor tests")


def _doctor(profile, flavor=None):
    command = [
        _powershell_exe(),
        "-NoProfile",
        "-File",
        str(PACKAGE_SCRIPT),
        "doctor",
        "-Profile",
        profile,
        "-Json",
    ]
    if flavor is not None:
        command.extend(("-Flavor", flavor))
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report = json.loads(result.stdout)
    assert report["command_status"] in ("READY", "NOT_READY")
    expected_returncode = 0 if report["command_status"] == "READY" else 1
    assert result.returncode == expected_returncode, result.stderr
    return report


def test_release_config_keeps_assurance_separate_from_distribution_contract():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    assert config["paths"]["release_identity"] == "manifests/release-identity.json"
    assert config["paths"]["release_evidence_root"] == "manifests/evidence"
    release = config["profiles"]["release"]
    assert release["minimum_free_bytes"] == 8589934592
    assert "required_project_distributions" not in release
    assert (
        json.loads(
            (ROOT / "config" / "bundle-flavors" / "minimal-cli.json").read_text(encoding="utf-8")
        )["agent_application_id"]
        == "embedagent.generic"
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows-only: requires PowerShell")
def test_release_doctor_projects_structured_runtime_and_asset_checks():
    report = _doctor("release", "cpp-desktop")
    checks = {item["code"]: item for item in report["doctor_checks"]}

    for code in (
        "python.version",
        "asset.cache.python_embedded_x64",
        "asset.cache.webview2_fixed_runtime_x64",
        "toolchain.llvm",
        "disk.output_free_space",
        "wheelhouse.output_root",
    ):
        assert code in checks
        assert {"code", "ok", "blocking"}.issubset(checks[code])


@pytest.mark.skipif(os.name != "nt", reason="Windows-only: requires PowerShell")
def test_minimal_release_doctor_omits_desktop_only_prerequisites():
    report = _doctor("release", "minimal-cli")
    codes = {item["code"] for item in report["doctor_checks"]}

    assert {
        "asset.cache.python_embedded_x64",
        "asset.cache.mingit_x64",
        "asset.cache.ripgrep_x64",
    }.issubset(codes)
    assert "asset.cache.universal_ctags_x64" not in codes
    assert "tool.build-gui-launcher.ps1" not in codes
    assert "runtime.npm" not in codes
    assert "asset.cache.webview2_fixed_runtime_x64" not in codes
    assert "toolchain.llvm" not in codes


@pytest.mark.skipif(os.name != "nt", reason="Windows-only: requires PowerShell")
def test_dev_and_release_doctor_preserve_profile_severity():
    dev = _doctor("dev")
    release = _doctor("release")

    dev_codes = {item["code"] for item in dev["doctor_checks"]}
    release_codes = {item["code"] for item in release["doctor_checks"]}
    assert dev_codes == release_codes
    assert all(item["blocking"] is True for item in release["doctor_checks"])
