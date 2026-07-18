import React, { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { INITIAL_REQUESTED_MODE, initialState, runtimeReducer } from "./client-runtime/runtime-reducer.js";
import { normalizeSessionPayload } from "./state-helpers.js";
import { createSessionTransportState } from "./session-runtime/session-transport-state.js";
import { buildAppHomeModel } from "./session-runtime/app-home-model.js";
import { buildSessionActivityRuntime } from "./session-runtime/activity-state.js";
import { buildComposerCommandsFromCapabilities } from "./session-runtime/command-capabilities.js";
import { buildSessionCapabilityModelFromState } from "./session-runtime/session-capability-model.js";
import { createSocketMessageController } from "./app-runtime/socket-message-controller.js";
import { createSurfacePanelController } from "./app-runtime/surface-panel-controller.js";
import { buildSurfacePanelProps } from "./app-runtime/surface-panel-props.js";
import { buildAppCapabilityModelFromState } from "./app-runtime/app-capability-model.js";
import { createBrowserDialogService } from "./app-runtime/browser-dialog-service.js";
import { fetchJson } from "./app-runtime/http-client.js";
import { createComposerController } from "./app-runtime/composer-controller.js";
import { createInitialAppLoadController } from "./app-runtime/initial-app-load-controller.js";
import { createDiffSurfaceController } from "./app-runtime/diff-surface-controller.js";
import { createFilePreviewController } from "./app-runtime/file-preview-controller.js";
import {
  createLoaderRequestExecutor,
  createSessionCommandCapabilityLoader,
} from "./app-runtime/session-loaders.js";
import { createPreviewController } from "./app-runtime/preview-controller.js";
import { createRespondingRequestIdsHandle } from "./app-runtime/responding-request-ids-handle.js";
import { createPanelResizeController } from "./app-runtime/panel-resize-controller.js";
import { createRightPanelController } from "./app-runtime/right-panel-controller.js";
import { createSessionActivationController } from "./app-runtime/session-activation-controller.js";
import { createSessionController } from "./app-runtime/session-controller.js";
import { createSessionTransportHandle } from "./app-runtime/session-transport-handle.js";
import { createSessionListController } from "./app-runtime/session-list-controller.js";
import { createSessionTransportController } from "./app-runtime/session-transport-controller.js";
import { createSourceControlController } from "./app-runtime/source-control-controller.js";
import { createTerminalController } from "./app-runtime/terminal-controller.js";
import { createThreadLifecycleController } from "./app-runtime/thread-lifecycle-controller.js";
import { createTimelineScrollController } from "./app-runtime/timeline-scroll-controller.js";
import { createWorkspaceFilesController } from "./app-runtime/workspace-files-controller.js";
import { createInteractionResponseController } from "./app-runtime/interaction-response-controller.js";
import { createWorkbenchCommandController } from "./app-runtime/workbench-command-controller.js";
import { createWorkspaceController } from "./app-runtime/workspace-controller.js";
import { createVisualDebugController } from "./app-runtime/visual-debug-controller.js";
import {
  clearTerminal,
  closeTerminal,
  listTerminals,
  openTerminal,
  restartTerminal,
  writeTerminal,
} from "./terminal/terminal-api.js";
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
import { createActiveWorkspaceDataLoader } from "./app-runtime/active-workspace-data-loader.js";
import { createWorkbenchKeyboardController } from "./app-runtime/workbench-keyboard-controller.js";
import {
  persistWorkbenchUiState,
  readPersistedWorkbenchUiState,
} from "./workbench/ui-state.js";

function readCurrentAppCapabilityModel(stateRef) {
  return buildAppCapabilityModelFromState(stateRef.current);
}

function readCurrentSessionCapabilityModel(stateRef) {
  return buildSessionCapabilityModelFromState(stateRef.current);
}

function App() {
  const [state, dispatch] = useReducer(runtimeReducer, initialState, (baseState) => ({
    ...baseState,
    workbench: readPersistedWorkbenchUiState(),
  }));
  const treeHeight = 640;
  const [respondingRequestIds, setRespondingRequestIdsState] = useState([]);
  const [sessionTransport, setSessionTransport] = useState(() => createSessionTransportState());
  const timelineRef = useRef(null);
  const currentSessionIdRef = useRef("");
  const runtimeStateRef = useRef(null);
  const sessionTransportControllerRef = useRef(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  const respondingRequestIdsHandle = useMemo(
    () =>
      createRespondingRequestIdsHandle({
        initialRequestIds: respondingRequestIds,
        setRequestIds: setRespondingRequestIdsState,
      }),
    [],
  );
  const sessionTransportHandle = useMemo(
    () =>
      createSessionTransportHandle({
        initialTransport: sessionTransport,
        setTransport: setSessionTransport,
      }),
    [],
  );

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
  const sourceControlController = useMemo(
    () =>
      createSourceControlController({
        dispatch,
        getAppCapabilities: () => readCurrentAppCapabilityModel(stateRef).appCapabilities,
        hasActiveWorkspace: () => stateRef.current.app.hasActiveWorkspace,
        getSourceControlChrome: () => readCurrentAppCapabilityModel(stateRef).sourceControlChrome,
        getDiffPanelChrome: () => readCurrentAppCapabilityModel(stateRef).diffPanelChrome,
      }),
    [],
  );
  const timelineScrollController = useMemo(
    () =>
      createTimelineScrollController({
        getElement: () => timelineRef.current,
      }),
    [],
  );
  const terminalController = useMemo(
    () =>
      createTerminalController({
        getState: () => stateRef.current,
        getAppCapabilities: () => readCurrentAppCapabilityModel(stateRef).appCapabilities,
        getTerminalChrome: () => readCurrentAppCapabilityModel(stateRef).terminalChrome,
        dispatch,
        api: {
          listTerminals,
          openTerminal,
          writeTerminal,
          clearTerminal,
          restartTerminal,
          closeTerminal,
        },
      }),
    [],
  );
  const loadSessionCommandCapabilitiesForApp = useMemo(
    () => createSessionCommandCapabilityLoader({ fetchJson, dispatch }),
    [],
  );

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    persistWorkbenchUiState(state.workbench);
  }, [state.workbench]);

  useEffect(() => {
    sessionTransportHandle.sync(sessionTransport);
  }, [sessionTransport, sessionTransportHandle]);

  useEffect(() => {
    respondingRequestIdsHandle.sync(respondingRequestIds);
  }, [respondingRequestIds, respondingRequestIdsHandle]);

  // initial app/workspace data load
  useEffect(() => {
    createInitialAppLoadController({
      loadAppBootstrap,
      loadSessionCommandCapabilities: loadSessionCommandCapabilitiesForApp,
    }).start();
  }, [loadSessionCommandCapabilitiesForApp]);

  // websocket lifecycle
  useEffect(() => {
    const controller = createSessionTransportController({
      getCurrentSessionId: () => currentSessionIdRef.current,
      getTransportState: sessionTransportHandle.read,
      updateTransportState: sessionTransportHandle.update,
      loadSession,
      handleMessage: socketMessageController.handleMessage,
      locationObject: window.location,
    });
    sessionTransportControllerRef.current = controller;
    controller.connect();
    return () => {
      controller.close();
      if (sessionTransportControllerRef.current === controller) {
        sessionTransportControllerRef.current = null;
      }
    };
  }, []);

  // smart auto-scroll: only follow when user is at bottom
  useEffect(() => {
    timelineScrollController.syncToBottom();
  }, [
    runtimeState.t3TimelineRows,
    state.thinkingActive,
    runtimeState.currentInteraction,
    timelineScrollController,
  ]);

  const sessionListController = useMemo(
    () =>
      createSessionListController({
        fetchJson,
        dispatch,
      }),
    [],
  );
  const { loadSessions } = sessionListController;
  const sessionActivationController = useMemo(
    () =>
      createSessionActivationController({
        fetchJson,
        dispatch,
        defaultMode: INITIAL_REQUESTED_MODE,
        createTransportState: sessionTransportHandle.createRuntimeTransport,
        replaceTransportState: sessionTransportHandle.replace,
        getAppCapabilities: () => readCurrentAppCapabilityModel(stateRef).appCapabilities,
        listTerminals,
      }),
    [sessionTransportHandle],
  );
  const loadSession = sessionActivationController;

  const workspaceFilesController = useMemo(
    () =>
      createWorkspaceFilesController({
        fetchJson,
        dispatch,
        getAppCapabilities: () => readCurrentAppCapabilityModel(stateRef).appCapabilities,
      }),
    [],
  );
  const rightPanelController = useMemo(
    () =>
      createRightPanelController({
        dispatch,
        terminalController,
        getAppCapabilities: () => readCurrentAppCapabilityModel(stateRef).appCapabilities,
      }),
    [terminalController],
  );
  const {
    openSurface: openRightPanelSurface,
  } = rightPanelController;
  const filePreviewController = useMemo(
    () =>
      createFilePreviewController({
        fetchJson,
        dispatch,
        getFilePreviewChrome: () => readCurrentAppCapabilityModel(stateRef).filePreviewChrome,
        rightPanelController,
      }),
    [rightPanelController],
  );
  const previewController = useMemo(
    () =>
      createPreviewController({
        dispatch,
        getCurrentSessionId: () => readActiveThreadId(stateRef.current),
        getPreviewChrome: () => readCurrentAppCapabilityModel(stateRef).previewChrome,
        rightPanelController,
      }),
    [rightPanelController],
  );
  const diffSurfaceController = useMemo(
    () =>
      createDiffSurfaceController({
        dispatch,
        getRuntimeState: () => runtimeStateRef.current || {},
        getDiffPanelChrome: () => readCurrentAppCapabilityModel(stateRef).diffPanelChrome,
      }),
    [],
  );
  const { loadFileChildren } = workspaceFilesController;

  const surfacePanelController = useMemo(
    () =>
      createSurfacePanelController({
        dispatch,
        sourceControlController,
      }),
    [sourceControlController],
  );

  const visualDebugController = useMemo(
    () =>
      createVisualDebugController({
        windowObject: typeof window === "undefined" ? null : window,
        dispatch,
        openDiffFixture: diffSurfaceController.open,
        getCurrentMode: () => stateRef.current.requestedMode || INITIAL_REQUESTED_MODE,
      }),
    [diffSurfaceController],
  );

  useEffect(() => {
    return visualDebugController.install();
  }, [runtimeState.timelineItems, state.requestedMode, visualDebugController]);

  const activeWorkspaceDataLoader = useMemo(
    () =>
      createActiveWorkspaceDataLoader({
        getAppCapabilities: () => readCurrentAppCapabilityModel(stateRef).appCapabilities,
        loadSessions,
        loadSessionCommandCapabilities: loadSessionCommandCapabilitiesForApp,
        loadFileChildren,
        loadStatus: sourceControlController.loadStatus,
      }),
    [loadSessionCommandCapabilitiesForApp, sourceControlController],
  );
  const workspaceController = useMemo(
    () =>
      createWorkspaceController({
        fetchJson,
        dispatch,
        getState: () => stateRef.current,
        getCurrentSessionId: () => readActiveThreadId(stateRef.current),
        loadWorkspaceData: activeWorkspaceDataLoader.loadActiveWorkspaceData,
      }),
    [activeWorkspaceDataLoader],
  );
  const {
    activateWorkspace,
    loadActiveWorkspaceData,
    loadAppBootstrap,
    openWorkspace,
    removeWorkspace,
    setWorkspacePath,
  } = workspaceController;

  const sessionController = useMemo(
    () =>
      createSessionController({
        fetchJson,
        dispatch,
        normalizeSessionPayload,
        getCurrentSessionId: () => readActiveThreadId(stateRef.current),
        getCurrentMode: () => stateRef.current.snapshot?.current_mode || stateRef.current.requestedMode,
        hasActiveWorkspace: () => Boolean(stateRef.current.app.hasActiveWorkspace),
        markTimelineBottom: timelineScrollController.markFollowingBottom,
        loadSessions,
        loadSession,
      }),
    [timelineScrollController],
  );
  const browserDialogService = useMemo(
    () => createBrowserDialogService({ windowObject: window }),
    [],
  );
  const threadLifecycleController = useMemo(
    () =>
      createThreadLifecycleController({
        fetchJson,
        dispatch,
        loadSessions,
        loadSession,
        getThreadSessions: () => readThreadSessions(stateRef.current),
        getThreadLifecycleCapabilities: () =>
          readCurrentAppCapabilityModel(stateRef).threadLifecycleCapabilities,
        prompt: browserDialogService.prompt,
        confirm: browserDialogService.confirm,
      }),
    [browserDialogService],
  );
  const { createSession, setMode, cancelSession, submitText } = sessionController;
  const { handleThreadLifecycleAction } = threadLifecycleController;
  const composerController = useMemo(
    () =>
      createComposerController({
        dispatch,
        getComposerDraft: () => readComposerDraft(stateRef.current),
        submitText,
        refreshSourceControl: sourceControlController.loadStatus,
      }),
    [sourceControlController, submitText],
  );

  const workbenchCommandController = useMemo(
    () =>
      createWorkbenchCommandController({
        dispatch,
        documentObject: document,
        setTimeoutFn: window.setTimeout.bind(window),
        getCurrentMode: () => stateRef.current.snapshot?.current_mode || stateRef.current.requestedMode,
        getActiveWorkspaceId: () => stateRef.current.app.activeWorkspace?.id || "",
        getSessionCapabilities: () => readCurrentSessionCapabilityModel(stateRef).sessionCapabilities,
        getAppCapabilities: () => readCurrentAppCapabilityModel(stateRef).appCapabilities,
        createSession,
        loadSessions,
        loadSession,
        loadAppBootstrap,
        activateWorkspace,
        removeWorkspace,
        sendMessage: composerController.sendMessage,
        cancelSession,
        submitText,
        setMode,
        openRightPanelSurface,
        terminalController,
      }),
    [composerController, openRightPanelSurface, terminalController],
  );
  const executeWorkbenchCommand = workbenchCommandController.execute;

  const workbenchKeyboardController = useMemo(
    () =>
      createWorkbenchKeyboardController({
        windowObject: window,
        documentObject: document,
        getKeybindings: () => readCurrentAppCapabilityModel(stateRef).keybindings,
        getCommandContext: () => {
          const current = stateRef.current;
          return buildCommandVisibilityContext({
            currentSessionId: readActiveThreadId(current),
            currentStatus: current.snapshot?.status || "idle",
            appState: current.app,
            workbenchState: current.workbench,
            sessionCapabilities: buildSessionCapabilityModelFromState(current).sessionCapabilities,
          });
        },
        getCurrentStatus: () => stateRef.current.snapshot?.status || "idle",
        isTurnInterruptibleStatus,
        cancelSession,
        executeWorkbenchCommand,
      }),
    [executeWorkbenchCommand],
  );

  useEffect(() => {
    return workbenchKeyboardController.install();
  }, [workbenchKeyboardController]);

  const executeLoaderRequest = createLoaderRequestExecutor({
    loadAppBootstrap,
    loadActiveWorkspaceData,
    loadSessions,
    loadSession,
    loadFileChildren,
    loadSessionCommandCapabilities: loadSessionCommandCapabilitiesForApp,
  });

  const socketMessageController = useMemo(
    () =>
      createSocketMessageController({
        dispatch,
        executeLoaderRequest,
        getSessionTransportController: () => sessionTransportControllerRef.current,
        getSessionTransportState: sessionTransportHandle.read,
        updateSessionTransportState: sessionTransportHandle.update,
        getCurrentSessionId: () => currentSessionIdRef.current,
        loadSession,
        getDiffPanelChrome: () => readCurrentAppCapabilityModel(stateRef).diffPanelChrome,
        scheduleMessage: startTransition,
      }),
    [],
  );

  const interactionResponseController = useMemo(
    () =>
      createInteractionResponseController({
        fetchJson,
        dispatch,
        normalizeSessionPayload,
        getCurrentSessionId: () => currentSessionIdRef.current,
        getCurrentInteraction: () => runtimeStateRef.current?.currentInteraction || null,
        getRespondingRequestIds: respondingRequestIdsHandle.read,
        setRespondingRequestIds: respondingRequestIdsHandle.set,
        loadSession,
      }),
    [respondingRequestIdsHandle],
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

  const panelResizeController = useMemo(
    () =>
      createPanelResizeController({
        documentObject: document,
        getComputedStyleFn: getComputedStyle,
      }),
    [],
  );

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
          onToggleRightPanel={workbenchCommandController.toggleRightPanel}
          onToggleBottomDrawer={workbenchCommandController.toggleBottomDrawer}
          onOpenPalette={workbenchCommandController.openPalette}
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
              onScroll={timelineScrollController.handleScroll}
              onOpenDiff={diffSurfaceController.open}
              onOpenFile={filePreviewController.openFile}
              chrome={appChrome.timeline || {}}
            />
            <Composer
              chrome={appChrome.composer || {}}
              interactionChrome={appChrome.interaction || {}}
              value={composerDraft}
              onChange={composerController.setDraft}
              onSend={composerController.sendMessage}
              onStop={cancelSession}
              isRunning={isTurnInterruptibleStatus(currentStatus)}
              currentMode={currentMode}
              modeCatalog={modeCatalog}
              commandGroupLabels={composerCommandGroupLabels}
              commands={composerCommands}
              fileTree={state.fileTree}
              onOpenCommandPalette={composerController.openCommandPalette}
              interaction={runtimeState.currentInteraction}
              interactionNotice={interactionNotice}
              interactionBusy={Boolean(
                runtimeState.currentInteraction?.interactionId &&
                  respondingRequestIds.includes(runtimeState.currentInteraction.interactionId)
              )}
              onRespondInteraction={interactionResponseController.respondToInteraction}
              branchToolbar={branchToolbarModel}
              onRefreshSourceControl={composerController.refreshSourceControl}
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
          onActivateSurface={rightPanelController.activateSurface}
          onCloseSurface={rightPanelController.closeSurface}
          onCloseOtherSurfaces={rightPanelController.closeOtherSurfaces}
          onCloseSurfacesToRight={rightPanelController.closeSurfacesToRight}
          onCloseAllSurfaces={rightPanelController.closeAllSurfaces}
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
            onOpenFile={filePreviewController.openFile}
            onOpenFilesSurface={rightPanelController.openFilesSurface}
            onLoadFileChildren={loadFileChildren}
            terminal={state.terminal}
            terminalChrome={terminalChrome}
            onTerminalNew={terminalController.openRightPanelSurface}
            onTerminalSplit={terminalController.splitActiveRightPanelSurface}
            onTerminalSplitVertical={terminalController.splitActiveRightPanelSurfaceVertical}
            onTerminalSelect={terminalController.activateActiveRightPanelPane}
            onTerminalSend={terminalController.sendTo}
            onTerminalClear={terminalController.clearById}
            onTerminalRestart={terminalController.restartById}
            onTerminalClose={terminalController.closeActiveRightPanelPane}
            previewChrome={previewChrome}
            previewServers={previewServers}
            onPreviewOpenUrl={previewController.openUrl}
            onPreviewRefresh={previewController.refresh}
            onPreviewOpenExternal={previewController.openExternal}
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
          onKindSelect={terminalController.selectBottomDrawerKind}
          onTerminalNew={terminalController.openNewBottomDrawerTerminal}
          onTerminalSelect={terminalController.activateBottomDrawerTerminal}
          onTerminalSend={terminalController.sendActive}
          onTerminalClear={terminalController.clearActive}
          onTerminalRestart={terminalController.restartActive}
          onTerminalClose={terminalController.closeActive}
        />
      }
      rightPanelOpen={state.workbench.rightPanel.open}
      bottomDrawerOpen={state.workbench.bottomDrawer.open}
      bottomDrawerHeight={state.workbench.bottomDrawer.height}
      onResizeSidebar={panelResizeController.startSidebarResize}
      onResizeRightPanel={panelResizeController.startRightPanelResize}
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
      onQueryChange={workbenchCommandController.updatePaletteQuery}
      onClose={workbenchCommandController.closePalette}
      onSelect={workbenchCommandController.selectPaletteCommand}
      onSelectSession={workbenchCommandController.selectPaletteSession}
      onSelectWorkspace={workbenchCommandController.selectPaletteWorkspace}
    />
    </>
  );
}

export default App;
