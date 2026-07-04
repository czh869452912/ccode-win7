import {
  commandPreviewFromToolPresentation,
  resolveToolPresentation,
} from "./tool-presentation.js";

export const T3_ROW_KINDS = Object.freeze({
  MESSAGE: "message",
  WORK: "work",
  TURN_FOLD: "turn_fold",
  INTERACTION: "interaction",
  DIFF_SUMMARY: "diff_summary",
  CONTEXT_SUMMARY: "context_summary",
  COMMAND_RESULT: "command_result",
  REVIEW_RESULT: "review_result",
  WORKING: "working",
  SYSTEM_NOTICE: "system_notice",
});

const META_ARG_PREFIX = "_";
const DETAIL_TEXT_LIMIT = 4000;
const TOOL_LIFECYCLE_STATUSES = new Set(["inProgress", "completed", "failed", "declined", "stopped"]);
const TOOL_ITEM_TYPES = new Set([
  "command_execution",
  "file_change",
  "web_search",
  "image_view",
  "mcp_tool_call",
  "dynamic_tool_call",
  "collab_agent_tool_call",
]);

function stringValue(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

function lineNumberValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.max(1, Math.trunc(number));
}

function lineDisplayValue(value) {
  const number = lineNumberValue(value);
  return number === null ? "" : String(number);
}

export function normalizeCompactToolLabel(value) {
  return stringValue(value).replace(/\s+(?:complete|completed|started)\s*$/i, "").trim();
}

function capitalizePhrase(value) {
  const trimmed = stringValue(value).trim();
  if (!trimmed) return trimmed;
  return `${trimmed.charAt(0).toUpperCase()}${trimmed.slice(1)}`;
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

function changedPathFromItem(item, presentation = null) {
  const key = stringValue(presentation?.changedPathArg);
  if (!key) return "";
  const data = item?.data || {};
  const args = publicArgs(item?.arguments || {});
  return stringValue(args[key] || data[key]);
}

function normalizeChangedFileEntry(entry) {
  if (typeof entry === "string") {
    const path = normalizeChangedFilePath(entry);
    return path ? { path, additions: 0, deletions: 0 } : null;
  }
  if (!entry || typeof entry !== "object") return null;
  const path = normalizeChangedFilePath(entry.path || entry.file || entry.filePath || entry.relativePath);
  if (!path) return null;
  return {
    path,
    additions: numberValue(entry.additions),
    deletions: numberValue(entry.deletions),
    diff: stringValue(entry.diff || entry.patch),
  };
}

function explicitChangedFiles(item) {
  const data = item?.data && typeof item.data === "object" ? item.data : {};
  const source =
    item?.changedFiles ||
    item?.changed_files ||
    data.changedFiles ||
    data.changed_files ||
    data.files_changed;
  if (!Array.isArray(source)) return [];
  return source.map(normalizeChangedFileEntry).filter(Boolean);
}

export function summarizeChangedFiles(items = [], options = {}) {
  const fileMap = new Map();
  const toolCatalog = options?.toolCatalog || {};
  for (const item of items || []) {
    for (const file of explicitChangedFiles(item)) {
      mergeFileStats(fileMap, { ...file, sourceId: item?.id || item?.call_id || "" });
    }
    const toolName = stringValue(item?.toolName || item?.tool_name);
    const toolPresentation = resolveToolPresentation(toolName, toolCatalog);
    const diffText = diffTextFromItem(item);
    const diffFiles = parseDiffFiles(diffText);
    if (diffFiles.length > 0) {
      for (const file of diffFiles) {
        mergeFileStats(fileMap, { ...file, sourceId: item?.id || item?.call_id || "" });
      }
      continue;
    }
    const path = changedPathFromItem(item, toolPresentation);
    if (path) {
      mergeFileStats(fileMap, {
        path,
        additions: numberValue(item?.data?.additions),
        deletions: numberValue(item?.data?.deletions),
        sourceId: item?.id || item?.call_id || "",
      });
    }
  }
  const files = Array.from(fileMap.values());
  return {
    files,
    additions: files.reduce((sum, file) => sum + numberValue(file.additions), 0),
    deletions: files.reduce((sum, file) => sum + numberValue(file.deletions), 0),
  };
}

function commandPreviewFor(args, presentation = null) {
  if (!args || typeof args !== "object") return "";
  return commandPreviewFromToolPresentation(presentation, args);
}

function permissionCategoryToRequestKind(value) {
  const text = stringValue(value);
  if (["command", "shell", "shell_exec", "toolchain_exec", "process", "network", "telemetry"].includes(text)) return "command";
  if (text === "file-read" || text === "read" || text === "workspace_read") return "file-read";
  if (text === "file-change" || text === "write" || text === "workspace_write" || text === "git_write") return "file-change";
  return "";
}

function normalizeRequestKind(value) {
  const text = stringValue(value);
  if (text === "command" || text === "file-read" || text === "file-change") return text;
  return permissionCategoryToRequestKind(text);
}

function normalizeItemType(value) {
  const text = stringValue(value);
  return TOOL_ITEM_TYPES.has(text) ? text : "";
}

function normalizeLifecycleStatus(value) {
  const text = stringValue(value);
  return TOOL_LIFECYCLE_STATUSES.has(text) ? text : "";
}

function changedFilePaths(files = []) {
  return (files || [])
    .map((file) => (typeof file === "string" ? file : file?.path))
    .map((path) => normalizeChangedFilePath(path))
    .filter(Boolean);
}

function normalizeEquivalentValue(value) {
  const trimmed = stringValue(value).trim();
  if (!trimmed) return "";
  return normalizeCompactToolLabel(trimmed).replace(/\s+/g, " ").toLowerCase();
}

function valuesEquivalent(left, right) {
  const normalizedLeft = normalizeEquivalentValue(left);
  const normalizedRight = normalizeEquivalentValue(right);
  return Boolean(normalizedLeft && normalizedLeft === normalizedRight);
}

function workLogEntryIsToolLike(entry) {
  if (entry?.tone === "tool" || entry?.tone === "thinking" || entry?.tone === "error") return true;
  if (stringValue(entry?.command).trim()) return true;
  if (stringValue(entry?.requestKind).trim()) return true;
  return Boolean(normalizeItemType(entry?.itemType));
}

function toolDetailTextLooksLikeFailure(text) {
  const value = stringValue(text).toLowerCase();
  if (!value) return false;
  if (value.includes("file not found")) return true;
  if (value.includes("no files found")) return true;
  if (value.includes("enoent") || value.includes("no such file or directory") || value.includes("no such file")) {
    return true;
  }
  if (value.includes("cannot find path") && value.includes("because it does not exist")) return true;
  if (value.includes("commandnotfoundexception")) return true;
  if (value.includes("is not recognized as the name of a cmdlet")) return true;
  if (value.includes("is not recognized") && value.includes("the term '")) return true;
  if (value.includes("a parameter cannot be found that matches parameter name")) return true;
  if (value.includes("command not found")) return true;
  if (/<exited with exit code\s+[1-9]\d*\s*>/i.test(text)) return true;
  if (/exit(?:ed)? with exit code\s+[1-9]\d*/i.test(text)) return true;
  if (/exit code\s*[:\s]\s*[1-9]\d*\b/i.test(text)) return true;
  return false;
}

function workEntryIndicatesToolFailure(entry) {
  if (entry?.tone === "error" || entry?.status === "error") return true;
  const lifecycleStatus = normalizeLifecycleStatus(entry?.toolLifecycleStatus);
  if (lifecycleStatus === "failed" || lifecycleStatus === "declined") return true;
  if (!workLogEntryIsToolLike(entry)) return false;
  const blob = [entry?.detail, entry?.command].map(stringValue).filter(Boolean).join("\n");
  return blob ? toolDetailTextLooksLikeFailure(blob) : false;
}

function workEntryIndicatesToolSuccess(entry) {
  if (!workLogEntryIsToolLike(entry)) return false;
  if (workEntryIndicatesToolFailure(entry)) return false;
  if (entry?.tone === "thinking") return false;
  const lifecycleStatus = normalizeLifecycleStatus(entry?.toolLifecycleStatus);
  if (lifecycleStatus === "failed" || lifecycleStatus === "declined") return false;
  if (lifecycleStatus === "inProgress" || lifecycleStatus === "stopped") return false;
  if (entry?.status === "running") return false;
  return true;
}

function workEntryIndicatesToolNeutralStatus(entry) {
  if (!workLogEntryIsToolLike(entry)) return false;
  if (workEntryIndicatesToolFailure(entry)) return false;
  if (workEntryIndicatesToolSuccess(entry)) return false;
  return true;
}

function workEntryPreview(entry) {
  if (entry?.command) return stringValue(entry.command);
  if (entry?.detail) return stringValue(entry.detail);
  const paths = changedFilePaths(entry?.changedFiles);
  if (paths.length === 0) return "";
  return paths.length === 1 ? paths[0] : `${paths[0]} +${paths.length - 1} more`;
}

function workEntryRawCommand(entry) {
  const rawCommand = stringValue(entry?.rawCommand).trim();
  const command = stringValue(entry?.command).trim();
  if (!rawCommand || !command) return "";
  return rawCommand === command ? "" : rawCommand;
}

function buildToolCallExpandedBody(entry) {
  const blocks = [];
  if (normalizeItemType(entry?.itemType) === "mcp_tool_call" && entry?.toolData !== undefined) {
    blocks.push(`MCP call\n${JSON.stringify(entry.toolData, null, 2)}`);
  }
  const raw = workEntryRawCommand(entry);
  if (raw) {
    blocks.push(raw);
  } else if (stringValue(entry?.command).trim()) {
    blocks.push(stringValue(entry.command).trim());
  }
  if (stringValue(entry?.detail).trim()) {
    blocks.push(stringValue(entry.detail).trim());
  }
  const paths = changedFilePaths(entry?.changedFiles);
  if (paths.length > 0) {
    blocks.push(paths.join("\n"));
  }
  return blocks.length > 0 ? blocks.join("\n\n") : "";
}

function workEntryIconName(entry) {
  if (entry?.sourceActivityKind === "runtime.warning") return "x";
  if (entry?.sourceActivityKind === "user-input.requested" || entry?.sourceActivityKind === "user-input.resolved") {
    return "message-circle";
  }
  if (entry?.iconName) return entry.iconName;
  if (entry?.requestKind === "command") return "terminal";
  if (entry?.requestKind === "file-read") return "eye";
  if (entry?.requestKind === "file-change") return "square-pen";
  const itemType = normalizeItemType(entry?.itemType);
  if (itemType === "command_execution" || stringValue(entry?.command).trim()) return "terminal";
  if (itemType === "file_change" || changedFilePaths(entry?.changedFiles).length > 0) return "square-pen";
  if (itemType === "web_search") return "globe";
  if (itemType === "image_view") return "eye";
  if (itemType === "mcp_tool_call") return "wrench";
  if (itemType === "dynamic_tool_call" || itemType === "collab_agent_tool_call") return "hammer";
  if (entry?.tone === "thinking") return "bot";
  if (entry?.tone === "info") return "check";
  return "";
}

function workEntryHeading(entry) {
  const base = entry?.toolTitle ? entry.toolTitle : entry?.label;
  return base ? capitalizePhrase(normalizeCompactToolLabel(base)) : "";
}

export function buildWorkPresentation(entry = {}) {
  const heading = workEntryHeading(entry);
  const rawPreview = workEntryPreview(entry);
  const preview = rawPreview && !valuesEquivalent(rawPreview, heading) ? rawPreview : "";
  const expandedBody = buildToolCallExpandedBody(entry);
  const failure = workEntryIndicatesToolFailure(entry);
  const warning = entry?.sourceActivityKind === "runtime.warning";
  const statusIndicator = failure
    ? "failure"
    : workEntryIndicatesToolSuccess(entry)
      ? "success"
      : workEntryIndicatesToolNeutralStatus(entry)
        ? "neutral"
        : "";
  return {
    heading,
    preview,
    iconName: workEntryIconName(entry),
    statusIndicator,
    headingTone: warning ? "warning" : failure ? "error" : "normal",
    iconTone: warning ? "warning" : failure ? "error" : "normal",
    canExpand: Boolean(expandedBody),
    expandedBody,
  };
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

function pushField(fields, key, value, options = {}) {
  if (value == null || value === "") return;
  fields.push({
    key,
    label: stringValue(options.label),
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
      const line = lineNumberValue(item.line);
      return {
        id: stringValue(item.id || `${item.path || "match"}-${line || index}`),
        path: stringValue(item.path),
        line,
        displayLine: lineDisplayValue(item.line),
        text: truncateText(item.text || item.content || item.preview || "", 320),
      };
    }
    return {
      id: `match-${index + 1}`,
      path: "",
      line: "",
      displayLine: "",
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
  const previewContent = firstString(data.content_preview, data.preview);
  const summaryContent = firstString(data.summary, data.message);
  const preview = previewContent || summaryContent;
  const previewKind = previewContent ? "preview" : summaryContent ? "summary" : "";
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
    if (fields.some((field) => field.key === key)) continue;
    pushField(fields, key, value);
  }

  if (item?.error) {
    sections.push({
      kind: "error",
      title: "",
      content: truncateText(item.error),
    });
  }
  if (preview) {
    sections.push({
      kind: previewKind,
      title: "",
      content: truncateText(preview),
    });
  }
  if (matches.length > 0) {
    sections.push({
      kind: "matches",
      title: "",
      items: matches,
    });
  }
  if (files.length > 0) {
    sections.push({
      kind: "files",
      title: "",
      items: files,
    });
  }
  if (stdout) {
    sections.push({
      kind: "stdout",
      title: "",
      content: truncateText(stdout),
    });
  }
  if (stderr) {
    sections.push({
      kind: "stderr",
      title: "",
      content: truncateText(stderr),
    });
  }
  if (diff) {
    sections.push({
      kind: "diff",
      title: "",
      content: truncateText(diff),
    });
  }
  if (Array.isArray(changed?.files) && changed.files.length > 0) {
    sections.push({
      kind: "changed_files",
      title: "",
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

export function normalizeWorkEntry(item, options = {}) {
  const args = publicArgs(item?.arguments || {});
  const toolName = stringValue(item?.toolName || item?.tool_name);
  const toolPresentation = resolveToolPresentation(toolName, options.toolCatalog || {});
  const status = stringValue(item?.status || "running");
  const changed = summarizeChangedFiles([item], { toolCatalog: options.toolCatalog || {} });
  const data = item?.data && typeof item.data === "object" ? item.data : {};
  const requestKind =
    normalizeRequestKind(item?.requestKind || item?.request_kind || data.requestKind || data.request_kind) ||
    normalizeRequestKind(item?.permissionCategory || item?.permission_category) ||
    permissionCategoryToRequestKind(toolPresentation.permissionCategory);
  const command =
    firstString(item?.command, item?.rawCommand ? "" : "", data.command) ||
    commandPreviewFor(args, toolPresentation);
  const rawCommand = firstString(item?.rawCommand, item?.raw_command, data.rawCommand, data.raw_command);
  const detail = firstString(item?.detail, data.detail) || detailTextFor(item);
  const itemType = normalizeItemType(item?.itemType || item?.item_type || data.itemType || data.item_type);
  const toolLifecycleStatus = normalizeLifecycleStatus(
    item?.toolLifecycleStatus ||
      item?.tool_lifecycle_status ||
      data.toolLifecycleStatus ||
      data.tool_lifecycle_status ||
      (status === "success" ? "completed" : ""),
  );
  const toolData = item?.toolData !== undefined
    ? item.toolData
    : item?.tool_data !== undefined
      ? item.tool_data
      : data.toolData !== undefined
        ? data.toolData
        : data.tool_data !== undefined
          ? data.tool_data
          : itemType === "mcp_tool_call" && data.item !== undefined
            ? data.item
            : undefined;
  const workEntry = {
    label: stringValue(
      item?.label ||
        item?.tool_label ||
        item?.toolTitle ||
        item?.tool_title ||
        toolPresentation.label ||
        toolName,
    ),
    detail,
    command,
    rawCommand,
    changedFiles: changed.files,
    tone: status === "error" ? "error" : "tool",
    toolTitle: firstString(item?.toolTitle, item?.tool_title, data.toolTitle, data.tool_title),
    toolData,
    itemType,
    requestKind,
    toolLifecycleStatus,
    iconName: toolPresentation.declared ? toolPresentation.iconKey : "",
    sourceActivityKind: firstString(
      item?.sourceActivityKind,
      item?.source_activity_kind,
      data.sourceActivityKind,
      data.source_activity_kind,
    ),
    status,
  };
  return {
    id: stringValue(item?.id || item?.call_id || toolName || "work"),
    kind: T3_ROW_KINDS.WORK,
    turnId: stringValue(item?.turnId || item?.turn_id),
    stepId: stringValue(item?.stepId || item?.step_id),
    stepIndex: numberValue(item?.stepIndex || item?.step_index),
    createdAt: timestampValue(item?.createdAt, item?.created_at, item?.startedAt, item?.started_at),
    completedAt: timestampValue(item?.completedAt, item?.completed_at, item?.finishedAt, item?.finished_at),
    toolName,
    label: workEntry.label,
    status,
    tone: toneForWork(item, status),
    requestKind,
    command,
    rawCommand,
    commandPreview: command || commandPreviewFor(args, toolPresentation),
    args,
    detail,
    detailModel: buildToolDetailModel(item, args, changed),
    changedFiles: changed.files,
    additions: changed.additions,
    deletions: changed.deletions,
    toolTitle: workEntry.toolTitle,
    toolData,
    itemType,
    toolLifecycleStatus,
    sourceActivityKind: workEntry.sourceActivityKind,
    presentation: buildWorkPresentation(workEntry),
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

function reasoningRow(item) {
  const content = stringValue(item?.content);
  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  return {
    id: stringValue(item?.id || `reasoning-${item?.turnId || item?.turn_id || "row"}`),
    kind: "reasoning",
    turnId: stringValue(item?.turnId || item?.turn_id),
    stepId: stringValue(item?.stepId || item?.step_id),
    stepIndex: numberValue(item?.stepIndex || item?.step_index),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    completedAt: timestampValue(item?.completedAt, item?.completed_at),
    label: stringValue(item?.label),
    content,
    wordCount,
    streaming: Boolean(item?.streaming),
    rawItem: item || {},
  };
}

function contextSummaryRow(item, placement = "fold_body") {
  return {
    id: stringValue(item?.id || `context-${item?.turnId || item?.turn_id || "row"}`),
    kind: T3_ROW_KINDS.CONTEXT_SUMMARY,
    turnId: stringValue(item?.turnId || item?.turn_id),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    placement,
    tone: "context",
    label: stringValue(item?.label),
    content: stringValue(item?.content || item?.summary),
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
  const commandName = stringValue(item?.commandName || item?.command_name);
  return {
    id: stringValue(item?.id || `command-${commandName}-${item?.turnId || item?.turn_id || "row"}`),
    kind: T3_ROW_KINDS.COMMAND_RESULT,
    turnId: stringValue(item?.turnId || item?.turn_id),
    createdAt: timestampValue(item?.createdAt, item?.created_at),
    commandName,
    label: stringValue(item?.label || (commandName ? `/${commandName}` : "")),
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
    title: stringValue(finding?.title || finding?.message),
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
    commandName: stringValue(item?.commandName || item?.command_name),
    label: stringValue(item?.label),
    findings,
    residualRisks,
  };
}

function workingRow({ activeTurnId, idSuffix = "active", createdAt = "" } = {}) {
  return {
    id: `working-${activeTurnId || idSuffix || "active"}`,
    kind: T3_ROW_KINDS.WORKING,
    turnId: stringValue(activeTurnId),
    createdAt: timestampValue(createdAt),
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

function experienceItemText(item) {
  if (item == null) return "";
  if (typeof item !== "object") return stringValue(item);
  const parts = [];
  for (const key of ["kind", "path", "command", "message", "reason"]) {
    const value = stringValue(item?.[key]).trim();
    if (value && !parts.includes(value)) parts.push(value);
  }
  return parts.join(" ");
}

function experienceListText(items) {
  if (!Array.isArray(items)) return "";
  return items.map(experienceItemText).filter(Boolean).join(", ");
}

function turnExperienceSummaryRow(turnExperience) {
  if (!turnExperience || typeof turnExperience !== "object") return null;
  const completed = experienceListText(turnExperience.completed);
  const unverified = experienceListText(turnExperience.unverified);
  const nextSteps = experienceListText(turnExperience.next_steps || turnExperience.nextSteps);
  const parts = [];
  if (completed) parts.push(`Done: ${completed}`);
  if (unverified) parts.push(`Unverified: ${unverified}`);
  if (nextSteps) parts.push(`Next: ${nextSteps}`);
  if (parts.length === 0) return null;
  return {
    id: "turn-experience-summary",
    kind: T3_ROW_KINDS.SYSTEM_NOTICE,
    tone: unverified || turnExperience.status === "blocked" ? "warning" : "context",
    content: parts.join(" · "),
    rawItem: turnExperience,
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

function activityRowForItem(item, context = {}) {
  if (!item) return null;
  if (item.kind === "tool") return normalizeWorkEntry(item, context);
  if (item.kind === "interaction_requested" || item.kind === "interaction_resolved") {
    return interactionRow(item);
  }
  if (item.kind === "reasoning") return item.streaming ? null : reasoningRow(item);
  if (item.kind === "compact") return contextSummaryRow(item);
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

function turnActivityEntries(group, context = {}) {
  const entries = [];
  function pushActivity(item) {
    const row = activityRowForItem(item, context);
    if (row) entries.push(row);
  }
  for (const item of (group?.leadingSystemItems || []).concat(group?.systemItems || [])) {
    if (item?.kind === "compact") pushActivity(item);
  }
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) {
      pushActivity(item);
    }
  }
  for (const item of group?.trailingTurnItems || []) {
    if (
      item?.kind === "tool" ||
      item?.kind === "compact" ||
      item?.kind === "interaction_requested" ||
      item?.kind === "interaction_resolved"
    ) {
      pushActivity(item);
    }
  }
  for (const item of group?.detachedItems || []) {
    if (
      item?.kind === "tool" ||
      item?.kind === "compact" ||
      item?.kind === "interaction_requested" ||
      item?.kind === "interaction_resolved"
    ) {
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

function rowForOpenPlacement(row, context) {
  if (context?.openPlacement && row?.kind === T3_ROW_KINDS.CONTEXT_SUMMARY) {
    return { ...row, kind: T3_ROW_KINDS.SYSTEM_NOTICE, placement: "active_turn_boundary" };
  }
  return row;
}

function orderedOpenRowsForTurn(group, context = {}) {
  const rows = [];
  for (const item of (group?.leadingSystemItems || []).concat(group?.systemItems || [])) {
    if (item?.kind !== "compact") continue;
    const row = activityRowForItem(item, context);
    if (row) rows.push(rowForOpenPlacement(row, context));
  }
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) {
      const row = activityRowForItem(item, context);
      if (row) rows.push(rowForOpenPlacement(row, context));
    }
    if (step?.assistantItem) {
      rows.push(messageRow(step.assistantItem, "assistant"));
    }
  }
  for (const item of (group?.trailingTurnItems || []).concat(group?.detachedItems || [])) {
    if (
      item?.kind === "tool" ||
      item?.kind === "compact" ||
      item?.kind === "interaction_requested" ||
      item?.kind === "interaction_resolved"
    ) {
      const row = activityRowForItem(item, context);
      if (row) rows.push(rowForOpenPlacement(row, context));
    }
  }
  return rows;
}

function terminalAssistantItemForTurn(group) {
  for (let index = (group?.steps || []).length - 1; index >= 0; index -= 1) {
    const item = group.steps[index]?.assistantItem;
    if (item) return item;
  }
  return null;
}

function stepOrderValue(step, fallback) {
  const value = numberValue(step?.stepIndex || step?.step_index, NaN);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function terminalAssistantStepOrder(group) {
  const terminalAssistantItem = terminalAssistantItemForTurn(group);
  if (!terminalAssistantItem) return NaN;
  const terminalId = stringValue(terminalAssistantItem?.id);
  const steps = group?.steps || [];
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const assistantItem = steps[index]?.assistantItem;
    if (!assistantItem) continue;
    const assistantId = stringValue(assistantItem?.id);
    if ((terminalId && assistantId === terminalId) || assistantItem === terminalAssistantItem) {
      return stepOrderValue(steps[index], index + 1);
    }
  }
  return NaN;
}

function foldEntriesForTurn(group, context = {}) {
  const terminalAssistantItem = terminalAssistantItemForTurn(group);
  return orderedOpenRowsForTurn(group, context).filter((row) => {
    if (row.kind !== T3_ROW_KINDS.MESSAGE || row.role !== "assistant") return true;
    return row.id !== stringValue(terminalAssistantItem?.id);
  });
}

function hasInterruptedWork(entries) {
  return entries.some((entry) => entry.tone === "interrupted" || entry.tone === "discarded");
}

function isErrorWorkEntry(entry) {
  return entry?.kind === T3_ROW_KINDS.WORK && (entry.status === "error" || entry.tone === "error");
}

function hasTerminalErrorWork(group, workEntries, context = {}) {
  if (!workEntries.some(isErrorWorkEntry)) return false;
  const terminalOrder = terminalAssistantStepOrder(group);
  if (!Number.isFinite(terminalOrder)) return true;

  let stepErrorCount = 0;
  const steps = group?.steps || [];
  for (let index = 0; index < steps.length; index += 1) {
    const stepOrder = stepOrderValue(steps[index], index + 1);
    for (const item of steps[index]?.activityItems || []) {
      const row = activityRowForItem(item, context);
      if (!isErrorWorkEntry(row)) continue;
      stepErrorCount += 1;
      if (stepOrder >= terminalOrder) return true;
    }
  }

  return workEntries.filter(isErrorWorkEntry).length > stepErrorCount;
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

export function isTurnFoldedByDefault(group, context = {}) {
  const entries = turnActivityEntries(group, context);
  const foldEntries = foldEntriesForTurn(group, context);
  const workEntries = entries.filter((entry) => entry.kind === T3_ROW_KINDS.WORK);
  if (foldEntries.length === 0) return false;
  if (group?.turnId && group.turnId === context.activeTurnId && context.currentStatus === "running") {
    return false;
  }
  if (hasInterruptedWork(workEntries)) return false;
  if (workEntries.some((entry) => entry.status === "running" || entry.tone === "running")) return false;
  if (hasTerminalErrorWork(group, workEntries, context)) return false;
  return assistantRowsForTurn(group).length > 0;
}

function pushLooseItem(push, item, context = {}) {
  if (!item) return;
  if (item.kind === "assistant") push(messageRow(item, "assistant"));
  else if (item.kind === "user") push(messageRow(item, "user"));
  else {
    const row = activityRowForItem(item, context);
    push(row || systemNoticeRow(item));
  }
}

function diffSummaryRow(group, context = {}) {
  const changed = summarizeChangedFiles(allTurnItems(group), { toolCatalog: context.toolCatalog || {} });
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
  turnExperience = null,
  toolCatalog = {},
} = {}) {
  const rows = [];
  const context = { currentStatus, activeTurnId, toolCatalog };
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
      if (item?.kind === "compact") continue;
      pushLooseItem(pushRow, item, context);
    }
    for (const item of group?.systemItems || []) {
      if (item?.kind === "compact") continue;
      pushLooseItem(pushRow, item, context);
    }

    const entries = turnActivityEntries(group, context);
    const assistantRows = assistantRowsForTurn(group);
    const shouldFold = isTurnFoldedByDefault(group, context);
    const foldEntries = shouldFold ? foldEntriesForTurn(group, context) : [];
    if (entries.length > 0 || foldEntries.length > 0) {
      if (shouldFold) {
        pushRow({
          id: `turn-fold-${group.turnId || rows.length}`,
          kind: T3_ROW_KINDS.TURN_FOLD,
          turnId: stringValue(group.turnId),
          createdAt: turnStartTimestamp(group, entries),
          completedAt: turnEndTimestamp(group, entries),
          interrupted: hasInterruptedWork(entries),
          label: stringValue(group?.label),
          workCount: entries.filter((entry) => entry.kind === T3_ROW_KINDS.WORK).length,
          reasoningCount: entries.filter((entry) => entry.kind === "reasoning").length,
          entryCount: foldEntries.length,
          defaultOpen: false,
          entries: foldEntries,
        });
      } else {
        for (const row of orderedOpenRowsForTurn(group, { ...context, openPlacement: true })) pushRow(row);
      }
    }

    const changedRow = diffSummaryRow(group, context);
    if (changedRow) pushRow(changedRow);

    if (entries.length === 0 || shouldFold) {
      const terminalAssistantItem = shouldFold ? terminalAssistantItemForTurn(group) : null;
      for (const row of assistantRows) {
        if (terminalAssistantItem && row.id !== stringValue(terminalAssistantItem.id)) continue;
        pushRow(row);
      }
    }

    for (const item of (group?.trailingTurnItems || []).concat(group?.detachedItems || [])) {
      if (item?.kind !== "tool" && item?.kind !== "interaction_requested" && item?.kind !== "interaction_resolved") {
        if (item?.kind === "compact") continue;
        pushLooseItem(pushRow, item, context);
      }
    }
    for (const item of group?.sessionFallbackItems || []) pushLooseItem(pushRow, item, context);
  }

  if (currentInteraction) {
    pushRow(
      interactionRow(currentInteraction, {
        id: currentInteraction.interactionId || currentInteraction.interaction_id,
        kind: currentInteraction.kind,
        label:
          currentInteraction.toolName ||
          currentInteraction.tool_name ||
          currentInteraction.question ||
          currentInteraction.kind,
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

  pushRow(turnExperienceSummaryRow(turnExperience));

  const hasActiveTurnRow = rows.some(
    (row) =>
      row.turnId === activeTurnId ||
      (row.kind === T3_ROW_KINDS.TURN_FOLD &&
        Array.isArray(row.entries) &&
        row.entries.some((entry) => entry.turnId === activeTurnId)),
  );
  if (currentStatus === "running" && thinkingActive && (activeTurnId || hasActiveTurnRow)) {
    const activeCreatedAt = minTimestamp(
      rows
        .filter((row) => row.turnId === activeTurnId)
        .map((row) => row.createdAt),
    );
    pushRow(workingRow({ activeTurnId, idSuffix: rows.length, createdAt: activeCreatedAt }));
  }

  if (currentStatus === "running" && rows.length === 0) {
    pushRow({
      id: "working",
      kind: T3_ROW_KINDS.WORKING,
      createdAt: "",
    });
  }

  return rows;
}
