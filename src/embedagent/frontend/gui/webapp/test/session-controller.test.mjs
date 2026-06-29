import assert from "node:assert/strict";

import { createSessionController } from "../src/app-runtime/session-controller.js";

export async function runSessionControllerTests() {
  const calls = [];
  const actions = [];
  const loadedSessions = [];
  const controller = createSessionController({
    fetchJson: async (url, options = {}) => {
      calls.push(["fetchJson", url, options.method || "GET"]);
      if (url === "/api/sessions?mode=debug") {
        return {
          session_id: "sess-new",
          status: "idle",
          current_mode: "debug",
        };
      }
      throw new Error(`unexpected url ${url}`);
    },
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

  const sessionId = await controller.createSession("debug");

  assert.equal(sessionId, "sess-new");
  assert.deepEqual(loadedSessions, ["sess-new"]);
  assert.equal(actions.some((action) => action.type === "session_activated"), false);
  assert.equal(calls.some((call) => call[0] === "loadSessions"), true);
}
