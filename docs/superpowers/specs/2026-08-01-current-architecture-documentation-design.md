# Current Architecture Documentation Design

> 状态：`active`
> 类型：`design`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-01`

## Purpose

Reorganize active documentation around the architecture EmbedAgent is converging toward:
a reusable, Windows 7-compatible Agent platform; independently owned applications built on that
platform; and the EmbedAgent product composition that packages and ships them. Remove active
descriptions of retired runtime paths and replace lifecycle-versioned document names with stable
ownership names.

This design is temporary implementation context. After the migration is verified, durable truth
belongs in the new authority documents and this design moves to the documentation-system archive.

## Reader And Outcome

The primary reader is a contributor or agent arriving without repository history. After reading
the documentation map, that reader must be able to identify whether a change belongs to the
generic Agent platform, an application such as the C/C++ workflow, or EmbedAgent product
composition and delivery, then open exactly one current owner before editing code.

## Problem

The source architecture has removed `QueryEngine`, `SessionRestorer`, mutable Host ownership of
Core `Session`, and the old harness-specific runtime. Several active authorities still describe
those objects as current participants or link to deleted source paths. The active C/C++ authority
is split between a module overview and `agent-harness-v2.md`, even though there is no maintained
V1/V2 document lifecycle.

The `docs/modules/` bucket also mixes generic Agent runtime, reusable GUI/TUI shells, C/C++
application behavior, and product delivery. That layout obscures the desired extraction boundary:
the Agent platform should eventually be movable to an independent repository without carrying the
C/C++ application or EmbedAgent-specific delivery policy with it.

## Considered Approaches

### Patch Names In Place

Rename `agent-harness-v2.md` and replace retired terms without changing the directory structure.
This minimizes churn but preserves ambiguous ownership and guarantees another documentation
migration when the Agent platform is extracted.

### Domain-Oriented Physical Migration

Move current authorities into `platform/`, `applications/`, and `product/`; consolidate duplicate
owners; update all routing; and add guards for retired terms and lifecycle-versioned active paths.
This creates link churn now, but the churn is mechanical and produces boundaries that match the
intended architecture. This is the selected approach.

### Standalone Agent Manual Now

Create a separate, extraction-ready Agent manual while leaving repository documentation in place.
This would duplicate current truth before the code is actually separated and directly violate the
one-fact-one-owner rule.

## Target Taxonomy

The root keeps only cross-domain and current-work authorities:

```text
docs/
  README.md
  overall-solution-architecture.md
  current-status.md
  implementation-roadmap.md
  platform/
  applications/
  product/
  guides/
  workflows/
  references/
  adrs/
  archive/
  superpowers/
```

### Platform

`docs/platform/` owns reusable Agent capabilities that are expected to survive extraction from the
EmbedAgent repository:

- public Agent SDK, kernel, loop, journal, reducer, and focused ports;
- hosted session runtime and durable session truth;
- extension, tool-runtime, permission, context, mode, and provider contracts;
- Host/UI protocol and capability projections;
- registrable GUI and TUI shell boundaries;
- the target blueprint for an independent Windows 7-compatible Agent platform.

GUI and TUI belong here because their behavior is backend-declared and moving toward generic
registration. Product-specific WebView2 packaging remains a product delivery concern.

### Applications

`docs/applications/` owns behavior selected above the generic platform. The first authority is
`cpp-workflow.md`, the sole current owner of C/C++ discipline profiles, execution phases,
`TaskGraph`, packs, recipes, workflow prompts, workflow tools, and workflow projection.

The document describes the C/C++ workflow as one bundled application, not as a Core default or a
generic Agent mode schema. New applications receive peer documents rather than extending the C/C++
authority.

### Product

`docs/product/` owns EmbedAgent-specific composition and delivery:

- product catalog and selection of the bundled C/C++ application;
- assembly of the six distributions into the shipped product;
- offline assets, Windows 7 packaging, and release evidence boundaries.

It does not own generic GUI/TUI behavior, tool activation, permission policy, or workflow
semantics.

## Authority Migration

| Current authority | Target authority | Action |
|---|---|---|
| `docs/modules/agent-core.md` | `docs/platform/agent-core.md` | Move and correct current execution ownership |
| `docs/modules/session-runtime.md` | `docs/platform/session-runtime.md` | Move, replace retired flow, absorb session-truth boundary |
| `docs/guides/session-truth-boundary.md` | `docs/platform/session-runtime.md` | Merge durable rules, then delete |
| `docs/modules/tools-and-tooling.md` | `docs/platform/tools-and-extensions.md` | Move and describe current extension-host/runtime split |
| `docs/tool-contracts.md` | `docs/platform/tool-contracts.md` | Move generic contracts; move C/C++ catalog to application |
| `docs/modules/permissions-and-context.md` | `docs/platform/permissions-and-context.md` | Move and replace retired data flow |
| `docs/permission-model.md` | `docs/platform/permission-model.md` | Move current permission contract |
| `docs/modules/protocol-and-core.md` | `docs/platform/protocol.md` | Move and describe current Core/Host/UI boundary |
| `docs/frontend-protocol.md` | `docs/platform/frontend-protocol.md` | Move current transport and shell protocol contract |
| `docs/modules/frontend-gui.md` | `docs/platform/frontend-gui.md` | Move as registrable generic shell authority |
| `docs/modules/frontend-tui.md` | `docs/platform/frontend-tui.md` | Move as registrable generic shell authority |
| `docs/mode-schema.md` | `docs/platform/mode-contract.md` | Move generic mode policy; move C/C++ phase semantics out |
| `docs/pi-inspired-agent-core-blueprint.md` | `docs/platform/agent-platform-blueprint.md` | Rename as future extraction direction, not current state |
| `docs/modules/harness.md` | `docs/applications/cpp-workflow.md` | Merge current module ownership |
| `docs/agent-harness-v2.md` | `docs/applications/cpp-workflow.md` | Merge current workflow contract, then delete |
| `docs/modules/packaging-and-deployment.md` | `docs/product/packaging-and-deployment.md` | Move and replace phase-named stable sections |
| none | `docs/product/composition.md` | Create product catalog and application-selection owner |

`docs/modules/README.md` is deleted after the migration. New `README.md` files in each domain are
local navigation indexes, while `docs/README.md` remains the only global intent map.

## Current Truth Rules

- Retired runtime names may appear only in an explicit removed/forbidden statement or historical
  archive. They must not appear as current actors, source paths, diagram participants, or test
  recommendations.
- Stable authority filenames do not carry implementation generations such as `v1`, `v2`, or a
  completed phase name.
- Real protocol/schema/tool identifiers keep their version suffixes. Examples include
  `report_quality_v2`, schema version fields, and Mermaid `stateDiagram-v2` syntax.
- Open delivery programs may retain Phase labels in `current-status.md`,
  `implementation-roadmap.md`, and indexed active plans. Stable architecture and module documents
  use outcome-oriented headings instead.
- ADRs and archive packages preserve historical names when the name is necessary to understand the
  decision or artifact.
- No compatibility redirect documents are created for old active paths. All active references are
  updated atomically.

## Content Boundaries

Module-style platform documents own responsibilities, collaborators, data flow, change triggers,
and verification entry points. Contract documents own public records, event shapes, decisions, and
semantics. They must link rather than restate each other's inventories.

The C/C++ application document owns all C/C++-specific tool names, packs, phases, tasks, recipes,
and prompt behavior. Generic platform contracts may explain how an application contributes those
capabilities but must not enumerate the default C/C++ catalog.

The platform blueprint describes the desired independent foundation and placement tests. It does
not claim that repository extraction has happened, track migration progress, or override current
platform authorities.

## Navigation And Governance

Update the contributor constitution, global documentation map, overall architecture, governance,
style guide, code-doc workflow, code-doc matrix, and local domain indexes in the same change. The
global map routes first by platform, application, or product intent, then by behavior.

Add an ADR for the durable platform/application/product separation. The ADR records why GUI/TUI
belong to the reusable platform while C/C++ remains an application and Win7 bundle assembly remains
product-owned. The ADR must not become a second current implementation manual.

## Mechanical Guards

Documentation tests must enforce:

1. all routed authority paths exist;
2. removed active paths no longer exist;
3. active Markdown filenames do not use lifecycle generation suffixes;
4. retired runtime names and deleted source paths occur only in explicit removed/forbidden context;
5. generic platform contracts do not enumerate application-owned C/C++ tools or workflow phases;
6. current-work Phase labels remain confined to current status, roadmap, active plans, release
   procedures, ADRs, and archive;
7. the global authority documents remain within their context budgets.

Existing architecture guards continue to verify code ownership. Documentation guards verify that
the written execution path cannot regress independently of the source path.

## Verification

Run the documentation navigation test first, then the architecture guard pair, full Python
partition, and lint. Use repository search to confirm old active paths, retired actors, and
lifecycle-versioned authority names are absent. Run link/path checks through the documentation test
rather than retaining compatibility stubs.

The migration is complete when a fresh reader can route from `docs/README.md` to one current owner
for each platform, application, or product change; no active authority describes a deleted runtime
path; and all prescribed gates pass.

## Non-Goals

- moving Python distributions to another repository in this change;
- changing runtime behavior, public APIs, protocol payloads, workflow semantics, or packaging;
- renaming real versioned protocol fields, tool identifiers, or Mermaid syntax;
- rewriting historical ADRs and archive artifacts to current terminology;
- creating a second documentation site or extraction-time compatibility layer.
