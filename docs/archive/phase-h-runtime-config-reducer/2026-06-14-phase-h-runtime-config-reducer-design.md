# Phase H Runtime Configuration Reducer Design

## Goal

Phase H turns the Phase G read models into replayable runtime state for the smallest useful surface:

- active model profile metadata
- active model-visible tool names for provider requests
- local resource revision metadata
- safe capability counts and resource revision diagnostics

The slice keeps runtime behavior unchanged for the default C/C++ hosted workflow. It adds a reducer-backed state layer that `TurnSnapshot`, session snapshots, and restore diagnostics can consume.

## Context

Phase G added:

- `TurnSnapshot` as the frozen provider-request input
- `CapabilityRegistry` as a non-executing read model for tools, local resources, slash commands, and model profiles

That foundation is still live-runtime driven. `QueryEngine` currently builds provider capability metadata directly from `ToolRuntime` and the client. `InProcessAdapter.reload_resources()` records `resource_discovered` and `resource_reloaded` events, but restore treats those as non-state events. This leaves a gap against the Pi-inspired target: durable session state should explain which runtime configuration a turn used.

## Design

Add `src/embedagent/runtime_config.py` with:

- `RuntimeConfigState`
- `ResourceRevision`
- `ProviderRequestSnapshotRecord`
- `RuntimeConfigReducer`
- helper projection functions for snapshot-safe dictionaries

The reducer consumes transcript schema v2 events only as durable inputs:

- `runtime_configured`
- `resource_reloaded`
- `operation_started` where `kind == "provider_request"` and metadata contains safe `turn_snapshot`

The reducer does not execute tools, reload files, load Python extensions, or decide active-tool policy. It only derives state from already-written events.

## Event Semantics

### `runtime_configured`

Purpose: durable runtime configuration marker.

Allowed payload:

- `reason`
- `model_profile`
- `capability_counts`
- `active_tool_names`
- `resource_revision`

Sensitive values such as API keys, raw prompt bodies, file contents, request bodies, response bodies, and tool outputs are not allowed.

### `resource_reloaded`

Purpose: durable local resource revision marker.

The reducer increments `resource_revision.revision` every time it sees a `resource_reloaded` event and stores:

- reason
- counts
- resource paths
- diagnostics
- event id, sequence, timestamp

`resource_discovered` remains diagnostic and does not advance the active resource revision.

### Provider `operation_started`

Purpose: recover the exact safe provider snapshot metadata used by a request.

The reducer reads `metadata.turn_snapshot`, including:

- snapshot id
- mode
- workflow state
- active tool names
- model profile
- capability counts
- resource revision, once Phase H adds it

It does not read `messages` or `tool_schemas`.

## Runtime Integration

`InProcessAdapter` will:

- emit `runtime_configured` during session creation after initial resource reload
- update `ManagedSession.runtime_config` from `RuntimeConfigReducer`
- expose `runtime_config` in session snapshots as diagnostic state
- preserve existing `extensions.local_resources` projection for frontend compatibility within this slice

`QueryEngine` will:

- accept an optional runtime config provider
- build `TurnSnapshot` model profile/resource revision metadata from reducer state when available
- emit provider metadata containing only safe reducer/snapshot metadata
- keep active-tool activation owned by `AgentExtensionHost` and `ExtensionManager`

## Boundaries

In scope:

- reducer module and tests
- resource reload event revision semantics
- provider snapshot metadata consuming reducer state
- session snapshot diagnostic projection
- source-of-truth docs update

Out of scope:

- online registries
- extension marketplace behavior
- dependency installation
- replacing built-in tools
- full model selection UI
- full workflow package manifest system
- structured compaction state
- clean Windows 7 smoke execution

## Acceptance Criteria

- A transcript can be reduced into model profile, active tool names, resource revision, and provider snapshot records.
- `resource_reloaded` advances a durable resource revision; `resource_discovered` does not.
- Session snapshots expose reducer-backed `runtime_config`.
- Provider request turn snapshots include safe runtime config metadata without prompts, file contents, tool outputs, request bodies, response bodies, or credentials.
- Existing Phase G snapshot/capability tests continue passing.
- Fast non-GUI test suite and lint pass before completion.
