import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare-release-artifacts.py"
FIXTURE = ROOT / "tests" / "fixtures" / "packaging" / "reproducibility-config.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("compare_release_artifacts", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(wheel_hash="a" * 64):
    names = (
        "embedagent-core",
        "embedagent-protocol",
        "embedagent-host",
        "embedagent-composition",
        "embedagent-workflow-cpp",
        "embedagent",
    )
    return {
        "schema_version": 1,
        "source_revision": "same-revision",
        "version": "0.1.0",
        "profile": "release",
        "project_distributions": list(names),
        "wheels": [
            {
                "name": name,
                "filename": "%s-0.1.0-py3-none-any.whl" % name.replace("-", "_"),
                "sha256": wheel_hash,
            }
            for name in names
        ],
        "gui_static_sha256": "b" * 64,
        "asset_manifest_sha256": "c" * 64,
        "runtime_contract_sha256": "d" * 64,
        "bundle_sha256": None,
        "zip_sha256": None,
        "tool_metadata": {"python": "3.8"},
    }


def _write_run(root, generated_at, wheel_hash="a" * 64, secret=None):
    manifests = root / "manifests"
    manifests.mkdir(parents=True)
    manifest = {
        "schema_version": 2,
        "generated_at": generated_at,
        "project_root": str(root.parent / "project"),
        "build_root": str(root.parent / "build"),
        "bundle_root": str(root),
        "asset_manifest_path": str(root.parent / "assets.json"),
        "source_mode": "wheel-installed",
    }
    (manifests / "bundle-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (manifests / "release-identity.json").write_text(
        json.dumps(_identity(wheel_hash=wheel_hash)), encoding="utf-8"
    )
    (root / "stable.txt").write_text("stable", encoding="utf-8")
    report = {
        "profile": "release",
        "source_revision": "same-revision",
        "execution_kind": "release",
        "config_origin": "production",
        "final_status": "TARGET_READY",
        "artifact_root": str(root),
    }
    if secret:
        report["api_key"] = secret
    report_path = root.parent / (root.name + "-report.json")
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return report_path


def test_generated_manifest_paths_are_normalized(tmp_path):
    module = _load_module()
    first_root = tmp_path / "run-a"
    second_root = tmp_path / "run-b"
    first_report = _write_run(first_root, "2026-01-01T00:00:00Z")
    second_report = _write_run(second_root, "2026-01-02T00:00:00Z")

    result = module.compare_release_runs(
        first_report,
        second_report,
        first_root,
        second_root,
        fixture_path=FIXTURE,
    )

    assert result["ok"] is True
    assert result["mismatches"] == []
    assert result["excluded_paths"]


def test_stable_file_mismatch_reports_relative_path(tmp_path):
    module = _load_module()
    first_root = tmp_path / "run-a"
    second_root = tmp_path / "run-b"
    first_report = _write_run(first_root, "one")
    second_report = _write_run(second_root, "two")
    (second_root / "stable.txt").write_text("changed", encoding="utf-8")

    result = module.compare_release_runs(
        first_report,
        second_report,
        first_root,
        second_root,
        fixture_path=FIXTURE,
    )

    assert result["ok"] is False
    assert "bundle.stable.txt" in result["mismatches"]


def test_wheel_hash_and_source_revision_mismatch_are_blocking(tmp_path):
    module = _load_module()
    first_root = tmp_path / "run-a"
    second_root = tmp_path / "run-b"
    first_report = _write_run(first_root, "one")
    second_report = _write_run(second_root, "two", wheel_hash="e" * 64)
    payload = json.loads(second_report.read_text(encoding="utf-8"))
    payload["source_revision"] = "different-revision"
    second_report.write_text(json.dumps(payload), encoding="utf-8")

    result = module.compare_release_runs(
        first_report,
        second_report,
        first_root,
        second_root,
        fixture_path=FIXTURE,
    )

    assert result["ok"] is False
    assert "report.source_revision" in result["mismatches"]
    assert any(item.startswith("identity.wheels") for item in result["mismatches"])


def test_cli_missing_report_is_safe_and_nonzero(tmp_path):
    secret = "super-secret-value"
    first_root = tmp_path / "run-a"
    second_root = tmp_path / "run-b"
    first_report = _write_run(first_root, "one", secret=secret)
    missing_report = tmp_path / "missing.json"
    output = tmp_path / "comparison.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--first-report",
            str(first_report),
            "--second-report",
            str(missing_report),
            "--first-root",
            str(first_root),
            "--second-root",
            str(second_root),
            "--fixture",
            str(FIXTURE),
            "--json-report",
            str(output),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert "report.second.missing" in payload["mismatches"]
    assert secret not in output.read_text(encoding="utf-8")


def _powershell_exe():
    return os.environ.get(
        "COMSPEC_POWERSHELL",
        r"C:\Program Files\PowerShell\7\pwsh.exe",
    )


def _write_package_config(root):
    source = ROOT / "tests" / "fixtures" / "package" / "mock-config.json"
    config = json.loads(source.read_text(encoding="utf-8"))
    config["metadata"] = {"config_origin": "production"}
    config["paths"]["reports_root"] = str(root / "outer-reports")
    path = root / "package-config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _run_reproducible_package(tmp_path, mutate_second=False):
    config_path = _write_package_config(tmp_path)
    env = os.environ.copy()
    env["EMBEDAGENT_PYTHON"] = sys.executable
    if mutate_second:
        env["EMBEDAGENT_REPRO_MUTATE_SECOND"] = "1"
    result = subprocess.run(
        [
            _powershell_exe(),
            "-NoProfile",
            "-File",
            str(ROOT / "scripts" / "package.ps1"),
            "release",
            "-Config",
            str(config_path),
            "-Reproducible",
            "-ReproducibilityRoot",
            str(tmp_path / "repro"),
            "-Json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result, payload


@pytest.mark.skipif(os.name != "nt", reason="Windows-only: requires PowerShell")
def test_package_reproducibility_gate_accepts_matching_runs(tmp_path):
    result, payload = _run_reproducible_package(tmp_path)

    assert result.returncode == 0, result.stderr
    stage = payload["stages"][-1]
    assert payload["final_status"] == "TARGET_READY"
    assert stage["name"] == "artifact_reproducibility"
    assert stage["status"] == "pass"
    assert stage["summary"]["mismatches"] == []


@pytest.mark.skipif(os.name != "nt", reason="Windows-only: requires PowerShell")
def test_package_reproducibility_gate_blocks_mutated_second_run(tmp_path):
    result, payload = _run_reproducible_package(tmp_path, mutate_second=True)

    assert result.returncode != 0
    assert payload, result.stderr
    stage = payload["stages"][-1]
    assert payload["final_status"] == "NOT_READY"
    assert stage["name"] == "artifact_reproducibility"
    assert stage["status"] == "fail"
    assert "bundle.stable.txt" in stage["summary"]["mismatches"]
