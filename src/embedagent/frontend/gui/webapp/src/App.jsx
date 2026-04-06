import React, { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { initialState, reducer } from "./store.js";
import {
  createTreeNode,
  makeEventId,
  normalizeSessionPayload,
  timelineFromEvents,
  timelineFromTurns,
} from "./state-helpers.js";
import { appendSessionEvent, capRetryAttempt, createSessionEventLog } from "./session-runtime/event-log.js";
import { projectSessionRuntime } from "./session-runtime/projector.js";
import { LangContext } from "./LangContext.js";
import { t } from "./strings.js";
import Sidebar from "./components/Sidebar.jsx";
import Timeline from "./components/Timeline.jsx";
import Inspector from "./components/Inspector.jsx";
import Composer from "./components/Composer.jsx";

const MODES = ["explore", "spec", "code", "debug", "verify"];
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
  "/todos",
  "/artifacts",
];

function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const treeHeight = 640;
  const [userAnswer, setUserAnswer] = useState("");
  const [sessionEventLog, setSessionEventLog] = useState(() => createSessionEventLog());
  const wsRef = useRef(null);
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
      }),
    [sessionEventLog, state.snapshot, state.timeline],
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

  // initial data load
  useEffect(() => {
    loadSessions();
    loadArtifacts();
    loadTodos("");
    loadFileChildren(".");
    loadToolCatalog();
    loadWorkspaceRecipes();
  }, []);

  // websocket lifecycle
  useEffect(() => {
    connectWebSocket();
    return () => wsRef.current?.close();
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
  }, [runtimeState.timelineView, state.thinkingActive, runtimeState.currentInteraction]);

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
      const error = new Error(payload?.detail || `HTTP ${res.status}`);
      error.status = res.status;
      error.detail = payload?.detail || "";
      throw error;
    }
    return payload;
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
    const [snapshotPayload, timelinePayload] = await Promise.all([
      fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}`),
      fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/timeline`),
    ]);
    const [planPayload, permissionPayload] = await Promise.all([
      fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/plan`).catch(() => ({ plan: null })),
      fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/permissions`).catch(() => null),
    ]);
    const snapshot = normalizeSessionPayload(snapshotPayload);
    dispatch({
      type: "session_activated",
      sessionId,
      snapshot,
      timeline:
        Array.isArray(timelinePayload.turns) && timelinePayload.turns.length > 0
          ? timelineFromTurns(
              timelinePayload.turns || [],
              timelinePayload.events || [],
              { projectionSource: timelinePayload.projection_source || "" },
            )
          : timelineFromEvents(timelinePayload.events || []),
    });
    replaceSessionEventLog(createRuntimeEventLog(snapshot));
    dispatch({ type: "plan_loaded", plan: planPayload.plan || null });
    if (permissionPayload) {
      dispatch({ type: "permission_context_loaded", context: permissionPayload });
    }
    await Promise.all([loadTodos(sessionId), loadArtifacts()]);
  }

  async function loadTodos(sessionId) {
    const payload = await fetchJson(`/api/todos?session_id=${encodeURIComponent(sessionId || "")}`);
    dispatch({ type: "todos_loaded", todos: payload.todos || [] });
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

  async function openFile(path) {
    const payload = await fetchJson(`/api/files/${encodeURIComponent(path)}`);
    dispatch({
      type: "preview_loaded",
      preview: { kind: "file", title: payload.path || path, content: payload.content || "" },
      inspectorTab: "preview",
    });
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
        type: "preview_loaded",
        preview: {
          kind: entry?.kind || "diff",
          title: entry?.title || "Review Diff",
          diff: entry.diff,
          content: "",
        },
        inspectorTab: "preview",
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

  async function createSession(mode) {
    const payload = await fetchJson(`/api/sessions?mode=${encodeURIComponent(mode)}`, {
      method: "POST",
    });
    const snapshot = normalizeSessionPayload(payload);
    dispatch({ type: "session_activated", sessionId: snapshot.session_id, snapshot, timeline: [] });
    replaceSessionEventLog(createRuntimeEventLog(snapshot));
    await Promise.all([loadSessions(), loadTodos(snapshot.session_id), loadPermissionContext(snapshot.session_id)]);
    return snapshot.session_id;
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
          session_id: data.session_id || state.currentSessionId || "",
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
          session_id: data.session_id || state.currentSessionId || "",
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
          type: "preview_loaded",
          preview: { kind: "diff", title: "Git Diff", diff: data.data.diff, content: "" },
          inspectorTab: "preview",
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
      if (state.currentSessionId) loadTodos(state.currentSessionId);
      logEvent("session_finished", "");
      return;
    }
    if (type === "todos_refresh") {
      if (state.currentSessionId) loadTodos(state.currentSessionId);
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

  const sessionCards = useMemo(
    () =>
      state.sessions.map((item) => {
        let updated = null;
        if (item.updated_at) {
          try {
            updated = new Date(item.updated_at).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            });
          } catch (_) {
            updated = item.updated_at;
          }
        }
        return {
          id: item.session_id,
          title:
            item.user_goal ||
            item.summary_text ||
            `Session ${item.session_id.slice(0, 8)}`,
          mode: item.current_mode || "code",
          updated,
        };
      }),
    [state.sessions],
  );

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
    <div className="app-shell">
      {/* ── Global Header ── */}
      <header className="app-header">
        <span className="app-logo">EmbedAgent</span>
        <span className={`mode-badge mode-${currentMode}`}>{currentMode}</span>
        <div className="header-right">
          <span className={`status-dot ${currentStatus}`} title={currentStatus} />
          <span className={`status-label ${currentStatus === "idle" ? "idle" : currentStatus === "error" ? "error" : ""}`}>
            {currentStatus}
          </span>
          {state.currentSessionId && (
            <span className="meta-text">{state.currentSessionId.slice(0, 8)}</span>
          )}
          {state.turnsUsed > 0 && (
            <span className="meta-text">turns {state.turnsUsed}/{state.maxTurns}</span>
          )}
          <button className="ghost" onClick={loadSessions} aria-label={t("header.refresh", state.lang)} data-testid="refresh-sessions">
            {t("header.refresh", state.lang)}
          </button>
          <button
            className="ghost lang-toggle"
            onClick={() => dispatch({ type: "set_lang", value: state.lang === "en" ? "zh" : "en" })}
            aria-label="Toggle language"
            data-testid="lang-toggle"
          >
            {t("lang.toggle", state.lang)}
          </button>
          <button
            className={`ghost inspector-toggle${state.inspectorOpen ? " active" : ""}`}
            onClick={() => dispatch({ type: "toggle_inspector" })}
            title={t("header.toggleInspector", state.lang)}
            aria-pressed={state.inspectorOpen}
            data-testid="inspector-toggle"
          >
            ⊞
          </button>
        </div>
      </header>

      {/* ── Workspace ── */}
      <div className="workspace">
        <Sidebar
          sidebarTab={state.sidebarTab}
          sessions={sessionCards}
          currentSessionId={state.currentSessionId}
          fileTree={state.fileTree}
          treeHeight={treeHeight}
          currentMode={currentMode}
          onTabChange={(v) => dispatch({ type: "set_sidebar", value: v })}
          onLoadSession={loadSession}
          onCreateSession={createSession}
          onOpenFile={openFile}
          onLoadFileChildren={loadFileChildren}
        />

        <div
          className="resize-handle"
          onPointerDown={(e) => startResize(e, "--sidebar-w-raw", RESIZE_RIGHT)}
          aria-hidden="true"
        />

        <main className="main-chat">
          <Timeline
            ref={timelineRef}
            timeline={runtimeState.timelineView}
            toolCatalog={state.toolCatalog}
            thinkingActive={state.thinkingActive}
            streamingReasoningId={state.streamingReasoningId}
            terminationReason={state.terminationReason}
            terminationDisplayReason={state.terminationDisplayReason}
            terminationMessage={state.terminationMessage}
            turnsUsed={state.turnsUsed}
            maxTurns={state.maxTurns}
            onScroll={handleTimelineScroll}
          />
          <Composer
            value={state.composer}
            onChange={(v) => dispatch({ type: "set_composer", value: v })}
            onSend={sendMessage}
            onStop={cancelSession}
            isRunning={currentStatus === "running" || currentStatus === "waiting_user_input"}
            currentMode={currentMode}
            commandHints={SLASH_COMMAND_HINTS}
          />
        </main>

        <div
          className="resize-handle"
          onPointerDown={(e) => startResize(e, "--inspector-w-raw", RESIZE_LEFT)}
          aria-hidden="true"
        />

        {state.inspectorOpen ? (
          <Inspector
            inspectorTab={state.inspectorTab}
            todos={state.todos}
            artifacts={state.artifacts}
            plan={state.plan}
            review={state.review}
            recipes={state.recipes}
            timeline={runtimeState.timelineItems}
            currentInteraction={runtimeState.currentInteraction}
            interactionNotice={interactionNotice}
            permissionContext={state.permissionContext}
            preview={state.preview}
            snapshot={state.snapshot}
            userAnswer={userAnswer}
            eventLog={state.eventLog}
            onTabChange={(v) => dispatch({ type: "set_inspector", value: v })}
            onOpenArtifact={openArtifact}
            onOpenReviewEvidence={openReviewEvidence}
            onRunRecipe={runRecipe}
            onUserAnswerChange={setUserAnswer}
            onRespondInteraction={respondToInteraction}
          />
        ) : (
          <div style={{ background: "var(--bg-default)", borderLeft: "1px solid var(--bg-subtle)" }} />
        )}
      </div>

    </div>
    </LangContext.Provider>
  );
}

export default App;
