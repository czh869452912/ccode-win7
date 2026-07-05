# EmbedAgent

EmbedAgent is a native, offline-first agentic coding platform built around a
generic Agent Core. The default packaged product remains optimized for the full
C/C++ development lifecycle.

The current product baseline is:

- Windows 7 compatible
- Offline deployable
- Python 3.8 runtime target
- Agent Core first, UI replaceable
- Clang-centered C/C++ workflow

## Current Official Architecture

The repository now separates the generic Agent Core, the hosted product
composition layer, and replaceable workflow packages:

- `src/embedagent_core/` is the workflow-neutral Agent Core package. It must not
  import GUI backend code, hosted product composition, or workflow packages.
- `src/embedagent_host/` assembles Core, selected workflow packages, session
  hosting, command/interaction services, and UI shells into the product runtime.
- `src/embedagent/agent_applications.py` is the base scenario application
  registry for profile-only agents. The hosted product registry in
  `src/embedagent_host/agent_application_registry.py` explicitly adds the
  bundled `embedagent.default_c_cpp` specialized agent as the packaged default.
- `src/embedagent/workflow_packages/c_cpp/` is the first-party default C/C++
  workflow package. It is bundled by the hosted product, but it is not Core.
- `src/embedagent/protocol/` contains the Agent App Protocol contracts consumed
  by reusable GUI/TUI shells.

`embedagent_core` is the generic Agent Core package boundary. It does not
import the product package, host package, GUI, TUI, or workflow packages.
Concrete provider clients, workspace tools, stores, context assembly, and
default workflow composition live outside Core and are injected by
`embedagent_host`.

Local offline self-extension is part of the official architecture: workspace file resources and manifest-gated project-local Python extensions can extend the hosted runtime while remote registries, online installs, dependency installation, plugin marketplaces, built-in tool replacement, and general multi-agent orchestration remain outside the product baseline.

Optional enterprise/intranet integrations follow the same minimal-core rule: they may exist as trusted providers, workflow packages, project extensions, or telemetry sinks, but Agent Core must not depend on network availability. Intranet Git, custom service, and telemetry features must be explicit, disableable, manifest/config gated, permission-checked, and failure-tolerant; they must not send prompts, source text, raw tool outputs, or credentials through diagnostics or telemetry.

The next long-term architecture direction is captured in `docs/pi-inspired-agent-core-blueprint.md`: continue learning from Pi's functional design and architecture philosophy while preserving EmbedAgent's offline, Windows 7, Python 3.8, and C/C++ engineering constraints. The current baseline remains valid, but the project is still pre-release and has no production user state to preserve. `docs/pre-release-architecture-debt-audit.md` records the closed pre-release cleanup baseline and remains the guardrail for future deletion-oriented work: old internal session formats, timeline dependencies, GUI reducer shapes, and extension-hook compatibility layers should be deleted or replaced when they block the Pi/T3 target. The blueprint guides work toward a smaller Agent Kernel, durable session-log reducers, source-aware hooks, explicit turn snapshots, replayable runtime configuration, structured compaction state, recovery markers, and a default C/C++ workflow package loaded through the same capability boundary as local extensions.

- User-visible modes: `explore`, `spec`, `build`, `debug`, `verify`
- Default C/C++ execution model: `mode + discipline_profile + execution_phase`
- Default task system: `TaskGraph` projected through `task_status` and session task snapshots
- Generic workflow state carrier: `Session.workflow_state`
- Frontend workflow projection: `Session.workflow_state["workflow"]` is the source for `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, and `task_items`
- GUI session bootstrap and renderer normalization must not invent a missing
  workflow-state name such as `chat`; they forward the explicit snapshot value
  and use the separate generic `workflow` payload for frontend workflow display.
- Default C/C++ task graph ownership: `CHarnessWorkflowExtension` keeps harness graph state behind the extension boundary; `Session` no longer exposes `task_graph`
- Default C/C++ workflow projection adapter: `src/embedagent/workflow_packages/c_cpp/workflow_projection.py` maps harness internals into the generic workflow payload
- Official build/verify execution: `list_recipes` + `run_recipe` + `report_quality_v2`
- Hosted agent profiles declare scenario mode metadata, base tool policy, and GUI mode capability projection. Workflow packages declare scenario-specific workflow tools, packs, prompts, resources, and manifests. Provider-facing schemas are always projected from explicit active tool names computed by the shared extension boundary.
- Mode allowed-tool contracts are workflow-neutral; default harness tools are activated by the built-in C/C++ workflow extension
- Bare `ToolRuntime` construction is workflow-neutral; the bundled C/C++ workflow package registers recipe, quality, evidence, and task-status tools through `CHarnessWorkflowExtension.register_tools(...)`
- C/C++ workflow pack definitions live only under `src/embedagent/workflow_packages/c_cpp/packs.py`; the obsolete `embedagent.tooling.packs` compatibility re-export has been removed
- Official file discovery: `list_dir`, `glob_files`, `grep_text`
- Official permission engine: `PermissionPolicy` with structured rule matching and stable explanation text
- Official enterprise permission categories: `network` and `telemetry` exist for optional intranet/custom-service tools and telemetry flush/sink actions; both require explicit metadata and default to confirmation
- Official session runtime ownership: one session-scoped `QueryEngine` remains the facade and transcript/session mutation owner, while `AgentLifecycleJournal`, `AgentKernel`, `AgentLoop`, `ProgressGuard`, `AgentToolActionService`, and `AgentExtensionHost` own durable lifecycle writes, turn frames and suspend/resume boundaries, open turn-loop continuation, no-progress/runaway protection, non-LLM tool action execution, and extension hook dispatch
- Official workflow extension hosting: `InProcessAdapter` owns one `ExtensionManager` shared with session-scoped `QueryEngine` and frontend tool catalog visibility
- Official hosted adapter services: `HostedCommandService` owns slash-command dispatch, command result emission, and hosted command tool execution; `HostedInteractionService` owns permission/user-input response glue and pending ticket state. User-input interaction kind comes from pending-interaction/session-event payloads; GUI code must not synthesize missing tool names as `ask_user`. GUI session-switch effects from command results are driven by `switch_session_id` payloads, not slash command names such as `/resume`; GUI run-output log labels for command results are optional payload fields such as `log_label` / `log_detail`, not renderer-synthesized slash-command copy. `InProcessAdapter` remains the host/session bridge and must not grow parallel command or interaction helper paths.
- Official extension runtime direction: `ExtensionManager` is the shared in-process capability boundary for workflow defaults, prompt/context hooks, tool-call/tool-result hooks, resource discovery contracts, dynamic in-process tool registration, extension diagnostics, and manifest-gated project-local Python extensions. Extensions expose hooks only through `extension_capabilities()` returning `ExtensionCapability` records; method-name hooks are no longer auto-discovered. Internally, capability records dispatch through the source-aware `AgentEventBus` with event-specific reducer semantics and diagnostics.
- Official workflow prompt boundary: `PromptAssemblyService` owns workflow prompt append/dedupe and emits generic `workflow_prompt` system messages. The old harness-specific prompt kind is not active and is not used for current prompt injection or deduplication.
- Official local resources: `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` are discovered as workspace-bound file resources and can be refreshed through `ToolRuntime.reload_resources()`, `InProcessAdapter.reload_resources(...)`, `/resources reload`, or `POST /api/sessions/{id}/resources/reload`. Skills support Agent Skills-style frontmatter; visible skills are summarized through one lightweight local skill listing prompt unit, while `/skill:<name> [args]` explicitly expands a local skill file into a normal user turn. Prompt files are not injected into default system prompts; `/prompt:<name-or-path> [args]` explicitly expands a workspace-bound prompt file into a normal user turn.
- Official local self-extension authoring: `SelfExtensionAuthoringService` and the `author_local_capability` tool generate workspace-bound skills, prompts, workflow-neutral recipe JSON, and disabled-by-default project extension skeletons. Authoring writes files only; it does not reload resources, load Python extension code, or stamp generated recipe files with default C/C++ workflow tool names.
- Official project extension loading: hosted product paths may load enabled `.embedagent/extensions/<name>/extension.json` manifests with workspace-bound `extension.py` entrypoints; `enabled` defaults to false, enabled manifests must declare permissions, no dependency installation or remote registry is allowed, and loaded extensions register explicit `api.ExtensionCapability` records through the same shared `ExtensionManager`
- Official agent application assembly: `src/embedagent/agent_applications.py` defines the hosted scenario application boundary, manifest registry, and selected-application loader. The default hosted product loads `src/embedagent/workflow_packages/c_cpp/application.py`, which installs the bundled C/C++ workflow extension outside `QueryEngine`; profile-only built-ins such as `embedagent.generic`, `embedagent.python`, and `embedagent.html` load the same Agent Core and GUI without installing the C/C++ workflow package. `QueryEngine` itself has no built-in harness import or constructor fallback.
- Official frontend application capability: hosted capability payloads expose the selected application as `agentApplication` and available same-package applications as `agentApplications`. GUI shells consume these backend-declared descriptors and must not hard-code C/C++ defaults, no-workspace copy, or application-specific mode/tool lists.
- Official GUI no-workspace shell copy: the empty workspace screen consumes
  app-shell metadata such as `app.productName`, `capabilities.home`, and
  `capabilities.emptyState`; renderer components must not hard-code the
  default product or agent name, and renderer app-shell normalizers must
  preserve missing product names as empty rather than inventing a default.
- Official GUI surface descriptor copy: right-panel surface titles and
  surface-owned panel headings, including the Files surface header, come from
  backend-declared app-shell surface descriptors rather than renderer-local
  defaults. Surface capabilities without explicit descriptor titles do not
  enter visible launchers or commands, and the renderer must not synthesize
  surface titles from kind/id values. Resource surface helper titles are
  limited to instance data such as file basenames, preview ids/URLs, and
  terminal ids; missing preview instance data does not create a fallback tab.
- Official GUI workbench command copy: app/workspace/workbench command labels
  come from app-shell command descriptors, and dynamic command labels come from
  explicit capability `label`, `usage`, or `slash` metadata. Commands with no
  visible label stay out of workbench command lists and the command palette;
  commands in command-palette groups without explicit descriptor titles also
  stay hidden. Renderer code must not synthesize labels, palette row titles, or
  group titles from command ids or group ids, and missing command row
  description/meta copy remains empty instead of falling back to command ids.
  Surface command row descriptions come from surface descriptors and are not
  synthesized from surface or drawer ids. Session/workspace palette row leading
  markers also come from command-palette label descriptors and are empty when
  absent. Command-palette group leading markers are explicit group descriptor
  fields and are not synthesized from group titles.
- Official application refresh path: `AgentApplication.refresh_managed_session()` delegates to the selected application's workflow refreshers. The bundled C/C++ application uses `CHarnessWorkflowExtension.refresh_managed_session()` internally; the old `HarnessStateSynchronizer` service facade has been removed.
- Official runtime schema projection: `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is the single schema projection entry point; callers must pass explicit active tool names and omitted `tool_names` project no provider-facing schemas
- Official core accessor surface: mode registry, command sanitizer, and adapter class lookup use `get_mode_registry()`, `get_command_sanitizer()`, and `get_inprocess_adapter()` directly. Removed registry, sanitizer, and adapter private aliases must not be reintroduced.
- Official turn snapshot boundary: `TurnSnapshotService` builds the provider `TurnSnapshot` after context assembly and active schema projection; provider requests consume `snapshot.messages` and `snapshot.tool_schemas`
- Official workflow package manifest read model: `WorkflowPackageManifest` describes package identity, supported modes/workflow states, tools, packs, resources, and diagnostics. The bundled C/C++ package manifest is derived from package-owned constants and exposed through `ExtensionManager`; it is not a public extension API and does not activate tools.
- Official capability read model: `CapabilityRegistry` describes tools, modes, local file resources, slash commands, model profiles, and workflow packages with provenance metadata. It does not activate tools, execute tools, load extensions, or replace `PermissionPolicy`.
- Official runtime configuration read model: `RuntimeConfigReducer` projects safe replayable runtime configuration from `transcript.jsonl`, including credential-free model profile metadata, registered tool names, model-visible active tool names, local resource revision metadata, capability counts, and provider snapshot records. It is diagnostic/replay state and does not replace extension activation, tool execution, resource reload, project extension loading, or permission policy.
- Official compaction read model: `CompactionJournal` builds safe `compact_boundary` and `compacted_history` transcript payloads, while `CompactionStateReducer` projects structured compact boundary state from those events. The reducer feeds restore results, managed sessions, protocol snapshots, and session snapshots, but it does not drive context selection or become a second history source.
- Official recovery read model: `RecoveryStateReducer` projects safe hosted-resume recovery markers from `recovery_marker` transcript events, including trusted-prefix counts, stop reasons, operation/compaction/runtime summaries, and diagnostics. It feeds restore results, managed sessions, protocol snapshots, and session snapshots, but it does not change restore rules or drive runtime policy.
- Official turn experience read model: `TurnExperienceReducer` projects safe completed, unverified, next-step, blocker, and last-failure state from transcript events. It feeds session snapshots and `session_finished` payloads for CLI/TUI/GUI display only; it does not decide loop continuation, validation policy, tool activation, permissions, or session history.
- Official offline runtime contract: `scripts/offline-runtime-contract.json` lists every runtime-invoked bundled external tool and release gate, including Python, Bash from MinGit, MinGit, ripgrep, Universal Ctags, the LLVM/Clang child executables, bundle-local C smoke validation, and Win7/WebView2 GUI smoke metadata. Bundle validators consume this contract instead of maintaining separate hard-coded tool lists.
- Official GUI bundle launcher: the GUI bundle includes a thin native Win32 launcher (`EmbedAgent.exe` / `embedagent-gui.exe`) for double-click startup, while Python, WebView2, LLVM/Clang, MinGit, ripgrep, and Universal Ctags remain explicit files in the portable bundle.
- Official frontend vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`
- Official GUI app-shell boundary: `GET /api/app/bootstrap` and `/api/app/workspaces*` expose GUI-owned workspace/app diagnostics, app commands, and local settings; this is separate from Agent Core session truth and from `GET /api/sessions/{id}/bootstrap`
- Official GUI session-list loading boundary: renderer session list loading is owned by `webapp/src/app-runtime/session-list-controller.js`; `App.jsx` composes that controller and must not directly fetch `/api/sessions` or dispatch `sessions_loaded`.
- Official GUI HTTP client boundary: shared JSON request/error handling lives in `webapp/src/app-runtime/http-client.js`; `App.jsx` imports `fetchJson` and must not define an inline HTTP helper or call browser `fetch` directly.
- Official GUI initial-load boundary: app bootstrap and session command
  capability warmup are started through
  `webapp/src/app-runtime/initial-app-load-controller.js`; `App.jsx` installs
  that controller and must not directly call `loadAppBootstrap()` or attach
  renderer-local warmup catch handlers.
- Official GUI socket-message boundary: raw WebSocket messages are handled by
  `webapp/src/app-runtime/socket-message-controller.js`, which combines pure
  effect derivation with `socket-effect-executor.js`; `App.jsx` must not
  directly call `deriveSocketMessageEffects`, append session transport events,
  branch on reload recovery, or loop over effect actions/loaders.
- Official GUI session-transport state bridge: current transport-state read,
  sync, replace, update, and runtime reset construction live in
  `webapp/src/app-runtime/session-transport-handle.js`; `App.jsx` owns the
  React state cell but must not keep a parallel `sessionTransportRef` or inline
  transport replace/update helpers.
- Official GUI interaction response busy-state bridge: pending response request
  ids are normalized, synced, read, and updated through
  `webapp/src/app-runtime/responding-request-ids-handle.js`; `App.jsx` owns the
  React state cell but must not keep a parallel `respondingRequestIdsRef` or
  inline request-id normalization helpers.
- Official GUI active-workspace data boundary: the post-activation read-model refresh fanout for sessions, session capabilities, workspace files, and local status surfaces is owned by `webapp/src/app-runtime/active-workspace-data-loader.js`; `App.jsx` wires dependencies but must not inline that reload `Promise.all`.
- Official GUI panel-resize boundary: pointer/DOM logic for sidebar and right-panel resizing lives in `webapp/src/app-runtime/panel-resize-controller.js`; `App.jsx` wires resize handlers but must not mutate `documentElement.style` directly.
- Official GUI timeline-scroll boundary: Timeline bottom-follow state and
  scrollTop/scrollHeight/clientHeight DOM logic live in
  `webapp/src/app-runtime/timeline-scroll-controller.js`; `App.jsx` wires the
  Timeline ref and scroll callback but must not inspect or mutate Timeline
  scroll fields directly.
- Official GUI backend route boundary: `server.py` is the GUI backend composition root; HTTP route families live in `routes_app.py`, `routes_sessions.py`, `routes_terminal.py`, `routes_source_control.py`, and `routes_preview.py`. New route families should be delegated through focused modules rather than concentrated back into `server.py`.
- Official GUI thread lifecycle boundary: GUI `rename`, `fork`, and `archive` actions flow through the session lifecycle facade and update session summary/projection metadata for app thread lists; action labels, disabled reason labels, and prompt/confirm/success/empty/failure copy come from app-shell action descriptors. Missing action labels remove actions from the visible rail, and missing notice copy remains absent rather than synthesized from action ids or labels. Lifecycle actions do not rewrite transcript history, own workflow state, activate tools, decide permissions, load extensions, or create source-control checkpoints.
- Official GUI browser-dialog boundary: native prompt/confirm access used by thread lifecycle actions lives in `webapp/src/app-runtime/browser-dialog-service.js`; `App.jsx` injects that service and must not call `window.prompt` or `window.confirm` directly.
- Official GUI workbench keyboard boundary: global keydown handling, Escape
  cancellation, composer-focus detection, and app-shell keybinding resolution
  live in `webapp/src/app-runtime/workbench-keyboard-controller.js`;
  `App.jsx` installs the controller and must not own keydown listeners or
  shortcut resolution logic directly.
- Official GUI renderer-state boundary: thread/session selection, session
  summaries, and history-integrity display state live in
  `webapp/src/session-runtime/thread-state.js`, composer draft text lives in
  `webapp/src/composer/composer-state.js`, terminal display buffers remain in
  `webapp/src/terminal/`, and workbench surface persistence remains in
  `webapp/src/workbench/`. Root-level GUI state must not reintroduce
  `sessions`, `currentSessionId`, `composer`, `historyIntegrity`, or retired
  sidebar tab sidecars as parallel fields.
- Official GUI visual-debug boundary: `?visual_debug=1` may expose
  `window.__EMBEDAGENT_VISUAL_DEBUG__`, but URL-gated fixture installation is
  owned by `webapp/src/app-runtime/visual-debug-controller.js`; fixture helpers
  expand private `dev_fixture_*` descriptors into ordinary product reducer
  actions. `App.jsx` must not import `installVisualDebugFixtures` or read
  `window.location.search` for this hook, and product reducers do not define
  `visual_*fixture` cases.
- Official GUI static asset policy: generated files under
  `src/embedagent/frontend/gui/static/` remain committed release artifacts for
  the current offline packaging model; `webapp/src/` is the review source of
  truth and `npm run build` refreshes the generated assets after source
  changes.
- Official GUI terminal boundary: the terminal bottom drawer is a GUI app-shell hosted, thread-scoped surface implemented with Windows 7-compatible Python stdlib subprocess pipes. It is not a full PTY, does not add runtime dependencies, and does not write transcript history, telemetry, workflow state, source-control checkpoints, or Agent Core policy.
- Official GUI source-control boundary: the Source Control right-panel and composer Branch Toolbar are GUI app-shell hosted, active-workspace surfaces. They use bundled/workspace MinGit through a read-only backend service for local Git status and file diffs only; surface chrome/copy is declared under `capabilities.source_control.chrome`, including group order, group/provider labels, file status badge labels, and `branch_toolbar` copy. Source-control/terminal/preview API helpers must not carry renderer-local request-failure copy; missing backend error messages fall through to app-shell chrome. Missing group/provider labels must not fall back to raw protocol ids as visible UI. They do not implement remote providers, push/pull, staging, commit, checkpoint mutation, transcript writes, workflow state, telemetry, permission policy, runtime reducers, provider config, extension loading, or Agent Core behavior.
- Official GUI composer menu boundary: the Composer slash-command and file-context menu is GUI app-shell display state. Menu aria labels, empty states, path/kind labels, fallback command group copy, default slash-command group id, and composer hint-bar descriptors are declared under `capabilities.chrome.composer`, while slash command group titles reuse `capabilities.command_palette.groups`; slash menu items must come from command capability projection, and the renderer must not keep static command hint fallbacks, hard-coded hint item lists, a parallel command/path menu string table, or synthesize missing command groups as `"command"`.
- Official GUI timeline boundary: the Timeline is a GUI app-shell display projection over session bootstrap/live activities. Log aria labels, empty/history/termination copy, work-group labels, activity-row labels/status/timer templates, work-row default heading/icon/status labels, changed-files card labels, and structured tool-detail field/section labels are declared under `capabilities.chrome.timeline`; the T3 timeline projection carries display data such as `createdAt`, `completedAt`, `interrupted`, detail field keys, and detail section kinds without precomputing renderer chrome labels. Review-result rows are selected from structured review payloads, not slash command names such as `/review`; command-result row labels come from explicit payload labels or app-shell `commandDefaultName`, not synthesized `/${commandName}` strings. The renderer must not turn timeline chrome into session-history truth, workflow state, provider/runtime policy, permission policy, telemetry, extension loading, or Agent Core behavior.
- Official GUI file-preview boundary: the File Preview right-panel is a GUI app-shell hosted, read-only surface over workspace file content loaded only through the renderer `file-preview-controller.js` after the active app shell declares the File Preview surface. `App.jsx` wires `filePreviewController.openFile` directly and must not keep an `openFile` wrapper. Its chrome/copy, metadata labels, fallback messages, and language labels are declared under `capabilities.surfaces.chrome.file_preview`; it does not save files, write transcript/workflow/reducer state, decide permissions, load extensions, or add Agent Core behavior.
- Official GUI diff-panel boundary: the Diff right-panel is a GUI app-shell hosted display surface for already-projected unified diff text. Command results open it from structured `data.diff` payloads rather than slash command names such as `/diff`, and timeline/manual diff opening is delegated to renderer `diff-surface-controller.js` instead of `App.jsx` constructing diff surface state directly. `App.jsx` wires `diffSurfaceController.open` directly and must not keep an `openDiffSurface` wrapper. Its default title, empty state, controls, file rail labels, collapse labels, and source-control diff title template are declared under `capabilities.surfaces.chrome.diff_panel`; workbench tab titles come from explicit diff payload titles or the app-shell surface descriptor, not a renderer `"diff"` fallback. It does not own source-control policy, workflow state, transcript history, permission policy, reducers, extension loading, or Agent Core behavior.
- Official GUI preview boundary: the Preview right-panel is a GUI app-shell hosted, local-only surface. Renderer Preview open/refresh/external-open orchestration lives in `preview-controller.js`, which preflights the active app-shell Preview surface before invoking backend preview routes; `App.jsx` wires those controller methods directly and must not keep `openPreview*` wrappers. Its backend preview service accepts loopback HTTP URLs only, probes them with Python stdlib networking, may open the same local URL in the system browser, and does not execute browser automation, contact remote hosts, write transcript/workflow/reducer state, or add Agent Core behavior.
- Official session-history model: `transcript.jsonl -> Session -> SessionHistoryAssembler -> /api/sessions/{id}/bootstrap`
- Official session-operation model: schema v2 `operation_started` / `operation_finished` / `operation_interrupted` events are the durable runtime operation truth; legacy `step_started`, `tool_call`, `tool_result`, and `loop_transition` events remain session replay/history events, not operation-state inference inputs. Current operation families include turns, agent steps, context assembly, context snapshots, provider requests, tool calls, pending interactions, workflow patches, and save points. Restore projections close unfinished operations as interrupted, while live session snapshots preserve active operations in `operation_diagnostics`.

The product no longer treats the old `code` mode or legacy todo-management workflow as the architecture baseline.

## Documentation Model

- `docs/superpowers/` stores design and implementation materials for the current slice only; completed slice materials move to `docs/archive/` after durable conclusions are synchronized into active docs.
- `docs/` active documents store the long-lived project source of truth.
- `docs/archive/` stores completed slice artifacts and historical references.

## Documentation Entry Points

- `docs/README.md`
- `docs/pre-release-architecture-debt-audit.md`
- `docs/documentation-governance.md`
- `docs/documentation-style-guide.md`
- `docs/workflows/code-doc-sync.md`
- `docs/references/glossary.md`

## Main Components

- `src/embedagent_core/query_engine.py`
  The session-scoped facade that owns session initialization, interaction suspend/resume, transcript integration, and live session mutation.
- `src/embedagent_core/agent_lifecycle.py`
  Durable lifecycle journal for schema v2 operation events, save points, pending interaction lifecycle, and context operation payload helpers.
- `src/embedagent_core/agent_kernel.py`
  Internal lifecycle kernel for turn frames and pending interaction creation/resolution boundaries.
- `src/embedagent_core/agent_loop.py`
  Pi-style open continuation loop for agent steps, provider/context attempts, compact retry, tool batches, guard stops, abort transitions, and explicit loop safety-limit compatibility transitions.
- `src/embedagent_core/guard.py`
  ProgressGuard for evidence-fingerprint based no-progress/runaway protection across tool actions and observations.
- `src/embedagent_core/agent_loop_continuation.py`
  Internal continuation decision policy for open-loop stop, continue, abort, and safety-limit behavior.
- `src/embedagent_core/agent_tool_action_service.py`
  Non-LLM action executor for active-tool checks, extension pre/post hooks, permission-gated runtime dispatch, path write guards, and extension-owned tool calls.
- `src/embedagent_core/agent_extension_host.py`
  QueryEngine-side extension host for prompt/context hooks, workflow state initialization, dynamic tool registration, explicit active schema projection, tool-call/tool-result hooks, and workflow patches.
- `src/embedagent_core/agent_event_bus.py`
  Source-aware internal event bus for extension observer/reducer dispatch and event-specific reducer stopping.
- `src/embedagent_core/turn_snapshot.py`
  Frozen provider-request input built from context messages, active schemas, workflow state, runtime metadata, and capability projections.
- `src/embedagent_core/turn_snapshot_service.py`
  Provider snapshot builder and safe snapshot metadata projector for runtime config, capabilities, prompt units, model profile, and context stats.
- `src/embedagent_core/prompt_assembly_service.py`
  Workflow prompt append/dedupe service for generic `workflow_prompt` system messages.
- `src/embedagent_core/ports.py`, `src/embedagent_core/policies.py`, and
  `src/embedagent_core/tool_contracts.py`
  Abstract host-service, mode/path-policy, and tool-runtime contracts injected
  by product composition.
- `src/embedagent_core/compaction_journal.py`
  Safe compact-boundary and compacted-history transcript payload builder.
- `src/embedagent_core/capabilities.py`
  Non-executing capability read model for runtime tools, local file resources, slash commands, model profiles, and workflow packages.
- `src/embedagent_core/runtime_config.py`
  Reducer-backed runtime configuration projection for model profile metadata, registered and active tool names, local resource revisions, capability counts, and provider snapshot diagnostics.
- `src/embedagent_core/compaction_state.py`
  Reducer-backed compaction projection for compact boundary metadata, safe file activity, evidence refs, and restore diagnostics.
- `src/embedagent_core/recovery_state.py`
  Reducer-backed recovery projection for hosted resume markers, trusted prefix metadata, and restore diagnostics.
- `src/embedagent_core/turn_experience.py`
  Reducer-backed turn experience projection for completed work, unverified changes, blockers, validation failures, and suggested next steps.
- `src/embedagent/telemetry.py`
  Local-only safe telemetry envelope helper that redacts prompt/source/output/credential fields before future sinks see metadata.
- `src/embedagent_core/extensions.py`
  In-process extension contract and manager for workflow prompt/tool/state hooks.
- `src/embedagent/agent_applications.py`
  Hosted scenario application boundary, manifest registry, selected-application loader, profile, mode policy, extension manager, and workflow refreshers.
- `src/embedagent/workflow_packages/c_cpp/application.py`
  Default C/C++ scenario application factory that installs the bundled workflow extension outside `QueryEngine`.
- `src/embedagent/session_runtime.py` and `src/embedagent/session_projector.py`
  Runtime host state plus pure snapshot/bootstrap projection from session truth.
- `src/embedagent/workflow_packages/c_cpp/`
  Default C/C++ workflow extension internals: mode registry, discipline/phase modeling, prompt stack, task graph, workflow projection, and session task snapshot persistence.
- `src/embedagent/tools/`
  Official tool runtime, catalog metadata, managed environment discovery, and tool execution.
- `src/embedagent/context.py`
  Context policy, reducer registry, replacement logic, and compaction pipeline.
- `src/embedagent_core/permissions.py`
  Structured permission categories, rule loading, rule matching, and explanation rendering.
- `src/embedagent_host/inprocess_adapter.py`
  Product-facing adapter used by CLI/TUI/GUI; it bridges sessions, snapshots, hosted services, and the shared extension manager.
- `src/embedagent_host/hosted_command_service.py` and `src/embedagent_host/hosted_interaction_service.py`
  Hosted slash-command and permission/user-input interaction services used by the product adapter.
- `src/embedagent/session_history.py`
  Canonical GUI history assembler built from transcript-backed `Session` state.
- `src/embedagent/core/` and `src/embedagent/protocol/`
  Stable frontend/core contract layer.
- `src/embedagent/frontend/`
  TUI and GUI shells built on the same core contract.

## Official Tools

The default C/C++ workflow tool vocabulary is centered on:

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

`bash` is the single shell primitive for explicit command execution. Recipe tools stay declarative and readiness-aware; if a project has no ready recipe, the model should inspect the workspace or use `bash` deliberately instead of forcing a wrapped build action. Git/status helpers remain supporting capabilities where appropriate, but the architecture no longer treats duplicate file/build/todo wrappers as first-class workflow primitives.

These tools are registered in the runtime catalog. Built-in mode prompts expose only workflow-neutral permission/write contracts; the default C/C++ harness extension activates recipe, quality, evidence, and task-status tools through focused packs.

Runtime schema filtering no longer activates the default harness pack on its own. Product paths that need the full default C/C++ tool set combine the mode contract with `ExtensionManager` active tools, then request schemas by explicit tool names.

The runtime catalog is also the source of safe GUI presentation metadata. Tool
entries may declare `metadata.preview_arg` and `metadata.changed_path_arg`, and
session capabilities project those fields to frontends so timeline tool
previews and changed-file summaries can adapt to different base or specialized
agents without hard-coded `bash`, `read_file`, `write_file`, or workflow-tool
name tables.

In-process extensions may register additional `ToolDefinition` objects into the shared runtime catalog. Registration records `source_type` and `source_id`, but a dynamic tool is model-visible only when activated through the shared `ExtensionManager` active-tool path and remains subject to `PermissionPolicy`.

Local resource reload is file-only. Skills and prompts are surfaced as discovered resources, while `.embedagent/recipes/*.json` contributes workflow-neutral recipe definitions. The default C/C++ workflow package normalizes runnable workspace recipes into the `list_recipes` / `run_recipe` path at its own aggregation boundary. Skills may include Agent Skills-style frontmatter (`name`, `description`, `disable-model-invocation`); visible skills are summarized once through the hosted local skill listing prompt unit, and `/skill:<name> [args]` expands the skill Markdown body into the next user turn. Prompt files are expanded only through explicit `/prompt:<name-or-path> [args]` invocation. Reloading resources records transcript-backed diagnostics and does not execute project-local Python code. `author_local_capability` can create local resource files and disabled extension skeletons, but the caller must still use resource reload or explicit extension loading as separate follow-up operations.

Project-local Python extensions are a separate, explicit opt-in path under `.embedagent/extensions/<name>/`. They require `extension.json` with `enabled: true` and a permissions list, load only a workspace-bound `extension.py` entrypoint, receive a narrow API object, and are surfaced in session snapshots under `extensions.project_extensions`. Hook methods must be declared from `extension_capabilities()` with `api.ExtensionCapability`; undeclared methods are inert. They cannot replace built-in tools and any dynamic tools they register remain metadata-classified and permission-gated.

## Development Constraints

- Do not require Docker, WSL, VS Code, Node.js-at-runtime, or online services.
- Keep runtime compatible with Python `>=3.8,<3.9`.
- The offline bundle must contain every runtime dependency it uses.
- Optional intranet integrations must stay opt-in extension/provider/sink capabilities; network failure must not prevent offline use.
- Runtime-invoked external tools must be represented in `scripts/offline-runtime-contract.json` and validated by the packaging gates.
- A clean Windows 7 machine must be able to unpack and run the bundle without preinstalled tools.

## Pre-Merge Architecture Gate

Before merging GUI, Agent Core, permission, extension, workflow-package, or frontend-protocol changes, run this gate from the repository root:

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

`npm run build` is required whenever webapp source changes, and the generated GUI static assets must be committed with the source change.

Windows 7 and offline-delivery claims require real bundle smoke evidence on the target-style bundle. Local development tests are useful regression evidence, but they are not a substitute for clean Win7/WebView2 bundle smoke results.

## Read In This Order

For implementation work, start with:

1. `README.md`
2. `AGENTS.md`
3. `docs/overall-solution-architecture.md`
4. `docs/implementation-roadmap.md`

## Status

Current architecture cutover status:

- Runtime promotion: completed
- Mode vocabulary cutover: completed
- Context/intelligence cutover: completed
- Permission/task truth cutover: completed
- Agent core ownership cutover: completed
- Agent Core boundary extraction: completed
- Frontend/protocol officialization: completed
- Session-history single-source cutover: completed
- Pi-inspired minimal Core Phase A durable operation log: completed
- Pi-inspired minimal Core Phase B HookBus/reducer registry: completed
- Pi-inspired minimal Core Phase C AgentKernel lifecycle extraction: completed
- Pi-inspired minimal Core Phase D default C/C++ workflow package ownership: completed
- Pi-inspired minimal Core Phase E local self-extension authoring: completed
- Pi-inspired minimal Core Phase F repo-side offline bundle validation: completed
- Pi-inspired minimal Core Phase G turn snapshot / capability registry foundation: completed
- Pi-inspired minimal Core Phase H runtime configuration reducer: completed
- Pi-inspired minimal Core Phase I workflow package manifest/read model: completed
- Pi-inspired minimal Core Phase J structured compaction state: completed
- Pi-inspired minimal Core Phase K recovery state: completed
- Pi-inspired minimal Core Phase L pack compatibility cleanup: completed
- Pi-inspired minimal Core Phase M core alias cleanup: completed
- Remaining release evidence: clean Win7/WebView2 bundle smoke and broader real C/C++ project validation before release claims; the pre-release debt cleanup slices are closed, and repo-side C smoke validation is contract-backed through `validate-cpp-smoke.py`

## Verification

Recent focused verification includes:

- Python unit tests for harness, query engine, adapter, GUI backend, and tool runtime
- Webapp helper/runtime tests
- GUI static asset rebuild from current webapp source

## Repository Scope

This repository is not trying to be:

- a browser automation platform
- an online search agent
- a plugin marketplace
- a general-purpose cloud coding service

It is a focused native Agent IDE core for offline C engineering workflows.
