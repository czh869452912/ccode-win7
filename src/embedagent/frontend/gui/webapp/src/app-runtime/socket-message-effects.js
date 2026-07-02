import { normalizeAppBootstrap } from "../app-workspaces.js";
import { createDiffSurfaceState } from "../session-runtime/diff-model.js";
import { makeEventId, normalizeSessionPayload } from "../state-helpers.js";
import { LOADER_REQUESTS } from "./session-loaders.js";

const WORKSPACE_FILES_INVALIDATION = "workspace_files";
const CAPABILITIES_INVALIDATION = "capabilities";

function emptyEffects() {
  return { actions: [], transportEvents: [], loaderRequests: [] };
}

function eventId(makeId, prefix) {
  return typeof makeId === "function" ? makeId(prefix) : makeEventId(prefix);
}

function nowValue(nowIso) {
  return typeof nowIso === "function" ? nowIso() : new Date().toISOString();
}

function logAction(label, detail = "") {
  return { type: "log_event", label, detail };
}

function pickToolPresentationPayload(payload = {}) {
  return {
    itemType: payload?.item_type || payload?.itemType || payload?.data?.item_type || payload?.data?.itemType || "",
    requestKind: payload?.request_kind || payload?.requestKind || payload?.data?.request_kind || payload?.data?.requestKind || "",
    toolTitle: payload?.tool_title || payload?.toolTitle || payload?.data?.tool_title || payload?.data?.toolTitle || "",
    toolLifecycleStatus:
      payload?.tool_lifecycle_status ||
      payload?.toolLifecycleStatus ||
      payload?.data?.tool_lifecycle_status ||
      payload?.data?.toolLifecycleStatus ||
      "",
    command: payload?.command || payload?.data?.command || "",
    rawCommand: payload?.raw_command || payload?.rawCommand || payload?.data?.raw_command || payload?.data?.rawCommand || "",
    detail: payload?.detail || payload?.data?.detail || "",
    sourceActivityKind:
      payload?.source_activity_kind ||
      payload?.sourceActivityKind ||
      payload?.data?.source_activity_kind ||
      payload?.data?.sourceActivityKind ||
      "",
    changedFiles:
      payload?.changed_files ||
      payload?.changedFiles ||
      payload?.data?.changed_files ||
      payload?.data?.changedFiles ||
      [],
    toolData:
      payload?.tool_data ||
      payload?.toolData ||
      payload?.data?.tool_data ||
      payload?.data?.toolData ||
      payload?.data?.item,
  };
}

function currentSession(options) {
  return options.currentSessionId || "";
}

function readModelInvalidations(payload = {}) {
  const raw = payload?.read_model_invalidations || payload?.readModelInvalidations || payload?.data?.read_model_invalidations || [];
  return Array.isArray(raw) ? raw.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

function text(value) {
  return String(value || "").trim();
}

function normalizeInteractionPayload(payload = {}) {
  return {
    requestKind: text(payload?.request_kind || payload?.requestKind),
    permissionCategory: text(payload?.category || payload?.permission_category || payload?.permissionCategory),
    toolName: text(payload?.tool_name || payload?.toolName),
    summary: text(payload?.summary || payload?.reason || payload?.question),
    reason: text(payload?.reason),
    details: payload?.details && typeof payload.details === "object" ? payload.details : {},
    questions: Array.isArray(payload?.questions) ? payload.questions : [],
    decision: text(payload?.decision),
    answer: text(payload?.answer || payload?.selected_option_text),
    error: text(payload?.error || payload?.detail),
  };
}

function commandResultEffects(data, options) {
  const effects = emptyEffects();
  const commandName = data?.command_name || "";
  const invalidations = readModelInvalidations(data);
  effects.actions.push({
    type: "command_result",
    id: eventId(options.makeId, "cmd"),
    commandName,
    success: Boolean(data?.success),
    message: data?.message || "",
    data: data?.data || {},
    turnId: data?.turn_id || "",
    stepId: data?.step_id || "",
    stepIndex: data?.step_index || 0,
    createdAt: data?.created_at || nowValue(options.nowIso),
  });
  if (commandName === "resume" && data?.data?.switch_session_id) {
    effects.loaderRequests.push({
      name: LOADER_REQUESTS.LOAD_SESSION,
      sessionId: data.data.switch_session_id,
    });
  }
  if (commandName === "diff" && typeof data?.data?.diff === "string" && data.data.diff) {
    effects.actions.push({
      type: "diff_surface_opened",
      diffSurface: createDiffSurfaceState({
        title: "Git Diff",
        diff: data.data.diff,
        source: "command",
        turnId: data?.turn_id || "",
      }),
    });
  }
  if (commandName === "workspace") {
    effects.actions.push({
      type: "preview_loaded",
      preview: {
        kind: "workspace",
        title: "Workspace",
        content: JSON.stringify(data?.data || {}, null, 2),
      },
      inspectorTab: "preview",
    });
  }
  if (commandName === "recipes") {
    effects.actions.push({ type: "recipes_loaded", items: data?.data?.items || [] });
    effects.actions.push({ type: "set_inspector", value: "run" });
  }
  if (commandName === "run") {
    effects.actions.push({ type: "set_inspector", value: "problems" });
  }
  if (commandName === "permissions") {
    effects.actions.push({
      type: "permission_context_loaded",
      context: data?.data || {},
      inspectorTab: "permissions",
    });
  }
  if (commandName === "review" && data?.data?.review) {
    effects.actions.push({
      type: "review_loaded",
      review: data.data.review,
      inspectorTab: "review",
    });
  }
  if (invalidations.includes(CAPABILITIES_INVALIDATION)) {
    effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_SESSION_CAPABILITIES });
  }
  effects.actions.push(logAction(`command: /${commandName || "?"}`, data?.success ? "ok" : "error"));
  return effects;
}

export function deriveSocketMessageEffects({
  type = "",
  data = {},
  currentSessionId = "",
  sessionTransport = null,
  makeId = makeEventId,
  nowIso = () => new Date().toISOString(),
} = {}) {
  const options = { currentSessionId, sessionTransport, makeId, nowIso };
  const payload = data || {};
  const effects = emptyEffects();

  if (type === "workspace_changed") {
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
    effects.actions.push({ type: "terminal_event", event: payload?.event || payload || {} });
    return effects;
  }

  if (type === "session_event") {
    effects.transportEvents.push(payload);
    const eventKind = payload?.event_kind || "";
    const eventPayload = payload?.payload || {};
    const createdAt = payload?.created_at || nowValue(options.nowIso);
    const requestId = String(eventPayload?.request_id || eventPayload?.interaction_id || "");
    if (eventKind === "turn.started") {
      effects.actions.push({
        type: "turn_started",
        turnId: eventPayload?.turn_id || "",
        userText: eventPayload?.user_text || "",
        createdAt,
      });
    } else if (eventKind === "transition.recorded") {
      effects.actions.push({
        type: "turn_ended",
        terminationReason: eventPayload?.termination_reason || "",
        terminationDisplayReason:
          eventPayload?.display_reason || eventPayload?.termination_reason || "",
        terminationMessage: eventPayload?.message || eventPayload?.error || "",
        turnsUsed: eventPayload?.turns_used || 0,
        maxTurns: eventPayload?.max_turns ?? null,
      });
    } else if (eventKind === "approval.requested" || eventKind === "user-input.requested") {
      effects.actions.push({
        type: "interaction_requested",
        id: payload?.event_id || eventId(options.makeId, "interaction"),
        kind: eventKind,
        requestId,
        turnId: String(eventPayload?.turn_id || ""),
        createdAt,
        payload: normalizeInteractionPayload(eventPayload),
      });
    } else if (
      eventKind === "approval.resolved" ||
      eventKind === "approval.response.failed" ||
      eventKind === "user-input.resolved" ||
      eventKind === "user-input.response.failed"
    ) {
      effects.actions.push({
        type: "interaction_resolved",
        id: payload?.event_id || eventId(options.makeId, "interaction"),
        kind: eventKind,
        requestId,
        turnId: String(eventPayload?.turn_id || ""),
        createdAt,
        payload: normalizeInteractionPayload(eventPayload),
      });
    }
    return effects;
  }

  if (type === "session_status") {
    const snap = payload.session_snapshot || payload;
    const action = {
      type: "session_snapshot",
      snapshot: normalizeSessionPayload(snap),
    };
    effects.actions.push(action);
    if (snap?.session_id) effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_SESSIONS });
    effects.actions.push(logAction("session_status", snap?.status || ""));
    return effects;
  }

  if (type === "stream_delta") {
    effects.actions.push({
      type: "assistant_delta",
      text: payload?.text || "",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      createdAt: nowValue(options.nowIso),
    });
    return effects;
  }

  if (type === "reasoning_delta") {
    effects.actions.push({
      type: "reasoning_delta",
      text: payload?.text || "",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      createdAt: nowValue(options.nowIso),
    });
    return effects;
  }

  if (type === "thinking_state") {
    effects.actions.push({ type: "thinking_state", active: payload?.active });
    effects.actions.push(logAction("thinking", payload?.active ? "started" : "stopped"));
    return effects;
  }

  if (type === "tool_start") {
    effects.actions.push({
      type: "tool_started",
      callId: payload?.call_id || eventId(makeId, "tool"),
      toolName: payload?.tool_name || "",
      label: payload?.tool_label || payload?.tool_name || "",
      arguments: payload?.arguments || {},
      permissionCategory: payload?.permission_category || "",
      supportsDiffPreview: Boolean(payload?.supports_diff_preview),
      progressRendererKey: payload?.progress_renderer_key || "",
      resultRendererKey: payload?.result_renderer_key || "",
      readModelInvalidations: readModelInvalidations(payload),
      runtimeSource: payload?.runtime_source || "",
      resolvedToolRoots: payload?.resolved_tool_roots || {},
      ...pickToolPresentationPayload(payload),
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      createdAt: payload?.created_at || nowValue(options.nowIso),
    });
    effects.actions.push(
      logAction(`tool: ${payload?.tool_name || "?"}`, JSON.stringify(payload?.arguments || {}).slice(0, 80)),
    );
    return effects;
  }

  if (type === "tool_finish") {
    effects.actions.push({
      type: "tool_finished",
      callId: payload?.call_id || "",
      toolName: payload?.tool_name || "",
      success: Boolean(payload?.success),
      error: payload?.error || "",
      data: payload?.data || {},
      label: payload?.tool_label || payload?.tool_name || "",
      permissionCategory: payload?.permission_category || "",
      supportsDiffPreview: Boolean(payload?.supports_diff_preview),
      progressRendererKey: payload?.progress_renderer_key || "",
      resultRendererKey: payload?.result_renderer_key || "",
      readModelInvalidations: readModelInvalidations(payload),
      runtimeSource: payload?.runtime_source || "",
      resolvedToolRoots: payload?.resolved_tool_roots || {},
      ...pickToolPresentationPayload(payload),
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      completedAt: payload?.completed_at || payload?.created_at || nowValue(options.nowIso),
    });
    effects.actions.push(
      logAction(
        `tool done: ${payload?.call_id || "?"}`,
        payload?.success ? "success" : `error: ${payload?.error || ""}`,
      ),
    );
    if (readModelInvalidations(payload).includes(WORKSPACE_FILES_INVALIDATION)) {
      effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN, path: "." });
    }
    return effects;
  }

  if (type === "permission_request" || type === "user_input_request") return effects;

  if (type === "command_result") return commandResultEffects(payload, options);

  if (type === "session_error") {
    effects.actions.push({
      type: "session_error",
      id: payload?.event_id || eventId(makeId, "error"),
      error: payload?.error || "",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
    });
    effects.actions.push(logAction("session_error", payload?.error || ""));
    return effects;
  }

  if (type === "plan_updated") {
    effects.actions.push({ type: "plan_loaded", plan: payload?.plan || null, inspectorTab: "plan" });
    effects.actions.push(logAction("plan_updated", payload?.plan?.title || ""));
    return effects;
  }

  if (type === "turn_end") {
    effects.actions.push({
      type: "turn_ended",
      terminationReason: payload?.termination_reason || "",
      terminationDisplayReason: payload?.display_reason || payload?.termination_reason || "",
      terminationMessage: payload?.message || "",
      turnsUsed: payload?.turns_used || 0,
      maxTurns: payload?.max_turns ?? null,
    });
    effects.actions.push(logAction("turn_end", `reason=${payload?.termination_reason} turns=${payload?.turns_used}`));
    return effects;
  }

  if (type === "turn_start") {
    effects.actions.push({
      type: "turn_started",
      turnId: payload?.turn_id || "",
      userText: payload?.user_text || "",
      createdAt: payload?.created_at || nowValue(options.nowIso),
    });
    effects.actions.push(logAction("turn_start", payload?.turn_id || ""));
    return effects;
  }

  if (type === "step_start") {
    effects.actions.push({
      type: "step_started",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
    });
    effects.actions.push(logAction("step_start", payload?.step_id || ""));
    return effects;
  }

  if (type === "step_end") {
    effects.actions.push({
      type: "step_ended",
      turnId: payload?.turn_id || "",
      stepId: payload?.step_id || "",
      stepIndex: payload?.step_index || 0,
      assistantText: payload?.assistant_text || "",
      status: payload?.status || "",
    });
    effects.actions.push(logAction("step_end", payload?.step_id || ""));
    return effects;
  }

  if (type === "session_finished") {
    effects.actions.push({ type: "stream_completed" });
    if (payload?.session_snapshot) {
      effects.actions.push({
        type: "session_snapshot",
        snapshot: normalizeSessionPayload(payload.session_snapshot),
      });
    }
    effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_SESSIONS });
    if (currentSession(options)) {
      effects.loaderRequests.push({
        name: LOADER_REQUESTS.LOAD_TASKS,
        sessionId: currentSession(options),
      });
    }
    effects.actions.push(logAction("session_finished", ""));
    return effects;
  }

  if (type === "tasks_refresh") {
    if (currentSession(options)) {
      effects.loaderRequests.push({
        name: LOADER_REQUESTS.LOAD_TASKS,
        sessionId: currentSession(options),
      });
    }
    return effects;
  }

  if (type === "artifacts_refresh") {
    effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_ARTIFACTS });
    return effects;
  }

  if (type === "message" && payload?.type === "ERROR") {
    effects.actions.push({
      type: "session_error",
      id: payload?.id || eventId(makeId, "error"),
      error: payload?.content || "Error",
      turnId: payload?.metadata?.turn_id || "",
      stepId: payload?.metadata?.step_id || "",
      stepIndex: payload?.metadata?.step_index || 0,
    });
    effects.actions.push(logAction("error", payload?.content || ""));
    return effects;
  }

  if (type === "message" && payload?.type === "CONTEXT_COMPACTED") {
    const metadata = payload?.metadata || {};
    effects.actions.push({
      type: "context_compacted",
      id: payload?.id || eventId(makeId, "context"),
      content: payload?.content || "",
      recentTurns: metadata.recent_turns,
      summarizedTurns: metadata.summarized_turns,
      approxTokensAfter: metadata.approx_tokens_after,
      turnId: metadata.turn_id || "",
      stepId: metadata.step_id || "",
      stepIndex: metadata.step_index || 0,
    });
    effects.actions.push(logAction("context_compacted", payload?.content || ""));
    return effects;
  }

  return effects;
}
