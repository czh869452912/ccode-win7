# Workflow Extension Boundary Slice 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `InProcessAdapter`'s runtime dependency on `HarnessStateSynchronizer` while keeping the synchronizer class as an import-compatible service facade.

**Architecture:** The default C harness extension is now the product path for harness refresh and task snapshot persistence. `HarnessStateSynchronizer` remains available under `embedagent.services` as a lazy compatibility export for tests and older imports, but `InProcessAdapter` should not directly import it, construct it, or store `_harness_sync`.

**Tech Stack:** Python 3.8, pytest, existing `InProcessAdapter`, `CHarnessWorkflowExtension`, and `HarnessStateSynchronizer`.

---

### Task 1: Lock Adapter Decoupling With Tests

**Files:**
- Modify: `tests/test_workflow_extensions.py`
- Modify: `tests/test_characterization.py`

- [ ] **Step 1: Add source and behavior tests**

```python
def test_inprocess_adapter_no_longer_depends_on_harness_state_synchronizer(tmp_path):
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    source = (_REPO_ROOT / "src" / "embedagent" / "inprocess_adapter.py").read_text(
        encoding="utf-8"
    )
    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))

    assert "HarnessStateSynchronizer" not in source
    assert "_harness_sync" not in source
    assert not hasattr(adapter, "_harness_sync")
```

- [ ] **Step 2: Update characterization expectation**

`TestServiceDelegation.test_inprocess_adapter_has_harness_sync` should become a test that the adapter no longer owns `_harness_sync`.

- [ ] **Step 3: Run red tests**

Run: `uv run pytest tests/test_workflow_extensions.py::test_inprocess_adapter_no_longer_depends_on_harness_state_synchronizer tests/test_characterization.py::TestServiceDelegation::test_inprocess_adapter_does_not_own_harness_sync -v`

Expected before implementation: FAIL because `InProcessAdapter` still imports and constructs `HarnessStateSynchronizer`.

### Task 2: Remove Adapter Dependency

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`

- [ ] **Step 1: Remove `HarnessStateSynchronizer` from the services import list**

- [ ] **Step 2: Delete `_harness_sync` construction from `__init__`**

- [ ] **Step 3: Keep `_refresh_harness_state()` using `self.harness_workflow.refresh_managed_session()`**

Keep `src/embedagent/services/harness_state_synchronizer.py` as a compatibility facade. It may receive targeted compatibility fixes, but it must not return to the product adapter path.

### Task 3: Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Record Slice 6**

Document that adapter no longer constructs `HarnessStateSynchronizer`.

- [ ] **Step 2: Keep compatibility wording precise**

State that `HarnessStateSynchronizer` remains importable as a lazy compatibility facade, not a product-path runtime dependency.

### Task 4: Verify

- [ ] **Step 1: Run focused tests**

Run: `uv run pytest tests/test_workflow_extensions.py tests/test_characterization.py::TestServiceDelegation tests/test_services.py::TestHarnessStateSynchronizer tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_tool_catalog_exposes_renderer_metadata tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py -v`

- [ ] **Step 2: Run targeted lint**

Run: `uv run ruff check src/embedagent/inprocess_adapter.py tests/test_workflow_extensions.py tests/test_characterization.py tests/test_services.py`

- [ ] **Step 3: Run fast suite**

Run: `uv run pytest tests/ -m "not slow and not gui" -v`
