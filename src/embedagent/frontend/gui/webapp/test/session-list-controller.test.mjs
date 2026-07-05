import assert from "node:assert/strict";

import { createSessionListController } from "../src/app-runtime/session-list-controller.js";

export async function runSessionListControllerTests() {
  const calls = [];
  const actions = [];
  const controller = createSessionListController({
    fetchJson: async (url, options = {}) => {
      calls.push([url, options.method || "GET"]);
      return {
        sessions: [
          { session_id: "sess-1", user_goal: "Inspect parser" },
          { session_id: "sess-2", user_goal: "Verify parser" },
        ],
      };
    },
    dispatch: (action) => actions.push(action),
  });

  const sessions = await controller.loadSessions();

  assert.deepEqual(calls, [["/api/sessions", "GET"]]);
  assert.deepEqual(sessions, [
    { session_id: "sess-1", user_goal: "Inspect parser" },
    { session_id: "sess-2", user_goal: "Verify parser" },
  ]);
  assert.deepEqual(actions, [
    {
      type: "sessions_loaded",
      sessions,
    },
  ]);
}
