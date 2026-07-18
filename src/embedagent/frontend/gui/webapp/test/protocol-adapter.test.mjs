import assert from "node:assert/strict";

import { createAgentAppProtocolAdapter } from "../src/client-runtime/protocol-adapter.js";

export async function runProtocolAdapterTests() {
  const requests = [];
  const adapter = createAgentAppProtocolAdapter({
    fetchJson: async (url, options = {}) => {
      requests.push({ url, options });
      return { session_id: "s-1" };
    },
  });

  const bootstrap = await adapter.loadSessionBootstrap("s-1");
  assert.equal(bootstrap.session_id, "s-1");
  assert.equal(requests[0].url, "/api/sessions/s-1/bootstrap");
  assert.equal(requests[0].options.method, "GET");

  await adapter.sendSessionMessage("s-1", "hello");
  assert.equal(requests[1].url, "/api/sessions/s-1/message");
  assert.equal(requests[1].options.method, "POST");
  assert.equal(requests[1].options.body, JSON.stringify({ text: "hello" }));

  await adapter.respondToInteraction("s-1", "interaction/1", { decision: "allow" });
  assert.equal(
    requests[2].url,
    "/api/sessions/s-1/interactions/interaction%2F1/respond",
  );
  assert.equal(requests[2].options.body, JSON.stringify({ decision: "allow" }));

  const socketMessages = [];
  const socketAdapter = createAgentAppProtocolAdapter({
    fetchJson: async () => ({}),
    sendSocketMessage: (message) => {
      socketMessages.push(message);
      return socketMessages.length;
    },
  });
  const event = { type: "session_event", data: { session_id: "s-1" } };
  assert.equal(socketAdapter.handleEvent(event), 1);
  assert.deepEqual(socketMessages, [event]);
}
