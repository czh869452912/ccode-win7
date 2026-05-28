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
- `Session.workflow_state` now exists as the generic workflow-state carrier while `Session.task_graph` remains a default harness compatibility mirror
- `SessionSnapshotProjector` and live frontend task APIs now project harness task fields from `Session.workflow_state["workflow"]`
- `InProcessAdapter` no longer constructs `HarnessRunner` directly; harness refresh and task-snapshot persistence are delegated to the built-in C harness extension
- `QueryEngine` now asks for schemas using explicit active tool names instead of `ToolRuntime.schemas_for_mode()`, so default harness pack activation is owned by the workflow extension boundary
- `CORE_PACK` no longer contains default harness workflow tools; build/debug/verify packs keep those tools explicitly for compatibility
- built-in mode `allowed_tools` no longer own default harness workflow tools; recipe, quality, evidence, and task-status tools are activated by the C harness extension
- `ToolRuntime.schemas_for()` now represents the pure mode contract by default, while default-harness paths use extension-active tool names or `schemas_for_mode()` compatibility projection
- `InProcessAdapter` now owns one `ExtensionManager` shared with session-scoped `QueryEngine` and frontend tool catalog visibility
- `InProcessAdapter` no longer directly imports or constructs `HarnessStateSynchronizer`; the service remains lazily import-compatible while product refresh uses the harness extension directly
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

### 4.1 Legacy Helper Deletion

Remaining cleanup should focus on:

- removing dead compatibility shims that are no longer part of product paths
- deleting or archiving superseded helper modules
- removing outdated tests/manual samples that preserve non-official behavior

### 4.2 Workflow Extension Decoupling

Near-term decoupling should continue from the new extension boundary:

- remove `HarnessStateSynchronizer` once downstream compatibility tests no longer import it directly
- remove remaining compatibility callers that still depend on `ToolRuntime.schemas_for_mode()` or harness-specific service facades
- defer project-local extension discovery until the built-in shared-manager path has more real-world mileage

### 4.3 Documentation Alignment

Current source-of-truth docs must remain aligned with the official architecture:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`

### 4.4 Documentation Governance Baseline

- establish the active docs governance scaffold
- create module-level documentation for core code areas
- standardize terminology, templates, and Mermaid usage
- keep `superpowers -> global docs -> archive` synchronization as the default closure path

### 4.5 Real-World Validation

After architecture cutover, the highest-value validation is:

- real C workspace flows
- recipe discovery quality
- Clang diagnostics quality
- Win7 bundle runtime validation

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
- keep tightening offline bundle behavior
- keep the transcript-backed session-history path as the only official history model
- do not reopen old dual-path architecture
