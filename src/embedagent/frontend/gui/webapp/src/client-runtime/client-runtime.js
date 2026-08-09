import { normalizeSessionPayload } from "../state-helpers.js";
import { createSessionTransportState } from "../session-runtime/session-transport-state.js";
import { buildSessionCapabilityModelFromState } from "../session-runtime/session-capability-model.js";
import { readComposerDraft } from "../composer/composer-state.js";
import { readActiveThreadId, readThreadSessions } from "../session-runtime/thread-state.js";
import { buildAppCapabilityModelFromState } from "../app-runtime/app-capability-model.js";
import { createActiveWorkspaceDataLoader } from "../app-runtime/active-workspace-data-loader.js";
import { createBrowserDialogService } from "../app-runtime/browser-dialog-service.js";
import { createComposerController } from "../app-runtime/composer-controller.js";
import { createContributionController } from "../app-runtime/contribution-controller.js";
import { createDiffSurfaceController } from "../app-runtime/diff-surface-controller.js";
import { createFilePreviewController } from "../app-runtime/file-preview-controller.js";
import { createInitialAppLoadController } from "../app-runtime/initial-app-load-controller.js";
import { createInteractionResponseController } from "../app-runtime/interaction-response-controller.js";
import {
  createLoaderRequestExecutor,
  createSessionCommandCapabilityLoader,
} from "../app-runtime/session-loaders.js";
import { createPreviewController } from "../app-runtime/preview-controller.js";
import { createRespondingRequestIdsHandle } from "../app-runtime/responding-request-ids-handle.js";
import { createSessionActivationController } from "../app-runtime/session-activation-controller.js";
import { createSessionController } from "../app-runtime/session-controller.js";
import { createSessionListController } from "../app-runtime/session-list-controller.js";
import { createSessionTransportController } from "../app-runtime/session-transport-controller.js";
import { createSessionTransportHandle } from "../app-runtime/session-transport-handle.js";
import { createSocketMessageController } from "../app-runtime/socket-message-controller.js";
import { createSourceControlController } from "../app-runtime/source-control-controller.js";
import { createTerminalController } from "../app-runtime/terminal-controller.js";
import { createThreadLifecycleController } from "../app-runtime/thread-lifecycle-controller.js";
import { createTimelineScrollController } from "../app-runtime/timeline-scroll-controller.js";
import { createVisualDebugController } from "../app-runtime/visual-debug-controller.js";
import { createWorkbenchCommandController } from "../app-runtime/workbench-command-controller.js";
import { createWorkbenchKeyboardController } from "../app-runtime/workbench-keyboard-controller.js";
import { createWorkspaceController } from "../app-runtime/workspace-controller.js";
import { createWorkspaceFilesController } from "../app-runtime/workspace-files-controller.js";
import {
  buildCommandVisibilityContext,
  isTurnInterruptibleStatus,
} from "../workbench/commands.js";

const CLOSED_ERROR = "client_runtime_closed";

function noop() {}

function defaultBrowser() {
  const windowObject = typeof window === "undefined" ? null : window;
  const documentObject = typeof document === "undefined" ? null : document;
  return { windowObject, documentObject };
}

function browserParts(browser = {}) {
  const defaults = defaultBrowser();
  const windowObject = browser.windowObject || defaults.windowObject || {
    addEventListener: noop,
    removeEventListener: noop,
    setTimeout,
    clearTimeout,
  };
  const documentObject = browser.documentObject || windowObject.document
    || defaults.documentObject || { activeElement: null, documentElement: null };
  const timer = browser.timer || windowObject;
  return {
    documentObject,
    getComputedStyleFn: browser.getComputedStyleFn,
    scheduleMessage: typeof browser.scheduleMessage === "function"
      ? browser.scheduleMessage
      : (callback) => callback(),
    timer,
    windowObject,
  };
}

function appModel(getState) {
  return buildAppCapabilityModelFromState(getState());
}

function sessionModel(getState) {
  return buildSessionCapabilityModelFromState(getState());
}

function actionKey(request) {
  if (typeof request === "string") return request;
  const kind = String(request?.kind || "").trim();
  const action = String(request?.action || "").trim();
  return kind && action ? `${kind}.${action}` : "";
}

export function createClientRuntime({
  protocol,
  dispatch,
  getState,
  browser,
  defaultMode = "",
  getActivityRuntime,
  getTimelineElement,
  onSessionTransportChange,
  onRespondingRequestIdsChange,
} = {}) {
  const dispatchAction = typeof dispatch === "function" ? dispatch : noop;
  const readState = typeof getState === "function" ? getState : () => ({});
  const readActivityRuntime =
    typeof getActivityRuntime === "function" ? getActivityRuntime : () => ({});
  const browserRuntime = browserParts(browser);
  const pendingTimerIds = new Set();
  let closed = false;
  let started = false;
  let startPromise = null;
  let keyboardCleanup = null;
  let visualDebugCleanup = null;
  let sessionTransportController = null;

  function send(action) {
    if (!closed) dispatchAction(action);
  }

  function assertOpen() {
    if (closed) throw new Error(CLOSED_ERROR);
  }

  function schedule(callback, delay = 0) {
    const id = browserRuntime.timer.setTimeout(() => {
      pendingTimerIds.delete(id);
      callback();
    }, delay);
    pendingTimerIds.add(id);
    return id;
  }

  const sessionTransportHandle = createSessionTransportHandle({
    initialTransport: createSessionTransportState(),
    setTransport: onSessionTransportChange,
  });
  const respondingRequestIdsHandle = createRespondingRequestIdsHandle({
    initialRequestIds: [],
    setRequestIds: onRespondingRequestIdsChange,
  });
  const readAppModel = () => appModel(readState);
  const readSessionModel = () => sessionModel(readState);

  const sourceControlController = createSourceControlController({
    protocol,
    dispatch: send,
    getAppCapabilities: () => readAppModel().appCapabilities,
    hasActiveWorkspace: () => Boolean(readState().app?.hasActiveWorkspace),
    getSourceControlChrome: () => readAppModel().sourceControlChrome,
    getDiffPanelChrome: () => readAppModel().diffPanelChrome,
  });
  const timelineScrollController = createTimelineScrollController({
    getElement: typeof getTimelineElement === "function" ? getTimelineElement : () => null,
  });
  const contributionController = createContributionController({
    dispatch: send,
    getShellDescriptor: () => readState().app?.shell || {},
  });
  const terminalController = createTerminalController({
    protocol,
    dispatch: send,
    getState: readState,
    getAppCapabilities: () => readAppModel().appCapabilities,
    getTerminalChrome: () => readAppModel().terminalChrome,
    contributionController,
  });
  const loadSessionCommandCapabilities = createSessionCommandCapabilityLoader({
    protocol,
    dispatch: send,
  });
  const sessionListController = createSessionListController({ protocol, dispatch: send });
  const workspaceFilesController = createWorkspaceFilesController({
    protocol,
    dispatch: send,
    getAppCapabilities: () => readAppModel().appCapabilities,
  });
  const filePreviewController = createFilePreviewController({
    protocol,
    dispatch: send,
    getFilePreviewChrome: () => readAppModel().filePreviewChrome,
    contributionController,
  });
  const previewController = createPreviewController({
    protocol,
    dispatch: send,
    getCurrentSessionId: () => readActiveThreadId(readState()),
    getPreviewChrome: () => readAppModel().previewChrome,
    contributionController,
  });
  const diffSurfaceController = createDiffSurfaceController({
    dispatch: send,
    getRuntimeState: readActivityRuntime,
    getDiffPanelChrome: () => readAppModel().diffPanelChrome,
  });
  let loadSession = () => Promise.resolve({ stale: true });
  const activeWorkspaceDataLoader = createActiveWorkspaceDataLoader({
    getAppCapabilities: () => readAppModel().appCapabilities,
    loadSessions: sessionListController.loadSessions,
    loadSessionCommandCapabilities,
    loadFileChildren: workspaceFilesController.loadFileChildren,
    loadStatus: sourceControlController.loadStatus,
  });
  const workspaceController = createWorkspaceController({
    protocol,
    dispatch: send,
    getState: readState,
    getCurrentSessionId: () => readActiveThreadId(readState()),
    loadWorkspaceData: activeWorkspaceDataLoader.loadActiveWorkspaceData,
  });
  const sessionController = createSessionController({
    protocol,
    dispatch: send,
    normalizeSessionPayload,
    getCurrentSessionId: () => readActiveThreadId(readState()),
    getCurrentMode: () => readState().snapshot?.current_mode || readState().requestedMode,
    hasActiveWorkspace: () => Boolean(readState().app?.hasActiveWorkspace),
    markTimelineBottom: timelineScrollController.markFollowingBottom,
    loadSessions: sessionListController.loadSessions,
    loadSession: (...args) => loadSession(...args),
  });
  const dialogService = createBrowserDialogService({
    windowObject: browserRuntime.windowObject,
  });
  const threadLifecycleController = createThreadLifecycleController({
    protocol,
    dispatch: send,
    loadSessions: sessionListController.loadSessions,
    loadSession: (...args) => loadSession(...args),
    getThreadSessions: () => readThreadSessions(readState()),
    getThreadLifecycleCapabilities: () => readAppModel().threadLifecycleCapabilities,
    prompt: dialogService.prompt,
    confirm: dialogService.confirm,
  });
  const composerController = createComposerController({
    dispatch: send,
    getComposerDraft: () => readComposerDraft(readState()),
    submitText: sessionController.submitText,
    refreshSourceControl: sourceControlController.loadStatus,
  });
  const workbenchCommandController = createWorkbenchCommandController({
    dispatch: send,
    documentObject: browserRuntime.documentObject,
    setTimeoutFn: schedule,
    getCurrentMode: () => readState().snapshot?.current_mode || readState().requestedMode,
    getCurrentSessionId: () => readActiveThreadId(readState()),
    getShellDescriptor: () => readAppModel().appCapabilities.shell,
    getSessionCapabilities: () => readSessionModel().sessionCapabilities,
    getAppCapabilities: () => readAppModel().appCapabilities,
    createSession: sessionController.createSession,
    loadSession: (...args) => loadSession(...args),
    activateWorkspace: workspaceController.activateWorkspace,
    cancelSession: sessionController.cancelSession,
    renameSession: (sessionId, command) => threadLifecycleController.renameThread(
      sessionId,
      { id: "rename", capability: "rename", label: command.label },
    ),
    archiveSession: (sessionId, command) => threadLifecycleController.archiveThread(
      sessionId,
      { id: "archive", capability: "archive", label: command.label },
    ),
    forkSession: (sessionId, command) => threadLifecycleController.forkThread(
      sessionId,
      { id: "fork", capability: "fork", label: command.label },
    ),
    submitText: sessionController.submitText,
    setMode: sessionController.setMode,
    openContributionSurface: contributionController.openSurface,
    prompt: dialogService.prompt,
  });
  const executeLoaderRequest = createLoaderRequestExecutor({
    loadAppBootstrap: workspaceController.loadAppBootstrap,
    loadActiveWorkspaceData: workspaceController.loadActiveWorkspaceData,
    loadSessions: sessionListController.loadSessions,
    loadSession: (...args) => loadSession(...args),
    loadFileChildren: workspaceFilesController.loadFileChildren,
    loadSourceControl: sourceControlController.refreshStatus,
    loadSessionCommandCapabilities,
  });
  const socketMessageController = createSocketMessageController({
    dispatch: send,
    executeLoaderRequest,
    getSessionTransportController: () => sessionTransportController,
    getSessionTransportState: sessionTransportHandle.read,
    getCurrentSessionId: () => readActiveThreadId(readState()),
    clearRespondingRequestId: respondingRequestIdsHandle.clear,
    getDiffPanelChrome: () => readAppModel().diffPanelChrome,
    scheduleMessage: browserRuntime.scheduleMessage,
  });
  loadSession = createSessionActivationController({
    protocol,
    dispatch: send,
    defaultMode,
    getTransportState: sessionTransportHandle.read,
    updateTransportState: sessionTransportHandle.update,
    dispatchAcceptedSessionEvent: socketMessageController.handleAcceptedSessionEvent,
    getAppCapabilities: () => readAppModel().appCapabilities,
  });
  sessionTransportController = createSessionTransportController({
    protocol,
    getCurrentSessionId: () => readActiveThreadId(readState()),
    getTransportState: sessionTransportHandle.read,
    updateTransportState: sessionTransportHandle.update,
    loadSession,
    handleMessage: socketMessageController.handleMessage,
    timer: browserRuntime.timer,
  });
  const interactionResponseController = createInteractionResponseController({
    protocol,
    dispatch: send,
    normalizeSessionPayload,
    getCurrentSessionId: () => readActiveThreadId(readState()),
    getCurrentInteraction: () => readActivityRuntime().currentInteraction || null,
    getRespondingRequestIds: respondingRequestIdsHandle.read,
    setRespondingRequestIds: respondingRequestIdsHandle.set,
    loadSession,
  });
  const keyboardController = createWorkbenchKeyboardController({
    windowObject: browserRuntime.windowObject,
    documentObject: browserRuntime.documentObject,
    getKeybindings: () => readAppModel().keybindings,
    getCommandContext: () => {
      const state = readState();
      return buildCommandVisibilityContext({
        currentSessionId: readActiveThreadId(state),
        currentStatus: state.snapshot?.status || "idle",
        appState: state.app,
        contributionState: state.contribution,
        sessionCapabilities: sessionModel(() => state).sessionCapabilities,
      });
    },
    getCurrentStatus: () => readState().snapshot?.status || "idle",
    isTurnInterruptibleStatus,
    cancelSession: sessionController.cancelSession,
    executeWorkbenchCommand: workbenchCommandController.execute,
  });
  const visualDebugController = createVisualDebugController({
    windowObject: browserRuntime.windowObject,
    dispatch: send,
    openDiffFixture: diffSurfaceController.open,
    getCurrentMode: () => readState().requestedMode || defaultMode,
  });
  const initialLoadController = createInitialAppLoadController({
    loadAppBootstrap: workspaceController.loadAppBootstrap,
    loadSessionCommandCapabilities,
  });

  function installVisualDebug() {
    if (typeof visualDebugCleanup === "function") visualDebugCleanup();
    visualDebugCleanup = visualDebugController.install() || null;
  }

  const actionHandlers = Object.freeze({
    "command_palette.close": workbenchCommandController.closePalette,
    "command_palette.open": workbenchCommandController.openPalette,
    "command_palette.query": workbenchCommandController.updatePaletteQuery,
    "command_palette.select_command": workbenchCommandController.selectPaletteCommand,
    "command_palette.select_session": workbenchCommandController.selectPaletteSession,
    "command_palette.select_workspace": workbenchCommandController.selectPaletteWorkspace,
    "composer.open_palette": composerController.openCommandPalette,
    "composer.refresh_source_control": composerController.refreshSourceControl,
    "composer.send": composerController.sendMessage,
    "composer.set_draft": composerController.setDraft,
    "diff.open": diffSurfaceController.open,
    "file.open": filePreviewController.openFile,
    "files.load": workspaceFilesController.loadFileChildren,
    "files.open_surface": contributionController.openFiles,
    "interaction.sync": (interactionId) => respondingRequestIdsHandle.set((ids) =>
      ids.filter((requestId) => requestId === String(interactionId || ""))),
    "preview.open_external": previewController.openExternal,
    "preview.open_url": previewController.openUrl,
    "preview.refresh": previewController.refresh,
    "session.reload_list": sessionListController.loadSessions,
    "source_control.change_settings": (patch) => send({ type: "app_shell_settings_changed", patch }),
    "source_control.focus_diff": (filePath) => send({ type: "diff_file_focused", filePath }),
    "source_control.open_file": (file, scope) => sourceControlController.openFile(
      typeof file === "string" ? { path: file } : file,
      scope,
    ),
    "source_control.refresh": () => sourceControlController.loadStatus(true),
    "surface.activate": contributionController.activate,
    "surface.close": contributionController.close,
    "surface.close_all": contributionController.closeAll,
    "surface.close_others": contributionController.closeOthers,
    "surface.close_after": contributionController.closeAfter,
    "surface.open": contributionController.openSurface,
    "terminal.activate": terminalController.activateContributionTerminal,
    "terminal.clear_active": terminalController.clearActive,
    "terminal.clear_by_id": terminalController.clearById,
    "terminal.close_active": terminalController.closeActive,
    "terminal.close": terminalController.closeContributionTerminal,
    "terminal.open": terminalController.openContribution,
    "terminal.restart_active": terminalController.restartActive,
    "terminal.restart_by_id": terminalController.restartById,
    "terminal.send_active": terminalController.sendActive,
    "terminal.send_to": terminalController.sendTo,
    "terminal.split": terminalController.splitContribution,
    "terminal.split_vertical": terminalController.splitContributionVertical,
    "timeline.mark_bottom": timelineScrollController.markFollowingBottom,
    "timeline.scroll": timelineScrollController.handleScroll,
    "timeline.sync_bottom": timelineScrollController.syncToBottom,
    "visual_debug.refresh": installVisualDebug,
    "workspace.load_active": workspaceController.loadActiveWorkspaceData,
    "workspace.path_changed": workspaceController.setWorkspacePath,
  });

  function action(callback) {
    return (...args) => {
      try {
        assertOpen();
        return Promise.resolve(callback(...args));
      } catch (error) {
        return Promise.reject(error);
      }
    };
  }

  const actions = Object.freeze({
    activateWorkspace: action((workspace) => {
      if (workspace && typeof workspace === "object") {
        if (workspace.remove) return workspaceController.removeWorkspace(workspace.id);
        if (Object.hasOwn(workspace, "path")) {
          return workspaceController.openWorkspace(workspace.path);
        }
        return workspaceController.activateWorkspace(workspace.id);
      }
      return workspaceController.activateWorkspace(workspace);
    }),
    selectSession: action((sessionId) => loadSession(sessionId)),
    createSession: action(sessionController.createSession),
    renameSession: action((sessionId) =>
      threadLifecycleController.handleThreadLifecycleAction("rename", sessionId)),
    archiveSession: action((sessionId) =>
      threadLifecycleController.handleThreadLifecycleAction("archive", sessionId)),
    forkSession: action((sessionId) =>
      threadLifecycleController.handleThreadLifecycleAction("fork", sessionId)),
    setMode: action(sessionController.setMode),
    cancelSession: action(sessionController.cancelSession),
    submitText: action(sessionController.submitText),
    respondToInteraction: action(interactionResponseController.respondToInteraction),
    executeCommand: action(workbenchCommandController.execute),
    dispatchAction: action((request, ...args) => {
      const handler = actionHandlers[actionKey(request)];
      if (typeof handler !== "function") return null;
      return handler(...args);
    }),
  });

  function start() {
    try {
      assertOpen();
    } catch (error) {
      return Promise.reject(error);
    }
    if (started) return startPromise;
    started = true;
    keyboardCleanup = keyboardController.install() || null;
    installVisualDebug();
    sessionTransportController.connect();
    const result = initialLoadController.start();
    startPromise = Promise.all([
      Promise.resolve(result.bootstrapResult),
      Promise.resolve(result.commandCapabilitiesResult),
    ]).then(() => undefined);
    return startPromise;
  }

  function close() {
    if (closed) return;
    closed = true;
    sessionTransportController.close();
    if (typeof keyboardCleanup === "function") keyboardCleanup();
    if (typeof visualDebugCleanup === "function") visualDebugCleanup();
    keyboardCleanup = null;
    visualDebugCleanup = null;
    for (const timerId of pendingTimerIds) browserRuntime.timer.clearTimeout(timerId);
    pendingTimerIds.clear();
  }

  return Object.freeze({ start, close, actions });
}
