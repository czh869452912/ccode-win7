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

export function summarizeBranchToolbarChanges(counts = {}, chrome = {}) {
  const safe = safeCounts(counts);
  if (safe.conflicted > 0) {
    const label = safe.conflicted === 1 ? chrome.conflictSingular : chrome.conflictPlural;
    return `${safe.conflicted} ${label}`.trim();
  }
  const total = safe.total || safe.staged + safe.unstaged + safe.untracked + safe.conflicted;
  if (total <= 0) return chrome.cleanLabel || "";
  const label = total === 1 ? chrome.changeSingular : chrome.changePlural;
  return `${total} ${label}`.trim();
}

export function resolveBranchLabel({
  branch = "",
  head = "",
  isRepo = false,
  gitAvailable = true,
} = {}, chrome = {}) {
  if (!gitAvailable) return { label: chrome.gitUnavailableLabel || "", tone: "disabled" };
  if (!isRepo) return { label: chrome.notRepositoryLabel || "", tone: "disabled" };
  const branchText = String(branch || "").trim();
  if (branchText) return { label: branchText, tone: "branch" };
  const headText = String(head || "").trim();
  if (headText) {
    return { label: `${chrome.detachedPrefix || ""} ${headText.slice(0, 7)}`.trim(), tone: "detached" };
  }
  return { label: chrome.unknownRefLabel || "", tone: "muted" };
}

export function buildBranchToolbarModel({
  activeWorkspace = null,
  sourceControl = null,
  sourceControlChrome = {},
} = {}) {
  if (!activeWorkspace) {
    return { visible: false };
  }
  const chrome = sourceControlChrome?.branchToolbar || {};
  const data = normalizeSourceControlStatus(sourceControl?.data || {});
  const status = String(sourceControl?.status || "idle");
  const workspaceLabel =
    String(activeWorkspace.label || "").trim() ||
    basenameFromPath(activeWorkspace.path || "") ||
    chrome.defaultWorkspaceLabel ||
    "";
  const loading = status === "loading";
  const error = status === "error";
  const branch = loading
    ? { label: chrome.loadingLabel || "", tone: "muted" }
    : error
      ? { label: chrome.errorLabel || "", tone: "disabled" }
      : resolveBranchLabel({
          branch: data.branch,
          head: data.head,
          isRepo: data.isRepo,
          gitAvailable: data.gitAvailable,
        }, chrome);
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
      ? chrome.gitUnavailableReason || ""
      : repoState === "not_repo"
        ? chrome.notRepositoryReason || ""
        : repoState === "error"
          ? String(sourceControl?.error || chrome.errorReasonFallback || "")
          : "";
  const providerText = providerLabel(data.provider, sourceControlChrome);
  const changeText = summarizeBranchToolbarChanges(data.counts, chrome);
  const separator = chrome.metadataSeparator || "";
  return {
    visible: true,
    workspaceLabel,
    modeLabel: chrome.currentCheckoutLabel || "",
    modeDescription: chrome.currentCheckoutDescription || "",
    branchLabel: branch.label,
    branchTone: branch.tone,
    providerLabel: providerText,
    changeCountLabel: changeText,
    branchMetaLabel: [providerText, changeText].filter(Boolean).join(separator),
    repoState,
    disabled,
    disabledReason,
    canRefresh: true,
    readOnlyActionTitle: chrome.readOnlyActionTitle || "",
    worktreeLabel: chrome.worktreeActionLabel || "",
    branchActionLabel: chrome.branchActionLabel || "",
    refreshLabel: chrome.refreshLabel || "",
    refreshTitle: chrome.refreshTitle || "",
  };
}
