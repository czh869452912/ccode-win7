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

This means the repository now has one official execution spine centered on:

- `build` instead of `code`
- `TaskGraph` instead of prompt-only todo flow
- `run_recipe` / `report_quality_v2` instead of legacy duplicate verify tools in product paths
- frontend `tasks` vocabulary instead of `todos`

Recent stabilization work has also completed the GUI session-history single-source cutover:

- `transcript.jsonl` is now the only durable session-history truth
- GUI history is serialized from transcript-backed `Session` state
- GUI activation now uses one `/api/sessions/{id}/bootstrap` payload instead of split snapshot/timeline fetches

## 4. Remaining Near-Term Work

### 4.1 Legacy Helper Deletion

Remaining cleanup should focus on:

- removing dead compatibility shims that are no longer part of product paths
- deleting or archiving superseded helper modules
- removing outdated tests that preserve non-official behavior

### 4.2 Documentation Alignment

Current source-of-truth docs must remain aligned with the official architecture:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`

### 4.3 Real-World Validation

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
