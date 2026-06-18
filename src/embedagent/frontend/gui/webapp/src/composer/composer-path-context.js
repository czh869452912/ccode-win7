function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizePath(value) {
  return String(value || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function fileNameFromPath(path) {
  const normalized = normalizePath(path);
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] || normalized;
}

function collectFileNodes(nodes, output) {
  for (const node of Array.isArray(nodes) ? nodes : []) {
    if (!node || typeof node !== "object") continue;
    const path = normalizePath(node.path || "");
    const kind = String(node.kind || "").toLowerCase();
    if (kind === "file" && path) {
      const name = node.name || fileNameFromPath(path);
      output.push({
        type: "path-context",
        id: `path:${path}`,
        label: name,
        detail: path,
        path,
        name,
        order: output.length,
      });
    }
    if (Array.isArray(node.children)) {
      collectFileNodes(node.children, output);
    }
  }
}

function scoreCandidate(candidate, query) {
  if (!query) return 100 + candidate.order;
  const path = normalizeText(candidate.path);
  const name = normalizeText(candidate.name);
  if (name === query) return 0;
  if (path === query) return 2;
  if (name.startsWith(query)) return 8;
  if (path.startsWith(query)) return 12;
  if (path.split("/").some((part) => part.startsWith(query))) return 20;
  if (name.includes(query)) return 30;
  if (path.includes(query)) return 40;
  return Number.POSITIVE_INFINITY;
}

export function flattenComposerPathCandidates(nodes = []) {
  const output = [];
  collectFileNodes(nodes, output);
  return output.sort((left, right) => left.path.localeCompare(right.path));
}

export function searchComposerPathCandidates(candidates = [], query = "", limit = 8) {
  const normalizedQuery = normalizeText(query);
  const ranked = (Array.isArray(candidates) ? candidates : [])
    .map((candidate) => ({ candidate, score: scoreCandidate(candidate, normalizedQuery) }))
    .filter((entry) => Number.isFinite(entry.score))
    .sort((left, right) => {
      if (left.score !== right.score) return left.score - right.score;
      const leftDepth = left.candidate.path.split("/").length;
      const rightDepth = right.candidate.path.split("/").length;
      if (leftDepth !== rightDepth) return leftDepth - rightDepth;
      return left.candidate.path.localeCompare(right.candidate.path);
    })
    .map((entry) => entry.candidate);
  return ranked.slice(0, Math.max(0, limit));
}

export function groupComposerPathCandidates(items = []) {
  return [
    {
      id: "path-group:files",
      label: "Files",
      items: Array.isArray(items) ? items : [],
    },
  ].filter((group) => group.items.length > 0);
}

export function buildPathContextInsertion(candidate) {
  if (!candidate || !candidate.path) return "";
  return `@${candidate.path} `;
}
