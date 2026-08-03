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
  protocol,
  dispatch,
  normalizeSessionPayload,
  getCurrentSessionId,
  getCurrentInteraction,
  getRespondingRequestIds,
  setRespondingRequestIds,
  loadSession,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const respond =
    protocol && typeof protocol.respondToInteraction === "function"
      ? protocol.respondToInteraction.bind(protocol)
      : null;
  const normalize =
    typeof normalizeSessionPayload === "function" ? normalizeSessionPayload : (payload) => payload;
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
    let keepResponding = false;
    try {
      const response = await respond(sessionId, interactionId, payload || {});
      if (response?.status === "accepted") {
        keepResponding = true;
      } else if (response?.snapshot) {
        send({ type: "session_snapshot", snapshot: normalize(response.snapshot) });
      } else {
        await reloadSession(sessionId);
      }
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
      if (!keepResponding) clearResponding(interactionId);
    }
  }

  return { respondToInteraction };
}
