import assert from "node:assert/strict";

import {
  BOTTOM_DRAWER_SURFACES,
  RIGHT_PANEL_SURFACES,
  activateSurface,
  closeSurface,
  createWorkbenchState,
  openSurface,
  reduceWorkbenchState,
} from "../src/workbench/surfaces.js";

export function runWorkbenchStateTests() {
  assert.equal(RIGHT_PANEL_SURFACES.includes("tasks"), true);
  assert.equal(RIGHT_PANEL_SURFACES.includes("preview"), true);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("run_output"), true);

  const initial = createWorkbenchState();
  assert.equal(initial.rightPanel.open, true);
  assert.equal(initial.rightPanel.activeKind, "tasks");
  assert.equal(initial.bottomDrawer.open, false);

  const withPreview = openSurface(initial, {
    sessionId: "sess-1",
    placement: "right",
    kind: "preview",
    title: "README.md",
    resourceId: "README.md",
  });
  assert.notEqual(withPreview, initial);
  assert.equal(withPreview.rightPanel.open, true);
  assert.equal(withPreview.rightPanel.activeKind, "preview");
  assert.equal(withPreview.surfacesBySession["sess-1"].right.length, 1);
  assert.equal(withPreview.surfacesBySession["sess-1"].right[0].resourceId, "README.md");

  const withRunOutput = openSurface(withPreview, {
    sessionId: "sess-1",
    placement: "bottom",
    kind: "run_output",
    title: "Build Output",
  });
  assert.equal(withRunOutput.bottomDrawer.open, true);
  assert.equal(withRunOutput.bottomDrawer.activeKind, "run_output");
  assert.equal(withRunOutput.surfacesBySession["sess-1"].bottom[0].kind, "run_output");

  const activated = activateSurface(withRunOutput, {
    placement: "right",
    kind: "tasks",
  });
  assert.equal(activated.rightPanel.activeKind, "tasks");

  const closed = closeSurface(withRunOutput, {
    sessionId: "sess-1",
    placement: "right",
    kind: "preview",
    resourceId: "README.md",
  });
  assert.equal(closed.surfacesBySession["sess-1"].right.length, 0);
  assert.equal(closed.rightPanel.activeKind, "tasks");

  const reduced = reduceWorkbenchState(initial, {
    type: "workbench_surface_opened",
    sessionId: "sess-2",
    placement: "right",
    kind: "runtime",
    title: "Runtime",
  });
  assert.equal(reduced.rightPanel.activeKind, "runtime");
  assert.equal(reduced.surfacesBySession["sess-2"].right[0].kind, "runtime");
}
