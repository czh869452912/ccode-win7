# TDD Test Feedback Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove pathological test scheduling and provide one audited command surface for fast local TDD, complete regular regression, release tests, and performance tests.

**Architecture:** Keep pytest as the test engine and add a small Python 3.8 command wrapper that owns stable suite expressions. Classify release and performance tests with orthogonal markers, make all remaining Python tests the regular partition, reject overlapping primary markers and nested full-suite pytest calls, then make Makefile, documentation, and CI consume the same wrapper.

**Tech Stack:** Python 3.8 standard library, pytest 8, pytest-cov, uv, GNU Make, GitHub Actions, PowerShell release tests, and the existing Node webapp toolchain.

---

## Scope Boundary

This is the first independently deliverable plan from
`docs/superpowers/specs/2026-07-30-tdd-test-feedback-design.md`.

It implements the feedback foundation:

- remove recursive full-suite execution
- separate regular, release, and performance partitions
- add `tdd`, `failed`, `pre-push`, `full`, `release`, `performance`, and
  `audit` commands
- remove coverage from the local TDD/pre-push path
- run the fixed complete partitions in CI
- publish the new commands in active documentation

It deliberately does not move all 146 test modules, split the five largest
modules, add architecture-owner slices, or introduce pytest-xdist. Those are
follow-up plans after this foundation produces a stable inventory and timing
baseline.

## Execution Rules

Execute the plan in an isolated worktree created from the approved design
commit:

```powershell
git worktree add ..\ccode-win7-tdd-feedback -b codex/tdd-test-feedback main
Set-Location ..\ccode-win7-tdd-feedback
git log -2 --oneline
```

Expected: `82bf35b2 docs: design faster TDD test feedback` is present or is an
ancestor of `HEAD`.

Use Python 3.8 syntax only. Do not add pytest plugins or edit `uv.lock`.

After every task, run its focused tests and commit only the listed files. Do
not run `make ci` during the red/green steps because this plan is specifically
removing full-suite work from the inner loop.

## Target File Map

New files:

- `scripts/test-suite.py`: cross-platform suite command builder, subprocess
  entry point, collection audit, and nested-pytest policy scan
- `tests/test_test_suite_script.py`: pure command-builder and audit-helper
  tests
- `tests/test_test_suite_policy.py`: repository-level suite classification and
  no-recursion guards

Existing files modified by the foundation:

- `tests/test_hygn_03_warning_cleanup.py`: keep warning-configuration checks;
  delete recursive pytest execution
- `tests/test_session_performance.py`: mark the module as performance
- release-oriented test modules listed in Task 3: mark each module as release
- `pyproject.toml`: register new markers and broaden configured coverage sources
- `scripts/lint.py`: include the new script in default lint targets
- `tests/test_lint_script.py`: update the exact default lint command contract
- `Makefile`: publish suite targets without local coverage
- `tests/test_packaging_control_plane.py`: protect Makefile and CI command wiring
- `AGENTS.md`, `README.md`, `docs/implementation-roadmap.md`: publish the active
  workflow and remaining follow-up boundary
- `.github/workflows/ci.yml`: execute regular, performance, release, and
  frontend partitions as fixed jobs

## Task 1: Add The Test Suite Command Contract

**Files:**

- Create: `scripts/test-suite.py`
- Create: `tests/test_test_suite_script.py`
- Modify: `scripts/lint.py`
- Modify: `tests/test_lint_script.py`

- [ ] **Step 1: Write failing command-builder tests**

Create `tests/test_test_suite_script.py` with a file loader matching the
existing lint-script test style:

```python
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
```

- [ ] **Step 2: Run the command tests and verify the script is missing**

```powershell
uv run pytest tests/test_test_suite_script.py -v
```

Expected: FAIL while loading `scripts/test-suite.py` because the file does not
exist.

- [ ] **Step 3: Implement the minimal command wrapper**

Create `scripts/test-suite.py`:

```python
"""Run EmbedAgent test feedback partitions through one stable entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import List, Sequence

REGULAR_EXPRESSION = "not release and not performance"
PRE_PUSH_EXPRESSION = "not release and not performance and not slow and not gui"


def _parser():
    parser = argparse.ArgumentParser(description="Run an EmbedAgent test suite partition.")
    commands = parser.add_subparsers(dest="command", required=True)

    tdd = commands.add_parser("tdd", help="Run exact test nodes or files.")
    tdd.add_argument("targets", nargs="+")

    commands.add_parser("failed", help="Rerun failures in the regular fast partition.")
    commands.add_parser("pre-push", help="Run the local fast partition.")

    full = commands.add_parser("full", help="Run all regular Python tests.")
    full.add_argument("--coverage", action="store_true")

    commands.add_parser("release", help="Run release and packaging tests.")
    commands.add_parser("performance", help="Run explicit performance tests.")
    return parser


def _partition_command(expression):
    # type: (str) -> List[str]
    return [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-m",
        expression,
        "--durations=20",
    ]


def build_command(argv):
    # type: (Sequence[str]) -> List[str]
    args = _parser().parse_args(list(argv))
    if args.command == "tdd":
        return [sys.executable, "-m", "pytest"] + list(args.targets) + [
            "-q",
            "-x",
            "--tb=short",
        ]
    if args.command == "failed":
        return _partition_command(PRE_PUSH_EXPRESSION) + ["--lf", "-q", "-x", "--tb=short"]
    if args.command == "pre-push":
        return _partition_command(PRE_PUSH_EXPRESSION)
    if args.command == "full":
        command = _partition_command(REGULAR_EXPRESSION)
        if args.coverage:
            command.extend(
                (
                    "--cov",
                    "--cov-config=pyproject.toml",
                    "--cov-report=xml",
                    "--cov-report=term-missing",
                )
            )
        return command
    if args.command == "release":
        return _partition_command("release")
    if args.command == "performance":
        return _partition_command("performance")
    raise ValueError("unsupported test suite command: %s" % args.command)


def _run(command):
    # type: (Sequence[str]) -> int
    print("+ " + " ".join(command), flush=True)
    return subprocess.call(list(command))


def main(argv=()):
    # type: (Sequence[str]) -> int
    return _run(build_command(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Do not add passthrough pytest arguments yet. Exact node/file selection covers
the TDD use case without creating an ambiguous second argparse surface.

- [ ] **Step 4: Add the script to the lint command contract**

Add `"scripts/test-suite.py",` to `DEFAULT_TARGETS` in `scripts/lint.py`.
Update both expected default command arrays in `tests/test_lint_script.py` so
the new path appears immediately after `scripts/lint.py`:

```python
"scripts/lint.py",
"scripts/test-suite.py",
"scripts/build-python-distributions.py",
```

- [ ] **Step 5: Run focused tests and lint**

```powershell
uv run pytest tests/test_test_suite_script.py tests/test_lint_script.py -v
uv run --locked python scripts/lint.py scripts/test-suite.py tests/test_test_suite_script.py tests/test_lint_script.py
```

Expected: all tests pass; Ruff and Black checks pass.

- [ ] **Step 6: Commit**

```powershell
git add scripts/test-suite.py scripts/lint.py tests/test_test_suite_script.py tests/test_lint_script.py
git commit -m "test: add unified test suite command"
```

## Task 2: Prevent Recursive Full-Suite Execution And Define Partition Policy

**Files:**

- Modify: `scripts/test-suite.py`
- Modify: `tests/test_test_suite_script.py`
- Create: `tests/test_test_suite_policy.py`
- Modify: `tests/test_hygn_03_warning_cleanup.py`

- [ ] **Step 1: Write failing policy-helper tests**

Append to `tests/test_test_suite_script.py`:

```python
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
        "import subprocess\n"
        "subprocess.run(['python', '-m', 'pytest', 'tests/'])\n",
        encoding="utf-8",
    )

    violations = suite.nested_full_pytest_violations(tmp_path)

    assert violations == ("test_nested.py:2",)
```

Create `tests/test_test_suite_policy.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "test-suite.py"


def load_test_suite_script():
    spec = importlib.util.spec_from_file_location("embedagent_test_suite_policy", str(SCRIPT_PATH))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_test_modules_do_not_spawn_nested_full_pytest():
    suite = load_test_suite_script()

    assert suite.nested_full_pytest_violations(ROOT / "tests") == ()
```

- [ ] **Step 2: Run the tests and verify both missing policy code and the current recursion**

```powershell
uv run pytest tests/test_test_suite_script.py tests/test_test_suite_policy.py -v
```

Expected: FAIL because the partition/scan helpers do not exist and
`test_hygn_03_warning_cleanup.py` still starts `python -m pytest tests/`.

- [ ] **Step 3: Add pure partition and nested-process policy helpers**

Add `ast` and `Path`, and replace the existing typing import so the complete
import block remains Ruff-sorted:

```python
import argparse
import ast
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple
```

Add the helpers:

```python
def primary_partition(marker_names):
    # type: (Iterable[str]) -> str
    names = frozenset(marker_names)
    if "release" in names and "performance" in names:
        raise ValueError("test cannot be both release and performance")
    if "release" in names:
        return "release"
    if "performance" in names:
        return "performance"
    return "regular"


def _call_name(node):
    # type: (ast.AST) -> str
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return (prefix + "." if prefix else "") + node.attr
    return ""


def _literal_strings(node):
    # type: (ast.AST) -> Tuple[str, ...]
    values = []
    for child in ast.walk(node):
        if isinstance(child, ast.Str):
            values.append(str(child.s))
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.append(child.value)
    return tuple(values)


def nested_full_pytest_violations(test_root):
    # type: (Path) -> Tuple[str, ...]
    root = Path(test_root).resolve()
    violations = []
    for path in sorted(root.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node.func) not in (
                "subprocess.call",
                "subprocess.Popen",
                "subprocess.run",
            ):
                continue
            values = _literal_strings(node)
            normalized = tuple(value.rstrip("/\\") for value in values)
            if "-m" in values and "pytest" in values and "tests" in normalized:
                violations.append("%s:%d" % (path.relative_to(root).as_posix(), node.lineno))
    return tuple(violations)
```

The scanner intentionally checks only subprocess APIs. Command arrays asserted
as test data are allowed; executing the repository test root from a test is
not.

- [ ] **Step 4: Delete the recursive test while keeping warning policy checks**

In `tests/test_hygn_03_warning_cleanup.py`:

- delete `test_pytest_runs_without_deprecation_warnings`
- delete the now-unused `subprocess` and `sys` imports
- keep `test_pytest_config_has_warning_filters`
- keep `test_no_utcnnow_in_characterization_tests`

Do not replace the deleted test with another pytest subprocess. The normal CI
pytest invocation already applies `[tool.pytest.ini_options].filterwarnings`.

- [ ] **Step 5: Run the policy tests**

```powershell
uv run pytest tests/test_test_suite_script.py tests/test_test_suite_policy.py tests/test_hygn_03_warning_cleanup.py -v
```

Expected: all command, partition-helper, and no-recursion tests pass.

- [ ] **Step 6: Commit**

```powershell
git add scripts/test-suite.py tests/test_test_suite_script.py tests/test_test_suite_policy.py tests/test_hygn_03_warning_cleanup.py
git commit -m "test: prevent recursive full-suite execution"
```

## Task 3: Separate Release And Performance Partitions

**Files:**

- Modify: `scripts/test-suite.py`
- Modify: `tests/test_test_suite_script.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_test_suite_policy.py`
- Modify: `tests/test_session_performance.py`
- Modify: `tests/test_gui_launcher_exe_contract.py`
- Modify: `tests/test_package_report_provenance.py`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_phase7_bundle_assembly.py`
- Modify: `tests/test_phase7_bundle_dependency_contract.py`
- Modify: `tests/test_phase7_dependency_stage.py`
- Modify: `tests/test_phase7_doctor.py`
- Modify: `tests/test_phase7_evidence_kit.py`
- Modify: `tests/test_phase7_verification.py`
- Modify: `tests/test_python_distribution_smoke.py`
- Modify: `tests/test_release_evidence.py`
- Modify: `tests/test_release_identity.py`
- Modify: `tests/test_release_reproducibility.py`

- [ ] **Step 1: Write failing marker-policy tests**

Add `import tomli` with the existing imports in `tests/test_test_suite_policy.py`, then append:

```python
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
```

- [ ] **Step 2: Run the marker-policy tests and verify they fail**

```powershell
uv run pytest tests/test_test_suite_policy.py -v
```

Expected: FAIL because the markers and module declarations do not exist.

- [ ] **Step 3: Register the primary partition markers**

Add to `[tool.pytest.ini_options].markers` in `pyproject.toml`:

```toml
"release: packaging, distribution, offline, and release-gate tests",
"performance: explicit performance threshold tests",
```

Keep the existing markers during this foundation. Removing or renaming
`unit`, `harness`, `session`, `gui`, or `slow` belongs to the directory
migration plan.

- [ ] **Step 4: Mark the performance module**

Add `import pytest` to `tests/test_session_performance.py`, then place this
after its imports:

```python
pytestmark = pytest.mark.performance
```

- [ ] **Step 5: Mark every release module**

For every file in `RELEASE_MODULES`, add `import pytest` when it is not already
present and add this module-level declaration after imports/constants:

```python
pytestmark = pytest.mark.release
```

Mark the whole module, including its fast contract cases. These modules share
release ownership and remain fully executed by the release partition. Do not
split them in this foundation task.

- [ ] **Step 6: Write the failing audit-dispatch test**

Append to `tests/test_test_suite_script.py`:

```python
def test_main_routes_audit_without_starting_a_pytest_subprocess(monkeypatch):
    suite = load_test_suite_script()
    monkeypatch.setattr(suite, "audit", lambda: 7, raising=False)

    assert suite.main(("audit",)) == 7
```

Run:

```powershell
uv run pytest tests/test_test_suite_script.py::test_main_routes_audit_without_starting_a_pytest_subprocess -v
```

Expected: FAIL because `audit` is not a recognized command and `main` does not
route it in process.

- [ ] **Step 7: Add the `audit` command**

Add `import json` to `scripts/test-suite.py`, then add an `audit` subparser and
collection recorder:

```python
commands.add_parser("audit", help="Audit complete and non-overlapping partitions.")
```

```python
class _CollectionRecorder(object):
    def __init__(self):
        self.items = []

    def pytest_collection_modifyitems(self, items):
        self.items = list(items)


def audit(root=Path(".")):
    # type: (Path) -> int
    import pytest

    recorder = _CollectionRecorder()
    result = pytest.main(["tests/", "--collect-only", "-q"], plugins=[recorder])
    if int(result) != 0:
        return int(result)

    counts = {"regular": 0, "release": 0, "performance": 0}
    errors = []
    for item in recorder.items:
        markers = tuple(marker.name for marker in item.iter_markers())
        try:
            partition = primary_partition(markers)
        except ValueError as exc:
            errors.append("%s: %s" % (item.nodeid, exc))
            continue
        counts[partition] += 1

    for violation in nested_full_pytest_violations(Path(root) / "tests"):
        errors.append("nested full pytest: %s" % violation)
    if counts["release"] == 0:
        errors.append("release partition is empty")
    if counts["performance"] == 0:
        errors.append("performance partition is empty")

    print(json.dumps({"counts": counts, "errors": errors}, sort_keys=True))
    return 1 if errors else 0
```

Change `main` so audit remains in-process:

```python
def main(argv=()):
    # type: (Sequence[str]) -> int
    argv = tuple(argv)
    if argv == ("audit",):
        return audit()
    return _run(build_command(argv))
```

`build_command(("audit",))` need not return a subprocess command.

- [ ] **Step 8: Run marker policy and collection audit**


```powershell
uv run pytest tests/test_test_suite_policy.py -v
uv run python scripts/test-suite.py audit
uv run pytest tests/ -m release --collect-only -q
uv run pytest tests/ -m performance --collect-only -q
```

Expected:

- policy tests pass
- audit JSON contains non-zero `regular`, `release`, and `performance` counts
- audit JSON contains an empty `errors` list
- performance collection contains exactly the five session performance cases
- release collection contains each listed release module

- [ ] **Step 9: Verify the fast command no longer selects release/performance tests**

```powershell
uv run python scripts/test-suite.py pre-push
```

Expected: PASS. The output does not contain
`test_python_distribution_smoke.py`, `test_packaging_control_plane.py`, or
`test_session_performance.py`.

- [ ] **Step 10: Commit**

```powershell
git add pyproject.toml tests
git commit -m "test: separate release and performance partitions"
```

## Task 4: Publish Fast Local Commands

**Files:**

- Modify: `Makefile`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/implementation-roadmap.md`

- [ ] **Step 1: Update the Makefile contract test first**

Rename
`TestPythonDistributionPackagingContract.test_make_ci_builds_checks_and_smokes_wheels_before_bundle_validation`
to `test_make_ci_runs_complete_test_partitions_before_bundle_validation` and replace its assertions with:

```python
self.assertIn("test:\n\tuv run python scripts/test-suite.py pre-push", makefile)
self.assertIn("test-full:\n\tuv run python scripts/test-suite.py full", makefile)
self.assertIn("test-release:\n\tuv run python scripts/test-suite.py release", makefile)
self.assertIn("test-performance:\n\tuv run python scripts/test-suite.py performance", makefile)
self.assertIn("test-audit:\n\tuv run python scripts/test-suite.py audit", makefile)
self.assertIn("python-distributions-check: python-distributions-build", makefile)
self.assertIn("python-distributions-smoke: python-distributions-check", makefile)
self.assertIn("offline-bundle-contract: python-distributions-smoke", makefile)
self.assertIn(
    "ci: lint test-audit test-full test-release test-performance smoke offline-bundle-contract",
    makefile,
)
```

- [ ] **Step 2: Run the contract test and verify the old Makefile fails it**

```powershell
uv run pytest tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_make_ci_runs_complete_test_partitions_before_bundle_validation -v
```

Expected: FAIL because the new targets do not exist.

- [ ] **Step 3: Replace Makefile test targets**

Use this target block while preserving the existing install, lint, smoke,
distribution, and offline-bundle recipes:

```make
.PHONY: install test test-full test-release test-performance test-audit harness lint lint-fix smoke python-distributions-build python-distributions-check python-distributions-smoke offline-bundle-contract ci

test:
	uv run python scripts/test-suite.py pre-push

test-full:
	uv run python scripts/test-suite.py full

test-release:
	uv run python scripts/test-suite.py release

test-performance:
	uv run python scripts/test-suite.py performance

test-audit:
	uv run python scripts/test-suite.py audit
```

Change the `ci` dependency line to:

```make
ci: lint test-audit test-full test-release test-performance smoke offline-bundle-contract
```

Keep `harness` as the existing focused command until the owner-slice follow-up
replaces domain markers.

- [ ] **Step 4: Replace the Quick Commands in AGENTS.md**

Use these exact commands and descriptions:

```bash
# Run one test node or file during the TDD red/green loop
uv run python scripts/test-suite.py tdd tests/test_agent_effect_kernel.py

# Re-run failures from the fast local partition
uv run python scripts/test-suite.py failed

# Run the local pre-push partition (no coverage, release, performance, slow, or GUI tests)
uv run python scripts/test-suite.py pre-push

# Run the complete regular Python partition
uv run python scripts/test-suite.py full

# Run delivery and performance partitions explicitly
uv run python scripts/test-suite.py release
uv run python scripts/test-suite.py performance

# Audit partition collection and forbidden nested pytest execution
uv run python scripts/test-suite.py audit
```

In the pre-merge architecture gate, replace the old fast-subset command with:

```bash
uv run python scripts/test-suite.py full
```

- [ ] **Step 5: Update README and the roadmap**

Replace the README's old `pytest tests/ -m "not slow and not gui"` gate with
the `full` command. Explain in the testing section:

```text
Local TDD uses exact nodes/files or the pre-push partition without coverage.
Complete verification is the audited union of regular, release, performance,
and frontend jobs. Release and performance tests are scheduled separately;
they are not skipped from CI.
```

Add an active quality-program item to `docs/implementation-roadmap.md`:

```text
- TDD feedback foundation: replace the recursive/full local test path with one
  audited suite command, separate release and performance execution, and keep
  complete fixed CI partitions. Architecture-owner directories, slice commands,
  and large test-module decomposition remain the next test-asset migration.
```

- [ ] **Step 6: Run the Makefile contract and documentation searches**

```powershell
uv run pytest tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_make_ci_runs_complete_test_partitions_before_bundle_validation -v
rg -n 'pytest tests/ -m "not slow and not gui"|--cov=src/embedagent' AGENTS.md README.md Makefile
```

Expected: the test passes; the search returns no active command occurrence.

- [ ] **Step 7: Commit**

```powershell
git add Makefile AGENTS.md README.md docs/implementation-roadmap.md tests/test_packaging_control_plane.py
git commit -m "docs: publish layered test feedback commands"
```

## Task 5: Run Complete Fixed Partitions In CI

**Files:**

- Modify: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`
- Modify: `tests/test_packaging_control_plane.py`

- [ ] **Step 1: Write the CI wiring assertions first**

Replace
`TestPythonDistributionPackagingContract.test_ci_workspace_jobs_provision_uv_and_share_offline_build_cache`
with assertions that preserve the existing uv/cache contract and add the fixed
partitions:

```python
workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

self.assertIn("name: Install uv", workflow)
self.assertIn("UV_CACHE_DIR: ${{ github.workspace }}\\.uv-cache", workflow)
self.assertIn("uv sync --locked --python python", workflow)
self.assertIn("python scripts/test-suite.py audit", workflow)
self.assertIn("python scripts/test-suite.py full --coverage", workflow)
self.assertIn("python scripts/test-suite.py performance", workflow)
self.assertIn("python scripts/test-suite.py release", workflow)
self.assertIn("npm test", workflow)
self.assertIn("npm run build", workflow)
self.assertNotIn("--cov=src/embedagent", workflow)
smoke = workflow.split("  smoke:\n", 1)[1].split("  windows-packaging:\n", 1)[0]
self.assertIn("name: Install uv", smoke)
```

- [ ] **Step 2: Run the CI contract and verify it fails**

```powershell
uv run pytest tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_ci_workspace_jobs_provision_uv_and_share_offline_build_cache -v
```

Expected: FAIL because the workflow still invokes pytest directly and has no
performance or frontend job.

- [ ] **Step 3: Broaden configured coverage sources**

Extend `[tool.coverage.run].source` in `pyproject.toml` to exactly:

```toml
source = [
    "src/embedagent",
    "packages/embedagent-core/src/embedagent_core",
    "packages/embedagent-protocol/src/embedagent_protocol",
    "packages/embedagent-host/src/embedagent_host",
    "packages/embedagent-composition/src/embedagent_composition",
    "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp",
]
```

Do not add a coverage percentage threshold in this task. Establish the new
multi-distribution report before setting a non-regression floor.

- [ ] **Step 4: Change the regular test job to audit and run full coverage**

Replace its direct pytest step with:

```yaml
      - name: Audit test partitions
        run: uv run --locked --python "$(which python)" python scripts/test-suite.py audit
      - name: Run complete regular tests
        run: >-
          uv run --locked --python "$(which python)" python
          scripts/test-suite.py full --coverage
```

Keep the existing `coverage.xml` artifact upload.

- [ ] **Step 5: Add the performance job**

Add a Python 3.8 Ubuntu job using the same checkout/setup-python/uv/sync pattern:

```yaml
  performance:
    name: Performance thresholds
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.8"
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: uv sync --locked --python "$(which python)"
      - name: Run performance tests
        run: >-
          uv run --locked --python "$(which python)" python
          scripts/test-suite.py performance
```

- [ ] **Step 6: Add the frontend test/build job**

Use the committed package lock and validate generated static assets:

```yaml
  frontend:
    name: Frontend test and build
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: src/embedagent/frontend/gui/webapp
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: src/embedagent/frontend/gui/webapp/package-lock.json
      - name: Install frontend dependencies
        run: npm ci
      - name: Run frontend tests
        run: npm test
      - name: Build frontend assets
        run: npm run build
      - name: Verify generated assets are committed
        working-directory: .
        run: git diff --exit-code -- src/embedagent/frontend/gui/static
```

Node is build/test tooling only and does not become an offline runtime
dependency.

- [ ] **Step 7: Replace the Windows packaging test list with the release partition**

Keep the existing checkout, Python 3.8.10, uv cache, uv installation, and
locked sync steps. Replace both current targeted pytest steps with:

```yaml
      - name: Run Windows release tests
        run: >-
          uv run --locked --python python python
          scripts/test-suite.py release
```

This ensures every release-marked module runs on the platform that can execute
its PowerShell, junction, and pinned-toolchain cases. Tests may still skip when
the CI host lacks privileges explicitly required by a safety contract; do not
add new skips.

- [ ] **Step 8: Run the CI contract and local YAML-sensitive checks**

```powershell
uv run pytest tests/test_packaging_control_plane.py::TestPythonDistributionPackagingContract::test_ci_workspace_jobs_provision_uv_and_share_offline_build_cache -v
uv run --locked python scripts/lint.py tests/test_packaging_control_plane.py scripts/test-suite.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add .github/workflows/ci.yml pyproject.toml tests/test_packaging_control_plane.py
git commit -m "ci: run complete fixed test partitions"
```

## Task 6: Verify The Foundation And Record Timing Evidence

**Files:**

- No planned source changes
- Update only `docs/superpowers/specs/2026-07-30-tdd-test-feedback-design.md`
  if a verified result exposes a material correction to the approved design

- [ ] **Step 1: Run the runner and policy tests**

```powershell
uv run pytest tests/test_test_suite_script.py tests/test_test_suite_policy.py tests/test_hygn_03_warning_cleanup.py -v
uv run python scripts/test-suite.py audit
```

Expected: all focused tests pass; audit returns exit code `0`, non-zero counts
for all three Python partitions, and no errors.

- [ ] **Step 2: Measure the TDD path**

```powershell
uv run python scripts/test-suite.py tdd tests/test_agent_effect_kernel.py
```

Expected: PASS in less than 10 seconds on the baseline developer machine.

- [ ] **Step 3: Measure the pre-push partition**

```powershell
uv run python scripts/test-suite.py pre-push
```

Expected: PASS. Record the pytest-reported duration in the implementation
handoff. It should be materially below the measured `484.27` seconds and must
not collect release/performance modules.

- [ ] **Step 4: Run every Python partition exactly once**

```powershell
uv run python scripts/test-suite.py full
uv run python scripts/test-suite.py performance
uv run python scripts/test-suite.py release
```

Expected: all three commands pass. Their audit counts sum to the complete
pytest collection count.

- [ ] **Step 5: Run lint and frontend gates**

```powershell
uv run --locked python scripts/lint.py
Push-Location src/embedagent/frontend/gui/webapp
npm test
npm run build
Pop-Location
git diff --exit-code -- src/embedagent/frontend/gui/static
```

Expected: lint, frontend tests, and build pass; the generated static tree has
no unexpected diff.

- [ ] **Step 6: Verify the retired commands and recursion are absent**

```powershell
rg -n 'pytest tests/ -m "not slow and not gui"|--cov=src/embedagent' AGENTS.md README.md Makefile .github/workflows/ci.yml
rg -n -U 'subprocess\.(run|call|Popen)\([\s\S]{0,500}["'']pytest["'']' tests -g '*.py'
```

Expected: both searches return no output.

- [ ] **Step 7: Inspect commit and worktree scope**

```powershell
git status --short
git log --oneline 82bf35b2..HEAD
git diff --stat 82bf35b2..HEAD
```

Expected: only files listed in this plan changed; commits are focused and the
worktree is clean.

## Foundation Completion Checklist

- [ ] No test invokes another complete pytest suite.
- [ ] Local `tdd`, `failed`, and `pre-push` commands never enable coverage.
- [ ] Release and performance tests remain present and run in fixed CI jobs.
- [ ] Regular, release, and performance primary markers are non-overlapping.
- [ ] Audit reports the complete pytest inventory across the three partitions.
- [ ] The frontend test/build job is a required CI partition.
- [ ] Coverage uses the configured multi-distribution source set.
- [ ] The existing six-wheel and offline-bundle build chain remains in
      `make ci`.
- [ ] Python 3.8, offline runtime, and Windows 7 constraints are unchanged.
- [ ] Pre-push duration is materially below the 484.27-second baseline.

## Follow-Up Plan Boundaries

After this foundation is implemented and its audit/timing evidence is stable,
write separate implementation plans for:

1. architecture-owner directories and `slice core|protocol|host|workflow-cpp|product`
2. behavior-based decomposition of the five largest test modules
3. fixed architecture CI sharding and optional isolated-unit parallelism

Those plans must consume the measured partition inventory from this
foundation. They must not introduce a second suite command or duplicate the
primary partition truth.
