import assert from "node:assert/strict";

import { createSessionActivationController } from "../src/app-runtime/session-activation-controller.js";

export async function runSessionActivationControllerTests() {
  const actions = [];
  const calls = [];
  let replacedTransport = null;
  const controller = createSessionActivationController({
    fetchJson: async (url) => {
      calls.push(["fetchJson", url]);
      return {
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
    createTransportState: () => ({ connectionState: "connected", reloadState: "healthy" }),
    replaceTransportState: (state) => {
      replacedTransport = state;
    },
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
  assert.deepEqual(replacedTransport, {
    connectionState: "connected",
    reloadState: "healthy",
  });
  assert.deepEqual(actions[1], { type: "plan_loaded", plan: { title: "Build plan" } });
  assert.deepEqual(actions[2], {
    type: "terminal_summaries_loaded",
    terminals: [{ terminal_id: "term-1" }],
  });
  assert.equal(calls.some((item) => item[0] === "loadTasks"), false);
  assert.equal(calls.some((item) => item[0] === "loadArtifacts"), false);

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
