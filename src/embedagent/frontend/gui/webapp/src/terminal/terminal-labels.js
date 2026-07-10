function chromeText(chrome, key) {
  return String((chrome && chrome[key]) || "").trim();
}

export function getTerminalLabel(terminalId, chrome = {}) {
  const id = String(terminalId || "").trim();
  const match = /^term(?:inal)?-(\d+)$/i.exec(id);
  const prefix = chromeText(chrome, "titlePrefix");
  if (match && prefix) return `${prefix} ${match[1]}`;
  return id || chromeText(chrome, "defaultTitle");
}

export function resolveTerminalSessionLabel(terminalId, summary) {
  const label = String((summary && summary.label) || "").trim();
  return label;
}

export function nextTerminalId(existingTerminalIds) {
  const used = new Set(
    (existingTerminalIds || []).map((item) => String(item || "").trim()).filter(Boolean),
  );
  let index = 1;
  while (used.has(`term-${index}`)) index += 1;
  return `term-${index}`;
}
