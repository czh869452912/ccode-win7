function stringValue(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

function booleanValue(value, fallback = false) {
  return typeof value === "boolean" ? value : fallback;
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
    return row.success === false;
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
  const previousTouched = previousState?.touched || {};
  const expanded = {};
  const touched = {};
  for (const row of collectRows(rows)) {
    const key = rowUiKey(row);
    if (!key) continue;
    if (previousTouched[key]) {
      expanded[key] = Boolean(previousExpanded[key]);
      touched[key] = true;
    } else {
      expanded[key] = isRowExpandedByDefault(row);
    }
  }
  return { expanded, touched };
}

export function toggleTimelineRow(state, rowKey) {
  const expanded = { ...(state?.expanded || {}) };
  const touched = { ...(state?.touched || {}) };
  expanded[rowKey] = !Boolean(expanded[rowKey]);
  touched[rowKey] = true;
  return { expanded, touched };
}

export function shouldPinToBottom({ scrollTop = 0, clientHeight = 0, scrollHeight = 0, threshold = 16 } = {}) {
  return scrollHeight - (scrollTop + clientHeight) <= threshold;
}

export function restoreAnchorScroll({ before, after, scrollTop = 0 } = {}) {
  if (!before || !after) return scrollTop;
  return scrollTop + (after.top - before.top);
}
