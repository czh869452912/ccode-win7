import { normalizeSourceControlStatus } from "./source-control-state.js";
import { providerLabel } from "./source-control-presentation.js";

function basenameFromPath(pathValue = "") {
  const parts = String(pathValue || "").replace(/\\/g, "/").split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "";
}

function safeCounts(counts = {}) {
  return {
    staged: Number(counts.staged || 0),
    unstaged: Number(counts.unstaged || 0),
    untracked: Number(counts.untracked || 0),
    conflicted: Number(counts.conflicted || 0),
    total: Number(counts.total || 0),
  };
}

export function summarizeBranchToolbarChanges(counts = {}) {
  const safe = safeCounts(counts);
  if (safe.conflicted > 0) {
    return `${safe.conflicted} ${safe.conflicted === 1 ? "conflict" : "conflicts"}`;
  }
  const total = safe.total || safe.staged + safe.unstaged + safe.untracked + safe.conflicted;
  if (total <= 0) return "Clean";
  return `${total} ${total === 1 ? "change" : "changes"}`;
}

export function resolveBranchLabel({
  branch = "",
  head = "",
  isRepo = false,
  gitAvailable = true,
} = {}) {
  if (!gitAvailable) return { label: "Git unavailable", tone: "disabled" };
  if (!isRepo) return { label: "No repository", tone: "disabled" };
  const branchText = String(branch || "").trim();
  if (branchText) return { label: branchText, tone: "branch" };
  const headText = String(head || "").trim();
  if (headText) return { label: `detached ${headText.slice(0, 7)}`, tone: "detached" };
  return { label: "Unknown ref", tone: "muted" };
}

export function buildBranchToolbarModel({ activeWorkspace = null, sourceControl = null } = {}) {
  if (!activeWorkspace) {
    return { visible: false };
  }
  const data = normalizeSourceControlStatus(sourceControl?.data || {});
  const status = String(sourceControl?.status || "idle");
  const workspaceLabel =
    String(activeWorkspace.label || "").trim() ||
    basenameFromPath(activeWorkspace.path || "") ||
    "Workspace";
  const loading = status === "loading";
  const error = status === "error";
  const branch = loading
    ? { label: "Checking Git...", tone: "muted" }
    : error
      ? { label: "Git status unavailable", tone: "disabled" }
      : resolveBranchLabel({
          branch: data.branch,
          head: data.head,
          isRepo: data.isRepo,
          gitAvailable: data.gitAvailable,
        });
  const repoState = loading
    ? "loading"
    : error
      ? "error"
      : !data.gitAvailable
        ? "git_unavailable"
        : data.isRepo
          ? "repo"
          : "not_repo";
  const disabled = repoState !== "repo";
  const disabledReason =
    repoState === "git_unavailable"
      ? "Git is unavailable in this offline bundle or workspace."
      : repoState === "not_repo"
        ? "This workspace is not a Git repository."
        : repoState === "error"
          ? String(sourceControl?.error || "Git status is unavailable.")
          : "";
  return {
    visible: true,
    workspaceLabel,
    modeLabel: "Current checkout",
    modeDescription: "Run in the active workspace checkout.",
    branchLabel: branch.label,
    branchTone: branch.tone,
    providerLabel: providerLabel(data.provider),
    changeCountLabel: summarizeBranchToolbarChanges(data.counts),
    repoState,
    disabled,
    disabledReason,
    canRefresh: true,
  };
}
