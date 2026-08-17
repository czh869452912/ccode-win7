# Public Contract And Repository Boundary Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已经完成的 selected-application runtime composition 收敛为可冻结、可独立验证、可供未来 C/C++ 独立仓库消费的公共契约，同时清除 Core/Host/Shell 中残留的 mode/profile 和隐式 workflow 技术债。

**Architecture:** Core 只保留 workflow-neutral session、turn、restore 和 focused ports；Host 只保留显式注入的通用 provider/runtime；application plugin 拥有 prompt、tool、context、mode 和 workflow state。通用 shell 只渲染 selected capability projection，bundle lock 是运行时 distribution、asset、registration entry 和 release gate 的唯一闭包真相。物理拆库延后到契约冻结和独立 wheel smoke 通过之后。

**Tech Stack:** Python 3.8、setuptools/uv workspace、stdlib JSON DTO、pytest、Ruff/Black、PowerShell offline bundle tooling、现有 CLI/TUI/GUI shell contract。

---

## Current Boundary

上一轮已经完成并归档：

- `ApplicationRuntimeContribution`、显式 registration entry 和可逆注册生命周期；
- generic product 与 C/C++ plugin 的运行时所有权切分；
- selected application closure 驱动的 distribution build/check/smoke；
- `embedagent-shell` 作为通用 product/bootstrap distribution 的命名与依赖方向。

本计划只处理仍可在源码中观察到的债务：

- Core/Host 仍通过 `AgentProfile`、`default_mode`、`current_mode` 和 mode policies 解释平台级行为；
- Host 的默认 workspace intelligence 和 generic profile factory 仍混合 application 语义；
- Protocol 和 shell 在 capability 缺失时仍可能合成 mode/profile 记录；
- 安全诊断 DTO 与 application contract 版本验证还没有成为独立的发布门禁；
- C++ plugin 尚未拥有可脱离 Host/Product/Composition 的独立 wheel proof；
- 根 README、部分 package metadata 和 release 文档仍需机械同步最终边界。

## Scope

本轮包含 mode/profile debt removal、capability-driven shell projection、safe diagnostic DTO、public
application contract freeze、C++ isolated wheel proof 和文档/ADR 同步。

本轮不执行物理 Git 仓库拆分，不引入远程 registry、运行时依赖安装、共享 service bag 或多 Agent
orchestration；Windows 7 clean-machine evidence 与真实 C/C++ 项目验证仍是独立交付轨道。

## File Map

- Core contract: `packages/embedagent-core/src/embedagent_core/api.py`, `hosting.py`, `session_input.py`, `runtime_config.py`, `profile.py`, `profile_runtime.py`。
- Host runtime: `packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py`, `runtime/profiles.py`, `runtime/context.py`, `runtime/workspace_intelligence.py`, `hosted/runtime.py`, `inprocess_adapter.py`。
- Protocol/shell: `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`, `frontend_ports.py`, `src/embedagent/frontend/shell/registration.py`, `compiler.py`, `src/embedagent/frontend/tui/`, `src/embedagent/frontend/gui/backend/`。
- Plugin and composition: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application.py`, `packages/embedagent-composition/src/embedagent_composition/application.py`, `src/embedagent/bundle_catalog.py`。
- Packaging/docs: `scripts/build-python-distributions.py`, `scripts/check-python-distributions.py`, `scripts/smoke-python-distributions.py`, `scripts/package-lib.ps1`, `pyproject.toml`, `README.md`, `AGENTS.md`, `docs/`。
- Tests: `tests/test_current_architecture_boundaries.py`, `tests/test_pre_release_architecture_guards.py`, `tests/test_agent_profiles.py`, `tests/test_modes.py`, `tests/test_agent_app_protocol.py`, `tests/test_python_distribution_contract.py`.

## Task 1: Freeze Public Application Contract

**Purpose:** 让 application manifest、runtime contribution、registration entry 和 selected lock 成为一组可版本化的公共输入。

**Files:**

- Modify: `packages/embedagent-composition/src/embedagent_composition/application.py`
- Modify: `packages/embedagent-core/src/embedagent_core/application.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py`
- Modify: `src/embedagent/bundle_catalog.py`
- Create: `tests/test_public_application_contract.py`

- [ ] **Step 1: Add contract stability tests**

```python
def test_application_contract_emits_stable_public_fields():
    manifest = generic_application_manifest()
    payload = manifest.to_dict()
    assert payload["api_version"] == "agent_application_v1"
    assert payload["registration_entry"] == "embedagent.product_catalog:register"
    assert "runtime_factory" not in payload


def test_selected_lock_records_registration_and_owner():
    plan = compile_bundle_plan_for("minimal-cli")
    assert plan.registration_entries == (
        "embedagent.product_catalog:register",
    )
    assert "embedagent-shell" in plan.project_distribution_ids
```

Run: `uv run pytest tests/test_public_application_contract.py -q`

Expected: FAIL until the manifest, compiled plan and lock serializer expose one stable contract.

- [ ] **Step 2: Normalize manifest and runtime contribution serializers**

Require `api_version`, `distribution_id`, `registration_entry`, capability ids, runtime requirement ids
and source id to be validated once. Serialize only JSON-safe data; never serialize factories, registrars,
ports, live sessions or permission objects. Reject duplicate application ids and registration entries in a
compiled selected plan.

- [ ] **Step 3: Add contract and lock isolation checks**

Make the distribution checker fail when a wheel's public application owner or registration entry is absent
from `bundle-plan.json`. Keep `embedagent-composition` build-time only and reject it from a runtime closure.

- [ ] **Step 4: Run contract gates and commit**

```bash
uv run pytest tests/test_public_application_contract.py tests/test_bundle_plan.py tests/test_current_architecture_boundaries.py -q
git add packages/embedagent-composition packages/embedagent-core packages/embedagent-host src/embedagent/bundle_catalog.py tests/test_public_application_contract.py
git commit -m "refactor: freeze public application composition contract"
```

## Task 2: Remove Platform Mode/Profile Debt From Core And Host

**Purpose:** generic Agent starts without a platform mode, profile, or implicit workflow policy; C++ keeps those semantics inside its plugin.

**Files:**

- Delete: `packages/embedagent-core/src/embedagent_core/profile.py`
- Delete: `packages/embedagent-core/src/embedagent_core/profile_runtime.py`
- Delete: `src/embedagent/modes.py`
- Modify: `packages/embedagent-core/src/embedagent_core/api.py`
- Modify: `packages/embedagent-core/src/embedagent_core/hosting.py`
- Modify: `packages/embedagent-core/src/embedagent_core/session_input.py`
- Modify: `packages/embedagent-core/src/embedagent_core/runtime_config.py`
- Modify: `packages/embedagent-core/src/embedagent_core/__init__.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/profiles.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/workspace_intelligence.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted/runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/component.py`
- Modify: `tests/test_agent_profiles.py`
- Modify: `tests/test_modes.py`
- Modify: `tests/test_agent_runtime_integration.py`
- Modify: `tests/test_workspace_profile.py`

- [ ] **Step 1: Add mode-free Core and empty-Host tests**

```python
def test_generic_runtime_definition_has_no_platform_mode():
    definition = RuntimeDefinition(model_client=FakeModelClient(), tools=FakeTools())
    assert not hasattr(definition, "default_mode")
    assert not hasattr(definition, "mode_runtime_policy")


def test_generic_host_workspace_intelligence_is_empty_until_injected():
    broker = WorkspaceIntelligenceBroker()
    assert broker.providers == ()


def test_generic_session_starts_with_empty_workflow_state():
    session = Agent.create(generic_runtime_definition()).open()
    assert session.view().workflow_state == {}
```

Run: `uv run pytest tests/test_agent_profiles.py tests/test_modes.py tests/test_agent_runtime_integration.py tests/test_workspace_profile.py -q`

Expected: FAIL because the current Core/Host construction still supplies mode/profile defaults.

- [ ] **Step 2: Delete Core profile exports and mode transitions**

Remove the profile classes and mode policy arguments from Core construction and exports. `RuntimeDefinition`
must accept application-supplied context, tool, prompt and permission collaborators without a default mode.
Delete mode-specific reducer/session input branches instead of adding aliases.

- [ ] **Step 3: Move policies and providers to application contributions**

Make `WorkspaceIntelligenceBroker()` default to an empty immutable provider tuple. Move generic file/project
providers into the generic application contribution and Ctags, recipes, diagnostics, LLVM and TaskGraph
providers into the C++ plugin. Keep writable-path and permission decisions as separate focused collaborators.

- [ ] **Step 4: Verify C++ behavior remains plugin-owned**

The C++ application must still construct its modes, profile policy, prompt stack and workflow state through
its own registration entry. Add a test proving that importing Core/Host alone cannot import
`embedagent_workflow_cpp.profile` or `embedagent_workflow_cpp.component`.

- [ ] **Step 5: Run Core/Host gates and commit**

```bash
uv run pytest tests/test_agent_effect_kernel.py tests/test_agent_loop_driver.py tests/test_session_reducer_restore.py tests/test_agent_runtime_integration.py tests/test_current_architecture_boundaries.py tests/test_pre_release_architecture_guards.py -q
git add packages/embedagent-core packages/embedagent-host packages/embedagent-workflow-cpp src/embedagent tests/test_agent_profiles.py tests/test_modes.py tests/test_agent_runtime_integration.py tests/test_workspace_profile.py
git commit -m "refactor: remove platform mode and implicit workflow defaults"
```

## Task 3: Make Protocol And Shell Capability-Driven

**Purpose:** a generic shell renders only generic capabilities; mode, profile, workflow commands and C++ surfaces appear only when selected by the application.

**Files:**

- Modify: `packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/frontend_ports.py`
- Modify: `src/embedagent/frontend/shell/registration.py`
- Modify: `src/embedagent/frontend/shell/compiler.py`
- Modify: `src/embedagent/frontend/tui/state.py`
- Modify: `src/embedagent/frontend/tui/controller.py`
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-capability-model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/shell/SessionComposer.jsx`
- Modify: `tests/test_agent_app_protocol.py`
- Modify: `tests/test_minimal_shell_contract.py`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-capability-model.test.mjs`

- [ ] **Step 1: Add absent-capability tests**

```python
def test_generic_descriptor_has_no_synthetic_modes():
    payload = generic_shell_descriptor_payload()
    assert payload["capabilities"] == []
    assert "modes" not in payload


def test_cpp_descriptor_adds_modes_only_when_cpp_source_is_active():
    payload = cpp_shell_descriptor_payload()
    assert {item["id"] for item in payload["capabilities"]} >= {"mode.explore", "mode.build"}
```

Run: `uv run pytest tests/test_agent_app_protocol.py tests/test_minimal_shell_contract.py -q`

Expected: FAIL where protocol normalizers or shell compilation synthesize mode/profile records.

- [ ] **Step 2: Define JSON-safe application capability DTOs**

Add immutable serializers for application identity, capability records, shell contributions, runtime
requirements and safe diagnostics. DTOs must contain data only and must not expose callables, tools,
permission objects, mutable sessions or private Host state.

- [ ] **Step 3: Remove shell-local workflow assumptions**

Compile generic contributions first, then merge only contributions whose source id is active in the session
capability projection. An absent mode capability produces no selector, badge, command or default label.
Preserve the canonical `session_event` envelope and do not add a frontend translation layer.

- [ ] **Step 4: Run Python and frontend gates**

```bash
uv run pytest tests/test_agent_app_protocol.py tests/test_minimal_shell_contract.py tests/test_gui_protocol_projection.py tests/test_tui_runtime.py -q
```

```powershell
Set-Location src/embedagent/frontend/gui/webapp
npm test
npm run build
Set-Location ../../../../..
```

```bash
git add packages/embedagent-protocol src/embedagent/frontend tests/test_agent_app_protocol.py tests/test_minimal_shell_contract.py tests/test_gui_protocol_projection.py tests/test_tui_runtime.py
git commit -m "refactor: render shells from selected capabilities"
```

## Task 4: Publish Safe Diagnostics And Runtime Requirement Ownership

**Purpose:** distinguish interaction, permission, provider and runtime failures without leaking prompts, source, tool output or credentials, and make runtime requirements application-owned.

**Files:**

- Modify: `packages/embedagent-protocol/src/embedagent_protocol/session_events.py`
- Modify: `packages/embedagent-host/src/embedagent_host/frontend_errors.py`
- Modify: `src/embedagent/cli/result.py`
- Modify: `src/embedagent/cli/app.py`
- Modify: `scripts/offline-runtime-contract.json`
- Modify: `src/embedagent/bundle_catalog.py`
- Create: `tests/test_safe_failure_diagnostics.py`

- [ ] **Step 1: Add red tests for safe failure records**

```python
def test_runtime_failure_has_phase_kind_and_correlation_without_exception_text():
    record = FailureRecord.from_exception(
        phase="tool_execution",
        kind="runtime",
        correlation_id="corr-1",
        exception=RuntimeError("secret prompt and token must not escape"),
    )
    payload = record.to_dict()
    assert payload["kind"] == "runtime"
    assert payload["correlation_id"] == "corr-1"
    assert "secret prompt" not in repr(payload)
```

Run: `uv run pytest tests/test_safe_failure_diagnostics.py -q`

Expected: FAIL until the structured failure DTO exists.

- [ ] **Step 2: Add stable safe fields and application-selected runtime checks**

Expose only `phase`, `kind`, `correlation_id`, `safe_message` and `exception_type`. Derive runtime asset and
gate checks from the selected plan's requirements; never reconstruct a global tool list in a validator.

- [ ] **Step 3: Run diagnostics and release-contract tests**

```bash
uv run pytest tests/test_safe_failure_diagnostics.py tests/test_cli_run.py tests/test_cli_chat.py tests/test_release_identity.py tests/test_python_distribution_contract.py -q
git add packages/embedagent-protocol packages/embedagent-host/src/embedagent_host/frontend_errors.py src/embedagent/cli src/embedagent/bundle_catalog.py scripts/offline-runtime-contract.json tests/test_safe_failure_diagnostics.py
git commit -m "fix: publish safe application-scoped diagnostics"
```

## Task 5: Prove Independent C/C++ Application Export

**Purpose:** establish the evidence required before moving C/C++ to another repository, without performing the move in this plan.

**Files:**

- Modify: `packages/embedagent-workflow-cpp/pyproject.toml`
- Modify: `scripts/build-python-distributions.py`
- Modify: `scripts/check-python-distributions.py`
- Modify: `scripts/smoke-python-distributions.py`
- Create: `tests/test_cpp_application_isolation.py`
- Create: `docs/guides/cpp-independent-repository-boundary.md`

- [ ] **Step 1: Add isolated import and dependency tests**

```python
def test_cpp_plugin_declares_only_public_runtime_dependencies():
    metadata = read_project_metadata("packages/embedagent-workflow-cpp/pyproject.toml")
    assert metadata.dependencies == ("embedagent-core==0.1.0", "embedagent-protocol==0.1.0")


def test_cpp_plugin_isolated_probe_cannot_discover_product_or_host():
    result = run_isolated_wheel_probe(("embedagent-core", "embedagent-protocol", "embedagent-workflow-cpp"))
    assert result.imported == ("embedagent_core", "embedagent_protocol", "embedagent_workflow_cpp")
    assert "embedagent_host" not in result.discoverable
    assert "embedagent" not in result.discoverable
```

Run: `uv run pytest tests/test_cpp_application_isolation.py -q`

Expected: FAIL until the selected-wheel probe and exact dependency assertion are implemented.

- [ ] **Step 2: Add a standalone application export probe**

Use the compiled `cpp-desktop` plan to install only Core, Protocol and C++ workflow wheels into a temporary
offline target. Invoke the explicit registration entry, verify the returned source-aware disposer, and
assert that Host/Product/Composition are not importable in that target.

- [ ] **Step 3: Document the future repository contract**

Document the exact public inputs (`embedagent-core`, `embedagent-protocol`, `agent_application_v1`, selected
runtime requirements), forbidden imports, versioning rule, offline asset ownership and product consumption
flow. State that repository extraction starts only after this probe and the public contract gates are green.

- [ ] **Step 4: Run selected closure verification and commit**

```bash
uv run python scripts/build-python-distributions.py --dist-dir dist-cpp --bundle-plan build/plans/cpp-desktop/bundle-plan.json
uv run python scripts/check-python-distributions.py --dist-dir dist-cpp --bundle-plan build/plans/cpp-desktop/bundle-plan.json
uv run python scripts/smoke-python-distributions.py --dist-dir dist-cpp --python .venv/Scripts/python.exe --bundle-plan build/plans/cpp-desktop/bundle-plan.json
uv run pytest tests/test_cpp_application_isolation.py tests/test_current_architecture_boundaries.py -q
git add packages/embedagent-workflow-cpp scripts tests/test_cpp_application_isolation.py docs/guides/cpp-independent-repository-boundary.md
git commit -m "test: prove independent C++ application export boundary"
```

## Task 6: Synchronize Authorities And Decide Physical Repository Split

**Files:**

- Create: `docs/adrs/0009-public-contract-and-repository-boundary.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/platform/agent-core.md`
- Modify: `docs/platform/protocol.md`
- Modify: `docs/applications/cpp-workflow.md`
- Modify: `docs/product/composition.md`
- Modify: `docs/product/packaging-and-deployment.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/references/code-doc-matrix.md`
- Modify: `docs/superpowers/README.md`

- [ ] **Step 1: Publish the ADR**

ADR-0009 must record the final ownership model, `agent_application_v1` freeze, selected-closure lock
semantics, mode/profile removal, isolated C++ proof, and the explicit decision that physical repository
split is gated by public contract versioning and release automation.

- [ ] **Step 2: Replace stale entry language**

Update `README.md` and all routed authorities so `embedagent-shell` and selected closure are named
mechanically. Remove fixed-six-wheel and implicit C++ registration claims. Keep Windows 7, Python 3.8,
offline runtime and external evidence requirements unchanged.

- [ ] **Step 3: Replace current status and roadmap in place**

Set the next architecture focus to this plan, keep Win7 and real-project evidence as separate blockers,
and define the physical split exit condition as: public contract tests green, isolated C++ wheel smoke green,
versioned release metadata available, and product consumption test green.

- [ ] **Step 4: Run the final local matrix**

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py tests/test_public_application_contract.py tests/test_cpp_application_isolation.py -q
uv run python scripts/test-suite.py full
uv run --locked python scripts/lint.py
```

Run both selected generic and C++ build/check/smoke commands from `AGENTS.md`. Do not claim Windows 7
acceptance from local results; archive this plan only after its local exit conditions and the durable docs
are synchronized.

## Exit Conditions

- Generic Core/Host/Shell can start without a platform mode, profile or implicit workflow provider.
- Protocol and all shells render only selected application capabilities.
- C++ owns its mode/profile/workflow semantics and passes an isolated Core/Protocol/C++ wheel probe.
- `agent_application_v1`, selected closure, registration entry and runtime requirements are versioned and
  represented in the same bundle lock.
- Active docs contain no fixed-six-wheel or product-owned C++ runtime claim.
- Physical repository extraction has a documented gate and is not started before the above conditions hold.
- Win7 clean-machine acceptance and real C/C++ project validation remain explicit external/product gates.
