import { makeEventId, resolveTimelineAnchor } from "../state-helpers.js";

export function createActivityState() {
  return {
    timeline: [],
    streamingAssistantId: "",
    streamingReasoningId: "",
    thinkingActive: false,
    activeTurnId: "",
    activeStepId: "",
    activeStepIndex: 0,
    terminationReason: "",
    terminationDisplayReason: "",
    terminationMessage: "",
    turnsUsed: 0,
    maxTurns: null,
  };
}

export function liveProjectionMeta() {
  return {
    projectionSource: "step_events",
    projectionKind: "recorded_step",
    synthetic: false,
  };
}

export function rawProjectionMeta() {
  return {
    projectionSource: "raw_events",
    projectionKind: "raw_event",
    synthetic: false,
  };
}

function upsertTimelineItem(timeline, nextItem, match) {
  const index = timeline.findIndex(match);
  if (index < 0) {
    return timeline.concat(nextItem);
  }
  return timeline.map((item, currentIndex) =>
    currentIndex === index ? { ...item, ...nextItem } : item,
  );
}

export function reduceActivityState(state, action) {
  switch (action.type) {
    case "activity_reset":
      return {
        ...createActivityState(),
        timeline: Array.isArray(action.timeline) ? action.timeline : [],
      };
    case "local_user_message": {
      const pendingTurnId = makeEventId("user");
      return {
        ...state,
        timeline: state.timeline
          .map((item) => (item.streaming ? { ...item, streaming: false } : item))
          .concat({
            id: pendingTurnId,
            kind: "user",
            content: action.text,
            turnId: "",
            pendingTurnId,
            createdAt: action.createdAt || new Date().toISOString(),
            ...liveProjectionMeta(),
          }),
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
        terminationReason: "",
        terminationDisplayReason: "",
        terminationMessage: "",
        turnsUsed: 0,
        maxTurns: null,
        activeTurnId: pendingTurnId,
      };
    }
    case "turn_started": {
      const turnId = action.turnId || "";
      let linked = false;
      let linkedAnchor = "";
      const timeline = state.timeline.map((item) => {
        if (!linked && item.kind === "user" && !item.turnId) {
          linked = true;
          linkedAnchor = item.pendingTurnId || item.id || "";
          return {
            ...item,
            turnId,
            pendingTurnId: "",
            content: action.userText || item.content,
            createdAt: item.createdAt || action.createdAt || "",
          };
        }
        return item;
      });
      const reboundTimeline = linkedAnchor
        ? timeline.map((item) => (item.turnId === linkedAnchor ? { ...item, turnId } : item))
        : timeline;
      if (!linked) {
        reboundTimeline.push({
          id: makeEventId("user"),
          kind: "user",
          content: action.userText || "",
          turnId,
          createdAt: action.createdAt || "",
          ...liveProjectionMeta(),
        });
      }
      return {
        ...state,
        timeline: reboundTimeline,
        activeTurnId: turnId,
      };
    }
    case "step_started":
      return {
        ...state,
        activeTurnId: action.turnId || state.activeTurnId,
        activeStepId: action.stepId || "",
        activeStepIndex: action.stepIndex || 0,
        streamingAssistantId: "",
        streamingReasoningId: "",
      };
    case "turn_ended":
      return {
        ...state,
        terminationReason: action.terminationReason || "",
        terminationDisplayReason: action.terminationDisplayReason || action.terminationReason || "",
        terminationMessage: action.terminationMessage || "",
        turnsUsed: action.turnsUsed || 0,
        maxTurns: action.maxTurns ?? null,
      };
    case "assistant_delta": {
      let timeline = state.timeline.slice();
      const turnId = action.turnId || state.activeTurnId;
      const stepId = action.stepId || state.activeStepId;
      const stepIndex = action.stepIndex || state.activeStepIndex;
      let id = state.streamingAssistantId;
      const existing = id ? timeline.find((item) => item.id === id) : null;
      if (!id || (existing && existing.stepId !== stepId)) {
        id = makeEventId("assistant");
        timeline.push({
          id,
          kind: "assistant",
          content: action.text,
          streaming: true,
          turnId,
          stepId,
          stepIndex,
          createdAt: action.createdAt || "",
          ...liveProjectionMeta(),
        });
      } else {
        timeline = timeline.map((item) =>
          item.id === id
            ? { ...item, content: `${item.content || ""}${action.text}`, streaming: true }
            : item,
        );
      }
      return { ...state, timeline, streamingAssistantId: id, thinkingActive: false };
    }
    case "reasoning_delta": {
      let timeline = state.timeline.slice();
      const turnId = action.turnId || state.activeTurnId;
      const stepId = action.stepId || state.activeStepId;
      const stepIndex = action.stepIndex || state.activeStepIndex;
      let id = state.streamingReasoningId;
      const existing = id ? timeline.find((item) => item.id === id) : null;
      if (!id || (existing && existing.stepId !== stepId)) {
        id = makeEventId("thinking");
        timeline.push({
          id,
          kind: "reasoning",
          content: action.text,
          open: false,
          streaming: true,
          turnId,
          stepId,
          stepIndex,
          createdAt: action.createdAt || "",
          ...liveProjectionMeta(),
        });
      } else {
        timeline = timeline.map((item) =>
          item.id === id
            ? { ...item, content: `${item.content || ""}${action.text}`, streaming: true }
            : item,
        );
      }
      return { ...state, timeline, streamingReasoningId: id };
    }
    case "thinking_state": {
      const timeline = state.timeline.map((item) => {
        if (item.id === state.streamingReasoningId) {
          return { ...item, streaming: Boolean(action.active) };
        }
        if (item.id === state.streamingAssistantId) {
          return { ...item, streaming: Boolean(action.active) ? item.streaming : false };
        }
        return item;
      });
      return { ...state, thinkingActive: Boolean(action.active), timeline };
    }
    case "tool_started":
      return {
        ...state,
        thinkingActive: false,
        timeline: upsertTimelineItem(
          state.timeline,
          {
            id: action.callId,
            kind: "tool",
            toolName: action.toolName,
            label: action.label || action.toolName,
            arguments: action.arguments,
            status: "running",
            turnId: action.turnId || state.activeTurnId,
            stepId: action.stepId || state.activeStepId,
            stepIndex: action.stepIndex || state.activeStepIndex,
            data: null,
            error: "",
            permissionCategory: action.permissionCategory || "",
            supportsDiffPreview: Boolean(action.supportsDiffPreview),
            progressRendererKey: action.progressRendererKey || "",
            resultRendererKey: action.resultRendererKey || "",
            runtimeSource: action.runtimeSource || "",
            resolvedToolRoots: action.resolvedToolRoots || {},
            itemType: action.itemType || "",
            requestKind: action.requestKind || "",
            toolTitle: action.toolTitle || "",
            toolLifecycleStatus: action.toolLifecycleStatus || "",
            command: action.command || "",
            rawCommand: action.rawCommand || "",
            detail: action.detail || "",
            sourceActivityKind: action.sourceActivityKind || "",
            changedFiles: action.changedFiles || [],
            toolData: action.toolData,
            completedAt: action.completedAt || "",
            ...liveProjectionMeta(),
          },
          (item) => item.kind === "tool" && item.id === action.callId,
        ),
      };
    case "tool_finished":
      return {
        ...state,
        timeline: upsertTimelineItem(
          state.timeline,
          {
            id: action.callId,
            kind: "tool",
            toolName: action.toolName,
            label: action.label || action.toolName,
            arguments: action.arguments || {},
            status: action.success ? "success" : "error",
            data: action.data,
            error: action.error,
            turnId: action.turnId || state.activeTurnId,
            stepId: action.stepId || state.activeStepId,
            stepIndex: action.stepIndex || state.activeStepIndex,
            permissionCategory: action.permissionCategory || "",
            supportsDiffPreview: Boolean(action.supportsDiffPreview),
            progressRendererKey: action.progressRendererKey || "",
            resultRendererKey: action.resultRendererKey || "",
            runtimeSource: action.runtimeSource || "",
            resolvedToolRoots: action.resolvedToolRoots || {},
            itemType: action.itemType || "",
            requestKind: action.requestKind || "",
            toolTitle: action.toolTitle || "",
            toolLifecycleStatus: action.toolLifecycleStatus || "",
            command: action.command || "",
            rawCommand: action.rawCommand || "",
            detail: action.detail || "",
            sourceActivityKind: action.sourceActivityKind || "",
            changedFiles: action.changedFiles || [],
            toolData: action.toolData,
            createdAt: action.createdAt || "",
            ...liveProjectionMeta(),
          },
          (item) => item.kind === "tool" && item.id === action.callId,
        ),
      };
    case "step_ended": {
      const turnId = action.turnId || state.activeTurnId;
      const stepId = action.stepId || state.activeStepId;
      const stepIndex = action.stepIndex || state.activeStepIndex;
      let timeline = state.timeline.map((item) => {
        if (
          (item.id === state.streamingAssistantId || item.id === state.streamingReasoningId) &&
          item.stepId === stepId
        ) {
          return { ...item, streaming: false };
        }
        return item;
      });
      const hasAssistant = timeline.some((item) => item.kind === "assistant" && item.stepId === stepId);
      if (!hasAssistant && action.assistantText) {
        timeline = timeline.concat({
          id: makeEventId("assistant"),
          kind: "assistant",
          content: action.assistantText,
          turnId,
          stepId,
          stepIndex,
          streaming: false,
          createdAt: action.createdAt || "",
          ...liveProjectionMeta(),
        });
      }
      return {
        ...state,
        timeline,
        streamingAssistantId: "",
        streamingReasoningId: "",
        activeTurnId: turnId,
        activeStepId: stepId,
        activeStepIndex: stepIndex,
      };
    }
    case "session_error":
      return {
        ...state,
        timeline: state.timeline.concat({
          id: action.id || makeEventId("error"),
          kind: "system",
          tone: "error",
          content: action.error || "会话出错",
          turnId: resolveTimelineAnchor({
            explicitTurnId: action.turnId || "",
            activeTurnId: state.activeTurnId,
            timeline: state.timeline,
          }),
          stepId: action.stepId || "",
          stepIndex: action.stepIndex || 0,
          ...rawProjectionMeta(),
        }),
        thinkingActive: false,
        streamingAssistantId: "",
        streamingReasoningId: "",
      };
    case "context_compacted":
      return {
        ...state,
        timeline: state.timeline.concat({
          id: action.id || makeEventId("context"),
          kind: "compact",
          content: action.content || "",
          recentTurns: action.recentTurns,
          summarizedTurns: action.summarizedTurns,
          approxTokensAfter: action.approxTokensAfter,
          turnId: resolveTimelineAnchor({
            explicitTurnId: action.turnId || "",
            activeTurnId: state.activeTurnId,
            timeline: state.timeline,
          }),
          stepId: action.stepId || "",
          stepIndex: action.stepIndex || 0,
          ...rawProjectionMeta(),
        }),
      };
    case "command_result": {
      const turnId = resolveTimelineAnchor({
        explicitTurnId: action.turnId || "",
        activeTurnId: state.activeTurnId,
        timeline: state.timeline,
      });
      const clearSessionView = Boolean(action.data?.clear_session_view);
      const timeline = clearSessionView
        ? []
        : state.timeline.concat({
            id: action.id || makeEventId("cmd"),
            kind: "command_result",
            commandName: action.commandName,
            content: action.message,
            data: action.data || {},
            success: action.success,
            turnId,
            stepId: action.stepId || "",
            stepIndex: action.stepIndex || 0,
            createdAt: action.createdAt || "",
            ...rawProjectionMeta(),
          });
      return {
        ...state,
        timeline,
        thinkingActive: false,
        streamingAssistantId: "",
        streamingReasoningId: "",
      };
    }
    case "stream_completed":
      return {
        ...state,
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
        timeline: state.timeline.map((item) => (item.streaming ? { ...item, streaming: false } : item)),
      };
    default:
      return state;
  }
}

export const ACTIVITY_ACTION_TYPES = new Set([
  "local_user_message",
  "turn_started",
  "step_started",
  "turn_ended",
  "assistant_delta",
  "reasoning_delta",
  "thinking_state",
  "tool_started",
  "tool_finished",
  "step_ended",
  "session_error",
  "context_compacted",
  "command_result",
  "stream_completed",
]);
