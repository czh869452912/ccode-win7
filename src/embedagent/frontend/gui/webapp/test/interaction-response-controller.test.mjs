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
  let inFlight = "";
  let cleared = 0;
  const calls = [];
  const dispatches = [];
  const logs = [];
  const pendingFetch = deferred();
  const controller = createInteractionResponseController({
    fetchJson: async (url, options) => {
      calls.push({ url, options });
      return pendingFetch.promise;
    },
    dispatch: (action) => dispatches.push(action),
    normalizeSessionPayload: (payload) => ({ ...payload, normalized: true }),
    getCurrentSessionId: () => "sess-1",
    getCurrentInteraction: () => ({ interaction_id: "ask-1", kind: "user_input" }),
    getResponseInFlight: () => inFlight,
    setResponseInFlight: (value) => {
      inFlight = value;
    },
    loadSession: async () => {
      throw new Error("loadSession should not run on resolved response");
    },
    clearUserAnswer: () => {
      cleared += 1;
    },
    logEvent: (label, detail) => logs.push({ label, detail }),
  });

  const first = controller.respondToInteraction({
    response_kind: "answer",
    answer: "yes",
  });
  assert.equal(inFlight, "ask-1");
  const duplicate = await controller.respondToInteraction({
    response_kind: "answer",
    answer: "again",
  });
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
  assert.equal(inFlight, "");
  assert.equal(cleared, 1);
  assert.equal(calls[0].url, "/api/sessions/sess-1/interactions/ask-1/respond");
  assert.equal(dispatches[0].type, "interaction_notice_clear");
  assert.equal(dispatches[1].type, "session_snapshot");
  assert.equal(dispatches[1].snapshot.normalized, true);
  assert.equal(logs[0].label, "interaction_response");
  assert.equal(logs[0].detail, "yes");

  let loadedSession = "";
  inFlight = "";
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
    getResponseInFlight: () => inFlight,
    setResponseInFlight: (value) => {
      inFlight = value;
    },
    loadSession: async (sessionId) => {
      loadedSession = sessionId;
    },
    logEvent: (label, detail) => logs.push({ label, detail }),
  });

  const expired = await expiredController.respondToInteraction({
    response_kind: "answer",
    answer: "late",
  });

  assert.equal(expired, null);
  assert.equal(inFlight, "");
  assert.equal(loadedSession, "sess-1");
  assert.equal(dispatches.at(-1).type, "interaction_notice_set");
  assert.equal(dispatches.at(-1).notice.kind, "expired");
}
