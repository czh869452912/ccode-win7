# Workflow Extension Boundary Slice 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move harness-specific tools out of the built-in mode allowed-tool contract while keeping the default C/C++ harness available through the workflow extension.

**Architecture:** Built-in modes describe workflow-neutral permission and write boundaries. The default C harness extension activates recipe, task, debug-evidence, and quality-report tools through workflow packs. Frontend tool catalog visibility unions the mode contract with extension-owned active tools.

**Tech Stack:** Python 3.8, pytest, existing `embedagent.modes`, `CHarnessWorkflowExtension`, `ToolRuntime`, and `InProcessAdapter`.

---

### Task 1: Lock The Boundary With Tests

**Files:**
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Add tests showing mode tools are workflow-neutral**

```python
def test_mode_allowed_tools_no_longer_own_harness_workflow_tools():
    from embedagent.modes import allowed_tools_for

    harness_tools = {
        "list_recipes",
        "run_recipe",
        "report_quality_v2",
        "record_failing_evidence",
        "task_status",
    }
    for mode_name in ("explore", "spec", "build", "debug", "verify"):
        leaked = sorted(set(allowed_tools_for(mode_name)) & harness_tools)
        assert leaked == [], "%s leaks harness tools: %s" % (mode_name, leaked)
```

- [ ] **Step 2: Add tests proving runtime and frontend paths still see harness tools through extensions**

```python
def test_tool_runtime_default_schemas_follow_mode_contract_not_harness_pack(tmp_path):
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))

    default_names = set(
        item["function"]["name"]
        for item in runtime.schemas_for("verify", workflow_state="review")
    )
    harness_names = set(
        item["function"]["name"]
        for item in runtime.schemas_for_mode("verify", workflow_state="review")
    )

    assert "read_file" in default_names
    assert "grep_text" in default_names
    assert "run_recipe" not in default_names
    assert "task_status" not in default_names
    assert "run_recipe" in harness_names
    assert "report_quality_v2" in harness_names
    assert "task_status" in harness_names
```

- [ ] **Step 3: Add frontend catalog regression test**

```python
def test_frontend_tool_catalog_gets_harness_tools_from_workflow_extension(tmp_path, monkeypatch):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    monkeypatch.setattr(
        "embedagent.inprocess_adapter.allowed_tools_for",
        lambda mode_name: ["read_file", "ask_user"],
    )

    names = set(item.get("name") for item in adapter.get_tool_catalog())

    assert "read_file" in names
    assert "run_recipe" in names
    assert "report_quality_v2" in names
    assert "task_status" in names
```

- [ ] **Step 4: Run red tests**

Run: `uv run pytest tests/test_workflow_extensions.py::test_mode_allowed_tools_no_longer_own_harness_workflow_tools tests/test_workflow_extensions.py::test_tool_runtime_default_schemas_follow_mode_contract_not_harness_pack tests/test_workflow_extensions.py::test_frontend_tool_catalog_gets_harness_tools_from_workflow_extension -v`

Expected: FAIL before implementation because mode allowed tools still contain harness tools and catalog filtering only reads mode contracts.

### Task 2: Shrink Mode Allowed Tools

**Files:**
- Modify: `src/embedagent/modes.py`
- Modify: `tests/test_modes.py`
- Modify: `tests/test_tools_package.py`

- [ ] **Step 1: Remove harness-owned tools from built-in mode `allowed_tools`**

Keep `ask_user` and mode-native read/write tools. Remove `list_recipes`, `run_recipe`, `report_quality_v2`, `record_failing_evidence`, and `task_status`.

- [ ] **Step 2: Make `verify` a read-only mode contract**

Set verify tools to:

```python
[
    "read_file",
    "list_dir",
    "glob_files",
    "grep_text",
    "ask_user",
]
```

- [ ] **Step 3: Update mode tests to assert workflow-neutral contracts**

Replace old task/recipe assertions with assertions that harness tools are absent from every mode contract and that build/debug keep write tools while verify remains read-only.

- [ ] **Step 4: Update ToolRuntime schema tests**

`schemas_for()` should now represent the pure mode contract; `schemas_for_mode()` remains the compatibility/default-harness path that exposes harness packs.

### Task 3: Preserve Frontend Catalog Visibility

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`

- [ ] **Step 1: Union extension active tools into `get_tool_catalog()`**

For every built-in mode, union `allowed_tools_for(mode_name)` with `self.harness_workflow.allowed_tool_names(mode_name, workflow_state="chat")`.

- [ ] **Step 2: Keep catalog filtering narrow**

Continue to omit legacy duplicate tools such as `compile_project`; only mode-contract tools and extension-active tools should pass.

### Task 4: Synchronize Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/mode-schema.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Document mode schema as workflow-neutral**

State that recipe/task/quality/evidence tools are activated by the default C harness extension, not owned by built-in mode contracts.

- [ ] **Step 2: Document frontend catalog union behavior**

Tool catalog includes mode-contract tools plus workflow-extension active tools.

### Task 5: Verify

- [ ] **Step 1: Run focused tests**

Run: `uv run pytest tests/test_workflow_extensions.py tests/test_modes.py tests/test_tools_package.py::TestToolRuntimeSchemas tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApi::test_tool_catalog_exposes_renderer_metadata -v`

- [ ] **Step 2: Run targeted lint**

Run: `uv run ruff check src/embedagent/modes.py src/embedagent/inprocess_adapter.py src/embedagent/tools/runtime.py src/embedagent/tools/harness_runtime.py tests/test_workflow_extensions.py tests/test_modes.py tests/test_tools_package.py`

- [ ] **Step 3: Run fast suite**

Run: `uv run pytest tests/ -m "not slow and not gui" -v`
