# Phase 2B: C++ TaskGraph Canonical Ledger

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Execute the design checkpoint before changing persistence code.

**Goal:** Remove the three-way C++ task state split between `HarnessSessionGraphState`, `Session.workflow_state`, and `task-graph.json`. Make one durable, replayable workflow record the source of truth and make all other forms projections.

**Architecture:** The C/C++ package owns task semantics. Core/Host continue to expose only the generic workflow carrier and session journal boundary. Task mutations must be committed through the canonical session ledger before live graph/projection updates. A sidecar may remain as an export or recovery cache only if it is derived, versioned, and never authoritative.

**Non-goals:** Do not move `TaskGraph` into Core, do not make Host interpret C++ phase/profile semantics, and do not add a second database or network service. Do not preserve compatibility with the current three-source write model after migration.

## Task 1: Design checkpoint and event schema

**Files:**
- Inspect/modify: `packages/embedagent-core/src/embedagent_core/session_journal.py`
- Inspect/modify: `packages/embedagent-core/src/embedagent_core/session_reducer.py`
- Inspect/modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/task_graph.py`
- Create/modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/task_events.py`
- Test: `tests/test_session_journal.py`
- Test: `tests/test_c_cpp_workflow_contracts.py`

- [ ] Enumerate every task mutation currently performed by `HarnessRunner`, `CHarnessWorkflowExtension`, and `refresh_managed_session`: graph creation, task status, phase, discipline, evidence, and repair.
- [ ] Decide whether the existing `workflow_patch` envelope can carry a lossless task mutation stream. If not, define a versioned C++ event family routed through `SessionJournal` and `SessionReducer` without changing the canonical `transcript.jsonl` location.
- [ ] Define event identity, session id, monotonic ordering, schema version, and deterministic replay rules. A projection must never be able to invent a task mutation that is absent from the ledger.
- [ ] Add preflight tests proving invalid task events do not change the live session or append to the ledger.

## Task 2: Implement append-before-apply task mutations

**Files:**
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/runner.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/session_graph_state.py`
- Modify: `packages/embedagent-core/src/embedagent_core/session_reducer.py`
- Test: `tests/test_c_cpp_workflow_runner_taskgraph.py`
- Test: `tests/test_c_cpp_workflow_task_projection.py`

- [ ] Replace direct `graph_state.set()` mutations with a workflow-owned command/commit path that appends a canonical event and then applies the same reducer used by restore.
- [ ] Make `HarnessSessionGraphState` a live projection cache keyed by session id, with explicit `restore()` and `dispose()`; it must not be able to create durable truth by itself.
- [ ] Ensure the workflow projection is generated from the replayed graph, not used as an input to reconstruct graph truth during normal operation.
- [ ] Keep all task event payloads JSON-safe, bounded, and free of prompts, source blobs, credentials, or raw tool output. Store references or summaries where needed.

## Task 3: Derive or remove the sidecar

**Files:**
- Modify/remove: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/task_store.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py`
- Modify: `docs/applications/cpp-workflow.md`
- Test: `tests/test_c_cpp_workflow_task_projection.py`
- Test: `tests/test_c_cpp_workflow_runner_taskgraph.py`

- [ ] Change `task-graph.json` from an independent write path into an explicitly versioned derived snapshot, or remove it if the normal projection/API can serve the same read model.
- [ ] If retained, write it only after the canonical ledger commit, include the source transcript sequence/checksum, and reject stale snapshots during restore instead of silently preferring them.
- [ ] Add tests for a fresh adapter/process restore, missing sidecar, corrupt sidecar, stale checksum, and a sidecar generated from the same ledger after replay.
- [ ] Update the workflow authority document to state exactly which object is truth, which objects are projections, and which recovery path wins.

## Task 4: Lifecycle, concurrency, and recovery gates

**Files:**
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/session_graph_state.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Test: `tests/test_c_cpp_workflow_task_projection.py`
- Test: `tests/test_hosted_runtime.py`

- [ ] Add per-session locking or an equivalent single-writer boundary around task event commit and graph projection.
- [ ] Add teardown tests proving a closed adapter drops graph cache entries, worker references, and extension-owned resources.
- [ ] Add recovery tests for a truncated final event, a failed preflight, and a replayed ledger with duplicate task event ids; no test may pass by loading an unverified sidecar as truth.
- [ ] Verify fork/resume behavior uses the existing stable transcript prefix rules and does not fork an in-memory graph without its corresponding event prefix.

## Verification

- [ ] Run: `uv run pytest tests/test_c_cpp_workflow_runner_taskgraph.py tests/test_c_cpp_workflow_task_projection.py tests/test_c_cpp_workflow_contracts.py tests/test_session_journal.py tests/test_hosted_runtime.py -q`
- [ ] Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -q`
- [ ] Run: `uv run --locked python scripts/lint.py`
- [ ] Run the C++ distribution/isolation tests required by the selected bundle plan.

## Exit criteria

After a process restart, replaying the canonical session ledger produces the same task graph and `Session.workflow_state["workflow"]` projection byte-for-byte (apart from explicitly documented timestamps). A missing or corrupt sidecar cannot change the result, and closing a session leaves no task graph cache or worker owned by the closed scope.
