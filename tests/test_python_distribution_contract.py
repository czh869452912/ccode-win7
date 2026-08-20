import importlib.util
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
    (Path("packages/embedagent-workflow-cpp/pyproject.toml"), "embedagent-workflow-cpp"),
    (Path("pyproject.toml"), "embedagent-shell"),
)

WORKSPACE_MEMBERS = [
    "packages/embedagent-core",
    "packages/embedagent-protocol",
    "packages/embedagent-host",
    "packages/embedagent-composition",
    "packages/embedagent-workflow-cpp",
]

WORKSPACE_DISTRIBUTIONS = (
    "embedagent-core",
    "embedagent-protocol",
    "embedagent-host",
    "embedagent-composition",
    "embedagent-workflow-cpp",
)

ROOT_DEPENDENCIES = [
    "embedagent-core==0.1.0",
    "embedagent-protocol==0.1.0",
    "embedagent-host==0.1.0",
]

ROOT_OPTIONAL_DEPENDENCIES = {
    "tui": ["prompt-toolkit==3.0.52", "rich==14.3.3"],
    "gui": [
        "pywebview>=4.0",
        "fastapi>=0.100",
        "uvicorn[standard]>=0.23",
        "websockets>=11.0",
    ],
}

PACKAGE_LAYOUTS = (
    (Path("packages/embedagent-core/pyproject.toml"), "embedagent_core*"),
    (Path("packages/embedagent-protocol/pyproject.toml"), "embedagent_protocol*"),
    (Path("packages/embedagent-host/pyproject.toml"), "embedagent_host*"),
    (Path("packages/embedagent-composition/pyproject.toml"), "embedagent_composition*"),
    (Path("packages/embedagent-workflow-cpp/pyproject.toml"), "embedagent_workflow_cpp*"),
)

DEPENDENCIES = (
    (Path("packages/embedagent-core/pyproject.toml"), []),
    (Path("packages/embedagent-protocol/pyproject.toml"), []),
    (
        Path("packages/embedagent-host/pyproject.toml"),
        ["embedagent-core==0.1.0", "embedagent-protocol==0.1.0"],
    ),
    (Path("packages/embedagent-composition/pyproject.toml"), []),
    (
        Path("packages/embedagent-workflow-cpp/pyproject.toml"),
        ["embedagent-core==0.1.0", "embedagent-protocol==0.1.0"],
    ),
)

WHEEL_PACKAGES = {
    "embedagent-core": "embedagent_core/",
    "embedagent-protocol": "embedagent_protocol/",
    "embedagent-host": "embedagent_host/",
    "embedagent-composition": "embedagent_composition/",
    "embedagent-workflow-cpp": "embedagent_workflow_cpp/",
    "embedagent-shell": "embedagent/",
}

CHECKER_BASELINE_DISTRIBUTIONS = (
    "embedagent-core",
    "embedagent-protocol",
    "embedagent-host",
    "embedagent-composition",
    "embedagent-workflow-cpp",
    "embedagent-shell",
)

VALID_WHEEL_DEPENDENCIES = {
    "embedagent-core": (),
    "embedagent-protocol": (),
    "embedagent-host": (
        "embedagent-core ==0.1.0",
        "embedagent-protocol ==0.1.0",
    ),
    "embedagent-composition": (),
    "embedagent-workflow-cpp": (
        "embedagent-core ==0.1.0",
        "embedagent-protocol ==0.1.0",
    ),
    "embedagent-shell": (
        "embedagent-core ==0.1.0",
        "embedagent-protocol ==0.1.0",
        "embedagent-host ==0.1.0",
        "prompt-toolkit ==3.0.52 ; extra == 'tui'",
        "rich ==14.3.3 ; extra == 'tui'",
        "pywebview >=4.0 ; extra == 'gui'",
        "fastapi >=0.100 ; extra == 'gui'",
        "uvicorn[standard] >=0.23 ; extra == 'gui'",
        "websockets >=11.0 ; extra == 'gui'",
    ),
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


def test_root_distribution_composes_exact_product_dependencies():
    root_project = _read_pyproject(Path("pyproject.toml"))["project"]

    assert root_project["name"] == "embedagent-shell"
    assert root_project["dependencies"] == ROOT_DEPENDENCIES
    assert root_project["optional-dependencies"] == ROOT_OPTIONAL_DEPENDENCIES


def test_root_distribution_owns_only_product_package():
    root = _read_pyproject(Path("pyproject.toml"))

    assert root["tool"]["setuptools"]["packages"]["find"] == {
        "where": ["src"],
        "include": ["embedagent", "embedagent.*"],
        "namespaces": False,
    }


def test_product_source_owns_current_cli_without_retired_frontend_facades():
    cli_root = ROOT / "src" / "embedagent" / "cli"

    assert {path.name for path in cli_root.glob("*.py")} >= {
        "app.py",
        "chat.py",
        "parser.py",
        "result.py",
        "run.py",
        "sessions.py",
    }
    assert not (cli_root / "interaction.py").exists()
    assert (
        ROOT / "src" / "embedagent" / "frontend" / "runtime" / "interaction_projection.py"
    ).exists()
    assert not (ROOT / "src" / "embedagent" / "core" / "adapter.py").exists()
    assert not (
        ROOT
        / "packages"
        / "embedagent-host"
        / "src"
        / "embedagent_host"
        / "hosted"
        / "session_host.py"
    ).exists()


def test_uv_workspace_members_and_sources_are_exact():
    root = _read_pyproject(Path("pyproject.toml"))

    assert root["tool"]["uv"]["workspace"]["members"] == WORKSPACE_MEMBERS
    assert root["tool"]["uv"]["sources"] == {
        distribution: {"workspace": True} for distribution in WORKSPACE_DISTRIBUTIONS
    }


def test_python38_toml_fallback_is_an_explicit_dev_dependency():
    root = _read_pyproject(Path("pyproject.toml"))

    assert "tomli==2.4.1" in root["dependency-groups"]["dev"]
    assert not any(dependency.startswith("tomli") for dependency in root["project"]["dependencies"])


def test_offline_wheel_backend_is_an_explicit_pinned_dev_dependency():
    root = _read_pyproject(Path("pyproject.toml"))

    assert "setuptools==75.3.2" in root["dependency-groups"]["dev"]
    assert not any(
        dependency.startswith("setuptools") for dependency in root["project"]["dependencies"]
    )


@pytest.mark.parametrize(("relative_path", "package_pattern"), PACKAGE_LAYOUTS)
def test_distribution_build_metadata_is_exact(relative_path, package_pattern):
    metadata = _read_pyproject(relative_path)

    assert metadata["build-system"] == {
        "requires": ["setuptools>=65"],
        "build-backend": "setuptools.build_meta",
    }
    assert metadata["project"]["version"] == "0.1.0"
    assert metadata["project"]["requires-python"] == ">=3.8,<3.9"
    assert metadata["tool"]["setuptools"]["package-dir"] == {"": "src"}
    assert metadata["tool"]["setuptools"]["packages"]["find"] == {
        "where": ["src"],
        "include": [package_pattern],
    }
    assert (ROOT / relative_path.parent / "src").is_dir()


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
    dependencies=None,
    extra_metadata_entries=(),
    metadata_bytes=None,
    version="0.1.0",
    suffix="",
    metadata_entry=None,
    raw_name_replacements=(),
):
    required_prefix = WHEEL_PACKAGES[distribution]
    package_files = files if files is not None else [required_prefix + "__init__.py"]
    wheel_path = _wheel_path(dist_dir, distribution, version=version, suffix=suffix)
    dist_info = "%s-0.1.0.dist-info" % distribution.replace("-", "_")
    if metadata_entry is None:
        metadata_entry = dist_info + "/METADATA"
    payload = metadata_bytes
    if payload is None:
        if dependencies is None:
            dependencies = VALID_WHEEL_DEPENDENCIES[distribution]
        payload = _metadata(distribution, dependencies=dependencies)

    with zipfile.ZipFile(str(wheel_path), "w") as wheel:
        for filename in package_files:
            wheel.writestr(filename, b"")
        wheel.writestr(metadata_entry, payload)
        for filename, content in extra_metadata_entries:
            wheel.writestr(filename, content)
    if raw_name_replacements:
        archive = wheel_path.read_bytes()
        for original, replacement in raw_name_replacements:
            assert len(original) == len(replacement)
            assert archive.count(original) == 2
            archive = archive.replace(original, replacement)
        wheel_path.write_bytes(archive)
    return wheel_path


def _write_valid_wheels(dist_dir):
    for distribution in CHECKER_BASELINE_DISTRIBUTIONS:
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


def _load_checker_module():
    spec = importlib.util.spec_from_file_location("python_distribution_checker", str(CHECKER))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert [item["name"] for item in first_report["distributions"]] == list(
        CHECKER_BASELINE_DISTRIBUTIONS
    )
    assert all(item["errors"] == [] for item in first_report["distributions"])


def test_wheel_checker_accepts_target_cpp_workflow_wheel(tmp_path):
    _write_valid_wheels(tmp_path)

    result, report = _run_checker(tmp_path)
    cpp_report = _distribution_report(report, "embedagent-workflow-cpp")

    assert report["errors"] == []
    assert result.returncode == 0
    assert cpp_report["requires_dist"] == [
        "embedagent-core ==0.1.0",
        "embedagent-protocol ==0.1.0",
    ]
    assert [item["name"] for item in report["distributions"]] == list(WHEEL_PACKAGES)


@pytest.mark.parametrize(
    ("distribution", "dependencies", "expected_code"),
    (
        ("embedagent-core", ("requests ==2.0",), "unexpected_runtime_dependency"),
        ("embedagent-protocol", ("embedagent-core ==0.1.0",), "unexpected_runtime_dependency"),
        ("embedagent-composition", ("tomli ==2.4.1",), "unexpected_runtime_dependency"),
        ("embedagent-workflow-cpp", (), "workspace_dependency_missing"),
        ("embedagent-host", ("embedagent-core ==0.1.0",), "workspace_dependency_missing"),
        (
            "embedagent-host",
            ("embedagent-core >=0.1.0", "embedagent-protocol ==0.1.0"),
            "workspace_dependency_invalid",
        ),
        (
            "embedagent-host",
            (
                "embedagent-core ==0.1.0 ; python_version >= '3.8'",
                "embedagent-protocol ==0.1.0",
            ),
            "workspace_dependency_invalid",
        ),
        (
            "embedagent-host",
            (
                "embedagent-core ==0.1.0",
                "EmbedAgent_Core ==0.1.0",
                "embedagent-protocol ==0.1.0",
            ),
            "workspace_dependency_duplicate",
        ),
        (
            "embedagent-host",
            (
                "embedagent-core ==0.1.0",
                "embedagent-protocol ==0.1.0",
                "requests ==2.0",
            ),
            "unexpected_runtime_dependency",
        ),
        (
            "embedagent-shell",
            (
                "prompt-toolkit ==3.0.52",
                "embedagent-core ==0.1.0",
                "embedagent-protocol ==0.1.0",
                "embedagent-workflow-cpp ==0.1.0",
            ),
            "workspace_dependency_missing",
        ),
        (
            "embedagent-shell",
            (
                "prompt-toolkit ==3.0.52",
                "embedagent-core >=0.1.0",
                "embedagent-protocol ==0.1.0",
                "embedagent-host ==0.1.0",
            ),
            "workspace_dependency_invalid",
        ),
    ),
)
def test_wheel_checker_enforces_workspace_dependency_dag(
    tmp_path, distribution, dependencies, expected_code
):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, distribution).unlink()
    _write_wheel(tmp_path, distribution, dependencies=dependencies)

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert expected_code in _error_codes(report, distribution)


def test_product_wheel_allows_documented_third_party_dependencies(tmp_path):
    _write_valid_wheels(tmp_path)

    result, report = _run_checker(tmp_path)

    assert result.returncode == 0
    assert _error_codes(report, "embedagent-shell") == []


def test_wheel_checker_accepts_pep427_build_tag_remainder(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(tmp_path, "embedagent-core", suffix="-1.foo")

    result, report = _run_checker(tmp_path)

    assert result.returncode == 0
    assert _error_codes(report, "embedagent-core") == []


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


@pytest.mark.parametrize(
    "forbidden_file",
    (
        "embedagent_core/leak.py",
        "embedagent_protocol/leak.py",
        "embedagent/protocol/legacy.py",
        "embedagent_host/leak.py",
    ),
)
def test_wheel_checker_rejects_product_wheel_package_ownership_leaks(tmp_path, forbidden_file):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-shell").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-shell",
        files=["embedagent/__init__.py", forbidden_file],
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-shell") == ["forbidden_prefix"]


def test_wheel_checker_rejects_product_package_in_host_wheel(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-host").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-host",
        files=["embedagent_host/__init__.py", "embedagent/leak.py"],
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-host") == ["forbidden_prefix"]


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


def test_wheel_checker_rejects_extra_build_tag_variant(tmp_path):
    _write_valid_wheels(tmp_path)
    _write_wheel(tmp_path, "embedagent-core", suffix="-1.local")

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert report["errors"] == []
    assert report["verified_wheels"] == []
    assert _error_codes(report, "embedagent-core") == ["wheel_ambiguous"]


def test_wheel_checker_rejects_unknown_valid_wheel(tmp_path):
    _write_valid_wheels(tmp_path)
    extra_wheel = _wheel_path(tmp_path, "extra-pkg")
    with zipfile.ZipFile(str(extra_wheel), "w") as wheel:
        wheel.writestr("extra_pkg/__init__.py", b"")
        wheel.writestr("extra_pkg-0.1.0.dist-info/METADATA", _metadata("extra-pkg"))

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert report["errors"] == [
        {
            "code": "unplanned_wheel",
            "detail": "unplanned wheel: extra_pkg-0.1.0-py3-none-any.whl",
        }
    ]
    assert report["verified_wheels"] == []


def test_wheel_checker_rejects_unparseable_extra_wheel(tmp_path):
    _write_valid_wheels(tmp_path)
    (tmp_path / "not-a-wheel.whl").write_bytes(b"not a zip")

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert report["errors"] == [
        {
            "code": "wheel_filename_unrecognized",
            "detail": "unrecognized wheel filename: not-a-wheel.whl",
        }
    ]
    assert report["verified_wheels"] == []


def test_wheel_checker_reports_only_the_current_verified_wheel_set(tmp_path):
    _write_valid_wheels(tmp_path)

    result, report = _run_checker(tmp_path)

    assert result.returncode == 0
    assert report["errors"] == []
    assert report["verified_wheels"] == [
        "embedagent_core-0.1.0-py3-none-any.whl",
        "embedagent_protocol-0.1.0-py3-none-any.whl",
        "embedagent_host-0.1.0-py3-none-any.whl",
        "embedagent_composition-0.1.0-py3-none-any.whl",
        "embedagent_workflow_cpp-0.1.0-py3-none-any.whl",
        "embedagent_shell-0.1.0-py3-none-any.whl",
    ]


@pytest.mark.parametrize(
    ("files", "raw_name_replacements"),
    (
        (
            ["embedagent_core/backslash.py"],
            (
                (
                    b"embedagent_core/backslash.py",
                    b"embedagent_core\\backslash.py",
                ),
            ),
        ),
        (
            ["embedagent_core/__init__.py", "xembedagent_core/absolute.py"],
            ((b"xembedagent_core/absolute.py", b"/embedagent_core/absolute.py"),),
        ),
        (["embedagent_core/__init__.py", "C:/escape.py"], ()),
        (["embedagent_core/../embedagent_host/leak.py"], ()),
        (["embedagent_core/.. /embedagent_host/leak.py"], ()),
        (["embedagent_core/./module.py"], ()),
        (
            ["embedagent_core/nullx.py"],
            ((b"embedagent_core/nullx.py", b"embedagent_core/null\x00.py"),),
        ),
    ),
)
def test_wheel_checker_rejects_unsafe_raw_member_paths(tmp_path, files, raw_name_replacements):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        files=files,
        raw_name_replacements=raw_name_replacements,
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["member_path_invalid"]


@pytest.mark.parametrize(
    "files",
    (
        ["embedagent_core/module.py", "EMBEDAGENT_CORE/MODULE.PY"],
        ["embedagent_core/name.py", "embedagent_core/name.py. "],
        ["embedagent_core/path.py", "embedagent_core//path.py"],
    ),
)
def test_wheel_checker_rejects_windows_member_path_collisions(tmp_path, files):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(tmp_path, "embedagent-core", files=files)

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["member_path_collision"]


@pytest.mark.parametrize(
    "filename",
    (
        "embedagent_core/CON.py",
        "embedagent_core/nul.txt",
        "embedagent_core/COM1.bin",
        "embedagent_core/LPT9",
    ),
)
def test_wheel_checker_rejects_win32_reserved_device_names(tmp_path, filename):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(tmp_path, "embedagent-core", files=[filename])

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["member_path_invalid"]


@pytest.mark.parametrize(
    "filename",
    (
        "embedagent_core/COM\u00b9.bin",
        "embedagent_core/com\u00b2.TxT",
        "embedagent_core/CoM\u00b3",
        "embedagent_core/LPT\u00b9.log",
        "embedagent_core/lpt\u00b2.BIN",
        "embedagent_core/LpT\u00b3",
    ),
)
def test_wheel_checker_rejects_superscript_win32_device_names(tmp_path, filename):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(tmp_path, "embedagent-core", files=[filename])

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["member_path_invalid"]


def test_wheel_checker_accepts_names_near_win32_reserved_devices(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        files=[
            "embedagent_core/COM0.bin",
            "embedagent_core/COM10.bin",
            "embedagent_core/CONSOLE.py",
            "embedagent_core/NULLED.txt",
            "embedagent_core/CLOCK.txt",
        ],
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode == 0
    assert _error_codes(report, "embedagent-core") == []


def test_wheel_checker_does_not_expand_unicode_case_keys(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        files=[
            "embedagent_core/stra\u00dfe.txt",
            "embedagent_core/strasse.txt",
        ],
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode == 0
    assert _error_codes(report, "embedagent-core") == []


def test_wheel_checker_collides_non_ascii_single_codepoint_case_pair(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        files=["embedagent_core/\u00c4.txt", "embedagent_core/\u00e4.txt"],
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["member_path_collision"]


def test_wheel_checker_collides_micro_sign_and_greek_capital_mu(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        files=["embedagent_core/\u00b5.txt", "embedagent_core/\u039c.txt"],
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["member_path_collision"]


def test_wheel_checker_keeps_sharp_s_and_capital_sharp_s_distinct(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        files=["embedagent_core/\u00df.txt", "embedagent_core/\u1e9e.txt"],
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode == 0
    assert _error_codes(report, "embedagent-core") == []


def test_wheel_checker_rejects_invalid_filename_version(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(tmp_path, "embedagent-core", version="not_a_version")

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["wheel_filename_invalid"]


def test_wheel_checker_rejects_unrelated_dist_info_identity(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        metadata_entry="unrelated-9.9.9.dist-info/METADATA",
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["dist_info_identity_mismatch"]


def test_product_wheel_rejects_webapp_source_and_node_modules(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-shell").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-shell",
        files=[
            "embedagent/__init__.py",
            "embedagent/frontend/gui/webapp/node_modules/tool.py",
        ],
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-shell") == ["forbidden_prefix"]


def test_wheel_checker_rejects_a_second_dist_info_stem(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        extra_metadata_entries=(("unrelated-9.9.9.dist-info/WHEEL", b"Wheel-Version: 1.0\n"),),
    )

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["dist_info_identity_mismatch"]


def test_wheel_checker_rejects_metadata_version_mismatch(tmp_path):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    metadata = _metadata("embedagent-core").replace(b"Version: 0.1.0", b"Version: 9.9.9")
    _write_wheel(tmp_path, "embedagent-core", metadata_bytes=metadata)

    result, report = _run_checker(tmp_path)

    assert result.returncode != 0
    assert _error_codes(report, "embedagent-core") == ["metadata_version_mismatch"]


def test_wheel_checker_limits_artifact_size_before_opening_zip(tmp_path, monkeypatch):
    _write_valid_wheels(tmp_path)
    checker = _load_checker_module()
    core_wheel = _wheel_path(tmp_path, "embedagent-core")
    monkeypatch.setattr(checker, "MAX_ARTIFACT_SIZE", core_wheel.stat().st_size - 1, raising=False)

    report = checker.build_report(tmp_path)

    assert _error_codes(report, "embedagent-core") == ["artifact_too_large"]


def test_wheel_checker_limits_archive_entry_count(tmp_path, monkeypatch):
    _write_valid_wheels(tmp_path)
    _wheel_path(tmp_path, "embedagent-core").unlink()
    _write_wheel(
        tmp_path,
        "embedagent-core",
        files=["embedagent_core/__init__.py", "embedagent_core/extra.py"],
    )
    checker = _load_checker_module()
    monkeypatch.setattr(checker, "MAX_ARCHIVE_ENTRIES", 2, raising=False)

    report = checker.build_report(tmp_path)

    assert _error_codes(report, "embedagent-core") == ["archive_entry_limit"]


def test_wheel_checker_limits_total_filename_bytes(tmp_path, monkeypatch):
    _write_valid_wheels(tmp_path)
    checker = _load_checker_module()
    monkeypatch.setattr(checker, "MAX_FILENAME_BYTES", 8, raising=False)

    report = checker.build_report(tmp_path)

    assert _error_codes(report, "embedagent-core") == ["archive_filename_limit"]
