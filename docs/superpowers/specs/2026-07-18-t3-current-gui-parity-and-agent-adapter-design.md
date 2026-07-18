# T3 Current GUI Parity And Agent Adapter Design

## Status

Approved for design capture on 2026-07-18.

This document defines the next GUI phase after the completed Core, Host,
Protocol, Composition, and C/C++ workflow extraction. It is an incremental
parity program. The existing GUI already contains several T3-inspired slices;
the work here continues them against the current `reference/t3code` checkout
instead of replacing the GUI with a second design.

The current T3 reference baseline is:

```text
commit: 2318e00270203780b72efbbcffce92e907312027
date:   2026-07-18
subject: fix(web): avoid duplicate mention text on paste
```

The reference commit is a moving comparison baseline, not a runtime
dependency. A later T3 update requires a new parity diff and does not justify
blindly importing its dependency graph.

## Decision Summary

Keep the current React 18, Vite 5, pywebview, WebView2 109, and offline build
baseline. Copy T3's user experience and frontend state boundaries where they
apply, while implementing the compatible subset with the repository's current
toolchain.

The GUI is divided into four explicit layers:

1. T3-shaped presentation components and page/workbench composition.
2. T3-shaped client runtime state and pure reducers.
3. A versioned, JSON-safe Agent App Protocol consumed by the client runtime.
4. One EmbedAgent transport adapter that maps HTTP/WebSocket traffic to the
   protocol and sends commands back to the selected hosted Agent.

The renderer does not import Agent Core, Host, workflow packages, or product
configuration. Base and specialized Agents expose the same protocol and differ
only through declared capabilities, surfaces, commands, and activity data.

## Goals

- Keep the existing GUI parity work and move it closer to the current T3 Code
  UX and client architecture.
- Use T3's Sidebar, ChatView, ChatHeader, Composer, timeline, right-panel,
  terminal, source-control, settings, and responsive interaction patterns as
  the visual and behavioral reference.
- Reduce `App.jsx` to top-level composition, route activation, and runtime
  wiring; move state transitions into domain-specific client-runtime modules.
- Make one protocol adapter the only place that knows EmbedAgent transport
  payload shapes.
- Let an unchanged GUI load a base Agent and a workflow-specialized Agent by
  consuming backend-declared capabilities.
- Track T3 changes with a pinned commit and a repeatable component/state/protocol
  difference ledger.
- Preserve Windows 7, Python 3.8, WebView2 109, and offline operation.

## Non-Goals

- Do not import T3's monorepo as a package or copy its whole dependency graph.
- Do not introduce React 19, Node 24, Effect runtime, Vite Plus, Electron,
  Clerk, Relay, cloud services, mobile surfaces, or remote-environment
  requirements solely for GUI parity.
- Do not create a new visual language or redesign existing T3-shaped surfaces.
- Do not move Agent policy, workflow execution, permissions, transcript truth,
  or tool implementation into the GUI.
- Do not preserve obsolete internal GUI reducer or transport compatibility
  shapes when a slice can replace them cleanly.

## Existing Work To Preserve

The current webapp already provides the foundation for this phase:

- T3-shaped `AppSidebarLayout`, `Sidebar`, `CommandPalette`, `BranchToolbar`,
  `Composer`, `DiffPanel`, and right-panel surfaces.
- `session-runtime/t3-timeline.js` for rich timeline projection.
- `workbench` parity models and responsive layout rules.
- app and session capability models backed by bootstrap data.
- separate session activity, interaction, source-control, terminal, and
  workspace-file controllers.
- visual debug fixtures and GUI-focused tests.

These modules are migrated or corrected in place. They are not duplicated in a
new parallel GUI shell.

## Target Runtime Architecture

### Presentation Layer

Presentation components follow the current T3 component hierarchy and consume
only client-runtime read models and callbacks. They may retain T3-specific
layout constants, typography, spacing, keyboard behavior, and responsive
breakpoints because those are UX decisions rather than Agent policy.

The primary parity surfaces are:

- app shell and workspace empty state;
- sidebar and thread navigation;
- thread header and branch/workspace controls;
- timeline rows, tool details, changed files, plans, and interactions;
- composer, slash-command menu, approval, and user-input panels;
- right-panel tabs, file preview, and diff surfaces;
- terminal drawer and source-control panel;
- command palette, settings navigation, and diagnostics;
- narrow and mobile-stacked layouts supported by the current shell.

### Client Runtime Layer

The frontend owns a T3-shaped state model and pure reducers. The minimum
domains are:

- `threadState` and `threadReducer`;
- `shellState` and `shellReducer`;
- `activityState` and `activityReducer`;
- `composerState`;
- `surfaceState` for right panels and drawers;
- `terminalState`;
- `sourceControlState`;
- `capabilityState` for app/session declarations.

The runtime consumes normalized protocol snapshots and ordered events. It does
not reconstruct history from raw WebSocket messages, infer workflow semantics,
or invoke Agent services directly.

`App.jsx` remains a composition root only. It may create the transport,
activate the current thread, and provide route-level providers, but domain
reducers and backend-specific event branching must live below it.

### Agent App Protocol

The protocol remains JSON-safe and versioned. It carries:

- app-shell metadata, workspace registry, surfaces, settings, and safe
  diagnostics;
- session/thread bootstrap snapshots;
- messages, activities, turn status, changed-file summaries, and workflow
  read-model payloads;
- mode, command, tool, resource, model, and workflow package capabilities;
- pending approval and user-input interactions;
- command requests/results and ordered lifecycle events.

The protocol may expose renderer presentation metadata such as labels, icons,
preview argument names, changed-file argument names, and surface descriptors.
It must not expose credentials, raw prompt bodies, source files, raw tool output,
or permission secrets.

### EmbedAgent Adapter

One adapter translates between the protocol and the current backend routes,
WebSocket event stream, and command APIs. It owns:

- HTTP bootstrap and command request encoding;
- WebSocket connection and reconnect behavior;
- protocol version negotiation;
- normalization of backend payloads;
- mapping command results to structured fields such as
  `switch_session_id`, `log_label`, and `log_detail`;
- transport-level error and pending-response handling.

Components and client reducers must not call `routes_sessions.py`, inspect
EmbedAgent-specific event names, or branch on slash command strings.

## Agent Adaptation Rules

The renderer must remain unchanged when a different Agent declares:

- a different product name or empty-state copy;
- different modes or workflow states;
- different tools and tool presentation metadata;
- different commands and command groups;
- different right-panel surfaces;
- different interaction questions or approval categories;
- no C/C++ workflow at all.

The following are allowed to remain GUI-owned constants:

- T3-derived layout dimensions and responsive breakpoints;
- generic activity row kinds and interaction affordances;
- generic keyboard and focus behavior;
- visual debug fixture identifiers in test-only modules.

The following must not be renderer-owned:

- Agent or workflow names;
- C/C++ or Clang labels;
- built-in tool-name presentation branches;
- mode-to-tool activation policy;
- slash-command-to-session switching inference;
- product or agent fallback branding;
- workflow-specific task fields outside the generic workflow projection.

## Incremental Milestones

### P4.0: Reference And Difference Ledger

- Record the T3 reference commit and affected upstream paths.
- Compare current and reference component structure, state modules, contracts,
  and key interaction flows.
- Classify each difference as UX, client-runtime, protocol, or intentionally
  unsupported T3 infrastructure.
- Add a short update procedure so a newer T3 checkout can be re-baselined.

### P4.1: Shell And Navigation Parity

- Close remaining visual and interaction differences in Sidebar, thread list,
  empty state, ChatHeader, BranchToolbar, command palette, settings, and
  responsive shell layout.
- Keep all visible copy and actions supplied by app-shell descriptors.
- Preserve existing focused component tests and add reference-behavior tests
  for changed interactions.

### P4.2: Client Runtime Convergence

- Extract remaining thread, shell, activity, composer, surface, terminal, and
  source-control transitions from `App.jsx` and ad hoc controllers.
- Make reducers consume normalized protocol records and ordered event
  envelopes.
- Remove duplicate GUI-local session-history and interaction truth.

### P4.3: Protocol Adapter Closure

- Define the single frontend adapter boundary and route all bootstrap, event,
  command, and interaction traffic through it.
- Add contract fixtures for a minimal base Agent and a workflow-specialized
  Agent.
- Delete direct renderer dependence on backend route and payload names.

### P4.4: T3 Timeline And Workbench Parity

- Reconcile current T3 timeline row behavior, composer states, changed-file
  presentation, diff/file surfaces, terminal drawer, and source-control
  interactions against the new reference commit.
- Copy applicable T3 interaction behavior; omit only unsupported cloud,
  remote, mobile, and desktop-host integrations.

### P4.5: Dynamic Agent Verification And Hardcode Removal

- Run the same GUI against at least two protocol fixtures with different
  capabilities.
- Remove remaining agent-specific renderer branches and fallback branding.
- Add static source checks for forbidden tool, workflow, and product literals.

### P4.6: Release-Ready GUI Gate

- Run `npm test`, `npm run build`, focused Python GUI/backend tests, and visual
  debug scenarios.
- Commit generated static assets with source changes.
- Run architecture guards and the non-GUI Python test subset.
- Keep real Win7/WebView2 bundle smoke as the release evidence gate; local
  development success is not a substitute for that evidence.

## Verification And Acceptance

Phase 4 is complete when all of the following hold:

- The current T3 reference diff has no unclassified GUI behavior differences.
- Primary T3 surfaces have parity-focused tests and visual debug coverage.
- `App.jsx` is only a composition root and contains no Agent-specific policy.
- The renderer imports only frontend runtime, protocol, and UI modules.
- Base and specialized Agent fixtures render through the same client runtime.
- No renderer source contains forbidden C/C++/Clang/tool/workflow branches,
  except test-only fixture data and explicitly documented generic metadata.
- The GUI build passes on the existing offline-compatible toolchain and updates
  tracked static assets.
- No new runtime dependency requires a post-Windows-7 API, online service, or
  non-bundled executable.

## T3 Update Procedure

When `reference/t3code` changes:

1. Record the new commit, date, and subject in the parity ledger.
2. Diff only `apps/web`, applicable `packages/client-runtime`, and applicable
   `packages/contracts` paths.
3. Reclassify changes into UX, client runtime, protocol, or excluded
   infrastructure.
4. Port UX and state behavior using the current project toolchain.
5. Run the GUI and architecture gates before accepting the new baseline.

The project may intentionally lag T3 features that require cloud, remote,
mobile, Electron, or incompatible runtime infrastructure. Such omissions must
be recorded as explicit exclusions rather than silently implemented differently.
