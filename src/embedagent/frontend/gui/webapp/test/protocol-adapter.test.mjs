import assert from "node:assert/strict";

import { createAgentAppProtocolAdapter } from "../src/client-runtime/protocol-adapter.js";

export async function runProtocolAdapterTests() {
  const calls = [];
  const http = {
    request: async (request) => {
      calls.push(request);
      return { session_id: "s-1" };
    },
  };
  const socketChannels = [];
  const socket = {
    connect(request) {
      socketChannels.push(request);
      return { close() {} };
    },
  };
  const adapter = createAgentAppProtocolAdapter({ http, socket });

  assert.equal("request" in adapter, false);
  assert.equal("fetchJson" in adapter, false);

  const bootstrap = await adapter.loadSessionBootstrap("s-1");
  assert.equal(bootstrap.session_id, "s-1");
  assert.deepEqual(calls[0], {
    path: "/api/sessions/s-1/bootstrap",
    method: "GET",
    body: undefined,
    signal: undefined,
  });

  await adapter.setSessionMode("s/1", "debug");
  assert.deepEqual(calls[1], {
    path: "/api/sessions/s%2F1/mode",
    method: "POST",
    body: { mode: "debug" },
    signal: undefined,
  });

  const controller = new AbortController();
  await adapter.sendSessionMessage("s-1", "hello", { signal: controller.signal });
  assert.deepEqual(calls[2], {
    path: "/api/sessions/s-1/message",
    method: "POST",
    body: { text: "hello" },
    signal: controller.signal,
  });

  await adapter.respondToInteraction(
    "s-1",
    "interaction/1",
    { decision: "allow" },
    { signal: controller.signal },
  );
  assert.deepEqual(calls[3], {
    path: "/api/sessions/s-1/interactions/interaction%2F1/respond",
    method: "POST",
    body: { decision: "allow" },
    signal: controller.signal,
  });

  const channel = adapter.openSessionEvents();
  assert.equal(typeof channel.close, "function");
  assert.deepEqual(socketChannels, [{ path: "/ws" }]);
}
