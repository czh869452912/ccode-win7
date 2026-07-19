# Phase 7 Offline Release Gates Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

Goal: Build a reproducible six-distribution offline release candidate and a hash-bound Win7/WebView2 acceptance kit, while keeping Phase 7 open until a real Windows 7 report is validated.

Architecture: Keep packaging orchestration in scripts/package.ps1 and scripts/package-lib.ps1. Put canonical release identity and target-report validation in small stdlib-only Python modules so PowerShell, tests, and future target tooling consume one JSON contract. The release state is NOT_READY -> TARGET_READY -> ACCEPTED; local execution can reach only TARGET_READY.

Tech Stack: PowerShell 5-compatible scripts, Python 3.8 stdlib, existing uv workspace wheel builders/checkers, JSON reports, SHA-256 hashes, existing GUI/C smoke validators.

---

## File Map

- Create: scripts/release_identity.py — canonical JSON, file/tree hashing, release identity construction, and identity comparison.
- Create: scripts/validate-release-evidence.py — offline target-report validator with NOT_READY, TARGET_READY, and ACCEPTED results.
- Create: tests/test_release_identity.py — deterministic identity and hash tests.
- Create: tests/test_release_evidence.py — target-report schema, mismatch, and acceptance tests.
- Modify: scripts/package.config.json — release identity/evidence paths, required local toolchain checks, and minimum free-space policy.
- Modify: scripts/package-lib.ps1 — strict doctor checks, release identity/evidence orchestration, status projection, and provisional-artifact handling.
- Modify: scripts/prepare-offline.ps1 — enforce wheel-installed source rules and record the six-wheel set in the bundle manifest.
- Modify: scripts/build-offline-bundle.ps1 — carry identity/evidence files into the final bundle and refuse an unverified wheel set.
- Modify: scripts/validate-offline-bundle.ps1 — validate release identity, six wheels, and provisional/final artifact status.
- Modify: tests/test_packaging_control_plane.py — strict doctor and bundle assembly regression coverage.
- Modify: tests/test_python_distribution_smoke.py — clean release wheelhouse and stale-input coverage.
- Modify: docs/modules/packaging-and-deployment.md — 7A/7B state and release evidence contract.
- Modify: docs/guides/win7-preflight-checklist.md — target-ready kit and report handoff.
- Modify: docs/guides/win7-gui-validation.md — report fields and acceptance validator command.
- Modify: docs/implementation-roadmap.md — Phase 7A status and explicit Phase 7B gap.
- Modify: docs/development-tracker.md — current phase, milestone rows, and target-ready evidence.
- Create: docs/superpowers/plans/2026-07-19-phase7-target-ready-closeout.md — 7A closeout record, without claiming Win7 acceptance.

## Task 1: Canonical Release Identity And Evidence Contracts

Files:
- Create: scripts/release_identity.py
- Create: tests/test_release_identity.py
- Create: scripts/validate-release-evidence.py
- Create: tests/test_release_evidence.py

- [ ] Step 1: Write failing identity tests.

Add tests for canonical_json(value), sha256_file(path), sha256_tree(root),
build_release_identity, and compare_release_identity. Assert sorted keys, compact
JSON, UTF-8 encoding, stable path ordering, exclusion of timestamps, and
different hashes after file mutation.

Run:

    uv run pytest tests/test_release_identity.py -v

Expected: collection fails because scripts/release_identity.py does not exist.

- [ ] Step 2: Implement the pure identity module.

Implement Python 3.8-compatible canonical_json, sha256_file, sha256_tree,
build_release_identity, and compare_release_identity functions. The public
function arguments are source_revision, version, profile, wheels,
gui_static_root, asset_manifest_path, runtime_contract_path, bundle_root, and
zip_path.

build_release_identity returns JSON-safe data with schema_version 1, the exact
six normalized distribution names, wheel hashes, GUI tree hash, asset and
runtime-contract hashes, bundle/zip hashes when present, and tool/profile
metadata. Reject duplicate wheel names, missing files, path escapes, and
secret-looking keys. Never include prompt text, source contents, raw tool output,
API keys, or timestamps in the identity payload.

- [ ] Step 3: Write failing target-report tests.

Use a fixture identity and assert validate_report(identity, report) returns
NOT_READY for missing reports, wrong identity hash, Windows 10, wrong WebView2
major, non-edgechromium, non-bundle runtime, failed C smoke, and non-empty
blocking errors. Assert ACCEPTED only for a complete report containing release
identity hash, Windows 7 SP1 x64 machine metadata, edgechromium, bundle runtime,
WebView2 109, successful bundle C smoke, disabled system-tool fallback, and
an empty blocking_errors list.

- [ ] Step 4: Implement the validator CLI.

Implement scripts/validate-release-evidence.py with this command:

    python scripts/validate-release-evidence.py --identity manifests/release-identity.json --report manifests/win7-evidence.json --json-report manifests/acceptance-report.json

Exit 0 only for ACCEPTED and exit 1 for NOT_READY. Emit a credential-free
report and preserve a stable failing field/code for every negative fixture.
Use only the standard library.

- [ ] Step 5: Run tests and commit.

    uv run pytest tests/test_release_identity.py tests/test_release_evidence.py -v
    uv run --locked python scripts/lint.py

Expected: all new tests pass and lint reports no changes.

    git add scripts/release_identity.py scripts/validate-release-evidence.py tests/test_release_identity.py tests/test_release_evidence.py
    git commit -m "feat: add release identity and Win7 evidence contracts"

## Task 2: Strict Release Doctor And Configuration

Files:
- Modify: scripts/package.config.json
- Modify: scripts/package-lib.ps1
- Modify: tests/test_packaging_control_plane.py

- [ ] Step 1: Add failing doctor tests.

Add isolated temporary project contexts asserting these machine-readable codes:
python_version_invalid, required_asset_cache_missing, llvm_bundle_missing,
webview2_asset_missing, insufficient_free_space, and unsafe_wheelhouse.
Also assert dev remains warning-tolerant while release marks the same missing
required input as blocking.

    uv run pytest tests/test_packaging_control_plane.py -k "doctor or config" -v

Expected: the new tests fail before strict checks and config fields exist.

- [ ] Step 2: Extend package configuration.

Add paths.release_identity as manifests/release-identity.json and
paths.release_evidence_root as manifests/evidence. Under profiles.release add
minimum_free_bytes as 8589934592 and required_project_distributions containing
these six values in order: embedagent-core, embedagent-protocol, embedagent-host,
embedagent-composition, embedagent-workflow-cpp, embedagent.

Keep the asset manifest and runtime contract as the only external-tool source of
truth.

- [ ] Step 3: Implement strict doctor checks.

In Invoke-PackageDoctor retain current config/script/npm checks and add:
Python 3.8 version validation; required asset cache validation when downloads
are disabled; LLVM clang.exe and runtime-contract child executable checks;
Fixed Version WebView2 109 cache validation; normal-directory/reparse-point
and minimum-free-space checks; all six workspace pyproject.toml checks; and
safe wheelhouse-entry checks.

Store each result under doctor_checks with code, ok, blocking, and a
credential-free path/value. Doctor is a preflight status; final acceptance is
computed only after identity and evidence exist.

- [ ] Step 4: Run tests and commit.

    uv run pytest tests/test_packaging_control_plane.py -k "doctor or config" -v
    uv run --locked python scripts/lint.py

Expected: doctor tests pass and lint passes.

    git add scripts/package.config.json scripts/package-lib.ps1 tests/test_packaging_control_plane.py
    git commit -m "feat: enforce strict offline release preflight"

## Task 3: Clean Six-Wheel Dependency Stage

Files:
- Modify: scripts/package-lib.ps1
- Modify: scripts/export-dependencies.py
- Modify: tests/test_python_distribution_smoke.py
- Modify: tests/test_packaging_control_plane.py

- [ ] Step 1: Add stale-input and clean-output tests.

Assert that release dependency export removes only generated entries below
build/offline-cache/site-packages-export; rejects a reparse-point wheelhouse
and unexpected non-wheel entries; produces exactly six wheel names including
embedagent_workflow_cpp; refuses a valid-looking five-wheel directory; and
records checker and smoke report paths.

    uv run pytest tests/test_python_distribution_smoke.py tests/test_packaging_control_plane.py -k "wheel or dependency or export" -v

Expected: new stale-input assertions fail before orchestration changes.

- [ ] Step 2: Make the dependency stage use one clean release wheelhouse.

Pass build/offline-cache/site-packages-export to export-dependencies.py after
checking it is a normal directory. Have the exporter return project_wheels,
verified_wheels, the exact six distribution list, and SHA-256 for every wheel.
Never read repository dist/ during package.ps1 deps.

When output exists, remove only known generated subdirectories site-packages,
wheels, and generated reports. Reject unknown entries instead of deleting them.
Keep third-party preparation separate and runtime installation offline.

- [ ] Step 3: Add a six-wheel report handoff.

Invoke-PackageDeps passes the checked wheel list to later assembly through the
package report, not a second hard-coded list. Store wheelhouse path, checker
report, smoke report, and wheel hashes in the deps summary. Later stages fail
if the list is missing or differs from the six configured names.

- [ ] Step 4: Run distribution gates and commit.

    uv run pytest tests/test_python_distribution_contract.py tests/test_python_distribution_smoke.py tests/test_packaging_control_plane.py -v
    uv run python scripts/build-python-distributions.py --dist-dir build/phase7-test-dist
    uv run python scripts/check-python-distributions.py --dist-dir build/phase7-test-dist
    uv run python scripts/smoke-python-distributions.py --dist-dir build/phase7-test-dist --python .venv/Scripts/python.exe

Expected: checker reports six verified wheels and isolated smoke reports every
independent/composed scenario.

    git add scripts/package-lib.ps1 scripts/export-dependencies.py tests/test_python_distribution_smoke.py tests/test_packaging_control_plane.py
    git commit -m "feat: make release dependency export six-wheel clean"

## Task 4: Wheel-Only Bundle Assembly And Artifact Identity

Files:
- Modify: scripts/prepare-offline.ps1
- Modify: scripts/build-offline-bundle.ps1
- Modify: scripts/package-lib.ps1
- Modify: scripts/validate-offline-bundle.ps1
- Modify: tests/test_packaging_control_plane.py

- [ ] Step 1: Add failing assembly tests.

Place a product package in both app/embedagent and runtime/site-packages, add an
__editable__*.pth, and provide a source-tree fallback with no installed product
package. Assert distinct failures. For a valid fixture assert app/embedagent
exists, runtime/site-packages has no embedagent package, the five lower packages
are present, and bundle-manifest project_wheels has exactly six names.

    uv run pytest tests/test_packaging_control_plane.py -k "site_packages or editable or duplicate or installed" -v

Expected: new negative fixtures fail before assembly enforcement.

- [ ] Step 2: Enforce installed-source staging.

Keep prepare-offline.ps1 sourcing the product from
build/offline-cache/site-packages-export/site-packages/embedagent and refuse
src/embedagent fallback. Keep editable cleanup, then fail if duplicate product
directories or product dist-info remain in runtime/site-packages.

Record project_wheels, wheel_hashes, identity_path, and source_mode:
wheel-installed in bundle-manifest.json. Keep all five lower distributions under
runtime/site-packages and the product only under app/embedagent.

- [ ] Step 3: Carry identity and classify the zip.

Copy release-identity.json, checker/deps reports, and target-report schema into
the bundle and sources output. A provisional zip may be generated during
assembly, but the package report marks it provisional until verify succeeds.
On failure, the final artifact path is not publishable.

- [ ] Step 4: Extend validator checks.

Require identity, six wheel metadata, source_mode wheel-installed, no editable
links, no duplicate product, and matching bundle/zip hashes. Keep the runtime
contract as the only external-tool requirements list.

- [ ] Step 5: Run assembly tests and commit.

    uv run pytest tests/test_packaging_control_plane.py -k "site_packages or editable or duplicate or installed or bundle_manifest" -v

Expected: valid and invalid assembly fixtures pass.

    git add scripts/prepare-offline.ps1 scripts/build-offline-bundle.ps1 scripts/package-lib.ps1 scripts/validate-offline-bundle.ps1 tests/test_packaging_control_plane.py
    git commit -m "feat: assemble release bundles from wheel-installed packages"

## Task 5: Repository Verification And Reproducibility

Files:
- Modify: scripts/package-lib.ps1
- Modify: scripts/build-offline-bundle.ps1
- Modify: scripts/validate-offline-bundle.ps1
- Modify: tests/test_packaging_control_plane.py
- Create: tests/fixtures/packaging/reproducibility-config.json

- [ ] Step 1: Add reproducibility tests.

Run two isolated assemblies using the same source revision, wheelhouse, asset
cache, and build/phase7-repro/first and build/phase7-repro/second output roots.
Assert identity JSON, wheel hashes, bundle manifest, checksums, and declared
bundle file hashes are byte-identical after operational timestamps are removed
from stage reports. Assert a source or wheel mutation changes identity.

    uv run pytest tests/test_packaging_control_plane.py -k "reproduc" -v

Expected: the test fails until identity and timestamp normalization exist.

- [ ] Step 2: Make verify consume every release gate.

Invoke-PackageVerify runs in order:
1. validate-offline-bundle.ps1 -RequireComplete;
2. check-bundle-dependencies.py;
3. bundle-local GUI headless smoke;
4. bundle-local C smoke;
5. zip extraction and re-validation;
6. identity/reproducibility comparison.

Record each result and report path. A local windowed run can be diagnostic
evidence but cannot change TARGET_READY to ACCEPTED.

- [ ] Step 3: Implement target-ready status.

After deps, assemble, and verify pass, write TARGET_READY into the package report
and generate the target evidence kit. No local PowerShell command writes
ACCEPTED.

- [ ] Step 4: Run the repository-side release gate and commit.

    powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor -Profile release -Json
    powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Json
    uv run pytest tests/test_packaging_control_plane.py -k "release or verify or repro" -v

Expected: the release report reaches TARGET_READY only when all local gates pass.

    git add scripts/package-lib.ps1 scripts/build-offline-bundle.ps1 scripts/validate-offline-bundle.ps1 tests/test_packaging_control_plane.py tests/fixtures/packaging/reproducibility-config.json
    git commit -m "feat: gate release candidates with reproducible verification"

## Task 6: Win7 Evidence Kit And Acceptance Validator Integration

Files:
- Modify: scripts/package-lib.ps1
- Modify: scripts/validate-release-evidence.py
- Modify: scripts/offline-runtime-contract.json
- Modify: docs/guides/win7-preflight-checklist.md
- Modify: docs/guides/win7-gui-validation.md
- Modify: tests/test_release_evidence.py
- Modify: tests/test_packaging_control_plane.py

- [ ] Step 1: Define the target report schema in the runtime contract.

Add win7_evidence_schema_version and keep win7_windowed_gui_smoke as the
authoritative GUI requirement. The target report contains release identity hash,
machine OS/service-pack/architecture, WebView2 major/runtime source, GUI
renderer, C smoke result, tool fallback flag, command exit codes, and
blocking_errors.

- [ ] Step 2: Generate the target kit during 7A.

Write these files under bundle manifests/evidence:
release-identity.json, target-report.schema.json, win7-runbook.md, and
expected-bundle-hashes.json.

Copy scripts/validate-release-evidence.py into the bundle validation tools
alongside validate-gui-smoke.py and validate-cpp-smoke.py. The runbook uses
validate-gui-smoke.cmd and validate-cpp-smoke.cmd, requires
--require-fixed-webview2, and asks the operator to return only structured report
and environment summary.

- [ ] Step 3: Implement acceptance validation.

validate-release-evidence.py emits a JSON report with status, identity hash,
checks, and blocking_errors. Every mismatch fixture exits 1 with a stable code.
Only the complete Win7 fixture exits 0; current local output is never accepted
as a substitute.

- [ ] Step 4: Run evidence tests and commit.

    uv run pytest tests/test_release_evidence.py tests/test_packaging_control_plane.py -k "evidence or target or acceptance" -v

Expected: positive and negative report fixtures pass.

    git add scripts/package-lib.ps1 scripts/validate-release-evidence.py scripts/offline-runtime-contract.json docs/guides/win7-preflight-checklist.md docs/guides/win7-gui-validation.md tests/test_release_evidence.py tests/test_packaging_control_plane.py
    git commit -m "feat: ship hash-bound Win7 acceptance kit"

## Task 7: Documentation, Target-Ready Closeout, And Full Gate

Files:
- Modify: docs/modules/packaging-and-deployment.md
- Modify: docs/guides/win7-preflight-checklist.md
- Modify: docs/guides/win7-gui-validation.md
- Modify: docs/implementation-roadmap.md
- Modify: docs/development-tracker.md
- Create: docs/superpowers/plans/2026-07-19-phase7-target-ready-closeout.md

- [ ] Step 1: Update active documentation.

Document the six-wheel release identity, wheel-only staging, strict doctor,
provisional zip semantics, TARGET_READY versus ACCEPTED, and the exact future
command that validates a copied Win7 report. Remove language implying local or
Windows 10 evidence proves Win7 delivery.

- [ ] Step 2: Write the 7A closeout record.

Record final source commit, six wheel names/hashes, bundle/zip hashes,
doctor/deps/assemble/verify reports, local GUI/C smoke results,
reproducibility comparison, target kit paths, and the explicit statement:
Phase 7A TARGET_READY; Phase 7B ACCEPTED not performed because no real Win7
machine was available.

- [ ] Step 3: Run the complete pre-merge gate.

    uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
    uv run pytest tests/ -m "not slow and not gui" -v
    uv run --locked python scripts/lint.py
    cd src/embedagent/frontend/gui/webapp
    npm test
    npm run build
    cd ../../../..
    git diff --check

Expected: architecture guards, non-GUI tests, lint, GUI tests, and production
build pass; generated static assets are committed if the build changes them.

- [ ] Step 4: Commit the target-ready closeout.

    git add scripts docs tests
    git commit -m "docs: close Phase 7A target-ready release gate"

The commit must not claim ACCEPTED, Win7 GUI success, or real C/C++ project
readiness.

## Final Phase 7A Handoff

After Task 7, report TARGET_READY release identity and artifact paths, exact
local verification commands and summaries, and the target-machine runbook.

Future acceptance command from the bundle root:

    python tools/validation/validate-release-evidence.py --identity manifests/release-identity.json --report manifests/win7-evidence.json --json-report manifests/acceptance-report.json

Current status remains TARGET_READY until a real Win7 SP1 x64 report passes.
Phase 8 remains reserved for real C/C++ project validation.
