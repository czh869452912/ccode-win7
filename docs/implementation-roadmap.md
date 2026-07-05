# Implementation Roadmap

## 1. Purpose

This document tracks the stable sequencing strategy for EmbedAgent.

It is not a historical backlog dump.
It describes the current implementation order and the next remaining priorities.

## 2. Sequencing Principles

- Keep Python runtime compatible with `>=3.8,<3.9`
- End each major program with a runnable, verifiable milestone
- Prefer one promoted architecture path over long-lived compatibility branches
- Keep current docs aligned with current code
- Treat pre-release internal compatibility as disposable; delete or replace old
  session, timeline, GUI reducer, and extension-hook shapes instead of adding
  new adapters over them

## 3. Completed Core Programs

The following core programs are now complete in the current architecture baseline:

1. Runtime promotion
2. Mode vocabulary cutover
3. Context / intelligence cutover
4. Permission / task truth cutover
5. Frontend / protocol officialization
6. Agent core ownership cutover

This means the repository now has one official execution spine centered on:

- `build` instead of `code`
- `TaskGraph` instead of prompt-only todo flow
- `bash` plus readiness-aware `run_recipe` / `report_quality_v2` instead of legacy duplicate verify tools in product paths
- frontend `tasks` vocabulary instead of the retired todo vocabulary

Recent workflow-boundary work has split the generic Agent Core from hosted
product composition and default C/C++ behavior:

- `src/embedagent_core/` now contains the workflow-neutral session engine,
  extension boundary, permission policy, reducers, turn snapshots, and
  capability read models
- `embedagent_core` no longer imports `embedagent`, `embedagent_host`, GUI/TUI,
  or workflow package modules
- product-owned concrete services are injected through Core ports
- deleted product-level compatibility paths are intentionally absent
- `src/embedagent_host/` now contains hosted product composition, default
  extension assembly, hosted command/interaction services, and adapter glue
- `src/embedagent/workflow_packages/c_cpp/` now contains the first-party C/C++
  workflow package
- `src/embedagent_core/extensions.py` now provides the in-process workflow extension boundary
- the C/C++ harness is wrapped as the default built-in workflow extension
- `QueryEngine` no longer imports or instantiates `TaskGraph` directly
- `QueryEngine` no longer imports or constructs the default C harness extension; hosted paths install selected scenario applications through `src/embedagent/agent_applications.py`, with the default C/C++ application factory in `src/embedagent/workflow_packages/c_cpp/application.py`
- `Session.workflow_state` is the generic workflow-state carrier; `Session.task_graph` has been removed and default C harness graph state is owned behind `CHarnessWorkflowExtension`
- `SessionSnapshotProjector` and live frontend task APIs now project harness task fields from `Session.workflow_state["workflow"]`
- the obsolete extracted turn-orchestrator strategy has been removed; `AgentLoop` is the only turn-loop owner and `AgentToolActionService` is the only non-LLM action execution owner
- `src/embedagent/workflow_packages/c_cpp/workflow_projection.py` now owns the C harness to generic workflow payload adapter
- `InProcessAdapter` no longer constructs `HarnessRunner` directly; managed-session workflow refresh is delegated through the selected `AgentApplication`, and the bundled C/C++ application delegates task-snapshot persistence to the built-in C harness extension
- `QueryEngine` now asks for schemas using explicit active tool names through `ToolRuntime.schemas_for(...)`, so default harness pack activation is owned by the workflow extension boundary
- Agent profile contracts now own hosted scenario mode/base-tool metadata and GUI mode capability projection, while workflow package contracts own scenario-specific workflow tools, package-owned tool names, and packs; the global `embedagent.modes` facade uses the generic base profile, and selected hosted applications provide specialized mode policy; `ToolRuntime.schemas_for(...)` no longer performs implicit mode fallback when active tool names are omitted
- `CORE_PACK` is the minimal file/search/editing/shell foundation; build/debug/verify packs keep harness-only recipe, quality, evidence, and task-status tools explicit
- built-in mode `allowed_tools` no longer own default harness workflow tools; recipe, quality, evidence, and task-status tools are activated by the C harness extension
- `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` is now the single runtime schema projection entry point; default-harness paths use extension-active explicit tool names, and omitted `tool_names` project no provider-facing schemas
- `InProcessAdapter` now owns one `ExtensionManager` shared with session-scoped `QueryEngine` and frontend tool catalog visibility
- `ExtensionManager` now carries generic diagnostics, resource discovery hooks, context hooks, tool-call/tool-result hooks, and dynamic in-process tool registration through explicit `ExtensionCapability` records returned by `extension_capabilities()`
- local file resources under `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes` can be refreshed through the runtime, adapter, slash command, and GUI/core API; root workspace recipe listing is workflow-neutral and does not assign default C/C++ tool names, while the bundled C/C++ workflow package owns CMake/Make/Ninja detection plus `list_recipes` / `run_recipe` projection; visible Agent Skills-style Markdown resources are summarized through one lightweight prompt unit, skill bodies expand only through `/skill:<name> [args]`, and prompt bodies expand only through `/prompt:<name-or-path> [args]`
- manifest-gated project-local Python extensions can be loaded from enabled `.embedagent/extensions/<name>/extension.json` manifests by hosted product paths and are registered into the shared `ExtensionManager`; hooks/tools are active only when declared with `api.ExtensionCapability`
- `AgentExtensionHost` now centralizes QueryEngine-side extension dispatch, dynamic tool registration, extension-aware active schema projection, context patches, tool-call hooks, tool-result hooks, and extension-owned tool handling
- `AgentEventBus` now provides the internal source-aware observer/reducer boundary for explicitly declared extension capabilities; method-name hook compatibility is no longer a product path
- `AgentLifecycleJournal` now owns durable lifecycle operation writes, transition save points, pending interaction lifecycle operation events, and context operation payload helpers
- `AgentKernel` now owns user/command/resume turn frames and pending interaction create/resolve boundaries behind the session facade
- `AgentToolActionService` now owns non-LLM tool action execution, including active-tool checks, extension pre/post hooks, `PermissionPolicy`, pending permission/user-input actions, mode-switch proposals, path write guards, runtime dispatch, extension-owned tool calls, resumed action execution, and workflow-patch capture
- `AgentLoop` now owns Pi-style open turn-loop continuation behind `QueryEngine`, including agent steps, context/provider attempts, active schema requests through `AgentExtensionHost`, compact retry, tool batch interruption, guard stops, abort, and explicit loop safety-limit compatibility transitions; `ProgressGuard` uses action-plus-observation evidence fingerprints for no-progress/runaway detection instead of repeated tool-name stopping; ordinary command/build/test failures are diagnostic tool results for the next model turn rather than automatic guard-stop conditions; `QueryEngine` no longer owns `_run_loop_impl`, `_run_loop`, `_is_completion_signal`, private active-tool schema wrappers, or action-execution forwarding wrappers, and hosted defaults no longer stop merely because eight model/tool cycles were used
- `ToolRuntime` construction is now workflow-neutral; the bundled C/C++ workflow package registers recipe, quality, evidence, and task-status tools with metadata through `CHarnessWorkflowExtension.register_tools(...)`
- C/C++ workflow context reducers have moved out of Core `ReducerRegistry`; harness-owned reducers now cover recipe results, quality reports, failing evidence, and task status through `CHarnessWorkflowExtension.register_context_reducers(...)`
- workflow prompt descriptors now use generic `WorkflowPrompt` naming and new prompt messages use `workflow_prompt`; old harness prompt names and compatibility aliases are no longer active prompt assembly kinds
- `propose_mode_switch` is no longer projected as an unconditional model tool; it appears only when explicitly activated through the active-tool boundary
- `ToolCatalogEntry` now keeps internal execution, presentation, and context-policy facets while preserving the legacy flat catalog payload for protocol/frontend compatibility
- C/C++ workflow pack definitions now live only under `src/embedagent/workflow_packages/c_cpp/packs.py`; the obsolete tooling-package compatibility export has been removed
- Pi-inspired minimal Core Phase A durable operation log, Phase B HookBus/reducer registry, Phase C AgentKernel lifecycle extraction, Phase D default C/C++ workflow package ownership, Phase E self-extension authoring loop, Phase F repo-side offline bundle validation, Phase G turn snapshot / capability registry foundation, Phase H runtime configuration reducer, Phase I workflow package manifest/read model, Phase J structured compaction state, Phase K recovery state, Phase L pack compatibility cleanup, Phase M core alias cleanup, Phase N agent application manifest/capability projection, and the Pi-style prompt-surface/resource/runtime-state alignment slice are complete
- the Pi-style enterprise/intranet capability boundary foundation is implemented: runtime tool catalog metadata is the source of truth for permission category, unknown or invalid categories fall back to ask-by-default `other`, `network` and `telemetry` permission categories are recognized by policy/runtime/extension metadata, and `embedagent.telemetry` provides local safe telemetry envelopes while future intranet Git, custom service, provider, organization-local catalog, and sink work stays optional and outside Agent Core
- stale core compatibility aliases have been removed; current code uses `get_mode_registry()`, `get_command_sanitizer()`, and `get_inprocess_adapter()` directly instead of removed registry, sanitizer, or adapter private aliases
- `TurnSnapshot` is now the explicit frozen provider-request input; `TurnSnapshotService` builds it after context assembly and active schema projection, then provider requests consume `snapshot.messages` and `snapshot.tool_schemas`
- `CapabilityRegistry` is now the non-executing read model for tools, modes, local file resources, slash commands, model profiles, and workflow packages; activation and execution remain owned by `AgentExtensionHost` / `ExtensionManager` and `ToolRuntime` / `AgentToolActionService`
- `RuntimeConfigReducer` now projects safe runtime configuration from transcript events, including model profile metadata, registered tool names, active model-visible tool names, local resource revision metadata, capability counts, and provider snapshot records
- `WorkflowPackageManifest` now describes the bundled C/C++ workflow package identity, declared tools, packs, supported modes/workflow states, and resource scopes as read-only non-executing control-plane data exposed through the shared extension manager
- `TurnExperienceReducer` now treats validation state as explicit tool-result metadata, not a command-name heuristic; build/test/compiler command strings remain diagnostic evidence for the next model turn unless the owning workflow/tool marks the result as validation
- Hosted `/review`, project memory, and workspace intelligence now classify recipe, test, coverage, diagnostic, and quality-gate evidence through workflow-neutral payload fields in `src/embedagent/tool_evidence.py`; they no longer import default C/C++ workflow tool constants
- `CHarnessWorkflowExtension` now owns default C/C++ workspace recipe projection through an explicit `workspace_recipes` capability; `src/embedagent/workspace_recipes.py` remains a generic local resource read model without CMake/Make/Ninja detection
- `SelfExtensionAuthoringService` and `author_local_capability` can generate local skills, prompts, recipes, and disabled-by-default project extension skeletons without reloading resources or loading Python code
- `scripts/offline-runtime-contract.json` is now the single repo-side contract for runtime-invoked bundled external tools; `validate-offline-bundle.ps1` and `check-bundle-dependencies.py` consume it for Python, Bash from MinGit, MinGit, ripgrep, Universal Ctags, and LLVM/Clang child executable validation
- Slice 6 completed the documentation cutover for self-extensible Agent Core: active source-of-truth docs and module docs now treat local offline self-extension as official architecture while keeping marketplaces, online installs, dependency installation, built-in tool replacement, and multi-agent orchestration out of scope
- `HarnessStateSynchronizer` has been removed; product refresh uses `AgentApplication.refresh_managed_session()`, with the default C/C++ application delegating to `CHarnessWorkflowExtension.refresh_managed_session()` internally
- `StreamingToolExecutor` now window-schedules parallel read batches so failure/discard semantics are deterministic

Recent stabilization work has also completed the GUI session-history single-source cutover:

- `transcript.jsonl` is now the only durable session-history truth
- GUI history is serialized from transcript-backed `Session` state
- GUI activation now uses one `/api/sessions/{id}/bootstrap` payload instead of split snapshot/timeline fetches; bootstrap history now includes nested diagnostic `turns` plus direct T3-style `activities`, and the React runtime consumes `history.activities` rather than reprojecting `turns` or transport events
- the old durable timeline-backed session-history store and review/event replay
  paths have been removed; there is no session event replay HTTP route, and the active T3
  timeline consumes bootstrap history plus live reducer actions rather than
  transport event-log history
- live GUI permission/user-input activity now comes from backend-owned
  `session_event` messages emitted from Core turn events; raw
  `permission_request` / `user_input_request` WebSocket messages only drive the
  blocking interaction UI and response path, so the renderer no longer
  synthesizes local interaction-created activity records
- The 2026-06-26 Pi/T3 residual debt cleanup removed timeline-shaped snapshot
  fields, the old session timeline API, and core flat timeline naming in favor of
  bootstrap/history projections; it also extracted hosted bootstrap,
  capability, slash-command, prompt-assembly, and turn-snapshot services so
  adapter/core facades stay small.
- The 2026-06-27 follow-up cleanup finished the next adapter/core split:
  GUI backend HTTP registration now lives in focused route modules;
  `HostedCommandService` owns slash-command dispatch, command-result emission,
  and command-owned tool execution; `HostedInteractionService` owns permission
  and user-input response glue; `TurnSnapshotService`,
  `PromptAssemblyService`, and `CompactionJournal` own provider snapshot,
  workflow prompt, and compaction payload assembly outside `QueryEngine`.

Recent GUI app-shell work has established the first standalone-app boundary:

- `/api/app/bootstrap` and `/api/app/workspaces*` now return a GUI-owned
  app-shell envelope for workspace registry projection, active workspace
  metadata, safe host/runtime/renderer diagnostics, app-level command metadata,
  app surfaces, and GUI-local settings
- frontend app-shell normalization/reducer helpers live under
  `webapp/src/app-shell/` and drive Settings/Diagnostics right-panel surfaces
- GUI workbench commands, right-panel launchers, bottom-drawer tabs, and
  keybinding targets are filtered from `/api/app/bootstrap` app-shell
  capabilities; app-shell app/workspace/workbench commands, surfaces, and
  keybindings are descriptor records carrying display, ordering, command,
  slash, shortcut, and safety metadata, while renderer-local surface
  registries now provide only known renderer mounting details through derived
  helper functions rather than exported fixed id lists, and do not invent
  visible app entrypoints when the `capabilities` object or relevant descriptor
  arrays are missing; command descriptors without explicit visible labels stay
  out of workbench command lists and command-palette rows, and dynamic slash
  commands require explicit `label`, `usage`, or `slash` metadata rather than
  command-id fallback copy; commands in undeclared or untitled palette groups
  remain hidden rather than using title-cased group ids; missing command row
  description/meta copy remains empty rather than falling back to command ids;
  surface command row descriptions come from surface descriptors rather than
  surface/drawer ids;
  session/workspace palette row leading markers come from command-palette label
  descriptors and remain empty when absent;
  command-palette group leading markers come from explicit group descriptors
  and are not synthesized from group titles;
  command-palette shortcut key labels and separators come from
  `command_palette.labels` rather than renderer-local platform-label defaults;
  right-panel surface open titles prefer the active surface descriptor and are
  no longer derived by stripping English command label prefixes;
  right-panel surface open behavior is selected by renderer-local `openKind`
  metadata rather than fixed surface-id branches in the controller, and
  supported `openKind` values route through a handler registry rather than a
  controller switch;
  App-level file, preview, and Files-browser open flows call semantic
  right-panel controller methods rather than dispatching concrete right-panel
  resource surface kinds;
  right-panel tab activation side effects are selected by renderer-local
  `activationKind` metadata through
  `RIGHT_PANEL_ACTIVATION_HANDLERS[definition.activationKind]` in
  `right-panel-controller.js` rather than inline App surface-id or terminal
  session branches;
  bottom-drawer surface commands may also carry descriptor-owned dispatch
  records, and the Terminal drawer opens through `terminal.ensure_open` rather
  than a renderer branch on `drawer: "terminal"`;
  bottom-drawer body selection uses renderer-local `bodyKind` metadata for
  supported surfaces, and stale declarations without a renderer body are
  removed instead of being shown through a misleading fallback; supported body
  kinds route through `BOTTOM_DRAWER_BODY_RENDERERS` rather than a component
  switch;
  bottom-drawer activation side effects use renderer-local `activationKind`
  metadata instead of drawer-kind branches in the terminal controller, and
  supported activation kinds route through a handler registry rather than a
  controller switch; terminal-controller right-panel surface validation and
  action payload assembly now route through `TERMINAL_SURFACE_KIND` and
  `terminalSurfaceActionInput(...)` instead of repeated surface-kind checks;
  right-panel body selection now follows the same renderer metadata path
  instead of branching on fixed surface kind strings in
  `RightPanelSurfaceBody`, and supported body kinds route through
  `RIGHT_PANEL_BODY_RENDERERS` rather than a component switch; body definition
  lookup is scoped by active app-shell capabilities, and hidden resource
  surfaces such as `file` are backend-declared with `launcher=False` /
  `command=False` rather than renderer-only body fallbacks;
  generic `SurfacePanel` content is selected by renderer-local `panelKind`
  metadata rather than surface-id branches;
  surface descriptors without explicit titles remain
  diagnostic capability records and do not enter visible launchers or surface
  commands; persisted workbench surface state is also re-sanitized
  after app bootstrap or workspace switch against those app-shell capabilities,
  shallow persisted surface fields are normalized by the renderer-local
  surface registry rather than `ui-state.js` file/terminal branches, and
  capability cleanup uses `persistedSurfaceDefinitions(appCapabilities, placement)`
  plus registry-declared `persistedRelatedKinds` rather than UI-state
  `files -> file` expansion; per-kind
  surface instance metadata is initialized through `SURFACE_INITIALIZERS[kind]`
  rather than `makeSurface(...)` file/terminal/preview branches, and
  right-panel open-time preparation routes through
  `SURFACE_OPEN_PREPARERS[surface.kind]` rather than `openSurface(...)`
  file/preview branches; right-panel surface-local pane operations route
  through `SURFACE_PANE_HANDLERS[surface.kind]` rather than reducer-level
  terminal kind branches;
  app bootstrap now also carries a safe selected-agent application registry and
  empty-state read model before a workspace/core exists, then defers to the
  active core's capability projection after workspace activation. This lets the
  GUI adapt for generic or specialized agents before a session is opened.
  Selected agent application manifests also declare `metadata.appShell`
  allow-lists for app commands, surfaces, keybinding targets, palette groups,
  and disabled GUI capability ids; `AppShellService` applies those lists to the
  injected spec so the Generic Agent does not inherit Preview/Diff/Source
  Control entrypoints from the default C/C++ application. The
  default descriptor set is now an injected backend `AppShellSpec`, so
  alternate hosts can provide a smaller or specialized GUI shell without
  editing `AppShellService`
- retired Inspector sidecar loaders/state/actions for artifacts, review panes,
  permission-rule panes, runtime panes, workspace previews, and event logs have
  been removed; the GUI uses active surfaces, session activities, interaction
  state, and app-shell diagnostics instead. The split GUI artifact refetch
  facade has also been removed: no `/api/artifacts` route, no
  `artifacts_refresh` WebSocket event, and no frontend callback bridge for
  artifact invalidation remains. The hosted `/artifacts` slash command and TUI
  artifact browser service/surface have also been retired; tool-result stored
  paths remain evidence metadata, not a standalone frontend browse API.
  The old `Inspector.jsx` component and `inspectorTab` / `inspectorKind`
  renderer adapter are also retired; right-panel fallback content now renders
  through `SurfacePanel` from renderer-local `panelKind` metadata.
- GUI thread lifecycle actions now route through the session lifecycle facade
  and are displayed from app-shell `thread_lifecycle.actions` descriptors
  rather than a renderer-owned fixed action list: the default descriptors map
  rename to summary/projection title metadata updates, archive to hiding a
  session from default thread lists without deleting transcript/summary/artifact
  references, and fork to copying the transcript to a new session id with fork
  provenance; action labels, disabled reason labels, prompt, confirmation,
  success, empty-title, and failure copy now travel on the same descriptors
  instead of being hard-coded by the renderer lifecycle controller, actions with
  missing labels stay out of the visible rail, and missing notice copy remains
  absent rather than being synthesized from action ids or labels
- GUI command-palette command group metadata now comes from app-shell
  `command_palette.groups` descriptors; the renderer no longer owns a fixed
  `COMMAND_GROUPS`, group title, group description table, palette placeholder,
  empty-state, current/missing badge, or root-section copy
- GUI composer slash-command default grouping is now app-shell declared through
  `capabilities.chrome.composer.command_menu.default_command_group_id`; session
  command normalization and renderer command helpers no longer synthesize
  missing command groups as `"command"`.
- GUI composer slash-command items now come only from command capability
  projection; the retired renderer-local `commandHints` fallback path has been
  deleted instead of preserved for compatibility.
- GUI composer hint-bar items are now app-shell descriptors under
  `capabilities.chrome.composer.hints`; renderer code no longer owns a fixed
  hint id/order list.
- GUI right-panel surface chrome now comes from app-shell `surfaces.chrome`
  descriptors; the renderer no longer owns right-panel aria copy, add-surface
  label, empty-state text, surface action menu labels, close labels, or
  surface command-label string concatenation. Surface-owned panel headings,
  including the Files surface header, use the active app-shell surface
  descriptor title instead of renderer-local defaults, and missing descriptor
  titles are not synthesized from surface kind/id values. Resource surface
  helper titles use only instance data such as file basenames, preview ids/URLs,
  and terminal ids; missing preview instance data does not create a fallback
  tab. File Preview breadcrumb aria text and markdown mode glyphs also come
  from `surfaces.chrome.file_preview` instead of renderer defaults. Diff
  workbench tab titles come from explicit diff payload titles or the app-shell
  surface descriptor rather than a renderer `"diff"` fallback
- GUI workbench session/message/view/palette command entries now come from
  app-shell `workbench_commands` descriptors; the renderer no longer owns a
  `LOCAL_COMMANDS` list, commands without visible labels are omitted instead of
  labeled from command ids, built-in shell actions route through
  descriptor-owned `dispatch.kind` records instead of command-id switches,
  supported dispatch kinds are implemented by a handler registry rather than a
  dispatch-kind switch,
  Terminal drawer opening is likewise declared by the bottom-drawer surface
  descriptor instead of inferred from the drawer kind, and the retired duplicate
  `workflow.diff` command is removed in favor of the declared `surface.diff`
  entrypoint
- GUI home/sidebar workspace and thread copy now comes from app-shell
  `home.workspace` / `home.threads` descriptors plus the selected agent
  `emptyState`; renderer components no longer own the default no-workspace,
  workspace path, missing-path, or empty-thread wording, and renderer
  app-shell normalizers do not invent the bundled product name when backend
  app metadata omits it. Untitled thread fallback prefixes are also declared
  by `home.threads` instead of hard-coded in the renderer
- GUI terminal bottom drawer is now an app-shell hosted, thread-scoped surface:
  the backend owns a workspace-bound in-memory terminal service using Python
  stdlib subprocess pipes for Win7/offline compatibility, while the React
  terminal reducer/API/UI keep terminal buffers as GUI-local display state.
  The default bottom drawer now exposes only implemented Run Output and
  Terminal renderer bodies; the stale Logs drawer declaration was removed
- GUI Source Control foundation is now an app-shell hosted, active-workspace
  surface: the backend owns a read-only `SourceControlService` over bundled or
  workspace MinGit, while the React source-control model/panel displays local
  status and opens existing Diff views for selected files. File status badges
  and group order are declared by app-shell chrome instead of synthesized from
  Git status initials, fixed group arrays, or raw group/provider ids in the
  renderer
- GUI Preview runtime boundary is now app-shell hosted and local-only: the
  backend owns a `PreviewService` that opens/probes loopback HTTP URLs, while
  the React preview model/API/chrome surface renders loading, success, and
  unreachable states without adding browser automation or Agent Core behavior.
  Preview, terminal, and source-control API helpers no longer carry
  helper-local request-failure copy, so missing backend error text falls through
  to app-shell chrome fallbacks
- GUI command-result run-output logging is now payload-declared: socket effects
  write bottom-drawer log entries only when `log_label` / `log_detail` is
  present, and no longer synthesize `command: /...` or ok/error labels from
  slash command names and success booleans
- GUI command-result timeline labels are now payload/app-shell declared:
  `t3-timeline.js` preserves command names as structured data without creating
  `/${commandName}` labels, and `TimelineRows.jsx` falls back only to
  app-shell `activity_rows.commandDefaultName`
- GUI renderer runtime state has started moving onto focused T3-style modules:
  `session-runtime/thread-state.js` owns thread/session selection, session
  summaries, and history-integrity display state, while
  `composer/composer-state.js` owns local draft text,
  `session-runtime/run-output-state.js` owns GUI run-output event-log display
  state, `session-runtime/session-transport-state.js` owns active session
  transport connection/reload projection,
  `app-runtime/session-transport-controller.js` owns WebSocket lifecycle, and
  `app-runtime/session-activation-controller.js` owns bootstrap activation.
  `App.jsx`, command palette, terminal
  controller, workspace reset, and tests consume those read models instead of
  root-level `sessions`, `currentSessionId`, `composer`, `historyIntegrity`,
  `connectionState`, or retired sidebar tab sidecars such as `sidebarTab` /
  `set_sidebar`.
- GUI visual-debug fixtures are now outside the product reducer state machine:
  `visual-debug-fixtures.js` keeps private `dev_fixture_*` descriptors and
  expands them into ordinary product actions, while `store.js` and
  `thread-state.js` no longer define `visual_*fixture` cases.
- Generated GUI static assets remain committed release artifacts for the
  current offline packaging model; source review should use `webapp/src/`, and
  `npm run build` refreshes `frontend/gui/static/` after source changes.
- The retired GUI workflow-runtime display helper and its tests have been
  removed; workflow detail now stays in backend-declared session snapshot,
  capability, or activity projections, and the renderer no longer synthesizes
  C/C++ phase, discipline, or activity rows from compatibility snapshot
  fields. New sessions without an explicit mode leave mode selection to the
  selected backend application/profile instead of injecting `explore` in GUI
  routes or renderer state.
- GUI tool presentation is now catalog-driven: labels, renderer keys,
  permission categories, and preview arguments come from backend-declared tool
  catalog metadata, while unknown tools fall back only to their tool id. The old
  renderer-owned built-in tool label table has been removed.
- GUI tasks now come only from session bootstrap/snapshot `task_items`; the old
  split `/api/tasks`, `tasks_refresh`, `tasks_loaded`, `/api/workspace/recipes`,
  renderer recipe-list load paths, and frontend-facing CoreInterface
  `list_tasks` / `list_workspace_recipes` facades have been removed.
  Workflow-specific quick actions must be exposed through backend capability or
  command metadata.
- GUI tool catalog display now comes from session capability/bootstrap
  `toolCatalog`; the old `/api/tool-catalog` route, root renderer
  `toolCatalog` fallback state, and frontend-facing `CoreInterface.get_tool_catalog`
  facade have been removed.
- Right-panel surface navigation is now the only GUI right-panel entrypoint
  truth. `SurfacePanel` receives renderer-local `panelKind` metadata from
  `RightPanelSurfaceBody`; the removed `Inspector` component no longer keeps an
  internal `RIGHT_PANEL_SURFACES` tab registry, `inspectorTab` adapter,
  `showTabs` flag, or `onTabChange` navigation contract.
- Root renderer `inspectorTab` / `inspectorOpen` state and `set_inspector` /
  `toggle_inspector` reducer actions have been removed; right-panel navigation
  now flows only through workbench surface state.
- GUI webapp source now uses active right-panel/surface vocabulary here:
  `surface.*` i18n keys, `surface-panel` CSS, `--right-panel-w-raw`, and
  `right-panel-toggle`. Retired Inspector shell names are guarded from active
  source.
- `AgentCoreAdapter` no longer imports built-in `DEFAULT_MODE` or injects
  `explore` into missing frontend protocol `current_mode`; selected
  application/profile mode state remains backend-declared.
- Offline GUI packaging now includes a native Win32 launcher exe in the portable
  bundle, preserving the one-folder delivery model while improving double-click
  startup.
- this is explicitly separate from Agent Core session truth, workflow state,
  tool activation, permission policy, extension loading, provider config, and
  `/api/sessions/{id}/bootstrap`

Recent stabilization work has also completed the agent-core ownership cutover:

- `QueryEngine` is now session-scoped and owns session mutation for the lifetime of a conversation
- frontend/live events now reuse engine-issued `step_id` values end-to-end
- resumed permission/user-input interactions re-enter the same action pipeline instead of bypassing it
- `AgentToolActionService` owns workflow-patch capture after tool-result hooks, so `QueryEngine` no longer wraps extension result patching
- `AgentLoop` asks `AgentExtensionHost` for active schemas directly, so `QueryEngine` no longer exposes private active-tool/schema forwarding methods
- hosted slash-command dispatch now lives in `HostedCommandService`; hosted
  `/review` synthesis remains in `ReviewCommandService` underneath that
  command boundary, while `InProcessAdapter` only bridges sessions and events
- hosted permission/user-input response glue now lives in
  `HostedInteractionService`; actual resumed action execution still re-enters
  the core action pipeline
- provider snapshot, workflow prompt append/dedupe, and compaction payload
  assembly now live in `TurnSnapshotService`, `PromptAssemblyService`, and
  `CompactionJournal`, so `QueryEngine` no longer owns those helper details
- Agent Core boundary extraction is complete: durable session and interaction
  records, model/tool contracts, loop guard primitives, prompt/compaction
  helpers, and host-service policy ports now live in `embedagent_core`, while
  concrete providers, tools, stores, context assembly, workspace intelligence,
  and default workflow composition stay in hosted/product layers
- session snapshots are now built by a pure `SessionSnapshotProjector`
- live tool-completion refresh has moved to `read_model_invalidations`
  metadata on tool catalog entries and events, so GUI/Core paths no longer
  maintain parallel tool-name lists for workspace file or task refresh; GUI
  artifact invalidation no longer opens a sidecar refetch facade
- transcript sequence allocation uses cached counters instead of rescanning on every append

## 4. Remaining Near-Term Work

The 2026-06-25 pre-release debt cleanup program described in
`pre-release-architecture-debt-audit.md` is closed, and its completed plan is
archived under `docs/archive/pre-release-debt-cleanup/`. The product is still
not live, so future implementation should continue deleting old internal state
instead of preserving it as if it were a public contract.
The follow-up Pi/T3 residual debt cleanup package is archived under
`docs/archive/pi-t3-residual-debt-cleanup/` after synchronizing durable
conclusions into active source-of-truth docs.

Near-term work should:

- keep future GUI/Core work on the promoted transcript, unified action,
  explicit capability, and T3-style renderer-state paths closed by the cleanup
  slices
- preserve the promoted service boundaries around `QueryEngine`,
  `InProcessAdapter`, GUI backend route registration, and renderer runtime
  state; future slices should delete stale helper paths instead of adding
  compatibility wrappers over them
- keep visual fixtures out of production reducer paths and preserve the
  generated-asset release-artifact policy until packaging is redesigned
- keep real Win7 WebView2 109 bundle validation and C/C++ workflow validation
  as release gates; repo-side validation now includes bundle-local
  `validate-cpp-smoke.py`, while Win7 windowed GUI smoke still requires target
  machine evidence

### 4.1 Pi-Inspired Minimal Core Program

The next long-term architecture program is documented in `docs/pi-inspired-agent-core-blueprint.md`.

It has two goals:

- keep learning Pi's functional design: extensions, resources, durable sessions, compaction, commands, model capability metadata, observability, and self-extension workflows
- keep learning Pi's architecture philosophy: a small Agent Core, capability registration, source-aware event reducers, explicit turn snapshots, save points, replaceable workflow packages, and environment-specific adapters outside Core

The current self-extensible Agent Core baseline remains valid. The next program should advance it in gradual slices:

1. **Durable operation log and reducers**
   - extend transcript truth from session history into durable runtime state
   - record explicit operation lifecycle events for turns, agent steps, context assembly, provider requests, tool calls, save points, pending interaction, context snapshot, workflow patch, and interruptions
   - restore by reducing a self-consistent log prefix
   - mark unfinished operations interrupted by default and avoid automatic retry of non-idempotent tool calls
   - keep legacy session replay events out of operation-state inference; they rebuild history, not runtime operation status

2. **Source-aware HookBus and reducer registry**
   - separate passive observers from result-producing reducers
   - encode reducer semantics per event instead of scattering merge behavior across the manager
   - attach source metadata, cleanup, diagnostics, and reload behavior to registrations
   - keep built-in workflow extensions and project-local extensions on the same internal event boundary
   - current implementation status: Phase B is complete for extension hook dispatch, and the pre-release explicit capability cleanup is complete; `ExtensionManager` routes declared `ExtensionCapability` records through `AgentEventBus` and no longer auto-registers hooks by method name

3. **AgentKernel lifecycle extraction**
   - current implementation status: Phase C is complete
   - `AgentLifecycleJournal` owns durable lifecycle operation writes and save points
   - `AgentKernel` owns turn frames and pending interaction create/resolve boundaries
   - `AgentLoop` owns turn-loop orchestration and `QueryEngine` remains the session facade
   - non-LLM action execution remains behind `AgentToolActionService`

4. **Default C/C++ workflow package**
   - current implementation status: Phase D is complete for tool capability ownership
   - C/C++ task graph, prompts, task snapshots, workflow projection, tool registration, metadata, pack activation, and extension-owned `task_status` handling live behind the bundled workflow package boundary
   - keep frontend shells consuming generic workflow projections
   - ensure bare Agent Core can run without the C/C++ package

5. **Self-extension authoring loop**
   - current implementation status: Phase E is complete
   - `SelfExtensionAuthoringService` generates local skills, prompts, recipes, extension manifests, extension code, docs, and validation recipes under `.embedagent`
   - `author_local_capability` exposes this as a build/debug `workspace_write` tool
   - resource reload remains separate from executable extension loading
   - generated project extensions are disabled by default and still require manifests, declared permissions, workspace-bound entrypoints, diagnostics, and normal `PermissionPolicy` enforcement

6. **Offline bundle validation**
   - current implementation status: Phase F is complete for repo-side validation, and the pre-release release-gate slice adds contract-backed C/C++ smoke validation
   - `scripts/offline-runtime-contract.json` lists all runtime-invoked bundled external tools
   - PowerShell and Python bundle validators consume the same runtime contract, including LLVM/Clang child executable checks and release-gate asset checks
   - `validate-cpp-smoke.py` compiles the bundled C smoke workspace with bundle-local Clang and rejects system-tool fallback by default
   - extension loading remains dependency-free at runtime and generated validation recipes use managed bundle commands
   - clean Windows 7 unpack-and-run GUI smoke remains a target-machine release gate

7. **Turn snapshot and capability registry foundation**
   - current implementation status: Phase G is complete
   - `TurnSnapshot` freezes provider-request messages, tool schemas, registered and active tool names, workflow state, model profile, runtime metadata, capability projection, and context stats
   - `CapabilityRegistry` projects tools, local file resources, slash commands, and model profiles as JSON-serializable descriptors with provenance
   - provider request diagnostics record safe snapshot metadata only, not prompt bodies, file contents, raw tool outputs, or credentials

8. **Runtime configuration reducer**
   - current implementation status: Phase H is complete
   - `RuntimeConfigReducer` reduces `runtime_configured`, `resource_reloaded`, and provider-request `operation_started` snapshot metadata from the transcript
   - session snapshots expose reducer-backed `runtime_config` for diagnostics and restore visibility
   - `TurnSnapshot` records reducer-backed model profile and local resource revision metadata when available
   - activation, execution, resource reload, extension loading, and permissions remain owned by their existing boundaries

9. **Workflow package manifest/read model**
   - current implementation status: Phase I is complete
   - `WorkflowPackageManifest` validates and serializes workflow package identity, supported modes/workflow states, tool declarations, packs, resource scopes, and diagnostics
   - the bundled C/C++ workflow package manifest is derived from its package-owned metadata and pack constants, then exposed through `CHarnessWorkflowExtension.package_manifest()` and `ExtensionManager.package_manifests()`
   - `CapabilityRegistry` now projects `workflow_package` descriptors for diagnostics and future reducer work
   - manifest projection is read-only; it does not activate tools, execute tools, grant permissions, reload resources, or load extensions

10. **Structured compaction state**
   - current implementation status: Phase J is complete
   - `ContextManager` can now perform deterministic pre-provider compact-policy rebuilds when assembled input reaches `auto_compact_threshold_ratio` and older turns can be summarized; reactive provider-error compact retry remains in `AgentLoop`
   - `compact_boundary` events now carry safe structured metadata: token/message counts, preserved message anchors, trigger/phase/window-generation diagnostics, file activity paths, evidence refs, and extension-summary flag
   - `compacted_history` events now carry a safe checkpoint payload: summary text, first-kept message anchor, replacement messages, trigger/phase metadata, token/message counts, file activity refs, and evidence refs
   - `CompactionStateReducer` projects reducer-backed compaction state from transcript events, including latest boundary, compacted-history checkpoints, and duplicate/malformed diagnostics
   - restore results, managed sessions, protocol snapshots, and session snapshots expose `compaction_state`
   - `SessionRestorer` validates compacted-history ids, anchors, and replacement-message shape before restoring live session checkpoint state
   - `ContextManager` can rebuild provider history from the latest valid compacted-history replacement checkpoint plus the newer transcript suffix, while still applying compact-policy shrinking on retry paths
   - projection remains read-only diagnostics/replay state; active context assembly, summary generation, extension loading, tool execution, and permissions remain owned by their existing boundaries
   - `ContextPlan` now provides a minimal explicit read model before provider requests for selected-message counts, recent/summarized turns, token/character summaries, pipeline steps, preserved message ids when available, and replacement refs
   - near-term follow-up direction: broaden validation and UX diagnostics around compacted-history checkpoints, without moving checkpoint projection into permission, extension, or workflow-package policy
   - keep deterministic local summary generation as the offline fallback; any provider-generated or extension-supplied compact summary must fail closed to the deterministic strategy and must not create a mandatory network dependency
   - keep `CompactionStateReducer` read-only and out of active planning, summary generation, replacement-history installation, extension loading, tool execution, and permission decisions

11. **Recovery state**
   - current implementation status: Phase K is complete
   - hosted resume appends safe `recovery_marker` events after restoring a trusted transcript prefix
- `RecoveryStateReducer` projects reducer-backed recovery state from transcript events, including latest marker, trusted-prefix counts, stop reasons, operation/compaction/runtime summaries, and diagnostics
- `TurnExperienceReducer` projects safe turn experience from transcript `tool_result` and `loop_transition` events, including completed files, unverified work, validation failures, blockers, and next steps; CLI/TUI/GUI consume this same snapshot field instead of maintaining frontend-specific completion or validation inference
   - restore results, managed sessions, protocol snapshots, and session snapshots expose `recovery_state`
   - projection remains read-only diagnostics/replay state; restore validation, mode selection, tool activation, context selection, extension loading, tool execution, and permissions remain owned by their existing boundaries

12. **Pack compatibility cleanup**
   - current implementation status: Phase L is complete
   - `src/embedagent/tooling/packs.py` has been removed
   - `embedagent.tooling` no longer re-exports C/C++ workflow pack aliases
   - bundled C/C++ workflow pack truth is available only from `src/embedagent/workflow_packages/c_cpp/packs.py`
   - active tool selection, schema projection, permissions, and default hosted C/C++ behavior remain unchanged

13. **Core alias cleanup**
   - current implementation status: Phase M is complete
   - mode registry access goes through `get_mode_registry()` / `initialize_modes()`
   - command sanitization access goes through `get_command_sanitizer()`
   - adapter class lookup goes through `get_inprocess_adapter()`
   - stale registry, sanitizer, and adapter compatibility names have been removed

14. **Agent application manifest and capability projection**
   - current implementation status: Phase N is complete for the hosted boundary and first built-in multi-application registry
- `AgentApplicationManifest` records describe application id, label, profile id, workflow package ids, source metadata, and default status
- `build_agent_application(application_id, tools)` is the hosted selected-application loader; the default C/C++ application is one builtin application, not a `QueryEngine` fallback
- built-in applications are declared as `AgentApplicationRecord` data; profile-only applications build directly from their profile record, while workflow-backed specialized applications declare a lazy `builder_path` so the generic loader does not hard-code C/C++ workflow branches; the default C/C++ application record/app-shell overlay lives in `src/embedagent/workflow_packages/c_cpp/application_record.py`, and its mode profile lives in `src/embedagent/workflow_packages/c_cpp/agent_profile.py`
- built-in ids now include `embedagent.default_c_cpp`, `embedagent.generic`, `embedagent.python`, and `embedagent.html`; the non-C applications are profile-only and do not install the C/C++ workflow package
   - profile-only records remain in the base application registry; workflow-backed built-in records are loaded through a lazy record list, so building `embedagent.generic`, `embedagent.python`, or `embedagent.html` no longer imports `embedagent.workflow_packages.c_cpp`
   - profile runtime policy is now shared through `src/embedagent/agent_profile_runtime.py`; hosted adapters compose `AgentProfileRuntimePolicy`, `AgentProfileToolPolicy`, and `AgentProfileWritePathPolicy` instead of carrying product prompt, write-glob, or mode-switch parsing copies
   - base config examples and `config/config.json.template` no longer pin `embedagent.default_c_cpp`; omitted `agent_application_id` is resolved by the hosted application registry
   - C/C++ workspace-profile file signals now live in `src/embedagent/workflow_packages/c_cpp/workspace_profile.py`; generic `src/embedagent/workspace_profile.py` consumes optional application detectors and no longer hard-codes CMake/Make/C++ source roots
   - GUI/session capability payloads expose `agentApplication` and `agentApplications` from the backend, and injected external applications do not leak the bundled C/C++ application into their available-application list
   - renderer no-workspace copy, capability normalizers, mode order, `workflowPackages`, and runtime workflow summary rows now come from backend-declared capability/snapshot payloads instead of C/C++ defaults
   - hosted review, project-memory, and workspace-intelligence helpers consume structured evidence payloads rather than default C/C++ workflow tool constants, so specialized applications can emit their own recipe/quality/diagnostic tools

This program must not introduce public online extension marketplaces, runtime dependency installation, public remote registries, built-in tool replacement by project-local code, container requirements, WSL requirements, VS Code dependency, or general multi-agent orchestration in Agent Core. Optional intranet Git/custom-service/provider/catalog/telemetry integrations may be considered only as trusted, explicitly configured hosted capabilities with disable/fallback behavior, safe diagnostics, source metadata, and normal permission checks.

### 4.2 Legacy Helper Deletion

Remaining cleanup should focus on:

- removing dead compatibility shims that are no longer part of product paths
- deleting or archiving superseded helper modules
- removing outdated tests/manual samples that preserve non-official behavior
- validating real C/C++ projects and the Win7/offline bundle while keeping documentation synchronized with the official extension boundaries
- keeping `scripts/offline-runtime-contract.json`, packaging validators, and the Win7 preflight checklist aligned when runtime-invoked tools change
- keeping future intranet or telemetry work out of Core by treating it as optional provider/extension/workflow-package/sink behavior

### 4.3 Workflow Extension Decoupling

Near-term decoupling should continue from the new extension boundary:

- default extension configuration has moved behind `AgentApplication`: hosted product paths use the selected scenario application's profile and extension manager, while bare `QueryEngine` callers pass an `ExtensionManager` explicitly when they need bundled workflow behavior
- `QueryEngine` should remain a facade over `AgentLoop`, `AgentToolActionService`, and `AgentExtensionHost`; new extension hook dispatch should not be added directly back to `QueryEngine`
- keep public remote registries, plugin marketplaces, runtime dependency installation, built-in tool replacement, and multi-agent orchestration out of scope; project-local Python extensions stay limited to explicit enabled manifests under `.embedagent/extensions/<name>/`, and future intranet capabilities must use the same explicit hosted boundary discipline

### 4.4 Documentation Alignment

Current source-of-truth docs must remain aligned with the official architecture:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/mode-schema.md`
- `docs/tool-contracts.md`
- `docs/permission-model.md`
- `docs/frontend-protocol.md`
- `docs/agent-harness-v2.md`
- `docs/pi-inspired-agent-core-blueprint.md`

### 4.5 Documentation Governance Baseline

- establish the active docs governance scaffold
- create module-level documentation for core code areas
- standardize terminology, templates, and Mermaid usage
- keep `superpowers -> global docs -> archive` synchronization as the default closure path

### 4.6 Real-World Validation

After architecture cutover, the highest-value validation is:

- real C workspace flows
- recipe discovery quality
- Clang diagnostics quality
- Win7 bundle runtime validation
- clean Win7 unpack-and-run smoke for the contract-backed offline bundle

## 5. Product Areas

### Agent Core

Priority remains highest on:

- `QueryEngine`
- harness
- runtime
- permissions
- context
- transcript/session truth

### Frontend Shells

Frontends should evolve only through the protocol/core contract and must not reintroduce workflow truth of their own.

### Offline Packaging

Offline packaging remains a first-class product requirement, but it must follow the current official runtime and protocol architecture rather than older mode/tool assumptions.

## 6. Verification Expectations

Before claiming a roadmap slice complete:

- run focused Python tests for the changed subsystem
- rebuild GUI assets if webapp source changed
- re-run relevant webapp helper/runtime tests
- update tracker and change log in the same change

## 7. Current Roadmap Summary

The repository is now past the architecture cutover stage and into pre-release
debt cleanup:

- delete or replace transitional session, timeline, GUI reducer, and
  extension-hook layers instead of adapting around them
- keep validating on real C projects
- keep tightening offline bundle behavior around the shared runtime contract
- keep the transcript-backed session-history path as the only official history model
- do not reopen old dual-path architecture
