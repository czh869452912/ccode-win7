export function createThreadState() {
  return {
    sessions: [],
    currentSessionId: "",
    historyIntegrity: null,
  };
}

export function readThreadState(state = {}) {
  return state.thread && typeof state.thread === "object" ? state.thread : createThreadState();
}

export function readThreadSessions(state = {}) {
  const thread = readThreadState(state);
  return Array.isArray(thread.sessions) ? thread.sessions : [];
}

export function readActiveThreadId(state = {}) {
  return String(readThreadState(state).currentSessionId || "");
}

export function readThreadHistoryIntegrity(state = {}) {
  return readThreadState(state).historyIntegrity || null;
}

function healHistoryIntegrity(current, snapshot = {}) {
  const historyIntegrity = current.historyIntegrity || null;
  if (
    historyIntegrity &&
    historyIntegrity.status === "partial" &&
    !snapshot.restore_stop_reason
  ) {
    return {
      ...historyIntegrity,
      status: "healthy",
      restore_stop_reason: "",
    };
  }
  return historyIntegrity;
}

export function reduceThreadState(state, action = {}) {
  const current = state && typeof state === "object" ? state : createThreadState();
  switch (action.type) {
    case "sessions_loaded":
      return {
        ...current,
        sessions: Array.isArray(action.sessions) ? action.sessions : [],
      };
    case "session_activated":
      return {
        ...current,
        currentSessionId: String(action.sessionId || action.snapshot?.session_id || ""),
        historyIntegrity: action.historyIntegrity || null,
      };
    case "session_snapshot": {
      const snapshot = action.snapshot || {};
      if (!snapshot) return current;
      return {
        ...current,
        currentSessionId: String(snapshot.session_id || current.currentSessionId || ""),
        historyIntegrity: healHistoryIntegrity(current, snapshot),
      };
    }
    case "workspace_scoped_state_reset":
      return createThreadState();
    default:
      return current;
  }
}
