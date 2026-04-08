# Agent Core Ownership Follow-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the highest-risk adapter leftovers from the agent core cutover so command execution, task truth, and snapshot projection all flow through the same runtime boundaries.

**Architecture:** Keep `QueryEngine` as the only execution owner. Route slash-command tool execution through engine-managed turn/interaction machinery instead of adapter-local permission loops. Then shrink adapter-owned derived workflow state so `TaskGraph` and projector outputs remain the only workflow truth.

**Tech Stack:** Python 3.8, unittest, existing `InProcessAdapter` / `QueryEngine` / `ManagedSession` / harness runtime / transcript-backed session model.

---

### Task 1: Remove Slash-Command Dual Path

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/query_engine.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`
- Test: `tests/test_query_engine_refactor.py`

- [ ] Add or update failing tests that prove `/run ...` and related command-triggered tool executions no longer use adapter-local permission / tool execution loops.
- [ ] Run the targeted tests and confirm they fail for the expected reason.
- [ ] Replace `_execute_tool_from_command(...)` with an engine-routed path, or a thin adapter wrapper over new engine API, so permission asks and tool execution re-enter the same action pipeline.
- [ ] Ensure command-triggered tool events keep stable engine-owned `turn_id` / `step_id` / `step_index`.
- [ ] Re-run the targeted tests and confirm they pass.

### Task 2: Reduce Adapter-Owned Derived Workflow State

**Files:**
- Modify: `src/embedagent/session_runtime.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/session_projector.py`
- Modify: `src/embedagent/workspace_profile.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`
- Test: `tests/test_harness_task_projection.py`
- Test: `tests/test_workspace_profile.py`

- [ ] Add or update failing tests that lock `TaskGraph` as the only live task truth for active sessions and assert snapshot/projected task fields do not depend on adapter-side fallback state.
- [ ] Run the targeted tests and confirm they fail correctly.
- [ ] Remove or shrink `ManagedSession` derived workflow fields where possible, and stop `list_tasks(...)` from falling back to `task_store.load_task_items(...)` for active in-memory sessions.
- [ ] Replace workspace-profile pending-task hints with task-graph-aware computation or remove the hint if a clean source is not available.
- [ ] Re-run the targeted tests and confirm they pass.

### Task 3: Align Public Runtime Contracts

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `tests/test_query_engine_refactor.py`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/frontend-protocol.md`

- [ ] Add or update failing tests for the public engine entrypoint names if renaming is done in this slice.
- [ ] Rename `submit_turn` / `resume_pending` to `submit_user_turn` / `resume_interaction`, or add explicit forwarders if a mechanical full rename is too risky for this slice.
- [ ] Remove stale adapter-owned harness injection helpers if they become unused after Task 1.
- [ ] Update source-of-truth docs to match the final contract names and ownership boundaries.
- [ ] Re-run focused regression tests and ensure docs reflect actual code.

### Task 4: Verification Sweep

**Files:**
- Verify only

- [ ] Run focused `.venv` unittest coverage for `tests.test_query_engine_refactor`, `tests.test_inprocess_adapter_frontend_api`, `tests.test_gui_backend_api`, `tests.test_harness_task_projection`, and any new targeted tests.
- [ ] Run `node src/embedagent/frontend/gui/webapp/run-local-tests.mjs` if frontend-visible event payloads change.
- [ ] Summarize which review findings are fully resolved and which are intentionally deferred.
