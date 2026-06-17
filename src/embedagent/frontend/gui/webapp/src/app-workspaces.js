export { normalizeAppBootstrap, normalizeWorkspaceRecord } from "./app-shell/model.js";

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
