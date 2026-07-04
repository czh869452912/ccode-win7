import { normalizeSessionPayload } from "../state-helpers.js";
import { normalizeHistoryActivities } from "../session-runtime/activity-state.js";
import { normalizeCommandCapabilities } from "../session-runtime/command-capabilities.js";

export const LOADER_REQUESTS = Object.freeze({
  LOAD_APP_BOOTSTRAP: "load_app_bootstrap",
  LOAD_ACTIVE_WORKSPACE_DATA: "load_active_workspace_data",
  LOAD_SESSIONS: "load_sessions",
  LOAD_SESSION: "load_session",
  LOAD_ARTIFACTS: "load_artifacts",
  LOAD_PERMISSION_CONTEXT: "load_permission_context",
  LOAD_FILE_CHILDREN: "load_file_children",
  LOAD_SESSION_CAPABILITIES: "load_session_capabilities",
});

function invoke(callback, ...args) {
  if (typeof callback !== "function") {
    return Promise.resolve();
  }
  return Promise.resolve().then(() => callback(...args));
}

export function createLoaderRequestExecutor(loaders = {}) {
  return function executeLoaderRequest(request = {}) {
    const name = request?.name || "";
    if (name === LOADER_REQUESTS.LOAD_APP_BOOTSTRAP) {
      return invoke(loaders.loadAppBootstrap);
    }
    if (name === LOADER_REQUESTS.LOAD_ACTIVE_WORKSPACE_DATA) {
      return invoke(
        loaders.loadActiveWorkspaceData,
        request.sessionId || "",
        Boolean(request.assumeWorkspace),
      );
    }
    if (name === LOADER_REQUESTS.LOAD_SESSIONS) {
      return invoke(loaders.loadSessions);
    }
    if (name === LOADER_REQUESTS.LOAD_SESSION) {
      if (!request.sessionId) return Promise.resolve();
      return invoke(loaders.loadSession, request.sessionId);
    }
    if (name === LOADER_REQUESTS.LOAD_ARTIFACTS) {
      return invoke(loaders.loadArtifacts);
    }
    if (name === LOADER_REQUESTS.LOAD_PERMISSION_CONTEXT) {
      if (!request.sessionId) return Promise.resolve();
      return invoke(loaders.loadPermissionContext, request.sessionId);
    }
    if (name === LOADER_REQUESTS.LOAD_FILE_CHILDREN) {
      return invoke(loaders.loadFileChildren, request.path || ".");
    }
    if (name === LOADER_REQUESTS.LOAD_SESSION_CAPABILITIES) {
      return invoke(loaders.loadSessionCommandCapabilities);
    }
    return Promise.resolve();
  };
}

export function deriveSessionActivation(payload = {}, sessionId = "", options = {}) {
  const safePayload = payload || {};
  const history = safePayload.history || {};
  const snapshot = normalizeSessionPayload(
    safePayload.snapshot || {},
    options.defaultMode || "",
  );
  return {
    sessionId,
    snapshot,
    activities: normalizeHistoryActivities(history.activities || []),
    historyIntegrity: history.integrity || null,
    plan: safePayload.plan || null,
    permissionContext: safePayload.permission_context || null,
    capabilities: normalizeCommandCapabilities(safePayload.capabilities || {}),
  };
}

export async function loadSessionCommandCapabilities({ fetchJson, dispatch } = {}) {
  const request = typeof fetchJson === "function" ? fetchJson : () => Promise.resolve({});
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const capabilities = normalizeCommandCapabilities(await request("/api/sessions/capabilities"));
  send({ type: "session_capabilities_loaded", capabilities });
  return capabilities;
}
