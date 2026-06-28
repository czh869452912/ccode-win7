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
        permission_context: { session_id: "sess-activation" },
      };
    },
    dispatch: (action) => actions.push(action),
    defaultMode: "explore",
    createTransportState: () => ({ connectionState: "connected", reloadState: "healthy" }),
    replaceTransportState: (state) => {
      replacedTransport = state;
    },
    listTerminals: async (sessionId) => {
      calls.push(["listTerminals", sessionId]);
      return { terminals: [{ terminal_id: "term-1" }] };
    },
    loadTasks: async (sessionId) => {
      calls.push(["loadTasks", sessionId]);
    },
    loadArtifacts: async () => {
      calls.push(["loadArtifacts"]);
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
  assert.deepEqual(replacedTransport, {
    connectionState: "connected",
    reloadState: "healthy",
  });
  assert.deepEqual(actions[1], { type: "plan_loaded", plan: { title: "Build plan" } });
  assert.deepEqual(actions[2], {
    type: "permission_context_loaded",
    context: { session_id: "sess-activation" },
  });
  assert.deepEqual(actions[3], {
    type: "terminal_summaries_loaded",
    terminals: [{ terminal_id: "term-1" }],
  });
  assert.deepEqual(calls.slice(-2), [
    ["loadTasks", "sess-activation"],
    ["loadArtifacts"],
  ]);

  const terminalFailureActions = [];
  const terminalFailureController = createSessionActivationController({
    fetchJson: async () => ({}),
    dispatch: (action) => terminalFailureActions.push(action),
    listTerminals: async () => {
      throw new Error("terminal unavailable");
    },
  });
  await terminalFailureController("sess-terminal-failure");
  assert.deepEqual(terminalFailureActions.at(-1), {
    type: "terminal_summaries_loaded",
    terminals: [],
  });
}
