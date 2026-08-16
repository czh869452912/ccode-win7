# CLI Output Encoding Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the packaged CLI tolerate localized output on constrained Windows code pages while making the real release smoke deterministic and safely diagnosable.

**Architecture:** A focused product CLI module prepares only `sys.stdout` and `sys.stderr`, preserving their encoding and changing encoding failures to replacement. The stdlib-only release validator drives the staged launcher under `cp1252` and represents process failures with structured, redacted fields; Core, Host, Protocol, and the shared session runtime remain unchanged.

**Tech Stack:** Python 3.8 stdlib, pytest 8, unittest-style release tests, PowerShell packaging pipeline, uv workspace.

---

### Task 1: Own Encoding Tolerance At The CLI Boundary

**Files:**
- Create: `src/embedagent/cli/text_output.py`
- Create: `tests/test_cli_text_output.py`
- Modify: `src/embedagent/cli/app.py:1-105`
- Modify: `tests/test_cli_parser.py:89-104`

- [ ] **Step 1: Write the failing standard-stream tests**

Create `tests/test_cli_text_output.py`:

```python
import io


def _text_stream(encoding):
    raw = io.BytesIO()
    return raw, io.TextIOWrapper(raw, encoding=encoding, errors="strict")


def test_prepare_cli_standard_streams_preserves_encoding_and_replaces_errors(monkeypatch):
    import embedagent.cli.text_output as text_output

    stdout_bytes, stdout = _text_stream("cp1252")
    stderr_bytes, stderr = _text_stream("utf-8")
    with monkeypatch.context() as patch:
        patch.setattr(text_output.sys, "stdout", stdout)
        patch.setattr(text_output.sys, "stderr", stderr)
        text_output.prepare_cli_standard_streams()

    assert stdout.encoding == "cp1252"
    assert stderr.encoding == "utf-8"
    assert stdout.errors == "replace"
    assert stderr.errors == "replace"

    stdout.write("该操作会修改工作区文件。")
    stderr.write("该操作会修改工作区文件。")
    stdout.flush()
    stderr.flush()
    assert b"?" in stdout_bytes.getvalue()
    assert stderr_bytes.getvalue().decode("utf-8") == "该操作会修改工作区文件。"


def test_prepare_cli_standard_streams_leaves_non_reconfigurable_streams_untouched(monkeypatch):
    import embedagent.cli.text_output as text_output

    stdout = io.StringIO()
    stderr = io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(text_output.sys, "stdout", stdout)
        patch.setattr(text_output.sys, "stderr", stderr)
        text_output.prepare_cli_standard_streams()

    stdout.write("该操作会修改工作区文件。")
    stderr.write("该操作会修改工作区文件。")
    assert stdout.getvalue() == "该操作会修改工作区文件。"
    assert stderr.getvalue() == "该操作会修改工作区文件。"
```

Extend `tests/test_cli_parser.py` with an entry-point ordering test:

```python
def test_main_prepares_standard_streams_before_parsing(monkeypatch):
    import embedagent.cli.app as cli_app

    calls = []
    application = type("Application", (), {"run": lambda self: 0})()

    class Parser(object):
        def parse_args(self, argv):
            calls.append(("parse", argv))
            return object()

    monkeypatch.setattr(cli_app, "prepare_cli_standard_streams", lambda: calls.append("prepare"))
    monkeypatch.setattr(cli_app, "build_parser", lambda: Parser())
    monkeypatch.setattr(
        cli_app.CliApplication,
        "from_options",
        classmethod(lambda cls, options: application),
    )

    assert cli_app.main(["run", "hello"]) == 0
    assert calls == ["prepare", ("parse", ["run", "hello"])]
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_cli_text_output.py tests/test_cli_parser.py::test_main_prepares_standard_streams_before_parsing
```

Expected: FAIL because `embedagent.cli.text_output` and `prepare_cli_standard_streams` do not exist.

- [ ] **Step 3: Implement the focused CLI output boundary**

Create `src/embedagent/cli/text_output.py`:

```python
from __future__ import annotations

import sys
from typing import Any


def _prepare_standard_stream(stream: Any) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(errors="replace")


def prepare_cli_standard_streams() -> None:
    _prepare_standard_stream(sys.stdout)
    _prepare_standard_stream(sys.stderr)
```

Import `prepare_cli_standard_streams` in `src/embedagent/cli/app.py` and call it as the first statement in `main(...)`, before `build_parser().parse_args(argv)`:

```python
from embedagent.cli.text_output import prepare_cli_standard_streams


def main(argv: Optional[List[str]] = None) -> int:
    prepare_cli_standard_streams()
    options = build_parser().parse_args(argv)
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_cli_text_output.py tests/test_cli_parser.py tests/test_cli_result.py tests/test_cli_chat.py
```

Expected: all selected tests PASS.

- [ ] **Step 5: Commit the CLI boundary**

```powershell
git add src/embedagent/cli/text_output.py src/embedagent/cli/app.py tests/test_cli_text_output.py tests/test_cli_parser.py
git commit -m "fix(cli): tolerate constrained output encodings"
```

### Task 2: Make The Staged CLI Smoke Exercise `cp1252`

**Files:**
- Modify: `scripts/validate-cli-smoke.py:218-239`
- Modify: `tests/test_packaging_control_plane.py:540-579`

- [ ] **Step 1: Write the failing validator-environment test**

Add a test to `TestRuntimeBundleContract` in `tests/test_packaging_control_plane.py`:

```python
    def test_cli_smoke_pins_english_windows_redirected_output_encoding(self):
        module = _load_python_module(CLI_SMOKE_SCRIPT, "validate_cli_smoke_encoding")

        environment = module._isolated_environment(
            Path("bundle"),
            Path("home"),
        )

        self.assertEqual(environment["PYTHONIOENCODING"], "cp1252")
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestRuntimeBundleContract::test_cli_smoke_pins_english_windows_redirected_output_encoding
```

Expected: FAIL with `KeyError: 'PYTHONIOENCODING'`.

- [ ] **Step 3: Pin the staged child process encoding in the validator**

In `_isolated_environment(...)`, add the test-owned encoding after stripping ambient Python variables:

```python
    environment["PYTHONIOENCODING"] = "cp1252"
```

Do not add this variable to `.github/workflows/ci.yml` or `embedagent.cmd`; it belongs only to the release validator's child environment.

- [ ] **Step 4: Run the contract and real staged-launcher smoke**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestRuntimeBundleContract::test_cli_smoke_pins_english_windows_redirected_output_encoding tests/test_packaging_control_plane.py::TestCliSmokeGate::test_cli_smoke_crosses_staged_launcher_for_both_flavors
```

Expected: both tests PASS. The second test must complete all nine scenarios for both `minimal-cli` and `cpp-desktop` under `cp1252`.

- [ ] **Step 5: Commit the deterministic release condition**

```powershell
git add scripts/validate-cli-smoke.py tests/test_packaging_control_plane.py
git commit -m "test(release): exercise constrained cli encoding"
```

### Task 3: Structure And Redact Launcher Failure Diagnostics

**Files:**
- Modify: `scripts/validate-cli-smoke.py:267-272,500-523`
- Modify: `tests/test_packaging_control_plane.py:579`

- [ ] **Step 1: Write failing diagnostics tests**

Add a cross-platform class before `TestCliSmokeGate` in `tests/test_packaging_control_plane.py`:

```python
class TestCliSmokeFailureReport(unittest.TestCase):
    def test_exit_mismatch_preserves_only_stable_process_fields(self):
        module = _load_python_module(CLI_SMOKE_SCRIPT, "validate_cli_smoke_exit")
        result = subprocess.CompletedProcess(
            ["embedagent.cmd"],
            4,
            stdout="sensitive stdout",
            stderr="sensitive stderr\nerror: protocol_error\n",
        )

        with self.assertRaises(module.CliScenarioFailure) as raised:
            module._require_exit(result, 0, "chat_permission")

        self.assertEqual(str(raised.exception), "cli_scenario_failed")
        self.assertEqual(raised.exception.scenario, "chat_permission")
        self.assertEqual(raised.exception.process_exit_code, 4)
        self.assertEqual(raised.exception.cli_failure_code, "protocol_error")
        self.assertNotIn("sensitive", repr(raised.exception.__dict__))

    def test_main_writes_structured_redacted_scenario_failure(self):
        module = _load_python_module(CLI_SMOKE_SCRIPT, "validate_cli_smoke_report")

        def fail_smoke(bundle_root, workspace, home):
            del bundle_root, workspace, home
            raise module.CliScenarioFailure("chat_permission", 4, "protocol_error")

        original_run_smoke = module._run_smoke
        module._run_smoke = fail_smoke
        try:
            with tempfile.TemporaryDirectory() as tmp:
                test_root = Path(tmp)
                report_path = test_root / "report.json"
                self.assertEqual(
                    module.main(
                        [
                            "--bundle-root",
                            str(test_root / "bundle"),
                            "--workspace",
                            str(test_root / "workspaces"),
                            "--json-report",
                            str(report_path),
                        ]
                    ),
                    1,
                )
                self.assertEqual(
                    json.loads(report_path.read_text(encoding="ascii")),
                    {
                        "cli_failure_code": "protocol_error",
                        "error_type": "CliScenarioFailure",
                        "failure_code": "cli_scenario_failed",
                        "failure_scenario": "chat_permission",
                        "failure_stage": "launcher",
                        "ok": False,
                        "process_exit_code": 4,
                        "schema_version": 2,
                    },
                )
        finally:
            module._run_smoke = original_run_smoke
```

- [ ] **Step 2: Run the diagnostics tests and verify RED**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestCliSmokeFailureReport
```

Expected: FAIL because `CliScenarioFailure` does not exist and `_require_exit(...)` raises an opaque `RuntimeError`.

- [ ] **Step 3: Implement the structured internal failure**

Add this stdlib-only exception above `_require_exit(...)`:

```python
class CliScenarioFailure(RuntimeError):
    def __init__(self, scenario: str, process_exit_code: int, cli_failure_code: str) -> None:
        super().__init__("cli_scenario_failed")
        self.scenario = str(scenario)
        self.process_exit_code = int(process_exit_code)
        self.cli_failure_code = str(cli_failure_code)
```

Replace the opaque raise in `_require_exit(...)`:

```python
        raise CliScenarioFailure(scenario, result.returncode, category)
```

Add a payload builder and use it from `main(...)`:

```python
def _failure_payload(exc: Exception, stage: str) -> Dict[str, object]:
    payload = {
        "error_type": type(exc).__name__,
        "failure_code": str(exc) if type(exc) is RuntimeError else type(exc).__name__,
        "failure_stage": str(stage),
        "ok": False,
        "schema_version": 2,
    }
    if isinstance(exc, CliScenarioFailure):
        payload.update(
            {
                "cli_failure_code": exc.cli_failure_code,
                "failure_code": "cli_scenario_failed",
                "failure_scenario": exc.scenario,
                "process_exit_code": exc.process_exit_code,
            }
        )
    return payload
```

Replace the inline failure dictionary in `main(...)` with:

```python
        _write_json(report_path, _failure_payload(exc, stage))
```

- [ ] **Step 4: Run diagnostics and complete CLI smoke tests**

Run:

```powershell
uv run python scripts/test-suite.py tdd tests/test_packaging_control_plane.py::TestCliSmokeFailureReport tests/test_packaging_control_plane.py::TestCliSmokeGate tests/test_cli_text_output.py tests/test_cli_parser.py tests/test_cli_chat.py
```

Expected: all selected tests PASS and no report contains raw stdout or stderr.

- [ ] **Step 5: Commit safe diagnostics**

```powershell
git add scripts/validate-cli-smoke.py tests/test_packaging_control_plane.py
git commit -m "refactor(release): structure cli smoke failures"
```

### Task 4: Synchronize Durable Documentation And Close The Slice

**Files:**
- Modify: `docs/product/packaging-and-deployment.md:102-123`
- Modify: `docs/superpowers/README.md`
- Move: `docs/superpowers/specs/2026-08-16-cli-output-encoding-boundary-design.md`
- Move: `docs/superpowers/plans/2026-08-16-cli-output-encoding-boundary.md`
- Create: `docs/archive/cli-output-encoding-boundary/README.md`

- [ ] **Step 1: Update the owning delivery authority**

In `docs/product/packaging-and-deployment.md`, extend the CLI launcher and smoke sections with these durable contracts:

```markdown
The product CLI prepares `sys.stdout` and `sys.stderr` once at startup. It keeps
the selected stream encoding and uses replacement for characters the encoding
cannot represent; Core and Host continue to carry Unicode without presentation
fallbacks.
```

```markdown
The validator runs the staged CLI with `PYTHONIOENCODING=cp1252` so the gate is
independent of the development machine locale and covers English Windows
redirected output. Failure reports may include only the scenario ID, process
exit code, and stable CLI failure code; raw stdout/stderr and interaction data
remain forbidden.
```

- [ ] **Step 2: Create the archive index and move the completed slice**

Create `docs/archive/cli-output-encoding-boundary/README.md`:

```markdown
# CLI Output Encoding Boundary Archive

This package records the closed 2026-08-16 convergence that made CLI standard
stream encoding tolerant at the product boundary, exercised the staged launcher
under `cp1252`, and made smoke failures structured without retaining raw output.

- `2026-08-16-cli-output-encoding-boundary-design.md`
- `2026-08-16-cli-output-encoding-boundary.md`
```

Move the spec and plan into that directory and remove the completed slice from
`docs/superpowers/README.md`:

```powershell
git mv docs/superpowers/specs/2026-08-16-cli-output-encoding-boundary-design.md docs/archive/cli-output-encoding-boundary/
git mv docs/superpowers/plans/2026-08-16-cli-output-encoding-boundary.md docs/archive/cli-output-encoding-boundary/
```

- [ ] **Step 3: Verify documentation guards**

Run:

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -q
```

Expected: all architecture guard tests PASS.

- [ ] **Step 4: Commit durable documentation and archive closure**

```powershell
git add docs/product/packaging-and-deployment.md docs/superpowers/README.md docs/archive/cli-output-encoding-boundary
git commit -m "docs: close cli output encoding boundary"
```

### Task 5: Run Complete Delivery Verification

**Files:**
- Verify only; no planned modifications.

- [ ] **Step 1: Run focused regression tests**

```powershell
uv run python scripts/test-suite.py tdd tests/test_cli_text_output.py tests/test_cli_parser.py tests/test_cli_chat.py tests/test_packaging_control_plane.py::TestCliSmokeFailureReport tests/test_packaging_control_plane.py::TestCliSmokeGate
```

Expected: all selected tests PASS.

- [ ] **Step 2: Run the required architecture, full, release, and lint gates**

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run python scripts/test-suite.py release
uv run --locked python scripts/lint.py
```

Expected: every command exits 0 with no failed tests or lint findings.

- [ ] **Step 3: Build, inspect, and isolate-smoke all six distributions**

```powershell
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: exactly six distributions build, the checker accepts the wheel set,
and all isolated smoke scenarios pass under Python 3.8.

- [ ] **Step 4: Run the product release pipeline**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release
```

Expected: the release pipeline exits 0 and its staged CLI gate passes under the
validator-owned `cp1252` environment. This produces repository-side release
evidence only and does not satisfy clean-machine Windows 7 acceptance.

- [ ] **Step 5: Verify final repository state**

```powershell
git status --short
git log -5 --oneline
```

Expected: the worktree is clean and the four implementation/documentation
commits are present above the design and plan commits.
