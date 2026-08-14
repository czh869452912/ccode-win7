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
  clearRespondingRequestId,
  getDiffPanelChrome,
  makeId,
  nowIso,
  scheduleMessage,
  deriveEffects,
  executeEffects,
} = {}) {
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
          clearRespondingRequestId,
        });

  function deriveMessageEffects(messageOrType, data) {
    const message = readMessageInput(messageOrType, data);
    return buildEffects({
        type: message.type,
        data: message.data,
        makeId,
        nowIso,
        diffPanelChrome: readDiffPanelChrome(),
      });
  }

  function handleMessage(messageOrType, data) {
    const message = readMessageInput(messageOrType, data);
    if (message.type === "session_event") {
      throw new Error("session_event_requires_runtime_acceptance");
    }
    return schedule(() => {
      const effects = deriveMessageEffects(message.type, message.data);
      applyEffects(effects);
      return effects;
    });
  }

  function handleAcceptedSessionEvent(envelope) {
    return schedule(() => {
      const effects = deriveMessageEffects("session_event", envelope);
      applyEffects(effects);
      return effects;
    });
  }

  return { handleAcceptedSessionEvent, handleMessage };
}
