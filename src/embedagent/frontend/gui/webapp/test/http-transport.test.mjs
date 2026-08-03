import assert from "node:assert/strict";

import { createHttpTransport } from "../src/client-runtime/http-transport.js";
import { runProtocolAdapterTests } from "./protocol-adapter.test.mjs";

function response({ ok = true, status = 200, payload = null } = {}) {
  return {
    ok,
    status,
    json: async () => payload,
  };
}

export async function runHttpTransportTests() {
  await runProtocolAdapterTests();

  const calls = [];
  const controller = new AbortController();
  const transport = createHttpTransport({
    fetchImpl: async (path, options = {}) => {
      calls.push({ path, options });
      return response({ payload: { ok: true } });
    },
  });

  assert.deepEqual(
    await transport.request({
      path: "/api/demo",
      method: "POST",
      body: { value: 1 },
      signal: controller.signal,
    }),
    { ok: true },
  );
  assert.deepEqual(calls, [
    {
      path: "/api/demo",
      options: {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: 1 }),
        signal: controller.signal,
      },
    },
  ]);

  const stringErrorTransport = createHttpTransport({
    fetchImpl: async () => response({ ok: false, status: 409, payload: { detail: "conflict" } }),
  });
  await assert.rejects(
    () => stringErrorTransport.request({ path: "/api/conflict" }),
    (error) => {
      assert.equal(error.message, "conflict");
      assert.equal(error.status, 409);
      assert.equal(error.detail, "conflict");
      return true;
    },
  );

  const objectErrorTransport = createHttpTransport({
    fetchImpl: async () =>
      response({ ok: false, status: 422, payload: { detail: { reason: "bad payload" } } }),
  });
  await assert.rejects(
    () => objectErrorTransport.request({ path: "/api/bad" }),
    (error) => {
      assert.equal(error.message, '{"reason":"bad payload"}');
      assert.equal(error.status, 422);
      assert.equal(error.detail, '{"reason":"bad payload"}');
      return true;
    },
  );
}
