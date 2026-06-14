# Phase K Recovery State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reducer-backed recovery markers so hosted resume attempts are durable, replayable diagnostic state.

**Architecture:** Keep current restore behavior unchanged. Add a pure `RecoveryStateReducer` over `recovery_marker` transcript events, emit safe markers from hosted resume, and project `recovery_state` through restore results, managed sessions, protocol snapshots, and frontend session snapshots.

**Tech Stack:** Python 3.8, dataclasses, existing `TranscriptStore`, `SessionRestorer`, `InProcessAdapter`, `SessionSnapshotProjector`, pytest.

---

## Files

- Create: `src/embedagent/recovery_state.py`
- Create: `tests/test_recovery_state.py`
- Modify: `src/embedagent/session_restore.py`
- Modify: `src/embedagent/session_runtime.py`
- Modify: `src/embedagent/session_projector.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/protocol/__init__.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `tests/test_session_restore.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_architecture.py`
- Modify docs listed in the Phase K design
- Move: `docs/superpowers/specs/2026-06-14-phase-k-recovery-state-design.md`
- Move: `docs/superpowers/plans/2026-06-14-phase-k-recovery-state.md`

## Task 1: Reducer Tests

- [ ] **Step 1: Write failing reducer tests**

Create `tests/test_recovery_state.py` with:

```python
import json
import unittest

from embedagent.recovery_state import RecoveryStateReducer


class TestRecoveryStateReducer(unittest.TestCase):
    def test_reducer_projects_structured_recovery_marker(self):
        events = [
            {
                "type": "recovery_marker",
                "event_id": "evt-1",
                "seq": 5,
                "ts": "2026-06-14T00:00:00Z",
                "payload": {
                    "marker_id": "rm-1",
                    "created_at": "2026-06-14T00:00:00Z",
                    "reason": "resume",
                    "status": "partial",
                    "current_mode": "build",
                    "trusted_event_count": 8,
                    "transcript_event_count": 10,
                    "stop_reason": "duplicate_compact_boundary_id",
                    "skipped_count": 0,
                    "skip_reasons": [],
                    "operation_summary": {
                        "total_count": 3,
                        "started_count": 0,
                        "finished_count": 2,
                        "interrupted_count": 1,
                    },
                    "compaction_summary": {
                        "boundary_count": 1,
                        "latest_boundary_id": "cb-1",
                    },
                    "runtime_summary": {
                        "active_tool_count": 4,
                        "resource_revision": 2,
                        "model_profile_name": "local-model",
                    },
                    "metadata": {"source": "resume_session"},
                },
            }
        ]

        state = RecoveryStateReducer().reduce(events)
        payload = state.to_dict()

        self.assertEqual(payload["marker_count"], 1)
        self.assertEqual(payload["latest_marker_id"], "rm-1")
        self.assertEqual(payload["latest_marker"]["status"], "partial")
        self.assertEqual(payload["latest_marker"]["trusted_event_count"], 8)
        self.assertEqual(payload["latest_marker"]["operation_summary"]["interrupted_count"], 1)
        self.assertEqual(payload["latest_marker"]["compaction_summary"]["latest_boundary_id"], "cb-1")
        self.assertEqual(payload["latest_marker"]["runtime_summary"]["active_tool_count"], 4)
        self.assertEqual(payload["partial_count"], 1)
        self.assertEqual(payload["diagnostics"], [])
        json.dumps(payload, sort_keys=True)

    def test_reducer_deduplicates_marker_id(self):
        events = [
            {"type": "recovery_marker", "event_id": "evt-1", "seq": 1, "payload": {"marker_id": "rm-dup", "status": "clean"}},
            {"type": "recovery_marker", "event_id": "evt-2", "seq": 2, "payload": {"marker_id": "rm-dup", "status": "partial"}},
        ]

        payload = RecoveryStateReducer().reduce(events).to_dict()

        self.assertEqual(payload["marker_count"], 1)
        self.assertEqual(payload["latest_marker"]["status"], "clean")
        self.assertEqual(payload["diagnostics"][0]["reason"], "duplicate_marker_id")

    def test_reducer_handles_empty_transcript(self):
        payload = RecoveryStateReducer().reduce([]).to_dict()

        self.assertEqual(payload["marker_count"], 0)
        self.assertEqual(payload["latest_marker_id"], "")
        self.assertEqual(payload["status"], "empty")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run red test**

Run:

```bash
uv run pytest tests/test_recovery_state.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'embedagent.recovery_state'`.

## Task 2: Reducer Implementation

- [ ] **Step 1: Add `src/embedagent/recovery_state.py`**

Implement:

- `_clean_text`
- `_copy_dict`
- `_safe_int`
- `_safe_status`
- `RecoveryMarkerRecord`
- `RecoveryState`
- `RecoveryStateReducer`

Reducer rules:

- consume only `recovery_marker`
- require non-empty `marker_id`
- dedupe duplicate `marker_id`
- normalize status to `clean`, `partial`, or `degraded`; unknown becomes `degraded`
- keep only safe summary dictionaries
- expose `marker_count`, `latest_marker_id`, `latest_marker`, `markers`, `clean_count`, `partial_count`, `degraded_count`, `diagnostics`, `status`

- [ ] **Step 2: Run reducer tests**

Run:

```bash
uv run pytest tests/test_recovery_state.py -v
```

Expected: PASS.

## Task 3: Restore Projection

- [ ] **Step 1: Write failing restore test**

Add `test_restore_projects_recovery_state` to `tests/test_session_restore.py`.

Use `TranscriptStore.append_event(...)` to append:

- `session_meta`
- `recovery_marker` with `marker_id = "rm-restore"` and `status = "partial"`

Assert:

```python
result = SessionRestorer().restore(self.store.load_events(session_id))
recovery = result.recovery_state.to_dict()
self.assertEqual(recovery["marker_count"], 1)
self.assertEqual(recovery["latest_marker_id"], "rm-restore")
self.assertEqual(recovery["latest_marker"]["status"], "partial")
```

- [ ] **Step 2: Run red restore test**

Run:

```bash
uv run pytest tests/test_session_restore.py::TestSessionRestorer::test_restore_projects_recovery_state -v
```

Expected: FAIL because `SessionRestoreResult` has no `recovery_state`.

- [ ] **Step 3: Implement restore projection**

Modify `src/embedagent/session_restore.py`:

- import `RecoveryState`, `RecoveryStateReducer`
- add `recovery_state: RecoveryState = field(default_factory=RecoveryState)` to `SessionRestoreResult`
- reduce `RecoveryStateReducer().reduce(consumed_events)`
- pass it into `SessionRestoreResult`

- [ ] **Step 4: Run restore test**

Run:

```bash
uv run pytest tests/test_session_restore.py::TestSessionRestorer::test_restore_projects_recovery_state -v
```

Expected: PASS.

## Task 4: Hosted Resume Marker And Snapshot Projection

- [ ] **Step 1: Write failing adapter snapshot test**

Add `test_resume_appends_recovery_marker_and_snapshot_projects_recovery_state` to `tests/test_inprocess_adapter_frontend_api.py`.

Flow:

- create an adapter with `FakeClient`
- create a session
- capture `session_id`
- instantiate a fresh `InProcessAdapter` over the same workspace
- call `resume_session(session_id, "build")`
- load transcript events with `resumed_adapter.transcript_store.load_events(session_id)`
- assert one `recovery_marker`
- assert snapshot `recovery_state.marker_count == 1`
- assert latest marker `status == "clean"`

- [ ] **Step 2: Run red adapter test**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_resume_appends_recovery_marker_and_snapshot_projects_recovery_state -v
```

Expected: FAIL because no marker is emitted and snapshot has no `recovery_state`.

- [ ] **Step 3: Add managed/session snapshot fields**

Modify:

- `src/embedagent/session_runtime.py`: add `recovery_state: Dict[str, Any] = field(default_factory=dict)`
- `src/embedagent/session_projector.py`: include `"recovery_state": dict(getattr(state, "recovery_state", {}) or {})`
- `src/embedagent/protocol/__init__.py`: add `recovery_state: Dict[str, Any] = field(default_factory=dict)`
- `src/embedagent/core/adapter.py`: map `recovery_state=dict(snapshot.get("recovery_state") or {})`

- [ ] **Step 4: Add adapter reducer refresh and marker emission**

Modify `src/embedagent/inprocess_adapter.py`:

- import `RecoveryStateReducer`
- add `_refresh_recovery_state(state)`
- call it near `_refresh_runtime_config` / `_refresh_compaction_state`
- add `_append_recovery_marker(state, restored, current_mode, events)`
- emit `recovery_marker` after state is registered in `resume_session(...)`
- refresh `recovery_state` after emitting

Marker summaries:

- `operation_summary` from `operation_diagnostics(restored.operation_state)`
- `compaction_summary` from `restored.compaction_state.to_dict()`
- `runtime_summary` from reducer-backed runtime config

- [ ] **Step 5: Run adapter test**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_resume_appends_recovery_marker_and_snapshot_projects_recovery_state -v
```

Expected: PASS.

## Task 5: Protocol Conversion Test

- [ ] **Step 1: Add protocol conversion assertion**

Add `test_session_snapshot_from_dict_preserves_recovery_state` to `tests/test_architecture.py`.

Assert `_session_snapshot_from_dict({... "recovery_state": {"marker_count": 1}}).recovery_state["marker_count"] == 1`.

- [ ] **Step 2: Run test**

Run:

```bash
uv run pytest tests/test_architecture.py::TestProtocol::test_session_snapshot_from_dict_preserves_recovery_state -v
```

Expected: PASS after Task 4 Step 3.

## Task 6: Documentation

- [ ] **Step 1: Update source-of-truth docs**

Update:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`
- `docs/pi-inspired-agent-core-blueprint.md`

Required wording:

- Phase K is complete.
- `RecoveryStateReducer` is an internal read model, not a public API.
- `recovery_state` is diagnostics/replay state.
- It does not drive mode, tools, permissions, context, extension loading, or frontend policy.

- [ ] **Step 2: Archive working docs**

Move:

```bash
docs/superpowers/specs/2026-06-14-phase-k-recovery-state-design.md -> docs/archive/phase-k-recovery-state/2026-06-14-phase-k-recovery-state-design.md
docs/superpowers/plans/2026-06-14-phase-k-recovery-state.md -> docs/archive/phase-k-recovery-state/2026-06-14-phase-k-recovery-state.md
```

## Task 7: Verification And Commit

- [ ] **Step 1: Run focused tests**

```bash
uv run pytest tests/test_recovery_state.py tests/test_session_restore.py::TestSessionRestorer::test_restore_projects_recovery_state tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_resume_appends_recovery_marker_and_snapshot_projects_recovery_state tests/test_architecture.py::TestProtocol::test_session_snapshot_from_dict_preserves_recovery_state -v
```

- [ ] **Step 2: Run harness tests**

```bash
uv run pytest tests/ -m harness -v
```

- [ ] **Step 3: Run fast suite**

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

- [ ] **Step 4: Run static checks**

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md README.md docs src tests
git commit -m "feat: add recovery state reducer"
```

## Task 8: Merge Back

- [ ] **Step 1: Merge into main**

```bash
cd D:\Claude-project\ccode-win7
git merge --ff-only codex/phase-k-recovery-state
```

- [ ] **Step 2: Verify main**

Run focused tests, harness tests, ruff, black, and `git diff --check` on main.

- [ ] **Step 3: Cleanup**

```bash
git worktree remove .worktrees/codex-phase-k-recovery-state
git branch -d codex/phase-k-recovery-state
```
