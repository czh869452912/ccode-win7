# Implementation Roadmap

## 1. Purpose

This document tracks the stable sequencing strategy for EmbedAgent.

It is not a historical backlog dump.
It describes the current implementation order and the next remaining priorities.

## 2. Sequencing Principles

- Keep Python runtime compatible with `>=3.8,<3.9`
- End each major program with a runnable, verifiable milestone
- Prefer one promoted architecture path over long-lived compatibility branches
- Keep current docs aligned with current code

## 3. Completed Core Programs

The following core programs are now complete in the current architecture baseline:

1. Runtime promotion
2. Mode vocabulary cutover
3. Context / intelligence cutover
4. Permission / task truth cutover
5. Frontend / protocol officialization
6. Agent core ownership cutover

This means the repository now has one official execution spine centered on:

- `build` instead of `code`
- `TaskGraph` instead of prompt-only todo flow
- `run_recipe` / `report_quality_v2` instead of legacy duplicate verify tools in product paths
- frontend `tasks` vocabulary instead of `todos`

Recent workflow-boundary work has started slimming Agent Core without changing the default C/C++ behavior:

- `src/embedagent/extensions.py` now provides the in-process workflow extension boundary
- the C/C++ harness is wrapped as the default built-in workflow extension
- `QueryEngine` no longer imports or instantiates `TaskGraph` directly
- `QueryEngine` no longer imports or constructs the default C harness extension; hosted paths install bundled extensions through `default_extensions.py`
- `Session.workflow_state` is the generic workflow-state carrier; `Session.task_graph` has been removed and default C harness graph state is owned behind `CHarnessWorkflowExtension`
- `SessionSnapshotProjector` and live frontend task APIs now project harness task fields from `Session.workflow_state["workflow"]`
- extracted core strategies now read task-status projection from `Session.workflow_state["workflow"]` instead of inspecting `Session.task_graph`
- `src/embedagent/harness/workflow_projection.py` now owns the C harness to generic workflow payload adapter
- `InProcessAdapter` no longer constructs `HarnessRunner` directly; harness refresh and task-snapshot persistence are delegated to the built-in C harness extension
- `QueryEngine` now asks for schemas using explicit active tool names through `ToolRuntime.schemas_for(...)`, so default harness pack activation is owned by the workflow extension boundary
- `CORE_PACK` no longer contains default harness workflow tools; build/debug/verify packs keep those tools explicitly for compatibility
- built-in mode `allowed_tools` no longer own default harness workflow tools; recipe, quality, evidence, and task-status tools are activated by the C harness extension
- `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is now the single runtime schema projection entry point; default-harness paths use extension-active explicit tool names
- `TurnOrchestrator` receives an injected allowed-tool policy from `QueryEngine` instead of calling runtime allowed-tool aliases
- `InProcessAdapter` now owns one `ExtensionManager` shared with session-scoped `QueryEngine` and frontend tool catalog visibility
- `ExtensionManager` now carries generic diagnostics, resource discovery hooks, context hooks, tool-call/tool-result hooks, and dynamic in-process tool registration
- local file resources under `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` can be refreshed through the runtime, adapter, slash command, and GUI/core API; recipe JSON files feed the existing recipe contract
- manifest-gated project-local Python extensions can be loaded from enabled `.embedagent/extensions/<name>/extension.json` manifests by hosted product paths and are registered into the shared `ExtensionManager`
- `AgentExtensionHost` now centralizes QueryEngine-side extension dispatch, dynamic tool registration, extension-aware active schema projection, context patches, tool-call hooks, tool-result hooks, workflow patches, and extension-owned tool handling
- `AgentEventBus` now provides the internal source-aware observer/reducer boundary for public extension hook dispatch while the public extension APIs remain unchanged
- `AgentLifecycleJournal` now owns durable lifecycle operation writes, transition save points, pending interaction lifecycle operation events, and context operation payload helpers
- `AgentKernel` now owns user/command/resume turn frames and pending interaction create/resolve boundaries behind the session facade
- `AgentToolActionService` now owns non-LLM tool action execution, including active-tool checks, extension pre/post hooks, `PermissionPolicy`, path write guards, runtime dispatch, and extension-owned tool calls
- `AgentLoop` now owns turn-loop orchestration behind `QueryEngine`, including agent steps, context/provider attempts, compact retry, tool batch interruption, guard stops, abort, and max-turn transitions; `QueryEngine` no longer owns `_run_loop_impl`
- `ToolRuntime` construction is now workflow-neutral; the bundled C/C++ workflow package registers recipe, quality, evidence, and task-status tools with metadata through `CHarnessWorkflowExtension.register_tools(...)`
- C/C++ workflow pack definitions now live under `src/embedagent/harness/packs.py`; `src/embedagent/tooling/packs.py` is only a compatibility export
- Pi-inspired minimal Core Phase A durable operation log, Phase B HookBus/reducer registry, Phase C AgentKernel lifecycle extraction, Phase D default C/C++ workflow package ownership, Phase E self-extension authoring loop, Phase F repo-side offline bundle validation, Phase G turn snapshot / capability registry foundation, Phase H runtime configuration reducer, Phase I workflow package manifest/read model, Phase J structured compaction state, and Phase K recovery state are complete
- `TurnSnapshot` is now the explicit frozen provider-request input; `QueryEngine` builds it after context assembly and active schema projection, then provider requests consume `snapshot.messages` and `snapshot.tool_schemas`
- `CapabilityRegistry` is now the non-executing read model for tools, local file resources, slash commands, model profiles, and workflow packages; activation and execution remain owned by `AgentExtensionHost` / `ExtensionManager` and `ToolRuntime` / `AgentToolActionService`
- `RuntimeConfigReducer` now projects safe runtime configuration from transcript events, including model profile metadata, active model-visible tool names, local resource revision metadata, capability counts, and provider snapshot records
- `WorkflowPackageManifest` now describes the bundled C/C++ workflow package identity, declared tools, packs, supported modes/workflow states, and resource scopes as read-only control-plane data exposed through the shared extension manager
- `SelfExtensionAuthoringService` and `author_local_capability` can generate local skills, prompts, recipes, and disabled-by-default project extension skeletons without reloading resources or loading Python code
- `scripts/offline-runtime-contract.json` is now the single repo-side contract for runtime-invoked bundled external tools; `validate-offline-bundle.ps1` and `check-bundle-dependencies.py` consume it for Python, MinGit, ripgrep, Universal Ctags, and LLVM/Clang child executable validation
- Slice 6 completed the documentation cutover for self-extensible Agent Core: active source-of-truth docs and module docs now treat local offline self-extension as official architecture while keeping marketplaces, online installs, dependency installation, built-in tool replacement, and multi-agent orchestration out of scope
- `HarnessStateSynchronizer` has been removed; product refresh uses `CHarnessWorkflowExtension.refresh_managed_session()` through the default harness extension directly
- `StreamingToolExecutor` now window-schedules parallel read batches so failure/discard semantics are deterministic

Recent stabilization work has also completed the GUI session-history single-source cutover:

- `transcript.jsonl` is now the only durable session-history truth
- GUI history is serialized from transcript-backed `Session` state
- GUI activation now uses one `/api/sessions/{id}/bootstrap` payload instead of split snapshot/timeline fetches

Recent stabilization work has also completed the agent-core ownership cutover:

- `QueryEngine` is now session-scoped and owns session mutation for the lifetime of a conversation
- frontend/live events now reuse engine-issued `step_id` values end-to-end
- resumed permission/user-input interactions re-enter the same action pipeline instead of bypassing it
- session snapshots are now built by a pure `SessionSnapshotProjector`
- transcript/timeline sequence allocation now uses cached counters instead of rescanning on every append

## 4. Remaining Near-Term Work

### 4.1 Pi-Inspired Minimal Core Program

The next long-term architecture program is documented in `docs/pi-inspired-agent-core-blueprint.md`.

It has two goals:

- keep learning Pi's functional design: extensions, resources, durable sessions, compaction, commands, model capability metadata, observability, and self-extension workflows
- keep learning Pi's architecture philosophy: a small Agent Core, capability registration, source-aware event reducers, explicit turn snapshots, save points, and replaceable workflow packages

The current self-extensible Agent Core baseline remains valid. The next program should advance it in gradual slices:

1. **Durable operation log and reducers**
   - extend transcript truth from session history into durable runtime state
   - record explicit operation lifecycle events for turns, agent steps, context assembly, provider requests, tool calls, save points, pending interaction, context snapshot, workflow patch, and interruptions
   - restore by reducing a self-consistent log prefix
   - mark unfinished operations interrupted by default and avoid automatic retry of non-idempotent tool calls
   - keep legacy session replay events out of operation-state inference; they rebuild history, not runtime operation status

2. **Source-aware HookBus and reducer registry**
   - separate passive observers from result-producing reducers
   - encode reducer semantics per event instead of scattering merge behavior across the manager
   - attach source metadata, cleanup, diagnostics, and reload behavior to registrations
   - keep built-in workflow extensions and project-local extensions on the same internal event boundary
   - current implementation status: Phase B is complete for extension hook dispatch; `ExtensionManager` routes public hook families through `AgentEventBus` and preserves existing public extension APIs

3. **AgentKernel lifecycle extraction**
   - current implementation status: Phase C is complete
   - `AgentLifecycleJournal` owns durable lifecycle operation writes and save points
   - `AgentKernel` owns turn frames and pending interaction create/resolve boundaries
   - `AgentLoop` owns turn-loop orchestration and `QueryEngine` remains the session facade
   - non-LLM action execution remains behind `AgentToolActionService`

4. **Default C/C++ workflow package**
   - current implementation status: Phase D is complete for tool capability ownership
   - C/C++ task graph, prompts, task snapshots, workflow projection, tool registration, metadata, pack activation, and extension-owned `task_status` handling live behind the bundled workflow package boundary
   - keep frontend shells consuming generic workflow projections
   - ensure bare Agent Core can run without the C/C++ package

5. **Self-extension authoring loop**
   - current implementation status: Phase E is complete
   - `SelfExtensionAuthoringService` generates local skills, prompts, recipes, extension manifests, extension code, docs, and validation recipes under `.embedagent`
   - `author_local_capability` exposes this as a build/debug `workspace_write` tool
   - resource reload remains separate from executable extension loading
   - generated project extensions are disabled by default and still require manifests, declared permissions, workspace-bound entrypoints, diagnostics, and normal `PermissionPolicy` enforcement

6. **Offline bundle validation**
   - current implementation status: Phase F is complete for repo-side validation
   - `scripts/offline-runtime-contract.json` lists all runtime-invoked bundled external tools
   - PowerShell and Python bundle validators consume the same runtime contract, including LLVM/Clang child executable checks
   - extension loading remains dependency-free at runtime and generated validation recipes use managed bundle commands
   - clean Windows 7 unpack-and-run smoke remains a release gate

7. **Turn snapshot and capability registry foundation**
   - current implementation status: Phase G is complete
   - `TurnSnapshot` freezes provider-request messages, tool schemas, active tool names, workflow state, model profile, runtime metadata, capability projection, and context stats
   - `CapabilityRegistry` projects tools, local file resources, slash commands, and model profiles as JSON-serializable descriptors with provenance
   - provider request diagnostics record safe snapshot metadata only, not prompt bodies, file contents, raw tool outputs, or credentials

8. **Runtime configuration reducer**
   - current implementation status: Phase H is complete
   - `RuntimeConfigReducer` reduces `runtime_configured`, `resource_reloaded`, and provider-request `operation_started` snapshot metadata from the transcript
   - session snapshots expose reducer-backed `runtime_config` for diagnostics and restore visibility
   - `TurnSnapshot` records reducer-backed model profile and local resource revision metadata when available
   - activation, execution, resource reload, extension loading, and permissions remain owned by their existing boundaries

9. **Workflow package manifest/read model**
   - current implementation status: Phase I is complete
   - `WorkflowPackageManifest` validates and serializes workflow package identity, supported modes/workflow states, tool declarations, packs, resource scopes, and diagnostics
   - the bundled C/C++ workflow package manifest is derived from its package-owned metadata and pack constants, then exposed through `CHarnessWorkflowExtension.package_manifest()` and `ExtensionManager.package_manifests()`
   - `CapabilityRegistry` now projects `workflow_package` descriptors for diagnostics and future reducer work
   - manifest projection is read-only; it does not activate tools, execute tools, grant permissions, reload resources, or load extensions

10. **Structured compaction state**
   - current implementation status: Phase J is complete
   - `compact_boundary` events now carry safe structured metadata: token/message counts, preserved message anchors, file activity paths, evidence refs, and extension-summary flag
   - `CompactionStateReducer` projects reducer-backed compaction state from transcript events, including latest boundary and duplicate/malformed diagnostics
   - restore results, managed sessions, protocol snapshots, and session snapshots expose `compaction_state`
   - projection remains read-only diagnostics/replay state; context selection, summary generation, extension loading, tool execution, and permissions remain owned by their existing boundaries

11. **Recovery state**
   - current implementation status: Phase K is complete
   - hosted resume appends safe `recovery_marker` events after restoring a trusted transcript prefix
   - `RecoveryStateReducer` projects reducer-backed recovery state from transcript events, including latest marker, trusted-prefix counts, stop reasons, operation/compaction/runtime summaries, and diagnostics
   - restore results, managed sessions, protocol snapshots, and session snapshots expose `recovery_state`
   - projection remains read-only diagnostics/replay state; restore validation, mode selection, tool activation, context selection, extension loading, tool execution, and permissions remain owned by their existing boundaries

This program must not introduce online extension marketplaces, dependency installation, remote registries, built-in tool replacement by project-local code, container requirements, WSL requirements, VS Code dependency, or general multi-agent orchestration in Agent Core.

### 4.2 Legacy Helper Deletion

Remaining cleanup should focus on:

- removing dead compatibility shims that are no longer part of product paths
- deleting or archiving superseded helper modules
- removing outdated tests/manual samples that preserve non-official behavior
- validating real C/C++ projects and the Win7/offline bundle while keeping documentation synchronized with the official extension boundaries
- keeping `scripts/offline-runtime-contract.json`, packaging validators, and the Win7 preflight checklist aligned when runtime-invoked tools change

### 4.3 Workflow Extension Decoupling

Near-term decoupling should continue from the new extension boundary:

- default extension configuration is closed for the current baseline: hosted product paths use `default_extensions.py`, while bare `QueryEngine` callers pass an `ExtensionManager` explicitly when they need bundled C harness behavior
- `QueryEngine` should remain a facade over `AgentLoop`, `AgentToolActionService`, and `AgentExtensionHost`; new extension hook dispatch should not be added directly back to `QueryEngine`
- keep remote registries, plugin marketplaces, dependency installation, built-in tool replacement, and multi-agent orchestration out of scope; project-local Python extensions stay limited to explicit enabled manifests under `.embedagent/extensions/<name>/`

### 4.4 Documentation Alignment

Current source-of-truth docs must remain aligned with the official architecture:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`
- `docs/pi-inspired-agent-core-blueprint.md`

### 4.5 Documentation Governance Baseline

- establish the active docs governance scaffold
- create module-level documentation for core code areas
- standardize terminology, templates, and Mermaid usage
- keep `superpowers -> global docs -> archive` synchronization as the default closure path

### 4.6 Real-World Validation

After architecture cutover, the highest-value validation is:

- real C workspace flows
- recipe discovery quality
- Clang diagnostics quality
- Win7 bundle runtime validation
- clean Win7 unpack-and-run smoke for the contract-backed offline bundle

## 5. Product Areas

### Agent Core

Priority remains highest on:

- `QueryEngine`
- harness
- runtime
- permissions
- context
- transcript/session truth

### Frontend Shells

Frontends should evolve only through the protocol/core contract and must not reintroduce workflow truth of their own.

### Offline Packaging

Offline packaging remains a first-class product requirement, but it must follow the current official runtime and protocol architecture rather than older mode/tool assumptions.

## 6. Verification Expectations

Before claiming a roadmap slice complete:

- run focused Python tests for the changed subsystem
- rebuild GUI assets if webapp source changed
- re-run relevant webapp helper/runtime tests
- update tracker and change log in the same change

## 7. Current Roadmap Summary

The repository is now past the architecture cutover stage and into stabilization:

- keep deleting dead compatibility layers
- keep validating on real C projects
- keep tightening offline bundle behavior around the shared runtime contract
- keep the transcript-backed session-history path as the only official history model
- do not reopen old dual-path architecture
