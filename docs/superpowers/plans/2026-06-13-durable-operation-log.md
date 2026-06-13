# Durable Operation Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Pi-inspired durable operation log slice so restore can explain completed and interrupted runtime operations without changing hosted C/C++ behavior.

**Architecture:** Keep `TranscriptStore` as the append-only JSONL ledger. Add a pure operation reducer over transcript events, then attach its output to `SessionRestoreResult`. The first slice must consume current durable events (`tool_call`, `tool_result`, `step_started`, `loop_transition`) and also understand future explicit `operation_started` / `operation_finished` / `operation_interrupted` events.

**Tech Stack:** Python 3.8, dataclasses, unittest/pytest, existing `TranscriptStore` and `SessionRestorer`.

---

## File Structure

- Create: `src/embedagent/session_operation_log.py`
  - Pure reducer for operation lifecycle state.
  - Contains `OperationRecord`, `OperationLogState`, and `OperationLogReducer`.
- Modify: `src/embedagent/session_restore.py`
  - Import the reducer.
  - Add `operation_state` to `SessionRestoreResult`.
  - Feed the same valid transcript prefix into the reducer.
- Create: `tests/test_session_operation_log.py`
  - Unit tests for the pure reducer and restore integration.
- Modify: `docs/development-tracker.md`
  - Mark T-029 as in progress after the first code slice lands.
- Modify: `docs/design-change-log.md`
  - Add a DC entry for the first durable operation-log implementation slice.

---

### Task 1: Pure Operation Reducer

**Files:**
- Create: `src/embedagent/session_operation_log.py`
- Create: `tests/test_session_operation_log.py`

- [ ] **Step 1: Write failing tests**

Add tests that import `OperationLogReducer` and assert:

```python
def test_unfinished_tool_call_is_interrupted_and_not_retryable(self):
    events = [{
        "schema_version": 2,
        "session_id": "sess-op",
        "event_id": "evt-tool",
        "seq": 1,
        "ts": "2026-06-13T00:00:00Z",
        "type": "tool_call",
        "payload": {
            "turn_id": "t-1",
            "step_id": "s-1",
            "call_id": "call-read",
            "tool_name": "read_file",
            "arguments": {"path": "src/demo.c"},
        },
    }]

    state = OperationLogReducer().reduce(events)

    record = state.operations["tool:call-read"]
    self.assertEqual(record.status, "interrupted")
    self.assertEqual(record.kind, "tool_call")
    self.assertFalse(record.retryable)
    self.assertEqual(record.interrupted_reason, "restore_incomplete_operation")
```

Also test a completed tool call and explicit `operation_started` / `operation_finished` events.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_session_operation_log.py -q
```

Expected: FAIL because `embedagent.session_operation_log` does not exist.

- [ ] **Step 3: Implement reducer**

Implement:

```python
@dataclass
class OperationRecord(object):
    operation_id: str
    kind: str
    status: str = "started"
    turn_id: str = ""
    step_id: str = ""
    tool_call_id: str = ""
    parent_operation_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    interrupted_reason: str = ""
    retryable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
```

`OperationLogReducer.reduce(events)` must start operations from explicit `operation_started` and legacy `tool_call` / `step_started`, finish them from explicit `operation_finished`, `operation_interrupted`, `tool_result`, and terminal `loop_transition`, then mark remaining started operations interrupted with `retryable=False` by default.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run pytest tests/test_session_operation_log.py -q
```

Expected: PASS.

---

### Task 2: Restore Integration

**Files:**
- Modify: `src/embedagent/session_restore.py`
- Modify: `tests/test_session_operation_log.py`

- [ ] **Step 1: Write failing integration test**

Add a test that builds a transcript with `TranscriptStore`, restores it, and asserts:

```python
result = SessionRestorer().restore(store.load_events(session_id))
record = result.operation_state.operations["tool:call-read"]
self.assertEqual(record.status, "interrupted")
self.assertEqual(result.operation_state.interrupted_count, 1)
```

- [ ] **Step 2: Run integration test to verify it fails**

Run:

```bash
uv run pytest tests/test_session_operation_log.py -q
```

Expected: FAIL because `SessionRestoreResult` has no `operation_state`.

- [ ] **Step 3: Attach reducer to restore**

Modify `SessionRestoreResult`:

```python
operation_state: OperationLogState = field(default_factory=OperationLogState)
```

At the end of `SessionRestorer.restore`, reduce only the consumed strict prefix:

```python
operation_events = events[:consumed_event_count]
operation_state = OperationLogReducer().reduce(operation_events)
```

Pass `operation_state=operation_state` into `SessionRestoreResult`.

- [ ] **Step 4: Run focused restore tests**

Run:

```bash
uv run pytest tests/test_session_operation_log.py tests/test_session_restore.py -q
```

Expected: PASS.

---

### Task 3: First Runtime Emission Boundary

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_query_engine_refactor.py` or a focused new test if an existing fixture is clearer.

- [ ] **Step 1: Characterize current durable events**

Write a focused test proving normal tool execution already emits `tool_call` and `tool_result` events that the operation reducer can consume.

- [ ] **Step 2: Add explicit operation lifecycle emission only where stable**

Add `_emit_operation_started`, `_emit_operation_finished`, and `_emit_operation_interrupted` helpers around the current transcript append boundary. In this slice, do not replace existing `tool_call` / `tool_result`; explicit operation events are additive and schema_v2.

- [ ] **Step 3: Verify no behavior changes**

Run:

```bash
uv run pytest tests/test_session_operation_log.py tests/test_session_restore.py tests/test_query_engine_refactor.py -q
```

Expected: PASS.

---

### Task 4: Documentation Closeout

**Files:**
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Update tracker**

Change T-029 from `planned` to `in_progress` and note that the first reducer-backed restore slice has landed.

- [ ] **Step 2: Update change log**

Add a DC entry for the durable operation-log reducer slice. State that this is an implementation step toward the blueprint, not the full AgentKernel extraction.

- [ ] **Step 3: Verify docs**

Run:

```bash
git diff --check
rg -n "durable operation log|OperationLogReducer|T-029|DC-" docs/development-tracker.md docs/design-change-log.md docs/pi-inspired-agent-core-blueprint.md
```

Expected: no whitespace errors and the new slice is traceable.

---

## Self-Review

- Spec coverage: Phase A from `docs/pi-inspired-agent-core-blueprint.md` starts with durable runtime state, interrupted operations, and non-idempotent tool-call retry safety. Tasks 1 and 2 implement the reducer and restore state; Task 3 starts additive runtime emission; Task 4 keeps source-of-truth docs synchronized.
- Placeholder scan: no placeholder markers or "implement later" phrasing are used.
- Type consistency: `OperationRecord`, `OperationLogState`, and `OperationLogReducer` are introduced in Task 1 and reused by Task 2.
