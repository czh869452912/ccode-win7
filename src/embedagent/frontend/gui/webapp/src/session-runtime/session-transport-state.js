const VALID_RELOAD_STATES = new Set(["healthy", "reload_required", "degraded"]);

function normalizeReloadState(value, fallback = "healthy") {
  const candidate = String(value || "").trim();
  if (VALID_RELOAD_STATES.has(candidate)) return candidate;
  return fallback;
}

export function createSessionTransportState(options = {}) {
  const eventCursor = Number(options.eventCursor || 0);
  return {
    sessionId: String(options.sessionId || ""),
    generation: Number(options.generation || 0),
    phase: options.phase || "idle",
    bufferedEvents: [],
    events: [],
    eventIds: new Set(),
    lastAppliedSeq: Number.isInteger(eventCursor) && eventCursor >= 0 ? eventCursor : 0,
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
  if (state.sessionId && event.session_id !== state.sessionId) {
    return application(state, false, "wrong_session");
  }
  if (state.eventIds.has(event.event_id)) {
    return application(state, false, "duplicate_event");
  }
  if (event.sequence <= state.lastAppliedSeq) {
    return application(state, false, "stale_sequence");
  }
  if (event.sequence !== state.lastAppliedSeq + 1) {
    const bufferedEvents = state.bufferedEvents.some(
      (item) => item.event_id === event.event_id,
    )
      ? state.bufferedEvents
      : state.bufferedEvents.concat(event);
    return application(
      {
        ...state,
        bufferedEvents,
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

export function beginSessionTransportBootstrap(state, sessionId) {
  const current = state || createSessionTransportState();
  const resolvedSessionId = String(sessionId || "");
  const bufferedEvents =
    current.sessionId === resolvedSessionId ? current.bufferedEvents.slice() : [];
  return {
    ...createSessionTransportState({
      sessionId: resolvedSessionId,
      phase: "buffering",
      connectionState: current.connectionState,
    }),
    bufferedEvents,
    generation: Number(current.generation || 0) + 1,
  };
}

export function bufferSessionTransportEvent(state, event) {
  if (!validEnvelope(event)) {
    return {
      ...state,
      reloadState: "degraded",
    };
  }
  if (state.phase !== "buffering" || event.session_id !== state.sessionId) {
    return state;
  }
  if (
    state.eventIds.has(event.event_id) ||
    state.bufferedEvents.some((item) => item.event_id === event.event_id)
  ) {
    return state;
  }
  return {
    ...state,
    bufferedEvents: state.bufferedEvents.concat(event),
  };
}

export function installSessionTransportBootstrap(state, options = {}) {
  const sessionId = String(options.sessionId || "");
  const generation = Number(options.generation || 0);
  if (
    state.phase !== "buffering" ||
    state.sessionId !== sessionId ||
    state.generation !== generation
  ) {
    return { state, applied: [], stale: true };
  }

  const eventCursor = Number(options.eventCursor || 0);
  if (!Number.isInteger(eventCursor) || eventCursor < 0) {
    return {
      state: { ...state, phase: "live", reloadState: "degraded" },
      applied: [],
      stale: false,
    };
  }

  let current = {
    ...state,
    phase: "live",
    bufferedEvents: [],
    events: [],
    eventIds: new Set(),
    lastAppliedSeq: eventCursor,
    reloadState: state.reloadState === "degraded" ? "degraded" : "healthy",
  };
  const candidates = state.bufferedEvents
    .filter((event) => event.session_id === sessionId)
    .sort((left, right) => left.sequence - right.sequence);
  const applied = [];
  const remaining = [];
  const seenEventIds = new Set();

  for (let index = 0; index < candidates.length; index += 1) {
    const event = candidates[index];
    if (seenEventIds.has(event.event_id)) continue;
    seenEventIds.add(event.event_id);
    if (event.sequence <= eventCursor) continue;
    const result = applySessionTransportEvent(current, event);
    current = result.state;
    if (result.accepted) {
      applied.push(event);
      continue;
    }
    if (result.reason === "sequence_gap") {
      remaining.push(event);
      for (const pending of candidates.slice(index + 1)) {
        if (!seenEventIds.has(pending.event_id)) {
          seenEventIds.add(pending.event_id);
          remaining.push(pending);
        }
      }
      break;
    }
  }

  return {
    state: { ...current, bufferedEvents: remaining },
    applied,
    stale: false,
  };
}

export function projectTransportView({ transportState } = {}) {
  return {
    connectionState: transportState?.connectionState || "connecting",
    reloadState: normalizeReloadState(transportState?.reloadState, "healthy"),
    lastAppliedSeq: Number(transportState?.lastAppliedSeq || 0),
  };
}
