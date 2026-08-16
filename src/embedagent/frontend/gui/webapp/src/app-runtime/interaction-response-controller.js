function interactionIdFor(interaction) {
  return String(
    interaction?.interactionId ||
      interaction?.interaction_id ||
      interaction?.permission_id ||
      interaction?.request_id ||
      "",
  ).trim();
}

function interactionLogDetail(interaction, payload) {
  if (interaction?.kind === "permission") return String(payload?.decision || "");
  return String(payload?.answers?.answer || "").slice(0, 40);
}

export function createInteractionResponseController({
  sessionRuntime,
  dispatch,
  getCurrentSessionId,
  getCurrentInteraction,
  getRespondingRequestIds,
  setRespondingRequestIds,
  loadSession,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const respond =
    sessionRuntime && typeof sessionRuntime.respondToInteraction === "function"
      ? sessionRuntime.respondToInteraction.bind(sessionRuntime)
      : null;
  const readSessionId = typeof getCurrentSessionId === "function" ? getCurrentSessionId : () => "";
  const readInteraction =
    typeof getCurrentInteraction === "function" ? getCurrentInteraction : () => null;
  const readRespondingIds =
    typeof getRespondingRequestIds === "function" ? getRespondingRequestIds : () => [];
  const writeRespondingIds =
    typeof setRespondingRequestIds === "function" ? setRespondingRequestIds : () => {};
  const reloadSession = typeof loadSession === "function" ? loadSession : () => Promise.resolve();

  function respondingIds() {
    const value = readRespondingIds();
    return Array.isArray(value) ? value.map((item) => String(item || "")) : [];
  }

  function isResponding(id) {
    return respondingIds().includes(id);
  }

  function markResponding(id) {
    writeRespondingIds((existing) => {
      const current = Array.isArray(existing) ? existing : [];
      return current.includes(id) ? current : [...current, id];
    });
  }

  function clearResponding(id) {
    writeRespondingIds((existing) => {
      const current = Array.isArray(existing) ? existing : [];
      return current.filter((value) => value !== id);
    });
  }

  async function respondToInteraction(payload) {
    if (!respond) return null;
    const sessionId = String(readSessionId() || "");
    const interaction = readInteraction();
    const interactionId = interactionIdFor(interaction);
    if (!sessionId || !interactionId || isResponding(interactionId)) return null;

    markResponding(interactionId);
    send({ type: "interaction_notice_clear" });
    try {
      const response = await respond(sessionId, interactionId, payload || {});
      if (!response?.thread?.id) throw new Error("invalid_session_bootstrap_response");
      send({
        type: "log_event",
        label: "interaction_response",
        detail: interactionLogDetail(interaction, payload || {}),
      });
      return response;
    } catch (error) {
      if ((error?.status === 409 || error?.status === 410) && sessionId) {
        await reloadSession(sessionId);
        send({
          type: "interaction_notice_set",
          notice: {
            kind: error.status === 410 ? "expired" : "conflict",
            detail: error.detail || "",
          },
        });
        send({
          type: "log_event",
          label: "interaction_response",
          detail: error.detail || `HTTP ${error.status}`,
        });
        return null;
      }
      throw error;
    } finally {
      clearResponding(interactionId);
    }
  }

  return { respondToInteraction };
}
