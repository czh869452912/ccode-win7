# Phase G Turn Snapshot And Capability Registry Design

## Status

This is the design spec for the next Pi-inspired minimal Core slice after Phase F.

Phase F closed the repo-side offline bundle validation boundary. Phase G moves back into Agent Core shape: make one provider request consume an explicit frozen turn snapshot, and introduce a minimal capability registry as the first shared catalog for model-visible and host-visible capabilities.

This spec is intentionally narrower than the full Pi target. It does not make all runtime configuration durable, does not add remote extension distribution, and does not replace the existing `ToolRuntime` or `ExtensionManager`.

## Goals

1. Introduce an explicit `TurnSnapshot` object.
2. Ensure provider request assembly consumes that snapshot rather than scattered live state.
3. Introduce a small `CapabilityRegistry` foundation.
4. Use the registry as a read model for tools, resources, commands, and model profiles.
5. Preserve current hosted C/C++ behavior and offline Windows 7 constraints.
6. Create a clean path toward later durable runtime configuration reducers.

## Non-Goals

Phase G will not:

- run clean Windows 7 bundle smoke; that remains blocked on external environment availability
- persist active tools, model selection, resource state, or extension state as new durable config reducers
- add online registries, dependency installation, plugin marketplaces, or remote extension installs
- replace `ToolRuntime` execution
- replace `ExtensionManager` activation policy
- redesign GUI protocol payloads beyond adding snapshot metadata already derived from existing state
- convert every large file into small modules

## Current Problem

The previous phases extracted important boundaries:

- `AgentKernel` owns turn frames and pending interaction boundaries.
- `AgentLifecycleJournal` owns operation lifecycle writes and save points.
- `AgentLoop` owns turn-loop orchestration.
- `AgentToolActionService` owns non-LLM tool execution.
- `AgentExtensionHost` centralizes extension dispatch.
- `ExtensionManager` dispatches public hook families through `AgentEventBus`.

However, a provider request still assembles from live state across `QueryEngine`, `AgentLoop`, `ContextManager`, `AgentExtensionHost`, and `ToolRuntime`. There is no single object that says:

- these were the messages sent to the provider
- these were the active tool names and schemas
- this was the workflow projection
- this was the model profile
- this was the runtime/bundle source
- this was the extension/resource state used for this request

This makes the architecture less Pi-like in two ways:

1. Turn inputs are not frozen as a first-class value.
2. Capabilities are registered and projected through several local catalogs instead of one shared read model.

## Pi Design Lessons Applied

Pi's harness design distinguishes live harness config from a turn snapshot. Getters can return latest config, but a provider request consumes the snapshot created at the turn boundary.

Pi also treats capabilities as product surface: tools, resources, commands, model data, and extension-owned additions are all explicit objects with provenance. Registration does not imply activation.

EmbedAgent should adopt those ideas in an offline-friendly Python 3.8 shape:

- `TurnSnapshot` is the frozen input for one provider request.
- `CapabilityRegistry` is the shared capability read model.
- activation remains policy-driven by mode, workflow state, extension manager, and permission metadata.

## Interface Decision

Three designs were considered.

### Design A: Snapshot Only

Add `TurnSnapshot` and leave all registries as-is.

Caller shape:

```python
snapshot = builder.build(session, mode_name, assembly)
reply = provider.call(snapshot.messages, snapshot.tool_schemas)
```

This is the smallest change and immediately freezes provider request inputs. It does not address the scattered capability surface.

### Design B: Registry First

Add `CapabilityRegistry` first and migrate tools, resources, commands, model profiles, workflow packages, renderer metadata, and diagnostics providers into it before creating snapshots.

Caller shape:

```python
registry.register(...)
active = registry.project_active(mode_name, workflow_state)
snapshot = TurnSnapshot.from_registry(active)
```

This is closest to the long-term blueprint but too broad for one safe slice.

### Design C: Durable Config Reducer First

Persist active tools, model choices, resources, and extension state into transcript/session entries, then build snapshots by reducing durable config.

Caller shape:

```python
state = SessionConfigReducer().reduce(transcript_events)
snapshot = TurnSnapshot.from_reduced_state(state)
```

This is powerful but touches recovery, GUI bootstrap, provider requests, extension loading, and session persistence at once.

### Chosen Hybrid

Phase G uses Design A plus the smallest useful part of Design B:

- Add `TurnSnapshot` and `TurnSnapshotBuilder`.
- Add `CapabilityRegistry` as a non-executing read model.
- Populate the registry from existing runtime state instead of moving execution ownership.
- Keep `ToolRuntime` as the executor.
- Keep `ExtensionManager` as the active-tool policy boundary.
- Store enough snapshot metadata to audit provider request inputs and support future reducer work.

## Proposed Modules

### `src/embedagent/capabilities.py`

Owns the generic capability catalog.

Data types:

- `CapabilityDescriptor`
- `CapabilityRegistry`
- `CapabilitySnapshot`

Initial capability kinds:

- `tool`
- `resource`
- `command`
- `model_profile`

Descriptor fields:

- `name`
- `kind`
- `source_type`
- `source_id`
- `metadata`
- `active`

Rules:

- registration does not imply model visibility
- duplicate `(kind, name, source_type, source_id)` is idempotent
- duplicate active built-in tool replacement remains prohibited by existing tool runtime rules
- registry does not execute tools or load code
- registry output is JSON-serializable

### `src/embedagent/turn_snapshot.py`

Owns the frozen provider-request input.

Data types:

- `TurnSnapshot`
- `TurnSnapshotBuilder`

Snapshot fields:

- `snapshot_id`
- `session_id`
- `turn_id`
- `step_id`
- `mode_name`
- `workflow_state`
- `messages`
- `tool_schemas`
- `active_tool_names`
- `model_profile`
- `runtime_environment`
- `capabilities`
- `context_stats`
- `created_at`

Rules:

- snapshot messages are copied, not referenced
- snapshot tool schemas are copied, not referenced
- snapshot capability data is a serializable projection, not live registry state
- snapshot captures active tool names sorted for deterministic tests
- snapshot does not execute hooks or mutate session state

## Integration Shape

### Provider Request

`QueryEngine` currently delegates context assembly and provider request orchestration through `AgentLoop`.

Phase G should preserve that structure but insert snapshot creation between context/tool-schema assembly and provider call:

```text
ContextAssemblyResult + active schemas + workflow state
  -> TurnSnapshotBuilder
  -> TurnSnapshot
  -> provider call
```

The provider call should receive `snapshot.messages` and `snapshot.tool_schemas`.

### Tool Schemas

`AgentExtensionHost.schemas_for_active_tools(...)` remains the policy-aware schema projection entry point. Phase G should call it before snapshot creation and put the resulting schemas into the snapshot.

`TurnSnapshot` must not decide which tools are active. It only records the result.

### Capability Registry

`ToolRuntime` and `InProcessAdapter` can populate a registry read model from existing sources:

- runtime tool catalog entries become `tool` descriptors
- local resource snapshot entries become `resource` descriptors
- slash command specs become `command` descriptors
- current configured model becomes a basic `model_profile` descriptor

Initial registry construction can be session-scoped or adapter-owned. It does not need durable persistence in Phase G.

### Session And Transcript

Phase G should record snapshot metadata in existing context/provider diagnostics, not add a new durable event family unless needed for tests.

Allowed metadata:

- `snapshot_id`
- `mode_name`
- `active_tool_names`
- `model_profile`
- `capability_counts`

Do not record full prompts, file contents, raw tool outputs, provider request bodies, or credentials.

## Safety And Compatibility

Phase G must preserve:

- Python `>=3.8,<3.9`
- offline bundle constraints
- Windows 7 runtime compatibility
- no new dependencies
- no online extension or package install behavior
- current C/C++ workflow tool activation
- current project extension permission checks
- current GUI bootstrap contract

The implementation must avoid Python 3.9+ syntax such as `dict | dict`, `list[str]`, and `match`.

## Testing Strategy

Add focused tests before implementation.

Test groups:

1. `tests/test_turn_snapshot.py`
   - snapshot copies messages and schemas
   - snapshot exposes deterministic active tool names
   - snapshot includes workflow state, runtime environment, model profile, and capability projection
   - mutating the original assembly/schema objects after build does not mutate the snapshot

2. `tests/test_capability_registry.py`
   - registers tool/resource/command/model_profile descriptors
   - duplicate descriptor registration is idempotent
   - snapshot output is JSON-serializable
   - activation is metadata only; registry does not execute tools

3. Existing integration tests
   - `tests/test_query_engine_refactor.py`
   - `tests/test_tools_package.py`
   - `tests/test_inprocess_adapter_frontend_api.py`

Expected behavior:

- provider calls use snapshot messages and schemas
- existing active tool policy remains unchanged
- frontend session behavior remains unchanged except safe diagnostic metadata

## Documentation Updates At Closeout

When implementation completes, update:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/pi-inspired-agent-core-blueprint.md`
- `docs/tool-contracts.md`

The completed Phase G spec and plan should be archived under:

- `docs/archive/phase-g-turn-snapshot-capability-registry/`

## Acceptance Criteria

Phase G is complete when:

1. `TurnSnapshot` exists and is the object consumed by provider request assembly.
2. Snapshot data freezes messages, tool schemas, active tool names, workflow state, model profile, runtime environment, and capability projection.
3. `CapabilityRegistry` exists as a generic, serializable read model for tools, resources, commands, and model profiles.
4. Existing extension activation policy still flows through `ExtensionManager` and `AgentExtensionHost`.
5. Existing tool execution still flows through `ToolRuntime` and `AgentToolActionService`.
6. Focused and fast test suites pass.
7. Source-of-truth docs describe Phase G status and the new snapshot/registry boundary.
