import assert from "node:assert/strict";

import { createSessionTransportHandle } from "../src/app-runtime/session-transport-handle.js";
import { createSessionTransportState } from "../src/session-runtime/session-transport-state.js";

export function runSessionTransportHandleTests() {
  const written = [];
  const initial = createSessionTransportState({
    connectionState: "degraded",
    reloadState: "reload_required",
    lastAppliedSeq: 2,
  });
  const handle = createSessionTransportHandle({
    initialTransport: initial,
    setTransport: (transport) => written.push(transport),
  });

  assert.equal(handle.read(), initial);
  const replaced = {
    ...createSessionTransportState({
      connectionState: "connected",
      reloadState: "healthy",
    }),
    lastAppliedSeq: 3,
  };
  assert.equal(handle.replace(replaced), replaced);
  assert.equal(handle.read(), replaced);
  assert.deepEqual(written, [replaced]);

  const updated = handle.update((current) => ({
    ...current,
    reloadState: "degraded",
    lastAppliedSeq: current.lastAppliedSeq + 1,
  }));
  assert.equal(updated.reloadState, "degraded");
  assert.equal(updated.lastAppliedSeq, 4);
  assert.equal(handle.read(), updated);
  assert.equal(written[1], updated);

  const runtimeTransport = handle.createRuntimeTransport();
  assert.equal(runtimeTransport.connectionState, "connected");
  assert.equal(runtimeTransport.reloadState, "healthy");
  assert.equal(runtimeTransport.lastAppliedSeq, 0);

  const synced = createSessionTransportState({ connectionState: "disconnected" });
  assert.equal(handle.sync(synced), synced);
  assert.equal(handle.read(), synced);
}
