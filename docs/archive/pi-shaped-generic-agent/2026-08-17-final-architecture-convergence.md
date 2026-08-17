# Final Architecture Convergence And Technical Debt Removal

> **For agentic workers:** use `superpowers:subagent-driven-development` or `superpowers:executing-plans` when executing this plan. Keep each checkbox slice green before moving to the next slice.

## Objective

Finish the Pi-shaped generic Agent architecture in one deliberate convergence phase. The exported generic Agent must be workflow-neutral, include a usable generic shell, and run without the C/C++ workflow package. C/C++ must be an explicitly selected application/workflow plugin that can later move to an independent repository. Remove retired internal shapes instead of adding compatibility aliases.

This plan supersedes the unfinished portions of `docs/superpowers/plans/2026-08-17-generic-agent-application-plugin-closure-export.md`. That plan remains useful as implementation history until this plan is accepted; after acceptance, its completed slice is archived and its remaining checkboxes are closed here rather than extended indefinitely.

## Current Gaps To Close

1. `src/embedagent/application_loader.py` defines loading behavior but is not the production bootstrap path. Normal runtime still relies on product-side registration.
2. `src/embedagent/product_catalog.py` still contains the lazy C/C++ application record and imports workflow-owned policy from the product.
3. Core, Host, CLI, and TUI still carry `default_mode`, profile runtime policy, mode tool policy, mode writable-path policy, or other platform-level workflow assumptions.
4. `ContextManager` still selects `WorkspaceIntelligenceBroker.default()` when no broker is injected, so generic Host is not genuinely empty by default.
5. Application capability projection exists, but frontend and shell paths still synthesize or assume mode-related state in some branches.
6. Packaging and documentation describe the selected closure in some places but still contain fixed-six-wheel, implicit-registration, or stale-status language in others.
7. Release identity and smoke tooling need to prove both selected closures, while real Windows 7 and C/C++ evidence remains an external gate.

## Target Shape

```
compiled bundle plan
        |
        v
generic product bootstrap ----> selected application registration entries
        |                                      |
        v                                      v
generic CLI/TUI/GUI shell       ApplicationRegistrar / focused ports
        |                                      |
        +--------------------------> Host runtime
                                           |
                                           v
                                  workflow-neutral Core

cpp-desktop plan additionally selects:
embedagent-workflow-cpp -> C/C++ application contributions, tools, policies, packs, shell capabilities
```

The runtime must never discover unselected distributions, and the composition compiler remains build-time only. The product owns launch configuration and generic shell bootstrap. Applications own prompt/context/tool/capability contributions. Workflow packages own workflow semantics. Core owns session transactions, event durability, kernel/loop execution, and focused ports. Permission and writable-path authorization remain separate decisions.

## Sequencing And Commit Boundaries

The work is split into three execution slices with a small preflight. Slice 1 establishes the runtime ownership boundary. Slice 2 removes platform mode/profile debt from Core and Host. Slice 3 removes shell assumptions and closes packaging, documentation, and release evidence. Do not start a later slice while the earlier slice's architecture guards are red.

Each slice should use focused TDD commits. Do not batch unrelated formatting, GUI asset regeneration, or migration aliases into these commits. Preserve the existing user edits in `src/embedagent/frontend/gui/static/assets/app.css` and `src/embedagent/frontend/gui/static/assets/app.js`.

## Preflight: Freeze The Debt Inventory

**Files:**

- Create: `tests/test_final_architecture_guards.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Read only: `docs/adrs/0008-generic-agent-application-plugin-closure-export.md`

### Step 1: Add failing guards

Add tests with stable names and failure messages:

```python
def test_generic_bootstrap_uses_selected_application_loader(): ...
def test_product_catalog_has_no_cpp_application_record(): ...
def test_core_public_api_has_no_mode_or_profile_symbols(): ...
def test_context_manager_has_no_implicit_workspace_intelligence(): ...
def test_generic_plan_is_not_a_cpp_or_composition_runtime_closure(): ...
```

Run:

```bash
uv run pytest tests/test_final_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_pre_release_architecture_guards.py -q
```

Expected result: the new guards identify the known gaps above.

### Step 2: Record the baseline

Capture the failing guard names and current plan identities in the implementation handoff. Do not add a completion diary to an active authority document. The baseline is evidence for the first slice only.

## Slice 1: Make Application Composition Real At Runtime

**Purpose:** make selected application registration the only runtime path and remove product ownership of C/C++ behavior.

**Files:**

- Modify: `src/embedagent/application_loader.py`
- Modify: `src/embedagent/product_catalog.py`
- Modify: `src/embedagent/bundle_catalog.py`
- Modify: `src/embedagent/hosted.py`
- Modify: `src/embedagent/config.py`
- Modify: `src/embedagent/frontend/shell/registration.py`
- Modify: `src/embedagent/frontend/shell/compiler.py`
- Modify: `src/embedagent/frontend/shell/defaults.py`
- Modify: `src/embedagent/cli/app.py`
- Modify: `packages/embedagent-core/src/embedagent_core/extensions.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/__init__.py`
- Create or modify: `tests/test_generic_shell_bootstrap.py`
- Modify: `tests/test_product_host_composition.py`
- Modify: `tests/test_cpp_application_registration.py`

### Step 1: Test the selected loader before implementation

Extend the shared fixtures in `tests/agent_runtime_test_helpers.py` and add tests that:

- load only registration entries listed in the compiled plan;
- reject a missing, malformed, mismatched, or duplicate registration entry with `application_registration_error`;
- dispose registrations in reverse order and make repeated disposal harmless;
- prove that a generic bootstrap imports neither `embedagent_workflow_cpp` nor `embedagent_composition`;
- prove that a C++ plan imports the workflow registration entry exactly once.

Run:

```bash
uv run pytest tests/test_generic_shell_bootstrap.py tests/test_product_host_composition.py tests/test_cpp_application_registration.py -q
```

### Step 2: Wire `load_selected_applications` into production bootstrap

Implement the production call chain as:

```
bundle plan -> selected registration entries -> ApplicationRegistrar -> Host and shell construction
```

`load_selected_applications` must validate the entry against the plan lock before importing it, import only the selected module, call `register_application(registrar)`, retain the disposer stack, and expose no service dictionary or mutable Core session. Keep source-aware extension registration and idempotent disposal.

### Step 3: Make the product catalog generic-only

Remove `default_c_cpp_application_record` and all direct C++ imports from `src/embedagent/product_catalog.py`. The generic product record may describe only the generic shell and workflow-neutral tools. `hosted.py` must receive the selected application registry produced by the plan rather than calling an unconditional product registry. Runtime bootstrap must not import `embedagent_composition`.

### Step 4: Move C++ ownership fully into the workflow package

`embedagent_workflow_cpp.application` must register the C++ application manifest, prompt/context providers, C/C++ tools, task projection, shell contributions, and workflow-specific policies. It must not import `embedagent.product_catalog`, `embedagent.hosted`, or `embedagent_composition`. Product code may know the registration entry only through the selected bundle plan.

### Step 5: Verify the slice and commit

Run:

```bash
uv run pytest tests/test_final_architecture_guards.py tests/test_generic_shell_bootstrap.py tests/test_product_host_composition.py tests/test_cpp_application_registration.py tests/test_cpp_workflow_distribution.py -q
```

Commit boundary:

```bash
git add src/embedagent packages/embedagent-core packages/embedagent-workflow-cpp tests
git commit -m "refactor: load selected applications through runtime composition"
```

Acceptance: generic runtime has no C++ or composition import; C++ behavior is reachable only through an explicit selected registration entry; registration disposal is idempotent.

## Slice 2: Remove Mode And Profile Debt From Core And Host

**Purpose:** make the lower platform workflow-neutral rather than a generic runtime with hidden mode defaults.

**Files:**

- Delete: `packages/embedagent-core/src/embedagent_core/profile.py`
- Delete: `packages/embedagent-core/src/embedagent_core/profile_runtime.py`
- Delete: `src/embedagent/modes.py`
- Modify: `packages/embedagent-core/src/embedagent_core/api.py`
- Modify: `packages/embedagent-core/src/embedagent_core/runtime_config.py`
- Modify: `packages/embedagent-core/src/embedagent_core/session_input.py`
- Modify: `packages/embedagent-core/src/embedagent_core/session_transaction.py`
- Modify: `packages/embedagent-core/src/embedagent_core/hosting.py`
- Modify: `packages/embedagent-core/src/embedagent_core/__init__.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/profiles.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/workspace_intelligence.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted/runtime.py`
- Modify: `src/embedagent/config.py`
- Modify: `src/embedagent/hosted.py`
- Modify: `src/embedagent/cli/run.py`
- Modify: `src/embedagent/cli/chat.py`
- Modify: `tests/test_agent_profiles.py`
- Modify: `tests/test_modes.py`
- Modify: `tests/test_workspace_profile.py`
- Modify: `tests/test_agent_runtime_integration.py`
- Modify: `tests/test_agent_core_public_api.py`

### Step 1: Add mode-free failing tests

Add or replace tests with these contracts:

```python
def test_runtime_definition_has_no_platform_mode_or_profile_fields(): ...
def test_empty_session_starts_with_empty_generic_workflow_state(): ...
def test_host_workspace_intelligence_is_empty_without_application_injection(): ...
def test_permission_and_writable_path_policies_remain_independent(): ...
```

Run the focused profile, mode, Core, and Host tests before implementation. The expected failures identify all callers that must be migrated; do not add aliases for the deleted names.

### Step 2: Remove the Core profile path

Delete `AgentModeDescriptor`, `AgentProfile`, `AgentProfileRuntimePolicy`, `AgentProfileToolPolicy`, and `AgentProfileWritePathPolicy` from Core exports and runtime construction. Remove `default_mode`, mode runtime policy, mode tool policy, and mode writable-path policy from `RuntimeDefinition` and `ApplicationRuntimePolicy`. Session transaction and reducer input must carry generic workflow state only; application-specific state remains under `Session.workflow_state`.

### Step 3: Make Host defaults explicit

Change `WorkspaceIntelligenceBroker` and `ContextManager` so an omitted broker means no providers. Remove `ContextManager`'s call to `.default()`. Generic file/project context must be injected by the selected generic application, while Ctags, recipes, diagnostics, LLVM, and similar providers are injected by the C++ application. Keep the provider port focused and immutable at the Host boundary.

### Step 4: Move prompt and write-path policy to applications

Make prompt assembly consume application-provided prompt units and active tool names. Keep `PermissionPolicy` and `DenyWritePathPolicy` as independent collaborators. No mode or application manifest may grant permission. Remove mode fields from `AppConfig` and replace implicit behavior with an explicit application runtime definition or focused port.

### Step 5: Remove CLI/TUI default mode assumptions

Delete `DEFAULT_MODE`, `_default_mode`, mode fallback branches, and `build_system_prompt` calls that assume a platform mode. CLI `run`, `chat`, and `sessions` continue to work with the selected application, but absent application capabilities must remain absent.

### Step 6: Verify the slice and commit

Run:

```bash
uv run pytest tests/test_agent_core_public_api.py tests/test_agent_effect_kernel.py tests/test_agent_loop_driver.py tests/test_session_reducer_restore.py tests/test_host_package_composition.py tests/test_agent_profiles.py tests/test_modes.py tests/test_workspace_profile.py tests/test_agent_runtime_integration.py tests/test_final_architecture_guards.py -q
```

Commit boundary:

```bash
git add packages/embedagent-core packages/embedagent-host src/embedagent tests
git commit -m "refactor: remove platform modes and implicit workflow defaults"
```

Acceptance: Core and Host no longer export or construct mode/profile objects; a generic session has no synthesized mode; an unconfigured Host has no workspace intelligence providers.

## Slice 3: Capability-Driven Shell, Closure-Based Delivery, And Debt Closure

**Purpose:** remove remaining frontend assumptions and make code, packaging, docs, and release evidence agree with the final boundary.

### Part A: Optional capability projection

**Files:**

- Modify: `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/frontend_ports.py`
- Modify: `src/embedagent/frontend/shell/registration.py`
- Modify: `src/embedagent/frontend/shell/compiler.py`
- Modify: `src/embedagent/frontend/tui/app.py`
- Modify: `src/embedagent/frontend/tui/controller.py`
- Modify: `src/embedagent/frontend/tui/state.py`
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_sessions.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/mode-style.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/shell/SessionComposer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/shell/SessionStatusFooter.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-capability-model.js`
- Modify: `tests/test_agent_app_protocol.py`
- Modify: `tests/test_minimal_shell_contract.py`
- Modify: `tests/test_gui_protocol_projection.py`
- Modify: `tests/test_tui_runtime.py`

Add tests that application descriptors are JSON-safe data only, generic descriptors do not synthesize modes, and C++ mode controls appear only when the C++ capability projection is active. Make shell compilation merge generic contributions plus active source ids. Absent capability means no selector, badge, command, or default label. Preserve the canonical `SessionEventEnvelope` and ordered frontend event queue.

Run:

```bash
uv run pytest tests/test_agent_app_protocol.py tests/test_minimal_shell_contract.py tests/test_gui_protocol_projection.py tests/test_tui_runtime.py -q
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../..
```

Commit boundary:

```bash
git add packages/embedagent-protocol src/embedagent/frontend tests
git commit -m "refactor: render shell behavior from selected capabilities"
```

Regenerate static GUI assets only when source changes require it. Do not overwrite unrelated user edits.

### Part B: Plan-driven distribution and release closure

**Files:**

- Modify: `pyproject.toml`
- Modify: `scripts/build-python-distributions.py`
- Modify: `scripts/check-python-distributions.py`
- Modify: `scripts/smoke-python-distributions.py`
- Modify: `scripts/export-dependencies.py`
- Modify: `scripts/check-bundle-dependencies.py`
- Modify: `scripts/package-lib.ps1`
- Modify: `scripts/build-offline-bundle.ps1`
- Modify: `scripts/prepare-offline.ps1`
- Modify: `scripts/validate-offline-bundle.ps1`
- Modify: `scripts/offline-runtime-contract.json`
- Modify: `scripts/validate-cli-smoke.py`
- Modify: `scripts/validate-cpp-smoke.py`
- Modify: `scripts/create-release-identity.py`
- Modify: `scripts/release_identity.py`
- Modify: `tests/test_python_distribution_contract.py`
- Modify: `tests/test_python_distribution_smoke.py`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_release_identity.py`
- Modify: `tests/test_release_reproducibility.py`
- Modify: `tests/test_release_evidence.py`

Use the compiled plan as the only source for `project_distribution_ids`, registration entries, runtime capabilities, assets, and gates. Release-oriented build/check/smoke commands must accept a selected plan and fail closed for missing, unexpected, duplicated, or unplanned wheels. The generic plan must omit C++/LLVM assets and workflow imports; the C++ plan must add them only through the selected workflow distribution. Keep the composition compiler build-only and out of the generic runtime closure.

Required focused tests:

```python
def test_generic_release_identity_excludes_cpp_and_llvm(): ...
def test_cpp_release_identity_requires_cpp_smoke_gate(): ...
def test_checker_rejects_unplanned_project_wheel(): ...
def test_smoke_runner_uses_the_selected_plan_closure(): ...
```

Run:

```bash
uv run pytest tests/test_python_distribution_contract.py tests/test_python_distribution_smoke.py tests/test_packaging_control_plane.py tests/test_release_identity.py tests/test_release_reproducibility.py tests/test_release_evidence.py -q
```

Commit boundary:

```bash
git add pyproject.toml scripts tests
git commit -m "refactor: make delivery gates consume selected closures"
```

### Part C: Publish the final architecture and archive stale slices

**Files:**

- Create: `docs/adrs/0009-final-runtime-application-convergence.md`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/platform/agent-core.md`
- Modify: `docs/platform/tools-and-extensions.md`
- Modify: `docs/platform/frontend-protocol.md`
- Modify: `docs/product/composition.md`
- Modify: `docs/product/packaging-and-deployment.md`
- Modify: `docs/guides/application-plugin-authoring.md`
- Modify: `docs/guides/win7-release-runbook.md`
- Modify: `docs/references/code-doc-matrix.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/superpowers/README.md`
- Create or modify: `docs/archive/pi-shaped-generic-agent/README.md`

ADR-0009 must state the final ownership model, selected-closure distribution rule, explicit registration lifecycle, absence of mode/profile compatibility scaffolding, and the future independent-repository boundary for C/C++. Update active authorities in place. Replace stale fixed-six-wheel and implicit-registration claims; do not duplicate architecture detail in entry files. Move the completed generic-plugin plan, report, and handoff into an indexed archive only after all acceptance tests pass. Keep external Win7 evidence listed as a release blocker until validated.

Commit boundary:

```bash
git add AGENTS.md README.md docs
git commit -m "docs: publish final runtime convergence architecture"
```

## Final Verification Matrix

Run all of the following from a clean Python 3.8 environment after the slice commits:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run --locked python scripts/lint.py
uv run python scripts/build-python-distributions.py --dist-dir dist --bundle-plan build/plans/minimal-cli.json
uv run python scripts/check-python-distributions.py --dist-dir dist --bundle-plan build/plans/minimal-cli.json
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe --bundle-plan build/plans/minimal-cli.json
uv run python scripts/build-python-distributions.py --dist-dir dist-cpp --bundle-plan build/plans/cpp-desktop.json
uv run python scripts/check-python-distributions.py --dist-dir dist-cpp --bundle-plan build/plans/cpp-desktop.json
uv run python scripts/smoke-python-distributions.py --dist-dir dist-cpp --python .venv/Scripts/python.exe --bundle-plan build/plans/cpp-desktop.json
```

When frontend sources changed:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../..
```

Run the product gates:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release
```

Do not claim release acceptance from local results alone. `minimal-cli` still requires clean-machine Windows 7 SP1 x64 evidence. `cpp-desktop` additionally requires bundle-local C/C++ smoke and WebView2 evidence. Evidence must match the selected plan, release identity, lock hash, and exact gate set.

## Exit Conditions

- Generic shell starts with Core/Protocol/Host/Shell only and no C++ or composition runtime import.
- C++ is activated only by an explicit selected application registration entry and has no product or Host ownership of workflow semantics.
- Core and Host contain no mode/profile/default-workflow compatibility path.
- Empty generic Host has no implicit workspace intelligence providers.
- Frontends render only selected capabilities and preserve the canonical event protocol.
- Packaging, lock, identity, smoke, and release scripts all consume the same compiled closure.
- Active docs and `AGENTS.md` describe the final architecture and no retired fixed-six-wheel contract.
- Focused tests, full Python partition, lint, frontend tests/build, selected generic/C++ distribution checks, and local release gates pass.
- Windows 7 and real C/C++ acceptance remain explicitly tracked external gates until their evidence validators report `ACCEPTED`.
- No compatibility aliases, duplicate truth sources, runtime dependency installation, remote registry, or unrelated GUI asset churn is introduced.
