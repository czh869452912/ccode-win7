function requireProtocolMethod(protocol, name) {
  const method = protocol && protocol[name];
  if (typeof method !== "function") {
    throw new Error(`protocol_method_missing:${name}`);
  }
  return method.bind(protocol);
}

function requireSessionRuntimeMethod(sessionRuntime, name) {
  const method = sessionRuntime && sessionRuntime[name];
  if (typeof method !== "function") {
    throw new Error(`session_runtime_method_missing:${name}`);
  }
  return method.bind(sessionRuntime);
}

export function createSessionController({
  protocol,
  sessionRuntime,
  dispatch,
  getCurrentSessionId,
  getCurrentMode,
  hasActiveWorkspace,
  markTimelineBottom,
  loadSessions,
}) {
  const createSessionRequest = requireSessionRuntimeMethod(sessionRuntime, "createSession");
  const setSessionMode = requireSessionRuntimeMethod(sessionRuntime, "setSessionMode");
  const cancelSessionRequest = requireSessionRuntimeMethod(sessionRuntime, "cancelSession");
  const sendSessionMessage = requireProtocolMethod(protocol, "sendSessionMessage");

  async function createSession(mode) {
    const requestedMode = String(mode || "").trim();
    const bootstrap = await createSessionRequest(requestedMode);
    await loadSessions();
    return String(bootstrap?.thread?.id || "");
  }

  async function setMode(mode) {
    dispatch({ type: "mode_requested", mode });
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    await setSessionMode(sessionId, mode);
  }

  async function cancelSession() {
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    dispatch({ type: "stream_completed" });
    await cancelSessionRequest(sessionId);
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
