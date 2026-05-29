# Turn Orchestrator Task Status Projection Slice 11 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the extracted core `TurnOrchestrator` from reading `Session.task_graph` directly when serving the legacy `task_status` tool path.

**Architecture:** `TurnOrchestrator` should treat task status as a projection read from `Session.workflow_state["workflow"]`, matching `SessionSnapshotProjector` and frontend task APIs. Default C harness internals may still maintain `TaskGraph`, but core strategies must not inspect it directly.

**Tech Stack:** Python 3.8, pytest, existing `TurnOrchestrator`, `Session.workflow_state`, and `Observation`.

---

### Task 1: Lock The Strategy Boundary

**Files:**
- Modify: `tests/test_strategies.py`
- Modify: `src/embedagent/strategies/turn_orchestrator.py`

- [ ] **Step 1: Add failing behavior test**

Add a `task_status` turn test where `session.task_graph` raises if inspected and `session.workflow_state["workflow"]` contains summary, items, activity, and metadata. The returned observation must be built from workflow projection.

- [ ] **Step 2: Add source boundary test**

Add a source-inspection assertion that `turn_orchestrator.py` does not contain `session.task_graph`.

- [ ] **Step 3: Run tests to verify red**

Run:

```bash
uv run pytest tests/test_strategies.py::TestTurnOrchestrator::test_task_status_reads_workflow_projection_without_task_graph tests/test_strategies.py::TestTurnOrchestrator::test_turn_orchestrator_no_longer_reads_session_task_graph -v
```

Expected before implementation: FAIL because `_execute_action()` reads `session.task_graph.is_empty()`.

### Task 2: Implement Workflow Projection Read

**Files:**
- Modify: `src/embedagent/strategies/turn_orchestrator.py`

- [ ] **Step 1: Add helper to read workflow payload**

Add a small private helper that returns a dict from `session.workflow_state["workflow"]` when available and `{}` otherwise.

- [ ] **Step 2: Build task_status observation from workflow**

Use workflow `summary`, `items`, and `metadata.current_phase` / `metadata.discipline_profile`. Keep the existing `"no active tasks"` fallback.

### Task 3: Synchronize Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Document strategy read model**

State that workflow-neutral strategies and projectors read task state from `Session.workflow_state["workflow"]`, not `Session.task_graph`.

- [ ] **Step 2: Mark this as Slice 11**

Add tracker and design-change-log entries.

### Task 4: Verify Slice

**Files:**
- Test: strategies, workflow extension boundary, query engine refactor

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_strategies.py tests/test_workflow_extensions.py tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_keeps_discarded_parallel_results_out_of_guard_stop -v
```

Expected: PASS.
- [ ] **Step 2: Run static checks**

Run:

```bash
uv run ruff check src/embedagent/strategies/turn_orchestrator.py tests/test_strategies.py
uv run ruff format --check src/embedagent/strategies/turn_orchestrator.py tests/test_strategies.py
git diff --check
```

Expected: PASS.
