import { canSwitchWorkspace as defaultCanSwitchWorkspace, normalizeAppBootstrap } from "../app-workspaces.js";

function invoke(callback, ...args) {
  if (typeof callback !== "function") return Promise.resolve();
  return Promise.resolve().then(() => callback(...args));
}

function workspaceErrorFrom(error) {
  return String(error?.failure?.code || error?.detail || error?.message || "workspace_open_failed");
}

function requireProtocolMethod(protocol, name) {
  const method = protocol && protocol[name];
  if (typeof method !== "function") throw new Error(`protocol_method_missing:${name}`);
  return method.bind(protocol);
}

export function createWorkspaceController({
  protocol,
  dispatch,
  getState,
  getAppState,
  getCurrentSessionId,
  canSwitchWorkspace = defaultCanSwitchWorkspace,
  loadWorkspaceData,
} = {}) {
  const requestAppBootstrap = requireProtocolMethod(protocol, "loadAppBootstrap");
  const requestOpenWorkspace = requireProtocolMethod(protocol, "openWorkspacePath");
  const requestActivateWorkspace = requireProtocolMethod(protocol, "activateWorkspace");
  const requestRemoveWorkspace = requireProtocolMethod(protocol, "removeWorkspace");
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const readState = typeof getState === "function" ? getState : () => ({});
  const readAppState =
    typeof getAppState === "function" ? getAppState : () => readState().app || {};
  const readCurrentSessionId =
    typeof getCurrentSessionId === "function" ? getCurrentSessionId : () => "";

  async function loadWorkspaceScopedData(sessionId, assumeWorkspace, appCapabilities = {}) {
    await invoke(loadWorkspaceData, sessionId || "", Boolean(assumeWorkspace), appCapabilities);
  }

  async function applyBootstrap(payload, actionType) {
    const bootstrap = normalizeAppBootstrap(payload || {});
    send({ type: actionType, bootstrap });
    if (bootstrap.hasActiveWorkspace) {
      await loadWorkspaceScopedData("", true, bootstrap.capabilities);
    } else {
      send({ type: "source_control_reset" });
    }
    return bootstrap;
  }

  async function loadAppBootstrap() {
    const payload = await requestAppBootstrap();
    return applyBootstrap(payload, "app_bootstrap_loaded");
  }

  async function loadActiveWorkspaceData(
    sessionId = readCurrentSessionId(),
    assumeWorkspace = readAppState().hasActiveWorkspace,
    appCapabilities = readAppState().capabilities || {},
  ) {
    await loadWorkspaceScopedData(sessionId, assumeWorkspace, appCapabilities);
  }

  function setWorkspacePath(value) {
    send({ type: "workspace_path_changed", value });
  }

  function assertCanSwitch() {
    const switchState = canSwitchWorkspace(readState());
    if (switchState.allowed) return true;
    send({ type: "workspace_activation_failed", error: switchState.reason });
    return false;
  }

  async function openWorkspace(path) {
    const targetPath = String(path || readAppState().workspacePathInput || "").trim();
    if (!targetPath) {
      send({ type: "workspace_activation_failed", error: "workspace_path_required" });
      return;
    }
    if (!assertCanSwitch()) return;
    send({ type: "workspace_activation_started" });
    try {
      await applyBootstrap(await requestOpenWorkspace(targetPath), "workspace_switched");
    } catch (error) {
      send({ type: "workspace_activation_failed", error: workspaceErrorFrom(error) });
    }
  }

  async function activateWorkspace(workspaceId) {
    if (!assertCanSwitch()) return;
    send({ type: "workspace_activation_started" });
    try {
      await applyBootstrap(await requestActivateWorkspace(workspaceId), "workspace_switched");
    } catch (error) {
      send({ type: "workspace_activation_failed", error: workspaceErrorFrom(error) });
    }
  }

  async function removeWorkspace(workspaceId) {
    await applyBootstrap(await requestRemoveWorkspace(workspaceId), "workspace_switched");
  }

  return {
    activateWorkspace,
    loadActiveWorkspaceData,
    loadAppBootstrap,
    openWorkspace,
    removeWorkspace,
    setWorkspacePath,
  };
}
