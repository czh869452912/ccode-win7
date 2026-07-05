import { canSwitchWorkspace as defaultCanSwitchWorkspace, normalizeAppBootstrap } from "../app-workspaces.js";

function invoke(callback, ...args) {
  if (typeof callback !== "function") {
    return Promise.resolve();
  }
  return Promise.resolve().then(() => callback(...args));
}

function workspaceErrorFrom(error) {
  return String(error?.detail || error?.message || "workspace_open_failed");
}

export function createWorkspaceController({
  fetchJson,
  dispatch,
  getState,
  getAppState,
  getCurrentSessionId,
  canSwitchWorkspace = defaultCanSwitchWorkspace,
  loadWorkspaceData,
} = {}) {
  const request = typeof fetchJson === "function" ? fetchJson : () => Promise.resolve({});
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
    const payload = await request("/api/app/bootstrap");
    const bootstrap = normalizeAppBootstrap(payload || {});
    send({ type: "app_bootstrap_loaded", bootstrap });
    if (bootstrap.hasActiveWorkspace) {
      await loadWorkspaceScopedData("", true, bootstrap.capabilities);
    } else {
      send({ type: "source_control_reset" });
    }
    return bootstrap;
  }

  async function loadActiveWorkspaceData(
    sessionId = readCurrentSessionId(),
    assumeWorkspace = readAppState().hasActiveWorkspace,
    appCapabilities = readAppState().capabilities || {},
  ) {
    await loadWorkspaceScopedData(sessionId, assumeWorkspace, appCapabilities);
  }

  function assertCanSwitch() {
    const switchState = canSwitchWorkspace(readState());
    if (switchState.allowed) {
      return true;
    }
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
      const payload = await request("/api/app/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: targetPath }),
      });
      await applyBootstrap(payload, "workspace_switched");
    } catch (error) {
      send({ type: "workspace_activation_failed", error: workspaceErrorFrom(error) });
    }
  }

  async function activateWorkspace(workspaceId) {
    if (!assertCanSwitch()) return;
    send({ type: "workspace_activation_started" });
    try {
      const payload = await request(
        `/api/app/workspaces/${encodeURIComponent(workspaceId)}/activate`,
        { method: "POST" },
      );
      await applyBootstrap(payload, "workspace_switched");
    } catch (error) {
      send({ type: "workspace_activation_failed", error: workspaceErrorFrom(error) });
    }
  }

  async function removeWorkspace(workspaceId) {
    const payload = await request(`/api/app/workspaces/${encodeURIComponent(workspaceId)}`, {
      method: "DELETE",
    });
    await applyBootstrap(payload, "workspace_switched");
  }

  return {
    activateWorkspace,
    loadActiveWorkspaceData,
    loadAppBootstrap,
    openWorkspace,
    removeWorkspace,
  };
}
