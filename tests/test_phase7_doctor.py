import json
import os
import subprocess
from pathlib import Path

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


def _doctor(profile):
    result = subprocess.run(
        [
            _powershell_exe(),
            "-NoProfile",
            "-File",
            str(PACKAGE_SCRIPT),
            "doctor",
            "-Profile",
            profile,
            "-Json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_release_config_declares_identity_evidence_and_distribution_contract():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    assert config["paths"]["release_identity"] == "manifests/release-identity.json"
    assert config["paths"]["release_evidence_root"] == "manifests/evidence"
    release = config["profiles"]["release"]
    assert release["minimum_free_bytes"] == 8589934592
    assert release["required_project_distributions"] == [
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-host",
        "embedagent-composition",
        "embedagent-workflow-cpp",
        "embedagent",
    ]


def test_release_doctor_projects_structured_runtime_and_asset_checks():
    report = _doctor("release")
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


def test_dev_and_release_doctor_preserve_profile_severity():
    dev = _doctor("dev")
    release = _doctor("release")

    dev_codes = {item["code"] for item in dev["doctor_checks"]}
    release_codes = {item["code"] for item in release["doctor_checks"]}
    assert dev_codes == release_codes
    assert all(item["blocking"] is True for item in release["doctor_checks"])
