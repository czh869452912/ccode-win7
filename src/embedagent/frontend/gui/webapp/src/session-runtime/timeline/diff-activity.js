import { resolveToolPresentation } from "../tool-presentation.js";
import { numberValue, stringValue } from "./activity-types.js";

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

export function normalizeChangedFilePath(pathValue) {
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

export function diffTextFromItem(item) {
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
  const args = Object.fromEntries(
    Object.entries(item?.arguments || {}).filter(([name]) => !name.startsWith("_")),
  );
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
  if (!Array.isArray(source)) return null;
  return source.map(normalizeChangedFileEntry).filter(Boolean);
}

export function summarizeChangedFiles(items = [], options = {}) {
  const fileMap = new Map();
  const toolCatalog = options?.toolCatalog || {};
  for (const item of items || []) {
    const declaredFiles = explicitChangedFiles(item);
    for (const file of declaredFiles || []) {
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
    if (declaredFiles !== null) continue;
    const path = changedPathFromItem(item, toolPresentation);
    const additions = numberValue(item?.data?.additions);
    const deletions = numberValue(item?.data?.deletions);
    if (path && (additions || deletions)) {
      mergeFileStats(fileMap, {
        path,
        additions,
        deletions,
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
