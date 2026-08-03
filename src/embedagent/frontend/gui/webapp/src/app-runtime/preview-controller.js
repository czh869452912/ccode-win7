function readChrome(getPreviewChrome) {
  const value = typeof getPreviewChrome === "function" ? getPreviewChrome() : {};
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function errorNotice(error, fallback = "") {
  return error instanceof Error && error.message ? error.message : fallback || "";
}

function optionalProtocolMethod(protocol, name) {
  const method = protocol && protocol[name];
  return typeof method === "function" ? method.bind(protocol) : null;
}

export function createPreviewController({
  protocol,
  dispatch,
  getCurrentSessionId,
  getPreviewChrome,
  rightPanelController,
} = {}) {
  const openPreviewSession = optionalProtocolMethod(protocol, "openPreviewSession");
  const refreshPreviewSession = optionalProtocolMethod(protocol, "refreshPreviewSession");
  const openPreviewExternal = optionalProtocolMethod(protocol, "openPreviewExternal");
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const panel = rightPanelController || {};
  const canOpenSurface =
    typeof panel.canOpenPreviewSurface === "function"
      ? panel.canOpenPreviewSurface
      : () => false;
  const openSurface =
    typeof panel.openPreviewSurface === "function" ? panel.openPreviewSurface : () => false;
  const currentSessionId =
    typeof getCurrentSessionId === "function" ? getCurrentSessionId : () => "";

  async function openUrl(url) {
    if (!openPreviewSession || !canOpenSurface()) return null;
    const chrome = readChrome(getPreviewChrome);
    const sessionId = currentSessionId();
    if (!sessionId) {
      send({ type: "interaction_notice_set", notice: chrome.sessionRequiredNotice || "" });
      return null;
    }
    try {
      const result = await openPreviewSession(sessionId, url);
      const snapshot = result.preview || null;
      const resourceId = snapshot?.url || url;
      openSurface({ resourceId, previewSnapshot: snapshot });
      return result;
    } catch (error) {
      send({ type: "interaction_notice_set", notice: errorNotice(error, chrome.failedNotice) });
      throw error;
    }
  }

  async function refresh(snapshot) {
    if (!refreshPreviewSession || !canOpenSurface()) return null;
    const chrome = readChrome(getPreviewChrome);
    const sessionId = currentSessionId();
    const tabId = snapshot?.tabId || snapshot?.tab_id || "";
    if (!sessionId || !tabId) return null;
    try {
      const result = await refreshPreviewSession(sessionId, tabId);
      const nextSnapshot = result.preview || null;
      const resourceId = nextSnapshot?.url || snapshot?.url || "";
      openSurface({ resourceId, previewSnapshot: nextSnapshot });
      return result;
    } catch (error) {
      send({
        type: "interaction_notice_set",
        notice: errorNotice(error, chrome.refreshFailedNotice),
      });
      throw error;
    }
  }

  async function openExternal(url) {
    if (!openPreviewExternal || !canOpenSurface()) return null;
    const chrome = readChrome(getPreviewChrome);
    try {
      return await openPreviewExternal(url);
    } catch (error) {
      send({ type: "interaction_notice_set", notice: errorNotice(error, chrome.openFailedNotice) });
      throw error;
    }
  }

  return { openExternal, openUrl, refresh };
}
