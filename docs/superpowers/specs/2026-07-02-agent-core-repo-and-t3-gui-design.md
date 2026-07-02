# Agent Core Repository Split And T3 GUI Design

## Status

Approved for design capture on 2026-07-02.

This document records the target architecture for moving EmbedAgent from a
C/C++-first monorepo product shape toward a generic, packageable Agent Core
with scenario-specific workflow packages and a T3 Code-style GUI contract.

This is an architecture design, not an implementation patch plan. The project
is pre-release, so the design intentionally avoids preserving old internal
session, reducer, GUI, or workflow compatibility shapes when replacing them is
cleaner.

## Goals

- Make Agent Core describable and buildable without C/C++ workflow vocabulary.
- Support a future standalone `agent-core` repository.
- Keep C/C++ development as a first-party packaged scenario, not as Core's
  defining product shape.
- Allow different scenario applications to be assembled from the same Core,
  host, and GUI primitives: general assistant, embedded C engineering, Python
  development, HTML/frontend development, and later trusted internal scenarios.
- Make the GUI follow the T3 Code design model: shared contracts, client
  runtime reducers, backend-owned thread/activity truth, and reusable UI
  components that adapt to backend-declared capabilities.
- Fix permission and user-input interaction lifecycle by making interactions
  activity-ledger state, not raw transport request state.
- Preserve Windows 7, offline deployment, Python 3.8, small dependency surface,
  and no runtime dependency installation.

## Non-Goals

- No Docker, WSL, VS Code, online marketplace, public remote registry, runtime
  dependency installation, or mandatory network service.
- No compatibility bridge for obsolete internal session/timeline/GUI reducer
  shapes.
- No front-end hardcoding of C/C++ modes, tool names, workflow phases, or
  recipes.
- No public extension API promise for internal reducer or hook implementation
  details.
- No general multi-agent orchestration in Agent Core.

## Current Findings

The codebase has already moved in the right direction: `AgentKernel`,
`AgentLoop`, `AgentLifecycleJournal`, `AgentToolActionService`,
`AgentExtensionHost`, `CapabilityRegistry`, runtime reducers, and workflow
package manifests exist as internal boundaries. The remaining issue is product
shape, not a missing first extraction.

The current package metadata still frames the product as embedded C
development. `pyproject.toml` describes EmbedAgent as an offline-first coding
platform for Windows 7 embedded C application development.

The default hosted extension assembly still directly imports the C harness in
`src/embedagent/default_extensions.py`. This is acceptable as a product
composition point, but it must not live inside a future generic Core repo.

The GUI is not yet fully backend-declared:

- `webapp/src/workbench/commands.js` hardcodes the five current modes and a
  workflow command list.
- `webapp/src/styles.css` hardcodes mode-specific visual classes.
- `webapp/src/store.js` hardcodes C/C++ workflow tool labels such as
  `run_recipe`, `report_quality_v2`, `task_status`, and
  `record_failing_evidence`.
- `webapp/src/components/NoWorkspaceState.jsx` still says users should choose a
  local C/C++ workspace.
- `webapp/src/session-runtime/t3-timeline.js` contains tool-specific
  presentation shortcuts for `run_recipe`, `bash`, file tools, and related
  categories.

The GUI interaction path has a partial T3-style split but still keeps raw
transport request handling. Backend `session_event` messages are routed into
the activity transport, while raw `permission_request` and `user_input_request`
messages still trigger reload behavior in `socket-message-effects.js`. The
target should be stricter: raw requests may exist only as a low-level response
transport, not as timeline/composer state truth.

## Target Repository Model

### `agent-core`

The future standalone Core repository contains only generic runtime concepts:

- `AgentKernel`
- `AgentLoop`
- `AgentLifecycleJournal`
- `AgentToolActionService`
- `AgentExtensionHost`
- `AgentEventBus` / HookBus
- `SessionLog` and reducers
- `TurnSnapshot` and snapshot builder
- `CapabilityRegistry`
- `RuntimeConfigReducer`
- `CompactionStateReducer`
- `RecoveryStateReducer`
- `TurnExperienceReducer`
- `WorkflowPackageManifest`
- `ToolRuntime`
- `PermissionPolicy`
- context assembly and compaction primitives
- provider/model profile interfaces

Core must not import C/C++ harness modules, GUI modules, hosted HTTP routes, or
scenario-specific workflow packages.

### `agent-host`

The host package owns product integration around Core:

- session lifecycle facade
- workspace registry
- app bootstrap
- HTTP/WebSocket/RPC server adapters
- hosted command dispatch
- hosted interaction response bridge
- runtime discovery for bundled tools
- project extension loading policy
- default product composition
- offline bundle contract integration

Host can choose which workflow packages to install. Host can ship a default
scenario, but that default is product assembly, not Core behavior.

### Workflow Packages

Workflow packages are first-party or project-local scenario capabilities.

Examples:

- `workflow-general`
- `workflow-c-cpp`
- `workflow-embedded-c`
- `workflow-python`
- `workflow-html`

Each workflow package owns:

- package manifest
- mode definitions and labels
- workflow states
- prompt units
- tool declarations and registration
- active-tool policy by mode/workflow state
- resource scopes
- workflow projection
- renderer metadata for generic GUI display
- tests and validation recipes

The current `src/embedagent/harness` should become the first-party C/C++
workflow package. `TaskGraph`, phase progression, discipline profiles, recipe
tools, quality reporting, failing evidence, and task status belong there.

### `agent-gui`

The GUI becomes a reusable T3-style shell:

- It consumes shared contracts rather than Python-specific payload shapes.
- It keeps client runtime reducers separate from components.
- It renders backend-declared modes, commands, tools, resources, workflow
  summaries, and interaction prompts.
- It does not know whether the active scenario is C/C++, Python, HTML, or
  general.
- It can be bundled into several scenario applications unchanged.

## Protocol And Contract Model

Introduce a versioned Agent App Protocol package before physical repo splits.
This should be the contract between host and GUI.

Required contract families:

- app bootstrap: app identity, workspace registry, surfaces, settings, safe
  diagnostics
- capability snapshot: modes, commands, workflow packages, tools, resources,
  model profiles, renderer metadata
- thread shell snapshot: thread list rows, archived state, active session
  status, pending interaction flags
- thread detail snapshot: messages, activities, checkpoints or changed-file
  summaries, proposed plans, workflow projection, session state
- command dispatch: create thread, send turn, set mode, respond to approval,
  respond to user input, stop turn, reload resources, lifecycle operations
- event stream: snapshot plus ordered thread/app events with sequence numbers

The GUI must consume snapshots and events through pure reducers. Components
must not call backend-specific projection helpers or rebuild session history
from raw transport events.

## Interaction Lifecycle

Permission and user-input interactions become durable activity-ledger state.

Backend emits canonical activity kinds:

- `approval.requested`
- `approval.resolved`
- `approval.response.failed`
- `user-input.requested`
- `user-input.resolved`
- `user-input.response.failed`

Activity payloads include:

- `requestId`
- `turnId`
- request kind: `command`, `file-read`, or `file-change`
- display detail
- questions and options for user input
- stale/expired/conflict metadata when relevant

The GUI derives composer pending state from activities, following the T3
pattern:

- pending approvals are open `approval.requested` records without a matching
  `approval.resolved`
- pending user inputs are open `user-input.requested` records without a
  matching `user-input.resolved`
- stale response failures close local pending UI when the backend reports that
  callback state is no longer valid

Raw `permission_request` and `user_input_request` transport messages may remain
only as a blocking response channel if the host still needs them internally.
They must not create timeline rows, composer cards, or independent interaction
truth in the renderer.

Interaction responses are commands:

- `thread.approval.respond`
- `thread.user-input.respond`

The response command returns an acknowledgement and the event stream or
snapshot update closes the pending UI. Optimistic busy state is allowed, but
optimistic resolution is not the source of truth.

## GUI Dynamic Capability Rules

The GUI may ship static components, but all scenario-specific choices must come
from the backend capability contract.

Replace hardcoded mode and tool assumptions with backend metadata:

- mode id, label, description, icon key, color token, command id
- command id, label, group, shortcut, availability, dispatch shape
- tool presentation metadata: label, icon key, renderer key, permission kind,
  command preview fields, changed-file fields
- workflow package descriptor: package id, label, active state, summary fields
- empty-state copy and product scenario label

The GUI may include generic fallback renderers:

- command/tool row
- file-change row
- approval row
- user-input row
- workflow summary row
- changed-files summary
- review/result row
- system notice row

Scenario packages may only contribute renderer metadata and safe display
payloads. They must not require GUI source changes for ordinary new modes,
tools, commands, or workflow states.

## Data Flow

Target high-level flow:

```text
Workflow package(s)
  -> register capabilities, tools, prompt units, workflow projection
  -> Agent Core turn snapshot and reducers
  -> Host protocol projection
  -> Agent App Protocol snapshots/events
  -> GUI client-runtime reducers
  -> reusable T3-style components
```

Provider/tool execution flow:

```text
User turn command
  -> host command dispatcher
  -> AgentKernel turn frame
  -> TurnSnapshot
  -> provider request
  -> tool action service
  -> permission/user-input activity if blocked
  -> response command resumes same action pipeline
  -> tool result and workflow patch
  -> session log reducers
  -> thread detail event stream
```

No frontend path should own workflow truth, permission policy, tool activation,
extension loading, provider configuration, or history replay.

## Migration Program

### Phase 1: Contract First

Create the Agent App Protocol inside the current repo. Add schemas or typed
dataclasses for app bootstrap, capability snapshot, thread shell, thread
detail, activities, commands, and stream items.

Acceptance criteria:

- GUI can consume a protocol-shaped bootstrap without reaching into legacy
  payload fields.
- Current backend can project existing sessions into the protocol.
- Tests cover snapshot decode/normalization and event reduction.

### Phase 2: Interaction Ledger Cutover

Promote approval and user-input activity kinds as the only renderer truth.
Update backend session events, bootstrap history, and live events to emit
canonical activity records.

Acceptance criteria:

- Composer pending approval/input state is derived from activities only.
- Raw request messages do not create renderer state.
- Stale, expired, conflict, and resolved interactions are represented by
  activities and tested.

### Phase 3: GUI Capability Cutover

Remove hardcoded mode, command, tool, workflow, and C/C++ copy from the GUI.
Replace them with protocol capability metadata.

Acceptance criteria:

- A fake non-C workflow package can drive modes and tool labels without GUI
  code changes.
- Existing C/C++ product behavior is preserved through metadata.
- Mode colors and labels are data-driven.
- Tool row presentation prefers renderer metadata and falls back generically.

### Phase 4: Package Boundary Cutover

Move C/C++ harness ownership behind a first-party workflow package boundary
inside the current repo before physical extraction.

Acceptance criteria:

- Core modules import no C/C++ harness internals.
- Hosted product assembly installs the C/C++ workflow package explicitly.
- Bare Core tests run with no workflow package.
- C/C++ workflow package tests cover task graph, recipes, quality, projection,
  context reducers, and active-tool policy.

### Phase 5: Physical Repo Split

After the in-repo boundaries are stable, split packages into repositories or
publishable artifacts:

- `agent-core`
- `agent-host`
- `agent-gui`
- `workflow-c-cpp`
- optional scenario workflow packages
- offline bundle assembly repository or package

Acceptance criteria:

- `agent-core` test suite passes without GUI or C/C++ package.
- `workflow-c-cpp` consumes only public Core/Host package interfaces.
- GUI consumes only Agent App Protocol contracts.
- Offline bundle validation includes all selected package runtime assets.

## Testing Strategy

Core tests:

- bare Core with empty workflow package set
- turn snapshot immutability
- save-point and pending interaction resume behavior
- reducers from transcript/session log
- permission policy and path guards
- dynamic tool registration and active-tool visibility

Workflow package tests:

- C/C++ package manifest projection
- tool registration metadata
- active pack selection
- workflow projection
- context reducer registration
- recipe and task-status behavior

Host/protocol tests:

- app bootstrap projection
- thread shell/detail snapshots
- event stream ordering and sequence handling
- command receipts
- interaction response conflict/expiry handling

GUI tests:

- protocol snapshot normalization
- thread reducer event application
- pending approval derivation
- pending user-input derivation
- dynamic modes and commands
- generic tool row fallback
- C/C++ workflow metadata rendering without C-specific hardcoding

Bundle tests:

- selected scenario bundle contains every runtime-invoked binary
- clean Windows 7 / WebView2 smoke remains required before release claims
- scenario packages do not install dependencies at runtime

## Documentation Updates

After implementation, update the long-lived docs:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/frontend-protocol.md`
- `docs/tool-contracts.md`
- `docs/agent-harness-v2.md`
- `docs/pi-inspired-agent-core-blueprint.md`

The active docs should describe only the promoted architecture. Old internal
paths should be archived rather than kept as compatibility alternatives.

## Open Design Decisions

1. Whether the first protocol implementation should use Python dataclasses only
   or generate a JSON schema artifact for GUI tests.
2. Whether physical repo split should happen before or after the C/C++ workflow
   package has complete fake non-C scenario test coverage.
3. Whether `agent-host` and offline bundle assembly should be separate packages
   or one package until release validation stabilizes.
4. How much scenario package renderer metadata should be validated by Core
   versus by Host protocol projection.

The recommended default is conservative: finish in-repo contract and package
boundaries first, prove them with fake non-C workflow tests, then split repos.

## Spec Self-Review

- No compatibility-first path is proposed.
- Core is explicitly free of C/C++ and GUI imports.
- GUI behavior is driven by protocol metadata and activities.
- Interaction lifecycle has one renderer truth.
- Windows 7, offline deployment, Python 3.8, and no runtime dependency
  installation remain hard constraints.
- The migration is decomposed into verifiable phases rather than broad
  replacement work.
