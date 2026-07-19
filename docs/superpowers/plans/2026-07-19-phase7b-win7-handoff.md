# Phase 7B Win7 Acceptance Handoff

Date: 2026-07-19

## Status

The repository-side Phase 7B handoff is complete in `main` commit `65e1946a`.
The local release candidate reaches `TARGET_READY` with
`acceptance_status=PENDING_WIN7` and `publishable=false`. This is not an
`ACCEPTED` claim.

A clean Windows 7 SP1 x64 machine is still required to run the bundled
windowed GUI flow and produce the hash-bound evidence report.

## Repository-Side Evidence

The current local release was run through the official entry point:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Json
```

The successful report is:

- `build/offline-reports/20260719120543-a53f55d563d04cff8fd3f172df889c5d-release.json`
- `final_status=TARGET_READY`
- `acceptance_status=PENDING_WIN7`
- `publishable=false`
- exact six project wheels and wheel hashes recorded in `build/offline-reports/deps.json`
- bundle static/dependency checks passed
- bundle-local C smoke passed with `runtime_source=bundle` and
  `allow_system_tool_fallback=false`
- zip extraction validation passed
- bundle GUI headless smoke passed with `renderer=edgechromium`,
  `runtime_source=bundle`, and `fixed_webview2.runtime_major=109`

The current GUI smoke protocol also covers the live `session_event` stream,
permission/user-input response endpoints, official `bash` and `task_status`
tools, and the synchronous interaction lease race. The launcher uses a
workspace-scoped `EMBEDAGENT_GUI_APP_HOME`, so the smoke does not write to the
developer's global application state.

## Build Reproducibility

The six-wheel builder and dependency exporter accept explicit `--cache-dir`
and `--offline` controls. Production packaging uses the ignored project-local
`.uv-cache` and release dependencies are installed only after a controlled
build-time cache-preparation step. Runtime bundle execution remains offline.

The Phase 7B code and documentation are committed in `main` as `65e1946a`.
The reports above were generated before that commit, so they are
repository-side diagnostic evidence. Before publishing, rerun the release and
reproducibility gate from this clean revision so the release identity binds to
the committed source.

## Target-Machine Procedure

On a clean Windows 7 SP1 x64 machine:

1. Extract the release zip without modifying its contents.
2. Run `validate-cpp-smoke.cmd` and retain its JSON report.
3. Run `validate-gui-smoke.cmd --require-fixed-webview2` and retain the
   headless report.
4. Run
   `validate-gui-smoke.cmd --windowed --auto-close-seconds 8
   --require-fixed-webview2`.
5. Combine machine, GUI, and C smoke fields into
   `manifests/evidence/win7-evidence.json`. Do not hand-edit the release
   identity or copy local Windows 10 values into this report.
6. Run:

```cmd
runtime\python\python.exe tools\validation\validate-release-evidence.py ^
  --identity manifests\release-identity.json ^
  --report manifests\evidence\win7-evidence.json ^
  --json-report manifests\evidence\acceptance-report.json
```

The acceptance validator must observe Windows 7 SP1 AMD64, renderer
`edgechromium`, bundled Fixed Version WebView2 major `109`, bundled C smoke,
`runtime_source=bundle`, zero system-tool fallback, zero command failures, and
no blocking errors. Only its `ACCEPTED` result closes Phase 7B.

## Remaining Work

- rerun `package.ps1 release -Profile release -Json` from commit `65e1946a`;
- optionally run `package.ps1 release -Reproducible` and retain both child
  reports plus the normalized comparison report;
- perform the external Win7 windowed smoke and run the offline acceptance
  validator;
- keep Phase 8 real C/C++ project validation separate from this release gate.

## Reproducibility Evidence

The two-run production gate also passed:

- outer report:
  build/offline-reports/20260719125057-ce0944fbb65a459c90437597982fe7bc-release.json
- comparison report:
  build/phase7-repro/ce0944fbb65a459c90437597982fe7bc/artifact-reproducibility.json
- mismatches=[]
- both normalized bundle tree hashes:
  15351b062f43054d43d3568bcaf098ed217ea8d515f56aa5e2736a925940fb52
- final_status=TARGET_READY
- acceptance_status=PENDING_WIN7
- publishable=false

The comparison excludes only generated operational evidence paths and
normalizes declared manifest path/timestamp fields. It does not exclude
wheels, project code, runtime assets, launcher binaries, or stable bundle
metadata.