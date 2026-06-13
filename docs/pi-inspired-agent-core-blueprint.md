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
  -> SessionLog + CapabilityRegistry + HookBus + ToolRuntime + PermissionPolicy
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

EmbedAgent should extend transcript truth in that direction. `transcript.jsonl` should become the reducer input for all durable session state that matters after restart.

### Turn Snapshot And Save Point Discipline

Pi distinguishes live configuration from the snapshot used by an in-flight provider request.

EmbedAgent should adopt this invariant:

- a turn snapshot freezes context, system prompt, model profile, active tools, workflow state, and stream options for a provider request
- configuration and extension changes made during a turn affect the next save point, not the in-flight request
- save points flush pending writes and prepare the next provider request deterministically

### Compaction As Structured State

Pi's compaction design tracks what was summarized, what remains, and file activity metadata.

EmbedAgent should evolve compact boundaries into structured durable entries with:

- first kept message or event anchor
- tokens before and after
- summarized turn count
- read files
- modified files
- evidence sources
- extension-provided summary flag

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

Current implementation status: the first operation reducer slice exists and uses explicit schema v2 `operation_started`, `operation_finished`, and `operation_interrupted` events as the operation-state truth. Current runtime emissions cover agent steps, context assembly, provider requests, tool calls, and save points. Remaining Phase A work is to broaden explicit lifecycle coverage for turn-level events, pending interaction lifecycle, workflow patches, and frontend/diagnostic projections.

### Phase B: HookBus And Reducers

Replace method-name hook dispatch with a source-aware hook bus.

Outcomes:

- observers and reducers are distinct
- reducer semantics are explicit per event
- extension source metadata is attached to registrations
- cleanup and reload behavior are deterministic
- built-in workflow extension and project-local extensions use the same internal bus

### Phase C: AgentKernel Extraction

Turn the current facade and thin loop boundary into a real lifecycle module.

Outcomes:

- turn snapshot creation is explicit
- save points are explicit
- suspend, resume, abort, compact retry, and failure cleanup share one lifecycle path
- the public session facade shrinks
- tool action execution remains behind the action service

### Phase D: Default C/C++ Workflow Package

Move more default C/C++ behavior behind the same package boundary.

Outcomes:

- C/C++ task graph internals stay behind the workflow package
- workflow prompts, tool packs, resources, recipes, task status, and quality gates register as package capabilities
- frontend projections consume generic workflow state
- bare AgentKernel works without the C/C++ package

### Phase E: Self-Extension Authoring Loop

Make local self-extension a safe product workflow.

Outcomes:

- users can ask the agent to create skills, prompts, recipes, and project-local extension skeletons
- generated extensions include manifests, permission declarations, docs, and validation recipes
- hosts show load state, diagnostics, and trust decisions
- reload paths remain separate for resources and executable extensions

### Phase F: Offline Bundle Validation

Keep the new architecture compatible with offline delivery.

Outcomes:

- all runtime-invoked tools are bundled
- extension loading does not install dependencies
- generated local capabilities remain workspace-bound
- clean Windows 7 bundle smoke remains a release gate

## 9. Acceptance Criteria For The Direction

The blueprint is working when:

- Agent Core can be described without C/C++ workflow vocabulary
- hosted product paths still load the bundled C/C++ workflow by default
- a bare engine can run with an empty workflow package set
- tools and resources are registered once and activated through capability policy
- durable restore can explain where an interrupted run stopped
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
