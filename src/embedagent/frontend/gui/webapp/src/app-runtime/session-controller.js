export function createSessionController({
  fetchJson,
  dispatch,
  normalizeSessionPayload,
  createRuntimeSessionTransport,
  replaceSessionTransport,
  getCurrentSessionId,
  getCurrentMode,
  hasActiveWorkspace,
  markTimelineBottom,
  loadSessions,
  loadTasks,
  loadPermissionContext,
  loadSession,
}) {
  async function createSession(mode) {
    const payload = await fetchJson(`/api/sessions?mode=${encodeURIComponent(mode)}`, {
      method: "POST",
    });
    const snapshot = normalizeSessionPayload(payload);
    dispatch({ type: "session_activated", sessionId: snapshot.session_id, snapshot, timeline: [] });
    replaceSessionTransport(createRuntimeSessionTransport());
    await Promise.all([
      loadSessions(),
      loadTasks(snapshot.session_id),
      loadPermissionContext(snapshot.session_id),
    ]);
    return snapshot.session_id;
  }

  async function setMode(mode) {
    dispatch({ type: "mode_requested", mode });
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    await loadSession(sessionId);
  }

  async function cancelSession() {
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    dispatch({ type: "stream_completed" });
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/cancel`, {
      method: "POST",
    });
  }

  async function submitText(rawText) {
    const text = (rawText || "").trim();
    if (!text) return;
    if (!hasActiveWorkspace()) {
      dispatch({ type: "workspace_activation_failed", error: "no_active_workspace" });
      return;
    }
    if (typeof markTimelineBottom === "function") {
      markTimelineBottom();
    }
    dispatch({ type: "stream_completed" });
    dispatch({ type: "local_user_message", text });
    let sessionId = getCurrentSessionId();
    if (!sessionId) sessionId = await createSession(getCurrentMode());
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  }

  return { createSession, setMode, cancelSession, submitText };
}
