# EmbedAgent

EmbedAgent is a native, offline-first Agent IDE core for the full C development lifecycle.

The current product baseline is:

- Windows 7 compatible
- Offline deployable
- Python 3.8 runtime target
- Agent Core first, UI replaceable
- Clang-centered C/C++ workflow

## Current Official Architecture

The repository now treats Agent Core as the workflow-neutral runtime, with the C/C++ Agent Harness shipped as the default built-in workflow extension.

Local offline self-extension is part of the official architecture: workspace file resources and manifest-gated project-local Python extensions can extend the hosted runtime while remote registries, online installs, dependency installation, plugin marketplaces, built-in tool replacement, and general multi-agent orchestration remain outside the product baseline.

The next long-term architecture direction is captured in `docs/pi-inspired-agent-core-blueprint.md`: continue learning from Pi's functional design and architecture philosophy while preserving EmbedAgent's offline, Windows 7, Python 3.8, and C/C++ engineering constraints. The current baseline remains valid; the blueprint guides gradual work toward a smaller Agent Kernel, durable session-log reducers, source-aware hooks, and a default C/C++ workflow package loaded through the same capability boundary as local extensions.

- User-visible modes: `explore`, `spec`, `build`, `debug`, `verify`
- Default C/C++ execution model: `mode + discipline_profile + execution_phase`
- Default task system: `TaskGraph` projected through `task_status` and session task snapshots
- Generic workflow state carrier: `Session.workflow_state`
- Frontend workflow projection: `Session.workflow_state["workflow"]` is the source for `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, and `task_items`
- Default C/C++ task graph ownership: `CHarnessWorkflowExtension` keeps harness graph state behind the extension boundary; `Session` no longer exposes `task_graph`
- Default C/C++ workflow projection adapter: `src/embedagent/harness/workflow_projection.py` maps harness internals into the generic workflow payload
- Official build/verify execution: `list_recipes` + `run_recipe` + `report_quality_v2`
- Mode allowed-tool contracts are workflow-neutral; default harness tools are activated by the built-in C/C++ workflow extension
- Official file discovery: `list_dir`, `glob_files`, `grep_text`
- Official permission engine: `PermissionPolicy` with structured rule matching and stable explanation text
- Official session runtime ownership: one session-scoped `QueryEngine` remains the facade and transcript/session mutation owner, while `AgentLoop`, `AgentToolActionService`, and `AgentExtensionHost` own turn orchestration, non-LLM tool action execution, and extension hook dispatch
- Official workflow extension hosting: `InProcessAdapter` owns one `ExtensionManager` shared with session-scoped `QueryEngine` and frontend tool catalog visibility
- Official extension runtime direction: `ExtensionManager` is the shared in-process capability boundary for workflow defaults, prompt/context hooks, tool-call/tool-result hooks, resource discovery contracts, dynamic in-process tool registration, extension diagnostics, and manifest-gated project-local Python extensions
- Official local resources: `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` are discovered as workspace-bound file resources and can be refreshed through `ToolRuntime.reload_resources()`, `InProcessAdapter.reload_resources(...)`, `/resources reload`, or `POST /api/sessions/{id}/resources/reload`
- Official project extension loading: hosted product paths may load enabled `.embedagent/extensions/<name>/extension.json` manifests with workspace-bound `extension.py` entrypoints; `enabled` defaults to false, enabled manifests must declare permissions, no dependency installation or remote registry is allowed, and loaded extensions register through the same shared `ExtensionManager`
- Official default extension assembly: `src/embedagent/default_extensions.py` installs the bundled C/C++ harness for hosted product paths; `QueryEngine` itself has no built-in harness import or constructor fallback
- Official harness refresh path: `CHarnessWorkflowExtension.refresh_managed_session()`; the old `HarnessStateSynchronizer` service facade has been removed
- Official runtime schema projection: `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single schema projection entry point; default harness-aware callers must pass extension-active tool names explicitly
- Official frontend vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`
- Official session-history model: `transcript.jsonl -> Session -> SessionHistoryAssembler -> /api/sessions/{id}/bootstrap`

The product no longer treats the old `code` mode or `manage_todos`-style workflow as the architecture baseline.

## Documentation Model

- `docs/superpowers/` stores design and implementation materials for the current slice.
- `docs/` active documents store the long-lived project source of truth.
- `docs/archive/` stores completed slice artifacts and historical references.

## Documentation Entry Points

- `docs/README.md`
- `docs/documentation-governance.md`
- `docs/documentation-style-guide.md`
- `docs/workflows/code-doc-sync.md`
- `docs/references/glossary.md`

## Main Components

- `src/embedagent/query_engine.py`
  The session-scoped facade that owns session initialization, interaction suspend/resume, transcript integration, and live session mutation.
- `src/embedagent/agent_loop.py`
  Thin turn-loop boundary used by `QueryEngine` to run the LLM/tool loop without making the facade own every loop detail.
- `src/embedagent/agent_tool_action_service.py`
  Non-LLM action executor for active-tool checks, extension pre/post hooks, permission-gated runtime dispatch, path write guards, and extension-owned tool calls.
- `src/embedagent/agent_extension_host.py`
  QueryEngine-side extension host for prompt/context hooks, workflow state initialization, dynamic tool registration, explicit active schema projection, tool-call/tool-result hooks, and workflow patches.
- `src/embedagent/extensions.py`
  In-process extension contract and manager for workflow prompt/tool/state hooks.
- `src/embedagent/default_extensions.py`
  Hosted-runtime factory that installs the bundled C/C++ harness extension outside `QueryEngine`.
- `src/embedagent/session_runtime.py` and `src/embedagent/session_projector.py`
  Runtime host state plus pure snapshot/bootstrap projection from session truth.
- `src/embedagent/harness/`
  Default C/C++ workflow extension internals: mode registry, discipline/phase modeling, prompt stack, task graph, workflow projection, and session task snapshot persistence.
- `src/embedagent/tools/`
  Official tool runtime, catalog metadata, managed environment discovery, and tool execution.
- `src/embedagent/context.py`
  Context policy, reducer registry, replacement logic, and compaction pipeline.
- `src/embedagent/permissions.py`
  Structured permission categories, rule loading, rule matching, and explanation rendering.
- `src/embedagent/inprocess_adapter.py`
  Product-facing adapter used by CLI/TUI/GUI, including session snapshots and slash command handling.
- `src/embedagent/session_history.py`
  Canonical GUI history assembler built from transcript-backed `Session` state.
- `src/embedagent/core/` and `src/embedagent/protocol/`
  Stable frontend/core contract layer.
- `src/embedagent/frontend/`
  TUI and GUI shells built on the same core contract.

## Official Tools

The default C/C++ workflow tool vocabulary is centered on:

- `read_file`
- `list_dir`
- `glob_files`
- `grep_text`
- `write_file`
- `edit_file`
- `list_recipes`
- `run_recipe`
- `report_quality_v2`
- `task_status`
- `record_failing_evidence`
- `ask_user`

Git/status helpers and `run_command` remain available as supporting capabilities where appropriate, but the architecture no longer treats the old duplicate file/build/todo tools as first-class workflow primitives.

These tools are registered in the runtime catalog. Built-in mode prompts expose only workflow-neutral permission/write contracts; the default C/C++ harness extension activates recipe, quality, evidence, and task-status tools through focused packs.

Runtime schema filtering no longer activates the default harness pack on its own. Product paths that need the full default C/C++ tool set combine the mode contract with `ExtensionManager` active tools, then request schemas by explicit tool names.

In-process extensions may register additional `ToolDefinition` objects into the shared runtime catalog. Registration records `source_type` and `source_id`, but a dynamic tool is model-visible only when activated through the shared `ExtensionManager` active-tool path and remains subject to `PermissionPolicy`.

Local resource reload is file-only. Skills and prompts are surfaced as discovered resources, while `.embedagent/recipes/*.json` contributes recipe definitions to the existing `list_recipes` / `run_recipe` path. Reloading resources records transcript-backed diagnostics and does not execute project-local Python code.

Project-local Python extensions are a separate, explicit opt-in path under `.embedagent/extensions/<name>/`. They require `extension.json` with `enabled: true` and a permissions list, load only a workspace-bound `extension.py` entrypoint, receive a narrow API object, and are surfaced in session snapshots under `extensions.project_extensions`. They cannot replace built-in tools and any dynamic tools they register remain metadata-classified and permission-gated.

## Development Constraints

- Do not require Docker, WSL, VS Code, Node.js-at-runtime, or online services.
- Keep runtime compatible with Python `>=3.8,<3.9`.
- The offline bundle must contain every runtime dependency it uses.
- A clean Windows 7 machine must be able to unpack and run the bundle without preinstalled tools.

## Read In This Order

For implementation work, start with:

1. `README.md`
2. `AGENTS.md`
3. `docs/overall-solution-architecture.md`
4. `docs/implementation-roadmap.md`

## Status

Current architecture cutover status:

- Runtime promotion: completed
- Mode vocabulary cutover: completed
- Context/intelligence cutover: completed
- Permission/task truth cutover: completed
- Agent core ownership cutover: completed
- Frontend/protocol officialization: completed
- Session-history single-source cutover: completed
- Remaining work: keep deleting stale shell-only labels/helpers and keep validating on real C projects and Win7 bundle targets

## Verification

Recent focused verification includes:

- Python unit tests for harness, query engine, adapter, GUI backend, and tool runtime
- Webapp helper/runtime tests
- GUI static asset rebuild from current webapp source

## Repository Scope

This repository is not trying to be:

- a browser automation platform
- an online search agent
- a plugin marketplace
- a general-purpose cloud coding service

It is a focused native Agent IDE core for offline C engineering workflows.
