# Legacy Removal And Release Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the superseded mixed architecture, prove every distribution and product from isolated inputs, and record target-machine evidence required for a Windows 7/WebView2 release claim.

**Architecture:** Treat pre-release compatibility as debt, not a feature. Add deletion-oriented guards first, remove old construction/protocol/GUI paths, then validate source dependencies, wheels, deterministic exports, bundle-local tools, and real target machines. Local CI may prove artifact integrity but cannot substitute for the final Win7 smoke record.

**Tech Stack:** Python 3.8, AST/source guards, pytest, uv wheel builds, Node/Vite tests, PowerShell offline packaging, SHA-256 evidence manifests, Windows 7 SP1, WebView2 109.

---

## Required Deletions

The phase is not complete while any of these active paths or contracts remain:

```text
src/embedagent/core/adapter.py
src/embedagent/agent_applications.py
src/embedagent/frontend/
src/embedagent/workflow_packages/
embedagent.protocol.CoreInterface
embedagent_protocol.app_protocol
AgentApplicationRecord
AgentApplicationRegistry
AgentApplicationDescriptor
profile_kind
builder_path
GET /api/sessions/capabilities
gui_app_shell_v1
```

Product composition may remain under the root `embedagent` distribution, but
it must contain only bootstrap/configuration code and explicit trusted catalog
registration. It must not become a second Core, Host, Protocol, GUI, or
workflow implementation package.

### Task 1: Add A Final Architecture Debt Gate

**Files:**
- Create: `scripts/check-final-architecture.py`
- Create: `tests/test_final_architecture.py`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `tests/test_current_architecture_boundaries.py`

- [ ] **Step 1: Write the target path and dependency tests**

Create `tests/test_final_architecture.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_retired_mixed_paths_are_absent():
    retired = (
        "src/embedagent/core/adapter.py",
        "src/embedagent/agent_applications.py",
        "src/embedagent/frontend",
        "src/embedagent/workflow_packages",
        "packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py",
    )
    assert [path for path in retired if (ROOT / path).exists()] == []


def test_root_product_contains_no_runtime_subsystems():
    root_package = ROOT / "src/embedagent"
    forbidden_names = {
        "query_engine.py",
        "session.py",
        "tool_runtime.py",
        "permissions.py",
        "app_protocol.py",
        "extension_manager.py",
    }
    found = {path.name for path in root_package.rglob("*.py")}
    assert found.isdisjoint(forbidden_names)
```

- [ ] **Step 2: Implement the architecture checker**

`check-final-architecture.py` parses imports with `ast`, inspects wheel
pyprojects with `tomllib`/`tomli`, and reports JSON diagnostics for:

- forbidden package dependency edges;
- retired paths and public names;
- multiple extension-manager or tool-catalog construction roots;
- Host/GUI imports of the C/C++ workflow;
- Core imports outside standard library and its declared dependencies;
- product modules implementing runtime classes instead of wiring factories;
- v1 GUI protocol identifiers and routes;
- forbidden runtime-discovery APIs in Composition.

The script accepts `--root`, returns 0 when clean and 1 when violations exist,
and sorts diagnostics by rule and path.

- [ ] **Step 3: Run the new gate and capture the red inventory**

```bash
uv run pytest tests/test_final_architecture.py -v
uv run python scripts/check-final-architecture.py --root .
```

Expected: FAIL and list only known paths scheduled below. Add any newly found
path to a concrete deletion task before continuing.

- [ ] **Step 4: Commit the red final gate**

```bash
git add scripts/check-final-architecture.py tests/test_final_architecture.py tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py
git commit -m "test: define final architecture deletion gate"
```

### Task 2: Delete Mixed Core And Application Construction

**Files:**
- Delete: `src/embedagent/core/adapter.py`
- Delete: `src/embedagent/agent_applications.py`
- Delete: obsolete root runtime modules identified by Task 1
- Modify: root product bootstrap and configuration modules
- Modify: `packages/embedagent-host/src/embedagent_host/agent_application_registry.py`
- Modify: launcher entry points
- Modify: affected tests

- [ ] **Step 1: Replace remaining callers with final boundaries**

GUI launch uses the root-product `GuiHostPort` adapter over Host. CLI/TUI launch
use Host services over `Agent`. Product selection loads a compiled product
definition through the explicit frozen catalog. No caller constructs
`QueryEngine`, an extension manager, a workflow extension, or a tool runtime
outside Core/Host binding.

- [ ] **Step 2: Delete application records and string builders**

Remove `AgentApplicationRecord`, `AgentApplicationRegistry`, `profile_kind`,
`builder_path`, `_load_application_builder`, and package-owned compatibility
wrappers. Base profiles are trusted Host components; C/C++ is selected by the
compiled workflow component. Do not retain aliases for tests or config.

- [ ] **Step 3: Delete CoreInterface and adapter inheritance**

Remove `CoreInterface`, `FrontendCallbacks`, and `AgentCoreAdapter`. Hosted
frontends depend on narrow Host ports and the public Core SDK records. Delete
the old `embedagent.frontend` package after GUI extraction.

- [ ] **Step 4: Run product and facade tests**

```bash
uv run pytest tests/test_host_package_composition.py tests/test_host_agent_facade.py tests/test_inprocess_adapter_frontend_api.py tests/test_gui_app_host.py tests/test_final_architecture.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit mixed-path deletion**

```bash
git add -A src packages tests
git commit -m "refactor: delete mixed core and application paths"
```

### Task 3: Delete Protocol And State Compatibility Paths

**Files:**
- Delete: obsolete protocol serializers and v1 fixtures
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/`
- Modify: `packages/embedagent-gui/src/embedagent_gui/backend/protocol_payloads.py`
- Modify: `packages/embedagent-gui/src/embedagent_gui/webapp/src/session-runtime/protocol-normalizer.js`
- Modify: Host session projection code
- Modify: protocol, history, and restore tests

- [ ] **Step 1: Enforce one field spelling and one version**

Protocol v2 emits camelCase at the wire and uses snake_case only inside Python
objects. Remove camel-or-snake readers, v1 protocol ids, global capabilities,
`AgentApplicationDescriptor`, nested history turns, timeline reload formats,
workflow fallbacks, and generated command fallbacks.

- [ ] **Step 2: Remove internal state compatibility**

Delete old session/timeline/reducer projections already superseded by:

- transcript-backed session history;
- operation/config/compaction/recovery/turn-experience reducers;
- explicit session `workflow` read model;
- capability revision documents;
- ordered v2 live events.

Do not change restore trust-prefix rules or add migration readers for pre-release
state.

- [ ] **Step 3: Add malformed-state tests at the current boundary**

Keep tests for corrupt transcript tails, interrupted operations, malformed
protocol v2 documents, sequence gaps, and unknown capability values. Delete
tests whose only purpose is asserting a removed v1/legacy projection.

- [ ] **Step 4: Run protocol and state gates**

```bash
uv run pytest tests/test_session_restore.py tests/test_session_history.py tests/test_session_operation_log.py tests/test_gui_protocol_v2.py tests/test_gui_protocol_projection.py tests/test_gui_session_events.py -v
cd packages/embedagent-gui/src/embedagent_gui/webapp
npm test
cd ../../../../..
```

Expected: PASS.

- [ ] **Step 5: Commit compatibility deletion**

```bash
git add -A packages src tests
git commit -m "refactor: delete protocol and state compatibility"
```

### Task 4: Gate Product And Workflow Hardcoding

**Files:**
- Create: `scripts/check-product-hardcoding.py`
- Create: `tests/test_product_hardcoding.py`
- Modify: GUI/Host/Core source flagged by the checker
- Modify: `Makefile`

- [ ] **Step 1: Define owned vocabularies**

The checker allows C/C++ workflow terms, tool names, modes, task fields, recipe
names, and Clang assets only in:

- `packages/embedagent-workflow-cpp/`;
- `products/cpp-agent.json`;
- explicit C/C++ tests/fixtures;
- offline asset-contract records that genuinely package those binaries.

It rejects those terms in Core, Protocol, Host policy, GUI production source,
base product definitions, and base export metadata. It separately rejects
visible product-name defaults, `chat` workflow fallbacks, and `explore` mode
fallbacks in production runtime paths.

- [ ] **Step 2: Distinguish generic shell behavior from agent behavior**

The GUI may keep fixed implementations for files, diff, terminal, preview,
source control, settings, diagnostics, timeline, composer, and the six safe
declarative renderers. Availability, visible labels, commands, placement, and
agent data come from app/IDE/capability documents. The checker must not reject
generic renderer names merely because they are fixed GUI code.

- [ ] **Step 3: Remove every reported production hardcode**

Move legitimate metadata to its owning descriptor. Replace functional branches
with catalog metadata such as `rendererKey`, `previewArg`, `changedPathArg`,
`readModelInvalidations`, surface descriptors, and command dispatch records.
Delete dead branches rather than preserving default behavior.

- [ ] **Step 4: Run hardcoding and architecture gates**

```bash
uv run pytest tests/test_product_hardcoding.py tests/test_final_architecture.py -v
uv run python scripts/check-product-hardcoding.py --root .
uv run python scripts/check-final-architecture.py --root .
```

Expected: all commands exit zero.

- [ ] **Step 5: Commit hardcoding removal**

```bash
git add scripts tests packages src products Makefile
git commit -m "test: gate product-specific hardcoding"
```

### Task 5: Prove Isolated Wheels And Deterministic Products

**Files:**
- Modify: `scripts/check-python-distributions.py`
- Modify: `scripts/smoke-python-distributions.py`
- Modify: `scripts/smoke-exported-agent.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/exporters.py`
- Modify: export and distribution tests

- [ ] **Step 1: Build from a clean distribution directory**

```bash
uv build --all-packages --out-dir build/release-dist
uv run python scripts/check-python-distributions.py --dist-dir build/release-dist
uv run python scripts/smoke-python-distributions.py --dist-dir build/release-dist --python .venv/Scripts/python.exe
```

The smoke creates isolated environments for Core-only, Core+Host,
Core+C/C++ workflow, Protocol-only, GUI+Protocol with a fake port, Composition,
and the root product.
It installs with `--no-index` using only the built wheel directory.

- [ ] **Step 2: Export each product twice**

```bash
uv run python -m embedagent_composition export products/base-agent.json --wheel-dir build/release-dist --output build/release/base-a
uv run python -m embedagent_composition export products/base-agent.json --wheel-dir build/release-dist --output build/release/base-b
uv run python -m embedagent_composition export products/cpp-agent.json --wheel-dir build/release-dist --output build/release/cpp-a
uv run python -m embedagent_composition export products/cpp-agent.json --wheel-dir build/release-dist --output build/release/cpp-b
```

Compare definition, lock, wheel hash, runtime asset, and export report records.
Timestamps and staging paths must not enter canonical lock material.

- [ ] **Step 3: Run exported product smokes**

```bash
uv run python scripts/smoke-exported-agent.py build/release/base-a --expect-agent embedagent.base
uv run python scripts/smoke-exported-agent.py build/release/cpp-a --expect-agent embedagent.default_c_cpp
```

Base must run without GUI, C/C++ wheel, LLVM, Ctags, or workflow assets. C/C++
must use only bundle-local Python, Bash, MinGit, ripgrep, Ctags, and Clang.

- [ ] **Step 4: Verify full local gates**

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_final_architecture.py tests/test_product_hardcoding.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
cd packages/embedagent-gui/src/embedagent_gui/webapp
npm test
npm run build
cd ../../../../..
```

Expected: PASS and the generated static assets match the GUI wheel contents.

- [ ] **Step 5: Commit release automation**

```bash
git add scripts tests packages Makefile
git commit -m "build: verify independent agent products"
```

### Task 6: Record Windows 7 And WebView2 Target Evidence

**Files:**
- Create: `scripts/record-target-smoke.py`
- Create: `docs/release-evidence/README.md`
- Create: `docs/release-evidence/0.1.0/manifest.json`
- Modify: `scripts/offline-runtime-contract.json`
- Modify: `scripts/validate-offline-bundle.ps1`
- Modify: `scripts/check-bundle-dependencies.py`

- [ ] **Step 1: Define a credential-free evidence schema**

The evidence manifest records release version, git commit, bundle SHA-256,
machine/OS architecture, Windows 7 service pack, WebView2 version, timestamp,
tester identity label, each smoke id/status/duration, referenced log/screenshot
hashes, and failures. It never stores prompts, source contents, API keys,
tokens, approval secrets, or model responses.

- [ ] **Step 2: Validate the candidate before target transfer**

```powershell
./scripts/validate-offline-bundle.ps1 -BundlePath build/release/cpp-a
uv run python scripts/check-bundle-dependencies.py --bundle build/release/cpp-a
uv run python scripts/record-target-smoke.py prepare --bundle build/release/cpp-a --output build/target-smoke
```

Expected: asset contract, PE/import checks, wheel hashes, and bundle-local C
smoke all pass before copying the candidate.

- [ ] **Step 3: Run the clean Windows 7 matrix**

On Windows 7 SP1 with no preinstalled Python, Git, LLVM, ripgrep, Ctags, Node,
or developer tools:

1. unpack and launch offline;
2. open a local C workspace;
3. start and resume a session;
4. run read/search/edit permission flows;
5. run bundled C compile and validation;
6. run one C/C++ workflow task/recipe/quality flow;
7. restart and restore the session;
8. verify missing network does not break default operation;
9. verify no system executable is used;
10. capture process exit, logs, and screenshots.

- [ ] **Step 4: Run WebView2 109 GUI smoke**

Verify windowed startup, app/session/capability bootstraps, streaming, cancel,
permission and user-input interactions, files/diff/terminal/source-control
surfaces, base/C++ capability switching, reconnect, and clean shutdown. Record
the exact WebView2 runtime version and renderer console diagnostics.

- [ ] **Step 5: Finalize and verify evidence**

```bash
uv run python scripts/record-target-smoke.py finalize --input build/target-smoke --output docs/release-evidence/0.1.0/manifest.json
uv run python scripts/record-target-smoke.py verify docs/release-evidence/0.1.0/manifest.json
```

Do not mark the release candidate ready if any required target smoke is absent,
failed, refers to another bundle hash, or uses a non-Windows-7 machine.

- [ ] **Step 6: Commit target evidence metadata**

```bash
git add docs/release-evidence scripts/offline-runtime-contract.json scripts/record-target-smoke.py scripts/validate-offline-bundle.ps1 scripts/check-bundle-dependencies.py
git commit -m "test: record windows 7 release evidence"
```

### Task 7: Promote Final Architecture Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/modules/packaging-and-deployment.md`
- Modify: `docs/adrs/0001-offline-portable-bundle-baseline.md`
- Archive completed superseded planning documents as directed by project policy

- [ ] **Step 1: Make the final vocabulary authoritative**

Document package dependencies, public `Agent` API, functional runner, frozen
composition, C/C++ workflow ownership, four GUI protocols, safe renderer
boundary, two product exports, and target evidence process. Remove text that
describes deleted paths as active.

- [ ] **Step 2: Run the complete final gate from a clean worktree**

```bash
uv sync
uv run python scripts/generate-gui-protocol.py --check
uv run python scripts/check-final-architecture.py --root .
uv run python scripts/check-product-hardcoding.py --root .
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_final_architecture.py tests/test_product_hardcoding.py -v
uv run pytest tests/ -v
uv run --locked python scripts/lint.py
uv build --all-packages --out-dir build/release-dist
uv run python scripts/check-python-distributions.py --dist-dir build/release-dist
```

Run from `packages/embedagent-gui/src/embedagent_gui/webapp`:

```bash
npm test
npm run build
```

Expected: all commands exit zero.

- [ ] **Step 3: Verify repository cleanliness and release evidence**

```bash
git status --short
uv run python scripts/record-target-smoke.py verify docs/release-evidence/0.1.0/manifest.json
```

Expected: only intentionally committed generated GUI assets/evidence metadata
exist, working tree is clean, and the evidence references the final bundle
hash.

- [ ] **Step 4: Commit final documentation**

```bash
git add README.md AGENTS.md docs
git commit -m "docs: promote independent agent architecture"
```

## Program Exit Criteria

- Core, Protocol, Host, C/C++ Workflow, Composition, and GUI wheels pass
  isolated Python 3.8 installation.
- Root product code is composition/bootstrap only.
- No retired compatibility path or public name remains.
- Base and C/C++ product locks and exports are reproducible.
- Base export has no C/C++ behavior or assets.
- GUI uses the same build for base, C/C++, and non-C agents.
- All local Python, GUI, architecture, distribution, and bundle gates pass.
- Clean Windows 7 SP1 and WebView2 109 evidence matches the final bundle hash.
