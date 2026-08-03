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

function defaultLocation() {
  if (typeof window !== "undefined") return window.location;
  return { protocol: "http:", host: "localhost" };
}

function defaultSocketFactory(url) {
  return new WebSocket(url);
}

export function createSessionTransportController({
  getCurrentSessionId,
  getTransportState,
  updateTransportState,
  loadSession,
  handleMessage,
  socketFactory,
  locationObject,
  timer,
} = {}) {
  let socket = null;
  let token = 0;
  let manualClose = false;
  let retryAttempt = 0;
  let retryTimerId = null;
  let closed = false;
  let recoveryPromise = null;
  let recoveryToken = -1;
  let recoverySessionId = "";
  const location = locationObject || defaultLocation();
  const clock = timer || defaultTimer();
  const makeSocket = socketFactory || defaultSocketFactory;
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
    if (typeof loadSessionBootstrap.abort === "function") {
      loadSessionBootstrap.abort();
    }
  }

  function recover(sessionId) {
    if (closed || !sessionId) return Promise.resolve({ stale: true });
    if (
      recoveryPromise &&
      recoveryToken === token &&
      recoverySessionId === sessionId
    ) {
      return recoveryPromise;
    }
    updateTransport((current) => ({
      ...current,
      connectionState: current.connectionState === "degraded" ? "degraded" : "connected",
      reloadState:
        current.reloadState === "degraded" ? "degraded" : "reload_required",
    }));
    const activeRecoveryToken = token;
    let pending = null;
    pending = Promise.resolve()
      .then(() => {
        if (
          closed ||
          token !== activeRecoveryToken ||
          recoveryPromise !== pending
        ) {
          return { stale: true };
        }
        return loadSessionBootstrap(sessionId, { reason: "gap" });
      })
      .catch(() => {
        if (
          closed ||
          token !== activeRecoveryToken ||
          recoveryPromise !== pending
        ) {
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

  function socketIsStale(activeSocket, socketToken) {
    return closed || token !== socketToken || socket !== activeSocket;
  }

  function connect() {
    if (closed || socket) return socket;
    manualClose = false;
    if (retryTimerId !== null) {
      clock.clearTimeout(retryTimerId);
      retryTimerId = null;
    }
    if (recoveryPromise) abortActiveBootstrap();
    const socketToken = token + 1;
    token = socketToken;
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const activeSocket = makeSocket(`${protocol}//${location.host}/ws`);
    socket = activeSocket;
    let closeHandled = false;
    activeSocket.onopen = async () => {
      if (socketIsStale(activeSocket, socketToken)) return;
      updateTransport((current) => ({ ...current, connectionState: "connected" }));
      retryAttempt = 0;
      const sessionId = readCurrentSessionId();
      const state = readTransportState();
      if (sessionId && state.reloadState !== "healthy") {
        await recover(sessionId);
      }
    };
    activeSocket.onclose = () => {
      if (socketIsStale(activeSocket, socketToken) || closeHandled) return;
      closeHandled = true;
      updateTransport((current) => ({ ...current, connectionState: "disconnected" }));
      if (
        !shouldReconnectSocket({
          activeToken: token,
          socketToken,
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
        if (closed || token !== socketToken || manualClose) return;
        if (socket === activeSocket) socket = null;
        connect();
      }, delay);
    };
    activeSocket.onerror = () => {
      if (socketIsStale(activeSocket, socketToken)) return;
      updateTransport((current) => ({
        ...current,
        connectionState: "degraded",
        reloadState: "reload_required",
      }));
    };
    activeSocket.onmessage = (event) => {
      if (socketIsStale(activeSocket, socketToken)) return;
      try {
        dispatchMessage(JSON.parse(event.data));
      } catch (_) {
        updateTransport((current) => ({
          ...current,
          connectionState: "degraded",
          reloadState: "degraded",
        }));
      }
    };
    return activeSocket;
  }

  function applyEvent(event) {
    let result = null;
    updateTransport((current) => {
      if (current.phase === "buffering") {
        const state = bufferSessionTransportEvent(current, event);
        result = {
          state,
          accepted: false,
          reason: "buffered_event",
        };
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
    if (retryTimerId !== null) {
      clock.clearTimeout(retryTimerId);
    }
    retryTimerId = null;
    abortActiveBootstrap();
    recoveryPromise = null;
    recoveryToken = -1;
    recoverySessionId = "";
    const activeSocket = socket;
    socket = null;
    if (activeSocket) {
      activeSocket.onopen = null;
      activeSocket.onmessage = null;
      activeSocket.onerror = null;
      activeSocket.onclose = null;
      activeSocket.close();
    }
  }

  return { connect, close, recover, applyEvent };
}
