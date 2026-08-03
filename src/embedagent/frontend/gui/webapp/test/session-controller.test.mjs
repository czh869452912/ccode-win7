import assert from "node:assert/strict";

import { createSessionController } from "../src/app-runtime/session-controller.js";

function requiredProtocol(overrides = {}) {
  return {
    createSession: async () => ({}),
    setSessionMode: async () => ({}),
    cancelSession: async () => ({}),
    sendSessionMessage: async () => ({}),
    ...overrides,
  };
}

export async function runSessionControllerTests() {
  const calls = [];
  const actions = [];
  const loadedSessions = [];
  const controller = createSessionController({
    protocol: requiredProtocol({
      createSession: async (mode) => {
        calls.push(["createSession", mode]);
        return { session_id: "sess-new", status: "idle", current_mode: mode || "agent-default" };
      },
    }),
    dispatch: (action) => actions.push(action),
    normalizeSessionPayload: (payload) => ({
      session_id: payload.session_id,
      status: payload.status || "idle",
      current_mode: payload.current_mode || "explore",
    }),
    getCurrentSessionId: () => "",
    getCurrentMode: () => "debug",
    hasActiveWorkspace: () => true,
    loadSessions: async () => calls.push(["loadSessions"]),
    loadSession: async (sessionId) => {
      loadedSessions.push(sessionId);
      calls.push(["loadSession", sessionId]);
    },
  });

  assert.equal(await controller.createSession("debug"), "sess-new");
  assert.equal(await controller.createSession(), "sess-new");
  assert.deepEqual(
    calls.filter((call) => call[0] === "createSession"),
    [["createSession", "debug"], ["createSession", ""]],
  );
  assert.deepEqual(loadedSessions, ["sess-new", "sess-new"]);
  assert.equal(actions.some((action) => action.type === "session_activated"), false);

  const cancelActions = [];
  const cancelController = createSessionController({
    protocol: requiredProtocol({
      cancelSession: async (sessionId) => {
        calls.push(["cancelSession", sessionId]);
        return {
          session_id: "sess-cancel",
          status: "idle",
          current_mode: "build",
          pending_interaction: null,
          pending_interaction_valid: false,
        };
      },
    }),
    dispatch: (action) => cancelActions.push(action),
    normalizeSessionPayload: (payload) => ({
      session_id: payload.session_id,
      status: payload.status || "idle",
      current_mode: payload.current_mode || "explore",
      pending_interaction: payload.pending_interaction || null,
      pending_interaction_valid: Boolean(payload.pending_interaction_valid),
    }),
    getCurrentSessionId: () => "sess-cancel",
    getCurrentMode: () => "build",
    hasActiveWorkspace: () => true,
    loadSessions: async () => {},
    loadSession: async () => {},
  });

  await cancelController.cancelSession();
  assert.deepEqual(cancelActions[0], { type: "stream_completed" });
  assert.equal(cancelActions[1].type, "session_snapshot");
  assert.equal(cancelActions[1].snapshot.session_id, "sess-cancel");

  assert.throws(
    () => createSessionController({ protocol: {}, normalizeSessionPayload() {} }),
    /protocol_method_missing:createSession/,
  );
}
