# Phase I Workflow Package Manifest Design

## Goal

Phase I introduces a small, local, read-only workflow package manifest control plane for the bundled default C/C++ workflow package.

The purpose is to keep moving toward a Pi-like Agent Core: capabilities should be declared, inspectable, and reusable through generic read models instead of being understood only by reading harness code.

## Current Gap

Phase D moved default C/C++ tool ownership behind `CHarnessWorkflowExtension`.
Phase G added `CapabilityRegistry`.
Phase H added reducer-backed runtime configuration.

The remaining gap is that the default C/C++ workflow package still has its package identity, packs, tools, modes, and resource boundaries scattered across Python modules:

- `src/embedagent/harness/extension.py`
- `src/embedagent/harness/packs.py`
- `src/embedagent/harness/tool_metadata.py`
- `src/embedagent/harness/tool_registry.py`
- docs that describe the intended package philosophy

This is workable, but it is not yet a minimal, inspectable control plane. An agent or frontend can see registered tools after runtime setup, but it cannot inspect the bundled workflow package as one local package declaration.

## Design

Add a manifest/read-model layer for workflow packages.

### New Module

Create `src/embedagent/workflow_package_manifest.py` with:

- `WorkflowPackageManifest`
- `WorkflowToolDeclaration`
- `WorkflowPackDeclaration`
- `WorkflowPackageManifestError`
- helper functions for validation, stable sorting, and JSON serialization

The manifest is structured data and contains only safe local metadata:

- package id, label, version, source type, source id
- supported modes and workflow states
- tool declarations with permission category and source metadata
- pack declarations with ordered tool names
- resource scopes, such as `.embedagent/recipes`
- diagnostics for invalid declarations

It must not execute code, load extensions, install dependencies, contact a registry, or replace built-in tools.

### Bundled C/C++ Manifest

Create `src/embedagent/harness/package_manifest.py`.

This module builds the bundled C/C++ workflow package manifest from existing package-owned constants:

- `C_WORKFLOW_PACKS`
- `C_WORKFLOW_TOOL_METADATA`
- the official C/C++ workflow package id `embedagent.c_workflow`

The manifest is initially derived from existing Python metadata rather than from a JSON file. This keeps Phase I conservative and avoids adding a second source of truth too early.

### Capability Registry Projection

Extend `src/embedagent/capabilities.py` so `CapabilityRegistry` supports a new kind:

- `workflow_package`

Add `workflow_package_capability_descriptors(manifests)` to project workflow package manifests as non-executing capability descriptors.

`InProcessAdapter.capability_snapshot()` should include the bundled C/C++ workflow package manifest descriptor. This makes the package visible through the same read model as tools, resources, commands, and model profiles.

### Extension Diagnostics

`CHarnessWorkflowExtension` should expose a small `package_manifest()` method returning the bundled manifest dictionary.

No runtime activation should consume this manifest yet. `allowed_tool_names()`, `register_tools()`, and tool schema projection remain owned by current extension methods. Phase I is read-only control-plane visibility.

### Frontend And Session Shape

No required protocol field is added in Phase I.

The new package descriptor appears through capability snapshots and existing diagnostics paths. Frontends must treat it as read-model state, not execution policy.

## Non-Goals

Phase I will not:

- load workflow packages from remote registries
- add plugin marketplace behavior
- install dependencies
- move C/C++ pack activation to manifest-driven runtime behavior
- let project-local packages replace built-in tools
- add general multi-agent orchestration
- require JSON manifest files for the bundled package

## Acceptance Criteria

Phase I is complete when:

1. A generic workflow package manifest model exists and is JSON-serializable.
2. The bundled C/C++ workflow package can produce a manifest containing package identity, packs, tools, supported modes, supported workflow states, and resource scopes.
3. Invalid manifests return diagnostics or raise local validation errors without executing code.
4. `CapabilityRegistry` counts and projects `workflow_package` descriptors.
5. `InProcessAdapter.capability_snapshot()` includes the bundled workflow package descriptor.
6. No tool activation, tool execution, permission checks, resource reload, or extension loading behavior changes.
7. Active source-of-truth docs describe Phase I as read-only control-plane groundwork.

## Recommended Approach

Implement Phase I as a narrow read-model slice.

This is better than immediately switching runtime activation to manifests because the project is still offline/Win7 constrained and the default C/C++ package is product-critical. A read-only manifest gives us auditability and future migration hooks with very low behavioral risk.

After Phase I, the next slices can decide whether to:

- use manifests for workflow package diagnostics in session snapshots
- make local self-extension author package declarations
- move default pack activation from code constants to validated package declarations
- implement structured compaction state
