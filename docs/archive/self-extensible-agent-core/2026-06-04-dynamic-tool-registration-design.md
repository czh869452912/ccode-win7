# Dynamic Tool Registration Design

## Status

Draft for Slice 2 implementation.

This document scopes the second self-extensible Agent Core slice after
`2026-06-04-self-extensible-agent-core-design.md` and the completed Slice 1
capability extension contract. The user-approved direction is to implement
dynamic tool registration before local resource loading or project-local Python
extension loading.

## Context

Slice 1 promoted `ExtensionManager` from a default C harness boundary into a
general in-process capability boundary:

- extension diagnostics
- resource discovery event/result contracts
- context hooks
- tool-call and tool-result hooks
- frontend snapshot diagnostics

The current `ToolRuntime` is still a closed construction-time registry. It
collects built-in tools and default C harness tools during `__init__`, builds a
catalog from static metadata, and later projects schemas or executes tools from
that fixed map.

Pi Agent's implementation takes a different shape:

- extensions can register tools through a narrow `registerTool()` API
- session/runtime code folds built-in, SDK/custom, and extension tools into one
  registry
- tools carry source metadata
- active tool names decide what the model sees
- tool-call and tool-result hooks wrap execution

EmbedAgent should adopt that shape while preserving its own constraints:

- Windows 7 and Python 3.8 compatibility
- offline deployment
- no Node/npm runtime dependency
- `PermissionPolicy` remains the final execution authority
- default C/C++ harness tools remain bundled defaults behind extension
  activation

## Goals

- Make `ToolRuntime` source-aware and dynamically extensible.
- Let in-process extensions register tools without project-local code loading.
- Preserve mode and workflow active-tool gating.
- Preserve permission enforcement for extension tools.
- Expose extension tool metadata through existing schema and frontend catalog
  paths.
- Add focused tests proving that dynamic tools are invisible until active,
  visible once active, executable, source-tagged, and permission-gated.

## Non-Goals

- Do not load `.embedagent/extensions/<name>/extension.py`.
- Do not discover `.embedagent/skills`, `.embedagent/prompts`, or
  `.embedagent/recipes`.
- Do not add reload commands or reload API.
- Do not add command, shortcut, provider, renderer, or UI extension APIs.
- Do not introduce a marketplace, online install path, or extra runtime
  dependency.
- Do not allow extension tools to replace built-in tools in this slice.

## Design Summary

Slice 2 adds a minimal dynamic tool registration path:

1. `ToolRuntime.register_tool()` registers a `ToolDefinition` plus source
   metadata.
2. `ExtensionManager.register_tools(...)` asks extensions for tool
   registrations and records diagnostics for invalid or conflicting tools.
3. `QueryEngine` and `InProcessAdapter` call the registration path before
   schema/catalog projection and before execution.
4. `ExtensionManager.allowed_tool_names(...)` remains the active-tool authority;
   registered tools appear to the model only when active for the current mode
   and workflow state.
5. `PermissionPolicy` can classify a tool by catalog metadata so extension tools
   with `workspace_write`, `shell_exec`, or `toolchain_exec` categories cannot
   fall through as unknown safe tools.

The key product behavior is:

> An injected extension can register a local echo/check helper tool. The model
> sees it only when the extension activates its name, frontend catalog shows its
> source, and execution still passes through permissions.

## Public Runtime Contract

`ToolRuntime.register_tool()` should accept existing local primitives rather
than a new plugin-specific type:

- `ToolDefinition`
- optional `source_id`
- optional `source_type`
- optional `replace`

`replace=False` is the only supported product behavior for this slice. If a
registered tool name already exists, the runtime rejects the registration and
records a diagnostic through the extension manager.

Tool metadata remains mandatory for security and projection:

- `permission_category`
- `mode_visibility`
- `workflow_visibility`
- `user_label`
- `read_only`
- `concurrency_safe`
- `interrupt_behavior`
- `result_budget_policy`

If optional rendering metadata is absent, the runtime fills conservative
defaults as it already does for built-in tools.

## Extension Contract

Extensions may expose a tool-registration hook. The exact method name can stay
simple and Pythonic:

```python
def register_tools(event, context):
    ...
```

The hook returns tool definitions and metadata rather than mutating the runtime
directly. This keeps registration deterministic and gives `ExtensionManager` one
place to catch errors, reject conflicts, and attach source metadata.

The event should include:

- `current_mode`
- `workflow_state_name`
- `reason`, such as `startup`, `session_start`, or `catalog`

The context already carries:

- workspace
- runtime environment
- tool registry
- permission policy
- session view

In this slice, extensions are still injected by tests or hosts through
`ExtensionManager([...])`. Project-local loading remains Slice 4.

## Source Metadata

Catalog entries should include stable source fields:

- `source_type`: `builtin`, `harness`, `extension`, or `runtime`
- `source_id`: extension id or built-in runtime id

Existing frontend consumers can ignore these fields. The fields are still useful
immediately for tests, diagnostics, and future extension management screens.

Built-in core tools are tagged as `builtin`. Default C harness tools are tagged
as `harness`. This keeps the catalog vocabulary short and makes the bundled
workflow default visibly distinct without introducing another built-in subtype.

## Permission Model

Today, `PermissionPolicy` classifies known tool names through static sets and
unknown tools as `other`, which defaults to allow. That is not acceptable for
dynamic tools.

Slice 2 adds a narrow metadata classification path. `PermissionPolicy` receives
an optional category lookup callable at construction time:

```python
def category_lookup(tool_name):
    entry = tool_runtime.tool_catalog_entry(tool_name)
    return entry.get("permission_category")
```

Then `_category_for_action()` can use metadata before falling back to static
sets. Unknown tools still become `other`, but properly registered dynamic tools
must declare their intended category.

Registration should reject unsupported categories. Initial supported categories
are the existing official categories:

- `read`
- `workspace_write`
- `shell_exec`
- `toolchain_exec`
- `git_write`

This preserves the current rule language and frontend permission vocabulary.

## Active Tool Flow

Dynamic registration and active-tool selection are separate:

```text
extension register_tools hook
  -> ToolRuntime.register_tool()
  -> ToolRuntime catalog contains tool
  -> extension allowed_tool_names hook activates name for mode/workflow
  -> QueryEngine _schemas_for_active_tools()
  -> model can call active registered tool
  -> QueryEngine checks mode active tools
  -> extension tool-call hook can block/patch
  -> PermissionPolicy evaluates metadata category
  -> ToolRuntime executes handler
  -> extension tool-result hook can patch result
```

This mirrors Pi's separation between "all registered tools" and "active tools",
but keeps EmbedAgent's mode contracts and permissions in the path.

## Error Handling

Registration failures should become extension diagnostics and should not crash
for project/injected extensions:

- invalid object returned instead of `ToolDefinition`
- empty or invalid tool name
- duplicate name conflict
- missing handler
- missing or unsupported permission category
- malformed parameter schema

Built-in extension failures still fail closed according to Slice 1 rules.

Tool execution errors continue to use existing `ToolRuntime.execute_with_interrupt`
behavior and produce normal `Observation` objects.

## Testing Strategy

Focused tests should cover:

- `ToolRuntime.register_tool()` adds schema and catalog entry with source
  metadata.
- duplicate registration is rejected without replacing a built-in tool.
- an extension-registered tool is absent from model schemas when not active.
- the same tool appears when `allowed_tool_names()` activates it.
- `QueryEngine` can execute an active extension tool.
- a dynamic `shell_exec` or `workspace_write` tool triggers a permission wait
  when auto-approval is disabled.
- `InProcessAdapter.get_tool_catalog()` includes active extension tools and
  preserves existing C harness catalog behavior.
- existing Slice 1 capability extension tests and workflow extension tests stay
  green.

## Documentation Updates

The implementation slice should update:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

The durable documentation should say that dynamic in-process tool registration
is official, while project-local extension loading and local resources remain
future slices.

## Risks And Guardrails

- Dynamic tools can become a second core if the API is too broad. Guardrail:
  accept only `ToolDefinition` plus metadata in this slice.
- Dynamic tools can bypass permissions if unknown categories default to allow.
  Guardrail: classify through catalog metadata and reject unsupported
  categories.
- Tool replacement can destabilize built-ins. Guardrail: no replacement in
  Slice 2.
- Registration timing can become non-deterministic. Guardrail: register through
  explicit host/query/catalog call sites and keep registration idempotent by
  name/source.
- Frontend scope can grow quickly. Guardrail: add source fields to existing
  catalog payloads, but do not build new UI surfaces.

## Implementation Decisions

- Harness catalog entries use `source_type="harness"`.
- Registration diagnostics use concise error strings plus structured metadata
  such as `tool_name`, `source_id`, and `reason`. They do not embed full schema
  validation dumps in this slice.
- `PermissionPolicy` receives the metadata category lookup at construction time.
  Hosts that construct the policy before the tool runtime may attach it with a
  narrow setter, but `evaluate()` keeps its current call shape.
