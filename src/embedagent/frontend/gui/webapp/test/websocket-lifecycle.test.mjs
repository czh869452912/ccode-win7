import assert from "node:assert/strict";

import { createSocketTransport } from "../src/client-runtime/socket-transport.js";
import { shouldReconnectSocket } from "../src/session-runtime/websocket-lifecycle.js";

class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.sent = [];
    this.closeCalls = 0;
    FakeWebSocket.instances.push(this);
  }

  send(value) {
    this.sent.push(value);
  }

  close() {
    this.closeCalls += 1;
    if (typeof this.onclose === "function") this.onclose({ code: 1000 });
  }
}

export function runWebSocketLifecycleTests() {
  assert.equal(
    shouldReconnectSocket({ activeToken: 2, socketToken: 1, manualClose: false }),
    false,
  );
  assert.equal(
    shouldReconnectSocket({ activeToken: 1, socketToken: 1, manualClose: true }),
    false,
  );
  assert.equal(
    shouldReconnectSocket({ activeToken: 1, socketToken: 1, manualClose: false }),
    true,
  );
  assert.equal(
    shouldReconnectSocket({ activeToken: 1, socketToken: 1, manualClose: false, closed: true }),
    false,
  );

  FakeWebSocket.instances = [];
  const transport = createSocketTransport({
    WebSocketImpl: FakeWebSocket,
    locationObject: { protocol: "https:", host: "localhost:8443" },
  });
  const channel = transport.connect({ path: "/ws" });
  const socket = FakeWebSocket.instances[0];
  const messages = [];
  const states = [];
  channel.onMessage((message) => messages.push(message));
  channel.onStateChange((state) => states.push(state));

  assert.equal(socket.url, "wss://localhost:8443/ws");
  assert.deepEqual(states, ["connecting"]);
  socket.onopen({});
  socket.onmessage({ data: '{"type":"session_event"}' });
  channel.send({ type: "client_event" });
  channel.close();

  assert.deepEqual(messages, [{ type: "session_event" }]);
  assert.deepEqual(states, ["connecting", "open", "closed"]);
  assert.deepEqual(socket.sent, ['{"type":"client_event"}']);
  assert.equal(socket.closeCalls, 1);
  channel.close();
  assert.equal(socket.closeCalls, 1);
}
