import assert from "node:assert/strict";

import { createSessionTransportController } from "../src/app-runtime/session-transport-controller.js";
import { createSessionTransportState } from "../src/session-runtime/session-transport-state.js";

function channelHarness() {
  let messageListener = () => {};
  let stateListener = () => {};
  let closeCalls = 0;
  return {
    channel: {
      onMessage(callback) { messageListener = callback; return () => { messageListener = () => {}; }; },
      onStateChange(callback) { stateListener = callback; return () => { stateListener = () => {}; }; },
      close() { closeCalls += 1; },
    },
    emitMessage(message) { messageListener(message); },
    emitState(state) { return stateListener(state); },
    closeCalls() { return closeCalls; },
  };
}

export async function runSessionTransportControllerTests() {
  const channels = [];
  const messages = [];
  const reloads = [];
  const timers = new Map();
  let nextTimerId = 1;
  let transport = createSessionTransportState();
  const controller = createSessionTransportController({
    protocol: {
      openSessionEvents() {
        const harness = channelHarness();
        channels.push(harness);
        return harness.channel;
      },
    },
    getCurrentSessionId: () => "session-1",
    getTransportState: () => transport,
    updateTransportState(updater) {
      transport = updater(transport);
      return transport;
    },
    loadSession: async (...args) => reloads.push(args),
    handleMessage: (message) => messages.push(message),
    timer: {
      setTimeout(callback) {
        const id = nextTimerId;
        nextTimerId += 1;
        timers.set(id, callback);
        return id;
      },
      clearTimeout(id) { timers.delete(id); },
    },
  });

  assert.deepEqual(Object.keys(controller).sort(), ["close", "connect"]);
  controller.connect();
  channels[0].emitMessage({ type: "terminal_event", data: {} });
  assert.equal(messages.length, 1);
  await channels[0].emitState("open");
  assert.equal(transport.connectionState, "connected");
  assert.deepEqual(reloads, []);

  await channels[0].emitState("error");
  assert.equal(transport.connectionState, "degraded");
  assert.equal(transport.reloadState, "reload_required");
  await channels[0].emitState("closed");
  assert.equal(transport.connectionState, "disconnected");
  assert.equal(timers.size, 1);

  const [retryTimerId, reconnect] = [...timers.entries()][0];
  timers.delete(retryTimerId);
  reconnect();
  assert.equal(channels.length, 2);
  await channels[1].emitState("open");
  assert.deepEqual(reloads, [["session-1", { reason: "reconnect" }]]);

  controller.close();
  controller.close();
  assert.equal(channels[1].closeCalls(), 1);
  assert.equal(timers.size, 0);

  assert.throws(
    () => createSessionTransportController({ protocol: {} }),
    /protocol_method_missing:openSessionEvents/,
  );
}
