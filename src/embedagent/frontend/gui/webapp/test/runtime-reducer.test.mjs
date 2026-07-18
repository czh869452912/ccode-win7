import assert from "node:assert/strict";

import {
  initialState,
  runtimeReducer,
} from "../src/client-runtime/runtime-reducer.js";

export function runRuntimeReducerTests() {
  const activated = runtimeReducer(initialState, {
    type: "session_activated",
    sessionId: "s-1",
    snapshot: {
      session_id: "s-1",
      current_mode: "",
      task_items: [],
    },
    activities: [],
    capabilities: {},
  });
  assert.equal(activated.thread.currentSessionId, "s-1");

  const next = runtimeReducer(activated, {
    type: "interaction_requested",
    id: "evt-approval",
    kind: "approval.requested",
    requestId: "r-1",
    turnId: "turn-1",
    payload: { toolName: "generic-tool" },
  });
  assert.equal(next.activities[0].requestId, "r-1");
  assert.equal(next.activities[0].sourceActivityKind, "approval.requested");
  assert.equal(next.thread.currentSessionId, "s-1");
}
