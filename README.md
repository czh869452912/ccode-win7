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

Optional enterprise/intranet integrations follow the same minimal-core rule: they may exist as trusted providers, workflow packages, project extensions, or telemetry sinks, but Agent Core must not depend on network availability. Intranet Git, custom service, and telemetry features must be explicit, disableable, manifest/config gated, permission-checked, and failure-tolerant; they must not send prompts, source text, raw tool outputs, or credentials through diagnostics or telemetry.

The next long-term architecture direction is captured in `docs/pi-inspired-agent-core-blueprint.md`: continue learning from Pi's functional design and architecture philosophy while preserving EmbedAgent's offline, Windows 7, Python 3.8, and C/C++ engineering constraints. The current baseline remains valid; the blueprint guides gradual work toward a smaller Agent Kernel, durable session-log reducers, source-aware hooks, explicit turn snapshots, replayable runtime configuration, structured compaction state, recovery markers, and a default C/C++ workflow package loaded through the same capability boundary as local extensions. Phase A durable operation truth, Phase B source-aware extension hook dispatch, Phase C AgentKernel lifecycle extraction, Phase D default C/C++ workflow package ownership, Phase E local self-extension authoring, Phase F repo-side offline bundle validation, Phase G turn snapshot / capability registry foundation, Phase H runtime configuration reducer, Phase I workflow package manifest/read model, Phase J structured compaction state, Phase K recovery state, Phase L pack compatibility cleanup, and Phase M core alias cleanup are complete. The next architecture work should focus on real Win7 bundle smoke validation, real C/C++ project validation, and continuing stale compatibility audits.

- User-visible modes: `explore`, `spec`, `build`, `debug`, `verify`
- Default C/C++ execution model: `mode + discipline_profile + execution_phase`
- Default task system: `TaskGraph` projected through `task_status` and session task snapshots
- Generic workflow state carrier: `Session.workflow_state`
- Frontend workflow projection: `Session.workflow_state["workflow"]` is the source for `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, and `task_items`
- Default C/C++ task graph ownership: `CHarnessWorkflowExtension` keeps harness graph state behind the extension boundary; `Session` no longer exposes `task_graph`
- Default C/C++ workflow projection adapter: `src/embedagent/harness/workflow_projection.py` maps harness internals into the generic workflow payload
- Official build/verify execution: `list_recipes` + `run_recipe` + `report_quality_v2`
- Mode allowed-tool contracts are workflow-neutral; default harness tools are activated by the built-in C/C++ workflow extension
- Bare `ToolRuntime` construction is workflow-neutral; the bundled C/C++ workflow package registers recipe, quality, evidence, and task-status tools through `CHarnessWorkflowExtension.register_tools(...)`
- C/C++ workflow pack definitions live only under `src/embedagent/harness/packs.py`; the obsolete `embedagent.tooling.packs` compatibility re-export has been removed
- Official file discovery: `list_dir`, `glob_files`, `grep_text`
- Official permission engine: `PermissionPolicy` with structured rule matching and stable explanation text
- Official enterprise permission categories: `network` and `telemetry` exist for optional intranet/custom-service tools and telemetry flush/sink actions; both require explicit metadata and default to confirmation
- Official session runtime ownership: one session-scoped `QueryEngine` remains the facade and transcript/session mutation owner, while `AgentLifecycleJournal`, `AgentKernel`, `AgentLoop`, `AgentToolActionService`, and `AgentExtensionHost` own durable lifecycle writes, turn frames and suspend/resume boundaries, open turn-loop continuation, non-LLM tool action execution, and extension hook dispatch
- Official workflow extension hosting: `InProcessAdapter` owns one `ExtensionManager` shared with session-scoped `QueryEngine` and frontend tool catalog visibility
- Official extension runtime direction: `ExtensionManager` is the shared in-process capability boundary for workflow defaults, prompt/context hooks, tool-call/tool-result hooks, resource discovery contracts, dynamic in-process tool registration, extension diagnostics, and manifest-gated project-local Python extensions. Internally, public extension hook families dispatch through the source-aware `AgentEventBus` with event-specific reducer semantics and diagnostics.
- Official workflow prompt boundary: workflow-package prompt units are appended as `workflow_prompt` system messages. Legacy `harness_prompt` messages are accepted only for historical session/transcript dedupe compatibility.
- Official local resources: `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` are discovered as workspace-bound file resources and can be refreshed through `ToolRuntime.reload_resources()`, `InProcessAdapter.reload_resources(...)`, `/resources reload`, or `POST /api/sessions/{id}/resources/reload`. Skills support Agent Skills-style frontmatter; model-visible skills are listed in the system prompt, and `/skill:<name> [args]` explicitly expands a local skill file into a normal user turn.
- Official local self-extension authoring: `SelfExtensionAuthoringService` and the `author_local_capability` tool generate workspace-bound skills, prompts, recipes, and disabled-by-default project extension skeletons. Authoring writes files only; it does not reload resources or load Python extension code.
- Official project extension loading: hosted product paths may load enabled `.embedagent/extensions/<name>/extension.json` manifests with workspace-bound `extension.py` entrypoints; `enabled` defaults to false, enabled manifests must declare permissions, no dependency installation or remote registry is allowed, and loaded extensions register through the same shared `ExtensionManager`
- Official default extension assembly: `src/embedagent/default_extensions.py` installs the bundled C/C++ harness for hosted product paths; `QueryEngine` itself has no built-in harness import or constructor fallback
- Official harness refresh path: `CHarnessWorkflowExtension.refresh_managed_session()`; the old `HarnessStateSynchronizer` service facade has been removed
- Official runtime schema projection: `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single schema projection entry point; default harness-aware callers must pass extension-active tool names explicitly
- Official core accessor surface: mode registry, command sanitizer, and adapter class lookup use `get_mode_registry()`, `get_command_sanitizer()`, and `get_inprocess_adapter()` directly. Stale global/proxy aliases such as `MODE_REGISTRY`, `_DEFAULT_SANITIZER`, `get_default_sanitizer()`, `_inprocess_adapter`, and `_get_adapter_class()` have been removed.
- Official turn snapshot boundary: `QueryEngine` builds a `TurnSnapshot` after context assembly and active schema projection; provider requests consume `snapshot.messages` and `snapshot.tool_schemas`
- Official workflow package manifest read model: `WorkflowPackageManifest` describes package identity, supported modes/workflow states, tools, packs, resources, and diagnostics. The bundled C/C++ package manifest is derived from package-owned constants and exposed through `ExtensionManager`; it is not a public extension API and does not activate tools.
- Official capability read model: `CapabilityRegistry` describes tools, local file resources, slash commands, model profiles, and workflow packages with provenance metadata. It does not activate tools, execute tools, load extensions, or replace `PermissionPolicy`.
- Official runtime configuration read model: `RuntimeConfigReducer` projects safe replayable runtime configuration from `transcript.jsonl`, including credential-free model profile metadata, model-visible active tool names, local resource revision metadata, capability counts, and provider snapshot records. It is diagnostic/replay state and does not replace extension activation, tool execution, resource reload, project extension loading, or permission policy.
- Official compaction read model: `CompactionStateReducer` projects structured compact boundary state from `compact_boundary` transcript events, including token/message counts, preserved message anchors, trigger/phase/window diagnostics, safe file activity, evidence refs, extension-summary flags, and diagnostics. It feeds restore results, managed sessions, protocol snapshots, and session snapshots, but it does not drive context selection or become a second history source.
- Official recovery read model: `RecoveryStateReducer` projects safe hosted-resume recovery markers from `recovery_marker` transcript events, including trusted-prefix counts, stop reasons, operation/compaction/runtime summaries, and diagnostics. It feeds restore results, managed sessions, protocol snapshots, and session snapshots, but it does not change restore rules or drive runtime policy.
- Official offline runtime contract: `scripts/offline-runtime-contract.json` lists every runtime-invoked bundled external tool, including Python, MinGit, ripgrep, Universal Ctags, and the LLVM/Clang child executables. Bundle validators consume this contract instead of maintaining separate hard-coded tool lists.
- Official frontend vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`
- Official GUI app-shell boundary: `GET /api/app/bootstrap` and `/api/app/workspaces*` expose GUI-owned workspace/app diagnostics, app commands, and local settings; this is separate from Agent Core session truth and from `GET /api/sessions/{id}/bootstrap`
- Official GUI thread lifecycle boundary: GUI `rename`, `fork`, and `archive` actions flow through the session lifecycle facade and update session summary/projection metadata for app thread lists; they do not rewrite transcript history, own workflow state, activate tools, decide permissions, load extensions, or create source-control checkpoints.
- Official GUI terminal boundary: the terminal bottom drawer is a GUI app-shell hosted, thread-scoped surface implemented with Windows 7-compatible Python stdlib subprocess pipes. It is not a full PTY, does not add runtime dependencies, and does not write transcript history, telemetry, workflow state, source-control checkpoints, or Agent Core policy.
- Official GUI source-control boundary: the Source Control right-panel is a GUI app-shell hosted, active-workspace surface. It uses bundled/workspace MinGit through a read-only backend service for local Git status and file diffs only; it does not implement remote providers, push/pull, staging, commit, checkpoint mutation, transcript writes, workflow state, telemetry, permission policy, runtime reducers, provider config, extension loading, or Agent Core behavior.
- Official session-history model: `transcript.jsonl -> Session -> SessionHistoryAssembler -> /api/sessions/{id}/bootstrap`
- Official session-operation model: schema v2 `operation_started` / `operation_finished` / `operation_interrupted` events are the durable runtime operation truth; legacy `step_started`, `tool_call`, `tool_result`, and `loop_transition` events remain session replay/history events, not operation-state inference inputs. Current operation families include turns, agent steps, context assembly, context snapshots, provider requests, tool calls, pending interactions, workflow patches, and save points. Restore projections close unfinished operations as interrupted, while live session snapshots preserve active operations in `operation_diagnostics`.

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
- `src/embedagent/agent_lifecycle.py`
  Durable lifecycle journal for schema v2 operation events, save points, pending interaction lifecycle, and context operation payload helpers.
- `src/embedagent/agent_kernel.py`
  Internal lifecycle kernel for turn frames and pending interaction creation/resolution boundaries.
- `src/embedagent/agent_loop.py`
  Pi-style open continuation loop for agent steps, provider/context attempts, compact retry, tool batches, guard stops, abort transitions, and explicit loop safety-limit compatibility transitions.
- `src/embedagent/agent_loop_continuation.py`
  Internal continuation decision policy for open-loop stop, continue, abort, and safety-limit behavior.
- `src/embedagent/agent_tool_action_service.py`
  Non-LLM action executor for active-tool checks, extension pre/post hooks, permission-gated runtime dispatch, path write guards, and extension-owned tool calls.
- `src/embedagent/agent_extension_host.py`
  QueryEngine-side extension host for prompt/context hooks, workflow state initialization, dynamic tool registration, explicit active schema projection, tool-call/tool-result hooks, and workflow patches.
- `src/embedagent/agent_event_bus.py`
  Source-aware internal event bus for extension observer/reducer dispatch and event-specific reducer stopping.
- `src/embedagent/turn_snapshot.py`
  Frozen provider-request input built from context messages, active schemas, workflow state, runtime metadata, and capability projections.
- `src/embedagent/capabilities.py`
  Non-executing capability read model for runtime tools, local file resources, slash commands, and model profiles.
- `src/embedagent/runtime_config.py`
  Reducer-backed runtime configuration projection for model profile metadata, active tool names, local resource revisions, capability counts, and provider snapshot diagnostics.
- `src/embedagent/compaction_state.py`
  Reducer-backed compaction projection for compact boundary metadata, safe file activity, evidence refs, and restore diagnostics.
- `src/embedagent/recovery_state.py`
  Reducer-backed recovery projection for hosted resume markers, trusted prefix metadata, and restore diagnostics.
- `src/embedagent/telemetry.py`
  Local-only safe telemetry envelope helper that redacts prompt/source/output/credential fields before future sinks see metadata.
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
- `author_local_capability`
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

Local resource reload is file-only. Skills and prompts are surfaced as discovered resources, while `.embedagent/recipes/*.json` contributes recipe definitions to the existing `list_recipes` / `run_recipe` path. Skills may include Agent Skills-style frontmatter (`name`, `description`, `disable-model-invocation`); visible skills are summarized in system prompts, and `/skill:<name> [args]` expands the skill Markdown body into the next user turn. Reloading resources records transcript-backed diagnostics and does not execute project-local Python code. `author_local_capability` can create local resource files and disabled extension skeletons, but the caller must still use resource reload or explicit extension loading as separate follow-up operations.

Project-local Python extensions are a separate, explicit opt-in path under `.embedagent/extensions/<name>/`. They require `extension.json` with `enabled: true` and a permissions list, load only a workspace-bound `extension.py` entrypoint, receive a narrow API object, and are surfaced in session snapshots under `extensions.project_extensions`. They cannot replace built-in tools and any dynamic tools they register remain metadata-classified and permission-gated.

## Development Constraints

- Do not require Docker, WSL, VS Code, Node.js-at-runtime, or online services.
- Keep runtime compatible with Python `>=3.8,<3.9`.
- The offline bundle must contain every runtime dependency it uses.
- Optional intranet integrations must stay opt-in extension/provider/sink capabilities; network failure must not prevent offline use.
- Runtime-invoked external tools must be represented in `scripts/offline-runtime-contract.json` and validated by the packaging gates.
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
- Pi-inspired minimal Core Phase A durable operation log: completed
- Pi-inspired minimal Core Phase B HookBus/reducer registry: completed
- Pi-inspired minimal Core Phase C AgentKernel lifecycle extraction: completed
- Pi-inspired minimal Core Phase D default C/C++ workflow package ownership: completed
- Pi-inspired minimal Core Phase E local self-extension authoring: completed
- Pi-inspired minimal Core Phase F repo-side offline bundle validation: completed
- Pi-inspired minimal Core Phase G turn snapshot / capability registry foundation: completed
- Pi-inspired minimal Core Phase H runtime configuration reducer: completed
- Pi-inspired minimal Core Phase I workflow package manifest/read model: completed
- Pi-inspired minimal Core Phase J structured compaction state: completed
- Pi-inspired minimal Core Phase K recovery state: completed
- Pi-inspired minimal Core Phase L pack compatibility cleanup: completed
- Pi-inspired minimal Core Phase M core alias cleanup: completed
- Remaining work: clean Win7 bundle smoke, real C project validation, and remaining stale compatibility audit

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
