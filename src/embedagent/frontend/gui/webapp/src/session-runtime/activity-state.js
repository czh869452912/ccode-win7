import { projectTransportView } from "./session-transport-state.js";
import { currentInteractionFromActivities } from "./interaction-model.js";
import {
  buildInteractionNotice,
  currentInteractionFromSnapshot,
  normalizeHistoryActivities,
  projectActivityTurnGroups,
} from "./timeline/activity-grouping.js";
import { buildActivityTimelineRows } from "./timeline/activity-timeline.js";

export function buildSessionActivityRuntime({
  snapshot,
  sessionTransport,
  activities = [],
  defaultMode = "",
  activeTurnId = "",
  thinkingActive = false,
  toolCatalog = {},
} = {}) {
  const timelineItems = normalizeHistoryActivities(activities);
  const activityInteraction = currentInteractionFromActivities(timelineItems);
  const currentInteraction = currentInteractionFromSnapshot(snapshot) || activityInteraction;
  const interactionNotice = buildInteractionNotice(snapshot, currentInteraction);
  const timelineView = projectActivityTurnGroups(timelineItems);
  return {
    currentInteraction,
    interactionNotice,
    transportView: projectTransportView({ transportState: sessionTransport }),
    sessionStatusView: {
      sessionId: snapshot?.session_id || "",
      status: snapshot?.status || "idle",
      mode: snapshot?.current_mode || defaultMode,
    },
    timelineItems,
    timelineView,
    timelineRows: buildActivityTimelineRows({
      turnGroups: timelineView,
      currentStatus: snapshot?.status || "idle",
      activeTurnId: activeTurnId || snapshot?.active_turn_id || "",
      currentInteraction,
      interactionNotice,
      thinkingActive,
      turnExperience: snapshot?.turnExperience || snapshot?.turn_experience || null,
      toolCatalog,
    }),
  };
}
