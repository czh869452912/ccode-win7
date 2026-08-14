import { isSessionEventEnvelope } from "./session-transport-state.js";

const INTERACTION_REQUEST_EVENTS = new Set([
  "approval.requested",
  "user-input.requested",
]);
const INTERACTION_FINISH_EVENTS = new Set([
  "approval.resolved",
  "approval.response.failed",
  "user-input.resolved",
  "user-input.response.failed",
]);

class ProtocolError extends Error {}

function record(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function requiredSessionId(value) {
  if (typeof value !== "string" || !value.trim()) {
    throw new TypeError("session_id is required");
  }
  return value.trim();
}

function deepClone(value) {
  if (Array.isArray(value)) return value.map(deepClone);
  if (!record(value)) return value;
  const result = {};
  for (const [key, child] of Object.entries(value)) result[key] = deepClone(child);
  return result;
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

function frozenCopy(value) {
  return deepFreeze(deepClone(value));
}

function validateBootstrap(value, sessionId) {
  if (!record(value)) throw new ProtocolError("invalid session bootstrap");
  if (value.schema_version !== 1) {
    throw new ProtocolError("unsupported session bootstrap schema");
  }
  if (!Number.isInteger(value.event_cursor) || value.event_cursor < 0) {
    throw new ProtocolError("invalid session bootstrap cursor");
  }
  if (!record(value.thread) || !record(value.snapshot)) {
    throw new ProtocolError("invalid session bootstrap projection");
  }
  if (!record(value.history) || !Array.isArray(value.history.activities)) {
    throw new ProtocolError("invalid session bootstrap history");
  }
  if (!record(value.history.integrity) || !record(value.capabilities)) {
    throw new ProtocolError("invalid session bootstrap capabilities");
  }
  if (value.plan !== null && !record(value.plan)) {
    throw new ProtocolError("invalid session bootstrap plan");
  }
  if (!record(value.permission_context)) {
    throw new ProtocolError("invalid session bootstrap permission context");
  }
  if (value.thread.id !== sessionId || value.snapshot.session_id !== sessionId) {
    throw new ProtocolError("session bootstrap id mismatch");
  }
  return frozenCopy(value);
}

function failureFor(error) {
  return {
    code: error instanceof ProtocolError ? "protocol_error" : String(error?.code || "runtime_error"),
    message: String(error?.message || error || "session runtime failed"),
    retryable: false,
    source: error instanceof ProtocolError ? "client_runtime" : "session",
  };
}

function lifecycleForBootstrap(bootstrap) {
  const status = String(bootstrap.snapshot.status || "");
  if (
    bootstrap.thread.pending_interaction === true ||
    status === "waiting_permission" ||
    status === "waiting_user_input"
  ) {
    return "waiting_interaction";
  }
  return "ready";
}

export class SessionClientRuntime {
  constructor({ transport, dispatch } = {}) {
    if (!transport || typeof transport.loadSessionBootstrap !== "function") {
      throw new TypeError("transport.loadSessionBootstrap is required");
    }
    if (dispatch !== undefined && typeof dispatch !== "function") {
      throw new TypeError("dispatch must be callable");
    }
    this.transport = transport;
    this.dispatch = dispatch || (() => {});
    this.sessionId = "";
    this.cursor = 0;
    this.generation = 0;
    this.activationBuffer = [];
    this.lifecycle = "idle";
    this.activating = false;
    this.recovering = false;
    this.recoveryAttempted = false;
  }

  async activateSession(reference, options = {}) {
    this.#assertOperable();
    const sessionId = requiredSessionId(reference);
    this.generation += 1;
    const generation = this.generation;
    this.sessionId = sessionId;
    this.cursor = 0;
    this.lifecycle = "activating";
    this.activating = true;
    this.recovering = false;
    this.recoveryAttempted = false;
    this.activationBuffer = [];
    try {
      const bootstrap = await this.transport.loadSessionBootstrap(sessionId, options);
      const validated = validateBootstrap(bootstrap, sessionId);
      return (await this.#installBootstrap(
        generation,
        sessionId,
        validated,
        options.reason || "activate",
      ))
        ? validated
        : null;
    } catch (error) {
      this.#failGeneration(generation, sessionId, failureFor(error));
      return null;
    }
  }

  async acceptSessionEvent(envelope) {
    if (!isSessionEventEnvelope(envelope)) {
      throw new TypeError("invalid session event envelope");
    }
    if (this.lifecycle === "closed" || this.lifecycle === "failed") return;
    if (envelope.session_id !== this.sessionId) return;
    const event = frozenCopy(envelope);
    if (this.activating || this.recovering) {
      this.activationBuffer.push(event);
      return;
    }
    if (event.sequence <= this.cursor) return;
    if (event.sequence !== this.cursor + 1) {
      if (this.recoveryAttempted) {
        this.#failGeneration(
          this.generation,
          this.sessionId,
          failureFor(new ProtocolError("session event sequence gap repeated after recovery")),
        );
        return;
      }
      this.recoveryAttempted = true;
      this.recovering = true;
      this.activationBuffer.push(event);
      await this.#recoverGeneration(this.generation, this.sessionId);
      return;
    }
    this.cursor = event.sequence;
    this.#applyEventLifecycle(event.event_kind);
    this.#emit({
      kind: "session_event",
      event,
      lifecycle: this.lifecycle,
      generation: this.generation,
    });
  }

  close() {
    if (this.lifecycle === "closed") return;
    this.generation += 1;
    this.lifecycle = "closed";
    this.activating = false;
    this.recovering = false;
    this.activationBuffer = [];
    if (typeof this.transport.close === "function") this.transport.close();
    this.#emit({ kind: "runtime_closed" });
  }

  async #recoverGeneration(generation, sessionId) {
    try {
      const bootstrap = await this.transport.loadSessionBootstrap(sessionId, { reason: "recovery" });
      const validated = validateBootstrap(bootstrap, sessionId);
      await this.#installBootstrap(generation, sessionId, validated, "recovery");
    } catch (error) {
      this.#failGeneration(generation, sessionId, failureFor(error));
    }
  }

  async #installBootstrap(generation, sessionId, bootstrap, reason) {
    if (this.lifecycle === "closed" || generation !== this.generation) return false;
    this.cursor = bootstrap.event_cursor;
    this.lifecycle = lifecycleForBootstrap(bootstrap);
    this.activating = false;
    this.recovering = false;
    const buffered = this.activationBuffer
      .slice()
      .sort((left, right) => left.sequence - right.sequence);
    this.activationBuffer = [];
    this.#emit({
      kind: "session_activated",
      session_id: sessionId,
      cursor: this.cursor,
      generation,
      reason: String(reason || "activate"),
      bootstrap,
    });
    for (const event of buffered) await this.acceptSessionEvent(event);
    return true;
  }

  #applyEventLifecycle(eventKind) {
    if (INTERACTION_REQUEST_EVENTS.has(eventKind)) {
      this.lifecycle = "waiting_interaction";
    } else if (INTERACTION_FINISH_EVENTS.has(eventKind)) {
      this.lifecycle = "ready";
    } else if (eventKind === "session.error") {
      this.lifecycle = "failed";
    }
  }

  #failGeneration(generation, sessionId, failure) {
    if (this.lifecycle === "closed" || generation !== this.generation) return;
    this.lifecycle = "failed";
    this.activating = false;
    this.recovering = false;
    this.activationBuffer = [];
    this.#emit({
      kind: "protocol_failed",
      session_id: sessionId,
      generation,
      failure,
    });
  }

  #assertOperable() {
    if (this.lifecycle === "closed") throw new Error("runtime_closed");
    if (this.lifecycle === "failed") throw new Error("runtime_failed");
  }

  #emit(action) {
    this.dispatch(frozenCopy(action));
  }
}
