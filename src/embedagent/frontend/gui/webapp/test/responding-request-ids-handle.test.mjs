import assert from "node:assert/strict";

import { createRespondingRequestIdsHandle } from "../src/app-runtime/responding-request-ids-handle.js";

export function runRespondingRequestIdsHandleTests() {
  const writes = [];
  const handle = createRespondingRequestIdsHandle({
    initialRequestIds: ["req-1"],
    setRequestIds: (requestIds) => writes.push(requestIds),
  });

  assert.deepEqual(handle.read(), ["req-1"]);
  assert.deepEqual(handle.set(["req-2", "", null, 7]), ["req-2", "7"]);
  assert.deepEqual(handle.read(), ["req-2", "7"]);
  assert.deepEqual(writes, [["req-2", "7"]]);

  assert.deepEqual(
    handle.set((current) => current.concat(["req-3", undefined])),
    ["req-2", "7", "req-3"],
  );
  assert.deepEqual(handle.read(), ["req-2", "7", "req-3"]);

  assert.deepEqual(handle.sync(["req-4", 0, ""]), ["req-4"]);
  assert.deepEqual(handle.read(), ["req-4"]);
}
