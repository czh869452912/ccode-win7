from __future__ import annotations

import importlib.util
from pathlib import Path

import tomli

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "test-suite.py"
RELEASE_MODULES = (
    "test_gui_launcher_exe_contract.py",
    "test_package_report_provenance.py",
    "test_packaging_control_plane.py",
    "test_phase7_bundle_assembly.py",
    "test_phase7_bundle_dependency_contract.py",
    "test_phase7_dependency_stage.py",
    "test_phase7_doctor.py",
    "test_phase7_evidence_kit.py",
    "test_phase7_verification.py",
    "test_python_distribution_smoke.py",
    "test_release_evidence.py",
    "test_release_identity.py",
    "test_release_reproducibility.py",
)


def load_test_suite_script():
    spec = importlib.util.spec_from_file_location("embedagent_test_suite_policy", str(SCRIPT_PATH))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_primary_partition_markers_are_registered():
    with (ROOT / "pyproject.toml").open("rb") as handle:
        config = tomli.load(handle)
    markers = config["tool"]["pytest"]["ini_options"]["markers"]

    assert "release: packaging, distribution, offline, and release-gate tests" in markers
    assert "performance: explicit performance threshold tests" in markers


def test_release_modules_declare_release_partition():
    for filename in RELEASE_MODULES:
        source = (ROOT / "tests" / filename).read_text(encoding="utf-8")
        assert "pytestmark = pytest.mark.release" in source, filename


def test_performance_module_declares_performance_partition():
    source = (ROOT / "tests" / "test_session_performance.py").read_text(encoding="utf-8")
    assert "pytestmark = pytest.mark.performance" in source


def test_test_modules_do_not_spawn_nested_full_pytest():
    suite = load_test_suite_script()

    assert suite.nested_full_pytest_violations(ROOT / "tests") == ()
