# Overall Solution Architecture

> 状态：`active`
> 类型：`architecture`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-09`

## Purpose

This document defines current cross-layer ownership and execution invariants for EmbedAgent. Read it when a change crosses distribution, Core/Host, application, frontend, or delivery boundaries. Use the domain authorities linked below for implementation detail.

The repository contains three explicit strata: a reusable workflow-neutral Agent Platform, replaceable upper-layer applications, and the EmbedAgent product composition. EmbedAgent selects the Clang-centered C/C++ application by default and launches registered CLI/TUI/GUI shells. Windows 7, Python 3.8, and a self-contained offline bundle are mandatory.

This document does not inventory source files, record completed phases, track progress, or describe individual GUI controllers.

## Distribution Topology

The uv workspace produces exactly six Python distributions:

| Distribution | Import package | Owner | Project dependencies |
|---|---|---|---|
| `embedagent-core` | `embedagent_core` | Public SDK and workflow-neutral runtime policy | none |
| `embedagent-protocol` | `embedagent_protocol` | Stdlib-only JSON-safe wire DTOs | none |
| `embedagent-host` | `embedagent_host` | Generic providers, tools, stores, context, and hosted sessions | exact-matched Core and Protocol |
| `embedagent-composition` | `embedagent_composition` | Dependency-free build-time definition/compiler/export contracts | none |
| `embedagent-workflow-cpp` | `embedagent_workflow_cpp` | Default C/C++ workflow package | exact-matched Core |
| `embedagent` | `embedagent` | Product bootstrap and CLI/TUI/GUI shells | all five lower distributions |

```text
embedagent-core -----------> embedagent-host ---------\
       |                           ^                   \
       +----> embedagent-workflow-cpp                   > embedagent
embedagent-protocol -------> embedagent-host ---------/
embedagent-composition ------------------------------/
```

Core never imports Protocol, Host, the product, GUI, or workflow packages. Protocol and Composition remain independent leaves. The C/C++ workflow depends only on Core. Host never imports `embedagent`; product bootstrap injects product registries, policies, runtime discovery, and the selected extension manager into Host.

## Official Execution Spine

A frontend submits a user turn or interaction reply through the product adapter. The supported path is:

```text
CLI / TUI / GUI
  -> product adapter and hosted services
  -> AgentSession
  -> SessionTransaction
  -> SessionJournal -> SessionLogPort -> SessionReducer
  -> AgentKernel -> AgentLoop
  -> AgentToolActionService -> AgentExtensionHost -> ToolRuntime
  -> durable stores and frozen projections
```

`Agent` / `AgentSession` are the public standalone Core SDK; `run_agent` is the lower-level execution primitive. `AgentSession` is the durable transaction handle. Internal `SessionTransaction` owns one leased restore-dispatch-project boundary, not tool execution or a second state machine.

`SessionJournal` preflights canonical event intents and appends them through `SessionLogPort` before `SessionReducer` applies the same event family to live state. Restore folds the same reducer. No other component writes live session state.

`AgentKernel` plans only private context, provider, and tool effect families. `AgentLoop` commits a kernel step before executing the next effect, then resumes with the observation. `AgentToolActionService` owns non-model action policy: active-tool checks, extension pre/post hooks, permission decisions, write-path guards, runtime dispatch, interaction suspension/resume, and workflow-patch capture. `ProgressGuard` detects no-progress/runaway behavior from evidence fingerprints without treating ordinary build or test failures as terminal.

Core runtime dependencies enter through focused ports: `ContextAssemblerPort`, `SessionProjectionPort`, `SessionRestorePolicyPort`, and `ToolRuntimePort`, plus permission and persistence collaborators. A general runtime service bag or callback bag is not part of the architecture.

## Session And Protocol Truth

`Session` and `session.turns` are the only live structured session truth. `transcript.jsonl` is the hosted adapter for `SessionLogPort` and the only durable hosted session-history ledger. `SessionHistoryAssembler` is the only frontend history serializer. Session activation uses `GET /api/sessions/{id}/bootstrap`; app bootstrap supplies shell metadata only.

Host creates one `SessionEventEnvelope` for every live session event with schema version, event id, session id, sequence, kind, timestamp, and JSON-safe payload. Product adapters, TUI, and GUI backends forward that envelope unchanged. Renderer activity enters through one `session_event` branch and applies sequence, duplicate, and gap handling; frontends do not translate event families or invent workflow/session defaults.

`HostedSessionController` is the supported non-root Core/Host boundary for trusted continuation and inspection. It exposes frozen hosted projections. Host does not receive mutable Core `Session`, call private `AgentSession` members, or own restore.

Transcript-backed runtime-configuration, compaction, recovery, and turn-experience reducers are read models. They never become alternate history, select context, activate tools, retry effects, decide permissions, or drive loop continuation.

## Extension, Workflow, Tool, And Permission Ownership

`ExtensionManager` is the shared in-process capability boundary for workflow packages, prompt/context hooks, tool hooks, local resources, dynamic tools, diagnostics, and manifest-gated project extensions. An extension participates only through declared `ExtensionCapability` records. Source-aware internal hook dispatch runs through `AgentEventBus`; `AgentExtensionHost` keeps direct extension-manager calls out of runtime owners.

The bundled `CHarnessWorkflowExtension` owns default C/C++ workflow registration, packs, prompts, recipes, task state, and `WorkflowPackageManifest`. Product composition selects and injects it; Core does not import or construct it. `Session.workflow_state["workflow"]` is the generic frontend projection. C/C++ `TaskGraph` remains workflow-owned and is exposed through `task_status` and session task snapshots.

`ToolRuntime` is the registration and execution catalog. `ToolRuntime.schemas_for(...)` projects model-visible schemas from explicit active tool names computed by the shared extension boundary. Mode contracts remain workflow-neutral. Catalog metadata owns permission category, presentation hints, changed-path hints, and read-model invalidations; Core policies and renderers do not maintain parallel tool-name taxonomies.

Permission and write-path authorization are independent. Standalone callers supply `AgentPorts.permissions`. Default `PermissionPolicy()` allows read and asks for workspace write, Git write, shell/toolchain execution, network, telemetry, and other unless a rule overrides it. `DenyWritePathPolicy` separately decides whether a target path is writable; a permission allow is never proof that the path is safe.

Workspace skills, prompts, and recipes are reloadable data resources. Enabled project-local Python extensions are separately loaded from workspace-bound manifests, declare permissions, install no dependencies, and cannot replace built-ins. Optional intranet providers, Git operations, or telemetry sinks stay explicit, disableable, permission-checked adapters outside Core.

## Host, Product, And Frontend Composition

Host owns generic concrete runtime services and managed-session projections. Platform protocol owns the registrable CLI/TUI/GUI contracts and shell behavior; those implementations currently ship in the product distribution. Product owns configuration/bootstrap, the default application catalog, product policies, shell selection, and offline assets. The product may compose all lower distributions; lower distributions never call back into product namespaces.

Frontend behavior is product-compiled and backend-declared through protocol DTOs and capability projections. GUI and TUI consume the same `ShellDescriptor`; the stable core is session navigation, one continuous timeline, composer/modes/commands, blocking interactions, and status. Terminal, source control, preview, file browser, and dedicated diff views are optional registered contributions and never become permanent layout or session truth.

Shells may render modes, commands, surfaces, thread actions, tool presentation, and `SessionSnapshot.workflow_state["workflow"]`, but they do not own activation, permission, restore, extension loading, session history, or workflow policy. Protocol and Host do not flatten C/C++ phase/task semantics. Missing declarations remain missing rather than being synthesized from product-specific defaults.

## Offline Runtime And Release Evidence

Runtime must work on a clean Windows 7 SP1 x64 machine without network or preinstalled developer tools. The bundle carries Python 3.8 embeddable, vendored dependencies, MinGit/Bash, ripgrep, Universal Ctags, LLVM/Clang children, Fixed Version WebView2 109, and every invoked binary. `scripts/offline-runtime-contract.json` is the single contract for runtime assets and release gates.

The six project wheels are built, checked, and smoke-tested before wheel-only offline staging. Product files live under `app/embedagent`; lower distributions live under `runtime/site-packages`. Runtime network resolution, editable links, or a duplicate product package are defects.

Repository status may reach `TARGET_READY`, but `publishable=false` remains until hash-bound evidence from a clean Windows 7 target validates windowed GUI startup, WebView2 loading, and bundle-local C smoke. Local tests and hosted Windows CI do not replace target evidence.

## Pre-Release Change Rule

There is no production internal state to preserve. When an internal session, timeline, reducer, hook, registry, adapter, or workflow shape conflicts with the current boundary, delete or replace it rather than adding compatibility facades. This deletion-oriented rule never weakens Windows 7, offline, Python 3.8, C/C++, public SDK, protocol, or release evidence obligations.

## Detailed Authorities

| Change area | Read next |
|---|---|
| Agent SDK, kernel, loop, and ports | `docs/platform/agent-core.md` |
| Transaction, transcript, restore, and projections | `docs/platform/session-runtime.md` |
| C/C++ workflow and task model | `docs/applications/cpp-workflow.md` |
| Tool registration and execution | `docs/platform/tools-and-extensions.md`, `docs/platform/tool-contracts.md` |
| Permissions and context | `docs/platform/permissions-and-context.md`, `docs/platform/permission-model.md` |
| Protocol and UI shells | `docs/platform/protocol.md`, `docs/platform/frontend-protocol.md` |
| GUI/TUI implementations | `docs/platform/frontend-gui.md`, `docs/platform/frontend-tui.md` |
| Offline packaging and acceptance | `docs/product/packaging-and-deployment.md`, `docs/guides/win7-release-runbook.md` |
| Long-term minimal-Core direction | `docs/platform/agent-platform-blueprint.md` |

## Verification And Change Triggers

Run the architecture guard pair, full Python partition, and lint for cross-boundary changes:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run python scripts/test-suite.py full
uv run --locked python scripts/lint.py
```

Run `npm test` and `npm run build` from the webapp for frontend source changes. Run the six-distribution build/check/smoke pipeline for distribution changes and the release pipeline for packaging changes. Update this document only when cross-layer ownership, dependency direction, execution spine, durable truth, or release evidence boundaries change; update the owning domain authority for local mechanics.
