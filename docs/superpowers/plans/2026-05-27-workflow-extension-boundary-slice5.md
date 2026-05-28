# Workflow Extension Boundary Slice 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `InProcessAdapter` and session-scoped `QueryEngine` share one `ExtensionManager` instance so runtime tool activation and frontend catalog visibility are sourced from the same extension chain.

**Architecture:** `InProcessAdapter` owns the default extension set for its hosted runtime. It registers the default C harness extension once, passes the manager into every `QueryEngine`, and uses the same manager for frontend catalog visibility. This keeps project-local/custom extension discovery deferred while removing today's adapter/engine extension split.

**Tech Stack:** Python 3.8, pytest, existing `ExtensionManager`, `CHarnessWorkflowExtension`, `InProcessAdapter`, and `QueryEngine`.

---

### Task 1: Lock Shared Manager Behavior

**Files:**
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Add a catalog-visible custom extension test**

```python
class CatalogExtension(object):
    def allowed_tool_names(self, mode_name, workflow_state="chat"):
        del workflow_state
        if mode_name == "build":
            return {"git_diff"}
        return set()

def test_inprocess_adapter_tool_catalog_uses_shared_extension_manager(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    adapter.extension_manager.register(CatalogExtension())

    names = set(item.get("name") for item in adapter.get_tool_catalog())

    assert "git_diff" in names
```

- [ ] **Step 2: Add an engine identity test**

```python
def test_inprocess_adapter_passes_extension_manager_to_query_engine(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    engine = adapter._build_engine()

    assert engine.extension_manager is adapter.extension_manager
```

- [ ] **Step 3: Run red tests**

Run: `uv run pytest tests/test_workflow_extensions.py::test_inprocess_adapter_tool_catalog_uses_shared_extension_manager tests/test_workflow_extensions.py::test_inprocess_adapter_passes_extension_manager_to_query_engine -v`

Expected before implementation: FAIL because `InProcessAdapter` does not expose/use a shared `extension_manager`.

### Task 2: Share The Extension Manager

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`

- [ ] **Step 1: Import `ExtensionManager`**

Use the existing `embedagent.extensions.ExtensionManager`.

- [ ] **Step 2: Create default harness extension once**

Keep `self.harness_workflow = CHarnessWorkflowExtension(tools=self.tools)` for compatibility and refresh methods.

- [ ] **Step 3: Register it in `self.extension_manager`**

```python
self.extension_manager = ExtensionManager([self.harness_workflow])
```

- [ ] **Step 4: Pass the manager into `_build_engine()`**

Add `extension_manager=self.extension_manager` to the `QueryEngine` constructor call.

- [ ] **Step 5: Use manager for `get_tool_catalog()`**

Replace direct `self.harness_workflow.allowed_tool_names(...)` calls with:

```python
allowed.update(
    self.extension_manager.allowed_tool_names(
        mode_name,
        workflow_state="chat",
        fallback=set(),
    )
)
```

### Task 3: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Document adapter-owned manager**

State that the hosted runtime has one `ExtensionManager` shared by `InProcessAdapter`, session-scoped `QueryEngine`, and frontend tool catalog visibility.

- [ ] **Step 2: Keep project-local discovery deferred**

Clarify that this is internal wiring only, not a plugin marketplace or extension discovery feature.

### Task 4: Verify

- [ ] **Step 1: Run focused tests**

Run: `uv run pytest tests/test_workflow_extensions.py tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_tool_catalog_exposes_renderer_metadata tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py -v`

- [ ] **Step 2: Run targeted lint**

Run: `uv run ruff check src/embedagent/inprocess_adapter.py src/embedagent/extensions.py src/embedagent/query_engine.py tests/test_workflow_extensions.py`

- [ ] **Step 3: Run fast suite**

Run: `uv run pytest tests/ -m "not slow and not gui" -v`
