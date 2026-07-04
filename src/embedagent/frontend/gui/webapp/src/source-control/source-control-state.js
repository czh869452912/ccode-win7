function read(input, snake, camel, fallback = "") {
  if (!input || typeof input !== "object") return fallback;
  if (Object.prototype.hasOwnProperty.call(input, snake)) return input[snake];
  if (Object.prototype.hasOwnProperty.call(input, camel)) return input[camel];
  return fallback;
}

function has(input, snake, camel) {
  if (!input || typeof input !== "object") return false;
  return (
    Object.prototype.hasOwnProperty.call(input, snake) ||
    Object.prototype.hasOwnProperty.call(input, camel)
  );
}

function asBoolean(value, fallback = false) {
  if (value == null || value === "") return fallback;
  if (value === true || value === false) return value;
  const text = String(value).toLowerCase();
  if (text === "true" || text === "1" || text === "yes") return true;
  if (text === "false" || text === "0" || text === "no") return false;
  return fallback;
}

function asNumber(value, fallback = 0) {
  if (value == null || value === "") return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function asText(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeGroup(value, status = "") {
  const group = asText(value).toLowerCase();
  if (group === "staged" || group === "unstaged" || group === "untracked" || group === "conflicted") {
    return group;
  }
  const normalizedStatus = asText(status).toLowerCase();
  if (normalizedStatus === "untracked") return "untracked";
  if (normalizedStatus === "conflicted") return "conflicted";
  return "unstaged";
}

export function normalizeSourceControlProvider(input = {}) {
  return {
    kind: asText(input.kind || "local"),
    name: asText(input.name || ""),
    baseUrl: asText(read(input, "base_url", "baseUrl", "")),
    remoteHost: asText(read(input, "remote_host", "remoteHost", "")),
  };
}

export function normalizeSourceControlCounts(input = {}, fileCount = 0) {
  const staged = asNumber(input.staged);
  const unstaged = asNumber(input.unstaged);
  const untracked = asNumber(input.untracked);
  const conflicted = asNumber(input.conflicted);
  return {
    staged,
    unstaged,
    untracked,
    conflicted,
    total: has(input, "total", "total")
      ? asNumber(input.total)
      : staged + unstaged + untracked + conflicted || fileCount,
  };
}

export function normalizeSourceControlFile(input = {}) {
  const status = asText(input.status || "");
  const group = normalizeGroup(input.group, status);
  const path = asText(input.path || "");
  const diffScopes = asArray(read(input, "diff_scopes", "diffScopes", []))
    .map((item) => asText(item))
    .filter(Boolean);
  return {
    path,
    displayPath: asText(read(input, "display_path", "displayPath", path)),
    group,
    status,
    indexStatus: asText(read(input, "index_status", "indexStatus", "")),
    worktreeStatus: asText(read(input, "worktree_status", "worktreeStatus", "")),
    insertions: asNumber(input.insertions),
    deletions: asNumber(input.deletions),
    binary: asBoolean(input.binary),
    diffScopes:
      diffScopes.length || group === "untracked" || group === "conflicted"
        ? diffScopes
        : [group],
  };
}

export function normalizeSourceControlStatus(input = {}) {
  const files = asArray(input.files)
    .map((file) => normalizeSourceControlFile(file))
    .filter((file) => file.path);
  return {
    workspaceRoot: asText(read(input, "workspace_root", "workspaceRoot", "")),
    isRepo: asBoolean(read(input, "is_repo", "isRepo", false)),
    gitAvailable: asBoolean(read(input, "git_available", "gitAvailable", false)),
    gitExecutable: asText(read(input, "git_executable", "gitExecutable", "")),
    runtimeSource: asText(read(input, "runtime_source", "runtimeSource", "")),
    branch: asText(input.branch || ""),
    head: asText(input.head || ""),
    hasPrimaryRemote: asBoolean(read(input, "has_primary_remote", "hasPrimaryRemote", false)),
    provider: normalizeSourceControlProvider(input.provider || {}),
    isDirty: asBoolean(read(input, "is_dirty", "isDirty", files.length > 0)),
    counts: normalizeSourceControlCounts(input.counts || {}, files.length),
    files,
    updatedAt: asText(read(input, "updated_at", "updatedAt", "")),
    diagnostics: asArray(input.diagnostics).map((item) => asText(item)).filter(Boolean),
  };
}

export function groupSourceControlFiles(files = []) {
  return asArray(files).reduce(
    (groups, file) => {
      const normalized = normalizeSourceControlFile(file);
      if (!normalized.path) return groups;
      const group = normalizeGroup(normalized.group, normalized.status);
      return { ...groups, [group]: groups[group].concat(normalized) };
    },
    { staged: [], unstaged: [], untracked: [], conflicted: [] },
  );
}

export function normalizeSourceControlDiff(input = {}) {
  return {
    workspaceRoot: asText(read(input, "workspace_root", "workspaceRoot", "")),
    path: asText(input.path || ""),
    scope: asText(input.scope || ""),
    available: asBoolean(input.available),
    binary: asBoolean(input.binary),
    diff: asText(input.diff || ""),
    fileCount: asNumber(read(input, "file_count", "fileCount", 0)),
    lineCount: asNumber(read(input, "line_count", "lineCount", 0)),
    truncated: asBoolean(input.truncated),
    reason: asText(input.reason || ""),
    updatedAt: asText(read(input, "updated_at", "updatedAt", "")),
  };
}

function defaultScopeForFile(file) {
  if (!file || !file.path) return "";
  if (file.diffScopes && file.diffScopes.length) return file.diffScopes[0];
  if (file.group === "staged" || file.group === "unstaged") return file.group;
  return "";
}

function firstSelectableFile(files = []) {
  return files.find((file) => file.diffScopes && file.diffScopes.length) || files[0] || null;
}

export function createSourceControlState() {
  return {
    status: "idle",
    error: "",
    data: normalizeSourceControlStatus(),
    selectedPath: "",
    selectedScope: "",
    diffStatus: "idle",
    diffError: "",
    diff: normalizeSourceControlDiff(),
  };
}

export function reduceSourceControlState(state, action = {}) {
  const current = state || createSourceControlState();
  switch (action.type) {
    case "source_control_reset":
      return createSourceControlState();
    case "source_control_load_started":
      return { ...current, status: "loading", error: "" };
    case "source_control_load_failed":
      return { ...current, status: "error", error: asText(action.error || "") };
    case "source_control_status_loaded": {
      const data = normalizeSourceControlStatus(action.status || action.sourceControl || {});
      const existingSelection = data.files.find((file) => file.path === current.selectedPath);
      const selected = existingSelection || firstSelectableFile(data.files);
      const selectedPath = selected ? selected.path : "";
      const selectedScope =
        existingSelection && current.selectedScope
          ? current.selectedScope
          : defaultScopeForFile(selected);
      const selectionChanged =
        selectedPath !== current.selectedPath || selectedScope !== current.selectedScope;
      return {
        ...current,
        status: "ready",
        error: "",
        data,
        selectedPath,
        selectedScope,
        diffStatus: selectionChanged ? "idle" : current.diffStatus,
        diffError: selectionChanged ? "" : current.diffError,
        diff: selectionChanged
          ? normalizeSourceControlDiff({ path: selectedPath, scope: selectedScope })
          : current.diff,
      };
    }
    case "source_control_file_selected": {
      const path = asText(action.path || "");
      const file = current.data.files.find((item) => item.path === path);
      const scope = asText(action.scope || defaultScopeForFile(file));
      return {
        ...current,
        selectedPath: path,
        selectedScope: scope,
        diffStatus: path ? "idle" : current.diffStatus,
        diffError: "",
        diff: normalizeSourceControlDiff({ path, scope }),
      };
    }
    case "source_control_diff_started":
      return { ...current, diffStatus: "loading", diffError: "" };
    case "source_control_diff_failed":
      return { ...current, diffStatus: "error", diffError: asText(action.error || "") };
    case "source_control_diff_loaded":
      return {
        ...current,
        diffStatus: "ready",
        diffError: "",
        diff: normalizeSourceControlDiff(action.diff || {}),
      };
    default:
      return current;
  }
}
