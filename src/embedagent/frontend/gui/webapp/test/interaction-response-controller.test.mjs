import assert from "node:assert/strict";

import { createInteractionResponseController } from "../src/app-runtime/interaction-response-controller.js";

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

export async function runInteractionResponseControllerTests() {
  let respondingIds = [];
  const calls = [];
  const dispatches = [];
  const pendingResponse = deferred();
  const controller = createInteractionResponseController({
    protocol: {
      respondToInteraction: async (sessionId, interactionId, response) => {
        calls.push({ sessionId, interactionId, response });
        return pendingResponse.promise;
      },
    },
    dispatch: (action) => dispatches.push(action),
    normalizeSessionPayload: (payload) => ({ ...payload, normalized: true }),
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

  pendingResponse.resolve({
    session_id: "sess-1",
    interaction_id: "ask-1",
    status: "resolved",
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "build",
      pending_interaction_valid: false,
      pending_interaction: null,
    },
  });
  const response = await first;

  assert.equal(response.status, "resolved");
  assert.deepEqual(respondingIds, []);
  assert.deepEqual(calls[0], {
    sessionId: "sess-1",
    interactionId: "ask-1",
    response: { answers: { answer: "yes" } },
  });
  assert.equal(dispatches[0].type, "interaction_notice_clear");
  assert.equal(dispatches[1].type, "session_snapshot");
  assert.equal(dispatches[1].snapshot.normalized, true);
  assert.deepEqual(dispatches[2], {
    type: "log_event",
    label: "interaction_response",
    detail: "yes",
  });

  respondingIds = [];
  let acceptedReloads = 0;
  const acceptedDispatches = [];
  const acceptedController = createInteractionResponseController({
    protocol: {
      respondToInteraction: async () => ({
        session_id: "sess-1",
        interaction_id: "ask-accepted",
        status: "accepted",
        snapshot: null,
      }),
    },
    dispatch: (action) => acceptedDispatches.push(action),
    getCurrentSessionId: () => "sess-1",
    getCurrentInteraction: () => ({ interactionId: "ask-accepted", kind: "user_input" }),
    getRespondingRequestIds: () => respondingIds,
    setRespondingRequestIds: (value) => {
      respondingIds = typeof value === "function" ? value(respondingIds) : value;
    },
    loadSession: async () => {
      acceptedReloads += 1;
    },
  });
  const accepted = await acceptedController.respondToInteraction({ answers: { answer: "yes" } });
  assert.equal(accepted.status, "accepted");
  assert.equal(acceptedReloads, 0);
  assert.equal(acceptedDispatches.some((action) => action.type === "session_snapshot"), false);
  assert.deepEqual(respondingIds, ["ask-accepted"]);

  let loadedSession = "";
  respondingIds = [];
  const expiredController = createInteractionResponseController({
    protocol: {
      respondToInteraction: async () => {
        const error = new Error("interaction_expired");
        error.status = 410;
        error.detail = "interaction_expired";
        throw error;
      },
    },
    dispatch: (action) => dispatches.push(action),
    normalizeSessionPayload: (payload) => payload,
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

  const missingProtocol = createInteractionResponseController({});
  assert.equal(await missingProtocol.respondToInteraction({}), null);
}
