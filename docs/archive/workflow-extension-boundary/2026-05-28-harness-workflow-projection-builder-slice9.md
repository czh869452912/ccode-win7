# Harness Workflow Projection Builder Slice 9 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move default C harness workflow projection assembly into a small harness-owned builder so Agent Core continues to consume generic `Session.workflow_state["workflow"]` while `Session.task_graph` remains an internal compatibility mirror.

**Architecture:** Add `embedagent.harness.workflow_projection` as the adapter between C harness internals and the generic workflow payload. `CHarnessWorkflowExtension` keeps owning task-graph mutation and synchronization, but delegates payload construction to the builder.

**Tech Stack:** Python 3.8, pytest, existing `CHarnessWorkflowExtension`, `TaskGraph`, and `Session.workflow_state`.

---

### Task 1: Lock The Projection Boundary

**Files:**
- Modify: `tests/test_workflow_extensions.py`
- Create: `src/embedagent/harness/workflow_projection.py`
- Modify: `src/embedagent/harness/extension.py`

- [ ] **Step 1: Add failing builder tests**

Add tests proving `build_c_harness_workflow_projection(graph, context=None)` returns the generic workflow dict and that `CHarnessWorkflowExtension._sync_workflow_state()` imports and uses that builder.

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_c_harness_workflow_projection_builder_shapes_generic_payload tests/test_workflow_extensions.py::test_c_harness_extension_delegates_workflow_projection_to_builder -v
```

Expected before implementation: FAIL because the builder module does not exist and `extension.py` still assembles the workflow dict inline.

### Task 2: Implement The Builder

**Files:**
- Create: `src/embedagent/harness/workflow_projection.py`
- Modify: `src/embedagent/harness/extension.py`

- [ ] **Step 1: Create the builder**

Implement `build_c_harness_workflow_projection(graph, context=None)` with the current payload fields:

```python
{
    "id": "c_harness",
    "label": "C Harness",
    "state": "idle" if graph.is_empty() else "active",
    "summary": summary,
    "items": items,
    "activity": activity,
    "metadata": {
        "current_phase": phase,
        "discipline_profile": discipline,
    },
}
```

- [ ] **Step 2: Delegate extension synchronization**

Replace inline dict assembly in `CHarnessWorkflowExtension._sync_workflow_state()` with:

```python
session.workflow_state["workflow"] = build_c_harness_workflow_projection(graph, context=context)
```

### Task 3: Synchronize Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Document the projection adapter**

State that `src/embedagent/harness/workflow_projection.py` owns C harness to generic workflow payload projection; frontend/core read generic workflow state only.

- [ ] **Step 2: Mark this as Slice 9**

Add a design-change-log entry and development tracker row for Slice 9.

### Task 4: Verify Slice

**Files:**
- Test: projection builder, workflow extension, QueryEngine/adapter focused paths

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_initialize_session_injects_profile_mode_and_harness_once -v
```

Expected: PASS.
- [ ] **Step 2: Run static checks**

Run:

```bash
uv run ruff check src/embedagent/harness/workflow_projection.py src/embedagent/harness/extension.py tests/test_workflow_extensions.py
uv run ruff format --check src/embedagent/harness/workflow_projection.py src/embedagent/harness/extension.py tests/test_workflow_extensions.py
git diff --check
```

Expected: PASS.
