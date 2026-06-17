const GROUP_ORDER = ["host", "runtime", "renderer", "workspace_registry", "active_core"];

function labelFor(key) {
  return String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatValue(value) {
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (value === null || value === undefined) return "";
  return String(value);
}

export function formatDiagnosticsRows(diagnostics = {}) {
  const rows = [];
  for (const group of GROUP_ORDER) {
    const values = diagnostics[group];
    if (!values || typeof values !== "object" || Array.isArray(values)) continue;
    for (const key of Object.keys(values)) {
      rows.push({
        group,
        key,
        label: labelFor(key),
        value: formatValue(values[key]),
      });
    }
  }
  return rows;
}
