# Workflow Extension Boundary Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion. This slice continues the already-approved workflow-extension boundary work.

**Goal:** Move frontend-facing task projection off direct `TaskGraph` reads and behind the generic workflow projection.

**Architecture:** The default C/C++ harness may still keep `Session.task_graph` as its internal compatibility mirror, but frontend and snapshot projection must read `Session.workflow_state["workflow"]`. `HarnessStateSynchronizer` remains as a compatibility service while delegating its real work into the built-in C harness workflow extension.

---

## Tasks

- [x] Add regression tests proving `SessionSnapshotProjector` prefers `Session.workflow_state["workflow"]` and no longer mentions `task_graph`.
- [x] Update `SessionSnapshotProjector` so legacy fields (`current_phase`, `discipline_profile`, `current_activity`, `task_summary`, `task_items`) are compatibility projections from the generic workflow payload.
- [x] Sync C harness state into `Session.workflow_state["workflow"]` during harness refresh.
- [x] Update `InProcessAdapter.get_session_snapshot()` so it does not call `HarnessRunner.describe_mode()` on the read path.
- [x] Update `InProcessAdapter.list_tasks()` so live session task APIs read workflow projection items, while persisted task snapshots remain the offline fallback.
- [x] Move harness refresh/snapshot persistence behavior into `CHarnessWorkflowExtension.refresh_managed_session()`, leaving `HarnessStateSynchronizer` as a compatibility facade.
- [x] Add boundary tests proving `InProcessAdapter` no longer imports or constructs `HarnessRunner` directly.
- [x] Run focused and fast-suite verification.
