# Windows 7 Acceptance Handoff

> Status: `active`
> Repository state: `TARGET_READY`
> Acceptance state: `PENDING_WIN7`
> Publishable: `false`
> Last synchronized: `2026-08-01`

## Open Acceptance Condition

Repository-side build, static validation, bundle smoke, and reproducibility gates
can establish target readiness. They cannot establish Windows 7 acceptance. The
remaining condition is a hash-bound evidence report produced by the current
release bundle on a clean Windows 7 SP1 x64 machine with Fixed Version WebView2
109.

The current delivery contract is owned by:

- `docs/product/packaging-and-deployment.md`;
- `docs/guides/win7-release-runbook.md`;
- `docs/guides/win7-preflight-checklist.md`.

This handoff tracks only the still-open external acceptance action. It is not a
second packaging authority.

## Repository-Side Preconditions

Before transfer to the target machine, create a release from the exact revision
being evaluated:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release -Profile release -Json
```

The resulting report must retain:

- `final_status=TARGET_READY`;
- `acceptance_status=PENDING_WIN7`;
- `publishable=false`;
- exact identities and hashes for all six project wheels;
- bundle-local C and GUI smoke results;
- `runtime_source=bundle` and `allow_system_tool_fallback=false`;
- the release identity consumed by the target-machine validator.

Any earlier local report is diagnostic evidence only. It must not be reused to
claim acceptance for a different source revision or bundle identity.

## Target-Machine Procedure

On a clean Windows 7 SP1 x64 machine:

1. Extract the unmodified release zip.
2. Run `validate-cpp-smoke.cmd` and retain its JSON report.
3. Run `validate-gui-smoke.cmd --require-fixed-webview2` and retain the
   headless report.
4. Run `validate-gui-smoke.cmd --windowed --auto-close-seconds 8
   --require-fixed-webview2`.
5. Populate `manifests/evidence/win7-evidence.json` from the target-machine
   results without editing the release identity.
6. Run:

```cmd
runtime\python\python.exe tools\validation\validate-release-evidence.py ^
  --identity manifests\release-identity.json ^
  --report manifests\evidence\win7-evidence.json ^
  --json-report manifests\evidence\acceptance-report.json
```

## Acceptance Contract

The validator must observe all of the following from the same bundle identity:

- Windows 7 SP1 AMD64;
- `edgechromium` windowed rendering;
- bundled Fixed Version WebView2 major `109`;
- successful bundle-local Clang C smoke;
- `runtime_source=bundle`;
- zero system-tool fallback;
- zero command failures;
- no blocking errors.

Only `acceptance-report.json` with `status=ACCEPTED` closes this slice and makes
a publishability update eligible. Local Windows results and hosted CI remain
diagnostic evidence.

## Remaining Work

1. Generate the release and release identity from the intended source revision.
2. Transfer the exact release zip to a clean Windows 7 SP1 x64 machine.
3. Run the C, headless GUI, and windowed GUI procedures.
4. Validate and return the hash-bound acceptance report.
5. Replace `docs/current-status.md` release state only after the validator
   reports `ACCEPTED`, then archive this handoff.
