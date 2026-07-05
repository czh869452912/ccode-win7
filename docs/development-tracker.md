# EmbedAgent 开发进度跟踪

> 更新日期：2026-07-05（Pi/T3 decoupling continuation）
> 用途：持续跟踪当前阶段、下一步任务、里程碑进度、风险与阻塞

---

## 1. 使用规则

本文件用于回答四个问题：

1. 当前做到哪一步了？
2. 下一步最应该做什么？
3. 哪些任务已经完成，哪些仍在阻塞？
4. 当前有哪些风险需要被持续关注？

更新规则：

- 每完成一个里程碑或子里程碑，更新本文件
- 每次重要设计变更，同时检查是否需要同步本文件
- 当前只保留“近期最重要”的 5-10 项任务，不把它写成无限 backlog

---

## 2. 当前阶段

### 2026-07-01 - Superpowers Archive Closeout

- Completed `docs/superpowers/` working materials for hosted runtime shell
  isolation, experience runtime convergence, interaction convergence, and
  interaction lifecycle convergence have been moved into
  `docs/archive/pi-t3-residual-debt-cleanup/`.
- Active documentation already carries the durable conclusions: hosted command
  and interaction glue live in hosted services, `Session.pending_interaction`
  is the single frontend-visible pending interaction truth, GUI/TUI responses
  use `respond_to_interaction(...)`, and old blocking frontend interaction
  callbacks are not product paths.
- `docs/modules/frontend-gui.md` has been synchronized away from the removed
  synchronous callback model.
- Current Pi/T3 decoupling continuation has removed the GUI workflow-runtime
  display helper and its old webapp test; renderer workflow detail now stays on
  backend-declared snapshot/capability/activity projections instead of a
  retired Inspector runtime panel path.
- The GUI artifact refetch facade has been removed from the current contract:
  `/api/artifacts`, `artifacts_refresh`, `on_artifacts_refresh`, and the
  CoreAdapter callback bridge for artifact invalidation are no longer GUI
  paths.
- The hosted `/artifacts` slash command and TUI artifact browser surface/service
  have also been removed; current frontends consume transcript/session evidence
  projections instead of a standalone artifact browse API.
- GUI webapp source CSS and the manual Playwright example no longer keep the
  retired artifact browser/Inspector-tab shell; manual GUI checks now target
  the current right-panel surface model.
- The old `Inspector.jsx` right-panel body and `inspectorTab` /
  `inspectorKind` adapter have been retired. `RightPanelSurfaceBody` now hands
  renderer-local `panelKind` metadata to `SurfacePanel`, so the right panel no
  longer has a hidden tab renderer behind the T3-style surface state.
- `/api/app/bootstrap` app-shell surface capabilities now use descriptor
  records instead of string ids. The renderer merges those backend-declared
  titles, icons, ordering, command/slash metadata, and safety hints with local
  supported renderers, so visible right-panel/bottom-drawer entrypoints are no
  longer presented from a GUI-owned surface id list.
- Generic local resource discovery no longer imports default C/C++ workflow
  tool names. Workspace-local recipes without an explicit `tool_name` stay
  workflow-neutral in `discover_local_resources(...)`; the default C/C++
  workflow recipe list applies its own `run_recipe` normalization only at the
  workflow-owned aggregation boundary.
- Local self-extension authoring now follows the same boundary: generated
  `.embedagent/recipes/*.json` and extension validation recipes no longer carry
  a default C/C++ `tool_name`, while active workflow packages remain responsible
  for projecting runnable recipe tools.
- `/api/app/bootstrap` now declares Preview surface chrome and local-server
  presets under `capabilities.preview`. The renderer uses those descriptors for
  Preview toolbar labels, empty states, status labels, and failure notices
  instead of keeping Preview-specific English copy in `App.jsx`,
  `PreviewSurface.jsx`, or `preview-surface-model.js`.
- Bottom drawer run-output chrome now comes from
  `capabilities.surfaces.chrome`: aria label, empty output text, and
  termination reason prefix are backend-declared descriptors consumed through
  `surfaceChromeLabels(appCapabilities)`.
- Timeline structured tool-detail chrome now comes from
  `capabilities.chrome.timeline.tool_detail`: field labels, section titles, and
  match fallback labels are backend-declared descriptors, while
  `t3-timeline.js` only projects field keys, section kinds, and display data.
- Timeline work-row chrome now comes from
  `capabilities.chrome.timeline.work_row`: fallback headings, fallback icon
  names, and status aria labels are backend-declared descriptors rather than
  renderer-local work-row defaults.
- Timeline tool-call preview text and command/file request kind are now
  catalog-driven: `ToolRuntime` projects safe `metadata.preview_arg` through
  session capabilities, the default C/C++ workflow package declares its
  workflow preview argument, and `t3-timeline.js` no longer keeps
  `bash`/`read_file`/`grep_text`/workflow-tool preview branches.
- Timeline changed-file path inference is now catalog-driven as well:
  `write_file` and `edit_file` declare safe `metadata.changed_path_arg`, and
  the GUI T3 timeline no longer keeps a `WRITE_TOOLS` or command-name diff
  table for changed-file summaries.
- Timeline review-result classification is now structured-payload driven:
  command results become review rows only when they carry `data.review` or
  `review`, so the GUI no longer treats the slash command name `/review` as a
  row-type policy.
- Command-result Diff surface activation is now structured-payload driven:
  WebSocket command results open the Diff right-panel from `data.diff` rather
  than from the slash command name `/diff`, so specialized agents can expose
  diff-producing commands without GUI command-name coupling.
- GUI user-input interaction projection no longer defaults missing
  `tool_name` values to the built-in `ask_user` tool. Pending user-input
  display is driven by `kind` / `sourceActivityKind` and whatever safe payload
  fields the backend provides.
- GUI session-load follow-up effects from command results are now
  structured-payload driven: a command result with `data.switch_session_id`
  triggers session load regardless of slash command name, so specialized
  resume/session-switch commands do not need GUI command-name branches.
- GUI session bootstrap projection and renderer session normalization no
  longer invent `workflow_state: "chat"` when a backend snapshot omits the
  state name; workflow display stays on explicit snapshot values plus the
  separate generic `workflow` payload.
- No-workspace GUI shell branding now comes from backend app metadata:
  `app-home-model.js` projects `app.productName`, and `NoWorkspaceState.jsx`
  renders that descriptor value instead of hard-coding the default product
  name. The renderer app-shell normalizer also preserves a missing
  `productName` as empty instead of falling back to the bundled product name.
- Files right-panel surface title now comes from the active app-shell surface
  descriptor: `RightPanelSurfaceBody.jsx` passes the surface record into
  `FilesSurface.jsx`, and the panel header no longer hard-codes the default
  Files copy.
- Right-panel surface opening now prefers the active app-shell surface
  descriptor title and no longer strips English command-label prefixes to
  invent panel titles.
- Command palette shortcut display labels now come from
  `command_palette.labels.shortcut_labels` / `shortcut_separator` instead of
  renderer-local `Ctrl` / `Shift` / `Esc` defaults.
- File Preview right-panel chrome now comes from
  `capabilities.surfaces.chrome.file_preview`: default file/project labels,
  loading/error fallback copy, retry/copy/explorer actions, metadata
  separators, breadcrumb aria text, markdown mode glyphs, line labels,
  language labels, and file-surface fallback tab title copy are
  backend-declared descriptors consumed by the file-preview model, right-panel
  controller, and surface.
- Diff right-panel chrome now comes from
  `capabilities.surfaces.chrome.diff_panel`: default titles, empty-state copy,
  controls, file rail labels, collapse labels, and source-control diff title
  templates are backend-declared descriptors consumed by the Diff model,
  socket effects, App source-control bridge, and surface; workbench tab titles
  come from explicit diff payload titles or the app-shell surface descriptor
  rather than a renderer `"diff"` fallback.
- Composer slash/path menu chrome now comes from
  `capabilities.chrome.composer.command_menu`, while slash command group labels
  reuse `capabilities.command_palette.groups`; the composer search,
  interaction, and menu components no longer keep a parallel command/path menu
  copy table. The default slash-command group id also comes from app-shell
  chrome, and renderer command helpers no longer synthesize missing command
  groups as `"command"`. Composer slash-command items now come only from
  command capability projection; the old renderer-local `commandHints`
  fallback path has been removed. Composer hint-bar items are now ordered
  `capabilities.chrome.composer.hints` descriptors instead of a renderer-owned
  fixed hint id list.
- Command Palette empty-state copy is now entirely descriptor-owned through
  `capabilities.command_palette.labels`; `CommandPaletteResults` no longer
  carries a renderer-local English fallback for missing app-shell labels.
- Timeline chrome now comes from `capabilities.chrome.timeline`: log aria label,
  empty/history/termination copy, work-group labels, activity-row labels/status
  and timer templates, and changed-files card labels are backend-declared
  descriptors consumed by Timeline, TimelineRows, and ChangedFilesCard. The T3
  timeline projection now carries turn-fold timing/interruption data without
  precomputing renderer chrome labels.
- Source Control right-panel chrome now comes from
  `capabilities.source_control.chrome`: panel title, status/diff fallback
  notices, empty states, group order, count/group/provider labels, file status
  badge labels, runtime labels, and refresh action copy are backend-declared
  descriptors consumed by the renderer. Missing group/provider descriptors do
  not fall back to raw ids as visible UI.
- Preview, Terminal, and Source Control frontend API helpers no longer carry
  local request-failure copy. When backend responses omit `detail` / `error`
  and status text, controllers fall through to app-shell chrome fallback
  notices instead of helper-level English strings.
- Command-result run-output logging is now payload-driven: WebSocket effects
  consume optional `log_label` / `log_detail` fields and no longer synthesize
  visible `command: /...` or ok/error copy from slash command names.
- Command-result timeline labels are now payload/app-shell driven: T3 timeline
  projection preserves command names as data but visible row labels come only
  from explicit payload labels or `activity_rows.commandDefaultName`.
- The retired GUI sidebar tab sidecar has been removed: root `sidebarTab`,
  `set_sidebar`, the old `sidebar-tab--chats` test id, and unused workbench
  `activeSection` / `projectSection` state are no longer product paths.
- Composer Branch Toolbar chrome now comes from
  `capabilities.source_control.chrome.branch_toolbar`: checkout labels,
  change/conflict summaries, disabled reasons, action labels, refresh title,
  and metadata separators are backend-declared descriptors consumed by the
  source-control toolbar model.

### 2026-06-27 - Pi/T3 Residual Debt Cleanup Closed

- GUI backend route registration is split by family: `server.py` is now the
  composition root, while app/session/terminal/source-control/preview routes
  live in focused route modules.
- `HostedCommandService` owns slash-command dispatch, command-result emission,
  and hosted command tool execution; `HostedInteractionService` owns
  permission/user-input response glue and pending ticket state.
- `TurnSnapshotService`, `PromptAssemblyService`, and `CompactionJournal` own
  provider snapshot metadata, workflow prompt append/dedupe, and compaction
  payload assembly outside `QueryEngine`.
- The 2026-06-27 residual cleanup plan and design spec are archived under
  `docs/archive/pi-t3-residual-debt-cleanup/` after active docs synchronization.
- Pre-merge architecture gate is now the default merge checklist for GUI,
  Agent Core, permission, extension, workflow-package, and frontend-protocol
  changes:
  `uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v`,
  `uv run pytest tests/ -m "not slow and not gui" -v`,
  `uv run --locked python scripts/lint.py`, plus `npm test` from the GUI
  webapp. When webapp source changes, `npm run build` must refresh and commit
  generated GUI static assets.
- Win7/offline delivery claims remain gated by real target-style bundle smoke
  evidence; local dev tests and webapp builds are regression gates, not release
  evidence for clean Win7/WebView2 operation.

### 2026-06-27 - Pi/T3 Residual Debt Cleanup Slice 3

- Tool catalog metadata now carries `read_model_invalidations` for safe
  projection refresh hints such as `workspace_files`, `tasks`, and
  `capabilities`.
- `InProcessAdapter`, `CallbackBridge`, GUI WebSocket payloads, and renderer
  loader effects now consume those invalidation hints instead of hard-coded
  tool-name lists for file/task/capability refresh.
- GUI interaction and timeline request-kind classification has been trimmed
  toward explicit request kind / permission category metadata, and stale
  inactive tool-label aliases were removed from the renderer store.

### 2026-06-27 - Pi/T3 Residual Debt Cleanup Slice 2

- GUI live permission/user-input activity now comes from backend-owned
  `session_event` messages emitted from Core turn events and bridged through
  `WebSocketFrontend.on_turn_event(...)`.
- Raw `permission_request` / `user_input_request` WebSocket messages now drive
  only the current blocking interaction UI and response path; the renderer no
  longer synthesizes `interaction.created` activity records from those raw
  request messages.
- `WebSocketFrontend` now completes GUI session-event metadata (`event_id`,
  `seq`, `created_at`) at the backend boundary when Core payloads do not
  provide it, keeping live transport sequencing out of renderer logic.

### 2026-06-27 - Pi/T3 Residual Debt Cleanup Slice 1

- Permission category classification now comes from `ToolRuntime` catalog
  metadata through the active runtime lookup; `PermissionPolicy` no longer owns
  a parallel built-in tool-name taxonomy.
- `other` is an official permission category and asks by default, so unknown
  tools or tools with invalid/missing permission metadata cannot fall through
  to allow.
- `bash` command failures and timeouts now carry
  `outcome_class=diagnostic_failure`; the guard path no longer counts ordinary
  command/build/test diagnostic failures toward hard `guard_stop`, so repeated
  compile or shell failures can feed the next model turn.
- Guard-stop remains available for provider/protocol no-progress, repeated
  non-diagnostic blocked actions, interruption, discarded parallel results, and
  explicit runtime/test safety fuses.

### 2026-06-26 - Pi/T3 Residual Debt Cleanup

- Default pre-release configuration and hosted GUI defaults now align with the
  current architecture: `default_mode: explore`, with no persistent loop
  ceiling in JSON config.
- `ToolRuntime.execute_for_mode`, adapter `_run_turn_v2`, adapter-local
  resource command spec builders, and adapter-local review evidence shaping
  were deleted or moved behind the intended boundaries.
- `slash_commands.resource_command_specs(...)` now projects local skill/prompt
  command specs for `/help` and capability descriptors.
- `ReviewCommandService.build_payload_from_session(...)` owns hosted `/review`
  evidence extraction, finding synthesis, git-diff evidence shaping, and
  markdown rendering.
- `SessionBootstrapService`, `RuntimeCapabilityService`,
  `SlashCommandService`, `TurnSnapshotService`, and `PromptAssemblyService`
  now own the corresponding hosted/Core projection work that had been
  accumulating in `InProcessAdapter` and `QueryEngine`.
- `SessionHistoryAssembler` now emits bootstrap `history.activities` as a
  direct T3-style activity read model from transcript-backed `Session` state,
  alongside the nested diagnostic `turns` structure; the React GUI now
  normalizes those activities through `session-runtime/activity-state.js` and
  the TUI formats the same activities into local display lines instead of using
  `timelineFromTurns`, `timelineFromEvents`, `session-runtime/projector.js`,
  `build_flat_history()`, `FlatTimelineView`, or event-list reload formatters.
- GUI run-output display state and transport connection/reload projection now
  live under `webapp/src/session-runtime/`; session activation and WebSocket
  lifecycle live under `webapp/src/app-runtime/`; root-level GUI
  `connectionState` / `set_connection` state and old timeline reload recovery
  were removed.
- The completed slice plan is archived under
  `docs/archive/pi-t3-residual-debt-cleanup/`.

### 2026-06-25 - Pre-Release Architecture Debt Cleanup Closed

- The project is explicitly treated as pre-release with no production user state
  to preserve.
- Old internal session formats, timeline dependencies, GUI reducer shapes,
  generated visual-debug state, and extension-hook compatibility layers are no
  longer protected compatibility targets.
- `docs/pre-release-architecture-debt-audit.md` now records the closed cleanup
  baseline and remains the deletion-oriented guardrail for future work.
- Slice 1 has removed `SessionTimelineStore` and timeline-backed `/review` /
  `/events` replay. Session activation and review now consume
  transcript/session projections; `/api/sessions/{id}/events` returns
  `reload_required`, and the GUI T3 timeline uses bootstrap history plus live
  reducer actions instead of transport event-log history.
- Slice 5 has started replacing the GUI's global root-state shape with
  T3-style renderer modules: thread/session selection and history-integrity
  display state now live in `webapp/src/session-runtime/thread-state.js`, and
  composer draft state lives in `webapp/src/composer/composer-state.js`.
  `App.jsx`, the command palette, terminal controller, workspace reset path,
  and reducer tests now consume these focused read models instead of
  root-level `sessions`, `currentSessionId`, `composer`, or
  `historyIntegrity` fields. Follow-on Pi/T3 residual cleanup moved GUI
  run-output event-log display state into
  `webapp/src/session-runtime/run-output-state.js`, moved transport
  connection/reload projection into
  `webapp/src/session-runtime/session-transport-state.js`, moved WebSocket
  lifecycle and bootstrap activation into focused app-runtime controllers, and
  removed root-level `connectionState` / `set_connection`.
- Slice 6 has removed visual-debug fixture actions from product GUI state:
  fixture helpers now use private `dev_fixture_*` descriptors and expand them
  into ordinary product actions before reaching `store.js`. Generated GUI
  static assets are documented as committed release artifacts for the current
  offline packaging model, with `webapp/src/` as the review source of truth.
- Slice 7 has converted release claims into contract-backed gates:
  `offline-runtime-contract.json` now declares release gates, bundle validators
  check those gate assets, release profile verification no longer forces
  `-SkipDynamicChecks`, and `validate-cpp-smoke.py` compiles the bundled C smoke
  workspace through bundle-local Clang without system PATH fallback. Clean
  Win7/WebView2 windowed GUI smoke remains a target-machine evidence item.
- The completed implementation plan has been archived under
  `docs/archive/pre-release-debt-cleanup/`. Future Pi/T3 work should delete or
  replace transitional paths instead of adding adapters over them, while
  preserving Windows 7, offline deployment, Python 3.8, and the default C/C++
  workflow.

### 2026-06-22 - GUI Native Bundle Launcher

- Offline GUI startup now has a native Win32 launcher entry point in the portable bundle: `EmbedAgent.exe` for user double-click startup and `embedagent-gui.exe` for scriptable GUI startup.
- The launcher is a thin environment/setup shim over the existing Python GUI launcher; it does not freeze Agent Core or change GUI backend/frontend semantics.
- `embedagent-gui.cmd` remains available for visible-console diagnostics and support.
- Packaging validators and GUI smoke tests now treat the native launcher as the preferred bundle GUI entry point while preserving WebView2 Fixed Version 109 and one-folder offline delivery.

### 2026-06-22 - T3 Workbench Renderer UI State Persistence

- GUI workbench state now follows T3 Code's renderer-owned UI-state store pattern: sanitized browser `localStorage` persistence for right-panel visibility/width, bottom-drawer visibility/kind/height, and session-scoped right-panel surface stacks.
- Session activation restores the current thread's shallow right-panel surface descriptors and active surface id, so Files/File/Diff/Preview/Terminal/Plan tabs behave like thread-local workbench UI rather than one global inspector.
- The persisted payload intentionally excludes command palette query/open state, file contents, preview snapshots, terminal output, tool data, backend snapshots, transcript history, workflow state, permission state, and runtime reducer state.
- This slice stays in the GUI app shell: no Agent Core, backend protocol truth, workflow package, permission policy, transcript ledger, runtime reducers, provider configuration, extension loading, source-control mutation, telemetry, or offline/Win7 runtime assumptions changed.
- 2026-06-22: Planned and implemented T3 GUI parity shell stabilization for right-panel floating menus, surface-store parity, shared terminal shell, and frontend-local timeline row model. Agent Core, transcript truth, reducers, workflow packages, permission policy, and backend protocol semantics remain unchanged.

### 2026-06-20 - Pi/T3 Residual Contract Cleanup

- GUI smoke validation now follows the current T3-style app-shell task contract:
  `build` sessions, session bootstrap `task_items`, `task_status`,
  permission/user-input flows, and `/review`; stale `mode=code`, `/api/todos`,
  `/api/tasks`, and `manage_todos` references are guarded by a focused contract
  test.
- Agent Core prompt behavior is slimmer and more Pi-like: build mode no longer hard-codes a `lite_spec_tdd` phase prescription in the base mode prompt, leaving workflow package prompt injection behind the extension boundary.
- C harness workflow injection now recognizes common Chinese development/debug/verification requests while keeping casual chat in build/debug from initializing workflow state.
- Tool result cache documentation and stats now describe only implemented cache tiers; the unused L3 projection placeholder has been removed instead of being treated as a public capability.
- `AgentCoreAdapter.shutdown()` now detaches frontend state and either delegates to runtime shutdown or cancels known sessions, keeping GUI workspace switching/app shutdown from depending on a no-op core cleanup path.
- Offline staging no longer ships stale `code` / fixed-eight-turn defaults: generated bundle configs use `default_mode: explore` and do not carry a persistent loop ceiling, while the workspace template is now a tiny buildable C smoke project instead of a placeholder directory.

### 2026-06-19 - Pi-Style Agent Core Prompt/Resource/Runtime-State Alignment

- Agent Core prompt surface is slimmer: built-in mode prompts no longer enumerate active tool directories, C workflow prompt units no longer expose pack tool lists, and visible local skills are summarized through a single hosted `local_skills_prompt` listing unit instead of being duplicated inside mode prompts.
- Runtime state now records registered tool names separately from model-visible active tool names through `runtime_configured` and provider turn snapshot metadata. This is diagnostic/replay state only; active-tool policy still flows through `ExtensionManager` / `AgentExtensionHost`.
- Workspace resources remain file-only. Skill bodies expand only through `/skill:<name> [args]`; prompt bodies expand only through `/prompt:<name-or-path> [args]`; reload indexes resources and updates reducer-backed resource revision metadata without executing local Python code.
- Workflow package manifests are guarded as non-executing control-plane data: identity, supported modes/workflow states, tools, packs, resource scopes, and diagnostics only. They do not activate tools, grant permissions, load code, or become a public extension API.
- Focused coverage now asserts prompt-surface diet, registered-vs-active tool state, explicit resource invocation, and workflow manifest non-execution boundaries.


### 2026-06-19 - T3 Right-Panel Preview Runtime Boundary

- GUI preview now has an app-shell hosted `PreviewService` with local-only URL normalization, loopback HTTP probing, in-memory preview tab snapshots, refresh, close, and open-in-system-browser actions.
- `GUIBackend` exposes preview routes under `/api/sessions/{id}/preview*` plus `/api/app/preview/open-external`; these routes are workspace/session scoped and reject remote or non-HTTP preview URLs before opening network connections.
- React preview API/model helpers now map backend snapshots into T3code-style `idle` / `loading` / `success` / `failed` state, and `PreviewSurface` renders refresh/open-external controls plus an unreachable state for failed local targets.
- Visual debug `preview` now asserts the local-card flow, URL-tab replacement, runtime action enablement, failed/unreachable feedback, and right-panel tab non-overlap.
- This slice still does not add an embedded browser runtime, browser automation, Electron, remote calls, source-control mutation, or Agent Core behavior. It does not write transcript history, workflow state, permission policy, runtime reducers, provider configuration, extension loading, telemetry, or checkpoints.

### 2026-06-19 - T3 Right-Panel Preview Surface Shell Parity

- GUI right panel now exposes `Preview` as the first manually addable T3code-style surface, with `surface.preview`, `/preview`, and default `mod+4` command/keybinding coverage.
- The new `PreviewSurface` renders compact URL chrome, local-server empty-state cards, concrete URL tabs, and an embedded-preview unavailable state while staying inside the GUI app-shell.
- `preview-surface-model.js` owns frontend-only URL normalization, display formatting, and local-server empty-state projection; opening a local server replaces the empty `right:preview` placeholder instead of leaving duplicate preview tabs.
- Visual debug `preview` now asserts the right-panel preview shell, URL input, local server cards, placeholder viewport, URL-tab replacement, and right-panel tab non-overlap.
- This slice does not add a browser runtime, browser automation, Electron APIs, remote calls, source-control mutation, or Agent Core behavior. It does not write transcript history, workflow state, permission policy, runtime reducers, provider configuration, extension loading, telemetry, or checkpoints.

### 2026-06-19 - T3 Right-Panel Editor/Diff Chrome Parity

- GUI right-panel file preview now uses a T3code-style `surface-subheader` with horizontally scrollable breadcrumbs, compact metadata, icon-style open/markdown/explorer controls, and the existing reveal-line code surface below it.
- GUI right-panel diff now uses a T3code-style subheader with selection chips, stacked/split display controls, line-wrap and whitespace toggles, a collapsible file rail, and a focused scrollable diff viewport.
- The file explorer affordance reuses the existing right-panel `FilesSurface`; the open affordance stays GUI-local and only copies the workspace-relative path when clipboard access is available.
- Visual debug `diff,file` now asserts both chrome states, control toggles, reveal markers, scroll containers, and right-panel tab non-overlap.
- This slice stays in the GUI app shell: it does not change Agent Core, backend protocol truth, transcript history, workflow state, permission policy, runtime reducers, provider configuration, extension loading, source-control mutation/checkpoints, telemetry, terminal execution, or offline/Win7 runtime constraints.

### 2026-06-19 - T3 Timeline File-Link Activation Parity

- Timeline markdown file links, grep match rows, structured tool file rows, changed-file rows, and review findings can now open the right-panel `FilePreviewSurface` through the existing GUI `openFile(path, line)` path.
- `t3-timeline.js` now preserves numeric match line targets and display line labels so click sources can pass a real reveal line instead of parsing display text.
- `Timeline.jsx` handles workspace-relative markdown file links while leaving remote URLs and hash-only anchors as normal links; `TimelineRows.jsx` and `WorkRow.jsx` thread the `onOpenFile` callback down to `ToolDetail.jsx` and review findings.
- Visual debug timeline fixtures now include a real `src/parser.c` workspace file, a grep match at line 4, a markdown file link, a review finding, and a preloaded preview record; the `timeline` visual scenario clicks the file link and asserts the T3 reveal marker pair plus target text.
- This slice stays in the GUI app shell: it does not write transcript history, change workflow state, mutate source control, alter backend protocol truth, or touch Agent Core, permission policy, runtime reducers, provider configuration, extension loading, telemetry, or terminal execution semantics.

### 2026-06-19 - T3 File Preview Reveal Parity

- GUI right-panel `FilePreviewSurface` now renders a T3code-style file viewer: project/directory/file breadcrumbs, a language + line-count metadata line, a numbered code gutter, and a code/markdown preview mode toggle that defaults `.md`/`.mdx` files to the rendered preview.
- Breadcrumb, markdown-mode, gutter, language, metadata, and reveal-line clamp logic live in a frontend-only pure module `webapp/src/session-runtime/file-preview-model.js`, with breadcrumb, markdown-mode, and reveal semantics aligned to `reference/t3code/apps/web/src/components/files/`.
- File preview code view now marks both the line-number gutter row and content row with `data-file-link-reveal`, clamps out-of-range reveal requests to the loaded file range, and scrolls the target row into view when the file surface reveal request changes.
- The active workspace label flows through `App.jsx` -> `RightPanelSurfaceBody` -> `FilePreviewSurface` only as the breadcrumb project name; no new backend field is added.
- Visual debug `file` scenario now asserts breadcrumbs, the markdown preview, the mode toggle, the numbered gutter, the reveal-line marker pair, and target-row visibility after switching to code view; webapp unit/source tests and rendered GUI visual QA pass.
- This slice stays in the GUI app shell: T3's file editing, save coordinator, comment annotation, and `@pierre/diffs` editor are intentionally out of scope, and no Agent Core, backend protocol, transcript history, workflow state, permission policy, runtime reducer, provider configuration, extension loading, source-control mutation, checkpoint, telemetry, or terminal execution semantics changed.

### 2026-06-18 - T3 Command Palette Root/Submenu Parity

- GUI command palette now uses a T3code-style grouped root model instead of the previous flat `visibleCommands(...).filter(...)` list.
- Root results project existing visible commands, recent sessions, and workspaces into rich rows with descriptions, metadata, shortcut hints, active/current labels, disabled missing-workspace rows, and command category submenu entries.
- Submenu view supports command-group navigation, keyboard-owned highlight movement, Enter execution, Escape close, and Backspace return from an empty submenu query.
- Command rows still execute through existing workbench command IDs; session/workspace rows route only through existing `App.jsx` callbacks (`loadSession` / `activateWorkspace`).
- Visual debug coverage now exercises root groups, session/workspace rows, submenu search, keyboard Enter execution, and overflow guardrails across `1280x720`, `700x640`, and `520x720`.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, transcript history, workflow state, permission policy, runtime reducer, provider configuration, extension loading, source-control mutation, checkpoint, telemetry, or terminal execution semantics changed.

### 2026-06-18 - T3 Composer Command Menu And Context Tokens

- GUI composer now owns a T3code-style grouped command menu instead of the previous inline slash hint list.
- Slash command search is ranked through frontend-only pure helpers, and selecting a command inserts the existing executable slash text such as `/diff ` into the prompt.
- `@` file context search now projects currently loaded GUI file-tree nodes into plain-text path insertions such as `@src/parser.c ` without adding backend attachment protocol.
- Composer primary send/stop controls now use compact T3-style action buttons while preserving existing `onSend` / `onStop` behavior.
- Visual debug coverage now exercises slash selection, path selection, keyboard highlight state, and overflow guardrails at `1280x720`, `700x640`, and `520x720`.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, transcript history, workflow state, permission policy, runtime reducer, provider configuration, extension loading, source-control mutation, checkpoint, telemetry, or terminal execution semantics changed.

### 2026-06-18 - T3 Branch Toolbar Run Context

- GUI composer footer now includes a T3code-style branch/run-context toolbar derived from the existing app-shell source-control state.
- The toolbar shows active workspace, mode context, local branch/detached/no-repo state, provider label, and change/conflict count, with disabled Worktree/Branch mutation affordances and a read-only refresh action.
- Visual debug fixtures now provide a deterministic `feature/t3-toolbar` local Git state so chat and responsive visual scenarios assert the toolbar renders with `4 changes`.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, transcript history, workflow state, permission policy, runtime reducer, provider configuration, extension loading, source-control mutation, checkpoint, telemetry, or terminal execution semantics changed.

### 2026-06-18 - T3 Timeline Parity Shell

- GUI timeline work rows now render through a T3code-style `WorkGroupSection`: consecutive work/tool rows are grouped, collapsed groups show only the latest entry by default, and `+N previous tool calls` expands older entries while preserving scroll position.
- Running timeline state now uses T3code-style pulsing dots plus a self-updating `Working for ...` timer when GUI-local timestamps are available.
- Timeline and right-panel layout guardrails now expose stable scrollbars, avoid the previous fixed `360px` narrow-layout center column, and let right-panel surface tabs/source-control actions shrink or wrap instead of overflowing the sidebar.
- GUI socket/reducer display state now carries frontend-local `createdAt` / `completedAt` timestamps for duration labels; these fields remain GUI display/read-model state and do not alter transcript history, backend protocol truth, Agent Core policy, workflow state, permission policy, runtime reducers, provider configuration, extension loading, terminal execution, source-control execution, or telemetry semantics.

### 2026-06-18 - Pi-Style Agent Loop Continuation

- `AgentLoop` has moved from the previous fixed eight-cycle product ceiling to a Pi-style open continuation loop with a small internal `AgentLoopContinuationPolicy`.
- Hosted defaults no longer stop merely because eight model/tool cycles were used; explicit positive `max_turns` values remain supported as the optional loop safety fuse.
- Safety-limit stops still emit the compatibility `max_turns` transition and now include `loop_safety_limit` metadata for diagnostics.
- Context compaction, guard-stop, pending interaction, permission policy, and C/C++ workflow ownership remain in their existing boundaries.

### 2026-06-18 - T3 Workbench IA And Tool Details

- GUI left sidebar now owns workspace/thread navigation only; duplicate left Files tab and file tree rendering have been removed.
- The right-panel `FilesSurface` is the sole file browsing surface and now has an explicit scroll wrapper for long file trees.
- T3 timeline work rows now project frontend-local `detailModel` data and render structured tool details through `ToolDetail.jsx` instead of falling back to raw JSON for normal tool data.
- Visual harness coverage now asserts timeline/file/thread scroll containers, absence of the left Files tree, and absence of raw JSON in expanded tool details.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, workflow package, permission policy, transcript, runtime reducer, provider configuration, extension loading, terminal execution, source-control execution, or telemetry semantics changed.

### 2026-06-18 - GUI Terminal Runtime Controller Boundary

- React webapp `webapp/src/app-runtime/terminal-controller.js` now owns GUI terminal action orchestration for bottom-drawer terminal actions and right-panel terminal open/split/activate/close behavior.
- `App.jsx` wires the controller through injected state, dispatch, terminal API helpers, and terminal id generation, while root render composition and command routing remain incremental follow-on work.
- Existing terminal HTTP helpers remain in `webapp/src/terminal/terminal-api.js`, and terminal snapshot/event normalization remains in `webapp/src/terminal/terminal-state.js`.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, terminal backend service, workflow package, permission policy, transcript, source-control, provider configuration, extension loading, telemetry, or runtime reducer semantics changed.

### 2026-06-18 - GUI Session/App Loader Runtime Boundary

- React webapp `webapp/src/app-runtime/session-loaders.js` now owns the GUI-private loader request vocabulary, defensive loader request executor, and session bootstrap projection helper.
- `socket-message-effects.js` shares that loader vocabulary instead of defining a second copy, while remaining a pure frontend effect derivation module.
- `App.jsx` now delegates session bootstrap projection and loader request execution branching to the app-runtime boundary, but still owns concrete HTTP route calls, reducer dispatch, event-log reset, terminal summary loading, task refreshes, and render composition.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, workflow package, permission policy, transcript, runtime reducer, operation reducer, compaction reducer, recovery reducer, terminal execution, or source-control execution semantics changed.

### 2026-06-18 - GUI App Runtime Controller Boundary

- React webapp now has a GUI-only `webapp/src/app-runtime/` boundary: socket messages are interpreted by pure descriptor derivation before `App.jsx` executes reducer actions, session event-log entries, and existing loader requests.
- Dev-only visual timeline/interaction/thread fixtures moved out of `App.jsx` into `visual-debug-fixtures.js`, while remaining gated by `?visual_debug=1`.
- This slice stays in the GUI app shell: no Agent Core, backend protocol, workflow package, permission policy, transcript, runtime reducer, operation reducer, compaction reducer, recovery reducer, terminal execution, or source-control execution semantics changed.

### 2026-06-18 - T3 Timeline Rich Projection

- GUI T3-style timeline now projects and renders thinking, reasoning, compact, command-result, and review-result rows in the active row renderer instead of relying on the legacy grouped fallback.
- Current `activity-state.js` runtime receives GUI-local `activeTurnId` / `thinkingActive` state so live `thinking_state` and `reasoning_delta` events are visible without new backend protocol.
- Timeline expansion defaults and visual fixtures now cover rich row kinds, and responsive CSS guardrails reduce clipping under narrow or zoomed layouts.
- This slice remains GUI app-shell display/read-model work only: no transcript writes, workflow-state ownership, permission/runtime reducer changes, provider configuration, extension loading, source-control checkpoints, or Agent Core policy changes.

### 2026-06-17 - T3 Right-Panel Terminal Group Surface

- GUI right panel 已新增 T3 Code-style terminal group surface：terminal surface descriptor 现在拥有 `terminalIds`、`activeTerminalId` 和可选 `splitDirection`，可在同一 right-panel terminal tab 内 split、activate 和 close pane。
- 右侧 terminal surface 现在按 surface-scoped terminal ids 渲染 panes，不再直接展示全局 active terminal；bottom drawer terminal 保持独立入口和既有行为。
- right-panel terminal actions 继续复用现有 GUI terminal backend routes，terminal process state/output buffer 仍属于 GUI-local terminal runtime state。
- 该切片继续保持 GUI app-shell 与 Agent Core 分离：不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、source-control checkpoints 或 Agent Core policy。

### 2026-06-17 - T3 Right-Panel File Surface

- GUI right panel 已新增 T3 Code-style `file` surface：文件树点击文件会打开/复用路径对应的右侧 file tab，tab title 使用文件 basename，重复打开同一文件刷新 reveal request 而不创建重复 tab。
- `file` 被加入 right-panel allowed surface kinds，但不进入 generic add-surface menu；加号/empty state 仍只提供 `diff`、`files`、`terminal`、`plan`，文件 surface 只能由文件动作打开。
- 文件内容现在存放在 GUI-local `filePreviewsByPath`，surface descriptor 只保存 path/resource/reveal metadata；`FilePreviewSurface` 负责 loading/error/content 三种展示状态。
- 该切片继续保持 GUI app-shell 与 Agent Core 分离：不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、source-control checkpoints 或 Agent Core policy。

### 2026-06-17 - T3 Right-Panel Surface Tabs

- React webapp right panel 已从固定 Inspector tab 列表改为 T3 Code-like ordered surface descriptors：当前首批 right-panel surfaces 为 `diff`、`files`、`terminal`、`plan`，由 `activeSurfaceId` 驱动激活、关闭、close others、close to right 和 close all。
- `RightPanelTabs` 现在复制 T3 的 surface tabbar / add menu / empty-state cards 结构；`RightPanelSurfaceBody` 负责把 Diff/Plan 交给 `SurfacePanel`，把 Files/Terminal 挂到 GUI app-shell hosted surfaces。
- Command palette 与默认 keybindings 已收敛到 T3 surface workflow：`mod+1` files、`mod+2` terminal、`mod+3` diff；旧 source-control/tasks 作为固定 right-panel tab 的入口不再属于本组 surface shell。
- 该切片只改变 GUI-local app-shell state 与 presentation，不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、checkpoint/source-control mutation 或 Agent Core policy。

### 2026-06-17 - GUI Source Control Foundation

- GUI backend 新增 active-workspace-bound `SourceControlService`，通过 bundled/workspace MinGit 执行 read-only local status/diff 命令，并对 workspace path escape、invalid diff scope、Git unavailable、not-a-repo 做安全映射。
- GUI backend 新增 `/api/app/source-control/status`、`/api/app/source-control/refresh`、`/api/app/source-control/diff` routes；app-shell capabilities 暴露 `source_control` 为 read-only/local/offline surface，明确不含 remote providers、network、checkpoints。
- React webapp 新增 `webapp/src/source-control/` model/API/presentation helpers 与 `SourceControlPanel` right-panel surface，显示 grouped local changes 并复用现有 Diff surface 打开 staged/unstaged unified diff。
- 该实现继续保持 T3 Code-like independent app 与 Agent Core 分离：不写 transcript、workflow state、telemetry、permission/runtime reducers、provider config、extension loading 或 checkpoint truth，也不实现 push/pull/stage/commit。

### 2026-06-17 - GUI Terminal Bottom Drawer

- GUI backend 新增 `TerminalService`，以 active workspace 为根目录启动线程作用域 terminal，并通过 Python stdlib subprocess pipes 读取 stdout/stderr、写 stdin、维护有限内存 history buffer。
- GUI backend 新增 `/api/sessions/{id}/terminals*` HTTP routes 与 `terminal_event` WebSocket 推送；app-shell capabilities 暴露 `terminal` 限制元数据和 `bottom_drawer` surfaces。
- React webapp 新增 `webapp/src/terminal/` model/API helpers，并把 Terminal 接入 bottom drawer tabs、toolbar、buffer 和输入行；terminal 状态仍是 GUI-local display state，不进入 transcript、workflow、telemetry、permission、extension 或 source-control/checkpoint truth。
- 该实现保持 Win7/offline 底线：不引入 ConPTY、`node-pty`、`pywinpty`、`pexpect`、Electron、runtime Node、Docker、WSL、VS Code 或在线服务依赖；当前能力不是 full PTY。

### 2026-06-17 - GUI Thread Lifecycle Boundary

- Session lifecycle facade 现在暴露 `rename` / `archive` / `fork`：rename 只更新 summary/projection thread title metadata，archive 默认隐藏 thread 但保留 transcript、summary 和外置 artifact/tool-result 引用，fork 复制 transcript 到新 session id 并写入 fork provenance。
- GUI backend 新增 `POST /api/sessions/{id}/rename`、`/archive`、`/fork`，`/api/app/bootstrap` 的 capabilities 暴露 `thread_lifecycle.actions` descriptor records，让 GUI 只消费显式 backend action 声明而不是伪造第二份 session truth 或固定 action list。
- React sidebar thread action rail 已接入真实 backend lifecycle API；frontend 从 app-shell descriptors 投影 action label/order/danger/enabled/disabled reason 状态，缺失 label 的 action 不进入可见 action rail，prompt/confirm/success/empty/failure copy 也来自同一 action descriptor；缺失的 notice copy 保持缺失，不再由 renderer 从 action id/label 拼 fallback 标题；renderer lifecycle controller 只做状态刷新和 notice，不拥有 transcript、workflow、permission、extension、provider 或 source-control/checkpoint policy。

### 2026-06-17 - T3code App-Shell Boundary

- GUI backend 新增 `AppShellService`，`/api/app/bootstrap` 与 `/api/app/workspaces*` 现在返回 GUI-owned app-shell envelope：workspace registry projection、active workspace metadata、safe host/runtime/renderer diagnostics、app commands、app surfaces 和 local shell settings。
- GUI backend route 依赖已从兼容 `_ActiveCoreProxy` 收敛为显式 app-host active-core resolution；workspace-bound routes 通过 `GUIAppHost.require_core()` 取得当前 core，不再在 backend 上保留 `self.core` 代理状态。
- React webapp 新增 `webapp/src/app-shell/` 纯 read-model/reducer helpers，并把现有 app bootstrap / workspace switch legacy actions 统一路由到 app-shell reducer；root `resetWorkspaceScopedState` 仍只负责清空 session/timeline/task 等 workspace-scoped GUI 状态。
- Right panel 新增 Settings / Diagnostics 两个 app-level surfaces，命令 palette 新增 `app.settings` / `app.diagnostics` / `app.reload`，并保持这些命令与 session/workflow commands 分离。
- 当前收敛：命令 palette、right-panel add-surface launcher、bottom drawer tab 与 keybinding target 现在全部按 `/api/app/bootstrap` 的 `app_commands`、`workspace_commands`、`workbench_commands`、`command_palette.groups` / `command_palette.labels`、`surfaces.right_panel`、`surfaces.bottom_drawer`、`surfaces.chrome` 和 `keybindings` descriptor records 过滤/合并；app/workspace/workbench command 的 label/order/visible_when/surface/drawer/keywords/dispatch.kind、surface title/icon/description/command_label/slash/launcher_order/keywords、right-panel aria/add-surface/empty/action/close copy，以及 command-palette group title/description/order、placeholder、empty/current/missing/root-section/leading-marker copy 也来自 backend descriptor，renderer-local command/surface registry 只保留已支持 renderer 的 mounting/execution、resource、close-behavior 和 persistence metadata，并且不再导出固定 app command、workbench command、command group 或 surface id list 给调用方当能力真相，内置 GUI shell command execution 也不再由 renderer switch 固定 command id 推断，缺失整个 `capabilities` 对象或相关 descriptor arrays 时都不再填充 GUI 默认入口，缺失 label 的 command descriptor 不进入可见 workbench command 或 command-palette row，动态 slash command 只能从显式 label/usage/slash 获得可见文案，未声明或缺失 title 的 command-palette group 不承载可见命令也不从 group id 合成标题，缺失 command row description/meta 时保持为空而不回退到 command id，surface/drawer command row description 从 surface descriptor 透传而不从 surface/drawer id 拼接，session/workspace palette row leading marker 从 command-palette labels 透传且缺失时为空，command-palette group leading marker 从 group descriptor 透传且不从 title 首字母或符号兜底，缺失 title 的 surface descriptor 只作为 capability 诊断记录保留，不进入可见 launcher/command，也不从 kind/id 合成标题；资源 surface helper 标题只使用文件 basename、preview id/URL、terminal id 等实例数据，缺失 preview 实例数据时不再创建 fallback tab；旧重复 `workflow.diff` 默认命令已删除，Diff 入口只走 `surface.diff` descriptor。
- 当前收敛：Terminal bottom-drawer command 的打开行为现在来自 `surfaces.bottom_drawer` descriptor 上的 `dispatch.kind: terminal.ensure_open`；renderer 只识别该 dispatch kind，不再把 `drawer: "terminal"` 当作特殊执行策略。
- 当前收敛：Bottom drawer body 选择现在来自 renderer-supported surface definition 的 `bodyKind` metadata；未实现的默认 `logs` drawer 已删除，初始/持久化 fallback 不再把 active drawer 写死为 `run_output`。
- 当前收敛：Right-panel body 选择也已改为 renderer-supported surface definition 的 `bodyKind` metadata；`RightPanelSurfaceBody` 不再用固定 `surface.kind === ...` 分支推断 Files/File Preview/Preview/Terminal body。
- 当前收敛：Generic `SurfacePanel` 子面板选择也已改为 renderer-supported surface definition 的 `panelKind` metadata；`SurfacePanel` 不再用固定 `surfaceKind === ...` 分支推断 Plan/Diff/Source Control/Settings/Diagnostics body。
- 当前收敛：App Home/sidebar 的 workspace/thread copy 现在来自 `/api/app/bootstrap` 的 `home.workspace` / `home.threads` descriptors，并与 selected agent `emptyState` 组合展示；renderer 不再持有默认 no-workspace、workspace path、missing-path、empty-thread 文案或 untitled thread fallback prefix。
- 当前收敛：Workbench header/sidebar/composer/composer-interaction/legacy panel chrome copy 现在来自 `/api/app/bootstrap` 的 `capabilities.chrome` descriptor；旧 `webapp/src/strings.js`、`LangContext.js` 和未挂载的 `components/InteractionPanel.jsx` 已删除，renderer 不再保留第二套全局 i18n/string registry。
- 当前收敛：Terminal surface/drawer 的 pane label fallback、toolbar action、placeholder、empty/unavailable state 和 failure notice copy 现在来自 `/api/app/bootstrap` 的 `capabilities.terminal.chrome` descriptor；`terminal-labels.js` 无 descriptor 时只回退到 terminal id，不再生成 renderer-owned `"Terminal N"` 文案。
- 当前收敛：默认 GUI shell descriptors 已移到可注入 `AppShellSpec`（`frontend/gui/backend/app_shell_spec.py`）；`AppShellService` 只组合 spec 与 active-core 安全投影，不再内联维护 surface、command 或 keybinding 清单。
- 当前收敛：`/api/app/bootstrap` 在没有 active workspace/core 时也会从 host/launcher 选中的 agent application registry 投影安全的 `agentApplication`、`agentApplications` 和 `emptyState`；workspace 激活后由 active core 的 capability projection 接管，因此 GUI 可在打开 session 前按当前基础/专用 agent 调整空状态文案。
- 当前收敛：workbench 持久化 surface 状态在 app bootstrap / workspace switch 后也会按同一份 app-shell capabilities 重新裁剪；旧 localStorage 里的 `preview`、`source_control`、`terminal` 等 surface 不能绕过当前 active app 的声明重新出现。
- 当前收敛：旧 Inspector sidecar 的 artifacts/review/permissions/runtime/workspace-preview/log state、loader request 和 socket action 已删除；review 结果只作为 timeline activity 呈现，permission/user-input 只走 session interaction state，诊断只走 app-shell diagnostics surface。
- 当前收敛：工具展示 catalog 现在只来自 session capabilities/bootstrap 的 `toolCatalog`；GUI `/api/tool-catalog` route、root `toolCatalog` fallback state 和 frontend-facing `CoreInterface.get_tool_catalog` facade 已删除。
- 当前收敛：旧 `Inspector.jsx` 组件、`inspectorTab` / `inspectorKind` adapter、内部 `RIGHT_PANEL_SURFACES` tab registry、`showTabs` 和 `onTabChange` 导航入口都已删除；right-panel surfaces 是唯一的右栏导航真相。
- 当前收敛：renderer root `inspectorTab` / `inspectorOpen` state 和 `set_inspector` / `toggle_inspector` reducer actions 已删除，socket effects、visual fixtures 与 App 打开面板动作都不再写这条旧状态。
- 当前收敛：GUI webapp 源码中的旧 Inspector shell 命名也已清理为 right-panel/surface 词汇：`surface.*` i18n keys、`surface-panel` CSS、`--right-panel-w-raw` layout variable、`right-panel-toggle` test id，并已重建 GUI static assets。
- 当前收敛：`AgentCoreAdapter` frontend protocol projection 不再导入 built-in `DEFAULT_MODE`，也不再把缺失 `current_mode` 注入为 `explore`；模式默认值由选中 application/profile 后端声明。
- 该切片补齐 T3code-like standalone app shell 的第一层边界；terminal 已由后续 bottom-drawer slice 补齐，source-control foundation 已由后续 right-panel slice 补齐，后续 mutation/checkpoint 仍不得把 Agent Core 加厚为 GUI-owned policy layer。

### 2026-06-15 - T3code Timeline / Diff / Visual Debug Harness

- GUI 已在既有 React/WebView2 技术栈内补齐 T3code-style timeline row projection/rendering、composer-local permission/user-input interaction panel、right-panel Diff surface。
- GUI 视觉语言已向 T3code neutral workbench 收敛：全局 token、timeline 宽度、message/work rows、composer shell、right-panel tabs 和 diff chrome 均已从 GitHub-dark 风格调整为更克制的 T3-style 工作台语言；实现仍使用 Win7/WebView2 109 兼容的 plain CSS。
- 新增 dev-only `scripts/gui-visual-debug.mjs` / `npm run visual:gui`，可在当前 Win10/Win11 开发机启动真实 GUI、执行 load/chat/diff 场景、截图、检查 console warning/error 与 DOM 状态；Playwright 不进入 Win7 离线运行时依赖。
- visual harness 抓出并已修复 streaming assistant 文本重复问题：`LLMClientRetryWrapper` 不再在 streaming client 已发 delta 后重放 final content；同时 GUI WebSocket lifecycle 增加 token/manual-close guard，避免 React StrictMode cleanup 触发旧连接重连。

### 2026-06-16 - T3code Timeline / Diff Refinement

- Timeline changed-files card 已从平铺列表升级为 T3code-like 目录树：支持目录折叠/展开、路径归一化、目录级 diff 统计与 “View diff” 入口；该投影仍是 frontend-local read model，不改变 transcript/session history truth。
- Diff right-panel 已改为 T3code-like header + changed-file rail + diff viewport；在窄右栏和移动布局下自动单列堆叠，避免文件 rail 挤坏 diff 内容。
- `scripts/gui-visual-debug.mjs` 的 diff 场景改为通过显式 `?visual_debug=1` 页面参数启用的 `window.__EMBEDAGENT_VISUAL_DEBUG__` fixture hook 打开离线 unified diff，稳定验证真实 GUI 的 diff panel、file rail、截图和 console 状态；该 hook 仅用于开发机 visual harness，不是产品协议、Agent Core 能力或 Win7 runtime 依赖。
- 修复 timeline T3 投影中的 loose system item callback 错误与 detached/trailing item 合并丢失问题；补充 helper 测试锁定 system notice、detached work row、changed-files tree 和 diff stats。

### 2026-06-16 - T3code App Workspace / Thread Management

- GUI sidebar/no-workspace home 已增加 frontend-local `app-home-model` read model，将现有 app bootstrap workspace records 与 session summaries 投影成 T3code-like project/thread 管理表面；该模型只负责 label、count、active/missing/disabled 状态和紧凑时间展示，不改变 workspace registry、session truth 或 Agent Core lifecycle。
- Project 管理区改为局部滚动并限制高度，避免最近项目累积时把 Threads 管理区挤出首屏；visual harness 的 app 场景已加入 sidebar bounding-rect 检查，确保 project manager、thread manager 和 empty-thread state 均在真实 GUI 中可见。
- `scripts/gui-visual-debug.mjs` 现在为每次 run 设置隔离的 `EMBEDAGENT_GUI_APP_HOME=<output>/app-home`，继续走真实 GUI backend registry/app host 路径，但不会污染开发机正常最近项目列表。
- Thread rows 已增加 T3code-like lifecycle action rail：可见 action 来自 app-shell `thread_lifecycle.actions` descriptors，当前默认声明 `Rename` / `Fork` / `Archive` 并接入 backend/Core session lifecycle facade，持久化到 summary/projection thread metadata，仍避免 GUI 伪造第二份 session truth。
- visual harness 新增 `thread` 场景，可在真实 GUI 中加载多 thread fixture、验证 action rail 数量/默认禁用状态/侧边栏边界并截图，继续保持 dev-only、Win10/Win11 开发流程内使用。

### 2026-06-15 - T3code/Pi Workbench Shell

- Added frontend-local workbench shell contracts for GUI surfaces, commands,
  keybindings, command palette, right panel, and bottom drawer.
- Migrated GUI layout toward a T3code-style Agent workbench while preserving
  existing protocol/Core boundaries.
- Added TUI workbench command/surface state and Pi-style command palette
  overlay without changing Agent Core workflow policy.

### 总阶段

- 当前阶段：`Phase 4 真实工程验证 + Phase 6 GUI / Win7 收口 + Pi-inspired minimal Core enterprise boundary 收口`
- 总体状态：`进行中`
- 当前重点：`Agent Harness V2 official cutover 六步程序与文档治理 Batch A 已完成。模块文档（protocol/core、TUI、GUI、packaging）已补齐，代码-文档矩阵已同步。workflow extension boundary 代码迁移、repo-side 回归、本机 release bundle 验证和本机剩余边界清理已收口；Pi-inspired minimal Core Phase M core alias cleanup、enterprise/intranet capability boundary foundation、GUI terminal bottom drawer 与 GUI source-control foundation 已完成。下一步重点是在真实 Win7 目标机重跑离线 bundle smoke、继续真实 C/C++ 工程验证，并用架构守卫防止旧兼容路径回流。`
- 最新 session-history 收口：`GUI session activation 已切到单一 `/api/sessions/{id}/bootstrap` 合约；历史 turns 现在只从 `transcript.jsonl -> Session -> SessionHistoryAssembler` 生成；当前契约无 durable timeline transport，raw fallback 不再是正式 GUI 恢复模式。`
- 最新稳定化收口：`set_session_mode()` 现在会先重置旧 phase 再刷新 Harness snapshot，避免 build/debug/verify 跨 mode 切换时把上一模式的 phase 残留到新会话快照；同时 `Context` 高优先级工具、reducer registry 与 `/review` 文案已统一到 `run_recipe/report_quality_v2/task_status` 正式词汇。`
- 最新 dead-code 清理：`tools_v2/` 中仍被正式主路径使用的 discovery/recipe/session 模块已迁入官方 `src/embedagent/tools/`；旧 `tools_v2/*.py` 与已无人引用的 legacy `loop.py` 已删除，产品源码不再直接 import `tools_v2`。当前 `src/embedagent/agent_loop.py` 是 Slice 5 新增的正式 turn-loop 边界。`
- 最新 core cutover：`ToolRuntime` 已不再维护 legacy execute aliases，`permissions.py` 也已只按正式工具词汇分类；`build_ops.py`、`todo_ops.py` 与 `tests/test_todo_ops.py` 已删除，官方 runtime 现在只接受正式 schema/catalog 中的工具名。`
- 最新 intelligence cutover：`ProjectMemoryStore` 与 `WorkspaceIntelligence` 现已按 `run_recipe + recipe_action + report_quality_v2` 工作，历史 recipe id 也已从 `history.run_tests.1` 之类旧命名收敛为 `history.test.1`；当前 `src/` 里剩余的 live legacy 主要集中在 frontend/protocol 旧接口与 `workspace_recipes` 的内部旧名映射。`
- 最新 shell cutover：frontend/protocol/backend 侧的 `list_files` 旧接口名已切为 `list_workspace_tree`；webapp tool labels、review 语义和 workspace recipe 数据也已移除 `legacy_tool_name` 及旧 verify 工具名。当前 `src/embedagent/` grep 已不再出现 `compile_project/run_tests/manage_todos/list_files/search_text/tools_v2` 这类 legacy 词汇。`
- 最新 agent core cutover：`QueryEngine` 已改为 session-scoped owner，`InProcessAdapter` 不再为前端事件重新生成 `step_id`；pending permission/user-input 的 resume 现已回到统一 action pipeline，`TaskGraph` 已进入 `Session` 真相层并驱动 task projection，`SessionSnapshotProjector` 已抽成纯投影器，`transcript/timeline` 追加序号也已改为缓存分配。`
- 最新 workflow extension boundary：`src/embedagent/extensions.py` 已建立本地 workflow extension contract，默认 C/C++ harness 现在通过 `src/embedagent/harness/extension.py` 接入；`src/embedagent/default_extensions.py` 负责 hosted runtime 的默认扩展装配，`src/embedagent/harness/workflow_projection.py` 负责把 C harness 内部状态映射为通用 workflow payload；`QueryEngine` 不再直接 import/构造默认 C harness extension；`QueryEngine` 不再直接 import/实例化 `TaskGraph`，schema 投影统一走 `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` 并由 `AgentLoop -> AgentExtensionHost` 直接请求 active schemas；导入和实例化 `embedagent.session.Session` 不再加载 `embedagent.harness.task_graph`；`ToolRuntime.allowed_tool_names()` 与 `OfficialRuntimeModes.allowed_tool_names()` 已删除；旧 `TurnOrchestrator` 并行执行器已删除，`AgentLoop` 是唯一 turn-loop owner，`AgentToolActionService` 是唯一非 LLM action execution owner；`QueryEngine` 里的 `_allowed_tools_for_mode`、`_schemas_for_active_tools`、`_execute_action` 与 `_execute_parallel_tool_action` 兼容转发已删除；`SessionSnapshotProjector` 与 live frontend task API 已改为从 `Session.workflow_state["workflow"]` 投影任务字段，`InProcessAdapter` 不再直接构造 `HarnessRunner`，且 `/review` finding/markdown 规则已下沉到 hosted `ReviewCommandService`；`HarnessStateSynchronizer` service facade 已删除，refresh 与 task snapshot persistence 只走默认 C harness workflow extension；`Session.task_graph` 已删除，默认 C harness 图状态由 `CHarnessWorkflowExtension` 背后的 harness-owned session graph state 持有。`
- 最新 self-extensible Agent Core：`ExtensionManager` 已从默认 C/C++ workflow extension 边界扩展为共享 in-process capability boundary，新增通用 extension diagnostics、resource discovery contract、context hook、tool-call/tool-result hooks、dynamic in-process tool registration、frontend snapshot diagnostics 与 manifest-gated project-local Python extension loading；当前扩展参与路径已改为显式 `extension_capabilities()` / `ExtensionCapability` 记录，旧方法名 hook 不再自动注册。`.embedagent/skills`、`.embedagent/prompts`、`.embedagent/recipes` 本地文件资源已可通过 runtime、adapter、slash command 与 GUI/core API reload；`.embedagent/extensions/<name>/extension.json` 可在 `enabled: true` 且声明 permissions 时加载 workspace-bound `extension.py`，但 hooks/tools 必须通过 `api.ExtensionCapability` 显式声明，并继续禁止依赖安装、远程 registry、built-in tool replacement 与权限绕行。`QueryEngine` 已继续瘦身为 session facade：`AgentExtensionHost` 集中 extension hook dispatch 与 active schema projection，`AgentToolActionService` 集中非 LLM tool action execution、pending permission/user-input action、mode-switch proposal、resumed action execution 与 workflow-patch capture，`AgentLoop` 承担 turn-loop 与 active-schema 请求边界，`ReviewCommandService` 承担 hosted `/review` synthesis。Slice 6 已将 active source-of-truth docs、module docs 与 self-extensible archive index 同步到当前官方口径，completed self-extensible slice materials 归档到 `docs/archive/self-extensible-agent-core/`。`
- 最新 Pi-inspired minimal Core 蓝图：`docs/pi-inspired-agent-core-blueprint.md` 已建立为下一阶段长期目标蓝图，同时学习 Pi 的功能设计和架构哲学；目标是把 Agent Core 继续收敛为更小的 Agent Kernel、durable SessionLog/reducer、source-aware HookBus、CapabilityRegistry、RuntimeConfigReducer、WorkflowPackageManifest、CompactionStateReducer、RecoveryStateReducer、Policy Boundary 与默认 C/C++ workflow package。当前官方 baseline 不变；durable operation log、HookBus/reducer registry、AgentKernel lifecycle extraction、default C/C++ workflow package、self-extension authoring loop、repo-side offline bundle validation、turn snapshot / capability registry foundation、runtime configuration reducer、workflow package manifest/read model、structured compaction state、recovery state、pack compatibility cleanup、core alias cleanup 已按 Phase A-M 渐进收口。`
- 最新 enterprise/intranet capability boundary：`参考 Pi 的 custom provider / package / observability adapter 结构，但不复制其开放度。EmbedAgent 允许未来接入内网 Git、custom service、组织内 catalog、provider gateway 和内网 telemetry sink，但这些能力必须作为显式配置、受信、可关闭、可降级的 hosted extension/provider/workflow-package/sink；Agent Core 只保留安全事件、capability/read model、permission 与 reducer 边界，默认离线 C/C++ 工作流不得依赖网络。`network` 与 `telemetry` 已成为正式 permission categories，并贯穿 `PermissionPolicy`、dynamic tool registration、project extension manifest 和 self-extension authoring；`src/embedagent/telemetry.py` 已提供本地 safe envelope helper，用于在未来 sink 之前剔除 prompt、源码、原始工具输出、API key、permission payload、token 或审批 secret。`
- 最新 durable operation log 切片：`Phase A 已完成`。`src/embedagent/session_operation_log.py` 已新增纯 `OperationLogReducer`，并已硬切为只从 schema_v2 `operation_started/operation_finished/operation_interrupted` 推导 operation state；`step_started/tool_call/tool_result/loop_transition` 继续服务 session replay/history，不再参与 operation 推断。`SessionRestorer` 已暴露 `operation_state` 并消费显式 operation lifecycle 事件；`QueryEngine` 已为 turn、agent step、context assembly、context snapshot、provider request、tool call、pending interaction、workflow patch 与 save point 写入显式 operation lifecycle；restore-time 与 live session snapshot 均已投影 reducer-backed `operation_diagnostics`。`
- 最新 HookBus/reducer registry 切片：`Phase B 已收口`，pre-release explicit capability cleanup 已完成。`src/embedagent/agent_event_bus.py` 已建立 source-aware `AgentEventBus`、observer/reducer registration、event-specific reducer stopping、dispatch diagnostics 与 trusted fail-closed 行为；`ExtensionManager` 现在只从 `extension_capabilities()` 注册 `ExtensionCapability` 记录，并通过 `AgentEventBus` 分发 context、tool-call、tool-result、resource discovery、dynamic tool registration、prompt patch、workflow initialization、active tool names、task snapshot loading 与 extension-owned tool handling。公共 method-name hook compatibility 已删除；后续 operation lifecycle 编排已由 Phase C AgentKernel extraction 收口。`
- 最新 AgentKernel lifecycle extraction / continuation 切片：`Phase C 已收口`，且后续 Pi-style continuation 已落地。`src/embedagent/agent_lifecycle.py` 已建立 `AgentLifecycleJournal`，集中 durable lifecycle operation 写入、transition save point、pending interaction lifecycle 与 context operation payload helper；`src/embedagent/agent_kernel.py` 已建立 `AgentKernel` / `AgentTurnFrame`，统一 user/command/resume turn frame 与 pending create/resolve boundary；`src/embedagent/agent_loop.py` 已从 runner callback 包装器升级为 Pi-style open turn-loop owner，负责 agent step、context/provider attempt、compact retry、tool batch interruption、guard-stop、abort 与显式 loop safety-limit 兼容 transition。默认 hosted 路径不再按 8 个 model/tool cycles 截断；`QueryEngine` 不再拥有 `_run_loop_impl`、`_run_loop` 或 `_is_completion_signal`，继续作为 session-scoped facade 与 transcript/session mutation 兼容面；后续 Phase D default C/C++ workflow package 已由下一切片收口。`
- 最新 default C/C++ workflow package 切片：`Phase D 已收口`。bare `ToolRuntime` 构造现在只注册 workflow-neutral built-ins；默认 C/C++ workflow package 通过 `CHarnessWorkflowExtension.register_tools(...)` 注册 recipe、quality、evidence 与 `task_status` 工具；workflow tool metadata 已迁到 `src/embedagent/harness/tool_metadata.py`，workflow packs 已迁到 `src/embedagent/harness/packs.py`，旧 `src/embedagent/tools/harness_runtime.py` 已删除。hosted adapter 仍通过 `default_extensions.py` 默认装载 C/C++ package，bare Agent Core 不再加载 harness runtime facade；后续 Phase E self-extension authoring loop 已由下一切片收口。`
- 最新 self-extension authoring loop 切片：`Phase E 已收口`。`src/embedagent/self_extension_authoring.py` 新增 `SelfExtensionAuthoringService`，可在 workspace 内生成 `.embedagent/skills`、`.embedagent/prompts`、`.embedagent/recipes` 和 disabled-by-default `.embedagent/extensions/<name>` skeleton；`author_local_capability` 作为 build/debug 下的 workflow-neutral `workspace_write` 工具暴露该能力。authoring 只写文件，不 reload resource，不 enable/load Python extension；resource reload 与 executable extension loading 继续分离。最新 skill slice 已让生成的 skill 带 Agent Skills-style frontmatter，并支持系统提示词列表与 `/skill:<name> [args]` 显式展开。`
- 最新 offline bundle validation 切片：`Phase F 已收口`。`scripts/offline-runtime-contract.json` 现在是 runtime-invoked bundled external tools 的 repo-side 单一契约，覆盖 Python、MinGit、ripgrep、Universal Ctags 与 LLVM/Clang child executables；`scripts/validate-offline-bundle.ps1` 与 `scripts/check-bundle-dependencies.py` 均消费同一契约并输出结构化 runtime_contract 结果；回归测试已锁定 extension loading 不调用依赖安装器，generated validation recipe 使用 managed Python command。clean Windows 7 unpack-and-run smoke 仍是 release gate。`
- 最新 turn snapshot / capability registry 切片：`Phase G 已收口`。`src/embedagent/turn_snapshot.py` 现在提供 `TurnSnapshot` / `TurnSnapshotBuilder`，`QueryEngine` 在 context assembly 与 active schema projection 后构造 snapshot，并以 `snapshot.messages` / `snapshot.tool_schemas` 调用 provider；`src/embedagent/capabilities.py` 现在提供非执行型 `CapabilityRegistry`，可投影 runtime tools、本地 file resources、slash commands 与 credential-free model profile。activation 仍由 `ExtensionManager` / `AgentExtensionHost` 决定，execution 仍由 `ToolRuntime` / `AgentToolActionService` 决定。`
- 最新 runtime configuration reducer 切片：`Phase H 已收口`。`src/embedagent/runtime_config.py` 新增 `RuntimeConfigReducer`，从 `runtime_configured`、`resource_reloaded` 与 provider-request `operation_started` safe turn snapshot metadata 投影 replayable runtime configuration；`ManagedSession.runtime_config` 与 session snapshots 现在暴露 credential-free model profile、active model-visible tool names、local resource revision、capability counts 与 provider snapshot records。`TurnSnapshot` 会记录 reducer-backed model profile/resource revision metadata；tool activation、execution、resource reload、extension loading 与 permission policy 仍由原边界负责。`
- 最新 workflow package manifest 切片：`Phase I 已收口`。`src/embedagent/workflow_package_manifest.py` 新增 `WorkflowPackageManifest` read model，描述 workflow package identity、supported modes/workflow states、tool declarations、packs、resource scopes 与 diagnostics；默认 C/C++ package 通过 `CHarnessWorkflowExtension.package_manifest()` 暴露由 harness-owned metadata/packs 派生的 manifest，`ExtensionManager.package_manifests()` 负责通用收集，`CapabilityRegistry` 现在可投影 `workflow_package` descriptors。manifest projection 只用于诊断/控制面，不驱动 tool activation、execution、resource reload、extension loading 或 permission policy。`
- 最新 structured compaction state 切片：`Phase J 已收口`。`src/embedagent/compaction_state.py` 新增 `CompactionStateReducer`，从 `compact_boundary` transcript events 投影结构化 compaction state；`ContextManager` 现在支持基于 `auto_compact_threshold_ratio` 的 deterministic pre-provider compact-policy rebuild，`ContextWindowState` 作为内部 value object 统一派生 safe trigger/phase/window-generation diagnostics，`QueryEngine` 会在 compact boundary payload 中写入 safe token/message counts、preserved message anchors、trigger/phase/window-generation diagnostics、file activity paths、evidence refs 与 extension-summary flag；`SessionRestorer`、`ManagedSession`、protocol snapshots 与 session snapshots 现在暴露 reducer-backed `compaction_state`。该投影只用于 diagnostics/replay，不驱动 context selection、summary generation、extension loading、tool execution 或 permission policy。`
- 最新 recovery state 切片：`Phase K 已收口`。`src/embedagent/recovery_state.py` 新增 `RecoveryStateReducer`，从 `recovery_marker` transcript events 投影 hosted resume recovery state；`InProcessAdapter.resume_session(...)` 现在会在 restore 出可信 prefix 后写入 safe recovery marker，记录 trusted/transcript event counts、stop reason、operation/compaction/runtime summaries 与 skip metadata；`SessionRestorer`、`ManagedSession`、protocol snapshots 与 session snapshots 现在暴露 reducer-backed `recovery_state`。该投影只用于 diagnostics/replay，不改变 restore validation、mode/tool/context policy、extension loading、tool execution 或 permission policy。`
- 最新 pack compatibility cleanup 切片：`Phase L 已收口`。`src/embedagent/tooling/packs.py` 已删除，`embedagent.tooling` 不再 re-export `BUILD_LITE_PACK` / `CORE_PACK` / `pack_tool_names` 等旧 pack aliases；默认 C/C++ workflow pack truth 只从 `src/embedagent/harness/packs.py` 暴露。active tool selection、runtime schema projection、permission policy 与 hosted C/C++ 行为不变。`
- 最新 core alias cleanup 切片：`Phase M 已收口`。`MODE_REGISTRY`、`_DEFAULT_SANITIZER`、`get_default_sanitizer()`、`_inprocess_adapter` 与 `_get_adapter_class()` 等核心兼容别名已删除；当前代码通过 `get_mode_registry()`、`get_command_sanitizer()` 与 `get_inprocess_adapter()` 直接访问正式边界。mode behavior、shell sanitizer behavior、adapter lifecycle、permission policy 与 hosted C/C++ 行为不变。`
- 最新 workflow extension cleanup：`InProcessAdapter.list_tasks()` 的 inactive-session task snapshot fallback 已改为通过共享 `ExtensionManager.load_session_tasks(...)` 查询，默认 C harness extension 继续负责读取自己的 task snapshot；adapter 不再直接 import `embedagent.harness.task_store`。`
- 最新 workflow extension validation：`2026-05-29 repo-side 验证已通过：fast suite 为 685 passed / 11 deselected，focused C/C++ build/debug/verify workflow 回归为 15 passed。官方 harness 门禁已修复 marker 漏标问题，uv run pytest tests/ -m harness -v 现在会选中并通过 23 个 task_graph / phase_engine / harness runner / prompt stack / harness injection 测试。本机 release bundle 已用当前分支源码重建并通过：validate-offline-bundle.ps1 -RequireComplete 为 59 pass / 0 warn / 0 fail，check-bundle-dependencies.py 全部通过，scripts/package.ps1 verify -Profile release -Json 返回 final_status READY。clean Windows 7 unpack-and-run smoke 尚未执行。`
- 最新 documentation cleanup：`docs/guides/configuration-guide.md` 已改写为当前正式配置指南，使用 `explore/spec/build/debug/verify` 与 `build` 实现模式口径，不再把 `code` 或 `manage_todos` 作为当前配置/工作流示例。`
- 最新 runtime cleanup：`task_status` 前端元数据现已统一为 `tasks/task` 词汇，workspace profile 不再输出待办语义提示，运行时残留 `todos.py` 已删除。`
- 最新 GUI closeout：GUI backend 与 webapp 默认新建会话入口已统一为 `explore`，resume 默认不再强制覆盖 restored mode；GUI task 面板、样式和静态产物已清理 `todo-*` / `tasks.todo` 与 `mode-code` 残留，保留正式 `tasks/task` 与 `mode-build` 词汇。T3code-style timeline rows、composer interaction panel、Diff right-panel surface、neutral workbench visual language 与 dev-only visual debug harness 已落地；changed-files card 已升级为目录树，Diff panel 已具备 file rail + viewport 布局，project/thread 管理表面和 backend-backed thread lifecycle action rail 已进入正式 GUI/Core 边界；`AppShellService` 与 frontend `app-shell` read model 已补齐 standalone app shell 第一层边界，Settings/Diagnostics app surfaces 与 app commands 已接入；right panel 已继续收敛到 T3 Code-like ordered surface descriptors / surface tabs / add menu / empty-state cards，首批 surface 为 `diff/files/terminal/plan`；visual harness 通过 `?visual_debug=1` fixture hook 稳定验证真实 GUI diff/thread surfaces；harness 已覆盖 app/thread/load/chat/diff/responsive/timeline/interaction 并修复 streaming assistant 文本重复问题。
- 最新归档收尾：已关闭的 documentation governance baseline、workflow extension boundary follow-up、Pi-inspired minimal Core Phase A/B、enterprise boundary foundation、local skills / remaining Pi architecture gap materials、GUI IDE redesign 旧设计、GUI app-shell boundary、GUI thread lifecycle boundary、Pi-aligned tool architecture、hosted runtime shell isolation、interaction lifecycle convergence 和根目录历史 refactor notes 已迁入对应 `docs/archive/<topic>/`；`docs/archive/README.md` 与主题包 README 已补索引。活动 `docs/superpowers/` 入口当前没有 plan/spec 文件；后续新切片启动时再放入新的工作材料。`

### 当前判断

项目已经完成：

- 范围和目标收敛
- 参考项目分析
- 总体方案设计
- 实施路线与文档治理基线
- 项目级 `AGENTS.md`
- Python 3.8 / `uv` / `conda` 版本策略落盘
- 工具设计规范 `docs/tool-design-spec.md`（DC-004）
- 实施分期重组（DC-005）：关键路径前移，Phase 1 = 最小可工作 Loop
- Phase 1 最小原型代码骨架（`src/embedagent/`）
- 本地闭环自测：工具调用、Observation 回注、CLI 启动、语法编译
- Python 3.8.10 `uv` 环境验证通过（`.venv`）
- Moonshot `kimi-k2.5` 真实联调已跑通最小工具闭环（需使用 `/v1`，并保留 `reasoning_content`）
- `docs/llm-adapter.md` 已建立，记录已验证 provider 兼容点
- Phase 2 工具核心实现已落地：`bash`、`git_status`、`git_diff`、`git_log`
- `docs/tool-contracts.md` 已建立，记录当前工具接口契约
- Phase 2 Loop 烟雾验证通过：`bash` 与 `git_status` 已通过主循环消费验证
- Phase 3 模式系统 v2 已落地：5 模式配置驱动（`explore`/`spec`/`code`/`debug`/`verify`）、`initialize_modes`、工具过滤、`/mode`；`switch_mode` LLM 工具已移除
- `docs/mode-schema.md` 与 `docs/harness-state-machine.md` 已建立
- Phase 3 验证通过：模式切换、违规工具拦截、写入范围拦截均已完成本地验证
- Phase 4 工具第一版已落地：`compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage`、`report_quality`
- `docs/clang-integration-plan.md` 已建立
- Phase 4 解析验证通过：编译诊断、测试汇总、覆盖率提取、质量门评估均已完成本地验证
- 项目内闭环 Clang 工具链已落地到 `toolchains/llvm/current`
- 已完成真实本地 smoke test：编译、analyze、clang-tidy、profdata、llvm-cov report
- Phase 5 最小权限模型已落地：CLI 可对写入和命令执行做确认
- Doom Loop Guard 已落地：连续失败和重复失败动作会触发防护
- `docs/permission-model.md` 已建立
- `docs/context-management-design.md` 已建立
- Phase 5 第一版上下文管理已落地：旧 turn 摘要化、Observation 遮蔽化、最近 turn 保真化
- Phase 5A 上下文预算器已接入：按 mode 分配预算并为输出/推理预留空间
- Phase 5A ReducerRegistry 已落地：不同工具按类型裁剪 Observation，并返回 ContextStats / BudgetEstimate
- transcript-truth tool-result cutover 已落地：`ArtifactStore` 与共享 `artifacts/index.json` 已从运行时热路径移除，长文本结果现在由 `ToolCommitCoordinator` 串行落到 `.embedagent/memory/sessions/<session_id>/tool-results/<tool_call_id>/...`，Observation 使用 `*_stored_path`
- cutover review follow-up 已收口：`SessionSummaryStore` 的 session list 已优先走 SQLite projection，`ProjectMemoryStore` 已补实例级锁与原子写，review/git evidence 里的 `diff_artifact_ref` 残留已清理为 `diff_stored_path`
- transcript-truth cutover 相关设计/计划/分析/复核文档已归档到 `docs/archive/transcript-truth-tool-result-cutover/`，当前这轮 slice 已关闭
- Phase 5C Session Summary Store 已落地：会话关键状态会持久化到 `.embedagent/memory/sessions/<session_id>/summary.json`
- Phase 5D Project Memory Store 已落地：项目级 profile / recipe / known issue 已可落盘并注入上下文
- Phase 5E Resume Entry 已落地：CLI 已支持 `--list-sessions` 与 `--resume <session_id|latest|summary.json>`
- Phase 5F / Query cutover memory maintenance 已收口：tool-result cleanup 已改为基于 session-local stored paths，artifact browse/session summary/project memory 的可查询投影已切到 SQLite
- Phase 5 historical validation has been superseded by current pytest/lint/offline gates; the old `scripts/validate-phase5.py` compatibility script has been retired from active `scripts/`.
- Phase 5 权限细化已完成：已支持规则文件、allow / ask / deny、路径与命令模式匹配
- Query / Context 重构切片已启动：`session.py` 已补齐 transcript/event 数据模型，`query_engine.py` 已成为新主循环骨架，`loop.py` 已退化为兼容入口
- `ContextManager.build_messages(...)` 已开始接入 workspace intelligence、tool result replacement、duplicate suppression、activity folding 与 compact boundary 复用
- `workspace_intelligence.py`、`tool_execution.py` 与 `tests/test_query_engine_refactor.py` 已落地；新测试已覆盖 pending interaction resume、tool batch partition、intelligence/boundary 注入
- `DiagnosticsProvider` 已升级为工作集优先的文件级热点聚合：同一文件上的 compile/tidy/analyzer 诊断会折叠为单条热点证据，最近编辑/读取文件优先于被动报错文件
- `DiagnosticsProvider` 已继续推进第二段：`verify` 模式下会把 `report_quality`、`run_tests`、`collect_coverage` 等无路径失败聚成一条 quality gate summary，避免质量门信息只剩零散 observation
- `RecipeProvider` 已继续推进第二段：当时会按 mode 区分 `project / history / detected` recipe 来源优先级，并把 `stage` 作为细粒度 tie-break；该记录中的旧 `code` 口径已由后续 official cutover 替换为当前正式 `build` 模式，`verify` 模式仍偏 project/history test
- `QueryEngine` 已具备第一版 reactive compact retry：当模型明确报出 prompt/context 过长时，会记录 `compact_retry` transition、复用 compact boundary，并以内部 compact policy 自动重试一次
- `ContextManager` 已具备第一版 pre-provider auto compact：当常规上下文接近输入预算阈值且存在可摘要旧 turn 时，会在 provider 请求前用内部 compact policy 重新组装，并通过 `compact_boundary` 记录 `auto_threshold/pre_provider` 诊断字段
- `compact_retry` 现在已对前端可观测：snapshot 暴露最近 transition reasons / compact retry 次数，timeline 也会记录 `compact_retry` event
- `build_structured_timeline()` 现在也保留 turn/step 级 transitions，`compact_retry` 不再只存在于 raw timeline event
- `build_structured_timeline()` 也开始保留 `user_input_required / permission_required` 等等待态 transition，并把 turn 状态同步为 waiting 态
- `turn_end` 的非完成终止态也开始进入 structured timeline transitions，当前已覆盖 `max_turns`
- 终止态 transition 现在会携带停止原因文本，structured timeline 不再只暴露终止类型
- `SessionSnapshot` 也开始保留 `last_transition_message`，并在会话结束后重持久化最终状态，避免末尾 transition 丢失
- `SessionSnapshot` 现在还会暴露结构化 `recent_transitions`，前端可直接查看最近几条状态迁移及其 `reason / message / display_reason`
- `SessionSnapshot` 还补了 `last_transition_display_reason`，前端可直接消费用户语义层的状态名称；历史 summary 缺失 `display_reason` 时也会在读取 snapshot 时即时补齐
- structured timeline 的 transition 也开始带 `display_reason`，等待态与终止态都能直接映射到 GUI 友好的状态语义
- GUI inspector 现在已开始直接消费 `last_transition_display_reason / last_transition_message / recent_transitions`，Runtime 面板不再只依赖内部 termination reason
- GUI webapp 本地验证链已补齐第一段：`build.mjs` 依赖的 `esbuild` 现在已声明为显式 `devDependency`，并新增根目录 `run-local-tests.mjs` 作为本地 test runner；当前已验证 `node .\\run-local-tests.mjs` 与 `npm run build`
- resume consistency 已切到 transcript-truth 语义：新增 `transcript_store.py`、`session_restore.py`，`resume_session()` 已从 transcript replay 恢复 `Session`，`summary.json` 不再作为恢复真相源
- single-writer commit 已落地：工具线程只返回 raw observation，`ToolCommitCoordinator` 统一负责 tool-result 落盘、`tool_result` / `content_replacement` transcript append 与 SQLite projection 更新，并确保 projection 失败不会反向把 tool success 改成失败
- transcript hardening 已推进一段：`TranscriptStore.append_event()` 现已按 transcript 文件串行化写入，避免并发 append 时 `seq` 竞争与 JSONL 尾部截断放大
- transcript 损坏恢复已推进一段：`TranscriptStore.load_events()` 现在会在 `seq` 跳号/乱序时停止读取；`append_event()` 追加前会截断损坏尾部，避免“坏尾后新事件永久不可见”
- transcript 消息因果链已推进一段：`TranscriptMessage` 与 transcript `message/tool_result` 事件现在会显式写入 `parent_message_id`，`SessionRestorer` 在提供父引用时也会验证其存在，resume 不再只依赖“当前顺序碰巧正确”
- restore 因果校验已推进一段：`SessionRestorer` 现在在 `tool_result` 缺少前置 `tool_call`、或 `pending_resolution` 缺少前置 `pending_interaction` 时停止回放，避免 malformed transcript 被静默脑补成合法状态
- restore 顺序校验已继续推进：`SessionRestorer` 现在在 `step_started` 缺少 user turn、`tool_call` 缺少 active step，或 replay 事件引用了错误的 `turn_id / step_id` 时停止回放，避免恢复链凭空补造空 turn / 空 step，或把事件静默挂到错误的活动节点上
- compact boundary replay 已继续推进：`SessionRestorer` 现在会校验 `preserved_head_message_id / preserved_tail_message_id` 是否存在且顺序正确；同时 `QueryEngine` 会在 transcript 缺失时先 bootstrap 现有内存 session 的 message / compact boundary 历史，避免新 boundary 引用了 transcript 里不存在的旧消息
- compact boundary 写入策略已继续收口：同一 step 在 `compact_retry` 前后现在只会落一条有效 `compact_boundary`，避免把“摘要套摘要”再次写回 transcript，导致 restore 后边界漂移
- message replay 边界已继续推进：`SessionRestorer` 现在会拒绝错误 `turn_id` 的 `assistant/tool` message；如果消息携带 `step_id`，也必须已经存在匹配的 active step，不再允许“未显式落 `step_started` 的 assistant/tool message”作为建步前缀继续恢复
- transcript 引用 ID 校验已继续推进：`SessionRestorer` 现在会在出现重复 `message_id` 或重复 `tool_call.call_id` 时停止回放，避免 compact boundary、content replacement 和 tool topology 的引用目标变得不唯一
- pending resolution replay 已继续推进：`SessionRestorer` 现在会校验 `pending_resolution` 的 `turn_id / step_id` 是否仍然指向当前活动节点，避免错误 resolution 把真正的 pending 状态提前清掉
- pending resolution 引用一致性已继续推进：`SessionRestorer` 现在还会校验 `pending_resolution` 的 `interaction_id / tool_name / kind` 是否匹配当前 pending interaction，避免“指向别的等待态”的 resolution 被错误消费
- tool result replay 已继续推进：`SessionRestorer` 现在会校验 `tool_result` 的 `tool_name`，以及显式提供时的 `arguments`，是否与前置 `tool_call` 记录一致，避免仅凭 `call_id` 就把错误结果挂到现有 tool call 上
- content replacement replay 已继续推进：`SessionRestorer` 现在会校验 `content_replacement` 必须指向一个已恢复的 `tool` message，且其 `tool_call_id / tool_name` 不得与目标消息冲突，避免错误 replacement 文案污染后续上下文组装
- restore 诊断性已推进一段：`SessionRestoreResult` 现在会暴露 `consumed_event_count` 与 `stop_reason`，上层可以区分“完整恢复”与“在某个校验点停在自洽前缀”
- restore 诊断透传已推进一段：`resume_session()` / session snapshot 现在会把 `restore_stop_reason / restore_consumed_event_count / restore_transcript_event_count` 透出给 adapter 上层，恢复截断不再只能靠日志推断
- step / pending identity 唯一性已继续推进：`SessionRestorer` 现在会在出现重复 `step_id` 或重复 `pending_interaction.interaction_id` 时停止回放，避免后续事件挂接到不唯一的活动节点
- turn identity 唯一性已继续推进：`SessionRestorer` 现在会在 replay 新 `user` message 时校验 `turn_id` 唯一性，避免 turn 级投影和后续 transition/pending 挂接重新出现歧义
- compact boundary identity 唯一性已继续推进：`SessionRestorer` 现在会在出现重复 `compact_boundary.boundary_id` 时停止回放，避免前端或恢复链把两个不同摘要边界当成同一个历史切点
- tool result message identity 已继续推进：`SessionRestorer` 现在会把 `tool_result.message_id` 也纳入唯一性校验，避免 tool result 与既有 message 共享同一引用目标
- compact / resume replay 已推进一段：`compact_boundary` 现在会显式写入 transcript，并补齐 `preserved_head_message_id / preserved_tail_message_id`，`SessionRestorer` 已可回放 compact 边界而不丢失 preserved segment 元数据
- pending interaction replay 已推进一段：`resume_pending()` 现在会把 `pending_resolution` 与恢复阶段生成的 `tool_result` 一并落入 transcript，恢复后的 tool call 状态不再卡在 `pending`
- tool interrupt / retry 已推进第一段：`tool_started` 之后若会话被取消，`QueryEngine` 现在会写入 synthetic interrupted tool_result，并在 transcript / timeline / adapter `tool_finished` 事件中统一表现为 aborted
- tool interrupt / retry 已继续推进第二段：parallel batch 中的 `discarded` synthetic result 仍会进 transcript，但不再误计入 guard 失败累计导致整轮提前 `guard_stop`
- tool interrupt / retry 已继续推进第三段：`StreamingToolExecutor` 并行批次已改成流式 start/result，`max_parallel_tools=1` 场景下现在能稳定落下“首个 action interrupted、后续未开始 action discarded”的 transcript 语义
- tool interrupt / retry 已继续推进第四段：`tool_call` transcript 现在在 assistant action 阶段统一落盘，因此 discarded action 也能保持完整 `tool_call -> tool_result` 链路
- tool interrupt / retry 已继续推进第五段：Windows 下 `bash` 现在以新进程组启动，并在取消时优先发送 `CTRL_BREAK_EVENT`；长命令用户中断不再依赖 `taskkill` 成功才会及时返回
- tool interrupt / retry 已继续推进第六段：`StreamingToolExecutor` 现在会直接观察 cancel event，因此 `max_parallel_tools>1` 时排队 action 在取消后会保持 `discarded`，不再偷偷升级成已启动的 `interrupted`
- tool interrupt / retry 已继续推进第七段：当前 batch 一旦已经出现 `discarded`，同一条 assistant plan 中后续 batch 会统一落 `discarded` result，而不会继续真实执行后续写动作
- tool interrupt / retry 已继续推进第八段：`StreamingToolExecutor` 现在对并行 batch 引入 idle timeout / cancel 收口；started 但迟迟不返回的只读 action 会落 `timeout` 或 `interrupted`，尚未开始的兄弟 action 会落 `discarded`，session 不再因单个卡死线程无限等待
- timeline 持久化已推进一段：`SessionTimelineStore` 现在与 transcript 一样按文件串行化写入并记录单调 `seq`；GUI raw timeline 顺序不再只依赖 `created_at`
- GUI turn 锚点已收口：webapp reducer 现在会给本地用户消息分配 provisional turn anchor，并在 `turn_started` 到来时整体回填，`/mode ... <message>` 这类“先命令结果、后真实 turn”链路不再把 command card 绑到伪 turn id 上
- GUI active-session runtime 已推进到 transport-state + activity-state：GUI backend 已新增统一 `session_event` envelope 和统一的 interaction response route；S04 后已删除 `GET /api/sessions/{session_id}/events?after_seq=N` reload 信号入口，transport recovery 通过 session bootstrap reload 收口；前端当前会以 `sessionTransport + history.activities` 作为 active session 读模型骨架
- Inspector / Timeline 交互边界已收口：Inspector 现在使用统一 `InteractionPanel` 处理当前 pending interaction，Timeline 只显示交互历史摘要，不再保留第二套 inline approve / answer 控件
- transport / restore 退化语义已补齐第一版：`ThreadsafeAsyncDispatcher` 现在会返回带 `reason` 的调度结果；`SessionRestorer` 遇到缺失可信 `interaction_id` 的 pending interaction 时会显式停在 `interaction_expired`；webapp transport state 已升级到 typed reload state
- GUI runtime hardening 第二段已完成：transport/bootstrap recovery 现在显式区分 `reload_required / degraded`，HTTP / WebSocket 错误边界已 typed 化；当前 webapp activity runtime 接管 reload state、command-result fallback、detached turn item 排序与 session-scoped runtime reset
- GUI runtime hardening slice 已关闭：相关设计与实施文档已归档到 `docs/archive/gui-runtime-hardening/`
- GUI timeline event-anchor unification 已完成：`command_result / context_compacted / session_error / permission_request / user_input_request` 现在在协议、GUI backend、前端 reducer、structured timeline 与 replay 路径上共享 `turn_id / step_id / step_index` 契约；slash/workflow 命令也已纳入正式 turn 生命周期
- turn-level `transitions` / `tool_calls` 历史能力已被收口到 bootstrap `history.activities`，`/help`、`/review`、`/run` 这类命令结果在刷新和重放后不再依赖前端从 nested turns 重建
- `ContextManager` 的 `compacted` 判定已收紧：常规 old-turn summary 不再单独触发 GUI `context_compacted` 卡片
- GUI timeline event-anchor 相关 spec/plan/analysis 已归档到 `docs/archive/gui-timeline-event-anchors/`，当前这轮 slice 视为关闭
- GUI backend broadcast 已硬化：`WebSocketFrontend` 现在会在广播前冻结连接快照，并在独立锁下做 connect/disconnect/cleanup，连接集变化不再触发 `Set changed size during iteration`
- QueryEngine session 互斥已补齐：`InProcessAdapter` 现在把 `state.lock` 传给 `QueryEngine`，后者会在上下文构建、消息追加、transition/tool_result 落盘、compact boundary 写入和 summary refresh 等关键路径上持锁，避免运行中的 session 与外部模式/快照操作共享可变 `Session` 时发生竞态
- GUI bundle runtime discovery 已收口：新增公共 `runtime_discovery.py` 作为 bundle 根目录单一事实源，`ToolContext`、GUI launcher 与 `check-bundle-dependencies.py` 已统一使用强签名检测，不再允许“GUI 自己识别到 bundle、工具层却识别不到”的分裂状态
- GUI launcher bundle 契约已加固：`embedagent-gui.cmd` 与 `prepare-offline.ps1` 生成脚本现已显式导出 `EMBEDAGENT_BUNDLE_ROOT` 并对齐 CLI PATH；`validate-offline-bundle.ps1` 还新增了 launcher contract 校验，能直接拦截这类脚本漂移
- GUI 静态资产门已收口到直连打包链：`package-lib.ps1`、`prepare-offline.ps1` 与 `build-offline-bundle.ps1` 现在统一检查 `index.html` / `app.js` / `app.css` / `katex.min.css`，残缺 staging 不会再静默进入 `offline-dist`
- Phase 7 设计基线已建立：`docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md`
- Phase 7 初始脚本骨架已落地：`scripts/prepare-offline.ps1` 已可生成 `build/offline-staging/EmbedAgent/`、launcher、模板配置和 manifest/checksum 草案，并已通过 `powershell.exe -NoProfile -File scripts/prepare-offline.ps1 -SkipBuild` 验证
- Phase 7 build 脚本骨架已落地：`scripts/build-offline-bundle.ps1` 已可把 staging bundle 复制到 `build/offline-dist/`、重写 manifest、重算 checksum，并生成 zip
- Phase 7 validate 脚本骨架已落地：`scripts/validate-offline-bundle.ps1` 已在 skeleton bundle 上验证通过，且 `-RequireComplete` 会按预期对缺失资产返回失败
- Phase 7 真实资产接入已打通第一段：`scripts/offline-assets.json` 已固定 `python_embedded_x64` 与 `mingit_x64`，`prepare/build/validate` 已完成真实 zip、SHA256、sources seed、license notice 与 launcher 校验
- Phase 7 真实资产接入已继续扩展到 `ripgrep_x64` 与 `universal_ctags_x64`，当前 `prepare/build/validate -RequireComplete` 已在四类核心资产上通过
- GUI 状态语义已收口：session status 现在以 `session_snapshot` 为权威，补齐了 `session_status`、`reasoning_delta`、`thinking_state`、稳定 `tool_call_id` 与 GUI 专用懒加载文件树接口
- GUI / Core 已完成第一段高拟态 clean-room 升级：时间线 API 现在以 `turns[].steps[]` 为主，单个用户问题下的多轮 Agent 自推进会拆成独立 step；GUI 也已开始按 step 渲染 thinking / tool / assistant
- 托管运行环境摘要已接入 ToolRuntime / SessionSnapshot / GUI Runtime inspector：当前会显示 `runtime_source`、`bundled_tools_ready`、`fallback_warnings` 与 `resolved_tool_roots`
- workbench 第一段已落地：Tool Runtime 可自动检测 `CMakeLists.txt` / `Makefile` 与历史成功命令 recipe；`compile_project` / `run_tests` / `run_clang_tidy` / `run_clang_analyzer` / `collect_coverage` 支持 `recipe_id`；slash command 新增 `/recipes` 与 `/run <recipe_id>`；GUI Inspector 已补 `Run` / `Problems` 并可直接执行 recipe
- todo 已切换为 session-scoped：真实会话默认使用 `.embedagent/memory/sessions/<session_id>/todos.json`，新建会话不再继承旧会话 todo
- 新 GUI webapp 已建立：`src/embedagent/frontend/gui/webapp/` 使用 React + Vite 构建，产物已写回 `src/embedagent/frontend/gui/static/`
- `scripts/validate-gui-smoke.py` 已升级：当前源码路径 smoke 可覆盖 tool / permission / ask_user / session todo 隔离、`/review` workflow 与 renderer 报告
- unified input / slash command / workflow 第一版已落地：`submit_user_message` 已统一分发普通消息与 `/help` `/mode` `/sessions` `/resume` `/workspace` `/clear` `/plan` `/review` `/diff` `/permissions` `/todos`
- 协议层已扩展 `CommandResult`、`PlanSnapshot`、`TurnRecord`、`TimelineItem` 与增强版 `SessionSnapshot`；GUI 已接入 command result、plan pane、command cards 与 slash command hint
- `/review` 已升级为结构化 findings 输出；GUI 工具卡片开始使用 Core 下发的 `tool_label` / `progress_renderer_key` / `result_renderer_key` 做分支渲染
- GUI 已新增独立 review inspector；后端已暴露 tool catalog API，前端开始用 Core 的工具目录为旧 timeline / fallback 展示补足 label 与 renderer
- 已补 workflow/filtering 回归测试：`test_tools_package.py` 现在覆盖 `schemas_for(mode, workflow)` 过滤与 tool metadata 注入，GUI webapp `run-tests.mjs` 现在覆盖 review command / permission context 状态回归
- 已完成 dist/source GUI 布局重新对齐：重建后的离线 bundle 已携带 `static/assets`、Fixed Version WebView2 109、无 `__editable__.embedagent-*.pth` 泄漏，且 bundle 级 `validate-offline-bundle.ps1`、`validate-gui-smoke.py`、`check-bundle-dependencies.py` 全部通过
- Phase 7 打包链路已开始切换到声明式控制面：`scripts/package.config.json`、`scripts/package-lib.ps1` 与 `scripts/package.ps1` 已落地；当前 `doctor/deps/assemble/verify/release` 已可通过 mocked orchestration contract 运行，并统一写入 `build/offline-reports/`

项目下一步：继续推进 Phase 4 真实工程验证，在 Win7 bundle 中验证 Fixed Version WebView2 109 路径，并把 Phase 7 的 site-packages 精简、真实 release pipeline 验收和 Win7 bundle 验收接上；Pi-inspired minimal Core Phase A-M 已收口，后续重点转为真实 Win7 smoke、真实 C/C++ 工程验证和架构守卫回归。

---

## 3. 下一步优先级

### P0：立刻要做（当前关键路径）

1. 推进 Phase 4 的真实 C 工程与 Win7 验证
2. 在 Win7 bundle 中完成 GUI Chromium 基线实机验证并记录结果
3. 为当前 `package.ps1 release` 路径评估并收敛 `site-packages` 的精简导出方案
4. 运行 contract-backed offline bundle 的 clean Win7 unpack-and-run smoke 并记录结果
5. 合并 GUI/Core 架构改动前执行 pre-merge architecture gate，防止 stale compatibility paths 回流，并保持 source-of-truth docs 与当前正式架构同步

实现备注：

- Phase 1 已按当前可用条件验收完成；`GLM5 int4` / `Qwen3.5` 因环境不具备暂不纳入阻塞项。
- 当前原型已收敛到 `src/embedagent/` 包结构，打包入口与导入路径已同步更新。
- Phase 2 里程碑已满足：文件读写、命令执行、Git 状态/差异/日志均已具备并完成 3.8 本地验证。
- Phase 3 v2 里程碑已满足：5 模式（explore/spec/code/debug/verify）、配置驱动、工具过滤、用户主导切换均已完成 3.8 本地验证。
- Phase 4 已具备项目内闭环工具链，但默认 recipe、真实 C 工程和 Win7 验证仍需补齐。
- Phase 5/6 legacy validation scripts have been retired from active `scripts/`; current verification uses focused pytest coverage, frontend helper tests, lint, and offline bundle/runtime contract gates.
- Phase 6 自动化验证口径已切到当前 GUI/TUI/frontend/backend 测试与 Win7 Chromium 实机证据，当前缺口仍是 Win7 真实交互体验。
- Phase 7 现已完成设计基线、ADR、`prepare/build/validate` 三段脚本骨架，以及 Python / MinGit / rg / ctags 的真实资产接入；公共控制面 `package.ps1` 已接上，下一步应转向 site-packages 精简与完整 bundle 验收。

### P1：紧随其后

1. 收敛 Clang bundle 的版本组合与默认命令 recipe
2. 决定是否将 memory browse / inspect 作为 Phase 6 收口项
3. 评估终端前端稳定后是否推进 stdio JSON-RPC adapter
4. 决定是否从 `.venv\Lib\site-packages` 继续直拷，还是切到更精简的运行时导出策略
5. 在 Win7 虚拟机上对当前四类核心资产 bundle 做一次真实验收
6. 将 default C/C++ workflow package 继续拆成可独立验证的 tracker tasks，避免一次性移动 harness/runtime 边界

---

## 4. 近期任务板

| 编号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| T-001 | 建立最小 `pyproject.toml` + 代码骨架 | `completed` | 已收敛为 `src/embedagent/` 包结构 |
| T-002 | 实现 `OpenAI-compatible LLM Adapter` | `completed` | 同步+流式，Python 标准库，无厂商 SDK |
| T-003 | 实现第一批工具（read/list/search/edit） | `completed` | 已按 `docs/tool-design-spec.md` 规范落地 |
| T-004 | 实现最小主循环 + CLI 入口 | `completed` | 本地假模型闭环已跑通 |
| T-005 | Phase 1 里程碑验证（GLM5 + Qwen3.5） | `completed` | 目标模型环境不具备，按 Moonshot + Python 3.8 验证口径验收 |
| T-006 | 实现 Phase 2 工具（bash / git） | `completed` | 已补齐工具契约与 Loop 烟雾验证 |
| T-007 | 实现模式系统 v1（dict + 工具过滤） | `completed` | 已补齐文档与本地验证 |
| T-008 | 实现 Phase 4 Clang 工具链第一版封装 | `in_progress` | 已有本地闭环工具链与 recipe-aware build/test 入口，待真实工程验证与版本收敛 |
| T-009 | 实现 Phase 5 最小权限与防循环保护 | `completed` | 权限模型、Doom Loop Guard、ContextManager、mode-aware budget、Artifact Store、SessionSummaryStore、ProjectMemoryStore、Resume Entry、MemoryMaintenance 已落地；历史 phase 验证脚本已退役，当前由 pytest/lint/offline gates 覆盖 |
| T-010 | 完成 Phase 6 前端协议与 TUI IA 设计 | `completed` | `frontend-protocol.md` 与 `tui-information-architecture.md` 已建立 |
| T-011 | 实现 Phase 6A InProcessAdapter | `completed` | CLI 已改为通过 adapter 驱动 Core，并完成最小行为验证 |
| T-012 | 落地模块化终端前端 | `completed` | 已完成 `src/embedagent/frontend/tui/` 模块化拆包，`src/embedagent/frontend/tui/` 已按新架构迁移，接入 timeline / workspace / artifact / todo 浏览接口，保留 `embedagent.tui` 兼容入口；下一步是继续做真实控制台 / Win7 手工验证与交互细化 |
| T-013 | 建立 Phase 6 验证入口 | `completed` | 历史 phase 脚本入口已退役；当前 Phase 6 验证入口为 GUI/TUI/frontend/backend focused tests、visual harness 与 Win7/WebView2 bundle smoke 证据 |
| T-014 | 建立 Phase 7 离线打包设计基线 | `completed` | 已新增 `docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md` |
| T-015 | 实现 Phase 7A prepare-offline 骨架 | `completed` | 已新增 `scripts/prepare-offline.ps1`，可生成 `build/offline-staging/EmbedAgent/`、launcher、模板配置、manifest 与 checksum 草案，并支持 `-SkipBuild` |
| T-016 | 实现 Phase 7B build-offline-bundle 骨架 | `completed` | 已新增 `scripts/build-offline-bundle.ps1`，可消费 staging bundle，生成 `build/offline-dist/<artifact>/` 与 zip，并重写 dist manifest/checksum |
| T-017 | 实现 Phase 7C validate-offline-bundle 骨架 | `completed` | 已新增 `scripts/validate-offline-bundle.ps1`，可校验 skeleton bundle，并支持 `-RequireComplete` 切换到严格门禁 |
| T-018 | 接入 Python embeddable 与 MinGit 真实资产 | `completed` | 已新增 `scripts/offline-assets.json`，并完成真实 zip 下载、SHA256 固定、staging 解压、sources seed、license notice 与 `-RequireComplete` 验收 |
| T-019 | 接入 ripgrep 与 Universal Ctags 真实资产 | `completed` | 已扩展 `scripts/offline-assets.json` 与 `prepare/build/validate`，完成真实 zip 下载、SHA256 固定、sources seed、license notice 与 `-RequireComplete` 验收 |
| T-020 | 实现新架构协议层（protocol/core/frontend） | `completed` | 已新增 `protocol/` 层定义 CoreInterface/FrontendCallbacks，`core/` 层实现 AgentCoreAdapter，`frontend/gui/` 实现 PyWebView 前端，架构测试 17 项全通过 |
| T-021 | GUI 前端与后端功能联动 | `in_progress` | 已完成 session-scoped todo、权威 session snapshot 状态事件、稳定 tool_call_id、reasoning/thinking 事件、GUI 懒加载文件树、新 React/Vite webapp 构建、slash command / plan pane / command cards、structured review command、review inspector、tool catalog fallback、step-based timeline、Runtime inspector、Run / Problems 面板、runtime hardening（typed replay / restore / projector ownership）与 `/review` smoke；剩余缺口是更完整的 workflow 深化与 Win7 实机验证 |
| T-026 | unified input / slash command / workflow 第一版 | `completed` | 已打通 `submit_user_message -> slash command dispatcher -> command_result / plan_updated -> GUI/TUI` 闭环，并补齐协议类型、计划存储、权限上下文与 focused tests |
| T-022 | 零依赖打包：Python 依赖完整导出 | `completed` | 已新增 `scripts/export-dependencies.py`，确保所有 Python 依赖（含传递依赖）完整导出到 site-packages |
| T-023 | 零依赖打包：依赖完整性验证 | `completed` | 已新增 `scripts/check-bundle-dependencies.py`，验证 bundle 包含所有必需依赖 |
| T-024 | 零依赖打包：内网部署文档 | `completed` | 已新增 `docs/intranet-deployment.md` 和 `docs/offline-packaging-guide.md`，提供完整内网部署指南 |
| T-025 | 零依赖打包：内网配置模板 | `completed` | 已新增 `config/config.json.template`，预配置内网大模型服务示例 |
| T-027 | Phase 7 打包控制面收口 | `in_progress` | `scripts/package.ps1`、`scripts/package.config.json`、`scripts/package-lib.ps1` 与 `tests/test_packaging_control_plane.py` 已打通 `doctor/deps/assemble/verify/release` mocked orchestration；下一步是完成文档迁移并在真实 bundle 路径上验收 |
| T-028 | Query / Context 内核重构切片 | `completed` | 已落地 `QueryEngine`、transcript/event 模型、workspace intelligence broker、tool capability metadata、batch tool orchestration、pending interaction resume、`transcript_store.py`、`session_restore.py`、transcript-truth resume、`parent_message_id` 因果链、timeline `seq` 顺序、parallel tool timeout/cancel 收口、single-writer tool commit、session-local tool-result store、SQLite projection cutover，以及 websocket/session-lock 竞态硬化；相关 transcript-truth cutover 设计/计划/分析/复核文档已归档到 `docs/archive/transcript-truth-tool-result-cutover/` |
| T-029 | Pi-inspired minimal Core 第一阶段：durable operation log / reducer | `completed` | Phase A 已收口：新增 `OperationLogReducer`、`SessionRestoreResult.operation_state`，并将 operation reducer 硬切为只消费显式 schema_v2 lifecycle；`QueryEngine` 已覆盖 turn、agent step、context assembly、context snapshot、provider request、tool call、pending interaction、workflow patch 与 save point；restore-time snapshot 会关闭未完成 operation，live snapshot 会保留 active operation，二者均已投影 `operation_diagnostics`；Phase B HookBus/reducer registry 已由 T-030 收口 |
| T-030 | Pi-inspired minimal Core Phase B：HookBus / reducer registry | `completed` | Phase B 已收口：新增 `AgentEventBus`，`ExtensionManager` 公开 extension hook family 已迁到 source-aware reducer dispatch，并保留公共 extension API；后续 operation lifecycle 编排已由 Phase C AgentKernel lifecycle extraction 收口 |
| T-031 | Pi-inspired minimal Core Phase C：AgentKernel lifecycle extraction | `completed` | Phase C 已收口：新增 `AgentLifecycleJournal`、`AgentKernel` / `AgentTurnFrame`，并将 `AgentLoop` 升级为 turn-loop owner；turn frames、save points、pending create/resolve、abort、compact retry、guard-stop 与 safety-limit compatibility transition 均已通过 lifecycle boundary；`QueryEngine` 不再拥有 `_run_loop_impl`、`_run_loop` 或 `_is_completion_signal` |
| T-032 | Pi-inspired minimal Core Phase D：default C/C++ workflow package | `completed` | Phase D 已收口：bare `ToolRuntime` 不再注册默认 C/C++ workflow tools，也不再 import `tools/harness_runtime.py`；默认 C/C++ package 通过 `CHarnessWorkflowExtension.register_tools(...)` 注册 recipe、quality、evidence 与 `task_status` 工具，metadata/packs 归属 `src/embedagent/harness/`；hosted adapter catalog 仍默认暴露 C/C++ workflow tools |
| T-033 | Pi-inspired minimal Core Phase E：self-extension authoring loop | `completed` | Phase E 已收口：`SelfExtensionAuthoringService` 与 `author_local_capability` 可生成 skills/prompts/recipes/disabled extension skeletons；authoring 只写 workspace-bound 文件，不 reload resources，不 load Python code，仍通过 `workspace_write` 权限与后续 reload/load 分离 |
| T-034 | Pi-inspired minimal Core Phase F：repo-side offline bundle validation | `completed` | Phase F 已收口：`scripts/offline-runtime-contract.json` 成为 runtime-invoked bundled external tools 的单一契约；bundle validators 共享该契约；clean Win7 smoke 仍是实机发布门禁 |
| T-035 | Pi-inspired minimal Core Phase G：turn snapshot / capability registry foundation | `completed` | Phase G 已收口：`TurnSnapshot` 成为 provider-request 冻结输入；`CapabilityRegistry` 可投影 tools、local file resources、slash commands 与 credential-free model profile；activation/execution 仍由 extension/runtime 边界负责 |
| T-036 | Pi-inspired minimal Core Phase H：runtime configuration reducer | `completed` | Phase H 已收口：`RuntimeConfigReducer` 从 `runtime_configured`、`resource_reloaded` 与 provider snapshot metadata 投影 credential-free runtime configuration；该 projection 不驱动 activation、execution、reload、extension loading 或 permission |
| T-037 | Pi-inspired minimal Core Phase I：workflow package manifest/read model | `completed` | Phase I 已收口：`WorkflowPackageManifest` 描述 package identity、tools、packs、supported modes/workflow states 与 resource scopes；默认 C/C++ package manifest 由 harness-owned constants 派生并通过 `ExtensionManager.package_manifests()` 投影到 `CapabilityRegistry.workflow_package` descriptors；manifest 不驱动 tool activation 或 permission |
| T-038 | Pi-inspired minimal Core Phase J：structured compaction state | `completed` | Phase J 已收口：`CompactionStateReducer` 从 `compact_boundary` transcript events 投影 structured compaction state；restore results、managed sessions、protocol snapshots 与 session snapshots 暴露 `compaction_state`；projection 不驱动 context selection 或 permission |
| T-039 | Pi-inspired minimal Core Phase K：recovery state | `completed` | Phase K 已收口：`RecoveryStateReducer` 从 `recovery_marker` transcript events 投影 hosted resume recovery state；resume 写入 safe recovery marker；projection 不改变 restore validation、tool activation、context selection 或 permission |
| T-040 | Pi-inspired minimal Core Phase L：pack compatibility cleanup | `completed` | Phase L 已收口：删除 `src/embedagent/tooling/packs.py` 与 `embedagent.tooling` package-root pack aliases；默认 C/C++ workflow pack truth 只从 `src/embedagent/harness/packs.py` 暴露，active tool selection 与 schema projection 不变 |
| T-041 | Pi-inspired minimal Core Phase M：core alias cleanup | `completed` | Phase M 已收口：删除 `MODE_REGISTRY`、`_DEFAULT_SANITIZER`、`get_default_sanitizer()`、`_inprocess_adapter` 与 `_get_adapter_class()` 等核心兼容别名；正式访问入口收敛为 `get_mode_registry()`、`get_command_sanitizer()` 与 `get_inprocess_adapter()` |
| T-042 | Pi-aligned tool architecture：minimal bash-centered tool surface | `completed` | 已收口：Core 模型可见命令原语收敛为 `bash`，旧 `run_build`/compiler helper surface 从公开工具、workflow packs 与文档中删除；C/C++ workflow helper 继续由默认 workflow extension 激活；recipes 增加 readiness/prerequisite/refusal 语义；命令输出改为 bytes-first 解码并同步离线 Bash runtime contract |

---

## 5. 里程碑进度

| 阶段 | 名称 | 状态 | 说明 |
|------|------|------|------|
| Phase 0 | 仓库基线与工作约束 | `completed` | 已完成文档、版本策略、治理基线、工具规范 |
| Phase 1 | 最小可工作 Loop | `completed` | 已完成 Python 3.8 与真实 OpenAI-compatible 工具闭环验证 |
| Phase 2 | 工具集 v1 | `completed` | 已实现 bash / git 工具，并完成 3.8 本地验证 |
| Phase 3 | 模式系统 v2 | `completed` | 5 模式配置驱动（explore/spec/code/debug/verify）、initialize_modes、工具过滤、/mode 已完成；switch_mode LLM 工具已移除 |
| Phase 4 | Clang 工具链 | `in_progress` | 已有项目内闭环工具链，待真实工程与 Win7 验证 |
| Phase 5 | 质量保障层 | `completed` | 权限、上下文、记忆、恢复与 cleanup 已落地；修复根目录文件写入边界后，专项验证脚本已复验通过 |
| Phase 6 | CLI / TUI / GUI | `in_progress` | InProcessAdapter 已扩展 workspace / timeline / artifact / task 前端接口；终端前端已拆为 `frontend/tui` 子模块；GUI 已切换到 React/Vite webapp + PyWebView 宿主，并已补 T3code-style timeline/composer/diff surfaces；当前环境 smoke 覆盖 tool / permission / ask_user / task 隔离，dev-only visual harness 覆盖 load/chat/diff；待 Win7 Chromium 实机验证与编辑闭环细化 |
| Phase 7 | 打包与离线交付 | `in_progress` | 设计基线、ADR、`prepare/build/validate` 三段脚本骨架已完成；Python/MinGit/rg/ctags 真实资产接入已完成；`package.ps1` 控制面已接上 mocked orchestration；GUI 依赖与 bundle-local smoke 已进入交付物，`validate-offline-bundle -RequireComplete`、`check-bundle-dependencies.py` 与 bundle 级 windowed GUI smoke 已通过；待真实 release pipeline 与 Win7 bundle 实机验收 |

---

## 6. 当前风险与关注点

| 编号 | 风险 | 当前判断 | 应对方式 |
|------|------|----------|----------|
| R-001 | Python 版本上滑 | 高 | 强制保持 `>=3.8,<3.9`，文档与配置双锁定 |
| R-002 | 过早做 UI 导致核心失焦 | 高 | Phase 6 才做 TUI，Phase 1 只做最简 CLI |
| R-003 | 内网模型 function calling 格式不标准 | 高 | Phase 1 里程碑强制在真实模型上验证，发现问题立即在 LLM Adapter 层补充兼容处理 |
| R-004 | 工具集设计退化（工具增多、描述变复杂） | 中 | `docs/tool-design-spec.md` 有审查清单，每次新增工具前必须过清单 |
| R-005 | 文档和实现脱节 | 高 | 每轮关键变更必须同步更新 tracker / change log / roadmap |
| R-006 | Clang bundle 包大小过大 | 低 | 静态链接验证已通过，打包细节推到 Phase 7 处理 |
| R-007 | provider 兼容差异未系统沉淀 | 中 | 已确认 Moonshot `kimi-k2.5` 需要 `/v1` 和 `reasoning_content`，后续整理到适配文档 |
| R-008 | 当前仓库缺少真实 C 构建入口 | 中 | 已完成本地 smoke test，后续仍需接默认命令和真实工程 |
| R-009 | 当前闭环工具链存在跨版本组合 | 中 | 现状已通过本地 smoke test，后续需要继续收敛到同版本或自建包 |
| R-010 | 当前上下文压缩仍较弱 | 中 | 已有 mode-aware budget、reducer registry、Artifact Store、SessionSummaryStore、ProjectMemoryStore 与 Resume Entry，后续继续补生命周期清理与可选 LLM condenser |
| R-011 | Python embeddable distribution 的 CRT / UCRT 本地部署复杂 | 中 | 用 Phase 7 preflight 清单和本地 DLL bundling 策略收口 |
| R-012 | 第三方二进制来源、License 和 checksum 追溯不足 | 中 | 用 bundle manifest 记录 version/source/license/checksum，并纳入构建产物 |
| R-013 | prepare 阶段与最终 build/validate 阶段契约不清晰，后续脚本容易返工 | 中 | 先把 `prepare/build/validate` 的输入输出边界写清，再继续实现 |
| R-014 | 当前 build 已验证四类核心资产可启动，但 `site-packages` 仍是直拷 `.venv`，离最终 bundle 仍有优化空间 | 中 | 下一步收敛更精简的运行时包导出方案 |
| R-015 | validate 默认允许 skeleton bundle 以告警通过，若无人切到 `-RequireComplete` 可能误判“已可交付” | 中 | 在正式验收和 CI 入口中强制使用 `-RequireComplete` |
| R-016 | 直接拷贝 `.venv\Lib\site-packages` 可能带来过大的 bundle 体积 | 中 | 评估更精简的运行时导出方案，再决定是否替换当前实现 |
| R-017 | 离线 bundle 容易因未重建或直接拷贝开发 `.venv` 而把旧 GUI 布局或项目内 editable `.pth` 带进发布物 | 中 | 保持 `prepare/build/validate` 串联执行，并在 bundle 验证中强制检查 `static/assets`、Fixed Version WebView2 和无 `__editable__*.pth` |
| R-018 | transcript-truth cutover 已完成，但后续增强若绕过单写提交边界，仍可能重新引入 projection/summary 漂移 | 低 | 继续保留 focused regression tests 覆盖 mode、timeline、pending interaction、context assembly 与 stored-path replacement；新增增强时优先复用 `ToolCommitCoordinator + ProjectionDb` 主线 |
| R-019 | GUI interaction 事件当前仍是“backend raw event + frontend local append”双轨去重，而非单一真相源 | 中 | 当前已统一结构并按 `interaction_id` 去重；若后续继续演进 event-sourced runtime，应评估把 Timeline/Inspector 收敛到单一 interaction event 主线 |
| R-020 | launcher 模板与 `prepare-offline.ps1` 仍存在重复定义，后续修改若不同步仍可能重新引入 bundle 契约漂移 | 中 | 当前已通过公共 runtime discovery + validate launcher contract 把缺陷前移到验收阶段；后续可继续收敛 launcher 生成来源 |
| R-021 | `package.ps1`、`prepare-offline.ps1` 与 `build-offline-bundle.ps1` 之间仍有部分共享打包逻辑分散在多个脚本，后续改动仍可能引入新分叉 | 中 | 当前已先把 GUI 静态资产门和 launcher 契约门收口到共享 helper / validator；后续继续抽公共能力而不是三处平行演化 |
| R-022 | 当前 mode / tool / permission 强耦合导致真实任务频繁切模式、奇怪拒绝和工具调用退化 | 高 | 已建立 `docs/agent-harness-v2.md` 作为整体重构基线；后续优先按 harness / tool contract / permission DSL 的顺序做切片，而不是继续在旧机制上打补丁 |
| R-023 | 架构 cutover 已完成，但若后续新增功能绕过 Harness/Protocol/Permission 的正式边界，仍可能重新引入平行术语和隐式兼容层 | 中 | 继续把 `README` / `AGENTS` / architecture docs 作为唯一 source of truth；新增功能优先复用 Harness、TaskGraph、recipe runtime 和 session snapshot，而不是再建第二套路径 |
| R-024 | 文档分层、模块映射和同步流程尚未完全建立 | 高 | Batch B 已完成：遗留文档已归档，操作指南已下沉，模块文档与 guides/ 索引已同步 |
| R-025 | Pi-inspired minimal Core 若被理解成一次性重写，可能破坏已收口的 hosted C/C++ workflow、Win7 bundle 和 self-extension baseline | 高 | 按 durable operation log -> HookBus/reducer -> AgentKernel -> default workflow package 的顺序做小切片；每片保持当前行为回归通过，并在 source-of-truth docs 中明确“目标蓝图”和“已实现 baseline”的边界 |
| R-026 | GUI/Core 架构改动若只跑局部测试，可能绕过 extension、permission、workflow package 或 GUI runtime 边界 | 高 | 合并前执行 pre-merge architecture gate；webapp source 变更必须运行 `npm run build` 并提交生成的 GUI static assets；Win7/offline 发布判断必须另有真实 bundle smoke 证据 |

---

## 7. 最近更新记录

| 日期 | 更新内容 |
|------|----------|
| 2026-06-16 | GUI app-level workspace/thread management polish: 新增 frontend-local `app-home-model`，Sidebar 与 NoWorkspaceState 共享 project/thread 展示投影；project recents 局部滚动，Threads 管理区保持可见；visual harness app 场景改用隔离 `EMBEDAGENT_GUI_APP_HOME` 并检查 project/thread 管理表面可见，不改变 Agent Core、产品协议或 Win7/offline runtime 依赖。 |
| 2026-06-16 | GUI timeline interaction polish slice: timeline work row / turn fold expansion 改为 frontend-local controlled UI state；`?visual_debug=1` hook 新增 deterministic `timeline` / `interaction` fixtures；`scripts/gui-visual-debug.mjs --scenario timeline,interaction` 可由 Codex 自动加载真实 GUI 状态、点击展开、截图并检查 console/DOM，不改变 Agent Core、产品协议或 Win7/offline runtime 依赖。 |
| 2026-06-16 | T3code GUI timeline/diff refinement 收口：changed-files card 改为目录树，Diff right-panel 改为 file rail + diff viewport，窄栏/移动端自动单列；`scripts/gui-visual-debug.mjs --scenario diff` 改用显式 `?visual_debug=1` fixture hook 稳定打开真实 DiffPanel 并检查 file rail/DOM/console；修复 T3 timeline projection 的 loose system item 与 detached item 丢失问题。 |
| 2026-06-15 | T3code GUI 核心体验切片落地：新增 T3-style timeline rows、composer 内 permission/user-input panel、right-panel Diff surface 与 dev-only Playwright visual harness；`npm run visual:gui -- --scenario all --bundle-root <bundle-root>` 已可启动真实 GUI、截图并检查 console/DOM；同时修复 streaming final content 重放导致的 assistant 文本重复问题；completed working docs 已迁入 `docs/archive/t3-parity-gui-debug/` |
| 2026-06-14 | Pi-inspired minimal Core Phase D 收口：bare `ToolRuntime` 已恢复 workflow-neutral 构造；默认 C/C++ workflow package 通过 `CHarnessWorkflowExtension.register_tools(...)` 注册 workflow tools，并在 `src/embedagent/harness/tool_metadata.py` / `src/embedagent/harness/packs.py` 内拥有 metadata 与 pack 定义；旧 `src/embedagent/tools/harness_runtime.py` 已删除。下一步进入 Phase E self-extension authoring loop |
| 2026-06-14 | Pi-inspired minimal Core Phase C 收口：新增 `AgentLifecycleJournal`、`AgentKernel` / `AgentTurnFrame`，`AgentLoop` 已成为 turn-loop owner；`QueryEngine` 继续作为 session facade，但不再拥有 `_run_loop_impl`、`_run_loop` 或 `_is_completion_signal`。下一步进入 Phase D default C/C++ workflow package |
| 2026-06-14 | Pi-inspired minimal Core Phase B 收口：`AgentEventBus` 现在承载 `ExtensionManager` 公开 extension hook family 的 source-aware reducer dispatch；tool-call block/update、resource discovery、dynamic tool registration、prompt patch、active tools、workflow init、task snapshot 与 extension-owned tool handling 均统一诊断。该阶段保留的公共 method-name API 已在 2026-06-25 explicit capability cleanup 中删除。Phase C AgentKernel lifecycle extraction 已由后续收口记录完成 |
| 2026-06-13 | Pi-inspired minimal Core Phase B 第一切片启动：新增 source-aware `AgentEventBus`，`ExtensionManager.context(...)` 与 `after_tool_result(...)` 已迁到 `extension.context` / `extension.tool_result` reducer event；当时保留的公共 extension method API 已在 2026-06-25 explicit capability cleanup 中删除 |
| 2026-06-13 | Pi-inspired minimal Core Phase A 收口：context snapshot 与 workflow patch 已纳入显式 schema_v2 operation lifecycle；`workflow_patch` transcript 事件可被 `SessionRestorer` 回放；live session snapshot 也会投影 reducer-backed `operation_diagnostics` |
| 2026-06-13 | Durable operation lifecycle 继续推进：`QueryEngine` 已为 turn 与 pending interaction 写入显式 schema_v2 operation lifecycle；pending resume 会写入 pending operation finish；restore-time session snapshot 已投影 `operation_diagnostics`，用于解释 finished/interrupted/active operation family |
| 2026-06-13 | Durable operation lifecycle 主路径推进：`OperationLogReducer` 不再从 legacy replay 事件推断 operation state；`QueryEngine` 已为 context assembly、provider request 和 save point 补显式 schema_v2 operation lifecycle，restore 会消费这些事件并输出 `operation_state` |
| 2026-06-13 | Pi-inspired minimal Agent Core 长期蓝图建立：新增 `docs/pi-inspired-agent-core-blueprint.md`，同时学习 Pi 的功能设计和架构哲学；README、AGENTS、overall architecture、roadmap 与 tracker 已同步“当前 baseline 不变、后续渐进改造”的口径 |
| 2026-06-12 | Self-extensible Agent Core Slice 6 文档收口：active source-of-truth docs 与 module docs 已同步 local offline self-extension 官方口径；resource reload 与 project-local Python extension loading 的边界重新写清；completed self-extensible slice materials 已迁入 `docs/archive/self-extensible-agent-core/` |
| 2026-06-12 | QueryEngine slimming Slice 5 落地：新增 `AgentExtensionHost`、`AgentToolActionService` 与 `AgentLoop`，将 extension hook dispatch、active schema projection、非 LLM tool action execution 与 turn-loop 边界从 `QueryEngine` 中抽出；bare `QueryEngine` 继续不启用默认 C harness，hosted 路径仍通过共享 `ExtensionManager` 获得默认 C/C++ 行为 |
| 2026-06-08 | Project-local Python extensions Slice 4 落地：新增 manifest-gated loader，hosted `InProcessAdapter` 可加载启用的 `.embedagent/extensions/<name>/extension.json` + workspace-bound `extension.py`，并注册到共享 `ExtensionManager`；loader diagnostics 投影到 `extensions.project_extensions` 与 `extension_diagnostics`，动态工具继续走 catalog metadata、active-tool gating 与 `PermissionPolicy` |
| 2026-06-05 | Local resource reload Slice 3 落地：新增 file-only local resource scanner，`.embedagent/skills` / `.embedagent/prompts` / `.embedagent/recipes` 可通过 `ToolRuntime.reload_resources()`、`InProcessAdapter.reload_resources(...)`、`/resources reload` 与 `POST /api/sessions/{session_id}/resources/reload` 刷新；recipe JSON 进入既有 `list_recipes/run_recipe` 合约，reload 事件进入 transcript-backed session truth |
| 2026-06-15 | Local skill resource invocation slice 落地：`.embedagent/skills` 支持 Agent Skills-style frontmatter（`name`、`description`、`disable-model-invocation`），visible skills 进入系统提示词列表，`/skill:<name> [args]` 会把 workspace-bound Markdown skill 展开成普通 user turn；该路径仍不执行本地 Python、不绕过权限或 extension loading |
| 2026-06-04 | Dynamic tool registration Slice 2 落地：in-process extensions 可向共享 `ToolRuntime` 注册 source-aware `ToolDefinition`，schema/catalog 可见性仍由共享 `ExtensionManager.allowed_tool_names(...)` 激活路径控制，权限分类通过 catalog metadata 接入 `PermissionPolicy` |
| 2026-06-04 | Capability extension contract Slice 1 落地：新增通用 extension diagnostics、resource discovery contract、context hook、tool-call/tool-result hooks 与 session snapshot diagnostics；project-local Python extension loading 当时尚未启用，后续已由 Slice 4 收口 |
| 2026-05-26 | Workflow extension boundary Slice 1 落地：新增 in-process extension manager、默认 C harness extension、`Session.workflow_state` 兼容位，并修复 parallel tool batch 失败后后续任务抢跑的竞态；fast/non-gui 测试通过 |
| 2026-05-26 | Workflow extension boundary Slice 2 落地：`SessionSnapshotProjector` 与 live frontend task API 已从 `task_graph` 直读迁到 `Session.workflow_state["workflow"]`，`HarnessStateSynchronizer` 降为兼容门面，adapter 的 harness 刷新与 task snapshot 持久化委托给默认 C harness extension |
| 2026-05-27 | Workflow extension boundary Slice 3 落地：`QueryEngine` 的 schema/allowed-tool 计算改为 mode fallback + workflow extension active tools，并通过 explicit tool names 调用 runtime；`CORE_PACK` 已移除 `run_recipe/list_recipes/task_status` 等默认 harness workflow 工具 |
| 2026-05-27 | Workflow extension boundary Slice 4 落地：内置 mode `allowed_tools` 已收缩为 workflow-neutral permission/write contract；默认 C harness 的 recipe/quality/evidence/task-status 工具由 extension pack 激活，frontend tool catalog 改为 mode contract + extension active tools 的并集 |
| 2026-05-27 | Workflow extension boundary Slice 5 落地：`InProcessAdapter` 现在拥有共享 `ExtensionManager`，并将同一 manager 传给 session-scoped `QueryEngine` 与 frontend tool catalog，消除 adapter/engine 各自持有 harness extension 的分叉 |
| 2026-05-27 | Workflow extension boundary Slice 6 落地：`InProcessAdapter` 已不再直接导入或构造 `HarnessStateSynchronizer`；product harness refresh 只走默认 C harness workflow extension，synchronizer 继续作为 services 惰性导出的兼容门面保留 |
| 2026-05-28 | Runtime schema boundary Slice 7 落地：`ToolRuntime.schemas_for_mode()` 与 `allowed_tool_names()` 不再默认合入 C harness pack，只保留纯 mode-contract 兼容投影；默认 harness-aware schema 继续由共享 `ExtensionManager` 的 active tool names 显式驱动 |
| 2026-05-28 | Default harness extension factory Slice 8 落地：默认 C harness extension 装配迁入 `default_extensions.py`，`QueryEngine` 默认只创建空 `ExtensionManager`，host/adapter 显式注入默认扩展集 |
| 2026-05-28 | Harness workflow projection builder Slice 9 落地：新增 `src/embedagent/harness/workflow_projection.py`，C harness 到 `Session.workflow_state["workflow"]` 的 payload 组装从 extension 内联逻辑抽为 harness-owned 适配器 |
| 2026-05-28 | Session task graph lazy boundary Slice 10 落地：`embedagent.session` 不再在模块导入期加载 `embedagent.harness.task_graph`，`Session().task_graph` 仍按需创建默认 C harness 兼容镜像 |
| 2026-05-28 | Turn orchestrator task-status projection Slice 11 落地：提取出的 core `TurnOrchestrator` 不再直读 `Session.task_graph`，legacy `task_status` 兼容响应改从 `Session.workflow_state["workflow"]` 读取 |
| 2026-05-29 | Workflow extension boundary Task 1 收口：删除 `HarnessStateSynchronizer` service facade，focused service tests 改为覆盖 `CHarnessWorkflowExtension.refresh_managed_session()` 正式刷新路径，product refresh 不再保留并行兼容入口 |
| 2026-05-29 | Workflow extension boundary Task 2 收口：`Session.task_graph` dataclass 字段已删除，默认 C harness `TaskGraph` 由 `CHarnessWorkflowExtension` 的 harness-owned session graph state 持有，并继续投影到 `Session.workflow_state["workflow"]` |
| 2026-05-29 | Workflow extension boundary Task 3 收口：删除 `ToolRuntime.schemas_for_mode()` runtime alias，runtime schema projection 统一为 `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` |
| 2026-05-29 | Workflow extension boundary Task 4 收口：删除 `ToolRuntime.allowed_tool_names()` 与 `OfficialRuntimeModes.allowed_tool_names()` wrappers，`TurnOrchestrator` 改为通过注入的 allowed-tool policy gating |
| 2026-05-29 | Workflow extension boundary Task 5 收口：默认扩展配置决策关闭，hosted product paths 继续通过 `default_extensions.py` 装配 bundled C harness，bare `QueryEngine` 保持空 manager；不引入 project-local discovery、registry、marketplace 或 multi-agent orchestration |
| 2026-05-29 | Workflow extension boundary Task 6 收口：completed slice plans 与 handoff 已迁入 `docs/archive/workflow-extension-boundary/`，活动 `docs/superpowers/plans/` 只保留 remaining validation plan |
| 2026-06-03 | Workflow extension boundary 本机剩余清理收口：`InProcessAdapter` 的 inactive task fallback 改走 `ExtensionManager.load_session_tasks(...)`，不再直接 import harness task store；配置指南已改写为当前 mode/task 口径 |
| 2026-04-09 | 文档治理 Batch B 完成：归档 10 份 superseded 文档至 archive/，下沉 8 份操作文档（6 份 packaging 归档 + 2 份 guides/），更新 docs/README.md 和模块文档 |
| 2026-04-09 | 文档治理 Batch A 完成：补齐 4 篇缺失模块文档，修复 tools-and-tooling 不准确引用，更新代码-文档矩阵与模块索引 |
| 2026-04-08 | 启动文档治理基线实施：建立 docs 分层、模板、术语表、同步工作流和第一批模块文档入口 |
| 2026-04-04 | Query / Context / Context Loop 这轮重构已收口：P0 问题全部关闭，handoff/analysis/review 文档已归档到 `docs/archive/context-loop/`，活动状态以后续真实工程集成回归和 Win7 验证为准 |
| 2026-04-04 | GUI runtime hardening 已推进完成：transport/bootstrap recovery / restore / typed HTTP-WS error boundary / active-session projector ownership 已收口，webapp 现已按 reload 状态和 grouped projector 读模型驱动 active session |
| 2026-04-04 | GUI runtime hardening 相关 spec/plan 已从活动 `docs/superpowers/` 入口移入 `docs/archive/gui-runtime-hardening/`，当前该 slice 视为关闭 |
| 2026-04-05 | GUI timeline event-anchor unification 已完成：slash/workflow 命令现在会生成正式 turn 生命周期，`command_result / context_compacted / session_error` 与 permission/user_input 交互在 live/bootstrap/replay 路径上的 turn/step 坐标已统一；定向 Python 与 webapp helper 验证已通过 |
| 2026-04-05 | GUI timeline event-anchor 相关设计/计划/分析文档已归档到 `docs/archive/gui-timeline-event-anchors/`；同时 `.venv\\Scripts\\python.exe -m unittest discover -s tests -v` 已在本轮收尾时全量通过 |
| 2026-04-05 | GUI bundle runtime discovery 缺陷已修复：bundle 根目录识别已统一收口到 `runtime_discovery.py`，`ToolContext`/GUI launcher/`check-bundle-dependencies.py` 已共享强签名规则；`embedagent-gui.cmd` 与 `prepare-offline.ps1` 已补 `EMBEDAGENT_BUNDLE_ROOT` 并对齐 PATH，`validate-offline-bundle.ps1` 也新增了 launcher contract 校验 |
| 2026-04-06 | 直连离线打包链已补齐 GUI 静态资产门：`prepare-offline.ps1` 现在会确保 KaTeX 等前端资源存在，`build-offline-bundle.ps1` 会拒绝复制残缺 staging；重建后的 `build-offline-dist/embedagent-win7-x64` 已重新通过 `validate-offline-bundle -RequireComplete`、`check-bundle-dependencies.py` 与 bundle 级 `validate-gui-smoke.py` |
| 2026-04-06 | `gui-bundled-runtime-discovery-failure` 问题分析文档已迁入 `docs/archive/issues/`，当前该问题视为关闭并退出活动 issue 入口 |
| 2026-04-06 | GUI interaction 生命周期已收口到专属 `interaction` tab：当前交互不再挂在所有 inspector tab 的公共尾部；`pending_interaction_valid=false` / `interaction_expired` 现在只显示 notice，不再伪装成可操作的 expired card；webapp helper 回归与 `tests.test_gui_runtime`、`tests.test_gui_backend_api` 已通过 |
| 2026-04-06 | 已建立 `docs/agent-harness-v2.md` 作为新一轮 mode/tool/permission 整体重构设计基线：保留用户可见 mode，但引入 execution phase、discipline profile、tool pack、permission DSL 与 failure taxonomy；后续建议以该文档为主线推进重构，而不是继续做局部补丁 |
| 2026-04-06 | Agent Harness V2 Program A/B 已开始实现：新增 `src/embedagent/harness/`、`tooling/`、`tools_v2/`、`permissions_v2/` 第一批基础包，`build` mode 已可挂载最小 harness context，`InProcessAdapter` snapshot 已暴露 `current_phase / discipline_profile / current_activity`，且新切片测试与定向旧回归均已通过 |
| 2026-04-06 | Agent Harness V2 Program D 已推进到第一批可运行切片：新增 `src/embedagent/harness/task_graph.py`，`build` mode 已支持 `full_spec_tdd` 的最小 task summary 与 artifact gate，`QueryEngine` / `InProcessAdapter` 现已开始暴露 `task_summary`，且新切片测试与定向旧回归均已通过 |
| 2026-04-07 | 已完成一轮文档归档收口：`gui-redesign`、`packaging-pipeline-redesign`、`agent-harness-v2` 与 `session-history-single-source-cutover` 相关的 plan/spec/review/handoff 文档已迁入 `docs/archive/`，同时补归档了 `2026-04-02-full-transcript-persistence-design.md` 与 documentation alignment 审查报告，并修正了活动文档中的旧路径引用 |
| 2026-04-06 | 已完成一轮“V2 是否可直接扶正”的仓库审查，并确认当前还不能直接暴力删除 legacy；已新增 `docs/archive/agent-harness-v2/2026-04-06-agent-harness-v2-official-cutover-plan.md`，明确后续需要按 runtime、mode、context、permission/task、frontend/protocol、docs/legacy deletion 六个程序完成正式 cutover |
| 2026-04-06 | official cutover 第 1、2 步已完成：官方 `ToolRuntime` 已提升为唯一 runtime 主入口，`HarnessToolBridge` 与 `ToolRuntimeV2` 已退出产品路径；同时产品和测试默认 mode 已从 `code` 切到 `build`，内建 mode 集现在以 `explore/spec/build/debug/verify` 为正式主词汇 |
| 2026-04-06 | official cutover 第 3 步已完成：`ContextManager` 与 `WorkspaceIntelligenceBroker` 已把 `list_dir/glob_files/grep_text/run_recipe/report_quality_v2/task_status` 纳入正式 reducer/intelligence 词汇，并将 `build` 作为上下文与情报层的正式实现模式；相关 focused tests 与外围回归均已通过 |
| 2026-04-06 | official cutover 第 4 步已完成：官方 mode prompt 和 schema 已把 `task_status` 作为唯一模型侧任务入口；`TaskGraph` 现在会投影到 session 级 task snapshot 并驱动 `list_todos` 的主路径，`permissions.py` 也已吸收 recipe/rule/explanation 能力并删除 `permissions_v2/` 并行包；相关 focused tests 与外围回归均已通过 |
| 2026-04-06 | official cutover 第 5 步已完成：`protocol/core/frontend` 现已把 `tasks` 作为正式前端任务词汇，session snapshot 会显式暴露 `current_phase / discipline_profile / current_activity / task_summary / task_items`，GUI/TUI 与 webapp 构建产物也已切到 `tasks/build` 词汇；相关 Python 与 webapp 验证均已通过 |
| 2026-04-06 | official cutover 第 6 步已完成：根 README、AGENTS、architecture/roadmap/mode/tool/permission/frontend/harness 文档已改写为单一正式架构说明；`list_todos` / `/api/todos` 等前端兼容壳层已移除，tool catalog 也已只投影正式 mode tool 集；当前 cutover 视为完成并进入稳定化阶段 |
| 2026-04-06 | 稳定化收口继续推进：`/review` 现已正式消费 `run_recipe + report_quality_v2` 证据，recipe 对外词汇已统一为 `run_recipe` 并保留 `legacy_tool_name` 仅作兼容映射；同时 `ToolRuntime.schemas()/catalog_entries()` 已不再暴露 `list_files/search_text/compile_project/manage_todos` 等 legacy 工具，只保留正式产品词汇 |
| 2026-04-08 | Agent core ownership cutover 已完成：`QueryEngine` 现为 session-scoped owner，step anchors 在 engine/transcript/frontend events 间已统一，permission resume 已回到同一 action pipeline，`TaskGraph` 已进入 `Session` 真相层，`SessionSnapshotProjector` 已成为无副作用投影器，`transcript/timeline` 序号分配已做缓存优化，并清除了 runtime `todo/todos` 残留词汇 |
| 2026-04-08 | Agent core cutover 相关 design / plan / review / implementation review / follow-up plan 已归档到 `docs/archive/agent-core-cutover/`；活动 `docs/superpowers/` 入口不再保留这轮已关闭切片 |
| 2026-03-27 | 建立进度跟踪文件，明确当前阶段与下一步优先级 |
| 2026-03-27 | DC-004/DC-005：工具设计规范建立，实施分期重组，Phase 1 改为最小可工作 Loop |
| 2026-03-27 | 已落地 Phase 1 最小原型代码，并完成本地语法检查、工具自测与假模型闭环验证 |
| 2026-03-27 | Moonshot `kimi-k2.5` 真实联调通过，补齐了温度参数与 `reasoning_content` 兼容处理 |
| 2026-03-27 | 代码骨架迁移到 `src/embedagent/`，并通过 `uv` 创建的 Python 3.8.10 环境验证 |
| 2026-03-27 | 按当前可用条件完成 Phase 1 验收，并切换到 Phase 2 工具集实现 |
| 2026-03-27 | Phase 2 核心工具已实现，并通过 Python 3.8 本地自测 |
| 2026-03-28 | Phase 2 工具契约与 Loop 烟雾验证完成，阶段状态切换到 Phase 3 准备中 |
| 2026-03-28 | Phase 3 模式系统 v1 已完成，并补齐模式结构与状态机文档 |
| 2026-03-28 | Phase 4 第一版工具封装与解析验证完成，并建立 Clang 集成计划文档 |
| 2026-03-28 | 已下载、组装并验证项目内闭环 Clang 工具链，完成编译/分析/tidy/coverage smoke test |
| 2026-03-28 | Phase 5 最小权限模型与 Doom Loop Guard 已落地，并清理了工具链临时产物 |
| 2026-03-28 | Phase 5 第一版 ContextManager 已落地，并完成本地压缩/回归验证 |
| 2026-03-28 | Phase 5A mode-aware budget、ReducerRegistry 与 ContextStats 已落地，并完成本地行为验证 |
| 2026-03-28 | Phase 5B Artifact Store 已落地，并完成大输出脱敏/落盘/回灌验证 |
| 2026-03-28 | Phase 5C Session Summary Store 已落地，并完成状态落盘/回归验证 |
| 2026-03-28 | Phase 5D Project Memory Store 已落地，并完成 recipe / known issue / context 注入验证 |
| 2026-03-28 | Phase 5E Resume Entry 已落地，并完成 list / load / resume 验证 |
| 2026-03-28 | Phase 5F Memory Maintenance 已落地，并完成 cleanup / index 验证 |
| 2026-03-28 | Phase 6B 交互深化已完成：TUI 新增会话列表浏览、权限确认/错误/上下文状态展示，并修复 --tui 空启动路径 |
| 2026-03-28 | Phase 6B 依赖与运行验证已推进：`prompt_toolkit` / `rich` 已接入，非控制台宿主会优雅报错，并完成 headless 真实事件循环验证 |
| 2026-03-28 | Phase 6 历史验证入口曾建立；当前活动验证已切换为 focused tests、visual harness 与 bundle smoke gates，旧 phase 脚本不再位于 active `scripts/` |
| 2026-03-29 | Phase 6 终端前端已模块化：新增 src/embedagent/frontend/tui/ 包、timeline store 和 adapter 浏览接口，保留 embedagent.tui 兼容入口，并通过 headless 与单元测试 |
| 2026-03-29 | 修复 `**/*.md` 等模式对根目录文件不匹配的问题并补充 `test_modes.py` 回归；旧 Phase 5 脚本复验记录为历史状态，当前不再作为活动验证入口 |
| 2026-03-29 | README、路线图、进度跟踪与变更日志已按当前能力和阶段状态完成一轮对齐 |
| 2026-03-29 | 建立 Phase 7 离线打包设计基线：新增 `docs/offline-packaging.md`、`docs/win7-preflight-checklist.md` 与 ADR `0001-offline-portable-bundle-baseline.md` |
| 2026-03-29 | 建立 `scripts/prepare-offline.ps1`：已可生成 staging bundle 骨架、launcher、模板配置、`bundle-manifest.json` 与 `checksums.txt`，并通过 `powershell.exe -NoProfile -File scripts/prepare-offline.ps1 -SkipBuild` 验证 |
| 2026-03-29 | 建立 `scripts/build-offline-bundle.ps1`：已可把 staging bundle 复制到 `build/offline-dist/`、生成 zip、重写 dist manifest 并重算 checksum |
| 2026-03-29 | 建立 `scripts/validate-offline-bundle.ps1`：默认模式可校验 skeleton bundle 并告警通过，`-RequireComplete` 下会对缺失资产返回失败 |
| 2026-03-29 | 建立 `scripts/offline-assets.json`，正式接入 `python_embedded_x64` 与 `mingit_x64`，并完成真实 prepare/build/validate 验收 |
| 2026-03-30 | 零依赖打包方案落地：新增 `scripts/export-dependencies.py` 导出完整 Python 依赖（含传递依赖），新增 `scripts/check-bundle-dependencies.py` 验证 bundle 完整性，新增 `docs/intranet-deployment.md` 内网部署指南，新增 `docs/offline-packaging-guide.md` 完整打包指南，配置模板已预置内网大模型服务示例 |
| 2026-03-30 | 当前环境 GUI 验证已补齐：已安装 `pywebview` / `fastapi` / `uvicorn` / `websockets`，新增 `scripts/validate-gui-smoke.py`，源码路径与 bundle 路径的 headless GUI smoke 均已通过 |
| 2026-03-30 | 离线 bundle GUI 集成已补齐：`prepare/build/validate` 与 `check-bundle-dependencies.py` 已纳入 GUI launcher / static files / 文档 / site-packages 检查，当前环境完整 bundle 验证通过 |
| 2026-03-30 | Win7 GUI 实机验证入口已准备：GUI launcher 新增 renderer report 与 auto-close 参数，bundle 已内置 `validate-gui-smoke.cmd` 和 `docs/win7-gui-validation.md`，当前 Windows 10 环境 windowed smoke 返回 `renderer=edgechromium` |
| 2026-03-30 | GUI 新壳层已落地：新增 `frontend/gui/webapp/` React + Vite 工程，产物写回 `frontend/gui/static/`；同时完成 session-scoped todo、权威 `session_status`/`thinking_state`/`reasoning_delta`、稳定 `tool_call_id`、GUI 懒加载文件树与增强版 smoke 校验 |
| 2026-03-31 | 已补 workflow/filtering 回归测试，并把 `scripts/validate-gui-smoke.py` 扩展到 `/review` workflow；源码路径 smoke 已通过，但当前 `build/offline-dist/` bundle 仍呈现旧 GUI 布局并在 bundle smoke / validate 中暴露出与最新 validator 的结构漂移 |
| 2026-03-31 | 已定位并修复 dist/source GUI 漂移：原因是旧 dist 未在 GUI 静态产物迁移后重建、WebView2 资产未纳入 prepare/build、以及 `.venv` 里的 `__editable__.embedagent-0.1.0.pth` 被直接带入 bundle；当前已重建 bundle，并通过 `validate-offline-bundle.ps1`、bundle 级 `validate-gui-smoke.py` 与 `check-bundle-dependencies.py` |
| 2026-04-02 | 已启动 Query / Context 激进重构切片：新增 `QueryEngine`、transcript/event 模型、workspace intelligence broker、tool capability metadata、batch tool orchestration、pending interaction resume 与 focused regression tests；`tests.test_context_config` / `tests.test_guard` / `tests.test_modes` / `tests.test_session_timeline` / `tests.test_query_engine_refactor` 已复验通过 |

