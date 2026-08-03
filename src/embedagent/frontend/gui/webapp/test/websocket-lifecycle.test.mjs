import assert from "node:assert/strict";

import { shouldReconnectSocket } from "../src/session-runtime/websocket-lifecycle.js";

export function runWebSocketLifecycleTests() {
  assert.equal(
    shouldReconnectSocket({
      activeToken: 2,
      socketToken: 1,
      manualClose: false,
    }),
    false,
  );
  assert.equal(
    shouldReconnectSocket({
      activeToken: 1,
      socketToken: 1,
      manualClose: true,
    }),
    false,
  );
  assert.equal(
    shouldReconnectSocket({
      activeToken: 1,
      socketToken: 1,
      manualClose: false,
    }),
    true,
  );
  assert.equal(
    shouldReconnectSocket({
      activeToken: 1,
      socketToken: 1,
      manualClose: false,
      closed: true,
    }),
    false,
  );
}
