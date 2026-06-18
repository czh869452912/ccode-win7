import { normalizeAppBootstrap } from "../app-workspaces.js";
import { createDiffSurfaceState } from "../session-runtime/diff-model.js";
import { makeEventId, normalizeSessionPayload } from "../state-helpers.js";
import { LOADER_REQUESTS } from "./session-loaders.js";

const FS_REFRESH_TOOLS = new Set(["write_file", "edit_file", "git_commit", "git_reset"]);

function emptyEffects() {
  return { actions: [], eventLogEntries: [], loaderRequests: [] };
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

function nextSeq(sessionEventLog) {
  return Number(sessionEventLog?.lastAppliedSeq || 0) + 1;
}

function currentSession(options) {
  return options.currentSessionId || "";
}

function interactionEvent({ data, options, interactionId, payload }) {
  return {
    session_id: data?.session_id || currentSession(options),
    event_id: interactionId || eventId(options.makeId, "evt"),
    seq: nextSeq(options.sessionEventLog),
    created_at: nowValue(options.nowIso),
    event_kind: "interaction.created",
    payload,
  };
}

function commandResultEffects(data, options) {
  const effects = emptyEffects();
  const commandName = data?.command_name || "";
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
  effects.actions.push(logAction(`command: /${commandName || "?"}`, data?.success ? "ok" : "error"));
  return effects;
}

export function deriveSocketMessageEffects({
  type = "",
  data = {},
  currentSessionId = "",
  sessionEventLog = null,
  makeId = makeEventId,
  nowIso = () => new Date().toISOString(),
} = {}) {
  const options = { currentSessionId, sessionEventLog, makeId, nowIso };
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
    effects.eventLogEntries.push(payload);
    if (payload?.event_kind === "turn.started") {
      effects.actions.push({
        type: "turn_started",
        turnId: payload.payload?.turn_id || "",
        userText: payload.payload?.user_text || "",
        createdAt: payload?.created_at || nowValue(options.nowIso),
      });
    } else if (payload?.event_kind === "transition.recorded") {
      effects.actions.push({
        type: "turn_ended",
        terminationReason: payload.payload?.termination_reason || "",
        terminationDisplayReason:
          payload.payload?.display_reason || payload.payload?.termination_reason || "",
        terminationMessage: payload.payload?.message || payload.payload?.error || "",
        turnsUsed: payload.payload?.turns_used || 0,
        maxTurns: payload.payload?.max_turns ?? null,
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
    if (snap?.timeline_replay_status && snap.timeline_replay_status !== "replay") {
      action.replayStatePatch = snap.timeline_replay_status;
    }
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
      runtimeSource: payload?.runtime_source || "",
      resolvedToolRoots: payload?.resolved_tool_roots || {},
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
      runtimeSource: payload?.runtime_source || "",
      resolvedToolRoots: payload?.resolved_tool_roots || {},
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
    if (FS_REFRESH_TOOLS.has(payload?.tool_name || "")) {
      effects.loaderRequests.push({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN, path: "." });
    }
    return effects;
  }

  if (type === "permission_request") {
    effects.actions.push({
      type: "permission_request",
      permission: {
        ...payload,
        turn_id: payload?.turn_id || "",
        step_id: payload?.step_id || "",
        step_index: payload?.step_index || 0,
      },
      inspectorTab: "interaction",
    });
    effects.eventLogEntries.push(
      interactionEvent({
        data: payload,
        options,
        interactionId: payload?.permission_id || "",
        payload: {
          interaction_id: payload?.permission_id || "",
          kind: "permission",
          tool_name: payload?.tool_name || "",
          category: payload?.category || "",
          reason: payload?.reason || "",
          details: payload?.details || {},
          turn_id: payload?.turn_id || "",
          step_id: payload?.step_id || "",
          step_index: payload?.step_index || 0,
        },
      }),
    );
    effects.actions.push(logAction("permission_request", payload?.reason || ""));
    return effects;
  }

  if (type === "user_input_request") {
    effects.actions.push({
      type: "user_input_request",
      request: {
        ...payload,
        turn_id: payload?.turn_id || "",
        step_id: payload?.step_id || "",
        step_index: payload?.step_index || 0,
      },
      resetUserAnswer: true,
    });
    effects.eventLogEntries.push(
      interactionEvent({
        data: payload,
        options,
        interactionId: payload?.request_id || "",
        payload: {
          interaction_id: payload?.request_id || "",
          kind: "user_input",
          tool_name: payload?.tool_name || "",
          question: payload?.question || "",
          options: payload?.options || [],
          turn_id: payload?.turn_id || "",
          step_id: payload?.step_id || "",
          step_index: payload?.step_index || 0,
        },
      }),
    );
    effects.actions.push(logAction("user_input_request", payload?.question || ""));
    return effects;
  }

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
