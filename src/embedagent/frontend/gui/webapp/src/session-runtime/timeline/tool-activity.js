import {
  commandPreviewFromToolPresentation,
  resolveToolPresentation,
} from "../tool-presentation.js";
import { ACTIVITY_ROW_KINDS, numberValue, stringValue, timestampValue } from "./activity-types.js";
import {
  diffTextFromItem,
  normalizeChangedFilePath,
  summarizeChangedFiles,
} from "./diff-activity.js";

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
  if (item?.failure?.message) return stringValue(item.failure.message).slice(0, 4000);
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
  if (status === "error" || status === "failed") return "error";
  if (status === "running") return "running";
  return "neutral";
}

export function normalizeWorkEntry(item, options = {}) {
  const args = publicArgs(item?.arguments || {});
  const toolName = stringValue(item?.toolName || item?.tool_name);
  const toolPresentation = resolveToolPresentation(toolName, options.toolCatalog || {});
  const sourceStatus = stringValue(item?.status || "running");
  const status = sourceStatus === "failed" ? "error" : sourceStatus;
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
    iconName: toolPresentation.declared && toolPresentation.iconKeyDeclared ? toolPresentation.iconKey : "",
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
    kind: ACTIVITY_ROW_KINDS.WORK,
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
    failure: item?.failure || null,
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
