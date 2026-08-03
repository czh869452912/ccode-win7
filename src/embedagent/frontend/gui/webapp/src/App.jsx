import React, { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { createClientRuntime } from "./client-runtime/client-runtime.js";
import { INITIAL_REQUESTED_MODE, initialState, runtimeReducer } from "./client-runtime/runtime-reducer.js";
import { createSessionTransportState } from "./session-runtime/session-transport-state.js";
import { buildAppHomeModel } from "./session-runtime/app-home-model.js";
import { buildSessionActivityRuntime } from "./session-runtime/activity-state.js";
import { buildComposerCommandsFromCapabilities } from "./session-runtime/command-capabilities.js";
import { buildSessionCapabilityModelFromState } from "./session-runtime/session-capability-model.js";
import { buildSurfacePanelProps } from "./app-runtime/surface-panel-props.js";
import { buildAppCapabilityModelFromState } from "./app-runtime/app-capability-model.js";
import { buildBranchToolbarModel } from "./source-control/branch-toolbar-model.js";
import { readComposerDraft } from "./composer/composer-state.js";
import {
  readActiveThreadId,
  readThreadHistoryIntegrity,
  readThreadSessions,
} from "./session-runtime/thread-state.js";
import NoWorkspaceState from "./components/NoWorkspaceState.jsx";
import Sidebar from "./components/Sidebar.jsx";
import Timeline from "./components/Timeline.jsx";
import Composer from "./components/Composer.jsx";
import AppSidebarLayout from "./components/workbench/AppSidebarLayout.jsx";
import BottomDrawer from "./components/workbench/BottomDrawer.jsx";
import CommandPalette from "./components/workbench/CommandPalette.jsx";
import RightPanelSurfaceBody from "./components/workbench/RightPanelSurfaceBody.jsx";
import RightPanelTabs from "./components/workbench/RightPanelTabs.jsx";
import WorkbenchHeader from "./components/workbench/WorkbenchHeader.jsx";
import {
  buildCommandVisibilityContext,
  isTurnInterruptibleStatus,
  visibleCommands,
} from "./workbench/commands.js";
import { buildCommandGroupLabels } from "./workbench/command-palette-model.js";
import {
  activeRightPanelSurfaceFrom,
  rightPanelSurfacesFrom,
} from "./workbench/surfaces.js";
import {
  persistWorkbenchUiState,
  readPersistedWorkbenchUiState,
} from "./workbench/ui-state.js";
function App({ protocol }) {
  const [state, dispatch] = useReducer(runtimeReducer, initialState, (baseState) => ({
    ...baseState,
    workbench: readPersistedWorkbenchUiState(),
  }));
  const treeHeight = 640;
  const [respondingRequestIds, setRespondingRequestIdsState] = useState([]);
  const [sessionTransport, setSessionTransport] = useState(() => createSessionTransportState());
  const timelineRef = useRef(null);
  const runtimeStateRef = useRef(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  const currentSessionId = readActiveThreadId(state);
  const threadSessions = readThreadSessions(state);
  const composerDraft = readComposerDraft(state);
  const historyIntegrity = readThreadHistoryIntegrity(state);
  const currentMode = state.snapshot?.current_mode || state.requestedMode;
  const currentStatus = state.snapshot?.status || "idle";
  const appCapabilityModel = useMemo(
    () => buildAppCapabilityModelFromState(state),
    [state.app],
  );
  const {
    appCapabilities,
    appChrome,
    keybindings,
    commandPalette,
    terminalChrome,
    sourceControlChrome,
    previewChrome,
    previewServers,
    filePreviewChrome,
    diffPanelChrome,
    threadLifecycleCapabilities,
    emptyState: appEmptyState,
  } = appCapabilityModel;
  const sessionCapabilityModel = useMemo(
    () => buildSessionCapabilityModelFromState(state),
    [state],
  );
  const {
    sessionCapabilities,
    modeCatalog,
    toolCatalog,
    emptyState: sessionEmptyState,
  } = sessionCapabilityModel;
  const commandContext = useMemo(() => buildCommandVisibilityContext({
    currentSessionId,
    currentStatus,
    appState: state.app,
    workbenchState: state.workbench,
    sessionCapabilities,
  }), [
    currentStatus,
    currentSessionId,
    state.app,
    state.workbench.commandPalette.open,
    sessionCapabilities,
  ]);
  const paletteCommands = useMemo(() => visibleCommands(commandContext), [commandContext]);
  const composerCommandGroupLabels = useMemo(
    () => buildCommandGroupLabels(commandPalette),
    [commandPalette],
  );
  const composerCommands = useMemo(
    () =>
      buildComposerCommandsFromCapabilities(sessionCapabilities, {
        defaultGroupId: appChrome.composer?.commandMenu?.defaultCommandGroupId || "",
      }),
    [appChrome.composer, sessionCapabilities],
  );
  const activeWorkspaceId = state.app.activeWorkspace?.id || "";
  const runtimeState = useMemo(
    () =>
      buildSessionActivityRuntime({
        snapshot: state.snapshot,
        sessionTransport,
        activities: state.activities,
        defaultMode: INITIAL_REQUESTED_MODE,
        activeTurnId: state.activeTurnId,
        thinkingActive: state.thinkingActive,
        toolCatalog,
      }),
    [
      sessionTransport,
      state.activeTurnId,
      state.snapshot,
      state.thinkingActive,
      state.activities,
      toolCatalog,
    ],
  );
  runtimeStateRef.current = runtimeState;
  const interactionNotice = state.interactionNotice || runtimeState.interactionNotice;
  const clientRuntime = useMemo(
    () =>
      createClientRuntime({
        protocol,
        dispatch,
        getState: () => stateRef.current,
        defaultMode: INITIAL_REQUESTED_MODE,
        getActivityRuntime: () => runtimeStateRef.current || {},
        getTimelineElement: () => timelineRef.current,
        onSessionTransportChange: setSessionTransport,
        onRespondingRequestIdsChange: setRespondingRequestIdsState,
        browser: {
          windowObject: window,
          documentObject: document,
          getComputedStyleFn: getComputedStyle,
          scheduleMessage: startTransition,
          timer: window,
        },
      }),
    [protocol],
  );
  const clientActions = clientRuntime.actions;
  const contribution = useMemo(
    () => (key) => (...args) => clientActions.openContribution(key, ...args),
    [clientActions],
  );

  useEffect(() => {
    void clientRuntime.start();
    return () => clientRuntime.close();
  }, [clientRuntime]);

  useEffect(() => {
    persistWorkbenchUiState(state.workbench);
  }, [state.workbench]);

  useEffect(() => {
    void clientActions.openContribution(
      "interaction.sync",
      runtimeState.currentInteraction?.interactionId || "",
    );
  }, [clientActions, runtimeState.currentInteraction?.interactionId]);

  useEffect(() => {
    void clientActions.openContribution("timeline.sync_bottom");
  }, [clientActions, runtimeState.t3TimelineRows, state.thinkingActive, runtimeState.currentInteraction]);

  useEffect(() => {
    void clientActions.openContribution("visual_debug.refresh");
  }, [clientActions, runtimeState.timelineItems, state.requestedMode]);

  const loadSessions = contribution("session.reload_list");
  const loadSession = clientActions.selectSession;
  const createSession = clientActions.createSession;
  const cancelSession = clientActions.cancelSession;
  const openWorkspace = (path) => clientActions.activateWorkspace({ path });
  const activateWorkspace = clientActions.activateWorkspace;
  const removeWorkspace = (id) => clientActions.activateWorkspace({ id, remove: true });
  const setWorkspacePath = contribution("workspace.path_changed");
  const loadFileChildren = contribution("files.load");
  const openRightPanelSurface = contribution("surface.open");
  const openFile = contribution("file.open");
  const openDiff = contribution("diff.open");
  const handleTimelineScroll = contribution("timeline.scroll");
  const setComposerDraft = contribution("composer.set_draft");
  const sendComposerMessage = contribution("composer.send");
  const openComposerPalette = contribution("composer.open_palette");
  const refreshComposerSourceControl = contribution("composer.refresh_source_control");
  const respondToInteraction = clientActions.respondToInteraction;
  const handleThreadLifecycleAction = (actionId, sessionId) => {
    if (actionId === "rename") return clientActions.renameSession(sessionId);
    if (actionId === "archive") return clientActions.archiveSession(sessionId);
    if (actionId === "fork") return clientActions.forkSession(sessionId);
    return Promise.resolve();
  };
  const toggleRightPanel = contribution("workbench.toggle_right_panel");
  const toggleBottomDrawer = contribution("workbench.toggle_bottom_drawer");
  const openCommandPalette = contribution("command_palette.open");
  const closeCommandPalette = contribution("command_palette.close");
  const updatePaletteQuery = contribution("command_palette.query");
  const selectPaletteCommand = contribution("command_palette.select_command");
  const selectPaletteSession = contribution("command_palette.select_session");
  const selectPaletteWorkspace = contribution("command_palette.select_workspace");
  const activateRightPanelSurface = contribution("surface.activate");
  const closeRightPanelSurface = contribution("surface.close");
  const closeOtherRightPanelSurfaces = contribution("surface.close_others");
  const closeRightPanelSurfacesToRight = contribution("surface.close_to_right");
  const closeAllRightPanelSurfaces = contribution("surface.close_all");
  const openFilesSurface = contribution("files.open_surface");
  const openPreviewUrl = contribution("preview.open_url");
  const refreshPreview = contribution("preview.refresh");
  const openPreviewExternal = contribution("preview.open_external");
  const selectBottomDrawerKind = contribution("terminal.select_bottom_kind");
  const openBottomDrawerTerminal = contribution("terminal.open_new_bottom");
  const activateBottomDrawerTerminal = contribution("terminal.activate_bottom");
  const sendActiveTerminal = contribution("terminal.send_active");
  const clearActiveTerminal = contribution("terminal.clear_active");
  const restartActiveTerminal = contribution("terminal.restart_active");
  const closeActiveTerminal = contribution("terminal.close_active");
  const openRightPanelTerminal = contribution("terminal.open_right");
  const splitRightPanelTerminal = contribution("terminal.split_right");
  const splitRightPanelTerminalVertical = contribution("terminal.split_right_vertical");
  const activateRightPanelTerminal = contribution("terminal.activate_right");
  const sendToTerminal = contribution("terminal.send_to");
  const clearTerminalById = contribution("terminal.clear_by_id");
  const restartTerminalById = contribution("terminal.restart_by_id");
  const closeRightPanelTerminal = contribution("terminal.close_right");
  const resizeSidebar = contribution("panel.resize_sidebar");
  const resizeRightPanel = contribution("panel.resize_right");
  const surfacePanelController = useMemo(
    () => ({
      changeAppSettings: contribution("source_control.change_settings"),
      focusDiffFile: contribution("source_control.focus_diff"),
      refreshSourceControl: contribution("source_control.refresh"),
      selectSourceControlFile: contribution("source_control.open_file"),
    }),
    [contribution],
  );
  const appHomeModel = useMemo(
    () => buildAppHomeModel({
      app: state.app,
      sessions: threadSessions,
      currentSessionId,
      defaultMode: INITIAL_REQUESTED_MODE,
      threadLifecycleCapabilities,
    }),
    [currentSessionId, state.app, threadLifecycleCapabilities, threadSessions],
  );
  const branchToolbarModel = useMemo(
    () =>
      buildBranchToolbarModel({
        activeWorkspace: state.app.activeWorkspace,
        sourceControl: state.sourceControl,
        sourceControlChrome,
      }),
    [sourceControlChrome, state.app.activeWorkspace, state.sourceControl],
  );

  const rightPanelSurfaces = rightPanelSurfacesFrom(state.workbench);
  const activeRightPanelSurface = activeRightPanelSurfaceFrom(state.workbench);

  const surfacePanelProps = buildSurfacePanelProps({
    state,
    appChrome,
    sourceControlChrome,
    diffPanelChrome,
    surfacePanelController,
  });

  return (
    <>
    <AppSidebarLayout
      header={
        <WorkbenchHeader
          productName={state.app.app.productName}
          chrome={appChrome.header || {}}
          currentMode={currentMode}
          currentStatus={currentStatus}
          currentSessionId={currentSessionId}
          activeWorkspace={state.app.activeWorkspace}
          modeCatalog={modeCatalog}
          turnsUsed={state.turnsUsed}
          maxTurns={state.maxTurns}
          rightPanelOpen={state.workbench.rightPanel.open}
          bottomDrawerOpen={state.workbench.bottomDrawer.open}
          onRefresh={loadSessions}
          onToggleRightPanel={toggleRightPanel}
          onToggleBottomDrawer={toggleBottomDrawer}
          onOpenPalette={openCommandPalette}
        />
      }
      sidebar={
        <Sidebar
          app={state.app}
          appHome={appHomeModel}
          chrome={appChrome}
          currentSessionId={currentSessionId}
          currentMode={currentMode}
          modeCatalog={modeCatalog}
          workspacePathInput={state.app.workspacePathInput}
          onWorkspacePathChange={setWorkspacePath}
          onLoadSession={loadSession}
          onCreateSession={createSession}
          onThreadLifecycleAction={handleThreadLifecycleAction}
          onOpenWorkspace={openWorkspace}
          onActivateWorkspace={activateWorkspace}
          onRemoveWorkspace={removeWorkspace}
        />
      }
      main={
        state.app.hasActiveWorkspace ? (
          <main className="main-chat">
            <Timeline
              ref={timelineRef}
              timeline={runtimeState.timelineView}
              rows={runtimeState.t3TimelineRows}
              toolCatalog={toolCatalog}
              historyIntegrity={historyIntegrity}
              thinkingActive={state.thinkingActive}
              streamingReasoningId={state.streamingReasoningId}
              terminationReason={state.terminationReason}
              terminationDisplayReason={state.terminationDisplayReason}
              terminationMessage={state.terminationMessage}
              turnsUsed={state.turnsUsed}
              maxTurns={state.maxTurns}
              onScroll={handleTimelineScroll}
              onOpenDiff={openDiff}
              onOpenFile={openFile}
              chrome={appChrome.timeline || {}}
            />
            <Composer
              chrome={appChrome.composer || {}}
              interactionChrome={appChrome.interaction || {}}
              value={composerDraft}
              onChange={setComposerDraft}
              onSend={sendComposerMessage}
              onStop={cancelSession}
              isRunning={isTurnInterruptibleStatus(currentStatus)}
              currentMode={currentMode}
              modeCatalog={modeCatalog}
              commandGroupLabels={composerCommandGroupLabels}
              commands={composerCommands}
              fileTree={state.fileTree}
              onOpenCommandPalette={openComposerPalette}
              interaction={runtimeState.currentInteraction}
              interactionNotice={interactionNotice}
              interactionBusy={Boolean(
                runtimeState.currentInteraction?.interactionId &&
                  respondingRequestIds.includes(runtimeState.currentInteraction.interactionId)
              )}
              onRespondInteraction={respondToInteraction}
              branchToolbar={branchToolbarModel}
              onRefreshSourceControl={refreshComposerSourceControl}
            />
          </main>
        ) : (
          <NoWorkspaceState
            value={state.app.workspacePathInput}
            error={state.app.workspaceError}
            activating={state.app.activatingWorkspace}
            workspaces={state.app.workspaces}
            appHome={appHomeModel}
            emptyState={appEmptyState || sessionEmptyState}
            onChange={setWorkspacePath}
            onOpen={openWorkspace}
            onActivate={activateWorkspace}
          />
        )
      }
      rightPanel={
        <RightPanelTabs
          appCapabilities={appCapabilities}
          surfaces={rightPanelSurfaces}
          activeSurfaceId={state.workbench.rightPanel.activeSurfaceId}
          onActivateSurface={activateRightPanelSurface}
          onCloseSurface={closeRightPanelSurface}
          onCloseOtherSurfaces={closeOtherRightPanelSurfaces}
          onCloseSurfacesToRight={closeRightPanelSurfacesToRight}
          onCloseAllSurfaces={closeAllRightPanelSurfaces}
          onAddSurface={openRightPanelSurface}
        >
          <RightPanelSurfaceBody
            appCapabilities={appCapabilities}
            surface={activeRightPanelSurface}
            surfacePanelProps={surfacePanelProps}
            filePreviewsByPath={state.filePreviewsByPath}
            filePreviewChrome={filePreviewChrome}
            projectName={state.app.activeWorkspace?.label || ""}
            fileTree={state.fileTree}
            treeHeight={treeHeight}
            onOpenFile={openFile}
            onOpenFilesSurface={openFilesSurface}
            onLoadFileChildren={loadFileChildren}
            terminal={state.terminal}
            terminalChrome={terminalChrome}
            onTerminalNew={openRightPanelTerminal}
            onTerminalSplit={splitRightPanelTerminal}
            onTerminalSplitVertical={splitRightPanelTerminalVertical}
            onTerminalSelect={activateRightPanelTerminal}
            onTerminalSend={sendToTerminal}
            onTerminalClear={clearTerminalById}
            onTerminalRestart={restartTerminalById}
            onTerminalClose={closeRightPanelTerminal}
            previewChrome={previewChrome}
            previewServers={previewServers}
            onPreviewOpenUrl={openPreviewUrl}
            onPreviewRefresh={refreshPreview}
            onPreviewOpenExternal={openPreviewExternal}
          />
        </RightPanelTabs>
      }
      bottomDrawer={
        <BottomDrawer
          appCapabilities={appCapabilities}
          activeKind={state.workbench.bottomDrawer.activeKind}
          runOutput={state.runOutput}
          terminationReason={state.terminationDisplayReason || state.terminationReason}
          terminationMessage={state.terminationMessage}
          terminal={state.terminal}
          terminalChrome={terminalChrome}
          onKindSelect={selectBottomDrawerKind}
          onTerminalNew={openBottomDrawerTerminal}
          onTerminalSelect={activateBottomDrawerTerminal}
          onTerminalSend={sendActiveTerminal}
          onTerminalClear={clearActiveTerminal}
          onTerminalRestart={restartActiveTerminal}
          onTerminalClose={closeActiveTerminal}
        />
      }
      rightPanelOpen={state.workbench.rightPanel.open}
      bottomDrawerOpen={state.workbench.bottomDrawer.open}
      bottomDrawerHeight={state.workbench.bottomDrawer.height}
      onResizeSidebar={resizeSidebar}
      onResizeRightPanel={resizeRightPanel}
    />
    <CommandPalette
      open={state.workbench.commandPalette.open}
      query={state.workbench.commandPalette.query}
      commands={paletteCommands}
      sessions={threadSessions}
      currentSessionId={currentSessionId}
      workspaces={state.app.workspaces}
      activeWorkspaceId={activeWorkspaceId}
      keybindings={keybindings}
      commandPalette={commandPalette}
      onQueryChange={updatePaletteQuery}
      onClose={closeCommandPalette}
      onSelect={selectPaletteCommand}
      onSelectSession={selectPaletteSession}
      onSelectWorkspace={selectPaletteWorkspace}
    />
    </>
  );
}

export default App;
