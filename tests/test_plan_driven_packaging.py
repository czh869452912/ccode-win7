from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wheel(root, distribution, package, dependencies=()):
    filename = "%s-0.1.0-py3-none-any.whl" % distribution.replace("-", "_")
    dist_info = "%s-0.1.0.dist-info" % distribution.replace("-", "_")
    path = root / filename
    with zipfile.ZipFile(str(path), "w") as archive:
        archive.writestr(package + "/__init__.py", b"")
        archive.writestr(
            dist_info + "/METADATA",
            (
                "Metadata-Version: 2.1\nName: %s\nVersion: 0.1.0\n%s"
                % (
                    distribution,
                    "".join("Requires-Dist: %s\n" % item for item in dependencies),
                )
            ).encode("ascii"),
        )
    return path


def test_checker_accepts_selected_generic_wheel_set(tmp_path):
    for distribution, package in (
        ("embedagent-core", "embedagent_core"),
        ("embedagent-protocol", "embedagent_protocol"),
        ("embedagent-host", "embedagent_host"),
        ("embedagent-shell", "embedagent"),
    ):
        dependencies = {
            "embedagent-host": (
                "embedagent-core ==0.1.0",
                "embedagent-protocol ==0.1.0",
            ),
            "embedagent-shell": (
                "embedagent-core ==0.1.0",
                "embedagent-protocol ==0.1.0",
                "embedagent-host ==0.1.0",
            ),
        }.get(distribution, ())
        _wheel(tmp_path, distribution, package, dependencies)
    checker = _load("scripts/check-python-distributions.py", "plan_checker")
    report = checker.build_report(
        tmp_path,
        selected_distributions=(
            "embedagent-core",
            "embedagent-protocol",
            "embedagent-host",
            "embedagent-shell",
        ),
    )
    assert report["ok"] is True
    assert "embedagent-workflow-cpp" not in report["verified_wheels"]


def test_smoke_runner_rejects_unplanned_project_wheel():
    smoke = _load("scripts/smoke-python-distributions.py", "plan_smoke")
    with pytest.raises(ValueError, match="unplanned distribution"):
        smoke.scenario_wheels(
            ("embedagent-core", "embedagent-workflow-cpp"),
            {"project_distribution_ids": ["embedagent-core"]},
        )
