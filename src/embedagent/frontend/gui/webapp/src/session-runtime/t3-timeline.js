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

const SORT_LOCALE_OPTIONS = { numeric: true, sensitivity: "base" };

function pathFromDiffHeader(line) {
  const value = stringValue(line).replace(/^(---|\+\+\+)\s+/, "").trim();
  if (!value || value === "/dev/null") return "";
  const first = value.split(/\s+/)[0];
  return first.replace(/^[ab]\//, "");
}

function normalizePathSegments(pathValue) {
  return stringValue(pathValue)
    .replace(/\\/g, "/")
    .split("/")
    .filter((segment) => segment.length > 0);
}

function normalizeChangedFilePath(pathValue) {
  return normalizePathSegments(pathValue).join("/");
}

function compareByName(left, right) {
  return stringValue(left?.name).localeCompare(stringValue(right?.name), undefined, SORT_LOCALE_OPTIONS);
}

function readDiffStat(file) {
  const additions = numberValue(file?.additions, NaN);
  const deletions = numberValue(file?.deletions, NaN);
  if (!Number.isFinite(additions) || !Number.isFinite(deletions)) return null;
  return { additions, deletions };
}

function compactDirectoryNode(node) {
  const compactedChildren = (node.children || []).map((child) =>
    child.kind === "directory" ? compactDirectoryNode(child) : child,
  );
  let compactedNode = {
    ...node,
    children: compactedChildren,
  };
  while (compactedNode.children.length === 1 && compactedNode.children[0]?.kind === "directory") {
    const onlyChild = compactedNode.children[0];
    compactedNode = {
      kind: "directory",
      name: `${compactedNode.name}/${onlyChild.name}`,
      path: onlyChild.path,
      stat: onlyChild.stat,
      children: onlyChild.children,
    };
  }
  return compactedNode;
}

function toChangedFileTreeNodes(directory) {
  const subdirectories = Array.from(directory.directories.values())
    .sort(compareByName)
    .map((subdirectory) =>
      compactDirectoryNode({
        kind: "directory",
        name: subdirectory.name,
        path: subdirectory.path,
        stat: {
          additions: subdirectory.stat.additions,
          deletions: subdirectory.stat.deletions,
        },
        children: toChangedFileTreeNodes(subdirectory),
      }),
    );
  const files = directory.files.slice().sort(compareByName);
  return subdirectories.concat(files);
}

export function summarizeDiffStats(files = []) {
  return (files || []).reduce(
    (acc, file) => {
      const stat = readDiffStat(file);
      if (!stat) return acc;
      return {
        additions: acc.additions + stat.additions,
        deletions: acc.deletions + stat.deletions,
      };
    },
    { additions: 0, deletions: 0 },
  );
}

export function buildChangedFilesTree(files = []) {
  const root = {
    name: "",
    path: "",
    stat: { additions: 0, deletions: 0 },
    directories: new Map(),
    files: [],
  };
  for (const file of files || []) {
    const segments = normalizePathSegments(file?.path);
    if (segments.length === 0) continue;
    const fileName = segments[segments.length - 1];
    const filePath = segments.join("/");
    const stat = readDiffStat(file);
    const ancestors = [root];
    let currentDirectory = root;
    for (const segment of segments.slice(0, -1)) {
      const nextPath = currentDirectory.path ? `${currentDirectory.path}/${segment}` : segment;
      let nextDirectory = currentDirectory.directories.get(segment);
      if (!nextDirectory) {
        nextDirectory = {
          name: segment,
          path: nextPath,
          stat: { additions: 0, deletions: 0 },
          directories: new Map(),
          files: [],
        };
        currentDirectory.directories.set(segment, nextDirectory);
      }
      currentDirectory = nextDirectory;
      ancestors.push(currentDirectory);
    }
    currentDirectory.files.push({
      kind: "file",
      name: fileName,
      path: filePath,
      stat,
      source: file,
    });
    if (stat) {
      for (const ancestor of ancestors) {
        ancestor.stat.additions += stat.additions;
        ancestor.stat.deletions += stat.deletions;
      }
    }
  }
  return toChangedFileTreeNodes(root);
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
  const path = normalizeChangedFilePath(file.path);
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
  const errorKind = stringValue(item?.data?.error_kind);
  if (errorKind === "interrupted") return "interrupted";
  if (errorKind === "discarded") return "discarded";
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
  for (const item of group?.trailingTurnItems || []) {
    if (item?.kind === "tool") entries.push(normalizeWorkEntry(item));
    if (item?.kind === "interaction_requested" || item?.kind === "interaction_resolved") {
      entries.push(interactionRow(item));
    }
  }
  for (const item of group?.detachedItems || []) {
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

function pushLooseItem(push, item) {
  if (!item) return;
  if (item.kind === "assistant") push(messageRow(item, "assistant"));
  else if (item.kind === "user") push(messageRow(item, "user"));
  else if (item.kind === "tool") push(normalizeWorkEntry(item));
  else if (item.kind === "interaction_requested" || item.kind === "interaction_resolved") {
    push(interactionRow(item));
  } else push(systemNoticeRow(item));
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
  const seenInteractionIds = new Set();
  function pushRow(row) {
    if (!row) return;
    if (row.kind === T3_ROW_KINDS.INTERACTION) {
      const key = row.interactionId || row.id || "";
      if (key && seenInteractionIds.has(key)) return;
      if (key) seenInteractionIds.add(key);
    }
    rows.push(row);
  }
  for (const group of turnGroups || []) {
    if (group?.userItem) pushRow(messageRow(group.userItem, "user"));
    for (const item of group?.leadingSystemItems || []) {
      pushLooseItem(pushRow, item);
    }
    for (const item of group?.systemItems || []) {
      pushLooseItem(pushRow, item);
    }

    const entries = turnWorkEntries(group);
    const shouldFold = isTurnFoldedByDefault(group, context);
    if (entries.length > 0) {
      if (shouldFold) {
        pushRow({
          id: `turn-fold-${group.turnId || rows.length}`,
          kind: T3_ROW_KINDS.TURN_FOLD,
          turnId: stringValue(group.turnId),
          label: "Worked for this turn",
          workCount: entries.filter((entry) => entry.kind === T3_ROW_KINDS.WORK).length,
          defaultOpen: false,
          entries,
        });
      } else {
        for (const entry of entries) pushRow(entry);
      }
    }

    const changedRow = diffSummaryRow(group);
    if (changedRow) pushRow(changedRow);

    for (const row of assistantRowsForTurn(group)) pushRow(row);

    for (const item of (group?.trailingTurnItems || []).concat(group?.detachedItems || [])) {
      if (item?.kind !== "tool" && item?.kind !== "interaction_requested" && item?.kind !== "interaction_resolved") {
        pushLooseItem(pushRow, item);
      }
    }
    for (const item of group?.sessionFallbackItems || []) pushLooseItem(pushRow, item);
  }

  if (currentInteraction) {
    pushRow(
      interactionRow(currentInteraction, {
        id: currentInteraction.interaction_id,
        kind: currentInteraction.kind,
        label: currentInteraction.tool_name || currentInteraction.question || currentInteraction.kind,
        detail: currentInteraction.reason || currentInteraction.question || "",
      }),
    );
  } else if (interactionNotice) {
    pushRow({
      id: `interaction-notice-${interactionNotice.interactionId || interactionNotice.kind || "notice"}`,
      kind: T3_ROW_KINDS.SYSTEM_NOTICE,
      tone: interactionNotice.kind === "expired" ? "context" : "warning",
      content: interactionNotice.detail || interactionNotice.kind || "interaction",
      rawItem: interactionNotice,
    });
  }

  if (currentStatus === "running" && rows.length === 0) {
    pushRow({
      id: "working",
      kind: T3_ROW_KINDS.WORKING,
      label: "Working",
    });
  }

  return rows;
}
