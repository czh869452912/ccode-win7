import { normalizeProtocolCapabilities } from "./protocol-normalizer.js";

function text(value) {
  return String(value || "").trim();
}

function defaultGroupId(options = {}) {
  return text(options.defaultGroupId || options.defaultCommandGroupId);
}

function insertionFromUsage(usage) {
  return `${text(usage).replace(/\s+(?:<[^>]+>|\[[^\]]+\]).*$/u, "")} `;
}

export function normalizeCommandCapabilities(input = {}) {
  const normalized = normalizeProtocolCapabilities(input);
  const commands = [];
  const seen = new Set();
  const source = Array.isArray(normalized.commands) ? normalized.commands : [];
  for (const item of source) {
    const usage = text(item?.usage || item?.slash || (String(item?.label || "").startsWith("/") ? item.label : ""));
    const protocolId = text(item?.id);
    const name = text(item?.name || protocolId);
    if (!name || !usage || item?.active === false) continue;
    const key = usage.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    commands.push({
      name,
      usage,
      id: protocolId || name,
      label: text(item?.label || usage),
      group: text(item?.group),
      dispatch: item?.dispatch && typeof item.dispatch === "object" ? item.dispatch : {},
      slash: text(item?.slash || usage),
      summary: text(item?.summary),
      sourceType: text(item?.source_type || item?.sourceType),
      sourceId: text(item?.source_id || item?.sourceId),
      visibleWhen: text(item?.visibleWhen || item?.visible_when || "always"),
      active: true,
    });
  }
  return { ...normalized, commands };
}

export function buildComposerCommandsFromCapabilities(capabilities = {}, options = {}) {
  const fallbackGroup = defaultGroupId(options);
  return normalizeCommandCapabilities(capabilities).commands.map((item) => ({
    id: `backend-command:${item.name}`,
    group: text(item.group) || fallbackGroup,
    label: item.usage,
    slash: item.usage,
    insertion: insertionFromUsage(item.usage),
    visibleWhen: "always",
    keywords: [item.name, item.summary].filter(Boolean),
  }));
}
