import assert from "node:assert/strict";

import { createSessionActivationController } from "../src/app-runtime/session-activation-controller.js";
import { createSessionTransportController } from "../src/app-runtime/session-transport-controller.js";
import { createSessionTransportState } from "../src/session-runtime/session-transport-state.js";

function createChannelHarness() {
  const channels = [];
  const protocol = {
    openSessionEvents() {
      const messageListeners = new Set();
      const stateListeners = new Set();
      const channel = {
        closeCalls: 0,
        onMessage(listener) {
          messageListeners.add(listener);
          return () => messageListeners.delete(listener);
        },
        onStateChange(listener) {
          stateListeners.add(listener);
          listener("connecting");
          return () => stateListeners.delete(listener);
        },
        send() {},
        close() {
          this.closeCalls += 1;
          return this.emitState("closed");
        },
        emitMessage(message) {
          for (const listener of [...messageListeners]) listener(message);
        },
        async emitState(state) {
          await Promise.all([...stateListeners].map((listener) => listener(state)));
        },
        messageListenerCount() {
          return messageListeners.size;
        },
        stateListenerCount() {
          return stateListeners.size;
        },
      };
      channels.push(channel);
      return channel;
    },
  };
  return { channels, protocol };
}

function createFakeClock() {
  return {
    callbacks: new Map(),
    nextId: 1,
    setTimeout(callback) {
      const id = this.nextId;
      this.nextId += 1;
      this.callbacks.set(id, callback);
      return id;
    },
    clearTimeout(id) {
      this.callbacks.delete(id);
    },
  };
}

export async function runSessionTransportControllerTests() {
  const harness = createChannelHarness();
  const scheduled = [];
  const loadedSessions = [];
  const messages = [];
  let transport = createSessionTransportState({
    connectionState: "connecting",
    reloadState: "reload_required",
  });
  const controller = createSessionTransportController({
    protocol: harness.protocol,
    getCurrentSessionId: () => "sess-transport",
    getTransportState: () => transport,
    updateTransportState: (updater) => {
      transport = updater(transport);
      return transport;
    },
    loadSession: async (sessionId) => {
      loadedSessions.push(sessionId);
      transport = { ...transport, connectionState: "connected", reloadState: "healthy" };
    },
    handleMessage: (message) => messages.push(message),
    timer: {
      setTimeout(callback, delay) {
        scheduled.push({ callback, delay });
        return scheduled.length;
      },
      clearTimeout() {},
    },
  });

  controller.connect();
  assert.equal(harness.channels.length, 1);
  await harness.channels[0].emitState("open");
  assert.deepEqual(loadedSessions, ["sess-transport"]);
  assert.equal(transport.reloadState, "healthy");

  harness.channels[0].emitMessage({ type: "session_event", data: { sequence: 1 } });
  assert.deepEqual(messages, [{ type: "session_event", data: { sequence: 1 } }]);

  let application = controller.applyEvent({
    schema_version: 1,
    session_id: "sess-transport",
    event_id: "evt-1",
    sequence: 1,
    event_kind: "turn.started",
    timestamp: "2026-06-26T00:00:00Z",
    payload: { turn_id: "turn-1" },
  });
  assert.equal(application.accepted, true);
  application = controller.applyEvent({
    schema_version: 1,
    session_id: "sess-transport",
    event_id: "evt-3",
    sequence: 3,
    event_kind: "step.started",
    timestamp: "2026-06-26T00:00:01Z",
    payload: { turn_id: "turn-1", step_id: "step-1" },
  });
  assert.equal(application.reason, "sequence_gap");
  await controller.recover("sess-transport");
  assert.equal(loadedSessions.length, 2);

  await harness.channels[0].emitState("error");
  assert.equal(transport.connectionState, "degraded");
  assert.equal(transport.reloadState, "reload_required");

  await harness.channels[0].emitState("closed");
  assert.equal(transport.connectionState, "disconnected");
  assert.equal(scheduled[0].delay, 1500);
  scheduled[0].callback();
  assert.equal(harness.channels.length, 2);

  const scheduleCount = scheduled.length;
  controller.close();
  assert.equal(harness.channels[1].closeCalls, 1);
  assert.equal(scheduled.length, scheduleCount);
  assert.equal(harness.channels[1].messageListenerCount(), 0);
  assert.equal(harness.channels[1].stateListenerCount(), 0);

  const recoveredEvents = [];
  let recoveryTransport = createSessionTransportState({
    sessionId: "sess-recovery",
    phase: "live",
    eventCursor: 1,
    connectionState: "connected",
  });
  const activateRecovery = createSessionActivationController({
    protocol: {
      loadSessionBootstrap: async () => ({
        event_cursor: 2,
        snapshot: { session_id: "sess-recovery", status: "running", current_mode: "build" },
        history: { activities: [], integrity: { status: "healthy" } },
        capabilities: {},
      }),
    },
    dispatch: () => {},
    getTransportState: () => recoveryTransport,
    updateTransportState: (updater) => {
      recoveryTransport = updater(recoveryTransport);
      return recoveryTransport;
    },
    dispatchAcceptedSessionEvent: (event) => recoveredEvents.push(event),
    getAppCapabilities: () => ({ terminal: { enabled: false } }),
  });
  const recoveryController = createSessionTransportController({
    protocol: createChannelHarness().protocol,
    getTransportState: () => recoveryTransport,
    updateTransportState: (updater) => {
      recoveryTransport = updater(recoveryTransport);
      return recoveryTransport;
    },
    loadSession: activateRecovery,
  });
  recoveryController.applyEvent({
    schema_version: 1,
    session_id: "sess-recovery",
    event_id: "evt-recovery-3",
    sequence: 3,
    event_kind: "step.started",
    timestamp: "2026-08-03T00:00:03Z",
    payload: { step_id: "step-3" },
  });
  const firstRecovery = recoveryController.recover("sess-recovery");
  assert.equal(firstRecovery, recoveryController.recover("sess-recovery"));
  await firstRecovery;
  assert.equal(recoveryTransport.lastAppliedSeq, 3);
  assert.deepEqual(recoveredEvents.map((event) => event.sequence), [3]);

  const shutdownHarness = createChannelHarness();
  const shutdownClock = createFakeClock();
  let shutdownTransport = createSessionTransportState({ reloadState: "reload_required" });
  let finishBootstrap;
  const bootstrapPromise = new Promise((resolve) => {
    finishBootstrap = resolve;
  });
  let bootstrapAbortCalls = 0;
  const loadShutdownSession = () => bootstrapPromise;
  loadShutdownSession.abort = () => {
    bootstrapAbortCalls += 1;
  };
  const shutdownController = createSessionTransportController({
    protocol: shutdownHarness.protocol,
    getCurrentSessionId: () => "sess-shutdown",
    getTransportState: () => shutdownTransport,
    updateTransportState: (updater) => {
      shutdownTransport = updater(shutdownTransport);
      return shutdownTransport;
    },
    loadSession: loadShutdownSession,
    timer: shutdownClock,
  });
  shutdownController.connect();
  const opening = shutdownHarness.channels[0].emitState("open");
  await Promise.resolve();
  shutdownController.close();
  assert.equal(shutdownHarness.channels[0].closeCalls, 1);
  assert.equal(shutdownClock.callbacks.size, 0);
  assert.equal(bootstrapAbortCalls, 1);
  finishBootstrap();
  await opening;

  assert.throws(
    () => createSessionTransportController({ protocol: {} }),
    /protocol_method_missing:openSessionEvents/,
  );
}
