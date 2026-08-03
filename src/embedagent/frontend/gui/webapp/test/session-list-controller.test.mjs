import assert from "node:assert/strict";

import { createSessionListController } from "../src/app-runtime/session-list-controller.js";

export async function runSessionListControllerTests() {
  const calls = [];
  const actions = [];
  const controller = createSessionListController({
    protocol: {
      listSessions: async () => {
        calls.push("listSessions");
        return {
          sessions: [
            { session_id: "sess-1", user_goal: "Inspect parser" },
            { session_id: "sess-2", user_goal: "Verify parser" },
          ],
        };
      },
    },
    dispatch: (action) => actions.push(action),
  });

  const sessions = await controller.loadSessions();
  assert.deepEqual(calls, ["listSessions"]);
  assert.deepEqual(sessions, [
    { session_id: "sess-1", user_goal: "Inspect parser" },
    { session_id: "sess-2", user_goal: "Verify parser" },
  ]);
  assert.deepEqual(actions, [{ type: "sessions_loaded", sessions }]);

  assert.throws(
    () => createSessionListController({ protocol: {} }),
    /protocol_method_missing:listSessions/,
  );
}
