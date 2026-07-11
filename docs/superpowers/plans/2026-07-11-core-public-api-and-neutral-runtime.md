# Core Public API And Neutral Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `embedagent_core` directly usable through a small Agent SDK while preserving the existing hosted product and removing implicit workflow, mode, and permission defaults.

**Architecture:** Introduce frozen public input types, an internal bound runtime, a functional `run_agent()` primitive, and `Agent`/`AgentSession` facades. Promote session restore and lease-aware log contracts into Core, then route hosted user turns and interaction replies through the facade without exposing `QueryEngine` as the integration API.

**Tech Stack:** Python 3.8 dataclasses and typing protocols, threading locks, existing transcript schema v2, pytest, no new runtime dependencies.

---

## File Structure

- Create `src/embedagent_core/api.py`
  - public inputs, results, observer, ports bundle, runtime definition, `Agent`,
    and `AgentSession`.
- Create `src/embedagent_core/runner.py`
  - internal `AgentRuntime`, one extension manager, engine construction, restore,
    and `run_agent()` dispatch.
- Create `src/embedagent_core/session_log.py`
  - `SessionLogPort`, lease protocol, conflict error, and in-memory adapter.
- Move `src/embedagent/session_restore.py` to
  `src/embedagent_core/session_restore.py`.
- Modify `src/embedagent_core/query_engine.py`
  - neutral workflow defaults and explicit permission default.
- Modify `src/embedagent_core/policies.py`
  - neutral no-mode policy.
- Modify `src/embedagent_core/turn_snapshot.py`
  - preserve empty workflow state.
- Modify `src/embedagent_core/extensions.py`,
  `src/embedagent_core/agent_extension_host.py`, and `src/embedagent_core/ports.py`
  - preserve empty workflow values and use the promoted log contract.
- Modify `src/embedagent_core/__init__.py`
  - export only the stable SDK surface.
- Modify `src/embedagent/transcript_store.py`
  - implement the session lease contract.
- Modify `src/embedagent_host/inprocess_adapter.py`
  - own one `Agent` and store `AgentSession` handles in managed state.
- Modify `src/embedagent/session_runtime.py`
  - remove the `chat` default and type the runtime handle generically.
- Test with `tests/test_agent_core_public_api.py`,
  `tests/test_session_log_port.py`, `tests/test_session_restore.py`,
  `tests/test_host_agent_facade.py`, and existing QueryEngine/adapter suites.

### Task 1: Add Failing Public Contract Guards

**Files:**
- Create: `tests/test_agent_core_public_api.py`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Test: `tests/test_agent_core_public_api.py`

- [ ] **Step 1: Write the public import and neutral-state tests**

Create `tests/test_agent_core_public_api.py` with the following initial tests:

```python
from unittest.mock import MagicMock

from embedagent_core import (
    Agent,
    AgentObserver,
    AgentPorts,
    AgentResult,
    AgentSession,
    CancelToken,
    InteractionReply,
    RuntimeDefinition,
    UserTurn,
)
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.turn_snapshot import TurnSnapshot


def test_public_sdk_exports_are_available():
    assert Agent is not None
    assert AgentSession is not None
    assert AgentObserver is not None
    assert CancelToken is not None
    assert AgentPorts is not None
    assert RuntimeDefinition is not None
    assert UserTurn is not None
    assert InteractionReply is not None
    assert AgentResult is not None


def test_turn_snapshot_preserves_empty_workflow_state():
    snapshot = TurnSnapshot(
        snapshot_id="snapshot-1",
        session_id="session-1",
        turn_id="turn-1",
        step_id="",
        mode_name="",
        workflow_state="",
    )
    assert snapshot.workflow_state == ""


def test_standalone_permission_policy_is_not_auto_approve():
    policy = PermissionPolicy()
    assert policy.auto_approve_all is False
```

- [ ] **Step 2: Add source guards for removed defaults**

Append this test to `tests/test_pre_release_architecture_guards.py`:

```python
def test_public_core_has_no_chat_or_auto_approve_defaults():
    checked = (
        ROOT / "src/embedagent_core/query_engine.py",
        ROOT / "src/embedagent_core/turn_snapshot.py",
        ROOT / "src/embedagent_core/ports.py",
        ROOT / "src/embedagent_core/extensions.py",
        ROOT / "src/embedagent_core/agent_extension_host.py",
    )
    offenders = []
    for path in checked:
        text = _read(path)
        for token in ('workflow_state: str = "chat"', 'or "chat"'):
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    query_text = _read(ROOT / "src/embedagent_core/query_engine.py")
    if "PermissionPolicy(auto_approve_all=True)" in query_text:
        offenders.append("query_engine.py auto-approves by default")
    assert offenders == []
```

- [ ] **Step 3: Run the tests and verify the target is red**

Run:

```bash
uv run pytest tests/test_agent_core_public_api.py tests/test_pre_release_architecture_guards.py::test_public_core_has_no_chat_or_auto_approve_defaults -v
```

Expected: FAIL because the public types do not exist and the current defaults
still contain `chat` and `auto_approve_all=True`.

- [ ] **Step 4: Commit the red contract tests**

```bash
git add tests/test_agent_core_public_api.py tests/test_pre_release_architecture_guards.py
git commit -m "test: define standalone agent core contract"
```

### Task 2: Define Frozen Public Input And Result Types

**Files:**
- Create: `src/embedagent_core/api.py`
- Modify: `src/embedagent_core/__init__.py`
- Modify: `src/embedagent_core/policies.py`
- Test: `tests/test_agent_core_public_api.py`

- [ ] **Step 1: Add input validation tests**

Append to `tests/test_agent_core_public_api.py`:

```python
import pytest


def test_user_turn_requires_text():
    with pytest.raises(ValueError, match="user turn text is required"):
        UserTurn("")


def test_interaction_reply_requires_identity():
    with pytest.raises(ValueError, match="interaction id is required"):
        InteractionReply("", {})


def test_runtime_definition_defaults_to_no_mode_or_workflow():
    definition = RuntimeDefinition()
    assert definition.agent_id == "embedagent.base"
    assert definition.default_mode == ""
    assert definition.workflow_state == ""
    assert definition.extensions == ()
```

- [ ] **Step 2: Run the focused tests and verify they fail**

```bash
uv run pytest tests/test_agent_core_public_api.py -v
```

Expected: FAIL because the data classes are not implemented.

- [ ] **Step 3: Add a neutral runtime policy**

Add to `src/embedagent_core/policies.py`:

```python
class NeutralModeRuntimePolicy(object):
    def default_mode(self) -> str:
        return ""

    def require_mode(self, mode_name: str) -> Dict[str, Any]:
        return {"slug": str(mode_name or "")}

    def build_system_prompt(
        self,
        mode_name: str,
        app_config: Any = None,
        workspace: str = "",
        local_resources: Any = None,
    ) -> str:
        del mode_name, app_config, workspace, local_resources
        return ""

    def parse_mode_switch_request(
        self,
        user_text: str,
        fallback_mode: str,
    ) -> Tuple[str, str, bool]:
        return str(fallback_mode or ""), str(user_text or ""), False
```

- [ ] **Step 4: Implement the public records and protocols**

Create `src/embedagent_core/api.py` with these public records. Leave `Agent`
and `AgentSession` construction methods raising `NotImplementedError` until
Task 5.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, Tuple, Union

from embedagent_core.model import ModelClient
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.policies import (
    DenyWritePathPolicy,
    EmptyModeToolPolicy,
    ModeRuntimePolicy,
    ModeToolPolicy,
    NeutralModeRuntimePolicy,
    WritePathPolicy,
)
from embedagent_core.ports import ContextAssemblerPort
from embedagent_core.session import PendingInteraction
from embedagent_core.session_log import SessionLogPort
from embedagent_core.tool_contracts import ToolRuntimePort


class AgentObserver(Protocol):
    def on_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError


class CancelToken(Protocol):
    def is_set(self) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class UserTurn:
    text: str
    mode: str = ""
    stream: bool = True

    def __post_init__(self) -> None:
        if not str(self.text or "").strip():
            raise ValueError("user turn text is required")


@dataclass(frozen=True)
class InteractionReply:
    interaction_id: str
    value: Dict[str, Any]
    stream: bool = True

    def __post_init__(self) -> None:
        if not str(self.interaction_id or "").strip():
            raise ValueError("interaction id is required")
        object.__setattr__(self, "value", dict(self.value or {}))


AgentInput = Union[UserTurn, InteractionReply]


@dataclass(frozen=True)
class AgentPorts:
    model: ModelClient
    tools: ToolRuntimePort
    session_log: SessionLogPort
    context: ContextAssemblerPort
    permissions: PermissionPolicy


@dataclass(frozen=True)
class RuntimeDefinition:
    agent_id: str = "embedagent.base"
    default_mode: str = ""
    workflow_state: str = ""
    extensions: Tuple[Any, ...] = field(default_factory=tuple)
    mode_tool_policy: ModeToolPolicy = field(default_factory=EmptyModeToolPolicy)
    write_path_policy: WritePathPolicy = field(default_factory=DenyWritePathPolicy)
    mode_runtime_policy: ModeRuntimePolicy = field(default_factory=NeutralModeRuntimePolicy)


@dataclass(frozen=True)
class AgentSessionView:
    session_id: str
    current_mode: str
    workflow_state: Dict[str, Any]
    message_count: int
    turn_count: int


@dataclass(frozen=True)
class AgentResult:
    final_text: str
    session: AgentSessionView
    termination_reason: str
    pending_interaction: Optional[PendingInteraction]
    turn_snapshot: Optional[Any]


class Agent(object):
    @classmethod
    def create(cls, ports: AgentPorts, definition: Optional[RuntimeDefinition] = None):
        raise NotImplementedError

    def open(self, session_id: str = ""):
        raise NotImplementedError


class AgentSession(object):
    def submit(
        self,
        input_value: AgentInput,
        observer: Optional[AgentObserver] = None,
        cancel: Optional[CancelToken] = None,
    ) -> AgentResult:
        raise NotImplementedError
```

Export these record/protocol names from `src/embedagent_core/__init__.py` in
this task so the public import and validation tests can turn green. The facade
classes are importable but their behavior remains intentionally unimplemented
until Task 5.

- [ ] **Step 5: Run the record tests**

```bash
uv run pytest tests/test_agent_core_public_api.py -v
```

Expected: public import and validation/default tests pass. No facade execution
test exists until Task 5.

- [ ] **Step 6: Commit the public records**

```bash
git add src/embedagent_core/api.py src/embedagent_core/__init__.py src/embedagent_core/policies.py tests/test_agent_core_public_api.py
git commit -m "feat: define agent core public records"
```

### Task 3: Promote Session Restore And Lease-Aware Log Contracts

**Files:**
- Create: `src/embedagent_core/session_log.py`
- Modify: `src/embedagent_core/ports.py`
- Modify: `src/embedagent_core/query_engine.py`
- Move: `src/embedagent/session_restore.py` to `src/embedagent_core/session_restore.py`
- Modify: `src/embedagent/transcript_store.py`
- Modify: `src/embedagent_host/inprocess_adapter.py`
- Modify: `src/embedagent/services/session_lifecycle.py`
- Test: `tests/test_session_log_port.py`
- Test: `tests/test_session_restore.py`

- [ ] **Step 1: Write lease and neutral restore tests**

Create `tests/test_session_log_port.py`:

```python
import pytest

from embedagent_core.session_log import InMemorySessionLog, SessionLeaseConflict


def test_session_log_rejects_overlapping_lease():
    log = InMemorySessionLog()
    with log.acquire_lease("session-1"):
        with pytest.raises(SessionLeaseConflict):
            with log.acquire_lease("session-1"):
                pass


def test_different_sessions_can_be_leased_independently():
    log = InMemorySessionLog()
    with log.acquire_lease("session-1"):
        with log.acquire_lease("session-2"):
            assert True


def test_session_log_emits_complete_schema_v2_events():
    log = InMemorySessionLog()
    first = log.append_event("session-1", "user", {"content": "hello"})
    second = log.append_event("session-1", "assistant", {"content": "done"})
    assert first["seq"] == 1
    assert second["seq"] == 2
    assert first["event_id"].startswith("evt-")
    assert first["ts"].endswith("Z")
```

Append to `tests/test_session_restore.py`:

```python
def test_restore_does_not_invent_default_mode():
    restored = SessionRestorer().restore([
        {
            "schema_version": 2,
            "seq": 1,
            "session_id": "session-1",
            "type": "session_meta",
            "ts": "2026-01-01T00:00:00Z",
            "payload": {},
        }
    ])
    assert restored.current_mode == ""
```

- [ ] **Step 2: Run the focused tests and verify they fail**

```bash
uv run pytest tests/test_session_log_port.py tests/test_session_restore.py::test_restore_does_not_invent_default_mode -v
```

Expected: FAIL because `session_log` does not exist and restore defaults to
`explore`.

- [ ] **Step 3: Implement the Core log contract and memory adapter**

Move `TranscriptStorePort` and `InMemoryTranscriptStore` out of
`src/embedagent_core/ports.py` into `src/embedagent_core/session_log.py`, rename
them `SessionLogPort` and `InMemorySessionLog`, and add the lease contract.
There must be one log protocol and one Core memory implementation after this
step. Use this complete memory behavior:

```python
from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Protocol


class SessionLeaseConflict(RuntimeError):
    pass


class SessionLogPort(Protocol):
    def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        event_id: str = "",
        ts: str = "",
        schema_version: int = 2,
    ) -> Any:
        raise NotImplementedError

    def transcript_exists(self, session_id: str) -> bool:
        raise NotImplementedError

    def load_events(self, session_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def acquire_lease(self, session_id: str):
        raise NotImplementedError


class InMemorySessionLog(object):
    def __init__(self) -> None:
        self._events = {}  # type: Dict[str, List[Dict[str, Any]]]
        self._leased = set()
        self._guard = threading.RLock()

    @contextmanager
    def acquire_lease(self, session_id: str) -> Iterator[None]:
        key = str(session_id or "")
        with self._guard:
            if key in self._leased:
                raise SessionLeaseConflict("session is already active: %s" % key)
            self._leased.add(key)
        try:
            yield
        finally:
            with self._guard:
                self._leased.discard(key)

    def append_event(
        self,
        session_id,
        event_type,
        payload,
        event_id="",
        ts="",
        schema_version=2,
    ):
        if schema_version != 2:
            raise ValueError("transcript events must use schema_version 2")
        key = str(session_id or "")
        with self._guard:
            events = self._events.setdefault(key, [])
            timestamp = ts or datetime.now(timezone.utc).replace(
                microsecond=0
            ).isoformat().replace("+00:00", "Z")
            event = {
                "schema_version": 2,
                "session_id": key,
                "event_id": event_id or ("evt-" + uuid.uuid4().hex[:12]),
                "seq": len(events) + 1,
                "ts": timestamp,
                "type": str(event_type or ""),
                "parent_message_id": str((payload or {}).get("parent_message_id") or ""),
                "payload": dict(payload or {}),
            }
            events.append(event)
        return dict(event)

    def transcript_exists(self, session_id):
        with self._guard:
            return bool(self._events.get(str(session_id or "")))

    def load_events(self, session_id):
        with self._guard:
            return [dict(item) for item in self._events.get(str(session_id or ""), [])]
```

Update `QueryEngine` to import `SessionLogPort` and `InMemorySessionLog` from
the new module. Keep the internal constructor keyword `transcript_store` in
this phase to limit caller churn, but delete `TranscriptStorePort` and
`InMemoryTranscriptStore` from `ports.py`; do not leave aliases.

- [ ] **Step 4: Move restore into Core and remove the mode fallback**

Run:

```bash
git mv src/embedagent/session_restore.py src/embedagent_core/session_restore.py
```

In the moved file, change:

```python
current_mode = "explore"
```

to:

```python
current_mode = ""
```

Update imports in `src/embedagent_host/inprocess_adapter.py`,
`src/embedagent/services/session_lifecycle.py`, and tests from
`embedagent.session_restore` to `embedagent_core.session_restore`. Do not add a
compatibility re-export.

- [ ] **Step 5: Add the same lease contract to TranscriptStore**

In `src/embedagent/transcript_store.py`, add an in-process lease set guarded by
an `RLock` and implement:

```python
@contextmanager
def acquire_lease(self, session_id: str):
    key = str(session_id or "")
    with self._session_lease_guard:
        if key in self._session_leases:
            raise SessionLeaseConflict("session is already active: %s" % key)
        self._session_leases.add(key)
    try:
        yield
    finally:
        with self._session_lease_guard:
            self._session_leases.discard(key)
```

Import `contextmanager` and `SessionLeaseConflict` explicitly.

- [ ] **Step 6: Run restore and log tests**

```bash
uv run pytest tests/test_session_log_port.py tests/test_session_restore.py tests/test_transcript_store.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit the log boundary**

```bash
git add src/embedagent_core/session_log.py src/embedagent_core/session_restore.py src/embedagent_core/ports.py src/embedagent_core/query_engine.py src/embedagent/transcript_store.py src/embedagent_host/inprocess_adapter.py src/embedagent/services/session_lifecycle.py tests/test_session_log_port.py tests/test_session_restore.py tests/test_transcript_store.py
git commit -m "refactor: promote session log restore boundary"
```

### Task 4: Implement The Functional Runner

**Files:**
- Create: `src/embedagent_core/runner.py`
- Modify: `src/embedagent_core/api.py`
- Test: `tests/test_agent_core_public_api.py`

- [ ] **Step 1: Add fake-model execution and interaction-id tests**

Add a minimal `FakeModel`, `NoopContextAssembler`, and tool runtime fixture to
`tests/test_agent_core_public_api.py`, following existing fixtures in
`tests/test_query_engine_refactor.py`. Add these assertions:

```python
def test_run_agent_executes_base_user_turn(base_runtime):
    result = run_agent(
        base_runtime,
        AgentRequest("session-1", UserTurn("hello", stream=False)),
    )
    assert result.session.session_id == "session-1"
    assert result.session.current_mode == ""
    assert result.final_text == "done"


def test_run_agent_rejects_wrong_interaction_id(runtime_with_pending):
    with pytest.raises(ValueError, match="interaction id does not match"):
        run_agent(
            runtime_with_pending,
            AgentRequest("session-1", InteractionReply("wrong", {})),
        )
```

- [ ] **Step 2: Run the focused tests and verify they fail**

```bash
uv run pytest tests/test_agent_core_public_api.py -k "run_agent" -v
```

Expected: FAIL because runner types and behavior do not exist.

- [ ] **Step 3: Implement the bound runtime and request**

In `src/embedagent_core/runner.py`, define:

```python
@dataclass(frozen=True)
class AgentRequest:
    session_id: str
    input: AgentInput


class AgentRuntime(object):
    def __init__(self, ports: AgentPorts, definition: RuntimeDefinition) -> None:
        self.ports = ports
        self.definition = definition
        self.extension_manager = ExtensionManager(list(definition.extensions))

    def build_engine(self) -> QueryEngine:
        return QueryEngine(
            client=self.ports.model,
            tools=self.ports.tools,
            permission_policy=self.ports.permissions,
            context_manager=self.ports.context,
            transcript_store=self.ports.session_log,
            extension_manager=self.extension_manager,
            mode_tool_policy=self.definition.mode_tool_policy,
            write_path_policy=self.definition.write_path_policy,
            mode_runtime_policy=self.definition.mode_runtime_policy,
        )
```

- [ ] **Step 4: Implement restore, dispatch, and result projection**

Add `run_agent()` in the same file. It must:

1. enter `runtime.ports.session_log.acquire_lease(session_id)`;
2. restore with `SessionRestorer` only when the log exists;
3. construct a new `Session(session_id=session_id)` otherwise;
4. dispatch `UserTurn` to `submit_user_turn()`;
5. verify the pending interaction id before `resume_interaction()`;
6. return `AgentResult` with a copied `AgentSessionView` and the engine's last
   snapshot.

Map QueryEngine callbacks to `AgentObserver.on_event()` with stable generic
kinds: `text.delta`, `reasoning.delta`, `tool.started`, `tool.finished`,
`context.assembled`, `step.started`, and `step.finished`. Payloads are copied
JSON-safe records and do not expose mutable Core objects. Pass `cancel`
directly as the QueryEngine stop event because the public `CancelToken`
contract is the required `is_set()` subset.

Use this exact projection helper:

```python
def _session_view(session: Session, current_mode: str) -> AgentSessionView:
    return AgentSessionView(
        session_id=session.session_id,
        current_mode=str(current_mode or ""),
        workflow_state=dict(session.workflow_state or {}),
        message_count=len(session.messages),
        turn_count=len(session.turns),
    )
```

Reject unsupported input types with `TypeError("unsupported agent input")`.

- [ ] **Step 5: Run runner and existing QueryEngine tests**

```bash
uv run pytest tests/test_agent_core_public_api.py tests/test_query_engine_refactor.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the functional runner**

```bash
git add src/embedagent_core/runner.py src/embedagent_core/api.py tests/test_agent_core_public_api.py
git commit -m "feat: add replayable agent runner"
```

### Task 5: Implement Agent And AgentSession Facades

**Files:**
- Modify: `src/embedagent_core/api.py`
- Modify: `src/embedagent_core/__init__.py`
- Test: `tests/test_agent_core_public_api.py`

- [ ] **Step 1: Add facade and overlap tests**

Append:

```python
def test_agent_facade_opens_and_submits(base_ports):
    agent = Agent.create(base_ports)
    result = agent.open("session-1").submit(UserTurn("hello", stream=False))
    assert result.final_text == "done"


def test_agent_session_rejects_overlapping_submit(base_ports):
    session = Agent.create(base_ports).open("session-1")
    session._submit_lock.acquire()
    try:
        with pytest.raises(SessionLeaseConflict):
            session.submit(UserTurn("hello", stream=False))
    finally:
        session._submit_lock.release()
```

- [ ] **Step 2: Run the facade tests and verify they fail**

```bash
uv run pytest tests/test_agent_core_public_api.py -k "facade or overlapping" -v
```

Expected: FAIL because facade methods still raise `NotImplementedError`.

- [ ] **Step 3: Implement one bound runtime per Agent**

Replace the placeholder classes in `api.py` with implementations that import
`AgentRuntime`, `AgentRequest`, and `run_agent` inside methods to avoid an
import cycle. `Agent.create()` constructs exactly one `AgentRuntime`.

`AgentSession.submit()` must acquire a non-blocking local lock before calling
the runner:

```python
if not self._submit_lock.acquire(False):
    raise SessionLeaseConflict("agent session already has an active submit")
try:
    return run_agent(
        self._runtime,
        AgentRequest(self.session_id, input_value),
        observer=observer,
        cancel=cancel,
    )
finally:
    self._submit_lock.release()
```

- [ ] **Step 4: Export the stable SDK names**

Replace `src/embedagent_core/__init__.py` with explicit exports:

```python
"""Public EmbedAgent Core SDK."""

__version__ = "0.1.0"

from embedagent_core.api import (
    Agent,
    AgentObserver,
    AgentPorts,
    AgentResult,
    AgentSession,
    AgentSessionView,
    CancelToken,
    InteractionReply,
    RuntimeDefinition,
    UserTurn,
)

__all__ = [
    "Agent",
    "AgentObserver",
    "AgentPorts",
    "AgentResult",
    "AgentSession",
    "AgentSessionView",
    "CancelToken",
    "InteractionReply",
    "RuntimeDefinition",
    "UserTurn",
]
```

- [ ] **Step 5: Run the full public contract suite**

```bash
uv run pytest tests/test_agent_core_public_api.py tests/test_session_log_port.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the SDK facade**

```bash
git add src/embedagent_core/api.py src/embedagent_core/__init__.py tests/test_agent_core_public_api.py
git commit -m "feat: expose standalone agent core sdk"
```

### Task 6: Remove Implicit Workflow, Mode, And Permission Defaults

**Files:**
- Modify: `src/embedagent_core/query_engine.py`
- Modify: `src/embedagent_core/turn_snapshot.py`
- Modify: `src/embedagent_core/ports.py`
- Modify: `src/embedagent_core/extensions.py`
- Modify: `src/embedagent_core/agent_extension_host.py`
- Modify: `src/embedagent/session_runtime.py`
- Modify: `src/embedagent/core/adapter.py`
- Test: `tests/test_agent_core_public_api.py`
- Test: `tests/test_gui_protocol_projection.py`

- [ ] **Step 1: Replace all Core workflow defaults with empty strings**

Use `rg` to enumerate the exact sites:

```bash
rg -n 'workflow_state[^\n]*"chat"|or "chat"' src/embedagent_core src/embedagent/core/adapter.py src/embedagent/session_runtime.py
```

Change function defaults and dataclass defaults to `""`. In
`TurnSnapshot.__post_init__`, use:

```python
self.workflow_state = str(self.workflow_state or "").strip()
```

Do not replace `chat` with another invented value.

- [ ] **Step 2: Change QueryEngine to explicit safe defaults**

In `QueryEngine.__init__`, replace:

```python
self.permission_policy = permission_policy or PermissionPolicy(auto_approve_all=True)
```

with:

```python
self.permission_policy = permission_policy or PermissionPolicy()
```

Use `NeutralModeRuntimePolicy()` rather than
`PassThroughModeRuntimePolicy()` as the default. Skip insertion of empty profile
or mode system messages in `initialize_session()` and `apply_mode()`.

- [ ] **Step 3: Run focused neutral-state tests**

```bash
uv run pytest tests/test_agent_core_public_api.py tests/test_gui_protocol_projection.py tests/test_query_engine_refactor.py -v
```

Expected: PASS.

- [ ] **Step 4: Run the source guard and inspect remaining chat values**

```bash
uv run pytest tests/test_pre_release_architecture_guards.py::test_public_core_has_no_chat_or_auto_approve_defaults -v
rg -n 'workflow_state[^\n]*"chat"|or "chat"' src/embedagent_core src/embedagent/core/adapter.py src/embedagent/session_runtime.py
```

Expected: test passes and `rg` prints no matches.

- [ ] **Step 5: Commit neutral defaults**

```bash
git add src/embedagent_core src/embedagent/session_runtime.py src/embedagent/core/adapter.py tests/test_agent_core_public_api.py tests/test_gui_protocol_projection.py tests/test_pre_release_architecture_guards.py
git commit -m "refactor: make core workflow and mode neutral"
```

### Task 7: Route Hosted User And Interaction Turns Through The Facade

**Files:**
- Modify: `src/embedagent/session_runtime.py`
- Modify: `src/embedagent_host/inprocess_adapter.py`
- Modify: `src/embedagent_host/hosted_interaction_service.py`
- Create: `tests/test_host_agent_facade.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Write the hosted integration ownership test**

Create `tests/test_host_agent_facade.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_host_constructs_agent_facade_not_query_engine():
    text = (ROOT / "src/embedagent_host/inprocess_adapter.py").read_text(encoding="utf-8")
    assert "Agent.create(" in text
    assert "QueryEngine(" not in text


def test_managed_session_uses_agent_session_handle():
    text = (ROOT / "src/embedagent/session_runtime.py").read_text(encoding="utf-8")
    assert "agent_session" in text
    assert "engine: Any" not in text
```

- [ ] **Step 2: Run the ownership tests and verify they fail**

```bash
uv run pytest tests/test_host_agent_facade.py -v
```

Expected: FAIL because the adapter still constructs `QueryEngine` and managed
state stores `engine`.

- [ ] **Step 3: Store AgentSession on managed state**

In `src/embedagent/session_runtime.py`, replace `engine: Any = None` with:

```python
agent_session: Any = None
```

Keep Host-owned status, command, and UI projection fields in `ManagedSession`;
do not move them into Core.

- [ ] **Step 4: Build one Agent in InProcessAdapter**

In adapter construction, create `AgentPorts` from the existing concrete model,
tools, transcript store, context manager, and permission policy. Build
`RuntimeDefinition` from the selected application policies and extensions, and
call `Agent.create()` once.

Replace the current `QueryEngine` factory with `self.agent.open(session_id)`.
Route normal user turns to
`AgentSession.submit(UserTurn(text, mode=current_mode, stream=stream))` and
interaction responses to
`AgentSession.submit(InteractionReply(interaction_id, payload, stream=stream))`.

Hosted command-owned tool execution may use an internal method on
`AgentSession` during this plan, but the method must remain under
`embedagent_core.runner` and must use the same engine/action pipeline and
extension manager. Do not construct a second engine or manager in Host.

- [ ] **Step 5: Run adapter, interaction, and facade tests**

```bash
uv run pytest tests/test_host_agent_facade.py tests/test_inprocess_adapter_frontend_api.py tests/test_hosted_interaction_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit hosted facade adoption**

```bash
git add src/embedagent/session_runtime.py src/embedagent_host/inprocess_adapter.py src/embedagent_host/hosted_interaction_service.py tests/test_host_agent_facade.py tests/test_inprocess_adapter_frontend_api.py
git commit -m "refactor: host sessions through agent facade"
```

### Task 8: Close Plan 1 Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`

- [ ] **Step 1: Update source-of-truth documentation**

Document these promoted facts:

```text
Agent / AgentSession are the public Core SDK.
run_agent is the low-level execution primitive.
QueryEngine is internal implementation.
SessionLogPort is the durable log contract; transcript.jsonl is an adapter.
Missing mode/workflow remains empty.
Standalone permissions default to ask/deny.
Hosted sessions use one Agent runtime and one extension manager.
```

Remove text that still presents `QueryEngine` as the public session facade or
`chat` as a universal workflow state.

- [ ] **Step 2: Run Plan 1 verification**

```bash
uv run pytest tests/test_agent_core_public_api.py tests/test_session_log_port.py tests/test_session_restore.py tests/test_host_agent_facade.py -v
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Expected: all commands exit zero.

- [ ] **Step 3: Run GUI regression tests**

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
```

Expected: frontend tests and production build pass; generated static assets are
updated and included if the build changes them.

- [ ] **Step 4: Verify import and source boundaries**

```bash
uv run python -c "from embedagent_core import Agent, AgentPorts, RuntimeDefinition; print(Agent.__name__)"
rg -n 'workflow_state[^\n]*"chat"|PermissionPolicy\(auto_approve_all=True\)' src/embedagent_core
git diff --check
```

Expected: prints `Agent`; `rg` prints no matches; `git diff --check` exits zero.

- [ ] **Step 5: Commit Plan 1 closeout**

```bash
git add README.md AGENTS.md docs src/embedagent/frontend/gui/static
git commit -m "docs: promote standalone agent core api"
```
