# Documentation Navigation System Design

**Status:** Approved

**Date:** 2026-08-01

## 1. Goal

Turn the active documentation set into a low-context navigation map for coding
agents and maintainers. A reader landing cold should be able to identify the
authoritative document for a task, load only the relevant contract or module
guide, and avoid historical implementation narrative unless explicitly doing
forensics.

The primary reader is an implementation agent entering the repository without
prior session context. After reading `AGENTS.md` and the documentation map, that
agent must be able to:

1. identify the non-negotiable product and delivery constraints;
2. find the single authority for the subsystem being changed;
3. find the relevant verification commands;
4. distinguish open work from completed history; and
5. avoid loading archive material during normal implementation.

## 2. Problem Evidence

The active documentation layer currently mixes navigation, current contracts,
implementation detail, and historical progress:

| Document | Current size | Main issue |
|---|---:|---|
| `README.md` | 546 lines / 6,279 words | Repeats architecture, module inventory, progress, and verification history |
| `AGENTS.md` | 615 lines / 6,048 words | Loads detailed subsystem history and GUI implementation rules into every agent context |
| `docs/overall-solution-architecture.md` | 1,155 lines / 9,909 words | Mixes system topology with detailed module notes and completed phase narrative |
| `docs/implementation-roadmap.md` | 911 lines / 8,197 words | Mostly records completed programs instead of remaining sequence |
| `docs/development-tracker.md` | 1,308 lines / 16,292 words | Contains dozens of dated closeouts despite its own recent-only rule |
| `docs/design-change-log.md` | 9,347 lines / 39,633 words | Acts as an unbounded historical ledger and duplicates ADR, tracker, and archive roles |

Completed Phase 7C, minimal Agent Core convergence, test-feedback foundation,
and earlier CI alignment materials also remain under active `docs/superpowers/`
even though their implementation commits have landed. The active navigation
page still describes an older state in which only the Phase 7B handoff remains.

## 3. Design Principles

### 3.1 Map, not memory

Default-loaded documents route the reader to authority. They do not preserve
the implementation journey or enumerate every current class and helper.

### 3.2 One fact, one owner

Every durable fact has one authoritative home:

- product constraints and agent rules: `AGENTS.md`;
- repository orientation and human quick start: `README.md`;
- documentation routing and authority map: `docs/README.md`;
- system topology and cross-distribution invariants: overall architecture;
- subsystem contracts: contract and module documents;
- open sequencing: implementation roadmap;
- immediate focus, blockers, and next actions: current status;
- durable decisions and rationale: ADRs;
- completed work and historical evidence: archive.

Other documents link to the owner and provide only the minimum local context
needed to explain why the link matters.

### 3.3 Progressive disclosure

The normal reading path is:

```text
AGENTS.md / README.md
        -> docs/README.md
        -> one architecture, contract, module, guide, or workflow document
        -> source and tests
```

Archive and completed slice documents are excluded from this path.

### 3.4 Open work only in active status documents

The roadmap and current-status page contain no completed phase chronology.
They may state a completed dependency only when it is necessary to explain an
open gate, and then only in one sentence with an archive or ADR reference.

### 3.5 Preserve history without promoting it

This cleanup does not delete historical evidence. Existing trackers, change
records, superseded roadmaps, completed designs, implementation plans, and
closeouts move into topic-based archive packages. Git history remains an
additional audit source, but archive indexes make preserved material
discoverable without placing it in the normal agent path.

## 4. Target Information Architecture

### 4.1 Entry layer

`README.md` becomes a compact human and agent entry point containing:

- product identity and stable compatibility promises;
- distribution-level architecture in one short diagram or table;
- quick development and release commands;
- a task-oriented documentation routing table;
- explicit release-evidence limitations.

It does not contain component-by-component inventories, completed phase lists,
recent verification summaries, or detailed GUI controller boundaries.

`AGENTS.md` becomes the smallest complete agent constitution containing:

- hard compatibility, dependency, security, and offline constraints;
- package ownership and dependency direction;
- official vocabulary and prohibited compatibility paths;
- required read routing by task type;
- test and release gates;
- documentation maintenance rules.

Detailed subsystem ownership moves to the relevant architecture, contract, or
module document. An agent reads those documents only when its task touches that
area.

### 4.2 Map layer

`docs/README.md` becomes the only global documentation map. It routes by reader
intent rather than merely listing directories:

| Intent | Authority |
|---|---|
| Understand system topology | overall architecture |
| Change Agent Core or session runtime | corresponding module and contract documents |
| Change tools, permissions, workflow, or protocol | corresponding contract and module documents |
| Change GUI/TUI | frontend contract plus the relevant frontend module document |
| Build or validate the offline bundle | packaging module plus Win7/release guides |
| Select current work | implementation roadmap and current status |
| Understand a past decision | ADR index |
| Investigate a completed slice | archive index |

The existing code-doc matrix is folded into this intent map or retained only as
a generated/detail reference if it adds information not present in the map.

### 4.3 Authority layer

The overall architecture is reduced to:

- scope and hard assumptions;
- six-distribution ownership and dependency graph;
- execution spine;
- session/transcript truth flow;
- extension, tool, permission, and workflow boundaries;
- frontend and product composition boundaries;
- offline bundle boundary;
- links to subsystem authorities.

Contract documents retain stable public or cross-layer behavior. Module
documents retain code ownership, entry points, data flow, dependencies, tests,
and prohibited responsibilities. Repeated cross-layer narrative is removed
from lower-priority documents.

Large on-demand documents such as the frontend protocol and GUI module are not
automatically archived: they remain active when their detail is current and
cohesive. This cleanup removes duplicated history and redirects overlapping
rules to one owner; later splitting is justified only if a document still has
multiple independent audiences after deduplication.

### 4.4 Current-work layer

`docs/implementation-roadmap.md` is rewritten around open programs only:

- clean Windows 7 SP1 x64 / WebView2 109 external acceptance;
- real C/C++ project validation;
- any genuinely open CI or test-asset follow-up confirmed by repository state;
- optional enterprise/intranet work clearly marked as later and out of Core.

A new `docs/current-status.md` contains only:

- current focus;
- blocking external evidence;
- next actions;
- active slice links;
- last verified date and evidence scope.

The page has no append-only update log. Each update replaces stale status.

### 4.5 History layer

A documentation-history archive package receives frozen snapshots of:

- the existing development tracker;
- the existing design change log;
- the superseded implementation roadmap where needed for continuity.

Completed slice documents move from `docs/superpowers/` into the closest
existing topic archive. At the current baseline:

- Phase 7C architecture convergence moves to `docs/archive/agent-core-program/`;
- minimal Agent Core convergence moves to `docs/archive/agent-core-program/`;
- the TDD test-feedback foundation moves to a new
  `docs/archive/test-feedback-and-ci/` package;
- the 2026-07-20 CI alignment plan moves to the same test/CI archive package;
- the Phase 7B Win7 handoff remains active while target-machine acceptance is open;
- the 2026-08-01 cross-platform frontend CI slice remains active until its
  required hosted verification is confirmed; it is not classified as completed
  merely because the implementation commit exists.

Every affected archive package receives or updates a short index. Active docs
may link to the archive only as historical evidence, never as the current
contract.

## 5. Context Budgets

Budgets are guardrails, not incentives to remove essential constraints. A
document exceeding its budget must either justify the exception in the
documentation map or move detail to a more specific authority.

| Document class | Target budget |
|---|---:|
| `README.md` | 1,500 words |
| `AGENTS.md` | 2,500 words |
| `docs/README.md` | 1,000 words |
| Overall architecture | 3,000 words |
| Implementation roadmap | 1,000 words |
| Current status | 750 words |
| Typical module document | 1,500 words |

Contract documents may exceed the typical module budget when they define a
single cohesive protocol or schema, but must not carry progress logs or repeat
module inventories already owned elsewhere.

## 6. Migration Rules

For every active document:

1. classify each section as navigation, current contract, operation guide,
   open status, durable decision, or history;
2. retain it only in the layer that owns that class;
3. replace duplicated detail with a link to the owner;
4. move historical content to an indexed archive package;
5. remove stale links and references to retired files or APIs;
6. ensure a cold reader can reach source and tests from the retained authority.

The cleanup must not change runtime behavior, package ownership, compatibility
requirements, or release acceptance criteria. It must preserve Python 3.8,
Windows 7, offline bundle, C/C++ workflow, and external Win7 evidence rules
without forcing those rules into every document.

## 7. Governance Changes

The documentation workflow changes from append-everywhere to update-the-owner:

- do not update a global tracker and change log for every implementation slice;
- update current status only when focus, blocker, or next action changes;
- update the roadmap only when open program sequencing changes;
- update a contract or module document only when its durable behavior changes;
- create an ADR only for a durable decision with meaningful alternatives;
- archive completed slice specs/plans after their durable conclusions are in
  the authority layer;
- keep `docs/superpowers/` indexed and limited to active work.

The documentation style guide gains explicit rules against completion
chronologies, recent-work sections, repeated component inventories, and
unbounded append-only active documents.

## 8. Verification

The cleanup adds or extends lightweight repository checks that verify:

- required entry and authority documents exist;
- navigation links resolve;
- archived tracker/change-log files are not listed as active authorities;
- `docs/superpowers/` contains only explicitly indexed active slices;
- default-loaded and status documents remain within their agreed budgets;
- active roadmap and current-status documents do not accumulate completed
  phase ledgers;
- active docs do not cite archive material as current truth;
- all six distribution, Win7, offline, Python 3.8, and C/C++ constraints remain
  reachable from `AGENTS.md` and the map.

Verification is documentation-only plus existing architecture/lint guards. No
GUI build, runtime test suite, or release bundle rebuild is required unless the
cleanup touches source, generated assets, commands, or release scripts.

## 9. Success Criteria

- A fresh agent reads `AGENTS.md`, follows one map hop, and reaches the correct
  subsystem authority without reading progress history.
- `README.md`, `AGENTS.md`, overall architecture, roadmap, and current status
  satisfy their context budgets or carry a documented exception.
- The existing development tracker and design change log are preserved only in
  archive history.
- The active roadmap contains only open sequencing and exit conditions.
- Completed slice documents are absent from active `docs/superpowers/`.
- Every historical move is indexed and every active reference resolves.
- No product or architecture invariant is lost; it has one explicit active
  owner.

## 10. Non-Goals

- rewriting source code or changing runtime behavior;
- preserving old active-document paths as compatibility aliases;
- creating a documentation portal or external site;
- introducing a general metadata registry before the simpler map proves
  insufficient;
- treating Git history or archive material as required reading for ordinary
  implementation.
