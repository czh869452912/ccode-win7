import assert from "node:assert/strict";

import { createSessionActivationController } from "../src/app-runtime/session-activation-controller.js";
import {
  bufferSessionTransportEvent,
  createSessionTransportState,
} from "../src/session-runtime/session-transport-state.js";
import { capabilitySnapshot, commandDescriptor } from "./protocol-fixtures.mjs";

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function bootstrap(sessionId, eventCursor) {
  return {
    event_cursor: eventCursor,
    snapshot: { session_id: sessionId, status: "idle", current_mode: "build" },
    history: { activities: [], integrity: { status: "healthy" } },
    plan: null,
    capabilities: {},
  };
}

export async function runSessionActivationControllerTests() {
  const actions = [];
  const calls = [];
  const acceptedEvents = [];
  let transport = createSessionTransportState();
  const controller = createSessionActivationController({
    protocol: {
      loadSessionBootstrap: async (sessionId, options) => {
        calls.push(["loadSessionBootstrap", sessionId, options.signal]);
        return {
          ...bootstrap("sess-activation", 6),
          history: {
            integrity: { status: "healthy" },
            activities: [
              {
                kind: "user",
                id: "activity-user",
                turn_id: "turn-1",
                content: "hello",
                projection_source: "session_state",
              },
            ],
            turns: [],
          },
          plan: { title: "Build plan" },
          capabilities: capabilitySnapshot({
            commands: [commandDescriptor("help", "/help")],
          }),
        };
      },
      listTerminals: async (sessionId) => {
        calls.push(["listTerminals", sessionId]);
        return { terminals: [{ terminal_id: "term-1" }] };
      },
    },
    dispatch: (action) => actions.push(action),
    defaultMode: "explore",
    getTransportState: () => transport,
    updateTransportState: (updater) => {
      transport = updater(transport);
      return transport;
    },
    dispatchAcceptedSessionEvent: (event) => acceptedEvents.push(event),
    getAppCapabilities: () => ({ terminal: { enabled: true } }),
  });

  await controller("sess-activation");
  assert.equal(calls[0][0], "loadSessionBootstrap");
  assert.equal(calls[0][1], "sess-activation");
  assert.equal(typeof calls[0][2]?.aborted, "boolean");
  assert.equal(actions[0].type, "session_activated");
  assert.equal(actions[0].capabilities.commands[0].usage, "/help");
  assert.equal(transport.phase, "live");
  assert.equal(transport.lastAppliedSeq, 6);
  assert.deepEqual(acceptedEvents, []);
  assert.deepEqual(actions[1], { type: "plan_loaded", plan: { title: "Build plan" } });
  assert.equal(actions[2].type, "terminal_summaries_loaded");

  const first = deferred();
  const second = deferred();
  const switchedActions = [];
  let switchedTransport = createSessionTransportState();
  const switchController = createSessionActivationController({
    protocol: {
      loadSessionBootstrap: (sessionId) => (sessionId === "s-1" ? first.promise : second.promise),
    },
    dispatch: (action) => switchedActions.push(action),
    getTransportState: () => switchedTransport,
    updateTransportState: (updater) => {
      switchedTransport = updater(switchedTransport);
      return switchedTransport;
    },
    getAppCapabilities: () => ({ terminal: { enabled: false } }),
  });
  const firstLoad = switchController("s-1");
  const secondLoad = switchController("s-2");
  second.resolve(bootstrap("s-2", 8));
  assert.equal((await secondLoad).stale, false);
  first.resolve(bootstrap("s-1", 4));
  assert.equal((await firstLoad).stale, true);
  assert.deepEqual(
    switchedActions
      .filter((action) => action.type === "session_activated")
      .map((action) => action.sessionId),
    ["s-2"],
  );

  const pendingBootstrap = deferred();
  const drainedEvents = [];
  let bufferedTransport = createSessionTransportState();
  const bufferedController = createSessionActivationController({
    protocol: { loadSessionBootstrap: () => pendingBootstrap.promise },
    dispatch: () => {},
    getTransportState: () => bufferedTransport,
    updateTransportState: (updater) => {
      bufferedTransport = updater(bufferedTransport);
      return bufferedTransport;
    },
    dispatchAcceptedSessionEvent: (event) => drainedEvents.push(event),
    getAppCapabilities: () => ({ terminal: { enabled: false } }),
  });
  const bufferedLoad = bufferedController("s-buffered");
  bufferedTransport = bufferSessionTransportEvent(bufferedTransport, {
    schema_version: 1,
    session_id: "s-buffered",
    event_id: "evt-buffered-3",
    sequence: 3,
    event_kind: "step.started",
    timestamp: "2026-08-03T00:00:03Z",
    payload: { step_id: "step-3" },
  });
  pendingBootstrap.resolve(bootstrap("s-buffered", 2));
  assert.equal((await bufferedLoad).stale, false);
  assert.equal(bufferedTransport.lastAppliedSeq, 3);
  assert.deepEqual(drainedEvents.map((event) => event.event_id), ["evt-buffered-3"]);

  const terminalFailureActions = [];
  const terminalFailureController = createSessionActivationController({
    protocol: {
      loadSessionBootstrap: async () => ({}),
      listTerminals: async () => {
        throw new Error("terminal unavailable");
      },
    },
    dispatch: (action) => terminalFailureActions.push(action),
    getAppCapabilities: () => ({ terminal: { enabled: true } }),
  });
  await terminalFailureController("sess-terminal-failure");
  assert.deepEqual(terminalFailureActions.at(-1), {
    type: "terminal_summaries_loaded",
    terminals: [],
  });

  assert.throws(
    () => createSessionActivationController({ protocol: {} }),
    /protocol_method_missing:loadSessionBootstrap/,
  );
}
