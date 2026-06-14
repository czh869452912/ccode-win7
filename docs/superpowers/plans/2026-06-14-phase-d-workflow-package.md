# Phase D Default C/C++ Workflow Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move default C/C++ workflow tool capability ownership out of `ToolRuntime` and into the bundled harness workflow package.

**Architecture:** Reuse the existing `ExtensionManager` / `AgentEventBus` reducer boundary. `CHarnessWorkflowExtension` becomes the owner of C/C++ tool registration, metadata, active tool packs, prompt units, task status, task graph state, and workflow projection. `ToolRuntime` remains workflow-neutral unless hosted product paths load the default extension set.

**Tech Stack:** Python 3.8, pytest, ruff, black, existing `ExtensionManager`, `ToolRuntime`, and `CHarnessWorkflowExtension`.

---

## File Map

- Modify: `src/embedagent/harness/extension.py`
  Add package-owned `register_tools(...)` and use harness-owned pack helpers.
- Create: `src/embedagent/harness/tool_metadata.py`
  Own default C/C++ workflow tool metadata.
- Create or Modify: `src/embedagent/harness/tool_registry.py`
  Build default C/C++ workflow `ToolDefinition` objects from existing recipe/discovery/session tool builders.
- Create or Modify: `src/embedagent/harness/packs.py`
  Own default C/C++ workflow pack definitions and `pack_tool_names(...)`.
- Modify: `src/embedagent/harness/runner.py`
  Import pack helpers from harness-owned module.
- Modify: `src/embedagent/tools/runtime.py`
  Remove harness imports, harness tool construction, and C/C++ metadata merge.
- Delete or shrink: `src/embedagent/tools/harness_runtime.py`
  Remove runtime-side harness facade after callers move.
- Modify: `src/embedagent/tooling/packs.py` and `src/embedagent/tooling/__init__.py`
  Keep compatibility exports only if needed by tests, but route them to harness-owned packs or remove product use.
- Modify: `tests/test_workflow_extensions.py`
  Add guardrails for bare runtime and hosted default package registration.
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
  Ensure hosted catalog still sees default C/C++ workflow tools.
- Modify: source-of-truth docs during D-E only.

---

## D-A: Package-Owned Tool Registration

**Files:**
- Modify: `src/embedagent/harness/extension.py`
- Create: `src/embedagent/harness/tool_registry.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Add failing tests for bare runtime and hosted package registration**

Add tests to `tests/test_workflow_extensions.py`:

```python
def test_bare_tool_runtime_does_not_register_default_c_workflow_tools(tmp_path):
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    names = set(item["name"] for item in runtime.catalog_entries())

    assert "read_file" in names
    assert "list_recipes" not in names
    assert "run_recipe" not in names
    assert "task_status" not in names
    assert "report_quality_v2" not in names


def test_default_c_workflow_extension_registers_workflow_tools(tmp_path):
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.extensions import ExtensionContext, ToolRegistrationEvent
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    default_set = build_default_extension_set(runtime)
    default_set.manager.register_tools(
        ToolRegistrationEvent(current_mode="build", workflow_state_name="chat", reason="test"),
        ExtensionContext(workspace=str(tmp_path), tool_registry=runtime),
    )
    names = set(item["name"] for item in runtime.catalog_entries())

    assert "list_recipes" in names
    assert "run_recipe" in names
    assert "task_status" in names
    assert "record_failing_evidence" in names
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_bare_tool_runtime_does_not_register_default_c_workflow_tools tests/test_workflow_extensions.py::test_default_c_workflow_extension_registers_workflow_tools -q
```

Expected: first test fails because `ToolRuntime` still registers harness tools, and second test may pass or duplicate-register depending current runtime behavior.

- [ ] **Step 3: Add harness tool registry**

Create `src/embedagent/harness/tool_registry.py`:

```python
from __future__ import annotations

from typing import List

from embedagent.tools import discovery_ops, recipe_ops, session_ops


def build_c_workflow_tools(ctx) -> List[object]:
    definitions = []
    definitions.extend(discovery_ops.build_tools(ctx))
    definitions.extend(recipe_ops.build_tools(ctx))
    definitions.extend(session_ops.build_tools(ctx))
    return definitions
```

- [ ] **Step 4: Register C workflow tools from the harness extension**

In `src/embedagent/harness/extension.py`, import `ToolRegistrationResult` and `build_c_workflow_tools`, then add:

```python
    def register_tools(self, event: Any, context: Any) -> ToolRegistrationResult:
        del event
        ctx = getattr(context, "tool_registry", None)
        tool_context = getattr(ctx, "_ctx", None)
        if tool_context is None:
            return ToolRegistrationResult(tools=[], source_id="embedagent.harness", source_type="harness")
        return ToolRegistrationResult(
            tools=build_c_workflow_tools(tool_context),
            source_id="embedagent.harness",
            source_type="harness",
        )
```

Use the existing runtime context until a public tool-construction context is added later. This keeps Phase D scoped to ownership movement without changing tool handler internals.

- [ ] **Step 5: Remove harness tool construction from `ToolRuntime.__init__`**

In `src/embedagent/tools/runtime.py`:

- remove `build_harness_tools` import
- remove `harness_tools = build_harness_tools(self._ctx)`
- remove the loop that registers `harness_tools`

- [ ] **Step 6: Run D-A tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_bare_tool_runtime_does_not_register_default_c_workflow_tools tests/test_workflow_extensions.py::test_default_c_workflow_extension_registers_workflow_tools tests/test_inprocess_adapter_frontend_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit D-A**

```bash
git add src/embedagent/harness/extension.py src/embedagent/harness/tool_registry.py src/embedagent/tools/runtime.py tests/test_workflow_extensions.py
git commit -m "feat: register c workflow tools from harness package"
```

---

## D-B: Package-Owned Tool Metadata

**Files:**
- Create: `src/embedagent/harness/tool_metadata.py`
- Modify: `src/embedagent/harness/tool_registry.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Add metadata ownership regression tests**

Add to `tests/test_workflow_extensions.py`:

```python
def test_tool_runtime_no_longer_imports_harness_runtime_metadata():
    source = (_REPO_ROOT / "src" / "embedagent" / "tools" / "runtime.py").read_text(
        encoding="utf-8"
    )

    assert "OFFICIAL_HARNESS_TOOL_METADATA" not in source
    assert "embedagent.tools.harness_runtime" not in source


def test_default_c_workflow_tool_metadata_survives_package_registration(tmp_path):
    from embedagent.default_extensions import build_default_extension_set
    from embedagent.extensions import ExtensionContext, ToolRegistrationEvent
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    default_set = build_default_extension_set(runtime)
    default_set.manager.register_tools(
        ToolRegistrationEvent(current_mode="verify", workflow_state_name="chat", reason="test"),
        ExtensionContext(workspace=str(tmp_path), tool_registry=runtime),
    )

    entry = runtime.tool_catalog_entry("run_recipe")
    assert entry["permission_category"] == "toolchain_exec"
    assert entry["source_type"] == "harness"
    assert entry["activity_kind"] == "diagnostic"
    assert entry["interrupt_behavior"] == "cancel"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_tool_runtime_no_longer_imports_harness_runtime_metadata tests/test_workflow_extensions.py::test_default_c_workflow_tool_metadata_survives_package_registration -q
```

Expected: import guard fails before metadata moves.

- [ ] **Step 3: Move metadata into `src/embedagent/harness/tool_metadata.py`**

Create the file and move the C/C++ workflow entries currently in `OFFICIAL_HARNESS_TOOL_METADATA` into:

```python
from __future__ import annotations

C_WORKFLOW_TOOL_METADATA = {
    ...
}
```

- [ ] **Step 4: Attach metadata inside `build_c_workflow_tools(...)`**

Update `src/embedagent/harness/tool_registry.py`:

```python
from embedagent.harness.tool_metadata import C_WORKFLOW_TOOL_METADATA


def _attach_metadata(tool):
    metadata = dict(C_WORKFLOW_TOOL_METADATA.get(tool.name, {}) or {})
    if metadata:
        tool.metadata.update(metadata)
    return tool
```

Return `[_attach_metadata(tool) for tool in definitions]`.

- [ ] **Step 5: Remove runtime metadata merge**

In `src/embedagent/tools/runtime.py`:

- remove `OFFICIAL_HARNESS_TOOL_METADATA` import
- remove `_DEFAULT_TOOL_METADATA.update(OFFICIAL_HARNESS_TOOL_METADATA)`

- [ ] **Step 6: Run D-B tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_tool_runtime_no_longer_imports_harness_runtime_metadata tests/test_workflow_extensions.py::test_default_c_workflow_tool_metadata_survives_package_registration tests/test_inprocess_adapter_frontend_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit D-B**

```bash
git add src/embedagent/harness/tool_metadata.py src/embedagent/harness/tool_registry.py src/embedagent/tools/runtime.py tests/test_workflow_extensions.py
git commit -m "feat: move c workflow tool metadata into harness package"
```

---

## D-C: Package-Owned Packs And Mode Description

**Files:**
- Create: `src/embedagent/harness/packs.py`
- Modify: `src/embedagent/harness/extension.py`
- Modify: `src/embedagent/harness/runner.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/tooling/packs.py`
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Add pack ownership guard tests**

Add to `tests/test_workflow_extensions.py`:

```python
def test_tool_runtime_no_longer_imports_harness_mode_describer():
    source = (_REPO_ROOT / "src" / "embedagent" / "tools" / "runtime.py").read_text(
        encoding="utf-8"
    )

    assert "OfficialRuntimeModes" not in source
    assert "pack_tool_names" not in source


def test_harness_package_owns_c_workflow_packs():
    from embedagent.harness.packs import C_WORKFLOW_CORE_PACK, pack_tool_names

    assert "run_recipe" not in C_WORKFLOW_CORE_PACK
    assert "run_recipe" in pack_tool_names("build_lite")
    assert "task_status" in pack_tool_names("verify")
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_tool_runtime_no_longer_imports_harness_mode_describer tests/test_workflow_extensions.py::test_harness_package_owns_c_workflow_packs -q
```

Expected: tests fail before `harness.packs` exists and runtime imports are removed.

- [ ] **Step 3: Create `src/embedagent/harness/packs.py`**

Move pack constants from `src/embedagent/tooling/packs.py` into harness-owned names:

```python
C_WORKFLOW_CORE_PACK = [...]
C_WORKFLOW_BUILD_LITE_PACK = C_WORKFLOW_CORE_PACK + [...]
C_WORKFLOW_DEBUG_LITE_PACK = [...]
C_WORKFLOW_VERIFY_PACK = [...]
C_WORKFLOW_PACKS = {...}


def pack_tool_names(pack_name):
    return list(C_WORKFLOW_PACKS.get(str(pack_name or "core"), C_WORKFLOW_CORE_PACK))
```

- [ ] **Step 4: Update harness imports**

In `src/embedagent/harness/extension.py` and `src/embedagent/harness/runner.py`, replace:

```python
from embedagent.tooling.packs import pack_tool_names
```

with:

```python
from embedagent.harness.packs import pack_tool_names
```

- [ ] **Step 5: Remove runtime mode describer usage**

In `src/embedagent/tools/runtime.py`:

- remove `OfficialRuntimeModes` import
- remove `pack_tool_names` import if only used by pack schemas
- remove `self._mode_runtime = OfficialRuntimeModes()`
- remove `describe_mode(...)`
- remove `schemas_for_pack(...)` if no product caller remains, or leave it as a non-harness compatibility method only if tests require it and route pack lookup away from runtime

Before removing `schemas_for_pack(...)`, run:

```bash
rg -n "schemas_for_pack|describe_mode\\(" src tests
```

If only harness/product callers remain, update those callers to use `CHarnessWorkflowExtension.describe_prompt(...)` instead of runtime mode description.

- [ ] **Step 6: Keep compatibility exports if needed**

If tests or docs still import `embedagent.tooling.packs`, update `src/embedagent/tooling/packs.py` to re-export from `embedagent.harness.packs` and add a short comment that product ownership is harness-side.

- [ ] **Step 7: Run D-C tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py tests/test_query_engine_refactor.py -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit D-C**

```bash
git add src/embedagent/harness/packs.py src/embedagent/harness/extension.py src/embedagent/harness/runner.py src/embedagent/tools/runtime.py src/embedagent/tooling/packs.py tests/test_workflow_extensions.py
git commit -m "feat: move c workflow packs into harness package"
```

---

## D-D: Core/Bare Runtime Guardrails

**Files:**
- Modify: `tests/test_workflow_extensions.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify source only if guardrails reveal leaks.

- [ ] **Step 1: Add import isolation tests**

Add to `tests/test_workflow_extensions.py`:

```python
def test_importing_tool_runtime_does_not_import_harness_runtime_modules():
    script = (
        "import sys\n"
        "import embedagent.tools.runtime\n"
        "for name in ('embedagent.tools.harness_runtime', 'embedagent.harness.runner'):\n"
        "    print(name, name in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    assert "embedagent.tools.harness_runtime False" in result.stdout
    assert "embedagent.harness.runner False" in result.stdout
```

- [ ] **Step 2: Add hosted catalog guard test**

Add or update a test proving hosted adapter registration:

```python
def test_inprocess_adapter_catalog_includes_default_c_workflow_tools(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    items = adapter.tool_catalog()
    names = set(item["name"] for item in items.get("items", []))

    assert "run_recipe" in names
    assert "task_status" in names
```

- [ ] **Step 3: Run guardrail tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py tests/test_inprocess_adapter_frontend_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run focused architecture suite**

Run:

```bash
uv run pytest tests/test_agent_lifecycle.py tests/test_query_engine_refactor.py tests/test_session_operation_log.py tests/test_inprocess_adapter_frontend_api.py tests/test_workflow_extensions.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit D-D**

```bash
git add tests/test_workflow_extensions.py tests/test_inprocess_adapter_frontend_api.py src/embedagent
git commit -m "test: guard bare core from c workflow package leaks"
```

---

## D-E: Documentation And Closeout

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/agent-harness-v2.md`
- Move: `docs/superpowers/specs/2026-06-14-phase-d-workflow-package-design.md`
- Move: `docs/superpowers/plans/2026-06-14-phase-d-workflow-package.md`

- [ ] **Step 1: Update source-of-truth docs**

Record that Phase D is complete for default C/C++ package ownership:

- `ToolRuntime` is workflow-neutral at construction.
- default C/C++ tools and metadata are registered by `CHarnessWorkflowExtension.register_tools(...)`.
- harness packs live in the harness package.
- hosted adapters still load the default package through `default_extensions.py`.

- [ ] **Step 2: Archive slice docs**

Move completed docs to:

```text
docs/archive/phase-d-workflow-package/2026-06-14-phase-d-workflow-package-design.md
docs/archive/phase-d-workflow-package/2026-06-14-phase-d-workflow-package.md
```

- [ ] **Step 3: Run documentation scans**

Run:

```bash
rg -n "Phase D.*(next|pending|准备)|ToolRuntime.*harness_runtime|OfficialRuntimeModes|OFFICIAL_HARNESS_TOOL_METADATA" README.md AGENTS.md docs src tests --glob "!docs/archive/**"
```

Expected: no active stale references except historical changelog context or explicit negative tests.

- [ ] **Step 4: Run final verification**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
uv run pytest tests/ -m "not slow and not gui" -q
```

Expected: all commands pass.

- [ ] **Step 5: Commit D-E**

```bash
git add README.md AGENTS.md docs
git commit -m "docs: close phase d workflow package extraction"
```

---

## Final Review

- [ ] Run `git status --short --branch`.
- [ ] Run `git log --oneline -8`.
- [ ] Confirm each subphase has a commit.
- [ ] Report verification evidence and remaining gap: Phase E self-extension authoring loop.
