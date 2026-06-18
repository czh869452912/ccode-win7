const GROUP_LABELS = {
  app: "App",
  session: "Session",
  message: "Message",
  mode: "Mode",
  surface: "Surface",
  workspace: "Workspace",
  workflow: "Workflow",
  view: "View",
  command: "Command",
};

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizeCommandQuery(query) {
  const normalized = normalizeText(query);
  return normalized.charAt(0) === "/" ? normalized.slice(1) : normalized;
}

function compactSlash(value) {
  const raw = String(value || "").trim();
  return raw.charAt(0) === "/" ? raw : `/${raw}`;
}

function wordBoundaryMatch(value, query) {
  if (!query) return false;
  return normalizeText(value)
    .split(/[^a-z0-9_./-]+/i)
    .filter(Boolean)
    .some((part) => part.startsWith(query));
}

function keywordMatch(keywords, query) {
  return (Array.isArray(keywords) ? keywords : []).some((keyword) => {
    const normalized = normalizeText(keyword);
    return normalized === query || normalized.startsWith(query) || normalized.includes(query);
  });
}

function scoreItem(item, query) {
  if (!query) return 100 + item.order;

  const slash = normalizeText(item.slash);
  const slashBare = slash.charAt(0) === "/" ? slash.slice(1) : slash;
  const label = normalizeText(item.label);

  if (slashBare === query || slash === `/${query}`) return 0;
  if (label === query) return 4;
  if (slashBare.startsWith(query)) return 10;
  if (slash.startsWith(`/${query}`)) return 12;
  if (label.startsWith(query)) return 20;
  if (wordBoundaryMatch(label, query)) return 30;
  if (keywordMatch(item.keywords, query)) return 40;
  if (slashBare.includes(query) || label.includes(query)) return 50;
  return Number.POSITIVE_INFINITY;
}

export function buildComposerCommandItems(commands = []) {
  const seenSlash = new Set();
  const items = [];
  for (const command of Array.isArray(commands) ? commands : []) {
    if (!command || !command.slash) continue;
    const slash = compactSlash(command.slash);
    const normalizedSlash = normalizeText(slash);
    if (seenSlash.has(normalizedSlash)) continue;
    seenSlash.add(normalizedSlash);
    items.push({
      type: "slash-command",
      id: `slash:${command.id || normalizedSlash}`,
      commandId: command.id || "",
      group: command.group || "command",
      groupLabel: GROUP_LABELS[command.group] || "Command",
      label: command.label || slash,
      detail: slash,
      slash,
      insertion: `${slash} `,
      keywords: Array.isArray(command.keywords) ? command.keywords : [],
      order: items.length,
    });
  }
  return items;
}

export function searchComposerCommandItems(items = [], query = "", limit = 8) {
  const normalizedQuery = normalizeCommandQuery(query);
  const ranked = (Array.isArray(items) ? items : [])
    .map((item) => ({ item, score: scoreItem(item, normalizedQuery) }))
    .filter((entry) => Number.isFinite(entry.score))
    .sort((left, right) => {
      if (left.score !== right.score) return left.score - right.score;
      return left.item.order - right.item.order;
    })
    .map((entry) => entry.item);
  return ranked.slice(0, Math.max(0, limit));
}

export function groupComposerCommandItems(items = []) {
  const groups = [];
  const byGroup = new Map();
  for (const item of Array.isArray(items) ? items : []) {
    const groupId = item.group || "command";
    if (!byGroup.has(groupId)) {
      const group = {
        id: `command-group:${groupId}`,
        label: item.groupLabel || GROUP_LABELS[groupId] || "Command",
        items: [],
      };
      byGroup.set(groupId, group);
      groups.push(group);
    }
    byGroup.get(groupId).items.push(item);
  }
  return groups;
}
