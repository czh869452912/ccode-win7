import assert from "node:assert/strict";

import { createInteractionResponseController } from "../src/app-runtime/interaction-response-controller.js";

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function bootstrap(sessionId) {
  return {
    schema_version: 2,
    event_cursor: 3,
    thread: { id: sessionId },
    snapshot: { session_id: sessionId, status: "idle", current_mode: "build" },
    history: { activities: [], integrity: {} },
    capabilities: {},
    plan: null,
    permission_context: {},
  };
}

export async function runInteractionResponseControllerTests() {
  let respondingIds = [];
  const calls = [];
  const dispatches = [];
  const pendingResponse = deferred();
  const controller = createInteractionResponseController({
    sessionRuntime: {
      respondToInteraction: async (sessionId, interactionId, response) => {
        calls.push({ sessionId, interactionId, response });
        return pendingResponse.promise;
      },
    },
    dispatch: (action) => dispatches.push(action),
    getCurrentSessionId: () => "sess-1",
    getCurrentInteraction: () => ({ interactionId: "ask-1", kind: "user_input" }),
    getRespondingRequestIds: () => respondingIds,
    setRespondingRequestIds: (value) => {
      respondingIds = typeof value === "function" ? value(respondingIds) : value;
    },
    loadSession: async () => {
      throw new Error("loadSession should not run on resolved response");
    },
  });

  const first = controller.respondToInteraction({ answers: { answer: "yes" } });
  assert.equal(respondingIds.includes("ask-1"), true);
  assert.equal(await controller.respondToInteraction({ answers: { answer: "again" } }), null);
  assert.equal(calls.length, 1);

  pendingResponse.resolve(bootstrap("sess-1"));
  const response = await first;

  assert.equal(response.thread.id, "sess-1");
  assert.deepEqual(respondingIds, []);
  assert.deepEqual(calls[0], {
    sessionId: "sess-1",
    interactionId: "ask-1",
    response: { answers: { answer: "yes" } },
  });
  assert.equal(dispatches[0].type, "interaction_notice_clear");
  assert.deepEqual(dispatches[1], {
    type: "log_event",
    label: "interaction_response",
    detail: "yes",
  });

  let loadedSession = "";
  respondingIds = [];
  const expiredController = createInteractionResponseController({
    sessionRuntime: {
      respondToInteraction: async () => {
        const error = new Error("interaction_expired");
        error.status = 410;
        error.detail = "interaction_expired";
        throw error;
      },
    },
    dispatch: (action) => dispatches.push(action),
    getCurrentSessionId: () => "sess-1",
    getCurrentInteraction: () => ({ interaction_id: "ask-2", kind: "user_input" }),
    getRespondingRequestIds: () => respondingIds,
    setRespondingRequestIds: (value) => {
      respondingIds = typeof value === "function" ? value(respondingIds) : value;
    },
    loadSession: async (sessionId) => {
      loadedSession = sessionId;
    },
  });
  assert.equal(
    await expiredController.respondToInteraction({ answers: { answer: "late" } }),
    null,
  );
  assert.deepEqual(respondingIds, []);
  assert.equal(loadedSession, "sess-1");
  assert.equal(dispatches.at(-2).notice.kind, "expired");

  const missingRuntime = createInteractionResponseController({});
  assert.equal(await missingRuntime.respondToInteraction({}), null);
}
