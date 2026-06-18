export const T3_ROW_KINDS = Object.freeze({
  MESSAGE: "message",
  WORK: "work",
  TURN_FOLD: "turn_fold",
  INTERACTION: "interaction",
  DIFF_SUMMARY: "diff_summary",
  THINKING: "thinking",
  REASONING: "reasoning",
  COMPACT: "compact",
  COMMAND_RESULT: "command_result",
  REVIEW_RESULT: "review_result",
  WORKING: "working",
  SYSTEM_NOTICE: "system_notice",
});

const WRITE_TOOLS = new Set(["write_file", "edit_file", "git_diff"]);
const META_ARG_PREFIX = "_";
const DETAIL_TEXT_LIMIT = 4000;

function stringValue(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

function timestampValue(...values) {
  for (const value of values) {
    const text = stringValue(value);
    if (!text) continue;
    const parsed = Date.parse(text);
    if (Number.isFinite(parsed)) return text;
  }
  return "";
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

function truncateText(value, limit = DETAIL_TEXT_LIMIT) {
  const text = stringValue(value);
  if (text.length <= limit) return text;
  return `${text.slice(0, limit)}\n...[truncated]`;
}

function pushField(fields, label, value, options = {}) {
  if (value == null || value === "") return;
  fields.push({
    label,
    value: stringValue(value),
    mono: options.mono !== false,
  });
}

function firstString(...values) {
  for (const value of values) {
    if (typeof value === "string" && value) return value;
  }
  return "";
}

function publicValuePairs(args = {}, data = {}) {
  const keys = [];
  for (const key of Object.keys(args || {})) {
    if (!keys.includes(key)) keys.push(key);
  }
  for (const key of Object.keys(data || {})) {
    if (!keys.includes(key)) keys.push(key);
  }
  const hidden = new Set([
    "content",
    "content_preview",
    "preview",
    "matches",
    "files",
    "stdout",
    "stdout_preview",
    "stderr",
    "stderr_preview",
    "diff",
    "diff_preview",
    "unified_diff",
    "summary",
    "message",
    "error_kind",
  ]);
  return keys
    .filter((key) => !key.startsWith(META_ARG_PREFIX) && !hidden.has(key))
    .map((key) => [key, data[key] != null ? data[key] : args[key]])
    .filter(([, value]) => value != null && value !== "" && typeof value !== "object");
}

function matchItems(data) {
  const source = Array.isArray(data?.matches)
    ? data.matches
    : Array.isArray(data?.preview)
      ? data.preview
      : [];
  return source.slice(0, 12).map((item, index) => {
    if (item && typeof item === "object") {
      return {
        id: stringValue(item.id || `${item.path || "match"}-${item.line || index}`),
        path: stringValue(item.path),
        line: item.line !== undefined ? stringValue(item.line) : "",
        text: truncateText(item.text || item.content || item.preview || "", 320),
      };
    }
    return {
      id: `match-${index + 1}`,
      path: "",
      line: "",
      text: truncateText(item, 320),
    };
  });
}

function fileItems(data) {
  const source = Array.isArray(data?.files)
    ? data.files
    : Array.isArray(data?.preview)
      ? data.preview
      : [];
  return source.slice(0, 20).map((item, index) => {
    if (item && typeof item === "object") {
      return {
        id: stringValue(item.path || item.name || `file-${index + 1}`),
        path: stringValue(item.path || item.name || item.file),
        text: stringValue(item.kind || item.type),
      };
    }
    return {
      id: `file-${index + 1}`,
      path: stringValue(item),
      text: "",
    };
  }).filter((item) => item.path);
}

function buildToolDetailModel(item, args, changed) {
  const data = item?.data && typeof item.data === "object" ? item.data : {};
  const toolName = stringValue(item?.toolName || item?.tool_name);
  const fields = [];
  const sections = [];
  const path = stringValue(data.path || data.file || args.path || args.file);
  const pattern = stringValue(data.pattern || data.query || args.pattern || args.query);
  const command = stringValue(data.command || args.command);
  const recipe = stringValue(data.recipe_id || data.recipeId || args.recipe_id || args.recipeId);
  const target = stringValue(data.target || args.target);
  const preview = firstString(data.content_preview, data.preview, data.summary, data.message);
  const stdout = firstString(data.stdout_preview, data.stdout);
  const stderr = firstString(data.stderr_preview, data.stderr);
  const diff = diffTextFromItem(item);
  const matches = matchItems(data);
  const files = fileItems(data);

  if (path) pushField(fields, "path", path);
  if (pattern) pushField(fields, "pattern", pattern);
  if (recipe) pushField(fields, "recipe", recipe);
  if (target) pushField(fields, "target", target);
  if (command) pushField(fields, "command", command);
  if (data.cwd || args.cwd) pushField(fields, "cwd", data.cwd || args.cwd);
  if (data.exit_code !== undefined) pushField(fields, "exit", data.exit_code);
  if (data.line_count !== undefined) pushField(fields, "lines", data.line_count);
  if (data.char_count !== undefined) pushField(fields, "chars", data.char_count);
  if (data.match_count !== undefined) pushField(fields, "matches", data.match_count);
  if (data.returned_count !== undefined && data.total_count !== undefined) {
    pushField(fields, "returned", `${data.returned_count}/${data.total_count}`);
  }
  for (const [key, value] of publicValuePairs(args, data)) {
    if (fields.some((field) => field.label === key)) continue;
    pushField(fields, key, value);
  }

  if (item?.error) {
    sections.push({
      kind: "error",
      title: "Error",
      content: truncateText(item.error),
    });
  }
  if (preview) {
    sections.push({
      kind: "preview",
      title: toolName === "read_file" ? "Preview" : "Summary",
      content: truncateText(preview),
    });
  }
  if (matches.length > 0) {
    sections.push({
      kind: "matches",
      title: "Matches",
      items: matches,
    });
  }
  if (files.length > 0) {
    sections.push({
      kind: "files",
      title: "Files",
      items: files,
    });
  }
  if (stdout) {
    sections.push({
      kind: "stdout",
      title: "stdout",
      content: truncateText(stdout),
    });
  }
  if (stderr) {
    sections.push({
      kind: "stderr",
      title: "stderr",
      content: truncateText(stderr),
    });
  }
  if (diff) {
    sections.push({
      kind: "diff",
      title: "Diff",
      content: truncateText(diff),
    });
  }
  if (Array.isArray(changed?.files) && changed.files.length > 0) {
    sections.push({
      kind: "changed_files",
      title: "Changed files",
      items: changed.files.map((file) => ({
        id: file.path,
        path: file.path,
        additions: numberValue(file.additions),
        deletions: numberValue(file.deletions),
      })),
    });
  }

  if (fields.length === 0 && sections.length === 0) return null;
  return {
    kind: "tool_detail",
    toolName,
    status: stringValue(item?.status || "running"),
    fields,
    sections,
  };
}

function detailTextFor(item) {
  if (item?.error) return stringValue(item.error).slice(0, 4000);
  const data = item?.data;
  if (data == null) return "";
  if (typeof data === "string") return data.slice(0, 4000);
  if (typeof data.summary === "string") return data.summary.slice(0, 4000);
  if (typeof data.message === "string") return data.message.slice(0, 4000);
  if (typeof data.diff_preview === "string") return data.diff_preview.slice(0, 4000);
  return "";
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
    createdAt: timestampValue(item?.createdAt, item?.created_at, item?.startedAt, item?.started_at),
    completedAt: timestampValue(item?.completedAt, item?.completed_at, item?.finishedAt, item?.finished_at),
    toolName,
    label: stringValue(item?.label || item?.tool_label || toolName || "Work"),
    status,
    tone: toneForWork(item, status),
    requestKind: stringValue(item?.permissionCategory || item?.permission_category),
    commandPreview: commandPreviewFor(toolName, args),
    args,
    detail: detailTextFor(item),
    detailModel: buildToolDetailModel(item, args, changed),
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
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    completedAt: timestampValue(item?.completedAt, item?.completed_at),
    content: stringValue(item?.content),
    streaming: Boolean(item?.streaming),
    rawItem: item || {},
  };
}

function wordCountFor(text) {
  return stringValue(text).split(/\s+/).filter(Boolean).length;
}

function reasoningRow(item) {
  const content = stringValue(item?.content || item?.text || item?.summary);
  return {
    id: stringValue(item?.id || `reasoning-${item?.turnId || item?.turn_id || "row"}`),
    kind: T3_ROW_KINDS.REASONING,
    turnId: stringValue(item?.turnId || item?.turn_id),
    stepId: stringValue(item?.stepId || item?.step_id),
    stepIndex: numberValue(item?.stepIndex || item?.step_index),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    label: stringValue(item?.label || "Thinking"),
    content,
    wordCount: wordCountFor(content),
    streaming: Boolean(item?.streaming),
    rawItem: item || {},
  };
}

function compactRow(item) {
  return {
    id: stringValue(item?.id || `compact-${item?.turnId || item?.turn_id || "row"}`),
    kind: T3_ROW_KINDS.COMPACT,
    turnId: stringValue(item?.turnId || item?.turn_id),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    tone: stringValue(item?.tone || "context"),
    content: stringValue(item?.content || item?.summary || "Context compacted"),
    summarizedTurns:
      item?.summarizedTurns !== undefined
        ? numberValue(item.summarizedTurns)
        : item?.summarized_turns !== undefined
          ? numberValue(item.summarized_turns)
          : undefined,
    recentTurns:
      item?.recentTurns !== undefined
        ? numberValue(item.recentTurns)
        : item?.recent_turns !== undefined
          ? numberValue(item.recent_turns)
          : undefined,
    approxTokensAfter:
      item?.approxTokensAfter !== undefined
        ? numberValue(item.approxTokensAfter)
        : item?.approx_tokens_after !== undefined
          ? numberValue(item.approx_tokens_after)
          : undefined,
    rawItem: item || {},
  };
}

function commandResultContent(item) {
  return stringValue(
    item?.content ||
      item?.message ||
      item?.summary ||
      item?.data?.message ||
      item?.data?.summary ||
      "",
  );
}

function commandResultRow(item) {
  const commandName = stringValue(item?.commandName || item?.command_name || "command");
  return {
    id: stringValue(item?.id || `command-${commandName}-${item?.turnId || item?.turn_id || "row"}`),
    kind: T3_ROW_KINDS.COMMAND_RESULT,
    turnId: stringValue(item?.turnId || item?.turn_id),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    commandName,
    label: `/${commandName}`,
    success: item?.success !== false,
    tone: item?.success === false ? "error" : "context",
    content: commandResultContent(item),
    data: item?.data || {},
    rawItem: item || {},
  };
}

function normalizeReviewFinding(finding, index) {
  return {
    id: stringValue(finding?.id || `finding-${index + 1}`),
    severity: stringValue(finding?.severity || ""),
    priority: finding?.priority !== undefined ? numberValue(finding.priority) : undefined,
    title: stringValue(finding?.title || finding?.message || "Review finding"),
    body: stringValue(finding?.body || finding?.detail || finding?.description || ""),
    file: stringValue(finding?.file || finding?.path || ""),
    line: finding?.line !== undefined ? numberValue(finding.line) : undefined,
  };
}

function reviewResultRow(item) {
  const review = item?.data?.review || item?.review || {};
  const findings = Array.isArray(review.findings)
    ? review.findings.map((finding, index) => normalizeReviewFinding(finding, index))
    : [];
  const residualRisks = Array.isArray(review.residual_risks)
    ? review.residual_risks.map((risk) => stringValue(risk)).filter(Boolean)
    : Array.isArray(review.residualRisks)
      ? review.residualRisks.map((risk) => stringValue(risk)).filter(Boolean)
      : [];
  return {
    ...commandResultRow(item),
    kind: T3_ROW_KINDS.REVIEW_RESULT,
    commandName: "review",
    label: "/review",
    findings,
    residualRisks,
  };
}

function thinkingRow({ activeTurnId, idSuffix = "active", createdAt = "" } = {}) {
  return {
    id: `thinking-${activeTurnId || idSuffix || "active"}`,
    kind: T3_ROW_KINDS.THINKING,
    turnId: stringValue(activeTurnId),
    createdAt: timestampValue(createdAt),
    label: "Thinking",
    streaming: true,
  };
}

function systemNoticeRow(item) {
  return {
    id: stringValue(item?.id || "system-notice"),
    kind: T3_ROW_KINDS.SYSTEM_NOTICE,
    turnId: stringValue(item?.turnId || item?.turn_id),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
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
    createdAt: timestampValue(item?.createdAt, item?.created_at, fallback.createdAt),
    interactionId: stringValue(item?.interactionId || item?.interaction_id || item?.id),
    interactionKind: stringValue(item?.interactionKind || item?.kind || fallback.kind),
    status: item?.kind === "interaction_resolved" || item?.resolved ? "resolved" : "pending",
    label: stringValue(item?.label || fallback.label || "interaction"),
    detail: stringValue(item?.detail || fallback.detail),
    rawItem: item || {},
  };
}

function activityRowForItem(item) {
  if (!item) return null;
  if (item.kind === "tool") return normalizeWorkEntry(item);
  if (item.kind === "interaction_requested" || item.kind === "interaction_resolved") {
    return interactionRow(item);
  }
  if (item.kind === "reasoning") return reasoningRow(item);
  if (item.kind === "compact") return compactRow(item);
  if (item.kind === "command_result" || item.kind === "command_result_fallback") {
    const commandName = stringValue(item?.commandName || item?.command_name);
    if (commandName === "review" || item?.data?.review || item?.review) {
      return reviewResultRow(item);
    }
    return commandResultRow(item);
  }
  if (item.kind === "system") return systemNoticeRow(item);
  return null;
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

function turnActivityEntries(group) {
  const entries = [];
  function pushActivity(item) {
    const row = activityRowForItem(item);
    if (row) entries.push(row);
  }
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) {
      pushActivity(item);
    }
  }
  for (const item of group?.trailingTurnItems || []) {
    if (item?.kind === "tool") pushActivity(item);
    if (item?.kind === "interaction_requested" || item?.kind === "interaction_resolved") {
      pushActivity(item);
    }
  }
  for (const item of group?.detachedItems || []) {
    if (item?.kind === "tool") pushActivity(item);
    if (item?.kind === "interaction_requested" || item?.kind === "interaction_resolved") {
      pushActivity(item);
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

function timestampMs(value) {
  const parsed = Date.parse(stringValue(value));
  return Number.isFinite(parsed) ? parsed : NaN;
}

function minTimestamp(...values) {
  let best = "";
  let bestMs = NaN;
  for (const value of values.flat()) {
    const text = stringValue(value);
    const parsed = timestampMs(text);
    if (!Number.isFinite(parsed)) continue;
    if (!Number.isFinite(bestMs) || parsed < bestMs) {
      best = text;
      bestMs = parsed;
    }
  }
  return best;
}

function maxTimestamp(...values) {
  let best = "";
  let bestMs = NaN;
  for (const value of values.flat()) {
    const text = stringValue(value);
    const parsed = timestampMs(text);
    if (!Number.isFinite(parsed)) continue;
    if (!Number.isFinite(bestMs) || parsed > bestMs) {
      best = text;
      bestMs = parsed;
    }
  }
  return best;
}

function formatElapsedDuration(startIso, endIso) {
  const start = timestampMs(startIso);
  const end = timestampMs(endIso);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return "";
  const totalSeconds = Math.max(0, Math.floor((end - start) / 1000));
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) return `${minutes}m ${seconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

function turnStartTimestamp(group, entries) {
  const candidates = [
    group?.startedAt,
    group?.started_at,
    group?.userItem?.createdAt,
    group?.userItem?.created_at,
    ...(entries || []).map((entry) => entry.createdAt),
  ];
  return minTimestamp(candidates);
}

function turnEndTimestamp(group, entries) {
  const assistantRows = assistantRowsForTurn(group);
  const candidates = [
    group?.completedAt,
    group?.completed_at,
    ...assistantRows.map((row) => row.completedAt || row.createdAt),
    ...(entries || []).map((entry) => entry.completedAt || entry.createdAt),
  ];
  return maxTimestamp(candidates);
}

function turnFoldLabel(group, entries) {
  const duration = formatElapsedDuration(turnStartTimestamp(group, entries), turnEndTimestamp(group, entries));
  if (hasInterruptedWork(entries)) {
    return duration ? `You stopped after ${duration}` : "You stopped this response";
  }
  return duration ? `Worked for ${duration}` : "Worked for this turn";
}

export function isTurnFoldedByDefault(group, context = {}) {
  const entries = turnActivityEntries(group);
  const workEntries = entries.filter((entry) => entry.kind === T3_ROW_KINDS.WORK);
  if (entries.length === 0) return false;
  if (hasInterruptedWork(workEntries)) return false;
  if (workEntries.some((entry) => entry.status === "running" || entry.tone === "running")) return false;
  if (workEntries.some((entry) => entry.status === "error" || entry.tone === "error")) return false;
  if (entries.some((entry) => entry.kind === T3_ROW_KINDS.REASONING && entry.streaming)) return false;
  if (context.currentStatus === "running" && group?.turnId && group.turnId === context.activeTurnId) {
    return false;
  }
  return assistantRowsForTurn(group).length > 0;
}

function pushLooseItem(push, item) {
  if (!item) return;
  if (item.kind === "assistant") push(messageRow(item, "assistant"));
  else if (item.kind === "user") push(messageRow(item, "user"));
  else {
    const row = activityRowForItem(item);
    push(row || systemNoticeRow(item));
  }
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
  thinkingActive = false,
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

    const entries = turnActivityEntries(group);
    const shouldFold = isTurnFoldedByDefault(group, context);
    if (entries.length > 0) {
      if (shouldFold) {
        pushRow({
          id: `turn-fold-${group.turnId || rows.length}`,
          kind: T3_ROW_KINDS.TURN_FOLD,
          turnId: stringValue(group.turnId),
          createdAt: turnStartTimestamp(group, entries),
          label: turnFoldLabel(group, entries),
          workCount: entries.filter((entry) => entry.kind === T3_ROW_KINDS.WORK).length,
          reasoningCount: entries.filter((entry) => entry.kind === T3_ROW_KINDS.REASONING).length,
          entryCount: entries.length,
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

  const hasVisibleReasoning = rows.some(
    (row) =>
      (row.kind === T3_ROW_KINDS.REASONING && (!activeTurnId || row.turnId === activeTurnId)) ||
      (row.kind === T3_ROW_KINDS.TURN_FOLD &&
        Array.isArray(row.entries) &&
        row.entries.some(
          (entry) => entry.kind === T3_ROW_KINDS.REASONING && (!activeTurnId || entry.turnId === activeTurnId),
        )),
  );
  const hasActiveTurnRow = rows.some(
    (row) =>
      row.turnId === activeTurnId ||
      (row.kind === T3_ROW_KINDS.TURN_FOLD &&
        Array.isArray(row.entries) &&
        row.entries.some((entry) => entry.turnId === activeTurnId)),
  );
  if (currentStatus === "running" && thinkingActive && !hasVisibleReasoning && (activeTurnId || hasActiveTurnRow)) {
    const activeCreatedAt = minTimestamp(
      rows
        .filter((row) => row.turnId === activeTurnId)
        .map((row) => row.createdAt),
    );
    pushRow(thinkingRow({ activeTurnId, idSuffix: rows.length, createdAt: activeCreatedAt }));
  }

  if (currentStatus === "running" && rows.length === 0) {
    pushRow({
      id: "working",
      kind: T3_ROW_KINDS.WORKING,
      label: "Working",
      createdAt: "",
    });
  }

  return rows;
}
