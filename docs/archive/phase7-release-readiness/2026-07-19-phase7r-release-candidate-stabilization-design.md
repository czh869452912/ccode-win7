# Phase 7R Release Candidate Stabilization Design

Date: 2026-07-19

Status: Approved design; implementation not started.

## Goal

Stabilize the Phase 7 release control plane so the repository can produce a
trustworthy local `TARGET_READY` candidate. Phase 7R closes the current GUI
smoke and evidence-integrity blockers before real Windows 7 acceptance and
Phase 8 real C/C++ project validation.

## Scope And Non-Goals

Phase 7R is limited to:

- GUI launcher startup diagnostics and smoke readiness;
- GUI smoke subprocess observation and failure classification;
- packaging report isolation, provenance, and atomic writes;
- two-build reproducibility and `TARGET_READY` aggregation;
- focused tests and release documentation.

It does not reopen Agent Core, workflow-package, protocol, T3 renderer, or GUI
UX architecture. It does not add runtime dependencies, alter WebView2 runtime
selection, write smoke state into Agent Core/session transcript/reducers, or
claim Windows 7 `ACCEPTED` evidence.

## Release State Model

The only valid progression is:

```text
NOT_READY -> TARGET_READY -> ACCEPTED
```

- `NOT_READY`: any repository, bundle, report, or GUI smoke gate fails.
- `TARGET_READY`: local source and bundle GUI smoke, six-wheel packaging,
  offline dependency validation, C smoke, static assets, report integrity, and
  reproducibility all pass.
- `ACCEPTED`: produced only by copied Windows 7 SP1 x64 evidence validated by
  `validate-release-evidence.py`; Phase 7R cannot synthesize it.

## Architecture And Data Flow

The release flow is:

```text
launch GUI subprocess
  -> capture startup diagnostics and process state
  -> wait for HTTP and app bootstrap readiness
  -> run WebSocket/session/permission/tool/review smoke
  -> verify renderer and bundled runtime
  -> aggregate release gates
  -> emit TARGET_READY or NOT_READY
```

`validate-gui-smoke.py` remains the smoke orchestrator. Launcher diagnostics
remain optional and file-based; they are not Agent Core or transcript state.
Packaging remains owned by `package.ps1` and `package-lib.ps1`, with the
existing production paths preserved for real releases.

## GUI Smoke Contract

The smoke runner will:

1. create an isolated diagnostic directory and fake model server;
2. start the source or bundle launcher;
3. capture stdout/stderr and monitor process exit;
4. wait for the root HTTP service;
5. request read-only `/api/app/bootstrap` readiness;
6. execute the existing WebSocket, session, permission, tool, `/review`, and
   task projection checks;
7. validate the renderer report and bundle WebView2 runtime;
8. write a structured success or failure report and clean up the process.

The runner must short-circuit when the child exits and must not rely on blind
timeout extension or automatic retries. Failure categories are:

- `launcher_missing`
- `launcher_exit`
- `http_timeout`
- `app_bootstrap_failure`
- `protocol_failure`
- `model_failure`
- `renderer_failure`
- `cleanup_failure`

Failure reports include the launcher type, command summary, paths, ports,
failed stage, exit code, stdout/stderr references and tail, renderer report,
completed checks, and cleanup result. They must not include credentials,
prompts, source files, or raw tool output.

The launcher may accept an optional startup-report path and record dependency
check, backend construction, server-thread start, headless/windowed branch,
and shutdown stages. This is diagnostic metadata only and does not change
runtime behavior.

## Report Isolation And Provenance

Packaging tests must use a temporary copy of the mock configuration with all
writable paths redirected to a temporary root:

- `reports_root`
- `build_root`
- `site_packages_export_root`
- `gui_launcher_build_root`
- `dist_bundle_root`

The production `scripts/package.config.json` paths remain unchanged. Mock tests
must not write to `build/offline-reports`, `build/offline-cache`, or the real
offline distribution directory.

Control-plane reports gain safe provenance fields:

- `run_id`
- `profile`
- `source_revision`
- `config_path`
- `reports_root`
- `artifact_root`
- `execution_kind` (`release` or `test`)

Reports are written to a temporary file and atomically replaced. A failed run
still leaves a complete JSON report. Only a release report from the production
configuration can be considered for `TARGET_READY`; test reports cannot be
promoted by aggregation.

## Reproducibility And Target-Ready Gate

Two independent release builds use the same source revision, lock file, and
offline inputs but separate cache, staging, artifact, report, and zip roots.
The gate compares:

- source revision and six wheel names/hashes;
- GUI static, asset-manifest, and runtime-contract hashes;
- release identity hash;
- normalized unpacked bundle tree hash.

The normalized tree hash uses stable path ordering and content hashes and
excludes only explicitly documented diagnostic fields such as absolute paths,
run timestamps, and runtime logs. The original zip hash remains evidence, but
normalized unpacked content is the reproducibility authority.

Both builds must pass:

- complete offline bundle validation;
- dependency checking;
- bundle-local C smoke with no system fallback;
- source-tree and bundle GUI smoke;
- GUI tests/build;
- architecture and focused Python gates.

Any mismatch, unresolved release warning, or failed gate leaves the state at
`NOT_READY`. A successful local report has `final_status=TARGET_READY`,
`artifact_status=verified`, and `publishable=false` until external Win7
evidence exists.

## Milestones

### 7R-1: GUI Smoke Diagnostics

Update the smoke runner and launcher diagnostics, then add regression coverage
for child exit, HTTP readiness, bootstrap readiness, categorized failures, and
cleanup.

### 7R-2: Test Report Isolation

Redirect packaging fixture writes to temporary roots, add provenance and atomic
report tests, and prove the repository's production `latest.json` is unchanged
by mock runs.

### 7R-3: Two-Build Reproducibility

Run isolated real releases, compare identity and normalized bundle hashes, and
make the release aggregator refuse inconsistent or test-origin reports.

### 7R-4: Closeout

Synchronize the roadmap, development tracker, packaging/deployment module, and
release runbook. Record `TARGET_READY` only with current evidence; retain the
Win7 `ACCEPTED` gap and Phase 8 C/C++ validation as explicit follow-up work.

## Verification

Focused verification:

```powershell
uv run pytest tests/test_gui_smoke_contract.py tests/test_packaging_control_plane.py tests/test_release_identity.py tests/test_release_evidence.py -v
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Frontend verification remains:

```powershell
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Finally run two real `package.ps1 release` executions with isolated outputs and
inspect the release reports for `TARGET_READY`.

## Expected Deliverables

- diagnostic GUI smoke reports for source and bundle paths;
- isolated, provenance-bound packaging reports;
- two-build reproducibility evidence;
- a current `TARGET_READY` or accurately retained `NOT_READY` release report;
- synchronized active release documentation;
- no Windows 7 `ACCEPTED` claim without target-machine evidence.
