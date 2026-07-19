# Phase 7 Offline Release Design

Date: 2026-07-19
Status: repository-side 7A gates implemented; 7B external acceptance pending

## Goal

Make the six-distribution offline release path reproducible from the current
Git revision and produce an auditable Win7/WebView2 acceptance kit without
claiming target-machine validation that has not occurred.

Phase 7 is split into two gates:

- **7A / TARGET_READY:** repository-side release engineering is complete and a
  release candidate plus target-machine evidence kit is ready.
- **7B / ACCEPTED:** a real Windows 7 SP1 x64 machine runs the kit and its
  hash-bound report matches the release candidate identity.

The current environment can implement and verify 7A. Because no real Win7
machine is currently available, Phase 7 must remain open after 7A until 7B is
performed.

## Context And Findings

The repository already contains the main control-plane pieces:

- `scripts/package.ps1` with `doctor`, `deps`, `assemble`, `verify`, and
  `release` commands;
- six-distribution build, wheel checker, and Python 3.8 isolated smoke scripts;
- `prepare-offline.ps1`, `build-offline-bundle.ps1`, and
  `validate-offline-bundle.ps1`;
- contract-backed bundle dependency, GUI, and bundle-local C smoke validators;
- `docs/guides/win7-gui-validation.md` and
  `docs/guides/win7-preflight-checklist.md`.

The audit found two release risks:

1. `dist/` currently contains an old five-wheel set and no current
   `embedagent-workflow-cpp` wheel. It must never be reused as a Phase 7
   release input.
2. `package.ps1 doctor -Profile release` currently reports `READY` after
   checking scripts and npm even when a current six-wheel artifact and target
   evidence do not exist. Doctor must become a strict preflight for the
   selected release profile.

The old `build/offline-dist/` material is historical input, not Phase 7
evidence. A new release candidate must be tied to the current source revision
and regenerated through the official entry point.

## Scope

### In scope

- deterministic release identity and evidence schemas;
- strict release-profile doctor checks;
- clean six-wheel build, exact DAG check, and Python 3.8 isolated smoke;
- wheel-only bundle assembly and stale-artifact rejection;
- static, dependency, headless GUI, bundle-local C smoke, zip, and hash gates;
- two-run reproducibility comparison for release metadata and declared files;
- a target-machine evidence kit and offline acceptance-report validator;
- packaging, Win7 checklist, roadmap, tracker, and release evidence docs.

### Out of scope

- real Win7 execution in the current environment;
- real customer C/C++ project validation, which belongs to Phase 8;
- new Agent Core, workflow, GUI UX, provider, or enterprise functionality;
- network downloads during runtime or mandatory online release services;
- accepting a local Windows 10/11 windowed smoke as Win7 proof.

## Architecture

The release control flow is:

```text
doctor
  -> deps: clean six wheels + exact checker + Python 3.8 smoke
  -> assemble: wheel-only installation + bundle staging
  -> verify: static/dependency/headless/C smoke + zip checks
  -> evidence: release identity + reports + target-machine kit
  -> TARGET_READY
  -> [external Win7 execution + matching report]
  -> ACCEPTED
```

The release identity is a credential-free JSON record containing:

- source Git commit and repository version;
- exact six distribution names and versions;
- SHA-256 values for six wheels;
- GUI static asset manifest/hash;
- offline asset manifest revision and resolved asset hashes;
- runtime contract revision/hash;
- bundle directory and zip hashes;
- build profile and tool/runtime versions.

The identity is written once for a release candidate and is referenced by all
reports. A report with a different identity is a failure, not a warning.

## Component Boundaries

### Release identity service

Owns canonical JSON serialization, stable ordering, hash calculation, and
identity comparison. It must not execute tools or infer acceptance.

### Strict doctor

Owns profile preflight. For `release`, it verifies the required local assets,
Python 3.8 runtime, npm, native launcher compiler, LLVM/Clang bundle, WebView2
109 asset, available output space, all configured script paths, and the absence
of an unsafe/reparse-point wheelhouse. It reports machine-readable blocking
codes and does not download assets unless explicitly authorized.

### Distribution pipeline

Uses `scripts/build-python-distributions.py`,
`scripts/check-python-distributions.py`, `scripts/smoke-python-distributions.py`,
and `scripts/export-dependencies.py`. The pipeline owns no GUI or workflow
policy; it only produces and verifies project wheels and controlled third-party
runtime inputs.

### Bundle assembler

Uses wheel-installed project distributions as the source of runtime Python
packages. Product code is staged under `app/embedagent`; Core, Protocol, Host,
Composition, and C/C++ workflow packages remain under `runtime/site-packages`.
The assembler rejects editable links, duplicate product packages, source-tree
fallbacks, undeclared files, and stale wheel names.

### Verification runner

Runs the existing static/dependency/runtime contract checks and the bundle-local
headless GUI and C smoke gates. It records each command, exit code, report path,
tool version, and result hash. It does not convert a local windowed run into a
Win7 acceptance result.

### Target evidence kit

Contains the release identity, expected bundle/zip hashes, Win7 preflight
checklist, command wrappers, environment collection instructions, and a JSON
report schema. It must not contain credentials, prompts, source files, raw tool
outputs, or user session state.

### Acceptance validator

Runs offline against a target report. It verifies schema, release identity,
bundle hash, Windows 7 SP1 x64 markers, WebView2 major 109, `edgechromium`,
`runtime_source == "bundle"`, required GUI/C smoke fields, and zero reported
blocking errors. It emits `ACCEPTED` only when every field matches.

## State And Failure Semantics

The release status is one of:

- `NOT_READY`: preflight, dependency, assembly, or verification failure;
- `TARGET_READY`: all repository-side gates pass and the target kit is complete;
- `ACCEPTED`: a matching real Win7 report passes the acceptance validator.

Missing target hardware, missing target report, mismatched hashes, missing
WebView2 109, non-bundle tool execution, system PATH fallback, stale wheels,
editable links, or incomplete reports all keep the status below `ACCEPTED`.
A provisional zip may be generated during assembly so verification can inspect
it, but a failed required stage must prevent that zip from being promoted as a
final release artifact. Existing artifacts are not silently promoted or
overwritten as a new release candidate.

## Milestones

Each milestone produces a focused commit and a runnable check:

1. Release identity and target evidence schemas with canonical hash tests.
2. Strict release doctor and stale-input/reparse-point rejection tests.
3. Clean six-wheel build, exact checker, isolated smoke, and report capture.
4. Wheel-only bundle assembly with duplicate/editable/source-fallback tests.
5. Repository verification, zip integrity, and two-run reproducibility tests.
6. Target evidence kit, acceptance validator, and negative/mismatch fixtures.
7. Packaging documentation, roadmap/tracker updates, target-ready closeout,
   and explicit Phase 7B handoff instructions.

## Verification Matrix

The 7A gate must run:

```powershell
uv run pytest tests/test_packaging_control_plane.py tests/test_python_distribution_contract.py tests/test_python_distribution_smoke.py -v
uv run python scripts/build-python-distributions.py --dist-dir <clean-dist>
uv run python scripts/check-python-distributions.py --dist-dir <clean-dist>
uv run python scripts/smoke-python-distributions.py --dist-dir <clean-dist> --python .venv/Scripts/python.exe
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor -Profile release -Json
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Json
```

The implementation must add focused tests for strict doctor failure codes,
identity mismatch, stale five-wheel input, source fallback, duplicate product
package, zip hash mismatch, incomplete target report, and successful
`TARGET_READY`/`ACCEPTED` transitions. The full non-GUI suite, architecture
guards, GUI tests, GUI production build, and lint remain the pre-merge gate.

## Documentation And Evidence

Phase 7A must update:

- `docs/modules/packaging-and-deployment.md`;
- `docs/guides/win7-preflight-checklist.md`;
- `docs/guides/win7-gui-validation.md`;
- `docs/development-tracker.md` and `docs/implementation-roadmap.md`;
- a target-ready closeout record under `docs/superpowers/plans/`.

Documentation must say clearly that local gates prove `TARGET_READY` only.
Phase 7 cannot be marked `ACCEPTED` until the future Win7 report is validated;
Phase 8 remains the separate real C/C++ project program.
