import assert from "node:assert/strict";

import {
  closePreviewSession,
  listPreviewSessions,
  openPreviewExternal,
  openPreviewSession,
  refreshPreviewSession,
} from "../src/preview/preview-api.js";

function createFetchHarness() {
  const calls = [];
  const fetch = async (url, options = {}) => {
    calls.push({ url, options });
    return {
      ok: true,
      statusText: "OK",
      json: async () => ({ ok: true, url, body: options.body ? JSON.parse(options.body) : null }),
    };
  };
  return { calls, fetch };
}

export async function runPreviewApiTests() {
  {
    const harness = createFetchHarness();
    const result = await openPreviewSession("sess-1", "http://localhost:5173", {
      fetch: harness.fetch,
    });
    assert.equal(harness.calls[0].url, "/api/sessions/sess-1/preview/open");
    assert.equal(harness.calls[0].options.method, "POST");
    assert.deepEqual(JSON.parse(harness.calls[0].options.body), {
      url: "http://localhost:5173",
    });
    assert.equal(result.ok, true);
  }

  {
    const harness = createFetchHarness();
    await listPreviewSessions("sess 1", { fetch: harness.fetch });
    await refreshPreviewSession("sess 1", "tab/1", { fetch: harness.fetch });
    await closePreviewSession("sess 1", "tab/1", { fetch: harness.fetch });
    await openPreviewExternal("http://localhost:5173", { fetch: harness.fetch });
    assert.deepEqual(
      harness.calls.map((call) => [call.url, call.options.method || "GET"]),
      [
        ["/api/sessions/sess%201/preview", "GET"],
        ["/api/sessions/sess%201/preview/tab%2F1/refresh", "POST"],
        ["/api/sessions/sess%201/preview/tab%2F1/close", "POST"],
        ["/api/app/preview/open-external", "POST"],
      ],
    );
  }
}
