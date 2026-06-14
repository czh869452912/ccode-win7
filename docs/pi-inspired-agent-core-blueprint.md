# Pi-Inspired Minimal Agent Core Blueprint

## 1. Status

This document is a target blueprint for the next architecture program.

It does not replace the current official runtime baseline. The current baseline remains the session-scoped Agent Core with the bundled C/C++ harness installed as the default workflow extension. This blueprint describes the next direction: keep learning from Pi at both levels:

- functional design: extensions, resources, session durability, compaction, commands, model capability metadata, observability, and self-extension workflows
- architecture philosophy: a small core, capability registration, event reducers, durable state, and replaceable product shells

The goal is not to clone Pi. EmbedAgent keeps its own constraints:

- Windows 7 compatibility
- offline deployment
- Python 3.8 runtime
- no Docker, WSL, VS Code, online registry, dependency installation, or plugin marketplace at runtime
- C/C++ engineering as the first-class default product workflow

## 2. Reader And Outcome

The intended reader is an engineer changing Agent Core, the default C/C++ workflow, or project-local self-extension.

After reading this document, the reader should be able to decide whether a proposed capability belongs in the minimal core, in the default C/C++ workflow package, in a project-local extension, or in a frontend shell.

## 3. Design Thesis

EmbedAgent Core should be able to run without knowing about C/C++ tasks.

The C/C++ Agent IDE experience should be the product shape produced by loading the default bundled workflow package into a small generic kernel. The default workflow remains first-class, bundled, and enabled for hosted product paths, but it should not define what Agent Core is.

The long-term boundary is:

```text
Frontend Shells
  -> Hosted Adapter
  -> AgentKernel
  -> SessionLog + CapabilityRegistry + RuntimeConfigReducer + WorkflowPackageManifest + HookBus + ToolRuntime + PermissionPolicy
  -> Default C/C++ Workflow Package and project-local extensions
```

## 4. Minimal Core

Agent Core should keep only the concepts required for any agentic runtime.

### AgentKernel

Owns the turn lifecycle:

- accept a user turn or resume event
- create a turn snapshot
- call the model adapter
- execute tool calls through the tool action pipeline
- write durable events
- advance to save points
- stop, suspend, or recover from known boundaries

The kernel should not own C/C++ phases, recipes, task graphs, or quality gates.

### SessionLog

The append-only durable state ledger.

The session log should record not only messages, but also explicit operation lifecycle state:

- operation started, finished, interrupted
- turn started, finished
- provider request started, finished
- tool call started, finished
- pending interaction created, resolved
- workflow patch applied
- context snapshot created
- compaction boundary written
- extension custom entry appended

Live `Session` state should become a reducer output of this log. Direct state patching should shrink over time. Legacy replay events can continue to rebuild historical session topology, but durable runtime operation status should come from explicit lifecycle events rather than inferred side effects.

### CapabilityRegistry

The shared registry for model-visible and host-visible capabilities:

- tools
- resources
- commands
- prompt units
- model profiles
- workflow packages
- renderer metadata
- diagnostics providers

Registration should not imply activation. Visibility is decided by mode contract, workflow state, extension policy, and permission metadata.

### WorkflowPackageManifest

The read-only package control-plane model:

- package identity and label
- supported modes and workflow states
- declared workflow tools and permission categories
- tool packs
- local resource scopes
- package diagnostics

Manifest projection should explain what a workflow package can provide without loading code, activating tools, executing tools, or granting permissions.

### RuntimeConfigReducer

The reducer-backed runtime configuration read model for one session:

- credential-free model profile metadata
- model-visible active tool names after backend activation
- local resource revision metadata
- capability counts
- provider snapshot records

It is a replay/diagnostic projection over transcript events. It should explain what configuration a turn used without becoming the source of future activation, execution, resource reload, extension loading, or permission decisions.

### HookBus

The source-aware event boundary for extensions.

It should separate:

- observers: passive listeners, return values ignored
- reducers: event-specific handlers that can patch context, tool calls, tool results, workflow state, or provider options

Reducer semantics should be explicit per event: chain, merge, first-block-wins, last-patch-wins, or cancel.

### Policy Boundary

Core owns common safety enforcement:

- permission decisions
- workspace path guards
- manifest permission checks
- project trust
- built-in tool replacement prohibition
- extension diagnostics

Extensions may request capability. They do not bypass policy.

## 5. Default C/C++ Workflow Package

The bundled C/C++ workflow remains the default product experience.

Its long-term shape should be a first-party workflow package loaded through the same capability boundary as other local extensions, with extra product privileges because it is bundled and trusted.

It owns:

- official C/C++ workflow modes and phase progression
- discipline profiles
- task graph internals
- recipe selection and execution semantics
- quality reporting and failing evidence contracts
- task status projection
- C/C++ prompt units
- C/C++ workflow tool activation

It projects generic workflow state to Agent Core and frontend shells. It should not require core modules to import C/C++ task internals.

## 6. Functional Design Lessons From Pi

### Extensions As The Main Product Surface

Pi treats extension points as first-class product behavior, not as afterthoughts. EmbedAgent should do the same, but with offline and manifest-gated constraints.

Useful capabilities to adopt:

- custom tools
- context injection
- tool-call blocking or argument patching
- tool-result patching
- workflow state patches
- custom commands
- session custom entries
- extension diagnostics
- reloadable resources

Capabilities not adopted for the baseline:

- online package installs
- remote registries
- dependency installation at runtime
- plugin marketplaces
- project code that can replace built-in tools
- general multi-agent orchestration as a core feature

### Resources Are Data, Extensions Are Code

Pi separates skills, prompts, templates, and extensions. EmbedAgent should preserve this distinction:

- resources are workspace files discovered and reloaded as data
- project-local Python extensions are explicit code loading, enabled by manifest and permissions

Reloading resources must not execute Python code.

### Session Is Durable Agent State

Pi's strongest durable design idea is that session storage is not only history. It is the durable state model for model choice, active tools, compaction, branch summaries, labels, extension state, and recovery markers.

EmbedAgent should extend transcript truth in that direction. `transcript.jsonl` should become the reducer input for all durable session state that matters after restart. Phase H starts this beyond operation state by reducing safe runtime configuration from transcript events, Phase J extends the same pattern to structured compaction state, and Phase K adds recovery markers for hosted resume attempts.

### Turn Snapshot And Save Point Discipline

Pi distinguishes live configuration from the snapshot used by an in-flight provider request.

EmbedAgent should adopt this invariant:

- a turn snapshot freezes context, system prompt, model profile, active tools, workflow state, and stream options for a provider request
- configuration and extension changes made during a turn affect the next save point, not the in-flight request
- save points flush pending writes and prepare the next provider request deterministically

### Compaction As Structured State

Pi's compaction design tracks what was summarized, what remains, and file activity metadata.

EmbedAgent has evolved compact boundaries into structured durable entries with:

- first kept message or event anchor
- tokens before and after
- summarized turn count
- read files
- modified files
- evidence sources
- extension-provided summary flag

Current implementation status: Phase J is complete. `CompactionStateReducer` projects structured compaction state from `compact_boundary` events. `QueryEngine` emits safe token/message counts, preserved message anchors, file activity paths, evidence refs, and extension-summary flags. Restore results, managed sessions, protocol snapshots, and session snapshots expose `compaction_state`. The projection is diagnostic/replay state only and does not select context, execute extensions, reload resources, or bypass permissions.

### Model Capability Metadata

Pi uses model metadata for context windows, reasoning support, provider behavior, and cross-provider compatibility.

EmbedAgent can adopt a smaller offline-friendly version:

- model id
- provider type
- context window
- reasoning support
- tool-call support
- streaming support
- image support if relevant later
- provider compatibility notes

This metadata should guide context budgeting and UI reporting without making Core depend on online model discovery.

### Observability Without A Vendor

Pi's observability idea fits EmbedAgent well: emit safe structured lifecycle events, and let hosts or tools route them.

Initial event families should include:

- agent turn
- context assembly
- model request
- tool call
- permission decision
- transcript append
- extension hook
- workflow patch
- recovery marker

Default payloads must avoid prompts, file contents, tool outputs, credentials, request bodies, and response bodies.

## 7. Self-Extension Model

Self-extension means the agent can help create new local capabilities for the workspace.

Allowed self-authored artifacts:

- skills
- prompts
- recipes
- project-local extension manifests
- project-local extension code
- documentation for local extensions
- tests or validation recipes for local extensions

Loading rules:

- generated resources can be reloaded as data
- generated extension code is not loaded by plain resource reload
- generated extension code requires an enabled manifest
- manifests must declare permissions
- hosts must surface diagnostics and trust state
- privileged tools still go through `PermissionPolicy`

This keeps self-extension useful without turning resource reload into arbitrary code execution.

## 8. Migration Program

### Phase A: Durable Operation Log

Promote the session log from transcript history to durable runtime state.

Outcomes:

- operation, turn, provider request, tool call, pending interaction, context snapshot, and workflow patch events are durable
- restore reduces the log into a self-consistent live session prefix
- unfinished operations are marked interrupted by default
- non-idempotent tool calls are not retried automatically

Current implementation status: Phase A is complete. The operation reducer uses explicit schema v2 `operation_started`, `operation_finished`, and `operation_interrupted` events as the operation-state truth. Runtime emissions cover turns, agent steps, context assembly, context snapshots, provider requests, tool calls, pending interaction start/finish, workflow patches, and save points. Restore snapshots close unfinished operations as interrupted, while live session snapshots preserve currently active operations in reducer-backed `operation_diagnostics`. Phase B has promoted extension hook dispatch into a source-aware HookBus/reducer registry. Phase C has moved lifecycle orchestration behind `AgentLifecycleJournal`, `AgentKernel`, and `AgentLoop` instead of growing one-off lifecycle helpers inside the session facade.

### Phase B: HookBus And Reducers

Replace method-name hook dispatch with a source-aware hook bus.

Outcomes:

- observers and reducers are distinct
- reducer semantics are explicit per event
- extension source metadata is attached to registrations
- cleanup and reload behavior are deterministic
- built-in workflow extension and project-local extensions use the same internal bus

Current implementation status: Phase B is complete for extension hook dispatch. `src/embedagent/agent_event_bus.py` defines the internal source-aware event bus, observer/reducer registrations, dispatch diagnostics, event-specific reducer stopping, and fail-closed behavior for trusted reducers. `ExtensionManager` keeps its public APIs but routes public extension hook families through `AgentEventBus`, including context patches, tool-call decisions, tool-result patches, resource discovery, dynamic tool registration, prompt patches, active tool names, workflow initialization, task snapshot loading, and extension-owned tool handling. Lifecycle orchestration is now behind the Phase C kernel/journal/loop boundaries; future lifecycle observers should use the bus boundary rather than adding direct facade hooks.

### Phase C: AgentKernel Extraction

Keep lifecycle orchestration behind the extracted kernel, journal, and loop modules.

Outcomes:

- turn snapshot creation is explicit
- save points are explicit
- suspend, resume, abort, compact retry, and failure cleanup share one lifecycle path
- the public session facade shrinks
- tool action execution remains behind the action service

Current implementation status: Phase C is complete. `src/embedagent/agent_lifecycle.py` defines `AgentLifecycleJournal` for durable lifecycle operation events, context operation payload helpers, pending interaction lifecycle events, and transition save points. `src/embedagent/agent_kernel.py` defines `AgentKernel` and `AgentTurnFrame` for user, command, and resume turn lifecycle plus pending interaction create/resolve boundaries. `src/embedagent/agent_loop.py` now owns turn-loop orchestration, including agent steps, context/provider attempts, compact retry, tool batch interruption, guard stops, aborts, and max-turn transitions. `QueryEngine` remains the session-scoped facade and transcript/session mutation compatibility surface.

### Phase D: Default C/C++ Workflow Package

Move more default C/C++ behavior behind the same package boundary.

Outcomes:

- C/C++ task graph internals stay behind the workflow package
- workflow prompts, tool packs, resources, recipes, task status, and quality gates register as package capabilities
- frontend projections consume generic workflow state
- bare AgentKernel works without the C/C++ package

Current implementation status: Phase D is complete for default C/C++ workflow capability ownership. `ToolRuntime` construction is workflow-neutral and no longer imports the harness runtime facade. `CHarnessWorkflowExtension.register_tools(...)` registers recipe, quality, evidence, and task-status tools into the shared runtime with source metadata. C/C++ workflow tool metadata lives in `src/embedagent/harness/tool_metadata.py`; C/C++ workflow packs live in `src/embedagent/harness/packs.py`; hosted product paths still load the bundled package through `src/embedagent/default_extensions.py`, while bare Agent Core does not expose C/C++ workflow tools unless that package is installed.

### Phase E: Self-Extension Authoring Loop

Make local self-extension a safe product workflow.

Outcomes:

- users can ask the agent to create skills, prompts, recipes, and project-local extension skeletons
- generated extensions include manifests, permission declarations, docs, and validation recipes
- hosts show load state, diagnostics, and trust decisions
- reload paths remain separate for resources and executable extensions

Current implementation status: Phase E is complete for the local authoring loop. `src/embedagent/self_extension_authoring.py` defines `SelfExtensionAuthoringService` for workspace-bound generation of `.embedagent/skills`, `.embedagent/prompts`, `.embedagent/recipes`, and disabled-by-default `.embedagent/extensions/<name>` skeletons with manifests, docs, and validation recipes. The workflow-neutral `author_local_capability` tool exposes authoring in build/debug mode with `workspace_write` permission. Authoring writes files only; resource reload and executable project-extension loading remain separate explicit operations.

### Phase F: Offline Bundle Validation

Keep the new architecture compatible with offline delivery.

Outcomes:

- all runtime-invoked tools are bundled
- extension loading does not install dependencies
- generated local capabilities remain workspace-bound
- clean Windows 7 bundle smoke remains a release gate

Current implementation status: Phase F is complete for repo-side validation. `scripts/offline-runtime-contract.json` is the single contract for runtime-invoked bundled external tools, including Python, MinGit, ripgrep, Universal Ctags, and LLVM/Clang child executables. `scripts/validate-offline-bundle.ps1` and `scripts/check-bundle-dependencies.py` consume the same contract and report `runtime_contract` metadata. Project extension loading remains dependency-install-free, generated extension validation recipes use managed Python commands, and the final clean Windows 7 unpack-and-run smoke remains a release gate outside the repository test suite.

### Phase G: Turn Snapshot / Capability Registry Foundation

Current implementation status: Phase G is complete. `TurnSnapshot` is now the explicit frozen provider-request input built after context assembly and active schema projection; provider calls consume `snapshot.messages` and `snapshot.tool_schemas`. `CapabilityRegistry` is now a non-executing read model for tools, local file resources, slash commands, and model profiles. Activation still belongs to `ExtensionManager` / `AgentExtensionHost`, execution still belongs to `ToolRuntime` / `AgentToolActionService`, and provider diagnostics record only safe snapshot metadata.

### Phase H: Runtime Configuration Reducer

Promote the smallest useful runtime configuration state from live read models to transcript-backed reducers.

Outcomes:

- `runtime_configured` records safe model profile, active tool names, and capability counts
- `resource_reloaded` advances local resource revision metadata
- provider-request `operation_started` metadata records safe `turn_snapshot` anchors
- session snapshots expose reducer-backed `runtime_config`
- `TurnSnapshot` can carry reducer-backed model profile and resource revision metadata

Current implementation status: Phase H is complete. `src/embedagent/runtime_config.py` defines `RuntimeConfigReducer` and serializable state objects. `InProcessAdapter` emits and refreshes runtime config during session creation, local resource reload, resume, and snapshot projection. `QueryEngine` can consume reducer-backed runtime configuration while building provider turn snapshots. The reducer ignores `resource_discovered` for revision advancement, strips unsafe provider inputs, and leaves activation, execution, resource reload, extension loading, and permission checks with their existing owners.

### Phase I: Workflow Package Manifest / Read Model

Make workflow package identity and package-owned capabilities explicit without making manifests executable.

Outcomes:

- workflow package manifests validate package identity, supported modes/workflow states, tool declarations, packs, resource scopes, and diagnostics
- the bundled C/C++ workflow package exposes a manifest derived from its package-owned tool metadata and pack constants
- the shared extension manager can collect package manifests from registered extensions
- the capability registry projects `workflow_package` descriptors for diagnostics and future reducer work
- manifest projection stays read-only and does not activate tools, execute tools, grant permissions, reload resources, or load extensions

Current implementation status: Phase I is complete. `src/embedagent/workflow_package_manifest.py` defines the generic manifest read model. The bundled C/C++ package exposes its manifest through `CHarnessWorkflowExtension.package_manifest()` and `ExtensionManager.package_manifests()`. `CapabilityRegistry` now includes `workflow_package` descriptors, and `InProcessAdapter.capability_snapshot()` includes the bundled C/C++ package descriptor through the shared extension manager rather than through a direct adapter-to-harness dependency.

### Phase J: Structured Compaction State

Make compact boundaries reducer-backed durable state rather than only live session compatibility records.

Outcomes:

- `compact_boundary` events carry safe structured metadata for preserved message anchors, token/message counts, file activity paths, evidence refs, and extension-summary flags
- `CompactionStateReducer` projects latest boundary, boundary history, aggregate summarized turns, and duplicate/malformed diagnostics
- restore results, managed sessions, protocol snapshots, and frontend session snapshots expose `compaction_state`
- `Session.compact_boundaries` remains live context compatibility state
- compaction projection stays read-only and does not select context, execute tools, load extensions, grant permissions, or replace session history

Current implementation status: Phase J is complete. `src/embedagent/compaction_state.py` defines the reducer and serializable read model; `QueryEngine` enriches `compact_boundary` transcript events; `SessionRestorer` reduces the consumed transcript prefix; `InProcessAdapter` refreshes `ManagedSession.compaction_state`; `SessionSnapshotProjector` and the protocol/core adapter expose the projection.

### Phase K: Recovery State

Make hosted resume attempts durable, replayable diagnostic state.

Outcomes:

- hosted resume appends safe `recovery_marker` events after restoring a trusted transcript prefix
- `RecoveryStateReducer` projects latest marker, marker history, trusted-prefix counts, stop reasons, skip summaries, operation/compaction/runtime summaries, and duplicate/malformed diagnostics
- restore results, managed sessions, protocol snapshots, and frontend session snapshots expose `recovery_state`
- restore validation, transcript repair, mode selection, tool activation, context selection, extension loading, tool execution, and permissions remain owned by existing boundaries
- recovery projection stays read-only and does not replace session history or frontend bootstrap truth

Current implementation status: Phase K is complete. `src/embedagent/recovery_state.py` defines the reducer and serializable read model; `InProcessAdapter.resume_session(...)` appends safe `recovery_marker` events after restore; `SessionRestorer` reduces recovery markers from the consumed transcript prefix; `ManagedSession`, `SessionSnapshotProjector`, and the protocol/core adapter expose `recovery_state`.

### Phase L: Pack Compatibility Cleanup

Delete stale C/C++ workflow pack import surfaces now that the default workflow package owns its pack definitions.

Outcomes:

- `src/embedagent/tooling/packs.py` is removed
- `embedagent.tooling` no longer re-exports C/C++ workflow pack aliases
- bundled C/C++ workflow pack truth is available only from `src/embedagent/harness/packs.py`
- active tool selection, schema projection, permissions, and hosted C/C++ behavior remain unchanged

Current implementation status: Phase L is complete. The historical `embedagent.tooling.packs` re-export has been deleted, package-root pack aliases have been removed from `embedagent.tooling`, and architecture tests guard the single harness-owned pack import path.

### Phase M: Core Alias Cleanup

Delete stale core-level compatibility aliases now that official factory/accessor
entry points are established.

Outcomes:

- mode registry access uses `get_mode_registry()` / `initialize_modes()`
- command sanitizer access uses `get_command_sanitizer()`
- hosted adapter class lookup uses `get_inprocess_adapter()`
- legacy names such as `MODE_REGISTRY`, `_DEFAULT_SANITIZER`,
  `get_default_sanitizer()`, `_inprocess_adapter`, and `_get_adapter_class()`
  are no longer exported or used
- mode behavior, shell sanitizer behavior, adapter lifecycle, permissions, and
  hosted C/C++ behavior remain unchanged

Current implementation status: Phase M is complete. The remaining core
compatibility aliases for mode registry, command sanitizer, and adapter class
lookup have been removed, and tests guard the explicit accessor boundary.

## 9. Acceptance Criteria For The Direction

The blueprint is working when:

- Agent Core can be described without C/C++ workflow vocabulary
- hosted product paths still load the bundled C/C++ workflow by default
- a bare engine can run with an empty workflow package set
- tools and resources are registered once and activated through capability policy
- workflow packages can be inspected through read-only manifests without making manifests the activation policy
- durable restore can explain where an interrupted run stopped
- durable restore can explain which safe runtime configuration a provider request used
- durable restore can explain what compaction boundary was written and which safe metadata it carried
- durable restore can explain hosted resume recovery markers and trusted transcript prefixes
- stale compatibility import paths and aliases are deleted once official ownership/accessor boundaries are established
- project-local extensions can add useful behavior without bypassing permissions
- resource reload and extension loading remain separate operations
- frontend shells consume projections, not workflow internals

## 10. Non-Goals

The next architecture program should not introduce:

- online extension marketplaces
- runtime dependency installation
- remote extension registries
- container or WSL requirements
- VS Code dependency
- general multi-agent orchestration in Agent Core
- replacement of built-in tools by project-local code

These may be useful in other products. They are outside the EmbedAgent baseline.
