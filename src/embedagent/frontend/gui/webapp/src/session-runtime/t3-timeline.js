export const T3_ROW_KINDS = Object.freeze({
  MESSAGE: "message",
  WORK: "work",
  TURN_FOLD: "turn_fold",
  INTERACTION: "interaction",
  DIFF_SUMMARY: "diff_summary",
  WORKING: "working",
  SYSTEM_NOTICE: "system_notice",
});

const WRITE_TOOLS = new Set(["write_file", "edit_file", "git_diff"]);
const META_ARG_PREFIX = "_";

function stringValue(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

function numberValue(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function pathFromDiffHeader(line) {
  const value = stringValue(line).replace(/^(---|\+\+\+)\s+/, "").trim();
  if (!value || value === "/dev/null") return "";
  const first = value.split(/\s+/)[0];
  return first.replace(/^[ab]\//, "");
}

function parseDiffFiles(diff) {
  const text = stringValue(diff);
  if (!text) return [];
  const files = [];
  let current = null;
  for (const line of text.split(/\r?\n/)) {
    if (line.startsWith("--- ")) {
      if (current) files.push(current);
      current = {
        oldPath: pathFromDiffHeader(line),
        path: "",
        additions: 0,
        deletions: 0,
        diff: `${line}\n`,
      };
      continue;
    }
    if (!current) continue;
    current.diff += `${line}\n`;
    if (line.startsWith("+++ ")) {
      current.path = pathFromDiffHeader(line) || current.oldPath;
    } else if (line.startsWith("+")) {
      current.additions += 1;
    } else if (line.startsWith("-")) {
      current.deletions += 1;
    }
  }
  if (current) files.push(current);
  return files
    .map((file) => ({
      path: file.path || file.oldPath,
      additions: file.additions,
      deletions: file.deletions,
      diff: file.diff,
    }))
    .filter((file) => file.path);
}

function mergeFileStats(fileMap, file) {
  const path = stringValue(file.path);
  if (!path) return;
  const existing = fileMap.get(path) || {
    path,
    additions: 0,
    deletions: 0,
    diff: "",
    sourceIds: [],
  };
  fileMap.set(path, {
    ...existing,
    additions: existing.additions + numberValue(file.additions),
    deletions: existing.deletions + numberValue(file.deletions),
    diff: existing.diff || stringValue(file.diff),
    sourceIds: existing.sourceIds.concat(file.sourceId ? [file.sourceId] : []),
  });
}

function diffTextFromItem(item) {
  const data = item?.data || {};
  if (typeof data.diff === "string" && data.diff) return data.diff;
  if (typeof data.diff_preview === "string" && data.diff_preview) return data.diff_preview;
  if (typeof data.unified_diff === "string" && data.unified_diff) return data.unified_diff;
  if (typeof item?.diff === "string" && item.diff) return item.diff;
  return "";
}

function changedPathFromItem(item) {
  const data = item?.data || {};
  const args = item?.arguments || {};
  return stringValue(data.path || data.file || args.path || args.file || item?.path);
}

export function summarizeChangedFiles(items = []) {
  const fileMap = new Map();
  for (const item of items || []) {
    const toolName = stringValue(item?.toolName || item?.tool_name);
    const commandName = stringValue(item?.commandName || item?.command_name);
    const diffText = diffTextFromItem(item);
    const diffFiles = parseDiffFiles(diffText);
    if (diffFiles.length > 0) {
      for (const file of diffFiles) {
        mergeFileStats(fileMap, { ...file, sourceId: item?.id || item?.call_id || "" });
      }
      continue;
    }
    if (WRITE_TOOLS.has(toolName) || commandName === "diff") {
      const path = changedPathFromItem(item);
      if (path) {
        mergeFileStats(fileMap, {
          path,
          additions: numberValue(item?.data?.additions),
          deletions: numberValue(item?.data?.deletions),
          sourceId: item?.id || item?.call_id || "",
        });
      }
    }
  }
  const files = Array.from(fileMap.values());
  return {
    files,
    additions: files.reduce((sum, file) => sum + numberValue(file.additions), 0),
    deletions: files.reduce((sum, file) => sum + numberValue(file.deletions), 0),
  };
}

function commandPreviewFor(toolName, args) {
  if (!args || typeof args !== "object") return "";
  if (toolName === "run_recipe") return stringValue(args.recipe_id || args.command);
  if (toolName === "run_command" || toolName === "shell" || toolName === "bash") {
    return stringValue(args.command);
  }
  if (toolName === "grep_text") return stringValue(args.pattern || args.query);
  if (toolName === "glob_files") return stringValue(args.pattern);
  if (toolName === "read_file" || toolName === "write_file" || toolName === "edit_file") {
    return stringValue(args.path);
  }
  return "";
}

function publicArgs(args) {
  const result = {};
  for (const [key, value] of Object.entries(args || {})) {
    if (key.startsWith(META_ARG_PREFIX)) continue;
    result[key] = value;
  }
  return result;
}

function detailTextFor(item) {
  if (item?.error) return stringValue(item.error).slice(0, 4000);
  const data = item?.data;
  if (data == null) return "";
  if (typeof data === "string") return data.slice(0, 4000);
  if (typeof data.summary === "string") return data.summary.slice(0, 4000);
  if (typeof data.message === "string") return data.message.slice(0, 4000);
  if (typeof data.diff_preview === "string") return data.diff_preview.slice(0, 4000);
  try {
    return JSON.stringify(data, null, 2).slice(0, 4000);
  } catch (_) {
    return "";
  }
}

function toneForWork(item, status) {
  if (status === "error") return "error";
  if (status === "running") return "running";
  return "neutral";
}

export function normalizeWorkEntry(item) {
  const args = publicArgs(item?.arguments || {});
  const toolName = stringValue(item?.toolName || item?.tool_name);
  const status = stringValue(item?.status || "running");
  const changed = summarizeChangedFiles([item]);
  return {
    id: stringValue(item?.id || item?.call_id || toolName || "work"),
    kind: T3_ROW_KINDS.WORK,
    turnId: stringValue(item?.turnId || item?.turn_id),
    stepId: stringValue(item?.stepId || item?.step_id),
    stepIndex: numberValue(item?.stepIndex || item?.step_index),
    toolName,
    label: stringValue(item?.label || item?.tool_label || toolName || "Work"),
    status,
    tone: toneForWork(item, status),
    requestKind: stringValue(item?.permissionCategory || item?.permission_category),
    commandPreview: commandPreviewFor(toolName, args),
    args,
    detail: detailTextFor(item),
    changedFiles: changed.files,
    additions: changed.additions,
    deletions: changed.deletions,
    rawItem: item || {},
  };
}

function messageRow(item, role) {
  return {
    id: stringValue(item?.id || `${role}-${item?.turnId || ""}`),
    kind: T3_ROW_KINDS.MESSAGE,
    role,
    turnId: stringValue(item?.turnId || item?.turn_id),
    stepId: stringValue(item?.stepId || item?.step_id),
    stepIndex: numberValue(item?.stepIndex || item?.step_index),
    content: stringValue(item?.content),
    streaming: Boolean(item?.streaming),
    rawItem: item || {},
  };
}

function systemNoticeRow(item) {
  return {
    id: stringValue(item?.id || "system-notice"),
    kind: T3_ROW_KINDS.SYSTEM_NOTICE,
    turnId: stringValue(item?.turnId || item?.turn_id),
    tone: stringValue(item?.tone || "context"),
    content: stringValue(item?.content || item?.label),
    rawItem: item || {},
  };
}

function interactionRow(item, fallback = {}) {
  return {
    id: stringValue(item?.id || item?.interactionId || fallback.id || "interaction"),
    kind: T3_ROW_KINDS.INTERACTION,
    turnId: stringValue(item?.turnId || item?.turn_id || fallback.turnId),
    interactionId: stringValue(item?.interactionId || item?.interaction_id || item?.id),
    interactionKind: stringValue(item?.interactionKind || item?.kind || fallback.kind),
    status: item?.kind === "interaction_resolved" || item?.resolved ? "resolved" : "pending",
    label: stringValue(item?.label || fallback.label || "interaction"),
    detail: stringValue(item?.detail || fallback.detail),
    rawItem: item || {},
  };
}

function allTurnItems(group) {
  const items = [];
  if (group?.userItem) items.push(group.userItem);
  for (const item of group?.leadingSystemItems || []) items.push(item);
  for (const item of group?.systemItems || []) items.push(item);
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) items.push(item);
    if (step?.assistantItem) items.push(step.assistantItem);
  }
  for (const item of group?.trailingTurnItems || []) items.push(item);
  for (const item of group?.detachedItems || []) items.push(item);
  for (const item of group?.sessionFallbackItems || []) items.push(item);
  return items;
}

function turnWorkEntries(group) {
  const entries = [];
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) {
      if (item?.kind === "tool") entries.push(normalizeWorkEntry(item));
      else if (item?.kind === "interaction_requested" || item?.kind === "interaction_resolved") {
        entries.push(interactionRow(item));
      }
    }
  }
  for (const item of group?.trailingTurnItems || group?.detachedItems || []) {
    if (item?.kind === "tool") entries.push(normalizeWorkEntry(item));
    if (item?.kind === "interaction_requested" || item?.kind === "interaction_resolved") {
      entries.push(interactionRow(item));
    }
  }
  return entries;
}

function assistantRowsForTurn(group) {
  const rows = [];
  for (const step of group?.steps || []) {
    if (step?.assistantItem) rows.push(messageRow(step.assistantItem, "assistant"));
  }
  return rows;
}

function hasInterruptedWork(entries) {
  return entries.some((entry) => entry.tone === "interrupted" || entry.tone === "discarded");
}

export function isTurnFoldedByDefault(group, context = {}) {
  const entries = turnWorkEntries(group).filter((entry) => entry.kind === T3_ROW_KINDS.WORK);
  if (entries.length === 0) return false;
  if (hasInterruptedWork(entries)) return false;
  if (context.currentStatus === "running" && group?.turnId && group.turnId === context.activeTurnId) {
    return false;
  }
  return assistantRowsForTurn(group).length > 0;
}

function pushLooseItem(rows, item) {
  if (!item) return;
  if (item.kind === "assistant") rows.push(messageRow(item, "assistant"));
  else if (item.kind === "user") rows.push(messageRow(item, "user"));
  else if (item.kind === "tool") rows.push(normalizeWorkEntry(item));
  else if (item.kind === "interaction_requested" || item.kind === "interaction_resolved") {
    rows.push(interactionRow(item));
  } else rows.push(systemNoticeRow(item));
}

function diffSummaryRow(group) {
  const changed = summarizeChangedFiles(allTurnItems(group));
  if (changed.files.length === 0) return null;
  return {
    id: `diff-summary-${group?.turnId || changed.files.map((file) => file.path).join("-")}`,
    kind: T3_ROW_KINDS.DIFF_SUMMARY,
    turnId: stringValue(group?.turnId),
    files: changed.files,
    changedFiles: changed.files,
    additions: changed.additions,
    deletions: changed.deletions,
  };
}

export function projectT3TimelineRows({
  turnGroups = [],
  currentStatus = "idle",
  activeTurnId = "",
  currentInteraction = null,
  interactionNotice = null,
} = {}) {
  const rows = [];
  const context = { currentStatus, activeTurnId };
  for (const group of turnGroups || []) {
    if (group?.userItem) rows.push(messageRow(group.userItem, "user"));
    for (const item of group?.leadingSystemItems || group?.systemItems || []) {
      pushLooseItem(rows, item);
    }

    const entries = turnWorkEntries(group);
    const shouldFold = isTurnFoldedByDefault(group, context);
    if (entries.length > 0) {
      if (shouldFold) {
        rows.push({
          id: `turn-fold-${group.turnId || rows.length}`,
          kind: T3_ROW_KINDS.TURN_FOLD,
          turnId: stringValue(group.turnId),
          label: "Worked for this turn",
          workCount: entries.filter((entry) => entry.kind === T3_ROW_KINDS.WORK).length,
          defaultOpen: false,
          entries,
        });
      } else {
        rows.push(...entries);
      }
    }

    const changedRow = diffSummaryRow(group);
    if (changedRow) rows.push(changedRow);

    rows.push(...assistantRowsForTurn(group));

    for (const item of group?.trailingTurnItems || group?.detachedItems || []) {
      if (item?.kind !== "tool" && item?.kind !== "interaction_requested" && item?.kind !== "interaction_resolved") {
        pushLooseItem(rows, item);
      }
    }
    for (const item of group?.sessionFallbackItems || []) pushLooseItem(rows, item);
  }

  if (currentInteraction) {
    rows.push(
      interactionRow(currentInteraction, {
        id: currentInteraction.interaction_id,
        kind: currentInteraction.kind,
        label: currentInteraction.tool_name || currentInteraction.question || currentInteraction.kind,
        detail: currentInteraction.reason || currentInteraction.question || "",
      }),
    );
  } else if (interactionNotice) {
    rows.push({
      id: `interaction-notice-${interactionNotice.interactionId || interactionNotice.kind || "notice"}`,
      kind: T3_ROW_KINDS.SYSTEM_NOTICE,
      tone: interactionNotice.kind === "expired" ? "context" : "warning",
      content: interactionNotice.detail || interactionNotice.kind || "interaction",
      rawItem: interactionNotice,
    });
  }

  if (currentStatus === "running" && rows.length === 0) {
    rows.push({
      id: "working",
      kind: T3_ROW_KINDS.WORKING,
      label: "Working",
    });
  }

  return rows;
}
