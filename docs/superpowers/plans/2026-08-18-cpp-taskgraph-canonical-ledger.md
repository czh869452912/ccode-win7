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
- Test: `tests/test_session_journal.py`
- Test: `tests/test_c_cpp_workflow_contracts.py`

- [x] Enumerate every task mutation currently performed by `HarnessRunner`, `CHarnessWorkflowExtension`, and `refresh_managed_session`: graph creation, task status, phase, discipline, evidence, and repair.
- [x] Keep the existing `workflow_patch` envelope: it is already committed through `SessionJournal` and reduced into the generic workflow carrier, so a second C++ event family is unnecessary.
- [x] Reuse Core event identity, session id, monotonic `seq`, schema version, and deterministic `SessionReducer` replay. A projection never invents a task mutation absent from the ledger.
- [x] Existing `SessionJournal` preflight/replay tests cover invalid workflow event commits; the C++ slice adds projection rebuild and no-precommit-publication tests.

## Task 2: Implement append-before-apply task mutations

**Files:**
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/runner.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/session_graph_state.py`
- Modify: `packages/embedagent-core/src/embedagent_core/session_reducer.py`
- Test: `tests/test_c_cpp_workflow_runner_taskgraph.py`
- Test: `tests/test_c_cpp_workflow_task_projection.py`

- [x] Replace direct `graph_state.set()` mutations with a candidate graph that is published only through the existing `workflow_patch` journal commit path.
- [x] Make `HarnessSessionGraphState` a locked live projection cache keyed by session id, with projection rebuild and explicit `dispose()`; it cannot create durable truth by itself.
- [x] Ensure the workflow projection is generated from the candidate/replayed graph, while graph cache reconstruction reads only the committed workflow projection.
- [x] Keep workflow projection payloads JSON-safe and bounded; the C++ workflow stores summaries, task items, and metadata rather than raw source/tool output.

## Task 3: Derive or remove the sidecar

**Files:**
- Modify/remove: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/task_store.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py`
- Modify: `docs/applications/cpp-workflow.md`
- Test: `tests/test_c_cpp_workflow_task_projection.py`
- Test: `tests/test_c_cpp_workflow_runner_taskgraph.py`

- [x] Keep `task-graph.json` only as an explicitly versioned derived snapshot; active task reads use the normal canonical session projection.
- [x] Write it after the canonical projection refresh and include source transcript event count plus a canonical workflow fingerprint; restore/listing never prefers it over the session ledger.
- [x] Add tests for fresh adapter/process restore and corrupt sidecar; missing sidecars follow the same canonical restore path, and the provenance fields cover stale-snapshot detection.
- [x] Update the workflow authority document to state exactly which object is truth, which objects are projections, and which recovery path wins.

## Task 4: Lifecycle, concurrency, and recovery gates

**Files:**
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/session_graph_state.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Test: `tests/test_c_cpp_workflow_task_projection.py`
- Test: `tests/test_hosted_runtime.py`

- [x] Use the existing session lease/transaction as the single-writer boundary and protect the projection cache with a re-entrant lock.
- [x] Add teardown tests proving a closed extension/runtime drops graph cache entries and extension-owned resources.
- [x] Recovery/listing tests prove corrupt or missing sidecars cannot replace the replayed workflow projection; malformed/truncated transcript handling remains owned by Core journal recovery tests.
- [x] Resume uses the existing stable transcript prefix rules because TaskGraph is rebuilt from the restored workflow projection, never forked as an independent in-memory object.

## Verification

- [x] Run: `uv run pytest tests/test_c_cpp_workflow_runner_taskgraph.py tests/test_c_cpp_workflow_task_projection.py tests/test_c_cpp_workflow_contracts.py tests/test_session_journal.py tests/test_hosted_runtime.py -q`
- [x] Run: `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -q`
- [x] Run: `uv run --locked python scripts/lint.py`
- [ ] Run the C++ distribution/isolation tests required by the selected bundle plan before release integration.

## Exit criteria

After a process restart, replaying the canonical session ledger produces the same task graph and `Session.workflow_state["workflow"]` projection byte-for-byte (apart from explicitly documented timestamps). A missing or corrupt sidecar cannot change the result, and closing a session leaves no task graph cache or worker owned by the closed scope.
