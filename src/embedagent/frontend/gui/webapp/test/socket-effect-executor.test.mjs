import assert from "node:assert/strict";

import { createSocketEffectExecutor } from "../src/app-runtime/socket-effect-executor.js";

export async function runSocketEffectExecutorTests() {
  const actions = [];
  const loaderRequests = [];
  const clearedRequestIds = [];
  const execute = createSocketEffectExecutor({
    dispatch: (action) => actions.push(action),
    executeLoaderRequest: (request) => loaderRequests.push(request),
    clearRespondingRequestId: (requestId) => clearedRequestIds.push(requestId),
  });

  execute({
    actions: [
      { type: "interaction_resolved", requestId: "ask-1" },
      { type: "session_snapshot", snapshot: { session_id: "sess-active" } },
    ],
    loaderRequests: [{ name: "load_sessions" }],
  });

  assert.deepEqual(clearedRequestIds, ["ask-1"]);
  assert.deepEqual(actions, [
    { type: "interaction_resolved", requestId: "ask-1" },
    { type: "session_snapshot", snapshot: { session_id: "sess-active" } },
  ]);
  assert.deepEqual(loaderRequests, [{ name: "load_sessions" }]);
}
