function isPlainObject(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function text(value) {
  return String(value ?? "").trim();
}

function workflowPayload(snapshot = {}) {
  return isPlainObject(snapshot?.workflow) ? snapshot.workflow : {};
}

function workflowMetadata(snapshot = {}) {
  const workflow = workflowPayload(snapshot);
  return isPlainObject(workflow.metadata) ? workflow.metadata : {};
}

function pushRow(rows, key, labelKey, value) {
  const normalized = text(value);
  if (!normalized) {
    return;
  }
  rows.push({ key, labelKey, label: "", value: normalized });
}

export function buildWorkflowRuntimeRows(snapshot = {}) {
  const workflow = workflowPayload(snapshot);
  const metadata = workflowMetadata(snapshot);
  const rows = [];

  pushRow(
    rows,
    "current_phase",
    "inspector.currentPhase",
    snapshot.current_phase || metadata.current_phase || workflow.current_phase,
  );
  pushRow(
    rows,
    "discipline_profile",
    "inspector.disciplineProfile",
    snapshot.discipline_profile || metadata.discipline_profile || workflow.discipline_profile,
  );
  pushRow(
    rows,
    "current_activity",
    "inspector.currentActivity",
    snapshot.current_activity || workflow.activity || metadata.current_activity,
  );

  const displayRows = Array.isArray(metadata.display_rows)
    ? metadata.display_rows
    : Array.isArray(metadata.displayRows)
      ? metadata.displayRows
      : [];
  for (const [index, item] of displayRows.entries()) {
    if (!isPlainObject(item)) {
      continue;
    }
    const value = text(item.value);
    if (!value) {
      continue;
    }
    rows.push({
      key: text(item.key) || text(item.label_key) || text(item.labelKey) || `workflow_row_${index}`,
      labelKey: text(item.label_key || item.labelKey),
      label: text(item.label),
      value,
    });
  }
  return rows;
}

export function workflowTaskSummary(snapshot = {}) {
  const workflow = workflowPayload(snapshot);
  return text(snapshot?.task_summary) || text(workflow.summary);
}
