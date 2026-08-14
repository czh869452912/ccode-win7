import { capRetryAttempt } from "../session-runtime/session-transport-state.js";
import { shouldReconnectSocket } from "../session-runtime/websocket-lifecycle.js";

function defaultTimer() {
  if (typeof window !== "undefined") return window;
  return { clearTimeout, setTimeout };
}

function requireProtocolMethod(protocol, name) {
  const method = protocol && protocol[name];
  if (typeof method !== "function") throw new Error(`protocol_method_missing:${name}`);
  return method.bind(protocol);
}

export function createSessionTransportController({
  protocol,
  getCurrentSessionId,
  getTransportState,
  updateTransportState,
  loadSession,
  handleMessage,
  timer,
} = {}) {
  let channel = null;
  let unsubscribeMessage = null;
  let unsubscribeState = null;
  let token = 0;
  let manualClose = false;
  let retryAttempt = 0;
  let retryTimerId = null;
  let closed = false;
  const clock = timer || defaultTimer();
  const openSessionEvents = requireProtocolMethod(protocol, "openSessionEvents");
  const readCurrentSessionId =
    typeof getCurrentSessionId === "function" ? getCurrentSessionId : () => "";
  const readTransportState =
    typeof getTransportState === "function" ? getTransportState : () => ({});
  const updateTransport =
    typeof updateTransportState === "function"
      ? updateTransportState
      : (updater) => updater(readTransportState());
  const reloadSession = typeof loadSession === "function" ? loadSession : () => Promise.resolve();
  const dispatchMessage = typeof handleMessage === "function" ? handleMessage : () => {};

  function releaseSubscriptions() {
    if (typeof unsubscribeMessage === "function") unsubscribeMessage();
    if (typeof unsubscribeState === "function") unsubscribeState();
    unsubscribeMessage = null;
    unsubscribeState = null;
  }

  function channelIsStale(activeChannel, channelToken) {
    return closed || token !== channelToken || channel !== activeChannel;
  }

  function scheduleReconnect(activeChannel, channelToken) {
    updateTransport((current) => ({
      ...current,
      connectionState: "disconnected",
      reloadState: "reload_required",
    }));
    if (!shouldReconnectSocket({
      activeToken: token,
      socketToken: channelToken,
      manualClose,
      closed,
    })) return;
    retryAttempt = capRetryAttempt(retryAttempt + 1);
    const delay = Math.min(1500 * Math.pow(2, Math.max(retryAttempt - 1, 0)), 30000);
    retryTimerId = clock.setTimeout(() => {
      retryTimerId = null;
      if (closed || token !== channelToken || manualClose) return;
      if (channel === activeChannel) {
        releaseSubscriptions();
        channel = null;
      }
      connect();
    }, delay);
  }

  function connect() {
    if (closed || channel) return channel;
    manualClose = false;
    if (retryTimerId !== null) {
      clock.clearTimeout(retryTimerId);
      retryTimerId = null;
    }
    const channelToken = token + 1;
    token = channelToken;
    const activeChannel = openSessionEvents();
    channel = activeChannel;
    let closeHandled = false;

    unsubscribeMessage = activeChannel.onMessage((message) => {
      if (!channelIsStale(activeChannel, channelToken)) dispatchMessage(message);
    });
    unsubscribeState = activeChannel.onStateChange(async (state) => {
      if (channelIsStale(activeChannel, channelToken)) return;
      if (state === "open") {
        const shouldReload = readTransportState().reloadState !== "healthy";
        updateTransport((current) => ({ ...current, connectionState: "connected" }));
        retryAttempt = 0;
        const sessionId = readCurrentSessionId();
        if (sessionId && shouldReload) await reloadSession(sessionId, { reason: "reconnect" });
        return;
      }
      if (state === "error") {
        updateTransport((current) => ({
          ...current,
          connectionState: "degraded",
          reloadState: "reload_required",
        }));
        return;
      }
      if (state === "closed" && !closeHandled) {
        closeHandled = true;
        scheduleReconnect(activeChannel, channelToken);
      }
    });
    return activeChannel;
  }

  function close() {
    if (closed) return;
    closed = true;
    manualClose = true;
    token += 1;
    if (retryTimerId !== null) clock.clearTimeout(retryTimerId);
    retryTimerId = null;
    const activeChannel = channel;
    channel = null;
    releaseSubscriptions();
    if (activeChannel) activeChannel.close();
  }

  return { connect, close };
}
