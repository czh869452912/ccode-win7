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
      workflow_state: { workflow: { id: "example", items: [{ id: "task-1" }] } },
    },
    activities: [],
    capabilities: {},
  });
  assert.equal(activated.thread.currentSessionId, "s-1");
  assert.equal(activated.snapshot.workflow_state.workflow.id, "example");
  assert.equal(Object.hasOwn(activated, "tasks"), false);

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
