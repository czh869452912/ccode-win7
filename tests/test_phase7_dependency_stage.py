import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
EXPORT_SCRIPT = ROOT / "scripts" / "export-dependencies.py"


def _load_exporter():
    spec = importlib.util.spec_from_file_location("phase7_dependency_exporter", str(EXPORT_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clean_export_root_removes_known_generated_entries(tmp_path):
    module = _load_exporter()
    root = tmp_path / "export"
    root.mkdir()
    (root / "site-packages").mkdir()
    (root / "wheels").mkdir()
    (root / "requirements-pinned.txt").write_text("old", encoding="ascii")
    (root / "site-packages-manifest.json").write_text("{}", encoding="ascii")

    module.clean_export_root(root)

    assert root.is_dir()
    assert list(root.iterdir()) == []


def test_clean_export_root_rejects_unknown_entries(tmp_path):
    module = _load_exporter()
    root = tmp_path / "export"
    root.mkdir()
    (root / "user-data.txt").write_text("preserve", encoding="ascii")

    with pytest.raises(ValueError, match="unexpected export entry"):
        module.clean_export_root(root)

    assert (root / "user-data.txt").read_text(encoding="ascii") == "preserve"


def test_export_report_contains_exact_project_wheel_set(tmp_path):
    module = _load_exporter()
    manifest = {
        "project_distributions": list(module.PROJECT_DISTRIBUTIONS),
        "project_wheels": [
            name.replace("-", "_") + "-0.1.0-py3-none-any.whl"
            for name in module.PROJECT_DISTRIBUTIONS
        ],
    }
    report_path = tmp_path / "site-packages-manifest.json"
    report_path.write_text(json.dumps(manifest), encoding="utf-8")

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["project_distributions"] == list(module.PROJECT_DISTRIBUTIONS)
    assert len(payload["project_wheels"]) == 6
