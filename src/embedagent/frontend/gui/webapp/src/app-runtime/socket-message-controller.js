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
  getCurrentSessionId,
  clearRespondingRequestId,
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
          getCurrentSessionId,
          clearRespondingRequestId,
        });

  function deriveMessageEffects(messageOrType, data) {
    const message = readMessageInput(messageOrType, data);
    return buildEffects({
        type: message.type,
        data: message.data,
        currentSessionId: readCurrentSessionId(),
        sessionTransport: readTransportState(),
        makeId,
        nowIso,
        diffPanelChrome: readDiffPanelChrome(),
      });
  }

  function handleMessage(messageOrType, data) {
    return schedule(() => {
      const effects = deriveMessageEffects(messageOrType, data);
      applyEffects(effects);
      return effects;
    });
  }

  function handleAcceptedSessionEvent(envelope) {
    return schedule(() => {
      const effects = deriveMessageEffects("session_event", envelope);
      const acceptedEffects = {
        ...effects,
        transportEvents: [],
      };
      applyEffects(acceptedEffects);
      return acceptedEffects;
    });
  }

  return { handleAcceptedSessionEvent, handleMessage };
}
