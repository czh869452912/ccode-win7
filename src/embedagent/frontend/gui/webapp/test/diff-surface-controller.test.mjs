import assert from "node:assert/strict";

import { createDiffSurfaceController } from "../src/app-runtime/diff-surface-controller.js";

const SAMPLE_DIFF = [
  "--- a/src/main.c",
  "+++ b/src/main.c",
  "@@ -1 +1 @@",
  "-old",
  "+new",
  "",
].join("\n");

export function runDiffSurfaceControllerTests() {
  const actions = [];
  const controller = createDiffSurfaceController({
    dispatch: (action) => actions.push(action),
    getRuntimeState: () => ({
      timelineItems: [
        {
          turnId: "turn-1",
          data: { path: "src/main.c", diff_preview: SAMPLE_DIFF },
          arguments: {},
        },
      ],
    }),
    getDiffPanelChrome: () => ({ defaultTitle: "Patch" }),
  });

  const opened = controller.open({
    title: "Direct",
    diff: SAMPLE_DIFF,
    turnId: "turn-2",
    filePath: "src/main.c",
  });
  assert.equal(opened, true);
  assert.equal(actions.at(-1).type, "diff_surface_opened");
  assert.equal(actions.at(-1).diffSurface.title, "src/main.c");
  assert.equal(actions.at(-1).diffSurface.turnId, "turn-2");
  assert.equal(actions.at(-1).diffSurface.files[0].path, "src/main.c");

  const fromRuntime = controller.open({ turnId: "turn-1", filePath: "src/main.c" });
  assert.equal(fromRuntime, true);
  assert.equal(actions.at(-1).diffSurface.title, "src/main.c");
  assert.equal(actions.at(-1).diffSurface.rawDiff, SAMPLE_DIFF);

  const missing = controller.open({ turnId: "missing", filePath: "src/missing.c" });
  assert.equal(missing, false);
  assert.equal(actions.length, 2);
}
