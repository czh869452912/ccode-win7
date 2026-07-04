export function fileStatusLabel(file = {}, chrome = {}) {
  const status = String(file.status || "").toLowerCase();
  const labels = chrome.fileStatusLabels || {};
  return String(labels[status] || labels.fallback || "");
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
