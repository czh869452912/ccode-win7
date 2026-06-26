import { projectTransportView } from "./event-log.js";
import { projectT3TimelineRows } from "./t3-timeline.js";

function toInteractionTimelineItem(source) {
  const payload = source?.payload || source || {};
  const nestedRequest = source?.request || {};
  const interactionId =
    payload.interaction_id ||
    payload.request_id ||
    payload.permission_id ||
    nestedRequest.interaction_id ||
    nestedRequest.request_id ||
    nestedRequest.permission_id ||
    source?.interactionId ||
    "";
  const interactionKind = payload.kind || source?.interactionKind || "interaction";
  const label =
    payload.tool_name ||
    nestedRequest.tool_name ||
    payload.question ||
    nestedRequest.question ||
    payload.reason ||
    nestedRequest.reason ||
    payload.selected_option_text ||
    interactionKind;
  return {
    ...source,
    id: source?.id || source?.event_id || interactionId,
    kind: source?.resolved || payload.resolved ? "interaction_resolved" : "interaction_requested",
    interactionId,
    interactionKind,
    label,
    detail:
      payload.reason ||
      nestedRequest.reason ||
      payload.question ||
      nestedRequest.question ||
      payload.answerText ||
      payload.answer ||
      "",
  };
}

function normalizePendingInteraction(snapshot) {
  const interaction = snapshot?.pending_interaction;
  if (!interaction || interaction.status === "resolved") {
    return null;
  }
  if (snapshot?.pending_interaction_valid === false || interaction.valid === false || interaction.status === "expired") {
    return null;
  }
  return interaction;
}

function buildInteractionNotice(snapshot, currentInteraction) {
  const interaction = snapshot?.pending_interaction;
  if (interaction && (snapshot?.pending_interaction_valid === false || interaction.valid === false || interaction.status === "expired")) {
    return {
      kind: "expired",
      interactionId: interaction.interaction_id || "",
      source: "session_snapshot",
    };
  }
  if (!currentInteraction && snapshot?.restore_stop_reason === "interaction_expired") {
    return {
      kind: "expired",
      interactionId: "",
      source: "session_restore",
    };
  }
  return null;
}

function projectHistoryTimeline(historyTimeline = []) {
  return (historyTimeline || []).map((item) => {
    if (item?.kind === "permission" || item?.kind === "user_input" || item?.kind === "mode_switch_proposal") {
      return toInteractionTimelineItem({
        ...item,
        payload: {
          ...(item?.request || {}),
          interaction_id:
            item?.request?.interaction_id ||
            item?.request?.request_id ||
            item?.request?.permission_id ||
            item?.interactionId ||
            item?.id ||
            "",
          kind: item?.kind === "permission" ? "permission" : "user_input",
        },
      });
    }
    return { ...(item || {}) };
  });
}

function mergeTimelineItems({ snapshot, historyTimeline = [] }) {
  const currentInteraction = normalizePendingInteraction(snapshot);
  const timelineItems = projectHistoryTimeline(historyTimeline);
  const interactionIds = new Set(
    timelineItems
      .filter((item) => item?.kind === "interaction_requested" || item?.kind === "interaction_resolved")
      .map((item) => item.interactionId || ""),
  );
  if (currentInteraction && !interactionIds.has(currentInteraction.interaction_id || "")) {
    timelineItems.push(
      toInteractionTimelineItem({
        id: currentInteraction.interaction_id,
        payload: currentInteraction,
        turnId: currentInteraction.turn_id || "",
        stepId: currentInteraction.step_id || "",
        stepIndex: currentInteraction.step_index || 0,
        projectionSource: "session_snapshot",
        projectionKind: "pending_interaction",
        synthetic: false,
      }),
    );
  }
  return timelineItems;
}

function createTurnGroup(turnId) {
  return {
    turnId,
    userItem: null,
    leadingSystemItems: [],
    steps: [],
    trailingTurnItems: [],
    sessionFallbackItems: [],
    _stepMap: new Map(),
  };
}

function getTurnGroup(groups, turnMap, item) {
  const fallbackId = item.kind === "user" ? item.id : `session-${item.id}`;
  const key = item.turnId || fallbackId;
  if (!turnMap.has(key)) {
    const group = createTurnGroup(key);
    turnMap.set(key, group);
    groups.push(group);
  }
  return turnMap.get(key);
}

function getStepGroup(turn, item) {
  const key = item.stepId || `step-${turn.steps.length + 1}`;
  if (!turn._stepMap.has(key)) {
    const step = {
      stepId: key,
      stepIndex: item.stepIndex || turn.steps.length + 1,
      projectionSource: item.projectionSource || "",
      projectionKind: item.projectionKind || "",
      synthetic: Boolean(item.synthetic),
      activityItems: [],
      assistantItem: null,
    };
    turn._stepMap.set(key, step);
    turn.steps.push(step);
  }
  const step = turn._stepMap.get(key);
  if (item.projectionSource && !step.projectionSource) step.projectionSource = item.projectionSource;
  if (item.projectionKind && !step.projectionKind) step.projectionKind = item.projectionKind;
  if (item.synthetic) step.synthetic = true;
  return step;
}

function projectTurnGroups(items = []) {
  const groups = [];
  const turnMap = new Map();
  for (const item of items || []) {
    const group = getTurnGroup(groups, turnMap, item);
    if (item.kind === "user") {
      group.userItem = item;
      continue;
    }
    if (item.kind === "command_result" && !item.turnId) {
      group.sessionFallbackItems.push({ ...item, kind: "command_result_fallback" });
      continue;
    }
    if (item.stepId) {
      const step = getStepGroup(group, item);
      if (item.kind === "assistant") {
        step.assistantItem = item;
      } else {
        step.activityItems.push(item);
      }
      continue;
    }
    if (item.kind === "system" || item.kind === "compact") {
      if (group.steps.length === 0 && group.trailingTurnItems.length === 0) {
        group.leadingSystemItems.push(item);
      } else {
        group.trailingTurnItems.push(item);
      }
      continue;
    }
    if (!item.turnId) {
      group.sessionFallbackItems.push(item);
      continue;
    }
    group.trailingTurnItems.push(item);
  }
  return groups.map((group) => ({
    turnId: group.turnId,
    userItem: group.userItem,
    leadingSystemItems: group.leadingSystemItems,
    steps: group.steps.sort((left, right) => (left.stepIndex || 0) - (right.stepIndex || 0)),
    trailingTurnItems: group.trailingTurnItems,
    sessionFallbackItems: group.sessionFallbackItems,
  }));
}

export function projectSessionRuntime({
  snapshot,
  eventLog,
  historyTimeline = [],
  defaultMode = "explore",
  activeTurnId = "",
  thinkingActive = false,
} = {}) {
  const currentInteraction = normalizePendingInteraction(snapshot);
  const interactionNotice = buildInteractionNotice(snapshot, currentInteraction);
  const timelineItems = mergeTimelineItems({ snapshot, historyTimeline });
  const timelineView = projectTurnGroups(timelineItems);
  return {
    currentInteraction,
    interactionNotice,
    transportView: projectTransportView({ snapshot, eventLog }),
    sessionStatusView: {
      sessionId: snapshot?.session_id || "",
      status: snapshot?.status || "idle",
      mode: snapshot?.current_mode || defaultMode,
    },
    timelineItems,
    timelineView,
    t3TimelineRows: projectT3TimelineRows({
      turnGroups: timelineView,
      currentStatus: snapshot?.status || "idle",
      activeTurnId: activeTurnId || snapshot?.active_turn_id || "",
      currentInteraction,
      interactionNotice,
      thinkingActive,
    }),
  };
}

