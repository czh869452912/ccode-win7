# Phase D Default C/C++ Workflow Package Design

## Goal

Move the remaining default C/C++ workflow capability ownership behind the bundled workflow package boundary while preserving the current hosted C/C++ product behavior.

Phase A made runtime operations durable. Phase B made extension hooks source-aware. Phase C extracted lifecycle ownership behind `AgentLifecycleJournal`, `AgentKernel`, and `AgentLoop`. Phase D now turns the default C/C++ harness from "an extension plus runtime-side helper imports" into the first-party workflow package that owns its own tool definitions, metadata, pack activation, prompt units, task graph state, task snapshots, and workflow projection.

## Non-Goals

- Do not rewrite the C/C++ task graph.
- Do not change the public workflow vocabulary.
- Do not introduce remote extension registries, dependency installation, plugin marketplaces, Docker, WSL, VS Code, or online services.
- Do not make project-local extensions able to replace built-in tools.
- Do not require a full new plugin framework before moving the default package.

## Current Coupling To Remove

The current implementation already routes most workflow behavior through `CHarnessWorkflowExtension`, but these C/C++ workflow concepts still leak into runtime/core-adjacent modules:

- `ToolRuntime` imports `embedagent.tools.harness_runtime`.
- `ToolRuntime` constructs default harness tools at initialization time.
- `ToolRuntime` imports `OfficialRuntimeModes` only to describe C/C++ modes.
- default C/C++ metadata is merged into `_DEFAULT_TOOL_METADATA`.
- `embedagent.tooling.packs` is a global pack registry used by harness but not owned by the harness package.

The desired shape is that a bare `ToolRuntime` can start with workflow-neutral tools only. Hosted product paths then load the bundled C/C++ workflow package through the shared `ExtensionManager`, and that package registers its tools and controls active tool names through extension hooks.

## Interface Design Alternatives

### Design 1: Single Package Facade

Expose one object:

```python
class CWorkflowPackage(object):
    def register(self, manager, tools):
        ...
```

Hosted paths call `CWorkflowPackage().register(...)`, and the package imperatively wires tools, prompts, active-tool policies, and task graph state.

This minimizes method count for callers, but it hides too much behind one side-effect-heavy method. It also duplicates the existing `ExtensionManager` registration path and makes testing harder because the caller cannot separately inspect tool registration, prompt behavior, or workflow task projection.

### Design 2: Capability Provider Interface

Expose a richer provider:

```python
class WorkflowPackage(object):
    def tool_definitions(self, context):
        ...

    def tool_metadata(self):
        ...

    def prompt_units(self, mode, workflow_state, session):
        ...

    def active_tool_names(self, mode, workflow_state):
        ...

    def workflow_projection(self, session):
        ...
```

This is explicit and flexible, but it creates a second extension protocol next to `ExtensionManager`. That would weaken Phase B by splitting reducer behavior across two surfaces.

### Design 3: Extension-Owned Capabilities

Keep `CHarnessWorkflowExtension` as the default package object and make it own more capabilities through existing extension hooks:

```python
class CHarnessWorkflowExtension(object):
    def register_tools(self, event, context):
        return ToolRegistrationResult(...)

    def allowed_tool_names(self, mode_name, workflow_state="chat"):
        return set(...)

    def describe_prompt(...):
        return HarnessPrompt(...)

    def initialize_workflow_state(...):
        ...

    def handle_tool_call(...):
        ...
```

This keeps the public capability boundary small: hosted paths still build a `DefaultExtensionSet`, the manager dispatches reducers through `AgentEventBus`, and `ToolRuntime` only knows how to register tool definitions. The complexity stays inside the workflow package.

Recommendation: use Design 3 for Phase D. It is the deepest interface for the current codebase because it hides C/C++ workflow complexity behind the source-aware extension boundary we already trust. A future `WorkflowPackage` protocol can be documented later if a second first-party workflow package appears, but Phase D should not add it prematurely.

## Target Architecture

After Phase D:

- `ToolRuntime` registers only workflow-neutral built-in tools in its constructor.
- `CHarnessWorkflowExtension.register_tools(...)` registers default C/C++ workflow tools and C/C++ discovery tools into the shared runtime.
- C/C++ tool metadata lives with the default workflow package, not in `ToolRuntime`.
- C/C++ pack definitions live with the default workflow package, not in a global runtime-adjacent pack module.
- `CHarnessWorkflowExtension.allowed_tool_names(...)` remains the single default C/C++ active-tool policy.
- `CHarnessWorkflowExtension.describe_prompt(...)` remains the single default C/C++ prompt-unit provider.
- `CHarnessWorkflowExtension.handle_tool_call(...)` remains the single extension-owned tool handling path for `task_status`.
- `ToolRuntime.schemas_for(...)` continues to project schemas from explicit tool names only.
- A bare `QueryEngine` plus bare `ToolRuntime` does not expose default C/C++ workflow tools.
- `InProcessAdapter` and hosted paths continue loading the bundled workflow by default through `default_extensions.py`.

## Subphases

### D-A: Package-Owned Tool Registration

Move `build_harness_tools(...)` ownership from `ToolRuntime.__init__` to `CHarnessWorkflowExtension.register_tools(...)`.

Expected behavior:

- bare `ToolRuntime` no longer has `run_recipe`, `task_status`, `report_quality_v2`, or `record_failing_evidence` until an extension registers them.
- hosted `InProcessAdapter` still exposes those tools because it calls extension tool registration.
- `QueryEngine` still registers extension tools before assembling active schemas.

### D-B: Package-Owned Tool Metadata

Move C/C++ workflow metadata out of `ToolRuntime._DEFAULT_TOOL_METADATA` and into the tool definitions returned by the default workflow package.

Expected behavior:

- `ToolRuntime` no longer imports `OFFICIAL_HARNESS_TOOL_METADATA`.
- runtime catalog entries for harness tools still include permission category, renderers, read-only flags, interruption behavior, activity kind, and context priority.
- dynamic extension tool metadata validation remains unchanged.

### D-C: Package-Owned Packs And Mode Description

Move C/C++ pack definitions and `OfficialRuntimeModes` out of `embedagent.tools.harness_runtime` / global runtime usage and into harness-owned modules.

Expected behavior:

- `ToolRuntime` no longer imports `OfficialRuntimeModes`.
- `ToolRuntime.describe_mode(...)` is removed or becomes a workflow-neutral compatibility shim that does not import harness.
- `CHarnessWorkflowExtension` and `HarnessRunner` use harness-owned pack definitions.

### D-D: Core/Bare Runtime Guardrails

Add regression tests proving that importing/constructing bare Agent Core does not load harness runtime helpers.

Expected behavior:

- importing `embedagent.tools.runtime` does not import `embedagent.harness.runner` or `embedagent.tools.harness_runtime`.
- constructing bare `ToolRuntime` does not register C/C++ workflow tools.
- hosted default extension assembly still registers C/C++ workflow tools.

### D-E: Documentation And Archive

Update active source-of-truth docs to mark Phase D complete for default workflow package capability ownership, then archive the Phase D spec and plan.

## Acceptance Criteria

- `ToolRuntime` does not import `embedagent.tools.harness_runtime`.
- `ToolRuntime` does not construct default harness tools in `__init__`.
- default C/C++ workflow tools are registered by `CHarnessWorkflowExtension.register_tools(...)`.
- default C/C++ workflow metadata is owned by the default package.
- default C/C++ pack definitions are owned by the harness package.
- bare engine tests prove C/C++ workflow tools are absent without the default extension set.
- hosted adapter tests prove C/C++ workflow tools are present with the default extension set.
- `uv run pytest tests/test_workflow_extensions.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py -q` passes.
- `uv run pytest tests/ -m "not slow and not gui" -q` passes before closeout.

## Design Self-Review

- Completeness scan: no open blanks or unspecified implementation slots remain.
- Scope check: the slice is limited to default C/C++ workflow capability ownership and avoids task graph rewrites.
- Boundary check: the chosen interface reuses `ExtensionManager`/`AgentEventBus` instead of creating a parallel package protocol.
- Constraint check: Python 3.8, offline deployment, Windows 7, and no runtime dependency installation remain unchanged.
