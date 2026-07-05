export function createSessionListController({ fetchJson, dispatch } = {}) {
  const request = typeof fetchJson === "function" ? fetchJson : () => Promise.resolve({});
  const send = typeof dispatch === "function" ? dispatch : () => {};

  async function loadSessions() {
    const payload = await request("/api/sessions");
    const sessions = Array.isArray(payload?.sessions) ? payload.sessions : [];
    send({ type: "sessions_loaded", sessions });
    return sessions;
  }

  return { loadSessions };
}
