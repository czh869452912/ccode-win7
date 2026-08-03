import {
  applySessionTransportEvent,
  bufferSessionTransportEvent,
  capRetryAttempt,
} from "../session-runtime/session-transport-state.js";
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
  let recoveryPromise = null;
  let recoveryToken = -1;
  let recoverySessionId = "";
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
  const loadSessionBootstrap =
    typeof loadSession === "function" ? loadSession : () => Promise.resolve();
  const dispatchMessage = typeof handleMessage === "function" ? handleMessage : () => {};

  function abortActiveBootstrap() {
    if (typeof loadSessionBootstrap.abort === "function") loadSessionBootstrap.abort();
  }

  function recover(sessionId) {
    if (closed || !sessionId) return Promise.resolve({ stale: true });
    if (recoveryPromise && recoveryToken === token && recoverySessionId === sessionId) {
      return recoveryPromise;
    }
    updateTransport((current) => ({
      ...current,
      connectionState: current.connectionState === "degraded" ? "degraded" : "connected",
      reloadState: current.reloadState === "degraded" ? "degraded" : "reload_required",
    }));
    const activeRecoveryToken = token;
    let pending = null;
    pending = Promise.resolve()
      .then(() => {
        if (closed || token !== activeRecoveryToken || recoveryPromise !== pending) {
          return { stale: true };
        }
        return loadSessionBootstrap(sessionId, { reason: "gap" });
      })
      .catch(() => {
        if (closed || token !== activeRecoveryToken || recoveryPromise !== pending) {
          return { stale: true };
        }
        updateTransport((current) => ({
          ...current,
          connectionState: "degraded",
          reloadState: "degraded",
        }));
      })
      .finally(() => {
        if (recoveryPromise !== pending) return;
        recoveryPromise = null;
        recoveryToken = -1;
        recoverySessionId = "";
      });
    recoveryPromise = pending;
    recoveryToken = activeRecoveryToken;
    recoverySessionId = sessionId;
    return pending;
  }

  function channelIsStale(activeChannel, channelToken) {
    return closed || token !== channelToken || channel !== activeChannel;
  }

  function releaseSubscriptions() {
    if (typeof unsubscribeMessage === "function") unsubscribeMessage();
    if (typeof unsubscribeState === "function") unsubscribeState();
    unsubscribeMessage = null;
    unsubscribeState = null;
  }

  function scheduleReconnect(activeChannel, channelToken) {
    updateTransport((current) => ({ ...current, connectionState: "disconnected" }));
    if (
      !shouldReconnectSocket({
        activeToken: token,
        socketToken: channelToken,
        manualClose,
        closed,
      })
    ) {
      return;
    }
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
    if (recoveryPromise) abortActiveBootstrap();
    const channelToken = token + 1;
    token = channelToken;
    const activeChannel = openSessionEvents();
    channel = activeChannel;
    let closeHandled = false;

    unsubscribeMessage = activeChannel.onMessage((message) => {
      if (channelIsStale(activeChannel, channelToken)) return;
      dispatchMessage(message);
    });
    unsubscribeState = activeChannel.onStateChange(async (state) => {
      if (channelIsStale(activeChannel, channelToken)) return;
      if (state === "open") {
        updateTransport((current) => ({ ...current, connectionState: "connected" }));
        retryAttempt = 0;
        const sessionId = readCurrentSessionId();
        const transportState = readTransportState();
        if (sessionId && transportState.reloadState !== "healthy") await recover(sessionId);
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

  function applyEvent(event) {
    let result = null;
    updateTransport((current) => {
      if (current.phase === "buffering") {
        const state = bufferSessionTransportEvent(current, event);
        result = { state, accepted: false, reason: "buffered_event" };
        return state;
      }
      result = applySessionTransportEvent(current, event);
      return result.state;
    });
    return result;
  }

  function close() {
    if (closed) return;
    closed = true;
    manualClose = true;
    token += 1;
    if (retryTimerId !== null) clock.clearTimeout(retryTimerId);
    retryTimerId = null;
    abortActiveBootstrap();
    recoveryPromise = null;
    recoveryToken = -1;
    recoverySessionId = "";
    const activeChannel = channel;
    channel = null;
    releaseSubscriptions();
    if (activeChannel) activeChannel.close();
  }

  return { connect, close, recover, applyEvent };
}
