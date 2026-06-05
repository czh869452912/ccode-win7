# Capability Extension Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first self-extensible Agent Core slice by adding a general extension event contract, diagnostics, resource discovery hooks, context/tool hooks, and snapshot diagnostics without enabling project-local code loading.

**Architecture:** Keep `ExtensionManager` as the shared in-process extension host, but evolve it from a C harness workflow boundary into a capability event runtime. The bundled C/C++ harness keeps working through existing hooks while new generic hooks are added around context assembly, tool calls, tool results, resource discovery, and snapshot projection.

**Tech Stack:** Python 3.8, dataclasses, existing `Session`, `QueryEngine`, `SessionSnapshotProjector`, `InProcessAdapter`, pytest.

---

## Scope

This plan implements Slice 1 from `docs/superpowers/specs/2026-06-04-self-extensible-agent-core-design.md`.

Included:

- extension diagnostics
- typed resource discovery event/result
- generic context transform hook
- generic tool call decision hook
- generic tool result patch hook
- snapshot projection of extension state and diagnostics
- source-of-truth documentation alignment for this first slice

Excluded:

- dynamic tool registration
- project-local `extension.py` loading
- skill/prompt/recipe filesystem discovery
- extension reload command/API
- custom model provider registration
- `QueryEngine` extraction into a standalone agent loop

## File Structure

- `src/embedagent/extensions.py`
  Owns extension dataclasses, diagnostics, hook dispatch, result merging, and compatibility with existing C harness workflow hooks.

- `src/embedagent/query_engine.py`
  Calls extension context, tool-call, and tool-result hooks at the existing execution boundaries.

- `src/embedagent/session_projector.py`
  Projects extension state and diagnostics into session snapshots.

- `src/embedagent/inprocess_adapter.py`
  Supplies extension diagnostics to the snapshot projector from the hosted shared `ExtensionManager`.

- `tests/test_capability_extensions.py`
  New focused tests for generic extension capability behavior.

- `tests/test_workflow_extensions.py`
  Existing workflow-boundary tests stay green. Add only compatibility tests here if a behavior already belongs to that file.

- `docs/overall-solution-architecture.md`
  Records that the extension boundary is growing into a local capability runtime while project-local code loading remains out of this slice.

- `docs/tool-contracts.md`
  Records that tool-call and tool-result interception are extension-runtime hooks but execution remains permission-gated.

- `docs/development-tracker.md`
  Adds a short implementation note for the Slice 1 capability extension contract.

- `docs/design-change-log.md`
  Adds a dated design-change entry for the Slice 1 capability extension contract.

---

### Task 1: Extension Diagnostics And Safe Hook Dispatch

**Files:**
- Modify: `src/embedagent/extensions.py`
- Create: `tests/test_capability_extensions.py`

- [x] **Step 1: Write failing tests for diagnostics and hook error isolation**

Create `tests/test_capability_extensions.py` with:

```python
from embedagent.extensions import ExtensionContext, ExtensionManager, WorkflowEvent


class BrokenProjectExtension(object):
    extension_id = "broken_project"
    builtin_extension = False

    def context(self, event, context):
        del event, context
        raise RuntimeError("project hook failed")


class BrokenBuiltinExtension(object):
    extension_id = "broken_builtin"
    builtin_extension = True

    def context(self, event, context):
        del event, context
        raise RuntimeError("builtin hook failed")


def test_project_extension_hook_error_is_recorded_and_isolated():
    manager = ExtensionManager([BrokenProjectExtension()])

    patch = manager.context(
        WorkflowEvent(current_mode="build"),
        ExtensionContext(workspace="."),
    )

    diagnostics = manager.diagnostics()
    assert patch.messages == []
    assert len(diagnostics) == 1
    assert diagnostics[0]["extension_id"] == "broken_project"
    assert diagnostics[0]["event"] == "context"
    assert diagnostics[0]["error"] == "project hook failed"
    assert diagnostics[0]["severity"] == "error"


def test_builtin_extension_hook_error_is_recorded_and_raised():
    manager = ExtensionManager([BrokenBuiltinExtension()])

    try:
        manager.context(
            WorkflowEvent(current_mode="build"),
            ExtensionContext(workspace="."),
        )
    except RuntimeError as exc:
        assert str(exc) == "builtin hook failed"
    else:
        raise AssertionError("built-in extension error should fail closed")

    diagnostics = manager.diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0]["extension_id"] == "broken_builtin"
    assert diagnostics[0]["event"] == "context"
```

- [x] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/test_capability_extensions.py -v
```

Expected: FAIL because `ExtensionManager.context` and `ExtensionManager.diagnostics` do not exist.

- [x] **Step 3: Add diagnostics dataclass and hook helper**

Modify `src/embedagent/extensions.py`.

First, add a string workflow-state name to `WorkflowEvent` while keeping the existing dict payload for compatibility:

```python
@dataclass
class WorkflowEvent:
    session_id: str = ""
    turn_id: str = ""
    step_id: str = ""
    current_mode: str = ""
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    workflow_state_name: str = ""
    user_text: str = ""
    tool_name: str = ""
    tool_arguments: Dict[str, Any] = field(default_factory=dict)
    observation: Any = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

Then add this dataclass after `WorkflowPatch`:

```python
@dataclass
class ExtensionDiagnostic:
    extension_id: str = ""
    event: str = ""
    error: str = ""
    severity: str = "error"
    source: str = "extension"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "extension_id": self.extension_id,
            "event": self.event,
            "error": self.error,
            "severity": self.severity,
            "source": self.source,
            "metadata": dict(self.metadata),
        }
```

Update `ExtensionManager.__init__` and add helper methods:

```python
class ExtensionManager(object):
    def __init__(self, extensions: Optional[List[Any]] = None) -> None:
        self._extensions = []  # type: List[Any]
        self._diagnostics = []  # type: List[ExtensionDiagnostic]
        for extension in list(extensions or []):
            self.register(extension)

    def register(self, extension: Any) -> None:
        self._extensions.append(extension)

    def diagnostics(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self._diagnostics]

    def clear_diagnostics(self) -> None:
        self._diagnostics = []

    def _extension_id(self, extension: Any) -> str:
        explicit = str(getattr(extension, "extension_id", "") or "").strip()
        if explicit:
            return explicit
        name = getattr(extension.__class__, "__name__", "")
        return str(name or "extension")

    def _is_builtin_extension(self, extension: Any) -> bool:
        return bool(getattr(extension, "builtin_extension", True))

    def _record_hook_error(self, extension: Any, event_name: str, exc: Exception) -> None:
        self._diagnostics.append(
            ExtensionDiagnostic(
                extension_id=self._extension_id(extension),
                event=event_name,
                error=str(exc),
                severity="error",
                source="builtin" if self._is_builtin_extension(extension) else "project",
            )
        )

    def _call_hook(self, extension: Any, event_name: str, *args: Any, **kwargs: Any) -> Any:
        hook = getattr(extension, event_name, None)
        if not callable(hook):
            return None
        try:
            return hook(*args, **kwargs)
        except Exception as exc:
            self._record_hook_error(extension, event_name, exc)
            if self._is_builtin_extension(extension):
                raise
            return None
```

- [x] **Step 4: Add the generic context hook dispatcher**

Add this method to `ExtensionManager`:

```python
    def context(
        self,
        event: WorkflowEvent,
        context: ExtensionContext,
    ) -> ContextPatch:
        merged = ContextPatch()
        for extension in list(self._extensions):
            patch = self._call_hook(extension, "context", event, context)
            if patch is None:
                continue
            messages = list(getattr(patch, "messages", []) or [])
            if messages:
                merged.messages = messages
            merged.metadata.update(dict(getattr(patch, "metadata", {}) or {}))
        return merged
```

- [x] **Step 5: Run the new tests and verify they pass**

Run:

```bash
uv run pytest tests/test_capability_extensions.py -v
```

Expected: PASS for the two diagnostics tests.

- [x] **Step 6: Run existing workflow extension tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py -v
```

Expected: PASS. Existing harness workflow extension behavior remains unchanged.

- [x] **Step 7: Commit Task 1**

```bash
git add src/embedagent/extensions.py tests/test_capability_extensions.py
git commit -m "feat: add extension diagnostics"
```

---

### Task 2: Resource Discovery Event Contract

**Files:**
- Modify: `src/embedagent/extensions.py`
- Modify: `tests/test_capability_extensions.py`

- [x] **Step 1: Write failing tests for resource discovery merging**

Add `ResourcesDiscoverResult` to the existing top-level import from `embedagent.extensions`, then append this test code to `tests/test_capability_extensions.py`:

```python
class ResourceExtension(object):
    extension_id = "resources"
    builtin_extension = False

    def resources_discover(self, event, context):
        assert event.cwd == "."
        assert event.reason == "startup"
        assert context.workspace == "."
        return ResourcesDiscoverResult(
            skill_paths=[".embedagent/skills", ".embedagent/skills"],
            prompt_paths=[".embedagent/prompts"],
            recipe_paths=[".embedagent/recipes"],
            metadata={"source": "resource-extension"},
        )


def test_resources_discover_merges_and_deduplicates_paths():
    manager = ExtensionManager([ResourceExtension()])

    result = manager.discover_resources(".", reason="startup")

    assert result.skill_paths == [".embedagent/skills"]
    assert result.prompt_paths == [".embedagent/prompts"]
    assert result.recipe_paths == [".embedagent/recipes"]
    assert result.metadata == {"source": "resource-extension"}
```

- [x] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_resources_discover_merges_and_deduplicates_paths -v
```

Expected: FAIL because `ResourcesDiscoverResult` and `discover_resources` do not exist.

- [x] **Step 3: Add resource event/result dataclasses**

In `src/embedagent/extensions.py`, add these dataclasses after `ExtensionDiagnostic`:

```python
@dataclass
class ResourcesDiscoverEvent:
    cwd: str = ""
    reason: str = "startup"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourcesDiscoverResult:
    skill_paths: List[str] = field(default_factory=list)
    prompt_paths: List[str] = field(default_factory=list)
    recipe_paths: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

- [x] **Step 4: Add path dedupe helper and discovery dispatcher**

Add these methods to `ExtensionManager`:

```python
    def _append_unique(self, target: List[str], values: List[str]) -> None:
        seen = set(target)
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            target.append(text)

    def discover_resources(self, cwd: str, reason: str = "startup") -> ResourcesDiscoverResult:
        event = ResourcesDiscoverEvent(cwd=str(cwd or ""), reason=str(reason or "startup"))
        context = ExtensionContext(workspace=str(cwd or ""))
        merged = ResourcesDiscoverResult()
        for extension in list(self._extensions):
            result = self._call_hook(extension, "resources_discover", event, context)
            if result is None:
                continue
            self._append_unique(merged.skill_paths, list(getattr(result, "skill_paths", []) or []))
            self._append_unique(merged.prompt_paths, list(getattr(result, "prompt_paths", []) or []))
            self._append_unique(merged.recipe_paths, list(getattr(result, "recipe_paths", []) or []))
            merged.metadata.update(dict(getattr(result, "metadata", {}) or {}))
        return merged
```

- [x] **Step 5: Run resource discovery test**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_resources_discover_merges_and_deduplicates_paths -v
```

Expected: PASS.

- [x] **Step 6: Run all capability extension tests**

Run:

```bash
uv run pytest tests/test_capability_extensions.py -v
```

Expected: PASS.

- [x] **Step 7: Commit Task 2**

```bash
git add src/embedagent/extensions.py tests/test_capability_extensions.py
git commit -m "feat: add extension resource discovery contract"
```

---

### Task 3: Context Hook Integration In QueryEngine

**Files:**
- Modify: `src/embedagent/extensions.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_capability_extensions.py`

- [x] **Step 1: Write failing integration test for context injection**

Add `AssistantReply` to the top-level imports from `embedagent.session`, then append this test code to `tests/test_capability_extensions.py`:

```python
class CapturingClient(object):
    def __init__(self):
        self.messages = []

    def generate(self, messages, tools=None):
        del tools
        self.messages = list(messages)
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        if on_reasoning_delta is not None:
            on_reasoning_delta(reply.reasoning_content)
        return reply


class ContextInjectingExtension(object):
    extension_id = "context_injector"
    builtin_extension = False

    def context(self, event, context):
        from embedagent.extensions import ContextPatch

        assert event.current_mode == "build"
        assert context.workspace
        messages = list(event.messages)
        messages.append({"role": "system", "content": "extension context note"})
        return ContextPatch(messages=messages, metadata={"changed": True})


def test_query_engine_applies_extension_context_patch(tmp_path):
    from embedagent.extensions import ExtensionManager
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    client = CapturingClient()
    tools = ToolRuntime(str(tmp_path))
    manager = ExtensionManager([ContextInjectingExtension()])
    engine = QueryEngine(
        client=client,
        tools=tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        extension_manager=manager,
    )

    engine.submit_user_turn(
        user_text="read context",
        stream=False,
        initial_mode="build",
    )

    assert {"role": "system", "content": "extension context note"} in client.messages
```

- [x] **Step 2: Run the integration test and verify it fails**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_query_engine_applies_extension_context_patch -v
```

Expected: FAIL because `QueryEngine._build_context` does not call the extension context hook.

- [x] **Step 3: Import extension types in QueryEngine**

Modify the existing import in `src/embedagent/query_engine.py`:

```python
from embedagent.extensions import (
    ExtensionContext,
    ExtensionManager,
    SessionView,
    WorkflowEvent,
)
```

- [x] **Step 4: Add helper for extension context and event creation**

Add these methods inside `QueryEngine`, near `_allowed_tools_for_mode`:

```python
    def _extension_context(self, session: Session) -> ExtensionContext:
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

    def _workflow_event(
        self,
        session: Session,
        current_mode: str,
        workflow_state: str,
        **metadata: Any,
    ) -> WorkflowEvent:
        turn_id = session.turns[-1].turn_id if session.turns else ""
        step_id = session.current_step().step_id if session.current_step() else ""
        return WorkflowEvent(
            session_id=session.session_id,
            turn_id=turn_id,
            step_id=step_id,
            current_mode=current_mode,
            workflow_state=dict(getattr(session, "workflow_state", {}) or {}),
            workflow_state_name=workflow_state,
            metadata=dict(metadata),
        )
```

- [x] **Step 5: Apply context patch in `_build_context`**

In `QueryEngine._build_context`, after the `assembly` object is built, add:

```python
        event = self._workflow_event(
            session,
            mode_name,
            workflow_state,
            force_compact=force_compact,
        )
        event.messages = [dict(message) for message in list(assembly.messages or [])]
        patch = self.extension_manager.context(event, self._extension_context(session))
        if patch.messages:
            assembly.messages = [dict(message) for message in patch.messages]
```

Keep the existing `return assembly`.

- [x] **Step 6: Run the context integration test**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_query_engine_applies_extension_context_patch -v
```

Expected: PASS.

- [x] **Step 7: Run focused query-engine workflow tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py::test_c_harness_extension_preserves_build_prompt_behavior tests/test_query_engine_refactor.py -q
```

Expected: PASS. The C harness prompt path and existing query-engine behavior remain compatible.

- [x] **Step 8: Commit Task 3**

```bash
git add src/embedagent/extensions.py src/embedagent/query_engine.py tests/test_capability_extensions.py
git commit -m "feat: route context through extension hooks"
```

---

### Task 4: Tool Call And Tool Result Hook Integration

**Files:**
- Modify: `src/embedagent/extensions.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_capability_extensions.py`

- [x] **Step 1: Write failing manager tests for tool call and result hooks**

Add `ToolCallDecision` and `ToolResultPatch` to the existing top-level import from `embedagent.extensions`. Add `Observation` to the top-level imports from `embedagent.session`. Then append this test code to `tests/test_capability_extensions.py`:

```python
class ToolPolicyExtension(object):
    extension_id = "tool_policy"
    builtin_extension = False

    def tool_call(self, event, context):
        del context
        if event.tool_name == "blocked_tool":
            return ToolCallDecision(block=True, reason="blocked by extension")
        updated = dict(event.tool_arguments)
        updated["path"] = "redirected.txt"
        return ToolCallDecision(updated_arguments=updated, metadata={"rewritten": True})

    def tool_result(self, event, context):
        del context
        return ToolResultPatch(
            observation=Observation(
                tool_name=event.tool_name,
                success=True,
                error=None,
                data={"patched": True},
            )
        )


def test_tool_call_hook_blocks_or_rewrites_arguments():
    manager = ExtensionManager([ToolPolicyExtension()])

    blocked = manager.before_tool_call(
        WorkflowEvent(tool_name="blocked_tool", tool_arguments={}),
        ExtensionContext(workspace="."),
    )
    rewritten = manager.before_tool_call(
        WorkflowEvent(tool_name="read_file", tool_arguments={"path": "original.txt"}),
        ExtensionContext(workspace="."),
    )

    assert blocked.block is True
    assert blocked.reason == "blocked by extension"
    assert rewritten.updated_arguments == {"path": "redirected.txt"}
    assert rewritten.metadata == {"rewritten": True}


def test_tool_result_hook_can_replace_observation():
    manager = ExtensionManager([ToolPolicyExtension()])

    patch = manager.after_tool_result(
        WorkflowEvent(
            tool_name="read_file",
            observation=Observation("read_file", True, None, {"original": True}),
        ),
        ExtensionContext(workspace="."),
    )

    assert patch.observation.success is True
    assert patch.observation.data == {"patched": True}
```

- [x] **Step 2: Run manager tests and verify they fail**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_tool_call_hook_blocks_or_rewrites_arguments tests/test_capability_extensions.py::test_tool_result_hook_can_replace_observation -v
```

Expected: FAIL because `before_tool_call` and `after_tool_result` do not exist.

- [x] **Step 3: Add hook dispatch methods**

Add these methods to `ExtensionManager`:

```python
    def before_tool_call(
        self,
        event: WorkflowEvent,
        context: ExtensionContext,
    ) -> ToolCallDecision:
        merged = ToolCallDecision()
        for extension in list(self._extensions):
            decision = self._call_hook(extension, "tool_call", event, context)
            if decision is None:
                continue
            if bool(getattr(decision, "block", False)):
                merged.block = True
                merged.reason = str(getattr(decision, "reason", "") or "")
                merged.metadata.update(dict(getattr(decision, "metadata", {}) or {}))
                return merged
            updated = getattr(decision, "updated_arguments", None)
            if updated is not None:
                merged.updated_arguments = dict(updated)
            merged.metadata.update(dict(getattr(decision, "metadata", {}) or {}))
        return merged

    def after_tool_result(
        self,
        event: WorkflowEvent,
        context: ExtensionContext,
    ) -> ToolResultPatch:
        merged = ToolResultPatch()
        for extension in list(self._extensions):
            patch = self._call_hook(extension, "tool_result", event, context)
            if patch is None:
                continue
            observation = getattr(patch, "observation", None)
            if observation is not None:
                merged.observation = observation
            workflow_patch = getattr(patch, "workflow_patch", None)
            if workflow_patch is not None:
                merged.workflow_patch = workflow_patch
            merged.metadata.update(dict(getattr(patch, "metadata", {}) or {}))
        return merged
```

- [x] **Step 4: Run manager tests and verify they pass**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_tool_call_hook_blocks_or_rewrites_arguments tests/test_capability_extensions.py::test_tool_result_hook_can_replace_observation -v
```

Expected: PASS.

- [x] **Step 5: Write failing QueryEngine integration tests**

Add `Action` to the top-level imports from `embedagent.session`, then append this test code to `tests/test_capability_extensions.py`:

```python
class ToolCallingClient(object):
    def __init__(self, action):
        self.action = action

    def generate(self, messages, tools=None):
        del messages, tools
        return AssistantReply(
            content="using tool",
            actions=[self.action],
            finish_reason="tool_calls",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        if on_reasoning_delta is not None:
            on_reasoning_delta(reply.reasoning_content)
        return reply


class BlockingToolExtension(object):
    extension_id = "blocking_tool"
    builtin_extension = False

    def tool_call(self, event, context):
        del context
        if event.tool_name == "read_file":
            return ToolCallDecision(block=True, reason="blocked by extension")
        return None


class PatchingToolResultExtension(object):
    extension_id = "patching_tool_result"
    builtin_extension = False

    def tool_result(self, event, context):
        del context
        return ToolResultPatch(
            observation=Observation(
                event.tool_name,
                True,
                None,
                {"patched_by_extension": True},
            )
        )


def test_query_engine_tool_call_hook_can_block_tool_execution(tmp_path):
    from embedagent.extensions import ExtensionManager
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    target = tmp_path / "blocked.txt"
    target.write_text("blocked", encoding="utf-8")
    action = Action("read_file", {"path": "blocked.txt"}, "call-read")
    engine = QueryEngine(
        client=ToolCallingClient(action),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        extension_manager=ExtensionManager([BlockingToolExtension()]),
        max_turns=1,
    )

    result = engine.submit_user_turn("read file", stream=False, initial_mode="build")
    observation = result.session.turns[-1].observations[-1]

    assert observation.success is False
    assert observation.error == "blocked by extension"
    assert observation.data["error_kind"] == "extension_blocked"


def test_query_engine_tool_result_hook_can_replace_observation(tmp_path):
    from embedagent.extensions import ExtensionManager
    from embedagent.permissions import PermissionPolicy
    from embedagent.query_engine import QueryEngine
    from embedagent.tools import ToolRuntime

    target = tmp_path / "readme.txt"
    target.write_text("hello", encoding="utf-8")
    action = Action("read_file", {"path": "readme.txt"}, "call-read")
    engine = QueryEngine(
        client=ToolCallingClient(action),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
        extension_manager=ExtensionManager([PatchingToolResultExtension()]),
        max_turns=1,
    )

    result = engine.submit_user_turn("read file", stream=False, initial_mode="build")
    observation = result.session.turns[-1].observations[-1]

    assert observation.success is True
    assert observation.data == {"patched_by_extension": True}
```

- [x] **Step 6: Run integration tests and verify they fail**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_query_engine_tool_call_hook_can_block_tool_execution tests/test_capability_extensions.py::test_query_engine_tool_result_hook_can_replace_observation -v
```

Expected: FAIL because `QueryEngine._execute_action` does not call the new generic hooks.

- [x] **Step 7: Apply tool call decision in `_execute_action`**

In `QueryEngine._execute_action`, after the allowed-tool check and before the `task_status` special case, add:

```python
        tool_event = self._workflow_event(session, current_mode, workflow_state)
        tool_event.tool_name = action.name
        tool_event.tool_arguments = dict(action.arguments)
        decision = self.extension_manager.before_tool_call(
            tool_event,
            self._extension_context(session),
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
                current_mode,
                None,
            )
        if decision.updated_arguments is not None:
            runtime_action = Action(
                name=action.name,
                arguments=dict(decision.updated_arguments),
                call_id=action.call_id,
                raw_arguments=action.raw_arguments,
            )
```

When later code reads arguments for `ask_user` and `propose_mode_switch`, use `runtime_action.arguments` instead of `action.arguments`.

Replace:

```python
            request = build_user_input_request(action.arguments)
```

with:

```python
            request = build_user_input_request(runtime_action.arguments)
```

Replace each `action.arguments.get(...)` inside the `propose_mode_switch` block with `runtime_action.arguments.get(...)`.

- [x] **Step 8: Apply tool result patch after execution**

Near the end of `QueryEngine._execute_action`, replace the final return:

```python
        return (
            precomputed_observation
            or self.tools.execute_with_interrupt(
                runtime_action.name, runtime_action.arguments, stop_event
            ),
            current_mode,
            None,
        )
```

with:

```python
        observation = precomputed_observation or self.tools.execute_with_interrupt(
            runtime_action.name, runtime_action.arguments, stop_event
        )
        result_event = self._workflow_event(session, current_mode, workflow_state)
        result_event.tool_name = runtime_action.name
        result_event.tool_arguments = dict(runtime_action.arguments)
        result_event.observation = observation
        patch = self.extension_manager.after_tool_result(
            result_event,
            self._extension_context(session),
        )
        if patch.workflow_patch is not None:
            workflow_patch = patch.workflow_patch
            if workflow_patch.workflow:
                session.workflow_state["workflow"] = dict(workflow_patch.workflow)
            if workflow_patch.metadata:
                extensions = session.workflow_state.setdefault("extensions", {})
                extensions["last_workflow_patch"] = dict(workflow_patch.metadata)
        if patch.observation is not None:
            observation = patch.observation
        return observation, current_mode, None
```

- [x] **Step 9: Run tool hook integration tests**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_query_engine_tool_call_hook_can_block_tool_execution tests/test_capability_extensions.py::test_query_engine_tool_result_hook_can_replace_observation -v
```

Expected: PASS.

- [x] **Step 10: Run broader focused tests**

Run:

```bash
uv run pytest tests/test_capability_extensions.py tests/test_workflow_extensions.py tests/test_query_engine_refactor.py -v
```

Expected: PASS.

- [x] **Step 11: Commit Task 4**

```bash
git add src/embedagent/extensions.py src/embedagent/query_engine.py tests/test_capability_extensions.py
git commit -m "feat: add extension tool hooks"
```

---

### Task 5: Snapshot Projection Of Extension State And Diagnostics

**Files:**
- Modify: `src/embedagent/session_projector.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `tests/test_capability_extensions.py`

- [x] **Step 1: Write failing snapshot projector test**

Append to `tests/test_capability_extensions.py`:

```python
def test_session_snapshot_projects_extension_state_and_diagnostics():
    from embedagent.session import Session
    from embedagent.session_projector import SessionSnapshotProjector
    from embedagent.session_runtime import ManagedSession

    session = Session()
    session.workflow_state["extensions"] = {
        "sample": {"state": {"enabled": True}},
    }
    state = ManagedSession(session=session, current_mode="build")

    snapshot = SessionSnapshotProjector().build_snapshot(
        state,
        summary={},
        runtime={},
        extension_diagnostics=[
            {
                "extension_id": "sample",
                "event": "context",
                "error": "sample error",
                "severity": "error",
                "source": "project",
                "metadata": {},
            }
        ],
    )

    assert snapshot["extensions"] == {"sample": {"state": {"enabled": True}}}
    assert snapshot["extension_diagnostics"][0]["extension_id"] == "sample"
    assert snapshot["extension_diagnostics"][0]["error"] == "sample error"
```

- [x] **Step 2: Run snapshot projector test and verify it fails**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_session_snapshot_projects_extension_state_and_diagnostics -v
```

Expected: FAIL because `build_snapshot` does not accept `extension_diagnostics`.

- [x] **Step 3: Update SessionSnapshotProjector signature and output**

In `src/embedagent/session_projector.py`, change the method signature:

```python
    def build_snapshot(
        self,
        state: Any,
        summary: Optional[Dict[str, Any]],
        runtime: Optional[Dict[str, Any]],
        pending_interaction: Optional[Dict[str, Any]] = None,
        harness_context: Optional[Any] = None,
        extension_diagnostics: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
```

Before `return`, compute:

```python
        workflow_state = getattr(state.session, "workflow_state", {}) or {}
        extensions = {}
        if isinstance(workflow_state, dict):
            raw_extensions = workflow_state.get("extensions") or {}
            if isinstance(raw_extensions, dict):
                extensions = dict(raw_extensions)
```

Add these fields to the returned dictionary:

```python
            "extensions": extensions,
            "extension_diagnostics": list(extension_diagnostics or []),
```

- [x] **Step 4: Run snapshot projector test**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_session_snapshot_projects_extension_state_and_diagnostics -v
```

Expected: PASS.

- [x] **Step 5: Write failing InProcessAdapter snapshot test**

Append to `tests/test_capability_extensions.py`:

```python
class SnapshotBrokenExtension(object):
    extension_id = "snapshot_broken"
    builtin_extension = False

    def context(self, event, context):
        del event, context
        raise RuntimeError("snapshot diagnostic")


def test_inprocess_snapshot_includes_extension_diagnostics(tmp_path):
    from embedagent.extensions import ExtensionContext, ExtensionManager, WorkflowEvent
    from embedagent.inprocess_adapter import InProcessAdapter
    from embedagent.tools import ToolRuntime

    adapter = InProcessAdapter(tools=ToolRuntime(str(tmp_path)))
    adapter.extension_manager = ExtensionManager([SnapshotBrokenExtension()])
    adapter.extension_manager.context(
        WorkflowEvent(current_mode="build"),
        ExtensionContext(workspace=str(tmp_path)),
    )
    snapshot = adapter.create_session(mode="build")

    diagnostics = snapshot.get("extension_diagnostics") or []
    assert diagnostics
    assert diagnostics[0]["extension_id"] == "snapshot_broken"
    assert diagnostics[0]["error"] == "snapshot diagnostic"
```

- [x] **Step 6: Run InProcessAdapter snapshot test and verify it fails**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_inprocess_snapshot_includes_extension_diagnostics -v
```

Expected: FAIL because `InProcessAdapter.get_session_snapshot` does not pass diagnostics into the projector.

- [x] **Step 7: Pass diagnostics from InProcessAdapter**

In `src/embedagent/inprocess_adapter.py`, update the `build_snapshot` call in `get_session_snapshot`:

```python
            return self.snapshot_projector.build_snapshot(
                state,
                summary,
                runtime,
                pending_interaction=_pending_interaction_payload(state),
                extension_diagnostics=self.extension_manager.diagnostics(),
            )
```

- [x] **Step 8: Run snapshot tests**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_session_snapshot_projects_extension_state_and_diagnostics tests/test_capability_extensions.py::test_inprocess_snapshot_includes_extension_diagnostics -v
```

Expected: PASS.

- [x] **Step 9: Run frontend adapter snapshot tests**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py tests/test_gui_backend_api.py -v
```

Expected: PASS. Existing snapshot consumers tolerate the new fields.

- [x] **Step 10: Commit Task 5**

```bash
git add src/embedagent/session_projector.py src/embedagent/inprocess_adapter.py tests/test_capability_extensions.py
git commit -m "feat: project extension diagnostics in snapshots"
```

---

### Task 6: Source-Of-Truth Documentation Alignment

**Files:**
- Modify: `README.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [x] **Step 1: Update README architecture bullets**

In `README.md`, add a bullet near the current extension-manager bullets:

```markdown
- Official extension runtime direction: `ExtensionManager` is the shared in-process capability boundary for workflow defaults, prompt/context hooks, tool-call/tool-result hooks, resource discovery contracts, and extension diagnostics; project-local Python code loading remains deferred.
```

- [x] **Step 2: Update overall architecture**

In `docs/overall-solution-architecture.md`, update the Agent Core Layer section with:

```markdown
`ExtensionManager` is now the shared in-process capability boundary. The current default C/C++ harness remains the bundled workflow extension, while the same boundary also carries generic prompt/context hooks, tool-call and tool-result interception, resource discovery contracts, and extension diagnostics. Project-local Python extension loading is not enabled in this slice; only the contract and built-in/injected extension path are official.
```

- [x] **Step 3: Update tool contracts**

In `docs/tool-contracts.md`, add a section after "Official Tool Contract":

```markdown
## Extension Tool Hooks

The extension runtime may observe or patch tool calls through typed in-process hooks:

- `tool_call` can block an allowed tool call or return updated arguments before permission/tool execution continues.
- `tool_result` can replace the structured observation or provide a workflow patch after execution.

These hooks do not bypass mode contracts, `PermissionPolicy`, path write checks, or tool metadata categories. Extension-provided tools are not part of this slice.
```

- [x] **Step 4: Update frontend protocol**

In `docs/frontend-protocol.md`, add these snapshot fields to the Session Snapshot list:

```markdown
- `extensions`
- `extension_diagnostics`
```

Add a short paragraph in the Tool Catalog or Core Boundary section:

```markdown
Extension diagnostics are frontend-visible health information. Frontends may display them, but they must not infer extension execution policy from them.
```

- [x] **Step 5: Update tracker and change log**

Append a concise dated note to `docs/development-tracker.md`:

```markdown
## 2026-06-04 Capability Extension Contract

- Added the first self-extensible Agent Core implementation slice to the active plan: general extension diagnostics, resource discovery contract, context hook, tool-call/tool-result hooks, and frontend snapshot diagnostics.
- Project-local Python extension loading, dynamic tool registration, and resource reload commands remain separate follow-up slices.
```

Append a concise dated note to `docs/design-change-log.md`:

```markdown
## 2026-06-04 Capability Extension Contract

Accepted the Pi-inspired microkernel direction for EmbedAgent by promoting `ExtensionManager` toward a general local capability boundary. The first implementation slice keeps C/C++ harness behavior unchanged while adding generic extension diagnostics and hook contracts. Runtime loading of project-local Python extensions remains deferred behind explicit offline and permission guardrails.
```

- [x] **Step 6: Run documentation vocabulary checks**

Run:

```bash
rg -n "manage_todos| code mode|code mode|Session.task_graph" README.md docs/overall-solution-architecture.md docs/tool-contracts.md docs/frontend-protocol.md docs/development-tracker.md docs/design-change-log.md
```

Expected: no matches for reintroduced deprecated vocabulary in the touched sections.

- [x] **Step 7: Commit Task 6**

```bash
git add README.md docs/overall-solution-architecture.md docs/tool-contracts.md docs/frontend-protocol.md docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: document capability extension contract"
```

---

### Task 7: Final Verification

**Files:**
- Verify only; no planned source edits.

- [x] **Step 1: Run focused extension and workflow tests**

Run:

```bash
uv run pytest tests/test_capability_extensions.py tests/test_workflow_extensions.py -v
```

Expected: PASS.

- [x] **Step 2: Run query-engine focused tests**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_query_engine_verify_slice.py -v
```

Expected: PASS.

- [x] **Step 3: Run frontend protocol tests**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py tests/test_gui_backend_api.py -v
```

Expected: PASS.

- [x] **Step 4: Run fast suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS.

- [x] **Step 5: Run lint checks**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
```

Expected: PASS.

- [x] **Step 6: Inspect final diff**

Run:

```bash
git status --short
git log --oneline -n 8
```

Expected: only intentional files are modified or all implementation tasks are already committed. The recent commits should correspond to Tasks 1 through 6.
