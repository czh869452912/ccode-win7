# Overall Solution Architecture

## 1. Scope

EmbedAgent is a native, offline-first Agent IDE core for C/C++ engineering.

The stable architecture assumptions are:

- Windows 7 compatibility
- Python 3.8 runtime target
- Offline bundle delivery
- Agent Core first, UI shells replaceable
- Clang-centered toolchain

## 2. Top-Level Structure

The product is organized around one main execution spine:

`Frontend -> Core Adapter -> InProcessAdapter -> Session Runtime -> QueryEngine -> AgentKernel -> AgentLoop / AgentLifecycleJournal -> AgentToolActionService -> AgentExtensionHost / ToolRuntime / PermissionPolicy -> Context/Stores`

### Frontend Layer

- `src/embedagent/frontend/tui/`
- `src/embedagent/frontend/gui/`

These are shells only. They do not own workflow semantics.

The GUI shell has a replaceable app-shell boundary for desktop-host state:
`src/embedagent/frontend/gui/backend/app_shell.py` wraps the GUI app host and
projects recent workspaces, active workspace metadata, safe host/runtime/
renderer diagnostics, app-level command metadata, and GUI-local settings. The
matching frontend model lives under
`src/embedagent/frontend/gui/webapp/src/app-shell/`. This boundary is not Agent
Core: it must not own sessions, transcript history, workflow state, mode/tool
policy, permission decisions, extension loading, provider configuration, or
runtime reducers.

GUI thread lifecycle operations (`rename`, `fork`, and `archive`) are exposed
through the session lifecycle facade and consumed by the GUI app shell. They
update session summary/projection metadata used by app thread lists; they do
not rewrite transcript history, own workflow state, activate tools, decide
permissions, load extensions, or create source-control checkpoints.

The GUI terminal bottom drawer is also app-shell hosted. `GUIBackend` owns an
in-memory terminal service bound to the active workspace and exposes
thread-scoped terminal HTTP routes plus `terminal_event` WebSocket messages.
The service uses Python stdlib subprocess pipes for Windows 7 compatibility and
offline deployment; it is not a full PTY and does not introduce ConPTY,
`node-pty`, `pywinpty`, `pexpect`, runtime Node, Electron, Docker, WSL, VS Code,
or online-service dependencies. Terminal buffers are GUI-local display state
only and must not become transcript history, workflow state, telemetry,
permission policy, runtime reducer truth, source-control checkpoints, or Agent
Core behavior.

### Protocol / Core Layer

- `src/embedagent/protocol/`
- `src/embedagent/core/`

This is the stable contract boundary between UI and Agent Core.

### Agent Core Layer

- `src/embedagent/inprocess_adapter.py`
- `src/embedagent/query_engine.py`
- `src/embedagent/agent_lifecycle.py`
- `src/embedagent/agent_kernel.py`
- `src/embedagent/agent_loop.py`
- `src/embedagent/agent_tool_action_service.py`
- `src/embedagent/agent_extension_host.py`
- `src/embedagent/agent_event_bus.py`
- `src/embedagent/turn_snapshot.py`
- `src/embedagent/capabilities.py`
- `src/embedagent/runtime_config.py`
- `src/embedagent/compaction_state.py`
- `src/embedagent/recovery_state.py`
- `src/embedagent/workflow_package_manifest.py`
- `src/embedagent/session_runtime.py`
- `src/embedagent/session_projector.py`
- `src/embedagent/session_history.py`
- `src/embedagent/extensions.py`
- `src/embedagent/default_extensions.py`
- `src/embedagent/harness/workflow_projection.py`
- `src/embedagent/tools/`
- `src/embedagent/context.py`
- `src/embedagent/permissions.py`

This is the product core.

The default C/C++ harness is now entered through the in-process workflow extension boundary. Harness internals remain bundled and enabled by default, but `QueryEngine` must not import concrete harness task classes directly.

`InProcessAdapter` owns the hosted runtime's `ExtensionManager` and passes that same manager to each session-scoped `QueryEngine`. Frontend tool catalog visibility is computed from the same manager, so model-facing tools and shell metadata share one extension chain.

`ExtensionManager` is now the shared in-process capability boundary. The current default C/C++ harness remains the bundled workflow extension, while the same boundary also carries generic prompt/context hooks, tool-call and tool-result interception, resource discovery contracts, dynamic in-process tool registration, extension diagnostics, and manifest-gated project-local Python extensions. Extension hook internals dispatch through `AgentEventBus`, the source-aware observer/reducer bus introduced and closed out in Phase B. Event-specific reducer semantics cover merge, union, first-result, first-block-wins, sequential argument rewrite, and trusted fail-closed diagnostics. Workspace-local file resources under `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` are official discoverable resources. Skills support Agent Skills-style frontmatter, system-prompt listing for visible skills, and explicit `/skill:<name> [args]` expansion as Markdown context; they are not executable extension code.

`AgentExtensionHost` is the session-engine side of that boundary. It builds extension contexts and workflow events, initializes workflow state, applies prompt/context hooks, registers dynamic tools, computes extension-aware active tool names, requests explicit tool schemas, applies tool-call/tool-result hooks, and handles extension-owned tool calls. `QueryEngine` keeps a compatibility `extension_manager` reference, but extension hook dispatch is centralized in `AgentExtensionHost`.

Workflow-package prompt units are appended as generic `workflow_prompt` system messages. Historical `harness_prompt` messages remain recognized only for session/transcript dedupe compatibility; new Agent Core prompt injection should not use harness-shaped message kinds.

`AgentLifecycleJournal` owns durable lifecycle writes for schema v2 operation events, transition save points, pending interaction lifecycle events, and context operation payload helpers. `AgentKernel` owns turn frames and pending interaction create/resolve boundaries. `AgentToolActionService` owns non-LLM tool action execution: active-tool checks, extension pre/post hooks, permission evaluation, path write guards, runtime dispatch, and extension-owned tool calls. `AgentLoop` owns turn-loop orchestration: agent step lifecycle, context/provider attempts, compact retry, tool batch interruption, guard-stop, abort, and max-turn transitions. `QueryEngine` remains the public session facade and keeps ownership of transcript-backed session mutation compatibility.

`TurnSnapshot` is the explicit frozen input for one provider request. `QueryEngine` builds it after context assembly and active tool schema projection, then calls the provider with `snapshot.messages` and `snapshot.tool_schemas`. Snapshot diagnostics may record safe metadata such as `snapshot_id`, mode/workflow state, active tool names, credential-free model profile metadata, and capability counts; they must not record prompt bodies, file contents, raw tool outputs, or credentials.

`WorkflowPackageManifest` is a non-executing read model for workflow package identity, supported modes and workflow states, declared tools, packs, resource scopes, and diagnostics. The bundled C/C++ package exposes its manifest through the extension boundary and derives it from the same package-owned constants that drive tool metadata and pack definitions. Manifest projection is diagnostic/control-plane state only; it does not activate tools, grant permissions, execute tools, or load packages.

`CapabilityRegistry` is a non-executing read model for runtime tools, local file resources, slash commands, model profiles, and workflow packages. It records provenance and metadata for diagnostics and future reducer work. It does not decide active tools, execute tools, reload resources, load extensions, or replace permission checks; those responsibilities remain with `AgentExtensionHost` / `ExtensionManager`, `ToolRuntime` / `AgentToolActionService`, resource reload paths, project extension loading, and `PermissionPolicy`.

`RuntimeConfigReducer` is the replayable runtime configuration read model. It reduces safe transcript events into credential-free model profile metadata, model-visible active tool names, local resource revision metadata, capability counts, and provider snapshot records. It feeds `ManagedSession.runtime_config`, session snapshots, and provider `TurnSnapshot` resource revision/model metadata when available. It remains diagnostic/replay state and must not become an active-tool selector, resource loader, extension loader, tool executor, or permission engine.

`ContextManager` owns deterministic context assembly. In addition to reactive compact retry after provider context-limit errors, it may pre-provider rebuild with the internal compact policy when the assembled input approaches `auto_compact_threshold_ratio` and there is older turn history to summarize. That trigger is expressed as a context pipeline step and compact-boundary diagnostic metadata, not as a new public extension API. `ContextWindowState` is a small internal value object that derives safe trigger/phase/window-generation diagnostics from context pipeline steps; it is not a durable history source or policy engine.

`CompactionStateReducer` is the replayable structured compaction read model. It reduces `compact_boundary` transcript events into safe boundary records with preserved message anchors, token/message counts, trigger/phase/window-generation diagnostics, file activity paths, evidence refs, extension-summary flags, and duplicate/malformed diagnostics. It feeds restore results, `ManagedSession.compaction_state`, protocol snapshots, and session snapshots. It remains diagnostic/replay state and must not become a context selector, summary generator, extension executor, permission engine, or second session-history source.

`RecoveryStateReducer` is the replayable hosted recovery read model. It reduces `recovery_marker` transcript events into safe recovery records with trusted-prefix counts, stop reasons, skip summaries, operation/compaction/runtime summaries, and duplicate/malformed diagnostics. It feeds restore results, `ManagedSession.recovery_state`, protocol snapshots, and session snapshots. It remains diagnostic/replay state and must not change restore validation, retry tool calls, select modes, activate tools, load extensions, bypass permissions, or become frontend-owned policy.

Default bundled extension assembly is outside `QueryEngine` in `src/embedagent/default_extensions.py`. A bare `QueryEngine` receives an empty `ExtensionManager`; hosted product paths install the default C/C++ harness explicitly before constructing session engines. Hosted product paths may additionally load project-local extensions from `.embedagent/extensions/<name>/extension.json` when the manifest is explicitly enabled and declares permissions. Public remote registries, plugin marketplaces, runtime dependency installation, built-in tool replacement, and multi-agent orchestration remain out of scope.

Optional enterprise/intranet integrations are hosted capabilities, not Agent Core responsibilities. Intranet Git adapters, custom service providers, model gateways, organization-local catalogs, and telemetry sinks must be explicitly configured, trusted, disableable, and failure-tolerant. They attach through provider, extension, workflow-package, or passive sink boundaries with source metadata and normal permission checks; they must not make startup, default C/C++ workflows, restore, resource reload, or session history depend on network availability.

The foundation for that boundary is implemented as metadata and policy, not as network behavior. `network` and `telemetry` are official permission categories recognized by `PermissionPolicy`, dynamic tool registration, project extension manifests, self-extension authoring, frontend permission context, and tool catalogs. `src/embedagent/telemetry.py` builds local safe envelopes for future sinks by redacting or summarizing prompt/source/output/credential metadata; it does not upload data or create a telemetry service.

Harness state refresh in the product adapter path goes through `CHarnessWorkflowExtension.refresh_managed_session()` behind the default C harness workflow extension. The old `HarnessStateSynchronizer` service facade has been removed rather than kept as a parallel compatibility path.

### Session Runtime Ownership

- `ManagedSession` hosts thread/lock/status and durable `Session` references
- one session-scoped `QueryEngine` is the facade and transcript/session mutation owner; `AgentKernel`, `AgentLifecycleJournal`, `AgentLoop`, `AgentToolActionService`, and `AgentExtensionHost` own lifecycle, journal, loop, action, and extension dispatch internals
- `InProcessAdapter` is a host/bridge layer and must not mint duplicate workflow identities
- `SessionSnapshotProjector` and `SessionHistoryAssembler` are projections, not workflow truth
- `SessionSnapshotProjector` reads the generic workflow projection, not default harness internals
- `runtime_config` in session snapshots is reducer-backed diagnostic state, not frontend-owned policy
- `compaction_state` in session snapshots is reducer-backed diagnostic state, not frontend-owned context policy
- `recovery_state` in session snapshots is reducer-backed diagnostic state, not frontend-owned recovery policy

## 3. Official Execution Model

The repository now uses one default C/C++ workflow model:

- user-visible `mode`
- internal `discipline_profile`
- internal `execution_phase`
- `TaskGraph` as default harness workflow truth
- `Session.workflow_state` as the generic workflow-state carrier

### Official Modes

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

`build` is the only implementation mode.

### Official Task Model

The default task system is no longer prompt-only.

Official task truth flows through:

- `TaskGraph`
- `task_status`
- session task snapshots

`Session.task_graph` has been removed. The default C/C++ harness keeps `TaskGraph` ownership behind `CHarnessWorkflowExtension` and a harness-owned session graph state adapter, while the core/frontend boundary carries only `Session.workflow_state["workflow"]`. Importing or instantiating `embedagent.session.Session` must not load harness task graph internals.

Frontend-facing task projection now comes from `Session.workflow_state["workflow"]`. The default C/C++ harness extension is responsible for keeping that projection synchronized with its internal task graph and persisted session task snapshots. The payload assembly itself is centralized in `src/embedagent/harness/workflow_projection.py`, which is the adapter from C harness internals to generic workflow state.

Workflow-neutral strategies, projectors, and frontend task APIs read task state from that generic workflow projection rather than from harness task graph internals.

Session snapshots carry:

- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`
- `extensions`
- `extension_diagnostics`

## 4. Tool Architecture

The tool runtime has one official facade:

- `src/embedagent/tools/runtime.py`

Harness selects focused tool packs by mode/phase, but execution still flows through one runtime object.

Built-in mode allowed-tool lists are workflow-neutral permission/write contracts. Default C/C++ workflow tools are activated by the harness extension and packs, then passed to runtime schema projection as explicit active tool names.

`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it projects only the workflow-neutral mode contract; it must not be used to activate the default harness pack implicitly.

The tool runtime is source-aware and dynamically extensible. A bare `ToolRuntime` registers workflow-neutral built-ins only. In-process extensions can register `ToolDefinition` objects into the shared runtime; the bundled C/C++ workflow package uses this same boundary for recipe, quality, evidence, and task-status tools. Source metadata is projected through the existing catalog, and active-tool visibility still flows through `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)`.

C/C++ workflow pack definitions live only in `src/embedagent/harness/packs.py`. The obsolete `src/embedagent/tooling/packs.py` re-export and package-root pack aliases have been removed so Agent Core no longer carries a second pack import surface.

Local self-extension authoring is a workflow-neutral write capability. `SelfExtensionAuthoringService` writes workspace-bound `.embedagent` skills, prompts, recipes, and disabled-by-default project extension skeletons. The `author_local_capability` tool exposes that service in build/debug mode with `workspace_write` permission. Authoring does not refresh resource caches and does not import or enable generated Python extensions; resource reload and project extension loading remain separate operations.

The tool runtime also owns a file-only local resource cache. `ToolRuntime.reload_resources()` refreshes workspace-bound `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` resources. Recipe JSON files feed the existing recipe contract, while skills and prompts are surfaced as resources but not executed as local code.

Project-local Python extensions are loaded by hosted adapters through `src/embedagent/project_extensions.py`, not by resource reload. The loader validates `extension.json`, keeps entrypoints inside the extension directory, passes a narrow workspace-bound API object, registers loaded objects into the shared `ExtensionManager`, and projects load state under `Session.workflow_state["extensions"]["project_extensions"]`.

Runtime-invoked external binaries are part of the tool architecture even when they are not model-visible tools. `scripts/offline-runtime-contract.json` is the repo-side contract for bundled Python, MinGit, ripgrep, Universal Ctags, and LLVM/Clang child executables. Packaging validators consume this contract so the runtime, bundle gate, and dependency checker share one external-tool truth.

Capability projections are read-only. `ToolRuntime.capability_descriptors()` projects registered tools and cached local file resources; `ExtensionManager.package_manifests()` collects workflow package manifests from registered extensions; `InProcessAdapter.capability_snapshot()` combines runtime capabilities, slash commands, workflow packages, and the active model profile. These projections are not active-tool policy and must not be used to bypass `AgentExtensionHost`, `ExtensionManager`, or `PermissionPolicy`.

Runtime configuration projections are also read-only. `runtime_configured`, `resource_reloaded`, and provider-request snapshot metadata are reduced by `RuntimeConfigReducer` so restore and frontend diagnostics can explain model profile metadata, active model-visible tool names, local resource revision, and capability counts. `resource_discovered` remains discovery/replay diagnostics only and does not advance runtime resource revision state.

### Official Tool Families

#### File / Discovery

- `read_file`
- `list_dir`
- `glob_files`
- `grep_text`
- `write_file`
- `edit_file`

#### Build / Verify

- `list_recipes`
- `run_recipe`
- `report_quality_v2`
- `record_failing_evidence`

#### Workflow / Interaction

- `task_status`
- `ask_user`

#### Supporting Capabilities

- `git_status`
- `git_diff`
- `git_log`
- `run_command` as controlled fallback

## 5. Workflow Extension And Harness Layer

`src/embedagent/extensions.py` owns the local in-process capability extension contract.

The default C/C++ harness extension in `src/embedagent/harness/extension.py` owns:

- mode registry
- discipline defaults
- phase advancement rules
- prompt unit construction
- task graph construction
- session task snapshot persistence

This keeps workflow structure out of the frontend, out of ad-hoc prompt text, and out of the workflow-neutral parts of Agent Core.

## 6. Permission Layer

`src/embedagent/permissions.py` is the only official permission engine.

It owns:

- action category mapping
- rule loading
- rule matching
- stable explanation text
- frontend-visible permission context

The frontend should never infer permission policy from mode alone.

## 7. Context Layer

`src/embedagent/context.py` and `src/embedagent/workspace_intelligence.py` own:

- context budgets
- reducer registry
- tool-result replacement
- summary assembly
- workspace intelligence evidence

The context system is aligned to the official harness vocabulary, especially:

- `build`
- `list_dir`
- `glob_files`
- `grep_text`
- `run_recipe`
- `report_quality_v2`
- `task_status`

## 8. Session / Transcript Truth

Session truth is distributed across:

- live `Session`
- transcript events
- `SessionHistoryAssembler` projections
- tool result storage/projections
- summary store
- task snapshots

No frontend should maintain its own workflow truth separate from session snapshots and replayable events.

Additional ownership rules:

- engine-issued `turn_id` / `step_id` / `step_index` are the only official execution anchors
- resumed interactions must re-enter the same action pipeline used by first execution
- snapshot/bootstrap payloads are projected from session truth and do not own side effects

### Session History Rule

Official session-history ownership is:

- `transcript.jsonl` is the only durable session-history ledger
- `Session` / `session.turns` is the only live structured history state
- `timeline.jsonl` is replay transport only
- GUI activation reads one bootstrap payload that includes snapshot, structured history, plan, permission context, and replay metadata

Historical turns must never be rebuilt from replay-log tails.

### Durable Operation State Rule

Durable runtime operation state is projected from explicit schema v2 lifecycle events:

- `operation_started`
- `operation_finished`
- `operation_interrupted`

`OperationLogReducer` consumes the validated transcript prefix and must not infer operation state from legacy replay/history events such as `step_started`, `tool_call`, `tool_result`, or `loop_transition`. Those events still rebuild structured session history and tool topology. Operation lifecycle events explain runtime execution units such as turns, agent steps, context assembly, context snapshots, provider requests, tool calls, pending interactions, workflow patches, and save points. Restore-time projections close unfinished operations as interrupted, while live snapshot projections preserve unfinished operations as active. Diagnostics such as `operation_diagnostics` are reducer projections over this operation state and must not become a second session-history source.

### Runtime Configuration State Rule

Replayable runtime configuration is projected from safe schema v2 events:

- `runtime_configured`
- `resource_reloaded`
- provider-request `operation_started` metadata containing safe `turn_snapshot` fields

`RuntimeConfigReducer` consumes the validated transcript prefix and must not infer runtime configuration from frontend replay, `resource_discovered`, prompts, raw tool outputs, or local extension code. Session snapshots may expose `runtime_config` for diagnostics and restore visibility; that projection does not activate tools, execute tools, reload resources, load project extensions, or bypass permissions.

### Structured Compaction State Rule

Replayable compaction state is projected from compact boundary events:

- `compact_boundary`

`CompactionStateReducer` consumes the validated transcript prefix and must not infer compaction state from `timeline.jsonl`, prompts, raw tool outputs, or local extension code. Session snapshots may expose `compaction_state` for diagnostics and restore visibility; that projection does not select active context, rewrite summaries, load extensions, execute tools, or bypass permissions. `Session.compact_boundaries` remains live context compatibility state, not a separate durable truth.

### Recovery State Rule

Replayable hosted recovery state is projected from recovery marker events:

- `recovery_marker`

`RecoveryStateReducer` consumes the validated transcript prefix and must not infer recovery state from `timeline.jsonl`, prompts, raw tool outputs, or local extension code. Hosted resume may append safe recovery markers after restoring a trusted prefix. Session snapshots may expose `recovery_state` for diagnostics and restore visibility; that projection does not change restore validation, retry tool calls, select modes, activate tools, select context, load extensions, or bypass permissions.

## 9. Frontend Contract

The frontend-facing vocabulary is now:

- `build`, not `code`
- `tasks`, not `todos`
- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

If a frontend change introduces older terms back into the product shell, that is an architectural regression.

## 10. Bundling Model

The shipped product is expected to be a self-contained offline bundle.

The architecture therefore assumes runtime discovery for bundled tools, not global machine dependencies.

`scripts/offline-runtime-contract.json` enumerates the bundled external tools that runtime flows may invoke. The release bundle validation gate and dependency checker must consume this contract rather than maintaining independent hard-coded lists. A clean Windows 7 unpack-and-run smoke remains the final release proof that the contract-backed bundle is actually portable.

Offline-first does not forbid explicitly configured intranet use. It means network services are optional adapters with timeouts, local fallback/disable paths, and safe diagnostics. Telemetry, when present, is a passive sink over safe structured lifecycle/capability/diagnostic events and must not export prompts, source text, raw tool outputs, API keys, permission payloads, tokens, or approval secrets. The current code has only the permission/category and safe-envelope foundation for those future adapters; it does not ship a network uploader.

## 11. Design Rule

Do not reintroduce parallel V1/V2 execution paths.

When changing architecture:

- promote the new path to the only official path
- then delete or archive the old path
- keep current docs describing only the official architecture

## 12. Next Architecture Direction

The current official architecture remains the baseline described above. The next architecture program is defined by `pi-inspired-agent-core-blueprint.md`.

That program keeps learning from Pi at two levels:

- functional design: extensions, resources, durable sessions, compaction, command surfaces, model capability metadata, observability, and self-extension workflows
- architecture philosophy: a smaller core, capability registration, event reducers, turn snapshots, save points, and replaceable workflow packages

The Pi lesson for enterprise capabilities is structural rather than permissive: keep Core small, expose stable capability/event/provider boundaries, and let optional adapters carry environment-specific behavior. EmbedAgent keeps the stricter offline and Windows 7 baseline, so intranet integrations must stay outside Core and must degrade cleanly when absent.

The intended long-term direction is that Agent Core can be described without C/C++ workflow vocabulary. The bundled C/C++ harness remains the default product workflow, but it should continue moving toward a first-party workflow package loaded through the same capability boundary as other local extensions.

This is a gradual direction, not a statement that the target state is fully implemented. Phase A durable operation reducers, Phase B extension hook bus dispatch, Phase C AgentKernel lifecycle extraction, Phase D default C/C++ workflow package ownership, Phase E local self-extension authoring, Phase F repo-side offline bundle validation, Phase G turn snapshot / capability registry foundation, Phase H runtime configuration reducer, Phase I workflow package manifest/read model, Phase J structured compaction state, Phase K recovery state, Phase L pack compatibility cleanup, and Phase M core alias cleanup are complete. Near-term changes should preserve the current hosted behavior while completing real Win7 smoke validation, continuing real C/C++ project validation, and continuing stale compatibility audits.

Phase M removed the remaining core-level global/proxy compatibility aliases for
mode registry access, command sanitizer access, and hosted adapter class lookup.
Current code should use `get_mode_registry()`, `get_command_sanitizer()`, and
`get_inprocess_adapter()` directly instead of compatibility names.
