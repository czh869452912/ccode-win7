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
  getCurrentSessionId,
  getCurrentMode,
  hasActiveWorkspace,
  markTimelineBottom,
  loadSessions,
  installSessionBootstrap,
}) {
  const createSessionRequest = requireProtocolMethod(protocol, "createSession");
  const setSessionMode = requireProtocolMethod(protocol, "setSessionMode");
  const cancelSessionRequest = requireProtocolMethod(protocol, "cancelSession");
  const sendSessionMessage = requireProtocolMethod(protocol, "sendSessionMessage");
  if (typeof installSessionBootstrap !== "function") {
    throw new Error("session_runtime_method_missing:installSessionBootstrap");
  }

  async function createSession(mode) {
    const requestedMode = String(mode || "").trim();
    const bootstrap = await createSessionRequest(requestedMode);
    await installSessionBootstrap(bootstrap, "create");
    await loadSessions();
    return String(bootstrap?.thread?.id || "");
  }

  async function setMode(mode) {
    dispatch({ type: "mode_requested", mode });
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    const bootstrap = await setSessionMode(sessionId, mode);
    await installSessionBootstrap(bootstrap, "mode_changed");
  }

  async function cancelSession() {
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    dispatch({ type: "stream_completed" });
    const bootstrap = await cancelSessionRequest(sessionId);
    await installSessionBootstrap(bootstrap, "cancel");
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
