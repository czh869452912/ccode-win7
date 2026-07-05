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
  const pendingFetch = deferred();
  const controller = createInteractionResponseController({
    fetchJson: async (url, options) => {
      calls.push({ url, options });
      return pendingFetch.promise;
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
  const duplicate = await controller.respondToInteraction({ answers: { answer: "again" } });
  assert.equal(duplicate, null);
  assert.equal(calls.length, 1);

  pendingFetch.resolve({
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
  assert.equal(calls[0].url, "/api/sessions/sess-1/interactions/ask-1/respond");
  assert.equal(dispatches[0].type, "interaction_notice_clear");
  assert.equal(dispatches[1].type, "session_snapshot");
  assert.equal(dispatches[1].snapshot.normalized, true);
  assert.deepEqual(dispatches[2], {
    type: "log_event",
    label: "interaction_response",
    detail: "yes",
  });

  let loadedSession = "";
  respondingIds = [];
  const expiredController = createInteractionResponseController({
    fetchJson: async () => {
      const error = new Error("interaction_expired");
      error.status = 410;
      error.detail = "interaction_expired";
      throw error;
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

  const expired = await expiredController.respondToInteraction({ answers: { answer: "late" } });

  assert.equal(expired, null);
  assert.deepEqual(respondingIds, []);
  assert.equal(loadedSession, "sess-1");
  assert.equal(dispatches.at(-2).type, "interaction_notice_set");
  assert.equal(dispatches.at(-2).notice.kind, "expired");
  assert.deepEqual(dispatches.at(-1), {
    type: "log_event",
    label: "interaction_response",
    detail: "interaction_expired",
  });
}
