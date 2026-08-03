import {
  applySessionTransportEvent,
  bufferSessionTransportEvent,
  capRetryAttempt,
} from "../session-runtime/session-transport-state.js";
import { shouldReconnectSocket } from "../session-runtime/websocket-lifecycle.js";

function defaultTimer() {
  if (typeof window !== "undefined") return window;
  return { setTimeout };
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
  let recoveryPromise = null;
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

  function recover(sessionId) {
    if (!sessionId) return Promise.resolve();
    if (recoveryPromise) return recoveryPromise;
    updateTransport((current) => ({
      ...current,
      connectionState: current.connectionState === "degraded" ? "degraded" : "connected",
      reloadState:
        current.reloadState === "degraded" ? "degraded" : "reload_required",
    }));
    recoveryPromise = Promise.resolve()
      .then(() => loadSessionBootstrap(sessionId, { reason: "gap" }))
      .catch(() => {
        updateTransport((current) => ({
          ...current,
          connectionState: "degraded",
          reloadState: "degraded",
        }));
      })
      .finally(() => {
        recoveryPromise = null;
      });
    return recoveryPromise;
  }

  function connect() {
    manualClose = false;
    const socketToken = token + 1;
    token = socketToken;
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    socket = makeSocket(`${protocol}//${location.host}/ws`);
    socket.onopen = async () => {
      updateTransport((current) => ({ ...current, connectionState: "connected" }));
      retryAttempt = 0;
      const sessionId = readCurrentSessionId();
      const state = readTransportState();
      if (sessionId && state.reloadState !== "healthy") {
        await recover(sessionId, state);
      }
    };
    socket.onclose = () => {
      updateTransport((current) => ({ ...current, connectionState: "disconnected" }));
      if (!shouldReconnectSocket({ activeToken: token, socketToken, manualClose })) return;
      retryAttempt = capRetryAttempt(retryAttempt + 1);
      const delay = Math.min(1500 * Math.pow(2, Math.max(retryAttempt - 1, 0)), 30000);
      clock.setTimeout(connect, delay);
    };
    socket.onerror = () => {
      updateTransport((current) => ({
        ...current,
        connectionState: "degraded",
        reloadState: "reload_required",
      }));
    };
    socket.onmessage = (event) => {
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
    manualClose = true;
    if (socket) socket.close();
    socket = null;
  }

  return { connect, close, recover, applyEvent };
}
