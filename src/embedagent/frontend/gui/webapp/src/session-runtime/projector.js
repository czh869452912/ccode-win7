export function projectSessionRuntime({ snapshot, eventLog }) {
  return {
    currentInteraction:
      snapshot?.pending_interaction && snapshot.pending_interaction.status !== "resolved"
        ? snapshot.pending_interaction
        : null,
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
    timelineView: [],
  };
}
