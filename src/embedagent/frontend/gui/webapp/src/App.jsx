import React, { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { DEFAULT_MODE, initialState, reducer } from "./store.js";
import {
  createTreeNode,
  makeEventId,
  normalizeSessionPayload,
  timelineFromTurns,
} from "./state-helpers.js";
import { appendSessionEvent, capRetryAttempt, createSessionEventLog } from "./session-runtime/event-log.js";
import { createDiffSurfaceState } from "./session-runtime/diff-model.js";
import { buildAppHomeModel } from "./session-runtime/app-home-model.js";
import { projectSessionRuntime } from "./session-runtime/projector.js";
import { shouldReconnectSocket } from "./session-runtime/websocket-lifecycle.js";
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
import { commandById } from "./workbench/commands.js";
import { DEFAULT_KEYBINDINGS, eventToKey, resolveKeybinding } from "./workbench/keybindings.js";

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
  const [state, dispatch] = useReducer(reducer, initialState);
  const treeHeight = 640;
  const [userAnswer, setUserAnswer] = useState("");
  const [sessionEventLog, setSessionEventLog] = useState(() => createSessionEventLog());
  const wsRef = useRef(null);
  const wsTokenRef = useRef(0);
  const wsClosingRef = useRef(false);
  const timelineRef = useRef(null);
  const wsRetryRef = useRef(0);
  const isAtBottomRef = useRef(true);
  const currentSessionIdRef = useRef("");
  const sessionEventLogRef = useRef(sessionEventLog);

  const currentMode = state.snapshot?.current_mode || state.requestedMode;
  const currentStatus = state.snapshot?.status || "idle";
  const runtimeState = useMemo(
    () =>
      projectSessionRuntime({
        snapshot: state.snapshot,
        eventLog: sessionEventLog,
        bootstrapTimeline: state.timeline,
        defaultMode: DEFAULT_MODE,
        activeTurnId: state.activeTurnId,
        thinkingActive: state.thinkingActive,
      }),
    [sessionEventLog, state.activeTurnId, state.snapshot, state.thinkingActive, state.timeline],
  );
  const interactionNotice = state.interactionNotice || runtimeState.interactionNotice;

  useEffect(() => {
    currentSessionIdRef.current = state.currentSessionId || "";
  }, [state.currentSessionId]);

  useEffect(() => {
    sessionEventLogRef.current = sessionEventLog;
  }, [sessionEventLog]);

  function replaceSessionEventLog(nextLog) {
    sessionEventLogRef.current = nextLog;
    setSessionEventLog(nextLog);
    return nextLog;
  }

  function updateSessionEventLog(updater) {
    const nextLog = updater(sessionEventLogRef.current);
    sessionEventLogRef.current = nextLog;
    setSessionEventLog(nextLog);
    return nextLog;
  }

  function createRuntimeEventLog(snapshot = null) {
    const readyState = wsRef.current?.readyState;
    const connectionState =
      readyState === WebSocket.OPEN
        ? "connected"
        : readyState === WebSocket.CLOSED
          ? "disconnected"
          : "connecting";
    return createSessionEventLog({
      connectionState,
      replayState: snapshot?.timeline_replay_status || "healthy",
    });
  }

  // initial app/workspace data load
  useEffect(() => {
    loadAppBootstrap();
  }, []);

  // websocket lifecycle
  useEffect(() => {
    connectWebSocket();
    return () => {
      wsClosingRef.current = true;
      wsRef.current?.close();
      wsRef.current = null;
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
  }, [currentStatus, state.currentSessionId]);

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

  async function loadActiveWorkspaceData(sessionId = state.currentSessionId || "", assumeWorkspace = state.app.hasActiveWorkspace) {
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
    const payload = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/bootstrap`);
    const snapshot = normalizeSessionPayload(payload.snapshot || {});
    const history = payload.history || {};
    dispatch({
      type: "session_activated",
      sessionId,
      snapshot,
      timeline: timelineFromTurns(history.turns || [], [], {
        projectionSource: history.history_source || "",
      }),
      historyIntegrity: history.integrity || null,
    });
    replaceSessionEventLog(createRuntimeEventLog(snapshot));
    dispatch({ type: "plan_loaded", plan: payload.plan || null });
    dispatch({ type: "permission_context_loaded", context: payload.permission_context || null });
    try {
      const terminals = await listTerminals(sessionId);
      dispatch({ type: "terminal_summaries_loaded", terminals: terminals.terminals || [] });
    } catch (_) {
      dispatch({ type: "terminal_summaries_loaded", terminals: [] });
    }
    await Promise.all([loadTasks(sessionId), loadArtifacts()]);
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

  function loadTimelineFixture() {
    dispatch({
      type: "visual_timeline_fixture_loaded",
      sessionId: "visual-debug-timeline",
      inspectorTab: "tasks",
      timeline: [
        {
          id: "visual-user-1",
          kind: "user",
          content: "Review parser recovery and show the work.",
          turnId: "visual-turn-1",
        },
        {
          id: "visual-compact-1",
          kind: "compact",
          content: "Earlier setup turns were compacted.",
          summarizedTurns: 5,
          recentTurns: 2,
          approxTokensAfter: 3600,
          turnId: "visual-turn-1",
        },
        {
          id: "visual-reasoning-1",
          kind: "reasoning",
          content: "Inspect the parser recovery path, then verify the changed diagnostic flow.",
          streaming: false,
          turnId: "visual-turn-1",
          stepId: "visual-step-1",
          stepIndex: 1,
        },
        {
          id: "visual-read-1",
          kind: "tool",
          toolName: "read_file",
          label: "Read File",
          status: "success",
          arguments: { path: "src/parser.c" },
          data: { summary: "Read parser entry point." },
          turnId: "visual-turn-1",
          stepId: "visual-step-1",
          stepIndex: 1,
        },
        {
          id: "visual-edit-1",
          kind: "tool",
          toolName: "edit_file",
          label: "Edit File",
          status: "success",
          arguments: { path: "src/parser.c" },
          data: {
            path: "src/parser.c",
            diff_preview: "--- a/src/parser.c\n+++ b/src/parser.c\n@@ -1 +1,2 @@\n-int parse(void) { return 0; }\n+int parse(void) { return 1; }\n+int parse_extra(void) { return 2; }\n",
          },
          turnId: "visual-turn-1",
          stepId: "visual-step-1",
          stepIndex: 1,
        },
        {
          id: "visual-review-result",
          kind: "command_result",
          commandName: "review",
          success: false,
          content: "Review found one follow-up item.",
          data: {
            review: {
              findings: [
                {
                  id: "visual-finding-1",
                  severity: "medium",
                  priority: 2,
                  title: "Add EOF recovery fixture",
                  body: "The parser recovery path is not covered by a fixture yet.",
                  file: "tests/parser_recovery_test.c",
                  line: 18,
                },
              ],
              residual_risks: ["Visual fixture only checks rendering, not parser behavior."],
            },
          },
          turnId: "visual-turn-1",
        },
        {
          id: "visual-assistant-1",
          kind: "assistant",
          content: "Parser recovery was updated and review found one fixture follow-up.",
          turnId: "visual-turn-1",
          stepId: "visual-step-1",
          stepIndex: 1,
        },
        {
          id: "visual-user-2",
          kind: "user",
          content: "Think through the next verification step.",
          turnId: "visual-turn-2",
        },
      ],
      snapshot: {
        session_id: "visual-debug-timeline",
        status: "running",
        current_mode: state.requestedMode || DEFAULT_MODE,
        pending_interaction_valid: false,
      },
      activeTurnId: "visual-turn-2",
      activeStepId: "visual-step-2",
      activeStepIndex: 1,
      thinkingActive: true,
    });
  }

  function loadInteractionFixture(kind = "permission") {
    const permission = kind === "permission"
      ? {
          interaction_id: "visual-permission-1",
          kind: "permission",
          tool_name: "edit_file",
          category: "workspace_write",
          reason: "Allow editing src/parser.c",
          details: { path: "src/parser.c" },
          turn_id: "visual-turn-1",
          step_id: "visual-step-2",
          step_index: 2,
        }
      : null;
    const userInput = kind === "user_input"
      ? {
          interaction_id: "visual-input-1",
          request_id: "visual-input-1",
          kind: "user_input",
          tool_name: "ask_user",
          question: "Which parser behavior should be preserved?",
          options: [
            { index: 1, text: "Keep strict parsing" },
            { index: 2, text: "Accept empty input" },
          ],
          turn_id: "visual-turn-1",
          step_id: "visual-step-2",
          step_index: 2,
        }
      : null;
    dispatch({
      type: "visual_interaction_fixture_loaded",
      sessionId: "visual-debug-interaction",
      permission,
      userInput,
    });
  }

  function loadThreadLifecycleFixture() {
    dispatch({
      type: "visual_thread_lifecycle_fixture_loaded",
      sessionId: "visual-thread-active",
      sessions: [
        {
          session_id: "visual-thread-active",
          user_goal: "Fix parser recovery",
          current_mode: "build",
          updated_at: "2026-06-16T09:30:00Z",
        },
        {
          session_id: "visual-thread-spec",
          summary_text: "Plan tokenizer cleanup",
          current_mode: "spec",
          updated_at: "2026-06-15T17:10:00Z",
        },
        {
          session_id: "visual-thread-verify",
          user_goal: "Verify offline bundle smoke",
          current_mode: "verify",
          updated_at: "2026-06-14T08:00:00Z",
        },
      ],
    });
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search || "");
    if (params.get("visual_debug") !== "1") return undefined;
    window.__EMBEDAGENT_VISUAL_DEBUG__ = {
      openDiffFixture({ title = "Visual Debug Diff", diff = "", filePath = "" } = {}) {
        openDiffSurface({ title, diff, filePath });
      },
      loadTimelineFixture,
      loadInteractionFixture,
      loadThreadLifecycleFixture,
    };
    return () => {
      if (window.__EMBEDAGENT_VISUAL_DEBUG__) {
        delete window.__EMBEDAGENT_VISUAL_DEBUG__;
      }
    };
  }, [runtimeState.timelineItems]);

  async function createSession(mode) {
    const payload = await fetchJson(`/api/sessions?mode=${encodeURIComponent(mode)}`, {
      method: "POST",
    });
    const snapshot = normalizeSessionPayload(payload);
    dispatch({ type: "session_activated", sessionId: snapshot.session_id, snapshot, timeline: [] });
    replaceSessionEventLog(createRuntimeEventLog(snapshot));
    await Promise.all([loadSessions(), loadTasks(snapshot.session_id), loadPermissionContext(snapshot.session_id)]);
    return snapshot.session_id;
  }

  async function renameThread(sessionId) {
    const current = (state.sessions || []).find((item) => item.session_id === sessionId) || {};
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
    if (!state.currentSessionId) return;
    await fetchJson(`/api/sessions/${encodeURIComponent(state.currentSessionId)}/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    await loadSession(state.currentSessionId);
  }

  async function cancelSession() {
    if (!state.currentSessionId) return;
    dispatch({ type: "stream_completed" });
    await fetchJson(`/api/sessions/${encodeURIComponent(state.currentSessionId)}/cancel`, {
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
    let sessionId = state.currentSessionId;
    if (!sessionId) sessionId = await createSession(currentMode);
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  }

  async function sendMessage() {
    await submitText(state.composer);
  }

  async function runRecipe(recipeId, options = {}) {
    const target = (options.target || "").trim();
    const profile = (options.profile || "").trim();
    const parts = ["/run", recipeId];
    if (target) parts.push(target);
    if (profile) parts.push(profile);
    await submitText(parts.join(" "));
  }

  async function ensureTerminalOpen(preferredId = "") {
    if (!state.currentSessionId) {
      dispatch({ type: "interaction_notice_set", notice: "Open a session before using the terminal." });
      return;
    }
    const terminalId =
      preferredId || state.terminal.activeTerminalId || nextTerminalId(state.terminal.terminalIds);
    try {
      const payload = await openTerminal(state.currentSessionId, terminalId, { cols: 100, rows: 30 });
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      dispatch({ type: "terminal_active_set", terminalId });
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: "terminal" });
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal failed to open." });
    }
  }

  async function openTerminalSession(terminalId) {
    if (!state.currentSessionId) {
      dispatch({ type: "interaction_notice_set", notice: "Open a session before using the terminal." });
      return null;
    }
    const targetTerminalId = String(terminalId || nextTerminalId(state.terminal.terminalIds));
    try {
      const payload = await openTerminal(state.currentSessionId, targetTerminalId, { cols: 100, rows: 30 });
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      return targetTerminalId;
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal failed to open." });
      return null;
    }
  }

  async function refreshTerminals() {
    if (!state.currentSessionId) return;
    try {
      const payload = await listTerminals(state.currentSessionId);
      dispatch({ type: "terminal_summaries_loaded", terminals: payload.terminals || [] });
    } catch (_) {
      return;
    }
  }

  async function sendTerminalInput(text) {
    await sendTerminalInputTo(state.terminal.activeTerminalId, text);
  }

  async function sendTerminalInputTo(terminalId, text) {
    const targetTerminalId = String(terminalId || "");
    if (!state.currentSessionId || !targetTerminalId) return;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      await writeTerminal(state.currentSessionId, targetTerminalId, text);
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal write failed." });
    }
  }

  async function clearActiveTerminal() {
    await clearTerminalById(state.terminal.activeTerminalId);
  }

  async function clearTerminalById(terminalId) {
    const targetTerminalId = String(terminalId || "");
    if (!state.currentSessionId || !targetTerminalId) return;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      const payload = await clearTerminal(state.currentSessionId, targetTerminalId);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal clear failed." });
    }
  }

  async function restartActiveTerminal() {
    await restartTerminalById(state.terminal.activeTerminalId);
  }

  async function restartTerminalById(terminalId) {
    const targetTerminalId = String(terminalId || "");
    if (!state.currentSessionId || !targetTerminalId) return;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      const payload = await restartTerminal(state.currentSessionId, targetTerminalId, { cols: 100, rows: 30 });
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal restart failed." });
    }
  }

  async function closeActiveTerminal() {
    const terminalId = state.terminal.activeTerminalId;
    if (!state.currentSessionId || !terminalId) return;
    try {
      await closeTerminal(state.currentSessionId, terminalId);
      dispatch({
        type: "terminal_event",
        event: { type: "closed", session_id: state.currentSessionId, terminal_id: terminalId },
      });
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal close failed." });
    }
  }

  async function selectBottomDrawerKind(kind) {
    if (kind === "terminal") {
      await ensureTerminalOpen();
      return;
    }
    dispatch({ type: "workbench_surface_activated", placement: "bottom", kind });
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

  function allKnownTerminalIds() {
    const panelIds = (state.workbench.rightPanel.surfaces || [])
      .filter((surface) => surface.kind === "terminal")
      .flatMap((surface) => surface.terminalIds || [surface.terminalId].filter(Boolean));
    return Array.from(new Set([...(state.terminal.terminalIds || []), ...panelIds]));
  }

  async function openRightPanelTerminalSurface(preferredId = "") {
    const terminalId = String(preferredId || nextTerminalId(allKnownTerminalIds()));
    const openedTerminalId = await openTerminalSession(terminalId);
    if (!openedTerminalId) return;
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: "terminal",
      title: "Terminal",
      resourceId: openedTerminalId,
      terminalId: openedTerminalId,
      terminalIds: [openedTerminalId],
      activeTerminalId: openedTerminalId,
    });
    dispatch({ type: "set_inspector", value: "terminal" });
  }

  async function splitRightPanelTerminalSurface(surface, splitDirection = "horizontal") {
    if (!surface || surface.kind !== "terminal") return;
    const terminalId = nextTerminalId(allKnownTerminalIds());
    const openedTerminalId = await openTerminalSession(terminalId);
    if (!openedTerminalId) return;
    dispatch({
      type: "workbench_terminal_surface_split",
      placement: "right",
      surfaceId: surface.id,
      terminalId: openedTerminalId,
      splitDirection,
    });
  }

  function activateRightPanelTerminalPane(surface, terminalId) {
    if (!surface || surface.kind !== "terminal") return;
    dispatch({
      type: "workbench_terminal_surface_terminal_activated",
      placement: "right",
      surfaceId: surface.id,
      terminalId,
    });
    dispatch({ type: "terminal_active_set", terminalId });
  }

  async function closeRightPanelTerminalPane(surface, terminalId) {
    if (!surface || surface.kind !== "terminal") return;
    const targetTerminalId = String(terminalId || "");
    if (!targetTerminalId) return;
    if (!state.currentSessionId) {
      dispatch({ type: "interaction_notice_set", notice: "Open a session before using the terminal." });
      return;
    }
    try {
      await closeTerminal(state.currentSessionId, targetTerminalId);
      dispatch({
        type: "terminal_event",
        event: { type: "closed", session_id: state.currentSessionId, terminal_id: targetTerminalId },
      });
      dispatch({
        type: "workbench_terminal_surface_terminal_closed",
        placement: "right",
        surfaceId: surface.id,
        terminalId: targetTerminalId,
      });
    } catch (error) {
      dispatch({ type: "interaction_notice_set", notice: error.message || "Terminal close failed." });
    }
  }

  function openRightPanelSurface(kind, title = "") {
    const surfaceKind = String(kind || "");
    if (surfaceKind === "file") return;
    if (surfaceKind === "terminal") {
      void openRightPanelTerminalSurface();
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
      dispatch({ type: "set_inspector", value: "settings" });
      dispatch({ type: "workbench_surface_activated", placement: "right", kind: "settings" });
      return;
    }
    if (command.id === "app.diagnostics") {
      dispatch({ type: "set_inspector", value: "diagnostics" });
      dispatch({ type: "workbench_surface_activated", placement: "right", kind: "diagnostics" });
      return;
    }
    if (command.id === "app.reload") {
      await loadAppBootstrap();
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
        await ensureTerminalOpen();
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
  }, [state.workbench.commandPalette.open, currentStatus, state.composer, state.currentSessionId]);

  async function recoverSessionReplay(sessionId, logState = sessionEventLogRef.current) {
    if (!sessionId) return;
    try {
      const replay = await fetchJson(
        `/api/sessions/${encodeURIComponent(sessionId)}/events?after_seq=${encodeURIComponent(logState.lastAppliedSeq || 0)}`,
      );
      if (replay?.status === "replay") {
        updateSessionEventLog((current) => {
          let next = {
            ...current,
            connectionState: "connected",
            replayState: "healthy",
          };
          const items = Array.isArray(replay.events) ? replay.events : [];
          for (const item of items) {
            next = appendSessionEvent(next, item);
          }
          return {
            ...next,
            connectionState: "connected",
            replayState: next.replayState === "replay_needed" ? "replay_needed" : "healthy",
          };
        });
        if (sessionEventLogRef.current.replayState === "replay_needed") {
          await loadSession(sessionId);
        }
        return;
      }
      updateSessionEventLog((current) => ({
        ...current,
        connectionState: replay?.status === "degraded" ? "degraded" : "connected",
        replayState: replay?.status || "degraded",
      }));
      await loadSession(sessionId);
    } catch (_) {
      updateSessionEventLog((current) => ({
        ...current,
        connectionState: "degraded",
        replayState: "degraded",
      }));
      await loadSession(sessionId);
    }
  }

  // ── WebSocket ──────────────────────────────────────────────────────

  function connectWebSocket() {
    wsClosingRef.current = false;
    const socketToken = wsTokenRef.current + 1;
    wsTokenRef.current = socketToken;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws`);
    wsRef.current = socket;
    socket.onopen = async () => {
      dispatch({ type: "set_connection", value: "connected" });
      updateSessionEventLog((current) => ({ ...current, connectionState: "connected" }));
      wsRetryRef.current = 0;
      if (currentSessionIdRef.current && sessionEventLogRef.current.replayState !== "healthy") {
        await recoverSessionReplay(currentSessionIdRef.current, sessionEventLogRef.current);
      }
    };
    socket.onclose = () => {
      dispatch({ type: "set_connection", value: "disconnected" });
      updateSessionEventLog((current) => ({ ...current, connectionState: "disconnected" }));
      if (
        !shouldReconnectSocket({
          activeToken: wsTokenRef.current,
          socketToken,
          manualClose: wsClosingRef.current,
        })
      ) {
        return;
      }
      const nextAttempt = capRetryAttempt(wsRetryRef.current + 1);
      const delay = Math.min(1500 * Math.pow(2, Math.max(nextAttempt - 1, 0)), 30000);
      wsRetryRef.current = nextAttempt;
      window.setTimeout(connectWebSocket, delay);
    };
    socket.onerror = () => {
      dispatch({ type: "set_connection", value: "disconnected" });
      updateSessionEventLog((current) => ({
        ...current,
        connectionState: "degraded",
        replayState: current.replayState === "reload_required" ? "reload_required" : "replay_needed",
      }));
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        startTransition(() => handleSocketMessage(message.type, message.data || {}));
      } catch (_) {
        dispatch({ type: "set_connection", value: "disconnected" });
        updateSessionEventLog((current) => ({
          ...current,
          connectionState: "degraded",
          replayState: "degraded",
        }));
      }
    };
  }

  function logEvent(label, detail) {
    dispatch({ type: "log_event", label, detail });
  }

  function handleSocketMessage(type, data) {
    if (type === "workspace_changed") {
      const bootstrap = normalizeAppBootstrap(data || {});
      dispatch({ type: "workspace_switched", bootstrap });
      if (bootstrap.hasActiveWorkspace) {
        void loadActiveWorkspaceData("", true);
      } else {
        dispatch({ type: "source_control_reset" });
      }
      return;
    }
    if (type === "terminal_event") {
      dispatch({ type: "terminal_event", event: data?.event || data || {} });
      return;
    }
    if (type === "session_event") {
      const nextLog = updateSessionEventLog((current) => appendSessionEvent(current, data || {}));
      if (
        (nextLog.replayState === "replay_needed" || nextLog.replayState === "degraded") &&
        currentSessionIdRef.current
      ) {
        void recoverSessionReplay(currentSessionIdRef.current, nextLog);
      }
      if (data?.event_kind === "turn.started") {
        dispatch({
          type: "turn_started",
          turnId: data.payload?.turn_id || "",
          userText: data.payload?.user_text || "",
        });
      } else if (data?.event_kind === "transition.recorded") {
        dispatch({
          type: "turn_ended",
          terminationReason: data.payload?.termination_reason || "",
          terminationDisplayReason: data.payload?.display_reason || data.payload?.termination_reason || "",
          terminationMessage: data.payload?.message || data.payload?.error || "",
          turnsUsed: data.payload?.turns_used || 0,
          maxTurns: data.payload?.max_turns || 8,
        });
      }
      return;
    }
    if (type === "session_status") {
      const snap = data.session_snapshot || data;
      dispatch({ type: "session_snapshot", snapshot: normalizeSessionPayload(snap) });
      if (snap.timeline_replay_status && snap.timeline_replay_status !== "replay") {
        updateSessionEventLog((current) => ({
          ...current,
          replayState: snap.timeline_replay_status,
        }));
      }
      if (snap.session_id) loadSessions();
      logEvent("session_status", snap.status || "");
      return;
    }
    if (type === "stream_delta") {
      dispatch({
        type: "assistant_delta",
        text: data.text || "",
        turnId: data.turn_id || "",
        stepId: data.step_id || "",
        stepIndex: data.step_index || 0,
      });
      return;
    }
    if (type === "reasoning_delta") {
      dispatch({
        type: "reasoning_delta",
        text: data.text || "",
        turnId: data.turn_id || "",
        stepId: data.step_id || "",
        stepIndex: data.step_index || 0,
      });
      return;
    }
    if (type === "thinking_state") {
      dispatch({ type: "thinking_state", active: data.active });
      logEvent("thinking", data.active ? "started" : "stopped");
      return;
    }
    if (type === "tool_start") {
      const callId = data.call_id || makeEventId("tool");
      dispatch({
        type: "tool_started",
        callId,
        toolName: data.tool_name || "",
        label: data.tool_label || data.tool_name || "",
        arguments: data.arguments || {},
        permissionCategory: data.permission_category || "",
        supportsDiffPreview: Boolean(data.supports_diff_preview),
        progressRendererKey: data.progress_renderer_key || "",
        resultRendererKey: data.result_renderer_key || "",
        runtimeSource: data.runtime_source || "",
        resolvedToolRoots: data.resolved_tool_roots || {},
        turnId: data.turn_id || "",
        stepId: data.step_id || "",
        stepIndex: data.step_index || 0,
      });
      logEvent(`tool: ${data.tool_name || "?"}`, JSON.stringify(data.arguments || {}).slice(0, 80));
      return;
    }
    if (type === "tool_finish") {
      dispatch({
        type: "tool_finished",
        callId: data.call_id || "",
        success: Boolean(data.success),
        error: data.error || "",
        data: data.data || {},
        label: data.tool_label || data.tool_name || "",
        permissionCategory: data.permission_category || "",
        supportsDiffPreview: Boolean(data.supports_diff_preview),
        progressRendererKey: data.progress_renderer_key || "",
        resultRendererKey: data.result_renderer_key || "",
        runtimeSource: data.runtime_source || "",
        resolvedToolRoots: data.resolved_tool_roots || {},
        turnId: data.turn_id || "",
        stepId: data.step_id || "",
        stepIndex: data.step_index || 0,
      });
      logEvent(
        `tool done: ${data.call_id || "?"}`,
        data.success ? "success" : `error: ${data.error || ""}`,
      );
      const FS_TOOLS = ["write_file", "edit_file", "git_commit", "git_reset"];
      if (FS_TOOLS.includes(data.tool_name || "")) {
        loadFileChildren(".");
      }
      return;
    }
    if (type === "permission_request") {
      dispatch({
        type: "permission_request",
        permission: {
          ...data,
          turn_id: data.turn_id || "",
          step_id: data.step_id || "",
          step_index: data.step_index || 0,
        },
        inspectorTab: "interaction",
      });
      updateSessionEventLog((current) =>
        appendSessionEvent(current, {
          session_id: data.session_id || currentSessionIdRef.current || "",
          event_id: data.permission_id || makeEventId("evt"),
          seq: current.lastAppliedSeq + 1,
          created_at: new Date().toISOString(),
          event_kind: "interaction.created",
          payload: {
            interaction_id: data.permission_id || "",
            kind: "permission",
            tool_name: data.tool_name || "",
            category: data.category || "",
            reason: data.reason || "",
            details: data.details || {},
            turn_id: data.turn_id || "",
            step_id: data.step_id || "",
            step_index: data.step_index || 0,
          },
        }),
      );
      logEvent("permission_request", data.reason || "");
      return;
    }
    if (type === "user_input_request") {
      setUserAnswer("");
      dispatch({
        type: "user_input_request",
        request: {
          ...data,
          turn_id: data.turn_id || "",
          step_id: data.step_id || "",
          step_index: data.step_index || 0,
        },
      });
      updateSessionEventLog((current) =>
        appendSessionEvent(current, {
          session_id: data.session_id || currentSessionIdRef.current || "",
          event_id: data.request_id || makeEventId("evt"),
          seq: current.lastAppliedSeq + 1,
          created_at: new Date().toISOString(),
          event_kind: "interaction.created",
          payload: {
            interaction_id: data.request_id || "",
            kind: "user_input",
            tool_name: data.tool_name || "",
            question: data.question || "",
            options: data.options || [],
            turn_id: data.turn_id || "",
            step_id: data.step_id || "",
            step_index: data.step_index || 0,
          },
        }),
      );
      logEvent("user_input_request", data.question || "");
      return;
    }
    if (type === "command_result") {
      dispatch({
        type: "command_result",
        id: makeEventId("cmd"),
        commandName: data.command_name || "",
        success: Boolean(data.success),
        message: data.message || "",
        data: data.data || {},
        turnId: data.turn_id || "",
        stepId: data.step_id || "",
        stepIndex: data.step_index || 0,
      });
      if (data.command_name === "resume" && data.data?.switch_session_id) {
        loadSession(data.data.switch_session_id);
      }
      if (data.command_name === "diff" && typeof data.data?.diff === "string" && data.data.diff) {
        dispatch({
          type: "diff_surface_opened",
          diffSurface: createDiffSurfaceState({
            title: "Git Diff",
            diff: data.data.diff,
            source: "command",
            turnId: data.turn_id || "",
          }),
        });
      }
      if (data.command_name === "workspace") {
        dispatch({
          type: "preview_loaded",
          preview: {
            kind: "workspace",
            title: "Workspace",
            content: JSON.stringify(data.data || {}, null, 2),
          },
          inspectorTab: "preview",
        });
      }
      if (data.command_name === "recipes") {
        dispatch({
          type: "recipes_loaded",
          items: data.data?.items || [],
        });
        dispatch({ type: "set_inspector", value: "run" });
      }
      if (data.command_name === "run") {
        dispatch({ type: "set_inspector", value: "problems" });
      }
      if (data.command_name === "permissions") {
        dispatch({
          type: "permission_context_loaded",
          context: data.data || {},
          inspectorTab: "permissions",
        });
      }
      if (data.command_name === "review" && data.data?.review) {
        dispatch({
          type: "review_loaded",
          review: data.data.review,
          inspectorTab: "review",
        });
      }
      logEvent(`command: /${data.command_name || "?"}`, data.success ? "ok" : "error");
      return;
    }
    if (type === "session_error") {
      dispatch({
        type: "session_error",
        id: data.event_id || makeEventId("error"),
        error: data.error || "",
        turnId: data.turn_id || "",
        stepId: data.step_id || "",
        stepIndex: data.step_index || 0,
      });
      logEvent("session_error", data.error || "");
      return;
    }
    if (type === "plan_updated") {
      dispatch({
        type: "plan_loaded",
        plan: data.plan || null,
        inspectorTab: "plan",
      });
      logEvent("plan_updated", data.plan?.title || "");
      return;
    }
    if (type === "turn_end") {
      dispatch({
        type: "turn_ended",
        terminationReason: data.termination_reason || "",
        terminationDisplayReason: data.display_reason || data.termination_reason || "",
        terminationMessage: data.message || "",
        turnsUsed: data.turns_used || 0,
        maxTurns: data.max_turns || 8,
      });
      logEvent("turn_end", `reason=${data.termination_reason} turns=${data.turns_used}`);
      return;
    }
    if (type === "turn_start") {
      dispatch({
        type: "turn_started",
        turnId: data.turn_id || "",
        userText: data.user_text || "",
      });
      logEvent("turn_start", data.turn_id || "");
      return;
    }
    if (type === "step_start") {
      dispatch({
        type: "step_started",
        turnId: data.turn_id || "",
        stepId: data.step_id || "",
        stepIndex: data.step_index || 0,
      });
      logEvent("step_start", data.step_id || "");
      return;
    }
    if (type === "step_end") {
      dispatch({
        type: "step_ended",
        turnId: data.turn_id || "",
        stepId: data.step_id || "",
        stepIndex: data.step_index || 0,
        assistantText: data.assistant_text || "",
        status: data.status || "",
      });
      logEvent("step_end", data.step_id || "");
      return;
    }

    if (type === "session_finished") {
      dispatch({ type: "stream_completed" });
      if (data.session_snapshot) {
        dispatch({
          type: "session_snapshot",
          snapshot: normalizeSessionPayload(data.session_snapshot),
        });
      }
      loadSessions();
      const activeSessionId = currentSessionIdRef.current;
      if (activeSessionId) loadTasks(activeSessionId);
      logEvent("session_finished", "");
      return;
    }
    if (type === "tasks_refresh") {
      const activeSessionId = currentSessionIdRef.current;
      if (activeSessionId) loadTasks(activeSessionId);
      return;
    }
    if (type === "artifacts_refresh") {
      loadArtifacts();
      return;
    }
    if (type === "message" && data.type === "ERROR") {
      dispatch({
        type: "session_error",
        id: data.id || makeEventId("error"),
        error: data.content || "Error",
        turnId: data.metadata?.turn_id || "",
        stepId: data.metadata?.step_id || "",
        stepIndex: data.metadata?.step_index || 0,
      });
      logEvent("error", data.content || "");
      return;
    }
    if (type === "message" && data.type === "CONTEXT_COMPACTED") {
      const metadata = data.metadata || {};
      dispatch({
        type: "context_compacted",
        id: data.id || makeEventId("context"),
        content: data.content || "",
        recentTurns: metadata.recent_turns,
        summarizedTurns: metadata.summarized_turns,
        approxTokensAfter: metadata.approx_tokens_after,
        turnId: metadata.turn_id || "",
        stepId: metadata.step_id || "",
        stepIndex: metadata.step_index || 0,
      });
      logEvent("context_compacted", data.content || "");
    }
  }

  async function respondToInteraction(payload) {
    const interaction = runtimeState.currentInteraction;
    if (!interaction || !state.currentSessionId) return;
    dispatch({ type: "interaction_notice_clear" });
    let response;
    try {
      response = await fetchJson(
        `/api/sessions/${encodeURIComponent(state.currentSessionId)}/interactions/${encodeURIComponent(interaction.interaction_id)}/respond`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload || {}),
        },
      );
    } catch (error) {
      if ((error?.status === 409 || error?.status === 410) && state.currentSessionId) {
        await loadSession(state.currentSessionId);
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
      await loadSession(state.currentSessionId);
    }
    updateSessionEventLog((current) =>
      appendSessionEvent(current, {
        session_id: state.currentSessionId,
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
        loadPermissionContext(state.currentSessionId);
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
      sessions: state.sessions,
      currentSessionId: state.currentSessionId,
      defaultMode: DEFAULT_MODE,
      threadLifecycleCapabilities: state.app.capabilities?.threadLifecycle || {},
    }),
    [state.app, state.sessions, state.currentSessionId],
  );

  const rightPanelSurfaces = state.workbench.rightPanel.surfaces || [];
  const activeRightPanelSurface =
    rightPanelSurfaces.find((surface) => surface.id === state.workbench.rightPanel.activeSurfaceId) || null;
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
    eventLog: state.eventLog,
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
          currentSessionId={state.currentSessionId}
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
          sidebarTab={state.sidebarTab}
          currentSessionId={state.currentSessionId}
          fileTree={state.fileTree}
          treeHeight={treeHeight}
          currentMode={currentMode}
          workspacePathInput={state.app.workspacePathInput}
          onWorkspacePathChange={(value) => dispatch({ type: "workspace_path_changed", value })}
          onTabChange={(v) => dispatch({ type: "set_sidebar", value: v })}
          onLoadSession={loadSession}
          onCreateSession={createSession}
          onThreadLifecycleAction={handleThreadLifecycleAction}
          onOpenWorkspace={openWorkspace}
          onActivateWorkspace={activateWorkspace}
          onRemoveWorkspace={removeWorkspace}
          onOpenFile={openFile}
          onLoadFileChildren={loadFileChildren}
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
              historyIntegrity={state.historyIntegrity}
              thinkingActive={state.thinkingActive}
              streamingReasoningId={state.streamingReasoningId}
              terminationReason={state.terminationReason}
              terminationDisplayReason={state.terminationDisplayReason}
              terminationMessage={state.terminationMessage}
              turnsUsed={state.turnsUsed}
              maxTurns={state.maxTurns}
              onScroll={handleTimelineScroll}
              onOpenDiff={openDiffSurface}
            />
            <Composer
              value={state.composer}
              onChange={(v) => dispatch({ type: "set_composer", value: v })}
              onSend={sendMessage}
              onStop={cancelSession}
              isRunning={currentStatus === "running" || currentStatus === "waiting_user_input"}
              currentMode={currentMode}
              commandHints={SLASH_COMMAND_HINTS}
              onOpenCommandPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
              interaction={runtimeState.currentInteraction}
              interactionNotice={interactionNotice}
              answerValue={userAnswer}
              onAnswerChange={setUserAnswer}
              onRespondInteraction={respondToInteraction}
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
              void openTerminalSession(surface.activeTerminalId);
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
            fileTree={state.fileTree}
            treeHeight={treeHeight}
            onOpenFile={openFile}
            onLoadFileChildren={loadFileChildren}
            terminal={state.terminal}
            onTerminalNew={() => openRightPanelTerminalSurface()}
            onTerminalSplit={() => splitRightPanelTerminalSurface(activeRightPanelSurface)}
            onTerminalSplitVertical={() => splitRightPanelTerminalSurface(activeRightPanelSurface, "vertical")}
            onTerminalSelect={(terminalId) => activateRightPanelTerminalPane(activeRightPanelSurface, terminalId)}
            onTerminalSend={sendTerminalInputTo}
            onTerminalClear={clearTerminalById}
            onTerminalRestart={restartTerminalById}
            onTerminalClose={(terminalId) => closeRightPanelTerminalPane(activeRightPanelSurface, terminalId)}
          />
        </RightPanelTabs>
      }
      bottomDrawer={
        <BottomDrawer
          activeKind={state.workbench.bottomDrawer.activeKind}
          eventLog={state.eventLog}
          terminationReason={state.terminationDisplayReason || state.terminationReason}
          terminationMessage={state.terminationMessage}
          terminal={state.terminal}
          onKindSelect={(kind) => {
            void selectBottomDrawerKind(kind);
          }}
          onTerminalNew={() => ensureTerminalOpen(nextTerminalId(state.terminal.terminalIds))}
          onTerminalSelect={(terminalId) => dispatch({ type: "terminal_active_set", terminalId })}
          onTerminalSend={sendTerminalInput}
          onTerminalClear={clearActiveTerminal}
          onTerminalRestart={restartActiveTerminal}
          onTerminalClose={closeActiveTerminal}
        />
      }
      rightPanelOpen={state.workbench.rightPanel.open}
      bottomDrawerOpen={state.workbench.bottomDrawer.open}
      onResizeSidebar={(e) => startResize(e, "--sidebar-w-raw", RESIZE_RIGHT)}
      onResizeRightPanel={(e) => startResize(e, "--inspector-w-raw", RESIZE_LEFT)}
    />
    <CommandPalette
      open={state.workbench.commandPalette.open}
      query={state.workbench.commandPalette.query}
      selectedIndex={state.workbench.commandPalette.selectedIndex}
      context={{
        hasSession: Boolean(state.currentSessionId),
        hasWorkspace: Boolean(state.app.hasActiveWorkspace),
        isRunning: currentStatus === "running" || currentStatus === "waiting_user_input",
        paletteOpen: state.workbench.commandPalette.open,
      }}
      onQueryChange={(query) => dispatch({ type: "workbench_command_palette_query_changed", query })}
      onClose={() => dispatch({ type: "workbench_command_palette_closed" })}
      onSelect={(command) => {
        dispatch({ type: "workbench_command_palette_closed" });
        void executeWorkbenchCommand(commandById(command.id));
      }}
    />
    </LangContext.Provider>
  );
}

export default App;
