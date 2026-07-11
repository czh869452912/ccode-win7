# Independent Agent Core And Adaptive GUI Design

## Status

Approved for design capture on 2026-07-11.

This design advances the repository beyond the completed in-repo dependency
extraction. The next milestone is a physically independent `embedagent-core`
distribution that can run a base agent without the hosted product, GUI, or
C/C++ workflow package. The default C/C++ product must be assembled from the
same Core through a separately delivered workflow package.

This design extends the direction recorded in
`2026-07-02-agent-core-repo-and-t3-gui-design.md`. It does not preserve
pre-release internal package, session, workflow, or GUI compatibility shapes.

## Decision Summary

Use three deliberately separate API layers:

1. A low-level functional runner owns the minimal replayable execution
   semantics.
2. An object facade provides the normal embeddable SDK experience.
3. A build-time composition layer freezes trusted components and exports base
   or specialized agents.

No single configuration object may span all three layers. Runtime state,
product composition metadata, GUI shell metadata, and export metadata remain
separate types.

The first milestone prioritizes independent Core delivery and C/C++ workflow
composition. GUI protocol separation follows after those runtime and packaging
boundaries are proven.

## Goals

- Publish and install `embedagent-core` without FastAPI, pywebview, GUI assets,
  hosted services, or C/C++ workflow modules.
- Provide a small stable Core API instead of exposing the current
  `QueryEngine` constructor as the SDK assembly surface.
- Preserve durable operation events, reducers, turn snapshots, compaction,
  recovery markers, permissions, and extension dispatch.
- Keep empty workflow state empty. Mode and workflow are optional capabilities,
  not unconditional Core concepts.
- Deliver the default C/C++ agent by composing an external first-party workflow
  package with Core and Host.
- Produce deterministic, auditable offline agent exports without runtime
  dependency installation or online discovery.
- Let one GUI shell consume base and specialized agents through versioned
  protocol projections rather than Python imports or workflow knowledge.
- Preserve Windows 7, Python 3.8, offline operation, and the default C/C++
  workflow throughout the migration.

## Non-Goals

- No online registry, marketplace, runtime package installation, or public
  remote extension discovery.
- No arbitrary frontend JavaScript plugins.
- No general dependency solver in the first composition milestone.
- No compatibility layer for old internal `QueryEngine`, application registry,
  workflow-state, or GUI protocol shapes.
- No Docker, WSL, VS Code, or mandatory network service.
- No general multi-agent orchestration in Core.

## Current Baseline And Residual Gaps

The source dependency direction is already substantially correct:

- `embedagent_core` does not import product, host, GUI, TUI, or C/C++ workflow
  modules.
- `AgentKernel`, `AgentLoop`, `AgentLifecycleJournal`,
  `AgentToolActionService`, `AgentExtensionHost`, reducers, snapshots, and
  capability read models exist.
- non-C profile applications can be injected into `InProcessAdapter`.
- GUI mode, tool, command, workflow, and application metadata is substantially
  backend-declared.

The remaining gaps are product-shape and public-contract gaps:

- one `embedagent` distribution still packages Core, Host, product, and GUI;
- GUI and server dependencies are unconditional project dependencies;
- `embedagent_core.__init__` does not expose a usable construction API;
- `QueryEngine` remains a large internal assembly and orchestration facade;
- Core and protocol paths still normalize missing workflow state to `chat`;
- the minimal `QueryEngine` permission default auto-approves;
- central application construction still owns built-in profile-kind branches;
- C/C++ composition still creates concrete runtime objects rather than
  contributing through one frozen composition root;
- GUI transport types are maintained separately in Python and JavaScript;
- GUI event, command, and renderer registries remain compile-time bounded.

## Alternatives Considered

### Object Facade Only

Expose `Agent.compose()`, `Agent.open()`, and `AgentSession.submit()` and hide
all current orchestration behind them.

This gives the best common-case SDK, but an object-only design can obscure the
replay boundary and can accumulate product composition concerns in a mutable
facade.

### Functional Runner Only

Expose one `run_agent(runtime, request)` function. Each call restores a trusted
session prefix, advances one input, persists events, and returns a read-only
view.

This makes replay, testing, and state ownership explicit, but it is awkward for
streaming observers, cancellation, steering, and long-lived hosted sessions.

### Build-Time Composition Only

Describe every provider, profile, workflow, tool, resource, host, and GUI as a
component in a manifest graph.

This gives deterministic specialized-agent exports, but using the manifest
graph as the runtime API would create a large service locator and make ordinary
embedding unnecessarily indirect.

### Chosen Hybrid

Use the functional runner as the deep runtime primitive, the object facade as
the stable Core SDK, and a frozen build-time catalog for product composition.
The layers exchange frozen typed values rather than sharing mutable managers or
configuration bags.

The approved object-facade candidate used the provisional name
`Agent.compose()`. The final API uses `Agent.create()` so that `compose` and
`compile` remain build-time composition terms and runtime construction cannot
be confused with product assembly.

## Target Distribution Model

### `embedagent-core`

Owns only generic agent runtime concepts:

- functional runner and object facade;
- session log contract and reducer-owned read models;
- agent loop, lifecycle, action, and snapshot semantics;
- provider, tool runtime, context, and storage ports;
- permission and workspace-path policy contracts;
- extension capability contracts and source-aware event dispatch;
- workflow package manifest as a non-executing read model;
- compaction, recovery, runtime configuration, and turn experience reducers.

It uses the Python 3.8 standard library and does not include concrete providers,
workspace tools, HTTP servers, GUI code, product branding, or scenario logic.

### `embedagent-host`

Owns concrete environment integrations:

- OpenAI-compatible provider adapter;
- workspace file and shell tools;
- JSONL session log and product stores;
- context assembly and local resource discovery;
- hosted command and interaction services;
- project extension loading policy;
- HTTP, WebSocket, CLI, and TUI hosting adapters;
- projection into the Agent App Protocol.

Host depends on Core public contracts. It does not own C/C++ workflow rules.

### `embedagent-workflow-cpp`

Owns all default C/C++ specialization:

- C/C++ profile and modes;
- discipline and phase rules;
- task graph internals and workflow projection;
- prompt units, packs, recipes, quality, evidence, and task status;
- C/C++ workspace detection and bundled tool asset declarations;
- the first-party workflow package manifest.

The package depends on Core public contracts. It does not import Host or GUI,
does not construct its own `ExtensionManager`, and does not install dependencies
at runtime.

### `embedagent-composition`

Owns build-time product composition:

- trusted component catalog registration and freezing;
- component dependency, conflict, API-version, and asset validation;
- deterministic component ordering;
- `AgentProductDefinition` compilation;
- `agent.json` and `agent.lock.json` generation;
- offline asset closure and export reports.

It is not a dependency of the base Core runtime.

### `embedagent-gui`

Owns the replaceable GUI shell and GUI-local services. It consumes the Agent App
Protocol and IDE service protocols. It does not import Core, Host, or workflow
Python modules.

Physical GUI distribution separation may land after the first runtime and
workflow packaging milestone, but this dependency direction is the target from
the start.

## Core Runtime API

### Functional Primitive

```python
def run_agent(
    runtime: "AgentRuntime",
    request: "AgentRequest",
    observer: Optional["AgentObserver"] = None,
    cancel: Optional["CancelToken"] = None,
) -> "AgentResult":
    ...
```

`AgentRuntime` is frozen before the first request and contains only runtime
ports and runtime policy:

```python
@dataclass(frozen=True)
class AgentRuntime:
    model: ModelClient
    tools: ToolRuntimePort
    session_log: SessionLogPort
    context: ContextAssemblerPort
    permissions: PermissionPolicy
    extensions: Tuple[AgentExtension, ...] = field(default_factory=tuple)
    policy: RuntimePolicy = field(default_factory=RuntimePolicy)
```

`AgentRequest.input` is a tagged `UserTurn` or `InteractionReply`. Permission,
user-input, and mode-switch continuation do not get separate runtime paths.

### Stable Object Facade

```python
class Agent(object):
    @classmethod
    def create(
        cls,
        runtime: AgentRuntime,
        definition: Optional[RuntimeDefinition] = None,
    ) -> "Agent":
        ...

    def open(self, session_id: str = "") -> "AgentSession":
        ...


class AgentSession(object):
    def submit(
        self,
        input_value: AgentInput,
        observer: Optional[AgentObserver] = None,
        cancel: Optional[CancelToken] = None,
    ) -> AgentResult:
        ...
```

The facade hides `QueryEngine`, `AgentKernel`, `AgentLoop`, lifecycle journals,
HookBus reducer semantics, trusted-prefix restore, snapshot creation, tool
activation, permission checks, compaction, recovery markers, and session
locking.

`RuntimeDefinition` contains runtime policy and extension declarations only. It
must not contain GUI descriptors, product branding, workspace registry state,
provider credentials, bundle assets, or export options.

## Composition API

```python
@dataclass(frozen=True)
class ComponentManifest:
    component_id: str
    kind: str
    version: str
    api_version: str
    requires: Tuple[str, ...] = field(default_factory=tuple)
    conflicts: Tuple[str, ...] = field(default_factory=tuple)
    permission_categories: Tuple[str, ...] = field(default_factory=tuple)
    runtime_assets: Tuple[str, ...] = field(default_factory=tuple)
    resource_scopes: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AgentProductDefinition:
    agent_id: str
    profile: ComponentRef
    providers: Tuple[ComponentRef, ...]
    workflows: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    tools: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    resources: Tuple[ComponentRef, ...] = field(default_factory=tuple)
    host: Optional[ComponentRef] = None
    gui: Optional[ComponentRef] = None


def compile_agent(
    definition: AgentProductDefinition,
    catalog: FrozenComponentCatalog,
) -> CompiledAgentSpec:
    ...
```

Manifest records are non-executing. They cannot contain arbitrary Python
builder paths, activate tools, grant permissions, load project code, or select
restore policy. Executable factories are registered by the trusted offline
catalog before it is frozen.

The first implementation supports only fixed wheel-set and Win7 portable-bundle
exports. It does not solve arbitrary component versions or discover runtime
entry points.

## Build-Time Data Flow

```text
Trusted component factories
  -> ComponentCatalog.register()
  -> ComponentCatalog.freeze()
  -> compile AgentProductDefinition
  -> validate ids, dependencies, conflicts, permissions, namespaces, assets
  -> CompiledAgentSpec
  -> agent.json + agent.lock.json + export report
  -> wheel set or portable bundle
```

The lock contains exact component versions, factory identities, file hashes,
declared runtime assets, and deterministic ordering. It must not contain API
keys, tokens, provider request bodies, prompts, source content, or raw tool
outputs.

Distribution components and workspace extensions are separate trust classes:

- distribution components are selected at build time and frozen into the lock;
- workspace resources remain data and can be reloaded;
- workspace Python extensions remain disabled-by-default manifest-gated code;
- workspace code cannot change the product profile or provider, replace built-in
  tools, or add undeclared bundle assets.

## Runtime Data Flow

```text
CompiledAgentSpec
  -> Host binds model, tools, log, context, permissions, secrets
  -> frozen AgentRuntime
  -> Agent.open(session_id)
  -> acquire session lease
  -> reduce trusted SessionLog prefix into SessionView
  -> freeze TurnSnapshot
  -> provider request and permission-gated tool pipeline
  -> append operation, message, tool, workflow, and save-point events
  -> reduce final SessionView
  -> release session lease
```

The provider consumes only the frozen `TurnSnapshot`. Configuration, resource,
and extension changes become visible at the next save point. The first
milestone prohibits workflow package replacement while a session is active.

The SessionLog is durable truth. `transcript.jsonl` is one `SessionLogPort`
adapter, not the public abstraction name. Live mutable `Session` state may
remain temporarily inside the runtime, but public results and restore state are
reducer-produced read models.

## Workflow And Mode Semantics

- Missing workflow state remains empty end to end.
- All Core `chat` fallbacks are deleted.
- Mode is optional and comes from runtime policy or a workflow/profile
  contribution.
- Workflow packages own workflow state namespaces and generic frontend
  projections.
- Only one selected primary workflow projection may populate the frontend
  `workflow` payload in the first milestone.
- Workflow package manifests describe capabilities but do not activate them.
- Active tool names still flow through the single extension host and runtime
  schema projection boundary.

## Concurrency And Save Points

- One `AgentSession` rejects overlapping `submit()` calls.
- `SessionLogPort` provides an atomic per-session lease for separate facade or
  process callers.
- Lease conflicts fail explicitly and do not append events.
- Provider requests freeze messages, schemas, model profile, runtime metadata,
  workflow state, and safe capability summaries.
- Runtime changes are staged until a save point. They never mutate an in-flight
  request.
- Non-idempotent tool calls are not retried automatically after interruption.

## Permission And Security Defaults

- Standalone Core defaults to ask or deny, never auto-approve.
- Component permission declarations are requirements, not grants.
- Runtime permission decisions remain owned by `PermissionPolicy`.
- Workspace path guards remain Core policy with Host-provided roots.
- Tool registration rejects replacement and invalid permission metadata.
- Provider credentials are resolved at runtime through a secret port and are
  excluded from locks, snapshots, logs, and diagnostics.
- GUI extension remains declarative and renderer-whitelisted. No workflow
  package can deliver executable frontend code.

## Failure Semantics

### Composition Failures

Unknown component ids, API-version mismatch, cycles, conflicts, duplicate tool
names, workflow namespace collision, undeclared assets, and invalid manifests
fail before an export is created. Partial output is removed or never promoted.

### Binding Failures

Missing required model, tool runtime, session log, context assembler, or
permission policy prevents Agent creation. Credentials are validated without
including secret values in diagnostics.

### Runtime Failures

- ordinary tool and build failures become observations for the next model turn;
- permission rejection returns a structured observation or pending state;
- trusted built-in reducer failure is fail closed and records safe diagnostics;
- project extension failure disables or isolates that capability without
  breaking the default offline agent;
- provider/context failure follows existing retry and compaction policy;
- unexpected process interruption leaves explicit unfinished operations;
- restore marks unfinished operations interrupted and stops at the trusted log
  prefix;
- corrupt log tails produce safe recovery diagnostics and do not trigger
  automatic non-idempotent tool replay.

## GUI Protocol Direction

The GUI phase separates four contracts:

- Agent Session Protocol for threads, activities, turns, interactions, and
  cancellation;
- Capability Protocol for modes, tools, commands, workflows, applications, and
  safe renderer hints;
- IDE Service Protocol for files, terminal, source control, preview, and local
  app settings;
- App Shell Protocol for branding, surfaces, commands, chrome, and keybindings.

Python and JavaScript consume one versioned schema artifact. Transport decode
validates typed envelopes, sequence, event kind, and payload shape before
updating client state.

The shared GUI must support a base agent, the default C/C++ agent, and a non-C
test workflow without React source changes. Unknown tools and activities use a
generic renderer. Unknown surfaces are limited to safe declarative panels such
as Markdown, property lists, tables, trees, forms, progress, and diagnostics.

## Migration Program

### Phase 0: Freeze Architecture Guards

Add target import-graph, public API, empty-workflow, permission-default,
distribution-content, and protocol-contract tests before moving modules.

Exit criteria:

- current architecture, fast Python, and GUI tests pass;
- expected residual violations are recorded as explicit failing target tests;
- no test encodes old internal compatibility as a requirement.

### Phase 1: Establish The Core Public API

Add the functional runner, object facade, frozen runtime types, typed inputs,
read-only results, and `SessionLogPort`. Route current hosted execution through
the facade.

Delete Core `chat` defaults, make mode/workflow optional, change standalone
permission defaults to ask/deny, and prevent duplicate extension managers.

Exit criteria:

- fake model, memory log, minimal tools, and default context can run a base
  agent directly from `embedagent_core`;
- multi-turn execution, tools, pending interactions, cancellation, and restore
  pass through the public facade;
- Host no longer constructs `QueryEngine` as its public integration contract.

### Phase 2: Split Physical Distributions

Create separately buildable Core, Host, C/C++ workflow, Composition, and product
distribution units. Keep one development workspace and exact offline lock
inputs while producing separate wheels.

Exit criteria:

- each wheel builds and installs in an isolated Python 3.8 environment;
- Core metadata has no GUI/server dependency;
- importing and running Core does not load Host, GUI, or C/C++ modules;
- the development test commands remain usable from the repository root.

### Phase 3: Move C/C++ Specialization Out

Move all C/C++ profile, application, workflow, task, recipe, tool, reducer, and
workspace-detection behavior into the C/C++ distribution. Replace central
profile-kind branches and executable builder paths with trusted catalog
registration.

Exit criteria:

- a base agent runs without the C/C++ wheel installed;
- the C/C++ product preserves current modes, tools, tasks, recipes, quality,
  and evidence behavior;
- Core, Host, and GUI source contain no imports of the C/C++ package;
- only product composition selects the C/C++ package as default.

### Phase 4: Freeze Composition And Export

Implement the minimal frozen catalog, deterministic compilation, lock files,
asset closure, and two export targets: base wheel set and C/C++ Win7 portable
bundle.

Exit criteria:

- identical inputs produce identical lock records, hashes, component order, and
  asset lists;
- conflicting tools, missing assets, undeclared binaries, and incompatible API
  versions fail before export promotion;
- export never accesses an online registry or installs dependencies at runtime.

Phases 1 through 4 complete the first milestone.

### Phase 5: Separate GUI Protocols

Split agent session, capability, IDE service, and app-shell contracts. Generate
or validate one shared schema at Python and JavaScript boundaries. Replace
remaining fixed workflow assumptions with safe declared projections.

Exit criteria:

- one unchanged GUI connects to base, C/C++, and non-C test agents;
- missing workflow and mode remain empty;
- no C/C++ copy or behavior appears for the base agent;
- unknown tool/activity values degrade through generic renderers;
- unsupported dynamic surfaces stay hidden rather than executing code.

### Phase 6: Delete Old Paths And Validate Delivery

Delete the old mixed `CoreInterface`, central profile-kind construction,
executable builder-path composition, duplicate manager/catalog paths, workflow
fallbacks, and compatibility serializers.

Exit criteria:

- architecture guards, full Python tests, lint, GUI tests, and GUI build pass;
- all wheels pass isolated install smoke tests;
- base and C/C++ export smoke tests pass with bundle-local assets;
- clean Windows 7 and WebView2 109 smoke evidence is recorded before release
  claims.

## Test Matrix

### Core Contract Tests

- base agent construction from public imports;
- empty workflow and mode behavior;
- ask/deny permission default;
- multi-turn execution and streaming observer ordering;
- tool success, diagnostic failure, interruption, and cancellation;
- pending interaction creation and unified reply resumption;
- trusted-prefix restore and corrupt-tail recovery;
- unfinished operation interruption;
- same-session lease conflict;
- snapshot immutability across save-point changes.

### Package Tests

- wheel contents and dependency metadata;
- isolated Python 3.8 installation;
- import poisoning that fails if Core loads Host, GUI, or C/C++;
- base environment without the C/C++ wheel;
- C/C++ package import without Host or GUI;
- public API export stability.

### Composition Tests

- manifest validation and API version checks;
- dependency cycle and conflict diagnostics;
- duplicate tool and workflow namespace rejection;
- deterministic ordering and lock generation;
- secret-field exclusion;
- offline asset closure against `offline-runtime-contract.json`;
- partial export cleanup.

### Specialized Agent Tests

- base agent has no C/C++ modes, tools, prompts, tasks, or assets;
- C/C++ agent preserves current workflow behavior;
- a non-C workflow package uses the same capability boundary;
- no workflow package creates a separate manager or tool catalog.

### GUI And Protocol Tests

- schema decode and structured diagnostics;
- ordered sequence and reconnect/bootstrap recovery;
- base, C/C++, and non-C capability projections;
- generic unknown tool and activity rendering;
- safe declarative surface rendering;
- absence of default workflow/mode/product copy;
- GUI `npm test`, production build, and responsive browser smoke.

### Delivery Tests

- base wheel-set smoke without GUI or C/C++ assets;
- C/C++ portable bundle smoke using bundle-local Python, MinGit, ripgrep,
  Ctags, and Clang;
- no system tool fallback in the C smoke path;
- clean Windows 7 and WebView2 109 windowed startup and workflow smoke.

## Acceptance Criteria

The architecture program is complete when all of the following are true:

- `embedagent-core` installs and runs independently on Python 3.8;
- `from embedagent_core import Agent` is the supported SDK entry point;
- Core has no GUI/server dependencies and no C/C++ vocabulary or imports;
- empty workflow state stays empty through runtime, protocol, and GUI;
- standalone permission defaults fail closed;
- base and C/C++ agents are separate deterministic product definitions;
- the C/C++ workflow package uses the same frozen capability boundary as other
  trusted workflow packages;
- a specialized agent export is reproducible from `agent.json`, lock metadata,
  wheels, and declared offline assets;
- one GUI shell consumes base, C/C++, and non-C agents without source changes;
- old mixed package, application, workflow fallback, and protocol paths are
  deleted;
- real Win7/WebView2 and C/C++ bundle evidence exists before release claims.

## Documentation Updates

Each promoted phase updates the active source-of-truth documents in the same
change:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/pi-inspired-agent-core-blueprint.md`
- `docs/frontend-protocol.md`
- `docs/tool-contracts.md`
- `docs/agent-harness-v2.md`
- packaging and offline deployment documentation

Completed slice plans move to the archive after durable conclusions are merged
into the active documents.

## Decision Record

The approved interface decision is the hybrid architecture described here:

- functional runner for minimal execution semantics;
- object facade for the public Core SDK;
- frozen build-time catalog for specialized agent composition and export.

This document is the durable decision record because `.gsd/` is project-ignored
runtime state and no active GSD slice context exists.
