function text(value) {
  return String(value || "").trim();
}

function insertionFromUsage(usage) {
  return `${text(usage).replace(/\s+(?:<[^>]+>|\[[^\]]+\]).*$/u, "")} `;
}

export function normalizeCommandCapabilities(input = {}) {
  const commands = [];
  const seen = new Set();
  const source = Array.isArray(input?.commands) ? input.commands : [];
  for (const item of source) {
    const name = text(item?.name);
    const usage = text(item?.usage);
    if (!name || !usage || item?.active === false) continue;
    const key = usage.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    commands.push({
      name,
      usage,
      summary: text(item?.summary),
      sourceType: text(item?.source_type || item?.sourceType),
      sourceId: text(item?.source_id || item?.sourceId),
      active: true,
    });
  }
  return { commands };
}

export function buildComposerCommandsFromCapabilities(capabilities = {}) {
  return normalizeCommandCapabilities(capabilities).commands.map((item) => ({
    id: `backend-command:${item.name}`,
    group: "command",
    label: item.usage,
    slash: item.usage,
    insertion: insertionFromUsage(item.usage),
    visibleWhen: "always",
    keywords: [item.name, item.summary].filter(Boolean),
  }));
}
