from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "test-suite.py"


def load_test_suite_script():
    spec = importlib.util.spec_from_file_location("embedagent_test_suite", str(SCRIPT_PATH))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tdd_command_runs_only_explicit_targets_without_coverage():
    suite = load_test_suite_script()

    command = suite.build_command(
        ("tdd", "tests/test_agent_effect_kernel.py::test_kernel_plans_context_before_provider")
    )

    assert command == [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_agent_effect_kernel.py::test_kernel_plans_context_before_provider",
        "-q",
        "-x",
        "--tb=short",
    ]
    assert not any(item.startswith("--cov") for item in command)


@pytest.mark.parametrize(
    ("argv", "expression"),
    (
        (("failed",), "not release and not performance and not slow and not gui"),
        (("pre-push",), "not release and not performance and not slow and not gui"),
        (("full",), "not release and not performance"),
        (("release",), "release"),
        (("performance",), "performance"),
    ),
)
def test_named_commands_use_stable_marker_expressions(argv, expression):
    suite = load_test_suite_script()

    command = suite.build_command(argv)

    assert command[:4] == [sys.executable, "-m", "pytest", "tests/"]
    marker_index = command.index("-m", 3)
    assert command[marker_index + 1] == expression


def test_failed_command_is_only_a_local_repair_loop():
    suite = load_test_suite_script()

    command = suite.build_command(("failed",))

    assert "--lf" in command
    assert "-x" in command
    assert not any(item.startswith("--cov") for item in command)


def test_full_coverage_uses_pyproject_coverage_sources():
    suite = load_test_suite_script()

    command = suite.build_command(("full", "--coverage"))

    assert "--cov" in command
    assert "--cov-config=pyproject.toml" in command
    assert "--cov-report=xml" in command
    assert "--cov-report=term-missing" in command
    assert "--cov=src/embedagent" not in command


def test_tdd_requires_an_explicit_target():
    suite = load_test_suite_script()

    with pytest.raises(SystemExit):
        suite.build_command(("tdd",))


def test_primary_partition_rejects_release_performance_overlap():
    suite = load_test_suite_script()

    with pytest.raises(ValueError, match="release and performance"):
        suite.primary_partition(("release", "performance"))


def test_primary_partition_defaults_to_regular():
    suite = load_test_suite_script()

    assert suite.primary_partition(()) == "regular"
    assert suite.primary_partition(("gui",)) == "regular"
    assert suite.primary_partition(("release",)) == "release"
    assert suite.primary_partition(("performance",)) == "performance"


def test_nested_full_pytest_scan_reports_subprocess_call(tmp_path):
    suite = load_test_suite_script()
    test_file = tmp_path / "test_nested.py"
    test_file.write_text(
        "import subprocess\n" "subprocess.run(['python', '-m', 'pytest', 'tests/'])\n",
        encoding="utf-8",
    )

    violations = suite.nested_full_pytest_violations(tmp_path)

    assert violations == ("test_nested.py:2",)


def test_main_runs_the_built_command(monkeypatch):
    suite = load_test_suite_script()
    calls = []
    monkeypatch.setattr(
        suite.subprocess,
        "call",
        lambda command: calls.append(command) or 0,
    )

    assert suite.main(("pre-push",)) == 0
