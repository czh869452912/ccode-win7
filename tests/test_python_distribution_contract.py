import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised by the Python 3.8 test runtime
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check-python-distributions.py"

PROJECTS = (
    (Path("packages/embedagent-core/pyproject.toml"), "embedagent-core"),
    (Path("packages/embedagent-protocol/pyproject.toml"), "embedagent-protocol"),
    (Path("packages/embedagent-host/pyproject.toml"), "embedagent-host"),
    (Path("packages/embedagent-composition/pyproject.toml"), "embedagent-composition"),
    (Path("pyproject.toml"), "embedagent"),
)

DEPENDENCIES = (
    (Path("packages/embedagent-core/pyproject.toml"), []),
    (Path("packages/embedagent-protocol/pyproject.toml"), []),
    (
        Path("packages/embedagent-host/pyproject.toml"),
        ["embedagent-core==0.1.0", "embedagent-protocol==0.1.0"],
    ),
    (Path("packages/embedagent-composition/pyproject.toml"), []),
)

WHEEL_PACKAGES = {
    "embedagent-core": "embedagent_core/",
    "embedagent-protocol": "embedagent_protocol/",
    "embedagent-host": "embedagent_host/",
    "embedagent-composition": "embedagent_composition/",
}


def _read_pyproject(relative_path):
    path = ROOT / relative_path
    assert path.is_file(), "missing target pyproject: %s" % relative_path.as_posix()
    with path.open("rb") as handle:
        return tomllib.load(handle)


def test_distribution_project_names_are_ordered_and_unique():
    actual_names = [
        _read_pyproject(relative_path)["project"]["name"]
        for relative_path, _expected_name in PROJECTS
    ]
    expected_names = [expected_name for _relative_path, expected_name in PROJECTS]

    assert actual_names == expected_names
    assert len(actual_names) == len(set(actual_names))


@pytest.mark.parametrize(("relative_path", "expected"), DEPENDENCIES)
def test_distribution_dependencies_are_exact(relative_path, expected):
    project = _read_pyproject(relative_path)["project"]
    assert project["dependencies"] == expected


def _wheel_path(dist_dir, distribution, version="0.1.0", suffix=""):
    wheel_name = distribution.replace("-", "_")
    filename = "%s-%s%s-py3-none-any.whl" % (wheel_name, version, suffix)
    return dist_dir / filename


def _metadata(distribution, dependencies=(), extra_headers=()):
    lines = [
        "Metadata-Version: 2.1",
        "Name: %s" % distribution,
        "Version: 0.1.0",
    ]
    lines.extend(extra_headers)
    lines.extend("Requires-Dist: %s" % dependency for dependency in dependencies)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write_wheel(
    dist_dir,
    distribution,
    files=None,
    dependencies=(),
    extra_metadata_entries=(),
    metadata_bytes=None,
    version="0.1.0",
    suffix="",
):
    required_prefix = WHEEL_PACKAGES[distribution]
    package_files = files if files is not None else [required_prefix + "__init__.py"]
    wheel_path = _wheel_path(dist_dir, distribution, version=version, suffix=suffix)
    dist_info = "%s-0.1.0.dist-info" % distribution.replace("-", "_")
    payload = metadata_bytes
    if payload is None:
        payload = _metadata(distribution, dependencies=dependencies)

    with zipfile.ZipFile(str(wheel_path), "w") as wheel:
        for filename in package_files:
            wheel.writestr(filename, b"")
        wheel.writestr(dist_info + "/METADATA", payload)
        for filename, content in extra_metadata_entries:
            wheel.writestr(filename, content)
    return wheel_path


def _write_valid_wheels(dist_dir):
    for distribution in WHEEL_PACKAGES:
        _write_wheel(dist_dir, distribution)


def _run_checker(dist_dir):
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--dist-dir", str(dist_dir)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.stdout, result.stderr
    return result, json.loads(result.stdout)


def _distribution_report(report, distribution):
    return next(item for item in report["distributions"] if item["name"] == distribution)


def _error_codes(report, distribution):
    item = _distribution_report(report, distribution)
    return [error["code"] for error in item["errors"]]


def test_wheel_checker_accepts_isolated_distribution_wheels(tmp_path):
    _write_valid_wheels(tmp_path)

    first_result, first_report = _run_checker(tmp_path)
    second_result, second_report = _run_checker(tmp_path)

    assert first_result.returncode == 0
    assert first_result.stderr == ""
    assert first_report == second_report
    assert first_result.stdout == second_result.stdout
    assert first_report["schema_version"] == 1
    assert first_report["ok"] is True
    assert [item["name"] for item in first_report["distributions"]] == list(WHEEL_PACKAGES)
    assert all(item["errors"] == [] for item in first_report["distributions"])


def test_wheel_checker_reports_a_missing_distribution_wheel(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-protocol").unlink()

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-protocol") == ["wheel_missing"]


def test_wheel_checker_reports_forbidden_file_and_normalized_dependency(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        files=["embedagent_core/__init__.py", "embedagent_host/leak.py"],
        dependencies=("PyWebView[qt] >= 4.0 ; python_version >= '3.8'",),
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == [
        "forbidden_prefix",
        "forbidden_dependency",
    ]


def test_wheel_checker_reports_a_missing_required_prefix(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-composition").unlink()
    _write_wheel(tmp_path, "embedagent-composition", files=["unrelated/__init__.py"])

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-composition") == ["required_prefix_missing"]


def test_wheel_checker_reports_ambiguous_metadata(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-host").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-host",
        extra_metadata_entries=(("other-0.1.0.dist-info/METADATA", _metadata("other")),),
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-host") == ["metadata_ambiguous"]


def test_wheel_checker_reports_damaged_metadata(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-protocol").unlink()
    damaged = _metadata("embedagent-protocol", extra_headers=("Name: duplicate",))
    _write_wheel(tmp_path, "embedagent-protocol", metadata_bytes=damaged)

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-protocol") == ["metadata_invalid"]


def test_wheel_checker_reports_ambiguous_wheel_candidates(tmp_path):
    _write_valid_wheels(tmp_path)
    _write_wheel(tmp_path, "embedagent-core", version="0.1.1", suffix="")

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["wheel_ambiguous"]
