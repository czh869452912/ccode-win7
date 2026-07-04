function basename(path) {
  const text = String(path || "").replace(/\\/g, "/");
  const parts = text.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : text;
}

function workspaceLabel(workspace = {}) {
  return String(workspace.label || "").trim()
    || basename(workspace.path)
    || String(workspace.path || "").trim()
    || "Workspace";
}

export function formatSessionUpdatedLabel(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  try {
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (_) {
    return text;
  }
}

export function buildThreadLifecycleActions(session, capabilities = {}) {
  const sessionId = String(session?.session_id || session?.id || "").trim();
  const actions = Array.isArray(capabilities?.actions) ? capabilities.actions : [];
  return actions.slice().sort((left, right) => {
    const leftOrder = Number(left?.order || 0);
    const rightOrder = Number(right?.order || 0);
    return leftOrder - rightOrder || String(left?.label || left?.id || "").localeCompare(String(right?.label || right?.id || ""));
  }).map((action) => {
    const actionId = String(action?.id || "").trim();
    const capability = String(action?.capability || actionId).trim();
    const available = action?.enabled !== false;
    const enabled = Boolean(sessionId && actionId && available);
    const reason = enabled ? "" : sessionId ? "backend_not_available" : "missing_session";
    return {
      ...action,
      id: actionId,
      label: String(action?.label || actionId).trim() || actionId,
      capability,
      sessionId,
      enabled,
      reason,
      reasonLabel:
        reason === "backend_not_available"
          ? "Backend lifecycle API is not available yet"
          : reason === "missing_session"
            ? "Thread is missing"
            : "",
    };
  });
}

export function buildAppHomeModel({
  app = {},
  sessions = [],
  currentSessionId = "",
  defaultMode = "",
  threadLifecycleCapabilities = {},
} = {}) {
  const activeWorkspace = app.activeWorkspace || null;
  const activatingWorkspace = Boolean(app.activatingWorkspace);
  const workspaceRows = (Array.isArray(app.workspaces) ? app.workspaces : [])
    .filter((workspace) => workspace && workspace.id)
    .map((workspace) => {
      const isActive = Boolean(activeWorkspace && activeWorkspace.id === workspace.id);
      const exists = workspace.exists !== false;
      return {
        id: String(workspace.id || ""),
        label: workspaceLabel(workspace),
        path: String(workspace.path || ""),
        exists,
        isActive,
        status: isActive ? "active" : exists ? "available" : "missing",
        disabled: activatingWorkspace || !exists,
      };
    });

  const threadRows = (Array.isArray(sessions) ? sessions : [])
    .filter((session) => session && session.session_id)
    .map((session) => {
      const sessionId = String(session.session_id || "");
      return {
        id: sessionId,
        title:
          String(session.thread?.title || "").trim()
          || String(session.title || "").trim()
          || String(session.user_goal || "").trim()
          || String(session.summary_text || "").trim()
          || `Session ${sessionId.slice(0, 8)}`,
        mode: String(session.current_mode || defaultMode || ""),
        updated: formatSessionUpdatedLabel(session.updated_at),
        isActive: sessionId === currentSessionId,
        actions: buildThreadLifecycleActions(session, threadLifecycleCapabilities),
      };
    });

  const hasActiveWorkspace = Boolean(app.hasActiveWorkspace && activeWorkspace);
  return {
    workspace: {
      hasActiveWorkspace,
      activeId: activeWorkspace ? String(activeWorkspace.id || "") : "",
      activeLabel: activeWorkspace ? workspaceLabel(activeWorkspace) : "No workspace",
      activePath: activeWorkspace ? String(activeWorkspace.path || "") : "Open a local project",
      activating: activatingWorkspace,
      count: workspaceRows.length,
      rows: workspaceRows,
    },
    threads: {
      count: threadRows.length,
      empty: threadRows.length === 0,
      canCreateThread: hasActiveWorkspace && !activatingWorkspace,
      rows: threadRows,
    },
  };
}
