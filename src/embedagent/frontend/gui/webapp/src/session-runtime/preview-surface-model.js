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

function normalizeServer(input) {
  if (!input || typeof input !== "object") return null;
  const url = normalizePreviewUrl(input.url || input.href || "");
  if (!url) return null;
  const displayUrl = formatPreviewUrlDisplay(url);
  const label = String(input.label || input.name || displayUrl || "Local server").trim();
  const port = Number(input.port);
  return {
    id: url,
    label,
    url,
    displayUrl,
    port: Number.isFinite(port) && port > 0 ? Math.trunc(port) : null,
  };
}

export function buildPreviewEmptyStateModel({ servers = [] } = {}) {
  const normalizedServers = (Array.isArray(servers) ? servers : [])
    .map(normalizeServer)
    .filter(Boolean);
  const hasServers = normalizedServers.length > 0;
  return {
    hasServers,
    title: hasServers ? "Local servers" : "No preview open",
    description: hasServers
      ? "Choose a local server to open in the preview panel."
      : "Start a local dev server or enter a localhost URL above.",
    servers: normalizedServers,
  };
}
