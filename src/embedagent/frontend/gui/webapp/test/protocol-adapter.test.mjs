import assert from "node:assert/strict";

import { createAgentAppProtocolAdapter } from "../src/client-runtime/protocol-adapter.js";

export async function runProtocolAdapterTests() {
  const calls = [];
  const http = {
    request: async (request) => {
      calls.push(request);
      if (request.path === "/api/app/source-control/status") {
        return { source_control: { branch: "main", files: [] } };
      }
      if (request.path.startsWith("/api/app/source-control/diff?")) {
        return { diff: { available: true, diff: "patch" } };
      }
      if (request.path.endsWith("/terminals")) {
        return { terminals: [{ terminal_id: "term-1" }] };
      }
      if (request.path.includes("/preview/open") || request.path.endsWith("open-external")) {
        return { preview: { tab_id: "tab-1" } };
      }
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
  assert.equal(calls[2].signal, controller.signal);
  assert.deepEqual(calls[2].body, { text: "hello" });

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

  assert.deepEqual(await adapter.listTerminals("s-1"), {
    terminals: [{ terminal_id: "term-1" }],
  });
  assert.equal(calls.at(-1).path, "/api/sessions/s-1/terminals");

  await adapter.openTerminal("s-1", "term/1", { cols: 120, rows: 40 });
  assert.deepEqual(calls.at(-1), {
    path: "/api/sessions/s-1/terminals/term%2F1/open",
    method: "POST",
    body: { cols: 120, rows: 40 },
    signal: undefined,
  });

  assert.deepEqual(await adapter.getSourceControlStatus(), {
    branch: "main",
    files: [],
  });
  assert.deepEqual(await adapter.getSourceControlDiff("src/main.c", "staged"), {
    available: true,
    diff: "patch",
  });
  assert.equal(
    calls.at(-1).path,
    "/api/app/source-control/diff?path=src%2Fmain.c&scope=staged",
  );

  await adapter.openPreviewSession("s-1", "http://localhost:5173");
  assert.equal(calls.at(-1).path, "/api/sessions/s-1/preview/open");
  assert.deepEqual(calls.at(-1).body, { url: "http://localhost:5173" });

  await adapter.openPreviewExternal("http://localhost:5173");
  assert.equal(calls.at(-1).path, "/api/app/preview/open-external");

  const channel = adapter.openSessionEvents();
  assert.equal(typeof channel.close, "function");
  assert.deepEqual(socketChannels, [{ path: "/ws" }]);
}
