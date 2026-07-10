import assert from "node:assert/strict";

import {
  createDiffSurfaceState,
  diffSummaryFromTimelineItems,
  focusDiffFile,
  parseUnifiedDiffFiles,
} from "../src/session-runtime/diff-model.js";

export function runDiffModelTests() {
  const diff = [
    "--- a/src/demo.c",
    "+++ b/src/demo.c",
    "@@ -1,2 +1,2 @@",
    "-old",
    "+new",
    " context",
    "--- a/README.md",
    "+++ b/README.md",
    "@@ -1 +1,2 @@",
    "-hello",
    "+hello",
    "+world",
    "",
  ].join("\n");

  const files = parseUnifiedDiffFiles(diff);
  assert.equal(files.length, 2);
  assert.equal(files[0].path, "src/demo.c");
  assert.equal(files[0].additions, 1);
  assert.equal(files[0].deletions, 1);
  assert.equal(files[1].path, "README.md");
  assert.equal(files[1].additions, 2);
  assert.equal(files[1].deletions, 1);

  const surface = createDiffSurfaceState({
    title: "Git Diff",
    diff,
    source: "command",
    turnId: "turn-1",
  });
  assert.equal(surface.title, "Git Diff");
  assert.equal(surface.files.length, 2);
  assert.equal(surface.focusedFilePath, "src/demo.c");
  assert.equal(surface.additions, 3);
  assert.equal(surface.deletions, 2);
  assert.equal(surface.focusedDiff.includes("src/demo.c"), true);
  assert.equal(surface.focusedDiff.includes("README.md"), false);

  const focused = focusDiffFile(surface, "README.md");
  assert.equal(focused.focusedFilePath, "README.md");
  assert.equal(focused.focusedDiff.includes("README.md"), true);

  const fallbackSurface = createDiffSurfaceState({
    diff,
    chrome: { defaultTitle: "Patch" },
  });
  assert.equal(fallbackSurface.title, "Patch");

  const summary = diffSummaryFromTimelineItems([
    {
      id: "cmd-diff",
      kind: "command_result",
      commandName: "diff",
      data: { diff },
    },
    {
      id: "write-1",
      kind: "tool",
      toolName: "write_file",
      arguments: { path: "src/new.c" },
      data: { diff_preview: "--- /dev/null\n+++ b/src/new.c\n@@ -0,0 +1 @@\n+new\n" },
    },
  ]);
  assert.equal(summary.files.length, 3);
  assert.deepEqual(summary.files.map((file) => file.path), ["src/demo.c", "README.md", "src/new.c"]);
  assert.equal(summary.additions, 4);
  assert.equal(summary.deletions, 2);

  const rawSurface = createDiffSurfaceState({
    title: "Raw",
    diff: "not a unified diff",
  });
  assert.equal(rawSurface.files.length, 0);
  assert.equal(rawSurface.focusedDiff, "not a unified diff");
}
