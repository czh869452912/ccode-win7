# QueryEngine Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Slice 5 by slimming `QueryEngine`, moving extension hook dispatch into an explicit host boundary, moving tool action execution into a service, and extracting the turn loop while preserving transcript, permission, and default C/C++ harness behavior.

**Architecture:** Add `AgentExtensionHost` as the only QueryEngine-side extension boundary, then add `AgentToolActionService` for non-LLM tool execution, then add `AgentLoop` for turn orchestration. `QueryEngine` remains the session-scoped facade and transcript/session mutation owner while delegating extension, action, and loop responsibilities through narrow interfaces.

**Tech Stack:** Python 3.8, standard library only, existing `ExtensionManager`, `ToolRuntime`, `PermissionPolicy`, `Session`, `TranscriptStore`, pytest.

---

## Scope

Included:

- Extract extension-context/event creation and extension hook dispatch from `QueryEngine`.
- Preserve active tool projection through `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)`.
- Preserve dynamic in-process extension tool registration behavior.
- Preserve extension pre-tool and post-tool hook behavior.
- Preserve extension-owned `task_status` behavior.
- Preserve permission pending/denial behavior.
- Preserve transcript event order and pending interaction shape.
- Extract a small `AgentLoop` wrapper around turn orchestration.
- Add regression tests proving a bare core engine can run without the default C harness extension.
- Update source-of-truth docs and archive-ready slice materials.

Excluded:

- Remote registries or marketplaces.
- Dependency installation.
- New runtime dependencies.
- Multi-agent orchestration.
- Frontend vocabulary changes.
- Replacing `PermissionPolicy`.
- Replacing transcript/session-history storage.

## File Structure

- Create `src/embedagent/agent_extension_host.py`
  - Own extension context construction, workflow event construction, active tool resolution, dynamic tool registration, schema projection, prompt/context hooks, tool-call hooks, tool-result hooks, extension-owned tool execution, and workflow patch application.

- Create `src/embedagent/agent_tool_action_service.py`
  - Own inactive-tool checks, extension pre/post hooks, permission evaluation, path write guard checks, extension-owned tool dispatch, runtime tool execution, and action-result return shape.

- Create `src/embedagent/agent_loop.py`
  - Own the user-turn loop by receiving callbacks from `QueryEngine` for transcript/session mutation and reusing existing loop helpers during the first extraction.

- Modify `src/embedagent/query_engine.py`
  - Instantiate the new components.
  - Keep compatibility wrappers such as `_allowed_tools_for_mode(...)` and `_schemas_for_active_tools(...)`.
  - Replace direct extension-manager hook calls with `AgentExtensionHost`.
  - Delegate `_execute_action(...)` to `AgentToolActionService`.
  - Delegate `_run_loop(...)` to `AgentLoop`.

- Modify `tests/test_dynamic_tool_registration.py`
  - Add direct `AgentExtensionHost` tests for dynamic tool registration and active schema projection.

- Modify `tests/test_capability_extensions.py`
  - Add direct `AgentExtensionHost` tests for context and tool-result workflow patches.

- Modify `tests/test_query_engine_refactor.py`
  - Add direct `AgentToolActionService` and `AgentLoop` regression tests.
  - Add source-level guard tests for `QueryEngine` direct extension-manager hook dispatch.

- Modify `tests/test_workflow_extensions.py`
  - Add or adjust bare-core no-harness tests and shared extension-manager compatibility checks.

- Update docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
  - move completed Slice 5 `docs/superpowers/specs/...` and `docs/superpowers/plans/...` to `docs/archive/self-extensible-agent-core/` after docs sync.

---

## Tasks

### Task 1: Agent Extension Host

**Files:**

- Create: `src/embedagent/agent_extension_host.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_dynamic_tool_registration.py`
- Modify: `tests/test_capability_extensions.py`

- [ ] **Step 1: Write failing tests for direct host behavior**

Add these tests to `tests/test_dynamic_tool_registration.py`:

```python
def test_agent_extension_host_registers_dynamic_tools_and_projects_active_schemas(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.extensions import ExtensionManager
    from embedagent.modes import allowed_tools_for
    from embedagent.permissions import PermissionPolicy
    from embedagent.session import Session
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    session = Session()
    extension = DynamicToolExtension(active=True)
    host = AgentExtensionHost(
        manager=ExtensionManager([extension]),
        tools=runtime,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        mode_allowed_tools=allowed_tools_for,
    )

    host.register_tools(session, "build", "chat", reason="session_start")
    names = set(item["function"]["name"] for item in host.schemas_for_active_tools("build", "chat"))

    assert "dynamic_echo" in names
    assert runtime.tool_catalog_entry("dynamic_echo")["source_id"] == "dynamic_tools"


def test_agent_extension_host_uses_mode_contract_as_active_tool_fallback(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.extensions import ExtensionManager
    from embedagent.modes import allowed_tools_for
    from embedagent.permissions import PermissionPolicy
    from embedagent.session import Session
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    host = AgentExtensionHost(
        manager=ExtensionManager(),
        tools=runtime,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        mode_allowed_tools=allowed_tools_for,
    )

    host.register_tools(Session(), "build", "chat", reason="session_start")
    names = set(item["function"]["name"] for item in host.schemas_for_active_tools("build", "chat"))

    assert "read_file" in names
    assert "write_file" in names
    assert "propose_mode_switch" in names
```

Add this test to `tests/test_capability_extensions.py`:

```python
def test_agent_extension_host_applies_context_and_tool_result_workflow_patch(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.extensions import ContextPatch, ExtensionManager, ToolResultPatch, WorkflowPatch
    from embedagent.permissions import PermissionPolicy
    from embedagent.session import Action, ContextAssemblyResult, Observation, Session
    from embedagent.tools import ToolRuntime

    class ContextAndPatchExtension(object):
        extension_id = "context_and_patch"
        builtin_extension = False

        def context(self, event, context):
            del context
            messages = list(event.messages)
            messages.append({"role": "system", "content": "extension context"})
            return ContextPatch(messages=messages)

        def tool_result(self, event, context):
            del context
            return ToolResultPatch(
                workflow_patch=WorkflowPatch(
                    workflow={"task_summary": {"total": 1}},
                    metadata={"source": "test"},
                )
            )

    session = Session()
    runtime = ToolRuntime(str(tmp_path))
    host = AgentExtensionHost(
        manager=ExtensionManager([ContextAndPatchExtension()]),
        tools=runtime,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
    )
    assembly = ContextAssemblyResult(messages=[{"role": "user", "content": "hello"}])

    patched = host.apply_context_patch(session, "build", "chat", assembly, force_compact=False)
    observation = host.apply_tool_result_patch(
        session,
        Action("read_file", {"path": "a.txt"}, "call-read"),
        "build",
        "chat",
        Observation("read_file", True, None, {"content": "ok"}),
    )

    assert patched.messages[-1]["content"] == "extension context"
    assert observation.success is True
    assert session.workflow_state["workflow"]["task_summary"]["total"] == 1
    assert session.workflow_state["extensions"]["last_workflow_patch"]["source"] == "test"
```

- [ ] **Step 2: Run tests and confirm they fail because the host does not exist**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py::test_agent_extension_host_registers_dynamic_tools_and_projects_active_schemas tests/test_dynamic_tool_registration.py::test_agent_extension_host_uses_mode_contract_as_active_tool_fallback tests/test_capability_extensions.py::test_agent_extension_host_applies_context_and_tool_result_workflow_patch -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'embedagent.agent_extension_host'`.

- [ ] **Step 3: Implement `AgentExtensionHost`**

Create `src/embedagent/agent_extension_host.py` with this implementation skeleton and fill only the shown behavior:

```python
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Set, Tuple

from embedagent.extensions import (
    ExtensionContext,
    ExtensionManager,
    SessionView,
    ToolRegistrationEvent,
    WorkflowEvent,
)
from embedagent.interaction import ask_user_schema, propose_mode_switch_schema
from embedagent.modes import allowed_tools_for
from embedagent.session import Action, ContextAssemblyResult, Observation, Session
from embedagent.tools import ToolRuntime


class AgentExtensionHost(object):
    def __init__(
        self,
        manager: Optional[ExtensionManager],
        tools: ToolRuntime,
        permission_policy: Any,
        mode_allowed_tools: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.manager = manager or ExtensionManager()
        self.tools = tools
        self.permission_policy = permission_policy
        self._mode_allowed_tools = mode_allowed_tools or allowed_tools_for

    def context_for(self, session: Session) -> ExtensionContext:
        runtime_snapshot = {}
        runtime_lookup = getattr(self.tools, "runtime_environment_snapshot", None)
        if callable(runtime_lookup):
            runtime_snapshot = runtime_lookup()
        return ExtensionContext(
            workspace=str(getattr(self.tools, "workspace", "") or ""),
            runtime_environment=dict(runtime_snapshot or {}),
            tool_registry=self.tools,
            permission_policy=self.permission_policy,
            session_view=SessionView.from_session(session),
        )

    def workflow_event(
        self,
        session: Session,
        current_mode: str,
        workflow_state_name: str,
        **metadata: Any
    ) -> WorkflowEvent:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step = session.current_step()
        step_id = step.step_id if step is not None else ""
        return WorkflowEvent(
            session_id=session.session_id,
            turn_id=turn_id,
            step_id=step_id,
            current_mode=current_mode,
            workflow_state=dict(getattr(session, "workflow_state", {}) or {}),
            workflow_state_name=workflow_state_name,
            metadata=dict(metadata),
        )

    def should_inject_workflow(self, user_text: str, current_mode: str) -> bool:
        return bool(self.manager.should_inject_workflow(user_text, current_mode))

    def describe_prompt(self, current_mode: str, workflow_state: str = "chat", session: Any = None) -> Any:
        return self.manager.describe_prompt(current_mode, workflow_state=workflow_state, session=session)

    def initialize_workflow_state(
        self,
        session: Session,
        user_text: str,
        current_mode: str,
        workflow_state: str = "chat",
    ) -> None:
        self.manager.initialize_workflow_state(
            session,
            user_text=user_text,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )

    def allowed_tool_names(self, mode_name: str, workflow_state: str = "chat") -> Set[str]:
        return set(
            self.manager.allowed_tool_names(
                mode_name,
                workflow_state=workflow_state,
                fallback=set(self._mode_allowed_tools(mode_name)),
            )
        )

    def register_tools(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        reason: str = "turn",
    ) -> None:
        self.manager.register_tools(
            ToolRegistrationEvent(
                current_mode=current_mode,
                workflow_state_name=workflow_state,
                reason=reason,
                metadata={"session_id": session.session_id},
            ),
            self.context_for(session),
        )

    def schemas_for_active_tools(self, mode_name: str, workflow_state: str) -> list:
        active_tool_names = sorted(self.allowed_tool_names(mode_name, workflow_state=workflow_state))
        schemas = list(
            self.tools.schemas_for(
                mode_name,
                workflow_state=workflow_state,
                tool_names=active_tool_names,
            )
        )
        names = set(item.get("function", {}).get("name", "") for item in schemas)
        if "ask_user" in self.allowed_tool_names(mode_name, workflow_state=workflow_state) and "ask_user" not in names:
            schemas.append(ask_user_schema())
            names.add("ask_user")
        if "propose_mode_switch" not in names:
            schemas.append(propose_mode_switch_schema())
        return schemas

    def apply_context_patch(
        self,
        session: Session,
        mode_name: str,
        workflow_state: str,
        assembly: ContextAssemblyResult,
        force_compact: bool = False,
    ) -> ContextAssemblyResult:
        event = self.workflow_event(session, mode_name, workflow_state, force_compact=force_compact)
        event.messages = [dict(message) for message in list(assembly.messages or [])]
        patch = self.manager.context(event, self.context_for(session))
        if patch.messages:
            assembly.messages = [dict(message) for message in patch.messages]
        return assembly

    def prepare_tool_call(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
    ) -> Tuple[Any, Action]:
        event = self.workflow_event(session, current_mode, workflow_state)
        event.tool_name = action.name
        event.tool_arguments = dict(action.arguments)
        decision = self.manager.before_tool_call(event, self.context_for(session))
        if decision.updated_arguments is not None:
            action = Action(
                name=action.name,
                arguments=dict(decision.updated_arguments),
                call_id=action.call_id,
                raw_arguments=action.raw_arguments,
            )
        return decision, action

    def apply_tool_result_patch(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        observation: Observation,
    ) -> Observation:
        event = self.workflow_event(session, current_mode, workflow_state)
        event.tool_name = action.name
        event.tool_arguments = dict(action.arguments)
        event.observation = observation
        patch = self.manager.after_tool_result(event, self.context_for(session))
        if patch.workflow_patch is not None:
            workflow_patch = patch.workflow_patch
            if workflow_patch.workflow:
                session.workflow_state["workflow"] = dict(workflow_patch.workflow)
            if workflow_patch.metadata:
                extensions = session.workflow_state.setdefault("extensions", {})
                extensions["last_workflow_patch"] = dict(workflow_patch.metadata)
        if patch.observation is not None:
            return patch.observation
        return observation

    def handle_tool_call(
        self,
        session: Session,
        tool_name: str,
        current_mode: str,
        workflow_state: str,
    ) -> Optional[Observation]:
        return self.manager.handle_tool_call(
            session,
            tool_name=tool_name,
            current_mode=current_mode,
            workflow_state=workflow_state,
        )
```

- [ ] **Step 4: Wire `QueryEngine` through the host while keeping compatibility wrappers**

In `src/embedagent/query_engine.py`:

```python
from embedagent.agent_extension_host import AgentExtensionHost
```

Change initialization:

```python
self.extension_host = AgentExtensionHost(
    manager=extension_manager or ExtensionManager(),
    tools=self.tools,
    permission_policy=self.permission_policy,
    mode_allowed_tools=allowed_tools_for,
)
self.extension_manager = self.extension_host.manager
```

Change wrapper methods:

```python
def _should_inject_harness(self, user_text: str, current_mode: str) -> bool:
    return self.extension_host.should_inject_workflow(user_text, current_mode)

def _allowed_tools_for_mode(self, mode_name: str, workflow_state: str = "chat") -> set:
    return set(self.extension_host.allowed_tool_names(mode_name, workflow_state=workflow_state))

def _extension_context(self, session: Session) -> ExtensionContext:
    return self.extension_host.context_for(session)

def _workflow_event(self, session: Session, current_mode: str, workflow_state: str, **metadata: Any) -> WorkflowEvent:
    return self.extension_host.workflow_event(session, current_mode, workflow_state, **metadata)

def _ensure_extension_tools_registered(self, session: Session, current_mode: str, workflow_state: str, reason: str = "turn") -> None:
    self.extension_host.register_tools(session, current_mode, workflow_state, reason=reason)
```

Replace direct prompt/state/context/schema/tool hook calls:

```python
self.extension_host.describe_prompt(...)
self.extension_host.initialize_workflow_state(...)
self.extension_host.apply_context_patch(...)
self.extension_host.schemas_for_active_tools(...)
self.extension_host.prepare_tool_call(...)
self.extension_host.apply_tool_result_patch(...)
self.extension_host.handle_tool_call(...)
```

- [ ] **Step 5: Run focused host and existing extension tests**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py tests/test_workflow_extensions.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add src/embedagent/agent_extension_host.py src/embedagent/query_engine.py tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py
git commit -m "refactor: add agent extension host"
```

### Task 2: Agent Tool Action Service

**Files:**

- Create: `src/embedagent/agent_tool_action_service.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_query_engine_refactor.py`
- Modify: `tests/test_capability_extensions.py`
- Modify: `tests/test_dynamic_tool_registration.py`

- [ ] **Step 1: Write failing service tests**

Add these tests to `tests/test_query_engine_refactor.py`:

```python
def test_agent_tool_action_service_rejects_inactive_tool(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.agent_tool_action_service import AgentToolActionService
    from embedagent.extensions import ExtensionManager
    from embedagent.permissions import PermissionPolicy
    from embedagent.session import Action, Session
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    policy = PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path))
    host = AgentExtensionHost(ExtensionManager(), runtime, policy, mode_allowed_tools=lambda mode: [])
    service = AgentToolActionService(
        tools=runtime,
        permission_policy=policy,
        extension_host=host,
        app_config_provider=lambda: None,
        failure_observation_factory=QueryEngine(
            client=FakeClient(),
            tools=runtime,
            permission_policy=policy,
        )._failure_observation,
    )

    observation, current_mode, suspended = service.execute_action(
        Session(),
        Action("read_file", {"path": "missing.txt"}, "call-read"),
        "build",
        "chat",
        permission_handler=None,
        user_input_handler=None,
    )

    assert current_mode == "build"
    assert suspended is None
    assert observation.success is False
    assert observation.data["error_kind"] == "mode_tool_blocked"
```

Add this test to `tests/test_dynamic_tool_registration.py`:

```python
def test_agent_tool_action_service_executes_active_dynamic_tool(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.agent_tool_action_service import AgentToolActionService
    from embedagent.extensions import ExtensionManager
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine
    from embedagent.session import Action, Session
    from embedagent.tools import ToolRuntime

    runtime = ToolRuntime(str(tmp_path))
    policy = PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path))
    host = AgentExtensionHost(
        ExtensionManager([DynamicToolExtension(active=True)]),
        runtime,
        policy,
    )
    session = Session()
    host.register_tools(session, "build", "chat", reason="session_start")
    service = AgentToolActionService(
        tools=runtime,
        permission_policy=policy,
        extension_host=host,
        app_config_provider=lambda: None,
        failure_observation_factory=QueryEngine(
            client=ToolCallingClient(Action("dynamic_echo", {"message": "hi"}, "call-client")),
            tools=runtime,
            permission_policy=policy,
        )._failure_observation,
    )

    observation, current_mode, suspended = service.execute_action(
        session,
        Action("dynamic_echo", {"message": "hello"}, "call-dynamic"),
        "build",
        "chat",
        permission_handler=None,
        user_input_handler=None,
    )

    assert suspended is None
    assert current_mode == "build"
    assert observation.success is True
    assert observation.data["echo"] == "hello"
```

- [ ] **Step 2: Run tests and confirm they fail because the service does not exist**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py::test_agent_tool_action_service_rejects_inactive_tool tests/test_dynamic_tool_registration.py::test_agent_tool_action_service_executes_active_dynamic_tool -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'embedagent.agent_tool_action_service'`.

- [ ] **Step 3: Implement `AgentToolActionService`**

Create `src/embedagent/agent_tool_action_service.py` with this structure:

```python
from __future__ import annotations

import os
import threading
from typing import Any, Callable, Optional, Tuple

from embedagent.agent_extension_host import AgentExtensionHost
from embedagent.interaction import UserInputRequest, UserInputResponse
from embedagent.modes import is_path_writable
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.session import Action, Observation, QueryTurnResult, Session
from embedagent.tools import ToolRuntime
from embedagent.tools._base import ToolError


class AgentToolActionService(object):
    def __init__(
        self,
        tools: ToolRuntime,
        permission_policy: PermissionPolicy,
        extension_host: AgentExtensionHost,
        app_config_provider: Callable[[], Any],
        failure_observation_factory: Callable[..., Observation],
    ) -> None:
        self.tools = tools
        self.permission_policy = permission_policy
        self.extension_host = extension_host
        self._app_config_provider = app_config_provider
        self._failure_observation = failure_observation_factory

    def is_extension_blocked_observation(self, observation: Optional[Observation]) -> bool:
        if observation is None or not isinstance(observation.data, dict):
            return False
        return observation.data.get("error_kind") == "extension_blocked"

    def is_interactive_precomputed_skip(self, observation: Optional[Observation]) -> bool:
        if observation is None or not isinstance(observation.data, dict):
            return False
        return observation.data.get("error_kind") == "interactive_precomputed_skip"

    def execute_parallel_tool_action(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        stop_event: Optional[threading.Event],
    ) -> Observation:
        if action.name in ("ask_user", "propose_mode_switch"):
            return Observation(
                action.name,
                False,
                "interactive tool requires query-engine handling",
                {"error_kind": "interactive_precomputed_skip", "retryable": False},
            )
        blocked_observation, runtime_action = self.prepare_extension_tool_call(
            session,
            action,
            current_mode,
            workflow_state,
        )
        if blocked_observation is not None:
            return blocked_observation
        return self.tools.execute_with_interrupt(
            runtime_action.name,
            runtime_action.arguments,
            stop_event,
        )

    def prepare_extension_tool_call(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
    ) -> Tuple[Optional[Observation], Action]:
        decision, runtime_action = self.extension_host.prepare_tool_call(
            session,
            action,
            current_mode,
            workflow_state,
        )
        if decision.block:
            return (
                self._failure_observation(
                    action.name,
                    decision.reason or "Tool call blocked by extension.",
                    "extension_blocked",
                    False,
                    "extension",
                    "Use a different tool or update the extension policy.",
                    {"extension_metadata": dict(decision.metadata)},
                ),
                action,
            )
        return None, runtime_action

    def apply_extension_tool_result_patch(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        observation: Observation,
    ) -> Observation:
        return self.extension_host.apply_tool_result_patch(
            session,
            action,
            current_mode,
            workflow_state,
            observation,
        )

    def execute_action(
        self,
        session: Session,
        action: Action,
        current_mode: str,
        workflow_state: str,
        permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
        user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
        precomputed_observation: Optional[Observation] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> Tuple[Observation, str, Optional[QueryTurnResult]]:
        del user_input_handler
        runtime_action = action
        if action.name not in self.extension_host.allowed_tool_names(current_mode, workflow_state=workflow_state) and action.name not in ("ask_user", "propose_mode_switch"):
            return (
                self._failure_observation(
                    action.name,
                    "当前模式 %s 不允许调用工具 %s。" % (current_mode, action.name),
                    "mode_tool_blocked",
                    False,
                    current_mode,
                    "请改用当前模式允许的工具。",
                ),
                current_mode,
                None,
            )
        if precomputed_observation is not None and not self.is_interactive_precomputed_skip(precomputed_observation):
            if self.is_extension_blocked_observation(precomputed_observation):
                return precomputed_observation, current_mode, None
            observation = self.apply_extension_tool_result_patch(
                session,
                action,
                current_mode,
                workflow_state,
                precomputed_observation,
            )
            return observation, current_mode, None
        blocked_observation, runtime_action = self.prepare_extension_tool_call(
            session,
            action,
            current_mode,
            workflow_state,
        )
        if blocked_observation is not None:
            return blocked_observation, current_mode, None
        if action.name == "task_status":
            observation = self.extension_host.handle_tool_call(
                session,
                tool_name=action.name,
                current_mode=current_mode,
                workflow_state=workflow_state,
            )
            if observation is not None:
                return observation, current_mode, None
        decision = self.permission_policy.evaluate(runtime_action)
        if decision.outcome == "deny":
            return (
                self._failure_observation(
                    action.name,
                    decision.error or "权限规则拒绝该操作。",
                    "permission_denied",
                    False,
                    "permission_policy",
                    "修改权限规则，或由用户手动放行后重试。",
                    {"permission_required": True, "permission_decision": "deny"},
                ),
                current_mode,
                None,
            )
        if decision.request is not None:
            approved = permission_handler(decision.request) if permission_handler is not None else None
            if approved is None:
                return (
                    self._failure_observation(
                        action.name,
                        "waiting permission",
                        "pending_interaction",
                        False,
                        "permission",
                        "等待用户批准。",
                        {"pending": True},
                    ),
                    current_mode,
                    QueryTurnResult("", session, None),
                )
            if not approved:
                return (
                    self._failure_observation(
                        action.name,
                        "操作未获批准，已跳过执行。",
                        "permission_denied",
                        False,
                        "user_confirmation",
                        "等待用户批准，或改为不需要该权限的方案。",
                        {"permission_required": True, "permission_decision": "deny"},
                    ),
                    current_mode,
                    None,
                )
        if action.name in ("edit_file", "write_file"):
            path = str(runtime_action.arguments.get("path") or "")
            if not path:
                return (
                    self._failure_observation(
                        action.name,
                        "%s 缺少 path 参数。" % action.name,
                        "invalid_arguments",
                        False,
                        "arguments",
                        "补充一个相对于工作区的 path 参数。",
                    ),
                    current_mode,
                    None,
                )
            if not is_path_writable(current_mode, path.replace("\\", "/"), self._app_config_provider()):
                return (
                    self._failure_observation(
                        action.name,
                        "当前模式 %s 不允许修改 %s。" % (current_mode, path.replace("\\", "/")),
                        "mode_path_blocked",
                        False,
                        current_mode,
                        "请改用当前模式允许的文件类型，或切换模式。",
                    ),
                    current_mode,
                    None,
                )
            if action.name == "edit_file":
                try:
                    resolved_path = self.tools._ctx.resolve_path(path.replace("\\", "/"), allow_missing=True)
                except ToolError as exc:
                    return (
                        self._failure_observation(
                            action.name,
                            str(exc),
                            "path_invalid",
                            False,
                            "workspace",
                            "改用工作区内的相对路径。",
                        ),
                        current_mode,
                        None,
                    )
                if not resolved_path or not os.path.exists(resolved_path):
                    return (
                        self._failure_observation(
                            action.name,
                            "目标文件不存在，edit_file 只能修改已存在的文件。",
                            "file_missing",
                            False,
                            "filesystem",
                            "若要新建文件，请改用 write_file。",
                        ),
                        current_mode,
                        None,
                    )
        observation = self.tools.execute_with_interrupt(
            runtime_action.name,
            runtime_action.arguments,
            stop_event,
        )
        observation = self.apply_extension_tool_result_patch(
            session,
            runtime_action,
            current_mode,
            workflow_state,
            observation,
        )
        return observation, current_mode, None
```

- [ ] **Step 4: Move QueryEngine execution behavior behind the service**

In `QueryEngine.__init__`, instantiate:

```python
from embedagent.agent_tool_action_service import AgentToolActionService

self._action_service = AgentToolActionService(
    tools=self.tools,
    permission_policy=self.permission_policy,
    extension_host=self.extension_host,
    app_config_provider=lambda: getattr(self.tools, "app_config", None),
    failure_observation_factory=self._failure_observation,
)
```

Then change these wrappers:

```python
def _prepare_extension_tool_call(...):
    return self._action_service.prepare_extension_tool_call(...)

def _execute_parallel_tool_action(...):
    return self._action_service.execute_parallel_tool_action(...)

def _is_extension_blocked_observation(...):
    return self._action_service.is_extension_blocked_observation(observation)

def _is_interactive_precomputed_skip(...):
    return self._action_service.is_interactive_precomputed_skip(observation)

def _apply_extension_tool_result_patch(...):
    return self._action_service.apply_extension_tool_result_patch(...)
```

For `_execute_action(...)`, keep `ask_user` and `propose_mode_switch` interaction branches in `QueryEngine` first, then delegate the remaining permission/runtime/default path to `self._action_service.execute_action(...)`. This keeps transcript-backed pending interaction creation in `QueryEngine` for Slice 5.

- [ ] **Step 5: Run focused action tests**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add src/embedagent/agent_tool_action_service.py src/embedagent/query_engine.py tests/test_query_engine_refactor.py tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py
git commit -m "refactor: extract agent tool action service"
```

### Task 3: Agent Loop Boundary

**Files:**

- Create: `src/embedagent/agent_loop.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_query_engine_refactor.py`
- Modify: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Write failing loop-boundary tests**

Add this test to `tests/test_query_engine_refactor.py`:

```python
def test_agent_loop_delegates_to_runner_callback(tmp_path):
    from embedagent.agent_loop import AgentLoop
    from embedagent.session import LoopTransition, QueryTurnResult, Session

    session = Session()
    calls = []

    def runner(**kwargs):
        calls.append(kwargs)
        transition = LoopTransition(reason="completed", message="runner finished")
        return QueryTurnResult("ok", kwargs["session"], transition, turns_used=1)

    loop = AgentLoop(runner=runner)
    result = loop.run(
        session=session,
        current_mode="build",
        workflow_state="chat",
        stream=False,
        stop_event=None,
        on_text_delta=None,
        on_reasoning_delta=None,
        on_tool_start=None,
        on_tool_finish=None,
        on_context_result=None,
        on_step_start=None,
        on_step_finish=None,
        permission_handler=None,
        user_input_handler=None,
    )

    assert result.final_text == "ok"
    assert calls[0]["session"] is session
    assert calls[0]["current_mode"] == "build"
    assert calls[0]["workflow_state"] == "chat"
```

Add this test to `tests/test_workflow_extensions.py`:

```python
def test_bare_query_engine_uses_empty_extension_host_without_c_harness(tmp_path):
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    engine = QueryEngine(client=DoneClient(), tools=ToolRuntime(str(tmp_path)), max_turns=1)

    assert engine.extension_manager.diagnostics() == []
    assert "run_recipe" not in engine._allowed_tools_for_mode("build", "chat")
    assert "task_status" not in engine._allowed_tools_for_mode("build", "chat")
    assert "propose_mode_switch" in set(
        item["function"]["name"] for item in engine._schemas_for_active_tools("build", "chat")
    )
```

- [ ] **Step 2: Run tests and confirm the loop module does not exist**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py::test_agent_loop_delegates_to_runner_callback tests/test_workflow_extensions.py::test_bare_query_engine_uses_empty_extension_host_without_c_harness -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'embedagent.agent_loop'` for the first test. The second test may already pass before loop extraction; keep it as a guard.

- [ ] **Step 3: Implement `AgentLoop` as a thin boundary**

Create `src/embedagent/agent_loop.py`:

```python
from __future__ import annotations

from typing import Any, Callable


class AgentLoop(object):
    def __init__(self, runner: Callable[..., Any]) -> None:
        self._runner = runner

    def run(self, **kwargs: Any) -> Any:
        return self._runner(**kwargs)
```

In `QueryEngine.__init__`:

```python
from embedagent.agent_loop import AgentLoop

self._agent_loop = AgentLoop(runner=self._run_loop_impl)
```

Rename current `_run_loop(...)` to `_run_loop_impl(...)`.

Add a new `_run_loop(...)` wrapper:

```python
def _run_loop(
    self,
    session: Session,
    current_mode: str,
    workflow_state: str,
    stream: bool,
    stop_event: Optional[threading.Event],
    on_text_delta: Optional[Callable[[str], None]],
    on_reasoning_delta: Optional[Callable[[str], None]],
    on_tool_start: Optional[Callable[[Action], None]],
    on_tool_finish: Optional[Callable[[Action, Observation], None]],
    on_context_result: Optional[Callable[[ContextAssemblyResult], None]],
    on_step_start: Optional[Callable[[str, int], None]],
    on_step_finish: Optional[Callable[[int, AssistantReply, str], None]],
    permission_handler: Optional[Callable[[PermissionRequest], Optional[bool]]],
    user_input_handler: Optional[Callable[[UserInputRequest], Optional[UserInputResponse]]],
) -> QueryTurnResult:
    return self._agent_loop.run(
        session=session,
        current_mode=current_mode,
        workflow_state=workflow_state,
        stream=stream,
        stop_event=stop_event,
        on_text_delta=on_text_delta,
        on_reasoning_delta=on_reasoning_delta,
        on_tool_start=on_tool_start,
        on_tool_finish=on_tool_finish,
        on_context_result=on_context_result,
        on_step_start=on_step_start,
        on_step_finish=on_step_finish,
        permission_handler=permission_handler,
        user_input_handler=user_input_handler,
    )
```

- [ ] **Step 4: Run loop and QueryEngine tests**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py::test_agent_loop_delegates_to_runner_callback tests/test_query_engine_orchestrator.py tests/test_workflow_extensions.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add src/embedagent/agent_loop.py src/embedagent/query_engine.py tests/test_query_engine_refactor.py tests/test_workflow_extensions.py
git commit -m "refactor: introduce agent loop boundary"
```

### Task 4: QueryEngine Slimming Guards and Cleanup

**Files:**

- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_workflow_extensions.py`
- Modify: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Write source-level regression guards**

Add this test to `tests/test_workflow_extensions.py`:

```python
def test_query_engine_no_longer_dispatches_extension_manager_hooks_directly():
    source = (_REPO_ROOT / "src" / "embedagent" / "query_engine.py").read_text(encoding="utf-8")
    forbidden = [
        ".should_inject_workflow(",
        ".allowed_tool_names(",
        ".register_tools(",
        ".describe_prompt(",
        ".initialize_workflow_state(",
        ".context(",
        ".before_tool_call(",
        ".after_tool_result(",
        ".handle_tool_call(",
    ]
    for needle in forbidden:
        assert "extension_manager" + needle not in source
```

Add this test to `tests/test_query_engine_refactor.py`:

```python
def test_query_engine_exposes_slim_agent_components(tmp_path):
    from embedagent.agent_extension_host import AgentExtensionHost
    from embedagent.agent_loop import AgentLoop
    from embedagent.agent_tool_action_service import AgentToolActionService
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    engine = QueryEngine(client=FakeClient(), tools=ToolRuntime(str(tmp_path)), max_turns=1)

    assert isinstance(engine.extension_host, AgentExtensionHost)
    assert isinstance(engine._action_service, AgentToolActionService)
    assert isinstance(engine._agent_loop, AgentLoop)
    assert engine.extension_manager is engine.extension_host.manager
```

- [ ] **Step 2: Run guard tests and confirm any remaining direct call failure**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_query_engine_no_longer_dispatches_extension_manager_hooks_directly tests/test_query_engine_refactor.py::test_query_engine_exposes_slim_agent_components -v
```

Expected: FAIL if any `extension_manager.*` hook calls remain in `QueryEngine`; PASS once wrappers are fully host-backed.

- [ ] **Step 3: Remove leftover direct hook calls and imports**

In `src/embedagent/query_engine.py`:

- Remove direct `ToolRegistrationEvent` imports if no wrapper needs them.
- Remove direct `SessionView` imports if no wrapper needs them.
- Remove direct `WorkflowEvent` import if no wrapper annotation needs it.
- Keep `ExtensionManager` import for constructor typing and compatibility.
- Keep `ExtensionContext` import only if `_extension_context(...)` compatibility annotation remains.
- Ensure every direct prompt/context/tool hook call goes through `self.extension_host`.

- [ ] **Step 4: Run focused guard and extension suites**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py tests/test_query_engine_refactor.py tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add src/embedagent/query_engine.py tests/test_workflow_extensions.py tests/test_query_engine_refactor.py
git commit -m "test: guard slim query engine extension boundary"
```

### Task 5: Source-of-Truth Documentation Sync

**Files:**

- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/agent-harness-v2.md`

- [ ] **Step 1: Update docs with the new execution spine**

Apply these durable wording changes:

- `QueryEngine` remains the session-scoped facade and transcript/session mutation owner.
- `AgentLoop` owns turn-loop orchestration.
- `AgentToolActionService` owns non-LLM tool action execution.
- `AgentExtensionHost` owns extension hook dispatch and explicit active-tool schema projection.
- Default C/C++ harness behavior remains installed through `default_extensions.py` and the shared `ExtensionManager`.
- Bare `QueryEngine` uses an empty extension host and does not activate harness workflow tools.

- [ ] **Step 2: Run doc terminology checks**

Run:

```bash
rg "AgentLoop|AgentToolActionService|AgentExtensionHost|QueryEngine" README.md AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md docs/tool-contracts.md docs/agent-harness-v2.md
```

Expected: output includes all three new component names in source-of-truth docs.

- [ ] **Step 3: Run focused doc-adjacent tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py tests/test_query_engine_orchestrator.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit Task 5**

Run:

```bash
git add README.md AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md docs/tool-contracts.md docs/agent-harness-v2.md
git commit -m "docs: document slim agent core execution spine"
```

### Task 6: Slice 5 Final Verification and Archive

**Files:**

- Move: `docs/superpowers/specs/2026-06-12-query-engine-slimming-design.md` to `docs/archive/self-extensible-agent-core/2026-06-12-query-engine-slimming-design.md`
- Move: `docs/superpowers/plans/2026-06-12-query-engine-slimming.md` to `docs/archive/self-extensible-agent-core/2026-06-12-query-engine-slimming-plan.md`

- [ ] **Step 1: Run focused verification**

Run:

```bash
uv run pytest tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py tests/test_workflow_extensions.py tests/test_query_engine_refactor.py tests/test_query_engine_orchestrator.py tests/test_strategies.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full fast verification**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v --basetemp .pytest-tmp-query-engine-slimming-fast
```

Expected: PASS.

- [ ] **Step 3: Run lint check on touched code/tests**

Run:

```bash
uv run ruff check src/embedagent/agent_extension_host.py src/embedagent/agent_tool_action_service.py src/embedagent/agent_loop.py src/embedagent/query_engine.py tests/test_dynamic_tool_registration.py tests/test_capability_extensions.py tests/test_workflow_extensions.py tests/test_query_engine_refactor.py
```

Expected: PASS.

- [ ] **Step 4: Archive completed slice-local docs**

Move the files:

```bash
git mv docs/superpowers/specs/2026-06-12-query-engine-slimming-design.md docs/archive/self-extensible-agent-core/2026-06-12-query-engine-slimming-design.md
git mv docs/superpowers/plans/2026-06-12-query-engine-slimming.md docs/archive/self-extensible-agent-core/2026-06-12-query-engine-slimming-plan.md
```

- [ ] **Step 5: Commit final archive state**

Run:

```bash
git add docs/archive/self-extensible-agent-core/2026-06-12-query-engine-slimming-design.md docs/archive/self-extensible-agent-core/2026-06-12-query-engine-slimming-plan.md
git commit -m "docs: archive query engine slimming slice"
```

- [ ] **Step 6: Inspect final state**

Run:

```bash
git status --short
git log --oneline -6
```

Expected: clean worktree except ignored test temp directories; recent commits show the Slice 5 design, implementation, docs, and archive commits.

---

## Self-Review

Spec coverage:

- Extension hook dispatch moves to `AgentExtensionHost`: Tasks 1 and 4.
- Tool action execution moves to `AgentToolActionService`: Task 2.
- Agent loop extraction: Task 3.
- Bare core without default harness extension: Task 3.
- Transcript and permission preservation: Task 2 keeps transcript-backed interaction creation in `QueryEngine`; focused and full tests verify behavior.
- Docs sync and archive: Tasks 5 and 6.

Placeholder scan:

- No `TBD`, `TODO`, or open-ended "implement later" steps remain.
- Each code-touching task includes concrete test or implementation snippets.

Type consistency:

- `AgentExtensionHost`, `AgentToolActionService`, and `AgentLoop` names match across tests, implementation snippets, and docs tasks.
- Compatibility attributes stay as `engine.extension_manager`, `engine.extension_host`, `engine._action_service`, and `engine._agent_loop`.

