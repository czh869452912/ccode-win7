# AGENTS.md

## Purpose

This file is the project constitution for future agent and contributor work.

It exists to keep implementation and documentation aligned with the current product baseline:

- Windows 7 compatibility is mandatory.
- Offline deployment is mandatory.
- Agent Core is the product core; UI shells and workflow extensions are replaceable.
- The first-class target workflow is C/C++ application development with a Clang-centered toolchain.
- The next architecture program learns Pi's functional design and architecture philosophy by moving toward a minimal, extensible, self-extensible Agent Core without weakening the offline, Windows 7, Python 3.8, or C/C++ constraints.

## Quick Commands

These are the exact commands to use — copy-paste directly.

```bash
# Install dev environment
uv sync

# Run tests (fast subset — excludes GUI and slow integration tests)
uv run pytest tests/ -m "not slow and not gui" -v

# Run harness component tests only (task_graph, phase_engine, mode_runner)
uv run pytest tests/ -m harness -v

# Run all tests
uv run pytest tests/ -v

# Check lint (read-only)
uv run --locked python scripts/lint.py

# Auto-fix lint
uv run --locked python scripts/lint.py --fix

# Full local CI equivalent
make ci
```

## Pre-Merge Architecture Gate

Before merging GUI, Agent Core, permission, extension, workflow-package, or
frontend-protocol changes, run this gate from the repository root:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

Run the GUI gate from `src/embedagent/frontend/gui/webapp`:

```bash
npm test
npm run build
```

`npm run build` is required whenever webapp source changes, and the generated
GUI static assets under `src/embedagent/frontend/gui/static/` must be committed
with the source change.

Win7/offline delivery claims require real bundle smoke evidence on the
target-style bundle. Local development tests do not replace clean
Win7/WebView2 bundle smoke results.

**Constraints (always enforce)**:
- Python **3.8.x strictly** — never use 3.9+ syntax (no walrus operator `:=`, no `match`, no `dict | dict`)
- Never import modules absent from `pyproject.toml` dependencies
- Never modify `uv.lock` manually
- Never commit `config/config.json` (contains `api_key`)
- Test files belong in `tests/` — never in `src/`

## Read First

Before non-trivial work, read in this order:

1. `README.md`
2. `docs/overall-solution-architecture.md`
3. `docs/implementation-roadmap.md`

Use `docs/archive/` and `analysis/` as historical/reference material only.

## Hard Constraints

- Do not introduce runtime dependencies on Docker, WSL, VS Code, or external online services.
- Keep runtime compatibility at Python `>=3.8,<3.9`.
- Do not use Python 3.9+/3.10+ syntax features.
- Prefer standard library plus a very small dependency surface.
- The offline bundle must include every runtime tool it invokes.

Required bundled runtime assets include:

- Python 3.8 embeddable distribution
- vendored Python third-party packages
- MinGit portable
- ripgrep
- Universal Ctags
- Clang toolchain binaries needed by runtime flows
- any other binary invoked by the product at runtime

If a clean Windows 7 machine cannot unpack and run the bundle without preinstalled tools, it is a defect.

Offline deployment means the base product can start, run, and execute the default C/C++ workflow with no network. Optional intranet Git, custom-service, provider, or telemetry integrations may exist only when explicitly configured and trusted; they must remain disableable, failure-tolerant, manifest/config gated, and outside Agent Core. A missing or unreachable network service must not break default offline operation.

## Official Product Vocabulary

The repository now has one official architecture vocabulary.

### Next Architecture Direction

The current baseline remains authoritative. `docs/pi-inspired-agent-core-blueprint.md` is the long-term target blueprint for making Agent Core more Pi-like in both function and philosophy: smaller kernel, durable session-log reducers, source-aware hooks, explicit turn snapshots, replayable runtime configuration, structured compaction state, recovery markers, capability read models, replaceable workflow packages, local self-extension, and optional enterprise adapters that do not thicken Core.

The project is still pre-release and has no production user state to preserve. `docs/pre-release-architecture-debt-audit.md` records the closed pre-release debt cleanup baseline and remains the deletion-oriented guardrail: do not add compatibility scaffolding for old internal session, timeline, GUI reducer, or extension-hook shapes when a slice can delete or replace them. Forward compatibility for pre-release internal state is not a goal; preserving Windows 7, offline deployment, Python 3.8, and the default C/C++ workflow remains mandatory.

`Agent` / `AgentSession` are the public standalone Core SDK. `run_agent` is the
low-level execution primitive, while `QueryEngine` is internal implementation
and must not be exposed as the Host or third-party integration facade.
`SessionLogPort` is the durable log contract; the hosted product's
`transcript.jsonl` store is one adapter rather than the public abstraction.
Standalone Core preserves missing mode and workflow values as empty and
defaults permissions to ask or deny, never auto-approve. Hosted product
composition may explicitly select its own initial mode/workflow policy.

Do not treat blueprint target terms such as public `HookBus` as implemented public APIs until a specific implementation slice lands and updates the source-of-truth docs. `AgentEventBus` is now the internal source-aware event/reducer boundary for public extension hook dispatch; it is not a public extension API. `AgentLifecycleJournal`, `AgentKernel`, `AgentLoop`, `AgentLoopContinuationPolicy`, `ProgressGuard`, `TurnSnapshot`, `CapabilityRegistry`, `RuntimeConfigReducer`, `WorkflowPackageManifest`, `CompactionStateReducer`, `RecoveryStateReducer`, and `TurnExperienceReducer` are implemented internal Agent Core boundaries/read models, not public extension APIs. The bundled default C/C++ workflow package now owns its workflow tool registration, metadata, packs, and read-only package manifest behind `CHarnessWorkflowExtension`; the obsolete `embedagent.tooling.packs` compatibility re-export has been removed, so C/C++ workflow pack truth lives only in `embedagent.workflow_packages.c_cpp.packs`. Core singleton-like access must use explicit accessors (`get_mode_registry()`, `get_command_sanitizer()`, `get_inprocess_adapter()`); removed registry, sanitizer, and adapter private aliases must not be reintroduced. Local self-extension authoring is available through `SelfExtensionAuthoringService` and `author_local_capability`; repo-side offline bundle validation and release-gate metadata are contract-backed through `scripts/offline-runtime-contract.json`, including bundle-local C smoke validation through `validate-cpp-smoke.py`; near-term work must keep the default C/C++ workflow runnable while deleting stale internal compatibility layers and recording real Win7/WebView2 bundle smoke evidence before release claims. Future intranet Git, custom service, provider, or telemetry work must follow Pi's adapter style rather than copying Pi's full openness: Core emits safe events/read models and enforces capability/permission boundaries, while networked behavior lives in optional hosted extensions, providers, workflow packages, or passive telemetry sinks.

### Modes

Official first-class modes are:

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

`code` is no longer a first-class mode.

Mode registry access must go through `get_mode_registry()` / `initialize_modes()`.
Do not reintroduce module-level mode-registry proxy aliases or make mode helpers
depend on mutable compatibility aliases.

### Harness

Official C/C++ execution semantics are provided by the default built-in harness workflow extension:

- `mode`
- `discipline_profile`
- `execution_phase`
- `TaskGraph`

Agent Core must route harness-specific prompt injection, task initialization, and workflow tool handling through the extension boundary instead of importing harness classes directly.

Local offline self-extension is an official architecture capability, limited to workspace file resources and manifest-gated project-local Python extensions. Public remote registries, online extension installs, runtime dependency installation, plugin marketplaces, built-in tool replacement, and general multi-agent orchestration remain out of scope. Organization-local catalogs, intranet Git sources, custom service providers, and telemetry sinks may be considered only as trusted/admin-provisioned optional capabilities outside Agent Core; they must not grant execution rights, install dependencies at runtime, or become required for offline operation.

`InProcessAdapter` owns one hosted `Agent` runtime and its shared
`ExtensionManager`. Every `ManagedSession` stores an `AgentSession` opened from
that runtime. Frontend tool catalog visibility must use the same manager instead
of a separate adapter-only harness extension chain. `InProcessAdapter` must not
import or construct `QueryEngine`.

`ExtensionManager` is also the shared in-process capability boundary for prompt/context hooks, tool-call and tool-result hooks, resource discovery contracts, dynamic in-process tool registration, extension diagnostics, and manifest-gated project-local Python extensions. Extensions participate only by exposing `extension_capabilities()` records built from `ExtensionCapability`; method-name hooks such as `context`, `register_tools`, `allowed_tool_names`, or `handle_tool_call` are ignored unless explicitly declared in that capability list. Its hook internals dispatch through `AgentEventBus` with source metadata, observer/reducer separation, event-specific merge/stop semantics, and diagnostics; do not add new extension hook merge semantics outside that bus. Workspace-local file resources under `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` are discoverable and reloadable as file resources only. Skills support Agent Skills-style frontmatter and visible skills are summarized through a single lightweight local skill listing prompt unit. Skill bodies expand only through `/skill:<name> [args]`; prompt bodies expand only through `/prompt:<name-or-path> [args]`. Both remain Markdown/resource loading, not code execution. `author_local_capability` may generate those resources and disabled extension skeletons, but it must not reload resources, load Python extension code, or stamp generated recipe JSON with default C/C++ workflow tool names. Project-local Python extensions are loaded only from enabled `.embedagent/extensions/<name>/extension.json` manifests with workspace-bound `extension.py` entrypoints, declared permissions, explicit `api.ExtensionCapability` registrations for any hooks/tools they expose, no dependency installation, no remote registry, and no built-in tool replacement.

`AgentExtensionHost` is the QueryEngine-side extension dispatch boundary. `QueryEngine` must not scatter direct `ExtensionManager` hook calls for prompt injection, context patching, dynamic tool registration, active-tool schema projection, tool-call hooks, tool-result hooks, or extension-owned tool handling.
`WorkflowPatch` from tool-result hooks carries only the generic `workflow`
read model plus safe `metadata`; do not reintroduce extension
`legacy_projection` or parallel workflow projection fields.

Workflow-package prompt units appended by `QueryEngine` must use the generic `workflow_prompt` system message kind. The old harness-specific prompt kind is not active and must not be used for workflow prompt injection or deduplication.

`AgentLifecycleJournal` owns durable lifecycle event emission, transition save points, pending interaction lifecycle operation events, context operation payload helpers, and workflow-patch persistence helpers. `AgentKernel` owns turn frames plus pending interaction creation/resolution boundaries. `AgentToolActionService` owns non-LLM tool action execution behind the internal `QueryEngine`: active-tool checks, extension pre/post hooks, `PermissionPolicy` evaluation, path write guards, runtime dispatch, extension-owned tool calls, interactive action handling, resumed action execution, and workflow-patch capture after tool-result hooks. `AgentLoop` owns Pi-style open turn-loop continuation behind `AgentSession`, including agent steps, provider/context attempts, active schema requests through `AgentExtensionHost`, compact retry, guard-stop, abort, and explicit loop safety-limit compatibility transitions. `ProgressGuard` owns evidence-fingerprint based no-progress/runaway detection over action plus observation pairs; it must not collapse distinct files, commands, diagnostics, or successful changes into a generic repeated-tool stop. Ordinary command/build/test failures are diagnostic tool results for the next model turn and must not trigger hard loop termination merely because they are non-zero or non-retryable; guard-stop is for no-progress/runaway protection. `max_turns` remains accepted only as an explicit runtime/test safety fuse; persistent JSON configuration must not set a product loop ceiling, and omitted values mean no fixed turn-count ceiling. `QueryEngine` remains an internal transcript/session mutation owner; do not reintroduce private loop, completion, active-tool, action-execution, snapshot-assembly, workflow-prompt, or compaction-payload forwarding wrappers such as `_run_loop`, `_is_completion_signal`, `_allowed_tools_for_mode`, `_schemas_for_active_tools`, `_execute_action`, `_execute_parallel_tool_action`, `_capability_snapshot_for_provider`, `_prompt_units_for_snapshot`, `_append_workflow_prompt_messages`, `_compaction_token_counts`, or `_compacted_history_payload`.

`TurnSnapshot` is the explicit frozen provider-request input. `TurnSnapshotService` builds it after context assembly and active tool schema projection, then provider requests consume `snapshot.messages` and `snapshot.tool_schemas`. Snapshot diagnostics may record `snapshot_id`, mode/workflow state, registered tool names, active tool names, credential-free model profile metadata, safe prompt-unit metadata, and capability counts; they must not record full prompt bodies, file contents, raw tool outputs, or API keys.

`WorkflowPackageManifest` is a non-executing read model for workflow package identity, supported modes/workflow states, tool declarations, packs, resource scopes, and diagnostics. The bundled C/C++ manifest is derived from C workflow package-owned constants and exposed through `CHarnessWorkflowExtension.package_manifest()` / `ExtensionManager.package_manifests()`. It is not a public extension API, not an activation policy, and not a permission grant.

`CapabilityRegistry` is a non-executing read model for tools, local file resources, slash commands, model profiles, and workflow packages. Registration records provenance and metadata only. Tool activation remains owned by `ExtensionManager` / `AgentExtensionHost`, execution remains owned by `ToolRuntime` / `AgentToolActionService`, and permission decisions remain owned by `PermissionPolicy`.

`RuntimeConfigReducer` is the transcript-backed read model for safe replayable runtime configuration. It reduces `runtime_configured`, `resource_reloaded`, and provider-request `operation_started` snapshot metadata into credential-free model profile metadata, registered tool names, model-visible active tool names, local resource revision metadata, capability counts, and provider snapshot records. It must not decide tool activation, execute tools, reload resources, load project extensions, or bypass `PermissionPolicy`.

`CompactionJournal` builds the safe `compact_boundary` and `compacted_history` transcript payloads. `CompactionStateReducer` is the transcript-backed read model for structured compact boundary state. It reduces `compact_boundary` events into safe boundary records with token/message counts, preserved message anchors, trigger/phase/window-generation diagnostics, file activity paths, evidence refs, extension-summary flags, duplicate/malformed diagnostics, and latest-boundary metadata. It must not select context, rewrite summaries, execute extension code, infer history from `timeline.jsonl`, or become a second session-history source.

`RecoveryStateReducer` is the transcript-backed read model for hosted resume recovery markers. It reduces `recovery_marker` events into safe records with trusted-prefix counts, stop reasons, skip summaries, operation/compaction/runtime summaries, duplicate/malformed diagnostics, and latest-marker metadata. It must not change restore validation, retry tool calls, select modes, activate tools, bypass permissions, infer history from `timeline.jsonl`, or become frontend-owned policy.

`TurnExperienceReducer` is the transcript-backed read model for user-facing turn experience. It reduces safe `tool_result` and `loop_transition` events into completed work, unverified changes, validation failures, blockers, and next steps. Session snapshots and `session_finished` events may expose `turn_experience` for CLI/TUI/GUI display; the projection must not drive loop continuation, validation policy, active tools, permissions, restore behavior, extension loading, or session-history truth.

Default extension assembly lives in `src/embedagent_host/default_extensions.py`. `QueryEngine` must not import or construct `CHarnessWorkflowExtension`; direct internal `QueryEngine` tests that need default C/C++ behavior must pass an explicit `ExtensionManager`, while hosts must bind the selected manager through `AgentPorts` and use `Agent` / `AgentSession`.

`HarnessStateSynchronizer` has been removed. Product adapter paths must refresh harness state through `CHarnessWorkflowExtension.refresh_managed_session()` behind the default harness workflow extension.

### Task System

Official task truth for the default C/C++ harness workflow is:

- `TaskGraph`
- `task_status`
- session task snapshots

`Session.workflow_state` is the generic workflow-state carrier. Frontend-facing task fields are projected from `Session.workflow_state["workflow"]`.

Default C/C++ workflow projection assembly lives in `src/embedagent/workflow_packages/c_cpp/workflow_projection.py`. Harness internals may use `TaskGraph`, but the core/frontend boundary must consume the generic workflow payload produced there.

`Session.task_graph` has been removed. Default C/C++ graph ownership lives behind `CHarnessWorkflowExtension` and its harness-owned session graph state. Workflow-neutral strategies, projectors, and frontend task APIs must consume only `Session.workflow_state["workflow"]`.

Importing or instantiating `embedagent.session.Session` must not load `embedagent.workflow_packages.c_cpp.task_graph`; C harness graph internals stay behind the default harness workflow extension.

The retired todo-management tool is not part of the official workflow architecture.

### Tooling

Official default workflow tools center on:

- `read_file`
- `list_dir`
- `glob_files`
- `grep_text`
- `write_file`
- `edit_file`
- `author_local_capability`
- `bash`
- `list_recipes`
- `run_recipe`
- `report_quality_v2`
- `task_status`
- `record_failing_evidence`
- `ask_user`

Built-in mode `allowed_tools` are workflow-neutral permission/write contracts. Default C/C++ harness tools such as `list_recipes`, `run_recipe`, `report_quality_v2`, `record_failing_evidence`, and `task_status` are activated by the default harness workflow extension, not owned by the core mode schema.

`ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single runtime schema projection entry point. Without explicit `tool_names`, it projects only the workflow-neutral mode contract. Do not use runtime mode contracts as a shortcut for default harness pack activation; use `AgentExtensionHost` over the shared `ExtensionManager` and pass explicit active tool names into runtime schema projection.

C/C++ workflow pack definitions live only in `src/embedagent/workflow_packages/c_cpp/packs.py`. Do not reintroduce `src/embedagent/tooling/packs.py`, `embedagent.tooling.packs`, or package-root pack aliases on `embedagent.tooling`; those were stale compatibility paths and are no longer part of the product contract.

Command sanitization uses `get_command_sanitizer()` directly. Do not reintroduce
removed sanitizer proxy/wrapper aliases; shell execution must continue through
the official sanitizer accessor and normal permission policy.

Dynamic in-process extension tools are registered into the shared `ToolRuntime` with source metadata and explicit permission categories. The runtime catalog is the source of truth for tool permission category; `PermissionPolicy` must not maintain a parallel built-in tool taxonomy, and missing or invalid metadata falls back to ask-by-default `other`. The default C/C++ workflow package uses the same registration boundary for recipe, quality, evidence, and task-status tools. A registered extension tool is model-visible only when active through the shared `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)` path and remains subject to `PermissionPolicy`. Tool completion read-model refresh must use catalog/event `read_model_invalidations`; do not maintain Core, adapter, or GUI hard-coded tool-name refresh lists. GUI tool preview text and changed-file path inference must come from safe catalog presentation metadata such as `metadata.preview_arg` and `metadata.changed_path_arg` projected through session capabilities; do not add renderer-side preview/request-kind/changed-file branches for built-in or workflow tool names.

Local resource reload is a file discovery operation. `ToolRuntime.reload_resources()`, `InProcessAdapter.reload_resources(...)`, `/resources reload`, and `POST /api/sessions/{session_id}/resources/reload` refresh workspace-bound skills, prompts, and recipe JSON resources. Skills/prompts are surfaced as resources; `.embedagent/recipes/*.json` feeds workflow-neutral recipe definitions, and the default C/C++ workflow package applies its own `run_recipe` normalization only at the workflow-owned recipe aggregation boundary. Agent Skills-style frontmatter (`name`, `description`, `disable-model-invocation`) controls skill metadata and the lightweight local skill listing prompt unit. `/skill:<name> [args]` expands a workspace-bound skill Markdown file into a normal user turn; `/prompt:<name-or-path> [args]` expands a workspace-bound prompt file into a normal user turn. Neither bypasses tools, permissions, or extension loading. Reload does not execute local Python code. `author_local_capability` writes local self-extension artifacts under `.embedagent` and reports next actions; it does not implicitly reload resources or enable/load project extensions.

Slash command specs for workspace-local skill and prompt resources must be projected through `slash_commands.resource_command_specs(resources)`. Hosted adapters and capability projections must not own parallel resource command spec builders.

`ToolRuntime.capability_descriptors()` and `InProcessAdapter.capability_snapshot()` expose read-only capability projections for diagnostics and future reducer work. They must not be used as shortcuts for active-tool policy, permission checks, tool execution, resource reload, or project extension loading.

Project-local Python extension loading is a separate hosted adapter operation, not resource reload. Enabled project extensions are registered into the shared `ExtensionManager`; any dynamic tools they expose are visible only through `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)` and remain subject to `PermissionPolicy`.

Runtime-invoked external tools and release gates are governed by `scripts/offline-runtime-contract.json`. Keep this contract aligned with bundled Python, Bash from MinGit, MinGit, ripgrep, Universal Ctags, LLVM/Clang child executables, bundle-local C smoke validation, and Win7/WebView2 GUI smoke metadata whenever a runtime or release flow starts invoking a new binary. `validate-offline-bundle.ps1` and `check-bundle-dependencies.py` consume this contract; do not add a separate hard-coded bundle tool or release-gate list.

Enterprise/intranet tools must not be introduced as hidden Core calls. Intranet Git operations, custom service calls, model/provider gateways, or telemetry uploaders must enter through explicit provider/extension/workflow-package/sink boundaries, source metadata, structured configuration, timeout/fallback behavior, and normal `PermissionPolicy` checks. `network` and `telemetry` are official permission categories for those optional capabilities and default to confirmation unless policy rules say otherwise. Telemetry may observe safe lifecycle/capability/diagnostic events only; `src/embedagent/telemetry.py` provides the local safe-envelope helper and must not export prompts, source files, raw tool outputs, API keys, permission payloads, tokens, or approval secrets.

### Session History

Official session-history truth is:

- `transcript.jsonl` as the only durable session-history ledger
- `Session` / `session.turns` as the only live structured session state
- `SessionHistoryAssembler` as the only frontend session-history serializer
- `GET /api/sessions/{id}/bootstrap` as the only GUI/TUI activation bootstrap contract

`GET /api/app/bootstrap` is the GUI app-shell activation bootstrap only. It may expose GUI-owned workspace registry projection, safe host/runtime/renderer diagnostics, app-level commands, app surfaces, and local shell settings; it must not become session history truth, workflow truth, provider/runtime policy, permission policy, extension loading policy, or a replacement for `GET /api/sessions/{id}/bootstrap`.
No-workspace shell branding and copy must come from app-shell metadata such as
`app.productName`, `capabilities.home`, and `capabilities.emptyState`; renderer
components must not hard-code the default product or agent name, and renderer
app-shell normalizers must preserve missing product names as empty rather than
inventing a default.
Right-panel surface titles and surface-owned panel headings, including the
Files surface header, must come from backend-declared app-shell surface
descriptors rather than renderer-local default copy.

GUI thread lifecycle operations (`rename`, `fork`, and `archive`) must flow through the session lifecycle facade and update session summary/projection metadata used by app thread lists. Action labels, disabled reason labels, prompt, confirmation, success, empty-title, and failure copy must come from app-shell action descriptors; actions with missing labels stay out of the visible rail, and missing notice copy stays absent rather than being synthesized from action ids or labels. They must not rewrite transcript history, own workflow state, activate tools, decide permissions, load extensions, or create source-control checkpoints.

Hosted slash-command dispatch, command result emission, and command-owned tool execution are owned by `HostedCommandService`, not by `InProcessAdapter` or Agent Core. Hosted permission/user-input approve/reject/reply/respond glue and pending ticket state are owned by `HostedInteractionService`. Hosted `/review` synthesis is owned by `ReviewCommandService` underneath the command service. Session tool-evidence extraction, review finding rules, git-diff evidence shaping, and markdown rendering must stay in hosted command services; the adapter only invokes those services and bridges resulting state/events.
GUI session-load effects from command results must use structured payload
fields such as `switch_session_id`, not slash command names such as `/resume`.
GUI run-output log labels for command results must also come from explicit
payload fields such as `log_label` / `log_detail`; renderer code must not
synthesize visible log copy from slash command names or success booleans.
GUI session bootstrap serializers and renderer session normalizers must not
invent a missing workflow-state name such as `chat`; they should preserve the
explicit snapshot value and render workflow details from the separate generic
`workflow` payload.

There is no durable timeline-backed session-history store or timeline-backed
history replay path, and there is no session event replay HTTP route. GUI
session history, TUI session history, and T3 timeline bootstrap must come from
`GET /api/sessions/{id}/bootstrap` `history.activities`; nested `history.turns`
is structured diagnostics and must not be reprojected into a second frontend
history source. `SessionHistoryAssembler.build()` is the only active history
serializer; flat history item streams, TUI `items` history fallbacks, and event-list timeline
reload formatters are not product contracts. Live WebSocket data, TUI line
buffers, and GUI run-output logs may update current display state only and must
not become durable history truth.

GUI live interaction activity must enter the renderer through backend-owned
`session_event` messages emitted from Core turn events such as
`permission_required` and `user_input_required`. Raw
`permission_request` / `user_input_request` WebSocket messages exist only to
drive the current blocking interaction UI and response path; renderer code must
not synthesize interaction-created activity/history records from those raw
request messages or maintain a parallel interaction activity stream. User-input
interaction display must be driven by `kind` / `sourceActivityKind` plus
payload fields; when `tool_name` is absent, renderer code must not fill in the
default built-in `ask_user` tool name.

Official durable operation truth is:

- schema v2 `operation_started`
- schema v2 `operation_finished`
- schema v2 `operation_interrupted`

`OperationLogReducer` must derive operation state only from those explicit lifecycle events. `step_started`, `tool_call`, `tool_result`, and `loop_transition` remain session replay/history events; do not reintroduce operation-state inference from them. Current lifecycle operation families include turns, agent steps, context assembly, context snapshots, provider requests, tool calls, pending interactions, workflow patches, and save points. Restore-time projections close unfinished operations as interrupted; live session snapshots must preserve unfinished operations as active. Session snapshots may expose `operation_diagnostics` projected from the same reducer state; operation diagnostics remain diagnostic state, not a second session-history source.

Official durable runtime-configuration truth is reducer-backed:

- schema v2 `runtime_configured`
- schema v2 `resource_reloaded`
- schema v2 provider-request `operation_started` metadata containing safe `turn_snapshot` fields

`RuntimeConfigReducer` must derive runtime configuration only from these safe transcript events. `resource_discovered` remains discovery/replay diagnostics only and must not advance resource revision state. Runtime configuration projections may appear in session snapshots as `runtime_config`; that field remains diagnostic/replay state, not a frontend-owned execution policy.

Official durable compaction truth is reducer-backed:

- schema v1/v2 `compact_boundary`

`CompactionStateReducer` must derive structured compaction state only from `compact_boundary` transcript events. `Session.compact_boundaries` remains live context compatibility state, while restore results and session snapshots may expose `compaction_state` as diagnostic/replay state. That projection must not drive active context selection, extension loading, permission decisions, or frontend-owned execution policy.

Official durable recovery truth is reducer-backed:

- schema v1/v2 `recovery_marker`

`RecoveryStateReducer` must derive recovery state only from `recovery_marker` transcript events. Hosted resume may append safe recovery markers after restoring a trusted prefix. Restore results and session snapshots may expose `recovery_state` as diagnostic/replay state. That projection must not change restore stop rules, retry tool calls, drive active mode/tool/context selection, load extensions, bypass permissions, or become frontend-owned execution policy.

## Mode Policy

- Modes are product contracts, not UI decorations.
- `explore` is the default entry mode.
- `verify` is read-only and owns quality-gate style execution.
- The LLM does not autonomously switch modes.
- User-driven switching happens through `/mode <name>`, explicit pure natural-language mode-switch requests, or confirmed `ask_user` choices.
- Explicit user mode-switch requests are routed before provider calls; compound work requests must remain normal user turns unless they use `/mode <name> <message>`.

Mode definitions live in `src/embedagent/modes.py`.

## Permission Policy

One official permission engine only:

- `src/embedagent_core/permissions.py`

Permission rules are structured data, not free-form prompt behavior.
When changing permission behavior, keep rule matching, decision categories, and explanation text aligned.
Do not hide network or intranet side effects behind `read` or generic `other` behavior. Use the official `network` or `telemetry` categories when a tool reaches intranet/custom services or sends telemetry diagnostics, and keep frontend explanations plus active permission documentation aligned when semantics change.

## Frontend / Protocol Policy

One official frontend vocabulary only:

- `tasks`, not the retired todo vocabulary
- `build`, not `code`
- `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, `task_items`

Frontend-facing contract changes must be reflected together in:

- `src/embedagent/protocol/`
- `src/embedagent/core/`
- `src/embedagent/frontend/`

Frontend session activation must not reintroduce split snapshot/timeline bootstrap. Use the single bootstrap payload and transcript-backed structured history only.
GUI and TUI timeline bootstrap must consume `history.activities`; the GUI uses
the focused session runtime activity module and the TUI formats the same
activities into local display lines. Do not reintroduce frontend
turn/event timeline rebuilders, `session-runtime/projector.js`, flat timeline
views, or event-list timeline reload formatter paths.

GUI backend HTTP routes must stay delegated by family. `server.py` is the
composition root for app/static/websocket/bootstrap wiring, while route
registration lives in `routes_app.py`, `routes_sessions.py`,
`routes_terminal.py`, `routes_source_control.py`, and `routes_preview.py`. Do
not concentrate new HTTP route decorators back into `server.py`.

GUI renderer runtime state must follow focused T3-style modules instead of
root-level global reducer fields. Thread/session selection, session summaries,
and history-integrity display state live in
`src/embedagent/frontend/gui/webapp/src/session-runtime/thread-state.js`;
session activity normalization and T3 timeline grouping live in
`src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js`;
GUI run-output event-log display state lives in
`src/embedagent/frontend/gui/webapp/src/session-runtime/run-output-state.js`;
active-session transport connection/reload projection lives in
`src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js`;
WebSocket lifecycle control lives in
`src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js`;
session bootstrap activation control lives in
`src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js`;
composer draft text lives in
`src/embedagent/frontend/gui/webapp/src/composer/composer-state.js`; terminal
display buffers remain under `src/embedagent/frontend/gui/webapp/src/terminal/`;
workbench surface persistence remains under
`src/embedagent/frontend/gui/webapp/src/workbench/`. Do not reintroduce
root-level `sessions`, `currentSessionId`, `composer`, `historyIntegrity`,
`connectionState`, retired sidebar tab state/actions such as `sidebarTab` or
`set_sidebar`, `set_connection`, or timeline reload state as parallel GUI state.

GUI visual debug fixtures are development-only. `?visual_debug=1` may expose
`window.__EMBEDAGENT_VISUAL_DEBUG__`, but fixture helpers must expand private
`dev_fixture_*` descriptors into ordinary product reducer actions. Product
reducers must not add or retain `visual_*fixture` action cases.

Generated GUI static assets under `src/embedagent/frontend/gui/static/` are
current release artifacts. When webapp source changes, rebuild them through the
webapp build command, but normal review and architecture reasoning should use
`src/embedagent/frontend/gui/webapp/src/` as source of truth.

GUI workbench surface titles are app-shell display descriptors. Renderer-local
surface registries may keep known renderer kind, resource, close-behavior, and
persistence metadata, but visible launcher/command entries require explicit
app-shell `title` metadata, and renderer helpers must not synthesize surface
titles from surface kind or id values. Resource instance titles such as file
basenames, preview ids/URLs, or terminal ids remain instance data, not
app-shell defaults; missing preview instance data must not create a renderer
fallback tab.

GUI workbench command labels are app-shell or capability display descriptors.
App/workspace/workbench command entries without explicit labels must stay out
of visible command lists, and dynamic slash commands are visible only when
their capability descriptors provide explicit `label`, `usage`, or `slash`
metadata. Commands in command-palette groups without explicit descriptor titles
must also stay hidden. Renderer command lists and command-palette rows must not
synthesize visible titles from command ids or group ids, and missing command
row description/meta copy must remain empty instead of falling back to command
ids. Surface command row descriptions must come from surface descriptors and
must not be synthesized from surface or drawer ids. Session/workspace palette
row leading markers must also come from command-palette label descriptors and
remain empty when absent. Command-palette group leading markers must come from
explicit group descriptors and must not be synthesized from group titles.

The GUI terminal bottom drawer is an app-shell hosted surface, not Agent Core. It uses Windows 7-compatible Python stdlib subprocess pipes, is not a full PTY, and must not depend on ConPTY, `node-pty`, `pywinpty`, `pexpect`, Electron, runtime Node, Docker, WSL, VS Code, or online services. Terminal output is GUI-local display state only: it must not be written to `transcript.jsonl`, telemetry, workflow state, source-control checkpoints, or permission/runtime reducer truth.

The GUI File Preview right-panel is an app-shell hosted, read-only display surface over already-loaded workspace file content, not Agent Core and not a file editing workflow. Its chrome/copy, metadata labels, fallback messages, and language labels must come from `capabilities.surfaces.chrome.file_preview` rather than renderer-local defaults. It must not save files, write transcript history, own workflow state, decide permissions, load extensions, update telemetry, or become a source-control checkpoint or Agent Core policy path.

The GUI Composer slash-command and file-context menu is app-shell display state. Its menu aria labels, empty states, path/kind labels, fallback command group copy, default slash-command group id, and hint-bar descriptors must come from `capabilities.chrome.composer`, and slash command group titles must reuse `capabilities.command_palette.groups`. Slash menu items must come from command capability projection, not renderer-local static command hints. Renderer composer modules must not keep a parallel English command/path menu string table, hard-coded hint item list, synthesize missing command groups as `"command"`, or infer agent/workflow identity from those labels.

The GUI Timeline is app-shell display projection over session bootstrap/live activities, not durable history truth and not Agent Core. Its log aria label, empty/history/termination copy, work-group labels, activity-row labels/status/timer templates, work-row default heading/icon/status labels, changed-files card labels, and structured tool-detail field/section labels must come from `capabilities.chrome.timeline` rather than renderer-local defaults. The T3 timeline projection may carry display data such as `createdAt`, `completedAt`, `interrupted`, detail field keys, and detail section kinds, but it must not precompute renderer chrome labels. Review-result row classification must use structured review payload fields such as `data.review` / `review`, not slash command names such as `/review`; command-result row labels must come from explicit payload labels or app-shell `commandDefaultName`, not synthesized `/${commandName}` strings. It must not rewrite transcript history, own workflow state, decide permissions, load extensions, update telemetry, or become provider/runtime policy.

The GUI Source Control right-panel and composer Branch Toolbar are app-shell hosted, active-workspace surfaces, not Agent Core and not the default C/C++ workflow package. They may use bundled/workspace MinGit through the GUI backend for read-only local `status` and `diff` views, and their surface chrome/copy, including group order, group/provider labels, and file status badge labels, must come from `capabilities.source_control.chrome` and `capabilities.source_control.chrome.branch_toolbar` rather than renderer-local defaults. Missing group/provider labels must not fall back to raw protocol ids as visible UI. They must remain local/offline by default and must not implement remote providers, push/pull, staging, commit, checkpoint mutation, transcript writes, workflow state, telemetry, permission policy, runtime reducer truth, provider configuration, extension loading, or hidden network behavior. Future source-control mutations or remote/intranet Git work must enter through explicit hosted extension/provider/workflow-package boundaries with normal permission categories and must not weaken Win7/offline support.
Source-control, terminal, and preview frontend API helpers must not carry
renderer-local request-failure copy; if the backend omits detail/error text,
controllers should fall through to the relevant app-shell chrome fallback.

The GUI Diff right-panel is an app-shell hosted display surface over already-projected unified diff text, not Agent Core, not source-control policy, and not a workflow package. Command results may open it only through structured diff payload fields such as `data.diff`, not slash command names such as `/diff`. Its default title, empty state, controls, file rail labels, collapse labels, and source-control diff title template must come from `capabilities.surfaces.chrome.diff_panel` rather than renderer-local defaults. Workbench tab titles must come from explicit diff payload titles or the app-shell surface descriptor, not a renderer `"diff"` fallback. It must not write transcript history, own workflow state, decide permissions, load extensions, update telemetry, mutate source control, or become an Agent Core policy path.

## Documentation Maintenance

When changing architecture or workflow assumptions, update the matching source-of-truth documents in the same change:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`

- `docs/superpowers/` design and plan documents are slice-local working materials, not permanent architecture truth.
- When a slice is completed, its durable conclusions must be synchronized back into global source-of-truth docs and module docs.
- Governance rules, workflow rules, terminology, and templates live under `docs/` active documentation, not inside archived or slice-local files.
- Completed slice documents should be moved to `docs/archive/` after global docs are synchronized.

Historical notes belong in `docs/archive/` or changelog material, not in current architecture docs.

## Non-Goals

The repository is not currently trying to become:

- a browser automation agent
- a web search system
- a heavyweight RAG platform
- a public plugin marketplace or runtime online installer
- a mandatory network-connected control plane
- a general multi-agent orchestration framework

The product is a focused native Agent IDE core for offline C engineering work.
