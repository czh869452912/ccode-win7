import { normalizeProtocolEnvelope } from "../session-runtime/protocol-envelope.js";

function text(value) {
  return String(value == null ? "" : value);
}

function encode(value) {
  return encodeURIComponent(text(value));
}

function getRequest(fetchJson) {
  return typeof fetchJson === "function" ? fetchJson : () => Promise.resolve({});
}

function jsonOptions(method, body) {
  const options = { method };
  if (body === undefined) return options;
  return {
    ...options,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function createAgentAppProtocolAdapter({
  fetchJson,
  sendSocketMessage,
} = {}) {
  const request = getRequest(fetchJson);

  function requestFor(protocol, url, options) {
    return Promise.resolve(request(url, options)).then((payload) => {
      if (!payload || typeof payload !== "object" || !payload.protocol) return payload;
      const normalized = normalizeProtocolEnvelope(payload, protocol);
      if (!normalized.valid) {
        const error = new Error("invalid_protocol_envelope");
        error.protocol = protocol;
        error.errors = normalized.errors;
        throw error;
      }
      return {
        ...normalized.payload,
        protocolEnvelope: {
          protocol: normalized.protocol,
          version: normalized.version,
          sequence: normalized.sequence,
          revision: normalized.revision,
        },
      };
    });
  }
  const sendSocket =
    typeof sendSocketMessage === "function" ? sendSocketMessage : () => undefined;

  const api = {
    request,
    fetchJson: request,
    loadAppBootstrap() {
      return requestFor("app_shell_v1", "/api/app/bootstrap", jsonOptions("GET"));
    },
    openWorkspacePath(path) {
      return request("/api/app/workspaces", jsonOptions("POST", { path: text(path) }));
    },
    activateWorkspace(workspaceId) {
      return request(
        "/api/app/workspaces/" + encode(workspaceId) + "/activate",
        jsonOptions("POST"),
      );
    },
    removeWorkspace(workspaceId) {
      return request("/api/app/workspaces/" + encode(workspaceId), { method: "DELETE" });
    },
    loadWorkspaceTree(path = ".") {
      return request("/api/files/tree?path=" + encode(path), jsonOptions("GET"));
    },
    readFile(path) {
      return request("/api/files/" + encode(path), jsonOptions("GET"));
    },
    listSessions(limit) {
      const query = limit ? "?limit=" + encode(limit) : "";
      return request("/api/sessions" + query, jsonOptions("GET"));
    },
    loadSessionCapabilities() {
      return requestFor("capability_v1", "/api/sessions/capabilities", jsonOptions("GET"));
    },
    loadSessionBootstrap(sessionId) {
      return requestFor(
        "agent_session_v1",
        "/api/sessions/" + encode(sessionId) + "/bootstrap",
        jsonOptions("GET"),
      );
    },
    createSession(mode = "") {
      const query = text(mode) ? "?mode=" + encode(mode) : "";
      return request("/api/sessions" + query, jsonOptions("POST"));
    },
    setSessionMode(sessionId, mode) {
      return request(
        "/api/sessions/" + encode(sessionId) + "/mode",
        jsonOptions("POST", { mode: text(mode) }),
      );
    },
    cancelSession(sessionId) {
      return request("/api/sessions/" + encode(sessionId) + "/cancel", jsonOptions("POST"));
    },
    sendSessionMessage(sessionId, value) {
      return request(
        "/api/sessions/" + encode(sessionId) + "/message",
        jsonOptions("POST", { text: text(value) }),
      );
    },
    renameSession(sessionId, title) {
      return request(
        "/api/sessions/" + encode(sessionId) + "/rename",
        jsonOptions("POST", { title: text(title) }),
      );
    },
    archiveSession(sessionId) {
      return request("/api/sessions/" + encode(sessionId) + "/archive", jsonOptions("POST"));
    },
    forkSession(sessionId, title) {
      return request(
        "/api/sessions/" + encode(sessionId) + "/fork",
        jsonOptions("POST", { title: text(title) }),
      );
    },
    respondToInteraction(sessionId, interactionId, response) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/interactions/" +
          encode(interactionId) +
          "/respond",
        jsonOptions("POST", response || {}),
      );
    },
    reloadSessionResources(sessionId) {
      return request(
        "/api/sessions/" + encode(sessionId) + "/resources/reload",
        jsonOptions("POST"),
      );
    },
    listTerminals(sessionId) {
      return request("/api/sessions/" + encode(sessionId) + "/terminals", jsonOptions("GET"));
    },
    openTerminal(sessionId, terminalId, options = {}) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/open",
        jsonOptions("POST", options),
      );
    },
    getTerminalSnapshot(sessionId, terminalId) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/snapshot",
        jsonOptions("GET"),
      );
    },
    writeTerminal(sessionId, terminalId, data) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/write",
        jsonOptions("POST", { data }),
      );
    },
    clearTerminal(sessionId, terminalId) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/clear",
        jsonOptions("POST"),
      );
    },
    restartTerminal(sessionId, terminalId, options = {}) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/restart",
        jsonOptions("POST", options),
      );
    },
    resizeTerminal(sessionId, terminalId, cols, rows) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/resize",
        jsonOptions("POST", { cols, rows }),
      );
    },
    closeTerminal(sessionId, terminalId) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/close",
        jsonOptions("POST"),
      );
    },
    getSourceControlStatus() {
      return request("/api/app/source-control/status", jsonOptions("GET"));
    },
    refreshSourceControlStatus() {
      return request("/api/app/source-control/refresh", jsonOptions("POST"));
    },
    getSourceControlDiff(path, scope = "") {
      const query = new URLSearchParams({ path: text(path) });
      if (text(scope)) query.set("scope", text(scope));
      return request("/api/app/source-control/diff?" + query.toString(), jsonOptions("GET"));
    },
    listPreviewSessions(sessionId) {
      return request("/api/sessions/" + encode(sessionId) + "/preview", jsonOptions("GET"));
    },
    openPreviewSession(sessionId, url) {
      return request(
        "/api/sessions/" + encode(sessionId) + "/preview/open",
        jsonOptions("POST", { url }),
      );
    },
    refreshPreviewSession(sessionId, tabId) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/preview/" +
          encode(tabId) +
          "/refresh",
        jsonOptions("POST"),
      );
    },
    closePreviewSession(sessionId, tabId) {
      return request(
        "/api/sessions/" +
          encode(sessionId) +
          "/preview/" +
          encode(tabId) +
          "/close",
        jsonOptions("POST"),
      );
    },
    openPreviewExternal(url) {
      return request("/api/app/preview/open-external", jsonOptions("POST", { url }));
    },
    handleEvent(message) {
      return sendSocket(message);
    },
  };

  return Object.freeze(api);
}

