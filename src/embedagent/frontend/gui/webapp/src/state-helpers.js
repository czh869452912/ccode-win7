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

export function findLatestPendingUserTurnKey(timeline) {
  for (let index = (timeline || []).length - 1; index >= 0; index -= 1) {
    const item = timeline[index];
    if (item?.kind === "user" && !item.turnId) {
      return item.pendingTurnId || item.id || "";
    }
  }
  return "";
}

export function resolveTimelineAnchor({ explicitTurnId = "", activeTurnId = "", timeline = [] } = {}) {
  return explicitTurnId || activeTurnId || findLatestPendingUserTurnKey(timeline) || "";
}

export function resolveVisiblePermission(explicitPermission, snapshot) {
  if (explicitPermission) {
    return explicitPermission;
  }
  if (snapshot?.has_pending_permission && snapshot?.pending_permission) {
    return snapshot.pending_permission;
  }
  return null;
}

export function normalizeSessionPayload(payload, defaultMode = "explore") {
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
    workflow_state: payload.workflow_state || "chat",
    has_active_plan: Boolean(payload.has_active_plan),
    active_plan_ref: payload.active_plan_ref || "",
    current_command_context: payload.current_command_context || "",
    has_pending_permission: Boolean(payload.has_pending_permission),
    has_pending_input: Boolean(payload.has_pending_input),
    pending_permission: payload.pending_permission || null,
    pending_user_input: payload.pending_user_input || null,
    last_error: payload.last_error || "",
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
        ? Boolean(payload.pending_interaction || payload.pending_permission || payload.pending_user_input)
        : Boolean(payload.pending_interaction_valid),
    compactRetryCount: payload.compact_retry_count || 0,
    compactBoundaryCount: payload.compact_boundary_count || 0,
    contextPipelineSteps: Array.isArray(payload.context_pipeline_steps) ? payload.context_pipeline_steps : [],
    contextAnalysis: payload.context_analysis || null,
    current_phase: payload.current_phase || "",
    discipline_profile: payload.discipline_profile || "",
    current_activity: payload.current_activity || "",
    task_summary: payload.task_summary || "",
    task_items: Array.isArray(payload.task_items) ? payload.task_items : [],
    pending_interaction:
      payload.pending_interaction ||
      (payload.pending_permission
        ? {
            interaction_id: payload.pending_permission.permission_id || "",
            session_id: payload.pending_permission.session_id || payload.session_id || "",
            kind: "permission",
            tool_name: payload.pending_permission.tool_name || "",
            category: payload.pending_permission.category || "",
            reason: payload.pending_permission.reason || "",
            details: payload.pending_permission.details || {},
            turn_id: payload.pending_permission.turn_id || "",
            step_id: payload.pending_permission.step_id || "",
            step_index: payload.pending_permission.step_index || 0,
          }
        : payload.pending_user_input
          ? {
              interaction_id: payload.pending_user_input.request_id || "",
              session_id: payload.pending_user_input.session_id || payload.session_id || "",
              kind: "user_input",
              tool_name: payload.pending_user_input.tool_name || "",
              question: payload.pending_user_input.question || "",
              options: payload.pending_user_input.options || [],
              details: payload.pending_user_input.details || {},
              turn_id: payload.pending_user_input.turn_id || "",
              step_id: payload.pending_user_input.step_id || "",
              step_index: payload.pending_user_input.step_index || 0,
            }
          : null),
  };
}

