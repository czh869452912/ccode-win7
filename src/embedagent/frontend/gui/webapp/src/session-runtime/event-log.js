const VALID_REPLAY_STATES = new Set(["healthy", "replay_needed", "reload_required", "degraded"]);

function normalizeReplayState(value, fallback = "healthy") {
  const candidate = String(value || "").trim();
  if (candidate === "replay") return "healthy";
  if (VALID_REPLAY_STATES.has(candidate)) return candidate;
  return fallback;
}

export function createSessionEventLog(options = {}) {
  return {
    events: [],
    eventIds: new Set(),
    lastAppliedSeq: 0,
    replayState: normalizeReplayState(options.replayState),
    connectionState: options.connectionState || "connecting",
  };
}

export function capRetryAttempt(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(Math.max(numeric, 0), 20);
}

export function appendSessionEvent(log, event) {
  if (!event || !event.event_id) return log;
  if (!event.event_kind || typeof event.payload !== "object" || event.payload === null) {
    return {
      ...log,
      replayState: "degraded",
    };
  }
  if (log.eventIds.has(event.event_id)) return log;
  const seq = Number(event.seq || 0);
  if (log.lastAppliedSeq && seq !== log.lastAppliedSeq + 1) {
    return {
      ...log,
      replayState: "replay_needed",
    };
  }
  const eventIds = new Set(log.eventIds);
  eventIds.add(event.event_id);
  return {
    ...log,
    events: log.events.concat(event),
    eventIds,
    lastAppliedSeq: seq || log.lastAppliedSeq,
  };
}
