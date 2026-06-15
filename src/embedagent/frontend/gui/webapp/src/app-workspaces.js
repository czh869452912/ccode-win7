function basename(path) {
  const text = String(path || "").replace(/\\/g, "/");
  const parts = text.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : text;
}

export function normalizeWorkspaceRecord(input = {}) {
  const path = String(input.path || "");
  const label = String(input.label || "").trim() || basename(path) || path || "Workspace";
  return {
    id: String(input.id || ""),
    path,
    label,
    exists: input.exists !== false,
    created_at: String(input.created_at || ""),
    last_opened_at: String(input.last_opened_at || ""),
  };
}

export function normalizeAppBootstrap(payload = {}) {
  const workspaces = Array.isArray(payload.workspaces)
    ? payload.workspaces.map(normalizeWorkspaceRecord).filter((item) => item.id)
    : [];
  const activePayload = payload.active_workspace || payload.activeWorkspace || null;
  const activeWorkspace = activePayload
    ? normalizeWorkspaceRecord(activePayload)
    : null;
  return {
    workspaces,
    activeWorkspace: activeWorkspace && activeWorkspace.id ? activeWorkspace : null,
    hasActiveWorkspace: Boolean(
      (payload.has_active_workspace || payload.hasActiveWorkspace) && activeWorkspace,
    ),
    lastError: String(payload.last_error || payload.lastError || ""),
  };
}

export function canSwitchWorkspace(state = {}) {
  const snapshot = state.snapshot || {};
  const status = String(snapshot.status || "");
  if (snapshot.pending_interaction_valid && snapshot.pending_interaction) {
    return { allowed: false, reason: "pending_interaction" };
  }
  if (status === "running" || status === "waiting_permission" || status === "waiting_user_input") {
    return { allowed: false, reason: "active_thread" };
  }
  return { allowed: true, reason: "" };
}

export function resetWorkspaceScopedState(state = {}) {
  return {
    ...state,
    sessions: [],
    currentSessionId: "",
    snapshot: null,
    timeline: [],
    streamingAssistantId: "",
    streamingReasoningId: "",
    thinkingActive: false,
    permission: null,
    userInput: null,
    interactionNotice: null,
    tasks: [],
    artifacts: [],
    plan: null,
    review: null,
    recipes: [],
    permissionContext: null,
    preview: null,
    diffSurface: null,
    fileTree: [],
    toolCatalog: {},
    eventLog: [],
    terminationReason: "",
    terminationDisplayReason: "",
    terminationMessage: "",
    turnsUsed: 0,
    activeTurnId: "",
    activeStepId: "",
    activeStepIndex: 0,
    historyIntegrity: null,
  };
}
