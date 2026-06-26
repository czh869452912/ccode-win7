import React, { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { DEFAULT_MODE, initialState, reducer } from "./store.js";
import {
  createTreeNode,
  makeEventId,
  normalizeSessionPayload,
} from "./state-helpers.js";
import { appendSessionTransportEvent, createSessionTransportState } from "./session-runtime/session-transport-state.js";
import { createDiffSurfaceState } from "./session-runtime/diff-model.js";
import { buildAppHomeModel } from "./session-runtime/app-home-model.js";
import { buildSessionActivityRuntime } from "./session-runtime/activity-state.js";
import { deriveSocketMessageEffects } from "./app-runtime/socket-message-effects.js";
import { createLoaderRequestExecutor } from "./app-runtime/session-loaders.js";
import { createSessionActivationController } from "./app-runtime/session-activation-controller.js";
import { createSessionTransportController } from "./app-runtime/session-transport-controller.js";
import { createTerminalController } from "./app-runtime/terminal-controller.js";
import { installVisualDebugFixtures } from "./app-runtime/visual-debug-fixtures.js";
import { canSwitchWorkspace, normalizeAppBootstrap } from "./app-workspaces.js";
import { LangContext } from "./LangContext.js";
import { t } from "./strings.js";
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
import { DEFAULT_KEYBINDINGS, eventToKey, resolveKeybinding } from "./workbench/keybindings.js";
import {
  persistWorkbenchUiState,
  readPersistedWorkbenchUiState,
} from "./workbench/ui-state.js";

const MODES = ["explore", "spec", "build", "debug", "verify"];
const SLASH_COMMAND_HINTS = [
  "/help",
  "/mode",
  "/sessions",
  "/resume",
  "/workspace",
  "/run",
  "/recipes",
  "/clear",
  "/plan",
  "/review",
  "/diff",
  "/permissions",
  "/tasks",
  "/artifacts",
];

function App() {
  const [state, dispatch] = useReducer(reducer, initialState, (baseState) => ({
    ...baseState,
    workbench: readPersistedWorkbenchUiState(),
  }));
  const treeHeight = 640;
  const [userAnswer, setUserAnswer] = useState("");
  const [sessionTransport, setSessionTransport] = useState(() => createSessionTransportState());
  const timelineRef = useRef(null);
  const isAtBottomRef = useRef(true);
  const currentSessionIdRef = useRef("");
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
  const commandContext = useMemo(() => ({
    hasSession: Boolean(currentSessionId),
    hasWorkspace: Boolean(state.app.hasActiveWorkspace),
    isRunning: currentStatus === "running" || currentStatus === "waiting_user_input",
    paletteOpen: state.workbench.commandPalette.open,
  }), [
    currentStatus,
    currentSessionId,
    state.app.hasActiveWorkspace,
    state.workbench.commandPalette.open,
  ]);
  const paletteCommands = useMemo(() => visibleCommands(commandContext), [commandContext]);
  const composerCommands = paletteCommands;
  const activeWorkspaceId = state.app.activeWorkspace?.id || "";
  const runtimeState = useMemo(
    () =>
      buildSessionActivityRuntime({
        snapshot: state.snapshot,
        sessionTransport,
        activities: state.timeline,
        defaultMode: DEFAULT_MODE,
        activeTurnId: state.activeTurnId,
        thinkingActive: state.thinkingActive,
      }),
    [sessionTransport, state.activeTurnId, state.snapshot, state.thinkingActive, state.timeline],
  );
  const interactionNotice = state.interactionNotice || runtimeState.interactionNotice;
  const terminalController = useMemo(
    () =>
      createTerminalController({
        getState: () => stateRef.current,
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
      if (e.key === "Escape" && (currentStatus === "running" || currentStatus === "waiting_user_input")) {
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

  async function loadAppBootstrap() {
    const payload = await fetchJson("/api/app/bootstrap");
    const bootstrap = normalizeAppBootstrap(payload || {});
    dispatch({ type: "app_bootstrap_loaded", bootstrap });
    if (bootstrap.hasActiveWorkspace) {
      await loadActiveWorkspaceData("", true);
    } else {
      dispatch({ type: "source_control_reset" });
    }
    return bootstrap;
  }

  async function loadActiveWorkspaceData(sessionId = currentSessionId, assumeWorkspace = state.app.hasActiveWorkspace) {
    await Promise.all([
      loadSessions(),
      loadArtifacts(),
      loadTasks(sessionId || ""),
      loadFileChildren("."),
      loadToolCatalog(),
      loadWorkspaceRecipes(),
      loadSourceControlStatus(false, assumeWorkspace),
    ]);
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
      dispatch({ type: "source_control_load_failed", error: error.message || "Source control unavailable" });
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
        dispatch({ type: "set_inspector", value: "diff" });
      } else {
        dispatch({ type: "source_control_diff_failed", error: diff.reason || "Diff unavailable" });
      }
    } catch (error) {
      dispatch({ type: "source_control_diff_failed", error: error.message || "Diff unavailable" });
    }
  }

  function workspaceErrorFrom(error) {
    return String(error?.detail || error?.message || "workspace_open_failed");
  }

  async function openWorkspace(path) {
    const targetPath = String(path || state.app.workspacePathInput || "").trim();
    if (!targetPath) {
      dispatch({ type: "workspace_activation_failed", error: "workspace_path_required" });
      return;
    }
    const switchState = canSwitchWorkspace(state);
    if (!switchState.allowed) {
      dispatch({ type: "workspace_activation_failed", error: switchState.reason });
      return;
    }
    dispatch({ type: "workspace_activation_started" });
    try {
      const payload = await fetchJson("/api/app/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: targetPath }),
      });
      const bootstrap = normalizeAppBootstrap(payload || {});
      dispatch({ type: "workspace_switched", bootstrap });
      if (bootstrap.hasActiveWorkspace) {
        await loadActiveWorkspaceData("", true);
      } else {
        dispatch({ type: "source_control_reset" });
      }
    } catch (error) {
      dispatch({ type: "workspace_activation_failed", error: workspaceErrorFrom(error) });
    }
  }

  async function activateWorkspace(workspaceId) {
    const switchState = canSwitchWorkspace(state);
    if (!switchState.allowed) {
      dispatch({ type: "workspace_activation_failed", error: switchState.reason });
      return;
    }
    dispatch({ type: "workspace_activation_started" });
    try {
      const payload = await fetchJson(
        `/api/app/workspaces/${encodeURIComponent(workspaceId)}/activate`,
        { method: "POST" },
      );
      const bootstrap = normalizeAppBootstrap(payload || {});
      dispatch({ type: "workspace_switched", bootstrap });
      if (bootstrap.hasActiveWorkspace) {
        await loadActiveWorkspaceData("", true);
      } else {
        dispatch({ type: "source_control_reset" });
      }
    } catch (error) {
      dispatch({ type: "workspace_activation_failed", error: workspaceErrorFrom(error) });
    }
  }

  async function removeWorkspace(workspaceId) {
    const payload = await fetchJson(`/api/app/workspaces/${encodeURIComponent(workspaceId)}`, {
      method: "DELETE",
    });
    const bootstrap = normalizeAppBootstrap(payload || {});
    dispatch({ type: "workspace_switched", bootstrap });
    if (bootstrap.hasActiveWorkspace) {
      await loadActiveWorkspaceData("", true);
    } else {
      dispatch({ type: "source_control_reset" });
    }
  }

  async function loadSessions() {
    const payload = await fetchJson("/api/sessions");
    dispatch({ type: "sessions_loaded", sessions: payload.sessions || [] });
  }

  async function loadToolCatalog() {
    const payload = await fetchJson("/api/tool-catalog");
    const items = Array.isArray(payload.items) ? payload.items : [];
    const catalog = {};
    for (const item of items) {
      if (!item || !item.name) continue;
      catalog[item.name] = item;
    }
    dispatch({ type: "tool_catalog_loaded", catalog });
  }

  async function loadPermissionContext(sessionId) {
    if (!sessionId) {
      dispatch({ type: "permission_context_loaded", context: null });
      return;
    }
    const payload = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/permissions`);
    dispatch({ type: "permission_context_loaded", context: payload });
  }

  async function loadSession(sessionId) {
    const loadSessionController = createSessionActivationController({
      fetchJson,
      dispatch,
      defaultMode: DEFAULT_MODE,
      createTransportState: createRuntimeSessionTransport,
      replaceTransportState: replaceSessionTransport,
      listTerminals,
      loadTasks,
      loadArtifacts,
    });
    await loadSessionController(sessionId);
  }

  async function loadTasks(sessionId) {
    const payload = await fetchJson(`/api/tasks?session_id=${encodeURIComponent(sessionId || "")}`);
    dispatch({ type: "tasks_loaded", tasks: payload.tasks || [] });
  }

  async function loadArtifacts() {
    const payload = await fetchJson("/api/artifacts");
    dispatch({ type: "artifacts_loaded", items: payload.items || [] });
  }

  async function loadWorkspaceRecipes() {
    const payload = await fetchJson("/api/workspace/recipes");
    dispatch({ type: "recipes_loaded", items: payload.items || [] });
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
      title: fileSurfaceTitle(filePath),
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
        error: error.message || "File unavailable",
      });
    }
  }

  async function openArtifact(reference) {
    const payload = await fetchJson(`/api/artifacts/${encodeURIComponent(reference)}`);
    const content =
      typeof payload.content === "string"
        ? payload.content
        : JSON.stringify(payload.content || {}, null, 2);
    dispatch({
      type: "preview_loaded",
      preview: { kind: "artifact", title: payload.path || reference, content },
      inspectorTab: "preview",
    });
  }

  async function openReviewEvidence(entry) {
    if (entry?.artifactRef) {
      await openArtifact(entry.artifactRef);
      return;
    }
    if (entry?.diff) {
      dispatch({
        type: "diff_surface_opened",
        diffSurface: createDiffSurfaceState({
          title: entry?.title || "Review Diff",
          diff: entry.diff,
          source: entry?.kind || "review",
        }),
      });
      return;
    }
    dispatch({
      type: "preview_loaded",
      preview: {
        kind: entry?.kind || "review",
        title: entry?.title || "Review Evidence",
        content: entry?.content || "",
      },
      inspectorTab: "preview",
    });
  }

  function openDiffSurface({ title = "Diff", diff = "", turnId = "", filePath = "" } = {}) {
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
        title: filePath || title || "Diff",
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
      currentMode: state.requestedMode || DEFAULT_MODE,
    });
  }, [runtimeState.timelineItems, state.requestedMode]);

  async function createSession(mode) {
    const payload = await fetchJson(`/api/sessions?mode=${encodeURIComponent(mode)}`, {
      method: "POST",
    });
    const snapshot = normalizeSessionPayload(payload);
    dispatch({ type: "session_activated", sessionId: snapshot.session_id, snapshot, timeline: [] });
    replaceSessionTransport(createRuntimeSessionTransport());
    await Promise.all([loadSessions(), loadTasks(snapshot.session_id), loadPermissionContext(snapshot.session_id)]);
    return snapshot.session_id;
  }

  async function renameThread(sessionId) {
    const current = threadSessions.find((item) => item.session_id === sessionId) || {};
    const initialTitle = current.thread?.title || current.title || current.user_goal || "";
    const title = window.prompt("Rename thread", initialTitle);
    if (title === null) return;
    const normalizedTitle = String(title || "").trim();
    if (!normalizedTitle) {
      dispatch({
        type: "interaction_notice_set",
        notice: {
          kind: "thread_lifecycle",
          title: "Rename failed",
          body: "Thread title cannot be empty.",
        },
      });
      return;
    }
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: normalizedTitle }),
    });
    await loadSessions();
  }

  async function archiveThread(sessionId) {
    const ok = window.confirm("Archive this thread?");
    if (!ok) return;
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/archive`, {
      method: "POST",
    });
    await loadSessions();
    dispatch({
      type: "interaction_notice_set",
      notice: {
        kind: "thread_lifecycle",
        title: "Thread archived",
        body: "The thread was archived and hidden from the normal thread list.",
      },
    });
  }

  async function forkThread(sessionId) {
    const title = window.prompt("Fork thread title", "");
    if (title === null) return;
    const payload = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/fork`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: String(title || "").trim() }),
    });
    await loadSessions();
    if (payload.session_id) {
      await loadSession(payload.session_id);
    }
  }

  async function handleThreadLifecycleAction(actionId, sessionId) {
    try {
      if (actionId === "rename") {
        await renameThread(sessionId);
        return;
      }
      if (actionId === "archive") {
        await archiveThread(sessionId);
        return;
      }
      if (actionId === "fork") {
        await forkThread(sessionId);
        return;
      }
    } catch (error) {
      dispatch({
        type: "interaction_notice_set",
        notice: {
          kind: "thread_lifecycle",
          title: "Thread action failed",
          body: error?.message || String(error || "thread_lifecycle_failed"),
        },
      });
    }
  }

  async function setMode(mode) {
    dispatch({ type: "mode_requested", mode });
    if (!currentSessionId) return;
    await fetchJson(`/api/sessions/${encodeURIComponent(currentSessionId)}/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    await loadSession(currentSessionId);
  }

  async function cancelSession() {
    if (!currentSessionId) return;
    dispatch({ type: "stream_completed" });
    await fetchJson(`/api/sessions/${encodeURIComponent(currentSessionId)}/cancel`, {
      method: "POST",
    });
  }

  async function submitText(rawText) {
    const text = (rawText || "").trim();
    if (!text) return;
    if (!state.app.hasActiveWorkspace) {
      dispatch({ type: "workspace_activation_failed", error: "no_active_workspace" });
      return;
    }
    isAtBottomRef.current = true;
    dispatch({ type: "stream_completed" });
    dispatch({ type: "local_user_message", text });
    let sessionId = currentSessionId;
    if (!sessionId) sessionId = await createSession(currentMode);
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  }

  async function sendMessage() {
    await submitText(composerDraft);
  }

  async function runRecipe(recipeId, options = {}) {
    const target = (options.target || "").trim();
    const profile = (options.profile || "").trim();
    const parts = ["/run", recipeId];
    if (target) parts.push(target);
    if (profile) parts.push(profile);
    await submitText(parts.join(" "));
  }

  function rightPanelSurfaceTitle(kind, fallback = "") {
    const label = String(fallback || "").replace(/^Open\s+/i, "").trim();
    if (label) return label;
    switch (kind) {
      case "diff":
        return "Diff";
      case "files":
        return "Files";
      case "terminal":
        return "Terminal";
      case "plan":
        return "Plan";
      case "source_control":
        return "Source Control";
      case "settings":
        return "Settings";
      case "diagnostics":
        return "Diagnostics";
      default:
        return String(kind || "");
    }
  }

  function normalizeFileSurfacePath(path) {
    return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
  }

  function fileSurfaceTitle(path) {
    const normalized = normalizeFileSurfacePath(path);
    if (!normalized) return "File";
    const parts = normalized.split("/");
    return parts[parts.length - 1] || normalized;
  }

  function openRightPanelSurface(kind, title = "") {
    const surfaceKind = String(kind || "");
    if (surfaceKind === "file") return;
    if (surfaceKind === "terminal") {
      void terminalController.openRightPanelSurface();
      return;
    }
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: surfaceKind,
      title: rightPanelSurfaceTitle(surfaceKind, title),
      resourceId: surfaceKind === "diff" ? "current" : "",
    });
    dispatch({ type: "set_inspector", value: surfaceKind });
  }

  async function executeWorkbenchCommand(command) {
    if (!command) return;
    if (command.id === "palette.open") {
      dispatch({ type: "workbench_command_palette_opened" });
      return;
    }
    if (command.id === "palette.close") {
      dispatch({ type: "workbench_command_palette_closed" });
      return;
    }
    if (command.id === "session.new") {
      await createSession(currentMode);
      return;
    }
    if (command.id === "thread.new") {
      await createSession(currentMode);
      return;
    }
    if (command.id === "session.refresh") {
      await loadSessions();
      return;
    }
    if (command.id === "workspace.open") {
      dispatch({ type: "set_sidebar", value: "chats" });
      window.setTimeout(() => {
        document.querySelector('[data-testid="sidebar-workspace-path-input"]')?.focus();
      }, 0);
      return;
    }
    if (command.id === "workspace.refresh") {
      await loadAppBootstrap();
      return;
    }
    if (command.id === "workspace.remove_current") {
      if (state.app.activeWorkspace?.id) {
        await removeWorkspace(state.app.activeWorkspace.id);
      }
      return;
    }
    if (command.id === "app.settings") {
      openRightPanelSurface("settings", command.label);
      return;
    }
    if (command.id === "app.diagnostics") {
      openRightPanelSurface("diagnostics", command.label);
      return;
    }
    if (command.id === "app.source_control") {
      openRightPanelSurface("source_control", command.label);
      return;
    }
    if (command.id === "app.reload") {
      await loadAppBootstrap();
      return;
    }
    if (command.id === "surface.preview") {
      openRightPanelSurface("preview", command.label);
      return;
    }
    if (command.id === "message.send") {
      await sendMessage();
      return;
    }
    if (command.id === "message.stop") {
      await cancelSession();
      return;
    }
    if (command.id === "view.toggle_right_panel") {
      dispatch({ type: "workbench_right_panel_toggled" });
      return;
    }
    if (command.id === "view.toggle_bottom_drawer") {
      dispatch({ type: "workbench_bottom_drawer_toggled" });
      return;
    }
    if (command.surface) {
      openRightPanelSurface(command.surface, command.label);
      return;
    }
    if (command.drawer) {
      if (command.drawer === "terminal") {
        await terminalController.ensureOpen();
        return;
      }
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: command.drawer });
      return;
    }
    if (command.slash) {
      await submitText(command.slash);
    }
  }

  useEffect(() => {
    function onWorkbenchKeyDown(event) {
      const command = resolveKeybinding(DEFAULT_KEYBINDINGS, eventToKey(event), {
        paletteOpen: state.workbench.commandPalette.open,
        isRunning: currentStatus === "running" || currentStatus === "waiting_user_input",
        composerFocused: document.activeElement?.dataset?.testid === "composer-input",
      });
      if (!command) return;
      event.preventDefault();
      void executeWorkbenchCommand(command);
    }
    window.addEventListener("keydown", onWorkbenchKeyDown);
    return () => window.removeEventListener("keydown", onWorkbenchKeyDown);
  }, [state.workbench.commandPalette.open, currentStatus, composerDraft, currentSessionId]);

  function logEvent(label, detail) {
    dispatch({ type: "log_event", label, detail });
  }

  const executeLoaderRequest = createLoaderRequestExecutor({
    loadAppBootstrap,
    loadActiveWorkspaceData,
    loadSessions,
    loadSession,
    loadTasks,
    loadArtifacts,
    loadPermissionContext,
    loadFileChildren,
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
      if (action.type === "user_input_request" && action.resetUserAnswer) {
        setUserAnswer("");
      }
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
  async function respondToInteraction(payload) {
    const interaction = runtimeState.currentInteraction;
    if (!interaction || !currentSessionId) return;
    dispatch({ type: "interaction_notice_clear" });
    let response;
    try {
      response = await fetchJson(
        `/api/sessions/${encodeURIComponent(currentSessionId)}/interactions/${encodeURIComponent(interaction.interaction_id)}/respond`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload || {}),
        },
      );
    } catch (error) {
      if ((error?.status === 409 || error?.status === 410) && currentSessionId) {
        await loadSession(currentSessionId);
        dispatch({
          type: "interaction_notice_set",
          notice: {
            kind: error.status === 410 ? "expired" : "conflict",
            detail: error.detail || "",
          },
        });
        logEvent("interaction_response", error.detail || `HTTP ${error.status}`);
        return;
      }
      throw error;
    }
    if (response?.snapshot) {
      dispatch({
        type: "session_snapshot",
        snapshot: normalizeSessionPayload(response.snapshot),
      });
    } else {
      await loadSession(currentSessionId);
    }
    updateSessionTransport((current) =>
      appendSessionTransportEvent(current, {
        session_id: currentSessionId,
        event_id: makeEventId("evt"),
        seq: current.lastAppliedSeq + 1,
        created_at: new Date().toISOString(),
        event_kind: "interaction.resolved",
        payload: {
          interaction_id: interaction.interaction_id,
          kind: interaction.kind,
          answer: payload?.answer || "",
          selected_option_text: payload?.selected_option_text || "",
          decision: payload?.decision,
        },
      }),
    );
    if (interaction.kind === "permission") {
      dispatch({ type: "permission_cleared" });
      if (payload?.decision && payload?.remember) {
        loadPermissionContext(currentSessionId);
      }
      logEvent("interaction_response", payload?.decision ? "approved" : "denied");
      return;
    }
    dispatch({
      type: "user_input_answered",
      requestId: interaction.interaction_id,
      answerText: payload?.selected_option_text || payload?.answer || userAnswer.trim(),
    });
    setUserAnswer("");
    logEvent("interaction_response", (payload?.answer || payload?.selected_option_text || "").slice(0, 40));
  }

  const appHomeModel = useMemo(
    () => buildAppHomeModel({
      app: state.app,
      sessions: threadSessions,
      currentSessionId,
      defaultMode: DEFAULT_MODE,
      threadLifecycleCapabilities: state.app.capabilities?.threadLifecycle || {},
    }),
    [currentSessionId, state.app, threadSessions],
  );
  const branchToolbarModel = useMemo(
    () =>
      buildBranchToolbarModel({
        activeWorkspace: state.app.activeWorkspace,
        sourceControl: state.sourceControl,
      }),
    [state.app.activeWorkspace, state.sourceControl],
  );

  const rightPanelSurfaces = state.workbench.rightPanel.surfaces || [];
  const activeRightPanelSurface =
    rightPanelSurfaces.find((surface) => surface.id === state.workbench.rightPanel.activeSurfaceId) || null;

  async function openPreviewUrl(url) {
    const sessionId = readActiveThreadId(stateRef.current);
    if (!sessionId) {
      dispatch({ type: "interaction_notice_set", notice: "Open a session before using preview." });
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
      dispatch({ type: "set_inspector", value: "preview" });
      return result;
    } catch (error) {
      dispatch({
        type: "interaction_notice_set",
        notice: error instanceof Error ? error.message : "Preview failed",
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
        notice: error instanceof Error ? error.message : "Preview refresh failed",
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
        notice: error instanceof Error ? error.message : "Open preview failed",
      });
      throw error;
    }
  }

  const inspectorProps = {
    tasks: state.tasks,
    artifacts: state.artifacts,
    plan: state.plan,
    review: state.review,
    recipes: state.recipes,
    timeline: runtimeState.timelineItems,
    currentInteraction: runtimeState.currentInteraction,
    interactionNotice,
    permissionContext: state.permissionContext,
    preview: state.preview,
    diffSurface: state.diffSurface,
    sourceControl: state.sourceControl,
    snapshot: state.snapshot,
    appShell: state.app,
    userAnswer,
    runOutput: state.runOutput,
    onTabChange: (v) => {
      dispatch({ type: "set_inspector", value: v });
      openRightPanelSurface(v);
    },
    onOpenArtifact: openArtifact,
    onOpenReviewEvidence: openReviewEvidence,
    onRunRecipe: runRecipe,
    onFocusDiffFile: (filePath) => dispatch({ type: "diff_file_focused", filePath }),
    onRefreshSourceControl: () => loadSourceControlStatus(true),
    onSelectSourceControlFile: openSourceControlFile,
    onAppSettingsChange: (patch) => dispatch({ type: "app_shell_settings_changed", patch }),
    onUserAnswerChange: setUserAnswer,
    onRespondInteraction: respondToInteraction,
  };

  const RESIZE_RIGHT = 1;   // sidebar: drag right = expand
  const RESIZE_LEFT  = -1;  // inspector: drag right = shrink

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
    <LangContext.Provider value={state.lang}>
    <AppSidebarLayout
      header={
        <WorkbenchHeader
          lang={state.lang}
          currentMode={currentMode}
          currentStatus={currentStatus}
          currentSessionId={currentSessionId}
          activeWorkspace={state.app.activeWorkspace}
          turnsUsed={state.turnsUsed}
          maxTurns={state.maxTurns}
          rightPanelOpen={state.workbench.rightPanel.open}
          bottomDrawerOpen={state.workbench.bottomDrawer.open}
          onRefresh={loadSessions}
          onToggleLang={() => dispatch({ type: "set_lang", value: state.lang === "en" ? "zh" : "en" })}
          onToggleRightPanel={() => dispatch({ type: "workbench_right_panel_toggled" })}
          onToggleBottomDrawer={() => dispatch({ type: "workbench_bottom_drawer_toggled" })}
          onOpenPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
        />
      }
      sidebar={
        <Sidebar
          app={state.app}
          appHome={appHomeModel}
          currentSessionId={currentSessionId}
          currentMode={currentMode}
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
              toolCatalog={state.toolCatalog}
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
              value={composerDraft}
              onChange={(v) => dispatch({ type: "set_composer", value: v })}
              onSend={sendMessage}
              onStop={cancelSession}
              isRunning={currentStatus === "running" || currentStatus === "waiting_user_input"}
              currentMode={currentMode}
              commandHints={SLASH_COMMAND_HINTS}
              commands={composerCommands}
              fileTree={state.fileTree}
              onOpenCommandPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
              interaction={runtimeState.currentInteraction}
              interactionNotice={interactionNotice}
              answerValue={userAnswer}
              onAnswerChange={setUserAnswer}
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
            onChange={(value) => dispatch({ type: "workspace_path_changed", value })}
            onOpen={openWorkspace}
            onActivate={activateWorkspace}
          />
        )
      }
      rightPanel={
        <RightPanelTabs
          surfaces={rightPanelSurfaces}
          activeSurfaceId={state.workbench.rightPanel.activeSurfaceId}
          onActivateSurface={(surface) => {
            dispatch({
              type: "workbench_surface_activated",
              placement: "right",
              surfaceId: surface.id,
              kind: surface.kind,
            });
            dispatch({ type: "set_inspector", value: surface.kind });
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
            inspectorProps={inspectorProps}
            filePreviewsByPath={state.filePreviewsByPath}
            projectName={state.app.activeWorkspace?.label || ""}
            fileTree={state.fileTree}
            treeHeight={treeHeight}
            onOpenFile={openFile}
            onOpenFilesSurface={() => openRightPanelSurface("files")}
            onLoadFileChildren={loadFileChildren}
            terminal={state.terminal}
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
            onPreviewOpenUrl={openPreviewUrl}
            onPreviewRefresh={refreshPreview}
            onPreviewOpenExternal={openPreviewInSystemBrowser}
          />
        </RightPanelTabs>
      }
      bottomDrawer={
        <BottomDrawer
          activeKind={state.workbench.bottomDrawer.activeKind}
          runOutput={state.runOutput}
          terminationReason={state.terminationDisplayReason || state.terminationReason}
          terminationMessage={state.terminationMessage}
          terminal={state.terminal}
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
      onResizeRightPanel={(e) => startResize(e, "--inspector-w-raw", RESIZE_LEFT)}
    />
    <CommandPalette
      open={state.workbench.commandPalette.open}
      query={state.workbench.commandPalette.query}
      commands={paletteCommands}
      sessions={threadSessions}
      currentSessionId={currentSessionId}
      workspaces={state.app.workspaces}
      activeWorkspaceId={activeWorkspaceId}
      keybindings={DEFAULT_KEYBINDINGS}
      onQueryChange={(query) => dispatch({ type: "workbench_command_palette_query_changed", query })}
      onClose={() => dispatch({ type: "workbench_command_palette_closed" })}
      onSelect={(command) => {
        dispatch({ type: "workbench_command_palette_closed" });
        void executeWorkbenchCommand(commandById(command.id));
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
    </LangContext.Provider>
  );
}

export default App;
