export function makeEventId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createTreeNode(entry) {
  return {
    id: entry.path,
    path: entry.path,
    name: entry.name,
    kind: entry.kind,
    children: [],
    childrenLoaded: false,
    hasChildren: Boolean(entry.has_children),
  };
}

export function injectChildren(nodes, targetPath, children) {
  return nodes.map((node) => {
    if (node.path === targetPath) {
      return {
        ...node,
        childrenLoaded: true,
        children: children.map(createTreeNode),
      };
    }
    if (!node.children || !node.children.length) {
      return node;
    }
    return {
      ...node,
      children: injectChildren(node.children, targetPath, children),
    };
  });
}

export function findLatestPendingUserTurnKey(activities) {
  for (let index = (activities || []).length - 1; index >= 0; index -= 1) {
    const item = activities[index];
    if (item?.kind === "user" && !item.turnId) {
      return item.pendingTurnId || item.id || "";
    }
  }
  return "";
}

export function resolveActivityAnchor({ explicitTurnId = "", activeTurnId = "", activities = [] } = {}) {
  return explicitTurnId || activeTurnId || findLatestPendingUserTurnKey(activities) || "";
}

export function resolveVisiblePermission(explicitPermission, snapshot) {
  if (explicitPermission) {
    return explicitPermission;
  }
  if (snapshot?.pending_interaction_valid && snapshot?.pending_interaction?.kind === "permission") {
    return snapshot.pending_interaction;
  }
  return null;
}

export function normalizeSessionPayload(payload, defaultMode = "") {
  const workflowState = payload.workflow_state
    && typeof payload.workflow_state === "object"
    && !Array.isArray(payload.workflow_state)
    ? payload.workflow_state
    : {};
  const recentTransitions = Array.isArray(payload.recent_transitions)
    ? payload.recent_transitions.map((entry) => ({
        ...entry,
        reason: entry?.reason || "",
        message: entry?.message || "",
        displayReason: entry?.display_reason || entry?.displayReason || entry?.reason || "",
      }))
    : [];
  return {
    session_id: payload.session_id || "",
    status: payload.status || "idle",
    current_mode: payload.current_mode || defaultMode,
    started_at: payload.started_at || payload.created_at || "",
    updated_at: payload.updated_at || "",
    workflow_state: workflowState,
    has_active_plan: Boolean(payload.has_active_plan),
    active_plan_ref: payload.active_plan_ref || "",
    current_command_context: payload.current_command_context || "",
    last_failure: payload.last_failure || null,
    lastTransitionReason: payload.last_transition_reason || "",
    lastTransitionDisplayReason:
      payload.last_transition_display_reason || payload.last_transition_reason || "",
    lastTransitionMessage: payload.last_transition_message || "",
    recentTransitions,
    runtimeSource: payload.runtime_source || "",
    bundledToolsReady: Boolean(payload.bundled_tools_ready),
    fallbackWarnings: payload.fallback_warnings || [],
    runtimeEnvironment: payload.runtime_environment || null,
    pending_interaction_valid:
      payload.pending_interaction_valid === undefined
        ? Boolean(payload.pending_interaction)
        : Boolean(payload.pending_interaction_valid),
    compactRetryCount: payload.compact_retry_count || 0,
    compactBoundaryCount: payload.compact_boundary_count || 0,
    contextPipelineSteps: Array.isArray(payload.context_pipeline_steps) ? payload.context_pipeline_steps : [],
    contextAnalysis: payload.context_analysis || null,
    turnExperience:
      payload.turn_experience && typeof payload.turn_experience === "object"
        ? payload.turn_experience
        : {},
    pending_interaction: payload.pending_interaction || null,
  };
}

