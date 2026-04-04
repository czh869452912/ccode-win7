function toInteractionTimelineItem(source) {
  const payload = source?.payload || source || {};
  const interactionId = payload.interaction_id || payload.request_id || payload.permission_id || source?.id || "";
  const interactionKind = payload.kind || source?.interactionKind || "interaction";
  const label =
    payload.tool_name ||
    payload.question ||
    payload.reason ||
    payload.selected_option_text ||
    interactionKind;
  return {
    ...source,
    id: source?.id || source?.event_id || interactionId,
    kind: source?.resolved || payload.resolved ? "interaction_resolved" : "interaction_requested",
    interactionId,
    interactionKind,
    label,
    detail: payload.reason || payload.question || payload.answerText || payload.answer || "",
  };
}

function projectBootstrapTimeline(bootstrapTimeline = []) {
  return (bootstrapTimeline || []).map((item) => {
    if (item?.kind === "permission" || item?.kind === "user_input" || item?.kind === "mode_switch_proposal") {
      return toInteractionTimelineItem(item);
    }
    return item;
  });
}

function projectEventLogTimeline(events = []) {
  const items = [];
  for (const event of events || []) {
    if (event?.event_kind === "interaction.created") {
      items.push(
        toInteractionTimelineItem({
          id: event.event_id,
          payload: event.payload,
          turnId: event.payload?.turn_id || "",
          stepId: event.payload?.step_id || "",
          stepIndex: event.payload?.step_index || 0,
          projectionSource: "session_events",
          projectionKind: "interaction_event",
          synthetic: false,
        }),
      );
    } else if (event?.event_kind === "interaction.resolved") {
      items.push(
        toInteractionTimelineItem({
          id: event.event_id,
          payload: { ...(event.payload || {}), resolved: true },
          resolved: true,
          turnId: event.payload?.turn_id || "",
          stepId: event.payload?.step_id || "",
          stepIndex: event.payload?.step_index || 0,
          projectionSource: "session_events",
          projectionKind: "interaction_event",
          synthetic: false,
        }),
      );
    }
  }
  return items;
}

export function projectSessionRuntime({ snapshot, eventLog, bootstrapTimeline = [] }) {
  const currentInteraction =
    snapshot?.pending_interaction && snapshot.pending_interaction.status !== "resolved"
      ? snapshot.pending_interaction
      : null;
  const timelineView = projectBootstrapTimeline(bootstrapTimeline);
  const eventItems = projectEventLogTimeline(eventLog?.events || []);
  const interactionIds = new Set(
    timelineView
      .filter((item) => item?.kind === "interaction_requested" || item?.kind === "interaction_resolved")
      .map((item) => item.interactionId || ""),
  );
  for (const item of eventItems) {
    const key = item.interactionId || item.id || "";
    if (!key || !interactionIds.has(key)) {
      timelineView.push(item);
      if (key) interactionIds.add(key);
    }
  }
  if (currentInteraction && !interactionIds.has(currentInteraction.interaction_id || "")) {
    timelineView.push(
      toInteractionTimelineItem({
        id: currentInteraction.interaction_id,
        payload: currentInteraction,
        turnId: "",
        stepId: "",
        stepIndex: 0,
        projectionSource: "session_snapshot",
        projectionKind: "pending_interaction",
        synthetic: false,
      }),
    );
  }
  return {
    currentInteraction,
    transportView: {
      connectionState: eventLog?.connectionState || "connecting",
      needsResync: Boolean(eventLog?.needsResync),
      lastAppliedSeq: Number(eventLog?.lastAppliedSeq || 0),
    },
    sessionStatusView: {
      sessionId: snapshot?.session_id || "",
      status: snapshot?.status || "idle",
      mode: snapshot?.current_mode || "code",
    },
    timelineView,
  };
}
