import assert from "node:assert/strict";

import { createSessionActivationController } from "../src/app-runtime/session-activation-controller.js";
import { createSessionTransportController } from "../src/app-runtime/session-transport-controller.js";
import { createSessionTransportState } from "../src/session-runtime/session-transport-state.js";

function createSocketHarness() {
  const sockets = [];
  return {
    sockets,
    factory(url) {
      const socket = {
        url,
        closeCalls: 0,
        close() {
          this.closeCalls += 1;
          if (typeof this.onclose === "function") {
            this.onclose({});
          }
        },
      };
      sockets.push(socket);
      return socket;
    },
  };
}

export async function runSessionTransportControllerTests() {
  const harness = createSocketHarness();
  const scheduled = [];
  const loadedSessions = [];
  const messages = [];
  let transport = createSessionTransportState({
    connectionState: "connecting",
    reloadState: "reload_required",
  });
  const controller = createSessionTransportController({
    getCurrentSessionId: () => "sess-transport",
    getTransportState: () => transport,
    updateTransportState: (updater) => {
      transport = updater(transport);
      return transport;
    },
    loadSession: async (sessionId) => {
      loadedSessions.push(sessionId);
      transport = {
        ...transport,
        connectionState: "connected",
        reloadState: "healthy",
      };
    },
    handleMessage: (message) => {
      messages.push(message);
    },
    socketFactory: harness.factory,
    locationObject: { protocol: "http:", host: "127.0.0.1:3000" },
    timer: {
      setTimeout(callback, delay) {
        scheduled.push({ callback, delay });
        return scheduled.length;
      },
    },
  });

  controller.connect();
  assert.equal(harness.sockets[0].url, "ws://127.0.0.1:3000/ws");
  await harness.sockets[0].onopen();
  assert.deepEqual(loadedSessions, ["sess-transport"]);
  assert.equal(transport.connectionState, "connected");
  assert.equal(transport.reloadState, "healthy");

  harness.sockets[0].onmessage({
    data: JSON.stringify({ type: "session_event", data: { sequence: 1 } }),
  });
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
  assert.equal(application.state.lastAppliedSeq, 1);
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
  assert.equal(application.state.reloadState, "reload_required");
  assert.equal(application.accepted, false);
  await controller.recover("sess-transport", application.state);
  assert.equal(loadedSessions.length, 2);
  assert.equal(transport.reloadState, "healthy");

  const recoveredEvents = [];
  let recoveryTransport = createSessionTransportState({
    sessionId: "sess-recovery",
    phase: "live",
    eventCursor: 1,
    connectionState: "connected",
  });
  const activateRecovery = createSessionActivationController({
    fetchJson: async () => ({
      event_cursor: 2,
      snapshot: {
        session_id: "sess-recovery",
        status: "running",
        current_mode: "build",
      },
      history: { activities: [], integrity: { status: "healthy" } },
      capabilities: {},
    }),
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
    getTransportState: () => recoveryTransport,
    updateTransportState: (updater) => {
      recoveryTransport = updater(recoveryTransport);
      return recoveryTransport;
    },
    loadSession: activateRecovery,
  });
  const recoveryGap = recoveryController.applyEvent({
    schema_version: 1,
    session_id: "sess-recovery",
    event_id: "evt-recovery-3",
    sequence: 3,
    event_kind: "step.started",
    timestamp: "2026-08-03T00:00:03Z",
    payload: { step_id: "step-3" },
  });
  assert.equal(recoveryGap.reason, "sequence_gap");
  const firstRecovery = recoveryController.recover("sess-recovery");
  const repeatedRecovery = recoveryController.recover("sess-recovery");
  assert.equal(firstRecovery, repeatedRecovery);
  await firstRecovery;
  assert.equal(recoveryTransport.lastAppliedSeq, 3);
  assert.equal(recoveryTransport.reloadState, "healthy");
  assert.deepEqual(recoveredEvents.map((event) => event.sequence), [3]);

  harness.sockets[0].onmessage({ data: "{bad json" });
  assert.equal(transport.connectionState, "degraded");
  assert.equal(transport.reloadState, "degraded");

  harness.sockets[0].onclose();
  assert.equal(transport.connectionState, "disconnected");
  assert.equal(scheduled[0].delay, 1500);
  scheduled[0].callback();
  assert.equal(harness.sockets.length, 2);

  const scheduleCount = scheduled.length;
  controller.close();
  assert.equal(harness.sockets[1].closeCalls, 1);
  assert.equal(scheduled.length, scheduleCount);

  const secureHarness = createSocketHarness();
  const secureController = createSessionTransportController({
    updateTransportState: (updater) => {
      transport = updater(transport);
      return transport;
    },
    socketFactory: secureHarness.factory,
    locationObject: { protocol: "https:", host: "example.test" },
    timer: { setTimeout() {} },
  });
  secureController.connect();
  assert.equal(secureHarness.sockets[0].url, "wss://example.test/ws");
}
