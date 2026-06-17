# Phase B HookBus First Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the first source-aware HookBus / reducer registry slice and migrate `ExtensionManager.context(...)` and `ExtensionManager.after_tool_result(...)` onto it without changing public extension APIs.

**Architecture:** Add a small `AgentEventBus` module that owns registrations, source metadata, dispatch diagnostics, observer ordering, and reducer result merging. `ExtensionManager` remains the public facade for existing callers, but internally registers context and tool-result reducers through the bus. Later Phase B slices can migrate tool-call, resources, dynamic tools, and lifecycle reducers onto the same boundary.

**Tech Stack:** Python 3.8 dataclasses and typing only; existing `ExtensionManager`, `WorkflowEvent`, `ContextPatch`, `ToolResultPatch`, and tests under `tests/test_capability_extensions.py`.

---

### Task 1: Add AgentEventBus Core

**Files:**
- Create: `src/embedagent/agent_event_bus.py`
- Test: `tests/test_capability_extensions.py`

- [x] **Step 1: Write failing bus tests**

Add tests that import `AgentEventBus`, `AgentEvent`, and `EventDispatchResult`; register two reducers on the same event; dispatch with source metadata; assert reducer outputs are preserved in order and a project-source exception becomes a diagnostic instead of raising.

- [x] **Step 2: Run the new tests to verify RED**

Run:

```bash
uv run pytest tests/test_capability_extensions.py::test_agent_event_bus_reduces_in_source_order tests/test_capability_extensions.py::test_agent_event_bus_records_project_reducer_diagnostics -q
```

Expected: import failure for `embedagent.agent_event_bus`.

- [x] **Step 3: Implement minimal bus**

Create dataclasses:

```python
AgentEvent
EventHandlerRegistration
EventDispatchResult
```

Implement:

```python
AgentEventBus.register_reducer(event_type, source_id, source_type, reducer, fail_closed=False)
AgentEventBus.dispatch(event, context=None)
```

`dispatch(...)` calls registered reducers in registration order, stores returned values in `EventDispatchResult.reducer_results`, and records diagnostics for project reducer errors. Built-in/fail-closed errors re-raise after recording diagnostics.

- [x] **Step 4: Verify GREEN**

Run the two new tests and confirm both pass.

### Task 2: Route ExtensionManager Context And Tool Result Through Bus

**Files:**
- Modify: `src/embedagent/extensions.py`
- Test: `tests/test_capability_extensions.py`

- [x] **Step 1: Write failing ExtensionManager tests**

Add assertions that `ExtensionManager` exposes bus source metadata for `context` and `tool_result` dispatch diagnostics, while preserving existing `ContextPatch` and `ToolResultPatch` merge behavior.

- [x] **Step 2: Run targeted tests to verify RED**

Run:

```bash
uv run pytest tests/test_capability_extensions.py -q
```

Expected: new metadata assertions fail before `ExtensionManager` is wired to `AgentEventBus`.

- [x] **Step 3: Implement bus-backed internal dispatch**

In `ExtensionManager.__init__`, create `self._event_bus = AgentEventBus()`. On `register(extension)`, register reducers for callable `context` and `tool_result` hooks with:

- `event_type="extension.context"`
- `event_type="extension.tool_result"`
- `source_id=self._extension_id(extension)`
- `source_type="builtin"` or `"project"`
- `fail_closed=True` for built-in extensions

Keep public `context(...)` and `after_tool_result(...)` method signatures unchanged; each builds an `AgentEvent`, calls the bus, mirrors bus diagnostics into existing `ExtensionDiagnostic`, and merges reducer results exactly as before.

- [x] **Step 4: Verify existing behavior**

Run:

```bash
uv run pytest tests/test_capability_extensions.py tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_persists_and_restores_workflow_patch_events -q
```

Expected: all pass.

### Task 3: Sync Docs And Tracker

**Files:**
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `README.md`
- Modify: `AGENTS.md`

- [x] **Step 1: Update Phase B status**

Record that Phase B first slice established `AgentEventBus` and migrated context/tool-result hooks. Keep the next work scoped to migrating `tool_call`, resources, dynamic tools, and operation lifecycle emitters.

- [x] **Step 2: Run final verification**

Run:

```bash
uv run ruff check src/embedagent/agent_event_bus.py src/embedagent/extensions.py tests/test_capability_extensions.py
uv run black --check src/embedagent/agent_event_bus.py src/embedagent/extensions.py tests/test_capability_extensions.py
uv run pytest tests/test_capability_extensions.py tests/test_dynamic_tool_registration.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py -q
uv run pytest tests/ -m "not slow and not gui" -q
git diff --check
```

- [x] **Step 3: Commit**

```bash
git add src/embedagent/agent_event_bus.py src/embedagent/extensions.py tests/test_capability_extensions.py README.md AGENTS.md docs/pi-inspired-agent-core-blueprint.md docs/development-tracker.md docs/design-change-log.md docs/superpowers/plans/2026-06-13-phase-b-hookbus-first-slice.md
git commit -m "feat: introduce source-aware agent event bus"
```
