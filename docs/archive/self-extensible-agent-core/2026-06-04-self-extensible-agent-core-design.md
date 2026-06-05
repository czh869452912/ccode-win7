# Self-Extensible Agent Core Design

## Status

Draft accepted for architecture direction.

This document records the direction approved after comparing EmbedAgent with Pi Agent's actual implementation in `reference/pi`.

## Context

EmbedAgent has already completed an important core cutover:

- `QueryEngine` no longer constructs the default C harness directly.
- `Session.workflow_state` is the generic workflow carrier.
- `CHarnessWorkflowExtension` owns default C/C++ task graph behavior behind an extension boundary.
- `ToolRuntime.schemas_for(..., tool_names=...)` is the single schema projection entry point.
- `InProcessAdapter` shares one hosted `ExtensionManager` with session-scoped engines and frontend tool catalog projection.

This is a strong foundation, but the current extension boundary is still mostly a workflow boundary for the bundled C/C++ harness. It is not yet a general capability runtime like Pi's extension system.

The desired product direction is:

- keep the agent itself extremely small
- ship strong offline C/C++ defaults as replaceable built-ins
- let local projects add skills, prompts, recipes, tools, commands, and workflow behavior
- let the agent create those local extensions for itself, then reload them
- preserve Windows 7, offline deployment, Python 3.8, and the permission engine

## Pi Reference Findings

Pi's design separates the product into thin layers:

- `packages/agent/src/agent-loop.ts` is a small loop over messages, tools, events, and before/after tool hooks.
- `packages/agent/src/harness/agent-harness.ts` owns session resources, active tools, compaction, event dispatch, and mutable harness state.
- `packages/coding-agent/src/core/extensions/types.ts` defines the real extension API: events, tools, commands, shortcuts, flags, provider registration, UI calls, custom messages, and resource discovery.
- `packages/coding-agent/src/core/extensions/loader.ts` discovers project-local and global extensions and supports reload.
- `packages/coding-agent/docs/extensions.md` documents the product promise: the agent can create extensions for user workflows.

The key lesson is not TypeScript, npm, or Pi's exact API surface. The key lesson is the shape:

1. a very small agent loop
2. a general extension runtime around it
3. rich local resources discovered progressively
4. strong defaults implemented as extensions, not as irreducible core

## Goals

- Promote the current workflow extension boundary into a general local capability extension runtime.
- Keep the default C/C++ harness as the bundled default extension, not as Agent Core.
- Support agent-created local extensions without requiring online services.
- Preserve the existing permission model as the final authority for tool execution.
- Keep runtime dependency rules compatible with Python `>=3.8,<3.9` and Windows 7.
- Avoid copying Pi's unrestricted execution model.
- Avoid introducing Docker, WSL, Node.js-at-runtime, npm installs, online registries, or a plugin marketplace.

## Non-Goals

- Do not build a public plugin marketplace.
- Do not load remote extensions automatically.
- Do not make MCP, browser automation, or cloud services part of the product baseline.
- Do not make mode definitions a plugin free-for-all in the first implementation.
- Do not weaken the permission engine to match Pi's "runs as the user" default.
- Do not require new runtime dependencies absent from `pyproject.toml` or the offline bundle.

## Design Principles

### Agent Core Is A Microkernel

Agent Core should own only the durable execution substrate:

- session and transcript truth
- LLM turn loop
- context assembly and compaction
- tool registry and execution
- permission evaluation
- interaction suspension and resumption
- extension event dispatch
- frontend snapshot/bootstrap projection
- bundled runtime discovery

Agent Core should not own:

- C/C++ task graph semantics
- phase names
- discipline profiles
- recipe policy
- project-specific workflow instructions
- custom command behavior
- custom provider behavior

### Defaults Are Extensions

The bundled C/C++ workflow remains first-class, but it should be described as:

- default built-in extension
- enabled by hosted product paths
- replaceable by future local workflow extensions
- internally allowed to use `TaskGraph`
- externally projected through generic workflow state

### Extensions Are Local And Manifested

Project-local extension discovery should be explicit and offline:

```text
.embedagent/
  extensions/
    my_extension/
      extension.json
      extension.py
  skills/
  prompts/
  recipes/
```

The first implementation should not install dependencies. An extension can import only:

- Python standard library
- modules already bundled with EmbedAgent
- modules explicitly allowed by the offline distribution
- helper files inside the extension directory

### Permission Remains Central

Extensions may register tools and request active tools, but execution still flows through:

- mode tool/write contract
- `PermissionPolicy`
- tool metadata permission category
- frontend/user approval for pending interactions

This is a deliberate divergence from Pi.

## Proposed Architecture

### 1. General Extension Runtime

Rename or evolve `ExtensionManager` into a general runtime while preserving compatibility:

- `ExtensionManager` remains the initial class name if renaming is too disruptive.
- The interface becomes capability-oriented instead of only workflow-oriented.
- Extensions are ordered, local, and deterministic.
- Hook errors are recorded in transcript/session diagnostics.
- Built-in extension errors fail closed.
- Project extension errors are isolated and surfaced.

Initial event families:

- `resources_discover`
- `session_start`
- `session_shutdown`
- `input`
- `before_agent_start`
- `context`
- `before_llm_request`
- `after_llm_response`
- `tool_call`
- `tool_result`
- `turn_end`
- `snapshot`
- `reload`

The first slice can implement only the subset needed for resources, tools, prompt injection, and tool interception.

### 2. Extension API

Local Python extensions should expose:

```python
def register(api):
    ...
```

The `api` object should support narrow registration methods:

- `on(event_name, handler)`
- `register_tool(tool_definition)`
- `register_command(command_definition)`
- `register_skill_path(path)`
- `register_prompt_path(path)`
- `register_recipe_path(path)`
- `set_extension_state(key, value)`
- `get_extension_state(key, default=None)`

Runtime actions that mutate sessions or execute commands should not be available during load. They should be available only inside event handlers through a guarded context object.

### 3. Dynamic Tool Registry

`ToolRuntime` should stop being a closed construction-time registry.

It should support:

- built-in tool registration
- extension tool registration
- tool source metadata
- tool replacement rules
- active tool names per turn
- frontend catalog projection from the active extension manager

Tool metadata remains mandatory:

- name
- description
- parameter schema
- permission category
- read-only flag
- concurrency safety
- renderer keys
- result budget policy

The bundled C harness extension activates:

- `list_recipes`
- `run_recipe`
- `report_quality_v2`
- `record_failing_evidence`
- `task_status`

Core keeps:

- `read_file`
- `list_dir`
- `glob_files`
- `grep_text`
- `write_file`
- `edit_file`
- `ask_user`
- controlled supporting tools such as `git_status`, `git_diff`, `git_log`, and `run_command`

### 4. Resource Discovery

Add first-class local resource discovery before arbitrary code extensions become broad:

- skills from `.embedagent/skills/`
- prompt templates from `.embedagent/prompts/`
- recipes from `.embedagent/recipes/`
- extension-contributed resource paths

This gives the agent a safe first form of self-extension:

1. create a skill or prompt file
2. reload resources
3. use the new capability

Only after this path is stable should arbitrary Python tool extensions be enabled by default.

### 5. Agent Loop Slimming

Long term, split `QueryEngine` into smaller parts:

- `AgentLoop`: LLM response, tool calls, loop continuation, stop reasons
- `AgentRuntimeHost`: session/transcript/context/permission ownership
- `ExtensionRuntime`: events, registrations, reload, diagnostics
- `DefaultCHarnessExtension`: bundled C/C++ workflow

This is the closest analogue to Pi's `agent-loop.ts` plus `agent-harness.ts`, translated into EmbedAgent's constraints.

### 6. Session And Transcript

Extension state must be durable and replayable.

Add transcript event types such as:

- `extension_loaded`
- `extension_error`
- `extension_tool_registered`
- `resource_discovered`
- `custom_message`
- `extension_state`

Use namespaced state:

```json
{
  "extensions": {
    "my_extension": {
      "state": {}
    }
  }
}
```

Do not overload `workflow_state["workflow"]` with unrelated extension state. Keep `workflow_state["workflow"]` for workflow projection.

### 7. Frontend Contract

The frontend should gain extension-aware surfaces without owning extension semantics:

- extension diagnostics
- available/active tools
- resource reload result
- custom message rendering fallback
- workflow projection from generic `workflow`

The current fields remain compatibility projections:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

The richer future source is:

- `snapshot.workflow`
- `snapshot.extensions`
- `GET /api/tool-catalog`
- future `GET /api/extensions`

### 8. Documentation Model

Current source-of-truth docs say project-local extension discovery is out of scope. That must change if this direction becomes baseline.

The revised position should be:

- local offline extension system is in scope
- remote marketplace is out of scope
- online extension install is out of scope
- C/C++ harness remains the default bundled extension
- Agent Core remains workflow-neutral

## Migration Plan

### Slice 1: Capability Extension Contract

- Extend `extensions.py` with typed events for prompt, context, tool call, tool result, resources, and snapshot.
- Keep `CHarnessWorkflowExtension` working through the same manager.
- Add extension diagnostics data structures.
- Add tests with a fake extension registering prompt text and active tools.
- Do not enable project-local code loading yet.

### Slice 2: Dynamic Tool Registration

- Add `ToolRuntime.register_tool()` and source-aware catalog metadata.
- Route extension tool registration through the shared manager/runtime.
- Preserve mode and permission gating.
- Add tests for an extension tool that is visible only when active.

### Slice 3: Local Resources

- Add `.embedagent/skills/`, `.embedagent/prompts/`, and `.embedagent/recipes/` discovery.
- Add reload command/API for resources.
- Add transcript events for resource discovery and reload diagnostics.
- Let the agent create a skill/prompt/recipe and then reload it.

### Slice 4: Project-Local Python Extensions

- Add manifest loading for `.embedagent/extensions/<name>/extension.json`.
- Load `extension.py` with a constrained API object.
- Record loading results and errors.
- Start disabled or confirmation-gated if needed by product policy.
- Add tests for load failure isolation.

### Slice 5: QueryEngine Slimming

- Extract a smaller agent loop from `QueryEngine`.
- Move extension hook dispatch out of ad hoc call sites and into the loop/host boundary.
- Keep transcript and permission behavior unchanged.
- Add tests that run core without the C harness extension.

### Slice 6: Documentation Cutover

- Update `README.md`, `AGENTS.md`, and active docs.
- State that local offline self-extension is part of the architecture.
- Keep marketplace, online install, and general multi-agent orchestration as non-goals.
- Archive superseded slice-local docs after global docs are synchronized.

## Verification Strategy

Use focused tests per slice:

- fake extension prompt/tool activation
- dynamic tool catalog projection
- extension tool permission enforcement
- extension load/reload diagnostics
- resource discovery and reload
- C harness behavior unchanged
- core-without-C-harness smoke test
- transcript event replay for extension diagnostics

Fast suite remains:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

## Risks

- Opening code extensions too early can weaken debuggability and security.
- A broad extension API can accidentally become a second core.
- C harness can remain privileged through hidden imports unless tests prove otherwise.
- Frontend custom rendering can expand scope quickly; start with fallback rendering and diagnostics.
- Project-local extension code has real execution risk, so user confirmation and manifest permissions may be needed.

## Open Decisions

- Whether project-local Python extensions are enabled by default or require explicit approval.
- Whether extension manifests must declare permission categories before tool registration.
- Whether extension tool replacement of built-in tools is allowed in the first public version.
- Whether custom providers are in scope for offline deployments, or deferred behind local-only model configuration.
- Whether `mode` remains core forever or eventually becomes an extension-provided permission profile.

## Recommendation

Adopt a microkernel direction:

- Agent Core owns execution truth and permissions.
- The bundled C/C++ workflow is the default extension.
- Local resources become the first self-extension path.
- Project-local Python extensions follow after resource reload and dynamic tools are stable.

This gives EmbedAgent the extensibility lesson from Pi while preserving the constraints that make this product distinct: offline deployment, Windows 7 compatibility, Python 3.8, a small dependency surface, and a controlled permission model.
