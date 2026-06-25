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

The project is still pre-release and has no production user state to preserve. `docs/pre-release-architecture-debt-audit.md` is the active debt baseline for the next cleanup program: do not add compatibility scaffolding for old internal session, timeline, GUI reducer, or extension-hook shapes when a slice can delete or replace them. Forward compatibility for pre-release internal state is not a goal; preserving Windows 7, offline deployment, Python 3.8, and the default C/C++ workflow remains mandatory.

Do not treat blueprint target terms such as `SessionLog` or public `HookBus` as implemented public APIs until a specific implementation slice lands and updates the source-of-truth docs. `AgentEventBus` is now the internal source-aware event/reducer boundary for public extension hook dispatch; it is not a public extension API. `AgentLifecycleJournal`, `AgentKernel`, `AgentLoop`, `AgentLoopContinuationPolicy`, `TurnSnapshot`, `CapabilityRegistry`, `RuntimeConfigReducer`, `WorkflowPackageManifest`, `CompactionStateReducer`, and `RecoveryStateReducer` are implemented internal Agent Core boundaries/read models, not public extension APIs. The bundled default C/C++ workflow package now owns its workflow tool registration, metadata, packs, and read-only package manifest behind `CHarnessWorkflowExtension`; the obsolete `embedagent.tooling.packs` compatibility re-export has been removed, so C/C++ workflow pack truth lives only in `embedagent.harness.packs`. Core singleton-like access must use explicit accessors (`get_mode_registry()`, `get_command_sanitizer()`, `get_inprocess_adapter()`); stale global/proxy aliases such as `MODE_REGISTRY`, `_DEFAULT_SANITIZER`, `get_default_sanitizer()`, `_inprocess_adapter`, and `_get_adapter_class()` must not be reintroduced. Local self-extension authoring is available through `SelfExtensionAuthoringService` and `author_local_capability`; repo-side offline bundle validation is contract-backed through `scripts/offline-runtime-contract.json`; near-term work must keep the default C/C++ workflow runnable while deleting stale internal compatibility layers and advancing real Win7 bundle smoke validation plus real C/C++ project validation. Future intranet Git, custom service, provider, or telemetry work must follow Pi's adapter style rather than copying Pi's full openness: Core emits safe events/read models and enforces capability/permission boundaries, while networked behavior lives in optional hosted extensions, providers, workflow packages, or passive telemetry sinks.

### Modes

Official first-class modes are:

- `explore`
- `spec`
- `build`
- `debug`
- `verify`

`code` is no longer a first-class mode.

Mode registry access must go through `get_mode_registry()` / `initialize_modes()`.
Do not reintroduce a module-level `MODE_REGISTRY` proxy or make mode helpers depend
on mutable compatibility aliases.

### Harness

Official C/C++ execution semantics are provided by the default built-in harness workflow extension:

- `mode`
- `discipline_profile`
- `execution_phase`
- `TaskGraph`

Agent Core must route harness-specific prompt injection, task initialization, and workflow tool handling through the extension boundary instead of importing harness classes directly.

Local offline self-extension is an official architecture capability, limited to workspace file resources and manifest-gated project-local Python extensions. Public remote registries, online extension installs, runtime dependency installation, plugin marketplaces, built-in tool replacement, and general multi-agent orchestration remain out of scope. Organization-local catalogs, intranet Git sources, custom service providers, and telemetry sinks may be considered only as trusted/admin-provisioned optional capabilities outside Agent Core; they must not grant execution rights, install dependencies at runtime, or become required for offline operation.

`InProcessAdapter` owns the hosted runtime's shared `ExtensionManager` and passes it to session-scoped `QueryEngine` instances. Frontend tool catalog visibility must use that same manager instead of a separate adapter-only harness extension chain.

`ExtensionManager` is also the shared in-process capability boundary for prompt/context hooks, tool-call and tool-result hooks, resource discovery contracts, dynamic in-process tool registration, extension diagnostics, and manifest-gated project-local Python extensions. Its hook internals dispatch through `AgentEventBus` with source metadata, observer/reducer separation, event-specific merge/stop semantics, and diagnostics; do not add new extension hook merge semantics outside that bus. Workspace-local file resources under `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` are discoverable and reloadable as file resources only. Skills support Agent Skills-style frontmatter and visible skills are summarized through a single lightweight local skill listing prompt unit. Skill bodies expand only through `/skill:<name> [args]`; prompt bodies expand only through `/prompt:<name-or-path> [args]`. Both remain Markdown/resource loading, not code execution. `author_local_capability` may generate those resources and disabled extension skeletons, but it must not reload resources or load Python extension code. Project-local Python extensions are loaded only from enabled `.embedagent/extensions/<name>/extension.json` manifests with workspace-bound `extension.py` entrypoints, declared permissions, no dependency installation, no remote registry, and no built-in tool replacement.

`AgentExtensionHost` is the QueryEngine-side extension dispatch boundary. `QueryEngine` must not scatter direct `ExtensionManager` hook calls for prompt injection, context patching, dynamic tool registration, active-tool schema projection, tool-call hooks, tool-result hooks, or extension-owned tool handling.

Workflow-package prompt units appended by `QueryEngine` must use the generic `workflow_prompt` system message kind. `harness_prompt` is legacy session/transcript compatibility only and must not be used for newly appended workflow prompts.

`AgentLifecycleJournal` owns durable lifecycle event emission, transition save points, pending interaction lifecycle operation events, context operation payload helpers, and workflow-patch persistence helpers. `AgentKernel` owns turn frames plus pending interaction creation/resolution boundaries. `AgentToolActionService` owns non-LLM tool action execution behind `QueryEngine`: active-tool checks, extension pre/post hooks, `PermissionPolicy` evaluation, path write guards, runtime dispatch, extension-owned tool calls, interactive action handling, resumed action execution, and workflow-patch capture after tool-result hooks. `AgentLoop` owns Pi-style open turn-loop continuation behind the session facade, including agent steps, provider/context attempts, active schema requests through `AgentExtensionHost`, compact retry, guard-stop, abort, and explicit loop safety-limit compatibility transitions. `max_turns` remains accepted as the legacy configuration field for that optional safety fuse; omitted values mean no fixed turn-count ceiling. `QueryEngine` remains the session-scoped facade and transcript/session mutation owner; do not reintroduce private active-tool or action-execution forwarding wrappers such as `_allowed_tools_for_mode`, `_schemas_for_active_tools`, `_execute_action`, or `_execute_parallel_tool_action`.

`TurnSnapshot` is the explicit frozen provider-request input. `QueryEngine` builds it after context assembly and active tool schema projection, then provider requests consume `snapshot.messages` and `snapshot.tool_schemas`. Snapshot diagnostics may record `snapshot_id`, mode/workflow state, registered tool names, active tool names, credential-free model profile metadata, safe prompt-unit metadata, and capability counts; they must not record full prompt bodies, file contents, raw tool outputs, or API keys.

`WorkflowPackageManifest` is a non-executing read model for workflow package identity, supported modes/workflow states, tool declarations, packs, resource scopes, and diagnostics. The bundled C/C++ manifest is derived from C workflow package-owned constants and exposed through `CHarnessWorkflowExtension.package_manifest()` / `ExtensionManager.package_manifests()`. It is not a public extension API, not an activation policy, and not a permission grant.

`CapabilityRegistry` is a non-executing read model for tools, local file resources, slash commands, model profiles, and workflow packages. Registration records provenance and metadata only. Tool activation remains owned by `ExtensionManager` / `AgentExtensionHost`, execution remains owned by `ToolRuntime` / `AgentToolActionService`, and permission decisions remain owned by `PermissionPolicy`.

`RuntimeConfigReducer` is the transcript-backed read model for safe replayable runtime configuration. It reduces `runtime_configured`, `resource_reloaded`, and provider-request `operation_started` snapshot metadata into credential-free model profile metadata, registered tool names, model-visible active tool names, local resource revision metadata, capability counts, and provider snapshot records. It must not decide tool activation, execute tools, reload resources, load project extensions, or bypass `PermissionPolicy`.

`CompactionStateReducer` is the transcript-backed read model for structured compact boundary state. It reduces `compact_boundary` events into safe boundary records with token/message counts, preserved message anchors, trigger/phase/window-generation diagnostics, file activity paths, evidence refs, extension-summary flags, duplicate/malformed diagnostics, and latest-boundary metadata. It must not select context, rewrite summaries, execute extension code, infer history from `timeline.jsonl`, or become a second session-history source.

`RecoveryStateReducer` is the transcript-backed read model for hosted resume recovery markers. It reduces `recovery_marker` events into safe records with trusted-prefix counts, stop reasons, skip summaries, operation/compaction/runtime summaries, duplicate/malformed diagnostics, and latest-marker metadata. It must not change restore validation, retry tool calls, select modes, activate tools, bypass permissions, infer history from `timeline.jsonl`, or become frontend-owned policy.

Default extension assembly lives in `src/embedagent/default_extensions.py`. `QueryEngine` must not import or construct `CHarnessWorkflowExtension`; direct `QueryEngine` tests or hosts that need default C/C++ behavior must pass an explicit `ExtensionManager`.

`HarnessStateSynchronizer` has been removed. Product adapter paths must refresh harness state through `CHarnessWorkflowExtension.refresh_managed_session()` behind the default harness workflow extension.

### Task System

Official task truth for the default C/C++ harness workflow is:

- `TaskGraph`
- `task_status`
- session task snapshots

`Session.workflow_state` is the generic workflow-state carrier. Frontend-facing task fields are projected from `Session.workflow_state["workflow"]`.

Default C/C++ workflow projection assembly lives in `src/embedagent/harness/workflow_projection.py`. Harness internals may use `TaskGraph`, but the core/frontend boundary must consume the generic workflow payload produced there.

`Session.task_graph` has been removed. Default C/C++ graph ownership lives behind `CHarnessWorkflowExtension` and its harness-owned session graph state. Workflow-neutral strategies, projectors, and frontend task APIs must consume only `Session.workflow_state["workflow"]`.

Importing or instantiating `embedagent.session.Session` must not load `embedagent.harness.task_graph`; C harness graph internals stay behind the default harness workflow extension.

`manage_todos` is not part of the official workflow architecture.

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

C/C++ workflow pack definitions live only in `src/embedagent/harness/packs.py`. Do not reintroduce `src/embedagent/tooling/packs.py`, `embedagent.tooling.packs`, or package-root pack aliases on `embedagent.tooling`; those were stale compatibility paths and are no longer part of the product contract.

Command sanitization uses `get_command_sanitizer()` directly. Do not reintroduce
`get_default_sanitizer()` or `_DEFAULT_SANITIZER`; shell execution must continue
through the official sanitizer accessor and normal permission policy.

Dynamic in-process extension tools are registered into the shared `ToolRuntime` with source metadata and explicit permission categories. The default C/C++ workflow package uses the same registration boundary for recipe, quality, evidence, and task-status tools. A registered extension tool is model-visible only when active through the shared `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)` path and remains subject to `PermissionPolicy`.

Local resource reload is a file discovery operation. `ToolRuntime.reload_resources()`, `InProcessAdapter.reload_resources(...)`, `/resources reload`, and `POST /api/sessions/{session_id}/resources/reload` refresh workspace-bound skills, prompts, and recipe JSON resources. Skills/prompts are surfaced as resources; `.embedagent/recipes/*.json` feeds the existing recipe contract. Agent Skills-style frontmatter (`name`, `description`, `disable-model-invocation`) controls skill metadata and the lightweight local skill listing prompt unit. `/skill:<name> [args]` expands a workspace-bound skill Markdown file into a normal user turn; `/prompt:<name-or-path> [args]` expands a workspace-bound prompt file into a normal user turn. Neither bypasses tools, permissions, or extension loading. Reload does not execute local Python code. `author_local_capability` writes local self-extension artifacts under `.embedagent` and reports next actions; it does not implicitly reload resources or enable/load project extensions.

`ToolRuntime.capability_descriptors()` and `InProcessAdapter.capability_snapshot()` expose read-only capability projections for diagnostics and future reducer work. They must not be used as shortcuts for active-tool policy, permission checks, tool execution, resource reload, or project extension loading.

Project-local Python extension loading is a separate hosted adapter operation, not resource reload. Enabled project extensions are registered into the shared `ExtensionManager`; any dynamic tools they expose are visible only through `ExtensionManager.allowed_tool_names(mode_name, workflow_state=workflow_state)` and remain subject to `PermissionPolicy`.

Runtime-invoked external tools are governed by `scripts/offline-runtime-contract.json`. Keep this contract aligned with bundled Python, Bash from MinGit, MinGit, ripgrep, Universal Ctags, and LLVM/Clang child executables whenever a runtime flow starts invoking a new binary. `validate-offline-bundle.ps1` and `check-bundle-dependencies.py` consume this contract; do not add a separate hard-coded bundle tool list.

Enterprise/intranet tools must not be introduced as hidden Core calls. Intranet Git operations, custom service calls, model/provider gateways, or telemetry uploaders must enter through explicit provider/extension/workflow-package/sink boundaries, source metadata, structured configuration, timeout/fallback behavior, and normal `PermissionPolicy` checks. `network` and `telemetry` are official permission categories for those optional capabilities and default to confirmation unless policy rules say otherwise. Telemetry may observe safe lifecycle/capability/diagnostic events only; `src/embedagent/telemetry.py` provides the local safe-envelope helper and must not export prompts, source files, raw tool outputs, API keys, permission payloads, tokens, or approval secrets.

### Session History

Official session-history truth is:

- `transcript.jsonl` as the only durable session-history ledger
- `Session` / `session.turns` as the only live structured session state
- `SessionHistoryAssembler` as the only GUI history serializer
- `GET /api/sessions/{id}/bootstrap` as the only GUI activation bootstrap contract

`GET /api/app/bootstrap` is the GUI app-shell activation bootstrap only. It may expose GUI-owned workspace registry projection, safe host/runtime/renderer diagnostics, app-level commands, app surfaces, and local shell settings; it must not become session history truth, workflow truth, provider/runtime policy, permission policy, extension loading policy, or a replacement for `GET /api/sessions/{id}/bootstrap`.

GUI thread lifecycle operations (`rename`, `fork`, and `archive`) must flow through the session lifecycle facade and update session summary/projection metadata used by app thread lists. They must not rewrite transcript history, own workflow state, activate tools, decide permissions, load extensions, or create source-control checkpoints.

Hosted `/review` synthesis is owned by `ReviewCommandService`, not by `InProcessAdapter` or Agent Core. The adapter may collect recent session tool evidence and emit the slash-command result, but review finding rules, git-diff evidence shaping, and markdown rendering must stay in that hosted command service.

There is no durable `SessionTimelineStore` or timeline-backed history replay
path. `GET /api/sessions/{id}/events` is a bootstrap-reload signal, not a
history API. GUI session history and T3 timeline bootstrap must come from
`GET /api/sessions/{id}/bootstrap`; live WebSocket/event-log data may update
current GUI display state only and must not become durable history truth.

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
- User-driven switching happens through `/mode <name>` or confirmed `ask_user` choices.

Mode definitions live in `src/embedagent/modes.py`.

## Permission Policy

One official permission engine only:

- `src/embedagent/permissions.py`

Permission rules are structured data, not free-form prompt behavior.
When changing permission behavior, keep rule matching, decision categories, and explanation text aligned.
Do not hide network or intranet side effects behind `read` or generic `other` behavior. Use the official `network` or `telemetry` categories when a tool reaches intranet/custom services or sends telemetry diagnostics, and keep frontend explanations plus active permission documentation aligned when semantics change.

## Frontend / Protocol Policy

One official frontend vocabulary only:

- `tasks`, not `todos`
- `build`, not `code`
- `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, `task_items`

Frontend-facing contract changes must be reflected together in:

- `src/embedagent/protocol/`
- `src/embedagent/core/`
- `src/embedagent/frontend/`

Frontend session activation must not reintroduce split snapshot/timeline bootstrap. Use the single bootstrap payload and transcript-backed structured history only.

The GUI terminal bottom drawer is an app-shell hosted surface, not Agent Core. It uses Windows 7-compatible Python stdlib subprocess pipes, is not a full PTY, and must not depend on ConPTY, `node-pty`, `pywinpty`, `pexpect`, Electron, runtime Node, Docker, WSL, VS Code, or online services. Terminal output is GUI-local display state only: it must not be written to `transcript.jsonl`, telemetry, workflow state, source-control checkpoints, or permission/runtime reducer truth.

The GUI Source Control right-panel is an app-shell hosted, active-workspace surface, not Agent Core and not the default C/C++ workflow package. It may use bundled/workspace MinGit through the GUI backend for read-only local `status` and `diff` views. It must remain local/offline by default and must not implement remote providers, push/pull, staging, commit, checkpoint mutation, transcript writes, workflow state, telemetry, permission policy, runtime reducer truth, provider configuration, extension loading, or hidden network behavior. Future source-control mutations or remote/intranet Git work must enter through explicit hosted extension/provider/workflow-package boundaries with normal permission categories and must not weaken Win7/offline support.

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
