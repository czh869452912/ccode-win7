import React, { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { INITIAL_REQUESTED_MODE, initialState, reducer } from "./store.js";
import {
  createTreeNode,
  makeEventId,
  normalizeSessionPayload,
} from "./state-helpers.js";
import { appendSessionTransportEvent, createSessionTransportState } from "./session-runtime/session-transport-state.js";
import { createDiffSurfaceState } from "./session-runtime/diff-model.js";
import { buildAppHomeModel } from "./session-runtime/app-home-model.js";
import { buildSessionActivityRuntime } from "./session-runtime/activity-state.js";
import { buildComposerCommandsFromCapabilities } from "./session-runtime/command-capabilities.js";
import { deriveSocketMessageEffects } from "./app-runtime/socket-message-effects.js";
import { createLoaderRequestExecutor, loadSessionCommandCapabilities } from "./app-runtime/session-loaders.js";
import { createRightPanelController } from "./app-runtime/right-panel-controller.js";
import { createSessionActivationController } from "./app-runtime/session-activation-controller.js";
import { createSessionController } from "./app-runtime/session-controller.js";
import { createSessionTransportController } from "./app-runtime/session-transport-controller.js";
import { createTerminalController } from "./app-runtime/terminal-controller.js";
import { createThreadLifecycleController } from "./app-runtime/thread-lifecycle-controller.js";
import { createInteractionResponseController } from "./app-runtime/interaction-response-controller.js";
import { createWorkbenchCommandController } from "./app-runtime/workbench-command-controller.js";
import { createWorkspaceController } from "./app-runtime/workspace-controller.js";
import { installVisualDebugFixtures } from "./app-runtime/visual-debug-fixtures.js";
import {
  clearTerminal,
  closeTerminal,
  listTerminals,
  openTerminal,
  restartTerminal,
  writeTerminal,
} from "./terminal/terminal-api.js";
import { nextTerminalId } from "./terminal/terminal-labels.js";
import {
  getSourceControlDiff,
  getSourceControlStatus,
  refreshSourceControlStatus,
} from "./source-control/source-control-api.js";
import {
  openPreviewExternal,
  openPreviewSession,
  refreshPreviewSession,
} from "./preview/preview-api.js";
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
import { eventToKey, resolveKeybinding } from "./workbench/keybindings.js";
import {
  persistWorkbenchUiState,
  readPersistedWorkbenchUiState,
} from "./workbench/ui-state.js";

const EMPTY_COMMAND_HINTS = [];
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
  const isAtBottomRef = useRef(true);
  const currentSessionIdRef = useRef("");
  const respondingRequestIdsRef = useRef([]);
  const runtimeStateRef = useRef(null);
  const sessionTransportRef = useRef(sessionTransport);
  const sessionTransportControllerRef = useRef(null);
  const stateRef = useRef(state);
  stateRef.current = state;

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
    () => buildComposerCommandsFromCapabilities(state.sessionCapabilities || {}),
    [state.sessionCapabilities],
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
    sessionTransportRef.current = sessionTransport;
  }, [sessionTransport]);

  function replaceSessionTransport(nextTransport) {
    sessionTransportRef.current = nextTransport;
    setSessionTransport(nextTransport);
    return nextTransport;
  }

  function updateSessionTransport(updater) {
    const nextTransport = updater(sessionTransportRef.current);
    sessionTransportRef.current = nextTransport;
    setSessionTransport(nextTransport);
    return nextTransport;
  }

  function setRespondingRequestIds(value) {
    const nextValue =
      typeof value === "function" ? value(respondingRequestIdsRef.current) : value;
    const normalized = Array.isArray(nextValue)
      ? nextValue.map((item) => String(item || "")).filter(Boolean)
      : [];
    respondingRequestIdsRef.current = normalized;
    setRespondingRequestIdsState(normalized);
  }

  function createRuntimeSessionTransport() {
    const connectionState = sessionTransportRef.current?.connectionState || "connecting";
    return createSessionTransportState({
      connectionState,
      reloadState: "healthy",
    });
  }

  // initial app/workspace data load
  useEffect(() => {
    loadAppBootstrap();
    loadSessionCommandCapabilities({ fetchJson, dispatch }).catch(() => {});
  }, []);

  // websocket lifecycle
  useEffect(() => {
    const controller = createSessionTransportController({
      getCurrentSessionId: () => currentSessionIdRef.current,
      getTransportState: () => sessionTransportRef.current,
      updateTransportState: updateSessionTransport,
      loadSession,
      handleMessage: (message) => {
        startTransition(() => handleSocketMessage(message.type, message.data || {}));
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

  // Escape key cancels running session
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === "Escape" && isTurnInterruptibleStatus(currentStatus)) {
        cancelSession();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [currentStatus, currentSessionId]);

  // smart auto-scroll: only follow when user is at bottom
  useEffect(() => {
    if (isAtBottomRef.current && timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [runtimeState.t3TimelineRows, state.thinkingActive, runtimeState.currentInteraction]);

  function handleTimelineScroll() {
    const el = timelineRef.current;
    if (!el) return;
    isAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  // ── API helpers ────────────────────────────────────────────────────

  async function fetchJson(url, options) {
    const res = await fetch(url, options);
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      const detail =
        typeof payload?.detail === "string" ? payload.detail : JSON.stringify(payload?.detail || "");
      const error = new Error(detail || `HTTP ${res.status}`);
      error.status = res.status;
      error.detail = detail;
      throw error;
    }
    return payload;
  }

  async function loadSourceControlStatus(refresh = false, assumeWorkspace = state.app.hasActiveWorkspace) {
    if (!assumeWorkspace) {
      dispatch({ type: "source_control_reset" });
      return null;
    }
    dispatch({ type: "source_control_load_started" });
    try {
      const payload = refresh ? await refreshSourceControlStatus() : await getSourceControlStatus();
      dispatch({ type: "source_control_status_loaded", status: payload });
      return payload;
    } catch (error) {
      dispatch({
        type: "source_control_load_failed",
        error: error.message || sourceControlChrome.statusUnavailableNotice,
      });
      return null;
    }
  }

  async function openSourceControlFile(file, scope = "unstaged") {
    const path = file?.path || "";
    if (!path) return;
    const selectedScope = scope || file?.diffScopes?.[0] || "unstaged";
    dispatch({ type: "source_control_file_selected", path, scope: selectedScope });
    dispatch({ type: "source_control_diff_started" });
    try {
      const diff = await getSourceControlDiff(path, selectedScope);
      dispatch({ type: "source_control_diff_loaded", diff });
      if (diff.available && diff.diff) {
        dispatch({
          type: "diff_surface_opened",
          diffSurface: createDiffSurfaceState({
            title: `Git Diff: ${path}`,
            diff: diff.diff,
            source: "source-control",
            filePath: path,
          }),
        });
      } else {
        dispatch({
          type: "source_control_diff_failed",
          error: diff.reason || sourceControlChrome.diffUnavailableNotice,
        });
      }
    } catch (error) {
      dispatch({
        type: "source_control_diff_failed",
        error: error.message || sourceControlChrome.diffUnavailableNotice,
      });
    }
  }

  async function loadSessions() {
    const payload = await fetchJson("/api/sessions");
    dispatch({ type: "sessions_loaded", sessions: payload.sessions || [] });
  }

  async function loadSession(sessionId) {
    const loadSessionController = createSessionActivationController({
      fetchJson,
      dispatch,
      defaultMode: INITIAL_REQUESTED_MODE,
      createTransportState: createRuntimeSessionTransport,
      replaceTransportState: replaceSessionTransport,
      listTerminals,
    });
    await loadSessionController(sessionId);
  }

  async function loadFileChildren(path) {
    const payload = await fetchJson(`/api/files/tree?path=${encodeURIComponent(path || ".")}`);
    const children = (payload.items || []).map(createTreeNode);
    if ((path || ".") === ".") {
      dispatch({ type: "file_tree_loaded", nodes: children });
    } else {
      dispatch({ type: "file_children_loaded", path, children: payload.items || [] });
    }
  }

  async function openFile(path, line) {
    const filePath = normalizeFileSurfacePath(path);
    if (!filePath) return;
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: "file",
      title: fileSurfaceTitle(filePath, filePreviewChrome),
      resourceId: filePath,
      filePath,
      revealLine: line,
    });
    dispatch({ type: "file_preview_load_started", path: filePath });
    try {
      const payload = await fetchJson(`/api/files/${encodeURIComponent(filePath)}`);
      dispatch({
        type: "file_preview_loaded",
        path: filePath,
        preview: {
          kind: "file",
          title: payload.path || filePath,
          content: payload.content || "",
        },
      });
    } catch (error) {
      dispatch({
        type: "file_preview_load_failed",
        path: filePath,
        error: error.message || filePreviewChrome.unavailableMessage,
      });
    }
  }

  function openDiffSurface({ title = "diff", diff = "", turnId = "", filePath = "" } = {}) {
    let resolvedDiff = diff;
    if (!resolvedDiff) {
      const item = runtimeState.timelineItems.find((candidate) => {
        if (turnId && candidate.turnId !== turnId) return false;
        const data = candidate.data || {};
        const args = candidate.arguments || {};
        if (filePath && data.path !== filePath && args.path !== filePath) return false;
        return typeof data.diff === "string" || typeof data.diff_preview === "string";
      });
      resolvedDiff = item?.data?.diff || item?.data?.diff_preview || "";
    }
    if (!resolvedDiff) return;
    dispatch({
      type: "diff_surface_opened",
      diffSurface: createDiffSurfaceState({
        title: filePath || title || "diff",
        diff: resolvedDiff,
        source: "gui",
        turnId,
        filePath,
      }),
    });
  }

  useEffect(() => {
    return installVisualDebugFixtures({
      windowObject: typeof window === "undefined" ? null : window,
      locationSearch: typeof window === "undefined" ? "" : window.location.search || "",
      dispatch,
      openDiffFixture: openDiffSurface,
      currentMode: state.requestedMode || INITIAL_REQUESTED_MODE,
    });
  }, [runtimeState.timelineItems, state.requestedMode]);

  const workspaceController = useMemo(
    () =>
      createWorkspaceController({
        fetchJson,
        dispatch,
        getState: () => stateRef.current,
        getCurrentSessionId: () => readActiveThreadId(stateRef.current),
        loadWorkspaceData: async (_sessionId, assumeWorkspace) => {
          await Promise.all([
            loadSessions(),
            loadSessionCommandCapabilities({ fetchJson, dispatch }),
            loadFileChildren("."),
            loadSourceControlStatus(false, assumeWorkspace),
          ]);
        },
      }),
    [],
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
        markTimelineBottom: () => {
          isAtBottomRef.current = true;
        },
        loadSessions,
        loadSession,
      }),
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
        prompt: (message, initialValue) => window.prompt(message, initialValue),
        confirm: (message) => window.confirm(message),
      }),
    [],
  );
  const { createSession, setMode, cancelSession, submitText } = sessionController;
  const { handleThreadLifecycleAction } = threadLifecycleController;

  async function sendMessage() {
    await submitText(composerDraft);
  }

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
    fileSurfaceTitle,
    normalizeFileSurfacePath,
    openSurface: openRightPanelSurface,
  } = rightPanelController;
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
        sendMessage: () => submitText(readComposerDraft(stateRef.current)),
        cancelSession,
        submitText,
        setMode,
        openRightPanelSurface,
        terminalController,
      }),
    [openRightPanelSurface, terminalController],
  );
  const executeWorkbenchCommand = workbenchCommandController.execute;

  useEffect(() => {
    function onWorkbenchKeyDown(event) {
      const command = resolveKeybinding(keybindings, eventToKey(event), {
        paletteOpen: state.workbench.commandPalette.open,
        isRunning: isTurnInterruptibleStatus(currentStatus),
        composerFocused: document.activeElement?.dataset?.testid === "composer-input",
        capabilities: state.sessionCapabilities || {},
        appCapabilities: state.app.capabilities || {},
      });
      if (!command) return;
      event.preventDefault();
      void executeWorkbenchCommand(command);
    }
    window.addEventListener("keydown", onWorkbenchKeyDown);
    return () => window.removeEventListener("keydown", onWorkbenchKeyDown);
  }, [
    state.workbench.commandPalette.open,
    currentStatus,
    composerDraft,
    currentSessionId,
    keybindings,
    state.sessionCapabilities,
    state.app.capabilities,
  ]);

  function logEvent(label, detail) {
    dispatch({ type: "log_event", label, detail });
  }

  const executeLoaderRequest = createLoaderRequestExecutor({
    loadAppBootstrap,
    loadActiveWorkspaceData,
    loadSessions,
    loadSession,
    loadFileChildren,
    loadSessionCommandCapabilities: () => loadSessionCommandCapabilities({ fetchJson, dispatch }),
  });

  function executeSocketEffects(effects = {}) {
    const transportEvents = effects.transportEvents || [];
    if (transportEvents.length) {
      const transportController = sessionTransportControllerRef.current;
      let nextTransport = sessionTransportRef.current;
      for (const entry of transportEvents) {
        if (transportController) {
          nextTransport = transportController.appendEvent(entry || {});
        } else {
          nextTransport = updateSessionTransport((current) =>
            appendSessionTransportEvent(current, entry || {}),
          );
        }
      }
      if (
        (nextTransport.reloadState === "reload_required" || nextTransport.reloadState === "degraded") &&
        currentSessionIdRef.current
      ) {
        if (transportController) {
          void transportController.recover(currentSessionIdRef.current, nextTransport);
        } else {
          void loadSession(currentSessionIdRef.current);
        }
      }
    }

    for (const action of effects.actions || []) {
      dispatch(action);
    }

    for (const request of effects.loaderRequests || []) {
      void executeLoaderRequest(request);
    }
  }

  function handleSocketMessage(type, data) {
    const effects = deriveSocketMessageEffects({
      type,
      data: data || {},
      currentSessionId: currentSessionIdRef.current,
      sessionTransport: sessionTransportRef.current,
      makeId: makeEventId,
      nowIso: () => new Date().toISOString(),
    });
    executeSocketEffects(effects);
  }

  const interactionResponseController = useMemo(
    () =>
      createInteractionResponseController({
        fetchJson,
        dispatch,
        normalizeSessionPayload,
        getCurrentSessionId: () => currentSessionIdRef.current,
        getCurrentInteraction: () => runtimeStateRef.current?.currentInteraction || null,
        getRespondingRequestIds: () => respondingRequestIdsRef.current,
        setRespondingRequestIds,
        loadSession,
        logEvent,
      }),
    [],
  );

  async function respondToInteraction(payload) {
    await interactionResponseController.respondToInteraction(payload);
  }

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

  async function openPreviewUrl(url) {
    const sessionId = readActiveThreadId(stateRef.current);
    if (!sessionId) {
      dispatch({ type: "interaction_notice_set", notice: previewChrome.sessionRequiredNotice || "" });
      return null;
    }
    try {
      const result = await openPreviewSession(sessionId, url);
      const snapshot = result.preview || null;
      const resourceId = snapshot?.url || url;
      dispatch({
        type: "workbench_surface_opened",
        placement: "right",
        kind: "preview",
        title: resourceId,
        resourceId,
        previewSnapshot: snapshot,
      });
      return result;
    } catch (error) {
      dispatch({
        type: "interaction_notice_set",
        notice: error instanceof Error ? error.message : previewChrome.failedNotice || "",
      });
      throw error;
    }
  }

  async function refreshPreview(snapshot) {
    const sessionId = readActiveThreadId(stateRef.current);
    const tabId = snapshot?.tabId || snapshot?.tab_id || "";
    if (!sessionId || !tabId) return null;
    try {
      const result = await refreshPreviewSession(sessionId, tabId);
      const nextSnapshot = result.preview || null;
      const resourceId = nextSnapshot?.url || snapshot?.url || "";
      dispatch({
        type: "workbench_surface_opened",
        placement: "right",
        kind: "preview",
        title: resourceId,
        resourceId,
        previewSnapshot: nextSnapshot,
      });
      return result;
    } catch (error) {
      dispatch({
        type: "interaction_notice_set",
        notice: error instanceof Error ? error.message : previewChrome.refreshFailedNotice || "",
      });
      throw error;
    }
  }

  async function openPreviewInSystemBrowser(url) {
    try {
      return await openPreviewExternal(url);
    } catch (error) {
      dispatch({
        type: "interaction_notice_set",
        notice: error instanceof Error ? error.message : previewChrome.openFailedNotice || "",
      });
      throw error;
    }
  }

  const surfacePanelProps = {
    plan: state.plan,
    diffSurface: state.diffSurface,
    sourceControl: state.sourceControl,
    sourceControlChrome,
    appShell: state.app,
    chrome: appChrome.surfacePanel || {},
    onFocusDiffFile: (filePath) => dispatch({ type: "diff_file_focused", filePath }),
    onRefreshSourceControl: () => loadSourceControlStatus(true),
    onSelectSourceControlFile: openSourceControlFile,
    onAppSettingsChange: (patch) => dispatch({ type: "app_shell_settings_changed", patch }),
  };

  const RESIZE_RIGHT = 1;   // sidebar: drag right = expand
  const RESIZE_LEFT  = -1;  // right panel: drag right = shrink

  function startResize(e, cssVar, direction) {
    e.preventDefault();
    const handle = e.currentTarget;
    handle.classList.add("dragging");
    const startX = e.clientX;
    const startVal =
      parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue(cssVar).trim()
      ) || (cssVar === "--sidebar-w-raw" ? 220 : 260);

    function onMove(ev) {
      const delta = (ev.clientX - startX) * direction;
      const newVal = Math.max(160, Math.min(480, startVal + delta));
      document.documentElement.style.setProperty(cssVar, `${newVal}px`);
    }
    function onEnd() {
      handle.classList.remove("dragging");
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup",   onEnd);
      handle.removeEventListener("pointercancel", onEnd);
    }
    handle.setPointerCapture(e.pointerId);
    handle.addEventListener("pointermove",   onMove);
    handle.addEventListener("pointerup",     onEnd);
    handle.addEventListener("pointercancel", onEnd);
  }

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
              onScroll={handleTimelineScroll}
              onOpenDiff={openDiffSurface}
              onOpenFile={openFile}
            />
            <Composer
              chrome={appChrome.composer || {}}
              value={composerDraft}
              onChange={(v) => dispatch({ type: "set_composer", value: v })}
              onSend={sendMessage}
              onStop={cancelSession}
              isRunning={isTurnInterruptibleStatus(currentStatus)}
              currentMode={currentMode}
              modeCatalog={state.sessionCapabilities?.modeCatalog || {}}
              commandHints={EMPTY_COMMAND_HINTS}
              commandGroupLabels={composerCommandGroupLabels}
              commands={composerCommands}
              fileTree={state.fileTree}
              onOpenCommandPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
              interaction={runtimeState.currentInteraction}
              interactionNotice={interactionNotice}
              interactionBusy={Boolean(
                runtimeState.currentInteraction?.interactionId &&
                  respondingRequestIds.includes(runtimeState.currentInteraction.interactionId)
              )}
              onRespondInteraction={respondToInteraction}
              branchToolbar={branchToolbarModel}
              onRefreshSourceControl={() => loadSourceControlStatus(true)}
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
            dispatch({
              type: "workbench_surface_activated",
              placement: "right",
              surfaceId: surface.id,
              kind: surface.kind,
            });
            if (surface.kind === "terminal" && surface.activeTerminalId) {
              void terminalController.openSession(surface.activeTerminalId);
            }
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
            surface={activeRightPanelSurface}
            surfacePanelProps={surfacePanelProps}
            filePreviewsByPath={state.filePreviewsByPath}
            filePreviewChrome={filePreviewChrome}
            projectName={state.app.activeWorkspace?.label || ""}
            fileTree={state.fileTree}
            treeHeight={treeHeight}
            onOpenFile={openFile}
            onOpenFilesSurface={() => openRightPanelSurface("files")}
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
            onPreviewOpenUrl={openPreviewUrl}
            onPreviewRefresh={refreshPreview}
            onPreviewOpenExternal={openPreviewInSystemBrowser}
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
      onResizeSidebar={(e) => startResize(e, "--sidebar-w-raw", RESIZE_RIGHT)}
      onResizeRightPanel={(e) => startResize(e, "--right-panel-w-raw", RESIZE_LEFT)}
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
