# Phase 7 Release Gate Closeout

Date: 2026-07-19

## Release Candidate

- Source revision used by the generated identity: `bb173d0334f53bf2bb128bd1293f92fe7b326b16`
- Closeout note: the Task 7 checker/exporter hardening landed after this artifact snapshot; the recorded bundle is diagnostic evidence only and must be rebuilt before publication.
- Version/profile: `0.1.0` / `release`
- Bundle directory: `build/offline-dist/embedagent-win7-x64`
- Zip: `build/offline-dist/embedagent-win7-x64.zip`
- Sources/evidence directory: `build/offline-dist/embedagent-win7-x64-sources`
- Identity SHA-256: `fd0cfb9c374e193f5a49f750f6eb64dd79aeb87783865c40cf9407faadc819e1`
- Bundle tree SHA-256: `288749703d2c88bc4a40c5e755f578fbf118ad3a0d64976473c759f056a685a3`
- Zip SHA-256: `9089ebc81b42a0dcb63d1f17d45b0686bf72520a67d468b3fd78afda15f285bb`

The six checked project wheels and hashes are recorded in
`build/offline-reports/deps.json` and the release identity:

| Distribution | Wheel | SHA-256 |
|---|---|---|
| `embedagent-core` | `embedagent_core-0.1.0-py3-none-any.whl` | `4256c7cdebead35199cfa79e7bc57608f5ab57b13be4dc1fb885a2f404fd4b56` |
| `embedagent-protocol` | `embedagent_protocol-0.1.0-py3-none-any.whl` | `17d8cdc5b89390c6fd4658ce07b8a9a55df706fa7b3e06220290b2666f3e4e52` |
| `embedagent-host` | `embedagent_host-0.1.0-py3-none-any.whl` | `875442de06681566cfa55c00d30f520e5236ef2b426d657d96b8d3e4a6c12462` |
| `embedagent-composition` | `embedagent_composition-0.1.0-py3-none-any.whl` | `a00fef1e6d0cae355fb95fb5dccc04fddaa31219f132390a9bca1a5e6e75b5ed` |
| `embedagent-workflow-cpp` | `embedagent_workflow_cpp-0.1.0-py3-none-any.whl` | `1ff9ee3fa6c7b6630d9864f1f982a7375e97afb7461e0894a914c7d4906e87bf` |
| `embedagent` | `embedagent-0.1.0-py3-none-any.whl` | `1e15df191b206267ae6306a8f15fa6f44fccf245427a4f9b60d8e57fe2260df8` |

## Repository Evidence

- `scripts/package.ps1 doctor -Profile release -Json`: READY.
- `build/offline-reports/deps.json`: exact six wheels, wheel hashes, and successful export.
- `build/offline-reports/phase7-static-validate.json`: 88 passes, 0 warnings, 0 failures.
- `build/offline-reports/phase7-dependency-check.json`: dependency checker PASS after allowing product code only in `app/embedagent`.
- `build/offline-reports/phase7-cpp-smoke.json`: PASS, `runtime_source=bundle`, `allow_system_tool_fallback=false`.
- GUI headless smoke: failed waiting for the local GUI HTTP endpoint after 20 seconds. The same timeout occurs on the current source-tree smoke path, so this is an environment/runtime blocker, not evidence of Win7 success.
- Reproducibility: identity and wheel hashes are deterministic and recorded; a second isolated full assembly was not completed because the GUI gate did not pass.

## State

Current state is `NOT_READY`. It is not `TARGET_READY` because the bundle-local GUI gate did not pass, and it is not `ACCEPTED` because no real Windows 7 SP1 x64 evidence report exists.

After the GUI blocker is resolved, rerun the full release command and require a report with `release_state=TARGET_READY`. On a real Win7 SP1 x64 machine, collect `manifests/evidence/win7-evidence.json` and run:

```cmd
runtime\python\python.exe tools\validation\validate-release-evidence.py --identity manifests\release-identity.json --report manifests\evidence\win7-evidence.json --json-report manifests\evidence\acceptance-report.json
```

Only that copied target report can move the state to `ACCEPTED`.
