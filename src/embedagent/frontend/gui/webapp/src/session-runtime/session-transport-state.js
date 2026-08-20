import { FRONTEND_PROTOCOL_SCHEMA_VERSION } from "./protocol-version.js";
import { normalizeSessionEventEnvelope } from "./protocol-envelope.js";

const VALID_RELOAD_STATES = new Set(["healthy", "reload_required", "degraded"]);

function normalizeReloadState(value, fallback = "healthy") {
  const candidate = String(value || "").trim();
  return VALID_RELOAD_STATES.has(candidate) ? candidate : fallback;
}

export function createSessionTransportState(options = {}) {
  const eventCursor = Number(options.eventCursor || options.lastAppliedSeq || 0);
  return {
    sessionId: String(options.sessionId || ""),
    generation: Number(options.generation || 0),
    phase: options.phase || "idle",
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

export function isSessionEventEnvelope(event) {
  try {
    normalizeSessionEventEnvelope(event);
    return true;
  } catch {
    return false;
  }
}

export function projectTransportView({ transportState } = {}) {
  return {
    connectionState: transportState?.connectionState || "connecting",
    reloadState: normalizeReloadState(transportState?.reloadState, "healthy"),
    lastAppliedSeq: Number(transportState?.lastAppliedSeq || 0),
  };
}
