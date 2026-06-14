# Phase F Offline Bundle Validation Design

## Context

Pi-inspired minimal Core Phases A through E made Agent Core smaller and more extensible:

- lifecycle state is reducer-backed and durable
- extension dispatch is source-aware
- the default C/C++ harness registers capabilities through the extension boundary
- local resources and project-local Python extensions are separate
- `SelfExtensionAuthoringService` can generate skills, prompts, recipes, and disabled extension skeletons under `.embedagent`

Phase F must prove those new boundaries still satisfy EmbedAgent's product constraints:

- Windows 7 compatibility remains mandatory
- offline deployment remains mandatory
- Python stays `>=3.8,<3.9`
- runtime cannot require Docker, WSL, VS Code, online services, package installation, or remote registries
- every tool the product invokes at runtime must be present in the portable bundle

The current packaging pipeline already has useful gates:

- `scripts/package.ps1` is the public packaging control plane
- `scripts/prepare-offline.ps1` stages the portable bundle
- `scripts/build-offline-bundle.ps1` promotes staging into dist artifacts and sources seed
- `scripts/validate-offline-bundle.ps1` checks bundle layout, manifests, checksums, launchers, and selected dynamic commands
- `scripts/check-bundle-dependencies.py` checks Python packages and core external tools

The remaining gap is that the runtime tool surface is not described once. `ToolContext` knows about managed runtime tools (`python`, `git`, `rg`, `ctags`, `llvm`), `prepare-offline.ps1` writes bundle components, `validate-offline-bundle.ps1` checks paths dynamically, `check-bundle-dependencies.py` has a separate hard-coded list, and docs describe another human-readable list. Those lists mostly agree, but drift is easy.

Phase F should make the offline runtime boundary explicit without turning packaging into a larger product.

## Requirements

1. Bundle validation must have one machine-readable contract for runtime-invoked tools.
2. The contract must cover the tools that Agent Core and the default C/C++ workflow expect to invoke through managed runtime resolution:
   - Python runtime for launcher execution and generated validation recipes
   - MinGit for built-in git tools and workspace intelligence
   - ripgrep for search workflows
   - Universal Ctags for symbol intelligence
   - LLVM/Clang toolchain root for C/C++ build, static analysis, and coverage flows
3. LLVM validation must check the concrete executables the current runtime recognizes:
   - `clang.exe`
   - `clang++.exe`
   - `clang-cl.exe`
   - `clang-tidy.exe`
   - `clang-analyzer.bat`
   - `llvm-profdata.exe`
   - `llvm-cov.exe`
4. Validators must fail release/strict checks when required runtime tools are missing.
5. Development-mode verification may still warn for incomplete local bundles where existing profile semantics allow it.
6. `check-bundle-dependencies.py` and `validate-offline-bundle.ps1` must agree on the contract.
7. Runtime tests must catch drift between the contract and `ToolContext` managed-tool classification.
8. Project-local Python extension loading must remain dependency-free:
   - no `pip`, `uv`, `conda`, npm, network, or registry activity during extension loading
   - extension imports use only manifest-gated, workspace-bound `extension.py`
9. Generated self-extension artifacts must remain workspace-bound and disabled-by-default for code.
10. Documentation must update the source-of-truth docs and packaging module docs.
11. The implementation must use Python 3.8-compatible syntax.

## Non-Goals

Phase F will not:

- build a new installer
- add online dependency installation
- add a plugin marketplace or registry
- solve full third-party toolchain acquisition for LLVM beyond the existing `toolchains/llvm/current` assembly path
- require a real Windows 7 VM inside the automated test suite
- change the default C/C++ workflow behavior
- let project-local extensions replace built-in tools

## Interface Designs

### Design 1: Validators Own Separate Lists

Keep the current shape and update both validators directly:

- `validate-offline-bundle.ps1` gains more static/dynamic checks for LLVM and Python
- `check-bundle-dependencies.py` gains the same checks
- docs list the same required tools

Usage:

```powershell
.\scripts\validate-offline-bundle.ps1 -BundleRoot build\offline-dist\embedagent-win7-x64 -RequireComplete
uv run python scripts\check-bundle-dependencies.py build\offline-dist\embedagent-win7-x64
```

What it hides:

- each validator hides its own path conventions

Trade-off:

This is simple, but it preserves duplication. It does not make future drift obvious when `ToolContext` starts recognizing a new managed executable.

### Design 2: Runtime Python Exports The Contract

Add a Python module such as `embedagent.runtime_tools` and make validators call it:

```python
from embedagent.runtime_tools import runtime_bundle_contract

for tool in runtime_bundle_contract():
    validate(tool)
```

PowerShell would shell out to bundled or build Python to load the contract.

What it hides:

- Python owns the contract and can keep it close to `ToolContext`

Trade-off:

This makes Python the source of truth, but it creates a fragile packaging dependency. `validate-offline-bundle.ps1` needs to work even when Python is missing so it can report that defect clearly. Requiring Python to load the contract before validating Python weakens the validator.

### Design 3: Packaging Contract JSON With Runtime Guard Tests

Create a small source-controlled JSON contract, for example `scripts/offline-runtime-contract.json`, and make both validators consume it. Add runtime tests that compare the contract to `ToolContext` constants and classification behavior.

Usage:

```powershell
.\scripts\validate-offline-bundle.ps1 -BundleRoot build\offline-dist\embedagent-win7-x64 -RequireComplete
uv run python scripts\check-bundle-dependencies.py build\offline-dist\embedagent-win7-x64
uv run pytest tests/test_packaging_control_plane.py tests/test_tools_package.py -q
```

Contract sketch:

```json
{
  "schema_version": 1,
  "required_tools": [
    {
      "id": "python",
      "component": "python_runtime",
      "paths": ["runtime/python/python.exe"],
      "dynamic_check": ["--version"]
    },
    {
      "id": "llvm",
      "component": "llvm_clang_bundle",
      "paths": ["bin/llvm/bin/clang.exe"],
      "children": [
        "bin/llvm/bin/clang++.exe",
        "bin/llvm/bin/clang-cl.exe",
        "bin/llvm/bin/clang-tidy.exe",
        "bin/llvm/bin/clang-analyzer.bat",
        "bin/llvm/bin/llvm-profdata.exe",
        "bin/llvm/bin/llvm-cov.exe"
      ]
    }
  ]
}
```

What it hides:

- validators hide path probing and report formatting
- runtime keeps its own execution logic
- tests hide the cross-check that both sides agree

Trade-off:

This adds one small config file, but it makes the release contract explicit and tool-agnostic. PowerShell can validate missing Python without importing Python, while Python tests still catch drift between the contract and runtime code.

## Recommendation

Use Design 3.

It fits the architecture philosophy from the Pi-inspired program: keep the core small, expose capabilities through explicit contracts, and let reducers/validators derive state from durable structured inputs rather than scattered imperative assumptions. The JSON contract becomes the packaging truth for runtime-invoked tools; `ToolContext` remains the runtime truth for resolving managed tools; tests enforce that those truths stay aligned.

## Architecture

### Contract

Add `scripts/offline-runtime-contract.json` with:

- `schema_version`
- `required_tools`
- per-tool stable `id`
- related bundle manifest `component`
- `category`
- one or more required static `paths`
- optional `alternatives` for layouts like MinGit
- optional `children` for toolchain subcommands
- optional `dynamic_check` command args
- optional documentation `notes`

The contract is not an asset manifest. It does not describe downloads. It describes what must be present in an assembled bundle.

### PowerShell Validation

`validate-offline-bundle.ps1` should:

- load the contract from `scripts/offline-runtime-contract.json` by default
- check each required path or alternative group under `BundleRoot`
- treat required missing tools as `fail` under `-RequireComplete`
- keep dev-mode behavior consistent with current warning semantics
- run dynamic checks from the contract when `-SkipDynamicChecks` is not set
- write result codes that identify contract items, such as `runtime_tool.python`, `runtime_tool.llvm.clang`
- include contract metadata in the JSON report

The script should still emit explicit legacy-friendly result codes for key existing checks where tests or operators depend on them, but those checks should be backed by the contract.

### Python Dependency Checker

`check-bundle-dependencies.py` should:

- load the same contract
- validate the required runtime tool paths
- report failures under the existing `External Tools` check
- include machine-readable details in the JSON report
- avoid importing runtime modules that depend on optional package state

### Runtime Guard Tests

Tests should verify:

- the contract file parses and has expected schema
- each contract `id` maps to a `ToolContext` managed tool key where applicable
- LLVM child executable names are recognized by `ToolContext.classify_managed_command(...)`
- direct executable names (`python`, `git`, `rg`, `ctags`) are recognized by `ToolContext`
- package validators report missing LLVM children as failures in strict mode
- a minimal complete mock bundle passes static contract checks with dynamic checks skipped

### Extension Dependency Guard

Project-local extension tests should verify:

- loading an enabled extension does not invoke `pip`, `uv`, `conda`, `npm`, or network/process installation commands
- generated extension skeletons remain disabled by default
- generated extension validation recipes use the managed Python command path through existing `run_recipe` behavior, not a new extension-loading path

The loader does not sandbox arbitrary Python. It keeps code loading explicit, manifest-gated, workspace-bound, permission-declared, and dependency-install-free.

## Acceptance Criteria

Phase F is complete when:

1. `scripts/offline-runtime-contract.json` exists and is validated by tests.
2. `validate-offline-bundle.ps1` consumes the contract and reports missing required runtime tools.
3. `check-bundle-dependencies.py` consumes the contract and reports the same missing runtime tools.
4. LLVM required executables are validated as release-gate items.
5. Runtime guard tests prove the contract matches `ToolContext` managed-tool classification.
6. Extension loading tests prove dependency installation is not part of project-local extension loading.
7. Source-of-truth docs describe the new contract and Phase F status.
8. Focused packaging/resource/extension tests pass.
9. Full fast non-GUI test suite passes.

## Open Constraints

A real clean Windows 7 target-machine smoke remains a release gate, but this development slice cannot execute that VM-only acceptance test in the current workspace. The slice must update the checklist and keep the automated bundle contract strict enough that the later Win7 smoke starts from a mechanically validated artifact rather than a best-effort bundle.

## Self-Review

- Placeholder scan: no placeholder sections remain.
- Internal consistency: the design keeps the JSON contract as packaging truth and runtime tests as drift detection.
- Scope check: this is one implementation plan focused on bundle validation, not a new packaging system.
- Ambiguity check: LLVM required child executables, extension dependency boundaries, and Win7 smoke limitations are explicit.
