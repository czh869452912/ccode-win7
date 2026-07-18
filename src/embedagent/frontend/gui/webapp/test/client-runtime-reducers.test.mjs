import assert from "node:assert/strict";

import { initialState, runtimeReducer } from "../src/client-runtime/runtime-reducer.js";
import { normalizeProtocolCapabilities } from "../src/session-runtime/protocol-normalizer.js";

export function runClientRuntimeReducerTests() {
  const activated = runtimeReducer(initialState, {
    type: "session_activated",
    sessionId: "matrix-session",
    snapshot: { session_id: "matrix-session", current_mode: "", task_items: [] },
    capabilities: normalizeProtocolCapabilities({
      modes: [],
      tools: [{ name: "future_tool", label: "Future Tool", rendererKey: "unknown" }],
      workflowPackages: [{ id: "future-workflow", label: "Future Workflow" }],
    }),
    activities: [{ id: "future-activity", kind: "future_activity", content: "opaque" }],
  });

  assert.equal(activated.thread.currentSessionId, "matrix-session");
  assert.equal(activated.sessionCapabilities.toolCatalog.future_tool.label, "Future Tool");
  assert.equal(activated.sessionCapabilities.workflowPackages[0].id, "future-workflow");
  assert.equal(activated.activities[0].kind, "future_activity");
}

runClientRuntimeReducerTests();
console.log("client runtime reducer checks passed");
