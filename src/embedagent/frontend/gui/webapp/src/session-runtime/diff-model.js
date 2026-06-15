function textValue(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

function numberValue(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeDiffPath(line) {
  const value = textValue(line).replace(/^(---|\+\+\+)\s+/, "").trim();
  if (!value || value === "/dev/null") return "";
  const first = value.split(/\s+/)[0];
  return first.replace(/^[ab]\//, "");
}

export function parseUnifiedDiffFiles(diff) {
  const text = textValue(diff);
  if (!text.trim()) return [];
  const files = [];
  let current = null;
  for (const line of text.split(/\r?\n/)) {
    if (line.startsWith("--- ")) {
      if (current) files.push(current);
      current = {
        oldPath: normalizeDiffPath(line),
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
      current.path = normalizeDiffPath(line) || current.oldPath;
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
      oldPath: file.oldPath,
      additions: file.additions,
      deletions: file.deletions,
      diff: file.diff,
    }))
    .filter((file) => file.path);
}

function diffTextFromItem(item) {
  const data = item?.data || {};
  if (typeof data.diff === "string" && data.diff) return data.diff;
  if (typeof data.diff_preview === "string" && data.diff_preview) return data.diff_preview;
  if (typeof data.unified_diff === "string" && data.unified_diff) return data.unified_diff;
  if (typeof item?.diff === "string" && item.diff) return item.diff;
  return "";
}

function mergeFile(filesByPath, file) {
  const path = textValue(file?.path);
  if (!path) return;
  const current = filesByPath.get(path) || {
    path,
    oldPath: textValue(file?.oldPath),
    additions: 0,
    deletions: 0,
    diff: "",
  };
  filesByPath.set(path, {
    ...current,
    additions: current.additions + numberValue(file?.additions),
    deletions: current.deletions + numberValue(file?.deletions),
    diff: current.diff || textValue(file?.diff),
  });
}

export function diffSummaryFromTimelineItems(items = []) {
  const filesByPath = new Map();
  for (const item of items || []) {
    const diff = diffTextFromItem(item);
    if (!diff) continue;
    for (const file of parseUnifiedDiffFiles(diff)) {
      mergeFile(filesByPath, file);
    }
  }
  const files = Array.from(filesByPath.values());
  return {
    files,
    additions: files.reduce((sum, file) => sum + numberValue(file.additions), 0),
    deletions: files.reduce((sum, file) => sum + numberValue(file.deletions), 0),
  };
}

export function createDiffSurfaceState({
  title = "Diff",
  diff = "",
  source = "",
  turnId = "",
  filePath = "",
} = {}) {
  const rawDiff = textValue(diff);
  const files = parseUnifiedDiffFiles(rawDiff);
  const focusedFilePath =
    textValue(filePath) ||
    (files.length > 0 ? files[0].path : "");
  const focusedFile = files.find((file) => file.path === focusedFilePath) || null;
  return {
    title: textValue(title || "Diff"),
    source: textValue(source),
    turnId: textValue(turnId),
    rawDiff,
    files,
    additions: files.reduce((sum, file) => sum + numberValue(file.additions), 0),
    deletions: files.reduce((sum, file) => sum + numberValue(file.deletions), 0),
    focusedFilePath,
    focusedDiff: focusedFile ? focusedFile.diff : rawDiff,
  };
}

export function focusDiffFile(surface, filePath = "") {
  if (!surface) return surface;
  const target = textValue(filePath);
  const focusedFile = (surface.files || []).find((file) => file.path === target) || null;
  if (!focusedFile) return surface;
  return {
    ...surface,
    focusedFilePath: focusedFile.path,
    focusedDiff: focusedFile.diff || surface.rawDiff || "",
  };
}
