export function createSessionEventLog() {
  return {
    events: [],
    eventIds: new Set(),
    lastAppliedSeq: 0,
    needsResync: false,
    connectionState: "connecting",
  };
}

export function appendSessionEvent(log, event) {
  if (!event || !event.event_id) return log;
  if (!event.event_kind || typeof event.payload !== "object" || event.payload === null) {
    return {
      ...log,
      needsResync: true,
    };
  }
  if (log.eventIds.has(event.event_id)) return log;
  const seq = Number(event.seq || 0);
  if (log.lastAppliedSeq && seq !== log.lastAppliedSeq + 1) {
    return {
      ...log,
      needsResync: true,
    };
  }
  const eventIds = new Set(log.eventIds);
  eventIds.add(event.event_id);
  return {
    ...log,
    events: log.events.concat(event),
    eventIds,
    lastAppliedSeq: seq,
  };
}
