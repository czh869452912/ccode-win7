import { createSessionTransportState } from "../session-runtime/session-transport-state.js";

export function createSessionTransportHandle({
  initialTransport,
  setTransport,
  createTransportState = createSessionTransportState,
} = {}) {
  let currentTransport = initialTransport || createTransportState();
  const writeTransport = typeof setTransport === "function" ? setTransport : () => {};

  function read() {
    return currentTransport;
  }

  function sync(nextTransport) {
    currentTransport = nextTransport || createTransportState();
    return currentTransport;
  }

  function replace(nextTransport) {
    currentTransport = nextTransport || createTransportState();
    writeTransport(currentTransport);
    return currentTransport;
  }

  function update(updater) {
    const nextTransport =
      typeof updater === "function" ? updater(currentTransport) : currentTransport;
    return replace(nextTransport);
  }

  function createRuntimeTransport() {
    return createTransportState({
      connectionState: currentTransport?.connectionState || "connecting",
      reloadState: "healthy",
    });
  }

  return { createRuntimeTransport, read, replace, sync, update };
}
