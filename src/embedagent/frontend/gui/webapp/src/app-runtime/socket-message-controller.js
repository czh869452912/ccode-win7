import { createSocketEffectExecutor } from "./socket-effect-executor.js";
import { deriveSocketMessageEffects } from "./socket-message-effects.js";

function readMessageInput(messageOrType, data) {
  if (typeof messageOrType === "object" && messageOrType !== null && data === undefined) {
    return {
      type: messageOrType.type || "",
      data: messageOrType.data || {},
    };
  }
  return {
    type: messageOrType || "",
    data: data || {},
  };
}

export function createSocketMessageController({
  dispatch,
  executeLoaderRequest,
  getSessionTransportController,
  getSessionTransportState,
  updateSessionTransportState,
  getCurrentSessionId,
  loadSession,
  getDiffPanelChrome,
  makeId,
  nowIso,
  scheduleMessage,
  deriveEffects,
  executeEffects,
} = {}) {
  const readCurrentSessionId =
    typeof getCurrentSessionId === "function" ? getCurrentSessionId : () => "";
  const readTransportState =
    typeof getSessionTransportState === "function" ? getSessionTransportState : () => null;
  const readDiffPanelChrome =
    typeof getDiffPanelChrome === "function" ? getDiffPanelChrome : () => ({});
  const buildEffects =
    typeof deriveEffects === "function" ? deriveEffects : deriveSocketMessageEffects;
  const schedule =
    typeof scheduleMessage === "function" ? scheduleMessage : (callback) => callback();
  const applyEffects =
    typeof executeEffects === "function"
      ? executeEffects
      : createSocketEffectExecutor({
          dispatch,
          executeLoaderRequest,
          getSessionTransportController,
          getSessionTransportState,
          updateSessionTransportState,
          getCurrentSessionId,
          loadSession,
        });

  function handleMessage(messageOrType, data) {
    return schedule(() => {
      const message = readMessageInput(messageOrType, data);
      const effects = buildEffects({
        type: message.type,
        data: message.data,
        currentSessionId: readCurrentSessionId(),
        sessionTransport: readTransportState(),
        makeId,
        nowIso,
        diffPanelChrome: readDiffPanelChrome(),
      });
      applyEffects(effects);
      return effects;
    });
  }

  return { handleMessage };
}
