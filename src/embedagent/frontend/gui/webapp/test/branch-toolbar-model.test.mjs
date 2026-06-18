import assert from "node:assert/strict";

import {
  buildBranchToolbarModel,
  resolveBranchLabel,
  summarizeBranchToolbarChanges,
} from "../src/source-control/branch-toolbar-model.js";
import { normalizeSourceControlStatus } from "../src/source-control/source-control-state.js";

export function runBranchToolbarModelTests() {
  assert.equal(
    summarizeBranchToolbarChanges({ staged: 0, unstaged: 0, untracked: 0, conflicted: 0 }),
    "Clean",
  );
  assert.equal(
    summarizeBranchToolbarChanges({ staged: 2, unstaged: 3, untracked: 1, conflicted: 0 }),
    "6 changes",
  );
  assert.equal(
    summarizeBranchToolbarChanges({ staged: 0, unstaged: 0, untracked: 0, conflicted: 2 }),
    "2 conflicts",
  );

  assert.deepEqual(
    resolveBranchLabel({ branch: "main", head: "abc1234", isRepo: true }),
    { label: "main", tone: "branch" },
  );
  assert.deepEqual(
    resolveBranchLabel({ branch: "", head: "abc1234567", isRepo: true }),
    { label: "detached abc1234", tone: "detached" },
  );
  assert.deepEqual(
    resolveBranchLabel({ branch: "", head: "", isRepo: false }),
    { label: "No repository", tone: "disabled" },
  );

  const ready = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-1", path: "D:/work/demo", label: "demo", exists: true },
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
  assert.equal(ready.modeLabel, "Current checkout");
  assert.equal(ready.branchLabel, "feature/parser");
  assert.equal(ready.providerLabel, "GitHub");
  assert.equal(ready.changeCountLabel, "4 changes");
  assert.equal(ready.repoState, "repo");
  assert.equal(ready.disabled, false);

  const unavailable = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-1", path: "D:/work/demo", label: "", exists: true },
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
  assert.equal(unavailable.branchLabel, "Git unavailable");
  assert.equal(unavailable.repoState, "git_unavailable");
  assert.equal(unavailable.disabled, true);
  assert.equal(unavailable.disabledReason, "Git is unavailable in this offline bundle or workspace.");

  const nonRepo = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-2", path: "D:/plain", label: "plain", exists: true },
    sourceControl: {
      status: "ready",
      data: normalizeSourceControlStatus({
        is_repo: false,
        git_available: true,
      }),
    },
  });
  assert.equal(nonRepo.branchLabel, "No repository");
  assert.equal(nonRepo.repoState, "not_repo");
  assert.equal(nonRepo.disabled, true);

  const loading = buildBranchToolbarModel({
    activeWorkspace: { id: "ws-3", path: "D:/loading", label: "loading", exists: true },
    sourceControl: { status: "loading", data: normalizeSourceControlStatus() },
  });
  assert.equal(loading.branchLabel, "Checking Git...");
  assert.equal(loading.repoState, "loading");

  const hidden = buildBranchToolbarModel({
    activeWorkspace: null,
    sourceControl: { status: "ready", data: normalizeSourceControlStatus() },
  });
  assert.equal(hidden.visible, false);
}
