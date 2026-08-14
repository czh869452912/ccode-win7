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

function bootstrap(sessionId, mode = "build") {
  return {
    schema_version: 1,
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
  const installed = [];
  const controller = createSessionController({
    protocol: requiredProtocol({
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
    loadSession: async () => { throw new Error("create must install its returned bootstrap"); },
    installSessionBootstrap: async (value, reason) => installed.push([value.thread.id, reason]),
  });

  assert.equal(await controller.createSession("debug"), "sess-new");
  assert.equal(await controller.createSession(), "sess-new");
  assert.deepEqual(
    calls.filter((call) => call[0] === "createSession"),
    [["createSession", "debug"], ["createSession", ""]],
  );
  assert.deepEqual(installed, [["sess-new", "create"], ["sess-new", "create"]]);
  assert.equal(actions.some((action) => action.type === "session_activated"), false);

  const cancelActions = [];
  const cancelController = createSessionController({
    protocol: requiredProtocol({
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
    loadSession: async () => {},
    installSessionBootstrap: async (value, reason) => installed.push([value.thread.id, reason]),
  });

  await cancelController.cancelSession();
  assert.deepEqual(cancelActions[0], { type: "stream_completed" });
  assert.equal(cancelActions.length, 1);
  assert.deepEqual(installed.at(-1), ["sess-cancel", "cancel"]);

  assert.throws(
    () => createSessionController({ protocol: {}, installSessionBootstrap() {} }),
    /protocol_method_missing:createSession/,
  );
}
