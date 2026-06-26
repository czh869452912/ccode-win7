const VALID_RELOAD_STATES = new Set(["healthy", "reload_required", "degraded"]);

function normalizeReloadState(value, fallback = "healthy") {
  const candidate = String(value || "").trim();
  if (VALID_RELOAD_STATES.has(candidate)) return candidate;
  return fallback;
}

export function createSessionTransportState(options = {}) {
  return {
    events: [],
    eventIds: new Set(),
    lastAppliedSeq: 0,
    reloadState: normalizeReloadState(options.reloadState),
    connectionState: options.connectionState || "connecting",
  };
}

export function capRetryAttempt(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(Math.max(numeric, 0), 20);
}

export function appendSessionTransportEvent(state, event) {
  if (!event || !event.event_id) return state;
  if (!event.event_kind || typeof event.payload !== "object" || event.payload === null) {
    return {
      ...state,
      reloadState: "degraded",
    };
  }
  if (state.eventIds.has(event.event_id)) return state;
  const seq = Number(event.seq || 0);
  if (state.lastAppliedSeq && seq !== state.lastAppliedSeq + 1) {
    return {
      ...state,
      reloadState: "reload_required",
    };
  }
  const eventIds = new Set(state.eventIds);
  eventIds.add(event.event_id);
  return {
    ...state,
    events: state.events.concat(event),
    eventIds,
    lastAppliedSeq: seq || state.lastAppliedSeq,
  };
}

export function projectTransportView({ transportState } = {}) {
  return {
    connectionState: transportState?.connectionState || "connecting",
    reloadState: normalizeReloadState(transportState?.reloadState, "healthy"),
    lastAppliedSeq: Number(transportState?.lastAppliedSeq || 0),
  };
}
