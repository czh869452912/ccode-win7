import React, { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { initialState, reducer } from "./store.js";
import {
  createTreeNode,
  makeEventId,
  normalizeSessionPayload,
  timelineFromEvents,
} from "./state-helpers.js";
import { LangContext } from "./LangContext.js";
import { t } from "./strings.js";
import Sidebar from "./components/Sidebar.jsx";
import Timeline from "./components/Timeline.jsx";
import Inspector from "./components/Inspector.jsx";
import Composer from "./components/Composer.jsx";
import PermissionModal from "./components/PermissionModal.jsx";

const MODES = ["explore", "spec", "code", "debug", "verify"];

function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [treeHeight, setTreeHeight] = useState(640);
  const [userAnswer, setUserAnswer] = useState("");
  const wsRef = useRef(null);
  const timelineRef = useRef(null);
  const wsRetryRef = useRef(0);
  const isAtBottomRef = useRef(true);

  const currentMode = state.snapshot?.current_mode || state.requestedMode;
  const currentStatus = state.snapshot?.status || "idle";

  // resize handler for file tree
  useEffect(() => {
    const update = () => setTreeHeight(Math.max(window.innerHeight - 180, 360));
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  // initial data load
  useEffect(() => {
    loadSessions();
    loadArtifacts();
    loadTodos("");
    loadFileChildren(".");
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
  }, [state.timeline, state.thinkingActive, state.permission, state.userInput]);

  function handleTimelineScroll() {
    const el = timelineRef.current;
    if (!el) return;
    isAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  // ── API helpers ────────────────────────────────────────────────────

  async function fetchJson(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function loadSessions() {
    const payload = await fetchJson("/api/sessions");
    dispatch({ type: "sessions_loaded", sessions: payload.sessions || [] });
  }

  async function loadSession(sessionId) {
    const [snapshot, timelinePayload] = await Promise.all([
      fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}`),
      fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/timeline`),
    ]);
    dispatch({
      type: "session_activated",
      sessionId,
      snapshot,
      timeline: timelineFromEvents(timelinePayload.events || []),
    });
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

  async function createSession(mode) {
    const payload = await fetchJson(`/api/sessions?mode=${encodeURIComponent(mode)}`, {
      method: "POST",
    });
    const snapshot = normalizeSessionPayload(payload);
    dispatch({ type: "session_activated", sessionId: snapshot.session_id, snapshot, timeline: [] });
    await Promise.all([loadSessions(), loadTodos(snapshot.session_id)]);
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

  async function sendMessage() {
    const text = state.composer.trim();
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

  // ── WebSocket ──────────────────────────────────────────────────────

  function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws`);
    wsRef.current = socket;
    socket.onopen = () => {
      dispatch({ type: "set_connection", value: "connected" });
      wsRetryRef.current = 0;
    };
    socket.onclose = () => {
      dispatch({ type: "set_connection", value: "disconnected" });
      const delay = Math.min(1500 * Math.pow(2, wsRetryRef.current), 30000);
      wsRetryRef.current += 1;
      window.setTimeout(connectWebSocket, delay);
    };
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      startTransition(() => handleSocketMessage(message.type, message.data || {}));
    };
  }

  function logEvent(label, detail) {
    dispatch({ type: "log_event", label, detail });
  }

  function handleSocketMessage(type, data) {
    if (type === "session_status") {
      const snap = data.session_snapshot || data;
      dispatch({ type: "session_snapshot", snapshot: normalizeSessionPayload(snap) });
      if (snap.session_id) loadSessions();
      logEvent("session_status", snap.status || "");
      return;
    }
    if (type === "stream_delta") {
      dispatch({ type: "assistant_delta", text: data.text || "" });
      return;
    }
    if (type === "reasoning_delta") {
      dispatch({ type: "reasoning_delta", text: data.text || "" });
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
        arguments: data.arguments || {},
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
      });
      logEvent(
        `tool done: ${data.call_id || "?"}`,
        data.success ? "success" : `error: ${data.error || ""}`,
      );
      return;
    }
    if (type === "permission_request") {
      dispatch({ type: "permission_request", permission: data });
      logEvent("permission_request", data.reason || "");
      return;
    }
    if (type === "user_input_request") {
      setUserAnswer("");
      dispatch({ type: "user_input_request", request: data });
      logEvent("user_input_request", data.question || "");
      return;
    }
    if (type === "turn_end") {
      dispatch({
        type: "turn_ended",
        terminationReason: data.termination_reason || "",
        turnsUsed: data.turns_used || 0,
        maxTurns: data.max_turns || 8,
      });
      logEvent("turn_end", `reason=${data.termination_reason} turns=${data.turns_used}`);
      return;
    }
    if (type === "turn_start") {
      logEvent("turn_start", data.turn_id || "");
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
    if (type === "message" && data.type === "ERROR") {
      dispatch({
        type: "append_timeline_item",
        item: {
          id: makeEventId("error"),
          kind: "system",
          tone: "error",
          content: data.content || "Error",
        },
      });
      logEvent("error", data.content || "");
    }
  }

  function sendPermissionResponse(approved) {
    if (!wsRef.current || !state.permission) return;
    wsRef.current.send(
      JSON.stringify({
        type: "permission_response",
        permission_id: state.permission.permission_id,
        approved,
      }),
    );
    dispatch({ type: "permission_cleared" });
    logEvent("permission_response", approved ? "approved" : "denied");
  }

  function sendUserInputResponse(option, overrideAnswer) {
    const request = state.userInput;
    if (!wsRef.current || !request) return;
    const answer = option?.text || overrideAnswer || userAnswer.trim();
    if (!answer) return;
    wsRef.current.send(
      JSON.stringify({
        type: "user_input_response",
        request_id: request.request_id,
        answer,
        selected_index: option?.index || null,
        selected_mode: option?.mode || "",
        selected_option_text: option?.text || "",
      }),
    );
    dispatch({
      type: "user_input_answered",
      requestId: request.request_id,
      answerText: option?.text || overrideAnswer || userAnswer.trim(),
    });
    setUserAnswer("");
    logEvent("user_input_response", answer.slice(0, 40));
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

  return (
    <LangContext.Provider value={state.lang}>
    <div className={`shell${state.inspectorOpen ? "" : " inspector-closed"}`}>
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

      <main className="chat-shell">
        <header className="header">
          <div className="header-group">
            <div className={`badge mode mode-${currentMode}`}>{currentMode}</div>
            <div className={`badge status status-${currentStatus}`}>{currentStatus}</div>
            <div className="status-copy">{state.connectionState}</div>
          </div>
          <div className="header-group">
            <select value={currentMode} onChange={(e) => setMode(e.target.value)}>
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <button className="ghost" onClick={loadSessions} aria-label={t("header.refresh", state.lang)}>
              {t("header.refresh", state.lang)}
            </button>
            <button
              className="ghost lang-toggle"
              onClick={() => dispatch({ type: "set_lang", value: state.lang === "en" ? "zh" : "en" })}
              aria-label="Toggle language"
              title="Toggle language"
            >
              {t("lang.toggle", state.lang)}
            </button>
            <button
              className={`ghost inspector-toggle${state.inspectorOpen ? " active" : ""}`}
              onClick={() => dispatch({ type: "toggle_inspector" })}
              title={t("header.toggleInspector", state.lang)}
              aria-pressed={state.inspectorOpen}
              aria-label={t("header.toggleInspector", state.lang)}
            >
              ⊞
            </button>
          </div>
        </header>

        <Timeline
          ref={timelineRef}
          timeline={state.timeline}
          thinkingActive={state.thinkingActive}
          streamingReasoningId={state.streamingReasoningId}
          terminationReason={state.terminationReason}
          turnsUsed={state.turnsUsed}
          maxTurns={state.maxTurns}
          userAnswer={userAnswer}
          onUserAnswerChange={setUserAnswer}
          onSubmitUserInput={sendUserInputResponse}
          onScroll={handleTimelineScroll}
        />

        <Composer
          value={state.composer}
          onChange={(v) => dispatch({ type: "set_composer", value: v })}
          onSend={sendMessage}
          onStop={cancelSession}
          isRunning={currentStatus === "running" || currentStatus === "waiting_user_input"}
        />
      </main>

      {state.inspectorOpen ? (
        <Inspector
          inspectorTab={state.inspectorTab}
          todos={state.todos}
          artifacts={state.artifacts}
          preview={state.preview}
          userInput={state.userInput}
          userAnswer={userAnswer}
          eventLog={state.eventLog}
          onTabChange={(v) => dispatch({ type: "set_inspector", value: v })}
          onOpenArtifact={openArtifact}
          onUserAnswerChange={setUserAnswer}
          onSubmitUserInput={sendUserInputResponse}
        />
      ) : null}

      <PermissionModal
        permission={state.permission}
        onApprove={() => sendPermissionResponse(true)}
        onDeny={() => sendPermissionResponse(false)}
      />
    </div>
    </LangContext.Provider>
  );
}

export default App;
