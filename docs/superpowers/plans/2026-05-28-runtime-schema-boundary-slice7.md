# Runtime Schema Boundary Slice 7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ToolRuntime.schemas_for_mode()` and `ToolRuntime.allowed_tool_names()` expose only the workflow-neutral mode contract instead of the default C harness pack.

**Architecture:** Runtime remains the complete local tool catalog and pure mode-contract projector. Default C/C++ harness activation stays behind `CHarnessWorkflowExtension`, and callers that need harness tools must request schemas through explicit active tool names from the extension boundary.

**Tech Stack:** Python 3.8, pytest, existing `embedagent.tools` runtime and workflow extension APIs.

---

### Task 1: Lock Runtime Projection Behavior

**Files:**
- Modify: `tests/test_tools_package.py`
- Modify: `tests/test_tools_v2_runtime.py`
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Write failing tests**

Change runtime schema tests so `schemas_for_mode("build"|"debug"|"verify")` and `allowed_tool_names("debug")` assert pure mode-contract tools and reject harness-only tools such as `run_recipe`, `task_status`, `report_quality_v2`, and `record_failing_evidence`.

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeSchemas tests/test_tools_v2_runtime.py tests/test_workflow_extensions.py::test_tool_runtime_default_schemas_follow_mode_contract_not_harness_pack -v
```

Expected: FAIL because production runtime still unions default harness packs into `schemas_for_mode()` and `allowed_tool_names()`.

### Task 2: Simplify Runtime APIs

**Files:**
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/tools/harness_runtime.py`

- [ ] **Step 1: Implement minimal production change**

Make `ToolRuntime.allowed_tool_names()` return `allowed_tools_for(mode_name)`. Make `ToolRuntime.schemas_for_mode()` delegate to `schemas_for(mode_name, workflow_state=workflow_state)`. Keep `describe_mode()` and `pack_tool_names_for_mode()` available for harness extension paths.

- [ ] **Step 2: Run focused green tests**

Run the red test command again with an explicit Windows-safe temp directory.

### Task 3: Synchronize Architecture Docs

**Files:**
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/mode-schema.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Update source-of-truth wording**

Document that `schemas_for_mode()` is no longer a default harness compatibility projection; it is retained only as a compatibility alias for the pure mode contract. State that harness-aware schema projection must come from extension-active explicit tool names.

- [ ] **Step 2: Run docs-related search**

Run:

```bash
rg -n "schemas_for_mode|allowed_tool_names|default-harness compatibility|harness-aware paths" docs README.md AGENTS.md
```

Expected: Active docs no longer describe `ToolRuntime.schemas_for_mode()` as the path that activates default harness packs.

### Task 4: Verify Slice

**Files:**
- Test: changed tests and QueryEngine harness-extension tests

- [ ] **Step 1: Run targeted runtime and extension tests**

Run:

```bash
uv run pytest tests/test_tools_package.py::TestToolRuntimeSchemas tests/test_tools_v2_runtime.py tests/test_workflow_extensions.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py -v
```

Expected: PASS. QueryEngine still exposes default harness tools through the extension manager.

- [ ] **Step 2: Run lint on changed Python files**

Run:

```bash
uv run ruff check src/embedagent/tools/runtime.py src/embedagent/tools/harness_runtime.py tests/test_tools_package.py tests/test_tools_v2_runtime.py tests/test_workflow_extensions.py
```

Expected: PASS.
