# Phase 6 GUI And Agent Export Convergence Closeout

Date: 2026-07-19
Status: complete for the repository-side Phase 6 definition of done

Phase 6 closes the GUI/runtime convergence slice. The renderer remains a T3
code-style client runtime and does not know the concrete Agent or workflow
implementation. Agent composition is a deterministic build-time layer that
can export a generic Agent product or add a specialized workflow package
without adding that specialization to Agent Core.

## Delivered Slices

The implementation landed as these commits on `main`:

| Commit | Slice |
|---|---|
| `12326fe1` | Phase 6 implementation plan |
| `831f203c` | Versioned GUI protocol envelopes |
| `2f07c35b` | Single renderer transport adapter for known envelopes |
| `9e6bed80` | T3 client-runtime composition boundary tests |
| `e6e4dd93` | Deterministic composition compiler/export layer |
| `05f6e3f3` | Generic, Python, HTML, and C/C++ Agent definitions |
| `0d4f1ec5` | Backend/frontend Agent capability matrix fixtures |
| `c04bc911` | T3 GUI parity gate and generated static asset update |

The documentation synchronization commit is the final commit for this phase.

## Protocol Boundary

The Python and JavaScript boundary validates these protocol versions:

- `agent_session_v1`
- `capability_v1`
- `ide_service_v1`
- `app_shell_v1`

Known GUI bootstrap/capability/session responses are normalized through one
transport adapter. Legacy raw payloads remain pass-through for compatibility;
invalid envelopes are rejected without inventing missing product names, mode
names, workflow names, or capability values. Envelope validation also rejects
invalid sequence/revision values, non-JSON-safe payloads, and sensitive keys.

## Agent Composition

`embedagent-composition` is a dependency-free build-time compiler/export layer.
It validates component dependencies, conflicts, namespaces, and asset paths;
then emits `agent.json`, `agent.lock.json`, `export-report.json`, component
files, and declared runtime assets with stable ordering and SHA-256 records.
Composition is not imported by Agent Core at runtime.

The following hashes are canonical JSON hashes of deterministic fixture locks
from `tests/test_agent_composition.py`:

| Agent fixture | Lock SHA-256 | Selected components |
|---|---|---|
| `embedagent.generic` | `91b5195053f0c99bf1c8f671ab31462738de27bce41bde1190afa1012f1cf292` | composition, core, generic profile, protocol, host |
| `embedagent.default_c_cpp` | `094643375b5b4eaf4399ac5528109acc44229f8c26118bca3d1216d8d45b859b` | generic fixture plus `embedagent-workflow-cpp` |

The export report contains no API keys or provider credentials. Component
assets are copied only from declared, workspace-resolved paths.

## T3 Reference And GUI Independence

The pinned reference is `reference/t3code` commit
`2318e00270203780b72efbbcffce92e907312027` from 2026-07-18. Phase 6 ports
only applicable client-runtime and UX boundaries. Cloud, Relay, Electron,
mobile, remote, marketplace, and other infrastructure-specific T3 surfaces
remain explicitly excluded.

The production renderer has no direct `fetch`/WebSocket transport ownership,
no C/C++/Clang branches, and no built-in workflow-tool branches. App shell
composition is tested separately from reducers and protocol normalization.
Development visual fixtures remain explicit and opt-in; static fixture imports
are not part of production startup.

The unchanged GUI build is covered by empty, generic, C/C++, Python, HTML, and
injected specialized Agent capability fixtures. Unknown capabilities degrade
to neutral empty projections rather than renderer-owned branding or workflow
defaults.

## Verification Evidence

Fresh repository-side gates on 2026-07-19:

- `uv run pytest tests/ -m "not slow and not gui" -v`: **1578 passed, 4 deselected**.
- `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`: **143 passed**.
- `uv run pytest tests/test_gui_protocol_projection.py tests/test_gui_app_shell.py tests/test_gui_agent_matrix.py -v`: **15 passed**.
- `uv run pytest tests/test_gui_agent_matrix.py -v`: **3 passed**.
- `npm test`: exit code 0 (`file preview model checks passed`, `frontend helper checks passed`).
- Direct JavaScript checks for protocol envelopes, adapter behavior, app composition, reducers, Agent matrix, and visual debug controller: all exit code 0.
- `npm run build`: exit code 0. Generated GUI assets remain tracked under `src/embedagent/frontend/gui/static/`.
- `uv run --locked python scripts/lint.py`: Ruff passed; Black reported **344 files would be left unchanged**.
- Deterministic composition tests and the distribution-contract suite were included in the full non-GUI result.

## Remaining Evidence

Phase 6 does not claim release or product validation that belongs to later
phases:

- **Phase 7:** build/check/smoke/export all six project wheels in a clean
  offline bundle, then record clean Windows 7 x64 plus bundled WebView2 109
  windowed GUI evidence. Local GUI build and architecture tests are not a
  substitute for that target-style evidence.
- **Phase 8:** validate real C/C++ projects with the bundle-local Clang
  workflow, including diagnostics, recipes, and build/test repair flows.
- **Phase 9:** optional trusted enterprise/intranet providers, catalogs,
  services, or telemetry sinks outside Agent Core.

Until the Phase 7 target bundle and Phase 8 real-project records exist, the
repository may claim Phase 6 implementation and local gates only, not full
Win7 delivery or real C/C++ production readiness.
