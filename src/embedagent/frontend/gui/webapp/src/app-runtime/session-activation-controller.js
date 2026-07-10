import { deriveSessionActivation as defaultDeriveSessionActivation } from "./session-loaders.js";
import { terminalCapabilityEnabled } from "../terminal/terminal-capability.js";

function invoke(callback, ...args) {
  if (typeof callback !== "function") {
    return Promise.resolve();
  }
  return Promise.resolve().then(() => callback(...args));
}

export function createSessionActivationController({
  fetchJson,
  dispatch,
  deriveSessionActivation,
  defaultMode = "",
  createTransportState,
  replaceTransportState,
  listTerminals,
  appCapabilities,
  getAppCapabilities,
} = {}) {
  const fetchBootstrap = typeof fetchJson === "function" ? fetchJson : () => Promise.resolve({});
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const derive = deriveSessionActivation || defaultDeriveSessionActivation;
  const buildTransportState =
    typeof createTransportState === "function" ? createTransportState : () => ({});
  const replaceTransport =
    typeof replaceTransportState === "function" ? replaceTransportState : () => {};
  const readAppCapabilities = () => {
    const value =
      typeof getAppCapabilities === "function" ? getAppCapabilities() : appCapabilities;
    return value && typeof value === "object" ? value : {};
  };

  return async function loadSession(sessionId) {
    const payload = await fetchBootstrap(
      `/api/sessions/${encodeURIComponent(sessionId)}/bootstrap`,
    );
    const activation = derive(payload, sessionId, { defaultMode });
    send({
      type: "session_activated",
      sessionId: activation.sessionId,
      snapshot: activation.snapshot,
      activities: activation.activities,
      historyIntegrity: activation.historyIntegrity,
      capabilities: activation.capabilities,
    });
    replaceTransport(buildTransportState());
    send({ type: "plan_loaded", plan: activation.plan });
    if (!terminalCapabilityEnabled(readAppCapabilities())) return;
    try {
      const terminalPayload = await invoke(listTerminals, sessionId);
      send({
        type: "terminal_summaries_loaded",
        terminals: terminalPayload?.terminals || [],
      });
    } catch (_) {
      send({ type: "terminal_summaries_loaded", terminals: [] });
    }
  };
}
