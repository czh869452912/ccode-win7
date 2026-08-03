function requireProtocolMethod(protocol, name) {
  const method = protocol && protocol[name];
  if (typeof method !== "function") {
    throw new Error(`protocol_method_missing:${name}`);
  }
  return method.bind(protocol);
}

export function createSessionController({
  protocol,
  dispatch,
  normalizeSessionPayload,
  getCurrentSessionId,
  getCurrentMode,
  hasActiveWorkspace,
  markTimelineBottom,
  loadSessions,
  loadSession,
}) {
  const createSessionRequest = requireProtocolMethod(protocol, "createSession");
  const setSessionMode = requireProtocolMethod(protocol, "setSessionMode");
  const cancelSessionRequest = requireProtocolMethod(protocol, "cancelSession");
  const sendSessionMessage = requireProtocolMethod(protocol, "sendSessionMessage");

  async function createSession(mode) {
    const requestedMode = String(mode || "").trim();
    const payload = await createSessionRequest(requestedMode);
    const snapshot = normalizeSessionPayload(payload);
    await Promise.all([loadSessions(), loadSession(snapshot.session_id)]);
    return snapshot.session_id;
  }

  async function setMode(mode) {
    dispatch({ type: "mode_requested", mode });
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    await setSessionMode(sessionId, mode);
    await loadSession(sessionId);
  }

  async function cancelSession() {
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    dispatch({ type: "stream_completed" });
    const snapshot = await cancelSessionRequest(sessionId);
    if (snapshot?.session_id) {
      dispatch({ type: "session_snapshot", snapshot: normalizeSessionPayload(snapshot) });
    }
  }

  async function submitText(rawText) {
    const text = (rawText || "").trim();
    if (!text) return;
    if (!hasActiveWorkspace()) {
      dispatch({ type: "workspace_activation_failed", error: "no_active_workspace" });
      return;
    }
    if (typeof markTimelineBottom === "function") markTimelineBottom();
    dispatch({ type: "stream_completed" });
    dispatch({ type: "local_user_message", text });
    let sessionId = getCurrentSessionId();
    if (!sessionId) sessionId = await createSession(getCurrentMode());
    await sendSessionMessage(sessionId, text);
  }

  return { createSession, setMode, cancelSession, submitText };
}
