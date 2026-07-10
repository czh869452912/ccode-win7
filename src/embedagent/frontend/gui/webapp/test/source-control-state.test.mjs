import assert from "node:assert/strict";

import {
  createSourceControlState,
  groupSourceControlFiles,
  normalizeSourceControlDiff,
  normalizeSourceControlStatus,
  reduceSourceControlState,
} from "../src/source-control/source-control-state.js";
import {
  fileStatusLabel,
  groupLabel,
  providerLabel,
} from "../src/source-control/source-control-presentation.js";

export function runSourceControlStateTests() {
  const initial = createSourceControlState();
  assert.equal(initial.status, "idle");
  assert.equal(initial.data.gitAvailable, false);
  assert.equal(initial.selectedPath, "");

  const normalized = normalizeSourceControlStatus({
    git_available: true,
    is_repo: true,
    branch: "main",
    provider: { kind: "github", name: "GitHub", base_url: "https://github.com" },
    counts: { staged: 1, unstaged: 1, untracked: 1, conflicted: 0, total: 3 },
    files: [
      {
        path: "src/main.c",
        group: "unstaged",
        status: "modified",
        insertions: 2,
        deletions: 1,
        diff_scopes: ["unstaged"],
      },
      {
        path: "include/api.h",
        group: "staged",
        status: "added",
        insertions: 5,
        deletions: 0,
        diff_scopes: ["staged"],
      },
      {
        path: "notes.txt",
        group: "untracked",
        status: "untracked",
        insertions: 0,
        deletions: 0,
        diff_scopes: [],
      },
    ],
  });
  assert.equal(normalized.gitAvailable, true);
  assert.equal(normalized.isRepo, true);
  assert.equal(normalized.branch, "main");
  assert.equal(normalized.provider.kind, "github");
  assert.equal(normalized.counts.total, 3);
  assert.equal(normalized.files[0].path, "src/main.c");

  const grouped = groupSourceControlFiles(normalized.files);
  assert.equal(grouped.unstaged[0].path, "src/main.c");
  assert.equal(grouped.staged[0].path, "include/api.h");
  assert.equal(grouped.untracked[0].path, "notes.txt");
  assert.equal(grouped.conflicted.length, 0);

  let state = reduceSourceControlState(initial, { type: "source_control_load_started" });
  assert.equal(state.status, "loading");
  state = reduceSourceControlState(state, {
    type: "source_control_status_loaded",
    status: normalized,
  });
  assert.equal(state.status, "ready");
  assert.equal(state.selectedPath, "src/main.c");
  state = reduceSourceControlState(state, {
    type: "source_control_file_selected",
    path: "include/api.h",
    scope: "staged",
  });
  assert.equal(state.selectedPath, "include/api.h");
  assert.equal(state.selectedScope, "staged");

  const diff = normalizeSourceControlDiff({
    path: "include/api.h",
    scope: "staged",
    available: true,
    binary: false,
    diff: "diff --git a/include/api.h b/include/api.h\n",
    file_count: 1,
    line_count: 1,
    truncated: false,
    reason: "",
  });
  state = reduceSourceControlState(state, {
    type: "source_control_diff_loaded",
    diff,
  });
  assert.equal(state.diff.path, "include/api.h");
  assert.equal(state.diff.available, true);

  assert.equal(
    fileStatusLabel({ status: "modified" }, { fileStatusLabels: { modified: "~" } }),
    "~",
  );
  assert.equal(fileStatusLabel({ status: "unknown" }, { fileStatusLabels: {} }), "");
  assert.equal(providerLabel(normalized.provider), "GitHub");
  assert.equal(groupLabel("unstaged", { groupLabels: { unstaged: "Modified" } }), "Modified");
  assert.equal(groupLabel("mystery", { groupLabels: {} }), "");
  assert.equal(
    providerLabel({ kind: "local" }, { providerLabels: { local: "Workspace Git" } }),
    "Workspace Git",
  );
  assert.equal(providerLabel({ kind: "unknown" }, { providerLabels: {} }), "");
}
