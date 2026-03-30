import React, { startTransition, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { Tree } from "react-arborist";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  createTreeNode,
  injectChildren,
  makeEventId,
  normalizeSessionPayload,
  timelineFromEvents,
} from "./state-helpers.js";

const initialState = {
  sidebarTab: "chats",
  inspectorTab: "todos",
  sessions: [],
  currentSessionId: "",
  snapshot: null,
  composer: "",
  timeline: [],
  streamingAssistantId: "",
  streamingReasoningId: "",
  thinkingActive: false,
  permission: null,
  userInput: null,
  todos: [],
  artifacts: [],
  preview: null,
  fileTree: [],
  requestedMode: "code",
  connectionState: "connecting",
};

function reducer(state, action) {
  switch (action.type) {
    case "set_sidebar":
      return { ...state, sidebarTab: action.value };
    case "set_inspector":
      return { ...state, inspectorTab: action.value };
    case "set_composer":
      return { ...state, composer: action.value };
    case "set_connection":
      return { ...state, connectionState: action.value };
    case "sessions_loaded":
      return { ...state, sessions: action.sessions };
    case "session_activated":
      return {
        ...state,
        currentSessionId: action.sessionId,
        snapshot: action.snapshot,
        requestedMode: action.snapshot?.current_mode || state.requestedMode,
        timeline: action.timeline,
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
        permission: null,
        userInput: null,
      };
    case "session_snapshot": {
      const snapshot = action.snapshot;
      if (!snapshot) {
        return state;
      }
      return {
        ...state,
        currentSessionId: snapshot.session_id || state.currentSessionId,
        snapshot,
        requestedMode: snapshot.current_mode || state.requestedMode,
      };
    }
    case "local_user_message":
      return {
        ...state,
        timeline: state.timeline.concat({
          id: makeEventId("user"),
          kind: "user",
          content: action.text,
        }),
        composer: "",
      };
    case "assistant_delta": {
      let timeline = state.timeline.slice();
      let id = state.streamingAssistantId;
      if (!id) {
        id = makeEventId("assistant");
        timeline.push({ id, kind: "assistant", content: action.text, streaming: true });
      } else {
        timeline = timeline.map((item) =>
          item.id === id ? { ...item, content: `${item.content || ""}${action.text}`, streaming: true } : item,
        );
      }
      return {
        ...state,
        timeline,
        streamingAssistantId: id,
        thinkingActive: false,
      };
    }
    case "reasoning_delta": {
      let timeline = state.timeline.slice();
      let id = state.streamingReasoningId;
      if (!id) {
        id = makeEventId("thinking");
        timeline.push({ id, kind: "reasoning", content: action.text, open: true, streaming: true });
      } else {
        timeline = timeline.map((item) =>
          item.id === id ? { ...item, content: `${item.content || ""}${action.text}`, streaming: true } : item,
        );
      }
      return {
        ...state,
        timeline,
        streamingReasoningId: id,
      };
    }
    case "thinking_state": {
      const timeline = state.timeline.map((item) => {
        if (item.id === state.streamingReasoningId) {
          return { ...item, streaming: Boolean(action.active) };
        }
        if (item.id === state.streamingAssistantId) {
          return { ...item, streaming: Boolean(action.active) ? item.streaming : false };
        }
        return item;
      });
      return {
        ...state,
        thinkingActive: Boolean(action.active),
        timeline,
      };
    }
    case "tool_started":
      return {
        ...state,
        thinkingActive: false,
        timeline: state.timeline.concat({
          id: action.callId,
          kind: "tool",
          toolName: action.toolName,
          arguments: action.arguments,
          status: "running",
          data: null,
          error: "",
        }),
      };
    case "tool_finished":
      return {
        ...state,
        timeline: state.timeline.map((item) =>
          item.id === action.callId
            ? {
                ...item,
                status: action.success ? "success" : "error",
                data: action.data,
                error: action.error,
              }
            : item,
        ),
      };
    case "append_timeline_item":
      return { ...state, timeline: state.timeline.concat(action.item) };
    case "permission_request":
      return { ...state, permission: action.permission, thinkingActive: false };
    case "permission_cleared":
      return { ...state, permission: null };
    case "user_input_request":
      return { ...state, userInput: action.request, thinkingActive: false };
    case "user_input_cleared":
      return { ...state, userInput: null };
    case "todos_loaded":
      return { ...state, todos: action.todos };
    case "artifacts_loaded":
      return { ...state, artifacts: action.items };
    case "preview_loaded":
      return { ...state, preview: action.preview, inspectorTab: action.inspectorTab || state.inspectorTab };
    case "file_tree_loaded":
      return { ...state, fileTree: action.nodes };
    case "file_children_loaded":
      return { ...state, fileTree: injectChildren(state.fileTree, action.path, action.children) };
    case "mode_requested":
      return { ...state, requestedMode: action.mode };
    case "stream_completed":
      return {
        ...state,
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
        timeline: state.timeline.map((item) =>
          item.streaming ? { ...item, streaming: false } : item,
        ),
      };
    default:
      return state;
  }
}

function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [treeHeight, setTreeHeight] = useState(640);
  const [userAnswer, setUserAnswer] = useState("");
  const wsRef = useRef(null);
  const timelineRef = useRef(null);

  const currentMode = state.snapshot?.current_mode || state.requestedMode;
  const currentStatus = state.snapshot?.status || "idle";

  useEffect(() => {
    const updateTreeHeight = () => {
      setTreeHeight(Math.max(window.innerHeight - 180, 360));
    };
    updateTreeHeight();
    window.addEventListener("resize", updateTreeHeight);
    return () => window.removeEventListener("resize", updateTreeHeight);
  }, []);

  useEffect(() => {
    loadSessions();
    loadArtifacts();
    loadTodos("");
    loadFileChildren(".");
  }, []);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [state.timeline, state.thinkingActive, state.permission, state.userInput]);

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
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
    const timeline = timelineFromEvents(timelinePayload.events || []);
    dispatch({ type: "session_activated", sessionId, snapshot, timeline });
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
      preview: {
        kind: "file",
        title: payload.path || path,
        content: payload.content || "",
      },
      inspectorTab: "preview",
    });
  }

  async function openArtifact(reference) {
    const payload = await fetchJson(`/api/artifacts/${encodeURIComponent(reference)}`);
    const content = typeof payload.content === "string"
      ? payload.content
      : JSON.stringify(payload.content || {}, null, 2);
    dispatch({
      type: "preview_loaded",
      preview: {
        kind: "artifact",
        title: payload.path || reference,
        content,
      },
      inspectorTab: "preview",
    });
  }

  async function createSession(mode) {
    const payload = await fetchJson(`/api/sessions?mode=${encodeURIComponent(mode)}`, { method: "POST" });
    const snapshot = normalizeSessionPayload(payload);
    dispatch({ type: "session_activated", sessionId: snapshot.session_id, snapshot, timeline: [] });
    await Promise.all([loadSessions(), loadTodos(snapshot.session_id)]);
    return snapshot.session_id;
  }

  async function setMode(mode) {
    dispatch({ type: "mode_requested", mode });
    if (!state.currentSessionId) {
      return;
    }
    await fetchJson(`/api/sessions/${encodeURIComponent(state.currentSessionId)}/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    await loadSession(state.currentSessionId);
  }

  async function sendMessage() {
    const text = state.composer.trim();
    if (!text) {
      return;
    }
    dispatch({ type: "local_user_message", text });
    let sessionId = state.currentSessionId;
    if (!sessionId) {
      sessionId = await createSession(currentMode);
    }
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  }

  function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws`);
    wsRef.current = socket;
    socket.onopen = () => dispatch({ type: "set_connection", value: "connected" });
    socket.onclose = () => {
      dispatch({ type: "set_connection", value: "disconnected" });
      window.setTimeout(connectWebSocket, 1500);
    };
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      startTransition(() => handleSocketMessage(message.type, message.data || {}));
    };
  }

  function handleSocketMessage(type, data) {
    if (type === "session_status") {
      dispatch({ type: "session_snapshot", snapshot: normalizeSessionPayload(data.session_snapshot || data) });
      if ((data.session_snapshot || data).session_id) {
        loadSessions();
      }
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
      dispatch({ type: "thinking_state", active: data.active, reason: data.reason || "" });
      return;
    }
    if (type === "tool_start") {
      dispatch({
        type: "tool_started",
        callId: data.call_id || makeEventId("tool"),
        toolName: data.tool_name || "",
        arguments: data.arguments || {},
      });
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
      return;
    }
    if (type === "permission_request") {
      dispatch({ type: "permission_request", permission: data });
      return;
    }
    if (type === "user_input_request") {
      setUserAnswer("");
      dispatch({ type: "user_input_request", request: data });
      return;
    }
    if (type === "session_finished") {
      dispatch({ type: "stream_completed" });
      if (data.session_snapshot) {
        dispatch({ type: "session_snapshot", snapshot: normalizeSessionPayload(data.session_snapshot) });
      }
      loadSessions();
      if (state.currentSessionId) {
        loadTodos(state.currentSessionId);
      }
      return;
    }
    if (type === "message" && data.type === "ERROR") {
      dispatch({
        type: "append_timeline_item",
        item: { id: makeEventId("error"), kind: "system", tone: "error", content: data.content || "错误" },
      });
    }
  }

  function sendPermissionResponse(approved) {
    if (!wsRef.current || !state.permission) {
      return;
    }
    wsRef.current.send(
      JSON.stringify({
        type: "permission_response",
        permission_id: state.permission.permission_id,
        approved,
      }),
    );
    dispatch({ type: "permission_cleared" });
  }

  function sendUserInputResponse(option) {
    if (!wsRef.current || !state.userInput) {
      return;
    }
    const answer = option?.text || userAnswer.trim();
    if (!answer) {
      return;
    }
    wsRef.current.send(
      JSON.stringify({
        type: "user_input_response",
        request_id: state.userInput.request_id,
        answer,
        selected_index: option?.index || null,
        selected_mode: option?.mode || "",
        selected_option_text: option?.text || "",
      }),
    );
    dispatch({ type: "user_input_cleared" });
    setUserAnswer("");
  }

  const sessionCards = useMemo(
    () =>
      state.sessions.map((item) => ({
        id: item.session_id,
        title: item.user_goal || item.summary_text || item.session_id,
        detail: `${item.current_mode || "-"} · ${item.updated_at || "-"}`,
      })),
    [state.sessions],
  );

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">EmbedAgent</div>
          <div className="brand-sub">Codex-grade local shell</div>
        </div>
        <div className="sidebar-tabs">
          <button className={state.sidebarTab === "chats" ? "active" : ""} onClick={() => dispatch({ type: "set_sidebar", value: "chats" })}>Chats</button>
          <button className={state.sidebarTab === "files" ? "active" : ""} onClick={() => dispatch({ type: "set_sidebar", value: "files" })}>Files</button>
        </div>
        {state.sidebarTab === "chats" ? (
          <div className="thread-panel">
            <button className="primary wide" onClick={() => createSession(currentMode)}>New Session</button>
            <div className="thread-list">
              {sessionCards.map((session) => (
                <button
                  key={session.id}
                  className={`thread-card ${state.currentSessionId === session.id ? "selected" : ""}`}
                  onClick={() => loadSession(session.id)}
                >
                  <span className="thread-title">{session.title}</span>
                  <span className="thread-detail">{session.detail}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="files-panel">
            <Tree
              data={state.fileTree}
              width={300}
              height={treeHeight}
              rowHeight={30}
              indent={18}
              onActivate={(node) => {
                if (node.data.kind === "file") {
                  openFile(node.data.path);
                } else if (!node.data.childrenLoaded && node.data.hasChildren) {
                  loadFileChildren(node.data.path);
                }
              }}
            >
              {({ node, style }) => (
                <div
                  style={style}
                  className={`tree-row ${node.data.kind}`}
                  onClick={() => {
                    if (node.data.kind === "dir") {
                      if (!node.data.childrenLoaded && node.data.hasChildren) {
                        loadFileChildren(node.data.path);
                      }
                      node.toggle();
                    } else {
                      openFile(node.data.path);
                    }
                  }}
                >
                  <span className="tree-icon">{node.data.kind === "dir" ? (node.isOpen ? "▾" : "▸") : "·"}</span>
                  <span className="tree-label">{node.data.name}</span>
                </div>
              )}
            </Tree>
          </div>
        )}
      </aside>

      <main className="chat-shell">
        <header className="header">
          <div className="header-group">
            <div className={`badge mode mode-${currentMode}`}>{currentMode}</div>
            <div className={`badge status status-${currentStatus}`}>{currentStatus}</div>
            <div className="status-copy">{state.connectionState}</div>
          </div>
          <div className="header-group">
            <select value={currentMode} onChange={(event) => setMode(event.target.value)}>
              <option value="explore">explore</option>
              <option value="spec">spec</option>
              <option value="code">code</option>
              <option value="debug">debug</option>
              <option value="verify">verify</option>
            </select>
            <button className="ghost" onClick={() => loadSessions()}>Refresh</button>
          </div>
        </header>

        <div className="timeline" ref={timelineRef}>
          {state.timeline.map((item) => (
            <TimelineItem key={item.id} item={item} />
          ))}
          {state.thinkingActive && !state.streamingReasoningId ? (
            <div className="thinking-placeholder">模型正在思考...</div>
          ) : null}
        </div>

        <footer className="composer">
          <textarea
            value={state.composer}
            onChange={(event) => dispatch({ type: "set_composer", value: event.target.value })}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
              }
            }}
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
          />
          <button className="primary send" onClick={sendMessage}>Send</button>
        </footer>
      </main>

      <aside className="inspector">
        <div className="inspector-tabs">
          <button className={state.inspectorTab === "todos" ? "active" : ""} onClick={() => dispatch({ type: "set_inspector", value: "todos" })}>Todos</button>
          <button className={state.inspectorTab === "artifacts" ? "active" : ""} onClick={() => dispatch({ type: "set_inspector", value: "artifacts" })}>Artifacts</button>
          <button className={state.inspectorTab === "preview" ? "active" : ""} onClick={() => dispatch({ type: "set_inspector", value: "preview" })}>Preview</button>
        </div>
        <div className="inspector-body">
          {state.inspectorTab === "todos" ? (
            <TodoPanel todos={state.todos} />
          ) : null}
          {state.inspectorTab === "artifacts" ? (
            <ArtifactPanel artifacts={state.artifacts} onOpen={openArtifact} />
          ) : null}
          {state.inspectorTab === "preview" ? (
            <PreviewPanel preview={state.preview} />
          ) : null}
          {state.userInput ? (
            <div className="prompt-panel">
              <h3>需要用户决策</h3>
              <p>{state.userInput.question}</p>
              <div className="option-list">
                {(state.userInput.options || []).map((option) => (
                  <button key={option.index} className="option-card" onClick={() => sendUserInputResponse(option)}>
                    <span>{option.text}</span>
                    {option.mode ? <small>mode: {option.mode}</small> : null}
                  </button>
                ))}
              </div>
              <textarea
                value={userAnswer}
                onChange={(event) => setUserAnswer(event.target.value)}
                placeholder="或输入自由回答"
              />
              <button className="primary wide" onClick={() => sendUserInputResponse(null)}>提交回答</button>
            </div>
          ) : null}
        </div>
      </aside>

      {state.permission ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h3>需要确认</h3>
            <p>{state.permission.reason}</p>
            <pre>{JSON.stringify(state.permission.details || {}, null, 2)}</pre>
            <div className="modal-actions">
              <button className="ghost" onClick={() => sendPermissionResponse(false)}>拒绝</button>
              <button className="primary" onClick={() => sendPermissionResponse(true)}>批准</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TimelineItem({ item }) {
  if (item.kind === "user") {
    return <div className="bubble user">{item.content}</div>;
  }
  if (item.kind === "assistant") {
    return (
      <div className={`bubble assistant ${item.streaming ? "streaming" : ""}`}>
        <Markdown content={item.content} />
      </div>
    );
  }
  if (item.kind === "reasoning") {
    return (
      <details className="reasoning-card" open={item.open || item.streaming}>
        <summary>Thinking</summary>
        <div className="reasoning-body">{item.content}</div>
      </details>
    );
  }
  if (item.kind === "tool") {
    return (
      <div className={`tool-card ${item.status || "running"}`}>
        <div className="tool-title">{item.toolName}</div>
        <pre>{JSON.stringify(item.arguments || item.data || {}, null, 2)}</pre>
        {item.error ? <div className="tool-error">{item.error}</div> : null}
      </div>
    );
  }
  return <div className={`system-card ${item.tone || ""}`}>{item.content}</div>;
}

function Markdown({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code(props) {
          const { inline, className, children, ...rest } = props;
          if (inline) {
            return <code className={className} {...rest}>{children}</code>;
          }
          return (
            <pre className="code-block">
              <code className={className} {...rest}>{children}</code>
            </pre>
          );
        },
      }}
    >
      {content || ""}
    </ReactMarkdown>
  );
}

function TodoPanel({ todos }) {
  return (
    <div className="panel-list">
      <h3>Session Todos</h3>
      {(todos || []).length ? (
        todos.map((todo) => (
          <div key={todo.id} className="todo-row">
            <span className={todo.done ? "todo-mark done" : "todo-mark"}>{todo.done ? "done" : "todo"}</span>
            <span>{todo.content}</span>
          </div>
        ))
      ) : (
        <div className="empty-copy">当前会话还没有 todo。</div>
      )}
    </div>
  );
}

function ArtifactPanel({ artifacts, onOpen }) {
  return (
    <div className="panel-list">
      <h3>Artifacts</h3>
      {(artifacts || []).length ? (
        artifacts.map((item) => (
          <button key={item.path} className="artifact-row" onClick={() => onOpen(item.path)}>
            <span>{item.path}</span>
            <small>{item.tool_name || item.kind}</small>
          </button>
        ))
      ) : (
        <div className="empty-copy">暂无 artifact。</div>
      )}
    </div>
  );
}

function PreviewPanel({ preview }) {
  if (!preview) {
    return <div className="empty-copy">选择文件或 artifact 以预览。</div>;
  }
  return (
    <div className="panel-preview">
      <h3>{preview.title}</h3>
      <pre>{preview.content}</pre>
    </div>
  );
}

export default App;
