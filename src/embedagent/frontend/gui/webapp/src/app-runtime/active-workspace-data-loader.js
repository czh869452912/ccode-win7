function invoke(callback, ...args) {
  if (typeof callback !== "function") {
    return Promise.resolve();
  }
  return Promise.resolve(callback(...args));
}

export function createActiveWorkspaceDataLoader({
  getAppCapabilities,
  loadSessions,
  loadSessionCommandCapabilities,
  loadFileChildren,
  loadStatus,
} = {}) {
  const readAppCapabilities =
    typeof getAppCapabilities === "function" ? getAppCapabilities : () => ({});

  async function loadActiveWorkspaceData(_sessionId, assumeWorkspace, appCapabilities) {
    const scopedAppCapabilities = appCapabilities || readAppCapabilities();
    await Promise.all([
      invoke(loadSessions),
      invoke(loadSessionCommandCapabilities),
      invoke(loadFileChildren, ".", { appCapabilities: scopedAppCapabilities }),
      invoke(loadStatus, false, Boolean(assumeWorkspace), scopedAppCapabilities),
    ]);
  }

  return { loadActiveWorkspaceData };
}
