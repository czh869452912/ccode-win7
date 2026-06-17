export function getTerminalLabel(terminalId) {
  const id = String(terminalId || "").trim();
  const match = /^term(?:inal)?-(\d+)$/i.exec(id);
  if (match) return `Terminal ${match[1]}`;
  return id || "Terminal";
}

export function resolveTerminalSessionLabel(terminalId, summary) {
  const label = String((summary && summary.label) || "").trim();
  return label || getTerminalLabel(terminalId);
}

export function nextTerminalId(existingTerminalIds) {
  const used = new Set(
    (existingTerminalIds || []).map((item) => String(item || "").trim()).filter(Boolean),
  );
  let index = 1;
  while (used.has(`term-${index}`)) index += 1;
  return `term-${index}`;
}
