# Generic Agent Application Plugin And Closure Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 EmbedAgent 实现为可由配置导出的通用 Agent（带通用 CLI shell），并把 C/C++ workflow 改造成通过显式 application plugin 选择的可独立建库能力。

**Architecture:** 保留现有 Core 的 AgentSession、journal/reducer、kernel/loop、permission 和 extension bus。新增静态 application manifest + 显式 registration entry + 可逆 disposer 契约；构建期 compiler 根据选定 application/plugin 的依赖闭包生成唯一 bundle plan，运行时只加载该 plan 选择的 distribution、runtime capability、asset 和 shell。`embedagent` 的运行时职责收敛为通用 shell/bootstrap，C/C++ 的 mode、prompt、TaskGraph、workspace intelligence、Clang/LLVM 和 shell contribution 全部由 C++ application plugin 拥有。

**Tech Stack:** Python 3.8、setuptools/uv workspace、pytest、PowerShell 离线打包脚本、现有 JSON-safe protocol、GUI webapp 的 Node build/test（仅构建期）。

---

## Task 1: Freeze Application Manifest And Registration Contracts

**Files:**
- Create: `packages/embedagent-composition/src/embedagent_composition/application.py`
- Create: `packages/embedagent-core/src/embedagent_core/application.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/model.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/catalog.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/__init__.py`
- Modify: `packages/embedagent-core/src/embedagent_core/extensions.py`
- Modify: `packages/embedagent-core/src/embedagent_core/__init__.py`
- Create: `tests/test_application_plugin_contract.py`
- Modify: `tests/agent_runtime_test_helpers.py`

The first test file must define the reusable fixture exactly once:

```python
def _manifest(**overrides):
    values = {
        "application_id": "app.generic",
        "version": "0.1.0",
        "api_version": "agent_application_v1",
        "distribution_id": "embedagent-shell",
        "registration_entry": "embedagent.generic_application:register_application",
    }
    values.update(overrides)
    return ApplicationManifest(**values)


class RecordingApplicationRegistrar(object):
    def __init__(self):
        self.source_ids = []
        self.active_source_ids = []

    def add_extension(self, extension, source_id):
        self.source_ids.append(source_id)
        self.active_source_ids.append(source_id)
        return lambda: self.active_source_ids.remove(source_id)

    def add_prompt_provider(self, provider, source_id):
        return self.add_extension(provider, source_id)

    def add_context_provider(self, provider, source_id):
        return self.add_extension(provider, source_id)

    def add_shell_contribution(self, contribution, source_id):
        return self.add_extension(contribution, source_id)

    def dispose(self):
        self.active_source_ids[:] = []
```

- [x] **Step 1: Write failing manifest validation tests**

```python
def test_application_manifest_requires_explicit_registration_entry():
    manifest = ApplicationManifest(
        application_id="app.generic",
        version="0.1.0",
        api_version="agent_application_v1",
        distribution_id="embedagent-shell",
        registration_entry="",
    )
    with pytest.raises(CompositionError, match="registration_entry"):
        validate_application_manifest(manifest)


def test_registration_entry_must_be_module_colon_symbol():
    manifest = _manifest(registration_entry="../unsafe.py")
    with pytest.raises(CompositionError, match="registration_entry"):
        validate_application_manifest(manifest)


def test_closure_does_not_grant_permission_from_manifest():
    manifest = _manifest(capabilities=("tool.write_file",), permission_categories=("write",))
    assert manifest.to_dict()["permission_categories"] == ["write"]
    assert "permission_grant" not in manifest.to_dict()
```

Run: `uv run pytest tests/test_application_plugin_contract.py -q`

Expected: FAIL because `ApplicationManifest`, `validate_application_manifest`, and the source-aware registration API do not exist.

- [x] **Step 2: Add the build-time manifest model**

Implement `ApplicationManifest` in `embedagent_composition.application` with these immutable fields:

```python
@dataclass(frozen=True)
class ApplicationManifest:
    application_id: str
    version: str
    api_version: str
    distribution_id: str
    registration_entry: str
    requires: Tuple[str, ...] = ()
    conflicts: Tuple[str, ...] = ()
    capabilities: Tuple[str, ...] = ()
    permission_categories: Tuple[str, ...] = ()
    prompt_resources: Tuple[str, ...] = ()
    toolset_ids: Tuple[str, ...] = ()
    context_provider_ids: Tuple[str, ...] = ()
    workflow_state_namespace: str = ""
    shell_contribution_ids: Tuple[str, ...] = ()
    runtime_requirements: Tuple[str, ...] = ()
    asset_ids: Tuple[str, ...] = ()
```

`validate_application_manifest` must reject empty ids, duplicate tuple values, unsafe registration paths, invalid runtime requirement ids, and an empty distribution owner. `to_dict()` must emit stable JSON-safe keys sorted by the existing canonical serializer.

Add a matching immutable `DistributionManifest(distribution_id, version, import_root,
runtime_only=True)` record. The catalog owns distribution records separately from application
records so the compiler can project selected component owners without making the composition
compiler a runtime dependency.

- [x] **Step 3: Add the runtime registrar without a general service bag**

Implement `ApplicationRegistrar` in Core with focused methods only:

```python
class ApplicationRegistrar(object):
    def __init__(self, extension_host, shell_registry):
        self._extension_host = extension_host
        self._shell_registry = shell_registry
        self._disposers = []

    def add_extension(self, extension, source_id):
        self._disposers.append(self._extension_host.register(extension, source_id))

    def add_prompt_provider(self, provider, source_id):
        self._disposers.append(self._extension_host.register_prompt_provider(provider, source_id))

    def add_context_provider(self, provider, source_id):
        self._disposers.append(self._extension_host.register_context_provider(provider, source_id))

    def add_shell_contribution(self, contribution, source_id):
        self._disposers.append(self._shell_registry.register(contribution, source_id))

    def dispose(self):
        while self._disposers:
            self._disposers.pop()()
```

Each method must validate the source id, delegate capability registration to `AgentExtensionHost`/`ExtensionManager`, and retain a disposer. `dispose()` must be idempotent and unwind registrations in reverse order. It must never expose the mutable Core `Session`, permission decisions, or a generic dictionary of services.

- [x] **Step 4: Export the contract and run focused tests**

Export `ApplicationManifest`, `validate_application_manifest`, and `ApplicationRegistrar` from their package `__init__.py` files. Run:

```bash
uv run pytest tests/test_application_plugin_contract.py tests/test_capability_extensions.py -q
```

Expected: all new contract tests pass and existing extension tests remain green.

- [x] **Step 5: Commit the contract boundary**

```bash
git add packages/embedagent-composition packages/embedagent-core tests/test_application_plugin_contract.py
git commit -m "feat: define application plugin registration contract"
```

## Task 2: Replace Fixed Six-Wheel Composition With Closure-Derived Plans

**Files:**
- Modify: `packages/embedagent-composition/src/embedagent_composition/model.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/catalog.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/compiler.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/definitions.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/bundle.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/export.py`
- Modify: `packages/embedagent-composition/src/embedagent_composition/__init__.py`
- Modify: `src/embedagent/bundle_catalog.py`
- Modify: `tests/test_bundle_plan.py`
- Modify: `tests/test_product_bundle_recipes.py`
- Create: `tests/test_selected_distribution_closure.py`

Add the plan helper to `tests/agent_runtime_test_helpers.py` so all later test modules use the same repository-owned manifests. The helper is deterministic:

```python
import json
from pathlib import Path

from embedagent_composition import compile_bundle_plan
from embedagent.bundle_catalog import official_bundle_recipe_registry, product_component_catalog

ROOT = Path(__file__).resolve().parents[1]


def compile_bundle_plan_for(flavor, target_id="win7-x64-portable", assurance="dev"):
    recipe = official_bundle_recipe_registry().resolve(flavor)
    return compile_bundle_plan(
        recipe=recipe,
        catalog=product_component_catalog(),
        runtime_contract=json.loads((ROOT / "scripts/offline-runtime-contract.json").read_text()),
        asset_manifest=json.loads((ROOT / "scripts/offline-assets.json").read_text()),
        target_id=target_id,
        assurance=assurance,
    )
```

- [x] **Step 1: Write failing closure tests**

```python
def test_generic_plan_contains_no_cpp_distribution_or_composition_runtime():
    plan = compile_bundle_plan_for("minimal-cli", target_id="win7-x64", assurance="dev")
    assert "embedagent-workflow-cpp" not in plan.project_distribution_ids
    assert "embedagent-shell" in plan.project_distribution_ids
    assert "embedagent-composition" not in plan.project_distribution_ids


def test_cpp_plan_adds_only_selected_workflow_distribution_and_assets():
    plan = compile_bundle_plan_for("cpp-desktop", target_id="win7-x64", assurance="dev")
    assert "embedagent-workflow-cpp" in plan.project_distribution_ids
    assert "toolchain.clang" in plan.runtime_capability_ids
    assert "symbols.ctags" in plan.runtime_capability_ids


def test_distribution_owner_is_derived_from_selected_components():
    plan = compile_bundle_plan_for("minimal-cli", target_id="win7-x64", assurance="dev")
    catalog = product_component_catalog()
    assert set(plan.project_distribution_ids) == set(
        catalog.manifest(component_id).distribution_id for component_id in plan.component_ids
    )
```

Run: `uv run pytest tests/test_selected_distribution_closure.py tests/test_bundle_plan.py -q`

Expected: FAIL because `PORTABLE_PROJECT_DISTRIBUTIONS` still overrides the selected component closure.

- [x] **Step 2: Add distribution ownership to component manifests**

Extend `ComponentManifest` with `distribution_id` and optional `registration_entry`. Require every runtime component to name its owning distribution. Make catalog freezing reject a component whose owner is not in the catalog's distribution records and reject an application registration entry that is not represented in the selected component.

- [x] **Step 3: Remove the fixed distribution constant**

Delete `PORTABLE_PROJECT_DISTRIBUTIONS` from `embedagent_composition.bundle`. In `compile_bundle_plan`, compute `project_distribution_ids` by preserving the dependency order of selected components and projecting each component's `distribution_id`; deduplicate while retaining first appearance. Do not add `embedagent-composition` unless a build-only command explicitly requests compiler tooling.

- [x] **Step 4: Bind lock, manifest, and plan hashes to the same closure**

Add `registration_entries` to `CompiledBundlePlan.to_dict()` while keeping the existing `project_distribution_ids` field as the single canonical wheel set. Make `export.py` write both values into `agent.lock.json` and make every hash use the same canonical plan payload. Reject a wheel manifest when its project wheel set differs from `plan.project_distribution_ids`.

- [x] **Step 5: Run composition tests and commit**

```bash
uv run pytest tests/test_selected_distribution_closure.py tests/test_bundle_plan.py tests/test_product_bundle_recipes.py -q
git add packages/embedagent-composition src/embedagent/bundle_catalog.py tests/test_selected_distribution_closure.py tests/test_bundle_plan.py tests/test_product_bundle_recipes.py
git commit -m "refactor: derive bundle distributions from selected closure"
```

## Task 3: Make Packaging And Offline Validation Plan-Driven

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
- Modify: `tests/test_python_distribution_contract.py`
- Modify: `tests/test_python_distribution_smoke.py`
- Modify: `tests/test_packaging_control_plane.py`
- Modify: `tests/test_phase7_bundle_dependency_contract.py`

The packaging tests must import `build_report`, `scenario_wheels`, and the selected-plan loader from the scripts under test rather than creating a second wheel allowlist.

- [ ] **Step 1: Write failing plan-aware packaging tests**

```python
def test_checker_accepts_selected_generic_wheel_set(tmp_path):
    report = build_report(tmp_path, selected_distributions=(
        "embedagent-core", "embedagent-protocol", "embedagent-host", "embedagent-shell",
    ))
    assert report["ok"] is True
    assert "embedagent-workflow-cpp" not in report["verified_wheels"]


def test_smoke_runner_rejects_unplanned_project_wheel():
    with pytest.raises(ValueError, match="unplanned distribution"):
        scenario_wheels(
            ("embedagent-core", "embedagent-workflow-cpp"),
            compile_bundle_plan_for("minimal-cli"),
        )
```

Run: `uv run pytest tests/test_python_distribution_contract.py tests/test_python_distribution_smoke.py -q`

Expected: FAIL because the scripts currently require exactly six wheels.

- [ ] **Step 2: Remove the product's workflow dependency and rename its distribution**

Change the root `[project]` name to `embedagent-shell`, remove `embedagent-composition` and `embedagent-workflow-cpp` from runtime dependencies, and keep the import package `embedagent` and console script `embedagent` unchanged. Keep all workspace members buildable for CI, but do not expose workflow C++ in the shell wheel metadata.

- [ ] **Step 3: Add selected-plan arguments to build/check/smoke scripts**

Add a required `--bundle-plan` option to release-oriented invocations. Load `project_distribution_ids` from the plan, filter wheels by normalized distribution name, and fail closed when a wheel is missing, unexpected, duplicated, or present outside the selected closure. Keep the standalone Core and Protocol isolation probes; replace the fixed product scenario with a plan-derived scenario that imports only selected packages.

- [ ] **Step 4: Select runtime assets from the same plan**

Change `managed_runtime_tools`, launcher checks, release-gate checks, and Python feature checks to receive the compiled plan. `offline-runtime-contract.json` remains the catalog of possible assets; `runtime_component_ids`, `asset_ids`, and `gate_ids` in the plan select the subset. Generic bundles keep only Python/MinGit/Bash/ripgrep and generic shell assets; C++ bundles add Ctags/LLVM and C++ gates.

- [ ] **Step 5: Run packaging unit tests and commit**

```bash
uv run pytest tests/test_python_distribution_contract.py tests/test_python_distribution_smoke.py tests/test_packaging_control_plane.py tests/test_phase7_bundle_dependency_contract.py -q
git add pyproject.toml scripts tests/test_python_distribution_contract.py tests/test_python_distribution_smoke.py tests/test_packaging_control_plane.py tests/test_phase7_bundle_dependency_contract.py
git commit -m "refactor: make offline packaging consume compiled bundle plans"
```

## Task 4: Convert Product Bootstrap Into A Generic Shell Loader

**Files:**
- Create: `src/embedagent/application_loader.py`
- Modify: `src/embedagent/product_catalog.py`
- Modify: `src/embedagent/bundle_catalog.py`
- Modify: `src/embedagent/hosted.py`
- Modify: `src/embedagent/config.py`
- Modify: `src/embedagent/frontend/shell/registration.py`
- Modify: `src/embedagent/frontend/shell/compiler.py`
- Modify: `src/embedagent/frontend/shell/defaults.py`
- Modify: `src/embedagent/cli/app.py`
- Modify: `src/embedagent/cli/parser.py`
- Modify: `src/embedagent/cli/run.py`
- Modify: `src/embedagent/cli/chat.py`
- Modify: `tests/test_product_host_composition.py`
- Modify: `tests/test_minimal_shell_contract.py`
- Create: `tests/test_generic_shell_bootstrap.py`

The shell test module reuses `RecordingApplicationRegistrar` from `tests/test_application_plugin_contract.py` through a test helper module, and loads the generic plan with `compile_bundle_plan_for("minimal-cli")`.

- [ ] **Step 1: Write the generic shell isolation test**

```python
def test_generic_shell_bootstrap_does_not_import_cpp_or_composition(monkeypatch):
    imported = []
    real_import = builtins.__import__

    def tracking_import(name, *args, **kwargs):
        imported.append(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", tracking_import)
    bootstrap_generic_shell(
        compile_bundle_plan_for("minimal-cli"),
        registrar=RecordingApplicationRegistrar(),
    )
    assert not any(name.startswith("embedagent_workflow_cpp") for name in imported)
    assert not any(name.startswith("embedagent_composition") for name in imported)


def test_generic_shell_has_no_synthesized_mode_capability():
    descriptor = compile_generic_shell_descriptor(
        compile_bundle_plan_for("minimal-cli"), session_capabilities={}
    )
    assert not any(item.id.startswith("mode.") for item in descriptor.commands)
```

Run: `uv run pytest tests/test_generic_shell_bootstrap.py tests/test_minimal_shell_contract.py -q`

Expected: FAIL because `product_catalog.py` imports the C++ package at module import and shell defaults synthesize application-specific records.

- [ ] **Step 2: Implement selected application loading**

Implement `load_selected_applications(plan, registrar)` in `application_loader.py`. It must validate each `registration_entry` against the plan lock, import only the selected module, call its `register_application(registrar)` function, and return a disposer stack. Missing entries, mismatched application ids, and duplicate source ids must raise a stable `application_registration_error` without importing unselected entries.

- [ ] **Step 3: Make product catalog generic-only**

Remove all C++ imports and `default_c_cpp_application_record` calls from `product_catalog.py`. Keep generic shell contributions in `defaults.py`; move application-specific contributions to plugin registration. Make `hosted.py` obtain the selected registry from the compiled plan rather than an unconditional product registry. Remove `embedagent_composition` imports from runtime bootstrap paths.

- [ ] **Step 4: Keep the CLI generic**

Keep `run`, `chat`, and `sessions` commands, but make their application label, prompt units, commands, and empty state come from the selected capability projection. Remove default mode parsing from `config.py` and reject mode-only config keys instead of silently applying them. `bash`, `ask_user`, file tools, and session interaction remain generic capabilities.

- [ ] **Step 5: Run shell tests and commit**

```bash
uv run pytest tests/test_generic_shell_bootstrap.py tests/test_minimal_shell_contract.py tests/test_product_host_composition.py tests/test_cli_run.py tests/test_cli_chat.py tests/test_cli_sessions.py -q
git add src/embedagent tests/test_generic_shell_bootstrap.py tests/test_minimal_shell_contract.py tests/test_product_host_composition.py
git commit -m "feat: load selected applications from the generic shell"
```

## Task 5: Move C/C++ Behavior Behind Its Application Plugin

**Files:**
- Create: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application.py`
- Modify: `packages/embedagent-workflow-cpp/pyproject.toml`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/__init__.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/component.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/profile.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workspace_profile.py`
- Modify: `src/embedagent/frontend/shell/defaults.py`
- Modify: `src/embedagent/product_catalog.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py`
- Create: `tests/test_cpp_application_registration.py`
- Modify: `tests/test_cpp_workflow_distribution.py`
- Modify: `tests/test_c_cpp_workflow_task_projection.py`

The C++ test module imports `cpp_application_manifest` and `register_application` from `embedagent_workflow_cpp.application`; it does not import `src/embedagent.product_catalog`.

- [ ] **Step 1: Write the C++ registration contract test**

```python
def test_cpp_plugin_manifest_declares_only_public_dependencies():
    manifest = cpp_application_manifest()
    assert manifest.distribution_id == "embedagent-workflow-cpp"
    assert manifest.registration_entry.endswith(":register_application")
    assert "embedagent" not in manifest.requires
    assert "toolchain.clang" in manifest.runtime_requirements


def test_cpp_registration_is_disposable():
    registrar = RecordingApplicationRegistrar()
    disposer = register_application(registrar)
    assert registrar.source_ids == ["embedagent.workflow.cpp"]
    disposer()
    assert registrar.active_source_ids == []
```

Run: `uv run pytest tests/test_cpp_application_registration.py -q`

Expected: FAIL until the C++ package exports a manifest and explicit registration function.

- [ ] **Step 2: Implement the C++ application entry**

Create `cpp_application_manifest()` and `register_application(registrar)`. The registration function must add the C++ runtime definition, mode descriptors, TaskGraph/workflow extension, workspace profile detectors, Ctags/recipe/diagnostics providers, and C++ shell contribution using source id `embedagent.workflow.cpp`. It must not import `embedagent.product_catalog`, `embedagent.hosted`, or `embedagent_composition`.

- [ ] **Step 3: Move C++ shell descriptors and runtime ownership**

Move `cpp_workflow_contribution()` and the C++ empty state into the plugin. The generic shell registry must merge only generic contributions unless the selected plan has the C++ registration source. Keep C++ modes and prompts in the workflow package; generic profiles are no longer a Host default.

- [ ] **Step 4: Update the C++ distribution contract**

Declare exact-matched `embedagent-core` and `embedagent-protocol` dependencies only. Add a package-level test that installs the C++ wheel with Core/Protocol in isolation and proves `embedagent_host` and the product shell are not importable.

- [ ] **Step 5: Run C++ plugin tests and commit**

```bash
uv run pytest tests/test_cpp_application_registration.py tests/test_cpp_workflow_distribution.py tests/test_c_cpp_workflow_task_projection.py -q
git add packages/embedagent-workflow-cpp src/embedagent/frontend/shell/defaults.py src/embedagent/product_catalog.py packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py tests/test_cpp_application_registration.py
git commit -m "refactor: register C++ workflow as an application plugin"
```

## Task 6: Remove Platform Modes And C++ Defaults From Core And Host

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
- Modify: `tests/test_agent_profiles.py`
- Modify: `tests/test_modes.py`
- Modify: `tests/test_workspace_profile.py`
- Modify: `tests/test_agent_runtime_integration.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Write failing mode-free Core tests**

```python
def test_runtime_definition_starts_without_mode_or_profile():
    definition = RuntimeDefinition(model_client=FakeModelClient(), tools=FakeTools())
    session = Agent.create(definition).open()
    assert session.view().workflow_state == {}


def test_host_workspace_intelligence_has_no_implicit_providers():
    broker = WorkspaceIntelligenceBroker()
    assert broker.providers == []


def test_runtime_definition_has_no_platform_prompt_or_mode():
    definition = RuntimeDefinition()
    assert not hasattr(definition, "default_mode")
    assert not hasattr(definition, "mode_runtime_policy")
```

Run: `uv run pytest tests/test_agent_profiles.py tests/test_modes.py tests/test_agent_runtime_integration.py -q`

Expected: FAIL because Core and Host currently require `AgentProfile`, `default_mode`, and default workspace providers.

- [ ] **Step 2: Delete the Core profile path**

Remove `AgentModeDescriptor`, `AgentProfile`, `AgentProfileRuntimePolicy`, `AgentProfileToolPolicy`, and `AgentProfileWritePathPolicy` from Core exports and runtime construction. `RuntimeDefinition` must accept application-supplied prompt/context/tool/permission ports without a mode argument. Delete mode transitions from session transaction and reducer inputs; do not add compatibility aliases.

- [ ] **Step 3: Make Host provider injection explicit**

Change `WorkspaceIntelligenceBroker(providers=None)` so its default is an empty tuple. Add an explicit provider list to the selected application registration path. Keep generic file/project context providers only when the generic application selects them; Ctags, recipe, diagnostics, LLSP, and LLVM providers are supplied by the C++ plugin.

- [ ] **Step 4: Move write-path and prompt policy to applications**

Remove `default_mode`, `mode_writable_globs`, and `mode_extra_writable_globs` from `AppConfig`. Make `prompt_assembly_service` consume application prompt units and active tool names. Make permission policy and writable-path policy remain independent focused collaborators; no application mode may grant either one.

- [ ] **Step 5: Update Core/Host boundary guards and commit**

```bash
uv run pytest tests/test_agent_core_public_api.py tests/test_agent_effect_kernel.py tests/test_agent_loop_driver.py tests/test_session_reducer_restore.py tests/test_host_package_composition.py tests/test_current_architecture_boundaries.py tests/test_pre_release_architecture_guards.py -q
git add packages/embedagent-core packages/embedagent-host src/embedagent tests/test_agent_profiles.py tests/test_modes.py tests/test_workspace_profile.py tests/test_agent_runtime_integration.py tests/test_current_architecture_boundaries.py tests/test_pre_release_architecture_guards.py
git commit -m "refactor: remove platform mode and implicit workflow defaults"
```

## Task 7: Make Protocol, TUI, And GUI Consume Optional Capabilities

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
- Modify: `src/embedagent/frontend/gui/webapp/test/protocol-normalizer.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-capability-model.test.mjs`

The protocol test module imports `_manifest` from the shared contract helper and imports
`cpp_application_manifest` from `embedagent_workflow_cpp.application`; it never builds a second
application descriptor shape.

- [ ] **Step 1: Write capability projection tests**

```python
def test_application_descriptor_does_not_synthesize_modes():
    payload = application_descriptor_payload(_manifest(), active=True)
    assert payload["capabilities"] == []
    assert "modes" not in payload


def test_cpp_descriptor_exposes_modes_only_when_selected():
    payload = application_descriptor_payload(cpp_application_manifest(), active=True)
    assert {item["id"] for item in payload["capabilities"]} >= {"mode.explore", "mode.build"}
```

Run: `uv run pytest tests/test_agent_app_protocol.py tests/test_minimal_shell_contract.py -q` and `npm test -- --runInBand` from `src/embedagent/frontend/gui/webapp`.

Expected: FAIL because protocol normalizers and shell registries currently synthesize mode/application records.

- [ ] **Step 2: Add JSON-safe application and capability DTOs**

Extend `app_protocol.py` with immutable descriptor serializers for application identity, capabilities, shell contributions, runtime requirements, and safe diagnostics. The DTOs must contain data only; they must not carry tool executors, permission objects, live sessions, or registration callables.

- [ ] **Step 3: Make shell compilation projection-driven**

Keep generic command/surface/tool/timeline contributions in `registration.py`. `compile_shell_descriptor` must merge only generic contributions plus contributions whose source id is active in the session capability projection. Remove hard-coded C++ application ids and make `session.mode` dispatch available only when a selected application declares it.

- [ ] **Step 4: Remove frontend mode assumptions**

Change TUI and GUI state/normalizers so absent mode descriptors produce no mode selector, badge, or default label. Preserve optional mode rendering for C++ capability projections. Do not change the durable session event envelope or add frontend translation layers.

- [ ] **Step 5: Run frontend gates and commit**

```bash
uv run pytest tests/test_agent_app_protocol.py tests/test_minimal_shell_contract.py tests/test_gui_protocol_projection.py tests/test_tui_runtime.py -q
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../..
git add packages/embedagent-protocol src/embedagent/frontend tests/test_agent_app_protocol.py tests/test_minimal_shell_contract.py tests/test_gui_protocol_projection.py tests/test_tui_runtime.py
git commit -m "refactor: render shell behavior from selected capabilities"
```

Regenerate and commit static GUI assets only if the webapp source changes require them. Preserve unrelated pre-existing changes to `src/embedagent/frontend/gui/static/assets/app.css` and `app.js`.

## Task 8: Replace Unsafe Generic Runtime Error Compression

**Files:**
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/session_events.py`
- Modify: `packages/embedagent-host/src/embedagent_host/frontend_errors.py`
- Modify: `src/embedagent/cli/result.py`
- Modify: `src/embedagent/cli/app.py`
- Modify: `src/embedagent/cli/renderer.py`
- Modify: `tests/test_cli_run.py`
- Modify: `tests/test_cli_chat.py`
- Modify: `tests/test_agent_app_protocol.py`
- Create: `tests/test_safe_failure_diagnostics.py`

- [ ] **Step 1: Write the safe diagnostic contract test**

```python
def test_failure_record_contains_phase_kind_and_correlation_without_exception_text():
    record = FailureRecord.from_exception(
        phase="tool_execution",
        kind="runtime",
        correlation_id="corr-1",
        exception=RuntimeError("secret prompt and token must not escape"),
    )
    payload = record.to_dict()
    assert payload["phase"] == "tool_execution"
    assert payload["kind"] == "runtime"
    assert payload["correlation_id"] == "corr-1"
    assert "secret prompt" not in repr(payload)


def test_interaction_failure_remains_distinguishable_from_runtime_failure():
    assert FailureRecord(kind="interaction").to_dict()["kind"] == "interaction"
```

Run: `uv run pytest tests/test_safe_failure_diagnostics.py -q`

Expected: FAIL because `FailureRecord` currently has only code/message/retryable/source.

- [ ] **Step 2: Add the safe DTO fields and mapping**

Add `phase`, `kind`, `correlation_id`, `safe_message`, and `exception_type` to `FailureRecord`. Map exceptions to stable safe messages and type names; never serialize raw exception messages, prompts, source files, tool output, credentials, or approval payloads.

- [ ] **Step 3: Update CLI and Host consumers**

Replace `runtime_error` compression with the structured record. Keep renderer output concise and stable while retaining the correlation id for diagnostics. Update frontend DTO validation to accept the new fields without exposing raw text.

- [ ] **Step 4: Run diagnostics tests and commit**

```bash
uv run pytest tests/test_safe_failure_diagnostics.py tests/test_cli_run.py tests/test_cli_chat.py tests/test_agent_app_protocol.py -q
git add packages/embedagent-protocol packages/embedagent-host/src/embedagent_host/frontend_errors.py src/embedagent/cli tests/test_safe_failure_diagnostics.py
git commit -m "fix: expose safe structured runtime diagnostics"
```

## Task 9: Synchronize Product, Packaging, And Independent-Repository Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/platform/agent-core.md`
- Modify: `docs/platform/tools-and-extensions.md`
- Modify: `docs/platform/frontend-protocol.md`
- Modify: `docs/product/composition.md`
- Modify: `docs/product/packaging-and-deployment.md`
- Modify: `docs/guides/win7-release-runbook.md`
- Modify: `docs/references/code-doc-matrix.md`
- Modify: `docs/current-status.md`
- Create: `docs/guides/application-plugin-authoring.md`
- Modify: `docs/superpowers/README.md`
- Modify: `docs/superpowers/handoffs/2026-08-16-pi-shaped-generic-agent-architecture/continue.md`

- [ ] **Step 1: Write documentation guard tests**

```python
def test_active_docs_do_not_claim_fixed_six_wheel_runtime_contract():
    paths = (
        "AGENTS.md",
        "docs/overall-solution-architecture.md",
        "docs/product/packaging-and-deployment.md",
    )
    text = "\n".join(Path(path).read_text(encoding="utf-8") for path in paths)
    assert "exactly six Python distributions" not in text
    assert "PORTABLE_PROJECT_DISTRIBUTIONS" not in text


def test_plugin_authoring_doc_names_the_public_registration_contract():
    text = Path("docs/guides/application-plugin-authoring.md").read_text(encoding="utf-8")
    assert "application_id" in text
    assert "registration_entry" in text
    assert "dispose" in text
```

Run: `uv run pytest tests/test_documentation_navigation.py -q`

Expected: FAIL until current authorities and the new authoring guide are synchronized.

- [ ] **Step 2: Replace the six-wheel authority language**

Document the selected-closure distribution contract, generic shell baseline, build-only composition compiler, plan-selected runtime assets, and explicit C++ application registration. Update `AGENTS.md` wording so Windows 7/offline requirements remain mandatory while Ctags/LLVM are required only when selected by the C++ plan.

- [ ] **Step 3: Add the application plugin authoring guide**

Document the exact manifest fields, registration entry shape, source ids, disposer semantics, allowed dependencies, test matrix, offline asset declaration, and the rule that plugins cannot mutate Core session truth or grant permissions. Include a generic application and C++ application example with no runtime dependency installation.

- [ ] **Step 4: Synchronize ownership and close the evaluation slice**

Update the code-doc matrix and current status to point at ADR-0008 and the accepted spec. Remove the evaluation entries from `docs/superpowers/README.md` only after implementation acceptance; until then, mark the plan as active and keep the handoff as the execution pointer.

- [ ] **Step 5: Run documentation tests and commit**

```bash
uv run pytest tests/test_documentation_navigation.py tests/test_current_architecture_boundaries.py -q
git add AGENTS.md README.md docs
git commit -m "docs: publish generic application plugin architecture"
```

## Task 10: Full Verification And Release Evidence

**Files:**
- Modify: `tests/test_release_identity.py`
- Modify: `tests/test_release_reproducibility.py`
- Modify: `tests/test_release_evidence.py`
- Modify: `tests/test_standalone_agent_example.py`
- Modify: `examples/standalone_agent.py`
- Modify: `scripts/validate-cli-smoke.py`
- Modify: `scripts/validate-cpp-smoke.py`
- Modify: `scripts/create-release-identity.py`
- Modify: `scripts/release_identity.py`

The release tests reuse `compile_bundle_plan_for("minimal-cli")` and `compile_bundle_plan_for("cpp-desktop")` from the closure test helper and pass the resulting plan object into the release identity builder.

- [ ] **Step 1: Add generic and C++ artifact acceptance tests**

```python
def test_generic_release_identity_excludes_cpp_and_llvm():
    identity = create_release_identity(compile_bundle_plan_for("minimal-cli"), evidence={})
    assert "embedagent-workflow-cpp" not in identity["project_distribution_ids"]
    assert "toolchain.clang" not in identity["runtime_capability_ids"]


def test_cpp_release_identity_requires_cpp_smoke_gate():
    identity = create_release_identity(compile_bundle_plan_for("cpp-desktop"), evidence={})
    assert "cpp_smoke_workspace" in identity["gate_ids"]
```

Run: `uv run pytest tests/test_release_identity.py tests/test_release_reproducibility.py tests/test_release_evidence.py -q`

Expected: FAIL until release identity and evidence consume the selected plan instead of six-wheel assumptions.

- [ ] **Step 2: Update standalone Core and selected application smoke probes**

Keep the Core-only probe free of Host, Protocol, Product, Composition, and Workflow imports. Add a generic shell probe that starts without a mode and a C++ probe that verifies modes, TaskGraph, Ctags, and Clang are present only in the C++ plan.

- [ ] **Step 3: Run the required local gates**

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run --locked python scripts/lint.py
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist --bundle-plan build/plans/generic-cli.json
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe --bundle-plan build/plans/generic-cli.json
```

Expected: architecture guards, full Python partition, lint, selected generic wheel check, and generic isolated smoke all pass. Repeat the selected-plan build/check/smoke for `cpp-desktop`.

- [ ] **Step 4: Run bundle and frontend release gates**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 doctor
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 release
```

From `src/embedagent/frontend/gui/webapp`, run `npm test` and `npm run build` when frontend sources changed. Validate both generic and C++ artifacts with `scripts/validate-offline-bundle.ps1` and retain clean-machine Win7/WebView2 evidence as an external release gate.

- [ ] **Step 5: Commit final verification and archive the completed slice**

```bash
git add examples scripts tests docs
git commit -m "test: verify generic and C++ closure-based artifacts"
```

After all acceptance conditions are met, move the completed spec/plan/report into an indexed `docs/archive/pi-shaped-generic-agent/` package, remove the active evaluation handoff from `docs/superpowers/README.md`, and update `docs/current-status.md` in place. Do not append a completion diary to active authorities.

## Execution Notes

- Do not add compatibility aliases for deleted mode/profile/reducer/catalog shapes.
- Keep `embedagent-workflow-cpp` free of product imports; its future independent repository must consume only the frozen public contracts.
- Keep application activation, tool execution, permission, and writable-path authorization as separate decisions.
- Preserve the existing user modifications in `src/embedagent/frontend/gui/static/assets/app.css` and `app.js`; only regenerate those files when a frontend source change requires it.
- Every task must leave its focused tests green before the commit; do not batch unrelated refactors into a task.
