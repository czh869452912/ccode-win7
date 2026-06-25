# Pre-Release Architecture Debt Audit

> Status: active
> Type: architecture audit baseline
> Owner: project maintainers
> Last synchronized: 2026-06-25

## 1. Purpose

This document records the pre-release architecture debt baseline for EmbedAgent.

The project is not live and has no production users. Therefore old internal
state formats, compatibility shims, transitional GUI contracts, and patch-style
adapter layers do not deserve product compatibility protection. Future work
should delete or replace those layers when they block the target architecture.

The hard product constraints still apply:

- Windows 7 compatibility is mandatory.
- Offline deployment is mandatory.
- Runtime Python remains `>=3.8,<3.9`.
- The default first-class workflow remains C/C++ application development with a
  bundled Clang-centered toolchain.
- Runtime behavior must not depend on Docker, WSL, VS Code, Electron, Node at
  runtime, online services, public marketplaces, or runtime dependency
  installation.

The target architecture is deliberately narrower:

- GUI behavior should match T3 Code directly instead of using custom product
  design or long-lived visual translation layers.
- Agent behavior should move toward Pi's small-core design: a durable
  session-log/reducer model, explicit turn snapshots, source-aware hooks,
  replaceable workflow packages, and local self-extension outside a thin kernel.

## 2. Reader And Action

This document is for internal engineers and future agents starting architecture
work. After reading it, they should be able to identify whether a proposed
change removes debt toward the Pi/T3 target or merely adds another adapter over
the current transitional design.

## 3. Operating Principle

Do not preserve compatibility with pre-release internal state.

When a subsystem is known to be transitional:

1. Promote the target model.
2. Migrate current tests and fixtures to the target model.
3. Delete the old model.
4. Update source-of-truth docs to describe only the promoted path.

Long-lived dual paths are defects. Short-lived migration scaffolding is allowed
only inside a bounded implementation slice and must be removed before the slice
is considered complete.

## 4. Core Findings

### 4.1 Agent Core Is Still Too Thick

The current codebase has introduced useful names such as AgentKernel,
AgentLoop, AgentLifecycleJournal, AgentToolActionService, AgentExtensionHost,
TurnSnapshot, and reducer-backed read models. The problem is that several of
these boundaries still sit behind a large session facade and callback-heavy
orchestration path.

Debt symptoms:

- QueryEngine still owns too much session mutation and orchestration knowledge.
- AgentLoop still coordinates context assembly, provider attempts, transcript
  writes, tool scheduling, compaction behavior, and session state updates in one
  path.
- InProcessAdapter still mixes hosted runtime ownership, GUI-facing projection,
  session lifecycle, timeline transport, resource reload, and review support.
- The implementation often says a responsibility has moved to a boundary while
  keeping compatibility references in the old owner.

Target direction:

- Reduce Agent Core to a small event-driven kernel that consumes a turn input,
  emits typed lifecycle events, requests provider/tool actions through explicit
  interfaces, and updates state through reducers.
- Keep workflow package behavior, hosted adapters, GUI projection, and
  environment-specific concerns outside the kernel.
- Treat QueryEngine as a facade only, not the place where new product semantics
  accumulate.

### 4.2 Session State Is Not Yet A Pi-Style Log Projection

The project has transcript truth, lifecycle events, runtime reducers,
compaction reducers, and recovery reducers. However live Session remains a
large mutable aggregate and restore still includes imperative replay logic.

Debt symptoms:

- Live Session contains messages, turns, compacted history, workflow state,
  pending interaction state, context snapshots, and other mutable fields.
- Restore reconstructs state through hand-authored event branching instead of a
  unified reducer graph.
- Some read models are transcript-backed, but the central session object is not
  yet a pure projection of durable entries.
- Compatibility state names make it easy for new code to bypass reducer truth.

Target direction:

- Make the durable session log the only state source.
- Derive live session, history, runtime config, compaction, recovery, workflow,
  and GUI bootstrap data through reducers/projections.
- Delete imperative restore branches as their corresponding reducer projections
  become authoritative.

### 4.3 Timeline Transport Still Behaves Like A Second Truth

The official rule says transcript is the session-history truth and timeline is
transport/replay infrastructure only. Current architecture still gives timeline
enough persistence and query behavior to act like a second state source.

Debt symptoms:

- Timeline events are persisted, sequenced, trimmed, repaired, queried, and
  replayed independently from transcript projections.
- GUI runtime merges bootstrap, snapshot, and timeline event data.
- Review and other GUI-facing flows can depend on timeline events rather than
  transcript/session projections.
- The existence of a durable timeline store invites future features to treat it
  as history.

Target direction:

- Remove durable product semantics from timeline.
- Build review, bootstrap, history, and diagnostics from transcript-backed
  projections.
- If a live event stream is still needed, keep it as an ephemeral transport
  cache or a transcript-derived replay channel, not an independent ledger.

### 4.4 Interactive Actions Are Outside The Unified Tool Pipeline

The tool action service owns most non-LLM action execution, but user
interaction and mode-switch style actions still have special handling in the
session facade.

Debt symptoms:

- Interaction tools can bypass normal action execution structure.
- Pending interaction lifecycle, prompt injection, resume behavior, and
  permission/tool semantics are split across multiple owners.
- Adding new interaction types risks creating more QueryEngine special cases.

Target direction:

- Model pending user input, approvals, and mode-switch proposals as first-class
  action results in the same execution pipeline.
- Keep permission checks, extension hooks, transcript events, lifecycle events,
  suspend/resume, and replay behavior on one path.
- Delete action-specific branches from the session facade once the common path
  exists.

### 4.5 Extension Hooks Are Source-Aware But Still Compatibility-Shaped

AgentEventBus is the right internal direction, but the current extension layer
still preserves method-name style hook dispatch and scattered merge semantics.

Debt symptoms:

- Extension behavior is still inferred from methods on extension objects.
- Some hook families go through the event bus while others remain direct
  manager calls.
- Reducer semantics are not yet visible as a compact, explicit extension
  contract.
- Self-extension authoring will remain fragile if generated extensions target
  implicit manager behavior.

Target direction:

- Define extension capabilities as explicit typed records and event reducers.
- Route all hook families through one source-aware event/reducer boundary or
  deliberately classify them as non-hook capability registrations.
- Remove method-name compatibility as a product contract.

### 4.6 GUI T3 Parity Is Currently Adapted, Not Native

The GUI has T3-inspired surfaces, but the app shape is still an EmbedAgent
design with T3-style rendering layered on top.

Debt symptoms:

- A large App component coordinates API calls, workspace/session activation,
  runtime state, permissions, tasks, artifacts, source control, terminal,
  preview, command palette behavior, and rendering.
- A large global reducer owns many unrelated state transitions.
- T3 timeline rows are projected from current EmbedAgent events instead of
  being fed by a backend contract shaped for the T3 runtime model.
- CSS and visual fixtures carry accumulated parity patches rather than a clean
  clone of the T3 UI architecture.

Target direction:

- Recreate T3 Code's GUI structure as the product target, not as an appearance
  layer.
- Use thread-scoped UI stores for right panel, terminal UI, composer state,
  thread selection, and workbench shell state.
- Make backend session/bootstrap payloads map directly to the T3-facing runtime
  contract expected by the GUI.
- Remove custom surfaces and controls that exist only because previous slices
  invented local design beyond T3 parity.

### 4.7 Visual Fixtures And Generated Assets Pollute Product Source

Visual debug fixtures are useful, but they should not live as first-class
production reducer actions. Generated static bundles are also too noisy for
normal source review when committed beside source code.

Debt symptoms:

- Product reducer state includes visual debug fixture actions.
- Generated static assets can hide real source changes in search and review.
- The visual harness can accidentally become a product behavior dependency.

Target direction:

- Move visual fixture injection into a dev-only harness boundary.
- Keep production reducers free of visual-only actions.
- Treat generated assets as release artifacts with explicit build/validation
  gates, or keep them out of ordinary source review paths.

### 4.8 Offline And Windows 7 Claims Need Real Bundle Proof

The repo-side offline runtime contract is valuable, but the release target is a
clean Windows 7 machine running the GUI and default C/C++ workflow from the
bundle.

Debt symptoms:

- Repo-side validation can pass without proving the real operating-system
  envelope.
- System-tool fallback is useful for development but can hide missing bundled
  tools if allowed in release paths.
- GUI parity is incomplete until the WebView2 109 fixed runtime and Win7 shell
  behavior are validated in the actual bundle.

Target direction:

- Treat clean Win7 unpack-and-run smoke as a release gate.
- Treat real C/C++ project validation as a release gate.
- Disable or explicitly quarantine system-tool fallback in release bundle
  validation.

## 5. Debt Retirement Order

The cleanup should proceed in deletion-oriented slices:

1. Freeze new feature work that deepens current transitional contracts.
2. Define the target Pi-style session-log/reducer/kernel contract and the
   target T3 GUI runtime contract.
3. Remove timeline as a durable product dependency.
4. Move interactive actions into the unified action pipeline.
5. Shrink the QueryEngine, AgentLoop, and InProcessAdapter responsibility
   cycle.
6. Replace GUI global app/reducer state with T3-shaped state modules.
7. Move visual fixtures and generated static assets out of product source
   paths.
8. Run real Win7 bundle and real C/C++ workflow validation against the promoted
   architecture.

Each slice must end by deleting the old path or explicitly recording why the
slice is incomplete.

## 6. Non-Goals For This Cleanup

This cleanup does not authorize:

- weakening Windows 7 support
- weakening offline deployment
- moving to Python 3.9+ syntax
- introducing Electron, Node runtime dependency, Docker, WSL, VS Code, or online
  services
- public plugin marketplaces
- runtime dependency installation
- hidden network or telemetry behavior
- general multi-agent orchestration
- replacing the default C/C++ workflow target with a generic web agent

## 7. Completion Bar

The debt program is not complete until:

- Agent Core can be explained without QueryEngine or InProcessAdapter carrying
  workflow-specific product behavior.
- Session restore is reducer-first instead of imperative replay with
  compatibility branches.
- Timeline is not queryable as history and not required for review/bootstrap
  truth.
- Interactive actions use the same action lifecycle as other tool calls.
- Extension contracts are explicit typed capabilities/events rather than
  method-name compatibility.
- GUI state shape follows T3 Code's module boundaries instead of a large custom
  reducer with T3-style renderers.
- Dev fixtures and generated assets no longer pollute production state review.
- A clean Windows 7 bundle can start the GUI and execute the default C/C++
  workflow offline.

