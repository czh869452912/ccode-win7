# Phase B HookBus Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Phase B by routing the remaining `ExtensionManager` hook families through the source-aware `AgentEventBus` while preserving public extension APIs.

**Architecture:** Keep `ExtensionManager` as the public extension facade. Internally, register each callable extension hook as a source-aware bus reducer, use event-specific merge helpers for the existing semantics, and record bus diagnostics uniformly. Do not move operation lifecycle orchestration out of `QueryEngine`; Phase B only creates the bus boundary and diagnostics surface needed for Phase C.

**Tech Stack:** Python 3.8 dataclasses and typing only; existing `AgentEventBus`, `ExtensionManager`, extension hook dataclasses, and pytest coverage under `tests/test_capability_extensions.py`, `tests/test_dynamic_tool_registration.py`, and `tests/test_workflow_extensions.py`.

---

### Task 1: Add Red Tests For Remaining Hook Families

**Files:**
- Modify: `tests/test_capability_extensions.py`

- [x] **Step 1: Add failing diagnostics tests**

Add tests proving project extension failures in `resources_discover`, `register_tools`, and `tool_call` produce diagnostics with `metadata.agent_event_type` and `metadata.handler_kind`.

- [x] **Step 2: Add failing merge semantics tests**

Add tests proving bus-backed `tool_call` still uses first block wins and sequential argument rewrites, and bus-backed `register_tools` still registers returned tools with extension source metadata.

- [x] **Step 3: Run targeted tests for RED**

Run:

```bash
uv run pytest tests/test_capability_extensions.py -q
```

Expected: new metadata assertions fail before the remaining hooks are routed through `AgentEventBus`.

### Task 2: Route Remaining Public Hooks Through AgentEventBus

**Files:**
- Modify: `src/embedagent/extensions.py`
- Test: `tests/test_capability_extensions.py`

- [x] **Step 1: Register reducers for all public hook families**

Extend `_register_bus_reducers(...)` to register reducers for:

- `extension.resources_discover`
- `extension.register_tools`
- `extension.tool_call`
- `extension.before_agent_start`
- `extension.should_inject_workflow`
- `extension.describe_prompt`
- `extension.initialize_workflow_state`
- `extension.allowed_tool_names`
- `extension.load_session_tasks`
- `extension.handle_tool_call`

- [x] **Step 2: Add a small dispatch helper**

Add an internal `_dispatch_event(...)` helper that builds `AgentEvent`, dispatches through the bus, mirrors diagnostics into `ExtensionDiagnostic`, and re-raises trusted built-in errors as their original exception.

- [x] **Step 3: Convert public methods to bus result merges**

Replace direct `_call_hook` loops in public methods with event-specific merges over `dispatch.reducer_results`. Preserve existing behavior:

- resource path dedupe
- dynamic tool registration and registration failure diagnostics
- first blocking `ToolCallDecision` wins
- sequential argument updates mutate the event for later reducers
- prompt patches concatenate in registration order
- allowed tool names union with fallback
- first non-null prompt/task/tool handler result wins

- [x] **Step 4: Run targeted tests for GREEN**

Run:

```bash
uv run pytest tests/test_capability_extensions.py tests/test_dynamic_tool_registration.py tests/test_workflow_extensions.py -q
```

Expected: all pass.

### Task 3: Sync Docs And Close Phase B

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/superpowers/plans/2026-06-14-phase-b-hookbus-closeout.md`

- [x] **Step 1: Update Phase B status**

Mark Phase B as complete for the extension hook bus boundary. State clearly that operation lifecycle orchestration remains Phase C AgentKernel work, although lifecycle events can now be observed through the bus boundary in future slices.

- [x] **Step 2: Run final verification**

Run:

```bash
uv run ruff check src/embedagent/agent_event_bus.py src/embedagent/extensions.py tests/test_capability_extensions.py
uv run black --check src/embedagent/agent_event_bus.py src/embedagent/extensions.py tests/test_capability_extensions.py
uv run pytest tests/test_capability_extensions.py tests/test_dynamic_tool_registration.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py tests/test_workflow_extensions.py -q
uv run pytest tests/ -m "not slow and not gui" -q
git diff --check
```

- [x] **Step 3: Commit**

```bash
git add README.md AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/pi-inspired-agent-core-blueprint.md docs/development-tracker.md docs/design-change-log.md docs/superpowers/plans/2026-06-14-phase-b-hookbus-closeout.md src/embedagent/extensions.py tests/test_capability_extensions.py
git commit -m "feat: close phase b hook bus migration"
```
