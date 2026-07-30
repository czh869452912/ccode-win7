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


def _powershell_exe():
    return os.environ.get(
        "COMSPEC_POWERSHELL",
        r"C:\Program Files\PowerShell\7\pwsh.exe",
    )


def _write_isolated_config(root, origin="fixture"):
    config = json.loads(MOCK_CONFIG.read_text(encoding="utf-8"))
    config["metadata"] = {"config_origin": origin}
    # The fixture scripts intentionally emit their mock bundle under the
    # repository build tree; only the package report ledger is under test here.
    config["paths"]["reports_root"] = str(root / "reports")
    config["paths"]["build_root"] = str(root / "build")
    config["paths"]["site_packages_export_root"] = str(root / "export")
    config["paths"]["site_packages_root"] = str(root / "export" / "site-packages")
    config["paths"]["gui_launcher_build_root"] = str(root / "launcher")
    config["paths"]["dist_bundle_root"] = str(root / "build" / "offline-dist" / "mock-artifact")
    config_path = root / "mock-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


@pytest.mark.skipif(sys.platform != "win32", reason="requires PowerShell")
def test_fixture_release_isolated_and_provenance_bound(tmp_path):
    config_path = _write_isolated_config(tmp_path)
    production_latest = ROOT / "build" / "offline-reports" / "latest.json"
    before = production_latest.read_bytes() if production_latest.exists() else None

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
            str(config_path),
            "-Json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["execution_kind"] == "test"
    assert payload["config_origin"] == "fixture"
    assert str(tmp_path) in payload["report_path"]
    assert Path(payload["report_path"]).exists()
    assert before == (production_latest.read_bytes() if production_latest.exists() else None)


@pytest.mark.skipif(sys.platform != "win32", reason="requires PowerShell")
def test_unknown_config_origin_is_rejected(tmp_path):
    config_path = _write_isolated_config(tmp_path, origin="unknown")
    result = subprocess.run(
        [
            _powershell_exe(),
            "-NoProfile",
            "-File",
            str(PACKAGE_SCRIPT),
            "doctor",
            "-Config",
            str(config_path),
            "-Json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert "config_origin" in payload["blocking_issues"][0]
