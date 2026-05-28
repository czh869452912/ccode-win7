# Workflow Extension Boundary Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working workflow-extension boundary without changing current C harness behavior.

**Architecture:** Add a small Python extension contract and manager, then wrap the current C harness behavior behind that manager. Keep legacy `Session.task_graph` and frontend fields as compatibility mirrors while introducing generic `Session.workflow_state`.

**Tech Stack:** Python 3.8 dataclasses, existing unittest/pytest suite, current `embedagent.harness` implementation.

---

## File Structure

- Create `src/embedagent/extensions.py`: workflow-neutral event, patch, manager, and protocol-shaped base behavior.
- Create `src/embedagent/harness/extension.py`: built-in C harness workflow extension that reuses `HarnessRunner` and `TaskGraph` internally.
- Modify `src/embedagent/session.py`: add `workflow_state: Dict[str, Any]` without removing `task_graph`.
- Modify `src/embedagent/query_engine.py`: inject extension manager, route harness prompt creation, task initialization, tool activation, and `task_status` through the manager.
- Add `tests/test_workflow_extensions.py`: tests for fake extension behavior, C harness compatibility, and direct import boundary.

## Task 1: Extension Contract And Manager

**Files:**
- Create: `src/embedagent/extensions.py`
- Test: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_fake_workflow_extension_adds_prompt_units_and_active_tools():
    manager = ExtensionManager()
    manager.register(FakeWorkflowExtension())
    session = Session()

    patch = manager.before_agent_start(
        WorkflowEvent(session_id=session.session_id, current_mode="build", user_text="build it"),
        ExtensionContext(workspace=".", session_view=SessionView.from_session(session)),
    )

    assert patch.prompt_units == ["fake prompt"]
    assert patch.active_tool_names == ["fake_tool"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workflow_extensions.py::test_fake_workflow_extension_adds_prompt_units_and_active_tools -v`

Expected: FAIL because `embedagent.extensions` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create dataclasses for `WorkflowEvent`, `ExtensionContext`, `SessionView`, `PromptPatch`, `ToolCallDecision`, `WorkflowPatch`, and an `ExtensionManager` that merges prompt units and active tool names in registration order.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workflow_extensions.py::test_fake_workflow_extension_adds_prompt_units_and_active_tools -v`

Expected: PASS.

## Task 2: Session Workflow State Compatibility

**Files:**
- Modify: `src/embedagent/session.py`
- Test: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Write the failing test**

```python
def test_session_has_generic_workflow_state_alongside_task_graph():
    session = Session()

    session.workflow_state["workflow"] = {"id": "fake", "state": "active"}

    assert session.workflow_state["workflow"]["id"] == "fake"
    assert session.task_graph.is_empty()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_workflow_extensions.py::test_session_has_generic_workflow_state_alongside_task_graph -v`

Expected: FAIL because `Session.workflow_state` does not exist.

- [ ] **Step 3: Write minimal implementation**

Add `workflow_state: Dict[str, Any] = field(default_factory=dict)` to `Session`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_workflow_extensions.py::test_session_has_generic_workflow_state_alongside_task_graph -v`

Expected: PASS.

## Task 3: Built-In C Harness Extension

**Files:**
- Create: `src/embedagent/harness/extension.py`
- Modify: `src/embedagent/query_engine.py`
- Test: `tests/test_workflow_extensions.py`

- [ ] **Step 1: Write failing tests**

```python
def test_c_harness_extension_preserves_build_prompt_behavior(tmp_path):
    tools = ToolRuntime(str(tmp_path))
    engine = QueryEngine(client=DoneClient(), tools=tools)
    result = engine.submit_user_turn("build the project", stream=False, initial_mode="build")

    contents = [message.content for message in result.session.messages if message.kind == "harness_prompt"]

    assert any("Mode: build" in item for item in contents)
    assert any("Discipline: lite_spec_tdd" in item for item in contents)

def test_query_engine_no_longer_imports_task_graph_directly():
    source = Path("src/embedagent/query_engine.py").read_text(encoding="utf-8")

    assert "from embedagent.harness.task_graph import TaskGraph" not in source
    assert "TaskGraph.from_user_request" not in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_workflow_extensions.py::test_c_harness_extension_preserves_build_prompt_behavior tests/test_workflow_extensions.py::test_query_engine_no_longer_imports_task_graph_directly -v`

Expected: first test may pass with old direct path; second test FAILS because `QueryEngine` imports and instantiates `TaskGraph` directly.

- [ ] **Step 3: Write minimal implementation**

Add `CHarnessWorkflowExtension` with methods for work-request detection, prompt patch creation, task graph initialization, active tool selection, and `task_status` observation. Inject a default `ExtensionManager` into `QueryEngine`, and replace direct `TaskGraph` imports/creation and hard-coded `task_status` assembly with manager calls.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workflow_extensions.py -v`

Expected: PASS.

## Task 4: Regression Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused regression tests**

Run:

```bash
uv run pytest tests/test_workflow_extensions.py tests/test_query_engine_build_lite.py tests/test_query_engine_debug_lite.py tests/test_task_graph_v2.py tests/test_tools_package.py::TestToolRuntimeSchemas -v
```

Expected: PASS.

- [ ] **Step 2: Run fast local suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS.
