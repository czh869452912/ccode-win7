import assert from "node:assert/strict";

import { createSessionActivationController } from "../src/app-runtime/session-activation-controller.js";
import {
  bufferSessionTransportEvent,
  createSessionTransportState,
} from "../src/session-runtime/session-transport-state.js";

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
    fetchJson: async (url) => {
      calls.push(["fetchJson", url]);
      return {
        event_cursor: 6,
        snapshot: {
          session_id: "sess-activation",
          status: "idle",
          current_mode: "build",
        },
        history: {
          history_source: "bootstrap",
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
        capabilities: {
          commands: [
            {
              name: "help",
              usage: "/help",
              active: true,
            },
          ],
        },
      };
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
    listTerminals: async (sessionId) => {
      calls.push(["listTerminals", sessionId]);
      return { terminals: [{ terminal_id: "term-1" }] };
    },
  });

  await controller("sess-activation");

  assert.deepEqual(calls[0], [
    "fetchJson",
    "/api/sessions/sess-activation/bootstrap",
  ]);
  assert.equal(actions[0].type, "session_activated");
  assert.equal(actions[0].sessionId, "sess-activation");
  assert.equal(actions[0].snapshot.current_mode, "build");
  assert.equal(actions[0].activities[0].kind, "user");
  assert.deepEqual(actions[0].historyIntegrity, { status: "healthy" });
  assert.equal(actions[0].capabilities.commands[0].usage, "/help");
  assert.equal(transport.sessionId, "sess-activation");
  assert.equal(transport.phase, "live");
  assert.equal(transport.lastAppliedSeq, 6);
  assert.deepEqual(acceptedEvents, []);
  assert.deepEqual(actions[1], { type: "plan_loaded", plan: { title: "Build plan" } });
  assert.deepEqual(actions[2], {
    type: "terminal_summaries_loaded",
    terminals: [{ terminal_id: "term-1" }],
  });
  assert.equal(calls.some((item) => item[0] === "loadTasks"), false);
  assert.equal(calls.some((item) => item[0] === "loadArtifacts"), false);

  const first = deferred();
  const second = deferred();
  const switchedActions = [];
  let switchedTransport = createSessionTransportState();
  const switchController = createSessionActivationController({
    fetchJson: (url) => (url.includes("s-1") ? first.promise : second.promise),
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
  const secondResult = await secondLoad;
  first.resolve(bootstrap("s-1", 4));
  const firstResult = await firstLoad;

  assert.equal(secondResult.stale, false);
  assert.equal(firstResult.stale, true);
  assert.deepEqual(
    switchedActions
      .filter((action) => action.type === "session_activated")
      .map((action) => action.sessionId),
    ["s-2"],
  );
  assert.equal(switchedTransport.sessionId, "s-2");
  assert.equal(switchedTransport.lastAppliedSeq, 8);

  const pendingBootstrap = deferred();
  const drainedEvents = [];
  let bufferedTransport = createSessionTransportState();
  const bufferedController = createSessionActivationController({
    fetchJson: () => pendingBootstrap.promise,
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
  assert.equal(bufferedTransport.phase, "buffering");
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
  const bufferedResult = await bufferedLoad;

  assert.equal(bufferedResult.stale, false);
  assert.equal(bufferedTransport.lastAppliedSeq, 3);
  assert.equal(bufferedTransport.bufferedEvents.length, 0);
  assert.deepEqual(
    drainedEvents.map((event) => event.event_id),
    ["evt-buffered-3"],
  );

  const terminalFailureActions = [];
  const terminalFailureController = createSessionActivationController({
    fetchJson: async () => ({}),
    dispatch: (action) => terminalFailureActions.push(action),
    getAppCapabilities: () => ({ terminal: { enabled: true } }),
    listTerminals: async () => {
      throw new Error("terminal unavailable");
    },
  });
  await terminalFailureController("sess-terminal-failure");
  assert.deepEqual(terminalFailureActions.at(-1), {
    type: "terminal_summaries_loaded",
    terminals: [],
  });

  const terminalDisabledActions = [];
  const terminalDisabledCalls = [];
  const terminalDisabledController = createSessionActivationController({
    fetchJson: async () => ({}),
    dispatch: (action) => terminalDisabledActions.push(action),
    getAppCapabilities: () => ({ terminal: { enabled: false } }),
    listTerminals: async (sessionId) => {
      terminalDisabledCalls.push(["listTerminals", sessionId]);
      return { terminals: [{ terminal_id: "hidden-terminal" }] };
    },
  });
  await terminalDisabledController("sess-terminal-disabled");
  assert.equal(terminalDisabledCalls.some((item) => item[0] === "listTerminals"), false);
  assert.equal(
    terminalDisabledActions.some((action) => action.type === "terminal_summaries_loaded"),
    false,
  );
}
