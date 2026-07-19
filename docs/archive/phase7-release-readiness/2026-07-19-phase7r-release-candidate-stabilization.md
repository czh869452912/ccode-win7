# Phase 7R Release Candidate Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Phase 7 offline release pipeline produce a diagnosable, isolated, and reproducible local `TARGET_READY` candidate without changing Agent Core or GUI UX architecture.

**Architecture:** Keep `validate-gui-smoke.py` as the GUI smoke orchestrator and keep launcher diagnostics file-based and outside Agent Core/session state. Keep packaging orchestration in `scripts/package.ps1` and `scripts/package-lib.ps1`, with production-derived per-run configs for reproducibility and fixture-derived temporary configs for tests. Promote `TARGET_READY` only after both release runs and their normalized artifact comparison pass.

**Tech Stack:** Python 3.8 stdlib, PowerShell 5-compatible scripts, pytest/unittest, existing `uv` workspace, React/Vite static asset build, bundled WebView2/Clang validation.

---

## File Map

### GUI smoke and launcher

- Modify: `scripts/validate-gui-smoke.py` - process observation, readiness checks, structured JSON reports, and failure categories.
- Modify: `src/embedagent/frontend/gui/launcher.py` - optional startup-stage report; no runtime policy changes.
- Modify: `tests/test_gui_smoke_contract.py` - static contract assertions for new CLI/report markers.
- Create: `tests/test_gui_smoke_runtime.py` - pure helper tests for process exit, readiness, failure serialization, and report redaction.
- Modify: `tests/test_gui_runtime.py` - launcher startup-report behavior using an injected temporary path.

### Packaging provenance and isolation

- Modify: `scripts/package.ps1` - pass explicit execution/provenance metadata through the package context without changing the normal command set.
- Modify: `scripts/package-lib.ps1` - context metadata, report identity, atomic report writes, and release eligibility checks.
- Modify: `scripts/package.config.json` - declare `config_origin=production` metadata.
- Modify: `tests/fixtures/package/mock-config.json` - declare `config_origin=fixture` metadata.
- Modify: `tests/test_packaging_control_plane.py` - redirect every fixture path to a temporary root and assert production report isolation.
- Modify: `tests/test_phase7_verification.py` - assert provenance and eligibility markers.

### Reproducibility

- Create: `scripts/compare-release-artifacts.py` - stdlib-only comparison of two release reports, identities, wheel hashes, and normalized bundle trees.
- Modify: `scripts/package.ps1` - add the explicit `-Reproducible` release switch and route it to the two-run orchestrator.
- Modify: `scripts/package-lib.ps1` - create production-derived isolated configs, invoke two child release runs, and aggregate the comparison result.
- Create: `tests/test_release_reproducibility.py` - unit tests for canonical tree hashing, dynamic-field normalization, mismatch reporting, and release-state promotion.
- Modify: `tests/fixtures/packaging/reproducibility-config.json` - declare the two isolated output roots and fields excluded from content comparison.

### Documentation and closeout

- Modify: `docs/implementation-roadmap.md` - record Phase 7R as the active release-candidate stabilization slice and retain Phase 7B/Phase 8 as open.
- Modify: `docs/development-tracker.md` - replace stale GUI smoke wording with current gate semantics and 7R milestones.
- Modify: `docs/modules/packaging-and-deployment.md` - document report provenance, temporary test configs, `-Reproducible`, and `TARGET_READY` requirements.
- Modify: `docs/guides/win7-release-runbook.md` - distinguish local 7R evidence from target-machine `ACCEPTED` evidence.

## Task 1: Make GUI Smoke Failures Diagnosable

**Files:** `scripts/validate-gui-smoke.py`, `tests/test_gui_smoke_contract.py`, `tests/test_gui_smoke_runtime.py`

- [ ] **Step 1: Add pure diagnostic helpers and a typed smoke failure.**

Add `SmokeFailure(RuntimeError)` carrying `category`, `stage`, and a JSON-safe `details` mapping. Add these helpers:

```python
def _tail_text(path, max_lines=40):
    """Return at most max_lines from a diagnostic text file."""

def _failure_payload(failure, process, stdout_path, stderr_path, checks):
    """Build the credential-free failure payload emitted by the smoke runner."""

def _process_exit_details(process):
    """Return None while running, otherwise return the integer exit code."""
```

The payload contains `ok=false`, `failure.category`, `failure.stage`, `failure.details`, `process.returncode`, stdout/stderr paths and tails, and completed check names. It must not contain credentials, prompts, source files, or raw tool output.

- [ ] **Step 2: Replace blind HTTP waiting with process-aware readiness.**

Change `_wait_for_http` to accept `process`, `stage`, and `checks`. Poll every 100 ms, short-circuit on child exit with `SmokeFailure("launcher_exit", stage, {"returncode": code})`, and classify a deadline as `SmokeFailure("http_timeout", stage, {"url": url, "timeout_sec": timeout})`.

Add `_wait_for_app_bootstrap(gui_port, timeout, process, checks)` that performs a read-only GET to `/api/app/bootstrap` and raises `SmokeFailure("app_bootstrap_failure", "app_bootstrap", ...)` for HTTP or transport errors.

- [ ] **Step 3: Add structured report output and controlled cleanup.**

Extend the parser with:

```python
parser.add_argument("--json-report", default="", help="Write a structured smoke report")
parser.add_argument("--diagnostic-dir", default="", help="Directory for launcher stdout/stderr")
parser.add_argument("--startup-timeout", type=float, default=20.0)
```

Redirect the child to `launcher.stdout.log` and `launcher.stderr.log`. Wrap the exercise flow in `try/except SmokeFailure`, map unknown errors to the current stage, and always terminate and wait in `finally`. Write a success or failure payload to `--json-report` and return `0` only on success.

- [ ] **Step 4: Add runtime tests before implementation verification.**

Import the script through `importlib.util.spec_from_file_location`. Test process exit, HTTP timeout, bootstrap HTTP error, JSON report serialization, and sensitive-key redaction with a temporary directory and fake process. Update `tests/test_gui_smoke_contract.py` to assert `--json-report`, `--diagnostic-dir`, `--startup-timeout`, `/api/app/bootstrap`, and all eight failure category strings.

- [ ] **Step 5: Run focused tests and commit.**

Run:

```powershell
uv run pytest tests/test_gui_smoke_runtime.py tests/test_gui_smoke_contract.py -v
```

Expected: all tests pass. Commit:

```powershell
git add scripts/validate-gui-smoke.py tests/test_gui_smoke_runtime.py tests/test_gui_smoke_contract.py
git commit -m "test: make GUI smoke failures diagnosable"
```

## Task 2: Emit Optional Launcher Startup Diagnostics

**Files:** `src/embedagent/frontend/gui/launcher.py`, `tests/test_gui_runtime.py`

- [ ] **Step 1: Add the startup-report writer and event list.**

Add `_write_startup_report(path, events, status="running", error=None)` that writes UTF-8 JSON through a sibling `.tmp` file and replacement. The payload has `schema_version`, `status`, `events`, and an optional exception type/message. Do not include runtime config values, API keys, prompts, source content, or tool output.

- [ ] **Step 2: Thread `startup_report` through the launcher API and CLI.**

Add `startup_report: str = ""` to `launch_gui` and `--startup-report` to the parser. Emit `dependencies_checked`, `backend_constructed`, `server_thread_started`, `headless_started` or `window_created`, `shutdown_started`, and `shutdown_finished`. Write `status=ready` before the headless loop or `webview.start`, and `status=failed` in the exception path. Preserve WebView2 selection and renderer reporting.

- [ ] **Step 3: Test without opening a window.**

Test `_write_startup_report` with a temporary path for atomic JSON output, event ordering, failed status metadata, and sensitive-key absence. Keep platform-specific window tests unchanged.

- [ ] **Step 4: Run launcher tests and commit.**

Run:

```powershell
uv run pytest tests/test_gui_runtime.py tests/test_gui_launcher_app_mode.py -v
```

Expected: all tests pass. Commit:

```powershell
git add src/embedagent/frontend/gui/launcher.py tests/test_gui_runtime.py
git commit -m "feat: add GUI launcher startup diagnostics"
```

## Task 3: Isolate Packaging Fixtures And Add Provenance

**Files:** `scripts/package.ps1`, `scripts/package-lib.ps1`, `scripts/package.config.json`, `tests/fixtures/package/mock-config.json`, `tests/test_packaging_control_plane.py`, `tests/test_phase7_verification.py`

- [ ] **Step 1: Declare config origin.**

Add a top-level `metadata` object with `config_origin=production` to `scripts/package.config.json` and `config_origin=fixture` to the mock config. `Read-PackageConfig` must reject any other value before a package command runs.

- [ ] **Step 2: Carry run identity through context and reports.**

Add `run_id`, `execution_kind`, `config_origin`, resolved `reports_root`, resolved artifact root, config path, and source revision to `New-PackageContext`/`New-PackageReport`. Use `git -C <project_root> rev-parse HEAD`; release contexts must fail when it cannot resolve, while fixture contexts may use `unknown`.

Update `New-PackageReport` to receive the context and preserve all existing stage timing fields.

- [ ] **Step 3: Make report writes atomic and gate `TARGET_READY`.**

Write timestamp and latest reports to `.tmp.<run_id>` siblings and replace them on the same volume. Delete temporary files in `finally`. Promote `READY` to `TARGET_READY` only when:

```powershell
$Context.execution_kind -eq 'release'
$Context.config_origin -eq 'production'
$Context.profile -eq 'release'
$identityConfigured
```

Fixture/dev behavior remains unchanged; a production release missing these fields becomes `NOT_READY` with a blocking issue.

- [ ] **Step 4: Redirect every packaging fixture output.**

Add `_temporary_mock_config(tmp_path)` to `tests/test_packaging_control_plane.py`. Deep-copy the fixture JSON, rewrite `reports_root`, `build_root`, `site_packages_export_root`, `gui_launcher_build_root`, and `dist_bundle_root` below `tmp_path`, write the config there, and use it for every mock invocation. Snapshot the real `build/offline-reports/latest.json` bytes/mtime when present and assert unchanged after the test.

- [ ] **Step 5: Add regression tests and commit.**

Test unknown-origin rejection, complete JSON after forced failure, fixture report isolation, and fixture rejection for `TARGET_READY`. Run:

```powershell
uv run pytest tests/test_packaging_control_plane.py tests/test_phase7_verification.py -v
```

Expected: all tests pass and the production report is unchanged. Commit:

```powershell
git add scripts/package.ps1 scripts/package-lib.ps1 scripts/package.config.json tests/fixtures/package/mock-config.json tests/test_packaging_control_plane.py tests/test_phase7_verification.py
git commit -m "fix: isolate packaging reports and provenance"
```

## Task 4: Add Two-Run Reproducibility Gate

**Files:** `scripts/compare-release-artifacts.py`, `scripts/package.ps1`, `scripts/package-lib.ps1`, `tests/test_release_reproducibility.py`, `tests/fixtures/packaging/reproducibility-config.json`

- [ ] **Step 1: Implement canonical artifact comparison.**

Define `canonical_bundle_records(root)` and `compare_release_runs(first_report, second_report, first_root, second_root)` in the new stdlib script. Reuse `release_identity.py` hashing/canonical JSON. Compare source revision, profile, exact six wheel filenames/hashes, GUI static hash, asset-manifest hash, runtime-contract hash, identity content, and normalized bundle records. For `manifests/bundle-manifest.json`, normalize only `generated_at`, `project_root`, `build_root`, `bundle_root`, and absolute asset path fields. Exclude only the generated evidence paths listed in the reproducibility fixture and report that exclusion list. Never compare absolute paths, durations, timestamps, or logs.

The CLI accepts `--first-report`, `--second-report`, `--first-root`, `--second-root`, and `--json-report`; it returns `0` only for a full match and emits `{"ok": false, "mismatches": [...]}` for differences.

- [ ] **Step 2: Add focused comparison tests.**

Create identical temporary bundle trees with differing generated fields and assert `ok=true`; mutate one stable file and assert the mismatch path. Add wheel-hash, source-revision, missing-report, and sensitive-output tests.

- [ ] **Step 3: Add `package.ps1 -Reproducible`.**

Add a switch and context field. For `release -Reproducible`, clone the production config twice, redirect build/reports/export/launcher/artifact/identity/evidence roots under `<reproducibility-root>\run-a` and `run-b`, invoke child `package.ps1 release -Reproducible:$false -Json`, require both child reports to be release-eligible, call `compare-release-artifacts.py`, and add an `artifact_reproducibility` stage with child report paths, normalized hashes, and mismatch paths. Write outer `TARGET_READY` only when both children and comparison pass; retain `publishable=false` and `PENDING_WIN7`.

- [ ] **Step 4: Test package-level reproducibility.**

Extend `tests/fixtures/packaging/reproducibility-config.json` with concrete output roots, generated fields, and excluded paths. Add a mock-stage orchestration test for matching runs and a mutation test expecting `NOT_READY` plus the mismatch path.

- [ ] **Step 5: Run tests and commit.**

Run:

```powershell
uv run pytest tests/test_release_reproducibility.py tests/test_packaging_control_plane.py tests/test_phase7_verification.py -v
```

Expected: all tests pass. Commit:

```powershell
git add scripts/compare-release-artifacts.py scripts/package.ps1 scripts/package-lib.ps1 tests/test_release_reproducibility.py tests/fixtures/packaging/reproducibility-config.json
git commit -m "feat: gate release candidates with two-run reproducibility"
```

## Task 5: Synchronize Closeout Documentation And Run The Gate

**Files:** `docs/implementation-roadmap.md`, `docs/development-tracker.md`, `docs/modules/packaging-and-deployment.md`, `docs/guides/win7-release-runbook.md`

- [ ] **Step 1: Update active status.**

Record Phase 7R as active until reproducibility passes. Replace stale “GUI smoke passed” wording with the current source/bundle timeout and diagnostic-report contract. Keep Win7 evidence and Phase 8 real C/C++ validation open.

- [ ] **Step 2: Document commands and state semantics.**

Document:

```powershell
uv run python scripts/validate-gui-smoke.py --json-report build/offline-reports/gui-smoke-source.json
uv run python scripts/validate-gui-smoke.py --bundle-root build/offline-dist/embedagent-win7-x64 --require-fixed-webview2 --json-report build/offline-reports/gui-smoke-bundle.json
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Reproducible -Json
```

State that only a production-derived `TARGET_READY` report is a local candidate and `ACCEPTED` requires the copied Win7 evidence report and `validate-release-evidence.py`.

- [ ] **Step 3: Run the complete verification gate.**

Run from the repository root:

```powershell
uv run pytest tests/test_gui_smoke_runtime.py tests/test_gui_smoke_contract.py tests/test_packaging_control_plane.py tests/test_release_identity.py tests/test_release_evidence.py tests/test_release_reproducibility.py -v
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Run from `src/embedagent/frontend/gui/webapp`:

```powershell
npm test
npm run build
```

Run two real releases with cached offline inputs and retain `TARGET_READY` only when every gate passes; otherwise retain `NOT_READY` with the diagnostic report path.

- [ ] **Step 4: Commit closeout evidence.**

Record source revision, report paths, identity hash, normalized bundle hashes, and remaining blockers in the tracker and runbook. Commit:

```powershell
git add docs/implementation-roadmap.md docs/development-tracker.md docs/modules/packaging-and-deployment.md docs/guides/win7-release-runbook.md
git commit -m "docs: close Phase 7R release candidate stabilization"
```

## Final Self-Review Checklist

- [ ] GUI source and bundle smoke failures produce categorized JSON with child logs.
- [ ] Launcher diagnostics contain only safe startup metadata.
- [ ] Fixture tests never write to production build/report roots.
- [ ] Release reports carry run identity, source revision, config origin, and execution kind.
- [ ] Atomic report writes leave complete JSON after failure.
- [ ] Two production-derived release runs compare stable content and normalize only documented generated fields.
- [ ] `TARGET_READY` is impossible for fixture-origin or mismatched reports.
- [ ] No code changes touch Agent Core, workflow ownership, T3 renderer state, or WebView2 selection.
- [ ] Win7 `ACCEPTED` remains unclaimed without Windows 7 SP1 x64 evidence.
