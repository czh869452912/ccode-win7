# Workflow Extension Migration Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the workflow-extension migration so Agent Core stays workflow-neutral while the bundled C/C++ harness remains the default hosted workflow extension.

**Architecture:** `QueryEngine`, session projection, runtime schema projection, and frontend read models must not own C harness internals. The bundled C/C++ harness owns its task graph and publishes the generic read model through `Session.workflow_state["workflow"]`. Runtime schema projection stays pure unless a caller passes explicit active tool names from `ExtensionManager`.

**Tech Stack:** Python 3.8, stdlib dataclasses, pytest, unittest, ruff, existing `ExtensionManager`, `ToolRuntime`, `CHarnessWorkflowExtension`, and harness task modules.

---

## Current Baseline

- `main` contains the workflow-extension migration handoff and the synchronizer-removal slice.
- `src/embedagent/query_engine.py` does not import or construct `CHarnessWorkflowExtension`.
- `src/embedagent/default_extensions.py` installs the bundled C/C++ harness for hosted adapter paths.
- `src/embedagent/session.py` still exposes `Session.task_graph`, but it is lazy and no longer imported at module import time.
- `src/embedagent/services/harness_state_synchronizer.py` has been deleted; default harness refresh now goes through `CHarnessWorkflowExtension.refresh_managed_session()`.
- `ToolRuntime.schemas_for_mode()` and `ToolRuntime.allowed_tool_names()` still exist as compatibility wrappers around the pure mode contract.
- `src/embedagent/strategies/turn_orchestrator.py` reads task-status data from `Session.workflow_state["workflow"]`, but it still calls `tools.allowed_tool_names(...)` for mode gating.

## Guardrails

- Keep runtime compatibility at Python `>=3.8,<3.9`.
- Do not use walrus operators, `match`, `dict | dict`, or other Python 3.9+ syntax.
- Do not add runtime dependencies outside `pyproject.toml`.
- Do not introduce Docker, WSL, VS Code, online service, plugin marketplace, or multi-agent orchestration dependencies.
- Do not reintroduce default harness construction inside `QueryEngine`.
- Do not make mode schemas own default harness workflow tools again.
- Do not let workflow-neutral modules read `Session.task_graph`.
- Keep each task as a separate commit.

## File Map

- `src/embedagent/services/__init__.py`
  Public service exports; no longer exposes the old synchronizer facade.
- `tests/test_backward_compatibility.py`
  Remove public-import expectations for `HarnessStateSynchronizer` in Task 1.
- `src/embedagent/session.py`
  Remove `Session.task_graph` and `_empty_task_graph` in Task 2.
- `src/embedagent/harness/extension.py`
  Keep C harness task graph ownership behind the extension in Task 2.
- `src/embedagent/harness/runner.py`
  Stop mutating `session.task_graph`; return harness-owned graphs in Task 2.
- `src/embedagent/harness/workflow_projection.py`
  Continue to be the C harness to generic workflow payload adapter.
- `src/embedagent/tools/runtime.py`
  Remove schema and tool-name compatibility wrappers in Tasks 3 and 4.
- `src/embedagent/tools/harness_runtime.py`
  Remove `OfficialRuntimeModes.allowed_tool_names()` only after no live caller remains in Task 4.
- `src/embedagent/strategies/turn_orchestrator.py`
  Use injected allowed-tool policy instead of `ToolRuntime.allowed_tool_names()` in Task 4.
- `src/embedagent/query_engine.py`
  Pass its extension-aware allowed-tool policy into `TurnOrchestrator` in Task 4.
- `docs/tool-contracts.md`, `docs/mode-schema.md`, `docs/overall-solution-architecture.md`, `docs/agent-harness-v2.md`, `docs/implementation-roadmap.md`, `docs/development-tracker.md`, `docs/design-change-log.md`
  Keep durable architecture truth synchronized after each task that changes public contracts.

## Verification Commands

Use this temp directory pattern for pytest on Windows:

```powershell
$tmp = "D:\Project\coding_agent\.worktrees\.pytest-env-tmp-workflow-extension-handoff"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$env:TMP = $tmp
$env:TEMP = $tmp
```

Run after every code task:

```powershell
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
git diff --check
uv run pytest tests/ -m "not slow and not gui" -v --basetemp "$tmp\basetemp-fast"
```

Expected fast-suite result at this baseline after Task 1: `681 passed, 11 deselected`.

### Task 1: Retire `HarnessStateSynchronizer` (completed 2026-05-29)

**Files:**
- Modify: `tests/test_backward_compatibility.py`
- Modify: `tests/test_workflow_extensions.py`
- Modify: `src/embedagent/services/__init__.py`
- Delete: `src/embedagent/services/harness_state_synchronizer.py`
- Modify docs: `README.md`, `AGENTS.md`, `docs/overall-solution-architecture.md`, `docs/agent-harness-v2.md`, `docs/implementation-roadmap.md`, `docs/development-tracker.md`, `docs/design-change-log.md`

- [x] **Step 1: Replace the public import compatibility test**

In `tests/test_backward_compatibility.py`, replace `test_import_services` with:

```python
    def test_import_services(self):
        from embedagent.services import (
            EventEmitter,
            SessionLifecycleManager,
            WorkspaceFileService,
        )

        assert EventEmitter is not None
        assert SessionLifecycleManager is not None
        assert WorkspaceFileService is not None
```

- [x] **Step 2: Add focused source-boundary tests**

Append these tests to `tests/test_workflow_extensions.py`:

```python
def test_services_no_longer_export_harness_state_synchronizer():
    import embedagent.services as services

    assert "HarnessStateSynchronizer" not in getattr(services, "__all__", [])
    assert not hasattr(services, "HarnessStateSynchronizer")


def test_harness_state_synchronizer_module_removed():
    path = (
        _REPO_ROOT
        / "src"
        / "embedagent"
        / "services"
        / "harness_state_synchronizer.py"
    )

    assert not path.exists()
```

- [x] **Step 3: Run tests and verify they fail for the current facade**

Run:

```powershell
uv run pytest tests/test_backward_compatibility.py::TestPublicImports::test_import_services tests/test_workflow_extensions.py::test_services_no_longer_export_harness_state_synchronizer tests/test_workflow_extensions.py::test_harness_state_synchronizer_module_removed -v
```

Expected: FAIL because `src/embedagent/services/__init__.py` still lazy-exports `HarnessStateSynchronizer` and `src/embedagent/services/harness_state_synchronizer.py` still exists.

- [x] **Step 4: Remove the compatibility facade**

Replace `src/embedagent/services/__init__.py` with:

```python
from embedagent.services.event_emitter import EventEmitter
from embedagent.services.session_lifecycle import SessionLifecycleManager
from embedagent.services.shadow_git import ShadowGitSnapshot
from embedagent.services.workspace_file_service import WorkspaceFileService

__all__ = [
    "EventEmitter",
    "SessionLifecycleManager",
    "ShadowGitSnapshot",
    "WorkspaceFileService",
]
```

Delete `src/embedagent/services/harness_state_synchronizer.py`.

- [x] **Step 5: Update durable docs**

Change docs that currently say `HarnessStateSynchronizer` remains as a compatibility facade so they say it has been removed and that product refresh goes through `CHarnessWorkflowExtension.refresh_managed_session(...)`.

Search command:

```powershell
rg -n "HarnessStateSynchronizer|harness_state_synchronizer" README.md AGENTS.md docs src tests
```

Expected remaining matches after this task: historical entries in `docs/design-change-log.md` and archived docs only, plus a new design-change entry describing the removal.

- [x] **Step 6: Verify and commit**

Run:

```powershell
uv run pytest tests/test_backward_compatibility.py::TestPublicImports::test_import_services tests/test_workflow_extensions.py -v
uv run pytest tests/ -m "not slow and not gui" -v --basetemp "$tmp\basetemp-retire-synchronizer"
git diff --check
```

Actual verification:

- `uv run pytest tests/test_backward_compatibility.py::TestPublicImports::test_import_services tests/test_workflow_extensions.py::test_services_no_longer_export_removed_sync_facade tests/test_workflow_extensions.py::test_removed_sync_facade_module_is_absent tests/test_workflow_extensions.py::test_inprocess_adapter_no_longer_depends_on_removed_sync_facade tests/test_services.py::TestHarnessWorkflowExtensionRefresh -v`: `6 passed`
- `uv run ruff check src/embedagent/services/__init__.py tests/test_backward_compatibility.py tests/test_services.py tests/test_workflow_extensions.py`: pass
- `uv run ruff format --check src/embedagent/services/__init__.py tests/test_backward_compatibility.py tests/test_services.py tests/test_workflow_extensions.py`: pass
- `git diff --check`: pass, with line-ending warnings only
- `uv run pytest tests/ -m "not slow and not gui" -v --basetemp "$tmp\basetemp-retire-synchronizer"`: `681 passed, 11 deselected`

Commit:

```powershell
git add tests/test_backward_compatibility.py tests/test_workflow_extensions.py src/embedagent/services/__init__.py README.md AGENTS.md docs/overall-solution-architecture.md docs/agent-harness-v2.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md
git add -u src/embedagent/services/harness_state_synchronizer.py
git commit -m "refactor: remove harness state synchronizer facade"
```

### Task 2: Move C Harness Graph Ownership Out Of `Session`

**Files:**
- Create: `src/embedagent/harness/session_graph_state.py`
- Modify: `src/embedagent/session.py`
- Modify: `src/embedagent/harness/extension.py`
- Modify: `src/embedagent/harness/runner.py`
- Modify: `tests/test_task_graph_v2.py`
- Modify: `tests/test_workflow_extensions.py`
- Modify docs: `README.md`, `AGENTS.md`, `docs/overall-solution-architecture.md`, `docs/agent-harness-v2.md`, `docs/implementation-roadmap.md`, `docs/development-tracker.md`, `docs/design-change-log.md`

- [ ] **Step 1: Add failing tests for removing the session field**

Append this test to `tests/test_workflow_extensions.py`:

```python
def test_session_no_longer_has_task_graph_field():
    from dataclasses import fields

    from embedagent.session import Session

    assert "task_graph" not in {field.name for field in fields(Session)}
    assert not hasattr(Session(), "task_graph")
```

Replace the first two tests in `tests/test_task_graph_v2.py` with this harness-owned behavior test:

```python
    def test_harness_extension_owns_task_graph_without_session_field(self):
        from embedagent.harness.extension import CHarnessWorkflowExtension
        from embedagent.session import Observation, Session
        from embedagent.session_runtime import ManagedSession

        extension = CHarnessWorkflowExtension()
        session = Session()

        extension.initialize_workflow_state(
            session,
            user_text="build the demo program",
            current_mode="build",
            workflow_state="chat",
        )

        self.assertFalse(hasattr(session, "task_graph"))
        self.assertIn("workflow", session.workflow_state)
        self.assertIn("summary", session.workflow_state["workflow"])

        managed = ManagedSession(
            session=session,
            current_mode="build",
            workflow_state="chat",
        )
        extension.refresh_managed_session(
            managed,
            os.getcwd(),
            observations=[Observation("run_recipe", True, None, {"recipe_id": "unit"})],
        )

        workflow = session.workflow_state["workflow"]
        self.assertTrue(workflow["summary"])
        self.assertTrue(workflow["items"])
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/test_workflow_extensions.py::test_session_no_longer_has_task_graph_field tests/test_task_graph_v2.py::TaskGraphV2Tests::test_harness_extension_owns_task_graph_without_session_field -v
```

Expected: FAIL because `Session.task_graph` still exists and the harness extension still reads/writes it.

- [ ] **Step 3: Create harness-owned graph state**

Create `src/embedagent/harness/session_graph_state.py`:

```python
from __future__ import annotations

from typing import Any, Dict, Optional

from embedagent.harness.task_graph import TaskGraph


class HarnessSessionGraphState(object):
    def __init__(self) -> None:
        self._graphs = {}  # type: Dict[str, TaskGraph]

    def _key(self, session: Any) -> str:
        return str(getattr(session, "session_id", "") or id(session))

    def get(self, session: Any) -> Optional[TaskGraph]:
        return self._graphs.get(self._key(session))

    def set(self, session: Any, graph: TaskGraph) -> TaskGraph:
        self._graphs[self._key(session)] = graph
        return graph

    def ensure_empty(self, session: Any) -> TaskGraph:
        graph = self.get(session)
        if graph is None:
            graph = self.set(session, TaskGraph.empty())
        return graph

    def from_user_request(self, session: Any, user_text: str, current_mode: str) -> TaskGraph:
        return self.set(session, TaskGraph.from_user_request(user_text, current_mode))
```

- [ ] **Step 4: Change `HarnessRunner.update_task_graph` to return a graph instead of mutating `Session`**

In `src/embedagent/harness/runner.py`, replace `update_task_graph(...)` with:

```python
    def update_task_graph(
        self,
        graph,
        mode_name,
        observations=None,
        discipline_override=None,
    ):
        current_phase = ""
        if graph is not None and str(getattr(graph, "mode_name", "") or "") == str(
            mode_name or ""
        ):
            current_phase = str(getattr(graph, "current_phase", "") or "")
        context = self.describe_mode(
            mode_name,
            discipline_override=discipline_override,
            current_phase=current_phase,
            observations=observations,
        )
        if context is None:
            updated = TaskGraph.empty()
        else:
            updated = TaskGraph.for_mode(
                context.mode_name,
                context.discipline_label,
                track=context.track,
                current_phase=context.current_phase,
            )
        if graph is not None:
            graph.replace_with(updated)
            return graph
        return updated
```

- [ ] **Step 5: Refactor `CHarnessWorkflowExtension` to use `HarnessSessionGraphState`**

In `src/embedagent/harness/extension.py`:

```python
from embedagent.harness.session_graph_state import HarnessSessionGraphState
```

Change the constructor:

```python
    def __init__(
        self,
        tools: Any = None,
        harness_runner: Optional[HarnessRunner] = None,
        graph_state: Optional[HarnessSessionGraphState] = None,
    ) -> None:
        self.tools = tools
        self.harness_runner = harness_runner or HarnessRunner()
        self.graph_state = graph_state or HarnessSessionGraphState()
```

Replace every `getattr(session, "task_graph", None)` with `self.graph_state.get(session)`.

In `initialize_workflow_state(...)`, replace direct assignment with:

```python
        graph = self.graph_state.get(session)
        if graph is not None and not graph.is_empty():
            return
        graph = self.graph_state.from_user_request(session, user_text, current_mode)
        self._sync_workflow_state(session, graph=graph)
```

In `refresh_managed_session(...)`, call the runner with the current graph and store the returned graph:

```python
        graph = self.harness_runner.update_task_graph(
            self.graph_state.get(managed_session.session),
            managed_session.current_mode,
            observations=observations,
            discipline_override=discipline_override,
        )
        self.graph_state.set(managed_session.session, graph)
```

Change `_sync_workflow_state(...)` to accept a graph:

```python
    def _sync_workflow_state(self, session: Any, graph: Any = None, context: Any = None) -> None:
        graph = graph or self.graph_state.get(session)
        if graph is None:
            return
        session.workflow_state["workflow"] = build_c_harness_workflow_projection(
            graph,
            context=context,
        )
```

- [ ] **Step 6: Remove `Session.task_graph`**

In `src/embedagent/session.py`, delete `_empty_task_graph()` and remove this dataclass field:

```python
    task_graph: Any = field(default_factory=_empty_task_graph)
```

Keep:

```python
    workflow_state: Dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 7: Update source-boundary tests**

In `tests/test_workflow_extensions.py`, replace tests that assign `session.task_graph = ExplodingTaskGraph()` with workflow-projection-only assertions. Keep source checks that workflow-neutral modules do not reference `session.task_graph`.

Use this source check:

```python
def test_workflow_neutral_modules_do_not_reference_session_task_graph():
    paths = [
        _REPO_ROOT / "src" / "embedagent" / "session_projector.py",
        _REPO_ROOT / "src" / "embedagent" / "strategies" / "turn_orchestrator.py",
        _REPO_ROOT / "src" / "embedagent" / "inprocess_adapter.py",
    ]

    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "session.task_graph" not in source
```

- [ ] **Step 8: Verify and commit**

Run:

```powershell
uv run pytest tests/test_task_graph_v2.py tests/test_workflow_extensions.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py -v
uv run pytest tests/ -m "not slow and not gui" -v --basetemp "$tmp\basetemp-session-task-graph-removal"
git diff --check
```

Expected: PASS.

Commit:

```powershell
git add src/embedagent/session.py src/embedagent/harness/session_graph_state.py src/embedagent/harness/extension.py src/embedagent/harness/runner.py tests/test_task_graph_v2.py tests/test_workflow_extensions.py README.md AGENTS.md docs/overall-solution-architecture.md docs/agent-harness-v2.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md
git commit -m "refactor: move task graph ownership into harness extension"
```

### Task 3: Remove `ToolRuntime.schemas_for_mode()`

**Files:**
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `tests/test_tools_package.py`
- Modify: `tests/test_tools_v2_runtime.py`
- Modify: `tests/test_workflow_extensions.py`
- Modify docs: `docs/tool-contracts.md`, `docs/mode-schema.md`, `docs/overall-solution-architecture.md`, `docs/agent-harness-v2.md`, `docs/implementation-roadmap.md`, `docs/development-tracker.md`, `docs/design-change-log.md`

- [ ] **Step 1: Add source-boundary test**

Append to `tests/test_workflow_extensions.py`:

```python
def test_tool_runtime_no_longer_exposes_schemas_for_mode_alias():
    source = (
        _REPO_ROOT / "src" / "embedagent" / "tools" / "runtime.py"
    ).read_text(encoding="utf-8")

    assert "def schemas_for_mode" not in source
```

- [ ] **Step 2: Replace test callsites with `schemas_for(...)`**

In `tests/test_tools_package.py`, rename the three `schemas_for_mode` tests and change calls:

```python
schemas = self.rt.schemas_for("verify", workflow_state="review")
schemas = self.rt.schemas_for("build", workflow_state="chat")
schemas = self.rt.schemas_for("debug", workflow_state="chat")
```

In `tests/test_tools_v2_runtime.py`, change:

```python
names = [item["function"]["name"] for item in runtime.schemas_for("build")]
names = [item["function"]["name"] for item in runtime.schemas_for("debug")]
names = [item["function"]["name"] for item in runtime.schemas_for("verify")]
```

In `tests/test_workflow_extensions.py`, remove `schemas_for_mode(...)` from `ToolRuntimeBoundaryProbe`; `QueryEngine` should already use `schemas_for(...)`.

- [ ] **Step 3: Run tests and verify failure before removing alias**

Run:

```powershell
uv run pytest tests/test_workflow_extensions.py::test_tool_runtime_no_longer_exposes_schemas_for_mode_alias -v
```

Expected: FAIL because `ToolRuntime.schemas_for_mode()` still exists.

- [ ] **Step 4: Remove the alias**

Delete this method from `src/embedagent/tools/runtime.py`:

```python
    def schemas_for_mode(
        self, mode_name: str, workflow_state: str = "chat"
    ) -> List[Dict[str, Any]]:
        return self.schemas_for(mode_name, workflow_state=workflow_state)
```

- [ ] **Step 5: Update docs**

Replace wording that says `schemas_for_mode()` remains as a compatibility entry point. The new durable wording is:

```markdown
`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it projects only the workflow-neutral mode contract. Harness-aware callers must obtain extension-active tool names from `ExtensionManager` and pass them explicitly.
```

- [ ] **Step 6: Verify and commit**

Run:

```powershell
uv run pytest tests/test_tools_package.py tests/test_tools_v2_runtime.py tests/test_workflow_extensions.py -v
uv run pytest tests/ -m "not slow and not gui" -v --basetemp "$tmp\basetemp-remove-schemas-for-mode"
git diff --check
```

Expected: PASS.

Commit:

```powershell
git add src/embedagent/tools/runtime.py tests/test_tools_package.py tests/test_tools_v2_runtime.py tests/test_workflow_extensions.py docs/tool-contracts.md docs/mode-schema.md docs/overall-solution-architecture.md docs/agent-harness-v2.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md
git commit -m "refactor: remove schemas_for_mode runtime alias"
```

### Task 4: Remove `ToolRuntime.allowed_tool_names()` From Core Gating

**Files:**
- Modify: `src/embedagent/strategies/turn_orchestrator.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/tools/harness_runtime.py`
- Modify: `tests/test_strategies.py`
- Modify: `tests/test_tools_package.py`
- Modify: `tests/test_workflow_extensions.py`
- Modify docs: `docs/tool-contracts.md`, `docs/mode-schema.md`, `docs/implementation-roadmap.md`, `docs/development-tracker.md`, `docs/design-change-log.md`

- [ ] **Step 1: Add a failing strategy boundary test**

In `tests/test_strategies.py`, add:

```python
    def test_turn_orchestrator_uses_injected_allowed_tool_policy(self):
        llm_wrapper = MagicMock()
        tools = MagicMock()
        tools.allowed_tool_names.side_effect = AssertionError(
            "TurnOrchestrator must not call ToolRuntime.allowed_tool_names"
        )
        tools.tool_capabilities.return_value = {}
        tools.execute_with_interrupt.return_value = MagicMock(success=True)
        action = Action(name="read_file", arguments={"path": "test.txt"}, call_id="call-1")
        llm_wrapper.call_with_retry.return_value = AssistantReply(content="", actions=[action])

        allowed_tool_names = MagicMock(return_value={"read_file"})
        orchestrator = self._make_orchestrator(
            llm_wrapper=llm_wrapper,
            tools=tools,
            allowed_tool_names=allowed_tool_names,
        )
        session = Session()

        result = orchestrator.execute_turn(
            session=session,
            messages=[{"role": "user", "content": "read"}],
            tool_schemas=[],
            current_mode="build",
        )

        self.assertEqual(result.transition.reason, "tool_calls")
        allowed_tool_names.assert_called_with("build", workflow_state="chat")
```

Update `_make_orchestrator(...)` in the same test class to pass `allowed_tool_names` through to `TurnOrchestrator`.

- [ ] **Step 2: Run the new test and verify failure**

Run:

```powershell
uv run pytest tests/test_strategies.py::TestTurnOrchestrator::test_turn_orchestrator_uses_injected_allowed_tool_policy -v
```

Expected: FAIL because `TurnOrchestrator` still calls `tools.allowed_tool_names(...)`.

- [ ] **Step 3: Inject the allowed-tool policy**

In `src/embedagent/strategies/turn_orchestrator.py`, add a constructor parameter:

```python
        allowed_tool_names=None,
```

Set the instance attribute:

```python
        self.allowed_tool_names = allowed_tool_names or (
            lambda mode_name, workflow_state="chat": set()
        )
```

Replace:

```python
        allowed = set(self.tools.allowed_tool_names(current_mode, workflow_state=workflow_state))
```

with:

```python
        allowed = set(
            self.allowed_tool_names(current_mode, workflow_state=workflow_state)
        )
```

In `src/embedagent/query_engine.py`, pass the extension-aware policy when constructing `TurnOrchestrator`:

```python
            allowed_tool_names=self._allowed_tools_for_mode,
```

- [ ] **Step 4: Remove runtime compatibility wrappers**

Delete `ToolRuntime.allowed_tool_names(...)` from `src/embedagent/tools/runtime.py`.

Delete `OfficialRuntimeModes.allowed_tool_names(...)` from `src/embedagent/tools/harness_runtime.py` after this search has no live callers:

```powershell
rg -n "allowed_tool_names\\(" src tests -g "*.py"
```

Expected remaining matches:
- `src/embedagent/extensions.py`
- `src/embedagent/harness/extension.py`
- `src/embedagent/query_engine.py`
- tests that exercise extension active tools

- [ ] **Step 5: Update runtime tests**

Remove `test_allowed_tool_names_default_to_mode_contract` from `tests/test_tools_package.py`.

Append this source-boundary test to `tests/test_workflow_extensions.py`:

```python
def test_tool_runtime_no_longer_exposes_allowed_tool_names_alias():
    source = (
        _REPO_ROOT / "src" / "embedagent" / "tools" / "runtime.py"
    ).read_text(encoding="utf-8")

    assert "def allowed_tool_names" not in source
```

- [ ] **Step 6: Verify and commit**

Run:

```powershell
uv run pytest tests/test_strategies.py tests/test_tools_package.py tests/test_workflow_extensions.py -v
uv run pytest tests/ -m "not slow and not gui" -v --basetemp "$tmp\basetemp-remove-allowed-tool-wrapper"
git diff --check
```

Expected: PASS.

Commit:

```powershell
git add src/embedagent/strategies/turn_orchestrator.py src/embedagent/query_engine.py src/embedagent/tools/runtime.py src/embedagent/tools/harness_runtime.py tests/test_strategies.py tests/test_tools_package.py tests/test_workflow_extensions.py docs/tool-contracts.md docs/mode-schema.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md
git commit -m "refactor: inject allowed tool policy into turn orchestration"
```

### Task 5: Close The Default Extension Configuration Decision

**Files:**
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify tests only when the audit finds a real product need for disabling the built-in C harness.

- [ ] **Step 1: Audit hosted and bare construction paths**

Run:

```powershell
rg -n "build_default_extension_set|ExtensionManager\\(|CHarnessWorkflowExtension\\(|extension_manager" src tests -g "*.py"
```

Expected:
- Hosted product paths use `build_default_extension_set(...)`.
- Bare `QueryEngine` construction defaults to an empty `ExtensionManager`.
- Direct tests that need C harness behavior pass an explicit `ExtensionManager`.

- [ ] **Step 2: Keep configuration deferred unless a failing product test requires it**

The durable decision text for docs is:

```markdown
Default C/C++ harness installation is a host assembly concern, not a project-local plugin discovery mechanism. `InProcessAdapter` installs the bundled default extension set for product paths. Bare `QueryEngine` hosts receive an empty `ExtensionManager` unless they explicitly pass extensions. Project-local extension discovery, remote registries, and plugin marketplaces remain out of scope.
```

- [ ] **Step 3: Add a focused test only when the audit finds a missing seam**

If a test needs a hosted adapter with no bundled harness, add this explicit constructor seam instead of adding project-local discovery:

```python
adapter = InProcessAdapter(
    tools=ToolRuntime(str(tmp_path)),
    extension_manager=ExtensionManager(),
)
```

The expected behavior is that `adapter.extension_manager.allowed_tool_names("build")` returns only the supplied extension tools plus any fallback provided by the caller, not implicit bundled harness tools.

- [ ] **Step 4: Verify and commit the decision**

Run:

```powershell
uv run pytest tests/test_workflow_extensions.py tests/test_query_engine_refactor.py -v
git diff --check
```

Expected: PASS.

Commit docs and any focused test changes:

```powershell
git add docs/implementation-roadmap.md docs/overall-solution-architecture.md docs/agent-harness-v2.md docs/development-tracker.md docs/design-change-log.md tests/test_workflow_extensions.py
git commit -m "docs: close default extension configuration decision"
```

### Task 6: Archive Completed Workflow-Extension Slice Documents

**Files:**
- Create: `docs/archive/workflow-extension-boundary/README.md`
- Move: `docs/superpowers/plans/2026-05-26-workflow-extension-boundary-slice1.md`
- Move: `docs/superpowers/plans/2026-05-26-workflow-extension-boundary-slice2.md`
- Move: `docs/superpowers/plans/2026-05-27-workflow-extension-boundary-slice3.md`
- Move: `docs/superpowers/plans/2026-05-27-workflow-extension-boundary-slice4.md`
- Move: `docs/superpowers/plans/2026-05-27-workflow-extension-boundary-slice5.md`
- Move: `docs/superpowers/plans/2026-05-27-workflow-extension-boundary-slice6.md`
- Move: `docs/superpowers/plans/2026-05-28-runtime-schema-boundary-slice7.md`
- Move: `docs/superpowers/plans/2026-05-28-default-harness-extension-factory-slice8.md`
- Move: `docs/superpowers/plans/2026-05-28-harness-workflow-projection-builder-slice9.md`
- Move: `docs/superpowers/plans/2026-05-28-session-task-graph-lazy-boundary-slice10.md`
- Move: `docs/superpowers/plans/2026-05-28-turn-orchestrator-task-status-projection-slice11.md`
- Move this handoff plan after Tasks 1-5 are complete.
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Create archive index**

Create `docs/archive/workflow-extension-boundary/README.md`:

```markdown
# Workflow Extension Boundary Archive

This directory preserves completed workflow-extension migration design and implementation plans.

Durable architecture truth now lives in:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/agent-harness-v2.md`
- `docs/implementation-roadmap.md`
- `docs/tool-contracts.md`
- `docs/mode-schema.md`

The active migration closed after Agent Core stopped owning default C/C++ harness construction, task graph storage, and runtime schema activation.
```

- [ ] **Step 2: Move completed plans**

Use `Move-Item` with literal paths from the file list above. Keep `docs/superpowers/plans/2026-05-28-remaining-workflow-extension-migration-plan.md` active only if any release validation remains open.

- [ ] **Step 3: Verify no active docs point at moved paths**

Run:

```powershell
rg -n "2026-05-2[678]-.*workflow-extension|runtime-schema-boundary|session-task-graph-lazy|turn-orchestrator-task-status|default-harness-extension|harness-workflow-projection" README.md AGENTS.md docs -g "!docs/archive/**"
```

Expected: active docs either point to `docs/archive/workflow-extension-boundary/` or describe durable conclusions without linking old active plan paths.

- [ ] **Step 4: Commit**

Run:

```powershell
git status --short
git diff --check
```

Expected: only archive moves and tracker/change-log updates are staged.

Commit:

```powershell
git add docs/archive/workflow-extension-boundary docs/development-tracker.md docs/design-change-log.md
git add -u docs/superpowers/plans
git commit -m "docs: archive workflow extension migration plans"
```

### Task 7: Product Target Validation Before Release

**Files:**
- Modify only validation notes in `docs/development-tracker.md` and `docs/design-change-log.md`.

- [ ] **Step 1: Run fast and harness suites**

Run:

```powershell
uv run pytest tests/ -m "not slow and not gui" -v --basetemp "$tmp\basetemp-release-fast"
uv run pytest tests/ -m harness -v --basetemp "$tmp\basetemp-release-harness"
```

Expected:
- Fast suite passes.
- Harness suite passes.

- [ ] **Step 2: Run focused C/C++ workflow regression tests**

Run:

```powershell
uv run pytest tests/test_query_engine_build_lite.py tests/test_query_engine_build_full_spec.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApi::test_workspace_recipe_api_detects_cmake -v
```

Expected: PASS.

- [ ] **Step 3: Run offline bundle and Windows 7 validation**

Use the repository's release validation procedure for the current package target. Record:

```markdown
- Python embeddable runtime present
- vendored Python packages present
- MinGit portable present
- ripgrep present
- Universal Ctags present
- Clang runtime tools present
- clean Windows 7 unpack-and-run smoke test passed
```

If a tool is missing from the bundle, treat it as a release-blocking defect.

- [ ] **Step 4: Commit validation notes**

Run:

```powershell
git add docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record workflow extension release validation"
```

## Handoff Checklist

- [ ] Each task above is implemented in its own commit.
- [ ] `rg -n "HarnessStateSynchronizer|harness_state_synchronizer" src tests` returns no matches.
- [ ] `rg -n "schemas_for_mode" src tests` returns no matches.
- [ ] `rg -n "def allowed_tool_names" src/embedagent/tools src/embedagent/strategies tests` does not show `ToolRuntime` or `TurnOrchestrator` compatibility wrappers.
- [ ] `rg -n "session\\.task_graph|Session\\.task_graph" src tests -g "*.py"` returns only archived historical references or no matches.
- [ ] `uv run pytest tests/ -m "not slow and not gui" -v` passes.
- [ ] Global docs and active plan docs agree on the same architecture vocabulary.
