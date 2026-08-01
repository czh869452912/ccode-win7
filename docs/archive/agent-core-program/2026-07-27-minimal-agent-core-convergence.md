# Minimal Agent Core Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the callback-heavy, dual-write Core runtime with one reducer-driven session journal, a small closed-effect kernel loop, and a hosted boundary that no longer exposes mutable Core session state.

**Architecture:** Keep `Agent` / `AgentSession` / `AgentPorts` as the public standalone SDK. Internally, append canonical events through `SessionJournal`, apply them through one `SessionReducer`, drive three private effect families through `AgentKernel` and `AgentLoop`, then delete `QueryEngine`; Host receives frozen projections through `HostedSessionController` and never owns `Session`.

**Tech Stack:** Python 3.8 standard library, existing `SessionLogPort`, pytest, uv workspace distributions, PowerShell release scripts, and the existing React/Vitest GUI gate.

---

## Execution Rules

Run this program in an isolated worktree:

```powershell
git worktree add ..\ccode-win7-minimal-core -b codex/minimal-agent-core-convergence main
Set-Location ..\ccode-win7-minimal-core
```

Before Task 1, verify the approved design commit is present:

```powershell
git log -1 --oneline
```

Expected: `d781396b docs: design minimal agent core convergence` or a descendant.

Run the pre-merge architecture gate after every numbered task that changes
production code:

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Do not add a compatibility wrapper when a task retires an internal path. Delete
the old branch, its direct tests, and its source-text guard in the same commit.

## Target File Map

New Core files:

- `packages/embedagent-core/src/embedagent_core/session_reducer.py`: closed event dispatcher and restore validation context.
- `packages/embedagent-core/src/embedagent_core/session_journal.py`: append-before-apply transaction boundary.
- `packages/embedagent-core/src/embedagent_core/session_view.py`: frozen public and hosted read models.
- `packages/embedagent-core/src/embedagent_core/agent_effects.py`: private context, provider, and tool effect/result union.
- `packages/embedagent-core/src/embedagent_core/provider_step_service.py`: context assembly, snapshot creation, provider request, and bounded provider retry.
- `packages/embedagent-core/src/embedagent_core/session_transaction.py`: lease, restore, input dispatch, observer projection, and result assembly.

Core files that converge and remain:

- `packages/embedagent-core/src/embedagent_core/api.py`: public SDK validation and frozen interaction DTO.
- `packages/embedagent-core/src/embedagent_core/runner.py`: `AgentRuntime` assembly and low-level `run_agent` entry.
- `packages/embedagent-core/src/embedagent_core/agent_kernel.py`: pure phase planning and effect-result acceptance.
- `packages/embedagent-core/src/embedagent_core/agent_loop.py`: commit-execute-resume driver.
- `packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py`: tool policy and execution only.
- `packages/embedagent-core/src/embedagent_core/agent_extension_host.py`: declared extension participation only.
- `packages/embedagent-core/src/embedagent_core/session.py`: internal state records and reducer-only mutation helpers.
- `packages/embedagent-core/src/embedagent_core/hosting.py`: typed non-root hosted operations and projections.
- `packages/embedagent-core/src/embedagent_core/ports.py`: read-only session view ports.
- `packages/embedagent-core/src/embedagent_core/tool_contracts.py`: observation materialization contract without transcript ownership.

Files deleted by the program:

- `packages/embedagent-core/src/embedagent_core/query_engine.py`
- `packages/embedagent-core/src/embedagent_core/session_restore.py`
- `packages/embedagent-core/src/embedagent_core/strategies/execution_tracer.py`
- `packages/embedagent-core/src/embedagent_core/strategies/circuit_breaker.py`
- `tests/test_query_engine_orchestrator.py`
- `tests/query_engine_product_helpers.py`

Host convergence files:

- `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- `packages/embedagent-host/src/embedagent_host/runtime/session_runtime.py`
- `packages/embedagent-host/src/embedagent_host/runtime/services/session_lifecycle.py`
- `packages/embedagent-host/src/embedagent_host/runtime/session_projection.py`
- `packages/embedagent-host/src/embedagent_host/runtime/session_projector.py`
- `packages/embedagent-host/src/embedagent_host/runtime/session_history.py`
- `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- `packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py`
- `packages/embedagent-host/src/embedagent_host/runtime/tool_commit.py`
- `packages/embedagent-host/src/embedagent_host/hosted_command_service.py`
- `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py`

## Milestone A: Public Contract And Reducer Truth

### Task 1: Unfreeze QueryEngine And Resolve Extension Assembly Ambiguity

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/api.py:141`
- Modify: `tests/test_agent_core_public_api.py:326`
- Modify: `tests/test_current_architecture_boundaries.py:202`
- Delete: `tests/test_query_engine_orchestrator.py`

- [ ] **Step 1: Write the failing public composition test**

Add to `tests/test_agent_core_public_api.py`:

```python
from embedagent_core.extensions import ExtensionManager


def test_agent_create_rejects_two_extension_assembly_sources(base_ports):
    manager = ExtensionManager()
    ports = AgentPorts(
        model=base_ports.model,
        tools=base_ports.tools,
        session_log=base_ports.session_log,
        context=base_ports.context,
        permissions=base_ports.permissions,
        extension_manager=manager,
    )

    with pytest.raises(
        ValueError,
        match="^extension_manager and RuntimeDefinition.extensions are mutually exclusive$",
    ):
        Agent.create(ports, RuntimeDefinition(extensions=(object(),)))
```

- [ ] **Step 2: Run the test and verify the ambiguity is currently accepted**

Run:

```powershell
uv run pytest tests/test_agent_core_public_api.py::test_agent_create_rejects_two_extension_assembly_sources -v
```

Expected: FAIL because `AgentRuntime` currently gives `AgentPorts.extension_manager`
silent precedence.

- [ ] **Step 3: Add fail-fast validation**

In `Agent.create`, after validating the manager type, add:

```python
if ports.extension_manager is not None and runtime_definition.extensions:
    raise ValueError(
        "extension_manager and RuntimeDefinition.extensions are mutually exclusive"
    )
```

- [ ] **Step 4: Remove tests that promote QueryEngine to a supported API**

Delete `TestQueryEngineBoundaries` from
`tests/test_current_architecture_boundaries.py` and delete
`tests/test_query_engine_orchestrator.py`. Keep the root-export assertion:

```python
def test_query_engine_is_not_a_public_core_symbol():
    import embedagent_core

    assert not hasattr(embedagent_core, "QueryEngine")
```

- [ ] **Step 5: Run the public and architecture tests**

```powershell
uv run pytest tests/test_agent_core_public_api.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add packages/embedagent-core/src/embedagent_core/api.py tests/test_agent_core_public_api.py tests/test_current_architecture_boundaries.py tests/test_query_engine_orchestrator.py
git commit -m "test: unfreeze internal query engine contract"
```

### Task 2: Add The Closed SessionReducer Contract

**Files:**
- Create: `packages/embedagent-core/src/embedagent_core/session_reducer.py`
- Create: `tests/test_session_reducer.py`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Write reducer contract tests**

Create `tests/test_session_reducer.py` with these first cases:

```python
from __future__ import annotations

import pytest

from embedagent_core.session import Session
from embedagent_core.session_reducer import (
    SessionReduceError,
    SessionReducer,
    SessionReducerContext,
)


def event(event_type, payload, seq=1):
    return {
        "schema_version": 2,
        "session_id": "session-1",
        "event_id": "event-%s" % seq,
        "seq": seq,
        "ts": "2026-07-27T00:00:00Z",
        "type": event_type,
        "payload": payload,
    }


def test_session_meta_sets_mode_and_started_at():
    session = Session(session_id="session-1")
    context = SessionReducerContext()

    SessionReducer().apply(
        session,
        context,
        event(
            "session_meta",
            {"current_mode": "debug", "started_at": "2026-07-27T00:00:00Z"},
        ),
    )

    assert context.current_mode == "debug"
    assert session.started_at == "2026-07-27T00:00:00Z"


def test_known_lifecycle_event_is_state_neutral():
    session = Session(session_id="session-1")
    context = SessionReducerContext()

    SessionReducer().apply(
        session,
        context,
        event("operation_started", {"operation_id": "turn:t-1"}),
    )

    assert session.messages == []
    assert session.turns == []


def test_unknown_event_fails_closed():
    with pytest.raises(SessionReduceError, match="^unknown_event_type$"):
        SessionReducer().apply(
            Session(session_id="session-1"),
            SessionReducerContext(),
            event("unknown", {}),
        )
```

- [ ] **Step 2: Run the new tests**

```powershell
uv run pytest tests/test_session_reducer.py -v
```

Expected: FAIL because `session_reducer.py` does not exist.

- [ ] **Step 3: Implement the reducer shell**

Create `session_reducer.py` with a closed dispatcher. Do not add dynamic handler
registration:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set

from embedagent_core.session import Session


class SessionReduceError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = str(reason or "session_reduce_error")
        super(SessionReduceError, self).__init__(self.reason)


@dataclass
class SessionReducerContext:
    current_mode: str = ""
    seen_turn_ids: Set[str] = field(default_factory=set)
    seen_step_ids: Set[str] = field(default_factory=set)
    seen_message_ids: Set[str] = field(default_factory=set)
    seen_tool_call_ids: Set[str] = field(default_factory=set)
    seen_interaction_ids: Set[str] = field(default_factory=set)
    seen_boundary_ids: Set[str] = field(default_factory=set)
    seen_compacted_history_ids: Set[str] = field(default_factory=set)


class SessionReducer(object):
    _STATE_NEUTRAL_TYPES = frozenset(
        (
            "operation_started",
            "operation_finished",
            "operation_interrupted",
            "tool_use",
            "command_execution",
            "interaction",
            "runtime_configured",
            "resource_reloaded",
            "recovery_marker",
        )
    )

    def __init__(self) -> None:
        self._handlers = {"session_meta": self._apply_session_meta}

    def apply(
        self,
        session: Session,
        context: SessionReducerContext,
        event: Dict[str, Any],
    ) -> None:
        if int(event.get("schema_version") or 0) != 2:
            raise SessionReduceError("unsupported_schema_version")
        if str(event.get("session_id") or "") != session.session_id:
            raise SessionReduceError("session_id_mismatch")
        event_type = str(event.get("type") or "")
        if event_type in self._STATE_NEUTRAL_TYPES:
            return
        handler = self._handlers.get(event_type)
        if handler is None:
            raise SessionReduceError("unknown_event_type")
        handler(session, context, dict(event.get("payload") or {}))

    def _apply_session_meta(
        self,
        session: Session,
        context: SessionReducerContext,
        payload: Dict[str, Any],
    ) -> None:
        context.current_mode = str(payload.get("current_mode") or context.current_mode)
        if payload.get("started_at"):
            session.started_at = str(payload["started_at"])
```

- [ ] **Step 4: Add a closed-dispatch architecture assertion**

Assert that production code contains no public reducer registration function:

```python
def test_session_reducer_is_closed_internal_dispatch():
    source = (ROOT / "packages/embedagent-core/src/embedagent_core/session_reducer.py").read_text(
        encoding="utf-8"
    )
    assert "def register" not in source
    assert "SessionReducer" not in (ROOT / "packages/embedagent-core/src/embedagent_core/__init__.py").read_text(
        encoding="utf-8"
    )
```

- [ ] **Step 5: Run tests and commit**

```powershell
uv run pytest tests/test_session_reducer.py tests/test_pre_release_architecture_guards.py -v
git add packages/embedagent-core/src/embedagent_core/session_reducer.py tests/test_session_reducer.py tests/test_pre_release_architecture_guards.py
git commit -m "feat: define closed session reducer"
```

Expected: PASS.

### Task 3: Add Append-Before-Apply SessionJournal

**Files:**
- Create: `packages/embedagent-core/src/embedagent_core/session_journal.py`
- Create: `tests/test_session_journal.py`
- Modify: `packages/embedagent-core/src/embedagent_core/session_log.py:43`

- [ ] **Step 1: Write commit-order and partial-failure tests**

Create `tests/test_session_journal.py`:

```python
from __future__ import annotations

import pytest

from embedagent_core.session import Session
from embedagent_core.session_journal import EventIntent, SessionJournal
from embedagent_core.session_log import InMemorySessionLog
from embedagent_core.session_reducer import SessionReducer, SessionReducerContext


class FailingSecondAppend(InMemorySessionLog):
    def append_event(self, *args, **kwargs):
        if len(self.load_events(args[0])) == 1:
            raise OSError("append failed")
        return super(FailingSecondAppend, self).append_event(*args, **kwargs)


def test_commit_applies_only_the_durable_event():
    store = InMemorySessionLog()
    session = Session(session_id="session-1")
    journal = SessionJournal(store, SessionReducer())

    result = journal.commit(
        session,
        SessionReducerContext(),
        (EventIntent("session_meta", {"current_mode": "debug"}),),
    )

    assert result.events[0]["seq"] == 1
    assert result.context.current_mode == "debug"


def test_partial_commit_exposes_only_stored_prefix():
    store = FailingSecondAppend()
    session = Session(session_id="session-1")
    journal = SessionJournal(store, SessionReducer())

    with pytest.raises(OSError, match="append failed"):
        journal.commit(
            session,
            SessionReducerContext(),
            (
                EventIntent("session_meta", {"current_mode": "debug"}),
                EventIntent("session_meta", {"current_mode": "verify"}),
            ),
        )

    assert len(store.load_events("session-1")) == 1
```

Add a preflight test so an invalid intent never becomes durable:

```python
def test_invalid_intent_is_rejected_before_append():
    store = InMemorySessionLog()
    journal = SessionJournal(store, SessionReducer())

    with pytest.raises(SessionReduceError, match="^unknown_event_type$"):
        journal.commit(
            Session(session_id="session-1"),
            SessionReducerContext(),
            (EventIntent("unknown", {}),),
        )

    assert store.load_events("session-1") == []
```

- [ ] **Step 2: Run the tests and verify they fail**

```powershell
uv run pytest tests/test_session_journal.py -v
```

Expected: FAIL because `SessionJournal` is missing.

- [ ] **Step 3: Implement the journal**

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Tuple

from embedagent_core.session import Session
from embedagent_core.session_log import SessionLogPort
from embedagent_core.session_reducer import SessionReducer, SessionReducerContext


@dataclass(frozen=True)
class EventIntent:
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    ts: str = ""


@dataclass(frozen=True)
class CommitResult:
    context: SessionReducerContext
    events: Tuple[Dict[str, Any], ...]


class SessionJournal(object):
    def __init__(self, session_log: SessionLogPort, reducer: SessionReducer) -> None:
        self._session_log = session_log
        self._reducer = reducer

    def commit(self, session, context, intents):
        # type: (Session, SessionReducerContext, Iterable[EventIntent]) -> CommitResult
        intents = tuple(intents)
        staged_session = deepcopy(session)
        staged_context = deepcopy(context)
        for index, intent in enumerate(intents):
            self._reducer.apply(
                staged_session,
                staged_context,
                {
                    "schema_version": 2,
                    "session_id": session.session_id,
                    "event_id": "preflight-%d" % (index + 1),
                    "seq": index + 1,
                    "ts": "1970-01-01T00:00:00Z",
                    "type": intent.event_type,
                    "payload": dict(intent.payload),
                },
            )
        stored_events = []
        for intent in intents:
            stored = self._session_log.append_event(
                session.session_id,
                intent.event_type,
                dict(intent.payload),
                event_id=intent.event_id,
                ts=intent.ts,
                schema_version=2,
            )
            self._reducer.apply(session, context, stored)
            stored_events.append(stored)
        return CommitResult(context=context, events=tuple(stored_events))
```

The staged preflight copy validates the full intent sequence without changing
live state. It is never persisted or published. The real state is updated only
from each envelope returned by `append_event`, so an I/O failure exposes the
durable prefix and nothing beyond it.

Change `SessionLogPort.append_event`'s return annotation from `Any` to
`Dict[str, Any]`; both existing adapters already return the stored envelope.

- [ ] **Step 4: Run focused tests and commit**

```powershell
uv run pytest tests/test_session_journal.py tests/test_session_log_port.py -v
git add packages/embedagent-core/src/embedagent_core/session_journal.py packages/embedagent-core/src/embedagent_core/session_log.py tests/test_session_journal.py
git commit -m "feat: add durable session journal"
```

Expected: PASS.

### Task 4: Move Conversation State To Reducer Handlers

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/session_reducer.py`
- Modify: `packages/embedagent-core/src/embedagent_core/session_restore.py:96`
- Modify: `packages/embedagent-core/src/embedagent_core/query_engine.py:829`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_loop.py:225`
- Modify: `packages/embedagent-core/src/embedagent_core/prompt_assembly_service.py`
- Modify: `tests/test_session_reducer.py`
- Modify: `tests/test_session_restore.py`
- Modify: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Add parity tests for messages, steps, and transitions**

Build one canonical event list and apply it once through `SessionReducer` and
once through the hosted transcript adapter. Assert these fields match:

```python
assert [item.to_api_dict() for item in live.messages] == [
    item.to_api_dict() for item in restored.messages
]
assert live.turns[-1].turn_id == restored.turns[-1].turn_id
assert live.turns[-1].steps[-1].step_id == restored.turns[-1].steps[-1].step_id
assert live.turns[-1].transitions[-1].reason == "completed"
```

The event list must include `session_meta`, `system`, `user`, `step_started`,
`assistant`, and `loop_transition` with explicit ids and parent ids.

- [ ] **Step 2: Verify the reducer rejects the conversation events**

```powershell
uv run pytest tests/test_session_reducer.py -k conversation -v
```

Expected: FAIL with `unknown_event_type`.

- [ ] **Step 3: Add closed handlers**

Move the validation logic from `SessionRestorer._apply_message` and the
`step_started` / `loop_transition` branches into private reducer methods. The
dispatcher entries must be explicit:

```python
self._handlers.update(
    {
        "message": self._apply_message,
        "system": self._apply_message,
        "user": self._apply_message,
        "assistant": self._apply_message,
        "tool": self._apply_message,
        "step_started": self._apply_step_started,
        "loop_transition": self._apply_loop_transition,
    }
)
```

Use `SessionReduceError` reason strings already asserted by
`tests/test_session_restore.py`; do not rename restore diagnostics in this task.

- [ ] **Step 4: Route live conversation commits through SessionJournal**

Replace each append-then-mutate pair with one intent. For a user message:

```python
self._journal.commit(
    session,
    reduction_context,
    (
        EventIntent(
            "user",
            {
                "role": "user",
                "content": user_text,
                "message_id": message_id,
                "parent_message_id": parent_message_id,
                "turn_id": turn_id,
                "step_id": "",
            },
        ),
    ),
)
```

During Tasks 4-6, add
`reduction_context: SessionReducerContext = field(default_factory=SessionReducerContext)`
to `SessionRestoreResult`. `SessionRestorer` creates that context before its
fold, updates the same seen-id sets in both migrated and not-yet-migrated
branches, and returns it. `QueryEngine` uses `restored.reduction_context`; a new
session starts `SessionReducerContext(current_mode=current_mode)`. Task 7 moves
this result field into `session_journal.py` unchanged, avoiding any attempt to
reconstruct resolved interaction ids from the lossy live `Session` projection.

Delete the adjacent `session.add_user_message`. Apply the same pattern to
system, assistant, `step_started`, and `loop_transition` events. Change
`PromptAssemblyService` to return message event payloads; it must not receive a
`session.add_system_message` callback.

- [ ] **Step 5: Make SessionRestorer call the same handlers**

For the migrated event types, replace imperative branches with:

```python
try:
    reducer.apply(session, reduction_context, event)
except SessionReduceError as exc:
    if _maybe_skip(exc.reason):
        continue
    break
continue
```

Delete `_apply_message` and migrated validation helpers from
`session_restore.py` after all their callers move.

- [ ] **Step 6: Run conversation, restore, and loop tests**

```powershell
uv run pytest tests/test_session_reducer.py tests/test_session_restore.py tests/test_query_engine_refactor.py -k "message or step or transition or prompt" -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add packages/embedagent-core/src/embedagent_core/session_reducer.py packages/embedagent-core/src/embedagent_core/session_restore.py packages/embedagent-core/src/embedagent_core/query_engine.py packages/embedagent-core/src/embedagent_core/agent_loop.py packages/embedagent-core/src/embedagent_core/prompt_assembly_service.py tests/test_session_reducer.py tests/test_session_restore.py tests/test_query_engine_refactor.py
git commit -m "refactor: reduce conversation state from journal"
```

### Task 5: Move Tool Results And Materialization Behind The Journal

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/session_reducer.py`
- Modify: `packages/embedagent-core/src/embedagent_core/tool_contracts.py:190`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py`
- Modify: `packages/embedagent-core/src/embedagent_core/query_engine.py:1123`
- Modify: `packages/embedagent-core/src/embedagent_core/session_restore.py:151`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py:328`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/tool_commit.py`
- Create: `tests/test_tool_observation_materialization.py`
- Modify: `tests/test_session_reducer.py`

- [ ] **Step 1: Write materialize-then-commit tests**

The Host materializer test must prove it does not append transcript events or
mutate session state:

```python
prepared = coordinator.materialize(
    "session-1",
    Action("read_file", {"path": "a.txt"}, "call-1"),
    Observation("read_file", True, None, {"content": long_text}),
)

assert prepared.observation.data["content_stored_path"]
assert prepared.replacements
assert transcript_store.load_events("session-1") == []
```

Add reducer parity tests containing `assistant`, `tool_call`, `tool_result`, and
`content_replacement` events. Assert presentation metadata and replacement refs
survive live and restore paths.

- [ ] **Step 2: Add the Core materialization DTO and port methods**

In `tool_contracts.py` add:

```python
@dataclass(frozen=True)
class PreparedToolObservation:
    observation: Observation
    replacements: List[Dict[str, Any]] = field(default_factory=list)
    commit_token: Any = None


class ToolRuntimePort(Protocol):
    def materialize_observation(
        self,
        session_id: str,
        action: Action,
        observation: Observation,
    ) -> PreparedToolObservation:
        raise NotImplementedError

    def finalize_observation(self, commit_token: Any) -> None:
        raise NotImplementedError
```

Remove `commit_observation` after every production implementation and test uses
the new two-stage contract.

- [ ] **Step 3: Split Host materialization from projection finalization**

Rename `ToolCommitCoordinator.commit` to `materialize`. Pass `session_id`
instead of `Session`, return `PreparedToolObservation`, and move projection DB
updates into `finalize(commit_token)`. Remove both transcript `append_event`
calls and `session.record_content_replacement`.

- [ ] **Step 4: Add reducer handlers and journal tool facts**

Register `tool_call`, `tool_result`, and `content_replacement`. The `tool_call`
handler must update presentation on an assistant-created record rather than
dropping it:

```python
record = session._find_tool_call(call_id)
if record is None:
    record = session.record_tool_call(action, presentation)
else:
    record.presentation = presentation
```

After materialization, commit `tool_result` and each `content_replacement`
through `SessionJournal`; call `finalize_observation` only after every durable
event succeeds.

- [ ] **Step 5: Delete direct tool-state mutation and old restore branches**

Delete adjacent `session.record_tool_call`, `session.add_observation`, and
`session.record_content_replacement` calls outside the reducer. Replace the
matching `SessionRestorer` branches with the reducer call used in Task 4.

- [ ] **Step 6: Run tests and commit**

```powershell
uv run pytest tests/test_tool_observation_materialization.py tests/test_session_reducer.py tests/test_session_restore.py tests/test_query_engine_refactor.py -k "tool or replacement" -v
git add packages/embedagent-core/src/embedagent_core packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py packages/embedagent-host/src/embedagent_host/runtime/tool_commit.py tests/test_tool_observation_materialization.py tests/test_session_reducer.py tests/test_session_restore.py tests/test_query_engine_refactor.py
git commit -m "refactor: commit tool observations through journal"
```

Expected: PASS.

### Task 6: Move Interaction And Workflow State To Reducers

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/session_reducer.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_kernel.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_lifecycle.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_extension_host.py:182`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py`
- Modify: `packages/embedagent-core/src/embedagent_core/query_engine.py:1556`
- Modify: `packages/embedagent-core/src/embedagent_core/session_restore.py:244`
- Modify: `tests/test_session_reducer.py`
- Modify: `tests/test_session_restore.py`
- Modify: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Add interaction replay tests**

Use events for one pending permission, one matching resolution, and one
workflow patch. Assert:

```python
assert session.pending_interaction is None
assert session.workflow_state["workflow"] == {"phase": "verify"}
assert session.workflow_state["extensions"]["last_workflow_patch"] == {
    "source": "test"
}
```

Also assert duplicate interaction ids, mismatched turn/step ids, and mismatched
resolution ids keep the current restore reason strings.

- [ ] **Step 2: Implement closed handlers**

Register `pending_interaction`, `pending_resolution`, and `workflow_patch`.
Create pending values only inside the reducer and deep-copy `request_payload`.

- [ ] **Step 3: Make AgentKernel emit intents instead of mutating Session**

Change pending methods to return event intents and transitions:

```python
return (
    EventIntent(
        "pending_interaction",
        {
            "turn_id": turn_id,
            "step_id": step_id,
            "interaction_id": pending.interaction_id,
            "kind": pending.kind,
            "tool_name": pending.tool_name,
            "request_payload": dict(pending.request_payload),
        },
    ),
    transition,
)
```

For resolution return `EventIntent("pending_resolution", payload)`; remove
`session.resolve_pending_interaction` from `AgentKernel`.

- [ ] **Step 4: Remove extension direct workflow mutation**

`AgentExtensionHost.apply_tool_result_patch` must return `WorkflowPatch` only.
`AgentToolActionService` converts the patch into a `workflow_patch` intent. No
extension or action service may assign `session.workflow_state`.

- [ ] **Step 5: Replace restore branches and run tests**

```powershell
uv run pytest tests/test_session_reducer.py tests/test_session_restore.py tests/test_query_engine_refactor.py -k "pending or interaction or workflow_patch" -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add packages/embedagent-core/src/embedagent_core tests/test_session_reducer.py tests/test_session_restore.py tests/test_query_engine_refactor.py
git commit -m "refactor: reduce interaction and workflow state"
```

### Task 7: Move Context And Compaction State, Then Delete SessionRestorer

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/session_reducer.py`
- Modify: `packages/embedagent-core/src/embedagent_core/compaction_journal.py`
- Modify: `packages/embedagent-core/src/embedagent_core/query_engine.py:1968`
- Modify: `packages/embedagent-core/src/embedagent_core/runner.py:269`
- Delete: `packages/embedagent-core/src/embedagent_core/session_restore.py`
- Rename: `tests/test_session_restore.py` to `tests/test_session_reducer_restore.py`
- Modify: `tests/test_session_performance.py`
- Modify: `tests/test_session_fault_injection.py`

- [ ] **Step 1: Add context and compaction parity tests**

Cover `context_snapshot`, `compact_boundary`, and `compacted_history`. Assert one
boundary creates exactly one summary message and that a replayed checkpoint has
the same first/last kept anchors as the live state.

- [ ] **Step 2: Implement handlers without nested mutation events**

The compact-boundary handler must construct both the boundary record and its
summary message directly. It must not call `Session.add_compact_boundary`,
because that helper performs a second implicit mutation. Move that construction
logic into the reducer and make the old helper reducer-private.

- [ ] **Step 3: Add SessionJournal.restore**

Move `SessionRestoreResult` unchanged from `session_restore.py` into
`session_journal.py`, then make the public restore boundary session-id and
policy based. `SessionJournal` owns event loading; callers cannot supply an
alternate history list:

```python
def restore(
    self,
    session_id: str,
    restore_policy: SessionRestorePolicyPort,
) -> SessionRestoreResult:
    events = self._session_log.load_events(session_id)
    if not events:
        raise ValueError("cannot restore an empty transcript")
    trusted_event_count = max(
        0,
        int(restore_policy.trusted_event_count(session_id) or 0),
    )
    return self._fold(events, trusted_event_count)


def _fold(
    self,
    events: List[Dict[str, Any]],
    trusted_event_count: int,
) -> SessionRestoreResult:
    session_id = str(events[0].get("session_id") or "")
    started_at = str(events[0].get("ts") or "")
    session = (
        Session(session_id=session_id, started_at=started_at)
        if started_at
        else Session(session_id=session_id)
    )
    context = SessionReducerContext()
    consumed = len(events)
    stop_reason = ""
    skipped = []  # type: List[Dict[str, Any]]
    for index, event in enumerate(events):
        try:
            self._reducer.apply(session, context, event)
        except SessionReduceError as exc:
            within_prefix = trusted_event_count <= 0 or index < trusted_event_count
            if trusted_event_count > 0 and within_prefix and self._should_skip_error(exc.reason):
                skipped.append(
                    {
                        "index": index,
                        "event_type": str(event.get("type") or ""),
                        "reason": exc.reason,
                        "event_id": str(event.get("event_id") or ""),
                    }
                )
                continue
            consumed = index
            stop_reason = exc.reason
            break
    consumed_events = events[:consumed]
    return SessionRestoreResult(
        session=session,
        current_mode=context.current_mode,
        transcript_event_count=len(events),
        consumed_event_count=consumed,
        stop_reason=stop_reason,
        skipped_count=len(skipped),
        skip_reasons=skipped,
        reduction_context=context,
        operation_state=OperationLogReducer().reduce(consumed_events),
        compaction_state=CompactionStateReducer().reduce(consumed_events),
        recovery_state=RecoveryStateReducer().reduce(consumed_events),
        runtime_config=RuntimeConfigReducer().reduce(consumed_events),
        turn_experience=TurnExperienceReducer().reduce(consumed_events),
    )
```

Move `_should_skip_error` with its current reason policy into `SessionJournal`;
do not duplicate that policy in Host. Test strict restore with
`StrictSessionRestorePolicy()` and trusted-prefix restore with a fake policy
whose `trusted_event_count(session_id)` returns the explicit prefix length.

- [ ] **Step 4: Switch every restore caller**

Replace construction and use of `SessionRestorer` with
`SessionJournal.restore(session_id, restore_policy)`. Core uses
`StrictSessionRestorePolicy`; Host injects its explicit trusted-prefix policy.
In this task Host may still receive `result.session`; mutable Host ownership is
removed in Task 14.

- [ ] **Step 5: Delete SessionRestorer and rename its tests**

Delete the file and private helper tests. Preserve every behavioral restore
case in `tests/test_session_reducer_restore.py`, but import `SessionJournal` and
`SessionReducer` rather than `SessionRestorer`.

- [ ] **Step 6: Run restore, fault, and performance tests**

```powershell
uv run pytest tests/test_session_reducer_restore.py tests/test_session_fault_injection.py tests/test_session_performance.py -v
```

Expected: PASS. The durable append and restore benchmarks must remain within
their existing thresholds.

- [ ] **Step 7: Add and run the single-writer guard**

Add an AST-based guard that rejects calls to these methods outside
`session_reducer.py`:

```python
MUTATORS = {
    "add_system_message",
    "add_user_message",
    "begin_step",
    "record_tool_call",
    "add_assistant_reply",
    "add_observation",
    "record_transition",
    "resolve_pending_interaction",
    "record_content_replacement",
    "record_context_snapshot",
    "add_compact_boundary",
    "record_compacted_history",
}
```

Use `ast.Call` attribute inspection; do not use fragile substring assertions.
In the same AST walk, reject assignments outside `session_reducer.py` whose
target is one of these mutable `Session` fields:

```python
MUTABLE_FIELDS = {
    "messages", "turns", "pending_interaction", "workflow_state",
    "context_snapshots", "compact_boundaries", "content_replacements",
    "compacted_history",
}
```

Cover `ast.Assign`, `ast.AnnAssign`, and `ast.AugAssign` targets.

- [ ] **Step 8: Commit**

```powershell
git add packages/embedagent-core packages/embedagent-host tests
git commit -m "refactor: make session journal the state truth"
```

## Milestone B: Closed Effects And QueryEngine Deletion

### Task 8: Define Private Effects And Kernel Cursor

**Files:**
- Create: `packages/embedagent-core/src/embedagent_core/agent_effects.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_kernel.py`
- Create: `tests/test_agent_effect_kernel.py`

- [ ] **Step 1: Write phase and stale-result tests**

```python
def test_kernel_rejects_result_for_wrong_effect_id():
    kernel = AgentKernel()
    cursor = KernelCursor("provider", "effect-1", 1, 1, False)

    with pytest.raises(ValueError, match="^effect_result_mismatch$"):
        kernel.accept(cursor, ProviderCompleted("effect-2", AssistantReply("done")))


def test_kernel_plans_context_before_provider():
    step = AgentKernel().start("t-1", "debug", "", "user")

    assert isinstance(step.effect, AssembleContextEffect)
    assert step.events[0].event_type == "operation_started"
```

- [ ] **Step 2: Run and verify the types are absent**

```powershell
uv run pytest tests/test_agent_effect_kernel.py -v
```

Expected: FAIL on import.

- [ ] **Step 3: Add the closed dataclass union**

Define frozen Python 3.8 dataclasses for:

```python
@dataclass(frozen=True)
class AssembleContextEffect:
    effect_id: str
    turn_id: str
    step_id: str
    mode_name: str
    workflow_state: str
    force_compact: bool = False


@dataclass(frozen=True)
class RequestProviderEffect:
    effect_id: str
    snapshot: TurnSnapshot
    stream: bool


@dataclass(frozen=True)
class ExecuteToolBatchEffect:
    effect_id: str
    actions: Tuple[Action, ...]
    mode_name: str
    workflow_state: str


AgentEffect = Union[AssembleContextEffect, RequestProviderEffect, ExecuteToolBatchEffect]
```

Define the matching result types in the same module:

```python
@dataclass(frozen=True)
class ContextAssembled:
    effect_id: str
    assembly: ContextAssemblyResult
    snapshot: TurnSnapshot
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProviderCompleted:
    effect_id: str
    reply: AssistantReply
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ToolBatchCompleted:
    effect_id: str
    observations: Tuple[Observation, ...] = field(default_factory=tuple)
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    commit_tokens: Tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class InteractionSuspended:
    effect_id: str
    pending: PendingInteraction
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EffectFailed:
    effect_id: str
    error_kind: str
    message: str
    retryable: bool = False
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)


AgentEffectResult = Union[
    ContextAssembled,
    ProviderCompleted,
    ToolBatchCompleted,
    InteractionSuspended,
    EffectFailed,
]
```

Do not export any effect or effect-result type from
`embedagent_core.__init__`.

- [ ] **Step 4: Add KernelCursor and KernelStep**

```python
@dataclass(frozen=True)
class KernelCursor:
    phase: str
    expected_effect_id: str
    step_index: int
    provider_attempt: int
    compact_retry_used: bool


@dataclass(frozen=True)
class KernelStep:
    cursor: KernelCursor
    events: Tuple[EventIntent, ...]
    effect: Optional[AgentEffect] = None
    outcome: Optional[LoopTransition] = None
    post_commit_tokens: Tuple[Any, ...] = field(default_factory=tuple)
```

`AgentKernel.accept(cursor, result)` compares `result.effect_id` with
`cursor.expected_effect_id`, uses explicit `isinstance` dispatch, and copies
`ToolBatchCompleted.commit_tokens` into `KernelStep.post_commit_tokens`. It has
no handler dictionary and no extension registration.

- [ ] **Step 5: Run tests and commit**

```powershell
uv run pytest tests/test_agent_effect_kernel.py tests/test_agent_lifecycle.py -v
git add packages/embedagent-core/src/embedagent_core/agent_effects.py packages/embedagent-core/src/embedagent_core/agent_kernel.py tests/test_agent_effect_kernel.py tests/test_agent_lifecycle.py
git commit -m "feat: define closed agent effects"
```

### Task 9: Extract Context And Provider Execution

**Files:**
- Create: `packages/embedagent-core/src/embedagent_core/provider_step_service.py`
- Modify: `packages/embedagent-core/src/embedagent_core/turn_snapshot.py`
- Modify: `packages/embedagent-core/src/embedagent_core/turn_snapshot_service.py`
- Modify: `packages/embedagent-core/src/embedagent_core/query_engine.py:464`
- Create: `tests/test_provider_step_service.py`
- Modify: `tests/test_turn_snapshot.py`
- Modify: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Write service tests for context, snapshot, and retry**

Test these exact outcomes:

```python
context_result = service.assemble_context(effect, session)
assert context_result.snapshot.messages == context_result.assembly.messages
assert context_result.snapshot.tool_schemas == expected_schemas

provider_result = service.request_provider(provider_effect, observer)
assert provider_result.reply.content == "done"
```

Add a provider that raises one context-limit `ModelClientError`; assert the
service returns `EffectFailed(error_kind="context_limit")` and does not decide
whether to retry. Retry policy belongs to `AgentKernel`.

Add frozen snapshot coverage to `tests/test_turn_snapshot.py`:

```python
from dataclasses import FrozenInstanceError

import pytest


def test_turn_snapshot_is_frozen_and_detached():
    messages = [{"role": "user", "content": "before"}]
    snapshot = TurnSnapshotBuilder().build(
        session_id="session-1",
        turn_id="turn-1",
        step_id="step-1",
        mode_name="build",
        workflow_state="",
        messages=messages,
        tool_schemas=[],
    )
    messages[0]["content"] = "after"

    assert snapshot.messages[0]["content"] == "before"
    with pytest.raises(FrozenInstanceError):
        snapshot.mode_name = "verify"
```

- [ ] **Step 2: Implement ProviderStepService**

Move these responsibilities from `QueryEngine` without forwarding wrappers:

- `_build_context_operation`
- `_record_context_snapshot_operation` payload construction
- `_call_provider_operation`
- `_call_llm_with_retry`
- active schema lookup through `AgentExtensionHost`
- `TurnSnapshotService` invocation

The transitional public methods are `assemble_context(effect, session) ->
ContextAssembled` and `request_provider(effect, observer) -> AgentEffectResult`.
The first must call the injected context assembler, project active schemas,
create a `TurnSnapshot`, and return the snapshot plus journal intents. The
second must call the injected model with the snapshot messages/schemas, forward
transient stream deltas to the observer, and convert only provider exceptions
to `EffectFailed`; neither method may append or mutate session state. Task 14
replaces the transitional internal `Session` argument with `SessionReadView` at
the Host-facing context port.

Make `TurnSnapshot` a frozen dataclass and replace every assignment in
`__post_init__` with `object.__setattr__`, preserving the existing deep-copy and
credential-scrubbing behavior. Remove the `runtime_config_provider` parameter
and callable branch from `TurnSnapshotService`; runtime configuration must come
from `RuntimeConfigReducer` over the injected `SessionLogPort`, not an internal
callback.

- [ ] **Step 3: Delete moved QueryEngine helpers and their direct tests**

Move behavior assertions to `tests/test_provider_step_service.py`. Delete the
helper methods instead of delegating them back to the new service.

- [ ] **Step 4: Run tests and commit**

```powershell
uv run pytest tests/test_provider_step_service.py tests/test_turn_snapshot.py tests/test_query_engine_refactor.py -k "context or provider or snapshot or compact_retry" -v
git add packages/embedagent-core/src/embedagent_core tests/test_provider_step_service.py tests/test_turn_snapshot.py tests/test_query_engine_refactor.py
git commit -m "refactor: extract provider step execution"
```

### Task 10: Make AgentToolActionService Return Effect Results Only

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_effects.py`
- Modify: `packages/embedagent-core/src/embedagent_core/query_engine.py`
- Create: `tests/test_agent_tool_effects.py`
- Modify: `tests/test_capability_extensions.py`
- Modify: `tests/test_dynamic_tool_registration.py`

- [ ] **Step 1: Write effect-result tests**

Assert a normal action returns `ToolBatchCompleted`, permission ask returns
`InteractionSuspended`, and an ordinary nonzero `bash` result remains a
successful effect containing a diagnostic observation rather than
`EffectFailed`.

- [ ] **Step 2: Replace callback handlers with typed results**

Remove `failure_observation_factory`, `permission_pending_handler`,
`permission_rejected_handler`, `user_input_pending_handler`, and
`user_input_response_handler` constructor callbacks. Add one required
`interaction_factory` object with explicit methods:

```python
class InteractionFactory(object):
    def permission_request(
        self,
        action: Action,
        request: PermissionRequest,
        mode_name: str,
    ) -> InteractionSuspended:
        return self._build_permission_suspension(action, request, mode_name)

    def user_input_request(
        self,
        action: Action,
        request: UserInputRequest,
        mode_name: str,
    ) -> InteractionSuspended:
        return self._build_user_input_suspension(action, request, mode_name)
```

`_build_permission_suspension` and `_build_user_input_suspension` move the
existing payload construction from `QueryEngine` into this focused class; they
must return typed results and perform no I/O. This is focused interaction
construction, not a general callback bag.

- [ ] **Step 3: Return event intents with tool results**

`ToolBatchCompleted.observations` contains the diagnostic observations;
`events` contains explicit `tool_result`, `content_replacement`, and
`workflow_patch` intents; `commit_tokens` contains only Host projection
finalization tokens. It must not contain or mutate a `Session`. Add this focused
method to `AgentToolActionService`:

```python
def finalize(self, commit_tokens: Tuple[Any, ...]) -> None:
    for commit_token in commit_tokens:
        self._tools.finalize_observation(commit_token)
```

- [ ] **Step 4: Run tests and commit**

```powershell
uv run pytest tests/test_agent_tool_effects.py tests/test_capability_extensions.py tests/test_dynamic_tool_registration.py -v
git add packages/embedagent-core/src/embedagent_core tests/test_agent_tool_effects.py tests/test_capability_extensions.py tests/test_dynamic_tool_registration.py
git commit -m "refactor: return typed tool effect results"
```

### Task 11: Rewrite AgentLoop As The Commit-Execute-Resume Driver

**Files:**
- Replace: `packages/embedagent-core/src/embedagent_core/agent_loop.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_kernel.py`
- Create: `tests/test_agent_loop_driver.py`
- Modify: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Write driver tests with fake collaborators**

The fake kernel must produce context, provider, and tool effects in order. The
test asserts every pre-effect event is committed before executor invocation:

```python
assert calls == [
    "commit:context_started",
    "execute:context",
    "commit:provider_started",
    "execute:provider",
    "commit:tool_started",
    "execute:tool",
    "commit:completed",
]
```

Add cancellation and stale-result tests. Add an observer that raises from
`on_event`; assert the canonical event remains in `SessionLogPort` and the next
restore sees it. Observer delivery happens after commit and cannot roll back
state.

- [ ] **Step 2: Replace the constructor**

The final constructor is:

```python
class AgentLoop(object):
    def __init__(
        self,
        kernel: AgentKernel,
        journal: SessionJournal,
        provider_steps: ProviderStepService,
        tool_actions: AgentToolActionService,
        continuation_policy: AgentLoopContinuationPolicy,
    ) -> None:
        self._kernel = kernel
        self._journal = journal
        self._provider_steps = provider_steps
        self._tool_actions = tool_actions
        self._continuation_policy = continuation_policy
```

No parameter is optional. Delete `_ensure_configured`, all callback fields,
`tool_capabilities`, and direct `Session` mutator calls.

- [ ] **Step 3: Implement explicit effect dispatch**

Use `isinstance` over the three closed effect types. Unknown effect types raise
`TypeError("unsupported agent effect")`. Commit `step.events`, publish committed
lifecycle events, finalize `step.post_commit_tokens`, execute one effect, and
call `kernel.accept` until an outcome exists. Tool materialization tokens are
finalized only after their corresponding tool-result and content-replacement
events have committed. If observer delivery fails, log a local safe diagnostic
without calling that observer again, then continue from the committed state; do
not undo or repeat the effect.

- [ ] **Step 4: Move loop behavior tests to the driver/kernel owners**

Move progress-guard, safety-fuse, parallel interruption, empty-provider,
compact-retry, and diagnostic-failure assertions from
`test_query_engine_refactor.py` into `test_agent_loop_driver.py` or
`test_agent_effect_kernel.py`. Delete the old direct `QueryEngine` versions.

- [ ] **Step 5: Run tests and commit**

```powershell
uv run pytest tests/test_agent_loop_driver.py tests/test_agent_effect_kernel.py tests/test_guard.py tests/test_c_cpp_workflow_guard_safety.py -v
git add packages/embedagent-core/src/embedagent_core/agent_loop.py packages/embedagent-core/src/embedagent_core/agent_kernel.py tests/test_agent_loop_driver.py tests/test_agent_effect_kernel.py tests/test_query_engine_refactor.py
git commit -m "refactor: make agent loop a closed effect driver"
```

### Task 12: Promote SessionTransaction And Delete QueryEngine

**Files:**
- Create: `packages/embedagent-core/src/embedagent_core/session_transaction.py`
- Modify: `packages/embedagent-core/src/embedagent_core/runner.py`
- Modify: `packages/embedagent-core/src/embedagent_core/api.py`
- Modify: `packages/embedagent-core/src/embedagent_core/hosting.py`
- Delete: `packages/embedagent-core/src/embedagent_core/query_engine.py`
- Delete: `tests/query_engine_product_helpers.py`
- Rename: `tests/test_query_engine_refactor.py` to `tests/test_agent_runtime_integration.py`
- Delete: `tests/test_query_engine_build_lite.py`
- Delete: `tests/test_query_engine_debug_lite.py`
- Delete: `tests/test_query_engine_verify_slice.py`
- Delete: `tests/test_query_engine_build_full_spec.py`

- [ ] **Step 1: Write transaction integration tests through public APIs**

Cover new session, restored session, interaction resume, cancel, explicit turn
fuse, provider compact retry, tool failure, and extension tool execution through
`AgentSession.submit` or `run_agent`. Add simultaneous submits against one
session and assert `SessionLeaseConflict`. Add a recovery transcript ending in
a started side-effecting tool operation with no result; assert resume reports
recovery required and the fake tool runtime is not called. No test imports
`QueryEngine`.

- [ ] **Step 2: Implement SessionTransaction**

The class owns only lease, restore, input dispatch, observer adaptation, and
result projection:

```python
class SessionTransaction(object):
    def __init__(self, session_log, journal, loop, definition, projection):
        self._session_log = session_log
        self._journal = journal
        self._loop = loop
        self._definition = definition
        self._projection = projection

    def submit(self, request, observer=None, cancel=None):
        with self._session_log.acquire_lease(request.session_id):
            state = self._restore_or_create(request.session_id)
            result = self._loop.run(state, request.input, observer, cancel)
            return self._project_result(result)
```

It must not contain provider, tool, extension, context, compaction, or direct
session mutation logic.

- [ ] **Step 3: Assemble the runtime once**

In `AgentRuntime.__init__`, construct one extension manager, reducer, journal,
kernel, provider service, action service, loop, and transaction. Delete
`build_engine` and all `host_*` methods that create a new engine per call.

- [ ] **Step 4: Delete QueryEngine and migrate tests**

Delete the source file and all helper/import paths. Rename retained behavior
tests by owner. The import search must return no result:

```powershell
rg -n "from embedagent_core\.query_engine|import embedagent_core\.query_engine" packages src tests --glob "*.py"
```

Expected: no output.

- [ ] **Step 5: Add architecture guards**

Use import graph and file-existence assertions:

```python
def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


assert not (CORE / "query_engine.py").exists()
for python_file in tuple(CORE.rglob("*.py")) + tuple(HOST.rglob("*.py")):
    assert all(
        "query_engine" not in module
        for module in imported_modules(python_file)
    )
```

- [ ] **Step 6: Run the Core and Host integration suites**

```powershell
uv run pytest tests/test_agent_core_public_api.py tests/test_agent_runtime_integration.py tests/test_host_package_composition.py tests/test_workflow_extensions.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add packages/embedagent-core tests
git commit -m "refactor: delete internal query engine"
```

### Task 13: Freeze The Public Interaction Projection

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/api.py`
- Modify: `packages/embedagent-core/src/embedagent_core/runner.py`
- Modify: `packages/embedagent-core/src/embedagent_core/__init__.py`
- Modify: `scripts/smoke-python-distributions.py`
- Modify: `tests/test_agent_core_public_api.py`

- [ ] **Step 1: Write frozen DTO tests**

```python
from dataclasses import FrozenInstanceError

from embedagent_core import AgentInteractionRequest, AgentResult, AgentSessionView


def test_agent_result_uses_frozen_public_interaction_request():
    source = {"prompt": "Approve?", "options": [{"value": "yes"}]}
    request = AgentInteractionRequest(
        interaction_id="interaction-1",
        kind="permission",
        tool_name="write_file",
        request_payload=source,
    )
    result = AgentResult(
        final_text="",
        session=AgentSessionView("session-1", "build", {}, 0, 0),
        termination_reason="pending_interaction",
        pending_interaction=request,
        turn_snapshot=None,
    )
    source["options"][0]["value"] = "no"

    assert isinstance(result.pending_interaction, AgentInteractionRequest)
    assert result.pending_interaction.request_payload["options"][0]["value"] == "yes"
    with pytest.raises(FrozenInstanceError):
        result.pending_interaction.kind = "changed"
```

- [ ] **Step 2: Add and export the DTO**

```python
@dataclass(frozen=True)
class AgentInteractionRequest:
    interaction_id: str
    kind: str
    tool_name: str
    request_payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_payload", deepcopy(self.request_payload))
```

Keep the `AgentResult.pending_interaction` field name and convert internal
pending state in `runner.py`. Do not export internal `PendingInteraction`.

- [ ] **Step 3: Extend the core-only wheel smoke**

Make the smoke script assert a pending request can round-trip through
`InteractionReply` without importing Host or product packages.

- [ ] **Step 4: Run tests and commit**

```powershell
uv run pytest tests/test_agent_core_public_api.py -v
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
git add packages/embedagent-core scripts/smoke-python-distributions.py tests/test_agent_core_public_api.py
git commit -m "feat: freeze public interaction projection"
```

## Milestone C: Hosted Boundary Without Mutable Session Ownership

### Task 14: Introduce Frozen SessionReadView Ports

**Files:**
- Create: `packages/embedagent-core/src/embedagent_core/session_view.py`
- Modify: `packages/embedagent-core/src/embedagent_core/ports.py`
- Modify: `packages/embedagent-core/src/embedagent_core/tool_contracts.py`
- Modify: `packages/embedagent-core/src/embedagent_core/provider_step_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/project_memory.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/workspace_intelligence.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py`
- Create: `tests/test_session_read_view.py`
- Create: `tests/test_workspace_intelligence.py`
- Modify: `tests/test_context_config.py`
- Modify: `tests/test_project_memory.py`
- Modify: `tests/test_session_projection_service.py`

- [ ] **Step 1: Write mutation-isolation tests**

```python
def test_session_read_view_detaches_nested_state():
    session = Session(session_id="session-1")
    session.add_user_message("hello", turn_id="t-1")

    view = session_read_view(session)
    session.messages[0].content = "changed"

    assert view.messages[0]["content"] == "hello"
```

- [ ] **Step 2: Implement the frozen view**

Use JSON-safe frozen tuples/dicts, not references to `TranscriptMessage`,
`Turn`, or `PendingInteraction`:

```python
@dataclass(frozen=True)
class SessionReadView:
    session_id: str
    started_at: str
    messages: Tuple[Dict[str, Any], ...]
    turns: Tuple[Dict[str, Any], ...]
    workflow_state: Dict[str, Any]
    compact_boundaries: Tuple[Dict[str, Any], ...]
    content_replacements: Tuple[Dict[str, Any], ...]
```

`session_read_view(session)` deep-copies every nested dict/list. Keep this type
out of the package root; it is a focused port value, not the standalone API.

- [ ] **Step 3: Change context and projection ports**

Replace `Session` annotations in `ContextAssemblerPort` and
`SessionProjectionPort` with `SessionReadView`. Update Host implementations to
read dict payloads and remove `from embedagent_core.session import Session`.

- [ ] **Step 4: Pass a view at every Host boundary**

`ProviderStepService` creates one view after each reducer commit and passes it
to context, projection, memory, workspace, and extension-facing operations.
Core tools receive `session_id` and effect metadata, not a mutable session.

- [ ] **Step 5: Run context and Host tests**

```powershell
uv run pytest tests/test_session_read_view.py tests/test_workspace_intelligence.py tests/test_context_config.py tests/test_project_memory.py tests/test_session_projection_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add packages/embedagent-core packages/embedagent-host tests/test_session_read_view.py tests/test_workspace_intelligence.py tests/test_context_config.py tests/test_project_memory.py tests/test_session_projection_service.py
git commit -m "refactor: pass frozen session views to host ports"
```

### Task 15: Remove ManagedSession.session And Promote Hosted Projections

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/hosting.py`
- Modify: `packages/embedagent-core/src/embedagent_core/session_transaction.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/services/session_lifecycle.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_projection.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_projector.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_history.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_command_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py`
- Modify: `tests/test_host_agent_facade.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_hosted_interaction_service.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: Write the target HostedSessionController contract tests**

The tests must call these signatures without constructing `Session`:

```python
controller.initialize(mode="build", workflow_state="")
controller.apply_mode(mode="debug", workflow_state="")
controller.record_command_result(
    HostedCommandRecord("/verify", "verify", True, "ok")
)
snapshot = controller.snapshot()

assert snapshot.session_id == agent_session.session_id
assert snapshot.current_mode == "debug"
```

- [ ] **Step 2: Add a frozen hosted projection**

In `hosting.py` define:

```python
@dataclass(frozen=True)
class HostedSessionProjection:
    session_id: str
    current_mode: str
    status: str
    pending_interaction: Optional[AgentInteractionRequest]
    snapshot: Dict[str, Any] = field(default_factory=dict)
    history: Dict[str, Any] = field(default_factory=dict)
```

Keep it out of the package root.

- [ ] **Step 3: Make hosted operations session-id based**

Remove `session: Session` parameters from `initialize`, `apply_mode`, and
`record_command_result`. Each operation enters `SessionTransaction`, acquires
the same lease, restores from `SessionJournal`, commits through the reducer, and
returns `HostedSessionProjection`.

- [ ] **Step 4: Remove mutable state from ManagedSession**

Replace:

```python
session: Session
```

with:

```python
session_id: str
projection: Dict[str, Any] = field(default_factory=dict)
history: Dict[str, Any] = field(default_factory=dict)
```

Retain `agent_session`, `hosted_session`, worker status, pending UI response,
threading primitives, and Host-owned diagnostics.

- [ ] **Step 5: Replace every `state.session` use**

Use `state.session_id`, `state.projection`, `state.history`, or a fresh
`HostedSessionController.snapshot()`. Do not add a property that reconstructs
or exposes Core `Session`.

Delete Host-side resource-prompt mutation at
`inprocess_adapter.py:793`; resource reload must commit its prompt event through
the hosted session transaction.

- [ ] **Step 6: Remove Host restore ownership**

`SessionLifecycleManager` asks `HostedSessionController` to create/restore and
then stores the returned projection. Delete its `SessionRestorer` constructor
parameter and all imports of `Session` / `SessionRestorer`.

- [ ] **Step 7: Add the Host boundary guard**

AST-scan `packages/embedagent-host/src` and fail on:

```python
FORBIDDEN = {
    "embedagent_core.session.Session",
    "embedagent_core.session_restore.SessionRestorer",
}
```

Imports of immutable Core action/observation DTOs remain allowed until a
separate DTO extraction is justified.

In the same AST guard, reject `agent_session._runtime`,
`agent_session._submit_lock`, and any call to a private `AgentRuntime` member
from Host. Hosted code must use `HostedSessionController`; it must not replace
the mutable `Session` leak with private SDK access.

- [ ] **Step 8: Run Host, Protocol, and GUI backend tests**

```powershell
uv run pytest tests/test_host_agent_facade.py tests/test_inprocess_adapter_frontend_api.py tests/test_hosted_interaction_service.py tests/test_services.py tests/test_session_projection_service.py tests/test_session_event_protocol.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add packages/embedagent-core/src/embedagent_core/hosting.py packages/embedagent-core/src/embedagent_core/session_transaction.py packages/embedagent-host tests
git commit -m "refactor: remove mutable session from host boundary"
```

## Milestone D: Redundancy Retirement And Final Gates

### Task 16: Delete Dormant Strategies And Close Documentation

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/strategies/llm_retry_wrapper.py`
- Delete: `packages/embedagent-core/src/embedagent_core/strategies/execution_tracer.py`
- Delete: `packages/embedagent-core/src/embedagent_core/strategies/circuit_breaker.py`
- Delete: `tests/test_execution_tracer.py`
- Modify: `tests/test_llm_resilience.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/modules/agent-core.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/superpowers/specs/2026-07-27-minimal-agent-core-convergence-design.md`
- Modify: `.gsd/DECISIONS.md`

- [ ] **Step 1: Delete unused resilience surfaces**

Remove the `CircuitBreaker` import, constructor parameter, state checks, and
`CircuitBreakerOpenError` branch from `LLMClientRetryWrapper`. Keep bounded
retry, retry delay parsing, and token tracking. Delete tracer and circuit
breaker source/tests.

- [ ] **Step 2: Add absence guards**

```python
@pytest.mark.parametrize(
    "path",
    (
        "packages/embedagent-core/src/embedagent_core/query_engine.py",
        "packages/embedagent-core/src/embedagent_core/session_restore.py",
        "packages/embedagent-core/src/embedagent_core/strategies/execution_tracer.py",
        "packages/embedagent-core/src/embedagent_core/strategies/circuit_breaker.py",
    ),
)
def test_retired_core_runtime_paths_do_not_exist(path):
    assert not (ROOT / path).exists()
```

- [ ] **Step 3: Update active source-of-truth documentation**

Use this exact architecture vocabulary:

- `AgentSession` is the public durable session transaction handle.
- `SessionJournal` appends before `SessionReducer` applies state.
- `AgentKernel` plans three private effect families.
- `AgentLoop` is the commit-execute-resume driver.
- Host receives frozen views through `HostedSessionController`.
- `QueryEngine`, `SessionRestorer`, mutable Host `Session`, tracer, and circuit
  breaker are retired and have no compatibility aliases.

Set the design and `.gsd/DECISIONS.md` status to `Implemented` only after all
commands in Step 5 pass.

- [ ] **Step 4: Run focused and full Python gates**

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run pytest tests/ -v
uv run --locked python scripts/lint.py
```

Expected: all tests pass; no deselection other than repository-defined markers.

- [ ] **Step 5: Build and smoke all six distributions**

```powershell
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: checker reports `ok: true`; `core_only`, `protocol_only`,
`host_stack`, `composition_only`, `workflow_cpp_only`, and `product_stack` all
report success.

- [ ] **Step 6: Run the GUI gate**

```powershell
Push-Location src/embedagent/frontend/gui/webapp
npm test
npm run build
Pop-Location
```

Expected: Vitest and production build pass; generated files under
`src/embedagent/frontend/gui/static/` are staged with their source change.

- [ ] **Step 7: Verify final searches**

```powershell
rg -n "from embedagent_core\.(query_engine|session_restore|strategies\.(execution_tracer|circuit_breaker))|import embedagent_core\.(query_engine|session_restore|strategies\.(execution_tracer|circuit_breaker))" packages src tests --glob "*.py"
rg -n "session\.(add_|begin_step|record_|resolve_pending)" packages/embedagent-core/src --glob "*.py"
rg -n "from embedagent_core\.session import .*Session" packages/embedagent-host/src --glob "*.py"
rg -n "runtime_config_provider" packages/embedagent-core/src tests --glob "*.py"
```

Expected:

- first search: no output
- second search: matches only inside `session_reducer.py`
- third search: no mutable `Session` import
- fourth search: no output

- [ ] **Step 8: Mark the decision implemented and commit**

After Steps 4-7 pass, change the two status lines to `Implemented`, then:

```powershell
git add AGENTS.md README.md docs .gsd packages/embedagent-core tests src/embedagent/frontend/gui/static
git commit -m "docs: close minimal agent core convergence"
```

## Final Acceptance Checklist

- [ ] `Agent.create -> Agent.open -> AgentSession.submit` remains the standalone SDK.
- [ ] `AgentInteractionRequest` is frozen and no public result exposes mutable pending state.
- [ ] Both extension assembly sources cannot be supplied simultaneously.
- [ ] Every durable state change appends through `SessionJournal` before reducer application.
- [ ] Live and restore use the same closed reducer handlers.
- [ ] `AgentLoop` has five required focused collaborators and no optional callback bag.
- [ ] Only context, provider, and tool private effect families exist.
- [ ] `QueryEngine` and `SessionRestorer` are deleted without aliases.
- [ ] `runtime_config_provider` and the loop callback bag are deleted.
- [ ] Host owns only handles, projections, diagnostics, and UI worker state.
- [ ] Host does not import or receive mutable Core `Session`.
- [ ] Ordinary tool/build/test failures remain model-visible observations.
- [ ] Uncertain side-effecting operations are never replayed automatically.
- [ ] Core remains Python 3.8 compatible and dependency-free.
- [ ] Generic Core and specialized C/C++ composition both pass isolated wheel smoke.
- [ ] Active architecture documents describe only the promoted path.
