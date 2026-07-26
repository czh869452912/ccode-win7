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

function application(state, accepted, reason = "") {
  return { state, accepted, reason };
}

function validEnvelope(event) {
  if (!event || typeof event !== "object") return false;
  if (!Number.isInteger(event.schema_version) || event.schema_version <= 0) return false;
  if (!String(event.event_id || "").trim()) return false;
  if (!String(event.session_id || "").trim()) return false;
  if (!Number.isInteger(event.sequence) || event.sequence <= 0) return false;
  if (!String(event.event_kind || "").trim()) return false;
  if (!String(event.timestamp || "").trim()) return false;
  if (
    typeof event.payload !== "object" ||
    event.payload === null ||
    Array.isArray(event.payload)
  ) {
    return false;
  }
  return true;
}

export function applySessionTransportEvent(state, event) {
  if (!validEnvelope(event)) {
    return application(
      {
        ...state,
        reloadState: "degraded",
      },
      false,
      "invalid_envelope",
    );
  }
  if (state.eventIds.has(event.event_id)) {
    return application(state, false, "duplicate_event");
  }
  if (state.lastAppliedSeq && event.sequence !== state.lastAppliedSeq + 1) {
    return application(
      {
        ...state,
        reloadState: "reload_required",
      },
      false,
      "sequence_gap",
    );
  }
  const eventIds = new Set(state.eventIds);
  eventIds.add(event.event_id);
  return application(
    {
      ...state,
      events: state.events.concat(event),
      eventIds,
      lastAppliedSeq: event.sequence,
    },
    true,
  );
}

export function projectTransportView({ transportState } = {}) {
  return {
    connectionState: transportState?.connectionState || "connecting",
    reloadState: normalizeReloadState(transportState?.reloadState, "healthy"),
    lastAppliedSeq: Number(transportState?.lastAppliedSeq || 0),
  };
}
