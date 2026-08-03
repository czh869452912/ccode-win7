import { normalizeProtocolEnvelope } from "../session-runtime/protocol-envelope.js";

function text(value) {
  return String(value == null ? "" : value);
}

function encode(value) {
  return encodeURIComponent(text(value));
}

function signalFrom(options) {
  return options && typeof options === "object" ? options.signal : undefined;
}

function requestDescriptor(path, method = "GET", body, options) {
  return {
    path,
    method,
    body,
    signal: signalFrom(options),
  };
}

export function createAgentAppProtocolAdapter({ http, socket } = {}) {
  const request = http && typeof http.request === "function" ? http.request.bind(http) : null;
  const connect =
    socket && typeof socket.connect === "function" ? socket.connect.bind(socket) : null;

  function requestHttp(path, method = "GET", body, options) {
    if (!request) return Promise.reject(new Error("protocol_port_missing:http.request"));
    return Promise.resolve(request(requestDescriptor(path, method, body, options)));
  }

  function requestFor(protocol, path, method = "GET", body, options) {
    return requestHttp(path, method, body, options).then((payload) => {
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

  const api = {
    loadAppBootstrap(options = {}) {
      return requestFor("app_shell_v1", "/api/app/bootstrap", "GET", undefined, options);
    },
    openWorkspacePath(path, options = {}) {
      return requestHttp("/api/app/workspaces", "POST", { path: text(path) }, options);
    },
    activateWorkspace(workspaceId, options = {}) {
      return requestHttp(
        "/api/app/workspaces/" + encode(workspaceId) + "/activate",
        "POST",
        undefined,
        options,
      );
    },
    removeWorkspace(workspaceId, options = {}) {
      return requestHttp(
        "/api/app/workspaces/" + encode(workspaceId),
        "DELETE",
        undefined,
        options,
      );
    },
    loadWorkspaceTree(path = ".", options = {}) {
      return requestHttp("/api/files/tree?path=" + encode(path), "GET", undefined, options);
    },
    readFile(path, options = {}) {
      return requestHttp("/api/files/" + encode(path), "GET", undefined, options);
    },
    listSessions(limit, options = {}) {
      const query = limit ? "?limit=" + encode(limit) : "";
      return requestHttp("/api/sessions" + query, "GET", undefined, options);
    },
    loadSessionCapabilities(options = {}) {
      return requestFor(
        "capability_v1",
        "/api/sessions/capabilities",
        "GET",
        undefined,
        options,
      );
    },
    loadSessionBootstrap(sessionId, options = {}) {
      return requestFor(
        "agent_session_v1",
        "/api/sessions/" + encode(sessionId) + "/bootstrap",
        "GET",
        undefined,
        options,
      );
    },
    createSession(mode = "", options = {}) {
      const query = text(mode) ? "?mode=" + encode(mode) : "";
      return requestHttp("/api/sessions" + query, "POST", undefined, options);
    },
    setSessionMode(sessionId, mode, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/mode",
        "POST",
        { mode: text(mode) },
        options,
      );
    },
    cancelSession(sessionId, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/cancel",
        "POST",
        undefined,
        options,
      );
    },
    sendSessionMessage(sessionId, value, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/message",
        "POST",
        { text: text(value) },
        options,
      );
    },
    renameSession(sessionId, title, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/rename",
        "POST",
        { title: text(title) },
        options,
      );
    },
    archiveSession(sessionId, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/archive",
        "POST",
        undefined,
        options,
      );
    },
    forkSession(sessionId, title, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/fork",
        "POST",
        { title: text(title) },
        options,
      );
    },
    respondToInteraction(sessionId, interactionId, response, options = {}) {
      return requestHttp(
        "/api/sessions/" +
          encode(sessionId) +
          "/interactions/" +
          encode(interactionId) +
          "/respond",
        "POST",
        response || {},
        options,
      );
    },
    reloadSessionResources(sessionId, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/resources/reload",
        "POST",
        undefined,
        options,
      );
    },
    listTerminals(sessionId, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/terminals",
        "GET",
        undefined,
        options,
      );
    },
    openTerminal(sessionId, terminalId, terminalOptions = {}, options = {}) {
      return requestHttp(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/open",
        "POST",
        terminalOptions,
        options,
      );
    },
    getTerminalSnapshot(sessionId, terminalId, options = {}) {
      return requestHttp(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/snapshot",
        "GET",
        undefined,
        options,
      );
    },
    writeTerminal(sessionId, terminalId, data, options = {}) {
      return requestHttp(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/write",
        "POST",
        { data },
        options,
      );
    },
    clearTerminal(sessionId, terminalId, options = {}) {
      return requestHttp(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/clear",
        "POST",
        undefined,
        options,
      );
    },
    restartTerminal(sessionId, terminalId, terminalOptions = {}, options = {}) {
      return requestHttp(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/restart",
        "POST",
        terminalOptions,
        options,
      );
    },
    resizeTerminal(sessionId, terminalId, cols, rows, options = {}) {
      return requestHttp(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/resize",
        "POST",
        { cols, rows },
        options,
      );
    },
    closeTerminal(sessionId, terminalId, options = {}) {
      return requestHttp(
        "/api/sessions/" +
          encode(sessionId) +
          "/terminals/" +
          encode(terminalId) +
          "/close",
        "POST",
        undefined,
        options,
      );
    },
    getSourceControlStatus(options = {}) {
      return requestHttp("/api/app/source-control/status", "GET", undefined, options).then(
        (payload) => payload?.source_control || {},
      );
    },
    refreshSourceControlStatus(options = {}) {
      return requestHttp("/api/app/source-control/refresh", "POST", undefined, options).then(
        (payload) => payload?.source_control || {},
      );
    },
    getSourceControlDiff(path, scope = "", options = {}) {
      const query = new URLSearchParams({ path: text(path) });
      if (text(scope)) query.set("scope", text(scope));
      return requestHttp(
        "/api/app/source-control/diff?" + query.toString(),
        "GET",
        undefined,
        options,
      ).then((payload) => payload?.diff || {});
    },
    listPreviewSessions(sessionId, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/preview",
        "GET",
        undefined,
        options,
      );
    },
    openPreviewSession(sessionId, url, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/preview/open",
        "POST",
        { url },
        options,
      );
    },
    refreshPreviewSession(sessionId, tabId, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/preview/" + encode(tabId) + "/refresh",
        "POST",
        undefined,
        options,
      );
    },
    closePreviewSession(sessionId, tabId, options = {}) {
      return requestHttp(
        "/api/sessions/" + encode(sessionId) + "/preview/" + encode(tabId) + "/close",
        "POST",
        undefined,
        options,
      );
    },
    openPreviewExternal(url, options = {}) {
      return requestHttp("/api/app/preview/open-external", "POST", { url }, options);
    },
    openSessionEvents() {
      if (!connect) throw new Error("protocol_port_missing:socket.connect");
      return connect({ path: "/ws" });
    },
  };

  return Object.freeze(api);
}
