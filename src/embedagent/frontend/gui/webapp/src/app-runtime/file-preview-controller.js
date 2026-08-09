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
  protocol,
  dispatch,
  getFilePreviewChrome,
  contributionController,
} = {}) {
  const readFile =
    protocol && typeof protocol.readFile === "function"
      ? protocol.readFile.bind(protocol)
      : null;
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const contributions = contributionController || {};
  const normalizePath =
    typeof contributions.normalizeFilePath === "function"
      ? contributions.normalizeFilePath
      : normalizeFallbackPath;
  const openSurface =
    typeof contributions.openFile === "function" ? contributions.openFile : () => false;

  async function openFile(path, line) {
    if (!readFile) return null;
    const filePath = normalizePath(path);
    if (!filePath) return null;
    const chrome = readChrome(getFilePreviewChrome);
    const opened = openSurface({
      filePath,
      revealLine: line,
      title: fallbackFileTitle(filePath, chrome),
    });
    if (!opened) return null;
    send({ type: "file_preview_load_started", path: filePath });
    try {
      const payload = await readFile(filePath);
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
