import assert from "node:assert/strict";

import { createSessionController } from "../src/app-runtime/session-controller.js";

function requiredProtocol(overrides = {}) {
  return {
    sendSessionMessage: async () => ({}),
    ...overrides,
  };
}

function requiredSessionRuntime(overrides = {}) {
  return {
    createSession: async () => bootstrap("sess-new"),
    setSessionMode: async (sessionId, mode) => bootstrap(sessionId, mode),
    cancelSession: async (sessionId) => bootstrap(sessionId),
    ...overrides,
  };
}

function bootstrap(sessionId, mode = "build") {
  return {
    schema_version: 2,
    event_cursor: 0,
    thread: { id: sessionId },
    snapshot: { session_id: sessionId, status: "idle", current_mode: mode },
    history: { activities: [], integrity: {} },
    capabilities: {},
    plan: null,
    permission_context: {},
  };
}

export async function runSessionControllerTests() {
  const calls = [];
  const actions = [];
  const controller = createSessionController({
    protocol: requiredProtocol(),
    sessionRuntime: requiredSessionRuntime({
      createSession: async (mode) => {
        calls.push(["createSession", mode]);
        return bootstrap("sess-new", mode || "agent-default");
      },
    }),
    dispatch: (action) => actions.push(action),
    getCurrentSessionId: () => "",
    getCurrentMode: () => "debug",
    hasActiveWorkspace: () => true,
    loadSessions: async () => calls.push(["loadSessions"]),
  });

  assert.equal(await controller.createSession("debug"), "sess-new");
  assert.equal(await controller.createSession(), "sess-new");
  assert.deepEqual(
    calls.filter((call) => call[0] === "createSession"),
    [["createSession", "debug"], ["createSession", ""]],
  );
  assert.equal(actions.some((action) => action.type === "session_activated"), false);

  const cancelActions = [];
  const cancelController = createSessionController({
    protocol: requiredProtocol(),
    sessionRuntime: requiredSessionRuntime({
      setSessionMode: async (sessionId, mode) => {
        calls.push(["setSessionMode", sessionId, mode]);
        return bootstrap(sessionId, mode);
      },
      cancelSession: async (sessionId) => {
        calls.push(["cancelSession", sessionId]);
        return bootstrap("sess-cancel");
      },
    }),
    dispatch: (action) => cancelActions.push(action),
    getCurrentSessionId: () => "sess-cancel",
    getCurrentMode: () => "build",
    hasActiveWorkspace: () => true,
    loadSessions: async () => {},
  });

  await cancelController.setMode("verify");
  await cancelController.cancelSession();
  assert.deepEqual(calls.at(-2), ["setSessionMode", "sess-cancel", "verify"]);
  assert.deepEqual(calls.at(-1), ["cancelSession", "sess-cancel"]);
  assert.deepEqual(cancelActions[0], { type: "mode_requested", mode: "verify" });
  assert.deepEqual(cancelActions[1], { type: "stream_completed" });
  assert.equal(cancelActions.length, 2);

  assert.throws(
    () => createSessionController({ protocol: requiredProtocol(), sessionRuntime: {} }),
    /session_runtime_method_missing:createSession/,
  );
}
