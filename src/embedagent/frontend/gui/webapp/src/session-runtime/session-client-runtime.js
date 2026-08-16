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

const BOOTSTRAP_KEYS = new Set([
  "schema_version",
  "event_cursor",
  "thread",
  "snapshot",
  "history",
  "capabilities",
  "plan",
  "permission_context",
]);
const THREAD_KEYS = new Set([
  "id",
  "title",
  "archived",
  "current_mode",
  "status",
  "updated_at",
  "pending_interaction",
]);

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
  if (Object.keys(value).some((key) => !BOOTSTRAP_KEYS.has(key))) {
    throw new ProtocolError("invalid session bootstrap field");
  }
  if (value.schema_version !== 1) {
    throw new ProtocolError("unsupported session bootstrap schema");
  }
  if (!Number.isInteger(value.event_cursor) || value.event_cursor < 0) {
    throw new ProtocolError("invalid session bootstrap cursor");
  }
  if (!record(value.thread) || !record(value.snapshot)) {
    throw new ProtocolError("invalid session bootstrap projection");
  }
  if (Object.keys(value.thread).some((key) => !THREAD_KEYS.has(key))) {
    throw new ProtocolError("invalid session thread field");
  }
  if (
    typeof value.thread.id !== "string" ||
    typeof value.thread.title !== "string" ||
    typeof value.thread.archived !== "boolean" ||
    typeof value.thread.current_mode !== "string" ||
    typeof value.thread.status !== "string" ||
    typeof value.thread.updated_at !== "string" ||
    typeof value.thread.pending_interaction !== "boolean"
  ) {
    throw new ProtocolError("invalid session thread");
  }
  if (!record(value.history) || !Array.isArray(value.history.activities)) {
    throw new ProtocolError("invalid session bootstrap history");
  }
  if (!record(value.history.integrity) || !record(value.capabilities)) {
    throw new ProtocolError("invalid session bootstrap capabilities");
  }
  if (value.capabilities.schema_version !== 1) {
    throw new ProtocolError("invalid session capabilities schema");
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
  if (status === "error" || status === "failed") return "failed";
  if (
    bootstrap.thread.pending_interaction === true ||
    status === "waiting_permission" ||
    status === "waiting_user_input"
  ) {
    return "waiting_interaction";
  }
  return "ready";
}

function reduceTerminalOutcome(current, event, sessionId) {
  if (INTERACTION_FINISH_EVENTS.has(event.event_kind)) return null;
  if (INTERACTION_REQUEST_EVENTS.has(event.event_kind)) {
    return frozenCopy({
      kind: "terminal_outcome",
      session_id: sessionId,
      status: "blocked",
      final_text: "",
      outcome: {},
      failure: {
        code: "interaction_required",
        message: "session interaction is required",
        retryable: false,
        source: "session",
      },
    });
  }
  if (event.event_kind === "session.error") {
    const failure = record(event.payload?.failure)
      ? event.payload.failure
      : failureFor(new ProtocolError("session.error did not contain a valid failure"));
    return frozenCopy({
      kind: "terminal_outcome",
      session_id: sessionId,
      status: "failed",
      final_text: "",
      outcome: {},
      failure,
    });
  }
  if (event.event_kind !== "session.finished") return current;
  const outcome = record(event.payload?.outcome) ? event.payload.outcome : {};
  const reason = String(outcome.reason || event.payload?.termination_reason || "");
  let status = "failed";
  if (outcome.kind === "completed" || outcome.is_success === true) {
    status = "completed";
  } else if (outcome.kind === "blocked") {
    status = "blocked";
  } else if (
    outcome.kind === "cancelled" ||
    reason === "aborted" ||
    reason === "cancelled"
  ) {
    status = "cancelled";
  }
  let failure = null;
  if (status !== "completed") {
    const code = status === "blocked" ? "interaction_required" :
      status === "cancelled" ? "cancelled" : "runtime_error";
    const message = status === "blocked" ? "session is blocked" :
      status === "cancelled" ? "session was cancelled" : "session failed";
    failure = {
      code,
      message: String(outcome.message || message),
      retryable: false,
      source: "session",
    };
  }
  return frozenCopy({
    kind: "terminal_outcome",
    session_id: sessionId,
    status,
    final_text: String(event.payload?.final_text || ""),
    outcome,
    failure,
  });
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
    this.terminalOutcome = null;
    this.transactionBaseline = null;
  }

  async activateSession(reference, options = {}) {
    this.#assertOperable();
    const sessionId = requiredSessionId(reference);
    try {
      return await this.#runBootstrapTransaction(
        sessionId,
        options.reason || "activate",
        () => this.transport.loadSessionBootstrap(sessionId, options),
      );
    } catch {
      return null;
    }
  }

  async createSession(mode = "", options = {}) {
    return this.#runBootstrapTransaction(
      "",
      "create",
      () => this.transport.createSession(String(mode || ""), options),
    );
  }

  async setSessionMode(sessionId, mode, options = {}) {
    const selected = requiredSessionId(sessionId);
    return this.#runBootstrapTransaction(
      selected,
      "mode_changed",
      () => this.transport.setSessionMode(selected, String(mode || ""), options),
    );
  }

  async cancelSession(sessionId, options = {}) {
    const selected = requiredSessionId(sessionId);
    return this.#runBootstrapTransaction(
      selected,
      "cancel",
      () => this.transport.cancelSession(selected, options),
    );
  }

  async respondToInteraction(sessionId, interactionId, payload, options = {}) {
    const selected = requiredSessionId(sessionId);
    return this.#runBootstrapTransaction(
      selected,
      "interaction_response",
      () => this.transport.respondToInteraction(
        selected,
        String(interactionId || ""),
        payload || {},
        options,
      ),
    );
  }

  async acceptSessionEvent(envelope) {
    if (!isSessionEventEnvelope(envelope)) {
      throw new TypeError("invalid session event envelope");
    }
    if (this.lifecycle === "closed" || this.lifecycle === "failed") return;
    const event = frozenCopy(envelope);
    if (this.activating) {
      this.activationBuffer.push(event);
      return;
    }
    if (event.session_id !== this.sessionId) return;
    if (this.recovering) {
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
    this.#emit(this.#acceptContiguousEvent(event));
  }

  #acceptContiguousEvent(event) {
    this.cursor = event.sequence;
    this.#applyEventLifecycle(event.event_kind);
    this.terminalOutcome = reduceTerminalOutcome(
      this.terminalOutcome,
      event,
      this.sessionId,
    );
    return {
      kind: "session_event",
      event,
      lifecycle: this.lifecycle,
      generation: this.generation,
    };
  }

  close() {
    if (this.lifecycle === "closed") return;
    this.generation += 1;
    this.lifecycle = "closed";
    this.activating = false;
    this.recovering = false;
    this.activationBuffer = [];
    this.transactionBaseline = null;
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

  async #drainBufferedEvents(generation, sessionId) {
    while (true) {
      if (this.lifecycle === "closed" || generation !== this.generation) return false;
      const pending = this.activationBuffer
        .filter(
          (event) => event.session_id === sessionId && event.sequence > this.cursor,
        )
        .sort((left, right) => left.sequence - right.sequence);
      this.activationBuffer = pending;
      if (pending.length === 0) {
        this.activating = false;
        this.recovering = false;
        this.transactionBaseline = null;
        return true;
      }
      const event = pending[0];
      if (event.sequence !== this.cursor + 1) {
        if (this.recoveryAttempted) {
          this.#failGeneration(
            generation,
            sessionId,
            failureFor(
              new ProtocolError("session event sequence gap repeated after recovery"),
            ),
          );
          return true;
        }
        this.recoveryAttempted = true;
        this.activating = false;
        this.recovering = true;
        await this.#recoverGeneration(generation, sessionId);
        return true;
      }
      this.activationBuffer = pending.slice(1);
      this.#emit(this.#acceptContiguousEvent(event));
    }
  }

  async #installBootstrap(generation, sessionId, bootstrap, reason) {
    if (this.lifecycle === "closed" || generation !== this.generation) return false;
    const matching = this.activationBuffer
      .filter((event) => event.session_id === sessionId)
      .sort((left, right) => left.sequence - right.sequence);
    let terminalOutcome = null;
    for (const event of matching) {
      if (event.sequence <= bootstrap.event_cursor) {
        terminalOutcome = reduceTerminalOutcome(terminalOutcome, event, sessionId);
      }
    }
    this.sessionId = sessionId;
    this.cursor = bootstrap.event_cursor;
    this.lifecycle = lifecycleForBootstrap(bootstrap);
    this.terminalOutcome = terminalOutcome;
    this.activationBuffer = matching.filter(
      (event) => event.sequence > bootstrap.event_cursor,
    );
    this.#emit({
      kind: "session_activated",
      session_id: sessionId,
      cursor: this.cursor,
      generation,
      reason: String(reason || "activate"),
      bootstrap,
    });
    return this.#drainBufferedEvents(generation, sessionId);
  }

  #applyEventLifecycle(eventKind) {
    if (INTERACTION_REQUEST_EVENTS.has(eventKind)) {
      this.lifecycle = "waiting_interaction";
    } else if (INTERACTION_FINISH_EVENTS.has(eventKind)) {
      this.lifecycle = "ready";
    } else if (eventKind === "session.finished") {
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
    this.transactionBaseline = null;
    this.terminalOutcome = frozenCopy({
      kind: "terminal_outcome",
      session_id: sessionId,
      status: "failed",
      final_text: "",
      outcome: {},
      failure,
    });
    this.#emit({
      kind: "protocol_failed",
      session_id: sessionId,
      generation,
      failure,
    });
  }

  #beginBootstrapTransaction(targetSessionId) {
    this.#assertOperable();
    if (!this.transactionBaseline) {
      this.transactionBaseline = Object.freeze({
        sessionId: this.sessionId,
        cursor: this.cursor,
        lifecycle: this.lifecycle,
        recoveryAttempted: this.recoveryAttempted,
        terminalOutcome: this.terminalOutcome,
      });
    }
    this.generation += 1;
    this.sessionId = String(targetSessionId || "");
    this.cursor = 0;
    this.lifecycle = "activating";
    this.activating = true;
    this.recovering = false;
    this.recoveryAttempted = false;
    this.terminalOutcome = null;
    return this.generation;
  }

  async #rollbackBootstrapTransaction(generation) {
    if (this.lifecycle === "closed" || generation !== this.generation) return false;
    const baseline = this.transactionBaseline;
    if (!baseline) return false;
    this.sessionId = baseline.sessionId;
    this.cursor = baseline.cursor;
    this.lifecycle = baseline.lifecycle;
    this.activating = true;
    this.recovering = false;
    this.recoveryAttempted = baseline.recoveryAttempted;
    this.terminalOutcome = baseline.terminalOutcome;
    this.activationBuffer = this.activationBuffer.filter(
      (event) => event.session_id === baseline.sessionId,
    );
    return this.#drainBufferedEvents(generation, baseline.sessionId);
  }

  async #runBootstrapTransaction(targetSessionId, reason, request) {
    const generation = this.#beginBootstrapTransaction(targetSessionId);
    let value;
    try {
      value = await request();
    } catch (error) {
      await this.#rollbackBootstrapTransaction(generation);
      throw error;
    }
    let sessionId;
    let bootstrap;
    try {
      sessionId = targetSessionId || requiredSessionId(value?.thread?.id);
      bootstrap = validateBootstrap(value, sessionId);
    } catch (error) {
      this.#failGeneration(generation, String(targetSessionId || ""), failureFor(error));
      throw error;
    }
    return (await this.#installBootstrap(generation, sessionId, bootstrap, reason))
      ? bootstrap
      : null;
  }

  #assertOperable() {
    if (this.lifecycle === "closed") throw new Error("runtime_closed");
    if (this.lifecycle === "failed") throw new Error("runtime_failed");
  }

  #emit(action) {
    this.dispatch(frozenCopy(action));
  }
}
