function normalizeFallbackPath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function fallbackFileTitle(path, filePreviewChrome = {}) {
  const normalized = normalizeFallbackPath(path);
  if (!normalized) return filePreviewChrome.defaultFileTitle || "";
  const parts = normalized.split("/");
  return parts[parts.length - 1] || normalized;
}

function readChrome(getFilePreviewChrome) {
  const value =
    typeof getFilePreviewChrome === "function" ? getFilePreviewChrome() : {};
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export function createFilePreviewController({
  fetchJson,
  dispatch,
  getFilePreviewChrome,
  rightPanelController,
} = {}) {
  const request = typeof fetchJson === "function" ? fetchJson : () => Promise.resolve({});
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const panel = rightPanelController || {};
  const normalizePath =
    typeof panel.normalizeFileSurfacePath === "function"
      ? panel.normalizeFileSurfacePath
      : normalizeFallbackPath;
  const fileTitle =
    typeof panel.fileSurfaceTitle === "function" ? panel.fileSurfaceTitle : fallbackFileTitle;
  const openSurface =
    typeof panel.openFileSurface === "function" ? panel.openFileSurface : () => false;

  async function openFile(path, line) {
    const filePath = normalizePath(path);
    if (!filePath) return null;
    const chrome = readChrome(getFilePreviewChrome);
    const opened = openSurface({
      filePath,
      revealLine: line,
      title: fileTitle(filePath, chrome),
    });
    if (!opened) return null;
    send({ type: "file_preview_load_started", path: filePath });
    try {
      const payload = await request(`/api/files/${encodeURIComponent(filePath)}`);
      send({
        type: "file_preview_loaded",
        path: filePath,
        preview: {
          title: payload.path || filePath,
          content: payload.content || "",
        },
      });
      return payload;
    } catch (error) {
      send({
        type: "file_preview_load_failed",
        path: filePath,
        error:
          error instanceof Error && error.message
            ? error.message
            : chrome.unavailableMessage || "",
      });
      return null;
    }
  }

  return { openFile };
}
