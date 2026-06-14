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

`ExtensionManager` is now the shared in-process capability boundary. The current default C/C++ harness remains the bundled workflow extension, while the same boundary also carries generic prompt/context hooks, tool-call and tool-result interception, resource discovery contracts, dynamic in-process tool registration, extension diagnostics, and manifest-gated project-local Python extensions. Extension hook internals dispatch through `AgentEventBus`, the source-aware observer/reducer bus introduced and closed out in Phase B. Event-specific reducer semantics cover merge, union, first-result, first-block-wins, sequential argument rewrite, and trusted fail-closed diagnostics. Workspace-local file resources under `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` are official discoverable resources.

`AgentExtensionHost` is the session-engine side of that boundary. It builds extension contexts and workflow events, initializes workflow state, applies prompt/context hooks, registers dynamic tools, computes extension-aware active tool names, requests explicit tool schemas, applies tool-call/tool-result hooks, and handles extension-owned tool calls. `QueryEngine` keeps a compatibility `extension_manager` reference, but extension hook dispatch is centralized in `AgentExtensionHost`.

`AgentLifecycleJournal` owns durable lifecycle writes for schema v2 operation events, transition save points, pending interaction lifecycle events, and context operation payload helpers. `AgentKernel` owns turn frames and pending interaction create/resolve boundaries. `AgentToolActionService` owns non-LLM tool action execution: active-tool checks, extension pre/post hooks, permission evaluation, path write guards, runtime dispatch, and extension-owned tool calls. `AgentLoop` owns turn-loop orchestration: agent step lifecycle, context/provider attempts, compact retry, tool batch interruption, guard-stop, abort, and max-turn transitions. `QueryEngine` remains the public session facade and keeps ownership of transcript-backed session mutation compatibility.

Default bundled extension assembly is outside `QueryEngine` in `src/embedagent/default_extensions.py`. A bare `QueryEngine` receives an empty `ExtensionManager`; hosted product paths install the default C/C++ harness explicitly before constructing session engines. Hosted product paths may additionally load project-local extensions from `.embedagent/extensions/<name>/extension.json` when the manifest is explicitly enabled and declares permissions. Remote registries, plugin marketplaces, dependency installation, built-in tool replacement, and multi-agent orchestration remain out of scope.

Harness state refresh in the product adapter path goes through `CHarnessWorkflowExtension.refresh_managed_session()` behind the default C harness workflow extension. The old `HarnessStateSynchronizer` service facade has been removed rather than kept as a parallel compatibility path.

### Session Runtime Ownership

- `ManagedSession` hosts thread/lock/status and durable `Session` references
- one session-scoped `QueryEngine` is the facade and transcript/session mutation owner; `AgentKernel`, `AgentLifecycleJournal`, `AgentLoop`, `AgentToolActionService`, and `AgentExtensionHost` own lifecycle, journal, loop, action, and extension dispatch internals
- `InProcessAdapter` is a host/bridge layer and must not mint duplicate workflow identities
- `SessionSnapshotProjector` and `SessionHistoryAssembler` are projections, not workflow truth
- `SessionSnapshotProjector` reads the generic workflow projection, not default harness internals

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

The tool runtime also owns a file-only local resource cache. `ToolRuntime.reload_resources()` refreshes workspace-bound `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` resources. Recipe JSON files feed the existing recipe contract, while skills and prompts are surfaced as resources but not executed as local code.

Project-local Python extensions are loaded by hosted adapters through `src/embedagent/project_extensions.py`, not by resource reload. The loader validates `extension.json`, keeps entrypoints inside the extension directory, passes a narrow workspace-bound API object, registers loaded objects into the shared `ExtensionManager`, and projects load state under `Session.workflow_state["extensions"]["project_extensions"]`.

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

The intended long-term direction is that Agent Core can be described without C/C++ workflow vocabulary. The bundled C/C++ harness remains the default product workflow, but it should continue moving toward a first-party workflow package loaded through the same capability boundary as other local extensions.

This is a gradual direction, not a statement that the target state is fully implemented. Phase A durable operation reducers, Phase B extension hook bus dispatch, Phase C AgentKernel lifecycle extraction, and Phase D default C/C++ workflow package ownership are complete. Near-term changes should preserve the current hosted behavior while building the local self-extension authoring loop.
