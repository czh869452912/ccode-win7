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
- Official session runtime ownership: one session-scoped `QueryEngine` owns turn/step/interaction execution; adapters host and project
- Official workflow extension hosting: `InProcessAdapter` owns one `ExtensionManager` shared with session-scoped `QueryEngine` and frontend tool catalog visibility
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
  The session-scoped engine that owns turn/step execution, interaction suspend/resume, context assembly, transcript integration, and the workflow extension boundary.
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
