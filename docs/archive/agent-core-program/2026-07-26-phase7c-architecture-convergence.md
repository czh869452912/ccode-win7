# Phase 7C Architecture Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining cross-layer compatibility paths so workflow policy, hosted session control, runtime services, and GUI events each have one explicit owner and one supported path.

**Architecture:** Work vertically through six independently mergeable milestones. Each task first fixes the intended contract in a focused test, promotes one path, deletes the displaced path in the same commit, and adds an architecture guard so the debt cannot return. Core remains dependency-free, Host depends only on Core and Protocol, workflow packages depend only on Core, and product/GUI code stays above those boundaries.

**Tech Stack:** Python 3.8, dataclasses and typing protocols, pytest, React/JavaScript helper tests, uv workspace builds, six isolated Python wheel smokes.

---

## Plan Boundaries

This plan implements the approved design in
`docs/superpowers/specs/2026-07-26-phase7c-architecture-convergence-design.md`.
It does not implement independent Agent export, clean Windows 7 acceptance, or
Phase 8 real-project C/C++ validation.

The tasks must run in order. Do not start the next numbered task while the
current task still has a legacy and promoted path in production source.

## File Ownership Map

- `packages/embedagent-core/src/embedagent_core/api.py`: standalone public Agent records and facade only.
- `packages/embedagent-core/src/embedagent_core/hosting.py`: supported non-root API used only by Host to control managed sessions.
- `packages/embedagent-core/src/embedagent_core/runner.py`: low-level Agent runtime construction and standalone turn execution.
- `packages/embedagent-core/src/embedagent_core/ports.py`: focused context, projection, and restore ports.
- `packages/embedagent-core/src/embedagent_core/tool_contracts.py`: workflow-neutral tool runtime contract.
- `packages/embedagent-core/src/embedagent_core/query_engine.py`: internal coordinator; no hosted service construction or compatibility forwarding.
- `packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py`: the only Host-to-Protocol event encoder and sequence owner.
- `packages/embedagent-protocol/src/embedagent_protocol/session_events.py`: JSON-safe wire envelope and structured failure record.
- `src/embedagent/core/adapter.py`: product facade over Host; forwards Protocol events without reshaping them.
- `src/embedagent/frontend/gui/backend/server.py`: transports Protocol events unchanged.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`: the single Protocol-event-to-UI effect projection.

## Phase 7C.1: Workflow Neutrality

### Task 1: Make Workflow-Neutral Tool Schemas Independent Of State Names

**Files:**
- Modify: `tests/test_tools_v2_runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Add the failing arbitrary-state schema test**

Add this test beside the existing schema projection tests:

```python
def test_workflow_neutral_tools_accept_arbitrary_workflow_state(self):
    from embedagent_host.runtime.tools import ToolRuntime

    runtime = ToolRuntime(self.workspace)
    names = [
        item["function"]["name"]
        for item in runtime.schemas_for(
            "build",
            workflow_state="custom-review-state",
            tool_names=["read_file", "write_file", "ask_user"],
        )
    ]
    self.assertEqual(names, ["read_file", "write_file", "ask_user"])
```

- [ ] **Step 2: Run the test and confirm the current filter fails**

Run:

```powershell
uv run pytest tests/test_tools_v2_runtime.py::ToolsV2RuntimeTests::test_workflow_neutral_tools_accept_arbitrary_workflow_state -v
```

Expected: FAIL because `schemas_for()` returns an empty list.

- [ ] **Step 3: Remove state visibility from built-in workflow-neutral metadata**

In `runtime.py`, set every built-in tool entry in `_BUILTIN_TOOL_METADATA` to an
empty visibility list and preserve the existing filter for dynamically
registered or workflow-owned tools:

```python
"workflow_visibility": [],
```

Change the projection default without changing explicit workflow-owned filters:

```python
def schemas_for(
    self,
    mode: str,
    workflow_state: str = "",
    tool_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
```

- [ ] **Step 4: Add a source guard against generic legacy-state metadata**

Add to `test_pre_release_architecture_guards.py`:

```python
def test_generic_host_tools_do_not_encode_legacy_workflow_states():
    source = (
        ROOT
        / "packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py"
    ).read_text(encoding="utf-8")
    metadata_source = source.split("class ToolRuntime", 1)[0]
    visibility_lines = [
        line.strip()
        for line in metadata_source.splitlines()
        if '"workflow_visibility"' in line
    ]
    assert visibility_lines
    assert set(visibility_lines) == {'"workflow_visibility": [],'}
```

- [ ] **Step 5: Run focused tool and extension tests**

Run:

```powershell
uv run pytest tests/test_tools_v2_runtime.py tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py tests/test_pre_release_architecture_guards.py -v
```

Expected: PASS. Dynamic/workflow-owned visibility tests still filter explicit
states, while built-in tools accept the custom state.

- [ ] **Step 6: Commit the workflow-neutral tool projection**

```powershell
git add tests/test_tools_v2_runtime.py packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py tests/test_pre_release_architecture_guards.py
git commit -m "refactor: make base tool projection workflow neutral"
```

### Task 2: Preserve Empty Workflow State Across Core, Host, Protocol, And C++

**Files:**
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/services/session_lifecycle.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py`
- Modify: `tests/test_agent_app_protocol.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_current_architecture_boundaries.py`

- [ ] **Step 1: Add tests that reject synthesized `chat` state**

Add protocol coverage:

```python
def test_session_snapshot_preserves_missing_workflow_state():
    snapshot = SessionSnapshot(
        session_id="s-1",
        status=SessionStatus.IDLE,
        current_mode="explore",
        created_at="",
        updated_at="",
    )
    assert snapshot.workflow_state == ""
```

Add an adapter test to `TestInProcessAdapterFrontendApis`, which already creates
a product adapter and session in `setUp()`:

```python
def test_session_starts_with_explicit_empty_workflow_state(self):
    self.assertEqual(self.snapshot["workflow_state"], "")
```

- [ ] **Step 2: Run the new tests and confirm old defaults fail**

Run:

```powershell
uv run pytest tests/test_agent_app_protocol.py tests/test_inprocess_adapter_frontend_api.py -k "workflow_state" -v
```

Expected: at least the Protocol default and generic session expectation FAIL
with `chat`.

- [ ] **Step 3: Replace generic defaults with explicit definition/state values**

Make `SessionSnapshot.workflow_state` default to an empty string. In
`InProcessAdapter`, use the selected runtime definition for new sessions and
preserve managed state thereafter:

```python
def _workflow_state_for_session(self, session_id: str) -> str:
    with self._lock:
        state = self._sessions.get(session_id)
    if state is None:
        return str(self.runtime_definition.workflow_state or "")
    with state.lock:
        return str(state.workflow_state or "")
```

New and resumed session construction must use:

```python
workflow_state=str(self.runtime_definition.workflow_state or "")
```

Do not reset a non-plan state to `chat` before a turn. Change generic context
and C++ extension method defaults from `"chat"` to `""`; keep the C++ package's
explicit `plan` discipline behavior.

- [ ] **Step 4: Add an architecture guard for generic default state**

Add to `test_current_architecture_boundaries.py`:

```python
def test_generic_layers_do_not_default_workflow_state_to_chat():
    paths = [
        ROOT / "packages/embedagent-protocol/src/embedagent_protocol/__init__.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/context.py",
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert 'workflow_state: str = "chat"' not in source
        assert 'workflow_state or "chat"' not in source
```

- [ ] **Step 5: Run workflow, Host, and Protocol gates**

```powershell
uv run pytest tests/test_agent_app_protocol.py tests/test_inprocess_adapter_frontend_api.py tests/test_workflow_extensions.py tests/test_cpp_workflow_distribution.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS with empty generic state and unchanged C/C++ task/discipline
behavior.

- [ ] **Step 6: Commit empty-state preservation**

```powershell
git add packages/embedagent-protocol/src/embedagent_protocol/__init__.py packages/embedagent-host/src/embedagent_host/inprocess_adapter.py packages/embedagent-host/src/embedagent_host/runtime/context.py packages/embedagent-host/src/embedagent_host/runtime/services/session_lifecycle.py packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py tests/test_agent_app_protocol.py tests/test_inprocess_adapter_frontend_api.py tests/test_current_architecture_boundaries.py
git commit -m "refactor: preserve explicit workflow state"
```

## Phase 7C.2: Hosted Session Contract

### Task 3: Replace Private `AgentSession._host_*` Methods

**Files:**
- Create: `packages/embedagent-core/src/embedagent_core/hosting.py`
- Modify: `packages/embedagent-core/src/embedagent_core/api.py`
- Modify: `packages/embedagent-core/src/embedagent_core/runner.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_command_service.py`
- Modify: `tests/test_agent_core_public_api.py`
- Modify: `tests/test_host_agent_facade.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_session_truth_boundaries.py`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Add public-root and private-access failure tests**

Add to `test_agent_core_public_api.py`:

```python
def test_hosting_controller_is_not_exported_from_core_root():
    import embedagent_core

    assert not hasattr(embedagent_core, "HostedSessionController")
```

Add to the architecture guards:

```python
def test_host_does_not_call_private_agent_session_methods():
    host_root = ROOT / "packages/embedagent-host/src/embedagent_host"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in host_root.rglob("*.py")
    )
    assert "._host_" not in source
```

- [ ] **Step 2: Run the private-access guard and confirm failure**

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py -k "private_agent_session" -v
```

Expected: FAIL on `inprocess_adapter.py` and `hosted_command_service.py`.

- [ ] **Step 3: Create the supported non-root hosting controller**

Create `embedagent_core/hosting.py` with a controller that is constructed from
an `AgentSession` inside the Core package and exposes explicit methods. Use
typed parameters for session/mode/command records and one callback dictionary
only at the existing QueryEngine callback boundary:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from embedagent_core.api import AgentSession
from embedagent_core.session import Action, Session


@dataclass(frozen=True)
class HostedCommandRecord:
    user_text: str
    command_name: str
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0


@dataclass(frozen=True)
class HostedCommandTurn:
    arguments: Dict[str, Any]


@dataclass(frozen=True)
class HostedCommandResume:
    arguments: Dict[str, Any]


class HostedSessionController(object):
    def __init__(self, agent_session: AgentSession) -> None:
        if not isinstance(agent_session, AgentSession):
            raise TypeError("agent_session must be AgentSession")
        self._runtime = agent_session._runtime
        self.session_id = agent_session.session_id

    def initialize(self, session: Session, mode: str, workflow_state: str) -> str:
        return self._runtime.host_initialize_session(
            self.session_id, session, mode, workflow_state
        )

    def apply_mode(self, session: Session, mode: str, workflow_state: str) -> str:
        return self._runtime.host_apply_mode(
            self.session_id, session, mode, workflow_state
        )

    def record_command_result(self, session: Session, record: HostedCommandRecord) -> None:
        self._runtime.host_record_command_result(
            self.session_id,
            session,
            user_text=record.user_text,
            command_name=record.command_name,
            success=record.success,
            message=record.message,
            data=dict(record.data),
            turn_id=record.turn_id,
            step_id=record.step_id,
            step_index=record.step_index,
        )

    def submit_command(self, request: HostedCommandTurn) -> Any:
        return self._runtime.host_submit_command_turn(
            self.session_id, **dict(request.arguments)
        )

    def resume_command_interaction(self, request: HostedCommandResume) -> Any:
        return self._runtime.host_resume_command_interaction(
            self.session_id, **dict(request.arguments)
        )
```

The two callback-heavy methods remain internal supported hosting operations;
do not export this module from `embedagent_core/__init__.py`.

- [ ] **Step 4: Store the controller beside every managed AgentSession**

Add a separate field to `ManagedSession`:

```python
agent_session: Any = None
hosted_session: Any = None
```

At both create and resume sites, bind it immediately after opening the public
session:

```python
from embedagent_core.hosting import HostedSessionController

agent_session = self.agent.open(session.session_id)
state.agent_session = agent_session
state.hosted_session = HostedSessionController(agent_session)
```

Replace all five Host `_host_*` calls with the corresponding
`state.hosted_session` method and construct `HostedCommandTurn` /
`HostedCommandResume` at the two callback-heavy call sites. Replace the monkeypatch in
`test_inprocess_adapter_frontend_api.py` so it patches
`resume_command_interaction` on the hosted controller.

- [ ] **Step 5: Delete private methods from `AgentSession`**

Remove `_host_initialize_session`, `_host_apply_mode`,
`_host_record_command_result`, `_host_submit_command_turn`, and
`_host_resume_command_interaction` from `api.py`. Keep the runtime hosting
methods in `runner.py` as the implementation behind the supported controller;
they are not a Host import surface.

- [ ] **Step 6: Run facade, command, interaction, and truth tests**

```powershell
uv run pytest tests/test_agent_core_public_api.py tests/test_host_agent_facade.py tests/test_inprocess_adapter_frontend_api.py tests/test_session_truth_boundaries.py tests/test_pre_release_architecture_guards.py -v
```

Expected: PASS; hosted command/resume transcript order is unchanged and Host
contains no private AgentSession call.

- [ ] **Step 7: Commit the supported hosting contract**

```powershell
git add packages/embedagent-core/src/embedagent_core/hosting.py packages/embedagent-core/src/embedagent_core/api.py packages/embedagent-core/src/embedagent_core/runner.py packages/embedagent-host/src/embedagent_host/runtime/session_runtime.py packages/embedagent-host/src/embedagent_host/inprocess_adapter.py packages/embedagent-host/src/embedagent_host/hosted_command_service.py tests/test_agent_core_public_api.py tests/test_host_agent_facade.py tests/test_inprocess_adapter_frontend_api.py tests/test_session_truth_boundaries.py tests/test_pre_release_architecture_guards.py
git commit -m "refactor: add explicit hosted session contract"
```

## Phase 7C.3: Runtime Ownership Slimming

### Task 4: Move Turn State, Restore Policy, And Permission Memory To Focused Owners

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/api.py`
- Modify: `packages/embedagent-core/src/embedagent_core/ports.py`
- Modify: `packages/embedagent-core/src/embedagent_core/permissions.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py`
- Modify: `packages/embedagent-core/src/embedagent_core/runner.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Create: `packages/embedagent-host/src/embedagent_host/runtime/session_restore_policy.py`
- Modify: `tests/test_agent_core_public_api.py`
- Modify: `tests/test_permissions.py`
- Modify: `tests/test_host_agent_facade.py`

- [ ] **Step 1: Add tests for explicit workflow state and focused restore policy**

Add `import dataclasses` near the test module imports, then add:

```python
class RecordingContext(NoopContextAssembler):
    def __init__(self):
        self.workflow_states = []

    def build_messages(
        self,
        session,
        mode_name,
        tools=None,
        workflow_state="",
        intelligence_broker=None,
        force_compact=False,
    ):
        self.workflow_states.append(workflow_state)
        return super(RecordingContext, self).build_messages(
            session,
            mode_name,
            tools=tools,
            workflow_state=workflow_state,
            intelligence_broker=intelligence_broker,
            force_compact=force_compact,
        )


def test_user_turn_carries_explicit_workflow_state(base_ports):
    context = RecordingContext()
    ports = dataclasses.replace(base_ports, context=context)
    Agent.create(ports).open("session-workflow").submit(
        UserTurn("hello", workflow_state="custom", stream=False)
    )
    assert context.workflow_states == ["custom"]


def test_runtime_definition_owns_optional_turn_fuse():
    definition = RuntimeDefinition(max_turns=3)
    assert definition.max_turns == 3
```

Add a restore policy fake and assert `run_agent` requests the trusted event
count through it rather than an `AgentRuntimeServices` callback.

- [ ] **Step 2: Add explicit fields and focused port**

Update the frozen input/definition records:

```python
@dataclass(frozen=True)
class UserTurn:
    text: str
    mode: str = ""
    stream: bool = True
    workflow_state: str = ""


@dataclass(frozen=True)
class InteractionReply:
    interaction_id: str
    value: Dict[str, Any]
    stream: bool = True
    workflow_state: str = ""


@dataclass(frozen=True)
class RuntimeDefinition:
    agent_id: str = "embedagent.base"
    default_mode: str = ""
    workflow_state: str = ""
    max_turns: Optional[int] = None
    # retain the existing policy and extension fields unchanged
```

Add to `ports.py`:

```python
class SessionRestorePolicyPort(Protocol):
    def trusted_event_count(self, session_id: str) -> int:
        raise NotImplementedError


class StrictSessionRestorePolicy(object):
    def trusted_event_count(self, session_id: str) -> int:
        del session_id
        return 0
```

Add `restore_policy: Optional[SessionRestorePolicyPort] = None` to `AgentPorts`.

- [ ] **Step 3: Make PermissionPolicy own remembered-category lookup**

Add an optional provider to `PermissionPolicy` and a safe accessor:

```python
def set_remembered_categories_provider(self, provider: Any) -> None:
    self._remembered_categories_provider = provider

def remembered_categories_for(self, session: Session) -> List[str]:
    provider = self._remembered_categories_provider
    if not callable(provider):
        return []
    return sorted(set(str(item) for item in (provider(session) or []) if str(item)))
```

Change `AgentToolActionService` to call
`permission_policy.remembered_categories_for(session)` and remove its separate
provider constructor argument.

- [ ] **Step 4: Consume explicit state and focused owners in the runner**

Use:

```python
workflow_state = str(
    getattr(input_value, "workflow_state", "")
    or runtime.definition.workflow_state
    or ""
)
```

Use `runtime.definition.max_turns` when constructing `QueryEngine`. Obtain the
best-effort trusted prefix from `ports.restore_policy` or
`StrictSessionRestorePolicy`; delete runtime service lookups for all three
values.

Create `ManagedSessionRestorePolicy` in Host with a constructor accepting the
managed-session lookup callback. Its `trusted_event_count(session_id)` returns
the locked `best_effort_restore_event_count` or zero when the session is not
managed. In Host, pass the managed workflow state into both `UserTurn` and
`InteractionReply`, configure the permission provider on the selected policy,
and bind this restore policy through `AgentPorts`.

- [ ] **Step 5: Run Core, permission, restore, and hosted facade tests**

```powershell
uv run pytest tests/test_agent_core_public_api.py tests/test_permissions.py tests/test_recovery_state.py tests/test_host_agent_facade.py tests/test_inprocess_adapter_frontend_api.py -v
```

Expected: PASS with explicit turn workflow state and no workflow/permission/
restore callbacks left in `AgentRuntimeServices`.

- [ ] **Step 6: Commit focused state ownership**

```powershell
git add packages/embedagent-core/src/embedagent_core/api.py packages/embedagent-core/src/embedagent_core/ports.py packages/embedagent-core/src/embedagent_core/permissions.py packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py packages/embedagent-core/src/embedagent_core/runner.py packages/embedagent-host/src/embedagent_host/inprocess_adapter.py packages/embedagent-host/src/embedagent_host/runtime/session_restore_policy.py tests/test_agent_core_public_api.py tests/test_permissions.py tests/test_host_agent_facade.py
git commit -m "refactor: move turn policy to focused core owners"
```

### Task 5: Replace Hosted Runtime Service Bag With Context, Projection, And Tool Ports

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/ports.py`
- Modify: `packages/embedagent-core/src/embedagent_core/tool_contracts.py`
- Modify: `packages/embedagent-core/src/embedagent_core/query_engine.py`
- Modify: `packages/embedagent-core/src/embedagent_core/runner.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/context.py`
- Create: `packages/embedagent-host/src/embedagent_host/runtime/session_maintenance.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Create: `packages/embedagent-host/src/embedagent_host/runtime/session_restore_policy.py`
- Modify: `tests/test_agent_core_public_api.py`
- Modify: `tests/test_query_engine_refactor.py`
- Modify: `tests/test_tool_commit.py`
- Modify: `tests/test_workspace_profile.py`

- [ ] **Step 1: Add focused-port behavior tests**

Add a `RecordingSessionProjection` fake and verify one refresh per completed
turn:

```python
class RecordingSessionProjection(object):
    def __init__(self):
        self.calls = []

    def refresh(self, session, current_mode, assembly=None):
        self.calls.append((session.session_id, current_mode, assembly))


def test_agent_uses_focused_session_projection(base_ports):
    projection = RecordingSessionProjection()
    ports = dataclasses.replace(base_ports, session_projection=projection)
    Agent.create(ports).open("projection-session").submit(
        UserTurn("hello", stream=False)
    )
    assert projection.calls
```

Add tool commit coverage proving the runtime receives the session log and
returns the committed observation.

- [ ] **Step 2: Add the focused Core contracts**

Add to `ports.py`:

```python
class SessionProjectionPort(Protocol):
    def refresh(
        self,
        session: Session,
        current_mode: str,
        assembly: Optional[ContextAssemblyResult] = None,
    ) -> None:
        raise NotImplementedError


class NoopSessionProjection(object):
    def refresh(self, session, current_mode, assembly=None):
        del session, current_mode, assembly
```

Extend `ContextAssemblerPort` and `NoopContextAssembler`:

```python
def initial_system_messages(
    self, session: Session, mode_name: str, workflow_state: str = ""
) -> List[str]:
    return []
```

Extend `ToolRuntimePort`:

```python
def commit_observation(
    self,
    session_log: SessionLogPort,
    session: Session,
    action: Action,
    observation: Observation,
    current_mode: str,
    turn_id: str = "",
    step_id: str = "",
    message_id: str = "",
    parent_message_id: str = "",
    finished_at: str = "",
) -> Observation:
    raise NotImplementedError
```

Add `session_projection: Optional[SessionProjectionPort] = None` to
`AgentPorts`.

- [ ] **Step 3: Move concrete hosted behavior behind those ports**

Make Host `ContextManager` own its `WorkspaceIntelligenceBroker` and workspace
profile provider. Its `initial_system_messages()` returns only non-empty profile
messages. Remove `intelligence_broker` from `build_messages()` parameters.

Create `HostedSessionMaintenance`:

```python
import logging


_LOG = logging.getLogger(__name__)


class HostedSessionMaintenance(object):
    def __init__(
        self,
        summary_store,
        project_memory_store,
        memory_maintenance,
        maintenance_interval=4,
    ):
        self.summary_store = summary_store
        self.project_memory_store = project_memory_store
        self.memory_maintenance = memory_maintenance
        self.maintenance_interval = max(1, int(maintenance_interval or 1))
        self._counter = 0

    def refresh(self, session, current_mode, assembly=None):
        summary_ref = None
        try:
            summary_ref = self.summary_store.persist(session, current_mode, assembly)
        except (OSError, TypeError, ValueError) as exc:
            _LOG.warning("session summary persist failed: %s", exc)
        try:
            self.project_memory_store.refresh(session, current_mode, summary_ref)
        except (OSError, TypeError, ValueError) as exc:
            _LOG.warning("project memory refresh failed: %s", exc)
        self._counter += 1
        if self._counter < self.maintenance_interval:
            return
        self._counter = 0
        try:
            self.memory_maintenance.run()
        except (RuntimeError, TypeError, ValueError) as exc:
            _LOG.warning("memory maintenance failed: %s", exc)
```

Implement `ToolRuntime.commit_observation()` by delegating to a
`ToolCommitCoordinator` constructed from the runtime's tool-result store,
projection database, and the supplied `SessionLogPort`. Keep the existing
fallback-to-in-memory observation behavior in Core when the commit raises.

- [ ] **Step 4: Simplify QueryEngine and AgentRuntime construction**

Replace summary/project/maintenance/intelligence/tool-commit/workspace-profile
constructor arguments with:

```python
session_projection: Optional[SessionProjectionPort] = None
```

Use `context_manager.initial_system_messages()` during initialization,
`tools.commit_observation()` during tool completion, and
`session_projection.refresh()` after state changes. Keep session trimming in
Core. Remove `_maybe_maintain_memory`, its counter, and all displaced no-op
classes from `ports.py`.

In `InProcessAdapter._build_agent()`, bind:

```python
ports = AgentPorts(
    model=self.client,
    tools=self.tools,
    session_log=self.transcript_store,
    context=self.context_manager,
    permissions=self.permission_policy,
    restore_policy=self.restore_policy,
    session_projection=self.session_maintenance,
    extension_manager=self.extension_manager,
)
```

- [ ] **Step 5: Run Core, context, tool commit, memory, and Host tests**

```powershell
uv run pytest tests/test_agent_core_public_api.py tests/test_query_engine_refactor.py tests/test_tool_commit.py tests/test_workspace_profile.py tests/test_project_memory.py tests/test_inprocess_adapter_frontend_api.py -v
```

Expected: PASS and the Host concrete services are reached only through the
three focused ports.

- [ ] **Step 6: Commit focused runtime services**

```powershell
git add packages/embedagent-core/src/embedagent_core/ports.py packages/embedagent-core/src/embedagent_core/tool_contracts.py packages/embedagent-core/src/embedagent_core/query_engine.py packages/embedagent-core/src/embedagent_core/runner.py packages/embedagent-host/src/embedagent_host/runtime/context.py packages/embedagent-host/src/embedagent_host/runtime/session_maintenance.py packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py packages/embedagent-host/src/embedagent_host/inprocess_adapter.py tests/test_agent_core_public_api.py tests/test_query_engine_refactor.py tests/test_tool_commit.py tests/test_workspace_profile.py
git commit -m "refactor: replace runtime service bag with focused ports"
```

### Task 6: Delete `AgentRuntimeServices` And Lock Coordinator Responsibilities

**Files:**
- Modify: `packages/embedagent-core/src/embedagent_core/api.py`
- Modify: `packages/embedagent-core/src/embedagent_core/runner.py`
- Modify: `packages/embedagent-core/src/embedagent_core/query_engine.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `tests/query_engine_product_helpers.py`
- Modify: `tests/test_agent_core_public_api.py`
- Modify: `tests/test_current_architecture_boundaries.py`

- [ ] **Step 1: Add deletion and ownership guards**

```python
def test_runtime_service_bag_is_deleted():
    core_root = ROOT / "packages/embedagent-core/src/embedagent_core"
    source = "\n".join(path.read_text(encoding="utf-8") for path in core_root.rglob("*.py"))
    assert "AgentRuntimeServices" not in source


def test_query_engine_has_no_hosted_service_constructor_parameters():
    source = (
        ROOT / "packages/embedagent-core/src/embedagent_core/query_engine.py"
    ).read_text(encoding="utf-8")
    for name in (
        "summary_store",
        "project_memory_store",
        "memory_maintenance",
        "intelligence_broker",
        "tool_commit",
        "workspace_profile",
    ):
        assert name not in source.split("def __init__", 1)[1].split(") -> None", 1)[0]
```

- [ ] **Step 2: Run guards and confirm the remaining bag fails**

```powershell
uv run pytest tests/test_current_architecture_boundaries.py -k "runtime_service_bag or hosted_service_constructor" -v
```

Expected: FAIL until the class and final constructor wiring are deleted.

- [ ] **Step 3: Delete the bag and remaining forwarding code**

Remove `AgentRuntimeServices`, the `AgentPorts.runtime_services` field,
`AgentRuntime._services()`, adapter pass-through keys for retired services, and
test helper construction of the bag. Do not add an alias. Update tests to pass
focused ports directly.

Inspect `QueryEngine` and `InProcessAdapter` method lists and delete wrappers
whose only body delegates to a promoted service. Keep methods only when they
enforce an adapter-owned lock, event, lifecycle, or application-selection rule.

- [ ] **Step 4: Run architecture and non-GUI regression gates**

```powershell
uv run pytest tests/test_agent_core_public_api.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py tests/test_current_architecture_boundaries.py tests/test_pre_release_architecture_guards.py -v
```

Expected: PASS with no production occurrence of `AgentRuntimeServices`.

- [ ] **Step 5: Commit service-bag deletion**

```powershell
git add packages/embedagent-core/src/embedagent_core/api.py packages/embedagent-core/src/embedagent_core/runner.py packages/embedagent-core/src/embedagent_core/query_engine.py packages/embedagent-host/src/embedagent_host/inprocess_adapter.py src/embedagent/core/adapter.py tests/query_engine_product_helpers.py tests/test_agent_core_public_api.py tests/test_current_architecture_boundaries.py
git commit -m "refactor: delete hosted runtime service bag"
```

## Phase 7C.4: Canonical Event Path

### Task 7: Define The Protocol Session Event Envelope And Host Encoder

**Files:**
- Create: `packages/embedagent-protocol/src/embedagent_protocol/session_events.py`
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Create: `packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_command_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted/session_host.py`
- Create: `tests/test_session_event_protocol.py`
- Modify: `tests/test_protocol_versions.py`

- [ ] **Step 1: Add failing serialization and sequencing tests**

Create `tests/test_session_event_protocol.py` with tests for round-trip JSON
safety, monotonic per-session sequence, and structured failure:

```python
def test_session_event_envelope_is_json_safe():
    envelope = SessionEventEnvelope(
        schema_version=1,
        event_id="evt-1",
        session_id="s-1",
        sequence=1,
        event_kind="tool.finished",
        timestamp="2026-07-26T00:00:00Z",
        payload={"failure": FailureRecord("path_missing", "missing", False, "tool").to_dict()},
    )
    encoded = envelope.to_dict()
    json.dumps(encoded)
    assert SessionEventEnvelope.from_dict(encoded).to_dict() == encoded


def test_host_encoder_sequences_each_session_independently():
    encoder = SessionEventEncoder()
    first = encoder.encode("s-1", "turn_start", {})
    second = encoder.encode("s-1", "turn_end", {})
    other = encoder.encode("s-2", "turn_start", {})
    assert [first.sequence, second.sequence, other.sequence] == [1, 2, 1]
```

- [ ] **Step 2: Run and confirm missing modules fail**

```powershell
uv run pytest tests/test_session_event_protocol.py -v
```

Expected: collection FAIL because the Protocol DTO and Host encoder do not
exist.

- [ ] **Step 3: Implement the JSON-safe Protocol records**

Create immutable `FailureRecord` and `SessionEventEnvelope` dataclasses. Validate
positive schema/sequence, non-empty identity/kind, mapping payloads, and preserve
the canonical wire names exactly:

```python
return {
    "schema_version": self.schema_version,
    "event_id": self.event_id,
    "session_id": self.session_id,
    "sequence": self.sequence,
    "event_kind": self.event_kind,
    "timestamp": self.timestamp,
    "payload": deepcopy(self.payload),
}
```

Export these two records from `embedagent_protocol`, because they are the wire
contract rather than a Core SDK type.

- [ ] **Step 4: Implement the single Host encoder**

Move the event-name mapping currently in GUI `session_events.py` into
`SessionEventEncoder`. The encoder owns its per-session sequence map and
generates event ids/timestamps. Normalize interaction request ids here, because
this is the one Core/Host-to-Protocol mapping point.

Define and use one Host handler alias:

```python
SessionEventHandler = Callable[[SessionEventEnvelope], None]
```

Delete the parallel `EventHandler` aliases from `InProcessAdapter`,
`HostedCommandService`, `HostedInteractionService`, and
`HostedSessionHost`; import `SessionEventHandler` from the encoder module.

`EventEmitter.emit()` encodes once and sends the same envelope object to every
handler. `emit_with_snapshot()` adds the snapshot before encoding.

- [ ] **Step 5: Run Protocol, Host event, and version tests**

```powershell
uv run pytest tests/test_session_event_protocol.py tests/test_gui_session_events.py tests/test_protocol_versions.py tests/test_protocol_package_imports.py tests/test_host_distribution_imports.py tests/test_hosted_runtime.py tests/test_inprocess_adapter_frontend_api.py -v
```

Expected: PASS; Host imports Protocol but Protocol remains dependency-free.

- [ ] **Step 6: Commit the canonical envelope and encoder**

```powershell
git add packages/embedagent-protocol/src/embedagent_protocol/session_events.py packages/embedagent-protocol/src/embedagent_protocol/__init__.py packages/embedagent-host/src/embedagent_host/runtime/session_event_protocol.py packages/embedagent-host/src/embedagent_host/runtime/services/event_emitter.py packages/embedagent-host/src/embedagent_host/inprocess_adapter.py packages/embedagent-host/src/embedagent_host/hosted_command_service.py packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py packages/embedagent-host/src/embedagent_host/hosted/session_host.py tests/test_session_event_protocol.py tests/test_protocol_versions.py
git commit -m "feat: define canonical hosted session events"
```

### Task 8: Remove Python Event Reshaping And Forward Envelopes Unchanged

**Files:**
- Modify: `packages/embedagent-protocol/src/embedagent_protocol/__init__.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/tui/frontend_adapter.py`
- Delete: `src/embedagent/frontend/gui/backend/session_events.py`
- Modify: `tests/test_gui_session_events.py`
- Modify: `tests/test_tui_activity_timeline.py`
- Modify: `tests/test_tui_timeline_activities.py`
- Modify: `tests/test_gui_protocol_projection.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Replace callback-shape tests with envelope-forwarding tests**

Add a frontend fake exposing one callback:

```python
class RecordingFrontend(object):
    def __init__(self):
        self.events = []

    def on_session_event(self, envelope):
        self.events.append(envelope)
```

Assert product and GUI layers preserve object fields without defaults:

```python
assert frontend.events[0].to_dict() == envelope.to_dict()
assert websocket_message == {"type": "session_event", "data": envelope.to_dict()}
```

- [ ] **Step 2: Run projection tests and confirm the old callback API fails them**

```powershell
uv run pytest tests/test_gui_session_events.py tests/test_gui_protocol_projection.py -v
```

Expected: FAIL because `CallbackBridge` and GUI backend still construct
`ToolCall`, `ToolResult`, and a second session-event shape.

- [ ] **Step 3: Collapse the Python callback surface**

Replace event-oriented methods on `FrontendCallbacks` with:

```python
def on_session_event(self, envelope: SessionEventEnvelope) -> None:
    ...
```

Keep request/response methods on `CoreInterface`; they are not event callbacks.
Delete `CallbackBridge`. Make `AgentCoreAdapter._on_adapter_event()` call the
single frontend method with the already encoded envelope.

Make `WebSocketFrontend.on_session_event()` dispatch exactly:

```python
self._dispatch_message({"type": "session_event", "data": envelope.to_dict()})
```

Replace the TUI's parallel callback methods with one
`TUIFrontend.on_session_event()` switch over `envelope.event_kind`. Reuse the
existing TUI reducer and observation formatter, but read only the canonical
payload and structured failure record.

Delete backend sequence completion, event-name mapping, interaction payload
normalization, tool metadata extraction, and `session_events.py`.

- [ ] **Step 4: Ensure failures use one structured payload**

At the Host event encoder, derive `failure` only from the existing failed
observation:

```python
if event_kind == "tool.finished" and not bool(payload.get("success")):
    data = dict(payload.get("data") or {})
    payload["failure"] = FailureRecord(
        code=str(data.get("error_kind") or "tool_failed"),
        message=str(payload.get("error") or ""),
        retryable=bool(data.get("retryable")),
        source=str(payload.get("tool_name") or "tool"),
    ).to_dict()
```

Do not emit a standalone message/error callback for the same failure.

- [ ] **Step 5: Run hosted, GUI protocol, interaction, and diff tests**

```powershell
uv run pytest tests/test_inprocess_adapter_frontend_api.py tests/test_gui_session_events.py tests/test_gui_protocol_projection.py tests/test_session_event_protocol.py tests/test_session_truth_boundaries.py tests/test_tui_activity_timeline.py tests/test_tui_timeline_activities.py -v
```

Expected: PASS with one Python event DTO and no backend event builder.

- [ ] **Step 6: Commit Python event-path convergence**

```powershell
git add packages/embedagent-protocol/src/embedagent_protocol/__init__.py packages/embedagent-host/src/embedagent_host/inprocess_adapter.py src/embedagent/core/adapter.py src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/tui/frontend_adapter.py tests/test_gui_session_events.py tests/test_gui_protocol_projection.py tests/test_inprocess_adapter_frontend_api.py tests/test_tui_activity_timeline.py tests/test_tui_timeline_activities.py
git rm src/embedagent/frontend/gui/backend/session_events.py
git commit -m "refactor: forward protocol session events unchanged"
```

### Task 9: Make The Renderer Consume Only Canonical Session Events

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `tests/test_pre_release_architecture_guards.py`
- Rebuild: `src/embedagent/frontend/gui/static/`

- [ ] **Step 1: Add JavaScript tests for canonical event ordering and failure**

Add fixtures containing `turn.started`, `tool.started`, failed `tool.finished`,
interaction request/resolution, and `session.finished`. Assert:

```javascript
assert.equal(transport.lastAppliedSeq, 6);
assert.equal(toolRow.status, "failed");
assert.equal(toolRow.failure.code, "path_missing");
assert.equal(pendingInteraction, null);
assert.equal(diffSummary.additions, 2);
assert.equal(diffSummary.deletions, 1);
```

Add a source assertion that legacy socket branches are absent:

```javascript
for (const legacyType of ["tool_start", "tool_finish", "command_result"]) {
  assert.equal(socketSource.includes(`type === "${legacyType}"`), false);
}
```

- [ ] **Step 2: Run GUI tests and confirm legacy-path assertions fail**

```powershell
npm test
```

Run from `src/embedagent/frontend/gui/webapp`.

Expected: FAIL while `socket-message-effects.js` still handles parallel
`tool_start`, `tool_finish`, and `command_result` messages.

- [ ] **Step 3: Route all Agent activity through `session_event`**

Keep app-shell/non-session transport messages unchanged. For session activity,
validate the envelope once through `applySessionTransportEvent()`, then map
`event_kind` to one activity reducer action. Read failure, diff, interaction,
tool presentation, and command payloads directly from `envelope.payload`.

Delete the legacy branches and their fallback activity construction. Do not
infer tool request kind, changed path, or visible copy from tool names.

- [ ] **Step 4: Add a Python source guard for one renderer event path**

```python
def test_renderer_has_one_agent_event_transport_path():
    source = (
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    ).read_text(encoding="utf-8")
    assert 'type === "session_event"' in source
    for legacy in ('type === "tool_start"', 'type === "tool_finish"'):
        assert legacy not in source
```

- [ ] **Step 5: Run tests and rebuild committed static assets**

```powershell
npm test
npm run build
```

Then from the repository root:

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_gui_runtime.py tests/test_gui_protocol_projection.py -v
```

Expected: all commands PASS and generated static assets reflect the new event
path.

- [ ] **Step 6: Commit renderer convergence and generated assets**

```powershell
git add src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static tests/test_pre_release_architecture_guards.py
git commit -m "refactor: consume canonical session events in gui"
```

## Phase 7C.5: Redundancy Retirement

### Task 10: Delete Dead Tooling And Consolidate Profile Policy

**Files:**
- Delete: `src/embedagent/tooling/contracts.py`
- Delete: `src/embedagent/tooling/result_budget.py`
- Delete: `src/embedagent/tooling/__init__.py`
- Delete: `src/embedagent/workflow_packages/__init__.py`
- Delete: `tests/test_tooling_budget_v2.py`
- Modify: `packages/embedagent-core/src/embedagent_core/profile_runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/profiles.py`
- Modify: `packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/profile.py`
- Modify: `tests/test_agent_profiles.py`
- Modify: `tests/test_current_architecture_boundaries.py`
- Modify: `docs/modules/tools-and-tooling.md`

- [ ] **Step 1: Reconfirm deletion evidence before editing**

Run:

```powershell
rg -n "ToolSpecV2|apply_aggregate_budget|embedagent\.workflow_packages" src packages tests --glob "*.py"
```

Expected: only the three tooling modules, `tests/test_tooling_budget_v2.py`, and
architecture guards reference the candidates. If a new production consumer is
present, stop this task and move that behavior to its official owner before
deletion.

- [ ] **Step 2: Add guards for retired imports and neutral Core prompt copy**

```python
def test_retired_product_tooling_modules_do_not_exist():
    retired = (
        "src/embedagent/tooling/contracts.py",
        "src/embedagent/tooling/result_budget.py",
        "src/embedagent/tooling/__init__.py",
        "src/embedagent/workflow_packages/__init__.py",
    )
    for relative_path in retired:
        assert not (ROOT / relative_path).is_file()


def test_core_profile_prompt_is_product_neutral():
    source = (
        ROOT / "packages/embedagent-core/src/embedagent_core/profile_runtime.py"
    ).read_text(encoding="utf-8")
    assert "EmbedAgent" not in source
    assert "优先用中文" not in source
```

- [ ] **Step 3: Consolidate neutral profile constants in Core**

Retain workflow-neutral base tool and spec-write constants in
`profile_runtime.py`, because mode allowed-tools are a Core runtime contract.
Replace the branded prompt frame with neutral language:

```python
PROFILE_PROMPT_FRAME = (
    "You are operating under an explicit agent mode. Follow the current mode "
    "boundary and answer in the user's language. Mode selection does not grant "
    "permissions; runtime permission and write-path policies remain authoritative.\n\n"
    "Current mode: {mode_name}\n"
    "Mode description: {mode_description}\n"
    "User confirmation: {ask_rule}\n"
    "Writable paths: {writable_globs}"
)
```

Delete duplicate `BASE_*` and `SPEC_WRITABLE_GLOBS` definitions from Host
profiles and import the neutral constants from Core. Keep Python/HTML and C/C++
domain-specific globs in their owning Host/workflow modules.

- [ ] **Step 4: Delete dead modules, test, and namespace**

```powershell
git rm src/embedagent/tooling/contracts.py src/embedagent/tooling/result_budget.py src/embedagent/tooling/__init__.py src/embedagent/workflow_packages/__init__.py tests/test_tooling_budget_v2.py
```

Remove the retired test from module documentation and replace it with the
active tool runtime/commit tests.

- [ ] **Step 5: Run profile, tool, package, and architecture tests**

```powershell
uv run pytest tests/test_agent_profiles.py tests/test_tools_package.py tests/test_tools_v2_runtime.py tests/test_cpp_workflow_distribution.py tests/test_current_architecture_boundaries.py tests/test_python_distribution_contract.py -v
```

Expected: PASS; Core prompt has no product branding, profiles share one neutral
constant set, and deleted modules are absent from package manifests.

- [ ] **Step 6: Commit redundancy retirement**

```powershell
git add packages/embedagent-core/src/embedagent_core/profile_runtime.py packages/embedagent-host/src/embedagent_host/runtime/profiles.py packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/profile.py tests/test_agent_profiles.py tests/test_current_architecture_boundaries.py docs/modules/tools-and-tooling.md
git commit -m "refactor: retire duplicate profile and tooling paths"
```

## Phase 7C.6: Governance Closure

### Task 11: Strengthen Core-Only Smoke And Synchronize Active Documentation

**Files:**
- Modify: `scripts/smoke-python-distributions.py`
- Modify: `tests/test_python_distribution_smoke.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: `docs/pre-release-architecture-debt-audit.md`
- Modify: `docs/modules/agent-core.md`
- Modify: `docs/modules/harness.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Add a smoke-script test requiring an executed Core turn**

In `test_python_distribution_smoke.py`, parse the `core_only` probe and assert it
contains all of:

```python
assert "AgentPorts(" in probe
assert "InMemorySessionLog" in probe
assert ".submit(UserTurn(" in probe
assert "result.final_text == 'done'" in probe
```

- [ ] **Step 2: Run the smoke-script test and confirm import-only probe fails**

```powershell
uv run pytest tests/test_python_distribution_smoke.py -v
```

Expected: FAIL because the current core-only probe imports `Agent` but does not
construct or execute it.

- [ ] **Step 3: Replace the core-only probe with a real fake-model turn**

The probe must define a Python 3.8-compatible fake model and no-op tool runtime,
build `AgentPorts` with `InMemorySessionLog`, `NoopContextAssembler`, and
`PermissionPolicy`, submit `UserTurn("hello", stream=False)`, and exit non-zero
unless the final text is `done`. Include `commit_observation()` on the fake tool
runtime if Task 5 made it mandatory.

Keep the existing assertions that Host, Protocol, and product packages are not
installed in the core-only environment.

- [ ] **Step 4: Correct active documentation against the current tree**

Replace references to non-existent workflow package files:

```text
application.py        -> component.py plus src/embedagent/product_catalog.py
application_record.py -> src/embedagent/product_catalog.py
agent_profile.py      -> profile.py
builder_path          -> current AgentApplicationRecord factory/component fields
```

Document `HostedSessionController` as a supported non-root Core/Host boundary,
the focused runtime ports, canonical `SessionEventEnvelope`, removed tooling
namespace, and Phase 7C completion requirements. Keep Phase 8 and Win7 external
acceptance explicitly open.

- [ ] **Step 5: Add documentation path and vocabulary guards**

Extend `test_pre_release_architecture_guards.py` so active documents cannot
mention the removed source paths or `AgentRuntimeServices`, and so they do
mention `SessionEventEnvelope` and the current C++ component/profile paths.

- [ ] **Step 6: Run documentation, smoke, and architecture tests**

```powershell
uv run pytest tests/test_python_distribution_smoke.py tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run --locked python scripts/lint.py
```

Expected: PASS with no stale active-document paths.

- [ ] **Step 7: Commit governance closure**

```powershell
git add scripts/smoke-python-distributions.py tests/test_python_distribution_smoke.py README.md AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/pi-inspired-agent-core-blueprint.md docs/pre-release-architecture-debt-audit.md docs/modules/agent-core.md docs/modules/harness.md docs/frontend-protocol.md docs/development-tracker.md docs/design-change-log.md tests/test_pre_release_architecture_guards.py
git commit -m "docs: close phase 7c architecture convergence"
```

### Task 12: Run Full Gates And Produce Fresh Six-Wheel Evidence

**Files:**
- No source changes expected
- Generated verification directory: `build/phase7c-dist/`

- [ ] **Step 1: Confirm the worktree contains no uncommitted source changes**

```powershell
git status --short
```

Expected: no output. If generated GUI assets are dirty, return to Task 9 and
commit them there.

- [ ] **Step 2: Run the pre-merge architecture gate**

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Expected: all commands exit 0.

- [ ] **Step 3: Run the GUI gate from the webapp directory**

```powershell
npm test
npm run build
```

Expected: both commands exit 0 and the rebuilt static tree remains clean.

- [ ] **Step 4: Build and inspect all six distributions in a fresh directory**

From the repository root:

```powershell
uv run python scripts/build-python-distributions.py --dist-dir build/phase7c-dist
uv run python scripts/check-python-distributions.py --dist-dir build/phase7c-dist
```

Expected: exactly six verified wheels and `"ok": true`.

- [ ] **Step 5: Run isolated wheel smoke under the project Python 3.8 runtime**

```powershell
uv run python scripts/smoke-python-distributions.py --dist-dir build/phase7c-dist --python .venv/Scripts/python.exe
```

Expected: all six scenarios report `"status": "ok"`; `core_only` executes a
fake-model turn without Host, Protocol, workflow, or product installed.

- [ ] **Step 6: Record final evidence without committing build output**

```powershell
git status --short --branch
git log -12 --oneline --decorate
```

Expected: clean worktree. Do not commit `build/phase7c-dist/`.

## Completion Checklist

- [ ] Base tool projection accepts arbitrary workflow-state names.
- [ ] Generic Core, Host, and Protocol do not synthesize `chat`.
- [ ] Host contains no call to `AgentSession._host_*` or another Core private member.
- [ ] `AgentRuntimeServices` and its callback/service bag are deleted.
- [ ] Context, session projection, restore policy, permission memory, and tool result commit have focused owners.
- [ ] Host produces one `SessionEventEnvelope`; Python GUI layers forward it unchanged.
- [ ] Renderer Agent activity enters through one `session_event` branch.
- [ ] Failed tool/edit/command results remain visible to both Agent and GUI through one payload.
- [ ] Dead tooling modules, old workflow namespace, duplicate constants, and obsolete tests are deleted.
- [ ] Active docs reference only current source files and preserve Phase 8/Win7 status.
- [ ] Architecture, non-GUI, lint, GUI, six-wheel inspection, and isolated smoke gates pass.
