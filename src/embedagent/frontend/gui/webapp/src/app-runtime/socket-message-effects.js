import { normalizeAppBootstrap } from "../app-workspaces.js";
import { createDiffSurfaceState } from "../session-runtime/diff-model.js";
import { normalizeSessionPayload } from "../state-helpers.js";
import { LOADER_REQUESTS } from "./session-loaders.js";

const WORKSPACE_FILES_INVALIDATION = "workspace_files";
const CAPABILITIES_INVALIDATION = "capabilities";
const SOURCE_CONTROL_INVALIDATION = "source_control";

function emptyEffects() {
  return { actions: [], transportEvents: [], loaderRequests: [] };
}

function text(value) {
  return String(value || "").trim();
}

function toolPresentation(payload = {}) {
  const data = payload?.data && typeof payload.data === "object" ? payload.data : {};
  return {
    itemType: payload?.item_type || data.item_type || "",
    requestKind: payload?.request_kind || data.request_kind || "",
    toolTitle: payload?.tool_title || data.tool_title || "",
    toolLifecycleStatus: payload?.tool_lifecycle_status || data.tool_lifecycle_status || "",
    command: payload?.command || data.command || "",
    rawCommand: payload?.raw_command || data.raw_command || "",
    detail: payload?.detail || data.detail || "",
    sourceActivityKind: payload?.source_activity_kind || data.source_activity_kind || "",
    changedFiles: payload?.changed_files || data.changed_files || [],
    toolData: payload?.tool_data !== undefined ? payload.tool_data : data.tool_data,
  };
}

function readModelInvalidations(payload = {}) {
  const raw = payload?.read_model_invalidations || payload?.data?.read_model_invalidations;
  return Array.isArray(raw) ? raw.map((item) => text(item)).filter(Boolean) : [];
}

function interactionPayload(payload = {}) {
  return {
    requestKind: text(payload?.request_kind),
    permissionCategory: text(payload?.category || payload?.permission_category),
    toolName: text(payload?.tool_name),
    summary: text(payload?.summary || payload?.reason || payload?.question),
    reason: text(payload?.reason),
    details: payload?.details && typeof payload.details === "object" ? payload.details : {},
    questions: Array.isArray(payload?.questions) ? payload.questions : [],
    decision: text(payload?.decision),
    answer: text(payload?.answer || payload?.selected_option_text),
    error: text(payload?.error || payload?.detail),
  };
}

function commandResultEffects(payload, envelope, options) {
  const effects = emptyEffects();
  effects.actions.push({
    type: "command_result",
    id: envelope.event_id,
    commandName: payload?.command_name || "",
    success: Boolean(payload?.success),
    message: payload?.message || "",
    data: payload?.data || {},
    turnId: payload?.turn_id || "",
    stepId: payload?.step_id || "",
    stepIndex: payload?.step_index || 0,
    createdAt: envelope.timestamp,
  });
  const switchSessionId = payload?.data?.switch_session_id;
  if (switchSessionId) {
    effects.loaderRequests.push({
      name: LOADER_REQUESTS.LOAD_SESSION,
      sessionId: switchSessionId,
    });
  }
  const commandDiff = payload?.data?.diff;
  if (typeof commandDiff === "string" && commandDiff) {
    effects.actions.push({
      type: "diff_surface_opened",
      diffSurface: createDiffSurfaceState({
        title: options.diffPanelChrome?.defaultTitle,
        diff: commandDiff,
        source: "command",
        turnId: payload?.turn_id || "",
        chrome: options.diffPanelChrome || {},
      }),
    });
  }
  if (readModelInvalidations(payload).includes(CAPABILITIES_INVALIDATION)) {
    effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_SESSION_CAPABILITIES });
  }
  if (text(payload?.log_label)) {
    effects.actions.push({
      type: "log_event",
      label: text(payload.log_label),
      detail: text(payload?.log_detail),
    });
  }
  return effects;
}

function toolEffects(eventKind, payload, envelope) {
  const effects = emptyEffects();
  const invalidations = readModelInvalidations(payload);
  const common = {
    callId: payload?.call_id || envelope.event_id,
    toolName: payload?.tool_name || "",
    label: payload?.tool_label || "",
    permissionCategory: payload?.permission_category || "",
    supportsDiffPreview: Boolean(payload?.supports_diff_preview),
    progressRendererKey: payload?.progress_renderer_key || "",
    resultRendererKey: payload?.result_renderer_key || "",
    readModelInvalidations: invalidations,
    runtimeSource: payload?.runtime_source || "",
    resolvedToolRoots: payload?.resolved_tool_roots || {},
    ...toolPresentation(payload),
    turnId: payload?.turn_id || "",
    stepId: payload?.step_id || "",
    stepIndex: payload?.step_index || 0,
  };
  if (eventKind === "tool.started") {
    effects.actions.push({
      type: "tool_started",
      ...common,
      arguments: payload?.arguments || {},
      createdAt: envelope.timestamp,
    });
    return effects;
  }
  const failure =
    payload?.failure && typeof payload.failure === "object" ? payload.failure : null;
  effects.actions.push({
    type: "tool_finished",
    ...common,
    success: Boolean(payload?.success),
    error: failure?.message || payload?.error || "",
    failure,
    data: payload?.data || {},
    completedAt: envelope.timestamp,
  });
  if (invalidations.includes(WORKSPACE_FILES_INVALIDATION)) {
    effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN, path: "." });
  }
  if (invalidations.includes(SOURCE_CONTROL_INVALIDATION)) {
    effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_SOURCE_CONTROL_STATUS });
  }
  return effects;
}

function interactionEffects(eventKind, payload, envelope) {
  const effects = emptyEffects();
  const requested =
    eventKind === "approval.requested" || eventKind === "user-input.requested";
  effects.actions.push({
    type: requested ? "interaction_requested" : "interaction_resolved",
    id: envelope.event_id,
    kind: eventKind,
    requestId: String(payload?.request_id || payload?.interaction_id || ""),
    turnId: String(payload?.turn_id || ""),
    createdAt: envelope.timestamp,
    payload: interactionPayload(payload),
  });
  return effects;
}

function sessionEventEffects(envelope, options) {
  const effects = emptyEffects();
  const eventKind = envelope?.event_kind || "";
  const payload = envelope?.payload || {};
  const createdAt = envelope?.timestamp || "";

  if (eventKind === "turn.started") {
    effects.actions.push({
      type: "turn_started",
      turnId: payload?.turn_id || "",
      userText: payload?.user_text || "",
      createdAt,
    });
  } else if (eventKind === "transition.recorded") {
    effects.actions.push({
      type: "turn_ended",
      terminationReason: payload?.termination_reason || "",
      terminationDisplayReason:
        payload?.display_reason || payload?.termination_reason || "",
      terminationMessage: payload?.message || payload?.error || "",
      turnsUsed: payload?.turns_used || 0,
      maxTurns: payload?.max_turns ?? null,
    });
  } else if (eventKind === "step.started") {
    effects.actions.push({
      type: "step_started",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
    });
  } else if (eventKind === "step.finished") {
    effects.actions.push({
      type: "step_ended",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      assistantText: payload?.assistant_text || "",
      status: payload?.status || "",
      createdAt,
    });
  } else if (eventKind === "assistant.delta") {
    effects.actions.push({
      type: "assistant_delta",
      text: payload?.text || "",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      createdAt,
    });
  } else if (eventKind === "reasoning.delta") {
    effects.actions.push({
      type: "reasoning_delta",
      text: payload?.text || "",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      createdAt,
    });
  } else if (eventKind === "thinking.state") {
    effects.actions.push({ type: "thinking_state", active: Boolean(payload?.active) });
  } else if (eventKind === "tool.started" || eventKind === "tool.finished") {
    return toolEffects(eventKind, payload, envelope);
  } else if (
    eventKind === "approval.requested" ||
    eventKind === "approval.resolved" ||
    eventKind === "approval.response.failed" ||
    eventKind === "user-input.requested" ||
    eventKind === "user-input.resolved" ||
    eventKind === "user-input.response.failed"
  ) {
    return interactionEffects(eventKind, payload, envelope);
  } else if (eventKind === "session.status" || eventKind === "mode.changed") {
    const snapshot = payload?.session_snapshot;
    if (snapshot && typeof snapshot === "object") {
      effects.actions.push({
        type: "session_snapshot",
        snapshot: normalizeSessionPayload(snapshot),
      });
      if (snapshot.session_id) {
        effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_SESSIONS });
      }
    }
  } else if (eventKind === "command.result") {
    return commandResultEffects(payload, envelope, options);
  } else if (eventKind === "plan.updated") {
    effects.actions.push({ type: "plan_loaded", plan: payload?.plan || null });
  } else if (eventKind === "context.compacted") {
    effects.actions.push({
      type: "context_compacted",
      id: envelope.event_id,
      content: payload?.content || payload?.summary || "",
      recentTurns: payload?.recent_turns,
      summarizedTurns: payload?.summarized_turns,
      approxTokensAfter: payload?.approx_tokens_after,
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      createdAt,
    });
  } else if (eventKind === "session.error") {
    if (payload?.session_snapshot && typeof payload.session_snapshot === "object") {
      effects.actions.push({
        type: "session_snapshot",
        snapshot: normalizeSessionPayload(payload.session_snapshot),
      });
    }
    effects.actions.push({
      type: "session_error",
      id: envelope.event_id,
      error: payload?.failure?.message || payload?.error || "",
      failure: payload?.failure || null,
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      createdAt,
    });
  } else if (eventKind === "session.finished") {
    effects.actions.push({ type: "stream_completed" });
    if (payload?.session_snapshot && typeof payload.session_snapshot === "object") {
      effects.actions.push({
        type: "session_snapshot",
        snapshot: normalizeSessionPayload(payload.session_snapshot),
      });
    }
    effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_SESSIONS });
  }
  return effects;
}

export function deriveSocketMessageEffects({
  type = "",
  data = {},
  diffPanelChrome = {},
} = {}) {
  const payload = data || {};
  if (type === "workspace_changed") {
    const effects = emptyEffects();
    const bootstrap = normalizeAppBootstrap(payload);
    effects.actions.push({ type: "workspace_switched", bootstrap });
    if (bootstrap.hasActiveWorkspace) {
      effects.loaderRequests.push({
        name: LOADER_REQUESTS.LOAD_ACTIVE_WORKSPACE_DATA,
        sessionId: "",
        assumeWorkspace: true,
      });
    } else {
      effects.actions.push({ type: "source_control_reset" });
    }
    return effects;
  }
  if (type === "terminal_event") {
    const effects = emptyEffects();
    effects.actions.push({ type: "terminal_event", event: payload?.event || payload || {} });
    return effects;
  }
  if (type === "session_event") {
    const effects = sessionEventEffects(payload, { diffPanelChrome });
    effects.transportEvents.push(payload);
    return effects;
  }
  return emptyEffects();
}
