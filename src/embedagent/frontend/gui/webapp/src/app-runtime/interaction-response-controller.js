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
    return String(payload?.decision || "");
  }
  return String(payload?.answers?.answer || "").slice(0, 40);
}

export function createInteractionResponseController({
  fetchJson,
  dispatch,
  normalizeSessionPayload,
  getCurrentSessionId,
  getCurrentInteraction,
  getRespondingRequestIds,
  setRespondingRequestIds,
  loadSession,
  loadPermissionContext,
  logEvent,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const fetchPayload = typeof fetchJson === "function" ? fetchJson : () => Promise.resolve({});
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
  const reloadPermissions =
    typeof loadPermissionContext === "function" ? loadPermissionContext : () => {};
  const recordEvent = typeof logEvent === "function" ? logEvent : () => {};

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
    const sessionId = String(readSessionId() || "");
    const interaction = readInteraction();
    const interactionId = interactionIdFor(interaction);
    if (!sessionId || !interactionId) return null;
    if (isResponding(interactionId)) return null;

    markResponding(interactionId);
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
        if (payload?.decision === "acceptForSession") {
          reloadPermissions(sessionId);
        }
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
      clearResponding(interactionId);
    }
  }

  return { respondToInteraction };
}
