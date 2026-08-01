# Standalone Agent Platform Direction

> 状态：`target`
> 类型：`architecture-direction`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-01`
> 当前实现：`docs/overall-solution-architecture.md`

## Purpose

This direction evaluates future architecture proposals against a small, composable, self-extensible Agent Platform inspired by Pi's functional design philosophy while preserving EmbedAgent's Windows 7, offline, Python 3.8, and default-application constraints.

It is not an implementation ledger, public API announcement, or migration schedule. Implemented behavior belongs in the current platform, application, product, and contract authorities.

## Minimal Core Thesis

Core should contain only the contracts and deterministic policy needed to run and restore an agent session. Concrete providers, workspace intelligence, stores, UI shells, workflow defaults, network adapters, and product configuration remain replaceable collaborators outside Core.

New Core responsibilities require stronger justification than new Host or extension responsibilities. A proposal belongs in Core only when it is workflow-neutral, required by standalone callers, deterministic under replay, and impossible to express through a focused port or capability boundary without breaking correctness.

## Durable State And Reducers

- Every durable state transition should be representable as an appendable, JSON-safe event.
- Live state and restore should fold the same event families through the same deterministic reducers.
- Event append must precede live-state publication; failure must not create a second truth.
- Runtime configuration, compaction, recovery, capabilities, and user-facing experience should be derived read models, never independent execution authorities.
- Recovery markers should explain trusted prefixes and skipped work without retrying effects or changing restore validation.

## Source-Aware Extension Boundary

Extensions should declare capabilities rather than gain behavior through method-name discovery. Every hook, tool, resource, and workflow contribution should carry source identity and safe diagnostics. Merge, stop, and observer semantics should be defined once per event family at the shared bus boundary.

Runtime owners should talk to one extension host. They should not accumulate direct calls to workflow packages or project extensions. A capability record describes participation; it never grants permission or execution authority by itself.

## Explicit Turn Snapshots

Provider requests should consume one frozen turn snapshot created after context assembly and active tool projection. Safe diagnostics may record identity, mode/workflow state, registered and active tool names, credential-free model metadata, prompt-unit metadata, and capability counts. They must not record prompt bodies, file contents, raw tool outputs, or secrets.

Snapshots make replay and failure analysis precise: the request is explained by one immutable input rather than reconstructed from mutable services.

## Structured Compaction And Recovery

Compaction should emit a safe boundary with token/message counts, preserved anchors, file activity, evidence references, and trigger metadata. It should not create a hidden history source or let extensions rewrite durable truth.

Recovery should reduce explicit markers into an inspection read model. It may summarize operations, compaction, runtime configuration, stop reasons, and malformed/duplicate records, but it must not retry tools, select modes, activate capabilities, or bypass permission policy.

## Capability And Workflow Read Models

A capability registry should describe tools, local resources, slash commands, model profiles, and workflow packages with provenance. A workflow package manifest should describe identity, supported states, declared tools, packs, scopes, and diagnostics. Both are non-executing read models.

Tool activation remains an extension-host decision; execution remains a tool-runtime decision; authorization remains a permission-policy decision. Frontends consume safe projections and do not infer these policies from tool names.

Every workflow application, including the product default, should remain a replaceable package using the same capability boundary as other trusted local extensions. Application tasks, packs, prompts, recipes, quality reporting, and workflow projection must not thicken workflow-neutral Core.

## Local Self-Extension

The offline product should support a bounded authoring loop:

- workspace skills, prompts, and recipe files as reloadable data;
- disabled-by-default project Python extension skeletons;
- explicit, workspace-bound manifests and permissions;
- no runtime dependency installation, remote registry, online marketplace, or built-in replacement;
- no implicit reload or code execution after authoring.

Self-extension improves local adaptability only when it preserves reproducibility, permission checks, provenance, and the base offline workflow.

## Enterprise And Intranet Adapters

Organization-local catalogs, intranet Git, custom model/service providers, and passive telemetry may be added as trusted Host providers, workflow packages, project extensions, or sinks. They must be explicit, disableable, timeout-bound, failure-tolerant, manifest/config gated, and subject to `network` or `telemetry` permissions.

Network availability must never become a Core assumption or a prerequisite for default operation. Diagnostics and telemetry expose safe envelopes, not prompts, source text, raw outputs, credentials, tokens, or approvals.

## Placement Test

| Responsibility | Correct owner |
|---|---|
| Workflow-neutral standalone SDK, deterministic session policy, focused ports | Core |
| Concrete providers, stores, workspace intelligence, hosted lifecycle, local tools | Host |
| Scenario prompts, tools, packs, tasks, recipes, workflow projection | Application package |
| Workspace-specific trusted hooks or tools with explicit manifest | Project extension |
| Composition, configuration defaults, app catalog, launcher selection, delivery assets | Product |
| Registrable shell contracts, rendering safe projections, collecting user intent | Platform frontend layer |

When a responsibility could fit multiple rows, choose the lowest-coupling owner that keeps Core standalone and replay deterministic. Do not move policy into the frontend merely to avoid a Host boundary.

## Non-Goals

- Public remote registries, online extension installation, dependency installation at runtime, or a plugin marketplace.
- General multi-agent orchestration in Core.
- Runtime dependencies on Docker, WSL, VS Code, Node.js, or network services.
- Compatibility layers for obsolete pre-release internals.
- Treating manifests, capability registries, snapshots, reducers, or telemetry as permission grants or execution engines.
- Weakening the bundled C/C++ workflow, Windows 7 support, Python 3.8, or clean offline startup.

## Acceptance Tests For Future Proposals

A proposal aligned with this blueprint should answer yes to all applicable questions:

1. Does Core remain workflow-neutral and usable without product or Host imports?
2. Can durable behavior be replayed from one event log through deterministic reducers?
3. Are activation, execution, permission, and write-path decisions still separate?
4. Is source identity visible for every extension contribution?
5. Can the feature be disabled without breaking the base offline C/C++ workflow?
6. Are provider inputs and recovery/compaction state explicit and safely inspectable?
7. Does the bundle contain every runtime dependency and remain compatible with Windows 7 and Python 3.8?
8. Is current behavior documented in the owning authority rather than in this direction document?
