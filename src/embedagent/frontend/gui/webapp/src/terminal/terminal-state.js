import { resolveTerminalSessionLabel } from "./terminal-labels.js";

const DEFAULT_MAX_BUFFER_CHARS = 128 * 1024;

function read(input, snake, camel, fallback = "") {
  if (!input || typeof input !== "object") return fallback;
  if (Object.prototype.hasOwnProperty.call(input, snake)) return input[snake];
  if (Object.prototype.hasOwnProperty.call(input, camel)) return input[camel];
  return fallback;
}

function normalizeCapabilities(input = {}) {
  return {
    stdin: input.stdin !== false,
    resize: input.resize === true,
    pty: input.pty === true,
  };
}

function trimBuffer(text, maxBufferChars) {
  const value = String(text || "");
  const limit = Number(maxBufferChars || DEFAULT_MAX_BUFFER_CHARS);
  if (value.length <= limit) return value;
  return value.slice(value.length - limit);
}

export function normalizeTerminalSummary(input = {}) {
  const terminalId = String(read(input, "terminal_id", "terminalId", ""));
  return {
    sessionId: String(read(input, "session_id", "sessionId", "")),
    terminalId,
    cwd: String(input.cwd || ""),
    status: String(input.status || "closed"),
    pid: input.pid == null ? null : Number(input.pid),
    exitCode:
      input.exit_code == null && input.exitCode == null
        ? null
        : Number(read(input, "exit_code", "exitCode", null)),
    label: resolveTerminalSessionLabel(terminalId, input),
    updatedAt: String(read(input, "updated_at", "updatedAt", "")),
    capabilities: normalizeCapabilities(input.capabilities || {}),
  };
}

export function normalizeTerminalSnapshot(input = {}) {
  return {
    ...normalizeTerminalSummary(input),
    history: String(input.history || ""),
    sequence: Number(input.sequence || 0),
    cols: Number(input.cols || 80),
    rows: Number(input.rows || 24),
  };
}

export function createTerminalState(options = {}) {
  return {
    activeTerminalId: "",
    terminalIds: [],
    sessions: {},
    maxBufferChars: Number(options.maxBufferChars || DEFAULT_MAX_BUFFER_CHARS),
    lastError: "",
  };
}

function upsertSnapshot(state, snapshot) {
  const normalized = normalizeTerminalSnapshot(snapshot);
  if (!normalized.terminalId) return state;
  const terminalIds = state.terminalIds.includes(normalized.terminalId)
    ? state.terminalIds
    : state.terminalIds.concat(normalized.terminalId);
  return {
    ...state,
    terminalIds,
    activeTerminalId: state.activeTerminalId || normalized.terminalId,
    sessions: {
      ...state.sessions,
      [normalized.terminalId]: {
        ...normalized,
        buffer: trimBuffer(normalized.history, state.maxBufferChars),
        error: "",
      },
    },
    lastError: "",
  };
}

function upsertSummary(state, summary) {
  const normalized = normalizeTerminalSummary(summary);
  if (!normalized.terminalId) return state;
  const previous = state.sessions[normalized.terminalId] || {};
  const terminalIds = state.terminalIds.includes(normalized.terminalId)
    ? state.terminalIds
    : state.terminalIds.concat(normalized.terminalId);
  return {
    ...state,
    terminalIds,
    activeTerminalId: state.activeTerminalId || normalized.terminalId,
    sessions: {
      ...state.sessions,
      [normalized.terminalId]: {
        ...previous,
        ...normalized,
        buffer: previous.buffer || "",
      },
    },
  };
}

function removeTerminal(state, terminalId) {
  const id = String(terminalId || "");
  if (!id || !state.sessions[id]) return state;
  const sessions = { ...state.sessions };
  delete sessions[id];
  const terminalIds = state.terminalIds.filter((item) => item !== id);
  return {
    ...state,
    terminalIds,
    sessions,
    activeTerminalId:
      state.activeTerminalId === id ? terminalIds[0] || "" : state.activeTerminalId,
  };
}

export function applyTerminalEvent(state, event = {}) {
  const current = state || createTerminalState();
  const terminalId = String(read(event, "terminal_id", "terminalId", ""));
  if (!terminalId) return current;
  if (event.snapshot) {
    const withSnapshot = upsertSnapshot(current, event.snapshot);
    if (event.type === "closed") {
      return removeTerminal(withSnapshot, terminalId);
    }
    return withSnapshot;
  }
  if (event.type === "closed") {
    return removeTerminal(current, terminalId);
  }
  const previous = current.sessions[terminalId] || normalizeTerminalSnapshot(event);
  const chunk = String(event.chunk || event.data || "");
  let nextBuffer = previous.buffer || previous.history || "";
  if (event.type === "output") {
    nextBuffer = trimBuffer(nextBuffer + chunk, current.maxBufferChars);
  } else if (event.type === "cleared") {
    nextBuffer = "";
  }
  const updated = {
    ...previous,
    terminalId,
    sessionId: String(read(event, "session_id", "sessionId", previous.sessionId || "")),
    status: String(event.status || previous.status || "running"),
    sequence: Number(event.sequence || previous.sequence || 0),
    buffer: nextBuffer,
  };
  const terminalIds = current.terminalIds.includes(terminalId)
    ? current.terminalIds
    : current.terminalIds.concat(terminalId);
  return {
    ...current,
    terminalIds,
    activeTerminalId: current.activeTerminalId || terminalId,
    sessions: {
      ...current.sessions,
      [terminalId]: updated,
    },
  };
}

export function reduceTerminalState(state, action = {}) {
  const current = state || createTerminalState();
  switch (action.type) {
    case "terminal_snapshot_loaded":
      return upsertSnapshot(current, action.snapshot || action.terminal || {});
    case "terminal_summaries_loaded":
      return (action.terminals || []).reduce(upsertSummary, {
        ...current,
        terminalIds: [],
        sessions: {},
        activeTerminalId: "",
      });
    case "terminal_event":
      return applyTerminalEvent(current, action.event || {});
    case "terminal_active_set":
      return {
        ...current,
        activeTerminalId: current.sessions[action.terminalId] ? action.terminalId : current.activeTerminalId,
      };
    default:
      return current;
  }
}
