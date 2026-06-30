function interactionIdFor(interaction) {
  return String(
    interaction?.interaction_id ||
      interaction?.permission_id ||
      interaction?.request_id ||
      "",
  ).trim();
}

function interactionLogDetail(interaction, payload) {
  if (interaction?.kind === "permission") {
    return payload?.decision ? "approved" : "denied";
  }
  return String(payload?.answer || payload?.selected_option_text || "").slice(0, 40);
}

export function createInteractionResponseController({
  fetchJson,
  dispatch,
  normalizeSessionPayload,
  getCurrentSessionId,
  getCurrentInteraction,
  getResponseInFlight,
  setResponseInFlight,
  loadSession,
  loadPermissionContext,
  clearUserAnswer,
  logEvent,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const fetchPayload = typeof fetchJson === "function" ? fetchJson : () => Promise.resolve({});
  const normalize =
    typeof normalizeSessionPayload === "function" ? normalizeSessionPayload : (payload) => payload;
  const readSessionId = typeof getCurrentSessionId === "function" ? getCurrentSessionId : () => "";
  const readInteraction =
    typeof getCurrentInteraction === "function" ? getCurrentInteraction : () => null;
  const readInFlight =
    typeof getResponseInFlight === "function" ? getResponseInFlight : () => "";
  const writeInFlight =
    typeof setResponseInFlight === "function" ? setResponseInFlight : () => {};
  const reloadSession = typeof loadSession === "function" ? loadSession : () => Promise.resolve();
  const reloadPermissions =
    typeof loadPermissionContext === "function" ? loadPermissionContext : () => {};
  const clearAnswer = typeof clearUserAnswer === "function" ? clearUserAnswer : () => {};
  const recordEvent = typeof logEvent === "function" ? logEvent : () => {};

  async function respondToInteraction(payload) {
    const sessionId = String(readSessionId() || "");
    const interaction = readInteraction();
    const interactionId = interactionIdFor(interaction);
    if (!sessionId || !interactionId) return null;
    if (readInFlight()) return null;

    writeInFlight(interactionId);
    send({ type: "interaction_notice_clear" });
    try {
      const response = await fetchPayload(
        `/api/sessions/${encodeURIComponent(sessionId)}/interactions/${encodeURIComponent(interactionId)}/respond`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload || {}),
        },
      );
      if (response?.snapshot) {
        send({
          type: "session_snapshot",
          snapshot: normalize(response.snapshot),
        });
      } else {
        await reloadSession(sessionId);
      }
      if (interaction.kind === "permission") {
        if (payload?.decision && payload?.remember) {
          reloadPermissions(sessionId);
        }
      } else {
        clearAnswer();
      }
      recordEvent("interaction_response", interactionLogDetail(interaction, payload || {}));
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
        recordEvent("interaction_response", error.detail || `HTTP ${error.status}`);
        return null;
      }
      throw error;
    } finally {
      if (readInFlight() === interactionId) {
        writeInFlight("");
      }
    }
  }

  return { respondToInteraction };
}
