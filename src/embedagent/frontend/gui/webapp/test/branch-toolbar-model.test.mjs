import assert from "node:assert/strict";

import {
  buildBranchToolbarModel,
  resolveBranchLabel,
  summarizeBranchToolbarChanges,
} from "../src/source-control/branch-toolbar-model.js";
import { normalizeSourceControlStatus } from "../src/source-control/source-control-state.js";

export function runBranchToolbarModelTests() {
  const branchToolbarChrome = {
    defaultWorkspaceLabel: "Project",
    loadingLabel: "Scanning Git",
    errorLabel: "Git check failed",
    gitUnavailableLabel: "No Git",
    notRepositoryLabel: "No repo",
    unknownRefLabel: "No ref",
    detachedPrefix: "at",
    cleanLabel: "Settled",
    changeSingular: "delta",
    changePlural: "deltas",
    conflictSingular: "collision",
    conflictPlural: "collisions",
    currentCheckoutLabel: "Checkout",
    currentCheckoutDescription: "Use the active checkout.",
    gitUnavailableReason: "No Git runtime.",
    notRepositoryReason: "Open a repository.",
    errorReasonFallback: "Git status failed.",
    readOnlyActionTitle: "Read-only action.",
    worktreeActionLabel: "Tree",
    branchActionLabel: "Ref",
    refreshLabel: "Poll",
    refreshTitle: "Poll Git status",
    metadataSeparator: " / ",
  };
  const sourceControlChrome = {
    branchToolbar: branchToolbarChrome,
    providerLabels: {
      github: "GitHub",
      fallback: "Local provider",
    },
  };

  assert.equal(
    summarizeBranchToolbarChanges(
      { staged: 0, unstaged: 0, untracked: 0, conflicted: 0 },
      branchToolbarChrome,
    ),
    "Settled",
  );
  assert.equal(
    summarizeBranchToolbarChanges(
      { staged: 2, unstaged: 3, untracked: 1, conflicted: 0 },
      branchToolbarChrome,
    ),
    "6 deltas",
  );
  assert.equal(
    summarizeBranchToolbarChanges(
      { staged: 0, unstaged: 0, untracked: 0, conflicted: 2 },
      branchToolbarChrome,
    ),
    "2 collisions",
  );

  assert.deepEqual(
    resolveBranchLabel({ branch: "main", head: "abc1234", isRepo: true }, branchToolbarChrome),
    { label: "main", tone: "branch" },
  );
  assert.deepEqual(
    resolveBranchLabel({ branch: "", head: "abc1234567", isRepo: true }, branchToolbarChrome),
    { label: "at abc1234", tone: "detached" },
  );
  assert.deepEqual(
    resolveBranchLabel({ branch: "", head: "", isRepo: false }, branchToolbarChrome),
    { label: "No repo", tone: "disabled" },
  );

  const ready = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-1", path: "D:/work/demo", label: "demo", exists: true },
    sourceControlChrome,
    sourceControl: {
      status: "ready",
      data: normalizeSourceControlStatus({
        is_repo: true,
        git_available: true,
        branch: "feature/parser",
        head: "1234567",
        provider: { kind: "github", name: "GitHub" },
        counts: { staged: 1, unstaged: 2, untracked: 1, conflicted: 0, total: 4 },
      }),
    },
  });
  assert.equal(ready.visible, true);
  assert.equal(ready.workspaceLabel, "demo");
  assert.equal(ready.modeLabel, "Checkout");
  assert.equal(ready.modeDescription, "Use the active checkout.");
  assert.equal(ready.branchLabel, "feature/parser");
  assert.equal(ready.providerLabel, "GitHub");
  assert.equal(ready.changeCountLabel, "4 deltas");
  assert.equal(ready.branchMetaLabel, "GitHub / 4 deltas");
  assert.equal(ready.worktreeLabel, "Tree");
  assert.equal(ready.branchActionLabel, "Ref");
  assert.equal(ready.refreshLabel, "Poll");
  assert.equal(ready.refreshTitle, "Poll Git status");
  assert.equal(ready.repoState, "repo");
  assert.equal(ready.disabled, false);
  assert.equal(ready.readOnlyActionTitle, "Read-only action.");

  const unavailable = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-1", path: "D:/work/demo", label: "", exists: true },
    sourceControlChrome,
    sourceControl: {
      status: "ready",
      data: normalizeSourceControlStatus({
        is_repo: false,
        git_available: false,
      }),
    },
  });
  assert.equal(unavailable.visible, true);
  assert.equal(unavailable.workspaceLabel, "demo");
  assert.equal(unavailable.branchLabel, "No Git");
  assert.equal(unavailable.repoState, "git_unavailable");
  assert.equal(unavailable.disabled, true);
  assert.equal(unavailable.disabledReason, "No Git runtime.");

  const nonRepo = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-2", path: "D:/plain", label: "plain", exists: true },
    sourceControlChrome,
    sourceControl: {
      status: "ready",
      data: normalizeSourceControlStatus({
        is_repo: false,
        git_available: true,
      }),
    },
  });
  assert.equal(nonRepo.branchLabel, "No repo");
  assert.equal(nonRepo.repoState, "not_repo");
  assert.equal(nonRepo.disabled, true);
  assert.equal(nonRepo.disabledReason, "Open a repository.");

  const loading = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-3", path: "D:/loading", label: "loading", exists: true },
    sourceControlChrome,
    sourceControl: { status: "loading", data: normalizeSourceControlStatus() },
  });
  assert.equal(loading.branchLabel, "Scanning Git");
  assert.equal(loading.repoState, "loading");

  const error = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-4", path: "D:/error", label: "error", exists: true },
    sourceControlChrome,
    sourceControl: { status: "error", error: "", data: normalizeSourceControlStatus() },
  });
  assert.equal(error.branchLabel, "Git check failed");
  assert.equal(error.disabledReason, "Git status failed.");

  const fallbackWorkspace = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-5", path: "", label: "", exists: true },
    sourceControlChrome,
    sourceControl: { status: "ready", data: normalizeSourceControlStatus() },
  });
  assert.equal(fallbackWorkspace.workspaceLabel, "Project");

  const hidden = buildBranchToolbarModel({
    activeWorkspace: null,
    sourceControlChrome,
    sourceControl: { status: "ready", data: normalizeSourceControlStatus() },
  });
  assert.equal(hidden.visible, false);
}
