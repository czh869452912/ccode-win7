import assert from "node:assert/strict";

import { createJsonHttpClient } from "../src/app-runtime/http-client.js";

function response({ ok = true, status = 200, payload = null } = {}) {
  return {
    ok,
    status,
    json: async () => payload,
  };
}

export async function runHttpClientTests() {
  const calls = [];
  const client = createJsonHttpClient({
    fetchImpl: async (url, options = {}) => {
      calls.push([url, options.method || "GET"]);
      return response({ payload: { ok: true } });
    },
  });

  assert.deepEqual(await client.fetchJson("/api/demo", { method: "POST" }), { ok: true });
  assert.deepEqual(calls, [["/api/demo", "POST"]]);

  const stringErrorClient = createJsonHttpClient({
    fetchImpl: async () => response({ ok: false, status: 409, payload: { detail: "conflict" } }),
  });
  await assert.rejects(
    () => stringErrorClient.fetchJson("/api/conflict"),
    (error) => {
      assert.equal(error.message, "conflict");
      assert.equal(error.status, 409);
      assert.equal(error.detail, "conflict");
      return true;
    },
  );

  const objectErrorClient = createJsonHttpClient({
    fetchImpl: async () =>
      response({ ok: false, status: 422, payload: { detail: { reason: "bad payload" } } }),
  });
  await assert.rejects(
    () => objectErrorClient.fetchJson("/api/bad"),
    (error) => {
      assert.equal(error.message, '{"reason":"bad payload"}');
      assert.equal(error.status, 422);
      assert.equal(error.detail, '{"reason":"bad payload"}');
      return true;
    },
  );
}
