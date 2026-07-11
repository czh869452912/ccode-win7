# Cpp Workflow Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver every C/C++-specific profile, workflow, task, recipe, tool, reducer, and workspace detector from an independent `embedagent-workflow-cpp` wheel selected only by product composition.

**Architecture:** Promote generic profile descriptor contracts into Core, move the C/C++ package to a top-level distribution namespace, and replace Host application records and executable builder paths with a package-owned frozen runtime definition factory. The workflow contributes tools and reducers through the one Core extension manager.

**Tech Stack:** Python 3.8, Core extension/tool/profile contracts, setuptools/uv workspace, pytest harness tests, existing Clang-centered offline runtime contract.

---

## Target Package

```text
packages/embedagent-workflow-cpp/
  pyproject.toml
  src/embedagent_workflow_cpp/
    profile.py
    component.py
    extension.py
    package_manifest.py
    contracts.py
    context_reducers.py
    packs.py
    phase_engine.py
    prompt_stack.py
    recipe_ops.py
    registry.py
    runner.py
    session_graph_state.py
    session_ops.py
    task_graph.py
    task_store.py
    tool_metadata.py
    tool_names.py
    tool_registry.py
    workflow_projection.py
    workspace_profile.py
    workspace_recipes.py
```

Distribution name: `embedagent-workflow-cpp`.
Import namespace: `embedagent_workflow_cpp`.
Runtime dependencies: `embedagent-core` only.

### Task 1: Add C/C++ Distribution And Import Boundary Guards

**Files:**
- Create: `tests/test_cpp_workflow_distribution.py`
- Modify: `tests/test_python_distribution_contract.py`
- Modify: `tests/test_core_package_imports.py`

- [ ] **Step 1: Write target package tests**

Create `tests/test_cpp_workflow_distribution.py`:

```python
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp"


def test_cpp_workflow_package_exists():
    assert (PACKAGE / "__init__.py").is_file()
    assert (PACKAGE / "component.py").is_file()


def test_cpp_workflow_imports_only_core_and_standard_library_project_packages():
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = node.module or "" if isinstance(node, ast.ImportFrom) else ""
            if module == "embedagent" or module.startswith("embedagent."):
                offenders.append((str(path.relative_to(ROOT)), module))
            if module == "embedagent_host" or module.startswith("embedagent_host."):
                offenders.append((str(path.relative_to(ROOT)), module))
            if module == "embedagent_protocol" or module.startswith("embedagent_protocol."):
                offenders.append((str(path.relative_to(ROOT)), module))
    assert offenders == []


def test_legacy_nested_cpp_package_is_deleted():
    assert not (ROOT / "src/embedagent/workflow_packages/c_cpp").exists()
```

- [ ] **Step 2: Add distribution metadata expectations**

Extend `tests/test_python_distribution_contract.py` to require
`packages/embedagent-workflow-cpp/pyproject.toml`, project name
`embedagent-workflow-cpp`, and exactly one runtime dependency:

```python
assert project["dependencies"] == ["embedagent-core==0.1.0"]
```

- [ ] **Step 3: Run the tests and verify they fail**

```bash
uv run pytest tests/test_cpp_workflow_distribution.py tests/test_python_distribution_contract.py -v
```

Expected: FAIL because the distribution does not exist.

- [ ] **Step 4: Commit red boundary tests**

```bash
git add tests/test_cpp_workflow_distribution.py tests/test_python_distribution_contract.py tests/test_core_package_imports.py
git commit -m "test: define cpp workflow distribution boundary"
```

### Task 2: Promote Generic Profile Contracts Into Core

**Files:**
- Create: `packages/embedagent-core/src/embedagent_core/profile.py`
- Modify: `packages/embedagent-core/src/embedagent_core/__init__.py`
- Move: profile implementation ownership from product/Host modules as required
- Test: `tests/test_agent_profiles.py`

- [ ] **Step 1: Add profile contract tests**

Add to `tests/test_agent_profiles.py`:

```python
def test_profile_contract_is_core_owned():
    from embedagent_core.profile import AgentModeDescriptor, AgentProfile

    profile = AgentProfile(
        profile_id="tests.base",
        label="Base",
        default_mode="",
        modes=(),
    )
    assert profile.default_mode == ""
    assert profile.modes == ()
```

- [ ] **Step 2: Implement immutable generic descriptors**

Create `embedagent_core/profile.py` with frozen `AgentModeDescriptor` and
`AgentProfile`. Use tuples rather than mutable lists for `allowed_tools`,
`writable_globs`, and `modes`. Keep `to_mode_definition()`,
`to_capability_metadata()`, `require_mode()`, `allowed_tools_for()`, and
`writable_globs_for()` generic.

Do not place default generic, Python, HTML, or C/C++ profiles in Core.

- [ ] **Step 3: Move base product profiles into Host runtime**

Move the generic/Python/HTML profile factories and prompt frame into
`packages/embedagent-host/src/embedagent_host/runtime/profiles.py`. Import the
descriptor types from `embedagent_core.profile`. Product application records
may refer to Host profile components until Plan 4.

- [ ] **Step 4: Export descriptor contracts from Core**

Add `AgentModeDescriptor` and `AgentProfile` to the explicit Core `__all__`.

- [ ] **Step 5: Run profile tests**

```bash
uv run pytest tests/test_agent_profiles.py tests/test_agent_core_public_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit profile ownership**

```bash
git add packages/embedagent-core packages/embedagent-host src tests/test_agent_profiles.py
git commit -m "refactor: promote generic profile contracts to core"
```

### Task 3: Create And Move The C/C++ Workflow Package

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` through uv only
- Create: `packages/embedagent-workflow-cpp/pyproject.toml`
- Move: all files under `src/embedagent/workflow_packages/c_cpp/`
- Modify: imports in `src/`, `packages/`, `tests/`, and active docs

- [ ] **Step 1: Add the workspace package metadata**

Add `packages/embedagent-workflow-cpp` to workspace members and sources. Its
pyproject uses:

```toml
[project]
name = "embedagent-workflow-cpp"
version = "0.1.0"
requires-python = ">=3.8,<3.9"
dependencies = ["embedagent-core==0.1.0"]

[tool.setuptools.package-dir]
"" = "src"

[tool.setuptools.packages.find]
where = ["src"]
include = ["embedagent_workflow_cpp*"]
```

- [ ] **Step 2: Move all C/C++ files with history**

```bash
New-Item -ItemType Directory -Force packages/embedagent-workflow-cpp/src | Out-Null
git mv src/embedagent/workflow_packages/c_cpp packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp
```

Replace all imports of `embedagent.workflow_packages.c_cpp` with
`embedagent_workflow_cpp`. Do not create a compatibility re-export.

- [ ] **Step 3: Regenerate workspace lock**

```bash
uv lock
uv sync
```

Expected: both commands exit zero.

- [ ] **Step 4: Run the C/C++ internal suites**

```bash
uv run pytest tests/test_task_graph_v2.py tests/test_phase_engine.py tests/test_prompt_stack_v2.py tests/test_c_cpp_workflow_contracts.py tests/test_c_cpp_workflow_runner_debug.py tests/test_c_cpp_workflow_runner_taskgraph.py tests/test_c_cpp_workflow_runner_verify.py -v
```

Expected: PASS after import rewrites.

- [ ] **Step 5: Commit the namespace move**

```bash
git add packages/embedagent-workflow-cpp src tests pyproject.toml uv.lock docs
git commit -m "refactor: move cpp workflow into independent package"
```

### Task 4: Replace Host Application Builders With A Core Runtime Contribution

**Files:**
- Delete after replacement:
  - `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application.py`
  - `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application_record.py`
- Create: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/component.py`
- Rename/modify: `agent_profile.py` to `profile.py`
- Delete: `packages/embedagent-host/src/embedagent_host/agent_application_registry.py`
- Create: `src/embedagent/product_catalog.py`
- Modify: product bootstrap/config selection
- Test: `tests/test_host_package_composition.py`

- [ ] **Step 1: Write the package contribution test**

Add to `tests/test_cpp_workflow_distribution.py`:

```python
def test_cpp_component_returns_core_runtime_definition():
    from embedagent_core import RuntimeDefinition
    from embedagent_workflow_cpp import cpp_runtime_definition

    definition = cpp_runtime_definition()
    assert isinstance(definition, RuntimeDefinition)
    assert definition.agent_id == "embedagent.default_c_cpp"
    assert len(definition.extensions) == 1
    assert definition.workflow_state == ""
```

- [ ] **Step 2: Implement `cpp_runtime_definition()`**

Create `component.py` with one package-owned factory:

```python
def cpp_runtime_definition() -> RuntimeDefinition:
    profile = default_cpp_profile()
    return RuntimeDefinition(
        agent_id="embedagent.default_c_cpp",
        default_mode=profile.default_mode,
        workflow_state="",
        extensions=(CHarnessWorkflowExtension(),),
        mode_tool_policy=AgentProfileToolPolicy(profile),
        write_path_policy=AgentProfileWritePathPolicy(profile),
        mode_runtime_policy=AgentProfileRuntimePolicy(profile),
    )
```

Move the generic `AgentProfile*Policy` adapters into Core or implement package
local adapters against Core policy protocols. Do not import Host profile
runtime code.

- [ ] **Step 3: Export only package contracts**

`embedagent_workflow_cpp.__init__` exports:

```python
from embedagent_workflow_cpp.component import cpp_runtime_definition
from embedagent_workflow_cpp.package_manifest import C_WORKFLOW_PACKAGE_ID

__all__ = ["C_WORKFLOW_PACKAGE_ID", "cpp_runtime_definition"]
```

- [ ] **Step 4: Update product selection**

`src/embedagent/product_catalog.py` is the product composition root and imports
`cpp_runtime_definition`. Delete the Host application registry so Host has no
C/C++ import. Remove central `profile_kind` switches for workflow-backed
applications and remove executable `builder_path` strings. Profile-only base
applications use trusted Host factories, not string imports. Plan 4 extends
this same product catalog with the frozen component catalog; it does not create
a second registry.

- [ ] **Step 5: Run composition and application tests**

```bash
uv run pytest tests/test_cpp_workflow_distribution.py tests/test_host_package_composition.py tests/test_agent_profiles.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the contribution boundary**

```bash
git add packages/embedagent-workflow-cpp packages/embedagent-host src tests
git commit -m "refactor: compose cpp workflow through core definition"
```

### Task 5: Remove Host And Resource Dependencies From C/C++

**Files:**
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workspace_recipes.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py`
- Modify: Core extension context/resource DTOs if required
- Test: `tests/test_local_resources.py`
- Test: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Add a resource-input contract test**

Write a test proving C/C++ recipe projection accepts already-discovered local
resource records and never imports Host discovery:

```python
def test_cpp_recipe_projection_consumes_resource_records():
    recipes = workspace_recipe_records(
        workspace="D:/demo",
        local_recipe_records=[{"name": "build", "command": "cmake --build build"}],
    )
    assert recipes[0]["name"] == "build"
```

- [ ] **Step 2: Replace direct local-resource discovery**

Remove imports of Host `local_resources`. Pass resource records through the
existing extension context or an explicit function parameter. Keep CMake,
Make, and Ninja detection package-owned, but keep generic `.embedagent/recipes`
file discovery Host-owned.

- [ ] **Step 3: Run resource and recipe tests**

```bash
uv run pytest tests/test_local_resources.py tests/test_workflow_extensions.py -v
```

Expected: PASS.

- [ ] **Step 4: Run import-boundary test**

```bash
uv run pytest tests/test_cpp_workflow_distribution.py::test_cpp_workflow_imports_only_core_and_standard_library_project_packages -v
```

Expected: PASS.

- [ ] **Step 5: Commit resource decoupling**

```bash
git add packages/embedagent-workflow-cpp packages/embedagent-core tests
git commit -m "refactor: decouple cpp recipes from host discovery"
```

### Task 6: Verify Behavior Parity And Wheel Isolation

**Files:**
- Modify: `scripts/check-python-distributions.py`
- Modify: `scripts/smoke-python-distributions.py`
- Modify: `scripts/offline-runtime-contract.json` only if package asset ids change
- Test: C/C++ workflow and bundle contract suites

- [ ] **Step 1: Add C/C++ wheel rules**

Require `embedagent_workflow_cpp/`, forbid product/Host/GUI files, and require
only `embedagent-core==0.1.0` in wheel metadata.

- [ ] **Step 2: Add isolated C/C++ import smoke**

Install Core plus C/C++ workflow, without Host/product/GUI, and run:

```python
from embedagent_workflow_cpp import cpp_runtime_definition
assert cpp_runtime_definition().agent_id == "embedagent.default_c_cpp"
```

- [ ] **Step 3: Run full C/C++ parity tests**

```bash
uv run pytest tests/ -m harness -v
uv run pytest tests/test_workflow_extensions.py tests/test_workflow_package_manifest.py tests/test_context_config.py tests/test_query_engine_build_lite.py -v
```

Expected: PASS.

- [ ] **Step 4: Build and inspect all wheels**

```bash
uv build --all-packages
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: all package reports pass.

- [ ] **Step 5: Commit distribution verification**

```bash
git add scripts tests packages
git commit -m "test: verify cpp workflow wheel isolation"
```

### Task 7: Close Plan 3 Documentation And Architecture Gates

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/tool-contracts.md`

- [ ] **Step 1: Update official package vocabulary**

Replace all active references to `embedagent.workflow_packages.c_cpp` with
`embedagent_workflow_cpp`. State that product composition selects the package
and that Core/Host/GUI do not import it.

- [ ] **Step 2: Strengthen architecture guards**

Update guard roots and banned imports for the new workspace layout. Delete old
tests that preserve application `builder_path` or central profile-kind behavior.

- [ ] **Step 3: Run Plan 3 gate**

```bash
uv run pytest tests/test_cpp_workflow_distribution.py tests/test_host_package_composition.py -v
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
uv build --all-packages
uv run python scripts/check-python-distributions.py --dist-dir dist
```

Expected: all commands exit zero.

- [ ] **Step 4: Run GUI gate**

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
```

Expected: PASS.

- [ ] **Step 5: Commit Plan 3 closeout**

```bash
git add README.md AGENTS.md docs tests src/embedagent/frontend/gui/static
git commit -m "docs: promote external cpp workflow package"
```
