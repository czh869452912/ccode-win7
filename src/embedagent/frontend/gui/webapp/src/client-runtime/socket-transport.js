function defaultLocation() {
  if (typeof window !== "undefined" && window.location) return window.location;
  return { protocol: "http:", host: "localhost" };
}

function defaultWebSocket() {
  if (typeof WebSocket === "undefined") return null;
  return WebSocket;
}

function socketUrl(location, path) {
  const value = String(path || "");
  if (/^wss?:\/\//.test(value)) return value;
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const normalizedPath = value.startsWith("/") ? value : "/" + value;
  return protocol + "//" + location.host + normalizedPath;
}

function decodeMessage(value) {
  if (typeof value !== "string") return value;
  return JSON.parse(value);
}

export function createSocketTransport({ WebSocketImpl, locationObject, timer } = {}) {
  const location = locationObject || defaultLocation();
  const WebSocketConstructor = WebSocketImpl || defaultWebSocket();

  function connect({ path } = {}) {
    if (typeof WebSocketConstructor !== "function") {
      throw new Error("websocket_unavailable");
    }
    const socket = new WebSocketConstructor(socketUrl(location, path));
    const messageListeners = new Set();
    const stateListeners = new Set();
    let state = "connecting";
    let closed = false;

    function publishState(nextState) {
      if (state === nextState) return;
      state = nextState;
      for (const listener of stateListeners) listener(state);
    }

    socket.onopen = () => publishState("open");
    socket.onerror = () => publishState("error");
    socket.onclose = () => {
      closed = true;
      publishState("closed");
    };
    socket.onmessage = (event) => {
      try {
        const message = decodeMessage(event.data);
        for (const listener of messageListeners) listener(message);
      } catch (_) {
        publishState("error");
      }
    };

    function onMessage(listener) {
      if (typeof listener !== "function") return () => {};
      messageListeners.add(listener);
      return () => messageListeners.delete(listener);
    }

    function onStateChange(listener) {
      if (typeof listener !== "function") return () => {};
      stateListeners.add(listener);
      listener(state);
      return () => stateListeners.delete(listener);
    }

    function send(message) {
      if (closed) throw new Error("socket_channel_closed");
      socket.send(typeof message === "string" ? message : JSON.stringify(message));
    }

    function close() {
      if (closed) return;
      closed = true;
      socket.close();
      publishState("closed");
    }

    return Object.freeze({ send, onMessage, onStateChange, close });
  }

  return Object.freeze({ connect });
}
