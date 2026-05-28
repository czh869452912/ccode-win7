# Session Task Graph Lazy Boundary Slice 10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `embedagent.session` from eagerly importing the C harness `TaskGraph` while preserving the compatibility behavior that `Session().task_graph` starts as an empty graph.

**Architecture:** Replace the module-level `TaskGraph` import in `session.py` with a small default factory that imports `TaskGraph` only when a `Session` instance is created. This keeps Agent Core session import lighter without removing the default harness compatibility mirror yet.

**Tech Stack:** Python 3.8, pytest, dataclasses, existing `Session` and `TaskGraph`.

---

### Task 1: Lock The Import Boundary

**Files:**
- Modify: `tests/test_workflow_extensions.py`
- Modify: `src/embedagent/session.py`

- [ ] **Step 1: Add failing import-boundary test**

Add a subprocess test that imports `embedagent.session` and asserts `embedagent.harness.task_graph` is not in `sys.modules`.

- [ ] **Step 2: Run test to verify red**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_session_import_does_not_eagerly_load_harness_task_graph -v
```

Expected before implementation: FAIL because `session.py` imports `TaskGraph` at module import time.

### Task 2: Implement Lazy Default Factory

**Files:**
- Modify: `src/embedagent/session.py`
- Modify: `tests/test_task_graph_v2.py`

- [ ] **Step 1: Add `_empty_task_graph()`**

In `session.py`, remove the top-level `TaskGraph` import and define:

```python
def _empty_task_graph() -> Any:
    from embedagent.harness.task_graph import TaskGraph

    return TaskGraph.empty()
```

Use `task_graph: Any = field(default_factory=_empty_task_graph)`.

- [ ] **Step 2: Keep compatibility test green**

Keep `tests/test_task_graph_v2.py::TaskGraphV2Tests::test_session_starts_with_empty_task_graph` passing to prove `Session().task_graph` still returns a `TaskGraph`.

### Task 3: Synchronize Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Document lazy compatibility mirror**

State that `Session.task_graph` is a lazy compatibility mirror and importing `embedagent.session` must not eagerly load harness task graph internals.

- [ ] **Step 2: Mark this as Slice 10**

Add a tracker row and design-change-log entry for Slice 10.

### Task 4: Verify Slice

**Files:**
- Test: workflow extension boundary and task graph compatibility

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py tests/test_task_graph_v2.py tests/test_backward_compatibility.py::TestQueryEngineCompatibility::test_can_instantiate_with_minimal_args -v
```

Expected: PASS.
- [ ] **Step 2: Run static checks**

Run:

```bash
uv run ruff check src/embedagent/session.py tests/test_workflow_extensions.py tests/test_task_graph_v2.py
uv run ruff format --check src/embedagent/session.py tests/test_workflow_extensions.py tests/test_task_graph_v2.py
git diff --check
```

Expected: PASS.
