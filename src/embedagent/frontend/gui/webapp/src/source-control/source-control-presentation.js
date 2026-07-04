const STATUS_LABELS = {
  added: "A",
  copied: "C",
  deleted: "D",
  modified: "M",
  renamed: "R",
  typechange: "T",
  untracked: "U",
  conflicted: "C",
};

export function fileStatusLabel(file = {}) {
  const status = String(file.status || "").toLowerCase();
  if (STATUS_LABELS[status]) return STATUS_LABELS[status];
  return status ? status.slice(0, 1).toUpperCase() : "?";
}

export function groupLabel(group, chrome = {}) {
  const normalized = String(group || "").toLowerCase();
  const labels = chrome.groupLabels || {};
  return String(labels[normalized] || labels.fallback || normalized || "");
}

export function providerLabel(provider = {}, chrome = {}) {
  if (provider.name) return String(provider.name);
  const normalized = String(provider.kind || "").toLowerCase();
  const labels = chrome.providerLabels || {};
  return String(labels[normalized] || labels.fallback || normalized || "");
}

export function changeSummary(file = {}) {
  const insertions = Number(file.insertions || 0);
  const deletions = Number(file.deletions || 0);
  if (!insertions && !deletions) return "";
  return `+${insertions} -${deletions}`;
}
