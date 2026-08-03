import { deriveSessionActivation as defaultDeriveSessionActivation } from "./session-loaders.js";
import { terminalCapabilityEnabled } from "../terminal/terminal-capability.js";
import {
  beginSessionTransportBootstrap,
  createSessionTransportState,
  installSessionTransportBootstrap,
} from "../session-runtime/session-transport-state.js";

function defaultAbortController() {
  return new AbortController();
}

function requireProtocolMethod(protocol, name) {
  const method = protocol && protocol[name];
  if (typeof method !== "function") throw new Error(`protocol_method_missing:${name}`);
  return method.bind(protocol);
}

export function createSessionActivationController({
  protocol,
  dispatch,
  deriveSessionActivation,
  defaultMode = "",
  getTransportState,
  updateTransportState,
  dispatchAcceptedSessionEvent,
  createAbortController,
  appCapabilities,
  getAppCapabilities,
} = {}) {
  const fetchBootstrap = requireProtocolMethod(protocol, "loadSessionBootstrap");
  const listTerminals =
    protocol && typeof protocol.listTerminals === "function"
      ? protocol.listTerminals.bind(protocol)
      : null;
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const derive = deriveSessionActivation || defaultDeriveSessionActivation;
  let internalTransport = createSessionTransportState();
  const readTransport =
    typeof getTransportState === "function" ? getTransportState : () => internalTransport;
  const updateTransport =
    typeof updateTransportState === "function"
      ? updateTransportState
      : (updater) => {
          internalTransport = updater(internalTransport);
          return internalTransport;
        };
  const dispatchAccepted =
    typeof dispatchAcceptedSessionEvent === "function"
      ? dispatchAcceptedSessionEvent
      : () => {};
  const makeAbortController =
    typeof createAbortController === "function" ? createAbortController : defaultAbortController;
  const readAppCapabilities = () => {
    const value =
      typeof getAppCapabilities === "function" ? getAppCapabilities() : appCapabilities;
    return value && typeof value === "object" ? value : {};
  };
  let activeRequest = null;

  function requestIsStale(request, sessionId, generation) {
    const current = readTransport();
    return (
      activeRequest !== request ||
      current.sessionId !== sessionId ||
      current.generation !== generation
    );
  }

  async function loadSession(sessionId) {
    const resolvedSessionId = String(sessionId || "");
    if (!resolvedSessionId) return { stale: true };
    if (activeRequest?.controller) activeRequest.controller.abort();
    const request = { controller: makeAbortController() };
    activeRequest = request;
    let generation = 0;
    updateTransport((current) => {
      const next = beginSessionTransportBootstrap(current, resolvedSessionId);
      generation = next.generation;
      return next;
    });

    try {
      const payload = await fetchBootstrap(resolvedSessionId, {
        signal: request.controller.signal,
      });
      if (requestIsStale(request, resolvedSessionId, generation)) return { stale: true };
      const activation = derive(payload, resolvedSessionId, { defaultMode });
      send({
        type: "session_activated",
        sessionId: activation.sessionId,
        snapshot: activation.snapshot,
        activities: activation.activities,
        historyIntegrity: activation.historyIntegrity,
        capabilities: activation.capabilities,
      });
      send({ type: "plan_loaded", plan: activation.plan });

      let installation = null;
      updateTransport((current) => {
        installation = installSessionTransportBootstrap(current, {
          sessionId: resolvedSessionId,
          generation,
          eventCursor: activation.eventCursor,
        });
        return installation.state;
      });
      if (installation.stale || requestIsStale(request, resolvedSessionId, generation)) {
        return { stale: true };
      }
      for (const event of installation.applied) dispatchAccepted(event);

      if (listTerminals && terminalCapabilityEnabled(readAppCapabilities())) {
        try {
          const terminalPayload = await listTerminals(resolvedSessionId);
          if (requestIsStale(request, resolvedSessionId, generation)) return { stale: true };
          send({ type: "terminal_summaries_loaded", terminals: terminalPayload?.terminals || [] });
        } catch (_) {
          if (requestIsStale(request, resolvedSessionId, generation)) return { stale: true };
          send({ type: "terminal_summaries_loaded", terminals: [] });
        }
      }
      return { stale: false, activation, transportState: installation.state };
    } catch (error) {
      if (
        activeRequest !== request ||
        request.controller.signal?.aborted ||
        error?.name === "AbortError"
      ) {
        return { stale: true };
      }
      throw error;
    } finally {
      if (activeRequest === request) activeRequest = null;
    }
  }

  loadSession.abort = () => {
    const request = activeRequest;
    activeRequest = null;
    if (request?.controller) request.controller.abort();
  };
  return loadSession;
}
