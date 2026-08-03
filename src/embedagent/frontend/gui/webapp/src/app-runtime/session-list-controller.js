function requireProtocolMethod(protocol, name) {
  const method = protocol && protocol[name];
  if (typeof method !== "function") throw new Error(`protocol_method_missing:${name}`);
  return method.bind(protocol);
}

export function createSessionListController({ protocol, dispatch } = {}) {
  const listSessions = requireProtocolMethod(protocol, "listSessions");
  const send = typeof dispatch === "function" ? dispatch : () => {};

  async function loadSessions() {
    const payload = await listSessions();
    const sessions = Array.isArray(payload?.sessions) ? payload.sessions : [];
    send({ type: "sessions_loaded", sessions });
    return sessions;
  }

  return { loadSessions };
}
