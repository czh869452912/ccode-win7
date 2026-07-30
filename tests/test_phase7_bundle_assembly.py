from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]


def _script(name):
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


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
