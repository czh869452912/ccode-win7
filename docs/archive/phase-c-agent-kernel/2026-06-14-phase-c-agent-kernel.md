# Phase C AgentKernel Lifecycle Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract QueryEngine lifecycle orchestration into AgentKernel boundaries while preserving hosted C/C++ behavior and current transcript/session contracts.

**Architecture:** Introduce `AgentLifecycleJournal` first, then route turn frames, suspend/resume, and loop ownership through `AgentKernel` and `AgentLoop`. `QueryEngine` remains the public facade while lifecycle decisions move behind internal kernel services.

**Tech Stack:** Python 3.8, unittest/pytest, existing EmbedAgent session/transcript/runtime modules.

---

## File Structure

- Create: `src/embedagent/agent_lifecycle.py`
  - Owns lifecycle event emission, pending interaction lifecycle, transition save points, context/workflow operation helpers, and compact boundary recording.
- Modify: `src/embedagent/query_engine.py`
  - Delegates lifecycle helpers to `AgentLifecycleJournal`, then later delegates turn frames and loop execution to `AgentKernel`.
- Modify: `src/embedagent/agent_loop.py`
  - Evolves from a thin callback wrapper into a loop owner.
- Create: `src/embedagent/agent_kernel.py`
  - Owns turn frame begin/finish/interruption and later suspend/resume coordination.
- Modify: `src/embedagent/inprocess_adapter.py`
  - Keeps public adapter behavior while using kernel-backed session state for pending interaction consistency if needed.
- Test: `tests/test_agent_lifecycle.py`
  - Direct unit coverage for journal and kernel lifecycle helpers.
- Modify: `tests/test_query_engine_refactor.py`
  - Characterization tests for unchanged transcript event ordering and QueryEngine delegation.
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
  - Regression tests for pending interaction atomicity and frontend-facing snapshots.
- Modify docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/pi-inspired-agent-core-blueprint.md`

## Task 1: C-A Lifecycle Journal

**Files:**
- Create: `src/embedagent/agent_lifecycle.py`
- Modify: `src/embedagent/query_engine.py`
- Test: `tests/test_agent_lifecycle.py`
- Test: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Write direct journal tests**

Add tests covering:

```python
def test_lifecycle_journal_records_transition_savepoint_events():
    session = Session()
    session.add_user_message("hi", turn_id="turn-1")
    session.begin_step(step_id="step-1")
    events = []
    journal = AgentLifecycleJournal(
        append_event=lambda event_type, payload, schema_version=1: events.append(
            {"type": event_type, "payload": payload, "schema_version": schema_version}
        ),
        session_guard=lambda: contextlib.nullcontext(),
    )

    journal.record_transition(
        session,
        LoopTransition(reason="completed", message="done", turns_used=1),
    )

    assert [item["type"] for item in events] == [
        "operation_started",
        "loop_transition",
        "operation_finished",
        "operation_finished",
    ]
    assert events[0]["payload"]["kind"] == "save_point"
    assert events[1]["payload"]["reason"] == "completed"
    assert session.turns[-1].transitions[-1].reason == "completed"
```

Also add a pending interaction case that expects `pending_interaction`, `operation_started(kind=pending_interaction)`, save point start/finish, and step finish.

- [ ] **Step 2: Run direct journal tests and verify they fail**

Run:

```bash
uv run pytest tests/test_agent_lifecycle.py -q
```

Expected: import failure for `embedagent.agent_lifecycle`.

- [ ] **Step 3: Implement `AgentLifecycleJournal`**

Implement:

- `emit_operation_started`
- `emit_operation_finished`
- `emit_operation_interrupted`
- `emit_turn_started`
- `emit_turn_finished`
- `emit_turn_interrupted`
- `emit_pending_started`
- `emit_pending_finished`
- `emit_step_finished`
- `emit_step_interrupted`
- `record_transition`

Use injected callbacks:

```python
class AgentLifecycleJournal(object):
    def __init__(self, append_event, session_guard):
        self._append_event = append_event
        self._session_guard = session_guard
```

Keep behavior identical to current `QueryEngine` helper bodies.

- [ ] **Step 4: Wire `QueryEngine` to journal**

In `QueryEngine.__init__`, create:

```python
self.lifecycle = AgentLifecycleJournal(
    append_event=self._append_transcript_event,
    session_guard=self._session_guard,
)
```

Replace existing lifecycle helper bodies with compatibility delegates to `self.lifecycle`.

- [ ] **Step 5: Run C-A focused tests**

Run:

```bash
uv run pytest tests/test_agent_lifecycle.py tests/test_query_engine_refactor.py tests/test_session_operation_log.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit C-A**

```bash
git add src/embedagent/agent_lifecycle.py src/embedagent/query_engine.py tests/test_agent_lifecycle.py
git commit -m "feat: extract agent lifecycle journal"
```

## Task 2: C-B AgentKernel Turn Frame

**Files:**
- Create: `src/embedagent/agent_kernel.py`
- Modify: `src/embedagent/query_engine.py`
- Test: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Write turn frame tests**

Add tests that assert `QueryEngine.submit_user_turn`, `submit_command_turn`, and `resume_interaction` use kernel turn frame helpers. Use a small spy kernel or journal to verify:

- user turn emits `operation_started(kind=turn)` once
- command turn emits `operation_started(kind=turn)` once
- resume turn emits `operation_started(kind=turn)` once
- exceptions emit `operation_interrupted(kind=turn)`

- [ ] **Step 2: Run turn frame tests and verify failure**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py -q
```

Expected: tests fail because no `AgentKernel` frame boundary exists.

- [ ] **Step 3: Implement `AgentKernel` and `AgentTurnFrame`**

Implement:

```python
class AgentTurnFrame(object):
    def finish(self, transition):
        ...

    def interrupt(self, reason, error=""):
        ...
```

`AgentKernel.begin_turn(...)` returns a frame with `turn_id`, `source`, `current_mode`, and `workflow_state`.

- [ ] **Step 4: Route QueryEngine turn start/finish/interruption through frames**

Replace direct calls to `_emit_turn_started`, `_emit_turn_finished`, and `_emit_turn_interrupted` in:

- `submit_user_turn`
- `submit_command_turn`
- `resume_interaction`

- [ ] **Step 5: Run C-B focused tests**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit C-B**

```bash
git add src/embedagent/agent_kernel.py src/embedagent/query_engine.py tests/test_query_engine_refactor.py
git commit -m "feat: introduce agent kernel turn frames"
```

## Task 3: C-C Suspend And Resume Boundary

**Files:**
- Modify: `src/embedagent/agent_kernel.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/query_engine.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`
- Test: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Write suspend/resume boundary tests**

Add tests that cover:

- permission wait snapshot and session history are atomic before engine returns
- approve permission waits for idle snapshot
- user input wait and response use the same pending interaction lifecycle
- `pending_resolution` and `operation_finished(kind=pending_interaction)` are emitted by the same boundary

- [ ] **Step 2: Run tests and verify failure where direct facade paths remain**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py tests/test_query_engine_refactor.py -q
```

- [ ] **Step 3: Move pending interaction creation into kernel/journal**

Expose kernel helpers:

- `record_pending_permission(...)`
- `record_pending_user_input(...)`
- `resolve_pending_interaction(...)`

Keep public adapter methods unchanged.

- [ ] **Step 4: Remove direct pending lifecycle emission from QueryEngine where replaced**

Ensure `QueryEngine` delegates to kernel/journal and does not add new direct pending lifecycle helpers.

- [ ] **Step 5: Run C-C focused tests**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py tests/test_query_engine_refactor.py tests/test_session_restore.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit C-C**

```bash
git add src/embedagent/agent_kernel.py src/embedagent/inprocess_adapter.py src/embedagent/query_engine.py tests/test_inprocess_adapter_frontend_api.py tests/test_query_engine_refactor.py
git commit -m "feat: centralize pending interaction lifecycle"
```

## Task 4: C-D AgentLoop Ownership

**Files:**
- Modify: `src/embedagent/agent_loop.py`
- Modify: `src/embedagent/agent_kernel.py`
- Modify: `src/embedagent/query_engine.py`
- Test: `tests/test_query_engine_refactor.py`
- Test: `tests/test_session_operation_log.py`

- [ ] **Step 1: Write loop ownership characterization tests**

Add tests that assert:

- `AgentLoop` can be constructed without a runner callback
- agent step started/finished lifecycle remains unchanged
- compact retry transition is still recorded
- aborted tool execution still marks step and turn lifecycle interrupted
- `QueryEngine` no longer owns `_run_loop_impl` lifecycle decisions after migration

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py -q
```

- [ ] **Step 3: Move loop implementation into `AgentLoop`**

Give `AgentLoop` explicit dependencies rather than a runner callback:

- lifecycle journal
- action executor callback
- context builder callback
- provider caller callback
- summary persistence callback
- tool observation recorder callback
- mode/tool schema callbacks

Keep behavior identical.

- [ ] **Step 4: Shrink `QueryEngine._run_loop_impl`**

Remove or reduce `_run_loop_impl` to a compatibility wrapper with no lifecycle decisions.

- [ ] **Step 5: Run C-D focused tests**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py tests/test_session_operation_log.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit C-D**

```bash
git add src/embedagent/agent_loop.py src/embedagent/agent_kernel.py src/embedagent/query_engine.py tests/test_query_engine_refactor.py
git commit -m "feat: move turn loop ownership into agent loop"
```

## Task 5: C-E Documentation And Closeout

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Move or archive: Phase C working materials if needed

- [ ] **Step 1: Update source-of-truth docs**

Document:

- `AgentLifecycleJournal`
- `AgentKernel`
- `AgentLoop` ownership
- `QueryEngine` as session facade
- Phase C completion status

- [ ] **Step 2: Update tracker and changelog**

Add a new design change entry for Phase C completion and mark tracker status.

- [ ] **Step 3: Run doc consistency scan**

Run:

```bash
rg -n "Phase C|AgentKernel|AgentLifecycleJournal|thin loop|lifecycle boundary" README.md AGENTS.md docs
```

Expected: active docs describe completed Phase C accurately, archive docs may retain historical wording.

- [ ] **Step 4: Run final verification**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
uv run pytest tests/ -m "not slow and not gui" -q
```

Expected: all pass.

- [ ] **Step 5: Commit C-E**

```bash
git add README.md AGENTS.md docs/
git commit -m "docs: close phase c agent kernel extraction"
```

## Final Closeout

- [ ] **Step 1: Review git history**

Run:

```bash
git log --oneline -8
```

- [ ] **Step 2: Check working tree**

Run:

```bash
git status --short --branch
```

Expected: clean branch `codex/phase-c-agent-kernel`.

- [ ] **Step 3: Report verification and merge readiness**

Summarize subphase commits, final test results, and remaining Phase D direction.
