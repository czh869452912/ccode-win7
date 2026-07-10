// GUI-local preview surface presentation helpers. This never opens network
// connections or mutates Agent Core state; callers decide what to display.

const LOCALHOST_WITH_PORT = /^(localhost|127(?:\.\d{1,3}){3}|\[::1\])(?::\d+)(?:\/.*)?$/i;

export function normalizePreviewUrl(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(text)) return text;
  if (LOCALHOST_WITH_PORT.test(text)) return `http://${text}`;
  return text;
}

export function formatPreviewUrlDisplay(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  try {
    const parsed = new URL(text);
    const path = `${parsed.pathname || ""}${parsed.search || ""}${parsed.hash || ""}`;
    const normalizedPath = path === "/" ? "" : path;
    return `${parsed.host}${normalizedPath}`;
  } catch (_) {
    return text;
  }
}

export function previewSnapshotFromApi(input) {
  const data = input && typeof input === "object" ? input : {};
  return {
    threadId: String(data.thread_id || data.threadId || ""),
    tabId: String(data.tab_id || data.tabId || ""),
    url: normalizePreviewUrl(data.url || ""),
    status: String(data.status || "idle"),
    title: String(data.title || ""),
    canGoBack: Boolean(data.can_go_back ?? data.canGoBack),
    canGoForward: Boolean(data.can_go_forward ?? data.canGoForward),
    errorCode: Number(data.error_code ?? data.errorCode ?? 0) || 0,
    errorDescription: String(data.error_description || data.errorDescription || ""),
    updatedAt: String(data.updated_at || data.updatedAt || ""),
  };
}

export function buildPreviewRuntimeState({ snapshot = null, chrome = {} } = {}) {
  const normalized = snapshot ? previewSnapshotFromApi(snapshot) : null;
  const status = normalized ? normalized.status : "idle";
  const loading = status === "loading";
  const unreachable = status === "failed";
  const displayTitle = normalized
    ? (normalized.title || formatPreviewUrlDisplay(normalized.url))
    : "";
  const statusLabel =
    status === "loading"
      ? String(chrome.statusLoading || "")
      : status === "success"
        ? String(chrome.statusReady || "")
        : status === "failed"
          ? (normalized.errorDescription || String(chrome.statusFailed || ""))
          : String(chrome.statusIdle || "");
  return {
    hasSnapshot: Boolean(normalized),
    loading,
    unreachable,
    canRefresh: Boolean(normalized && normalized.url),
    canOpenExternal: Boolean(normalized && normalized.url),
    displayTitle,
    statusLabel,
  };
}

function normalizeServer(input, chrome) {
  if (!input || typeof input !== "object") return null;
  const url = normalizePreviewUrl(input.url || input.href || "");
  if (!url) return null;
  const displayUrl = formatPreviewUrlDisplay(url);
  const label = String(
    input.label || input.name || chrome.localServerFallbackLabel || displayUrl || "",
  ).trim();
  const port = Number(input.port);
  return {
    id: url,
    label,
    url,
    displayUrl,
    port: Number.isFinite(port) && port > 0 ? Math.trunc(port) : null,
  };
}

export function buildPreviewEmptyStateModel({ servers = [], chrome = {} } = {}) {
  const normalizedServers = (Array.isArray(servers) ? servers : [])
    .map((server) => normalizeServer(server, chrome))
    .filter(Boolean);
  const hasServers = normalizedServers.length > 0;
  return {
    hasServers,
    title: hasServers ? String(chrome.serversTitle || "") : String(chrome.emptyTitle || ""),
    description: hasServers
      ? String(chrome.serversDescription || "")
      : String(chrome.emptyDescription || ""),
    servers: normalizedServers,
  };
}
