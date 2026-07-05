# EmbedAgent 设计与变更跟踪

> 更新日期：2026-07-05
> 用途：记录关键设计变更、影响范围、关联文档和后续动作

---

## 1. 使用规则

本文件不是完整 changelog，也不是 ADR 替代品。

它的定位是：

- 记录“已经发生的关键设计变化”
- 标明“哪些文档受影响”
- 指向相关 ADR、方案文档、实现任务

适合记录的变更类型：

- 架构分层变化
- 模式系统变化
- Python / 打包 / 运行时主线变化
- 工具链或质量门设计变化
- 文档治理机制变化

若某个变更足够重大且具有长期影响，应同时新增 ADR。

---

## 2. 变更记录格式

建议每次新增一条记录，包含：

- `ID`
- `日期`
- `变更主题`
- `变更摘要`
- `影响范围`
- `关联文档`
- `是否需要 ADR`
- `后续动作`

---

## 3. 当前变更记录

### DC-308

- Date: 2026-07-05
- Change Topic: GUI command visibility context moves into workbench model
- Summary:
  - `workbench/commands.js` now owns `isTurnInterruptibleStatus(...)` and
    `buildCommandVisibilityContext(...)`, the pure read model used by command
    visibility filtering.
  - `App.jsx` passes app/workbench state slices into that builder instead of
    hand-assembling `hasSession`, `hasWorkspace`, `isRunning`, and
    `paletteOpen` fields in the root component.
  - `workbench-parity-model.js` reuses the same running-status and command
    visibility context semantics instead of keeping a second status helper.
  - Frontend and architecture guards reject reintroducing root-level command
    visibility context assembly in `App.jsx`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/workbench-parity-model.js`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No
- Follow-up:
  - Continue shrinking `App.jsx` by moving remaining root-level read-model
    assembly into focused app-runtime or workbench model modules.

### DC-307

- Date: 2026-07-05
- Change Topic: GUI composer command group labels use command-palette model
- Summary:
  - `workbench/command-palette-model.js` now exports
    `buildCommandGroupLabels(...)` for deriving Composer slash-menu group
    labels from app-shell command-palette descriptors.
  - `App.jsx` no longer hand-builds `composerCommandGroupLabels` with a
    root-level `commandPaletteGroups.reduce(...)`.
  - Frontend and architecture guards reject reintroducing that reducer in
    `App.jsx`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No
- Follow-up:
  - Continue moving remaining App-level descriptor projection into focused
    read models where the mapping is more than direct dependency wiring.

### DC-306

- Date: 2026-07-05
- Change Topic: GUI SurfacePanel props are mapped outside root App
- Summary:
  - Added `surface-panel-props.js` as a pure app-runtime props builder for
    generic `SurfacePanel` state, chrome, and action handles.
  - `App.jsx` now calls `buildSurfacePanelProps(...)` instead of spelling out
    per-action `surfacePanelController.*` prop mappings in the root component.
  - Frontend and architecture guards reject reintroducing those action prop
    mappings in `App.jsx`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/surface-panel-props.js`
  - `src/embedagent/frontend/gui/webapp/test/surface-panel-props.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue shrinking `App.jsx` to composition-only wiring where remaining
    prop assemblers still encode component contracts.

### DC-305

- Date: 2026-07-05
- Change Topic: GUI socket message scheduling moves into controller boundary
- Summary:
  - `socket-message-controller.js` now accepts a generic `scheduleMessage`
    callback and applies raw WebSocket messages inside that scheduler.
  - `App.jsx` passes React `startTransition` as the scheduler and wires
    `socketMessageController.handleMessage` directly into
    `session-transport-controller.js`.
  - Frontend and architecture guards reject the old root-level
    `startTransition(() => socketMessageController.handleMessage(...))`
    wrapper.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/socket-message-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue reducing root-level App callbacks that still encode runtime
    behavior instead of plain dependency wiring.

### DC-304

- Date: 2026-07-05
- Change Topic: GUI active-workspace source-control refresh uses controller handle
- Summary:
  - `App.jsx` now passes `sourceControlController.loadStatus` directly into
    `active-workspace-data-loader.js`.
  - The root-level three-argument Source Control status-refresh forwarding
    lambda has been removed from the active-workspace refresh path.
  - Frontend and architecture guards reject the old adapter lambda and require
    the direct controller handle.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue reducing remaining root-level dependency adapter lambdas where
    they encode behavior instead of simple composition.

### DC-303

- Date: 2026-07-05
- Change Topic: GUI session command capability refresh uses a loader handle
- Summary:
  - `session-loaders.js` now exposes
    `createSessionCommandCapabilityLoader(...)` for the GUI command capability
    refresh path.
  - `App.jsx` creates one `loadSessionCommandCapabilitiesForApp` handle and
    passes it into initial app load, active workspace refresh, and loader
    request execution instead of repeating inline
    `loadSessionCommandCapabilities({ fetchJson, dispatch })` lambdas.
  - Frontend and architecture guards reject the removed root-level inline
    fetch/dispatch loader pattern.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`
  - `src/embedagent/frontend/gui/webapp/test/session-loaders.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workspace-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue reducing remaining root-level dependency adapter lambdas where
    they encode behavior instead of simple dependency injection.

### DC-302

- Date: 2026-07-05
- Change Topic: GUI right-panel active surface selection is a surface read model
- Summary:
  - `workbench/surfaces.js` now exposes `rightPanelSurfacesFrom(...)` and
    `activeRightPanelSurfaceFrom(...)` as the renderer-owned active surface
    selectors.
  - `App.jsx` uses those selectors instead of resolving the active right-panel
    surface with root-level `surfaces.find(...)` logic.
  - `terminal-controller.js` reuses the shared selector and no longer keeps a
    private `activeRightPanelSurface` helper.
  - Frontend and architecture guards reject root-level active-surface lookup
    and duplicate terminal-controller selector logic.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue reducing root-level App composition glue around dependency adapter
    lambdas and surface prop assembly.

### DC-301

- Date: 2026-07-05
- Change Topic: GUI interaction response event logging is controller-owned
- Summary:
  - `interaction-response-controller.js` now emits the
    `interaction_response` `log_event` through its injected reducer dispatch.
  - `App.jsx` no longer injects a root-level `logEvent` callback into the
    interaction response path.
  - Frontend and architecture guards reject the removed `logEvent` injection
    seam and require response event logging to stay in the controller.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue moving remaining root-level GUI dependency adapter lambdas toward
    semantic controller methods where they represent behavior rather than
    composition.

### DC-300

- Date: 2026-07-05
- Change Topic: GUI panel resize handlers are controller-owned
- Summary:
  - `panel-resize-controller.js` now exposes semantic
    `startSidebarResize` / `startRightPanelResize` handlers for the workbench
    panel handles.
  - `App.jsx` wires those handlers directly instead of passing CSS variable
    names, resize direction constants, or the generic resize helper through
    inline callbacks.
  - Frontend and architecture guards reject root-level resize parameterization
    and the exported resize-direction compatibility path.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/panel-resize-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/panel-resize-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue shrinking remaining root-level App composition glue around
    interaction event logging and non-semantic dependency adapters.

### DC-299

- Date: 2026-07-05
- Change Topic: GUI SurfacePanel actions are controller-owned
- Summary:
  - Added `surface-panel-controller.js` for generic SurfacePanel actions:
    diff-file focus, Source Control refresh/file selection, and app-shell
    settings patching.
  - `App.jsx` now wires controller methods into `surfacePanelProps` instead of
    inline reducer dispatch or source-control controller lambdas.
  - Frontend and architecture guards reject root-level `diff_file_focused`,
    `app_shell_settings_changed`, and direct Source Control lambdas for this
    surface-panel path.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/surface-panel-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue shrinking the remaining App composition glue around resize event
    factories and interaction event logging.

### DC-298

- Date: 2026-07-05
- Change Topic: GUI workspace path input is controller-owned
- Summary:
  - `workspace-controller.js` now exposes `setWorkspacePath(...)` and owns the
    `workspace_path_changed` reducer action.
  - `App.jsx` wires `setWorkspacePath` directly into Sidebar and
    NoWorkspaceState instead of inline-dispatching workspace path input
    changes.
  - Frontend and architecture guards now reject root-level
    `workspace_path_changed` dispatches.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/workspace-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/workspace-controller.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Move surface-panel action wiring out of `App.jsx` once that controller
    boundary is isolated.

### DC-297

- Date: 2026-07-05
- Change Topic: GUI right-panel terminal pane actions are controller-owned
- Summary:
  - `terminal-controller.js` now derives the active right-panel terminal
    surface from workbench state for pane new/split/select/close actions.
  - `App.jsx` wires right-panel terminal callbacks directly to controller
    methods instead of passing `activeRightPanelSurface` through inline
    lambdas.
  - Frontend and architecture guards now reject root-level calls to
    `splitRightPanelSurface(...)`, `activateRightPanelPane(...)`, or
    `closeRightPanelPane(...)`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue moving workspace path input and surface-panel action wiring out
    of `App.jsx` when their controller boundaries are clear.

### DC-296

- Date: 2026-07-05
- Change Topic: GUI workbench command lifecycle is controller-owned
- Summary:
  - `workbench-command-controller.js` now owns header right-panel/bottom-drawer
    toggles, command-palette open/close/query state, command-palette
    command/session/workspace selection, and command-id resolution.
  - `App.jsx` wires controller methods directly and no longer imports
    `commandById` or dispatches palette/toggle reducer actions inline.
  - `CommandPalette.jsx` remains a display component for root/submenu
    navigation, Escape, and backdrop close; selected rows hand intent to
    controller-owned callbacks.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/workbench-command-controller.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue shrinking `App.jsx` by moving workspace-path input and
    surface-panel action wiring into focused controllers.

### DC-295

- Date: 2026-07-05
- Change Topic: GUI right-panel body lookup is app-capability scoped
- Summary:
  - `RightPanelSurfaceBody` now receives `appCapabilities` from `App.jsx` and
    resolves `surfaceDefinitionFor(surface.kind, appCapabilities)`.
  - The backend app-shell spec now declares the hidden `file` resource surface
    with `launcher=False` and `command=False`, so file preview bodies remain
    capability-declared without becoming visible launcher or command entries.
  - Frontend and architecture guards now reject capability-blind
    `surfaceDefinitionFor(surface.kind)` body lookup.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Future hidden/resource surfaces must be backend-declared capability records
    with visibility metadata instead of relying on renderer-only body fallback.

### DC-294

- Date: 2026-07-05
- Change Topic: GUI resource right-panel surfaces open through controller methods
- Summary:
  - Added `openFileSurface(...)`, `openPreviewSurface(...)`, and
    `openFilesSurface()` to `right-panel-controller.js`.
  - Moved App-level file, preview, and Files browser surface-kind dispatch out
    of `App.jsx`; App now delegates resource surface opening by semantic
    controller method instead of writing `kind: "file"`, `kind: "preview"`, or
    `openRightPanelSurface("files")`.
  - Removed the stale `preview.kind = "file"` payload shape from the App file
    preview load path and test fixture.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/right-panel-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Future App-level resource open flows should add semantic controller methods
    or metadata-driven handlers; App must not reintroduce concrete right-panel
    surface-kind dispatch.

### DC-293

- Date: 2026-07-05
- Change Topic: GUI right-panel activation uses controller handler registry
- Summary:
  - Added renderer-local `RIGHT_PANEL_ACTIVATION_HANDLERS` to
    `right-panel-controller.js` and routed supported right-panel activation
    side effects through `definition.activationKind`.
  - Moved the terminal right-panel re-open side effect out of `App.jsx`;
    `App.jsx` now delegates tab activation to the right-panel controller.
  - Updated frontend and architecture guards so App-level
    `surfaceDefinitionFor(...)`, `definition.activationKind`, and
    `terminalController.openSession(...)` paths fail.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/right-panel-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Future right-panel activation side effects must add explicit
    `activationKind` handler entries in the controller; App must remain a
    surface activation delegate, not a surface-policy owner.

### DC-292

- Date: 2026-07-05
- Change Topic: GUI persisted related surfaces are registry-declared
- Summary:
  - Added renderer-local `persistedRelatedKinds` metadata to surface registry
    records and declared the Files surface as the owner of persisted File
    resource surfaces.
  - Added `persistedSurfaceDefinitions(...)` so workbench UI-state
    sanitization consumes registry-declared persisted surface definitions.
  - Removed the `ui-state.js` hard-coded `files -> file` persisted-kind
    expansion and updated guards to make the old shortcut fail.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Any future hidden/resource surface that should survive persistence under a
    visible launcher must be declared through registry metadata, not UI-state
    string expansion.

### DC-291

- Date: 2026-07-05
- Change Topic: GUI terminal controller centralizes terminal surface adaptation
- Summary:
  - Added a terminal-controller-local `TERMINAL_SURFACE_KIND` and
    `terminalSurfaceActionInput(...)` helper for right-panel terminal surface
    validation and workbench action payload preparation.
  - `terminal-controller.js` no longer repeats `surface.kind !== "terminal"`
    checks or calls `surfaceDefinitionFor("terminal", ...)` directly at action
    sites.
  - Frontend and architecture guards now prevent reintroducing those scattered
    terminal surface checks.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Keep future terminal surface work behind the terminal controller adapter
    helpers rather than adding per-action surface-kind checks.

### DC-290

- Date: 2026-07-05
- Change Topic: GUI right-panel surface pane operations use per-kind handlers
- Summary:
  - Moved terminal split/activate/close pane metadata updates behind a
    renderer-local `SURFACE_PANE_HANDLERS` registry.
  - Right-panel pane actions now resolve `SURFACE_PANE_HANDLERS[surface.kind]`
    before mutating surface-local pane state instead of branching on the fixed
    terminal surface id in reducer code.
  - Frontend and architecture guards now prevent reintroducing the old
    `surface.kind === "terminal"` pane-operation branches.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New right-panel surface kinds that own multi-pane metadata must add pane
    handlers rather than branches in the workbench reducer.

### DC-289

- Date: 2026-07-05
- Change Topic: GUI right-panel surface opening uses per-kind preparers
- Summary:
  - Moved `openSurface(...)` file reveal/deduplication and preview placeholder
    cleanup into a renderer-local `SURFACE_OPEN_PREPARERS` registry.
  - Right-panel surface opening now resolves `SURFACE_OPEN_PREPARERS[surface.kind]`
    before upsert/activation instead of branching in the main open flow.
  - Frontend and architecture guards now prevent reintroducing the old
    `openSurface(...)` file/preview preparation branches.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New right-panel surface kinds that need custom open-time preparation must
    add a preparer registry entry rather than branches in `openSurface(...)`.

### DC-288

- Date: 2026-07-05
- Change Topic: GUI workbench surfaces use per-kind initializers
- Summary:
  - Moved `makeSurface(...)` file, terminal, and preview instance-field setup
    into a renderer-local `SURFACE_INITIALIZERS` registry.
  - `makeSurface(...)` now handles common surface fields and resolves
    per-kind instance metadata through `SURFACE_INITIALIZERS[kind]`.
  - Frontend and architecture guards now prevent reintroducing the old
    `makeSurface(...)` file/terminal/preview initializer branches.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New renderer-supported surface kinds that need instance-specific fields
    must add an initializer registry entry rather than branches in
    `makeSurface(...)`.

### DC-287

- Date: 2026-07-05
- Change Topic: GUI bottom-drawer body mounting uses a renderer registry
- Summary:
  - Replaced `BottomDrawer`'s `bodyKind` switch with a renderer-local
    `BOTTOM_DRAWER_BODY_RENDERERS` registry.
  - Bottom drawer descriptors still provide `bodyKind` metadata, but Run
    Output and Terminal body mounting now route through table lookup.
  - Frontend and architecture guards now prevent reintroducing
    `switch (activeBodyKind)` in the bottom drawer body.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New bottom-drawer body kinds must add explicit renderer registry entries
    rather than component switch branches.

### DC-286

- Date: 2026-07-05
- Change Topic: GUI right-panel body mounting uses a renderer registry
- Summary:
  - Replaced `RightPanelSurfaceBody`'s `bodyKind` switch with a
    renderer-local `RIGHT_PANEL_BODY_RENDERERS` registry.
  - Surface descriptors still provide `bodyKind` / `panelKind` metadata, but
    component mounting now routes through table lookup rather than fixed JSX
    branches.
  - Frontend and architecture guards now prevent reintroducing
    `switch (activeBodyKind)` in the right-panel body.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New right-panel body kinds must add explicit renderer registry entries
    rather than component switch branches.

### DC-285

- Date: 2026-07-05
- Change Topic: GUI bottom-drawer activation uses a handler registry
- Summary:
  - Replaced the terminal controller's bottom-drawer `activationKind` switch
    with a renderer-local `BOTTOM_DRAWER_ACTIVATION_HANDLERS` registry.
  - `selectBottomDrawerKind(...)` still reads bottom surface
    `definition.activationKind`, but now dispatches through table lookup.
  - Frontend and architecture guards now prevent reintroducing the old
    `switch (definition ? definition.activationKind : "")` path.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New bottom-drawer activation effects must add explicit handler registry
    entries rather than terminal-controller switch branches.

### DC-284

- Date: 2026-07-05
- Change Topic: GUI right-panel open behavior uses a handler registry
- Summary:
  - Replaced the right-panel `openKind` switch with a renderer-local
    `RIGHT_PANEL_OPEN_HANDLERS` registry.
  - `createRightPanelController().openSurface(...)` still reads
    `definition.openKind`, but now dispatches through table lookup instead of
    a controller switch.
  - Frontend and architecture guards now prevent reintroducing the old
    `switch (definition ? definition.openKind : "")` path.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New right-panel open behaviors must add explicit `openKind` handler
    registry entries rather than controller switch branches.

### DC-283

- Date: 2026-07-05
- Change Topic: GUI command dispatch uses a handler registry
- Summary:
  - Replaced the `workbench-command-controller` dispatch-kind switch with a
    renderer-local `COMMAND_DISPATCH_HANDLERS` registry.
  - Descriptor-owned `dispatch.kind` values now select built-in shell actions
    by table lookup, while unknown dispatch kinds continue to fall through to
    surface/drawer/slash descriptor fields.
  - Frontend and architecture guards now prevent reintroducing a
    `switch (dispatchDescriptor.kind)` path.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/workbench-command-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New built-in GUI shell dispatch kinds must be added as explicit handler
    registry entries rather than controller switch branches.

### DC-282

- Date: 2026-07-05
- Change Topic: GUI persisted workbench surfaces use registry normalization
- Summary:
  - Added `persistedSurfaceFrom(...)` to the renderer-local workbench surface
    model.
  - `ui-state.js` now sanitizes persisted surface descriptors through that
    registry-owned normalizer instead of branching on fixed `file` or
    `terminal` surface kinds.
  - The normalizer preserves the existing shallow persistence contract while
    keeping file/terminal field rules inside `surfaces.js`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New persisted surface fields must be declared and normalized by the
    renderer-local surface model, not by localStorage state code.

### DC-281

- Date: 2026-07-05
- Change Topic: GUI bottom-drawer activation uses renderer metadata
- Summary:
  - Added `activationKind` metadata to bottom drawer surface definitions.
  - Added `bottomDrawerSurfaceDefinitionFor(...)` so terminal drawer selection
    can use the same descriptor merge path as visible drawer tabs and commands.
  - `TerminalController.selectBottomDrawerKind(...)` now reads
    `definition.activationKind` instead of branching on `kind === "terminal"`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/terminal-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New bottom drawer activation side effects must be explicit renderer
    metadata, not drawer-kind conditionals.

### DC-280

- Date: 2026-07-05
- Change Topic: GUI right-panel activation side effects use renderer metadata
- Summary:
  - Added renderer-local `activationKind` metadata to surface registry records.
  - Right-panel tab activation now uses `definition.activationKind` to trigger
    terminal session re-opening for terminal surfaces.
  - `App.jsx` no longer branches on `surface.kind === "terminal"` for
    activation side effects.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New right-panel activation side effects must be explicit renderer metadata,
    not inline App surface-id checks.

### DC-279

- Date: 2026-07-05
- Change Topic: GUI right-panel surface open behavior uses renderer metadata
- Summary:
  - Added renderer-local `openKind` metadata to right-panel surface registry
    records.
  - `createRightPanelController().openSurface(...)` now uses
    `definition.openKind` to decide between generic workbench surface opening
    and terminal right-panel session creation.
  - Frontend and architecture guards now prevent the controller from branching
    on fixed surface ids such as `surfaceKind === "terminal"` or `"file"`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/right-panel-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New right-panel open behaviors must add explicit renderer metadata instead
    of adding surface-id conditionals to the controller.

### DC-278

- Date: 2026-07-05
- Change Topic: GUI generic right-panel subpanels use renderer metadata
- Summary:
  - Added renderer-local `panelKind` metadata for generic `SurfacePanel`
    surfaces such as Plan, Diff, Source Control, Settings, and Diagnostics.
  - `RightPanelSurfaceBody` now passes `activeDefinition.panelKind` into
    `SurfacePanel`; the panel no longer branches on fixed surface ids such as
    `surfaceKind === "diff"`.
  - Frontend and architecture guards now prevent old generic right-panel
    surface-id routing from returning.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - New generic right-panel panels must add explicit renderer metadata instead
    of reintroducing surface-id conditionals.

### DC-277

- Date: 2026-07-05
- Change Topic: GUI right-panel body mounting uses renderer metadata
- Summary:
  - Added renderer-local `bodyKind` metadata to right-panel surface registry
    records for Files, File Preview, Preview, Terminal, and generic
    `SurfacePanel` bodies.
  - `RightPanelSurfaceBody` now reads `surfaceDefinitionFor(surface.kind)` and
    selects the body from `activeDefinition.bodyKind` instead of branching on
    fixed surface kinds.
  - Frontend and architecture guards now prevent the old `surface.kind === ...`
    body routing from returning.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Keep future right-panel surfaces behind explicit renderer metadata and
    app-shell visibility descriptors.

### DC-276

- Date: 2026-07-05
- Change Topic: GUI bottom drawer renderer metadata replaces stale logs surface
- Summary:
  - Removed the default `logs` bottom-drawer surface because the renderer had
    no corresponding body implementation and previously fell through to Run
    Output.
  - Bottom-drawer surface registry records now carry renderer-local
    `bodyKind` metadata for the supported `run_output` and `terminal`
    surfaces.
  - `BottomDrawer` selects its body from the active surface definition instead
    of branching on `activeKind === "terminal"`, and initial/persisted fallback
    bottom drawer state no longer hard-codes `run_output`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Add future bottom-drawer surfaces only with a matching renderer body or
    keep them out of the supported registry/default app-shell descriptor set.

### DC-275

- Date: 2026-07-05
- Change Topic: GUI terminal drawer dispatch is descriptor-owned
- Summary:
  - Added `dispatch.kind: terminal.ensure_open` to the default Terminal
    bottom-drawer surface descriptor.
  - App-shell and workbench surface normalizers now preserve surface dispatch
    descriptors, and bottom-drawer command projection passes them through to
    command rows.
  - `workbench-command-controller` opens the hosted terminal through the
    declared dispatch kind; `drawer: "terminal"` alone now uses the generic
    bottom-surface activation path.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/workbench-command-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-command-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue moving GUI shell-specific execution behavior into explicit
    app-shell descriptors while keeping renderer fallback paths generic.

### DC-274

- Date: 2026-07-05
- Change Topic: GUI workbench command dispatch is descriptor-driven
- Summary:
  - Added `dispatch.kind` descriptors to default app/workspace/workbench
    command records for built-in GUI shell actions.
  - `workbench-command-controller` now routes command execution by
    descriptor-owned action kinds such as `command_palette.open`,
    `app_shell.reload`, and `message.submit` instead of switching on fixed
    command ids.
  - Surface, drawer, and slash command execution remains descriptor-field
    driven, and frontend/Python guards now prevent the old command-id switch
    from returning.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/workbench-command-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-command-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue moving remaining GUI shell behavior that is app-specific into
    explicit app-shell descriptors while keeping renderer mounting local.

### DC-273

- Date: 2026-07-05
- Change Topic: GUI File Preview mode chrome is app-shell declared
- Summary:
  - Added `breadcrumb_aria_label`, `markdown_source_glyph`, and
    `markdown_preview_glyph` to the default `file_preview` app-shell chrome
    payload.
  - The React app-shell normalizer preserves those fields and
    `FilePreviewSurface` consumes them for breadcrumb accessibility text and
    markdown mode button glyphs instead of hard-coding `File path`, `C`, or
    `P`.
  - Added frontend and Python guards so File Preview chrome cannot regain
    renderer-local visible copy or mode symbols.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue scanning GUI chrome-only symbols and dev fixtures for app-shell
    ownership where they affect visible shell behavior.

### DC-272

- Date: 2026-07-05
- Change Topic: GUI command-palette shortcut labels are app-shell declared
- Summary:
  - Added `command_palette.labels.shortcut_labels` and
    `shortcut_separator` to the default app-shell capability payload.
  - The React app-shell normalizer preserves shortcut display descriptors, and
    `command-palette-model` formats keybindings from those descriptors instead
    of hard-coding `Ctrl`, `Alt`, `Shift`, or `Esc`.
  - Unknown keybinding parts now remain raw tokens, with only single-character
    key tokens uppercased for display.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue moving renderer-owned chrome text and visible formatting tokens
    into app-shell descriptors.

### DC-271

- Date: 2026-07-05
- Change Topic: GUI right-panel surface titles are descriptor-first
- Summary:
  - `rightPanelSurfaceTitle` now prefers the active app-shell surface
    descriptor `title` and uses the caller fallback only when no descriptor
    title exists.
  - Removed the renderer-local English `Open ...` command-label stripping
    heuristic from the right-panel controller.
  - Added frontend and Python guards so surface opening cannot derive panel
    titles by parsing command copy.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/right-panel-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Required: No
- Follow-up:
  - Continue removing renderer-local visible-copy heuristics where app-shell
    descriptors already carry the display contract.

### DC-270

- Date: 2026-07-05
- Change Topic: GUI App Home untitled thread fallback is descriptor-owned
- Summary:
  - Added `home.threads.session_fallback_prefix` to the default app-shell
    capability payload.
  - `app-home-model` now uses the app-shell prefix for untitled thread rows
    and falls back only to the safe session id fragment when the descriptor is
    absent.
  - Added frontend and Python guards so renderer-local ``Session ${id}``
    fallback copy cannot return.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/app-home-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No
- Follow-up:
  - Continue auditing app-home/workbench display fallbacks that still derive
    visible copy from renderer-local English defaults.

### DC-269

- Date: 2026-07-05
- Change Topic: GUI composer hints are app-shell descriptors
- Summary:
  - `/api/app/bootstrap` now declares ordered
    `capabilities.chrome.composer.hints` records for composer hint-bar items.
  - The React app-shell model normalizes hint descriptors with labels, tone,
    status, and visibility state.
  - `composer-interaction-model` filters hint descriptors by running and
    pending-interaction state instead of owning a fixed hint id/order list.
  - Added frontend and Python guards so renderer-local composer hint lists
    cannot return.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/composer/composer-interaction-model.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/composer-interaction-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No
- Follow-up:
  - Continue moving renderer-owned fallback UI behavior to backend/app-shell
    descriptors where the GUI needs to adapt to different agent applications.

### DC-268

- Date: 2026-07-05
- Change Topic: GUI composer slash commands do not use static hint fallbacks
- Summary:
  - Removed the renderer-local `commandHints` slash-command fallback path from
    `App`, `Composer`, and `composer-interaction-model`.
  - Composer slash-command menu items now come only from command capability
    projection.
  - Added frontend and Python architecture guards so static command hint
    fallbacks and their `"command"` group synthesis cannot be reintroduced.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/composer/composer-interaction-model.js`
  - `src/embedagent/frontend/gui/webapp/test/composer-integration-source.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No
- Follow-up:
  - Continue deleting GUI fallbacks that synthesize agent/workflow behavior
    instead of consuming backend/app-shell descriptors.

### DC-267

- Date: 2026-07-05
- Change Topic: GUI slash-command default group is app-shell declared
- Summary:
  - `/api/app/bootstrap` `capabilities.chrome.composer.command_menu` now
    declares `default_command_group_id`.
  - Session command normalization no longer synthesizes the `"command"` group
    when protocol command descriptors omit `group`.
  - Composer and workbench command conversion use the app-shell default group
    descriptor when they need to place backend slash commands.
  - Added frontend and Python architecture guards for the no renderer-local
    command group fallback rule.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/command-capabilities.js`
  - `src/embedagent/frontend/gui/webapp/src/composer/composer-command-search.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/command-capabilities.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/composer-command-search.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No
- Follow-up:
  - Continue removing renderer-local command and status fallbacks so GUI
    surfaces adapt through app-shell descriptors only.

### DC-266

- Date: 2026-07-04
- Change Topic: GUI source-control group/provider labels do not fall back to raw kinds
- Summary:
  - `groupLabel()` and `providerLabel()` now render only app-shell declared
    labels or app-shell declared fallback labels.
  - Missing Source Control group/provider descriptors no longer display raw
    normalized kind strings as renderer-local UI copy.
  - Added frontend and Python architecture guards for the no raw-kind label
    fallback rule.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/source-control/source-control-presentation.js`
  - `src/embedagent/frontend/gui/webapp/test/source-control-state.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No
- Follow-up:
  - Continue removing renderer-local fallbacks where raw protocol/workflow ids
    still leak into visible GUI chrome.

### DC-265

- Date: 2026-07-04
- Change Topic: GUI source-control group order is app-shell chrome
- Summary:
  - `/api/app/bootstrap` `capabilities.source_control.chrome` now declares
    `group_order` for Source Control file grouping order.
  - The renderer normalizes that descriptor to `groupOrder` and
    `SourceControlPanel` maps over it instead of owning a fixed
    `conflicted/staged/unstaged/untracked` array.
  - Added frontend and Python architecture guards for descriptor-owned Source
    Control group ordering.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No
- Follow-up:
  - Continue removing renderer-local GUI semantic fallbacks that prevent app
    shells from adapting cleanly to different base or specialized agents.

### DC-264

- Date: 2026-07-04
- Change Topic: GUI source-control file status labels are app-shell chrome
- Summary:
  - `/api/app/bootstrap` `capabilities.source_control.chrome` now declares
    `file_status_labels` for Source Control file badges.
  - The renderer normalizes those descriptors to `fileStatusLabels` and
    `fileStatusLabel()` no longer synthesizes labels from Git status initials
    or `?`.
  - Added frontend and Python architecture guards for the no renderer-local
    status badge fallback rule.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/source-control/source-control-presentation.js`
  - `src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/source-control-state.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No
- Follow-up:
  - Continue removing renderer-local GUI copy/semantic fallbacks so app shells
    can adapt to different base or specialized agents through descriptors.

### DC-263

- Date: 2026-07-04
- Change Topic: GUI command-palette group leading markers are descriptors
- Summary:
  - Default app-shell command-palette group descriptors now explicitly declare
    leading markers.
  - Command-palette command/submenu rows use `descriptor.leading` only and no
    longer fall back to the group title's first character or `>`.
  - Added frontend and Python architecture guards for the no synthesized group
    leading marker rule.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-262

- Date: 2026-07-04
- Change Topic: GUI command-palette session/workspace leading markers are descriptors
- Summary:
  - Added app-shell command-palette label descriptors for session and workspace
    leading markers.
  - Command-palette session/workspace rows now render those descriptor values
    and leave the marker empty when absent instead of hard-coding `T` / `W`.
  - Added frontend and Python architecture guards for the no renderer-local
    leading marker rule.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-261

- Date: 2026-07-04
- Change Topic: GUI surface command palette copy is descriptor-owned
- Summary:
  - Surface and bottom-drawer command projections now carry surface descriptor
    descriptions into workbench commands.
  - Command-palette command row descriptions no longer synthesize
    `Open <surface>` or `Open <drawer>` copy from surface/drawer ids.
  - Added frontend and Python architecture guards so surface command secondary
    copy stays descriptor-owned.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-260

- Date: 2026-07-04
- Change Topic: GUI command-palette command rows avoid command-id copy
- Summary:
  - Removed command-palette command row description and meta fallbacks that
    displayed command ids when slash/description descriptors were absent.
  - Commands with explicit labels but no secondary copy now render empty
    secondary fields instead of leaking implementation ids into the UI.
  - Added frontend and Python architecture guards for command row
    description/meta no-fallback behavior.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-259

- Date: 2026-07-04
- Change Topic: GUI command-palette groups require descriptor titles
- Summary:
  - Removed command-palette group title fallbacks that title-cased group ids.
  - Commands in undeclared or untitled command-palette groups now stay out of
    root and submenu palette projections instead of becoming renderer-owned
    groups.
  - Added frontend and Python architecture guards for the no-fallback group
    title rule.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-258

- Date: 2026-07-04
- Change Topic: GUI workbench command labels are descriptor-driven
- Summary:
  - App-shell command normalization now preserves missing command labels as
    empty instead of synthesizing visible labels from command ids.
  - Workbench command projection omits app/workbench commands without explicit
    labels, while dynamic slash commands remain visible only when their
    capability descriptor provides an explicit `usage`, `slash`, or label.
  - Command palette rows no longer fall back from missing command labels to
    command ids, including submenu projection.
  - Added frontend and Python architecture guards to keep command id strings
    out of visible workbench command labels.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-257

- Date: 2026-07-04
- Change Topic: GUI Diff workbench tab title is payload/app-shell driven
- Summary:
  - Removed the store fallback that opened Diff workbench surfaces with a
    renderer-local `"diff"` title when the diff payload title was absent.
  - Untitled Diff payloads now keep an empty workbench surface title so the
    right-panel tab can use the app-shell surface descriptor or remain empty.
  - Added frontend and Python architecture guards to keep Diff tab titles from
    regressing to renderer string literals.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/test/store-reducer.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-256

- Date: 2026-07-04
- Change Topic: GUI resource surface titles use instance data only
- Summary:
  - Removed renderer-local `"file"`, `"preview"`, and `"terminal"` fallback
    titles from workbench resource surface helpers.
  - Preview surface helper calls without an explicit title or preview
    id/resource no longer create a visible fallback tab.
  - Added frontend and Python guards so resource surface titles stay limited to
    instance data such as file basenames, preview ids/URLs, and terminal ids.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/test/right-panel-store-parity.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-255

- Date: 2026-07-04
- Change Topic: GUI surface launcher titles are descriptor-only
- Summary:
  - Removed app-shell normalization fallback that synthesized surface titles
    from surface kind/id values.
  - Workbench surface launchers and surface commands now require explicit
    app-shell descriptor titles before becoming visible entrypoints.
  - `titleForSurfaceKind` now returns an empty title when no descriptor title is
    available instead of exposing a renderer-local kind fallback.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-state.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-254

- Date: 2026-07-04
- Change Topic: GUI thread action rail labels are descriptor-only
- Summary:
  - Removed app-shell and app-home fallback paths that synthesized thread
    lifecycle action labels from action ids.
  - Actions without descriptor labels no longer render in the visible thread
    action rail.
  - Removed renderer-local disabled reason text for thread lifecycle actions;
    disabled reason labels now remain descriptor-declared when present.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/app-home-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-253

- Date: 2026-07-04
- Change Topic: GUI thread lifecycle notice copy is descriptor-only
- Summary:
  - Removed renderer-synthesized thread lifecycle fallback notice titles such
    as `${action.label} failed`.
  - Unknown lifecycle actions now keep only minimal id/capability routing data
    instead of inventing visible labels from action ids.
  - Added frontend and Python architecture guards so empty-title and failure
    notices remain app-shell descriptor driven, with missing notice copy left
    absent instead of locally synthesized.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/thread-lifecycle-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/thread-lifecycle-controller.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-252

- Date: 2026-07-04
- Change Topic: GUI command-result timeline labels are payload/app-shell declared
- Summary:
  - Removed `/${commandName}` synthesis from the T3 timeline command-result
    projection and visible command-result row fallback.
  - Command names remain structured data for payload-driven effects, while
    visible timeline labels now come only from explicit payload `label` values
    or app-shell `activity_rows.commandDefaultName`.
  - Added frontend and Python architecture guards to prevent command-name based
    timeline label fallback from returning.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-251

- Date: 2026-07-04
- Change Topic: GUI command-result run-output logs are payload-declared
- Summary:
  - Removed renderer-synthesized `command: /...` run-output labels from
    `socket-message-effects.js`.
  - Command-result WebSocket effects now write bottom-drawer log entries only
    when the backend/hosted command payload declares `log_label` / `log_detail`.
  - Added frontend and Python architecture guards so command-result logging
    remains payload-driven instead of slash-command-name driven.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-250

- Date: 2026-07-04
- Change Topic: GUI API error fallback copy is app-shell declared
- Summary:
  - Removed helper-local request-failure copy from Preview, Terminal, and
    Source Control frontend API helpers.
  - API helpers now throw backend `detail`, backend `error`, status text, or an
    empty message; renderer controllers then fall through to app-shell chrome
    fallback notices.
  - Added preview API behavior coverage plus frontend and architecture guards
    so surface API helpers do not reintroduce local request-failure strings.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/preview/preview-api.js`
  - `src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js`
  - `src/embedagent/frontend/gui/webapp/src/source-control/source-control-api.js`
  - `src/embedagent/frontend/gui/webapp/test/preview-api.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-249

- Date: 2026-07-04
- Change Topic: Retired GUI sidebar sidecar state removed
- Summary:
  - Removed unused root `sidebarTab` state and the `set_sidebar` reducer action
    from the GUI store.
  - Removed `set_sidebar` dispatches from the workspace command path and visual
    debug fixtures; workspace open still focuses the workspace path input
    directly.
  - Removed unused workbench `activeSection` / `projectSection` sidebar state
    and renamed the remaining thread tab test id away from the old `chats`
    vocabulary.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/workbench-command-controller.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
  - `tests/manual/playwright_example.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-248

- Date: 2026-07-04
- Change Topic: App-shell product-name fallback removed from renderer model
- Summary:
  - Removed the renderer app-shell model fallback that filled missing
    `productName` metadata with the bundled `EmbedAgent` product name.
  - `createAppShellState()` and `normalizeAppBootstrap()` now preserve missing
    product names as empty strings so generic or specialized GUI shells must
    receive their branding from backend app metadata.
  - Added frontend behavior/source checks and an architecture guard to prevent
    reintroducing product-name defaults in renderer app-shell normalization.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-247

- Date: 2026-07-04
- Change Topic: Files surface title is app-shell declared
- Summary:
  - Removed the hard-coded `Files` header from the GUI right-panel
    `FilesSurface`.
  - `RightPanelSurfaceBody.jsx` now passes the active surface descriptor into
    `FilesSurface.jsx`, and the panel header renders `surface.title`.
  - Added frontend and architecture guards so right-panel Files surface titles
    stay descriptor-driven for generic or specialized agent shells.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-246

- Date: 2026-07-04
- Change Topic: No-workspace GUI branding is app-shell declared
- Summary:
  - Removed the hard-coded `EmbedAgent` no-workspace kicker from the GUI
    renderer.
  - `app-home-model.js` now projects backend app metadata `productName`, and
    `NoWorkspaceState.jsx` renders that descriptor value when present.
  - Added frontend and architecture guards so no-workspace shell branding stays
    driven by app-shell metadata instead of renderer defaults.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx`
  - `src/embedagent/frontend/gui/webapp/test/app-home-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-245

- Date: 2026-07-04
- Change Topic: GUI session workflow-state defaults are not invented
- Summary:
  - Removed GUI protocol/backend and renderer fallbacks that filled missing
    session `workflow_state` values with the legacy `chat` state name.
  - Session bootstrap now preserves the explicit snapshot value and leaves
    omitted workflow-state names empty, while workflow display uses the
    separate generic `workflow` payload.
  - Added Python and frontend regressions plus source/architecture guards to
    keep GUI session payloads free of invented workflow-state defaults.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/protocol_payloads.py`
  - `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
  - `src/embedagent/frontend/gui/webapp/test/state-helpers.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_protocol_projection.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-244

- Date: 2026-07-04
- Change Topic: GUI session-load command-result effects are payload-driven
- Summary:
  - Removed the GUI WebSocket effect branch that loaded a switched session only
    for `commandName === "resume"`.
  - Command results now trigger session load from structured
    `data.switch_session_id`, allowing specialized resume/session-switch
    commands without GUI command-name coupling.
  - Added frontend regression coverage and source/architecture guards to keep
    command-result session-load effects payload-driven.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-243

- Date: 2026-07-04
- Change Topic: GUI user-input interactions do not default to `ask_user`
- Summary:
  - Removed the GUI interaction read-model fallback that filled missing
    user-input `tool_name` values with the built-in `ask_user` tool name.
  - Pending user-input display is now driven by `kind` /
    `sourceActivityKind` and explicit backend payload fields, keeping the GUI
    adaptable to base or specialized agents that do not expose `ask_user`.
  - Added frontend regression coverage and source/architecture guards to keep
    user-input interaction projection free of built-in tool-name defaults.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`
  - `src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-242

- Date: 2026-07-04
- Change Topic: GUI Diff surface command-result activation is payload-driven
- Summary:
  - Removed the GUI WebSocket effect branch that opened the Diff surface only
    for `commandName === "diff"`.
  - Command results now open the Diff right-panel whenever they carry a
    structured `data.diff` payload, allowing specialized agents to expose
    diff-producing commands without GUI command-name coupling.
  - Added frontend regression coverage and source/architecture guards to keep
    command-result Diff activation payload-driven.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-241

- Date: 2026-07-04
- Change Topic: GUI timeline review rows are payload-driven
- Summary:
  - Removed the T3 timeline projection branch that treated
    `commandName === "review"` as review-result semantics.
  - Review result rows are now selected only from structured `data.review` or
    `review` payload fields, allowing alternate command names and specialized
    agents without GUI command-name coupling.
  - Added frontend regression coverage and source/architecture guards so the
    renderer cannot reintroduce `/review` command-name row classification.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-240

- Date: 2026-07-04
- Change Topic: GUI timeline changed-file inference is catalog-driven
- Summary:
  - Added `changed_path_arg` to the safe tool presentation metadata projected
    through `ToolCatalogEntry.metadata`.
  - Declared `changed_path_arg = "path"` for `write_file` and `edit_file`.
  - Removed the frontend `WRITE_TOOLS`/`commandName === "diff"` changed-file
    inference table from `t3-timeline.js`; changed-file summaries now use
    explicit changed-file lists, explicit diffs, or catalog-declared changed
    path arguments.
  - Extended frontend projection tests, runtime catalog tests, source checks,
    and architecture guards to keep changed-file path inference metadata-owned.
- Impacted Scope:
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/tool-presentation.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_dynamic_tool_registration.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/tool-contracts.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-239

- Date: 2026-07-04
- Change Topic: GUI timeline tool previews are catalog-driven
- Summary:
  - Added safe tool presentation metadata projection through
    `ToolCatalogEntry.metadata`, currently including `preview_arg` only.
  - Declared preview arguments for default built-in tools and the default
    C/C++ `run_recipe` workflow tool, and exposed tool descriptors through
    session capabilities for GUI consumption.
  - Removed renderer-side timeline preview/request-kind branches for
    `bash`, `read_file`, `grep_text`, and related built-in tool names.
  - Added runtime, workflow, adapter capability, frontend projection, and
    architecture guard coverage so specialized agents can drive GUI timeline
    previews through catalog metadata.
- Impacted Scope:
  - `src/embedagent_core/tool_contracts.py`
  - `src/embedagent_core/capabilities.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/workflow_packages/c_cpp/tool_metadata.py`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_dynamic_tool_registration.py`
  - `tests/test_workflow_extensions.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/tool-contracts.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-238

- Date: 2026-07-04
- Change Topic: GUI timeline work-row chrome declaration
- Summary:
  - Added `/api/app/bootstrap` `capabilities.chrome.timeline.work_row`
    descriptors for fallback work-row heading, fallback icon name, and status
    aria labels.
  - Removed renderer/projection fallback work-row copy from `WorkRow.jsx` and
    `t3-timeline.js`; projection now leaves missing heading/icon presentation
    data empty for the app-shell renderer to fill.
  - Extended frontend projection tests, source checks, backend payload
    assertions, app-shell descriptor tests, and architecture guards for the
    work-row chrome/data split.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-237

- Date: 2026-07-04
- Change Topic: GUI timeline tool-detail chrome declaration
- Summary:
  - Added `/api/app/bootstrap` `capabilities.chrome.timeline.tool_detail`
    descriptors for tool-detail field labels, section titles, and match
    fallback labels.
  - Changed T3 timeline work-detail projection to emit field keys and section
    kinds without default renderer chrome labels.
  - Routed `TimelineRows.jsx` / `WorkRow.jsx` / `ToolDetail.jsx` through the
    app-shell tool-detail chrome so specialized agent shells can replace tool
    detail copy without changing the renderer.
  - Extended frontend T3 timeline tests, source checks, app-shell descriptor
    tests, backend payload assertions, and architecture guards for the
    tool-detail chrome/data split.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-236

- Date: 2026-07-04
- Change Topic: GUI T3 timeline projection chrome/data split
- Summary:
  - Stopped `t3-timeline.js` from precomputing Timeline renderer chrome labels
    such as turn-fold elapsed/stopped copy, reasoning fallback copy, compact
    fallback copy, and review fallback labels.
  - Added turn-fold `completedAt` and `interrupted` display data so
    `TimelineRows` can format elapsed/stopped labels from
    `capabilities.chrome.timeline.activity_rows` templates.
  - Extended frontend T3 timeline tests, source checks, app-shell descriptor
    tests, backend payload assertions, and architecture guards for the
    projection/data split.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-235

- Date: 2026-07-04
- Change Topic: GUI Timeline activity-row chrome descriptor convergence
- Summary:
  - Extended `/api/app/bootstrap` `capabilities.chrome.timeline.activity_rows`
    descriptors for Timeline working, turn-fold, interaction, reasoning,
    thinking, context-summary, command-result, review-result, and timer copy.
  - Routed `TimelineRows` activity-row labels, status text, count templates, and
    timer templates through normalized app-shell chrome instead of
    renderer-local English defaults.
  - Extended frontend source checks, app-shell normalizer assertions, backend
    payload assertions, and pre-release architecture guards for the
    activity-row copy boundary.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-234

- Date: 2026-07-04
- Change Topic: GUI Timeline work-group chrome descriptor convergence
- Summary:
  - Extended `/api/app/bootstrap` `capabilities.chrome.timeline.work_group`
    descriptors for Timeline work-group aria labels and overflow toggle copy.
  - Routed `TimelineRows` work-group labels through normalized app-shell chrome
    instead of renderer-local tool-call English strings.
  - Extended frontend source checks, app-shell normalizer assertions, backend
    payload assertions, and pre-release architecture guards for the work-group
    copy boundary.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-233

- Date: 2026-07-04
- Change Topic: GUI Timeline chrome descriptor convergence
- Summary:
  - Added `/api/app/bootstrap` `capabilities.chrome.timeline` descriptors for
    Timeline log aria labels, empty/history/termination copy, and changed-files
    card summary/action labels.
  - Routed `Timeline`, `TimelineRows`, and `ChangedFilesCard` through normalized
    timeline chrome instead of renderer-local English defaults.
  - Added frontend source checks, app-shell normalizer assertions, backend
    payload assertions, and pre-release architecture guards for the new
    display-only boundary.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/ChangedFilesCard.jsx`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-232

- Date: 2026-07-04
- Change Topic: GUI Diff Panel chrome descriptor convergence
- Summary:
  - Added `/api/app/bootstrap` `capabilities.surfaces.chrome.diff_panel`
    descriptors for Diff Panel default title, empty state, controls, file rail,
    collapse labels, and source-control diff title templates.
  - Routed `DiffPanel`, `createDiffSurfaceState`, source-control diff opening,
    and `/diff` socket effects through normalized `diffPanel` chrome instead of
    renderer-local Diff/Git title defaults.
  - Added webapp source checks, model/socket tests, backend app-shell payload
    assertions, and pre-release architecture guards for the new boundary.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/diff-model.js`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-231

- Date: 2026-07-04
- Change Topic: GUI File surface tab title fallback convergence
- Summary:
  - Routed `fileSurfaceTitle(...)` through normalized
    `capabilities.surfaces.chrome.file_preview.default_file_title`.
  - Removed the remaining renderer-local `"File"` fallback from the right-panel
    controller.
  - Added frontend source and architecture guard coverage for the App/controller
    handoff.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/development-tracker.md`
- ADR Required: No

### DC-230

- Date: 2026-07-04
- Change Topic: GUI Command Palette empty-state copy hardening
- Summary:
  - Removed the renderer-local English default from `CommandPaletteResults`.
  - Kept Command Palette empty-state copy owned by `/api/app/bootstrap`
    `capabilities.command_palette.labels`.
  - Added frontend source and architecture guard coverage so missing app-shell
    labels no longer revive a built-in GUI fallback.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPaletteResults.jsx`
  - `src/embedagent/frontend/gui/webapp/test/command-palette-source.test.mjs`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/development-tracker.md`
- ADR Required: No

### DC-229

- Date: 2026-07-04
- Change Topic: GUI Composer menu chrome descriptor convergence
- Summary:
  - Extended `/api/app/bootstrap` `capabilities.chrome.composer` with a
    `command_menu` descriptor for slash/path menu aria labels, empty states,
    path group label, item-kind labels, and fallback command group copy.
  - Routed `App.jsx`, `Composer.jsx`, `ComposerCommandMenu.jsx`, and the
    composer search/interaction helpers through normalized app-shell Composer
    menu chrome.
  - Reused `capabilities.command_palette.groups` for Composer slash-command
    group labels so the GUI does not keep a second command group title table.
  - Added app-shell, frontend model/source, and architecture guard coverage for
    Composer menu chrome ownership.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerCommandMenu.jsx`
  - `src/embedagent/frontend/gui/webapp/src/composer/composer-command-search.js`
  - `src/embedagent/frontend/gui/webapp/src/composer/composer-interaction-model.js`
  - `src/embedagent/frontend/gui/webapp/src/composer/composer-path-context.js`
  - `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/composer-command-search.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/composer-components-source.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/composer-interaction-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/composer-path-context.test.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-228

- Date: 2026-07-04
- Change Topic: GUI File Preview chrome descriptor convergence
- Summary:
  - Extended `/api/app/bootstrap` `capabilities.surfaces.chrome` with a
    `file_preview` descriptor for default file/project labels, loading/error
    fallback copy, retry/copy/explorer actions, metadata separators, line
    labels, and language labels.
  - Routed `App.jsx`, `RightPanelSurfaceBody.jsx`, `FilePreviewSurface.jsx`,
    and `file-preview-model.js` through normalized app-shell file-preview
    chrome instead of renderer-local English defaults.
  - Removed the store-level file preview error fallback and added app-shell,
    frontend model/source, and architecture guard coverage for File Preview
    chrome ownership.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/file-preview-model.js`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/test/file-preview-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-227

- Date: 2026-07-04
- Change Topic: GUI Branch Toolbar chrome descriptor convergence
- Summary:
  - Extended `/api/app/bootstrap` `capabilities.source_control.chrome` with a
    `branch_toolbar` descriptor for checkout labels, change/conflict summary
    words, disabled reasons, action labels, refresh title, and metadata
    separator.
  - Routed `App.jsx`, `branch-toolbar-model.js`, and `BranchToolbar.jsx`
    through normalized source-control chrome so the composer toolbar no longer
    owns renderer-local English defaults.
  - Added focused app-shell, webapp model/source, and architecture guard
    coverage for Branch Toolbar chrome ownership.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/BranchToolbar.jsx`
  - `src/embedagent/frontend/gui/webapp/src/source-control/branch-toolbar-model.js`
  - `src/embedagent/frontend/gui/webapp/test/branch-toolbar-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-226

- Date: 2026-07-04
- Change Topic: GUI source-control chrome descriptor convergence
- Summary:
  - Extended `/api/app/bootstrap` `capabilities.source_control.chrome` with
    source-control panel labels, notices, count labels, group labels, provider
    labels, and runtime labels.
  - Routed `App.jsx`, `SourceControlPanel.jsx`, and source-control
    presentation helpers through normalized app-shell source-control chrome
    instead of renderer-local English defaults.
  - Added app-shell, frontend source, presentation-helper, and architecture
    guard coverage for source-control chrome ownership.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx`
  - `src/embedagent/frontend/gui/webapp/src/source-control/source-control-presentation.js`
  - `src/embedagent/frontend/gui/webapp/src/source-control/source-control-state.js`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-225

- Date: 2026-07-04
- Change Topic: Self-extension authoring workflow default decoupling
- Summary:
  - Removed the default C/C++ workflow `run_recipe` tool-name import from
    `SelfExtensionAuthoringService`.
  - Generated local recipe files and generated extension validation recipes no
    longer write a default workflow `tool_name`; selected workflow packages
    project runnable recipe tools at their own boundaries.
  - Added behavior coverage and an architecture guard preventing
    `self_extension_authoring.py` from importing C/C++ workflow defaults.
- Impacted Scope:
  - `src/embedagent/self_extension_authoring.py`
  - `tests/test_self_extension_authoring.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/tool-contracts.md`
  - `docs/modules/tools-and-tooling.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-224

- Date: 2026-07-04
- Change Topic: GUI bottom drawer chrome descriptor convergence
- Summary:
  - Extended `/api/app/bootstrap` `capabilities.surfaces.chrome` with bottom
    drawer aria label, run-output empty text, and termination reason prefix.
  - Routed `BottomDrawer.jsx` through `surfaceChromeLabels(appCapabilities)`
    instead of renderer-local run-output copy.
  - Added app-shell, frontend source, and architecture guard coverage for the
    bottom drawer chrome fields.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-223

- Date: 2026-07-04
- Change Topic: GUI preview chrome descriptor convergence
- Summary:
  - Added `/api/app/bootstrap` `capabilities.preview` descriptors for preview
    local-server presets, toolbar labels, status labels, empty states, and
    failure notices.
  - Routed `App.jsx`, `RightPanelSurfaceBody`, `PreviewSurface`, and
    `preview-surface-model` through normalized preview chrome instead of
    renderer-local English defaults.
  - Added frontend source checks and architecture guards so Preview surface
    copy cannot return to renderer-owned component/model paths.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/PreviewSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/preview-surface-model.js`
  - `tests/test_gui_app_shell.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-222

- Date: 2026-07-04
- Change Topic: Local resource discovery workflow default decoupling
- Summary:
  - Removed the default C/C++ workflow `run_recipe` tool-name import from
    generic `local_resources` discovery.
  - Local `.embedagent/recipes/*.json` resources now keep an empty `tool_name`
    unless the resource explicitly declares one; the default C/C++ workflow
    recipe list still normalizes runnable workspace recipes to its own
    `run_recipe` tool boundary.
  - Added local-resource behavior coverage and an architecture guard preventing
    `local_resources.py` from importing C/C++ workflow defaults.
- Impacted Scope:
  - `src/embedagent/local_resources.py`
  - `src/embedagent/workspace_recipes.py`
  - `tests/test_local_resources.py`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/tools-and-tooling.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-221

- Date: 2026-07-04
- Change Topic: GUI terminal chrome descriptor convergence
- Summary:
  - Added `/api/app/bootstrap` `capabilities.terminal.chrome` descriptors for
    terminal pane labels, toolbar actions, input placeholder, empty/unavailable
    states, and failure notices.
  - Routed `TerminalShell`, `terminal-controller`, and terminal label fallback
    logic through the normalized app-shell terminal chrome instead of
    renderer-local English defaults.
  - Added frontend and architecture guards so terminal copy cannot return to
    `TerminalShell.jsx`, `terminal-controller.js`, or `terminal-labels.js`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx`
  - `src/embedagent/frontend/gui/webapp/src/terminal/terminal-labels.js`
  - `tests/test_pre_release_architecture_guards.py`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-220

- Date: 2026-07-04
- Change Topic: GUI surface display copy descriptor convergence
- Summary:
  - Removed renderer-local right-panel and bottom-drawer surface display copy
    from `workbench/surfaces.js`; the local registry now keeps only supported
    renderer mounting, resource, close-behavior, launcher support, and
    persistence metadata.
  - Surface titles, icons, descriptions, command labels, slash metadata,
    launcher ordering, visibility hints, and keywords now come from normalized
    `/api/app/bootstrap` app-shell surface descriptors when surfaces are
    listed, opened, or rendered.
  - Added frontend and architecture guards so missing app-shell surface
    descriptors do not silently re-enable local GUI defaults.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `tests/test_pre_release_architecture_guards.py`
  - `docs/modules/frontend-gui.md`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-219

- Date: 2026-07-04
- Change Topic: GUI app-shell chrome copy descriptor convergence
- Summary:
  - Added `/api/app/bootstrap` `capabilities.chrome` descriptors for workbench
    header, sidebar, composer, composer interaction, and legacy
    Settings/Diagnostics/Plan panel copy.
  - Removed the renderer-local `strings.js` / `LangContext` i18n table,
    deleted the unused `InteractionPanel.jsx`, and routed active React
    components through the normalized app-shell chrome read model.
  - Added architecture guards so command/app/surface copy and GUI chrome copy
    cannot return as frontend-owned global string registries.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/app_shell_spec.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/`
  - `tests/test_pre_release_architecture_guards.py`
  - `docs/modules/frontend-gui.md`
- Related Docs:
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- ADR Required: No

### DC-218

- Date: 2026-07-01
- Change Topic: Completed superpowers material archive closeout
- Summary:
  - Moved completed hosted runtime, experience runtime, interaction
    convergence, and interaction lifecycle working materials out of active
    `docs/superpowers/` into
    `docs/archive/pi-t3-residual-debt-cleanup/`.
  - Updated archive indexes and active docs navigation so
    `docs/superpowers/` again represents only current-slice material.
  - Synchronized the active GUI module document with the current hosted
    pending-interaction lifecycle instead of the removed synchronous callback
    model.
- Impacted Scope:
  - `docs/superpowers/`
  - `docs/archive/pi-t3-residual-debt-cleanup/`
  - `docs/modules/frontend-gui.md`
  - `docs/README.md`
  - `docs/development-tracker.md`
- Related Docs:
  - `docs/documentation-governance.md`
  - `docs/workflows/code-doc-sync.md`
  - `docs/archive/README.md`
- ADR Required: No

### DC-217

- Date: 2026-06-29
- Change Topic: ProgressGuard and turn experience read-model convergence
- Summary:
  - Replaced repeated tool-name stopping with `ProgressGuard`, which compares
    action intent plus observation evidence fingerprints for no-progress
    detection.
  - Added `TurnExperienceReducer` to project completed work, unverified work,
    blockers, validation failures, and next steps from `tool_result` and
    `loop_transition` transcript events.
  - Exposed `turn_experience` through session snapshots and `session_finished`
    events so CLI, TUI, and GUI render one backend-owned read model.
- Impacted Scope:
  - `src/embedagent/guard.py`
  - `src/embedagent/agent_loop.py`
  - `src/embedagent/turn_experience.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/cli.py`
  - `src/embedagent/frontend/tui/`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/`
- Related Docs:
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
- ADR Required: No

### DC-216

- Date: 2026-06-27
- Change Topic: Hosted adapter and QueryEngine service-boundary cleanup
- Summary:
  - Split GUI backend HTTP route registration into focused route modules while
    keeping `server.py` as the composition root.
  - Extracted hosted slash-command dispatch/result emission into
    `HostedCommandService` and permission/user-input response glue into
    `HostedInteractionService`.
  - Moved provider snapshot metadata, workflow prompt append/dedupe, and
    compact-boundary/compacted-history payload assembly into
    `TurnSnapshotService`, `PromptAssemblyService`, and `CompactionJournal`.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/backend/routes_app.py`
  - `src/embedagent/frontend/gui/backend/routes_sessions.py`
  - `src/embedagent/frontend/gui/backend/routes_terminal.py`
  - `src/embedagent/frontend/gui/backend/routes_source_control.py`
  - `src/embedagent/frontend/gui/backend/routes_preview.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/hosted_command_service.py`
  - `src/embedagent/hosted_interaction_service.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/turn_snapshot_service.py`
  - `src/embedagent/prompt_assembly_service.py`
  - `src/embedagent/compaction_journal.py`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/modules/agent-core.md`
  - `docs/modules/frontend-gui.md`
  - `docs/frontend-protocol.md`
- ADR Needed: No
- Follow-up:
  - Preserve these service boundaries in future Pi/T3 cleanup and avoid
    reintroducing adapter-local command helpers, QueryEngine snapshot helpers,
    QueryEngine compaction payload helpers, or monolithic GUI route modules.

### DC-215

- Date: 2026-06-27
- Change Topic: Tool metadata-driven GUI read-model invalidations
- Summary:
  - Added `read_model_invalidations` to tool catalog metadata and runtime
    observation/event decoration.
  - Moved GUI/Core task, artifact, and workspace-file refresh decisions to
    those metadata hints instead of hard-coded tool-name lists.
  - Trimmed stale renderer tool-label aliases and moved interaction request
    classification toward explicit request kind / permission category metadata.
- Impacted Scope:
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/harness/tool_metadata.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
- ADR Needed: No
- Follow-up:
  - Continue auditing frontend surfaces for remaining root-state or tool-name
    policy couplings.

### DC-214

- Date: 2026-06-27
- Change Topic: GUI live interaction activity stream convergence
- Summary:
  - Forwarded Core `permission_required` and `user_input_required` events
    through `CallbackBridge` into the backend-owned GUI `session_event` stream.
  - Moved GUI live session-event metadata completion (`event_id`, `seq`,
    `created_at`) to `WebSocketFrontend`, keeping renderer code from minting
    interaction activity records.
  - Removed renderer-side synthesis of `interaction.created` from raw
    `permission_request` / `user_input_request` WebSocket messages; those
    messages now only drive the blocking interaction UI and response path.
- Impacted Scope:
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `tests/test_gui_runtime.py`
  - `docs/frontend-protocol.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `AGENTS.md`
- ADR Needed: No
- Follow-up:
  - Continue GUI metadata-driven invalidation cleanup so file/task refresh
    behavior follows backend/tool metadata instead of hard-coded renderer tool
    sets.

### DC-213

- Date: 2026-06-27
- Change Topic: Permission category convergence and diagnostic loop failures
- Summary:
  - Removed `PermissionPolicy`'s parallel built-in tool-name taxonomy; the
    active `ToolRuntime` catalog metadata is now the source of truth for tool
    permission category.
  - Promoted `other` to an official ask-by-default permission category so
    unknown or invalid tool metadata cannot fall through to allow.
  - Marked command failures and timeouts as `outcome_class=diagnostic_failure`
    and excluded those diagnostic failures from hard loop guard stops, keeping
    C/C++ build/test failures visible to the next model turn.
- Impacted Scope:
  - `src/embedagent/permissions.py`
  - `src/embedagent/guard.py`
  - `src/embedagent/tools/_base.py`
  - `tests/test_permissions.py`
  - `tests/test_harness_guard_safety.py`
  - `tests/test_query_engine_refactor.py`
  - `docs/permission-model.md`
  - `docs/tool-contracts.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
- ADR Needed: No
- Follow-up:
  - Continue the remaining Pi/T3 residual cleanup slices for backend session
    stream contracts and GUI T3 state convergence.

### DC-212

- Date: 2026-06-26
- Change Topic: TUI session history cutover to bootstrap activities
- Summary:
  - Removed the old TUI flat history item view and event-list reload formatter.
  - Deleted `SessionHistoryAssembler.build_flat_history()` so
    `SessionHistoryAssembler.build().activities` is the only active frontend
    session-history read model.
  - Added pre-release guards preventing TUI flat item history, old item
    mutation callbacks, and event-list history reload paths from returning.
- Impacted Scope:
  - `src/embedagent/session_history.py`
  - `src/embedagent/frontend/tui/`
  - `tests/test_session_history.py`
  - `tests/test_tui_timeline_activities.py`
  - `tests/test_pre_release_architecture_guards.py`
  - `docs/frontend-protocol.md`
  - `docs/overall-solution-architecture.md`
  - `AGENTS.md`
- ADR Needed: No
- Follow-up:
  - Keep GUI and TUI session activation on the single session bootstrap
    `history.activities` contract; live transport output may update local
    display state only.

### DC-211

- Date: 2026-06-26
- Change Topic: WorkflowPatch projection field cleanup
- Summary:
  - Removed the unused `legacy_projection` field from extension
    `WorkflowPatch`.
  - Locked the current tool-result workflow patch shape to `workflow` plus safe
    `metadata`.
  - Added regression coverage so extension patch read models cannot regain
    legacy projection fields.
- Impacted Scope:
  - `src/embedagent/extensions.py`
  - `tests/test_capability_extensions.py`
  - `docs/tool-contracts.md`
  - `docs/overall-solution-architecture.md`
  - `AGENTS.md`
- ADR Needed: No
- Follow-up:
  - Keep extension/capability projections read-only and avoid adding parallel
    workflow-state carriers outside `workflow`/`metadata`.

### DC-210

- Date: 2026-06-26
- Change Topic: Active validation vocabulary cleanup
- Summary:
  - Removed compact-boundary reducer inference for old metadata-only payloads;
    current `compact_boundary` events must carry structured `token_counts` and
    `message_counts` if those diagnostics are needed.
  - Retired old Phase 5/6 validation scripts from active `scripts/` because
    they encoded pre-cutover mode/tool names and old loop entry points.
  - Updated the manual GUI Playwright example to use the current `tasks`
    inspector tab vocabulary.
- Impacted Scope:
  - `src/embedagent/compaction_state.py`
  - `tests/test_compaction_state.py`
  - `scripts/validate-phase5.py`
  - `scripts/validate-phase6.py`
  - `tests/manual/playwright_example.py`
  - `docs/development-tracker.md`
- ADR Needed: No
- Follow-up:
  - Keep historical phase validation notes in archive/changelog only; do not
    reintroduce active scripts that exercise removed mode or tool aliases.

### DC-209

- Date: 2026-06-26
- Change Topic: GUI activity runtime cutover
- Summary:
  - Switched React session activation to consume bootstrap `history.activities`
    through `session-runtime/activity-state.js`.
  - Removed the old frontend runtime projector and the `timelineFromEvents` /
    `timelineFromTurns` history reconstruction helpers from product source.
  - Removed the Runtime inspector timeline-projection diagnostic row so the GUI
    no longer exposes the old raw/structured replay split as current state.
- Impacted Scope:
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  - `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/frontend-protocol.md`
- ADR Needed: No
- Follow-up:
  - Continue GUI cleanup by removing dev fixture/product vocabulary remnants
    without reintroducing product reducer fixture actions.

### DC-208

- Date: 2026-06-26
- Change Topic: Bootstrap session activity read model
- Summary:
  - Added `history.activities` to `SessionHistoryAssembler.build(...)` so
    bootstrap history exposes a direct T3-style activity stream.
  - Kept nested `history.turns` as structured diagnostics while avoiding any
    event replay or frontend-owned history reconstruction.
  - Added backend tests proving session bootstrap carries the new activity read
    model.
- Impacted Scope:
  - `src/embedagent/session_history.py`
  - `tests/test_session_history.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
  - `docs/frontend-protocol.md`
  - `docs/overall-solution-architecture.md`
- ADR Needed: No
- Follow-up:
  - S06 should switch GUI activation to consume `history.activities` and remove
    the old timeline projection helpers from product runtime.

### DC-207

- Date: 2026-06-26
- Change Topic: GUI timeline/event reload route removal
- Summary:
  - Removed the `/api/sessions/{session_id}/events` reload route and the
    `load_session_events_after` adapter/core surface.
  - Renamed the GUI live event metadata carrier from `_timeline_event` to
    `_session_event`.
  - Added pre-release guards so session-history replay cannot re-enter through
    a timeline/event reload API.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/backend/session_events.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/core/adapter.py`
  - `tests/test_pre_release_architecture_guards.py`
- ADR Needed: No
- Follow-up:
  - S05/S06 should finish moving the frontend read model away from legacy
    timeline projection helpers.

### DC-206

- Date: 2026-06-26
- Change Topic: GUI backend active-core proxy removal
- Summary:
  - Removed the GUI backend `_ActiveCoreProxy` compatibility object and the
    `self.core` route proxy state.
  - Updated workspace-bound HTTP routes to resolve the active core explicitly
    through `GUIAppHost.require_core()`.
  - Added a pre-release architecture guard preventing the proxy from returning.
- Impacted Scope:
  - `src/embedagent/frontend/gui/backend/server.py`
  - `tests/test_pre_release_architecture_guards.py`
  - `docs/frontend-protocol.md`
  - `docs/overall-solution-architecture.md`
- ADR Needed: No
- Follow-up:
  - S04 should remove the remaining timeline/event reload vocabulary now that
    GUI route dependencies are explicit.

### DC-205

- Date: 2026-06-26
- Change Topic: QueryEngine loop/completion compatibility wrapper removal
- Summary:
  - Removed private `_run_loop` and `_is_completion_signal` compatibility
    wrappers from `QueryEngine`.
  - Routed turn-loop execution directly into `AgentLoop.run(...)`.
  - Kept completion decisions on the official `classify_assistant_turn(...)`
    classification boundary and added regression guards against reintroducing
    the wrappers.
- Impacted Scope:
  - `src/embedagent/query_engine.py`
  - `src/embedagent/agent_loop.py`
  - `tests/test_harness_completion_signal.py`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
- ADR Needed: No
- Follow-up:
  - Continue removing private facade wrappers as later slices move GUI and
    hosted adapter calls to explicit service boundaries.

### DC-204

- Date: 2026-06-26
- Change Topic: Pi/T3 residual debt cleanup
- Summary:
  - Aligned pre-release defaults to `default_mode: explore` with no persistent
    loop ceiling in JSON config.
  - Removed `ToolRuntime.execute_for_mode` and collapsed the adapter turn
    runner to a single `_run_turn` entrypoint.
  - Moved local skill/prompt slash command spec projection to
    `slash_commands.resource_command_specs(...)`.
  - Moved hosted `/review` session evidence shaping into
    `ReviewCommandService.build_payload_from_session(...)`.
  - Moved GUI run-output display state and transport connection/reload
    projection into `webapp/src/session-runtime/`, removing root-level GUI
    `connectionState` / `set_connection`.
  - Moved session activation and WebSocket lifecycle mechanics into focused
    `webapp/src/app-runtime/` controllers.
  - Archived the completed slice plan under
    `docs/archive/pi-t3-residual-debt-cleanup/`.
- Impacted Scope:
  - Agent Core hosted adapter boundaries
  - Tool/runtime contracts
  - GUI renderer runtime state
  - Documentation governance
- Related Docs:
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/tool-contracts.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/archive/pi-t3-residual-debt-cleanup/README.md`
- ADR Needed: No
- Follow-up:
  - Continue shrinking remaining hosted adapter slash-command responsibilities
    into focused services when the boundary is behaviorally clear.

### DC-203

- Date: 2026-06-25
- Change Topic: Pre-release debt cleanup closeout
- Summary:
  - Closed the seven-slice pre-release debt cleanup program after the
    transcript/session truth, unified action pipeline, Agent Core ownership,
    explicit extension capability, T3-style GUI state, dev fixture isolation,
    and release-gate slices landed.
  - Reclassified `docs/pre-release-architecture-debt-audit.md` from active
    backlog baseline to completed debt-retirement record and future
    deletion-oriented guardrail.
  - Archived the completed implementation plan under
    `docs/archive/pre-release-debt-cleanup/` and removed the active
    `docs/superpowers/plans/` pointer.
  - Kept clean Windows 7/WebView2 windowed GUI smoke and broader real C/C++
    workflow validation as release-cut evidence items before release claims.
- Impacted Scope:
  - Documentation governance
  - Architecture debt tracking
  - Release evidence planning
- Related Docs:
  - `AGENTS.md`
  - `README.md`
  - `docs/README.md`
  - `docs/archive/README.md`
  - `docs/archive/pre-release-debt-cleanup/README.md`
  - `docs/pre-release-architecture-debt-audit.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/overall-solution-architecture.md`
- ADR Needed: No
- Follow-up:
  - Run `validate-gui-smoke.cmd --windowed --auto-close-seconds 8` on a clean
    Windows 7 target machine and record the WebView2/runtime evidence before
    release claims.

### DC-202

- Date: 2026-06-25
- Change Topic: Contract-backed Win7 and C/C++ release gates
- Summary:
  - Added `release_gates` to `scripts/offline-runtime-contract.json` for
    runtime contract checks, bundle-local C smoke, GUI headless smoke, and
    Win7 windowed GUI smoke with Fixed Version WebView2 109 expectations.
  - Added `scripts/validate-cpp-smoke.py` and bundle staging for
    `validate-cpp-smoke.cmd`; the gate compiles
    `data/workspace-template/main.c` through bundle-local Clang and does not
    allow system-tool fallback by default.
  - Updated `validate-offline-bundle.ps1` and
    `check-bundle-dependencies.py` to consume release-gate metadata from the
    same runtime contract instead of maintaining separate hard-coded gate
    assumptions.
  - Fixed package verification so release profiles with
    `run_dynamic_checks: true` no longer force `-SkipDynamicChecks`.
  - Strengthened GUI smoke validation with `--require-fixed-webview2` and
    explicit fixed WebView2 evidence fields in the JSON output.
- Impacted Scope:
  - Offline packaging validation
  - Win7 GUI smoke procedure
  - C/C++ workflow release proof
  - Release documentation and preflight checklists
- Related Docs:
  - `AGENTS.md`
  - `README.md`
  - `docs/guides/win7-preflight-checklist.md`
  - `docs/guides/win7-gui-validation.md`
  - `docs/modules/packaging-and-deployment.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/pre-release-architecture-debt-audit.md`
- ADR Needed: No
- Follow-up:
  - Run `validate-gui-smoke.cmd --windowed --auto-close-seconds 8` on a clean
    Windows 7 target machine and record the WebView2/runtime evidence before
    release claims.

### DC-201

- Date: 2026-06-25
- Change Topic: GUI visual debug fixtures isolated from product reducers
- Summary:
  - Removed `visual_*fixture` action handling from the product GUI reducer and
    from `session-runtime/thread-state.js`.
  - Changed `visual-debug-fixtures.js` so the dev-only `?visual_debug=1` hook
    builds private `dev_fixture_*` descriptors and expands them into ordinary
    product actions such as `app_shell_bootstrap_loaded`,
    `session_activated`, `sessions_loaded`, `file_tree_loaded`,
    `file_preview_loaded`, `source_control_status_loaded`, and
    `workbench_surface_opened`.
  - Updated webapp tests to assert fixture expansion never dispatches
    `visual_*` actions and product stores do not contain visual fixture cases.
  - Documented generated GUI static assets as committed release artifacts for
    the current offline packaging model, with `webapp/src/` as the review source
    of truth.
- Impacted Scope:
  - GUI React reducer state
  - Dev-only visual debug harness
  - GUI generated static asset review policy
- Related Docs:
  - `AGENTS.md`
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/pre-release-architecture-debt-audit.md`
- ADR Needed: No
- Follow-up:
  - Closed by DC-202 release gates and DC-203 cleanup closeout; clean
    Win7/WebView2 windowed smoke remains release-cut evidence.

### DC-200

- Date: 2026-06-25
- Change Topic: T3-style GUI renderer state modules
- Summary:
  - Added `webapp/src/session-runtime/thread-state.js` as the focused owner for
    GUI session summaries, active thread id, and history-integrity display
    state.
  - Added `webapp/src/composer/composer-state.js` as the focused owner for the
    local composer draft.
  - Updated `App.jsx`, workspace reset, terminal controller, command palette
    wiring, reducer tests, and source tests so GUI code consumes focused read
    models instead of root-level `sessions`, `currentSessionId`, `composer`, or
    `historyIntegrity` fields.
  - Kept the existing T3-style right-panel/workbench persistence path as the
    promoted right-panel state boundary instead of adding another adapter over
    it.
- Impacted Scope:
  - GUI React renderer state
  - Workbench command palette and sidebar session selection
  - Composer local draft handling
  - Terminal controller session lookup
  - Workspace switch/reset behavior
- Related Docs:
  - `AGENTS.md`
  - `README.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/pre-release-architecture-debt-audit.md`
- ADR Needed: No
- Follow-up:
  - Continue GUI cleanup with dev-only visual fixture isolation and generated
    asset policy.
  - Continue shrinking `App.jsx` API orchestration and the T3 timeline runtime
    contract in later slices.

### DC-199

- Date: 2026-06-25
- Change Topic: Explicit extension capability contracts
- Summary:
  - Introduced `ExtensionCapability` as the internal typed registration record
    for extension hooks, event reducers/observers, workflow package manifests,
    context reducer registration, active tool names, tool registration, and
    extension-owned tool handling.
  - Changed `ExtensionManager` registration so extensions participate only
    through `extension_capabilities()`; method-name hooks are no longer
    auto-discovered compatibility paths.
  - Migrated the bundled `CHarnessWorkflowExtension`, dynamic tool test
    extensions, local resource extensions, and project-local extension examples
    to explicit capability records.
  - Exposed `api.ExtensionCapability` to project-local extension authors and
    updated generated extension skeletons so hooks must be declared explicitly.
  - Added diagnostics for invalid capability records so malformed project
    extensions fail visibly without becoming silent no-ops.
- Impacted Scope:
  - In-process extension runtime
  - Default C/C++ workflow extension
  - Project-local Python extension API
  - Dynamic tool registration
  - Local self-extension skeleton generation
- Related Docs:
  - `AGENTS.md`
  - `README.md`
  - `docs/tool-contracts.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Needed: No
- Follow-up:
  - Continue pre-release cleanup with the T3-native GUI runtime state slice.

### DC-198

- Date: 2026-06-25
- Change Topic: Agent core ownership shrink
- Summary:
  - Moved workflow-patch persistence helpers into `AgentLifecycleJournal` and
    workflow-patch capture into `AgentToolActionService`, so QueryEngine no
    longer wraps extension tool-result patching.
  - Let `AgentLoop` depend on `AgentExtensionHost` and `AgentToolActionService`
    directly for active schema projection and action execution, then deleted
    QueryEngine private forwarding wrappers for active tools and tool actions.
  - Extracted hosted `/review` synthesis into `ReviewCommandService`, leaving
    `InProcessAdapter` responsible only for collecting session evidence and
    emitting the slash-command result.
  - Updated focused tests to assert the formal host/action-service boundaries
    instead of relying on QueryEngine private compatibility methods.
- Impacted Scope:
  - Agent Core turn loop
  - Tool action execution
  - Workflow patch lifecycle
  - Hosted slash-command review synthesis
  - In-process adapter ownership
- Related Docs:
  - `AGENTS.md`
  - `docs/tool-contracts.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Needed: No
- Follow-up:
  - Continue Slice 4 by replacing method-name extension compatibility hooks
    with explicit capability contracts.

### DC-197

- Date: 2026-06-25
- Change Topic: Unified interactive action pipeline
- Summary:
  - Moved `ask_user` and `propose_mode_switch` execution into
    `AgentToolActionService`, including pending user-input creation, resume
    handling, and mode-switch observation generation.
  - Removed the QueryEngine-only interactive tool branches. Resume of pending
    user input now re-enters the same action execution path as the original
    action.
  - Reclassified parallel pre-execution skips for interactive actions as
    `interactive_serial_skip`, making serial action-service execution the
    owner instead of QueryEngine.
  - Deleted the obsolete `TurnOrchestrator` strategy module and its tests so
    `AgentLoop` remains the only turn-loop owner.
- Impacted Scope:
  - Agent Core action execution
  - Pending interaction lifecycle
  - Mode-switch proposal handling
  - Core strategy exports
- Related Docs:
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Needed: No
- Follow-up:
  - Continue Slice 3 by shrinking remaining QueryEngine/InProcessAdapter
    facade methods that only exist for old compatibility tests.

### DC-196

- Date: 2026-06-25
- Change Topic: Pre-release timeline truth removal
- Summary:
  - Deleted `SessionTimelineStore` and its persistence tests. `EventEmitter`
    now only broadcasts live events and no longer writes a second history log.
  - Moved `/review` input construction to live transcript-backed `Session`
    tool observations, and changed `/api/sessions/{id}/events` to return
    `reload_required` instead of replaying timeline tails.
  - Simplified the GUI runtime projector from `bootstrapTimeline + eventLog`
    merging to a single `historyTimeline` input. Transport event logs now
    affect connection/reload state only; live permission/user-input cards are
    created by reducer actions in current GUI display state.
  - Updated source-of-truth docs so session history remains
    `transcript.jsonl -> Session -> SessionHistoryAssembler -> /bootstrap`.
- Impacted Scope:
  - Agent Core session/runtime boundary
  - GUI session bootstrap and T3 timeline projection
  - `/review` command input construction
  - Frontend protocol documentation
- Related Docs:
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/archive/pre-release-debt-cleanup/2026-06-25-pre-release-debt-cleanup.md`
- ADR Required: No. This is a deletion-oriented pre-release cleanup slice and
  does not add a new public API, dependency, deployment model, or permission
  category.

### DC-195

- Date: 2026-06-25
- Change Topic: Pre-release architecture debt baseline
- Summary:
  - Established `docs/pre-release-architecture-debt-audit.md` as the active
    baseline for deleting or replacing transitional Agent Core and GUI layers.
  - Made explicit that the project has no production user state to preserve, so
    old internal session formats, timeline dependencies, GUI reducer shapes,
    visual fixture actions, and extension-hook compatibility layers are not
    forward-compatibility targets.
  - Kept the hard constraints unchanged: Windows 7, offline deployment, Python
    3.8, bundled runtime tools, and the default C/C++ workflow.
- Impacted Scope:
  - Architecture planning
  - Agent Core cleanup sequencing
  - GUI T3 parity sequencing
  - Documentation governance
- Related Docs:
  - `docs/pre-release-architecture-debt-audit.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- ADR Required: No. This records a pre-release cleanup policy and does not add a
  new runtime dependency, deployment model, permission category, or public API.

### DC-194

- Date: 2026-06-25
- Change Topic: Pi-aligned minimal tool architecture
- Summary:
  - Re-centered the model-visible command primitive on `bash`.
  - Removed legacy public `run_build`, compiler listing, and build-environment helper tools from public schemas, workflow packs, metadata, and docs.
  - Kept C/C++ workflow capabilities behind the default workflow extension boundary: recipes, quality reporting, failing evidence, and task status.
  - Added recipe readiness/prerequisite/refusal behavior so unconfigured projects get actionable next steps instead of repeated failed recipe execution.
  - Improved non-streaming subprocess output handling with byte capture, explicit decoding fallback, and safe metadata.
  - Added bundled Bash to the offline runtime contract.
- Impacted Scope:
  - `src/embedagent/tools/`
  - `src/embedagent/harness/`
  - `src/embedagent/workspace_recipes.py`
  - `src/embedagent/modes.py`
  - `scripts/offline-runtime-contract.json`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/mode-schema.md`
  - `docs/agent-harness-v2.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
- Related Docs:
  - `docs/archive/pi-aligned-tool-architecture/2026-06-24-pi-aligned-tool-architecture-design.md`
  - `docs/archive/pi-aligned-tool-architecture/2026-06-24-pi-aligned-tool-architecture.md`
  - `docs/archive/pi-aligned-tool-architecture/README.md`
- ADR Required: No. This is an approved implementation slice of the existing Pi-inspired Agent Core architecture program and does not add a new runtime dependency, network dependency, public marketplace, or incompatible deployment model.

### DC-193

- 日期：2026-06-22
- 变更主题：T3 GUI parity shell
- 变更摘要：
  - Copied T3 Code's GUI shell architecture shape for right-panel surfaces, floating tab menus, terminal drawer/panel ownership, and timeline row projection.
  - Kept all display state in the GUI app shell.
  - Preserved the minimal Agent Core boundary: no QueryEngine, transcript, permission, workflow package, reducer, provider, or extension-loading changes.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/`
  - `src/embedagent/frontend/gui/webapp/src/workbench/`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- 关联文档：
  - `docs/archive/t3-gui-parity-shell/2026-06-22-t3-gui-parity-shell-design.md`
  - `docs/archive/t3-gui-parity-shell/2026-06-22-t3-gui-parity-shell.md`
  - `docs/modules/frontend-gui.md`
- 是否需要 ADR：否；该变更是 GUI app-shell parity/stabilization work，不改变 Agent Core、session-history truth、permission policy、workflow package ownership、runtime reducers、provider behavior、extension loading、backend protocol semantics、offline deployment, or Windows 7 constraints.

### DC-192

- 日期：2026-06-22
- 变更主题：GUI native launcher in portable offline bundle
- 变更摘要：
  - The portable offline bundle now includes `EmbedAgent.exe` and `embedagent-gui.exe` as thin native GUI launchers.
  - The launchers set the same bundle environment as `embedagent-gui.cmd`, check bundled Python and WebView2 Fixed Version runtime, and forward to the existing Python GUI launcher.
  - The one-folder portable bundle remains the release baseline; this does not adopt PyInstaller, Nuitka, Electron, installer-first packaging, or one-file exe delivery.
- 影响范围：
  - `scripts/launcher/embedagent_gui_launcher.cpp`
  - `scripts/build-gui-launcher.ps1`
  - `scripts/package.config.json`
  - `scripts/package-lib.ps1`
  - `scripts/prepare-offline.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `scripts/check-bundle-dependencies.py`
  - `scripts/validate-gui-smoke.py`
  - `docs/adrs/0005-gui-native-launcher-in-portable-bundle.md`
- 关联文档：
  - `docs/adrs/0001-offline-portable-bundle-baseline.md`
  - `docs/adrs/0005-gui-native-launcher-in-portable-bundle.md`
  - `docs/modules/packaging-and-deployment.md`
  - `docs/guides/win7-gui-validation.md`
- 是否需要 ADR：是；native launcher exe changes the long-lived bundle entry-point strategy while preserving the portable bundle baseline.

### DC-191

- 日期：2026-06-22
- 变更主题：T3 Code-style workbench renderer UI state persistence
- 变更摘要：
  - GUI workbench now has a sanitized renderer-local UI-state store mirroring T3 Code's `uiStateStore` pattern for durable app-shell preferences.
  - The store persists right-panel open/width, bottom-drawer open/kind/height, active workbench session key, and shallow session-scoped right-panel surface descriptors plus active surface id.
  - Session activation routes through the workbench reducer so each thread restores its own right-panel surface stack without making frontend state a session-history source.
  - The persistence boundary strips command palette open/query state, file contents, preview snapshots, terminal output, tool data, backend snapshots, transcript history, workflow state, permission state, and runtime reducer state.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/webapp/test/workbench-ui-state.test.mjs`
  - `src/embedagent/frontend/gui/static/assets/app.js`
  - `src/embedagent/frontend/gui/static/assets/app.css`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：否；该变更是 GUI app-shell renderer state parity，不改变 Agent Core、backend protocol truth、session-history truth、permission engine、runtime reducers、workflow package ownership、extension loading policy 或 offline/Win7 runtime contract。

### DC-190

- 日期：2026-06-20
- 变更主题：Pi/T3 residual contract cleanup
- 变更摘要：
  - GUI smoke validation now uses the current `build` / `/api/tasks` / `task_status` contract and no longer invokes historical `mode=code`, `/api/todos`, or `manage_todos` paths.
  - Build mode prompt text no longer prescribes a fixed `lite_spec_tdd` phase track; workflow-specific prompt units remain owned by the default C/C++ workflow extension.
  - C harness workflow injection recognizes Chinese work requests such as implementation, debugging, running tests, and failure triage, while casual chat remains non-triggering.
  - Tool result cache stats and documentation now expose only implemented L1/L2 tiers, removing the unused L3 projection placeholder.
  - `AgentCoreAdapter.shutdown()` now detaches frontend callback state and performs best-effort runtime/session cleanup for GUI host shutdown and workspace switching.
  - `prepare-offline.ps1` generated configs now use `default_mode: explore` without a persistent loop ceiling; the staged workspace template is now a tiny buildable C smoke project instead of a placeholder directory.
- 影响范围：
  - `scripts/prepare-offline.ps1`
  - `scripts/validate-gui-smoke.py`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/harness/extension.py`
  - `src/embedagent/modes.py`
  - `src/embedagent/strategies/tool_cache.py`
  - `tests/test_core_adapter_shutdown.py`
  - `tests/test_gui_smoke_contract.py`
  - `tests/test_harness_mode_contract.py`
  - `tests/test_modes.py`
  - `tests/test_packaging_control_plane.py`
  - `tests/test_tool_cache.py`
- 关联文档：
  - `docs/development-tracker.md`
- 是否需要 ADR：否；该变更是既有 Pi-style core boundary 和 T3 GUI contract 的残留清理，不改变 session-history truth、permission engine、extension loading policy 或 GUI app-shell ownership。

### DC-189

- 日期：2026-06-20
- 变更主题：Compacted-history checkpoints implemented
- 变更摘要：
  - 新增 `compacted_history` transcript event projection、`CompactedHistoryReducer`、live `Session.compacted_history` checkpoint state 和 `DeterministicCompactor` payload builder。
  - `QueryEngine` 在记录 `compact_boundary` 后写入对应 compacted-history checkpoint，并通过 reducer 自校验后更新 live session state。
  - `SessionRestorer` 验证 checkpoint id、first-kept anchor 和 replacement message shape 后恢复 checkpoint；重复 checkpoint id 或缺失 anchor 在 best-effort restore 中可被跳过。
  - `ContextManager` 可从最新有效 checkpoint 的 replacement messages 加 newer transcript suffix 重建 provider history，并在 compact retry 路径继续应用 compact policy 收缩。
  - `CompactionStateReducer` 现在把 compacted-history checkpoints 作为诊断/read-model projection 暴露，但不接管权限、工具执行、扩展加载或 session-history truth。
- 影响范围：
  - `src/embedagent/compacted_history.py`
  - `src/embedagent/compactor.py`
  - `src/embedagent/compaction_state.py`
  - `src/embedagent/context.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/session.py`
  - `src/embedagent/session_restore.py`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
- 关联文档：
  - `docs/archive/pi-like-agent-core-boundary/2026-06-20-compacted-history-checkpoints.md`
  - `docs/archive/pi-like-agent-core-boundary/2026-06-20-pi-style-minimal-core-and-compaction-design.md`
- 是否需要 ADR：否；该变更实现既有 compact/recovery 方向，未改变 session-history truth、permission engine、tool contract 或 extension loading policy。

### DC-188

- 日期：2026-06-20
- 变更主题：Pi/Codex-inspired compacted-history direction documented
- 变更摘要：
  - 在 durable architecture docs 中明确下一步 compact 方向：从 diagnostic-only `compact_boundary` 走向 durable compacted-history checkpoint，记录 summary、first-kept anchor、replacement messages、trigger/phase、file activity refs 与 evidence refs。
  - 明确未来 context assembly 可从最新有效 replacement checkpoint 加 newer transcript suffix 重建 provider history，同时 `transcript.jsonl` 继续是审计日志。
  - 保留 deterministic local summary 作为离线 fallback；provider-generated 或 extension-supplied summary 只能是可替换策略，失败时必须回落，不能引入强制网络依赖。
  - 继续约束 `CompactionStateReducer` 为 transcript-backed diagnostics/replay projection，不能接管 active context selection、summary generation、replacement-history installation、extension loading、tool execution 或 permission decisions。
- 影响范围：
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
  - `docs/design-change-log.md`
  - `docs/archive/pi-like-agent-core-boundary/2026-06-20-pi-style-minimal-core-and-compaction-design.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/pi-like-agent-core-boundary/2026-06-20-pi-style-minimal-core-and-compaction-design.md`
- 是否需要 ADR：否；这是现有 Pi-inspired compact/recovery program 的下一步实现方向，不改变当前 session-history truth、permission engine、tool contract 或 extension loading policy。
- 后续动作：
  - 后续实现应先新增 compacted-history event contract 与 reducer projection，再抽取 compactor interface，最后让 context assembly 使用 replacement checkpoint 加 suffix 的恢复模型。

### DC-187

- 日期：2026-06-20
- 变更主题：Pi-style Agent Core boundary slimming for workflow tools and context reducers
- 变更摘要：
  - C/C++ workflow context reducers 从 Core `ReducerRegistry` 物理迁出，改由 `src/embedagent/harness/context_reducers.py` 通过 `CHarnessWorkflowExtension.register_context_reducers(...)` 注册。
  - bare `ToolRuntime` 不再默认注册 `list_compilers`、`configure_build_env`、`run_build`；这些 build helpers 现在随 C workflow extension 注册、metadata、pack 和 manifest 一起归属默认 C/C++ workflow package。
  - 新 prompt descriptor 使用 `WorkflowPrompt`，新系统消息保持 `kind="workflow_prompt"`；`harness_prompt` 不再作为活动 prompt assembly kind 参与注入或去重。
  - `propose_mode_switch` 不再无条件进入 provider tool schema，只有通过 active-tool boundary 显式激活时才投影。
  - `ToolCatalogEntry` 内部继续向 execution / presentation / context-policy facets 收敛，同时保持 flat catalog payload 兼容前端和协议。
  - 新增 provider request 前的最小 `ContextPlan` read model，用于记录 selected-message counts、recent/summarized turns、token/char summary、pipeline steps、preserved message ids 与 replacement refs；`CompactionStateReducer` 继续只做 transcript-backed diagnostics/replay projection。
- 影响范围：
  - `src/embedagent/context.py`
  - `src/embedagent/harness/context_reducers.py`
  - `src/embedagent/harness/extension.py`
  - `src/embedagent/harness/tool_registry.py`
  - `src/embedagent/harness/tool_metadata.py`
  - `src/embedagent/harness/packs.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/extensions.py`
  - `src/embedagent/agent_extension_host.py`
  - `tests/test_context_config.py`
  - `tests/test_tools_package.py`
  - `tests/test_workflow_extensions.py`
  - `tests/test_dynamic_tool_registration.py`
  - `docs/` source-of-truth files
- 关联文档：
  - `docs/overall-solution-architecture.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：否；这是既有 Pi-inspired minimal Core 方向下的边界瘦身，不引入公共 extension API、远程 registry、运行时依赖安装、权限引擎或新的 session-history truth。
- 后续动作：
  - 继续丰富 `ContextPlan` 的 context-window generation、file activity refs、evidence refs 和 compact summary inputs，并在真实 C/C++ 项目与 Win7 离线 bundle 上验证 build helpers 通过 workflow extension 激活后的行为。

### DC-186

- 日期：2026-06-19
- 变更主题：Pi-style Agent Core prompt/resource/runtime-state alignment
- 变更摘要：
  - 系统提示词表面收窄：mode prompt 不再列出 active tool directory，C workflow prompt units 不再暴露 pack tool lists，visible local skills 只通过一个 hosted `local_skills_prompt` listing unit 出现。
  - `RuntimeConfigReducer` 与 provider turn snapshot metadata 现在区分 `registered_tool_names` 和 `active_tool_names`，用于诊断/重放，不参与 active-tool policy。
  - `.embedagent/skills` 与 `.embedagent/prompts` 保持 file-only resources；`/skill:<name> [args]` 和 `/prompt:<name-or-path> [args]` 显式展开正文到普通 user turn，resource reload 只做索引/诊断/资源版本推进。
  - `WorkflowPackageManifest` 增加测试守住 non-executing control-plane 边界：manifest 不包含 entrypoint/enabled/autoload/dependencies/permissions 等执行或授权字段。
- 影响范围：
  - `src/embedagent/modes.py`
  - `src/embedagent/harness/runner.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/runtime_config.py`
  - `src/embedagent/prompts.py`
  - `tests/test_modes.py`
  - `tests/test_workflow_extensions.py`
  - `tests/test_query_engine_build_lite.py`
  - `tests/test_runtime_config.py`
  - `tests/test_local_resources.py`
  - `tests/test_query_engine_refactor.py`
  - `tests/test_workflow_package_manifest.py`
  - `README.md` / `AGENTS.md` / `docs/` source-of-truth files
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/tool-contracts.md`
  - `docs/overall-solution-architecture.md`
- 是否需要 ADR：否；该变更是既有 Pi-inspired minimal Agent Core blueprint 的收口切片，不引入 public extension API、remote registry、runtime dependency installation、built-in tool replacement 或新的 permission engine。
- 后续动作：
  - Continue real Win7 bundle smoke validation and real C/C++ project validation while keeping future intranet/provider/catalog/telemetry work outside Agent Core.


### DC-185

- 日期：2026-06-19
- 变更主题：GUI T3 Code-style preview runtime boundary
- 变更摘要：
  - 新增 GUI app-shell `PreviewService`，提供 local-only URL normalization、loopback HTTP probe、in-memory preview tab snapshots、refresh、close 与 open-in-system-browser actions。
  - `GUIBackend` 新增 `/api/sessions/{id}/preview*` 与 `/api/app/preview/open-external` routes；remote、non-HTTP、无端口或过长 URL 在发起网络连接前被拒绝。
  - `webapp/src/preview/preview-api.js` 与 `preview-surface-model.js` 将 backend snapshots 映射为 T3code-style `idle` / `loading` / `success` / `failed` runtime state。
  - `PreviewSurface.jsx` 现在接入 backend open/refresh/open-external，渲染 loading、unreachable、refresh/open-external enabled states，并在失败时保持在 right-panel surface 内部。
  - `scripts/gui-visual-debug.mjs` 的 `preview` scenario 现在验证 local-card flow、URL-tab replacement、runtime action enablement、failed/unreachable feedback 与 right-panel tab non-overlap。
- 影响范围：
  - `src/embedagent/frontend/gui/backend/preview_service.py`
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/webapp/src/preview/preview-api.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/preview-surface-model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/PreviewSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `tests/test_gui_backend_api.py`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `src/embedagent/frontend/gui/static/assets/`
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `reference/t3code/packages/contracts/src/preview.ts`
  - `reference/t3code/apps/web/src/previewStateStore.ts`
  - `reference/t3code/apps/web/src/components/preview/PreviewPanel.tsx`
  - `reference/t3code/apps/web/src/components/preview/PreviewUnreachable.tsx`
  - `docs/modules/frontend-gui.md`
- 是否需要 ADR：否；该变更是 GUI app-shell local preview boundary，不改变 Agent Core、session-history truth、workflow package contracts、permission policy、runtime reducers、provider configuration、telemetry、terminal execution、source-control mutation policy 或 public extension API。
- 后续动作：
  - 下一片建议做 Win7/offline embedded preview feasibility：验证 WebView2 109 或可替代本地 renderer 的打包/安装/降级策略，在不引入 Electron、runtime Node、online service 或 Agent Core coupling 的前提下替换当前 unavailable viewport。

### DC-184

- 日期：2026-06-19
- 变更主题：GUI T3 Code-style right-panel preview surface shell parity
- 变更摘要：
  - `RIGHT_PANEL_SURFACES` now exposes `preview` as the first manually addable right-panel surface, while `RIGHT_PANEL_KINDS` keeps `file` as an action-opened surface.
  - `WORKBENCH_COMMANDS` / `DEFAULT_KEYBINDINGS` now include `surface.preview`, `/preview`, and `mod+4`.
  - `PreviewSurface.jsx` renders compact T3code-style preview chrome, URL input, local-server cards, concrete URL viewport state, and embedded-preview unavailable feedback.
  - `preview-surface-model.js` owns frontend-only URL normalization, display formatting, and local-server empty-state projection.
  - `openSurface(...)` replaces the empty `right:preview` placeholder when a concrete preview URL opens, avoiding duplicate Preview tabs.
  - `scripts/gui-visual-debug.mjs` now includes a `preview` scenario that verifies the shell, local server card activation, URL tab replacement, and right-panel tab non-overlap.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/PreviewSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/preview-surface-model.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `src/embedagent/frontend/gui/static/assets/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `reference/t3code/apps/web/src/components/RightPanelTabs.tsx`
  - `reference/t3code/apps/web/src/rightPanelStore.ts`
  - `docs/modules/frontend-gui.md`
- 是否需要 ADR：否；该变更是 GUI app-shell presentation/read-model parity work，不改变 Agent Core、backend protocol、session-history truth、workflow package contracts、permission policy、runtime reducers、provider configuration、source-control mutation policy、terminal execution、telemetry 或 public extension API。
- 后续动作：
  - 继续一比一推进 T3code parity：下一片建议实现 hosted/local preview runtime boundary（仍保持 Win7/offline、可禁用、不进入 Agent Core），然后再推进 editor annotation/comment 或 source-control mutation affordance boundaries。

### DC-183

- 日期：2026-06-19
- 变更主题：GUI T3 Code-style right-panel editor/diff chrome parity
- 变更摘要：
  - `FilePreviewSurface.jsx` now uses a T3code-style `surface-subheader` with horizontally scrollable breadcrumbs, compact metadata, icon-style open/markdown/explorer actions, and the existing code/markdown content surface below it.
  - `RightPanelSurfaceBody.jsx` / `App.jsx` pass an app-shell `onOpenFilesSurface` callback so the file explorer affordance reuses the existing right-panel `FilesSurface`.
  - `DiffPanel.jsx` now uses a T3code-style subheader, diff-selection chip strip, stacked/split display controls, line-wrap and whitespace toggles, collapsible file rail, and focused scrollable viewport.
  - `scripts/gui-visual-debug.mjs` now verifies file and diff chrome states, control toggles, reveal markers, scroll containers, and right-panel tab non-overlap in the `diff,file` scenario.
  - This slice intentionally does not import T3's `@pierre/diffs` editor runtime, Electron context menus, browser preview runtime, online/editor integrations, or source-control mutation behavior.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `src/embedagent/frontend/gui/static/assets/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `reference/t3code/apps/web/src/components/files/FilePreviewPanel.tsx`
  - `reference/t3code/apps/web/src/components/DiffPanelShell.tsx`
  - `reference/t3code/apps/web/src/components/DiffPanel.tsx`
  - `reference/t3code/apps/web/src/components/RightPanelTabs.tsx`
  - `docs/archive/t3code-pi-workbench/2026-06-19-t3-right-panel-editor-diff-chrome-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-19-t3-right-panel-editor-diff-chrome.md`
- 是否需要 ADR：否；该变更是 GUI app-shell presentation/read-model parity work，不改变 Agent Core、backend protocol、session-history truth、workflow package contracts、permission policy、runtime reducers、provider configuration、source-control mutation policy、terminal execution、telemetry 或 public extension API。
- 后续动作：
  - 继续一比一推进 T3code parity：source-control/branch mutation affordance boundaries、right-panel browser/preview shell、以及更深的 file editor 行为需要继续按 Win7/offline/hosted-extension 边界拆片。

### DC-182

- 日期：2026-06-19
- 变更主题：GUI T3 Code-style timeline file-link activation parity
- 变更摘要：
  - `Timeline.jsx` now treats workspace-relative markdown links as T3code-style file preview links and calls the existing GUI `openFile(path, line)` callback; remote URLs and hash-only anchors remain ordinary markdown links.
  - `TimelineRows.jsx` / `WorkRow.jsx` now thread `onOpenFile` through work groups, turn folds, structured command/review rows, and `ToolDetail.jsx`.
  - `ToolDetail.jsx` renders grep match rows, file rows, and changed-file rows as quiet file-link buttons when a path is present; review findings can also open the target file/line.
  - `t3-timeline.js` preserves numeric match `line` values plus display labels, so reveal requests do not depend on parsing rendered text.
  - `scripts/gui-visual-debug.mjs` now creates a real `src/parser.c` fixture, clicks a timeline file link, and asserts the right-panel file preview receives the T3 reveal marker pair on line 4.
  - 该变更只影响 GUI-local projection / presentation / visual debug harness / 文档；file-link activation still uses existing GUI file preview loading and does not add backend protocol fields.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `reference/t3code/apps/web/src/components/ChatMarkdown.tsx`
  - `reference/t3code/apps/web/src/rightPanelStore.ts`
  - `reference/t3code/apps/web/src/components/files/FilePreviewPanel.tsx`
  - `docs/archive/t3code-pi-workbench/2026-06-19-t3-timeline-file-link-activation.md`
- 是否需要 ADR：否；该变更是 GUI app-shell presentation/read-model parity work，不改变 Agent Core、backend protocol、session-history truth、workflow package contracts、permission policy、runtime reducers、provider configuration、source-control mutation policy、terminal execution、telemetry 或 public extension API。
- 后续动作：
  - 继续一比一推进 T3code parity：深化 editor/diff chrome，并梳理 source-control / branch mutation affordance 在 offline/Win7 约束下的 hosted-extension 边界。

### DC-181

- 日期：2026-06-19
- 变更主题：GUI T3 Code-style file preview chrome parity
- 变更摘要：
  - 新增 frontend-only 纯模块 `webapp/src/session-runtime/file-preview-model.js`，提供 `fileBreadcrumbs`、`isMarkdownPreviewFile`、`defaultFilePreviewMode`、`fileLanguageForPath`、`numberFileLines` 与 `filePreviewMeta`；breadcrumb 与 markdown-mode helper 一比一移植自 `reference/t3code/apps/web/src/components/files/filePath.ts` 与 `filePreviewMode.ts`。
  - `FilePreviewSurface.jsx` 现在渲染 T3code-style file viewer：project/dir/file 面包屑、language + 行数 metadata、带行号的 code gutter，以及对 `.md`/`.mdx` 默认进入 rendered preview 的 code/markdown 模式切换。
  - file-link reveal 请求现在复用 T3code 的 clamp/highlight 语义：`fileRevealLine(...)` 将目标行限制到已加载文件范围内，code view 同时给 gutter 行和内容行标记 `data-file-link-reveal`，并在 reveal request 变化时把目标行滚入视图。
  - active workspace label 经 `App.jsx` -> `RightPanelSurfaceBody` -> `FilePreviewSurface` 仅作为面包屑 project name 传入，不新增 backend 字段。
  - `scripts/gui-visual-debug.mjs` 的 `file` scenario 现在断言面包屑、markdown preview、模式切换、行号 gutter、reveal marker pair 与目标行可见性。
  - 该变更只影响 GUI-local projection / presentation / visual debug harness / 文档；T3 的文件编辑、save coordinator、comment annotation 与 `@pierre/diffs` editor 刻意不在范围内。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/file-preview-model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `reference/t3code/apps/web/src/components/files/FilePreviewPanel.tsx`
  - `reference/t3code/apps/web/src/components/files/filePath.ts`
  - `reference/t3code/apps/web/src/components/files/filePreviewMode.ts`
- 是否需要 ADR：否；该变更是 GUI app-shell presentation/read-model parity work，不改变 Agent Core、backend protocol、session-history truth、workflow package contracts、permission policy、runtime reducers、provider configuration、source-control mutation policy 或 public extension API。
- 后续动作：
  - 继续一比一推进 T3code parity：在 hosted/offline 约束下深化 editor/diff chrome，以及 source-control / branch mutation 边界。

### DC-180

- 日期：2026-06-18
- 变更主题：GUI T3 command palette root/submenu parity
- 变更摘要：
  - `command-palette-model.js` now projects visible workbench commands, recent sessions, workspaces, and keybindings into T3code-style grouped palette rows.
  - `CommandPalette.jsx` now owns GUI-local root/submenu view state, highlight state, keyboard navigation, and descriptor activation while rendering through `CommandPaletteResults.jsx`.
  - Command rows still route through existing workbench command IDs; session and workspace rows route through existing `App.jsx` callbacks (`loadSession` and `activateWorkspace`).
  - `scripts/gui-visual-debug.mjs` now includes a `palette` scenario covering root groups, session/workspace rows, submenu search, keyboard Enter execution, and narrow viewport guardrails.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPaletteResults.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `reference/t3code/apps/web/src/components/CommandPalette.tsx`
  - `reference/t3code/apps/web/src/components/CommandPaletteResults.tsx`
  - `reference/t3code/apps/web/src/components/CommandPalette.logic.ts`
  - `reference/t3code/apps/web/src/components/ui/command.tsx`
  - `reference/t3code/apps/web/src/keybindings.ts`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-command-palette-root-submenu-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-command-palette-root-submenu.md`
- 是否需要 ADR：否；该变更是 GUI app-shell presentation/read-model parity work，不改变 Agent Core、backend protocol、session-history truth、workflow package contracts、permission policy、runtime reducers、provider configuration、source-control mutation policy 或 public extension API。
- 后续动作：
  - Continue one-to-one T3code parity with branch/environment mutation boundaries, source-control mutation affordances, and file/editor chrome after validating hosted/offline constraints.

### DC-179

- 日期：2026-06-18
- 变更主题：GUI T3 composer command menu and context tokens
- 变更摘要：
  - `Composer.jsx` now owns trigger detection, menu highlight state, keyboard selection, and text insertion for T3code-style slash and `@` context flows.
  - Frontend-only composer helpers now provide trigger parsing, ranked slash-command search, and loaded-file path context projection from GUI file-tree state.
  - `ComposerCommandMenu.jsx` renders the grouped floating menu, and `ComposerPrimaryActions.jsx` renders compact send/stop controls while preserving the existing send/stop callbacks.
  - Visual debug fixtures and `scripts/gui-visual-debug.mjs` now assert slash command insertion, `@src/parser.c` insertion, active menu item state, and no horizontal overflow across desktop and narrow viewports.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/composer/`
  - `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerCommandMenu.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPrimaryActions.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `reference/t3code/apps/web/src/components/chat/ChatComposer.tsx`
  - `reference/t3code/apps/web/src/components/chat/ComposerCommandMenu.tsx`
  - `reference/t3code/apps/web/src/components/chat/composerSlashCommandSearch.ts`
  - `reference/t3code/apps/web/src/components/chat/ComposerPrimaryActions.tsx`
  - `reference/t3code/packages/shared/src/composerTrigger.ts`
  - `reference/t3code/packages/client-runtime/src/composerPathSearchState.ts`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-composer-command-menu-context-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-composer-command-menu-context.md`
- 是否需要 ADR：否；该变更是 GUI app-shell presentation/read-model parity work，不改变 Agent Core、backend protocol、session-history truth、workflow package contracts、permission policy、runtime reducers、provider configuration、source-control mutation policy 或 public extension API。
- 后续动作：
  - Continue one-to-one T3code parity for command palette depth, branch/worktree selectors behind explicit hosted boundaries, source-control mutation affordances, and file/editor chrome.

### DC-178

- 日期：2026-06-18
- 变更主题：GUI T3 branch toolbar run context
- 变更摘要：
  - React webapp now derives a `BranchToolbar` read model from active workspace and source-control state, mirroring T3code's branch/run-context strip under the composer.
  - `BranchToolbar.jsx` renders mode/workspace context, branch or detached/no-repo state, provider label, and change/conflict count while keeping Worktree/Branch mutation affordances disabled in the current read-only GUI shell.
  - `App.jsx` wires the toolbar through `Composer.jsx` using existing source-control refresh behavior; the component does not fetch, write transcript history, or own backend policy.
  - Visual debug fixtures and `scripts/gui-visual-debug.mjs` now assert a deterministic `feature/t3-toolbar` / `4 changes` toolbar state in chat and responsive scenarios.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/source-control/branch-toolbar-model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/BranchToolbar.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `reference/t3code/apps/web/src/components/BranchToolbar.tsx`
  - `reference/t3code/apps/web/src/components/BranchToolbarActions.tsx`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-branch-toolbar-run-context-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-branch-toolbar-run-context.md`
- 是否需要 ADR：否；该变更是 GUI app-shell presentation/read-model parity work，不改变 Agent Core、backend protocol、session-history truth、workflow package contracts、permission policy、runtime reducers、provider configuration、source-control mutation policy 或 public extension API。
- 后续动作：
  - Continue one-to-one T3code parity for command routing, branch/worktree action surfacing behind explicit hosted boundaries, and file/editor chrome while preserving the small Agent Core boundary.

### DC-177

- 日期：2026-06-18
- 变更主题：GUI T3 timeline parity shell
- 变更摘要：
  - `TimelineRows.jsx` now mirrors T3code's work-log grouping shape: consecutive work rows are owned by a local `WorkGroupSection`, collapsed groups show one latest entry, and the overflow control expands older tool calls while preserving the nearest scroll container position.
  - Running timeline display now uses T3code-style pulsing dots and a self-updating `WorkingTimer` label when GUI-local timestamps exist.
  - GUI timeline/right-panel CSS now keeps stable scrollbars visible, removes fixed `360px` narrow-layout pressure, and lets right-panel surface tabs/source-control actions shrink or wrap instead of overflowing.
  - GUI socket/reducer display actions carry frontend-local `createdAt` / `completedAt` fields so fold labels can render `Worked for ...`; these fields are not transcript history, backend protocol truth, workflow policy, permission policy, or Agent Core state.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `reference/t3code/apps/web/src/components/chat/MessagesTimeline.tsx`
  - `reference/t3code/apps/web/src/components/chat/MessagesTimeline.logic.ts`
- 是否需要 ADR：否；该变更是 GUI app-shell presentation/read-model parity work，不改变 Agent Core、backend session-history truth、workflow package contracts、permission policy、runtime reducers、provider configuration 或 public extension API。
- 后续动作：
  - Continue one-to-one T3code parity on command routing, right-panel file/editor chrome, source-control action surfacing, and deeper visual QA while preserving the small Agent Core boundary.

### DC-176

- 日期：2026-06-18
- 变更主题：Pi-style agent loop continuation
- 变更摘要：
  - `AgentLoop` now runs as an open continuation loop instead of the previous fixed-count loop.
  - The default hosted path no longer synthesizes an eight-cycle safety value; omitted `max_turns` means no fixed turn-count cutoff.
  - Explicit positive `max_turns` values remain supported as a loop safety fuse and continue to emit compatibility `max_turns` transitions with `loop_safety_limit` metadata.
  - `AgentLoopContinuationPolicy` is an internal Agent Core boundary, not a public extension API.
- 影响范围：
  - `src/embedagent/agent_loop.py`
  - `src/embedagent/agent_loop_continuation.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/frontend/tui/`
  - `src/embedagent/frontend/gui/`
  - `docs/`
- 关联文档：
  - `docs/archive/pi-like-agent-core-boundary/2026-06-18-pi-style-agent-loop-continuation-design.md`
  - `docs/archive/pi-like-agent-core-boundary/2026-06-18-pi-style-agent-loop-continuation.md`
- 是否需要 ADR：否；该变更实现既有 Pi-inspired blueprint 的小切片，不引入公共 extension API。
- 后续动作：
  - Continue real Win7 bundle smoke validation and real C/C++ project validation with the new continuation behavior.

### DC-175

- 日期：2026-06-18
- 变更主题：GUI T3 workbench IA and timeline tool details
- 变更摘要：
  - React webapp left sidebar no longer renders a Files tab or file tree; workspace/thread navigation remains the sidebar's only responsibility.
  - Right-panel `FilesSurface` is now the single file browsing surface and owns an explicit scroll container for long trees.
  - T3 timeline work rows now project `detailModel` data in `t3-timeline.js`, and `ToolDetail.jsx` renders structured tool-aware fields and sections instead of raw JSON fallback for normal tool data.
  - Visual harness assertions now cover timeline/file/thread scroll containers, right-panel-only file tree ownership, and no raw JSON in expanded tool details.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-workbench-ia-tool-details-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-workbench-ia-tool-details.md`
- 是否需要 ADR：否；该变更是 GUI app-shell display/read-model refinement，不是 backend protocol、session-history truth、workflow policy、permission policy 或 Agent Core extension API。
- 后续动作：
  - Continue T3 parity slices for command routing, source-control action surfacing, file editor layout polish, and deeper responsive workbench behavior while keeping Agent Core small and separate.

### DC-174

- 日期：2026-06-18
- 变更主题：GUI terminal runtime controller boundary
- 变更摘要：
  - React webapp 新增 `webapp/src/app-runtime/terminal-controller.js`，集中管理 GUI terminal action orchestration，包括 bottom drawer terminal open/send/clear/restart/close 和 right-panel terminal open/split/activate/close。
  - `App.jsx` 通过注入 state reader、dispatch 和 terminal API helpers 来装配 controller；terminal id generation 和 bottom drawer terminal open/select actions 归入 controller，不再承载大段 inline terminal action cluster。
  - Terminal HTTP route helpers 仍位于 `webapp/src/terminal/terminal-api.js`，terminal snapshot/event normalization 仍位于 `webapp/src/terminal/terminal-state.js`。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js`
  - `src/embedagent/frontend/gui/webapp/src/terminal/terminal-state.js`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/gui-app-runtime-boundary/2026-06-18-gui-terminal-runtime-controller-boundary-design.md`
  - `docs/archive/gui-app-runtime-boundary/2026-06-18-gui-terminal-runtime-controller-boundary.md`
- 是否需要 ADR：否；该 controller 是 GUI app-shell implementation detail，不是 backend protocol、terminal execution owner、session-history truth 或 Agent Core extension API。
- 后续动作：
  - 可继续按相同模式规划 command router、source-control action controller 或 file preview controller 切片，让 `App.jsx` 进一步收敛为 composition shell。

### DC-173

- 日期：2026-06-18
- 变更主题：GUI session/app loader runtime boundary
- 变更摘要：
  - React webapp 新增 `webapp/src/app-runtime/session-loaders.js`，集中管理 GUI-private loader request vocabulary、防御性 loader request executor 与 session bootstrap projection helper。
  - `socket-message-effects.js` 改为共享 `session-loaders.js` 的 loader vocabulary，避免 socket effect derivation 和 loader execution 维护两份私有请求名。
  - `App.jsx` 继续拥有实际 HTTP route calls、reducer dispatch、event-log reset、terminal summary loading、task/artifact refreshes 和 render composition，但不再承载 loader request switch 或 session bootstrap projection 细节。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js`
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/gui-app-runtime-boundary/2026-06-18-gui-session-app-loader-runtime-boundary-design.md`
  - `docs/archive/gui-app-runtime-boundary/2026-06-18-gui-session-app-loader-runtime-boundary.md`
- 是否需要 ADR：否；该边界是 GUI app-shell implementation detail，不是 backend protocol、session-history truth 或 Agent Core extension API。
- 后续动作：
  - 可在后续切片继续把 command routing、terminal action helpers、source-control action helpers 或 file preview loading 从 `App.jsx` 抽到更小 controller/hook 中。

### DC-172

- 日期：2026-06-18
- 变更主题：GUI app-runtime boundary for socket effects and visual fixtures
- 变更摘要：
  - React webapp 新增 `webapp/src/app-runtime/socket-message-effects.js`，把现有 WebSocket message 转换成私有 GUI descriptors：reducer actions、session event-log entries 和 loader requests。
  - `App.jsx` 继续执行现有 HTTP loader、session event-log append 和 reducer dispatch，但不再承载完整 socket message 分支解释。
  - React webapp 新增 `webapp/src/app-runtime/visual-debug-fixtures.js`，集中管理 `?visual_debug=1` 下的 timeline、interaction 和 thread lifecycle fixtures。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/gui-app-runtime-boundary/2026-06-18-gui-app-runtime-controller-boundary-design.md`
  - `docs/archive/gui-app-runtime-boundary/2026-06-18-gui-app-runtime-controller-boundary.md`
- 是否需要 ADR：否；该边界是 GUI app-shell implementation detail，不是 backend protocol、session-history truth 或 Agent Core extension API。
- 后续动作：
  - 可在后续切片继续把 app/session/bootstrap loaders 和 command routing 从 `App.jsx` 抽到更小 controller/hook 中。

### DC-171

- 日期：2026-06-18
- 变更主题：GUI T3 Code-style rich timeline projection
- 变更摘要：
  - React webapp 的 T3 timeline row projection 现在覆盖 thinking、reasoning、compact、command result、review result、tool/work、diff summary、interaction 和 system notice。
  - live thinking/reasoning display 由 GUI reducer state 传入 `projectSessionRuntime(...)`，不新增 backend/Core 协议。
  - `TimelineRows.jsx` 成为 active T3 row renderer 的富格式入口，legacy grouped renderer 不再是 reasoning/compact/command/review 的唯一显示路径。
  - 该变更只影响 GUI-local projection、presentation、visual debug harness 和文档，不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、source-control checkpoints 或 Agent Core policy。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-timeline-rich-projection-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-timeline-rich-projection.md`
- 是否需要 ADR：否；属于已批准的 GUI/T3 Code parity program 内部 timeline rendering slice，不改变 Agent Core public architecture。
- 后续动作：
  - 继续拆分 `App.jsx` 的 session runtime bridge、visual debug hooks、workbench shell composition，让 GUI 架构继续靠近 T3 Code 的 frontend-owned domain model，同时保持 Agent Core 小核心。

### DC-170

- 日期：2026-06-17
- 变更主题：GUI T3 Code-style right-panel terminal group surfaces
- 变更摘要：
  - React webapp right panel 的 `terminal` surface 现在复制 T3 Code terminal surface model，保存 `terminalIds`、`activeTerminalId` 和可选 `splitDirection`。
  - right-panel terminal body 渲染 surface-scoped terminal panes，并支持 new、split horizontal、split vertical、activate、clear、restart 和 close pane。
  - bottom drawer terminal 与 right-panel terminal 共用现有 GUI terminal backend/runtime state，但 UI surface state 分离，打开 right-panel terminal 不再顺手打开 bottom drawer。
  - 该变更只影响 GUI-local state、presentation、visual debug harness 和既有 terminal backend route 消费路径，不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、source-control checkpoints 或 Agent Core policy。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTerminalSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/archive/t3code-pi-workbench/2026-06-17-t3-right-panel-terminal-group-surface-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-17-t3-right-panel-terminal-group-surface.md`
- 是否需要 ADR：否；属于已批准的 GUI standalone app-shell / T3 Code parity program 内部 surface parity 切片，不改变 Agent Core public architecture。
- 后续动作：
  - 继续按 `reference/t3code` 规划 browser preview、deeper file/editor parity 或 source-control checkpoint/diff 后续 slices，每项继续保持 Win7/offline 和 GUI/Core separation 约束。

### DC-169

- 日期：2026-06-17
- 变更主题：GUI T3 Code-style right-panel file surfaces
- 变更摘要：
  - React webapp right panel 新增 T3 Code-style `file` surface，workspace 文件动作会打开/复用路径对应的右侧 file tab，而不是继续写入旧 Inspector preview。
  - `file` 被纳入 right-panel allowed surface kinds，但保持在 generic add-surface menu 之外；文件 tab 由文件树/文件动作创建，`diff`、`files`、`terminal`、`plan` 仍是手动可添加 surface。
  - `workbench/surfaces.js` 只保存 file surface 的 path/resource/reveal metadata，文件内容由 GUI-local `filePreviewsByPath` 管理，`FilePreviewSurface` 渲染 loading/error/content 状态。
  - 该变更只影响 GUI-local state、presentation、visual debug harness 和既有 `/api/files/{path}` 消费路径，不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、source-control checkpoints 或 Agent Core policy。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/app-workspaces.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/archive/t3code-pi-workbench/2026-06-17-t3-right-panel-file-surface-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-17-t3-right-panel-file-surface.md`
- 是否需要 ADR：否；属于已批准的 GUI standalone app-shell / T3 Code parity program 内部 surface parity 切片，不改变 Agent Core public architecture。
- 后续动作：
  - 继续按 `reference/t3code` 规划 terminal grouping/split、browser preview 或 checkpoint diff 等后续 surface slices，每项继续保持 Win7/offline 和 GUI/Core separation 约束。

### DC-168

- 日期：2026-06-17
- 变更主题：T3 Code-like right-panel surface tabs
- 变更摘要：
  - React webapp right panel 从固定 Inspector tab 列表切到 T3 Code-like ordered surface descriptors，首批 surface 为 `diff`、`files`、`terminal`、`plan`。
  - `RightPanelTabs` 采用 surface tabbar、add-surface menu、empty-state cards、active tab scroll 和 close/close others/close right/close all 操作；`RightPanelSurfaceBody` 负责把 Diff/Plan 复用 Inspector 内容，把 Files/Terminal 挂到 GUI-local app-shell hosted surfaces。
  - Command palette 与 keybindings 对齐该 surface shell：`surface.files`、`surface.terminal`、`surface.diff`、`surface.plan` 与 `mod+1/mod+2/mod+3` 分别打开 files/terminal/diff。
  - 该变更只影响 GUI-local state、presentation 和 command routing，不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、checkpoint/source-control mutation 或 Agent Core policy。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/archive/t3code-pi-workbench/2026-06-17-t3-right-panel-surface-tabs-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-17-t3-right-panel-surface-tabs.md`
- 是否需要 ADR：否；属于已批准的 GUI standalone app-shell / T3 Code parity program 内部 UI shell 收敛，不改变 Agent Core public architecture。
- 后续动作：
  - 继续按 `reference/t3code` 逐步补齐 browser/file preview/terminal grouping/checkpoint diff 等 surface，但每项必须保持 Win7/offline 和 GUI/Core separation 约束。

### DC-167

- 日期：2026-06-17
- 变更主题：GUI source-control foundation as read-only app-shell surface
- 变更摘要：
  - GUI backend 新增 `SourceControlService` 和 `/api/app/source-control/*` routes，通过 bundled/workspace MinGit 提供 active-workspace-bound local status、refresh 和 staged/unstaged diff 读模型。
  - app-shell capabilities 新增 `source_control` 限制元数据，并把 `source_control` 暴露为 right-panel surface；当前明确为 read-only、local-only、offline-friendly，不含 remote providers、network、checkpoints。
  - React webapp 新增 `webapp/src/source-control/` model/API/presentation helpers 与 `SourceControlPanel`，显示 grouped changed files、数量徽标和 refresh，并复用既有 Diff right-panel 打开文件 diff。
  - 该边界保持 T3 Code-like independent app 与 Agent Core 分离：不写 transcript、workflow state、telemetry、permission/runtime reducers、provider config、extension loading 或 checkpoint truth，也不实现 push/pull/stage/commit。
- 影响范围：
  - `src/embedagent/frontend/gui/backend/source_control_service.py`
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/backend/app_shell.py`
  - `src/embedagent/frontend/gui/webapp/src/source-control/`
  - `src/embedagent/frontend/gui/webapp/src/components/source-control/`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `tests/test_gui_source_control_service.py`
  - `tests/test_gui_source_control_api.py`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/archive/gui-source-control-foundation/`
- 是否需要 ADR：暂不需要；该切片实现既有 GUI app-shell 边界内的 hosted read-only surface，不改变 Agent Core 架构、公开 extension API 或 permission policy。
- 后续动作：
  - 在真实 Win7/WebView2 109 离线 bundle 上补 GUI Source Control smoke validation。
  - 若后续实现 stage/commit/checkpoint/remote/intranet Git，必须作为新的显式 hosted boundary，并通过 normal permission categories 与 disable/fallback 设计进入。

### DC-166

- 日期：2026-06-17
- 变更主题：GUI terminal bottom drawer as app-shell hosted surface
- 变更摘要：
  - GUI backend 新增 `TerminalService` 和 `/api/sessions/{id}/terminals*` routes，使用 workspace-bound Python stdlib subprocess pipes 提供 thread-scoped terminal open/list/snapshot/write/clear/restart/resize/close 能力。
  - GUI WebSocket 新增 `terminal_event` 推送，React webapp 新增 `webapp/src/terminal/` reducer/API helpers，并把 Terminal 接入 bottom drawer tabs、toolbar、buffer 和输入行。
  - app-shell capabilities 新增 `surfaces.bottom_drawer` 与 `terminal` 限制元数据，明确当前能力不是 full PTY，`resize`/persistent history 仅作为 limitation metadata 暴露。
  - 该边界保持 T3 Code-like independent app 与 Agent Core 分离：terminal 输出是 GUI-local display state，不进入 transcript、workflow state、telemetry、permission/runtime reducers、extension loading、provider config、source-control checkpoints 或 Agent Core policy。
- 影响范围：
  - `src/embedagent/frontend/gui/backend/terminal_service.py`
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/backend/app_shell.py`
  - `src/embedagent/frontend/gui/webapp/src/terminal/`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `tests/test_gui_terminal_service.py`
  - `tests/test_gui_terminal_api.py`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/archive/gui-terminal-bottom-drawer/`
- 是否需要 ADR：暂不需要；该切片实现既有 GUI app-shell 边界内的 hosted surface，不改变 Agent Core 架构。
- 后续动作：
  - 在真实 Win7/WebView2 109 离线 bundle 上补 smoke validation。
  - 继续规划 source-control mutation/checkpoint GUI surfaces，保持它们在 app-shell/hosted extension 边界外接入，不加厚 Agent Core。

### DC-165

- 日期：2026-06-17
- 变更主题：GUI thread lifecycle boundary through session facade
- 变更摘要：
  - `SessionSummaryStore` 与 session projection 增加 thread metadata：`title`、`archived`、`archived_at`、`forked_from`、`forked_at`；默认 thread list 隐藏 archived sessions，但 cleanup 和 stored artifact reference collection 保留 archived session 资产。
  - `SessionLifecycleManager` / `InProcessAdapter` 暴露 `rename_session`、`archive_session`、`fork_session` facade；fork 复制 transcript 到新 session id 并重写同源 session_id payload 字段，仍让 `transcript.jsonl` 保持唯一 durable history truth。
  - GUI backend 新增 `POST /api/sessions/{id}/rename`、`/archive`、`/fork`，app-shell capabilities 暴露 `thread_lifecycle`；React thread action rail 调用 backend lifecycle API 并刷新 session list/current session。
  - 该边界保持 T3code-like independent app 与 Agent Core 分离：GUI 不拥有 transcript、workflow/task truth、permission policy、tool activation、extension loading、provider config、source-control 或 checkpoint policy。
- 影响范围：
  - `src/embedagent/projection_db.py`
  - `src/embedagent/session_store.py`
  - `src/embedagent/services/session_lifecycle.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/frontend/gui/backend/app_shell.py`
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js`
  - `tests/test_session_store.py`
  - `tests/test_services.py`
  - `tests/test_characterization.py`
  - `tests/test_gui_backend_api.py`
  - `tests/test_gui_app_shell.py`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/archive/gui-thread-lifecycle-boundary/`
- 是否需要 ADR：否；属于 GUI standalone shell program 的第二层 session lifecycle facade 实现，未改变 Agent Core durable truth 或 public extension API。
- 后续动作：
  - 继续把 terminal、source-control 与 checkpoint slices 放在 GUI hosted boundary 或显式 extension/provider/workflow-package/sink 边界外侧，避免把 Agent Core 加厚为 GUI-owned app policy layer。

### DC-164

- 日期：2026-06-17
- 变更主题：GUI app-shell boundary for standalone app state
- 变更摘要：
  - GUI backend 新增 `AppShellService`，将 `/api/app/bootstrap` 与 `/api/app/workspaces*` 收敛为 GUI-owned app-shell envelope，包含 workspace registry projection、active workspace metadata、safe host/runtime/renderer diagnostics、app command metadata、app surfaces 和 local shell settings。
  - React webapp 新增 `webapp/src/app-shell/` pure model/reducer/diagnostics helpers，现有 app bootstrap / workspace switch actions 通过 app-shell reducer 归一化；root workspace reset 仍负责清空 session/timeline/task/artifact 等 workspace-scoped GUI state。
  - Workbench commands 新增 `app.settings`、`app.diagnostics`、`app.reload` 与 `app` group，right panel 新增 Settings / Diagnostics surfaces。
  - 该边界保持 T3code-like standalone app shell 与 Agent Core 分离；它不拥有 session history、workflow truth、tool activation、permission policy、extension loading、provider configuration 或 runtime reducers。
- 影响范围：
  - `src/embedagent/frontend/gui/backend/app_shell.py`
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/launcher.py`
  - `src/embedagent/frontend/gui/webapp/src/app-shell/`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - `src/embedagent/frontend/gui/webapp/src/workbench/`
  - `tests/test_gui_app_shell.py`
  - `tests/test_gui_app_host.py`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/frontend-protocol.md`
  - `docs/overall-solution-architecture.md`
  - `docs/modules/frontend-gui.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：否；这是既定 T3code/Pi GUI shell 方向下的一层边界实现，未改变 Agent Core ownership 或公开扩展 API。
- 后续动作：
  - 后续 terminal/source-control/checkpoint slices 继续放在 GUI hosted boundary 或显式 extension/provider/workflow-package boundary 外侧，不把 Agent Core 加厚为 GUI-owned app policy layer。

### DC-163

- 日期：2026-06-17
- 变更主题：Documentation archive closeout and active docs index maintenance
- 变更摘要：
  - 已将完成切片材料从 `docs/superpowers/` 移入对应 `docs/archive/<topic>/`，覆盖 documentation governance baseline、workflow extension boundary follow-up、Pi-inspired minimal Core Phase A/B、enterprise boundary foundation、local skills / remaining Pi architecture gap materials 和 GUI IDE redesign 旧设计。
  - 已将历史阶段说明 `agent-state-machine.md` 与 `architecture-refactor.md` 从活动 docs 根目录迁入 `docs/archive/agent-core-refactor-history/`，避免历史 refactor 记录继续停留在当前 source-of-truth 入口。
  - 新增 `docs/archive/README.md`，并补齐新建或扩充主题包 README，使 archive 有明确索引和当前 source-of-truth 指向。
  - 更新 `docs/README.md`、documentation governance/workflow/reference 文档，明确活动 `docs/superpowers/` 当前只保留两个 GUI 进行中切片，并把完成 plan/spec 留在活动区列为禁止状态。
- 影响范围：
  - `docs/README.md`
  - `docs/documentation-governance.md`
  - `docs/documentation-style-guide.md`
  - `docs/workflows/`
  - `docs/references/`
  - `docs/archive/`
  - `docs/superpowers/`
- 关联文档：
  - `docs/archive/README.md`
  - `docs/workflows/code-doc-sync.md`
  - `docs/workflows/release-doc-checklist.md`
  - `docs/references/glossary.md`
- 是否需要 ADR：否；这是文档治理和历史材料归档收口，不改变产品架构、协议或运行时边界。
- 后续动作：
  - GUI standalone workspace/thread app 与 GUI timeline interaction polish 收口后，按同一规则先回写长期文档，再移入对应 archive 包。

### DC-162

- 日期：2026-06-17
- 变更主题：Pre-provider auto compact and compact-boundary diagnostics
- 变更摘要：
  - `ContextManager` now supports a conservative `auto_compact_threshold_ratio` setting. When a normal context assembly is near the input budget and older turns can be summarized, it rebuilds once with the internal compact policy before the provider call.
  - The auto compact path is represented as the `auto_compact_threshold` context pipeline step. Reactive provider-error retry continues to use `reactive_compact_retry`.
  - `QueryEngine` now writes compact-boundary `trigger`, `phase`, and `context_window_generation` diagnostics into both the transcript payload and boundary metadata; `CompactionStateReducer` projects those fields as read-model state.
  - `ContextWindowState` centralizes those diagnostic derivation rules as an internal value object; it is not a new durable history source or policy engine.
  - `QueryEngine` no longer constructs the legacy `ContextCompactionEngine`; wrapper-level compaction has been removed from `LLMClientRetryWrapper`, so provider context-length recovery is owned by the AgentLoop/ContextManager compaction path.
  - `SessionRestorer` preserves those diagnostics when replaying compact boundaries.
- 影响范围：
  - `src/embedagent/context.py`
  - `src/embedagent/config.py`
  - `src/embedagent/context_window.py`
  - `src/embedagent/agent_loop.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/compaction_state.py`
  - `src/embedagent/session_restore.py`
  - `tests/test_context_config.py`
  - `tests/test_context_window_state.py`
  - `tests/test_compaction_state.py`
  - `tests/test_query_engine_refactor.py`
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/frontend-protocol.md`
- 是否需要 ADR：否；这是既有 context/compaction 边界内的 deterministic policy refinement，没有新增公共 extension API 或新的 session-history truth。
- 后续动作：
  - Observe real C/C++ long-session traces and tune the default threshold only with evidence.
  - If future slices add richer context-window state, keep it reducer-backed diagnostics unless a separate policy slice explicitly moves ownership.

### DC-161

- 日期：2026-06-16
- 变更主题：GUI thread lifecycle surface and visual fixture
- 变更摘要：
  - Extended frontend-local `app-home-model` with explicit thread lifecycle action descriptors for `Rename`, `Fork`, and `Archive`.
  - Sidebar thread rows now render a T3code-like action rail without nesting secondary action buttons inside the primary open-thread button.
  - Action enablement is gated by explicit lifecycle capabilities; because the backend/Core contract does not yet expose persistent thread rename/fork/archive APIs, actions default to disabled instead of creating frontend-owned session metadata.
  - `scripts/gui-visual-debug.mjs` gained a `thread` scenario and a `loadThreadLifecycleFixture()` visual-debug hook to validate real rendered thread rows, action counts, disabled state, sidebar bounds, screenshots, and console cleanliness.
  - 本次继续保持 T3code-style shell 借鉴与 Pi-style Core decoupling：没有复制 T3code 源码，没有新增 Agent Core、permission policy、workflow package、session history truth 或 Win7/offline runtime 依赖。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- 关联文档：
  - `docs/modules/frontend-gui.md`
- 是否需要 ADR：否；这是 GUI shell display/read-model refinement and dev visual harness expansion，不改变长期架构边界。
- 后续动作：
  - Add backend/Core lifecycle API slices for persistent rename/fork/archive before enabling these controls.
  - Keep `npm run visual:gui -- --scenario app,thread` as the focused regression for app-level thread management.

### DC-160

- 日期：2026-06-16
- 变更主题：GUI app-level workspace/thread management polish
- 变更摘要：
  - Added frontend-local `app-home-model` to project app bootstrap workspace records and session summaries into Sidebar and NoWorkspaceState display state.
  - The GUI sidebar now presents a T3code-like project manager plus thread manager without making the frontend own workspace registry persistence, session truth, workflow policy, or Core lifecycle.
  - Project recents are locally scroll-bounded so accumulated recent projects cannot push the Threads manager out of view.
  - `scripts/gui-visual-debug.mjs` now launches with isolated `EMBEDAGENT_GUI_APP_HOME=<output>/app-home`, so app/workspace visual scenarios exercise the real backend registry path without polluting the developer machine's normal recent-project list.
  - 本次继续保持 T3code-style shell 借鉴与 Pi-style Core decoupling：没有复制 T3code 源码，没有新增 Agent Core、permission policy、workflow package、session history truth 或 Win7/offline runtime 依赖。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- 关联文档：
  - `docs/modules/frontend-gui.md`
- 是否需要 ADR：否；这是 GUI shell display/read-model refinement and dev harness isolation，不改变长期架构边界。
- 后续动作：
  - Continue toward richer T3code-like thread lifecycle management: rename/archive/fork metadata and per-project thread grouping, still through existing Core/protocol boundaries.
  - Keep `npm run visual:gui -- --scenario all` as the default GUI visual regression entry.

### DC-159

- 日期：2026-06-16
- 变更主题：GUI timeline interaction polish and visual fixture expansion
- 变更摘要：
  - Timeline work row / turn fold expansion became frontend-local controlled UI state.
  - Visual harness gained deterministic timeline and interaction fixture scenarios.
  - The fixture hook remains gated by `?visual_debug=1` and is not product protocol or Agent Core capability.
  - 本次保持 T3code-style shell 借鉴与 Pi-style Core decoupling：没有复制 T3code 源码，没有新增 Agent Core、permission policy、workflow package、session history truth 或 Win7/offline runtime 依赖。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/`
  - `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerInteractionPanel.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `scripts/gui-visual-debug.mjs`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- 关联文档：
  - `docs/archive/t3code-pi-workbench/2026-06-16-gui-timeline-interaction-polish-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-16-gui-timeline-interaction-polish.md`
- 是否需要 ADR：否；这是 GUI shell and dev harness refinement，不改变长期架构边界。
- 后续动作：
  - Continue later with Diff panel split/wrap review polish.
  - 视觉回归默认使用 `npm run visual:gui -- --scenario all`；定位 timeline / pending interaction 问题时可单独运行 `--scenario timeline,interaction`。

### DC-158

- 日期：2026-06-16
- 变更主题：T3code-style GUI timeline/diff refinement and fixture-backed visual debugging
- 变更摘要：
  - GUI timeline changed-files card 从平铺列表升级为 T3code-like 目录树，支持目录折叠/展开、目录级 diff 统计、路径归一化与 `View diff` 入口。
  - Diff right-panel 改为 header + changed-file rail + diff viewport；右栏和窄屏布局自动单列堆叠，避免文件列表挤压 diff 内容。
  - `scripts/gui-visual-debug.mjs` 的 diff 场景不再依赖后端 `/diff` 链路是否产出 diff，而是在显式 `?visual_debug=1` 下通过 `window.__EMBEDAGENT_VISUAL_DEBUG__` 打开离线 unified-diff fixture，稳定验证真实 GUI 的 DiffPanel、file rail、截图和 console 状态。
  - 修复 frontend T3 timeline projection 中 loose system item callback 错误，以及 detached/trailing item 合并丢失问题。
  - 本次仍未复制 T3code 源码，未改变 Agent Core、permission policy、workflow package、session history truth、HTTP/WebSocket 产品协议或 Win7/offline runtime 依赖。
- 影响范围：
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/ChangedFilesCard.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `src/embedagent/frontend/gui/static/assets/`
  - `src/embedagent/frontend/gui/webapp/test/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- 关联文档：
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/archive/t3-parity-gui-debug/2026-06-15-t3-parity-gui-debug-design.md`
- 是否需要 ADR：否；这是 GUI shell/display surface 与开发机 visual harness 细化，不改变长期架构边界。
- 后续动作：
  - 继续按 T3code 参考细化编辑闭环、timeline fold/scroll anchoring 和 review diff 交互。
  - 视觉回归默认使用 `npm run visual:gui -- --scenario all`，必要时单独运行 `--scenario diff,responsive` 检查 file rail 和窄屏布局。

### DC-157

- 日期：2026-06-15
- 变更主题：T3code-inspired GUI neutral visual language
- 变更摘要：
  - GUI 在不更换技术栈、不复制 T3code 代码的前提下，将视觉语言向 T3code neutral workbench 收敛。
  - 全局 CSS token 从 GitHub-dark 风格调整为 neutral dark workbench；timeline 增加 centered shell，message/work rows、composer、right-panel tabs、diff panel 统一使用更柔和的边框、圆角、面板层级与更克制的状态色。
  - 新增 frontend CSS contract 测试，锁定 T3-style token、timeline shell、composer fade、diff/right-panel shell 等关键视觉规则。
  - 本次只改变 GUI shell 显示语言，不改变 Agent Core、permission policy、workflow package、session history 或 protocol truth。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - `src/embedagent/frontend/gui/webapp/test/visual-language-css.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `src/embedagent/frontend/gui/static/assets/`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- 关联文档：
  - `docs/archive/t3-parity-gui-debug/2026-06-15-t3-visual-language.md`
  - `docs/modules/frontend-gui.md`
- 是否需要 ADR：否；这是 GUI shell 视觉语言收敛，不改变长期架构边界。
- 后续动作：
  - 继续用 `npm run visual:gui -- --scenario all` 作为 GUI polish 的默认可视回归入口。
  - 后续细化编辑闭环、timeline 折叠和 diff review 交互时继续按 T3code 参考收敛。

### DC-156

- 日期：2026-06-15
- 变更主题：T3code-style GUI core surfaces and Codex visual debug harness
- 变更摘要：
  - GUI 在既有 React/Vite + PyWebView/WebView2 技术栈内新增 T3-style timeline row projection/rendering、composer-local permission/user-input interaction panel、right-panel Diff surface。
  - 新增 dev-only `scripts/gui-visual-debug.mjs` 与 `npm run visual:gui`，可在 Win10/Win11 开发机启动真实 GUI、执行 load/chat/diff 场景、生成截图和 `summary.json`，并检查 console warning/error 与关键 DOM 状态。
  - Visual harness 发现并推动修复 streaming assistant 文本重复：`LLMClientRetryWrapper` 在 `stream=True` 时不再重放 final content delta；GUI WebSocket lifecycle 增加 token/manual-close guard，避免旧连接 cleanup 后安排重连。
  - Playwright 是 webapp devDependency，仅用于开发机可视调试；Win7 离线运行时仍不依赖 Node、Playwright、Electron、外部浏览器自动化服务或在线资源。
- 影响范围：
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/`
  - `src/embedagent/frontend/gui/webapp/src/components/composer/`
  - `src/embedagent/frontend/gui/webapp/src/components/diff/`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/strategies/llm_retry_wrapper.py`
  - `tests/test_llm_resilience.py`
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
- 关联文档：
  - `docs/archive/t3-parity-gui-debug/2026-06-15-t3-parity-gui-debug-design.md`
  - `docs/archive/t3-parity-gui-debug/2026-06-15-t3-parity-gui-debug.md`
  - `docs/modules/frontend-gui.md`
- 是否需要 ADR：否；本次是 GUI shell/display surface 与开发调试能力切片，不改变 Agent Core、permission、workflow 或离线 runtime 架构边界。
- 后续动作：
  - 继续按 T3code 参考细化 timeline/diff/编辑闭环。
  - 后续可为 TUI 增加低优先级的 headless visual/state capture，但不得引入 runtime 在线依赖。

### DC-155

- 日期：2026-06-15
- 变更主题：T3code-inspired Pi-bounded workbench shell
- 变更摘要：
  - Adopted T3code's workbench product shape for frontend shell interaction: thread/project sidebar, central Agent timeline, rich composer, thread-scoped right-panel surfaces, optional bottom drawer, command palette, and keybinding rules.
  - Preserved Pi-style decoupling by keeping this state frontend-local and read-model driven.
  - Agent Core, ExtensionManager, PermissionPolicy, SessionHistoryAssembler, workflow packages, transcript history, and tool runtime policy remain authoritative.
  - No source code was copied from `reference/t3code`; this implementation recreates the shell model with project-local React and prompt_toolkit code.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/workbench/`
  - `src/embedagent/frontend/gui/webapp/src/components/workbench/`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/tui/workbench.py`
  - `src/embedagent/frontend/tui/layout.py`
  - `src/embedagent/frontend/tui/views/command_palette.py`
  - `docs/frontend-protocol.md`
  - `docs/modules/frontend-gui.md`
  - `docs/modules/frontend-tui.md`
- 关联文档：
  - `docs/archive/t3code-pi-workbench/2026-06-15-t3code-pi-workbench-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-15-t3code-pi-workbench.md`
- 是否需要 ADR：否
- 后续动作：
  - 在真实 Win7 WebView2 109 环境执行 GUI smoke。
  - 继续打磨 C/C++ workflow 的 run output、problem、diff surfaces。

### DC-154

- 日期：2026-06-15
- 变更主题：Enterprise boundary foundation implementation
- 变更摘要：
  - 新增正式 permission categories：`network` 与 `telemetry`
  - `PermissionPolicy`、dynamic tool registration、project extension manifest validation 和 `SelfExtensionAuthoringService` 已共享这些类别
  - `network` / `telemetry` 默认需要确认，不能通过未分类 `other` 或 `read` 隐藏内网/遥测副作用
  - 新增 `src/embedagent/telemetry.py`，提供本地 safe telemetry envelope helper，剔除或摘要 prompt、source text、raw tool output、API key、permission payload、token、secret 等敏感 metadata
  - 本次没有新增真实内网 Git/custom service、telemetry uploader、remote catalog 或 runtime dependency installation
- 影响范围：
  - `src/embedagent/permissions.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/project_extensions.py`
  - `src/embedagent/self_extension_authoring.py`
  - `src/embedagent/telemetry.py`
  - `tests/test_permissions.py`
  - `tests/test_dynamic_tool_registration.py`
  - `tests/test_project_extensions.py`
  - `tests/test_self_extension_authoring.py`
  - `tests/test_telemetry.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
- 关联文档：
  - `docs/archive/enterprise-boundary-foundation/2026-06-15-enterprise-boundary-foundation-design.md`
  - `docs/archive/enterprise-boundary-foundation/2026-06-15-enterprise-boundary-foundation.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
- 是否需要 ADR：`否，本次是既有 extension/tool/permission 边界的类别与安全投影补强；不新增网络运行时或外部依赖`
- 后续动作：
  - 后续真实内网 Git/custom service/telemetry sink 必须作为独立 extension/provider/sink slice 实施，并复用本次 permission 与 safe envelope 边界

### DC-153

- 日期：2026-06-15
- 变更主题：Pi-style enterprise/intranet capability boundary
- 变更摘要：
  - 参考 Pi 的 custom provider、package 与 observability adapter 结构，但保持 EmbedAgent Core 极简、离线优先和 Win7 约束
  - 明确未来内网 Git、custom service、provider gateway、组织内 catalog 与 telemetry sink 只能作为显式配置、受信、可关闭、可降级的 hosted extension/provider/workflow-package/sink
  - 明确 telemetry 只能观察安全 lifecycle/capability/diagnostic 事件，不得导出 prompt、源码、原始工具输出、API key、审批 secret 或 permission token
  - 将 public marketplace、runtime online install、public remote registry、mandatory network control plane 继续固定为非目标
- 影响范围：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/overall-solution-architecture.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
- 是否需要 ADR：`否，本次是长期架构边界和非目标澄清；不新增执行型 API 或运行时依赖`
- 后续动作：
  - 后续若实施内网 Git/custom service/telemetry slice，必须先补齐显式 permission/category、配置、redaction、超时降级和离线 bundle/admin provisioning 方案

### DC-152

- 日期：2026-06-15
- 变更主题：Prompt-unit snapshot safe metadata
- 变更摘要：
  - `TurnSnapshot` 新增安全 `prompt_units` 元数据，用于记录 local skill listing 的 visible skill names/counts 和可选 resource revision
  - `QueryEngine` provider request operation metadata 现在写入 `turn_snapshot.prompt_units`，不记录 skill body、完整 prompt、文件内容、工具输出或凭据
  - `RuntimeConfigReducer` provider snapshot records 会保留安全 prompt-unit summary，resource reload 只影响后续 provider request snapshot
- 影响范围：
  - `src/embedagent/query_engine.py`
  - `src/embedagent/turn_snapshot.py`
  - `src/embedagent/runtime_config.py`
  - `tests/test_query_engine_refactor.py`
  - `tests/test_runtime_config.py`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/self-extensible-agent-core/2026-06-15-remaining-pi-architecture-gaps.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
- 是否需要 ADR：`否，本次是现有 TurnSnapshot / RuntimeConfigReducer 安全诊断字段扩展；不新增执行型 API`
- 后续动作：
  - 继续用完整 fast subset 验证本轮剩余 Pi architecture slice 收口情况

### DC-151

- 日期：2026-06-15
- 变更主题：Internal SkillIndex read model
- 变更摘要：
  - 新增 `SkillIndex` / `SkillRecord` 内部只读模型，统一 local skill prompt listing、`/skill:<name>` lookup、visible skill slash-command projection 与 safe summary
  - `modes.build_system_prompt`、`InProcessAdapter` skill command/help 投影、session-scoped local skills prompt refresh 和 `expand_skill_invocation` 已切到同一个 read model
  - `SkillIndex` 不执行 skill、不 reload resource、不决定权限或 active-tool policy，也不新增 frontend `skill` capability kind
- 影响范围：
  - `src/embedagent/skill_index.py`
  - `src/embedagent/skills.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/modes.py`
  - `tests/test_local_resources.py`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/self-extensible-agent-core/2026-06-15-remaining-pi-architecture-gaps.md`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
- 是否需要 ADR：`否，本次是内部 read model 收口；不改变 public frontend protocol kind 或 extension execution contract`
- 后续动作：
  - 继续 prompt-unit snapshot safe metadata，把 visible skill listing 作为安全 prompt unit 记录到 provider snapshot metadata

### DC-150

- 日期：2026-06-15
- 变更主题：Pi-compatible skill discovery ignore rules
- 变更摘要：
  - `.embedagent/skills` 扫描现在会读取本地 `.gitignore`、`.ignore`、`.fdignore`
  - ignore 语义保持轻量和离线：支持空行、`#` 注释、相对路径、目录规则、`fnmatch` glob 和 `!` negation
  - ignore 只影响 skill file discovery，不执行代码、不加载 extension、不改变 workspace-bound path check 或权限策略
- 影响范围：
  - `src/embedagent/skills.py`
  - `tests/test_local_resources.py`
  - `docs/tool-contracts.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/self-extensible-agent-core/2026-06-15-remaining-pi-architecture-gaps.md`
  - `docs/tool-contracts.md`
- 是否需要 ADR：`否，本次是本地文件发现过滤语义补齐；不新增 public extension API`
- 后续动作：
  - 继续内部 `SkillIndex` read model，统一 prompt listing、command projection 与显式 invocation lookup
  - 继续 prompt-unit snapshot safe metadata

### DC-149

- 日期：2026-06-15
- 变更主题：Workflow prompt kind generic cleanup 收口
- 变更摘要：
  - `QueryEngine` 内部 workflow prompt 注入 helper 已改为 `_should_inject_workflow_prompt` / `_append_workflow_prompt_messages`
  - 新增的 workflow prompt system message 使用 `kind="workflow_prompt"`，不再使用 harness-shaped `harness_prompt`
  - 后续 S01 清理已删除 `kind="harness_prompt"` 的活动 prompt assembly 去重兼容；hosted C/C++ prompt content 与 activation 行为继续使用 `workflow_prompt`
- 影响范围：
  - `src/embedagent/query_engine.py`
  - `tests/test_query_engine_refactor.py`
  - `tests/test_workflow_extensions.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/self-extensible-agent-core/2026-06-15-remaining-pi-architecture-gaps.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
- 是否需要 ADR：`否，本次是内部命名与 message kind 清理；不改变 public extension API 或默认 C/C++ workflow 行为`
- 后续动作：
  - 继续 Pi-compatible skill discovery ignore rules
  - 继续内部 SkillIndex read model

### DC-148

- 日期：2026-06-15
- 变更主题：Pi-inspired local skill resource invocation slice 收口
- 变更摘要：
  - 新增 `src/embedagent/skills.py`，支持 Agent Skills-style frontmatter（`name`、`description`、`disable-model-invocation`）、workspace-bound skill discovery metadata 与 system prompt 可见列表格式化
  - `.embedagent/skills/<name>/SKILL.md` 与 legacy `.md` / `.txt` skill 文件继续作为 file-only local resources 发现；visible skills 进入系统提示词，disabled skills 仍可作为资源发现但不进入 model invocation listing
  - 新增 `/skill:<name> [args]` 显式调用路径，读取 workspace-bound Markdown skill、剥离 frontmatter、包装为普通 user turn context；不执行 Python、不加载 project extension、不绕过权限或 active-tool policy
  - session-scoped resource reload 会刷新当前会话的 `local_skills_prompt` system message；visible skill commands 也会进入 `/help` 与 command capability projection
  - `SelfExtensionAuthoringService` 生成的 skill 模板现在带 frontmatter，便于 reload 后进入 prompt listing
- 影响范围：
  - `src/embedagent/skills.py`
  - `src/embedagent/local_resources.py`
  - `src/embedagent/modes.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/self_extension_authoring.py`
  - `tests/test_local_resources.py`
  - `tests/test_self_extension_authoring.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/mode-schema.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
- 关联文档：
  - `docs/archive/self-extensible-agent-core/2026-06-15-pi-style-local-skills.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
- 是否需要 ADR：`否，本次是 Pi-inspired local self-extension 方向下的资源语义增强；不新增执行型 extension API`
- 后续动作：
  - 继续清理 remaining harness-named prompt injection internals
  - 在真实 Win7 目标机执行 clean offline bundle smoke
  - 继续真实 C/C++ 工程验证

### DC-147

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase M core alias cleanup 收口
- 变更摘要：
  - 删除 `embedagent.modes.MODE_REGISTRY` 兼容代理，mode helpers 直接通过 `get_mode_registry()` 读取 registry
  - 删除 `embedagent.command_sanitizer._DEFAULT_SANITIZER` 与 `get_default_sanitizer()`，shell tooling 改为直接使用 `get_command_sanitizer()`
  - 删除 `embedagent.core.adapter` 内的 `_inprocess_adapter` / `_get_adapter_class()` 兼容访问器，adapter class lookup 只保留 `get_inprocess_adapter()`
  - mode behavior、command sanitizer behavior、adapter lifecycle、permission policy 与 hosted C/C++ behavior 不变
- 影响范围：
  - `src/embedagent/modes.py`
  - `src/embedagent/command_sanitizer.py`
  - `src/embedagent/tools/shell_ops.py`
  - `src/embedagent/core/adapter.py`
  - `tests/test_backward_compatibility.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/mode-schema.md`
  - `docs/permission-model.md`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/agent-core-refactor-history/architecture-refactor.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-m-core-alias-cleanup/2026-06-14-phase-m-core-alias-cleanup-design.md`
  - `docs/archive/phase-m-core-alias-cleanup/2026-06-14-phase-m-core-alias-cleanup.md`
- 是否需要 ADR：`否，本次是已批准 minimal Core 方向下的 stale compatibility alias 删除；不改变运行时行为或公共 extension API`
- 后续动作：
  - 在真实 Win7 目标机执行 clean offline bundle smoke
  - 继续真实 C/C++ 工程验证
  - 继续按 source-of-truth docs 审计剩余 compatibility/deprecated 路径

### DC-146

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase L pack compatibility cleanup 收口
- 变更摘要：
  - 删除 `src/embedagent/tooling/packs.py`，移除历史 C/C++ workflow pack compatibility re-export
  - `src/embedagent/tooling/__init__.py` 不再 re-export `BUILD_LITE_PACK`、`CORE_PACK`、`DEBUG_LITE_PACK`、`VERIFY_PACK`、`PACKS` 或 `pack_tool_names`
  - workflow pack ownership 只保留在 `src/embedagent/harness/packs.py`
  - active tool selection、runtime schema projection、permission policy 与 hosted C/C++ behavior 不变
- 影响范围：
  - `src/embedagent/tooling/__init__.py`
  - `src/embedagent/tooling/packs.py`
  - `tests/test_workflow_extensions.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-l-pack-compat-cleanup/2026-06-14-phase-l-pack-compat-cleanup-design.md`
  - `docs/archive/phase-l-pack-compat-cleanup/2026-06-14-phase-l-pack-compat-cleanup.md`
- 是否需要 ADR：`否，本次是已批准架构方向下的 stale compatibility path 删除；不改变默认 C/C++ workflow 行为或公共 extension API`
- 后续动作：
  - 在真实 Win7 目标机执行 clean offline bundle smoke
  - 继续真实 C/C++ 工程验证
  - 继续删除已证明不属于当前正式架构的 stale compatibility paths

### DC-145

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase K recovery state 收口
- 变更摘要：
  - 新增 `src/embedagent/recovery_state.py`，由 `RecoveryStateReducer` 从 `recovery_marker` transcript events 投影 replayable hosted recovery state
  - `InProcessAdapter.resume_session(...)` 在 restore 出可信 transcript prefix 后追加 safe `recovery_marker`，记录 trusted/transcript event counts、stop reason、skip reasons、operation summary、compaction summary 与 runtime summary
  - `SessionRestorer` 暴露 `recovery_state`，并只对已消费的 self-consistent transcript prefix 做 reducer 投影
  - `ManagedSession`、`SessionSnapshotProjector`、protocol `SessionSnapshot` 与 core adapter snapshot conversion 现在暴露 reducer-backed `recovery_state`
  - recovery projection 保持 diagnostics/replay state，不改变 restore validation、mode/tool/context policy、extension loading、tool execution 或 permission policy
- 影响范围：
  - `src/embedagent/recovery_state.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/session_restore.py`
  - `src/embedagent/session_runtime.py`
  - `src/embedagent/session_projector.py`
  - `src/embedagent/protocol/__init__.py`
  - `src/embedagent/core/adapter.py`
  - `tests/test_recovery_state.py`
  - `tests/test_session_restore.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
  - `tests/test_architecture.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/mode-schema.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-k-recovery-state/2026-06-14-phase-k-recovery-state-design.md`
  - `docs/archive/phase-k-recovery-state/2026-06-14-phase-k-recovery-state.md`
- 是否需要 ADR：`否，本次是已批准 Phase K 的内部 reducer/read-model 收口；不新增公共 extension API，不改变 restore validation 或自动恢复策略`
- 后续动作：
  - 在真实 Win7 目标机执行 clean offline bundle smoke
  - 继续真实 C/C++ 工程验证，观察 recovery_state 是否足以解释 restore/resume 降级路径
  - 删除剩余 stale compatibility paths

### DC-144

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase J structured compaction state 收口
- 变更摘要：
  - 新增 `src/embedagent/compaction_state.py`，由 `CompactionStateReducer` 从 `compact_boundary` transcript events 投影 replayable structured compaction state
  - `compact_boundary` payload 现在携带 safe token/message counts、preserved message anchors、file activity paths、evidence refs 与 extension-summary flag
  - `SessionRestorer` 暴露 `compaction_state`，并只对已消费的 self-consistent transcript prefix 做 reducer 投影
  - `ManagedSession`、`SessionSnapshotProjector`、protocol `SessionSnapshot` 与 core adapter snapshot conversion 现在暴露 reducer-backed `compaction_state`
  - compaction projection 保持 diagnostics/replay state，不驱动 context selection、summary generation、extension loading、tool execution 或 permission policy
- 影响范围：
  - `src/embedagent/compaction_state.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/session_restore.py`
  - `src/embedagent/session_runtime.py`
  - `src/embedagent/session_projector.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/protocol/__init__.py`
  - `src/embedagent/core/adapter.py`
  - `tests/test_compaction_state.py`
  - `tests/test_query_engine_refactor.py`
  - `tests/test_session_restore.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
  - `tests/test_architecture.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/frontend-protocol.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-j-structured-compaction/2026-06-14-phase-j-structured-compaction-design.md`
  - `docs/archive/phase-j-structured-compaction/2026-06-14-phase-j-structured-compaction.md`
- 是否需要 ADR：`否，本次是已批准 Phase J 的内部 reducer/read-model 收口；不新增公共 extension API，不改变 context selection 算法`
- 后续动作：
  - 在真实 Win7 目标机执行 clean offline bundle smoke
  - 继续真实 C/C++ 工程验证，观察 compaction_state 是否足以解释长会话压缩边界
  - 删除剩余 stale compatibility paths

### DC-143

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase I workflow package manifest 收口
- 变更摘要：
  - 新增 `src/embedagent/workflow_package_manifest.py`，由 `WorkflowPackageManifest` / `WorkflowToolDeclaration` / `WorkflowPackDeclaration` 表示 workflow package 的只读 manifest/read model
  - 新增默认 C/C++ workflow package manifest builder，从 harness-owned tool metadata 与 pack constants 派生 package identity、supported modes/workflow states、tool declarations、packs 与 `.embedagent/recipes` resource scope
  - `CHarnessWorkflowExtension.package_manifest()` 暴露 bundled manifest，`ExtensionManager.package_manifests()` 通过共享 extension manager 通用收集 package manifests
  - `CapabilityRegistry` 新增 `workflow_package` capability kind，`InProcessAdapter.capability_snapshot()` 现在通过 shared `ExtensionManager` 投影 bundled workflow package descriptor
  - manifest projection 保持只读诊断/控制面状态，不驱动 active tools、tool execution、resource reload、extension loading 或 permission policy
- 影响范围：
  - `src/embedagent/workflow_package_manifest.py`
  - `src/embedagent/harness/package_manifest.py`
  - `src/embedagent/harness/extension.py`
  - `src/embedagent/extensions.py`
  - `src/embedagent/capabilities.py`
  - `src/embedagent/inprocess_adapter.py`
  - `tests/test_workflow_package_manifest.py`
  - `tests/test_capability_registry.py`
  - `tests/test_local_resources.py`
  - `tests/test_workflow_extensions.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/mode-schema.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-i-workflow-package-manifest/2026-06-14-phase-i-workflow-package-manifest-design.md`
  - `docs/archive/phase-i-workflow-package-manifest/2026-06-14-phase-i-workflow-package-manifest.md`
- 是否需要 ADR：`否，本次是已批准 Phase I 的内部 manifest/read-model 收口；公共 extension API 未新增稳定承诺，frontend 只获得诊断型 capability descriptor`
- 后续动作：
  - structured compaction state 已由 DC-144 / Phase J 收口
  - 在更多真实 C/C++ 工程中验证默认 workflow package manifest 与 tool/catalog 诊断信息是否足够解释问题
  - 继续真实 Win7 bundle smoke 与剩余 stale compatibility paths 删除

### DC-142

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase H runtime configuration reducer 收口
- 变更摘要：
  - 新增 `src/embedagent/runtime_config.py`，由 `RuntimeConfigReducer` 从 transcript events 投影 replayable runtime configuration
  - reducer 消费 `runtime_configured`、`resource_reloaded` 与 provider-request `operation_started` safe turn snapshot metadata，投影 credential-free model profile、active model-visible tool names、local resource revision metadata、capability counts 与 provider snapshot records
  - `InProcessAdapter` 在 session start / resource reload / resume / snapshot 路径刷新 `ManagedSession.runtime_config`，session snapshots 现在暴露 reducer-backed `runtime_config`
  - `TurnSnapshot` 增加 `resource_revision`，`QueryEngine` 可从 reducer-backed runtime config 读取 model profile 与 resource revision metadata，并继续只把 safe snapshot metadata 写入 provider operation diagnostics
  - `resource_discovered` 保持 discovery/replay diagnostics，不推进 resource revision；tool activation、execution、resource reload、extension loading 与 permission policy 仍由原边界负责
- 影响范围：
  - `src/embedagent/runtime_config.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/turn_snapshot.py`
  - `src/embedagent/session_runtime.py`
  - `src/embedagent/session_projector.py`
  - `tests/test_runtime_config.py`
  - `tests/test_local_resources.py`
  - `tests/test_query_engine_refactor.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-h-runtime-config-reducer/2026-06-14-phase-h-runtime-config-reducer-design.md`
  - `docs/archive/phase-h-runtime-config-reducer/2026-06-14-phase-h-runtime-config-reducer.md`
- 是否需要 ADR：`否，本次是已批准 Phase H 的内部 reducer/read-model 收口；公共 extension API 未新增，frontend 只获得诊断型 snapshot 字段`
- 后续动作：
  - workflow package manifest/read model 已由 DC-143 / Phase I 收口
  - structured compaction state 已由 DC-144 / Phase J 收口
  - 继续真实 Win7 bundle smoke 与真实 C/C++ 工程验证

### DC-141

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase G turn snapshot / capability registry 收口
- 变更摘要：
  - 新增 `src/embedagent/turn_snapshot.py`，由 `TurnSnapshot` / `TurnSnapshotBuilder` 表示一次 provider request 的冻结输入
  - `QueryEngine` 现在在 context assembly 与 active tool schema projection 后构造 turn snapshot，并以 `snapshot.messages` / `snapshot.tool_schemas` 调用 provider
  - provider request operation metadata/result 只记录 safe snapshot metadata：`snapshot_id`、mode/workflow state、active tool names、credential-free model profile 与 capability counts
  - 新增 `src/embedagent/capabilities.py`，由 `CapabilityRegistry` 作为非执行型 read model 投影 tools、local file resources、slash commands 与 model profiles
  - `ToolRuntime.capability_descriptors()` 与 `InProcessAdapter.capability_snapshot()` 暴露只读 capability projection；tool activation 仍归 `ExtensionManager` / `AgentExtensionHost`，execution 仍归 `ToolRuntime` / `AgentToolActionService`
- 影响范围：
  - `src/embedagent/turn_snapshot.py`
  - `src/embedagent/capabilities.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/slash_commands.py`
  - `src/embedagent/inprocess_adapter.py`
  - `tests/test_turn_snapshot.py`
  - `tests/test_capability_registry.py`
  - `tests/test_query_engine_refactor.py`
  - `tests/test_local_resources.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-g-turn-snapshot-capability-registry/2026-06-14-phase-g-turn-snapshot-capability-registry-design.md`
  - `docs/archive/phase-g-turn-snapshot-capability-registry/2026-06-14-phase-g-turn-snapshot-capability-registry.md`
- 是否需要 ADR：`否，本次是已批准 Phase G 的内部 provider-request boundary 与 read-model foundation；公共 frontend protocol 与 extension API 未新增必需字段`
- 后续动作：
  - durable runtime configuration reducer 已由 DC-142 / Phase H 收口
  - 继续真实 Win7 bundle smoke 与真实 C/C++ 工程验证

### DC-140

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase F offline bundle validation 收口
- 变更摘要：
  - 新增 `scripts/offline-runtime-contract.json` 作为 runtime-invoked bundled external tools 的 repo-side 单一契约
  - `scripts/validate-offline-bundle.ps1` 现在消费 runtime contract，对 Python、MinGit、ripgrep、Universal Ctags 与 LLVM/Clang child executables 做静态与动态 bundle gate 检查
  - `scripts/check-bundle-dependencies.py` 现在消费同一 runtime contract，并在结构化报告中输出 `runtime_contract` 元数据与 `runtime_tool.*` 外部工具错误
  - 补充回归测试锁定 project extension loading 不调用 dependency installers，generated extension validation recipe 使用 managed Python command
  - clean Windows 7 unpack-and-run smoke 保持为发布门禁，repo-side validation 不替代实机验收
- 影响范围：
  - `scripts/offline-runtime-contract.json`
  - `scripts/validate-offline-bundle.ps1`
  - `scripts/check-bundle-dependencies.py`
  - `tests/test_packaging_control_plane.py`
  - `tests/test_tools_package.py`
  - `tests/test_project_extensions.py`
  - `tests/test_self_extension_authoring.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/modules/packaging-and-deployment.md`
  - `docs/guides/win7-preflight-checklist.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-f-offline-bundle-validation/2026-06-14-phase-f-offline-bundle-validation-design.md`
  - `docs/archive/phase-f-offline-bundle-validation/2026-06-14-phase-f-offline-bundle-validation.md`
- 是否需要 ADR：`否，本次是已批准 Phase F 的 repo-side offline bundle validation 收口；真实 Win7 smoke 仍由发布验收记录承载`
- 后续动作：
  - 在干净 Windows 7 目标机重跑 contract-backed bundle smoke
  - 用真实 C/C++ 工程继续验证默认 harness workflow 与 LLVM/Clang bundle

### DC-139

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase E self-extension authoring loop 收口
- 变更摘要：
  - 新增 `src/embedagent/self_extension_authoring.py`，由 `SelfExtensionAuthoringService` 统一生成 workspace-bound local self-extension artifacts
  - 新增 `author_local_capability` workflow-neutral built-in tool，在 build/debug mode 下以 `workspace_write` 权限生成 skills/prompts/recipes/disabled project extension skeletons
  - generated project extension manifest 默认 `enabled: false`，并包含 workspace-bound `extension.py`、README 与 validation recipe
  - resource reload 与 executable project extension loading 继续分离；authoring 不 reload resources，不 load/import Python extension code
  - 补充回归测试覆盖 authoring artifact generation、overwrite/permission guard、resource snapshot reload boundary 与 disabled extension non-import boundary
- 影响范围：
  - `src/embedagent/self_extension_authoring.py`
  - `src/embedagent/tools/authoring_ops.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/modes.py`
  - `tests/test_self_extension_authoring.py`
  - `tests/test_tools_package.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-e-self-extension-authoring/2026-06-14-phase-e-self-extension-authoring-design.md`
  - `docs/archive/phase-e-self-extension-authoring/2026-06-14-phase-e-self-extension-authoring.md`
- 是否需要 ADR：`否，本次是已批准 Phase E 的 local authoring workflow extraction；公共 frontend protocol 未新增 endpoint`
- 后续动作：
  - Phase F 已完成 repo-side offline bundle validation；后续继续真实 Win7 smoke 与真实 C/C++ 工程验证

### DC-138

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase D default C/C++ workflow package 收口
- 变更摘要：
  - bare `ToolRuntime` 构造恢复为 workflow-neutral，只注册文件、发现、shell/git/build-env 等 core tools
  - `CHarnessWorkflowExtension.register_tools(...)` 现在通过共享 `ExtensionManager` / `AgentEventBus` 注册默认 C/C++ workflow tools
  - C/C++ workflow tool metadata 迁入 `src/embedagent/harness/tool_metadata.py`
  - C/C++ workflow pack 定义迁入 `src/embedagent/harness/packs.py`；当时 `src/embedagent/tooling/packs.py` 仅保留兼容 re-export，后续已由 DC-146 删除
  - 删除旧 runtime-side facade `src/embedagent/tools/harness_runtime.py`
  - 新增 guardrails，证明 importing bare `ToolRuntime` 不加载 harness runtime/runner，hosted adapter catalog 仍默认暴露 C/C++ workflow tools
- 影响范围：
  - `src/embedagent/harness/extension.py`
  - `src/embedagent/harness/tool_registry.py`
  - `src/embedagent/harness/tool_metadata.py`
  - `src/embedagent/harness/packs.py`
  - `src/embedagent/harness/runner.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/tooling/packs.py`（历史兼容出口，后续已由 DC-146 删除）
  - `tests/test_workflow_extensions.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-d-workflow-package/2026-06-14-phase-d-workflow-package-design.md`
  - `docs/archive/phase-d-workflow-package/2026-06-14-phase-d-workflow-package.md`
- 是否需要 ADR：`否，本次是已批准 Phase D 的默认 workflow package ownership extraction；公共 frontend protocol 与 project extension API 未变`
- 后续动作：
  - 启动 Phase E self-extension authoring loop
  - 继续保持 resource reload 与 executable project extension loading 的安全边界

### DC-137

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase C AgentKernel lifecycle extraction 收口
- 变更摘要：
  - 新增 `AgentLifecycleJournal`，集中 schema v2 lifecycle operation 写入、transition save point、pending interaction lifecycle、context operation payload helper
  - 新增 `AgentKernel` / `AgentTurnFrame`，统一 user、command、resume turn frame，并把 permission/user-input pending 创建与 resolution 边界迁出 `QueryEngine`
  - `AgentLoop` 从 runner callback 包装器升级为 turn-loop owner，负责 agent step lifecycle、context/provider attempt、compact retry、tool batch interruption、guard-stop、abort 与 safety-limit compatibility transition
  - `QueryEngine` 保持 session-scoped facade 与 transcript/session mutation 兼容面，但不再拥有 `_run_loop_impl`
  - Phase C working design/plan 已从 `docs/superpowers/` 归档到 `docs/archive/phase-c-agent-kernel/`
- 影响范围：
  - `src/embedagent/agent_lifecycle.py`
  - `src/embedagent/agent_kernel.py`
  - `src/embedagent/agent_loop.py`
  - `src/embedagent/query_engine.py`
  - `tests/test_agent_lifecycle.py`
  - `tests/test_query_engine_refactor.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-c-agent-kernel/2026-06-14-phase-c-agent-kernel-design.md`
  - `docs/archive/phase-c-agent-kernel/2026-06-14-phase-c-agent-kernel.md`
- 是否需要 ADR：`否，本次是已批准 Phase C 的内部 lifecycle boundary extraction；公共 extension API 与 frontend protocol 未变`
- 后续动作：
  - 启动 Phase D default C/C++ workflow package 设计
  - 继续保持 `AgentToolActionService`、`AgentExtensionHost`、`AgentEventBus` 与 `AgentKernel` 的边界清晰，避免把 lifecycle 或 workflow package 逻辑加回 `QueryEngine`

### DC-136

- 日期：2026-06-14
- 变更主题：Phase A/B 收尾：live operation diagnostics 保留 active 状态
- 变更摘要：
  - `OperationLogReducer` 新增 `close_unfinished` 选项，默认保持 restore-time 行为：未完成 operation 关闭为 `interrupted`
  - `InProcessAdapter.get_session_snapshot(...)` 的 live diagnostics 使用 `close_unfinished=False`，避免把正在运行的 provider/tool/turn operation 误报为 `restore_incomplete_operation`
  - 新增 reducer 与 adapter 回归测试，明确 restore-time 与 live snapshot 的 operation 语义差异
  - 删除 Phase B 后遗留的未使用 `_record_diagnostic` helper
  - 同步 source-of-truth docs，把 Phase A/T-029 残留的“下一步进入 Phase B”口径修正为 Phase B 已收口、Phase C 继续抽 AgentKernel lifecycle boundary
- 影响范围：
  - `src/embedagent/session_operation_log.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/extensions.py`
  - `tests/test_session_operation_log.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，属于 Phase A/B 收尾语义修正；AgentKernel lifecycle boundary 硬切时再评估 ADR`
- 后续动作：
  - Phase C 抽 AgentKernel lifecycle 时继续保持 restore-time close 与 live active 两种 reducer 投影视角

### DC-135

- 日期：2026-06-14
- 变更主题：Pi-inspired minimal Core Phase B HookBus/reducer registry 收口
- 变更摘要：
  - `AgentEventBus.dispatch(...)` 新增 event-specific `reducer_stop`，用于表达 first-block-wins、first-result-wins 等 reducer 停止语义
  - `ExtensionManager` 公开 extension hook family 已统一通过 `AgentEventBus` 分发；当时保留的公共 method-name extension API 已在 DC-199 删除
  - bus-backed hook families 包括 context patch、resource discovery、dynamic tool registration、tool-call decision、tool-result patch、prompt patch、workflow injection decision、prompt description、workflow initialization、active tool names、session task snapshot loading 与 extension-owned tool handling
  - tool-call reducer 保留旧语义：sequential argument rewrites 会更新同一个 `WorkflowEvent`，第一个 blocking decision 停止后续 reducer
  - extension diagnostics 统一携带 `agent_event_type`、`handler_kind`、source metadata 与安全事件 metadata
  - 删除 `ExtensionManager` 内部旧 `_call_hook` 分发路径，避免 Phase B 收口后继续存在平行 hook dispatch
  - operation lifecycle 编排迁移不在本次完成范围内；它归入 Phase C AgentKernel lifecycle extraction，并应复用已建立的 bus boundary
- 影响范围：
  - `src/embedagent/agent_event_bus.py`
  - `src/embedagent/extensions.py`
  - `tests/test_capability_extensions.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-b-hookbus-reducer-registry/2026-06-14-phase-b-hookbus-closeout.md`
- 是否需要 ADR：`否，本次是已批准 Pi-inspired minimal Core Phase B 的实现收口；AgentKernel lifecycle boundary 硬切时再评估 ADR`
- 后续动作：
  - 启动 Phase C AgentKernel lifecycle extraction 设计
  - 在 Phase C 中把 turn snapshot、save point、suspend/resume、abort、compact retry 与 cleanup 迁出 session facade
  - 后续生命周期 observer/reducer 应复用 `AgentEventBus`，不要恢复 direct facade hooks

### DC-134

- 日期：2026-06-13
- 变更主题：Pi-inspired minimal Core Phase B AgentEventBus 第一切片
- 变更摘要：
  - 新增 `src/embedagent/agent_event_bus.py`，建立内部 source-aware `AgentEventBus`、`AgentEvent`、observer/reducer registration、dispatch diagnostics 与 trusted fail-closed 异常传播
  - `ExtensionManager.context(...)` 与 `ExtensionManager.after_tool_result(...)` 保持公共 API 不变，但内部改为通过 `extension.context` / `extension.tool_result` reducer event 合并 `ContextPatch` 与 `ToolResultPatch`
  - extension diagnostics 现在会附带 `agent_event_type`、`handler_kind` 与 source metadata，后续可把更多 hook family 迁入同一 reducer 边界
  - observer 语义明确为被动监听；observer 返回值不参与 reducer 结果
  - 本次不是 Phase B 全量完成；tool-call decisions、resource discovery、dynamic tool registration、operation lifecycle emitters、cleanup 与 reload semantics 仍是后续切片
- 影响范围：
  - `src/embedagent/agent_event_bus.py`
  - `src/embedagent/extensions.py`
  - `tests/test_capability_extensions.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-b-hookbus-reducer-registry/2026-06-13-phase-b-hookbus-first-slice.md`
- 是否需要 ADR：`否，本次是 Phase B 的第一实现切片；当 HookBus 成为所有 extension hooks 与 lifecycle reducers 的唯一边界时再评估 ADR`
- 后续动作：
  - 迁移 `tool_call` hook 到 bus，并明确 block/update argument 的 reducer 语义
  - 迁移 resource discovery 与 dynamic tool registration，同时保留 resource reload 与 executable extension loading 的分离
  - 评估 operation lifecycle emitters 是否通过同一 bus 暴露给 diagnostics/observability observer

### DC-133

- 日期：2026-06-13
- 变更主题：Pi-inspired minimal Core Phase A durable operation log 收口
- 变更摘要：
  - context snapshot 现在通过显式 `context_snapshot` operation lifecycle 写入，`context_snapshot` transcript 事件继续作为 session restore 的上下文快照输入
  - extension workflow patch 不再只是 live `session.workflow_state` 修改；`QueryEngine` 会在工具结果 hook 修改 workflow state 后写入 schema v2 `workflow_patch` transcript 事件与 `workflow_patch` operation lifecycle
  - `SessionRestorer` 会回放 `workflow_patch`，恢复 `Session.workflow_state["workflow"]` 与 `extensions.last_workflow_patch`
  - `InProcessAdapter.get_session_snapshot(...)` 会从 transcript reducer 刷新 live `operation_diagnostics`，restore-time 与 live snapshot 都能解释 operation family 的 finished/interrupted/active 状态
  - Phase A durable operation log 已覆盖 turn、agent step、context assembly、context snapshot、provider request、tool call、pending interaction、workflow patch 与 save point；后续应进入 Phase B HookBus/reducer registry，不继续把 reducer 语义散落在 facade helper 中
- 影响范围：
  - `src/embedagent/query_engine.py`
  - `src/embedagent/session_restore.py`
  - `src/embedagent/inprocess_adapter.py`
  - `tests/test_query_engine_refactor.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，本次关闭既有 Phase A implementation slice；Phase B HookBus/reducer registry 设计开始时再评估 ADR`
- 后续动作：
  - 启动 Phase B HookBus/reducer registry 设计，把 lifecycle/reducer 语义集中到 source-aware event boundary
  - 评估 AgentKernel extraction 时是否将 resume attempt 作为 turn operation 的子 operation
  - 保持 operation diagnostics 为诊断投影，不替代 session history、timeline reload 或 frontend workflow projection

### DC-132

- 日期：2026-06-13
- 变更主题：Turn / pending lifecycle 纳入 durable operation truth
- 变更摘要：
  - `QueryEngine` 现在为 user、command 与 resume turn 写入显式 `turn` operation lifecycle，turn operation 结果记录 transition reason、next mode、workflow state 与 turns used
  - pending permission / user input 创建时写入 `pending_interaction` operation start，恢复处理时写入 operation finish，避免 pending lifecycle 只靠 legacy interaction event 推断
  - agent step 在 `tool_calls`、`permission_wait`、`user_input_wait` 等非最终 completed 状态下也会写入明确 finish/interruption，restore 不再把正常等待或工具批次边界误判为 incomplete operation
  - 新增 `operation_diagnostics(...)` 作为 reducer-backed 诊断投影；`InProcessAdapter.resume_session(...)` 会把 restore-time operation diagnostics 放入 session snapshot
  - 本次仍不把 operation diagnostics 升级为 live UI 历史源；GUI/history 继续消费 `SessionHistoryAssembler` 与正式 session snapshot 字段
- 影响范围：
  - `src/embedagent/query_engine.py`
  - `src/embedagent/session_operation_log.py`
  - `src/embedagent/session_runtime.py`
  - `src/embedagent/session_projector.py`
  - `src/embedagent/inprocess_adapter.py`
  - `tests/test_query_engine_refactor.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，本次仍属于 Pi-inspired minimal Core Phase A 的 operation lifecycle 覆盖切片；HookBus/reducer registry 或 AgentKernel 边界硬切时再评估 ADR`
- 后续动作：
  - 已由 DC-133 收口 workflow patch / context snapshot lifecycle 与 live diagnostics projection
  - 下一步进入 Phase B HookBus/reducer registry 设计
  - 为 resume attempt 是否需要独立子 operation 建立 AgentKernel lifecycle 设计规则

### DC-131

- 日期：2026-06-13
- 变更主题：Operation lifecycle 明确切为 durable operation truth
- 变更摘要：
  - 接受“项目未上线，可以大胆动刀”的产品阶段判断，将 operation state 主路径从 legacy transcript 推断切为显式 lifecycle 事件
  - `OperationLogReducer` 现在只消费 schema_v2 `operation_started`、`operation_finished`、`operation_interrupted`，不再从 `step_started`、`tool_call`、`tool_result`、`loop_transition` 推断 runtime operation 状态
  - legacy transcript 事件继续用于 session replay、history、tool topology 和 GUI bootstrap，不再承担 operation-state truth
  - `QueryEngine` 已为 context assembly、provider request 和 save point 写入显式 operation lifecycle；既有 agent step 与 tool call lifecycle 继续保留
  - `SessionRestorer` 会消费显式 operation lifecycle 事件，使 `SessionRestoreResult.operation_state` 能解释运行中断点、完成的 provider/context/savepoint 与未完成 operation
- 影响范围：
  - `src/embedagent/session_operation_log.py`
  - `src/embedagent/session_restore.py`
  - `src/embedagent/query_engine.py`
  - `tests/test_session_operation_log.py`
  - `tests/test_query_engine_refactor.py`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/archive/phase-a-durable-operation-log/2026-06-13-durable-operation-log.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-a-durable-operation-log/2026-06-13-durable-operation-log.md`
- 是否需要 ADR：`否，本次仍是 Pi-inspired minimal Core Phase A 的 implementation slice；AgentKernel 生命周期边界硬切时再评估 ADR`
- 后续动作：
  - 补 turn lifecycle、pending interaction lifecycle、workflow patch lifecycle 的显式 operation/事件覆盖
  - 评估把 `operation_state` 投影到 session snapshot / diagnostics，供前端和恢复诊断消费
  - 继续推进 HookBus/reducer registry，让扩展 reducer 明确 source metadata 与 merge/cancel 语义

### DC-130

- 日期：2026-06-13
- 变更主题：Durable operation log reducer Slice 1 落地
- 变更摘要：
  - 接受 Pi-inspired minimal Core 的第一实现切片：先让 session transcript 具备可 reducer 的 operation lifecycle 状态，而不是直接重写 `QueryEngine` 或提取完整 `AgentKernel`
  - 新增 `src/embedagent/session_operation_log.py`，提供纯 `OperationLogReducer`、`OperationRecord` 与 `OperationLogState`
  - `SessionRestorer` 现在暴露 `operation_state`，并只对严格恢复已消费的 transcript 前缀做 operation reducer，避免损坏尾部参与状态推断
  - reducer 兼容现有 `step_started`、`tool_call`、`tool_result`、`loop_transition` 事件，也支持新的显式 `operation_started`、`operation_finished`、`operation_interrupted` 事件
  - `QueryEngine` 在保持旧 transcript 事件不变的前提下，附加写入 schema_v2 operation lifecycle 事件；未完成 operation 在 restore 语义中默认标为 `interrupted` 且 `retryable=false`
- 影响范围：
  - `src/embedagent/session_operation_log.py`
  - `src/embedagent/session_restore.py`
  - `src/embedagent/query_engine.py`
  - `tests/test_session_operation_log.py`
  - `tests/test_session_restore.py`
  - `tests/test_query_engine_refactor.py`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/archive/phase-a-durable-operation-log/2026-06-13-durable-operation-log.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `docs/archive/phase-a-durable-operation-log/2026-06-13-durable-operation-log.md`
- 是否需要 ADR：`否，本次是目标蓝图下的增量实现切片；完整 AgentKernel lifecycle boundary 提取前再评估 ADR`
- 后续动作：
  - 将 turn lifecycle、pending interaction lifecycle 与 workflow patch 事件纳入显式 operation/log lifecycle
  - 评估是否把 operation_state 投影到 session snapshot / diagnostics，供前端或恢复诊断消费
  - 继续保持旧 transcript 事件作为 session replay/history 输入，但 operation state 必须来自显式 lifecycle 事件

### DC-129

- 日期：2026-06-13
- 变更主题：Pi-inspired minimal Agent Core 长期蓝图建立
- 变更摘要：
  - 新增 `docs/pi-inspired-agent-core-blueprint.md`，将下一阶段架构程序明确为同时学习 Pi 的功能设计与架构哲学
  - 功能设计学习重点包括 extensions、resources、durable sessions、compaction、commands、model capability metadata、observability 与 self-extension workflows
  - 架构哲学学习重点包括 minimal Agent Core、capability registration、source-aware event reducers、explicit turn snapshots、save points 与 replaceable workflow packages
  - 明确当前 self-extensible Agent Core baseline 仍然有效；`AgentKernel`、`SessionLog`、`HookBus` 等是目标边界，不是已实现公共 API
  - 后续改造按 durable operation log / reducers、source-aware HookBus、AgentKernel lifecycle extraction、default C/C++ workflow package、self-extension authoring loop、offline validation 分阶段推进
  - 继续保持 offline、Windows 7、Python 3.8、C/C++ first、no Docker/WSL/VS Code runtime dependency、no online registry、no dependency installation、no plugin marketplace、no built-in tool replacement by project-local code 的产品约束
- 影响范围：
  - `README.md`
  - `AGENTS.md`
  - `docs/README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
- 关联文档：
  - `docs/pi-inspired-agent-core-blueprint.md`
- 是否需要 ADR：`否，本次是长期目标蓝图与路线图更新；后续 hard-to-reverse implementation slice 需要按具体设计判断是否新增 ADR`
- 后续动作：
  - 为 durable operation log / reducer 第一阶段补设计与测试计划
  - 将后续 HookBus、AgentKernel、default C/C++ workflow package 等改造拆成可独立验证的小切片
  - 每个实现切片都必须保持当前 hosted C/C++ 行为、Win7/offline 约束和 source-of-truth docs 同步

### DC-128

- 日期：2026-06-12
- 变更主题：Self-extensible Agent Core documentation cutover Slice 6 落地
- 变更摘要：
  - 接受 documentation cutover 作为 self-extensible Agent Core 的第六实现 slice
  - 将 active source-of-truth docs 与 module docs 同步到当前官方口径：local offline self-extension 已是架构 baseline，默认 C/C++ harness 是 hosted paths 安装的 bundled built-in extension，`QueryEngine` 保持 session facade
  - 明确 resource reload 与 project-local Python extension loading 是两条不同路径：前者 file-only，后者 manifest-gated hosted adapter loading
  - 将完成的 self-extensible slice-local materials 从 active `docs/superpowers/` 迁入 `docs/archive/self-extensible-agent-core/`
  - 继续保持 remote registry、plugin marketplace、online install、dependency installation、built-in tool replacement 与 multi-agent orchestration 不在当前产品范围内
- 影响范围：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/modules/`
  - `docs/archive/self-extensible-agent-core/README.md`
  - `docs/README.md`
  - `docs/development-tracker.md`
- 关联文档：
  - `docs/archive/self-extensible-agent-core/2026-06-12-self-extensible-documentation-cutover-design.md`
  - `docs/archive/self-extensible-agent-core/2026-06-12-self-extensible-documentation-cutover-plan.md`
- 是否需要 ADR：`否，属于已批准 self-extensible Agent Core 方向的第六实现 slice`
- 后续动作：
  - 后续如果新增 extension authoring guide 或 sample extension，应作为独立 slice 设计，不混入本次 documentation cutover
  - 继续通过 active docs 与 module docs 维护 local offline self-extension 的边界，避免重新把 marketplace 或 dependency installation 写入产品 baseline

### DC-127

- 日期：2026-06-12
- 变更主题：QueryEngine slimming Slice 5 落地
- 变更摘要：
  - 接受 QueryEngine slimming 作为 self-extensible Agent Core 的第五实现 slice
  - 新增 `src/embedagent/agent_extension_host.py`，集中 QueryEngine-side extension context/event 构造、workflow state 初始化、context patch、dynamic tool registration、extension-aware active schema projection、tool-call hook、tool-result hook、workflow patch 与 extension-owned tool handling
  - 新增 `src/embedagent/agent_tool_action_service.py`，集中非 LLM tool action execution，包括 active-tool gating、extension pre/post hooks、`PermissionPolicy`、path write guards、runtime dispatch 与 extension-owned tools
  - 新增 `src/embedagent/agent_loop.py`，作为 `QueryEngine` 背后的 turn-loop 边界
  - `QueryEngine` 保持 session-scoped facade、transcript/session mutation owner 与 interaction suspend/resume owner；兼容 `engine.extension_manager` 仍指向共享 manager
  - bare `QueryEngine` 继续使用空 extension host，不激活默认 C harness workflow tools；hosted product paths 仍通过 `default_extensions.py` 与共享 `ExtensionManager` 获得默认 C/C++ 行为
- 影响范围：
  - `src/embedagent/query_engine.py`
  - `src/embedagent/agent_extension_host.py`
  - `src/embedagent/agent_tool_action_service.py`
  - `src/embedagent/agent_loop.py`
  - `tests/test_dynamic_tool_registration.py`
  - `tests/test_capability_extensions.py`
  - `tests/test_query_engine_refactor.py`
  - `tests/test_workflow_extensions.py`
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
  - `docs/development-tracker.md`
  - `docs/archive/self-extensible-agent-core/2026-06-12-query-engine-slimming-design.md`
  - `docs/archive/self-extensible-agent-core/2026-06-12-query-engine-slimming-plan.md`
- 是否需要 ADR：`否，属于已批准 self-extensible Agent Core 方向的第五实现 slice`
- 后续动作：
  - 继续保持 remote registry、plugin marketplace、dependency installation、built-in tool replacement 与 multi-agent orchestration 不在当前产品范围内
  - 后续如果继续压缩 `QueryEngine`，应沿 `AgentLoop` / `AgentToolActionService` / `AgentExtensionHost` 边界推进，而不是恢复 direct hook dispatch

### DC-126

- 日期：2026-06-08
- 变更主题：Project-local Python extensions Slice 4 落地
- 变更摘要：
  - 接受 manifest-gated project-local Python extension loading 作为 self-extensible Agent Core 的第四实现 slice
  - 新增 `src/embedagent/project_extensions.py`，发现并验证 `.embedagent/extensions/<name>/extension.json`
  - `enabled` 默认 false；启用 manifest 必须声明 permissions，并且 entrypoint 必须保持在 extension 目录内
  - hosted `InProcessAdapter` 在默认扩展装配后加载项目扩展，并把成功加载的对象注册到同一个共享 `ExtensionManager`
  - loader diagnostics 会进入 `project_extension_state`、`extensions.project_extensions` session snapshot state 和 `extension_diagnostics`
  - project extension dynamic tools 继续走 `ToolRuntime` catalog metadata、`ExtensionManager.allowed_tool_names(...)` active-tool gating 与 `PermissionPolicy`
  - 不引入依赖安装、远程 registry、plugin marketplace、built-in tool replacement 或权限绕行
- 影响范围：
  - `src/embedagent/project_extensions.py`
  - `src/embedagent/extensions.py`
  - `src/embedagent/inprocess_adapter.py`
  - `tests/test_project_extensions.py`
  - hosted adapter session snapshot contract
  - frontend extension diagnostics contract
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/development-tracker.md`
  - `docs/archive/self-extensible-agent-core/2026-06-05-project-local-python-extensions-design.md`
  - `docs/archive/self-extensible-agent-core/2026-06-05-project-local-python-extensions.md`
- 是否需要 ADR：`否，属于已批准 self-extensible Agent Core 方向的第四实现 slice`
- 后续动作：
  - 继续保持依赖安装、远程 registry、plugin marketplace、built-in tool replacement 与 multi-agent orchestration 不在当前产品范围内
  - 后续如需 project extension reload 或 frontend extension inspector，应单独设计权限和可观测性边界

### DC-125

- 日期：2026-06-05
- 变更主题：Local resource reload Slice 3 落地
- 变更摘要：
  - 接受 file-only local resources 作为 self-extensible Agent Core 的第三实现 slice
  - 新增 `src/embedagent/local_resources.py`，发现 workspace-bound `.embedagent/skills`、`.embedagent/prompts` 与 `.embedagent/recipes` 资源
  - `.embedagent/recipes/*.json` 进入既有 workspace recipe contract，继续通过 `list_recipes` / `run_recipe` 使用
  - `ToolRuntime.reload_resources()`、`InProcessAdapter.reload_resources(...)`、`/resources reload` 与 `POST /api/sessions/{session_id}/resources/reload` 形成显式刷新路径
  - session-scoped reload 写入 `resource_discovered` / `resource_reloaded` transcript events，并把最新状态投影到 `Session.workflow_state["extensions"]["local_resources"]`
  - skills/prompts 只作为文件资源发现，不执行 project-local Python code
- 影响范围：
  - `src/embedagent/local_resources.py`
  - `src/embedagent/workspace_recipes.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/tools/_base.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/protocol/__init__.py`
  - `src/embedagent/frontend/gui/backend/server.py`
  - slash command contract
  - frontend/core API contract
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
  - `docs/mode-schema.md`
  - `docs/permission-model.md`
  - `docs/agent-harness-v2.md`
  - `docs/development-tracker.md`
  - `docs/superpowers/plans/2026-06-05-local-resource-reload.md`
- 是否需要 ADR：`否，属于已批准 self-extensible Agent Core 方向的第三实现 slice`
- 后续动作：
  - 归档已完成 Slice 1/2 design 与 plan 文档
  - project-local Python extension loading 的离线安全边界已由 DC-126 收口

### DC-124

- 日期：2026-06-04
- 变更主题：Dynamic tool registration Slice 2 落地
- 变更摘要：
  - 接受 dynamic in-process tool registration 作为 self-extensible Agent Core 的第二实现 slice
  - `ToolRuntime` 现在是 source-aware registry，in-process extensions 可注册带 source metadata 的 `ToolDefinition`
  - `QueryEngine` 与 `InProcessAdapter` 在 schema/catalog 边界前同步 extension tool registration，动态工具仍必须通过 `ExtensionManager.allowed_tool_names(...)` 激活后才可见
  - `PermissionPolicy` 通过 runtime catalog metadata 分类动态工具，privileged dynamic tools 继续走同一 ask/rule 路径
  - built-in tool replacement 当时保持未启用；project-local Python loading 后续已由 DC-126 收口，file-only resource reload 已在 Slice 3 落地
- 影响范围：
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/extensions.py`
  - `src/embedagent/permissions.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/inprocess_adapter.py`
  - frontend tool catalog contract
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
  - `docs/archive/self-extensible-agent-core/2026-06-04-dynamic-tool-registration-design.md`
  - `docs/archive/self-extensible-agent-core/2026-06-04-dynamic-tool-registration.md`
- 是否需要 ADR：`否，属于已批准 self-extensible Agent Core 方向的第二实现 slice`
- 后续动作：
  - 设计并实现 project-local extension loading 的离线安全边界
  - 评估是否允许 built-in tool replacement，并单独设计权限边界

### DC-123

- 日期：2026-06-04
- 变更主题：Capability extension contract Slice 1 落地
- 变更摘要：
  - 接受 Pi-inspired microkernel 方向，将 `ExtensionManager` 从默认 C/C++ workflow boundary 推进为共享 in-process capability boundary
  - 新增通用 extension diagnostics、resource discovery contract、context hook、tool-call/tool-result hooks 与 session snapshot diagnostics
  - 默认 C/C++ harness 行为保持通过 bundled workflow extension 接入，`QueryEngine` 继续不直接 import/构造默认 harness extension
  - project-local Python extension loading 当时保留为显式后续 slice，后续已由 DC-126 收口；dynamic tool registration 与 file-only resource reload 已在后续 slices 落地
- 影响范围：
  - `src/embedagent/extensions.py`
  - `src/embedagent/query_engine.py`
  - `src/embedagent/session_projector.py`
  - `src/embedagent/inprocess_adapter.py`
  - frontend snapshot contract
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/tool-contracts.md`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
  - `docs/archive/self-extensible-agent-core/2026-06-04-self-extensible-agent-core-design.md`
  - `docs/archive/self-extensible-agent-core/2026-06-04-capability-extension-contract.md`
- 是否需要 ADR：`否，属于已批准 self-extensible Agent Core 方向的第一实现 slice`
- 后续动作：
  - 设计并实现 project-local extension loading 的离线安全边界
  - 基于 local resource reload 结果评估是否需要 frontend resource inspector

### DC-122

- 日期：2026-06-04
- 变更主题：GUI 默认入口与任务词汇收口到正式模式协议
- 变更摘要：
  - GUI backend 的 `POST /api/sessions` 默认 mode 改为共享 `DEFAULT_MODE == "explore"`，与正式模式入口保持一致
  - GUI resume 路由默认传空 mode，让 core adapter 沿用 restored session mode，不再无意覆盖为 `build`
  - GUI webapp 新增前端默认 mode 常量，session normalize、runtime projector、session list fallback 均使用 `explore` 兜底
  - GUI task 面板和样式从 `todo-*` / `tasks.todo` 清理为 `task-*` / `tasks.pending`，并移除旧 `mode-code` 样式残留
  - 已重建 `src/embedagent/frontend/gui/static/`，使实际 GUI serve 的静态产物与源码一致
- 影响范围：
  - GUI session create / resume 默认行为
  - GUI task inspector 命名与样式
  - frontend protocol mode vocabulary
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/frontend-protocol.md`
- 是否需要 ADR：`否，属于既定模式/前端词汇 cutover 的收口修正`
- 后续动作：
  - clean Windows 7 GUI smoke 仍作为外部目标机 gate
  - 真实 C/C++ 工程 GUI 验证仍作为产品 gate

### DC-121

- 日期：2026-06-03
- 变更主题：Workflow extension 本机剩余边界清理
- 变更摘要：
  - 新增 `ExtensionManager.load_session_tasks(...)` 作为 frontend task snapshot fallback 的 extension hook
  - 默认 C harness extension 继续读取自己的 task snapshot，返回 `count/tasks/path/session_id` 前端 payload
  - `InProcessAdapter.list_tasks()` 对 active session 仍优先读取 `Session.workflow_state["workflow"]`，对 inactive session 改为通过共享 `ExtensionManager` 获取 fallback payload，不再直接 import `embedagent.harness.task_store`
  - 新增边界测试防止 adapter 重新直连 harness task store，并保留 active session task snapshot path 行为断言
  - `docs/guides/configuration-guide.md` 已从 pre-cutover 历史指南改写为当前正式配置指南，使用 `explore/spec/build/debug/verify` 与 `task_status` 口径，不再提供 `code` / `manage_todos` 当前使用示例
- 影响范围：
  - frontend task read model fallback
  - workflow extension hook surface
  - configuration guide handoff clarity
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/archive/workflow-extension-boundary/2026-05-28-remaining-workflow-extension-migration-plan.md`
  - `docs/guides/configuration-guide.md`
- 是否需要 ADR：`否，属于既定 workflow extension boundary 的本机剩余清理`
- 后续动作：
  - Win7 clean-machine unpack-and-run smoke 仍作为外部 release gate
  - 真实 C/C++ 工程验证仍作为外部产品验证 gate

### DC-120

- 日期：2026-05-29
- 变更主题：Workflow extension release validation 收口
- 变更摘要：
  - 恢复官方 harness pytest marker 覆盖，`uv run pytest tests/ -m harness -v` 不再选空，现在覆盖 task_graph、phase_engine、harness runner、prompt stack 与 harness injection 组件测试
  - workflow extension repo-side 验证通过：fast suite 为 685 passed / 11 deselected，focused C/C++ build/debug/verify workflow 回归为 15 passed，harness suite 为 23 passed / 673 deselected
  - 当前分支 release bundle 已用本机离线 cache、vendored site-packages 与 LLVM root 重新组装，`scripts/validate-offline-bundle.ps1 -RequireComplete` 通过，结果为 59 pass / 0 warn / 0 fail
  - `scripts/check-bundle-dependencies.py` 对该 bundle 全部通过，`scripts/package.ps1 verify -Profile release -Json` 返回 `final_status == READY`
  - 修复 `scripts/prepare-offline.ps1` 的操作指南 staging 源路径，使 bundle 从 active `docs/guides/` 获取 configuration / Win7 preflight / intranet deployment / Win7 GUI validation 文档
  - clean Windows 7 unpack-and-run smoke 尚未执行，必须在 release cut 前作为目标机 gate 补跑
- 影响范围：
  - workflow extension release validation evidence
  - harness pytest marker coverage
  - packaging / Win7 release gate handoff
  - offline bundle documentation staging
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/archive/workflow-extension-boundary/2026-05-28-remaining-workflow-extension-migration-plan.md`
  - `docs/archive/workflow-extension-boundary/2026-05-28-workflow-extension-migration-handoff.md`
- 是否需要 ADR：`否，属于 release validation 结果与测试门禁修复记录`
- 后续动作：
  - 在 clean Windows 7 目标机上运行 bundle unpack-and-run smoke，并记录 renderer/runtime/toolchain 结果

### DC-119

- 日期：2026-05-29
- 变更主题：Workflow extension boundary plans 归档
- 变更摘要：
  - 已完成的 workflow-extension boundary slice1-11、runtime/default-extension/session/task-status plans 和 implementation handoff 迁入 `docs/archive/workflow-extension-boundary/`
  - 新增 `docs/archive/workflow-extension-boundary/README.md`，说明 durable architecture truth 的当前位置
  - 活动 `docs/superpowers/plans/` 仅保留 remaining workflow-extension validation plan
- 影响范围：
  - docs archive layout
  - workflow extension migration handoff discovery
  - active planning surface
- 关联文档：
  - `docs/archive/workflow-extension-boundary/`
  - `docs/archive/workflow-extension-boundary/2026-05-28-remaining-workflow-extension-migration-plan.md`
- 是否需要 ADR：`否，属于完成切片归档`

### DC-118

- 日期：2026-05-29
- 变更主题：Default extension configuration 决策关闭
- 变更摘要：
  - 审计 `build_default_extension_set(...)`、`ExtensionManager`、`CHarnessWorkflowExtension` 与 adapter/engine 构造路径
  - 当前 hosted product paths 继续通过 `src/embedagent/default_extensions.py` 装配 bundled C harness
  - bare `QueryEngine` 保持空 `ExtensionManager` 默认值，需要默认 C/C++ 行为的 host 必须显式注入 extension manager
  - 不新增 project-local extension discovery、remote registry、plugin marketplace 或 multi-agent orchestration layer
  - 未发现需要新增 adapter constructor seam 的当前产品/测试需求
- 影响范围：
  - hosted runtime default extension assembly
  - bare QueryEngine construction contract
  - workflow extension migration scope control
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-workflow-extension-migration-handoff.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`否，属于既定边界配置决策的文档收口`

### DC-117

- 日期：2026-05-29
- 变更主题：Allowed-tool runtime wrapper 删除
- 变更摘要：
  - 删除 `ToolRuntime.allowed_tool_names()`
  - 删除 `OfficialRuntimeModes.allowed_tool_names()`
  - `TurnOrchestrator` 改为接收注入的 `allowed_tool_names` policy，不再调用 runtime wrapper
  - `QueryEngine` 将 extension-aware `_allowed_tools_for_mode(...)` 传入 turn orchestration
  - runtime tests 删除 wrapper 兼容断言，新增源码边界测试防止 alias 回流
- 影响范围：
  - core turn orchestration mode gating
  - runtime public compatibility surface
  - workflow extension active-tool boundary
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-workflow-extension-migration-handoff.md`
  - `docs/tool-contracts.md`
  - `docs/mode-schema.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`否，属于既定 workflow extension migration 的 runtime wrapper cleanup`

### DC-116

- 日期：2026-05-29
- 变更主题：ToolRuntime schema projection alias 删除
- 变更摘要：
  - 删除 `ToolRuntime.schemas_for_mode()`
  - `ToolRuntime.schemas_for(mode, workflow_state, tool_names=...)` 成为唯一 runtime schema projection entry point
  - 测试调用点和 boundary probe 均改为 `schemas_for(...)`
  - Durable docs 不再描述 `schemas_for_mode()` 兼容入口
- 影响范围：
  - tool runtime public schema projection surface
  - QueryEngine explicit active-tool schema path
  - workflow extension boundary cleanup
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-workflow-extension-migration-handoff.md`
  - `docs/tool-contracts.md`
  - `docs/mode-schema.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`否，属于既定 workflow extension migration 的 runtime alias cleanup`

### DC-115

- 日期：2026-05-29
- 变更主题：Session task graph compatibility mirror 删除
- 变更摘要：
  - 删除 `src/embedagent/session.py` 的 `Session.task_graph` dataclass 字段和 `_empty_task_graph()` lazy factory
  - 新增 `src/embedagent/harness/session_graph_state.py`，由默认 C harness workflow extension 保存 session-scoped `TaskGraph`
  - `HarnessRunner.update_task_graph(...)` 改为接收并返回 harness-owned graph，不再读写 `Session`
  - `CHarnessWorkflowExtension` 负责把 harness-owned graph 投影到 `Session.workflow_state["workflow"]`
  - focused tests 改为确认 workflow-neutral modules 和 frontend read models 只消费 generic workflow projection
- 影响范围：
  - Agent Core session schema
  - default C harness task graph ownership
  - workflow extension boundary cleanup
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-workflow-extension-migration-handoff.md`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`否，属于既定 workflow extension migration 的兼容镜像删除切片`

### DC-114

- 日期：2026-05-29
- 变更主题：HarnessStateSynchronizer 兼容门面删除
- 变更摘要：
  - 删除 `src/embedagent/services/harness_state_synchronizer.py`
  - `src/embedagent/services/__init__.py` 不再 lazy export `HarnessStateSynchronizer`
  - focused service tests 改为直接覆盖 `CHarnessWorkflowExtension.refresh_managed_session()` 与 `build_mode_context()` 正式路径
  - product harness refresh 与 task snapshot persistence 只保留默认 C harness workflow extension 入口
- 影响范围：
  - services public import surface
  - default C harness refresh ownership
  - workflow extension boundary cleanup
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-workflow-extension-migration-handoff.md`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`否，属于既定 workflow extension migration 的兼容门面删除切片`

### DC-113

- 日期：2026-05-28
- 变更主题：Turn orchestrator task-status projection 第十一切片
- 变更摘要：
  - `src/embedagent/strategies/turn_orchestrator.py` 的 legacy `task_status` 兼容路径不再读取 `Session.task_graph`
  - `task_status` observation 现在从 `Session.workflow_state["workflow"]` 的 `summary`、`items` 和 `metadata` 投影生成
  - 新增行为测试与源码边界测试，防止 workflow-neutral strategy 重新依赖 harness task graph internals
- 影响范围：
  - extracted core strategy task-status path
  - generic workflow projection read model
  - future `Session.task_graph` shrink/removal path
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-turn-orchestrator-task-status-projection-slice11.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`否，属于 workflow extension boundary 的读模型收缩切片`

### DC-112

- 日期：2026-05-28
- 变更主题：Session task graph lazy boundary 第十切片
- 变更摘要：
  - `src/embedagent/session.py` 不再在模块导入期 import `embedagent.harness.task_graph.TaskGraph`
  - `Session.task_graph` 继续保留为默认 C harness 兼容镜像，但通过 lazy default factory 在实例化 `Session` 时按需创建
  - 新增导入边界回归，确认 `import embedagent.session` 不会急切加载 harness task graph internals
- 影响范围：
  - Agent Core session import boundary
  - default C harness compatibility mirror
  - future `Session.task_graph` shrink/removal path
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-session-task-graph-lazy-boundary-slice10.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`否，属于 workflow extension boundary 的导入期耦合收缩切片`

### DC-111

- 日期：2026-05-28
- 变更主题：Harness workflow projection builder 第九切片
- 变更摘要：
  - 新增 `src/embedagent/harness/workflow_projection.py`，集中构造默认 C harness 的通用 workflow payload
  - `CHarnessWorkflowExtension._sync_workflow_state()` 不再内联组装 `Session.workflow_state["workflow"]`，而是委托 `build_c_harness_workflow_projection()`
  - `TaskGraph` 仍作为默认 harness 兼容镜像保留在 harness-owned 路径内，core/frontend 继续只消费通用 workflow projection
- 影响范围：
  - default C harness workflow state adapter
  - `Session.workflow_state["workflow"]` payload ownership
  - future `Session.task_graph` compatibility-mirror shrink path
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-harness-workflow-projection-builder-slice9.md`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
- 是否需要 ADR：`否，属于 workflow extension boundary 的投影适配器抽离切片`

### DC-110

- 日期：2026-05-28
- 变更主题：Default harness extension factory 第八切片
- 变更摘要：
  - 新增 `src/embedagent/default_extensions.py`，作为 hosted runtime 默认扩展装配层
  - `QueryEngine` 不再 import 或构造 `CHarnessWorkflowExtension`；未传入 `extension_manager` 时只创建空 `ExtensionManager`
  - `InProcessAdapter` 继续默认启用 bundled C harness，但通过 `build_default_extension_set()` 获取共享 manager 与兼容 `harness_workflow`
  - 直接构造 `QueryEngine` 且需要默认 C/C++ harness 行为的调用方和测试必须显式传入默认 extension manager
- 影响范围：
  - QueryEngine workflow extension dependency boundary
  - hosted runtime default extension assembly
  - direct QueryEngine test setup
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-default-harness-extension-factory-slice8.md`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/agent-harness-v2.md`
- 是否需要 ADR：`否，属于 workflow extension boundary 的默认装配外移切片`

### DC-109

- 日期：2026-05-28
- 变更主题：Runtime schema boundary 第七切片
- 变更摘要：
  - `ToolRuntime.schemas_for_mode()` 已从默认 C harness 兼容投影降级为纯 mode-contract 兼容入口
  - `ToolRuntime.allowed_tool_names()` 与 `OfficialRuntimeModes.allowed_tool_names()` 现在只返回 `modes.py` 的 workflow-neutral allowed tools
  - 默认 C/C++ harness-aware schema 继续由 `ExtensionManager` active tool names 显式驱动，`QueryEngine` 和 frontend tool catalog 不依赖 runtime fallback
  - runtime tool catalog 仍注册 harness tools，避免破坏 extension-driven explicit schema projection 与 tool execution
- 影响范围：
  - ToolRuntime schema projection boundary
  - legacy runtime compatibility APIs
  - default C harness extension ownership docs
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-28-runtime-schema-boundary-slice7.md`
  - `docs/agent-harness-v2.md`
  - `docs/mode-schema.md`
  - `docs/tool-contracts.md`
  - `docs/overall-solution-architecture.md`
- 是否需要 ADR：`否，属于 workflow extension boundary 的 runtime 兼容入口收缩切片`

### DC-108

- 日期：2026-05-27
- 变更主题：Agent Core workflow extension boundary 第六切片
- 变更摘要：
  - `InProcessAdapter` 已不再直接导入或构造 `HarnessStateSynchronizer`
  - product harness refresh 与 task snapshot persistence 继续由 `CHarnessWorkflowExtension.refresh_managed_session()` 负责
  - `HarnessStateSynchronizer` 类与 `services.__all__` 导出保留，作为老导入和 focused service tests 的惰性兼容门面
  - 旧 characterization test 已更新为断言 adapter 不再拥有 `_harness_sync`
  - compat facade 的 `build_mode_context()` 可显式接收 mode，以便老调用方不必依赖 `ManagedSession.current_mode`
- 影响范围：
  - in-process adapter harness dependency surface
  - services compatibility facade boundary
  - workflow extension ownership docs
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-27-workflow-extension-boundary-slice6.md`
  - `docs/agent-harness-v2.md`
  - `docs/overall-solution-architecture.md`
- 是否需要 ADR：`否，属于内部兼容门面退场切片`

### DC-107

- 日期：2026-05-27
- 变更主题：Agent Core workflow extension boundary 第五切片
- 变更摘要：
  - `InProcessAdapter` 现在创建并持有一个共享 `ExtensionManager`
  - 默认 C harness extension 只注册一次，同时供 adapter harness refresh 兼容路径、session-scoped `QueryEngine` 和 frontend tool catalog visibility 使用
  - `_build_engine()` 显式把 adapter-owned `extension_manager` 传给 `QueryEngine`
  - `get_tool_catalog()` 通过共享 manager 读取 extension-active tools，不再直接调用 `harness_workflow.allowed_tool_names()`
- 影响范围：
  - in-process adapter / query engine wiring
  - frontend tool catalog extension visibility
  - future project-local extension readiness
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-27-workflow-extension-boundary-slice5.md`
  - `docs/frontend-protocol.md`
  - `docs/overall-solution-architecture.md`
- 是否需要 ADR：`否，属于内部 wiring 收口；project-local extension discovery 仍延后`

### DC-106

- 日期：2026-05-27
- 变更主题：Agent Core workflow extension boundary 第四切片
- 变更摘要：
  - 内置 mode `allowed_tools` 已收缩为 workflow-neutral permission/write contract，不再直接包含 `list_recipes`、`run_recipe`、`report_quality_v2`、`record_failing_evidence`、`task_status`
  - `verify` 的 mode contract 现在是只读探测工具 + `ask_user`，默认 C harness 的 verify 执行工具继续通过 extension pack 激活
  - `ToolRuntime.schemas_for()` 表示纯 mode contract；`schemas_for_mode()` 当时保留默认 harness 兼容投影，并返回 mode contract + harness pack 并集（该兼容投影已在 DC-109 降级为纯 mode-contract alias）
  - `CHarnessWorkflowExtension.allowed_tool_names()` 只返回 extension pack tools，mode contract 由调用方或 extension manager fallback 合并
  - frontend tool catalog visibility 改为 mode contract + 默认 C harness extension active tools，避免 UI 元数据依赖 mode schema 泄漏 harness 工具
- 影响范围：
  - mode schema / prompt allowed-tool presentation
  - ToolRuntime schema projection
  - InProcessAdapter frontend tool catalog
  - default C harness extension ownership
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-27-workflow-extension-boundary-slice4.md`
  - `docs/mode-schema.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
- 是否需要 ADR：`否，属于 workflow extension boundary 的局部实现切片`

### DC-105

- 日期：2026-05-27
- 变更主题：Agent Core workflow extension boundary 第三切片
- 变更摘要：
  - `QueryEngine._allowed_tools_for_mode()` 不再使用 `ToolRuntime.allowed_tool_names()` 作为 harness pack fallback，改为 mode permission contract + workflow extension active tools
  - `QueryEngine` 不再调用当时的 `ToolRuntime.schemas_for_mode()`，改为用 explicit active tool names 调用 runtime schema projection
  - `CORE_PACK` 已移除 `run_recipe`、`list_recipes`、`task_status` 等默认 harness workflow 工具
  - build/debug/verify packs 继续显式包含 harness 工具，保持当前 C/C++ 默认行为兼容
- 影响范围：
  - QueryEngine tool activation boundary
  - tooling pack definitions
  - default C harness extension ownership
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-27-workflow-extension-boundary-slice3.md`
  - `docs/tool-contracts.md`
  - `docs/mode-schema.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`否，属于 workflow extension boundary 的局部实现切片`
- 后续动作：
  - 继续收缩 `modes.py` 中的 harness tool 列表，使 mode schema 更接近纯权限/写入边界
  - `ToolRuntime.schemas_for_mode()` 的兼容投影降级已在 DC-109 完成，当前仅保留纯 mode-contract alias

### DC-104

- 日期：2026-05-26
- 变更主题：Agent Core workflow extension boundary 第二切片
- 变更摘要：
  - `SessionSnapshotProjector` 不再直接读取 `task_graph`，legacy snapshot 字段改由 `Session.workflow_state["workflow"]` 投影
  - `InProcessAdapter.get_session_snapshot()` 不再在读路径调用 `HarnessRunner.describe_mode()`
  - `InProcessAdapter.list_tasks()` 的 live session 路径改为读取 workflow projection items，离线 session 仍回落到持久化 task snapshot
  - `CHarnessWorkflowExtension` 新增 managed-session refresh 路径，负责同步 workflow projection 与保存 task snapshot
  - `HarnessStateSynchronizer` 保留为 services 兼容门面，但实际刷新逻辑委托给默认 C harness extension
  - `InProcessAdapter` 不再直接 import 或构造 `HarnessRunner`
- 影响范围：
  - session snapshot / frontend task projection
  - default C harness workflow extension
  - in-process adapter harness boundary
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-26-workflow-extension-boundary-slice2.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`否，属于 DC-103 已批准架构反转的第二切片`
- 后续动作：
  - 继续把 harness-specific tool pack 从 core pack 中剥离
  - 等兼容测试和下游导入收敛后，进一步删除或缩小 `HarnessStateSynchronizer`

### DC-103

- 日期：2026-05-26
- 变更主题：Agent Core workflow extension boundary 第一切片
- 变更摘要：
  - 新增 `src/embedagent/extensions.py`，提供本地 in-process workflow extension contract 与 manager
  - 新增 `src/embedagent/harness/extension.py`，把当前 C/C++ harness 包装为默认内置 workflow extension
  - `QueryEngine` 不再直接 import 或实例化 `TaskGraph`，harness prompt 注入、任务初始化、工具激活与 `task_status` 入口开始经由 extension manager
  - `Session.workflow_state` 已作为通用 workflow state carrier 落地，`Session.task_graph` 暂保留为默认 harness 兼容镜像
  - `StreamingToolExecutor` 改为窗口式并行调度，修复并行只读批次中失败后未启动兄弟任务抢跑的问题
- 影响范围：
  - Agent Core / QueryEngine workflow boundary
  - default C harness integration
  - session workflow state
  - parallel tool execution determinism
  - source-of-truth architecture docs
- 关联文档：
  - `docs/archive/workflow-extension-boundary/2026-05-26-workflow-extension-boundary-slice1.md`
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/agent-harness-v2.md`
- 是否需要 ADR：`否，先作为已批准 architecture reversal 的第一切片落地；后续若开放 project-local extensions 再补 ADR`
- 后续动作：
  - 已在 DC-104 中完成 `SessionSnapshotProjector` 与 live frontend task API 向 `workflow_state` 投影迁移
  - 已在 DC-104 中将 `HarnessStateSynchronizer` 降为默认 harness extension 的兼容门面
  - 待兼容投影稳定后，再把 harness-specific tools 从 core pack 中迁出

### DC-102

- 日期：2026-04-09
- 变更主题：归档遗留活动文档并下沉操作指南
- 变更摘要：
  - 将 10 份 superseded 文档迁入 docs/archive/ 对应主题目录
  - 将 6 份 packaging/Win7 操作文档迁入 docs/archive/packaging-pipeline-redesign/
  - 将 configuration-guide.md、llm-adapter.md 下沉为 docs/guides/ 操作指南
  - 更新 docs/modules/packaging-and-deployment.md 以吸纳 bundle 布局、组件清单和 GUI 验收标准
  - 更新 docs/README.md 模块列表并新增 guides 索引
- 影响范围：
  - docs/README.md
  - docs/modules/packaging-and-deployment.md
  - docs/guides/
  - docs/archive/gui-redesign/
  - docs/archive/context-loop/
  - docs/archive/agent-harness-v2/
  - docs/archive/packaging-pipeline-redesign/
  - docs/archive/tui-information-architecture/
  - docs/archive/tool-design/
  - docs/archive/clang-integration/
  - docs/archive/phase6-validation/
- 关联文档：
  - docs/archive/documentation-governance-baseline/2026-04-08-documentation-governance-baseline-design.md
- 是否需要 ADR：否，先作为文档治理基线实施
- 后续动作：
  - 继续按 doc-impact-first 工作流执行后续切片
  - 定期复核 archive README 索引与活动文档死链


### DC-101

- 日期：2026-04-09
- 变更主题：补齐剩余模块文档并修正代码-文档映射准确性
- 变更摘要：
  - 新建 `docs/modules/protocol-and-core.md`、`frontend-tui.md`、`frontend-gui.md`、`packaging-and-deployment.md`
  - 修正 `docs/modules/tools-and-tooling.md` 中不准确的 tool pack 类引用
  - 更新 `docs/modules/README.md` 与 `docs/references/code-doc-matrix.md` 以反映新增模块
- 影响范围：
  - `docs/modules/protocol-and-core.md`
  - `docs/modules/frontend-tui.md`
  - `docs/modules/frontend-gui.md`
  - `docs/modules/packaging-and-deployment.md`
  - `docs/modules/tools-and-tooling.md`
  - `docs/modules/README.md`
  - `docs/references/code-doc-matrix.md`
  - `docs/development-tracker.md`
- 关联文档：
  - `docs/archive/documentation-governance-baseline/2026-04-08-documentation-governance-baseline-design.md`
- 是否需要 ADR：`否，先作为文档治理基线实施`
- 后续动作：
  - 继续推进 Batch B：归档遗留活动文档并下沉操作指南

### DC-100

- 日期：2026-04-08
- 变更主题：建立文档治理基线与 `superpowers -> 全局文档 -> archive` 回写闭环
- 变更摘要：
  - 建立 `docs/` 下的治理规则、工作流、术语和模板体系
  - 明确 `superpowers` 文档是当前切片说明书，而不是长期架构真相
  - 建立核心模块文档入口和代码-文档映射规则
- 影响范围：
  - `README.md`
  - `AGENTS.md`
  - `docs/README.md`
  - `docs/documentation-governance.md`
  - `docs/documentation-style-guide.md`
  - `docs/workflows/`
  - `docs/references/`
  - `docs/templates/`
  - `docs/modules/`
- 关联文档：
  - `docs/archive/documentation-governance-baseline/2026-04-08-documentation-governance-baseline-design.md`
- 是否需要 ADR：`否，先作为文档治理基线实施`
- 后续动作：
  - 继续补齐协议、前端、交付模块文档
  - 分批归档 superseded 活动文档

### DC-099

- 日期：2026-04-08
- 变更主题：Agent core cutover 相关 superpowers 文档归档
- 变更摘要：
  - `agent-core-cutover` 相关的 design / plan / review / implementation review / follow-up plan 已从活动 `docs/superpowers/` 迁入 `docs/archive/agent-core-cutover/`
  - 新增 `docs/archive/agent-core-cutover/README.md` 作为归档索引，说明本轮 cutover 与 follow-up 已完成
  - 活动文档只保留仍在推进中的主题，已关闭切片不再占用 `docs/superpowers/` 入口
- 影响范围：
  - `docs/archive/agent-core-cutover/`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/agent-core-cutover/README.md`
- 是否需要 ADR：`否，属于文档治理收尾`
- 后续动作：
  - 后续类似已关闭切片继续保持“活动入口最小化，archive 留痕”的治理方式

### DC-098

- 日期：2026-04-08
- 变更主题：Agent core ownership cutover，收拢 session owner / step anchor / resume pipeline
- 变更摘要：
  - `QueryEngine` 已改为 per-session 常驻执行 owner，负责 turn/step/interactions 与 transcript mutation；`InProcessAdapter` 降为 host/bridge
  - frontend live events 已直接复用 engine-issued `step_id`，adapter 不再生成第二套 step identity
  - pending permission/user-input 的恢复已重新进入统一 action pipeline，不再直接旁路到 `tools.execute(...)`
  - `TaskGraph` 已进入 `Session` 真相层，`SessionSnapshotProjector` 已抽为无副作用 projector，`task_status` 前端元数据正式统一为 `tasks/task`
  - `TranscriptStore` / `SessionTimelineStore` 追加序号已切到缓存分配，运行时残留 `todos.py` 已删除
- 影响范围：
  - query engine / in-process adapter / session runtime ownership
  - interaction resume correctness
  - frontend event anchors / tool catalog metadata
  - task projection / workspace profile wording / runtime cleanup
  - transcript/timeline append hot path
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/mode-schema.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，属于已批准 cutover spec 的实施收口`
- 后续动作：
  - 继续删除剩余非正式 shell-only labels / manual samples
  - 在真实 C 工程和 Win7 bundle 上继续验证恢复、bootstrap 和长会话性能

### DC-097

- 日期：2026-04-07
- 变更主题：已完成切片的 plan/spec/review/handoff 文档统一归档
- 变更摘要：
  - `gui-redesign`、`packaging-pipeline-redesign`、`agent-harness-v2`、`session-history-single-source-cutover` 相关的活动 plan/spec/review/handoff 文档已迁入新的 `docs/archive/<topic>/` 目录
  - `2026-04-02-full-transcript-persistence-design.md` 已补归档到 `docs/archive/transcript-truth-tool-result-cutover/`
  - `architecture_documentation_alignment_issues.md` 已迁入 `docs/archive/issues/`，活动 `docs/issues/` 入口不再保留已关闭审查报告
  - `development-tracker` 与 `design-change-log` 中引用旧活动路径的记录已同步改到 archive 路径，避免后续断链
- 影响范围：
  - `docs/archive/` 目录结构
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
- 关联文档：
  - `docs/archive/gui-redesign/README.md`
  - `docs/archive/packaging-pipeline-redesign/README.md`
  - `docs/archive/agent-harness-v2/README.md`
  - `docs/archive/session-history-single-source-cutover/README.md`
- 是否需要 ADR：`否，属于文档治理收口`
- 后续动作：
  - 后续新切片在确认实现完成后，继续保持“活动入口最小化、archive 留痕”的文档治理习惯

### DC-096

- 日期：2026-04-07
- 变更主题：GUI session history 切到 transcript-backed single source
- 变更摘要：
  - 新增 `session_history.py`，由 `SessionHistoryAssembler` 统一把 transcript-backed `Session` 序列化为 GUI history DTO
  - `QueryEngine` / `SessionRestorer` 现已持久化并恢复稳定 `ToolPresentationSnapshot`，历史工具卡片不再依赖 replay-log 元数据补洞
  - GUI session activation 已切到单一 `/api/sessions/{session_id}/bootstrap` 负载，包含 `snapshot + history + plan + permission_context + replay`
  - replay-log 结构化历史重建路径与 `/api/sessions/{session_id}/timeline` 已删除，raw fallback 不再是正式 GUI 状态
- 影响范围：
  - session history ownership / transcript restore
  - inprocess adapter / core / GUI backend bootstrap contract
  - webapp activation flow / reducer merge semantics / timeline integrity UI
  - adapter / GUI backend / webapp helper 回归测试
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/frontend-protocol.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，属于已批准 session-history cutover 的正式落地`
- 后续动作：
  - 继续用真实 C 工程和 Win7 bundle 场景验证 bootstrap / replay / transcript restore 性能与稳定性
  - 不再接受 replay-log 历史重建或 raw fallback 兼容层回流

### DC-095

- 日期：2026-04-07
- 变更主题：产品壳层正式化，移除剩余 legacy recipe/tool 词汇
- 变更摘要：
  - `workspace_recipes`、`recipe_ops`、`context`、`project_memory`、`workspace_intelligence` 和 frontend recipe UI 已移除 `legacy_tool_name`，并统一围绕 `run_recipe + recipe_action` 组织数据
  - 协议/core/backend 的旧 `list_files` 方法名已切为 `list_workspace_tree`，webapp tool label 也只保留正式工具词汇
  - 相关测试样本和 webapp helper fixtures 已全部切到正式 recipe 格式，`src/embedagent/` 已不再保留旧工具壳层词汇
- 影响范围：
  - workspace recipe normalization / resolve path
  - review / context / project memory / workspace intelligence
  - protocol/core/backend file tree contract
  - webapp store / fixtures / labels
- 关联文档：
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，属于 official cutover 的最终壳层清理`
- 后续动作：
  - 维持 merge 前全量回归与 webapp build 为准入门槛
  - 准备最终 merge/PR

### DC-094

- 日期：2026-04-06
- 变更主题：工程记忆与工程情报切到 `recipe_action` 正式语义
- 变更摘要：
  - `ProjectMemoryStore` 现在记录 `run_recipe` 的 `recipe_action`，并在 system message 中渲染 `[build]/[test]/[tidy]` 等正式类别，而不再把 `compile_project/run_tests` 当作用户可见语义
  - `WorkspaceIntelligence.DiagnosticsProvider` 已改按 `run_recipe` 的 `recipe_action` 和 `report_quality_v2` 聚合热点与质量门摘要，诊断首屏不再依赖旧 verify 工具名
  - `workspace_recipes` 的 history recipe id 已从 `history.<legacy_tool_name>.<n>` 收敛到 `history.<recipe_action>.<n>`
- 影响范围：
  - project memory recipe / known issue 选择逻辑
  - workspace intelligence diagnostics / recipe evidence
  - history recipe id 生成规则
  - query_engine_refactor / session_store / tools_package 回归测试
- 关联文档：
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，属于 official cutover 后的语义收口`
- 后续动作：
  - 继续切掉 frontend/protocol 中暴露给用户的 `list_files` 和旧 tool label
  - 再决定是否把 `workspace_recipes` 内部的 legacy 输入映射也进一步压缩

### DC-093

- 日期：2026-04-06
- 变更主题：runtime 与 permission 正式切断 legacy execute aliases
- 变更摘要：
  - `ToolRuntime` 现已删除 `_legacy_tools / _legacy_catalog` 双轨执行层，运行时只接受正式工具集合
  - `permissions.py` 已移除对 `list_files/search_text/manage_todos/compile_project/run_tests/...` 等旧工具名的正式分类，权限判断只围绕当前官方工具词汇展开
  - `file_ops.py` 已收缩为纯官方 `read_file/write_file/edit_file`；`build_ops.py`、`todo_ops.py` 与对应旧测试 `tests/test_todo_ops.py` 已删除
- 影响范围：
  - runtime execute path
  - permission category mapping
  - file/build/task legacy module deletion
  - focused runtime / adapter / architecture tests
- 关联文档：
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，属于 official cutover 后的核心壳层切断`
- 后续动作：
  - 继续切除 `project_memory.py`、`workspace_intelligence.py`、frontend/protocol 中仍把旧工具名当一等语义的兼容逻辑
  - 在最终 merge 前复跑更大范围回归，确认不再依赖任何 legacy execute alias

### DC-092

- 日期：2026-04-06
- 变更主题：删除死文件并把 `tools_v2` 正式迁入官方 `tools/` 包
- 变更摘要：
  - `tools_v2/` 中仍被正式 runtime 使用的 `discovery_ops`、`recipe_ops`、`session_ops` 已迁入 `src/embedagent/tools/`，`harness_runtime.py` 改为只从官方 `tools/` 包装载这些能力
  - 旧 `src/embedagent/tools_v2/*.py` 代码文件已删除，避免官方产品路径继续依赖带迁移语义的包名
  - 已完全无人引用的 `src/embedagent/loop.py` 已删除，`session.py` 与 `core/adapter.py` 中关于 `AgentLoop` 的说明同步收敛到当前 `InProcessAdapter / QueryEngine` 主链路
- 影响范围：
  - 官方工具模块布局
  - harness runtime 的导入边界
  - dead code / dead file 清理
  - focused runtime / adapter / architecture tests
- 关联文档：
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，属于 official cutover 后的结构收口`
- 后续动作：
  - 继续评估 `ToolRuntime` 中 legacy aliases、`permissions.py`、`project_memory.py`、`workspace_intelligence.py` 里的旧工具词汇是否继续下线
  - 若要宣布“无历史包袱”，还需完成这些仍在产品代码中的兼容逻辑切除

### DC-091

- 日期：2026-04-06
- 变更主题：merge 前稳定化收口，消除 mode-change phase 残留与 context 旧词汇主地位
- 变更摘要：
  - `set_session_mode()` 现会在刷新 Harness 状态前清空旧 `current_phase`，避免从 `build/debug` 切到 `verify` 等场景时把旧 phase 残留到新 mode snapshot
  - `Context` 高优先级工具和 reducer registry 已进一步收口到正式词汇：`run_recipe`、`report_quality_v2`、`task_status`；`manage_todos`、`compile_project`、`report_quality` 等旧工具不再作为 context 一等公民
  - `run_recipe` 现拥有专用 reducer，可保留 `recipe_action / test_summary / coverage_summary / recipe_source` 等关键信息，而不是继续沿用旧 verify 工具的裁剪语义
  - `/review` 在官方 verify 证据路径上的用户可见文案已从旧 `run_tests` 术语改成“测试 recipe”，避免产品词汇重新漂移回 legacy 工具名
- 影响范围：
  - adapter mode change snapshot 刷新
  - context compaction / replacement / tool summarization
  - review findings 文案与 evidence metadata
  - focused regression tests
- 关联文档：
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，属于 official cutover 完成后的 merge 前稳定化收口`
- 后续动作：
  - 继续评估 `workspace_intelligence`、`project_memory`、`permissions` 中剩余 legacy 兼容逻辑是否还能继续下线
  - 在 merge 前保持 `.venv` Python 测试和 webapp helper/build 验证为准入门槛

### DC-090

- 日期：2026-04-06
- 变更主题：稳定化收口补齐 `/review`、recipe 词汇与 runtime 正式目录
- 变更摘要：
  - `/review` 现在会把 `run_recipe` 和 `report_quality_v2` 视为正式 verify 证据，并按 `recipe_action / test_summary / coverage_summary / quality gate` 生成结构化 findings
  - `workspace_recipes` 对外输出已统一为 `tool_name=run_recipe`，并显式附带 `legacy_tool_name` 与 `recipe_action`，避免 GUI/recipe 列表继续把旧 verify 工具名当作正式产品词汇
  - `run_recipe` observation 现会回填 `recipe_action / legacy_tool_name / recipe_source / recipe_label / target / profile` 等字段，便于 review 和前端统一消费
  - `ToolRuntime.schemas()` 与 `catalog_entries()` 现已只暴露正式产品工具；legacy file/build/todo wrappers 仅保留为兼容执行别名，不再进入正式 schema/catalog
- 影响范围：
  - review synthesizer
  - workspace recipe metadata
  - GUI Run 面板 / recipe 文案
  - runtime schema/catalog 的正式边界
- 关联文档：
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，属于已确定 official cutover 后的稳定化收口`
- 后续动作：
  - 继续在真实 C 工程上验证 review、recipe 和 verify 行为
  - 若后续确认不再需要兼容执行别名，再考虑删除 `build_ops` / `todo_ops` 等剩余旧实现

### DC-089

- 日期：2026-04-06
- 变更主题：official cutover 第六步完成，当前文档与前端兼容壳层正式收口
- 变更摘要：
  - 当前 source-of-truth 文档已改写为单一正式架构说明：README、AGENTS、overall architecture、roadmap、mode schema、tool contracts、permission model、frontend protocol、agent harness baseline
  - `list_todos` / `/api/todos` / sessionless todo fallback 等前端兼容壳层已从正式产品路径移除，`tasks` 成为唯一前端任务词汇
  - `InProcessAdapter.get_tool_catalog()` 现在只投影正式 mode tool vocabulary，避免 GUI/TUI 再把 legacy duplicate tools 当作产品功能展示
  - 若仍保留历史设计材料，则已明确标注为 superseded/historical，不再作为当前架构依据
- 影响范围：
  - source-of-truth 文档集合
  - frontend / protocol / adapter 的兼容边界
  - tool catalog 的前端可见语义
- 关联文档：
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/mode-schema.md`
  - `docs/tool-contracts.md`
  - `docs/permission-model.md`
  - `docs/frontend-protocol.md`
  - `docs/agent-harness-v2.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，当前阶段更需要保持文档与实现同步`
- 后续动作：
  - 进入真实 C 项目和 Win7 bundle 稳定化验证
  - 后续若继续清理内部 dead code，应以“不改变正式架构词汇”为前提推进

### DC-088

- 日期：2026-04-06
- 变更主题：official cutover 第五步完成，frontend/protocol 正式词汇切到 `tasks/build`
- 变更摘要：
  - `protocol` / `core.adapter` / GUI backend 现已把 `tasks` 作为正式会话任务接口，并在 `SessionSnapshot` 中显式携带 `current_phase / discipline_profile / current_activity / task_summary / task_items`
  - TUI 与 GUI webapp 状态层已把 inspector、command hint、slash command、route、refresh event 和 task panel 从 `todos` 改为 `tasks`
  - webapp 的 `normalizeSessionPayload()`、store、Inspector Runtime 面板与静态构建产物现已显示 Harness 官方任务语义，而不再只停留在 legacy session status
  - webapp tests、GUI backend tests、GUI sync tests 与 adapter 前端 API 回归均已同步到 `tasks/build` 词汇并通过
- 影响范围：
  - CoreInterface / FrontendCallbacks 协议词汇
  - GUI backend route / websocket refresh event
  - TUI explorer / inspector / slash command 展示
  - React webapp store / inspector / runtime summary / built assets
- 关联文档：
  - `docs/archive/agent-harness-v2/2026-04-06-agent-harness-v2-official-cutover-plan.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，继续沿 official cutover 计划推进`
- 后续动作：
  - 进入最后一轮 docs rewrite + legacy deletion，删除兼容性的 `list_todos` / `/api/todos` /旧术语残留
  - 收口 review/loop/README/architecture 等仍使用 legacy mode/tool 词汇的文档与实现

### DC-087

- 日期：2026-04-06
- 变更主题：official cutover 第四步完成，permission/task truth 切到正式主线
- 变更摘要：
  - 当时官方 mode prompt 与 mode tool list 已统一改为 `task_status`，`manage_todos` 不再出现在正式模型工具包中；后续 workflow extension boundary 切片已进一步把 `task_status` 从内置 mode contract 中移出，改由默认 C harness extension 激活
  - `HarnessRunner` 开始输出结构化 `task_items`，`TaskGraph` 能被投影为稳定 task 列表，并通过新的 `harness/task_store.py` 持久化到 session 级 task snapshot
  - `InProcessAdapter` 创建/恢复/切 mode 后会刷新 Harness task snapshot，`list_todos(session_id=...)` 的主路径已改为读取 Harness task truth，而不是 session todo 文件
  - `permissions.py` 已吸收 recipe 规则匹配、规则别名解析与稳定 explanation 模板，`permissions_v2/` 并行包已删除
- 影响范围：
  - 官方模型任务工具契约
  - session 级任务真相源与 task projection
  - 权限规则加载、匹配与前端可见解释文本
  - focused regression tests 与 adapter/task API 行为
- 关联文档：
  - `docs/archive/agent-harness-v2/2026-04-06-agent-harness-v2-official-cutover-plan.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，继续沿 official cutover 计划推进`
- 后续动作：
  - 进入 frontend/protocol officialization，把 inspector、tool catalog、UI 文案和事件语义切到正式 V2 词汇
  - 在最终 legacy deletion 阶段删除剩余 todo 兼容壳层与相关旧测试

### DC-086

- 日期：2026-04-06
- 变更主题：official cutover 第三步完成，context/intelligence 切到 V2 tool 词汇
- 变更摘要：
  - `ContextConfig` 已从旧的 `ask/orchestra/test/code/...` 组合收敛到正式 `explore/spec/build/debug/verify` 加内部 `compact`
  - `ReducerRegistry` 现已正式支持 `list_dir`、`glob_files`、`grep_text`、`list_recipes`、`run_recipe`、`report_quality_v2`、`task_status`、`record_failing_evidence`，而不再只围绕 `list_files/search_text/compile_project/report_quality`
  - `ContextManager` 的文件/列表/搜索/命令/通用 reducer 和 duplicate suppression 逻辑已能处理 V2 结果结构，官方上下文系统开始以 V2 tool vocabulary 为主词汇，同时保留 legacy tool alias 兼容旧测试和非主路径调用
  - `WorkspaceIntelligenceBroker` 的 diagnostics/intelligence 路径现已接受 `run_recipe` 与 `report_quality_v2`，并把 `build` 作为正式实现模式继续向外投影
- 影响范围：
  - 上下文压缩与 tool message reducer
  - workspace intelligence / diagnostics summary / quality gate summary
  - focused regression tests
- 关联文档：
  - `docs/archive/agent-harness-v2/2026-04-06-agent-harness-v2-official-cutover-plan.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否，继续沿 official cutover 计划推进`
- 后续动作：
  - 进入 permission/task truth 收口
  - 在最终 legacy deletion 前，继续保留 legacy tool alias，但不再让其主导 context/intelligence 语义

### DC-085

- 日期：2026-04-06
- 变更主题：official cutover 第二步完成，正式 mode 词汇从 `code` 切到 `build`
- 变更摘要：
  - 内建 mode registry 已移除 `code`，正式用户可见 mode 词汇现为 `explore/spec/build/debug/verify`
  - `interaction.py`、CLI/TUI/GUI 默认值、Core Adapter / GUI backend / webapp session state 等产品入口默认 mode 已切到 `build`
  - `config.py`、`session_store.py`、`context.py`、`workspace_intelligence.py` 与 `tools/runtime.py` 中依赖 mode 名称的默认值和判断分支已开始统一到 `build`
  - 相关 Python 与前端测试已同步改成 `build` 语义，webapp 静态资产也已重建，避免 GUI 仍沿用旧默认 mode
- 影响范围：
  - 模式注册表与 mode 命名约定
  - CLI / TUI / GUI / protocol 的默认 mode
  - context / workspace intelligence / tool metadata 的 mode 判断
  - 相关测试与 GUI 静态产物
- 关联文档：
  - `docs/archive/agent-harness-v2/2026-04-06-agent-harness-v2-official-cutover-plan.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`与 DC-084 同步，仍建议在 official cutover 真正完成前补一条 ADR，固定唯一 mode 词汇与 build 作为唯一实现模式`
- 后续动作：
  - 继续执行 context/intelligence cutover，消除 `list_files/search_text/compile_project/report_quality` 这类 legacy 词汇在上下文系统中的主地位
  - 在最终 docs rewrite 时把 README / architecture / mode schema / protocol 示例全部改成 build 词汇

### DC-084

- 日期：2026-04-06
- 变更主题：确立 Agent Harness V2 的 official cutover 原则，不再接受长期 V1/V2 并行
- 变更摘要：
  - 在完成 build/debug/verify 第一批 V2 切片与主链路接线后，对仓库进行了“是否可直接删 legacy”审查
  - 结论是：当前主循环已经明显向 Harness V2 收敛，但 runtime、mode vocabulary、context、permission、task truth、frontend/protocol 和文档仍保留大量 legacy 词汇与双轨结构
  - 因此后续路线不应是“继续桥接 + 局部补丁”，而应改成 official cutover：按 `runtime -> mode vocabulary -> context -> permission/task truth -> frontend/protocol -> docs/legacy deletion` 的顺序，把 V2 扶正为唯一正式实现
  - 新增 `docs/archive/agent-harness-v2/2026-04-06-agent-harness-v2-official-cutover-plan.md` 作为本轮正式化计划留痕，明确不再把 `ToolRuntime + ToolRuntimeV2 + bridge`、`code + build`、`manage_todos + TaskGraph`、`permissions.py + permissions_v2` 视为可长期共存的结构
- 影响范围：
  - Agent Harness V2 的后续实施顺序
  - runtime / mode / permission / task / frontend 的收敛原则
  - 文档治理与 legacy 删除节奏
- 关联文档：
  - `docs/agent-harness-v2.md`
  - `docs/archive/agent-harness-v2/2026-04-06-agent-harness-v2-official-cutover-plan.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`建议在开始实际 official cutover implementation 前补一条 ADR，固定“唯一正式实现”与 mode vocabulary cutover 的原则`
- 后续动作：
  - 先做 runtime promotion，再做 mode vocabulary cutover
  - 在 context/intelligence 和 permission/task truth 收敛前，不再继续扩展新的 V2 侧边包
  - 完成前端/协议与文档切换后，再做最终 legacy deletion

### DC-083

- 日期：2026-04-06
- 变更主题：Agent Harness V2 Program D 启动，实现 `full_spec_tdd + TaskGraph` 的最小闭环
- 变更摘要：
  - 新增 `src/embedagent/harness/task_graph.py`，把 `TaskGraph` 作为 Harness V2 的最小真相源引入，而不是继续依赖旧 `manage_todos` 或自由文本
  - `phase_engine` 现已支持 `build` 模式下 `full_spec_tdd` 的关键 artifact gate：`contract -> test_design` 与 `check -> repair`
  - `HarnessRunner` 现在支持 `discipline_override="full_spec_tdd"`，并开始把 task summary 注入到 mode context 中
  - `InProcessAdapter` / `SessionSnapshot` 已补 `task_summary` 字段，`QueryEngine` 在 `build + workflow_state=plan` 路径下可挂起 full-spec harness context
  - 这轮实现继续遵守“新核心留在 `harness/`，旧主循环只做薄桥接”的边界，没有把 TaskGraph 或 full-spec phase 细节塞回 `query_engine.py` / `modes.py`
- 影响范围：
  - `build` mode 的 full-spec 轨道
  - session snapshot 的 task-level 可见性
  - 后续 Program D 的 artifact gate 与任务同步扩展空间
- 关联文档：
  - `docs/agent-harness-v2.md`
  - `docs/archive/agent-harness-v2/2026-04-06-agent-harness-v2-full-spec-taskgraph.md`
  - `docs/development-tracker.md`
  - `tests/test_task_graph_v2.py`
  - `tests/test_harness_runner_taskgraph.py`
  - `tests/test_query_engine_build_full_spec.py`
- 是否需要 ADR：`仍建议在继续扩展 TaskGraph 自动同步前补一条 ADR，固定任务真相源与旧 todos 的关系`
- 后续动作：
  - 继续扩展 TaskGraph 自动同步，而不是停留在初始单任务摘要
  - 在后续切片中把 `failing_evidence_ready / implementation_ready / check_result_ready` 的自动化来源接到更真实的工具结果上
  - 继续用旧回归保护 QueryEngine / tool execution / permission 主链

### DC-082

- 日期：2026-04-06
- 变更主题：Agent Harness V2 Program A/B 启动实现，并固定“新包承载新核心、旧文件仅做薄桥接”的架构边界
- 变更摘要：
  - 新增 `src/embedagent/harness/`、`src/embedagent/tooling/`、`src/embedagent/tools_v2/`、`src/embedagent/permissions_v2/` 四个新包，开始承载 Harness V2 的核心实现
  - `harness` 已落地第一批核心契约：`WorkMode`、`DisciplineProfile`、`ExecutionPhase`、`ModeDefinition`、artifact 驱动 phase 推进和 3 单元 prompt stack
  - `tooling` 已落地最小工具契约、pack 定义和 aggregate budget 基础设施；`tools_v2` 已能暴露 `build_lite` 所需的第一批 schema；`permissions_v2` 已上线 Rule Schema V1 的最小形态和确定性 explanation 模板
  - `build` mode 已被接入旧 mode registry 作为薄入口，`QueryEngine` 仅增加最小 harness context 注入，`InProcessAdapter` snapshot 已开始暴露 `current_phase / discipline_profile / current_activity`
  - 这轮实现明确遵守“新核心不继续塞进 `query_engine.py` / `modes.py` / `permissions.py` / `tools/runtime.py`”的边界：旧文件只承担兼容入口和薄桥接，不承接 V2 具体逻辑
- 影响范围：
  - Harness V2 的目录结构与模块边界
  - `build` mode 的最小可运行上下文
  - Session snapshot 对 phase / discipline / activity 的可见性
  - 后续 Program C/D/E 的实现落点
- 关联文档：
  - `docs/agent-harness-v2.md`
  - `docs/archive/agent-harness-v2/2026-04-06-agent-harness-v2-foundation.md`
  - `docs/development-tracker.md`
  - `tests/test_harness_contracts.py`
  - `tests/test_phase_engine.py`
  - `tests/test_prompt_stack_v2.py`
  - `tests/test_tooling_budget_v2.py`
  - `tests/test_rule_schema_v2.py`
  - `tests/test_tools_v2_runtime.py`
  - `tests/test_query_engine_build_lite.py`
- 是否需要 ADR：`仍建议在继续推进 Program C 之前补一条 ADR，固定 visible mode 与 internal phase 的分层原则`
- 后续动作：
  - 继续推进 Program C：`debug + lite_spec_tdd`
  - 在 Program D 前补齐 TaskGraph 自动同步和更真实的 artifact gate
  - 在后续切断旧体系前，继续用定向旧回归测试保护 `QueryEngine` / `PermissionPolicy` / `ToolCommitCoordinator`

### DC-081

- 日期：2026-04-06
- 变更主题：确立 Agent Harness V2 作为下一轮 mode / tool / permission 整体重构基线
- 变更摘要：
  - 新增 `docs/agent-harness-v2.md`，正式把下一轮重构目标从“修补现有 mode/tool/permission”提升为“重建执行内核”
  - 新基线保留用户可见 mode，但将其从硬工具围栏改为工作模式；真正驱动自动化的是 mode 内部的 `execution phase`
  - 新设计引入 `discipline profile`（`full_spec_tdd` / `lite_spec_tdd`）、`tool pack`、`permission DSL`、统一 `failure taxonomy` 与结果预算策略
  - 设计明确借鉴 `reference/claude-code` 的工具完整契约、结果持久化、权限解释和错误格式化机制，同时保留更适合弱模型的 mode 聚焦与最小工具暴露面
  - 当前这是一条已确认的设计基线，而非已完成实现；后续实现切片应按该文档推进，而不是继续在旧 mode 和旧权限上做局部修补
- 影响范围：
  - mode 系统定位
  - tool contract / result budget / validator / recovery 设计
  - allowlist / permission 设计
  - spec-driven / TDD 默认工作流
- 关联文档：
  - `docs/agent-harness-v2.md`
  - `docs/development-tracker.md`
  - `docs/tool-design-spec.md`
  - `docs/mode-schema.md`
  - `docs/permission-model.md`
- 是否需要 ADR：`建议在正式进入实现切片前补一条 ADR，固定 visible mode 与 internal phase 的分层决策`
- 后续动作：
  - 基于该文档继续细化可执行重构计划与切片边界
  - 在进入实现前，明确新 mode 命名、recipe 中心验证工具面、permission DSL 文法与 session/front-end 暴露字段

### DC-080

- 日期：2026-04-06
- 变更主题：GUI interaction panel 改为专属 tab，并把失效交互降级为 notice
- 变更摘要：
  - webapp `Inspector` 不再把当前交互面板挂在所有右侧 tab 的公共尾部，而是新增专属 `interaction` tab 作为唯一可操作入口
  - `projectSessionRuntime()` 现在把 `currentInteraction` 收敛为“仍然可操作的活跃交互”；`pending_interaction_valid = false`、`interaction.status = expired` 与 `restore_stop_reason = interaction_expired` 会投影成 notice，而不是伪造一个可点击的 expired interaction
  - `permission_request` / `user_input_request` / session activation with pending interaction 会自动把 Inspector 切到 `interaction` tab；409/410 交互响应错误也会回收到同一 notice 语义
  - ask_user、permission、restore stale interaction 与并发响应冲突开始共用一套交互生命周期边界，避免“所有 tab 底部长出 expired 卡片”的跨面板污染
- 影响范围：
  - GUI Inspector / InteractionPanel / session-runtime projector
  - pending interaction 的前端读模型边界
  - interaction expired / conflict 的用户可理解性与恢复路径
- 关联文档：
  - `docs/frontend-protocol.md`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx`
- 是否需要 ADR：`否`
- 后续动作：
  - 在真实 GUI 宿主与 Win7 手工验证中复查 ask_user / permission / expired interaction 的 tab 聚焦与恢复体验
  - 若后续继续推进 event-sourced runtime，可考虑把 interaction notice 也收口到统一的 interaction event 类型，而不是 snapshot + client notice 双来源

### DC-079

- 日期：2026-04-06
- 变更主题：GUI bundled runtime discovery 问题分析文档已归档
- 变更摘要：
  - `docs/issues/gui-bundled-runtime-discovery-failure.md` 已迁入 `docs/archive/issues/`
  - 当前该问题已随 bundle runtime discovery 与 GUI 资产门禁修复一起关闭，不再保留在活动 issue 入口
  - 活跃事实来源收敛为 tracker / change-log / 已合并实现；问题分析文档仅保留为历史追踪材料
- 影响范围：
  - 活动问题入口整洁度
  - bundle runtime discovery 缺陷的关闭状态
- 关联文档：
  - `docs/archive/issues/README.md`
  - `docs/archive/issues/gui-bundled-runtime-discovery-failure.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 后续若再发现 GUI bundle/runtime 相关缺陷，使用新的 issue 文档而不是复用这份已归档分析

### DC-078

- 日期：2026-04-06
- 变更主题：离线打包直连脚本链补齐 GUI 静态资产门，避免 KaTeX 资源残缺静默入包
- 变更摘要：
  - `scripts/package-lib.ps1` 新增 GUI 静态资产检查与确保逻辑，统一识别 `index.html`、`app.js`、`app.css` 与 `assets/katex/katex.min.css` 是否完整
  - `Invoke-FrontendBuild` 已改为复用同一套检查/构建函数；控制面 `package.ps1` 继续保留强制前端构建语义，但逻辑不再与直连脚本链分叉
  - `scripts/prepare-offline.ps1` 现在会在复制应用代码前确保 GUI 静态资产完整，缺失时尝试 `npm install --force` + `npm run build`，仍失败则直接中止
  - `scripts/build-offline-bundle.ps1` 现在会对现有 staging bundle 做 GUI 静态资产门禁；即使用户不带 `-RunPrepare`，也不会再把缺少 KaTeX 的旧 staging 静默复制到 `offline-dist`
- 影响范围：
  - Phase 7 直连脚本链（`prepare-offline` / `build-offline-bundle`）
  - `package.ps1` 控制面与直连脚本链的一致性
  - GUI 数学公式渲染相关静态资源的随包完整性
- 关联文档：
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `scripts/package-lib.ps1`
  - `scripts/prepare-offline.ps1`
  - `scripts/build-offline-bundle.ps1`
- 是否需要 ADR：`否`
- 后续动作：
  - 若后续继续精简打包脚本，应进一步收敛 `prepare/build/package` 三条路径中的共享验证逻辑，减少 PowerShell 侧重复实现

### DC-077

- 日期：2026-04-05
- 变更主题：bundle 运行时发现统一为强签名单一事实源，并补齐 GUI launcher 契约防回归
- 变更摘要：
  - 新增 `src/embedagent/runtime_discovery.py`，把 bundle 根目录识别统一收敛为“环境变量优先 + 安装位置 fallback + 强签名校验”的公共逻辑；只有同时满足 `app/embedagent`、`runtime/python`、`bin` 等关键目录标记时才认定为 bundle 根目录
  - `ToolContext.bundle_root()` 与 GUI `launcher.py` 不再各自维护分裂的 bundle 推断逻辑，`scripts/check-bundle-dependencies.py` 也复用同一套发现规则，避免出现“GUI 认为在 bundle 中、工具运行时却认为不在 bundle 中”的状态分裂
  - `scripts/templates/embedagent-gui.cmd` 与 `scripts/prepare-offline.ps1` 生成的 GUI launcher 现在显式导出 `EMBEDAGENT_BUNDLE_ROOT`，并与 CLI launcher 对齐 `git\\bin` / `llvm\\libexec` 的 PATH 注入
  - `scripts/validate-offline-bundle.ps1` 新增 launcher contract 校验；即使 launcher 文件存在，只要缺失 `EMBEDAGENT_BUNDLE_ROOT` 或关键 PATH 片段，也会被视为 bundle 缺陷而非仅做存在性通过
- 影响范围：
  - GUI 离线 bundle 启动链路
  - Tool Runtime 托管工具发现与 PATH 构造
  - Phase 7 bundle 验证脚本的缺陷检出能力
- 关联文档：
  - `docs/archive/issues/gui-bundled-runtime-discovery-failure.md`
  - `docs/development-tracker.md`
  - `src/embedagent/runtime_discovery.py`
  - `scripts/validate-offline-bundle.ps1`
- 是否需要 ADR：`否`
- 后续动作：
  - 在下一次真实 `prepare/build/validate` 与 Win7 bundle 验收中，复核 GUI runtime inspector 是否稳定显示 bundle 工具根目录
  - 若后续继续精简 launcher 生成链路，可进一步消除模板文件与 `prepare-offline.ps1` 内嵌字符串的重复来源

### DC-076

- 日期：2026-04-05
- 变更主题：GUI timeline event-anchor 文档已归档
- 变更摘要：
  - 本轮 `GUI timeline event-anchor unification` 的设计稿、实施计划与问题分析文档已迁入 `docs/archive/gui-timeline-event-anchors/`
  - 当前仓库不再把这轮 GUI timeline/event-anchor 的 spec/plan 保留在活动 `docs/superpowers/` 入口，也不再把对应问题分析留在活动 `docs/issues/` 入口
  - 当前这轮工作的活跃事实来源收敛为 tracker / change-log / frontend protocol 与已合并实现
- 影响范围：
  - 文档入口与活动工作区整洁度
  - GUI timeline event-anchor slice 的关闭状态
- 关联文档：
  - `docs/archive/gui-timeline-event-anchors/README.md`
  - `docs/development-tracker.md`
  - `docs/frontend-protocol.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 后续若继续推进 GUI timeline/runtime 的独立增强，应新开独立 spec/plan，而不是复用这轮已归档文档

### DC-075

- 日期：2026-04-05
- 变更主题：GUI timeline 事件锚点统一为 turn/step 契约，并把 slash/workflow 命令纳入正式 turn 生命周期
- 变更摘要：
  - `CommandResult`、`PermissionRequest`、`UserInputRequest` 现在统一携带 `turn_id / step_id / step_index`；pending interaction snapshot 也保留同样坐标
  - slash/workflow 输入现在会在命令分发前预生成 `turn_id`，并为 handled-only 命令补齐 `turn_start / turn_end`；命令结果、命令侧工具执行与命令侧权限请求都会锚定到同一 turn
  - `context_compacted` / `session_error` 的后端 emit、协议转换、WebSocket 转发、前端 reducer 与 raw replay 路径已补齐坐标，避免卡片在 Timeline 中游离或掉到底部 fallback 区
  - `build_structured_timeline()` 与 `timelineFromTurns()` 现在显式保留并投影 turn-level `transitions` / `tool_calls`，初始加载、实时流与 reload/replay 的时间线语义开始统一
  - `permission_request` 前端本地 `interaction.created` 追加事件已补齐 turn/step 坐标；permission / user_input 的双源结构仍保留，但结构已对齐且按 `interaction_id` 去重
  - `ContextManager` 的 `compacted` 判定移除了 `bool(old_turns)`，常规摘要窗口不再被误判为 GUI 层面的真实 compaction
- 影响范围：
  - GUI Timeline / Inspector / runtime projector
  - in-process adapter / core callback bridge / GUI backend websocket payload
  - structured timeline bootstrap 与 raw replay 的一致性
  - slash/workflow 命令的时间线生命周期语义
- 关联文档：
  - `docs/archive/gui-timeline-event-anchors/GUI_timeline_turnid_binding_analysis.md`
  - `docs/archive/gui-timeline-event-anchors/2026-04-05-gui-timeline-event-anchors-design.md`
  - `docs/archive/gui-timeline-event-anchors/2026-04-05-gui-timeline-event-anchors.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 在 Win7 / 真实 GUI 宿主里继续验证 `/review`、`/run`、permission wait 与 context compact 的视觉位置是否符合预期
  - 后续若继续推进 event-sourced runtime，可考虑让 Timeline/Inspector 最终统一只消费一套 interaction event 源，而不是本地 append + backend raw event 双轨并存

### DC-074

- 日期：2026-04-05
- 变更主题：transcript-truth tool-result cutover 文档已归档
- 变更摘要：
  - transcript-truth cutover 的设计稿、实施计划、影响分析与代码审阅结论已迁入 `docs/archive/transcript-truth-tool-result-cutover/`
  - 当前仓库不再把这轮 cutover 的 spec/plan 留在活动 `docs/superpowers/` 入口，也不再把相关分析材料留在活动 issue 入口
  - 这轮工作当前的活跃事实来源收敛为 tracker / change-log / redesign 文档与已合并实现，而不是继续保留执行期文档作为待办入口
- 影响范围：
  - 文档入口与活动工作区整洁度
  - transcript-truth cutover slice 的关闭状态
- 关联文档：
  - `docs/archive/transcript-truth-tool-result-cutover/README.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 后续若继续扩展 tool-result 外置或 projection 存储，应开启新的独立 spec/plan，而不是复用这轮归档文档

### DC-073

- 日期：2026-04-05
- 变更主题：transcript-truth cutover review follow-up 收口了投影层残留竞争与命名债务
- 变更摘要：
  - `SessionSummaryStore` 现在会把 session list / latest resolution 优先建立在 `ProjectionDb.session_projection` 上，不再依赖运行时写 `.embedagent/memory/sessions/index.json`
  - `ProjectMemoryStore` 已增加实例级锁与原子 JSON 写，避免 recipes/issues/profile 在并发 refresh/cleanup 下留下损坏文件
  - `ToolCommitCoordinator` 已把 SQLite projection refresh 移到单写锁外，继续保持 transcript 与 tool-result 文件为真相提交，同时缩短 commit 临界区
  - review evidence 与前端 Inspector 中残留的 `diff_artifact_ref` 已统一更名为 `diff_stored_path`
- 影响范围：
  - session summary / latest session projection
  - project memory 持久化稳定性
  - tool commit 临界区长度
  - review evidence 前后端字段契约
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
  - `docs/archive/transcript-truth-tool-result-cutover/2026-04-05-transcript-truth-cutover-code-review.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 若后续继续把 project memory 完全迁入 SQLite，可在当前锁与原子写基线上渐进替换
  - 若 review evidence 还发现别的 `*_artifact_ref` 残留，继续按 `*_stored_path` 主线统一

### DC-072

- 日期：2026-04-05
- 变更主题：transcript-truth tool-result cutover 完成，运行时移除共享 ArtifactStore 索引
- 变更摘要：
  - 工具执行与持久化提交已经彻底分层：工具线程只返回 raw observation，`ToolCommitCoordinator` 在单写者边界内串行完成 tool-result 落盘、`tool_result`/`content_replacement` transcript append 与 projection 更新
  - 长文本结果改为写入 session-local `.embedagent/memory/sessions/<session_id>/tool-results/<tool_call_id>/...` 唯一路径，运行时不再维护 `artifacts/index.json`
  - artifact browse / session summary / project memory 已统一降级为 derived projection，并由 `ProjectionDb`（SQLite）提供可查询元数据；projection 失败不再把主工具结果翻成失败
  - `ArtifactStore` 已从运行时代码删除，`SessionTimelineStore`/`ToolRuntime`/相关测试与上下文 replacement 逻辑已切到 `*_stored_path` 语义
- 影响范围：
  - Query / Context 主线
  - tool result 持久化与 `/artifacts` 浏览后端
  - resume / replacement 真相边界
  - memory maintenance / projection 清理链路
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/tool-contracts.md`
  - `docs/development-tracker.md`
  - `docs/archive/transcript-truth-tool-result-cutover/2026-04-05-transcript-truth-tool-result-cutover-design.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 在真实 GUI / Win7 路径上继续复查 `/artifacts`、resume 与 review evidence 的投影行为
  - 后续若继续扩展大列表/诊断外置策略，优先复用 `ToolResultStore + ProjectionDb`，不要重新引入共享 mutable index

### DC-070

- 日期：2026-04-04
- 变更主题：GUI runtime hardening 进入 typed reload + projector ownership 第二阶段
- 变更摘要：
  - timeline reload / bootstrap API 现在显式区分 `reload_required / degraded`，HTTP route 不再只返回扁平 events 数组
  - websocket / HTTP 错误边界现在会把常见 session / interaction 故障映射成 typed 错误，并在 websocket 非正常异常时确保清理连接
  - `SessionSnapshot` / GUI snapshot payload 当时保留 reload metadata；当前架构已删除 timeline-shaped snapshot 字段
  - webapp active session projector 现在接管 reload state、command result fallback、detached turn item 排序、session-scoped runtime reset，并让 Timeline 直接消费 grouped runtime view
- 影响范围：
  - GUI replay / restore / transport 恢复语义
  - active-session Timeline / Inspector 的读模型边界
  - front-end runtime 与 backend snapshot/replay 契约
- 关联文档：
  - `docs/archive/gui-runtime-hardening/2026-04-04-gui-runtime-hardening-design.md`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续观察 Win7 真实宿主中的 reconnect / degraded 流体验
  - 如仍存在 step streaming 消息拆分问题，按独立 streaming aggregation slice 继续推进
  - 在最终 bundle 验收中复查 static build 产物与 runtime hardening 文档是否同步

### DC-063

- 日期：2026-04-04
- 变更主题：GUI active-session runtime 改为 transport-state + projector 驱动
- 变更摘要：
  - GUI backend 新增统一 `session_event` envelope，并补 `GET /api/sessions/{session_id}/events?after_seq=N` reload 信号入口
  - active session 当前交互改为统一 interaction response route；Inspector 成为唯一可操作入口，Timeline 退化为交互历史摘要投影
  - webapp 新增 session transport state 与 `session-runtime/projector.js`，当前会话读模型开始从 `snapshot + transport state + bootstrap history` 统一派生
  - dispatcher 失败开始带 `reason`，restore 遇到缺失可信 `interaction_id` 的 pending interaction 会显式停在 `interaction_expired`
- 影响范围：
  - GUI Timeline / Inspector / transport 恢复语义
  - pending interaction 的 UI 真相边界
  - reconnect / resync / degraded-state 处理
- 关联文档：
  - `docs/archive/gui-runtime-hardening/2026-04-04-gui-event-sourced-session-design.md`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续把更多 live event 从 reducer patching 收口到 `session_event` 驱动
  - 为 malformed transport、interaction conflict/gone 和 replay gap 补更多前端/后端回归
  - 在最终 bundle 验收时验证 GUI degraded/resync 流在真实宿主中的表现

### DC-071

- 日期：2026-04-04
- 变更主题：GUI runtime hardening 文档从活动入口归档
- 变更摘要：
  - `gui event-sourced session runtime` 与 `gui runtime hardening` 这轮 spec/plan 已确认完成当前目标，不再保留在活动 `docs/superpowers/specs/` / `plans/` 入口
  - 相关文档已统一迁入 `docs/archive/gui-runtime-hardening/`
  - 当前仓库中关于这轮工作的活跃入口收敛为 tracker / change-log / frontend protocol，而不是继续把旧计划当作待执行项
- 影响范围：
  - 文档入口与活动工作区整洁度
  - GUI runtime hardening slice 的关闭状态
- 关联文档：
  - `docs/archive/gui-runtime-hardening/README.md`
  - `docs/development-tracker.md`
  - `docs/frontend-protocol.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 若后续继续推进 GUI runtime 相关工作，应以新的独立 spec/plan 开启，而不是复用这轮已归档计划

### DC-060

- 日期：2026-04-04
- 变更主题：上下文主循环的因果链、timeline 顺序与并行工具收口现在统一硬化
- 变更摘要：
  - `TranscriptMessage`、普通 `message` 事件和 `tool_result` 事件现在都会显式携带 `parent_message_id`，`SessionRestorer` 在提供父引用时也会校验父消息是否已经存在
  - `QueryEngine` 对同一 step 的 compact retry 边界改成“最多记录一条有效 boundary”，避免 retry 前后重复写入导致 transcript 中出现“摘要套摘要”
  - `SessionTimelineStore` 现在引入文件级串行化与单调 `seq`，GUI reducer 也开始使用 provisional turn anchor 并在 `turn_started` 时回填
  - `StreamingToolExecutor` 现在为并行只读 batch 增加 cancel / idle-timeout 收口：started 但卡住的 action 会变成 `interrupted` 或 `timeout`，未开始的兄弟 action 会变成 `discarded`
- 影响范围：
  - transcript resume 一致性
  - compact boundary replay 稳定性
  - GUI timeline / command card 的 turn 关联正确性
  - 并行工具执行的卡死风险
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
  - `docs/archive/context-loop/context-loop-handoff-status.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续评估 transcript/timeline 的轮转策略与跨会话长期增长控制
  - 视 GUI 真实宿主验证结果，决定是否把更多 raw event 投影切换到 `seq` 驱动的增量加载
  - 为更复杂的 resume / compact / mode-change 组合场景补集成回归

### DC-061

- 日期：2026-04-04
- 变更主题：GUI broadcast 与 QueryEngine session 共享状态的竞态点现在显式收口
- 变更摘要：
  - `WebSocketFrontend` 现在为 `connections` 增加锁保护，并在广播时先复制快照再发送，连接在发送期间断开不再触发集合迭代异常
  - `QueryEngine` 新增可选 `session_lock`，并在 context build、message/tool_result/transition 追加、pending resolution replay、summary persist 与 compact boundary 写入等关键路径上统一持锁
  - `InProcessAdapter` 已把 `ManagedSession.lock` 作为 `session_lock` 传给 `QueryEngine`，让真实 GUI/API 运行链路也能受益，而不只是单元测试路径
- 影响范围：
  - GUI WebSocket 稳定性
  - Query loop 与 adapter/session snapshot 的并发一致性
  - 运行中 session 的状态真相边界
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续观察是否需要把 timeline/project memory 等更多只读投影统一迁移到 session truth 的同一锁域
  - 在真实 GUI 宿主里继续观察高频事件下的广播吞吐与顺序表现

### DC-062

- 日期：2026-04-04
- 变更主题：context loop 这轮 handoff/analysis/review 文档已归档
- 变更摘要：
  - `docs/context-loop-handoff-plan.md`、`docs/context-loop-handoff-status.md` 以及本轮相关的 context-loop issue/review 文档已移动到 `docs/archive/context-loop/`
  - 新增 `docs/archive/context-loop/README.md` 说明该轮迭代已关闭，并指向当前仍然活跃的 tracker/change-log/redesign 文档
  - 仓库内原先引用旧 handoff 路径的文档已统一改到 archive 路径，避免归档后出现失效链接
- 影响范围：
  - 文档信息架构
  - context loop 历史材料的留档方式
  - 当前活跃工作流入口的清晰度
- 关联文档：
  - `docs/archive/context-loop/README.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 后续若开启新的 context loop 增量迭代，直接在活跃文档中记录，不再复用这组归档 handoff 文件

### DC-056

- 日期：2026-04-04
- 变更主题：transcript replay 链路补齐 compact boundary 与 pending resolution 持久化
- 变更摘要：
  - `TranscriptStore.append_event()` 现在会按 transcript 文件串行化写入，避免并发 append 时出现重复 `seq`
  - `QueryEngine` 现在会把 `compact_boundary` 显式写入 transcript，并补齐 `preserved_head_message_id / preserved_tail_message_id`
  - `resume_pending()` 现在会把 `pending_resolution` 与恢复阶段生成的 `tool_result` 一并落盘，`SessionRestorer` 也会回放新的 compact metadata
- 影响范围：
  - transcript 一致性
  - compact boundary replay
  - pending interaction / resume 可审计性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补消息链 / preserved segment 的更强一致性验证
  - 评估 transcript 尾部损坏修复与轮转策略
  - 补更贴近真实工程的长会话恢复回归

### DC-057

- 日期：2026-04-04
- 变更主题：transcript damaged-tail recovery 现在会拦截 seq gap 并在追加前修复尾部
- 变更摘要：
  - `TranscriptStore.load_events()` 现在要求 `seq` 严格连续，遇到跳号、乱序或损坏行会停止在最后一个连续前缀
  - `TranscriptStore.append_event()` 现在会在追加前截断损坏尾部，避免新事件被追加到坏尾后面却永远读不出来
  - 新增 focused regression 覆盖 `seq` gap 和坏尾后继续写入两条路径
- 影响范围：
  - transcript corruption handling
  - append-only transcript 的自愈能力
  - resume 前的事件读取一致性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续评估 transcript 轮转与更细的损坏诊断输出
  - 补 restore 侧的更强事件因果校验

### DC-058

- 日期：2026-04-04
- 变更主题：SessionRestorer 现在只回放因果自洽的 transcript 前缀
- 变更摘要：
  - `SessionRestorer` 在遇到没有前置 `tool_call` 的 `tool_result` 时不再自动补造 `ToolCallRecord`
  - `pending_resolution` 如果前面没有已建立的 `pending_interaction`，恢复流程会停在最后一个自洽前缀
  - 新增 focused regression 覆盖这两类 malformed transcript，保证恢复链不会静默放大坏数据
- 影响范围：
  - transcript replay 边界
  - malformed transcript 的恢复安全性
  - restore / adapter 的状态可信度
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 message-chain / preserved segment 的更强一致性验证
  - 评估是否要暴露“恢复停止于哪个 event”的诊断信息

### DC-059

- 日期：2026-04-04
- 变更主题：SessionRestorer 现在拒绝补造缺失的 turn / step 拓扑
- 变更摘要：
  - `step_started` 若前面没有 user turn，恢复会停在最后一个合法前缀，而不是创建空 turn
  - `tool_call` 若前面没有 active step，恢复会停止，而不是隐式补造 step
  - 新增 focused regression 覆盖这两类顺序错误，保证 transcript replay 不会把拓扑损坏“修饰”为正常状态
- 影响范围：
  - transcript replay 的 turn/step 拓扑可信度
  - malformed transcript 的恢复安全性
  - adapter resume 的状态稳定性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 message-chain / preserved segment 的一致性校验
  - 评估是否要在恢复结果里暴露 stop reason / stop event index

### DC-060

- 日期：2026-04-04
- 变更主题：SessionRestorer 现在校验 replay 事件的 turn_id / step_id 一致性
- 变更摘要：
  - `tool_call`、`tool_result`、`pending_interaction`、`loop_transition` 现在都会校验其 `turn_id / step_id` 是否匹配当前活动节点
  - 一旦 transcript 事件引用了错误的活动 turn/step，恢复会停在最后一个自洽前缀，而不是把事件静默挂到当前节点
  - 同时把 `pending_interaction` 的 focused fixture 补齐为真实链路：包含前置 `step_started`
- 影响范围：
  - transcript replay 的 ID 一致性
  - malformed transcript 的恢复安全性
  - adapter resume 的状态可信度
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 message-chain / preserved segment 的一致性校验
  - 评估 restore 结果是否要暴露 stop reason / consumed event count

### DC-061

- 日期：2026-04-04
- 变更主题：compact boundary replay 现在校验 preserved segment，QueryEngine 会为已有内存历史补 transcript bootstrap
- 变更摘要：
  - `SessionRestorer` 在回放 `compact_boundary` 前，会验证 `preserved_head_message_id / preserved_tail_message_id` 是否都能在已恢复 message 中找到，且顺序必须合法
  - `QueryEngine` 在遇到“已有内存历史但 transcript 还不存在”的 session 时，会先把当前 `session.messages` 与 `compact_boundaries` bootstrap 到 transcript，再继续本轮执行
  - 这避免了新生成的 compact boundary 引用了 transcript 中根本不存在的旧 message，导致恢复器把 boundary 判为坏数据
- 影响范围：
  - compact boundary replay
  - transcript bootstrap for existing in-memory sessions
  - resumed session 的 compact 边界稳定性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 message event 自身的 chain / parent consistency 校验
  - 评估 bootstrap 是否需要进一步回填 tool topology / transitions

### DC-062

- 日期：2026-04-04
- 变更主题：message replay 现在校验 turn 一致性，并兼容缺少 step_started 的旧 transcript
- 变更摘要：
  - `SessionRestorer` 现在会拒绝错误 `turn_id` 的 `assistant/tool` message
  - 对 `step_id` 的处理改成“有 active step 时严格匹配；没有 active step 时允许 assistant/tool message 作为旧 transcript 的建步前缀”
  - 这既收紧了 message replay 的错误挂接风险，也保住了历史 transcript 中 message-only 形态的兼容恢复
- 影响范围：
  - assistant/tool message replay
  - legacy transcript compatibility
  - compact replay / content replacement 的恢复稳定性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 message chain / parent consistency
  - 评估是否要为 legacy compatibility 打上显式 restore note

### DC-063

- 日期：2026-04-04
- 变更主题：SessionRestorer 现在拒绝重复 message_id / tool_call_id
- 变更摘要：
  - `SessionRestorer` 在 replay `message` 事件时会校验 `message_id` 唯一性
  - `tool_call` 的 `call_id` 现在也要求唯一；一旦 transcript 中重复声明同一个 call id，恢复会停在最后一个自洽前缀
  - 这保证了 compact boundary、content replacement 和 tool topology 不会落到不唯一的引用目标上
- 影响范围：
  - message identity
  - tool call identity
  - transcript replay 的引用稳定性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续评估是否要把 restore stop reason / consumed event count 暴露给上层
  - message chain / parent consistency 目前已开始具备基础前置条件，后续可继续推进

### DC-064

- 日期：2026-04-04
- 变更主题：pending_resolution replay 现在校验活动 turn / step 一致性
- 变更摘要：
  - `SessionRestorer` 在处理 `pending_resolution` 时，除了要求当前存在 `pending_interaction`，还会校验该 resolution 的 `turn_id / step_id` 必须匹配当前活动节点
  - 一旦 resolution 指向错误的 turn 或 step，恢复会停在最后一个自洽前缀，而不是把真正的 pending 状态提前清掉
  - 新增 focused regression 覆盖 wrong-turn / wrong-step 两条路径
- 影响范围：
  - pending interaction replay
  - resume 状态可信度
  - malformed transcript 的恢复安全性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续评估 restore stop reason / consumed event count 的上抛
  - 若继续推进 message chain，可把 pending interaction 纳入统一 parent/reference 校验

### DC-065

- 日期：2026-04-04
- 变更主题：pending_resolution replay 现在校验 interaction identity
- 变更摘要：
  - `SessionRestorer` 现在会校验 `pending_resolution` 的 `interaction_id / tool_name / kind` 是否与当前 `pending_interaction` 一致
  - 一旦 resolution 指向了别的 interaction、别的工具或别的等待类型，恢复会停在最后一个自洽前缀，而不会把当前等待态错误清掉
  - 新增 focused regression 覆盖 wrong-interaction-id 和 wrong-tool-name 两条路径
- 影响范围：
  - pending interaction replay
  - resume 状态可信度
  - malformed transcript 的引用一致性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续评估 restore stop reason / consumed event count 的上抛
  - 若继续推进 parent/reference contract，可把 compact boundary / pending interaction 统一到一套引用校验模型

### DC-066

- 日期：2026-04-04
- 变更主题：tool_result replay 现在校验与前置 tool_call 的引用一致性
- 变更摘要：
  - `SessionRestorer` 在处理 `tool_result` 时，除了要求 `call_id` 已存在，还会校验 `tool_name` 是否与已记录的 `tool_call` 一致
  - 若 `tool_result` 显式带了 `arguments`，也会要求它与前置 `tool_call.arguments` 保持一致
  - 这样可以避免“只碰巧复用了同一个 call id”的错误结果被挂到现有 tool call 上
- 影响范围：
  - tool result replay
  - tool topology 的恢复可信度
  - malformed transcript 的引用一致性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续评估 restore stop reason / consumed event count 的上抛
  - 若继续推进 parent/reference contract，可把 assistant action/tool_result/message 三条链路纳入统一约束

### DC-067

- 日期：2026-04-04
- 变更主题：content_replacement replay 现在校验目标 tool message 的引用一致性
- 变更摘要：
  - `SessionRestorer` 现在要求 `content_replacement.message_id` 必须命中一个已恢复的 `tool` message
  - 若 `content_replacement` 显式提供了 `tool_call_id / tool_name`，它们也必须与目标 tool message 保持一致
  - 这避免了错误 replacement 文案被挂到无关消息上，进而污染后续的 context assembly
- 影响范围：
  - content replacement replay
  - artifact replacement 的恢复可信度
  - malformed transcript 的引用一致性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续评估 restore stop reason / consumed event count 的上抛
  - 若继续推进 parent/reference contract，可把 compact boundary / pending / replacement 收拢成统一引用验证层

### DC-068

- 日期：2026-04-04
- 变更主题：SessionRestorer 现在暴露 consumed_event_count 与 stop_reason
- 变更摘要：
  - `SessionRestoreResult` 现在会区分 transcript 总事件数和实际消费到的连续前缀长度
  - 当恢复在某个校验点提前停止时，会带上稳定的 `stop_reason`，便于 adapter / UI / 日志层诊断具体是在哪类一致性检查上停下来的
  - focused regression 已覆盖“完整恢复 consumed=total”与“坏 transcript 返回明确 stop_reason”两条路径
- 影响范围：
  - transcript replay diagnostics
  - restore 可观测性
  - 上层恢复故障排查
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 评估是否要把 stop reason / consumed count 透传到 session snapshot 或 GUI inspector
  - 若继续推进统一引用验证层，可顺手把 stop reason 归类成更稳定的错误码集合

### DC-069

- 日期：2026-04-04
- 变更主题：restore diagnostics 现在透传到 adapter session snapshot
- 变更摘要：
  - `ManagedSession` 与 session snapshot 现在会保存并暴露 `restore_stop_reason / restore_consumed_event_count / restore_transcript_event_count`
  - 这让 `resume_session()` 的调用方可以直接判断“本次恢复是否被截断、截断点在哪里”，而不再只能从日志或 transcript 间接推断
  - focused regression 已覆盖 clean replay 与 truncated replay 两条路径
- 影响范围：
  - adapter resume observability
  - session snapshot contract
  - 上层恢复诊断体验
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 评估是否把这些字段继续接到 GUI inspector / runtime 面板
  - 若后续收敛 stop reason 枚举，可把 snapshot contract 改成更稳定的 code + message 组合

### DC-070

- 日期：2026-04-04
- 变更主题：SessionRestorer 现在拒绝重复 step_id / pending_interaction_id
- 变更摘要：
  - `step_started` 现在要求 `step_id` 唯一；重复 step id 会让恢复停在最后一个自洽前缀
  - `pending_interaction` 现在要求 `interaction_id` 唯一；重复 interaction id 不再覆盖已有等待态
  - 这样可以避免后续 `tool_call / tool_result / pending_resolution / loop_transition` 被挂到不唯一的活动节点上
- 影响范围：
  - step topology replay
  - pending interaction replay
  - transcript identity consistency
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 评估是否还需要对 `turn_id` 做全局唯一性校验
  - 若继续推进统一引用验证层，可把这些 identity checks 收敛成统一 helper

### DC-071

- 日期：2026-04-04
- 变更主题：SessionRestorer 现在拒绝重复 turn_id
- 变更摘要：
  - `user` message 在 replay 时现在会校验 `turn_id` 唯一性
  - 一旦 transcript 中重复声明新的 turn id，恢复会停在最后一个自洽前缀，而不会创建两个语义上冲突的 turn
  - 这进一步收紧了 turn/step/pending/tool 四层 identity 体系中的 turn 层约束
- 影响范围：
  - turn-level replay
  - transition/pending 的 turn 挂接稳定性
  - transcript identity consistency
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 若继续推进统一引用验证层，可把 turn/message/step/call/interaction 的 uniqueness checks 收敛成统一 helper
  - 评估 stop reason 是否需要继续细分成“identity”与“ordering”两级分类

### DC-072

- 日期：2026-04-04
- 变更主题：SessionRestorer 现在拒绝重复 compact_boundary.boundary_id
- 变更摘要：
  - `compact_boundary` 在 replay 时现在要求 `boundary_id` 唯一
  - 一旦 transcript 中重复声明同一个 boundary id，恢复会停在最后一个自洽前缀，而不会让两个不同摘要边界共享同一个 identity
  - 这让 compact history 的边界引用和后续 UI/恢复投影更稳定
- 影响范围：
  - compact boundary replay
  - compact history identity consistency
  - transcript restore 安全性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 若继续推进统一引用验证层，可把 boundary/message/turn/step/call/interaction identity checks 收敛成统一 helper
  - 评估是否还需要为 context_snapshot 一类衍生事件定义 identity/replace 规则

### DC-073

- 日期：2026-04-04
- 变更主题：SessionRestorer 现在拒绝重复 tool_result.message_id
- 变更摘要：
  - `tool_result` replay 现在会把显式给出的 `message_id` 纳入全局 message identity 校验
  - 一旦 tool result 的 message id 与既有 message 冲突，恢复会停在最后一个自洽前缀，而不会让后续 replacement / preserved segment 指向不唯一的消息节点
  - 这补齐了 `message_id` 唯一性在 `message` 事件路径之外的最后一个明显缺口
- 影响范围：
  - tool result replay
  - message identity consistency
  - replacement / preserved segment 的引用稳定性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 若继续推进统一引用验证层，可把所有 identity checks 收敛到统一 helper / registry
  - 评估是否还需要把 `tool_result.message_id` 缺失时的自动生成语义也显式记录进 transcript contract

### DC-055

- 日期：2026-04-02
- 变更主题：discard-on-retry 已扩展到后续 batch
- 变更摘要：
  - `QueryEngine` 现在会把“当前 batch 已出现 discarded”视为当前 assistant plan 已不完整的明确边界
  - 在这种情况下，同一条 assistant reply 中后续 batch 的 action 不再继续真实执行，而是统一落 `discarded` tool_result
  - 新增回归覆盖“前一个并行读 batch 已 discarded，后续 edit batch 必须 discarded 且不得改文件”的 transcript 语义
- 影响范围：
  - discard-on-retry transcript contract
  - 多 batch assistant plan 的安全边界
  - 写动作在部分失败后的继续执行策略
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 在真实 C 工程回归里验证 compile/test/diagnose 链路上的 discard-on-retry 体验
  - 评估是否要把 discarded 的 reason contract 再细分为 cancel / retry 两类

### DC-054

- 日期：2026-04-02
- 变更主题：并行执行器现在直接观察 cancel event
- 变更摘要：
  - `StreamingToolExecutor` 现在在 worker 获得并发槽位后，会直接检查 cancel event，而不再只等主线程处理 update 后再转述 `discard()`
  - 这让 `max_parallel_tools>1` 时尚未启动的 queued action 在取消后保持 `discarded`，不会因为主线程观察延迟而偷偷变成已启动的 `interrupted`
  - 新增高并发回归，覆盖“两条慢读已启动、第三条排队、取消后第三条仍应 discarded”的 transcript 语义
- 影响范围：
  - 并行 tool batch 的取消边界
  - discard vs interrupted 的 transcript 语义
  - 高并发 focused regression
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续覆盖更复杂的 multi-batch retry 组合边界
  - 评估是否要把 cancel/discard contract 明确写成独立文档

### DC-053

- 日期：2026-04-02
- 变更主题：Windows 长命令中断已切到进程组 + CTRL_BREAK_EVENT
- 变更摘要：
  - `run_command` 现在在 Windows 下以新进程组启动子进程，取消时优先发送 `CTRL_BREAK_EVENT`
  - 这让长命令用户中断不再依赖 `taskkill` 成功，避免当前运行环境里 `taskkill` 返回 `Access denied` 时仍然要等命令自然结束
  - Query loop 现在可以更稳定地得到非 synthetic 的 interrupted observation，并及时以 `aborted` transition 收束
- 影响范围：
  - Tool runtime 的 Windows 中断语义
  - 长命令取消时的端到端响应延迟
  - interrupt/retry focused regression
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续覆盖更高并发下的 abort/retry 组合边界
  - 评估 compile/test/toolchain 类工具是否也需要复用更细的 runtime interrupt contract

### DC-049

- 日期：2026-04-02
- 变更主题：中断后的 synthetic interrupted tool_result 已接入 transcript 主线
- 变更摘要：
  - 当会话在 `tool_started` 之后被取消时，`QueryEngine` 现在会生成 synthetic interrupted observation，而不是让工具调用只留下 `tool_call` 没有结果
  - 该 synthetic result 会同步写入 transcript、session observation、timeline 和 adapter 的 `tool_finished` 事件
  - 会话最终仍以 `aborted` transition 收束，但前端和恢复链现在都能看到更完整的“中断发生在工具执行阶段”语义
- 影响范围：
  - Query loop 中断语义
  - Transcript 完整性
  - Adapter / timeline 的取消态投影
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 discard-on-retry transcript 语义
  - 收紧多 tool batch 下的 abort 边界
  - 评估长命令 / tool runtime 的真实 interrupt 行为

### DC-050

- 日期：2026-04-02
- 变更主题：discarded synthetic result 不再误触发 guard stop
- 变更摘要：
  - parallel batch 中被丢弃的 synthetic `discarded` tool_result 仍会写入 transcript 和 session observation
  - `LoopGuard` 现在不会把 `discarded` / `interrupted` synthetic result 当成真实工具失败累计
  - 这避免了“第一个只读工具失败，后续被丢弃的工具结果反而把整轮提前打成 `guard_stop`”的错误语义
- 影响范围：
  - parallel tool batch 的失败路径
  - QueryEngine 的 retry/abort 行为
  - transcript 中 synthetic result 的语义一致性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补多 tool batch 下的 abort 边界
  - 明确 discard-on-retry 的更细 transcript contract

### DC-051

- 日期：2026-04-02
- 变更主题：并行 tool batch 已切到流式 start/result writeback
- 变更摘要：
  - `StreamingToolExecutor` 的并行批次不再一次性收集完结果后整体返回，而是改为流式发出 `start` / 有序 `result`
  - 这让 `QueryEngine` 能在看到 `tool_started` 后及时 `discard()` 尚未开始的后续 action
  - 在 `max_parallel_tools=1` 等受控场景下，当前已验证“首个 action interrupted、后续未开始 action discarded”的 transcript 语义
- 影响范围：
  - Tool batch 执行时序
  - QueryEngine 的 cancel/discard 协同
  - interrupt/retry transcript 一致性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补更高并发下的 abort/retry 组合边界
  - 评估是否需要显式 progress event / result buffering contract 文档

### DC-052

- 日期：2026-04-02
- 变更主题：tool_call transcript 改为在 assistant action 阶段统一落盘
- 变更摘要：
  - `tool_call` transcript event 不再依赖实际 start 时机，而是在 assistant 产出 action 后就按原始顺序统一写入
  - 这保证了后续 action 即使因取消而变成 `discarded`，仍然有完整的 `tool_call -> tool_result` transcript 链路
  - `SessionRestorer` 也已避免为同一 `call_id` 重复创建 `ToolCallRecord`
- 影响范围：
  - Transcript 完整性
  - Resume replay 的 tool-call 重建
  - 并行 batch 取消场景的可审计性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续验证更高并发下 `tool_call` / `tool_result` 顺序与 retry 组合语义

### DC-048

- 日期：2026-04-02
- 变更主题：Resume truth source switched to transcript replay
- 变更摘要：
  - 新增 append-only session transcript 持久化，路径为 `.embedagent/memory/sessions/<session_id>/transcript.jsonl`
  - 新增 `SessionRestorer`，可按 transcript event replay 重建 `Session`
  - `resume_session()` 已从 summary-driven reconstruction 切到 transcript-driven replay
  - `summary.json` / snapshot 数据已降级为 derived projection，不再作为恢复真相源
- 影响范围：
  - Session persistence
  - Resume 语义
  - Context replacement / compact snapshot 持久化
  - Frontend snapshot/timeline projection 的恢复来源
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/archive/transcript-truth-tool-result-cutover/2026-04-02-full-transcript-persistence-design.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 补 interrupt / synthetic tool_result / discard-on-retry 的 transcript 语义
  - 补更贴近真实工程的 transcript restore 集成回归
  - 继续收缩 summary-only 兼容路径

### DC-046

- 日期：2026-04-02
- 变更主题：QueryEngine 增加 reactive compact retry
- 变更摘要：
  - `QueryEngine` 现在会识别 `prompt/context too long` 一类 LLM 错误，并在同一步内触发一次内部 `compact_retry`
  - retry 前会尽量落下 `CompactBoundary`，随后以更紧的 compact budget 重组上下文，再自动重试一次模型调用
  - compact retry 仍保持原始 mode 作为工具过滤和 workspace intelligence 选证依据，不把 `compact` 暴露成用户可切换 mode
- 影响范围：
  - Query loop 状态迁移
  - Context pipeline 的内部 compact 策略
  - 长任务上下文超限后的恢复体验
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 把 retry 触发条件从字符串匹配升级为更稳的 provider/error contract
  - 继续补 LLM compact 与多次 retry 的边界策略
  - 补 adapter/session snapshot 对 compact retry 的显式可观测性

### DC-047

- 日期：2026-04-02
- 变更主题：compact retry 已投影到 snapshot 与 timeline
- 变更摘要：
  - `SessionSummaryStore` / `SessionSnapshot` 现在会暴露 `last_transition_reason`、`recent_transition_reasons` 与 `compact_retry_count`
  - `InProcessAdapter` 在检测到 `reactive_compact_retry` 上下文装配时，会额外发出 `compact_retry` event，前端和调试工具可直接从 timeline 观察到自动压缩重试
  - 这让 compact retry 不再只是 loop 内部细节，而是成为可调试、可回归验证的显式状态
- 影响范围：
  - Session summary / snapshot 协议
  - Timeline event 可观测性
  - 前端调试和 QA 回归
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 决定 GUI inspector 是否要给 compact retry 单独展示卡片/徽标
  - 继续把更多 transition 信息投影为结构化 timeline 语义

### DC-048

- 日期：2026-04-02
- 变更主题：structured timeline 保留 compact retry transitions
- 变更摘要：
  - `build_structured_timeline()` 现在会在 turn/step 级别保留 `transitions`
  - `compact_retry`、`context_compacted`、`mode_changed` 这类事件不再只存在于 raw events，而能进入结构化 timeline 供 GUI 直接消费
  - 这让 step-based timeline 和 snapshot 对同一条状态机变化的观察口径开始收敛
- 影响范围：
  - 结构化时间线协议
  - GUI step timeline / inspector 展示能力
  - 前端回归测试口径
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 决定 transitions 在 GUI 中的展示形式
  - 继续把更多 loop transition 结构化到 step/turn 记录中

### DC-049

- 日期：2026-04-02
- 变更主题：structured timeline 保留 waiting-state transitions
- 变更摘要：
  - `build_structured_timeline()` 现在会把 `user_input_required` / `permission_required` 作为 turn/step 级 transition 保留下来
  - 当会话进入等待态时，structured timeline 的 turn 状态也会同步更新为 `waiting_user_input` 或 `waiting_permission`
  - 这让 pending interaction 不再只靠 snapshot 判断，structured timeline 也能完整表达“为什么停住了”
- 影响范围：
  - 结构化时间线协议
  - pending interaction 的前端展示能力
  - 调试与回归测试口径
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续把 `guard_stop / max_turns / aborted` 等终止态也统一投影到 structured timeline transitions

### DC-050

- 日期：2026-04-02
- 变更主题：structured timeline 开始保留终止态 transitions
- 变更摘要：
  - `turn_end` 的 `termination_reason` 现在会在非 `completed` 情况下同步投影到 structured timeline transitions
  - 目前已覆盖 `max_turns`，同一条规则也为后续 `guard_stop / cancelled` 留好了入口
  - 这样 structured timeline 不再只靠 turn status 文本表达终止原因，而是能把它当成显式状态机事件
- 影响范围：
  - 结构化时间线协议
  - loop 终止态的前端可观测性
  - 调试与回归测试口径
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 补 `guard_stop / cancelled` 的回归测试
  - 决定 GUI 是否对终止态 transitions 做统一展示

### DC-051

- 日期：2026-04-02
- 变更主题：structured timeline 终止态补齐停止原因文本
- 变更摘要：
  - `turn_end` / `session_finished` 现在会携带 `error` 字段，把 loop 终止时的原因文本显式传给前端
  - structured timeline 中由终止态生成的 transition 会直接消费这段文本，而不再只暴露一个无说明的 `kind`
  - 这让 `max_turns` 以及后续 `guard / cancelled` 的展示和排障信息更完整
- 影响范围：
  - turn_end / session_finished 事件契约
  - structured timeline transition 语义
  - 前端调试与展示质量
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 `guard_stop / cancelled` 的专项测试

### DC-052

- 日期：2026-04-02
- 变更主题：snapshot 补齐最后 transition 的原因文本
- 变更摘要：
  - `SessionSummaryStore` / `SessionSnapshot` 现在会暴露 `last_transition_message`
  - adapter 在会话结束后会重新持久化一次最终 session，使 `max_turns` 等最后才落下的 transition 进入 summary / snapshot
  - 这让前端无需强依赖 timeline，也能直接解释当前 session 的最后状态
- 影响范围：
  - Session summary / snapshot 协议
  - 会话结束时的持久化链路
  - 前端状态说明质量
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 `guard_stop / cancelled` 的 snapshot/timeline 一致性测试

### DC-053

- 日期：2026-04-02
- 变更主题：snapshot 补齐结构化 recent transitions
- 变更摘要：
  - `SessionSummaryStore` 现在会持久化 `recent_transitions`，每项包含 `reason`、`message` 与 `display_reason`
  - `SessionSnapshot` 已投影这一结构化列表，前端可直接消费最近几条状态迁移，而不必先解析 raw timeline
  - 对历史 summary，如果 `recent_transitions` 尚未带 `display_reason`，adapter 也会在读取 snapshot 时即时补齐
  - 这让 snapshot 和 structured timeline 之间的可观测性口径进一步靠近
- 影响范围：
  - Session summary / snapshot 协议
  - 前端状态面板与调试能力
  - transition 相关回归测试
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 `guard_stop / cancelled` 的专项回归
  - 视 GUI 需求决定 recent transitions 的展示排序与截断策略

### DC-054

- 日期：2026-04-02
- 变更主题：snapshot 补齐 display 级 transition reason
- 变更摘要：
  - `SessionSnapshot` 现在会额外暴露 `last_transition_display_reason`
  - 该字段把内部 loop reason 映射到更适合前端消费的语义，例如 `aborted -> cancelled`、`guard_stop -> guard`
  - `build_structured_timeline()` 里的 transition 项现在也会带上同一套 `display_reason`
  - 这让前端可以同时保留底层 raw reason 和用户可读 reason，而无需在 UI 层硬编码映射表
- 影响范围：
  - Session snapshot 协议
  - 前端状态文案与展示逻辑
  - transition 相关回归测试
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 视 GUI 需求决定是否把 `display_reason` 进一步统一成完整的展示文案层模型

### DC-045

- 日期：2026-04-02
- 变更主题：Workspace intelligence 的诊断热点改为按工作集优先聚合
- 变更摘要：
  - `DiagnosticsProvider` 不再只返回最近两条原始诊断摘录，而是先按文件聚合 compile / test / tidy / analyzer 等诊断热点
  - 最近编辑/读取过的工作集文件会优先于“仅出现在报错输出里的文件”，避免被动报错文件抢占焦点
  - 同一文件上的多条诊断会折叠为一条热点证据，并带出诊断数量、来源工具集合与最新一条摘要，便于 `code/debug/verify` 模式把首屏上下文留给更有操作价值的问题
- 影响范围：
  - Workspace intelligence 证据选择
  - Context pipeline 首屏上下文质量
  - Diagnostics / Problems 聚合的一致性预期
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续补 pathless 的 failing tests / quality gate / coverage 热点聚合
  - 后续把 LLSP/clangd 的引用链与调用关系证据并入同一热点选择器
  - 观察 GUI Problems / timeline inspector 是否也应复用同一聚合逻辑

### DC-056

- 日期：2026-04-02
- 变更主题：DiagnosticsProvider 已补 quality gate / pathless summary 聚合
- 变更摘要：
  - `verify` 模式下，`DiagnosticsProvider` 现在会把 `report_quality`、`run_tests`、`collect_coverage` 等无明确文件路径的失败或告警聚成一条 `Quality Gate Summary`
  - 这让质量门信息不再散落成多条 pathless observation，而能以单条高优先级证据进入 workspace intelligence
  - 若没有 `report_quality` 但存在多条无路径诊断，provider 也会退化输出 `Pathless Diagnostics` 摘要
- 影响范围：
  - verify mode 的工程情报首屏质量
  - quality gate / test / coverage 的上下文聚合
  - DiagnosticsProvider 的 pathless failure contract
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续深化 `RecipeProvider` 的 mode-aware 选证
  - 评估 GUI Problems / inspector 是否也应直接复用这条 quality gate summary

### DC-057

- 日期：2026-04-02
- 变更主题：RecipeProvider 已补 mode-aware source/stage 排序
- 变更摘要：
  - `RecipeProvider` 现在不再只按 `tool_name + id` 粗排，而是按 mode 区分 `project / history / detected` 的来源优先级
  - `code/debug` 模式更偏显式 project recipe 和 detected build 链路，`verify` 模式则更偏 project/history 的 test recipe
  - `stage` 现在也参与 tie-break，因此 `build / test / configure` 在不同 mode 下有更稳定的相对顺序
- 影响范围：
  - workspace intelligence 的 recipe 首屏质量
  - `/recipes` / `/run` 之前的模型选证
  - code/debug/verify 模式下的 recipe 提示稳定性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 评估是否要引入 session hint 作为 recipe tie-break
  - 继续推进真实 `LlspProvider`

### DC-058

- 日期：2026-04-02
- 变更主题：GUI inspector 已开始直接消费 display_reason
- 变更摘要：
  - 前端 `normalizeSessionPayload()` 现在会保留 `last_transition_display_reason`、`last_transition_message` 与 `recent_transitions`
  - GUI Runtime inspector 已开始直接展示最后状态与最近状态迁移，优先使用 `display_reason` 而不是内部 `reason`
  - `loadSession()` 也已统一走 snapshot normalize，避免刷新/切会话后 다시退回原始 payload 导致前端丢字段
- 影响范围：
  - GUI inspector 状态语义
  - Session snapshot 到前端的字段透传一致性
  - 前端 helper tests
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-plan.md`
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/development-tracker.md`
  - `docs/query-context-redesign.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续判断 `step/turn` 是否还需要 raw/internal 双层语义
  - 评估是否把相同展示语义继续下沉到 timeline 顶部终止态提示

### DC-059

- 日期：2026-04-02
- 变更主题：GUI webapp 本地验证链补齐显式 esbuild 依赖与根目录 test runner
- 变更摘要：
  - `build.mjs` 直接依赖 `esbuild`，现在 `package.json` / `package-lock.json` 已把它声明为显式 `devDependency`
  - 新增 webapp 根目录 `run-local-tests.mjs`，把原有 helper checks 与 `node:test` 回归统一成一个直接可运行的本地测试入口
  - 当前已确认可复跑的本地命令链是：`npm install`、`node .\\run-local-tests.mjs`、`npm run build`
- 影响范围：
  - GUI webapp 本地开发验证
  - webapp 依赖声明完整性
  - 静态资源重建链路
- 关联文档：
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 若后续继续依赖 npm script runner，再单独调查当前环境里 `npm test` 的 `EPERM lstat C:\\Users\\Administrator` 异常

### DC-044

- 日期：2026-04-02
- 变更主题：上下文与 Query Loop 激进重构切片落地
- 变更摘要：
  - `session.py` 已升级为 transcript/event 基础模型，新增 `TranscriptMessage`、`ToolCallRecord`、`AgentStepState`、`PendingInteraction`、`LoopTransition`、`CompactBoundary` 与 `ContextAssemblyResult`
  - 新增 `query_engine.py` 作为真实主循环；`loop.py` 已退化为兼容 shim
  - `ContextManager.build_messages(...)` 已扩展为上下文流水线入口，开始接入 workspace intelligence、tool result replacement、duplicate suppression、activity folding 与 compact boundary 复用
  - 新增 `workspace_intelligence.py`，统一挂接 `WorkingSet / ProjectMemory / Recipe / Ctags / Diagnostics / Git / Llsp(empty)` provider
  - `ToolDefinition` 与 `ToolRuntime` 已补齐 `read_only / concurrency_safe / interrupt_behavior / result_budget_policy / activity_kind / context_priority`
  - 新增 `tool_execution.py`，提供批处理分组与流式工具执行器骨架
  - `InProcessAdapter` 已开始采用 pending interaction + resume 主链路，不再只依赖线程阻塞等待 `ask_user` / permission
- 影响范围：
  - Agent Core 主循环
  - 会话与 transcript 模型
  - 上下文管理
  - Tool Runtime 能力模型
  - 前端兼容投影
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `README.md`
- 是否需要 ADR：`建议后续补一条 Query / Context 内核 ADR`
- 后续动作：
  - 继续把 reactive compact、resume consistency 与 workspace intelligence provider 深化到真实工程场景
  - 逐步把旧的 event-blocking 交互路径完全切换到 pending interaction / resume
  - 扩充对旧测试集的兼容回归覆盖

### DC-043

- 日期：2026-04-02
- 变更主题：离线打包切换到 `package.ps1` 控制面
- 变更摘要：
  - 新增 `scripts/package.config.json`、`scripts/package-lib.ps1` 与 `scripts/package.ps1`，把离线打包的公共入口收敛为 `doctor` / `deps` / `assemble` / `verify` / `release`
  - 现有 `export-dependencies.py`、`prepare-offline.ps1`、`build-offline-bundle.ps1`、`validate-offline-bundle.ps1` 与 `check-bundle-dependencies.py` 继续保留，但转为控制面内部 stage 或兼容入口
  - `tests/test_packaging_control_plane.py` 已覆盖 foundation、stage JSON 报告、doctor 契约以及 mocked orchestration；`tests/fixtures/package/` 提供最小 mock stage 夹具
  - `build/offline-reports/` 现在成为控制面统一的阶段报告与最终报告目录，`release -Json` 可直接输出机器可读状态
  - 对外文档开始全面改口：用户和维护者默认不再串联旧多脚本流程，而是从 `pwsh -File scripts/package.ps1 release` 开始
- 影响范围：
  - Phase 7 打包控制面
  - 脚本职责分层
  - operator-facing 文档与部署流程
  - 后续真实 bundle 验收口径
- 关联文档：
  - `docs/offline-packaging-guide.md`
  - `docs/offline-packaging.md`
  - `docs/intranet-deployment.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
  - `docs/adrs/0004-packaging-control-plane-redesign.md`
- 是否需要 ADR：`是`
- 后续动作：
  - 在真实 bundle 路径上验证 `package.ps1 release`
  - 继续收紧 `site-packages` 导出策略
  - 在 Win7 实机上补控制面主路径验收

### DC-042

- 日期：2026-04-01
- 变更主题：recipe-aware build/test 入口与 GUI Run / Problems 面板
- 变更摘要：
  - 新增 `workspace_recipes.py`，统一收集项目自定义 recipe、自动检测的 `CMakeLists.txt` / `Makefile` recipe，以及历史成功命令 recipe
  - `compile_project` / `run_tests` / `run_clang_tidy` / `run_clang_analyzer` / `collect_coverage` 已支持 `recipe_id`，并把 `recipe_id`、`recipe_source`、`recipe_label` 回写到 Observation
  - `InProcessAdapter` 与 GUI backend 已暴露 workspace recipe API；slash command 新增 `/recipes` 与 `/run <recipe_id>`
  - GUI Inspector 已新增 `Run` / `Problems` 面板：Run 用于查看并直接执行 recipe，Problems 用于聚合最近 diagnostics / failing tests / quality reasons
  - workspace profile 会把探测到的 recipe 样本注入给 Agent，减少后续 build/test 仍走自由拼命令的概率
- 影响范围：
  - Tool Runtime recipe 解析
  - slash command / workspace API
  - GUI Inspector 工作台
  - Agent workspace profile 注入
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续把 recipe / preset 扩展到更强的 `target / profile / coverage` 工作流
  - 在 Win7 bundle 中验证 Run / Problems 与 step timeline 的联动

### DC-041

- 日期：2026-04-01
- 变更主题：Agent step 时间线与托管运行环境摘要接入 GUI 壳层
- 变更摘要：
  - `AgentLoop` / `InProcessAdapter` 现在会在单个用户 turn 内生成多个 agent step，并写出 `step_start` / `step_end`
  - `build_structured_timeline()` 已从旧的扁平事件推断切换为以 `turns[].steps[]` 为主，同时保留 raw events 作为调试/回放补充
  - `ToolRuntime` / `ToolContext` 新增托管运行环境摘要，统一产出 `runtime_source`、`bundled_tools_ready`、`fallback_warnings` 与 `resolved_tool_roots`
  - GUI timeline 已改为按 turn 下的多个 step 呈现 thinking / tool / assistant；Inspector 新增 Runtime 面板
  - `styles.css` 已与 `Timeline.jsx` / `Sidebar.jsx` / `Inspector.jsx` / `Composer.jsx` 的类名重新对齐，修复缺失卡片与样式漂移
- 影响范围：
  - AgentLoop 与 InProcessAdapter 事件模型
  - 协议层 `TurnRecord` / `SessionSnapshot`
  - Tool Runtime 与 GUI Runtime inspector
  - GUI 时间线与样式系统
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/adrs/0003-agent-step-timeline-and-managed-runtime-shell.md`
- 是否需要 ADR：`是`
- 后续动作：
  - 在 Phase 2 中把 build/test/tidy/coverage 收敛到默认 recipe / preset
  - 继续推进 Runtime inspector 与 Problems / Diagnostics / Diff 工作台联动
  - 在 Win7 bundle 中验证 step-based GUI 与托管环境路径

### DC-040

- 日期：2026-03-31
- 变更主题：离线 bundle GUI 布局重新对齐与 editable path 泄漏修复
- 变更摘要：
  - 确认 `build/offline-dist/` 先前之所以仍是旧的 `static/js` / `static/css` 布局，不是 `prepare-offline.ps1` 回退了静态资源，而是旧 dist 根本没有在 GUI webapp 迁移到 `static/assets` 之后重新构建
  - `prepare-offline.ps1` 现在会在复制 `site-packages` 后清理指向开发工作区的 `__editable__*.pth`，避免 bundle 运行时串回本机源码树
  - `build-offline-bundle.ps1` 现在正确透传 `WebView2RuntimeRoot`，并在重建时显式接入 `webview2_fixed_runtime_x64`
  - `prepare-offline.ps1` 的压缩包解包逻辑改成基于 `System.IO.Compression.ZipFile`，从而真正支持 `.nupkg` 形式的 WebView2 runtime 资产
  - bundle 生成的 `embedagent-gui.cmd` 改为直接执行 bundle 内 `launcher.py`，并设置 `PYTHONNOUSERSITE=1`，减少 `runpy` warning 与宿主环境污染
  - `validate-offline-bundle.ps1` 与 `check-bundle-dependencies.py` 新增对 `__editable__*.pth` 的门禁检查；重建后的 dist 已通过 `validate-offline-bundle.ps1`、bundle 级 `validate-gui-smoke.py` 与 `check-bundle-dependencies.py`
- 影响范围：
  - Phase 7 prepare/build/validate 脚本
  - bundle GUI launcher 稳定性
  - 离线包对宿主开发环境的隔离性
- 关联文档：
  - `docs/development-tracker.md`
  - `scripts/prepare-offline.ps1`
  - `scripts/build-offline-bundle.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `scripts/check-bundle-dependencies.py`
- 是否需要 ADR：`否`
- 后续动作：
  - 在 Win7 目标机上执行 `validate-gui-smoke.cmd --windowed`
  - 继续推进 `site-packages` 精简导出，减少 bundle 体积
  - 视需要把“禁止 bundle 残留 editable path”纳入更多自动化入口

### DC-039

- 日期：2026-03-31
- 变更主题：补强 workflow/filtering 回归测试与 GUI smoke 的 `/review` 覆盖
- 变更摘要：
  - `tests/test_tools_package.py` 新增 `schemas_for(mode, workflow_state)` 过滤回归，确认 `spec` 在 `review` workflow 下不会暴露写工具，`verify` 仍保留质量门工具
  - `ToolRuntime.execute()` 的 metadata 回灌新增回归断言，确保 `tool_label`、`permission_category`、renderer key 与 `supports_diff_preview` 在观察结果里稳定存在
  - GUI webapp `test/run-tests.mjs` 新增 reducer 级状态断言，覆盖 review command result 和 permission context inspector 所依赖的状态流
  - `scripts/validate-gui-smoke.py` 现在会显式执行 `/review`，让源码路径 smoke 覆盖 command/workflow 链路，而不仅是普通对话与工具调用
  - 当前验证也暴露出 `build/offline-dist/` 里的既有 bundle 仍是旧 GUI 布局（`static/js` / `static/css`），尚未与最新 validator 所要求的 `static/assets` / Fixed Version WebView2 路径完全同步
- 影响范围：
  - Core workflow/tool filtering 回归测试
  - GUI 状态层 smoke 与 reducer 回归
  - Phase 7 bundle/source 布局一致性检查
- 关联文档：
  - `docs/development-tracker.md`
  - `tests/test_tools_package.py`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `scripts/validate-gui-smoke.py`
- 是否需要 ADR：`否`
- 后续动作：
  - 重新生成离线 bundle，并在新 bundle 上重跑 `validate-offline-bundle.ps1`
  - 用 bundle 级 `validate-gui-smoke.py` 复核 `/review` workflow 与 renderer runtime 路径
  - 继续收敛 GUI 打包产物布局，避免 source 与 dist 结构漂移

### DC-034

- 日期：2026-03-31
- 变更主题：统一输入总线与 slash command / workflow 第一版
- 变更摘要：
  - `submit_user_message` 升级为统一输入入口，先分发普通消息与 slash command，再决定是否进入 `AgentLoop`
  - 新增 `/help`、`/mode`、`/sessions`、`/resume`、`/workspace`、`/clear`、`/plan`、`/review`、`/diff`、`/permissions`、`/todos`、`/artifacts`
  - 新增 `CommandResult`、`PlanSnapshot`、`TurnRecord`、`TimelineItem`、`PermissionContextView`，并扩展 `SessionSnapshot`
  - GUI 已接入 command result、plan pane、timeline command cards、slash command hint；TUI 已可透传核心 workflow 命令
- 影响范围：
  - Core 输入分发
  - 协议层
  - GUI/TUI 交互层
  - 会话计划与权限上下文
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/adrs/0002-gui-workflow-shell-clean-room.md`
- 是否需要 ADR：`是`
- 后续动作：
  - 继续把 `/review`、`/permissions`、`/diff` 的 GUI inspector 表现收口
  - 在 Win7 bundle 中完成 GUI workflow / plan pane / renderer 路径验收

### DC-035

- 日期：2026-03-31
- 变更主题：`/review` 结构化 findings 与 renderer metadata 前端消费
- 变更摘要：
  - `/review` 不再只返回普通文本，而是输出带 `priority` / `severity` / `title` / `body` / `evidence` 的 findings 列表
  - GUI timeline 新增 review result 卡片，能够直接渲染 findings 与 residual risks
  - 工具事件开始把 `progress_renderer_key` / `result_renderer_key` 从 Core 传到前端，GUI 工具卡片已按 renderer key 展示不同摘要
  - `permissions` inspector 已独立于 `plan` inspector，减少工作流视图混杂
- 影响范围：
  - command/workflow 结果模型
  - GUI timeline 与 inspector 渲染
  - tool metadata 消费链路
- 关联文档：
  - `docs/development-tracker.md`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续把 quality / diagnostics / coverage 的 review evidence 展示细化到 inspector
  - 继续减少前端 `toolName -> UI` 的硬编码映射

### DC-036

- 日期：2026-03-31
- 变更主题：review inspector 独立化与 tool catalog API 前端 fallback
- 变更摘要：
  - GUI inspector 新增独立 `review` 面板，`/review` 的结构化结果不再只存在于 timeline bubble
  - 后端新增 tool catalog API，前端会在事件未携带完整 label / renderer 时使用 Core 工具目录做 fallback
  - 这让前端进一步从“猜测工具展示”转向“消费 Core 工具定义”
- 影响范围：
  - GUI inspector 信息架构
  - 前后端工具元数据链路
  - 旧 timeline / fallback 展示逻辑
- 关联文档：
  - `docs/development-tracker.md`
  - `src/embedagent/frontend/gui/backend/server.py`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- 是否需要 ADR：`否`
- 后续动作：
  - 把 permissions inspector 从 JSON 视图升级为结构化规则列表
  - 继续把 review evidence 细化为可展开的 diagnostics / tests / coverage 分组

### DC-001

- 日期：2026-03-27
- 变更主题：确立 Windows 7 离线 Agent Core 总体架构
- 变更摘要：
  - 确立 `Frontend -> Agent Core API -> Orchestration -> Runtime/LLM/State` 分层
  - 确立 Agent Core 为产品本体，前端可替换
  - 确立 Python 3.8、离线打包、Clang 生态为主线
- 影响范围：
  - 总体架构
  - 技术选型
  - 运行时约束
- 关联文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
- 是否需要 ADR：`暂缓`
- 后续动作：
  - 进入 Core 骨架细化

### DC-002

- 日期：2026-03-27
- 变更主题：确立可配置模式与 Agent Harness
- 变更摘要：
  - 确立模式是 Core 契约而不是 UI 标签
  - 确立 `ask / orchestra / spec / code / test / verify / debug / compact` 模式集
  - 确立 `Spec-Driven + TDD + Coverage/MC/DC Gate` 默认工程方法学
- 影响范围：
  - Core 设计
  - Harness 设计
  - 多智能体演进路径
- 关联文档：
  - `docs/overall-solution-architecture.md`
  - `AGENTS.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`建议后续补`
- 后续动作：
  - 编写 `docs/mode-schema.md`
  - 编写 `docs/harness-state-machine.md`

### DC-003

- 日期：2026-03-27
- 变更主题：建立文档治理与版本策略
- 变更摘要：
  - 建立 `AGENTS.md`
  - 建立 `implementation-roadmap.md`
  - 建立 `docs/adrs/`
  - 锁定 Python `>=3.8,<3.9`
  - 明确 `uv` 优先、`conda` 兜底
- 影响范围：
  - 开发环境
  - 文档治理
  - 后续实现纪律
- 关联文档：
  - `AGENTS.md`
  - `docs/implementation-roadmap.md`
  - `.python-version`
  - `pyproject.toml`
- 是否需要 ADR：`可不单独写`
- 后续动作：
  - 建立进度跟踪文件
  - 在每轮关键设计调整时持续维护本文件

### DC-004

- 日期：2026-03-27
- 变更主题：工具集设计提升为一等公民
- 变更摘要：
  - 内网模型（GLM5 int4、Qwen3.5）验证表明工具集设计质量是系统稳定性的关键变量
  - 确立每个模式工具上限 5 个（目标 3-4 个）
  - 确立工具描述模板：中文描述 + 英文命名，三段结构，参数含示例
  - 确立 7 类工具设计反模式（禁止使用）
  - 确立结构化 Observation 规范
  - Clang on Win7 风险项解除：已验证完全静态链接的最新版 Clang 可正常运行
- 影响范围：
  - 所有工具的实现与 schema 编写
  - 工具数量与模式分配
  - 工具返回值结构
- 关联文档：
  - `docs/tool-design-spec.md`（新建）
  - `docs/overall-solution-architecture.md`（补充 §8.3a）
  - `AGENTS.md`（补充工具规范约束）
- 是否需要 ADR：`暂缓，先在 Phase 1 验证后再决定是否需要`
- 后续动作：
  - 每次新增工具前必须过 `docs/tool-design-spec.md` 审查清单
  - Phase 1 完成后根据实际测试结果补充兼容处理细节

### DC-005

- 日期：2026-03-27
- 变更主题：实施分期重组，关键路径前移
- 变更摘要：
  - 原 Phase 1（Core 骨架）+ 原 Phase 3（LLM Adapter）合并为新 Phase 1（最小可工作 Loop）
  - Phase 2 改为工具集 v1（run_command + git），Phase 3 改为模式系统 v1
  - 每个 Phase 结束时必须有可实际运行的端到端验证点
  - `orchestra` 模式推迟到 Phase 3 之后实现
  - Harness 改为分阶段叠加：Phase 1 无 Harness，Phase 3 引入 dict 实现，Phase 5 可选 TOML
- 影响范围：
  - 实施顺序与里程碑定义
  - 开发节奏（从文档驱动转为端到端验证驱动）
- 关联文档：
  - `docs/implementation-roadmap.md`（Phase 1-5 重写）
  - `docs/development-tracker.md`（里程碑、任务板、风险更新）
  - `docs/overall-solution-architecture.md`（补充 Harness 演进路径）
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 直接进入 Phase 1 编码

### DC-006

- 日期：2026-03-27
- 变更主题：Phase 1 骨架收敛到 `src/embedagent`，模型验证策略允许受限替代
- 变更摘要：
  - 将 Phase 1 原型代码从仓库根目录平铺模块收敛到 `src/embedagent/` 包结构
  - `pyproject.toml` 同步切换为 `src` 布局与 console script 入口
  - 当 `GLM5 int4` / `Qwen3.5` 联调环境暂不可用时，允许用可访问的 OpenAI-compatible 服务完成真实 function calling 闭环验证
  - 基于 Moonshot `kimi-k2.5` 补齐了 `temperature` 与 `reasoning_content` 兼容处理
- 影响范围：
  - 代码组织结构
  - Phase 1 验证口径
  - LLM 适配层兼容策略
- 关联文档：
  - `pyproject.toml`
  - `README.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/llm-adapter.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 进入 Phase 2 工具集实现

### DC-007

- 日期：2026-03-28
- 变更主题：Phase 2 工具集 v1 落地并验收
- 变更摘要：
  - 在 `src/embedagent/tools/` 包中实现 `run_command`、`git_status`、`git_diff`、`git_log`
  - 命令执行支持超时终止，并在 Windows 上使用 `taskkill /F /T /PID` 处理进程树
  - 建立 `docs/tool-contracts.md` 记录当前工具 Observation 契约
  - 在 Python 3.8.10 环境下完成工具直调与 Loop 烟雾验证
- 影响范围：
  - Tool Runtime
  - Phase 2 验证口径
  - 后续模式系统的工具过滤基线
- 关联文档：
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/tools/shell_ops.py`
  - `src/embedagent/tools/git_ops.py`
  - `docs/tool-contracts.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 进入 Phase 3 模式系统 v1

### DC-008

- 日期：2026-03-28
- 变更主题：Phase 3 模式系统 v1 落地并验收
- 变更摘要：
  - 新增 `src/embedagent/modes.py`，以 Python dict 形式定义 `MODE_REGISTRY`
  - Loop 按当前模式过滤工具，并对违规工具调用返回失败 Observation
  - 实现 `switch_mode(target)` 工具与用户显式 `/mode <name>` 入口
  - `edit_file` 增加基于 `writable_globs` 的写入边界检查
  - 新增 `docs/mode-schema.md` 与 `docs/harness-state-machine.md`
- 影响范围：
  - Agent Loop
  - CLI 入口
  - Tool Runtime 调用边界
  - 后续 Harness 演进基线
- 关联文档：
  - `src/embedagent/modes.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/cli.py`
  - `docs/mode-schema.md`
  - `docs/harness-state-machine.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 进入 Phase 4 Clang 工具链实现

### DC-009

- 日期：2026-03-28
- 变更主题：Phase 4 工具链第一版封装落地
- 变更摘要：
  - 在 `src/embedagent/tools/build_ops.py` 中新增 `compile_project`、`run_tests`、`run_clang_tidy`、`run_clang_analyzer`、`collect_coverage`、`report_quality`
  - 引入 Clang/MSVC 风格诊断解析、测试结果统计和覆盖率摘要提取
  - 调整 `code` / `test` / `verify` 模式工具集，使其更贴近阶段职责
  - 建立 `docs/clang-integration-plan.md`，明确当前采用显式 command 封装、后续再接真实工具链
- 影响范围：
  - Tool Runtime
  - Mode Registry
  - Phase 4 验证口径
- 关联文档：
  - `src/embedagent/tools/build_ops.py`
  - `src/embedagent/modes.py`
  - `docs/tool-contracts.md`
  - `docs/clang-integration-plan.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 接入真实项目构建命令与 Clang 二进制路径

### DC-010

- 日期：2026-03-28
- 变更主题：项目内闭环 Clang 工具链组装与验证
- 变更摘要：
  - 下载并测试多个静态 Windows LLVM/Clang 发行包
  - 基于 `clang-20.1.8 libcmt`、静态 `clang-tidy` 和 `win-llvm 21.1.8` 组装出 `toolchains/llvm/current`
  - 在 `ToolRuntime` 中为子进程自动注入 `toolchains/llvm/current/bin` 与 `libexec`
  - 补本地 `clang-analyzer` 包装入口
  - 完成编译、静态分析、clang-tidy、profdata、llvm-cov 的真实 smoke test
- 影响范围：
  - 本地工具链目录布局
  - Tool Runtime 的子进程环境
  - Phase 4 验证口径
- 关联文档：
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/tools/build_ops.py`
  - `docs/clang-integration-plan.md`
  - `toolchains/README.md`
  - `toolchains/manifest.json`
  - `scripts/activate-bundled-llvm.ps1`
  - `scripts/test-bundled-llvm.ps1`
- 是否需要 ADR：`暂不写，先等待真实工程和 Win7 验证结果`
- 后续动作：
  - 收敛版本组合
  - 在真实 C 工程和 Win7 上补验

### DC-011

- 日期：2026-03-28
- 变更主题：Phase 5 最小权限与防循环保护落地
- 变更摘要：
  - 新增 `src/embedagent/permissions.py`，定义最小权限分类和 CLI 确认策略
  - 新增 `src/embedagent/guard.py`，实现连续失败与相同失败动作的防护
  - `AgentLoop` 接入权限确认和 Doom Loop Guard
  - CLI 增加 `--approve-all`、`--approve-writes`、`--approve-commands`
  - 工具链 smoke test 脚本增加清理逻辑，减少临时产物污染
- 影响范围：
  - Agent Loop
  - CLI 入口
  - Phase 5 验证口径
- 关联文档：
  - `src/embedagent/permissions.py`
  - `src/embedagent/guard.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/cli.py`
  - `docs/permission-model.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 继续补上下文压缩和更细粒度权限规则

### DC-012

- 日期：2026-03-28
- 变更主题：Phase 5 第一版上下文管理落地
- 变更摘要：
  - 新增 `src/embedagent/context.py`，以确定性规则实现会话上下文构建
  - `Turn` 新增消息范围索引，允许精确保留最近 turn 的原始消息链
  - 旧 turn 被压缩为摘要，工具 Observation 被结构化遮蔽与截断
  - `AgentLoop` 在每轮模型调用前不再直接发送全量 `session.messages`，而是交由 `ContextManager` 构建上下文
  - 新增 `docs/context-management-design.md` 记录当前策略与后续演进方向
- 影响范围：
  - Session 结构
  - Agent Loop 的上下文构建流程
  - Phase 5 上下文预算与压缩口径
- 关联文档：
  - `src/embedagent/context.py`
  - `src/embedagent/session.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 引入更精确的 token 预算
  - 视需要增加 LLM 摘要压缩路径

### DC-013

- 日期：2026-03-28
- 变更主题：Phase 5A 上下文预算器与 Observation Reducer Registry 落地
- 变更摘要：
  - `ContextManager` 引入 mode-aware budget，为不同模式分配不同输入预算并预留输出/推理空间
  - 新增 `ContextPolicy`、`BudgetEstimate`、`ContextStats`，让上下文压缩过程可观测
  - 引入 `ReducerRegistry`，按工具类型裁剪 Observation，而不是只依赖统一截断逻辑
  - `AgentLoop` 在构建上下文时显式传入当前 mode，使预算策略不再只靠 system prompt 反推
- 影响范围：
  - Context Manager
  - Agent Loop 的模型输入构建逻辑
  - Phase 5 上下文压缩评估与后续 condenser 触发策略
- 关联文档：
  - `src/embedagent/context.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在 Tool Runtime 源头引入 Artifact Store
  - 持久化 session summary
  - 评估可选 LLM condenser 的接入点

### DC-014

- 日期：2026-03-28
- 变更主题：Phase 5B Artifact Store 与 Observation 源头瘦身落地
- 变更摘要：
  - 新增 `src/embedagent/artifacts.py`，提供本地 artifact 落盘与基础脱敏能力
  - `ToolRuntime` 在 Observation 返回前，会把长 `content/stdout/stderr/diff` 和大列表写入 `.embedagent/memory/artifacts/...`
  - Observation 改为保留预览 + `artifact_ref` + 元数据，不再把大输出完整塞入会话
  - `ContextManager` 的 reducer 现在会保留关键 `artifact_ref`，允许模型按需回看工件
- 影响范围：
  - Tool Runtime
  - 上下文管理链路
  - Tool Observation 契约
- 关联文档：
  - `src/embedagent/artifacts.py`
  - `src/embedagent/tools/runtime.py`
  - `src/embedagent/context.py`
  - `docs/tool-contracts.md`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 持久化 session summary
  - 增加 artifact 生命周期清理与索引
  - 评估是否需要单独的 artifact 读取工具

---

### DC-015

- 日期：2026-03-28
- 变更主题：Phase 5C Session Summary Store 与会话状态持久化落地
- 变更摘要：
  - 新增 `src/embedagent/session_store.py`，负责将会话关键状态持久化到 `.embedagent/memory/sessions/<session_id>/summary.json`
  - `AgentLoop` 在初始化、构建上下文、assistant 回复和 Observation 回注后都会刷新摘要文件
  - 摘要当前保留 `user_goal`、`current_mode`、`working_set`、`modified_files`、`last_success`、`last_blocker`、`recent_actions`、`recent_artifacts` 以及最近一次上下文预算统计
  - 该摘要文件作为后续恢复入口和 Project Memory 的基础落点，而不是全量历史回放
- 影响范围：
  - Agent Loop
  - 会话状态持久化
  - Phase 5 后续恢复与记忆演进路径
- 关联文档：
  - `src/embedagent/session_store.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 建立 Project Memory 加载层
  - 增加基于 `summary.json` 的恢复入口
  - 为 session / artifact 增加生命周期清理与索引

---

### DC-016

- 日期：2026-03-28
- 变更主题：Phase 5D Project Memory Store 与项目级记忆装载落地
- 变更摘要：
  - 新增 `src/embedagent/project_memory.py`，维护 `project-profile.json`、`command-recipes.json`、`known-issues.json` 与处理索引
  - `AgentLoop` 在持久化 session summary 后，会继续刷新 Project Memory
  - `ContextManager` 现在会按当前 mode 装载 Project Memory system message
  - 模型在新轮次中可直接看到项目硬约束、最近成功命令 recipe 和最近 open issue
- 影响范围：
  - Agent Loop
  - Context Manager
  - Phase 5 后续恢复与长期记忆演进路径
- 关联文档：
  - `src/embedagent/project_memory.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/context.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 增加基于 `summary.json` 的恢复入口
  - 为 memory 文件增加生命周期清理与索引
  - 评估是否需要 Project Memory 的显式编辑入口

### DC-017

- 日期：2026-03-28
- 变更主题：Phase 5E Resume Entry 与会话索引落地
- 变更摘要：
  - `SessionSummaryStore` 新增 `index.json`、最近会话列表、`latest` 解析和摘要加载能力
  - CLI 新增 `--list-sessions` 与 `--resume <session_id|latest|summary.json>`
  - 恢复会话时，会基于 `summary.json` 注入恢复摘要，再叠加当前模式 prompt 与 Project Memory
  - 这使 Phase 5 的记忆层首次形成“落盘 -> 列出 -> 加载 -> 续跑”的闭环
- 影响范围：
  - CLI 入口
  - Session Summary Store
  - Context Manager 的 system message 装载逻辑
- 关联文档：
  - `src/embedagent/cli.py`
  - `src/embedagent/session_store.py`
  - `src/embedagent/context.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 为 memory 文件增加生命周期清理与索引收口
  - 继续细化权限规则
  - 在长任务上验证恢复与记忆层稳定性

### DC-018

- 日期：2026-03-28
- 变更主题：Phase 5F Memory Maintenance 与记忆生命周期清理落地
- 变更摘要：
  - 新增 `src/embedagent/memory_maintenance.py`，统一协调 artifact / session / project memory 的清理
  - `ArtifactStore` 新增 `index.json` 与基础 cleanup 能力
  - `SessionSummaryStore` 新增会话目录 cleanup 与活跃 artifact 引用收集
  - `ProjectMemoryStore` 新增 artifact 引用收集与 resolved issue 收敛
  - `AgentLoop` 现在会周期性触发 memory maintenance，避免文件型记忆无限增长
- 影响范围：
  - Artifact / Session / Project Memory 全链路
  - Agent Loop 的后台维护逻辑
  - Phase 5 的长期稳定性与离线可持续运行能力
- 关联文档：
  - `src/embedagent/memory_maintenance.py`
  - `src/embedagent/artifacts.py`
  - `src/embedagent/session_store.py`
  - `src/embedagent/project_memory.py`
  - `src/embedagent/loop.py`
  - `docs/context-management-design.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在长任务上验证 cleanup 策略是否足够稳健
  - 继续细化权限规则
  - 评估 memory browse / inspect 入口

### DC-019

- 日期：2026-03-28
- 变更主题：Phase 5 长任务稳定性验证完成并升级规则驱动权限模型
- 变更摘要：
  - 新增 `scripts/validate-phase5.py`，提供 Phase 5 的长任务稳定性与权限专项回归入口
  - 完成 20+ turn 长任务、多次上下文压缩、恢复续跑和 Project Memory 注入的本地验证
  - `PermissionPolicy` 升级为规则驱动模型，支持 `allow / ask / deny`、路径 glob 和命令正则匹配
  - CLI 新增 `--permission-rules`，支持加载 `.embedagent/permission-rules.json`
- 影响范围：
  - 权限模型
  - Phase 5 验证基线
  - CLI 配置入口
- 关联文档：
  - `src/embedagent/permissions.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/cli.py`
  - `scripts/validate-phase5.py`
  - `docs/permission-model.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在真实模型与更长时间跨度上补稳定性验证
  - 继续推进 Phase 4 真正工程验证
  - 评估 memory browse / inspect 入口

### DC-020

- 日期：2026-03-28
- 变更主题：Phase 6 前端协议与 TUI 信息架构设计落地
- 变更摘要：
  - 新增 `docs/frontend-protocol.md`，定义 Frontend 与 Core 的 Command / Event 边界、In-Process adapter 和 stdio JSON-RPC 演进路径
  - 新增 `docs/tui-information-architecture.md`，定义首版 TUI 的页面结构、关键交互流和首版范围边界
  - 明确 Phase 6 首先实现 `InProcessAdapter`，再在其上构建最小 TUI，最后才考虑 stdio adapter
- 影响范围：
  - Phase 6 实现顺序
  - CLI / TUI 的边界定义
  - Frontend 与 Core 的协议收敛方式
- 关联文档：
  - `docs/frontend-protocol.md`
  - `docs/tui-information-architecture.md`
  - `docs/development-tracker.md`
  - `README.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 实现 `InProcessAdapter`
  - 让现有 CLI 改为通过 adapter 调用 Core
  - 在 adapter 上实现最小 TUI

### DC-021

- 日期：2026-03-28
- 变更主题：Phase 6A InProcessAdapter 落地并接管 CLI 驱动路径
- 变更摘要：
  - 新增 `src/embedagent/inprocess_adapter.py`，统一封装会话创建、恢复、消息提交、事件回调和会话快照
  - `AgentLoop` 新增 `on_context_result` 钩子，允许前端层接收 `context_compacted` 事件
  - 现有 CLI 已改为通过 `InProcessAdapter` 驱动 Core，而不再直接组装 loop
  - 当前适配层已具备 Phase 6 最小可用边界，为最小 TUI 直接复用铺平路径
- 影响范围：
  - CLI 入口
  - Frontend / Core 协议落地方式
  - Phase 6 的实现顺序
- 关联文档：
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/cli.py`
  - `src/embedagent/loop.py`
  - `docs/frontend-protocol.md`
  - `docs/tui-information-architecture.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在 adapter 之上实现最小 TUI
  - 评估是否需要 stdio adapter 提前落地
  - 继续推进 Phase 4 真实工程验证

### DC-022

- 日期：2026-03-28
- 变更主题：Phase 6B 最小 TUI 原型接入 CLI
- 变更摘要：
  - 新增 `src/embedagent/tui.py`，在 `InProcessAdapter` 之上实现最小单会话 TUI 骨架
  - TUI 已具备 Header、Transcript、Side Panel、Composer 和基本快捷键
  - 现有 CLI 新增 `--tui` 入口，并在依赖缺失时返回明确错误提示
  - 当前已验证普通 CLI 不退化，以及 `--tui` 在缺少 `prompt_toolkit` / `rich` 时会 graceful fallback
- 影响范围：
  - CLI 入口
  - Phase 6 最小可运行交互壳
  - 后续 TUI 实现节奏
- 关联文档：
  - `src/embedagent/tui.py`
  - `src/embedagent/cli.py`
  - `docs/tui-information-architecture.md`
  - `docs/development-tracker.md`
  - `README.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 补齐 `prompt_toolkit` / `rich` 依赖并完成真实运行验证
  - 完善权限确认、会话列表和侧栏刷新交互
  - 评估是否推进 stdio adapter

### DC-023

- 日期：2026-03-28
- 变更主题：Phase 6B 最小 TUI 交互深化与 `--tui` 空启动修复
- 变更摘要：
  - `src/embedagent/tui.py` 新增会话列表浏览、选中恢复、帮助/快照侧栏，以及权限、错误、上下文压缩状态展示
  - `src/embedagent/cli.py` 修复 `--tui` 仍要求启动消息的问题，并支持将可选初始消息交给 TUI 在首轮自动提交
  - 已补做本地回归：普通 CLI 不退化，TUI 逻辑可用假依赖验证，缺失 `prompt_toolkit` / `rich` 时继续保持 graceful fallback
- 影响范围：
  - Phase 6 最小 TUI 交互能力
  - CLI 的 `--tui` 启动路径
  - 后续真实 TUI 运行验证的准备状态
- 关联文档：
  - `src/embedagent/tui.py`
  - `src/embedagent/cli.py`
  - `README.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 补齐 `prompt_toolkit` / `rich` 依赖并完成真实运行验证
  - 评估是否接入 artifact 浏览或 inspect 入口
  - 继续推进 Phase 4 真实工程验证

### DC-024

- 日期：2026-03-28
- 变更主题：Phase 6B TUI 依赖接入与宿主兼容性收口
- 变更摘要：
  - `pyproject.toml` 已声明 `prompt-toolkit==3.0.52` 与 `rich==14.3.3`，开发环境可通过 `uv sync --python 3.8.10` 直接拉起 TUI 依赖
  - `src/embedagent/tui.py` 新增非控制台宿主拦截，遇到 `NoConsoleScreenBufferError` 时会转换为清晰的 `TUIUnavailableError`
  - 新增 `EMBEDAGENT_TUI_HEADLESS=1` 的内部验证路径，用于在当前宿主下跑通真实 prompt_toolkit 事件循环
- 影响范围：
  - TUI 依赖声明
  - 非控制台宿主的错误体验
  - Phase 6 的自动化验证能力
- 关联文档：
  - `pyproject.toml`
  - `src/embedagent/tui.py`
  - `README.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在真实控制台里补一轮手工验证
  - 评估是否为 headless 验证补独立脚本
  - 继续推进 Phase 4 真实工程验证

### DC-025

- 日期：2026-03-28
- 变更主题：Phase 6 进入脚本可追踪状态
- 变更摘要：
  - 新增 `scripts/validate-phase6.py`，固化 Phase 6 的自动化验证入口
  - 新增 `docs/phase6-validation.md`，记录自动化命令与真实控制台手工验证清单
  - 修正 `docs/frontend-protocol.md` 中 Phase 6B/6C 的阶段编号，使其与实际实现顺序一致
- 影响范围：
  - Phase 6 验证口径
  - 前端协议文档与路线图一致性
  - 阶段收口状态的可追踪性
- 关联文档：
  - `scripts/validate-phase6.py`
  - `docs/phase6-validation.md`
  - `docs/frontend-protocol.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在真实控制台里执行手工验证并记录结果
  - 继续推进 Phase 4 真实工程验证

## 4. 维护约定

- 若改动影响总体架构，更新本文件
- 若改动影响项目纪律或版本边界，同时更新 `AGENTS.md`
- 若改动影响实施顺序，同时更新 `docs/implementation-roadmap.md`
- 若改动具有长期不可逆影响，补充一个 ADR


### DC-026

- 日期：2026-03-29
- 变更主题：Phase 6 终端前端模块化与浏览接口扩展
- 变更摘要：
  - `src/embedagent/tui.py` 已收敛为兼容 shim，真实终端前端迁移到 `src/embedagent/frontend/tui/`
  - 终端前端按 `state / reducer / controller / layout / services / views` 拆分，避免继续把交互逻辑堆在单文件中
  - `InProcessAdapter` 新增 workspace / timeline / artifact / todo 读取接口，并接入 `SessionTimelineStore`
  - 新增单元测试覆盖 timeline store、adapter 前端接口与终端补全模块；`scripts/validate-phase6.py` 回归通过
- 影响范围：
  - Phase 6 前端包结构
  - Frontend/Core 浏览型接口边界
  - 后续 Win7 控制台与 ConEmu 收口路径
- 关联文档：
  - `src/embedagent/frontend/tui/`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/session_timeline.py`
  - `docs/frontend-protocol.md`
  - `docs/development-tracker.md`
- 是否需要 ADR：`暂不写`
- 后续动作：
  - 在真实 Win7 控制台与 ConEmu 下补手工验证
  - 继续细化 explorer / editor / plan 交互
  - 评估是否将同一协议推广到 stdio adapter

### DC-027

- 日期：2026-03-29
- 变更主题：修复根目录文件写入边界匹配并对齐当前文档状态
- 变更摘要：
  - `modes.py` 现在把前导 `**/` 视为“可为空的目录前缀”，使 `README.md`、`AGENTS.md`、`pyproject.toml` 等根目录文件能按模式写入规则正确匹配
  - `tests/test_modes.py` 新增根目录 `README.md` / `pyproject.toml` / `manage.py` 的可写边界回归
  - `scripts/validate-phase5.py` 已在该修复后重新跑通，Phase 5 状态从“实现完成”校正为“脚本复验通过”
  - README、路线图、进度跟踪与变更日志已同步对齐当前能力、阶段状态与验证口径
- 影响范围：
  - 模式写入边界
  - Phase 5 验证基线
  - 文档治理一致性
- 关联文档：
  - `src/embedagent/modes.py`
  - `tests/test_modes.py`
  - `README.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
  - `docs/design-change-log.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 继续推进 Phase 4 真实 C 工程与 Win7 验证
  - 在真实控制台与 Win7 / ConEmu 下完成 Phase 6 手工验证
  - 启动 Phase 7 打包文档与前置自检设计

### DC-028

- 日期：2026-03-29
- 变更主题：建立 Phase 7 离线打包与 Win7 preflight 设计基线
- 变更摘要：
  - 新增 `docs/offline-packaging.md`，固定 one-folder portable bundle、目录布局、组件清单、构建流水线与 bundle 级验证口径
  - 新增 `docs/win7-preflight-checklist.md`，固定 Windows 7 目标机部署与首次运行检查项
  - 新增 ADR `0001-offline-portable-bundle-baseline.md`，把 Phase 7 首个交付形态收敛为 x64 one-folder portable bundle
  - README、tracker 与 roadmap 已同步登记 Phase 7 设计基线已建立
- 影响范围：
  - Phase 7 交付路线
  - 文档治理与验收口径
  - 后续打包脚本命名与职责拆分
- 关联文档：
  - `README.md`
  - `docs/offline-packaging.md`
  - `docs/win7-preflight-checklist.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/adrs/0001-offline-portable-bundle-baseline.md`
- 是否需要 ADR：`已补 ADR-0001`
- 后续动作：
  - 落 bundle manifest / checksum / license 生成方案
  - 规划 `prepare-offline` / `build-offline-bundle` / `validate-offline-bundle` 脚本骨架
  - 在 Win7 虚拟机上按 preflight 口径完成首轮 bundle 验收

### DC-029

- 日期：2026-03-29
- 变更主题：落地 Phase 7A `prepare-offline` 脚本骨架
- 变更摘要：
  - 新增 `scripts/prepare-offline.ps1`，可生成 `build/offline-staging/EmbedAgent/` 目录布局
  - 该脚本会写出 `embedagent.cmd`、`embedagent-tui.cmd`、默认配置模板、`bundle-manifest.json` 和 `checksums.txt`
  - 脚本支持 `-SkipBuild`，允许在第三方资产尚未收齐时先生成稳定的 staging 布局和组件状态清单
  - 已用 `powershell.exe -NoProfile -File scripts/prepare-offline.ps1 -SkipBuild` 验证脚本可运行
- 影响范围：
  - Phase 7 打包脚本分层
  - bundle 目录布局的可执行基线
  - manifest / checksum 生成口径
- 关联文档：
  - `scripts/prepare-offline.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 补 `build-offline-bundle.ps1`
  - 补 `validate-offline-bundle.ps1`
  - 固化 MinGit / ripgrep / Universal Ctags / embeddable Python 的来源与校验和

### DC-030

- 日期：2026-03-29
- 变更主题：落地 Phase 7B `build-offline-bundle` 脚本骨架
- 变更摘要：
  - 新增 `scripts/build-offline-bundle.ps1`，可直接消费 `build/offline-staging/EmbedAgent/`
  - 脚本会把 staging bundle 复制到 `build/offline-dist/<artifact>/`，重写 dist 上下文 `bundle-manifest.json`，重算 `checksums.txt`，并生成 zip
  - 脚本已在 skeleton bundle 上通过 `powershell.exe -NoProfile -File scripts/build-offline-bundle.ps1` 验证
  - `prepare-offline.ps1` 同步增加对 `__pycache__` / `.pyc` / `.pyo` 的清理，避免把瞬态 Python 产物带进发布包
- 影响范围：
  - Phase 7 build 阶段脚本分层
  - dist 目录与 zip 产物约定
  - bundle manifest / checksum 在 dist 上下文的生成口径
- 关联文档：
  - `scripts/build-offline-bundle.ps1`
  - `scripts/prepare-offline.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 补 `validate-offline-bundle.ps1`
  - 将 launcher、manifest 与关键文件存在性检查纳入自动验证
  - 在真实资产收齐后补全 end-to-end bundle 验证

### DC-031

- 日期：2026-03-29
- 变更主题：落地 Phase 7C `validate-offline-bundle` 脚本骨架
- 变更摘要：
  - 新增 `scripts/validate-offline-bundle.ps1`，可校验 bundle 根目录、manifest、checksums、关键 launcher 和目录布局
  - 默认模式下，缺失 embeddable Python / MinGit / rg / ctags / LLVM 等资产会以告警呈现，便于在 skeleton bundle 阶段继续推进
  - `-RequireComplete` 下，相同缺失项会被提升为失败，作为后续正式离线交付验收门
  - 已在当前 skeleton bundle 上完成两轮验证：默认模式返回告警但通过；`-RequireComplete` 按预期返回失败
- 影响范围：
  - Phase 7 validate 阶段脚本分层
  - skeleton bundle 与正式验收之间的门禁切换策略
  - bundle manifest/checksum 的自动校验口径
- 关联文档：
  - `scripts/validate-offline-bundle.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 在正式验收入口中强制使用 `-RequireComplete`
  - 接入 embeddable Python 与第三方工具后补动态启动验证
  - 将 validate 结果沉淀到 bundle manifest 或独立报告文件

### DC-032

- 日期：2026-03-29
- 变更主题：接入 Python embeddable 与 MinGit 的真实资产链路
- 变更摘要：
  - 新增 `scripts/offline-assets.json`，固定 `python_embedded_x64` 与 `mingit_x64` 的官方 URL、SHA256、stage/cache 路径与 License 元数据
  - `scripts/prepare-offline.ps1` 现在支持 `-AssetManifestPath`、`-AssetIds` 和 `-AllowDownload`，并会对 Python/MinGit 执行缓存校验、按需下载、解压和 license notice 生成
  - Python embeddable 会在 prepare 阶段修补 `python38._pth`，写入 `..\..\app`、`..\site-packages` 和 `import site`
  - `scripts/build-offline-bundle.ps1` 现在会生成 `embedagent-win7-x64-sources/`，包含 `assets-manifest.json`、原始 zip 归档和 `checksums.txt`
  - `scripts/validate-offline-bundle.ps1` 已在真实 Python/MinGit 资产接入后通过默认模式和 `-RequireComplete` 模式验收
- 影响范围：
  - Phase 7 真实资产接入路径
  - bundle manifest / sources seed 结构
  - Python embeddable 启动方式
- 关联文档：
  - `scripts/offline-assets.json`
  - `scripts/prepare-offline.ps1`
  - `scripts/build-offline-bundle.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 接入 `ripgrep` 与 `Universal Ctags`
  - 评估是否用更精简的方式导出运行时 `site-packages`
  - 在 Win7 虚拟机上补 bundle 级真实验收

### DC-033

- 日期：2026-03-29
- 变更主题：接入 ripgrep 与 Universal Ctags 的真实资产链路
- 变更摘要：
  - `scripts/offline-assets.json` 已新增 `ripgrep_x64` 与 `universal_ctags_x64`，固定官方 URL、SHA256、stage/cache 路径与 License 元数据
  - `scripts/prepare-offline.ps1` 现在会对这两类 zip 执行缓存校验、按需下载、解压与 license notice 生成
  - prepare 新增“单层顶级目录自动拍平”逻辑，使 ripgrep zip 能稳定落到 `bin/rg/rg.exe`
  - `scripts/validate-offline-bundle.ps1` 已把 `rg.exe`、`ctags.exe`、对应 license notice、sources archive 和 `--version` 动态检查纳入正式门禁
  - 当前 `prepare/build/validate -RequireComplete` 已在 Python / MinGit / ripgrep / Universal Ctags 四类核心资产上全量通过
- 影响范围：
  - Phase 7 第三方资产接入范围
  - bundle 与 sources seed 的完整性门禁
  - validate 的动态工具检查覆盖面
- 关联文档：
  - `scripts/offline-assets.json`
  - `scripts/prepare-offline.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `docs/offline-packaging.md`
  - `docs/development-tracker.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`不单独写`
- 后续动作：
  - 评估 `.venv\Lib\site-packages` 的精简导出方案
  - 在 Win7 虚拟机上补 bundle 级真实验收
  - 视需要继续收敛第三方工具 license 文件的随包归档方式

### DC-034

- 日期：2026-03-29
- 变更主题：模式/权限解耦与空目录启动收口
- 变更摘要：
  - 新增 `write_file`，允许 agent 在工作区内创建新文件并自动创建父目录，解决空目录下 `spec` 无法起草文档的问题
  - 新增 `ask_user` 与 `waiting_user_input` 交互流，将用户问答与权限审批彻底分开
  - `switch_mode` 不再全模式可用，只保留给 `orchestra`；其他模式只能通过 `ask_user` 或文本建议请求用户决定
  - `MODE_REGISTRY` 的默认可写范围改为按文件类型放行，不再把 `docs/` / `src/` / `tests/` 固定成唯一目录结构
  - 配置新增 `mode_extra_writable_globs`，用于在保留默认值的前提下增量追加可写规则
  - 引入工作区画像 system message，并把非重试型阻塞纳入 LoopGuard 的提前停机逻辑
- 影响范围：
  - Mode Registry
  - Agent Loop / Guard
  - InProcessAdapter / CLI / TUI
  - 配置与文档治理
- 关联文档：
  - `src/embedagent/modes.py`
  - `src/embedagent/loop.py`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/tools/file_ops.py`
  - `src/embedagent/workspace_profile.py`
  - `docs/mode-schema.md`
  - `docs/tool-design-spec.md`
  - `docs/permission-model.md`
  - `docs/configuration-guide.md`
  - `docs/harness-state-machine.md`
  - `docs/implementation-roadmap.md`
- 是否需要 ADR：`暂不单独写`
- 后续动作：
  - 在真实 TUI / Win7 手工验证中复查 `waiting_user_input` 与 `waiting_permission` 的宿主体验
  - 继续评估 `ask_user` 是否需要被扩展到 `code` / `debug` 等执行模式

### DC-035

- 日期：2026-03-29
- 变更主题：模式系统 v2 重构——5 模式配置驱动，移除 switch_mode LLM 工具
- 变更摘要：
  - 模式集从 8 个缩减为 5 个：`explore`（默认，重命名自 ask）/`spec`/`code`/`debug`/`verify`；删除 `orchestra`、`test`、`compact`
  - `switch_mode` LLM 工具彻底移除；LLM 不能主动切换模式，只能通过 `ask_user` 建议，由用户确认
  - 模式定义迁移到 `_BUILTIN_MODES` + `initialize_modes(workspace)` 配置加载层；项目可通过 `.embedagent/modes.json` 覆盖或新增模式
  - `build_system_prompt()` 改为 `str.format()` + 可替换框架模板（`prompt_frame.txt`）
  - `manage_todos` / `ask_user` 在所有模式中统一可用
  - 会话启动时自动注入待办提示（通过 `workspace_profile.py`）
  - 旧 session 中已删除模式名（如 `orchestra`）自动回落到 `explore`，不崩溃
- 影响范围：
  - `src/embedagent/modes.py`（主要改动）
  - `src/embedagent/loop.py`（删除 switch_mode 逻辑）
  - `src/embedagent/workspace_profile.py`（加入待办提示）
  - `src/embedagent/cli.py` / `inprocess_adapter.py`（调用 initialize_modes）
  - 所有引用旧模式集的文档
- 关联文档：
  - `docs/mode-schema.md`（完全重写）
  - `docs/harness-state-machine.md`（更新切换机制）
  - `docs/tool-design-spec.md`（更新工具分配表）
  - `AGENTS.md`（更新模式政策与 Harness 演进策略）
  - `README.md`（更新模式列表）
  - `docs/implementation-roadmap.md` / `docs/development-tracker.md` / `docs/configuration-guide.md`（同步更新）
- 是否需要 ADR：`暂不单独写`
- 后续动作：
  - 在真实 TUI / Win7 环境验证新默认模式 `explore` 的入口体验
  - 评估是否需要为常见 C 维护工程提供预置的 `modes.json` 样板文件

### DC-036

- 日期：2026-03-30
- 变更主题：新架构落地——protocol/core/frontend 分层与 GUI PyWebView 前端
- 变更摘要：
  - 新增 `src/embedagent/protocol/`，定义 `CoreInterface`、`FrontendCallbacks` 及数据类型，实现前后端协议层
  - 新增 `src/embedagent/core/adapter.py`，实现 `AgentCoreAdapter` 包装 `InProcessAdapter` 并统一事件分发
  - 新增 `src/embedagent/frontend/gui/`，实现 PyWebView + FastAPI + WebSocket 的 GUI 前端，包含 diff/权限确认弹窗
  - 迁移 `src/embedagent/frontend/tui/`，按新架构实现 `TUIFrontend` 适配器，延迟导入处理缺失依赖
  - 旧 `src/embedagent/frontend/tui/` 保留向后兼容，未来逐步迁移
  - 新增 `tests/test_architecture.py`，17 项架构测试覆盖协议、Core、前后端导入
  - 新增 `docs/architecture-new.md` 记录新架构设计
- 影响范围：
  - 整体架构分层（新增 protocol/core/frontend）
  - TUI/GUI 前端实现方式
  - Agent Core 与前端解耦程度
  - 文档治理（README、development-tracker、architecture-new）
- 关联文档：
  - `docs/architecture-new.md`（新建）
  - `docs/frontend-protocol.md`（需要后续更新以反映 protocol 层）
  - `docs/development-tracker.md`（新增 T-020、T-021）
  - `README.md`（目录结构、技术选型、项目现状更新）
  - `src/embedagent/protocol/__init__.py`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/frontend/tui/`
  - `src/embedagent/frontend/gui/`
  - `tests/test_architecture.py`
- 是否需要 ADR：`建议后续补 ADR 记录架构分层决策`
- 后续动作：
  - 将旧 `frontend/tui/` 完全迁移到 `frontend/tui/`
  - 实现 GUI 的 diff 确认弹窗与后端实际联动
  - 更新 `docs/frontend-protocol.md` 以反映新 protocol 层设计
  - 在 Win7 环境下验证 GUI 前端兼容性（IE11 回退）

### DC-037

- 日期：2026-03-30
- 变更主题：补齐 GUI smoke 与离线 bundle GUI 验证链路
- 变更摘要：
  - 在当前开发环境安装并同步 GUI 运行依赖，新增 `scripts/validate-gui-smoke.py`，可对源码路径和 bundle 路径执行 headless GUI smoke
  - `src/embedagent/frontend/gui/launcher.py` 新增 renderer report 与 auto-close 参数，便于在真实 Windows 宿主执行 windowed smoke
  - 修正 `scripts/prepare-offline.ps1` 生成的 `embedagent-gui.cmd`，使其直接进入 GUI launcher，支持 GUI 专属参数
  - 离线 bundle 新增 `validate-gui-smoke.cmd` 与 `docs/win7-gui-validation.md`，作为 Win7 实机验收入口
  - 修正 `scripts/build-offline-bundle.ps1` 的 `AssetIds` 参数处理
  - 扩展 `scripts/validate-offline-bundle.ps1` 与 `scripts/check-bundle-dependencies.py`，把 GUI launcher、静态资源、内网部署文档和 GUI 依赖纳入正式校验
- 影响范围：
  - GUI 当前环境验收口径
  - 离线 bundle 的 GUI 交付完整性
  - Phase 6 / Phase 7 的验证结论
- 关联文档：
  - `docs/development-tracker.md`
  - `docs/gui-packaging.md`
  - `scripts/validate-gui-smoke.py`
  - `scripts/prepare-offline.ps1`
  - `scripts/build-offline-bundle.ps1`
  - `scripts/validate-offline-bundle.ps1`
  - `scripts/check-bundle-dependencies.py`
- 是否需要 ADR：`暂不单独写`
- 后续动作：
  - 实现 GUI 的 diff 确认弹窗与后端实际联动
  - 在真实 Win7 环境完成 WebView2 / MSHTML 回退实机验证

### DC-038

- 日期：2026-03-30
- 变更主题：GUI 状态语义收口、session-scoped todo 与 React/Vite 新壳层
- 变更摘要：
  - `manage_todos` 与前端 `list_todos` 默认切换为 session 作用域，真实会话数据落到 `.embedagent/memory/sessions/<session_id>/todos.json`；新建会话不再继承旧会话 todo
  - `InProcessAdapter` / `protocol` / `core.adapter` 补齐权威 `session_snapshot` 状态流，新增 `session_status`、`reasoning_delta`、`thinking_state`，并修复 `tool_started` / `tool_finished` 的稳定 `call_id`
  - 新增 GUI 专用懒加载文件树接口 `list_workspace_children`
  - 新增 `src/embedagent/frontend/gui/webapp/` React + Vite 工程，构建产物写回 `src/embedagent/frontend/gui/static/`
  - GUI launcher 现在优先要求 bundle 内 Fixed Version WebView2 runtime；bundle 模式下若缺失 Chromium 运行时会显式失败，不再静默回退到 IE11
  - `scripts/validate-gui-smoke.py` 已升级，可覆盖 tool / permission / ask_user / session todo 隔离与 renderer runtime source
- 影响范围：
  - GUI / Core 协议边界
  - todo 持久化语义
  - Win7 GUI 运行时基线
  - GUI 前端构建与静态资源来源
- 关联文档：
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/protocol/__init__.py`
  - `src/embedagent/tools/todo_ops.py`
  - `src/embedagent/frontend/gui/webapp/`
  - `src/embedagent/frontend/gui/launcher.py`
  - `scripts/validate-gui-smoke.py`
  - `docs/frontend-protocol.md`
  - `docs/gui-packaging.md`
  - `docs/win7-gui-validation.md`
  - `docs/configuration-guide.md`
- 是否需要 ADR：`建议后续补一条 GUI Chromium 基线 ADR`
- 后续动作：
  - 在 Win7 bundle 中完成 Fixed Version WebView2 109 实机验证
  - 继续细化文件预览 / diff / 编辑闭环
  - 评估是否继续保留 `mshtml` 仅作报错级兜底

### DC-039

- 日期：2026-04-03
- 变更主题：LlspProvider 接入默认文件型 backend
- 变更摘要：
  - `LlspProvider` 不再默认返回“空实现占位”提示，而是优先读取工作区 `.embedagent/llsp/evidence.json`
  - 新增 `LlspFileBackend`，支持离线读取 LLSP 证据文件，并保持 `llsp` 仍然是 optional provider，不引入新的运行时硬依赖
  - provider 侧增加基于 `focus path / working set` 的最小排序逻辑，让当前正在编辑或诊断的文件优先浮到上下文和 snapshot 投影前部
  - 新增测试覆盖默认 backend 读取、缺文件静默退化，以及 snapshot 对 LLSP 证据的投影
- 影响范围：
  - workspace intelligence 证据来源
  - context pipeline 的 intelligence 选证结果
  - session snapshot / frontend inspector 的情报投影
- 关联文档：
  - `docs/query-context-redesign.md`
  - `docs/archive/context-loop/context-loop-handoff-plan.md`
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `src/embedagent/workspace_intelligence.py`
  - `tests/test_query_engine_refactor.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
- 是否需要 ADR：`否`
- 后续动作：
  - 若需要更强实时语义，再接入真实 llsp/clangd daemon backend
  - 在真实 C 工程回归中验证 LLSP 证据文件与 diagnostics/ctags 的协同排序是否合适

### DC-040

- 日期：2026-04-03
- 变更主题：structured timeline 显式暴露投影来源语义
- 变更摘要：
  - `build_structured_timeline()` 现在会返回 `projection_source`，明确区分 `raw_events / turn_events / step_events`
  - 当 timeline 只有 turn 级事件时，adapter 会生成带 `projection_kind = synthetic_single_step` 和 `synthetic = true` 的 step，前端不再需要通过缺少 `step_start` 去猜当前语义
  - `protocol` 中的 `TurnRecord / AgentStepRecord` 也补上对应字段，开始把“记录的 step”和“投影出来的 step”区分开
- 影响范围：
  - frontend/protocol 的 structured timeline 语义
  - legacy timeline 向 step-based timeline 的投影方式
  - 后续 GUI 对 raw/internal 双层状态的收口空间
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-plan.md`
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/query-context-redesign.md`
  - `src/embedagent/inprocess_adapter.py`
  - `src/embedagent/protocol/__init__.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续决定前端最终是否仍保留 raw timeline 调试层
  - 继续收缩 adapter 内 legacy 分支，逐步把 structured timeline 变成默认消费面

### DC-041

- 日期：2026-04-03
- 变更主题：structured timeline 终止态同步收口 step status
- 变更摘要：
  - `step_events` 路径下，当 `turn_end` 投影出 `max_turns` 一类终止态时，adapter 现在会同步更新当前 step 的 `status`
  - 这样 structured timeline 不再出现 turn 已明确终止，但最后一个 step 仍停留在 `tool_calls` 的不一致状态
  - 新增回归测试覆盖 `max_turns` 场景下 step/turn 状态一致性
- 影响范围：
  - structured timeline 的终止态语义
  - 前端 step/turn 状态展示一致性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `docs/query-context-redesign.md`
  - `src/embedagent/inprocess_adapter.py`
  - `tests/test_inprocess_adapter_frontend_api.py`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续检查其他终止态是否还存在 step/turn 语义分裂

### DC-042

- 日期：2026-04-03
- 变更主题：GUI timeline 开始显示 projection 调试徽标
- 变更摘要：
  - webapp `state-helpers` 现在会保留 structured timeline item 的 `projectionSource / projectionKind / synthetic`
  - `Timeline` 组件开始在 step header 上显示 synthetic / projected step 的调试徽标，普通 recorded step 仍保持静默
  - helper 测试、smoke test 和一次完整 webapp build 已重新验证这条消费链路
- 影响范围：
  - GUI timeline 的 step 调试可见性
  - structured timeline 语义在前端的最终消费链
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - `src/embedagent/frontend/gui/webapp/test/state-helpers.test.mjs`
- 是否需要 ADR：`否`
- 后续动作：
  - 决定是否还要把 projection 语义补到 Inspector / runtime 调试面板
  - 继续收缩 raw timeline 只保留给诊断与回放使用

### DC-043

- 日期：2026-04-03
- 变更主题：Runtime 面板开始汇总 timeline projection 来源
- 变更摘要：
  - `state-helpers` 新增 timeline projection 汇总逻辑，能区分 `step_events / turn_events / raw_events`
  - GUI `Runtime` 面板现在会直接显示当前 timeline projection 来源，帮助区分“原生 step 时间线”和“退化回放”
  - webapp helper 测试、smoke test 和 build 都已对这条显示链路复验
- 影响范围：
  - GUI runtime 调试可见性
  - structured timeline / raw fallback 的前端区分能力
- 关联文档：
  - `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - `src/embedagent/frontend/gui/webapp/src/strings.js`
  - `src/embedagent/frontend/gui/webapp/test/state-helpers.test.mjs`
- 是否需要 ADR：`否`
- 后续动作：
  - 视需要继续把 projection 摘要补到 event log 或 timeline 顶部 banner

### DC-044

- 日期：2026-04-03
- 变更主题：raw fallback timeline 增加顶部提示
- 变更摘要：
  - `timelineFromEvents()` 现在会把 `raw_events` 作为 projection source 带到前端 timeline item
  - GUI `Timeline` 组件会在 raw fallback 场景顶部显示一条提示，明确当前看到的是原始事件回放而不是结构化 step timeline
  - helper 测试、smoke test、Python 前端回归和 webapp build 都已重新验证
- 影响范围：
  - raw/internal 双层语义在 GUI 中的可见性
  - timeline fallback 场景的用户可理解性
- 关联文档：
  - `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - `src/embedagent/frontend/gui/webapp/test/state-helpers.test.mjs`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续决定 raw timeline 是否只保留在调试场景

### DC-045

- 日期：2026-04-03
- 变更主题：live reducer 追加的 timeline item 与 structured timeline 语义对齐
- 变更摘要：
  - webapp `store` 现在会给 live session 期间追加的 `user / reasoning / tool / assistant / command_result / user_input` item 统一补上 `step_events / recorded_step / synthetic=false`
  - 这让“流式进行中的 timeline”和“刷新后重新加载的 structured timeline”在 projection 语义上开始真正对齐
  - smoke test、helper test 和 webapp build 已重新验证
- 影响范围：
  - GUI live timeline / reload timeline 的一致性
  - projection 调试语义在前端状态层的稳定性
- 关联文档：
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续检查 websocket 增量路径是否还存在未标记 projection 的边角事件

### DC-046

- 日期：2026-04-03
- 变更主题：live raw-event 卡片与 reload timeline 继续收口
- 变更摘要：
  - webapp `store` 现在会把 live `command_result` 明确标成 `raw_events / raw_event`，不再误带 `step_events / recorded_step`
  - live `permission_request` 已补成 inline permission card，因此进行中的 session 与刷新后的 structured timeline 不再缺少同一张等待卡片
  - `message(ERROR)` 也改为走统一的 raw-event error 卡片路径，避免 system error 只存在于 event log 而不进入 timeline
- 影响范围：
  - GUI live timeline / reload timeline 一致性
  - raw-event 与 step-event 的投影边界
  - websocket 增量事件的调试可见性
- 关联文档：
  - `docs/archive/context-loop/context-loop-handoff-status.md`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续检查所有 `message(*)` 分支是否仍有 live/reload 语义差异

### DC-047

- 日期：2026-04-03
- 变更主题：GUI live context_compacted 卡片恢复 compact 元数据
- 变更摘要：
  - `CallbackBridge` 现在会在 `MessageType.CONTEXT_COMPACTED` 上保留 `recent_turns / summarized_turns / approx_tokens_after / analysis`
  - GUI webapp 开始消费 `message(CONTEXT_COMPACTED)`，并在 live timeline 中生成带 `raw_events / raw_event` 语义的 context 卡片
  - 这让上下文压缩卡片不再只在 reload/raw timeline 中可见，live session 期间也能看到与 compact 边界一致的调试信息
- 影响范围：
  - CallbackBridge 消息元数据契约
  - GUI live timeline 的 context_compacted 可见性
  - compact observability 在 live / reload 两条路径上的一致性
- 关联文档：
  - `docs/query-context-redesign.md`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `tests/test_gui_sync.py`
- 是否需要 ADR：`否`
- 后续动作：
  - 继续决定是否要把更多 compact analysis 明细暴露到 inspector 而不只留在 metadata
