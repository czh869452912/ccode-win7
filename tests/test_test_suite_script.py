from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

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
    target = "tests/test_example.py::test_failure"

    command = suite.build_command(("failed",), failed_targets=(target,))

    assert target in command
    assert "tests/" not in command
    assert "--lf" not in command
    assert "-x" in command
    assert not any(item.startswith("--cov") for item in command)


def test_failed_command_requires_collected_targets():
    suite = load_test_suite_script()

    with pytest.raises(ValueError, match="no matching failed tests"):
        suite.build_command(("failed",))


def test_failed_main_skips_subprocess_when_no_regular_failures(monkeypatch, capsys):
    suite = load_test_suite_script()
    monkeypatch.setattr(suite, "collect_failed_targets", lambda: (0, ()))
    monkeypatch.setattr(
        suite,
        "_run",
        lambda command: pytest.fail("failed command must not start pytest"),
    )

    assert suite.main(("failed",)) == 0
    assert "No failed tests" in capsys.readouterr().out


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


def test_collect_failed_targets_filters_stale_and_non_fast_nodes(monkeypatch, tmp_path):
    suite = load_test_suite_script()
    regular = "tests/test_regular.py::test_failure"
    release = "tests/test_release.py::test_failure"
    stale = "tests/test_regular.py::test_removed"
    cache_path = tmp_path / ".pytest_cache" / "v" / "cache" / "lastfailed"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        '{"%s": true, "%s": true, "%s": true}' % (regular, release, stale),
        encoding="utf-8",
    )

    class Item(object):
        def __init__(self, nodeid, marker_names=()):
            self.nodeid = nodeid
            self._marker_names = marker_names

        def iter_markers(self):
            return tuple(SimpleNamespace(name=name) for name in self._marker_names)

    def collect(args, plugins):
        plugins[0].items = [
            Item(regular),
            Item(release, ("release",)),
            Item("tests/test_other.py::test_not_cached"),
        ]
        return 0

    monkeypatch.setattr(pytest, "main", collect)

    status, targets = suite.collect_failed_targets(tmp_path)

    assert status == 0
    assert targets == (regular,)


def test_collect_failed_targets_propagates_collection_failure(monkeypatch, tmp_path):
    suite = load_test_suite_script()
    cache_path = tmp_path / ".pytest_cache" / "v" / "cache" / "lastfailed"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        '{"tests/test_regular.py::test_failure": true}',
        encoding="utf-8",
    )
    monkeypatch.setattr(pytest, "main", lambda args, plugins: 2)

    assert suite.collect_failed_targets(tmp_path) == (2, ())


def test_audit_collects_quietly(monkeypatch, tmp_path):
    suite = load_test_suite_script()
    calls = []

    def collect(args, plugins):
        calls.append(args)
        return 0

    monkeypatch.setattr(pytest, "main", collect)

    assert suite.audit(tmp_path) == 1
    assert calls == [["tests/", "--collect-only", "-o", "addopts=", "-p", "no:terminal"]]


def test_main_routes_audit_without_starting_a_pytest_subprocess(monkeypatch):
    suite = load_test_suite_script()
    monkeypatch.setattr(suite, "audit", lambda: 7, raising=False)

    assert suite.main(("audit",)) == 7


def test_main_runs_the_built_command(monkeypatch):
    suite = load_test_suite_script()
    calls = []
    monkeypatch.setattr(
        suite.subprocess,
        "call",
        lambda command: calls.append(command) or 0,
    )

    assert suite.main(("pre-push",)) == 0
