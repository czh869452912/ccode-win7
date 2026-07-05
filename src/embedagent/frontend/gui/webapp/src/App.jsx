import React, { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { INITIAL_REQUESTED_MODE, initialState, reducer } from "./store.js";
import { normalizeSessionPayload } from "./state-helpers.js";
import { createSessionTransportState } from "./session-runtime/session-transport-state.js";
import { buildAppHomeModel } from "./session-runtime/app-home-model.js";
import { buildSessionActivityRuntime } from "./session-runtime/activity-state.js";
import { buildComposerCommandsFromCapabilities } from "./session-runtime/command-capabilities.js";
import { createSocketMessageController } from "./app-runtime/socket-message-controller.js";
import { createBrowserDialogService } from "./app-runtime/browser-dialog-service.js";
import { fetchJson } from "./app-runtime/http-client.js";
import { createComposerController } from "./app-runtime/composer-controller.js";
import { createInitialAppLoadController } from "./app-runtime/initial-app-load-controller.js";
import { createDiffSurfaceController } from "./app-runtime/diff-surface-controller.js";
import { createFilePreviewController } from "./app-runtime/file-preview-controller.js";
import { createLoaderRequestExecutor, loadSessionCommandCapabilities } from "./app-runtime/session-loaders.js";
import { createPreviewController } from "./app-runtime/preview-controller.js";
import { createRespondingRequestIdsHandle } from "./app-runtime/responding-request-ids-handle.js";
import {
  createPanelResizeController,
  RESIZE_DIRECTIONS,
} from "./app-runtime/panel-resize-controller.js";
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
import { nextTerminalId } from "./terminal/terminal-labels.js";
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
import { commandById, visibleCommands } from "./workbench/commands.js";
import { createActiveWorkspaceDataLoader } from "./app-runtime/active-workspace-data-loader.js";
import { createWorkbenchKeyboardController } from "./app-runtime/workbench-keyboard-controller.js";
import {
  persistWorkbenchUiState,
  readPersistedWorkbenchUiState,
} from "./workbench/ui-state.js";

const EMPTY_COMMAND_GROUPS = [];
const EMPTY_KEYBINDINGS = [];

function isTurnInterruptibleStatus(status) {
  return status === "running" || status === "waiting_permission" || status === "waiting_user_input";
}

function App() {
  const [state, dispatch] = useReducer(reducer, initialState, (baseState) => ({
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
  const appChrome = state.app.capabilities?.chrome || {};
  const commandContext = useMemo(() => ({
    hasSession: Boolean(currentSessionId),
    hasWorkspace: Boolean(state.app.hasActiveWorkspace),
    isRunning: isTurnInterruptibleStatus(currentStatus),
    paletteOpen: state.workbench.commandPalette.open,
    capabilities: state.sessionCapabilities || {},
    appCapabilities: state.app.capabilities || {},
  }), [
    currentStatus,
    currentSessionId,
    state.app.capabilities,
    state.app.hasActiveWorkspace,
    state.workbench.commandPalette.open,
    state.sessionCapabilities,
  ]);
  const paletteCommands = useMemo(() => visibleCommands(commandContext), [commandContext]);
  const keybindings = state.app.capabilities.keybindings || EMPTY_KEYBINDINGS;
  const commandPaletteGroups =
    state.app.capabilities?.commandPalette?.groups || EMPTY_COMMAND_GROUPS;
  const composerCommandGroupLabels = useMemo(
    () =>
      commandPaletteGroups.reduce((labels, group) => {
        if (group?.id) labels[group.id] = group.title || "";
        return labels;
      }, {}),
    [commandPaletteGroups],
  );
  const composerCommands = useMemo(
    () =>
      buildComposerCommandsFromCapabilities(state.sessionCapabilities || {}, {
        defaultGroupId: appChrome.composer?.commandMenu?.defaultCommandGroupId || "",
      }),
    [appChrome.composer, state.sessionCapabilities],
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
        toolCatalog: state.sessionCapabilities?.toolCatalog || {},
      }),
    [
      sessionTransport,
      state.activeTurnId,
      state.snapshot,
      state.thinkingActive,
      state.activities,
      state.sessionCapabilities,
    ],
  );
  runtimeStateRef.current = runtimeState;
  const interactionNotice = state.interactionNotice || runtimeState.interactionNotice;
  const terminalChrome = state.app.capabilities?.terminal?.chrome || {};
  const sourceControlCapability = state.app.capabilities?.sourceControl || {};
  const sourceControlChrome = sourceControlCapability.chrome || {};
  const previewCapability = state.app.capabilities?.preview || {};
  const previewChrome = previewCapability.chrome || {};
  const surfaceChrome = state.app.capabilities?.surfaces?.chrome || {};
  const filePreviewChrome = surfaceChrome.filePreview || {};
  const diffPanelChrome = surfaceChrome.diffPanel || {};
  const sourceControlController = useMemo(
    () =>
      createSourceControlController({
        dispatch,
        getAppCapabilities: () => stateRef.current.app.capabilities || {},
        hasActiveWorkspace: () => stateRef.current.app.hasActiveWorkspace,
        getSourceControlChrome: () =>
          stateRef.current.app.capabilities?.sourceControl?.chrome || {},
        getDiffPanelChrome: () =>
          stateRef.current.app.capabilities?.surfaces?.chrome?.diffPanel || {},
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
        getAppCapabilities: () => stateRef.current.app.capabilities || {},
        getTerminalChrome: () => stateRef.current.app.capabilities?.terminal?.chrome || {},
        dispatch,
        api: {
          listTerminals,
          openTerminal,
          writeTerminal,
          clearTerminal,
          restartTerminal,
          closeTerminal,
        },
        nextTerminalId,
      }),
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
      loadSessionCommandCapabilities: () => loadSessionCommandCapabilities({ fetchJson, dispatch }),
    }).start();
  }, []);

  // websocket lifecycle
  useEffect(() => {
    const controller = createSessionTransportController({
      getCurrentSessionId: () => currentSessionIdRef.current,
      getTransportState: sessionTransportHandle.read,
      updateTransportState: sessionTransportHandle.update,
      loadSession,
      handleMessage: (message) => {
        startTransition(() => socketMessageController.handleMessage(message));
      },
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
        getAppCapabilities: () => stateRef.current.app.capabilities || {},
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
        getAppCapabilities: () => stateRef.current.app.capabilities || {},
      }),
    [],
  );
  const rightPanelController = useMemo(
    () =>
      createRightPanelController({
        dispatch,
        terminalController,
        getAppCapabilities: () => stateRef.current.app.capabilities || {},
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
        getFilePreviewChrome: () =>
          stateRef.current.app.capabilities?.surfaces?.chrome?.filePreview || {},
        rightPanelController,
      }),
    [rightPanelController],
  );
  const previewController = useMemo(
    () =>
      createPreviewController({
        dispatch,
        getCurrentSessionId: () => readActiveThreadId(stateRef.current),
        getPreviewChrome: () => stateRef.current.app.capabilities?.preview?.chrome || {},
        rightPanelController,
      }),
    [rightPanelController],
  );
  const diffSurfaceController = useMemo(
    () =>
      createDiffSurfaceController({
        dispatch,
        getRuntimeState: () => runtimeStateRef.current || {},
        getDiffPanelChrome: () =>
          stateRef.current.app.capabilities?.surfaces?.chrome?.diffPanel || {},
      }),
    [],
  );
  const { loadFileChildren } = workspaceFilesController;

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
        getAppCapabilities: () => stateRef.current.app.capabilities || {},
        loadSessions,
        loadSessionCommandCapabilities: () => loadSessionCommandCapabilities({ fetchJson, dispatch }),
        loadFileChildren,
        loadStatus: (refresh, assumeWorkspace, appCapabilities) =>
          sourceControlController.loadStatus(refresh, assumeWorkspace, appCapabilities),
      }),
    [sourceControlController],
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
        getThreadLifecycleCapabilities: () => stateRef.current.app.capabilities?.threadLifecycle || {},
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
        createSession,
        loadSessions,
        loadAppBootstrap,
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
        getKeybindings: () => stateRef.current.app.capabilities.keybindings || EMPTY_KEYBINDINGS,
        getCommandContext: () => {
          const current = stateRef.current;
          const status = current.snapshot?.status || "idle";
          return {
            paletteOpen: current.workbench.commandPalette.open,
            isRunning: isTurnInterruptibleStatus(status),
            capabilities: current.sessionCapabilities || {},
            appCapabilities: current.app.capabilities || {},
          };
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
    loadSessionCommandCapabilities: () => loadSessionCommandCapabilities({ fetchJson, dispatch }),
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
        getDiffPanelChrome: () =>
          stateRef.current.app.capabilities?.surfaces?.chrome?.diffPanel || {},
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
        logEvent: (label, detail) => dispatch({ type: "log_event", label, detail }),
      }),
    [respondingRequestIdsHandle],
  );

  const appHomeModel = useMemo(
    () => buildAppHomeModel({
      app: state.app,
      sessions: threadSessions,
      currentSessionId,
      defaultMode: INITIAL_REQUESTED_MODE,
      threadLifecycleCapabilities: state.app.capabilities?.threadLifecycle || {},
    }),
    [currentSessionId, state.app, threadSessions],
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

  const rightPanelSurfaces = state.workbench.rightPanel.surfaces || [];
  const activeRightPanelSurface =
    rightPanelSurfaces.find((surface) => surface.id === state.workbench.rightPanel.activeSurfaceId) || null;

  const surfacePanelProps = {
    plan: state.plan,
    diffSurface: state.diffSurface,
    sourceControl: state.sourceControl,
    sourceControlChrome,
    diffPanelChrome,
    appShell: state.app,
    chrome: appChrome.surfacePanel || {},
    onFocusDiffFile: (filePath) => dispatch({ type: "diff_file_focused", filePath }),
    onRefreshSourceControl: () => sourceControlController.loadStatus(true),
    onSelectSourceControlFile: (file, scope) => sourceControlController.openFile(file, scope),
    onAppSettingsChange: (patch) => dispatch({ type: "app_shell_settings_changed", patch }),
  };

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
          modeCatalog={state.sessionCapabilities?.modeCatalog || {}}
          turnsUsed={state.turnsUsed}
          maxTurns={state.maxTurns}
          rightPanelOpen={state.workbench.rightPanel.open}
          bottomDrawerOpen={state.workbench.bottomDrawer.open}
          onRefresh={loadSessions}
          onToggleRightPanel={() => dispatch({ type: "workbench_right_panel_toggled" })}
          onToggleBottomDrawer={() => dispatch({ type: "workbench_bottom_drawer_toggled" })}
          onOpenPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
        />
      }
      sidebar={
        <Sidebar
          app={state.app}
          appHome={appHomeModel}
          chrome={appChrome}
          currentSessionId={currentSessionId}
          currentMode={currentMode}
          modeCatalog={state.sessionCapabilities?.modeCatalog || {}}
          workspacePathInput={state.app.workspacePathInput}
          onWorkspacePathChange={(value) => dispatch({ type: "workspace_path_changed", value })}
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
              toolCatalog={state.sessionCapabilities?.toolCatalog || {}}
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
              value={composerDraft}
              onChange={composerController.setDraft}
              onSend={composerController.sendMessage}
              onStop={cancelSession}
              isRunning={isTurnInterruptibleStatus(currentStatus)}
              currentMode={currentMode}
              modeCatalog={state.sessionCapabilities?.modeCatalog || {}}
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
            emptyState={state.app.capabilities?.emptyState || state.sessionCapabilities?.emptyState}
            onChange={(value) => dispatch({ type: "workspace_path_changed", value })}
            onOpen={openWorkspace}
            onActivate={activateWorkspace}
          />
        )
      }
      rightPanel={
        <RightPanelTabs
          appCapabilities={state.app.capabilities}
          surfaces={rightPanelSurfaces}
          activeSurfaceId={state.workbench.rightPanel.activeSurfaceId}
          onActivateSurface={(surface) => {
            rightPanelController.activateSurface(surface);
          }}
          onCloseSurface={(surface) => {
            dispatch({
              type: "workbench_surface_closed",
              placement: "right",
              surfaceId: surface.id,
              kind: surface.kind,
              resourceId: surface.resourceId,
            });
          }}
          onCloseOtherSurfaces={(surface) => {
            dispatch({
              type: "workbench_surface_close_others",
              placement: "right",
              surfaceId: surface.id,
            });
          }}
          onCloseSurfacesToRight={(surface) => {
            dispatch({
              type: "workbench_surface_close_to_right",
              placement: "right",
              surfaceId: surface.id,
            });
          }}
          onCloseAllSurfaces={() => {
            dispatch({ type: "workbench_surface_close_all", placement: "right" });
          }}
          onAddSurface={(kind) => openRightPanelSurface(kind)}
        >
          <RightPanelSurfaceBody
            appCapabilities={state.app.capabilities}
            surface={activeRightPanelSurface}
            surfacePanelProps={surfacePanelProps}
            filePreviewsByPath={state.filePreviewsByPath}
            filePreviewChrome={filePreviewChrome}
            projectName={state.app.activeWorkspace?.label || ""}
            fileTree={state.fileTree}
            treeHeight={treeHeight}
            onOpenFile={filePreviewController.openFile}
            onOpenFilesSurface={() => rightPanelController.openFilesSurface()}
            onLoadFileChildren={loadFileChildren}
            terminal={state.terminal}
            terminalChrome={terminalChrome}
            onTerminalNew={() => terminalController.openRightPanelSurface()}
            onTerminalSplit={() => terminalController.splitRightPanelSurface(activeRightPanelSurface)}
            onTerminalSplitVertical={() =>
              terminalController.splitRightPanelSurface(activeRightPanelSurface, "vertical")
            }
            onTerminalSelect={(terminalId) =>
              terminalController.activateRightPanelPane(activeRightPanelSurface, terminalId)
            }
            onTerminalSend={terminalController.sendTo}
            onTerminalClear={terminalController.clearById}
            onTerminalRestart={terminalController.restartById}
            onTerminalClose={(terminalId) =>
              terminalController.closeRightPanelPane(activeRightPanelSurface, terminalId)
            }
            previewChrome={previewChrome}
            previewServers={previewCapability.localServers || []}
            onPreviewOpenUrl={previewController.openUrl}
            onPreviewRefresh={previewController.refresh}
            onPreviewOpenExternal={previewController.openExternal}
          />
        </RightPanelTabs>
      }
      bottomDrawer={
        <BottomDrawer
          appCapabilities={state.app.capabilities}
          activeKind={state.workbench.bottomDrawer.activeKind}
          runOutput={state.runOutput}
          terminationReason={state.terminationDisplayReason || state.terminationReason}
          terminationMessage={state.terminationMessage}
          terminal={state.terminal}
          terminalChrome={terminalChrome}
          onKindSelect={(kind) => {
            void terminalController.selectBottomDrawerKind(kind);
          }}
          onTerminalNew={() => terminalController.ensureOpen(nextTerminalId(state.terminal.terminalIds))}
          onTerminalSelect={(terminalId) => dispatch({ type: "terminal_active_set", terminalId })}
          onTerminalSend={terminalController.sendActive}
          onTerminalClear={terminalController.clearActive}
          onTerminalRestart={terminalController.restartActive}
          onTerminalClose={terminalController.closeActive}
        />
      }
      rightPanelOpen={state.workbench.rightPanel.open}
      bottomDrawerOpen={state.workbench.bottomDrawer.open}
      bottomDrawerHeight={state.workbench.bottomDrawer.height}
      onResizeSidebar={(e) =>
        panelResizeController.startResize(e, "--sidebar-w-raw", RESIZE_DIRECTIONS.RIGHT)
      }
      onResizeRightPanel={(e) =>
        panelResizeController.startResize(e, "--right-panel-w-raw", RESIZE_DIRECTIONS.LEFT)
      }
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
      commandPalette={state.app.capabilities?.commandPalette || {}}
      onQueryChange={(query) => dispatch({ type: "workbench_command_palette_query_changed", query })}
      onClose={() => dispatch({ type: "workbench_command_palette_closed" })}
      onSelect={(command) => {
        dispatch({ type: "workbench_command_palette_closed" });
        void executeWorkbenchCommand(commandById(
          command.id,
          state.sessionCapabilities || {},
          state.app.capabilities || {},
        ));
      }}
      onSelectSession={(sessionId) => {
        dispatch({ type: "workbench_command_palette_closed" });
        void loadSession(sessionId);
      }}
      onSelectWorkspace={(workspaceId) => {
        dispatch({ type: "workbench_command_palette_closed" });
        void activateWorkspace(workspaceId);
      }}
    />
    </>
  );
}

export default App;
