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

export function describeProjectionBadge({
  projectionSource = "",
  projectionKind = "",
  synthetic = false,
} = {}) {
  const source = String(projectionSource || "").trim();
  const kind = String(projectionKind || "").trim();
  if (!synthetic && kind === "recorded_step") {
    return null;
  }
  if (!source && !kind && !synthetic) {
    return null;
  }
  const sourceLabelMap = {
    turn_events: "turn projection",
    raw_events: "raw fallback",
    step_events: "step events",
  };
  const detail = sourceLabelMap[source] || source.replace(/_/g, " ");
  if (synthetic || kind === "synthetic_single_step") {
    return {
      label: "synthetic",
      detail: detail || "projected",
    };
  }
  return {
    label: kind || "projected",
    detail: detail || "",
  };
}

export function summarizeTimelineProjection(timeline = []) {
  const items = Array.isArray(timeline) ? timeline : [];
  if (items.length === 0) {
    return {
      source: "",
      syntheticCount: 0,
      projectedCount: 0,
    };
  }
  let source = "";
  let syntheticCount = 0;
  let projectedCount = 0;
  for (const item of items) {
    const itemSource = String(item?.projectionSource || "").trim();
    if (!source && itemSource) {
      source = itemSource;
    }
    if (item?.synthetic) syntheticCount += 1;
    if (itemSource && itemSource !== "raw_events") projectedCount += 1;
  }
  return {
    source: source || "raw_events",
    syntheticCount,
    projectedCount,
  };
}

export function describeTimelineProjectionNotice(summary = {}) {
  const source = String(summary?.source || "").trim();
  if (source !== "raw_events") {
    return null;
  }
  return {
    tone: "context",
    title: "raw fallback",
    detail: "showing raw timeline events",
  };
}

export function timelineFromEvents(events) {
  const items = [];
  const toolIndex = {};
  // Tracks an in-progress reasoning aggregation across consecutive delta events.
  let pendingReasoningId = null;
  let pendingReasoningIdx = -1;

  function flushReasoning() {
    pendingReasoningId = null;
    pendingReasoningIdx = -1;
  }

  for (const record of events || []) {
    const eventName = record.event;
    const payload = record.payload || {};
    if ((eventName === "turn_started" || eventName === "turn_start") && (payload.text || payload.user_text)) {
      flushReasoning();
      items.push({
        id: record.event_id,
        kind: "user",
        content: payload.text || payload.user_text || "",
        turnId: payload.turn_id || "",
        projectionSource: "raw_events",
      });
    } else if (eventName === "reasoning_delta" && payload.text) {
      // Aggregate consecutive reasoning deltas into a single card.
      if (pendingReasoningId !== null) {
        items[pendingReasoningIdx] = {
          ...items[pendingReasoningIdx],
          content: (items[pendingReasoningIdx].content || "") + payload.text,
        };
      } else {
        pendingReasoningId = record.event_id;
        pendingReasoningIdx = items.length;
        items.push({
          id: record.event_id,
          kind: "reasoning",
          content: payload.text,
          open: false,
          turnId: payload.turn_id || "",
          stepId: payload.step_id || "",
          stepIndex: payload.step_index || 0,
          projectionSource: "raw_events",
        });
      }
      // Do NOT flush — stay in accumulation mode until a non-reasoning event arrives.
      continue;
    } else if (eventName === "tool_started") {
      flushReasoning();
      const item = {
        id: payload.call_id || record.event_id,
        kind: "tool",
        toolName: payload.tool_name,
        label: payload.tool_label || payload.tool_name,
        arguments: payload.arguments,
        status: "running",
        turnId: payload.turn_id || "",
        stepId: payload.step_id || "",
        stepIndex: payload.step_index || 0,
        permissionCategory: payload.permission_category || "",
        supportsDiffPreview: Boolean(payload.supports_diff_preview),
        progressRendererKey: payload.progress_renderer_key || "",
        resultRendererKey: payload.result_renderer_key || "",
        projectionSource: "raw_events",
      };
      toolIndex[item.id] = items.length;
      items.push(item);
    } else if (eventName === "tool_finished") {
      const callId = payload.call_id || record.event_id;
      const index = toolIndex[callId];
      const toolItem = {
        id: callId,
        kind: "tool",
        toolName: payload.tool_name,
        label: payload.tool_label || payload.tool_name,
        arguments: {},
        status: payload.success ? "success" : "error",
        turnId: payload.turn_id || "",
        stepId: payload.step_id || "",
        stepIndex: payload.step_index || 0,
        data: payload.data,
        error: payload.error,
        permissionCategory: payload.permission_category || "",
        supportsDiffPreview: Boolean(payload.supports_diff_preview),
        progressRendererKey: payload.progress_renderer_key || "",
        resultRendererKey: payload.result_renderer_key || "",
        projectionSource: "raw_events",
      };
      if (index === undefined) {
        items.push(toolItem);
      } else {
        items[index] = { ...items[index], ...toolItem };
      }
    } else if (eventName === "context_compacted") {
      flushReasoning();
      items.push({
        id: record.event_id,
        kind: "compact",
        content: payload.content || "",
        recentTurns: payload.recent_turns,
        summarizedTurns: payload.summarized_turns,
        approxTokensAfter: payload.approx_tokens_after,
        projectionSource: "raw_events",
      });
    } else if (eventName === "session_error") {
      flushReasoning();
      items.push({
        id: record.event_id,
        kind: "system",
        tone: "error",
        content: payload.error || "会话出错",
        projectionSource: "raw_events",
      });
    } else if (eventName === "command_result") {
      flushReasoning();
      items.push({
        id: record.event_id,
        kind: "command_result",
        commandName: payload.command_name || "",
        content: payload.message || "",
        data: payload.data || {},
        success: Boolean(payload.success),
        projectionSource: "raw_events",
      });
    } else if (eventName === "plan_updated") {
      flushReasoning();
      const plan = payload.plan || {};
      items.push({
        id: record.event_id,
        kind: "system",
        tone: "context",
        content: `计划已更新：${plan.title || "Current Plan"}`,
        projectionSource: "raw_events",
      });
    } else if (eventName === "session_finished" && payload.final_text) {
      flushReasoning();
      items.push({
        id: record.event_id,
        kind: "assistant",
        content: payload.final_text,
        turnId: payload.turn_id || "",
        projectionSource: "raw_events",
      });
    }
  }
  return items;
}

/**
 * Convert a structured Turn list (from build_structured_timeline) into flat timeline items.
 * Each turn produces: user bubble, reasoning card, tool cards, assistant bubble.
 */
export function timelineFromTurns(turns, events = [], options = {}) {
  const items = [];
  const eventCardsByStep = {};
  const projectionSource = options?.projectionSource || "";
  for (const record of events || []) {
    const payload = record.payload || {};
    const stepId = payload.step_id || "";
    if (!stepId) continue;
    if (record.event === "user_input_required") {
      if (!eventCardsByStep[stepId]) eventCardsByStep[stepId] = [];
      const request = payload.user_input || {};
      eventCardsByStep[stepId].push({
        id: request.request_id || record.event_id,
        kind:
          request.tool_name === "propose_mode_switch"
            ? "mode_switch_proposal"
            : "user_input",
        request,
        answered: false,
        turnId: payload.turn_id || "",
        stepId,
        stepIndex: payload.step_index || 0,
      });
    }
  }
  for (const turn of turns || []) {
    const turnId = turn.turn_id || makeEventId("turn");
    if (turn.user_text) {
      items.push({
        id: `${turnId}-user`,
        kind: "user",
        content: turn.user_text,
        turnId,
        projectionSource,
        projectionKind: turn.projection_kind || "",
        synthetic: false,
      });
    }
    const steps =
      Array.isArray(turn.steps) && turn.steps.length > 0
        ? turn.steps
        : [
            {
              step_id: `${turnId}-step-1`,
              step_index: 1,
              reasoning: turn.reasoning || "",
              assistant_text: turn.assistant_text || "",
              tool_calls: turn.tool_calls || [],
              status: turn.status || "completed",
            },
          ];
    for (const step of steps) {
      const stepId = step.step_id || makeEventId("step");
      const stepIndex = step.step_index || 0;
      const projectionKind = step.projection_kind || turn.projection_kind || "";
      const synthetic = Boolean(step.synthetic);
      if (step.reasoning) {
        items.push({
          id: `${stepId}-reasoning`,
          kind: "reasoning",
          content: step.reasoning,
          open: false,
          turnId,
          stepId,
          stepIndex,
          projectionSource,
          projectionKind,
          synthetic,
        });
      }
      for (const tc of step.tool_calls || []) {
        items.push({
          id: tc.call_id || makeEventId("tool"),
          kind: "tool",
          toolName: tc.tool_name,
          label: tc.tool_label || tc.tool_name,
          arguments: tc.arguments || {},
          status: tc.status || "success",
          data: tc.data,
          error: tc.error || "",
          permissionCategory: tc.permission_category || "",
          supportsDiffPreview: Boolean(tc.supports_diff_preview),
          progressRendererKey: tc.progress_renderer_key || "",
          resultRendererKey: tc.result_renderer_key || "",
          runtimeSource: tc.runtime_source || "",
          resolvedToolRoots: tc.resolved_tool_roots || {},
          turnId,
          stepId,
          stepIndex,
          projectionSource,
          projectionKind,
          synthetic,
        });
      }
      for (const card of eventCardsByStep[stepId] || []) {
        items.push({
          ...card,
          projectionSource,
          projectionKind,
          synthetic,
        });
      }
      if (step.assistant_text) {
        items.push({
          id: `${stepId}-assistant`,
          kind: "assistant",
          content: step.assistant_text,
          turnId,
          stepId,
          stepIndex,
          projectionSource,
          projectionKind,
          synthetic,
        });
      }
    }
  }
  return items;
}

export function normalizeSessionPayload(payload) {
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
    current_mode: payload.current_mode || "code",
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
    compactRetryCount: payload.compact_retry_count || 0,
    compactBoundaryCount: payload.compact_boundary_count || 0,
    contextPipelineSteps: Array.isArray(payload.context_pipeline_steps) ? payload.context_pipeline_steps : [],
    contextAnalysis: payload.context_analysis || null,
  };
}
