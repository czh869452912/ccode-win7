# Pi-Like Agent Core Remaining Slices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining Pi-inspired Agent Core cleanup so Core stays minimal, workflow behavior lives behind extensions, and context/compact architecture has a clear next-step contract.

**Architecture:** Preserve the current product baseline while moving C/C++ workflow-specific behavior behind `CHarnessWorkflowExtension` and package-owned modules. Keep public/frontend payloads compatible while simplifying internal contracts. Treat compact/recovery reducers as read-only transcript-backed state, and document the future context planner direction without turning reducers into policy engines.

**Tech Stack:** Python 3.8, pytest, ruff, black, existing `embedagent` extension/runtime/context architecture.

---

## File Structure

- Create `src/embedagent/harness/context_reducers.py`
  - Owns C/C++ workflow context reducers for recipe results, quality reports, task status, and C build diagnostics.
- Modify `src/embedagent/context.py`
  - Keeps workflow-neutral reducers and generic helper surface only.
  - Exposes reusable helper methods needed by workflow reducer modules without importing harness code.
- Modify `src/embedagent/harness/extension.py`
  - Registers C workflow context reducers from the harness-owned module.
  - Uses generic workflow prompt naming.
- Modify `src/embedagent/harness/tool_registry.py`
  - Registers build/compile tool definitions as C workflow tools.
- Modify `src/embedagent/harness/tool_metadata.py`
  - Owns catalog metadata for C workflow build tools.
- Modify `src/embedagent/harness/packs.py`
  - Activates build tools through workflow packs only when appropriate.
- Modify `src/embedagent/harness/package_manifest.py`
  - Exposes build tools as workflow package declarations.
- Modify `src/embedagent/tools/runtime.py`
  - Removes `compile_ops.build_tools` from Core runtime initialization.
  - Keeps `compile_ops` importable for compatibility and tests, but not auto-registered in bare Core.
  - Continues internal `ToolCatalogEntry` faceting migration without changing external payload shape.
- Modify `src/embedagent/extensions.py`
  - Renames `HarnessPrompt` to `WorkflowPrompt` while keeping a compatibility alias.
- Modify `src/embedagent/query_engine.py`
  - Appends new workflow prompts with kind `workflow_prompt`.
  - Stops relying on legacy harness prompt naming in newly written code.
- Modify `src/embedagent/agent_extension_host.py`
  - Makes `propose_mode_switch` projection conditional on active mode-switch support rather than unconditional default tool exposure.
- Modify tests under `tests/`
  - Update expectations for bare runtime vs default C workflow extension registration.
  - Add source-level guard tests preventing C workflow reducers/build tools/prompt names from leaking back into Core.
- Modify durable docs:
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
  - `docs/design-change-log.md`

## Task 1: Move C Workflow Context Reducers Out Of Core

**Files:**
- Create: `src/embedagent/harness/context_reducers.py`
- Modify: `src/embedagent/context.py`
- Modify: `src/embedagent/harness/extension.py`
- Test: `tests/test_context_config.py`
- Test: `tests/test_workflow_extensions.py`

- [ ] Add tests that assert `ReducerRegistry` no longer defines C workflow reducer methods such as `_reduce_recipe_result`, `_reduce_quality`, and `_reduce_tasks`.
- [ ] Add tests that `CHarnessWorkflowExtension.register_context_reducers()` preserves `run_recipe`, `report_quality_v2`, `task_status`, and high-priority behavior.
- [ ] Create `harness/context_reducers.py` with pure functions that accept a `ReducerRegistry` instance as a helper object.
- [ ] Move recipe, quality, task, and build-diagnostic reducer logic into the harness module.
- [ ] Update `CHarnessWorkflowExtension.register_context_reducers()` to call the harness module registration helper.
- [ ] Run `uv run pytest tests/test_context_config.py tests/test_workflow_extensions.py -q`.

## Task 2: Move Compile/Build Tools Behind The C Workflow Extension

**Files:**
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/harness/tool_registry.py`
- Modify: `src/embedagent/harness/tool_metadata.py`
- Modify: `src/embedagent/harness/packs.py`
- Modify: `src/embedagent/harness/package_manifest.py`
- Test: `tests/test_tools_package.py`
- Test: `tests/test_workflow_extensions.py`
- Test: `tests/test_dynamic_tool_registration.py`

- [ ] Add/update tests proving a bare `ToolRuntime` catalog excludes `list_compilers`, `configure_build_env`, and `run_build`.
- [ ] Add/update tests proving default C workflow registration adds those tools with `source_type == "harness"`.
- [ ] Add/update active-tool tests proving build/debug/verify exposure comes through C workflow packs, not mode contracts.
- [ ] Remove `compile_ops.build_tools(self._ctx)` from Core runtime initialization.
- [ ] Register `compile_ops.build_tools(ctx)` from `build_c_workflow_tools(ctx)`.
- [ ] Move build tool catalog metadata from `_DEFAULT_TOOL_METADATA` into `C_WORKFLOW_TOOL_METADATA`.
- [ ] Add build tool names to appropriate C workflow packs.
- [ ] Run `uv run pytest tests/test_tools_package.py tests/test_workflow_extensions.py tests/test_dynamic_tool_registration.py -q`.

## Task 3: Neutralize Legacy Harness Prompt Naming

**Files:**
- Modify: `src/embedagent/extensions.py`
- Modify: `src/embedagent/harness/extension.py`
- Modify: `src/embedagent/query_engine.py`
- Test: `tests/test_workflow_extensions.py`

- [ ] Add tests asserting source code uses `WorkflowPrompt` for new extension prompt descriptors.
- [ ] Keep `HarnessPrompt = WorkflowPrompt` as a compatibility alias only.
- [ ] Update type hints/imports in harness extension and extension manager to use `WorkflowPrompt`.
- [ ] Ensure new workflow prompt messages keep kind `workflow_prompt`.
- [ ] Ensure no new code appends `harness_prompt` except explicit legacy compatibility paths.
- [ ] Run `uv run pytest tests/test_workflow_extensions.py -q`.

## Task 4: Reduce Default `propose_mode_switch` Tool Exposure

**Files:**
- Modify: `src/embedagent/agent_extension_host.py`
- Modify: `tests/test_dynamic_tool_registration.py`
- Modify: `tests/test_workflow_extensions.py`

- [ ] Add tests for the new rule: `propose_mode_switch` is not always injected into every active schema list.
- [ ] Preserve existing user-driven switching behavior through `/mode` and `ask_user`.
- [ ] Add a narrow condition for exposing `propose_mode_switch`, such as explicit active tool name or host configuration.
- [ ] Ensure bare QueryEngine active schemas no longer expand beyond the mode/extension active tool set by default.
- [ ] Run `uv run pytest tests/test_dynamic_tool_registration.py tests/test_workflow_extensions.py -q`.

## Task 5: Continue Tool Catalog Facet Migration Internally

**Files:**
- Modify: `src/embedagent/tools/runtime.py`
- Test: `tests/test_dynamic_tool_registration.py`
- Test: `tests/test_tools_package.py`

- [ ] Add tests that runtime execution uses `ToolCatalogEntry.presentation` and `ToolCatalogEntry.execution` internally while `to_dict()` remains legacy-compatible.
- [ ] Update `execute_with_interrupt()` to read presentation fields through `entry.presentation`.
- [ ] Update any local internal checks that can use `entry.execution` or `entry.context_policy` without changing external payloads.
- [ ] Keep compatibility properties temporarily for frontend/protocol callers.
- [ ] Run `uv run pytest tests/test_dynamic_tool_registration.py tests/test_tools_package.py -q`.

## Task 6: Document Compact/Context Follow-Up And Architecture State

**Files:**
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/design-change-log.md`

- [ ] Document that Core context reducers are workflow-neutral and C workflow reducers are package-owned.
- [ ] Document that compile/build tools are C workflow extension tools, not Core runtime defaults.
- [ ] Document generic `WorkflowPrompt` naming and `workflow_prompt` message kind.
- [ ] Document compact next direction: `ContextPlan`, context window generation, compact anchors, structured summary fields, and transcript-backed reducer diagnostics.
- [ ] Keep docs clear that compaction/recovery/runtime reducers do not drive permissions, tool activation, extension loading, or frontend-owned policy.
- [ ] Run `uv run pytest tests/ -m "not slow and not gui" -v` if time permits; otherwise run focused architecture/tool/context suites plus lint.

## Final Verification

- [ ] Run `uv run black --check src/ tests/`.
- [ ] Run `uv run ruff check src/ tests/`.
- [ ] Run focused pytest suites covering changed surfaces.
- [ ] Run `uv run pytest tests/ -m "not slow and not gui" -v` before claiming merge readiness.
- [ ] Review `git diff --stat` and source guard searches for stale names/leaks.
