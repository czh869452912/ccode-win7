function stringValue(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

function booleanValue(value, fallback = false) {
  return typeof value === "boolean" ? value : fallback;
}

function normalizeDensity(value, fallback = "compact") {
  const text = stringValue(value, fallback);
  if (text === "compact" || text === "normal" || text === "expanded") return text;
  return fallback;
}

export function rowUiKey(row) {
  const kind = stringValue(row?.kind, "row");
  const turnId = stringValue(row?.turnId || row?.turn_id);
  const id = stringValue(row?.id);
  if (kind === "work") {
    return [
      "work",
      turnId,
      stringValue(row?.stepId || row?.step_id),
      stringValue(id || row?.toolName || row?.tool_name),
    ].join(":");
  }
  if (kind === "turn_fold") {
    return [
      "turn_fold",
      turnId,
      id,
    ].join(":");
  }
  if (turnId && id) {
    return `${kind}:${turnId}:${id}`;
  }
  if (id) {
    return `${kind}:${id}`;
  }
  return `${kind}:unknown`;
}

export function isRowExpandedByDefault(row) {
  if (!row) return false;
  if (row.kind === "turn_fold") return booleanValue(row.defaultOpen, false);
  if (row.kind === "command_result") {
    return row.success === false || stringValue(row.content).trim().length > 0;
  }
  if (row.kind === "review_result") {
    return row.success === false;
  }
  if (row.kind === "context_summary") return false;
  if (row.kind !== "work") return false;
  if (row.tone === "interrupted" || row.tone === "discarded") return true;
  if (row.status === "error" || row.tone === "error") return true;
  return false;
}

export function defaultRowDensity(row) {
  return isRowExpandedByDefault(row) ? "expanded" : "compact";
}

function collectRows(rows) {
  const collected = [];
  for (const row of rows || []) {
    collected.push(row);
    if (row?.kind === "turn_fold" && Array.isArray(row.entries)) {
      for (const entry of row.entries) collected.push(entry);
    }
  }
  return collected;
}

export function createTimelineUiState(rows = [], previousState = null) {
  const previousExpanded = previousState?.expanded || {};
  const previousDensity = previousState?.density || {};
  const previousTouched = previousState?.touched || {};
  const expanded = {};
  const density = {};
  const touched = {};
  for (const row of collectRows(rows)) {
    const key = rowUiKey(row);
    if (!key) continue;
    if (previousTouched[key]) {
      density[key] = normalizeDensity(
        previousDensity[key],
        previousExpanded[key] ? "expanded" : "compact",
      );
      expanded[key] = density[key] === "expanded";
      touched[key] = true;
    } else {
      density[key] = defaultRowDensity(row);
      expanded[key] = density[key] === "expanded";
    }
  }
  return { expanded, density, touched };
}

export function toggleTimelineRow(state, rowKey) {
  const expanded = { ...(state?.expanded || {}) };
  const density = { ...(state?.density || {}) };
  const touched = { ...(state?.touched || {}) };
  const nextExpanded = !Boolean(expanded[rowKey]);
  expanded[rowKey] = nextExpanded;
  density[rowKey] = nextExpanded ? "expanded" : "compact";
  touched[rowKey] = true;
  return { expanded, density, touched };
}

export function toggleTimelineRowDensity(state, rowKey, nextDensity = "expanded") {
  const expanded = { ...(state?.expanded || {}) };
  const density = { ...(state?.density || {}) };
  const touched = { ...(state?.touched || {}) };
  const value = normalizeDensity(nextDensity, "expanded");
  density[rowKey] = value;
  expanded[rowKey] = value === "expanded";
  touched[rowKey] = true;
  return { expanded, density, touched };
}

export function rowDensityFor(row, state = null) {
  const key = rowUiKey(row);
  return normalizeDensity(state?.density?.[key], defaultRowDensity(row));
}

export function shouldPinToBottom({ scrollTop = 0, clientHeight = 0, scrollHeight = 0, threshold = 16 } = {}) {
  return scrollHeight - (scrollTop + clientHeight) <= threshold;
}

export function restoreAnchorScroll({ before, after, scrollTop = 0 } = {}) {
  if (!before || !after) return scrollTop;
  return scrollTop + (after.top - before.top);
}
