import assert from "node:assert/strict";

import {
  activateSurface,
  closeAllSurfaces,
  closeOtherSurfaces,
  closeSurface,
  closeSurfacesToRight,
  createWorkbenchState,
  openFileSurface,
  openPreviewSurface,
  openSurface,
  openTerminalSurface,
  splitTerminalSurfaceForWorkbench,
  activateTerminalPaneForWorkbench,
  closeTerminalPaneForWorkbench,
} from "../src/workbench/surfaces.js";

function surfaceIds(state) {
  return state.workbench
    ? state.workbench.rightPanel.surfaces.map((surface) => surface.id)
    : state.rightPanel.surfaces.map((surface) => surface.id);
}

function rightPanel(state) {
  return state.workbench ? state.workbench.rightPanel : state.rightPanel;
}

export function runRightPanelStoreParityTests() {
  let state = createWorkbenchState();

  state = openSurface(state, { placement: "right", kind: "files", sessionId: "thread-a" });
  state = openSurface(state, { placement: "right", kind: "files", sessionId: "thread-a" });
  assert.deepEqual(surfaceIds(state), ["right:files"]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:files");
  assert.equal(rightPanel(state).open, true);

  state = openFileSurface(state, { sessionId: "thread-a", filePath: "src/main.c", revealLine: 12 });
  assert.deepEqual(surfaceIds(state), ["right:file:src/main.c"]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:file:src/main.c");
  assert.equal(rightPanel(state).surfaces[0].revealLine, 12);
  assert.equal(rightPanel(state).surfaces[0].revealRequestId, 1);

  state = openFileSurface(state, { sessionId: "thread-a", filePath: "src/main.c", revealLine: 24 });
  assert.deepEqual(surfaceIds(state), ["right:file:src/main.c"]);
  assert.equal(rightPanel(state).surfaces[0].revealLine, 24);
  assert.equal(rightPanel(state).surfaces[0].revealRequestId, 2);

  state = openPreviewSurface(state, { sessionId: "thread-a", previewId: "preview-a" });
  state = openPreviewSurface(state, { sessionId: "thread-a", previewId: "preview-b" });
  assert.deepEqual(surfaceIds(state), [
    "right:file:src/main.c",
    "right:preview:preview-a",
    "right:preview:preview-b",
  ]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:preview:preview-b");

  state = openTerminalSurface(state, { sessionId: "thread-a", terminalId: "term-1" });
  state = openTerminalSurface(state, { sessionId: "thread-a", terminalId: "term-2" });
  assert.deepEqual(surfaceIds(state).slice(-2), ["right:terminal:term-1", "right:terminal:term-2"]);
  assert.deepEqual(rightPanel(state).surfaces.at(-1), {
    id: "right:terminal:term-2",
    placement: "right",
    kind: "terminal",
    title: "Terminal",
    resourceId: "term-2",
    filePath: "",
    terminalId: "term-2",
    revealLine: null,
    revealRequestId: 0,
    terminalIds: ["term-2"],
    activeTerminalId: "term-2",
  });

  state = splitTerminalSurfaceForWorkbench(state, {
    sessionId: "thread-a",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-3",
    splitDirection: "vertical",
  });
  const splitSurface = rightPanel(state).surfaces.find((surface) => surface.id === "right:terminal:term-1");
  assert.deepEqual(splitSurface.terminalIds, ["term-1", "term-3"]);
  assert.equal(splitSurface.activeTerminalId, "term-3");
  assert.equal(splitSurface.splitDirection, "vertical");

  state = activateTerminalPaneForWorkbench(state, {
    sessionId: "thread-a",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.equal(
    rightPanel(state).surfaces.find((surface) => surface.id === "right:terminal:term-1").activeTerminalId,
    "term-1",
  );

  state = closeTerminalPaneForWorkbench(state, {
    sessionId: "thread-a",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.deepEqual(
    rightPanel(state).surfaces.find((surface) => surface.id === "right:terminal:term-1").terminalIds,
    ["term-3"],
  );

  state = closeTerminalPaneForWorkbench(state, {
    sessionId: "thread-a",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-3",
  });
  assert.equal(surfaceIds(state).includes("right:terminal:term-1"), false);
  assert.equal(rightPanel(state).open, true);

  state = activateSurface(state, { placement: "right", sessionId: "thread-a", surfaceId: "right:file:src/main.c" });
  state = closeOtherSurfaces(state, { placement: "right", sessionId: "thread-a", surfaceId: "right:file:src/main.c" });
  assert.deepEqual(surfaceIds(state), ["right:file:src/main.c"]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:file:src/main.c");

  state = closeSurface(state, {
    placement: "right",
    sessionId: "thread-a",
    surfaceId: "right:file:src/main.c",
    kind: "file",
    resourceId: "src/main.c",
  });
  assert.deepEqual(surfaceIds(state), []);
  assert.equal(rightPanel(state).activeSurfaceId, null);
  assert.equal(rightPanel(state).open, false);

  state = openSurface(state, { placement: "right", sessionId: "thread-a", kind: "diff", resourceId: "current" });
  state = openSurface(state, { placement: "right", sessionId: "thread-a", kind: "plan" });
  state = openSurface(state, { placement: "right", sessionId: "thread-a", kind: "source_control" });
  state = closeSurfacesToRight(state, { placement: "right", sessionId: "thread-a", surfaceId: "right:diff:current" });
  assert.deepEqual(surfaceIds(state), ["right:diff:current"]);
  assert.equal(rightPanel(state).activeSurfaceId, "right:diff:current");

  state = closeAllSurfaces(state, { placement: "right", sessionId: "thread-a" });
  assert.equal(rightPanel(state).open, false);
  assert.deepEqual(surfaceIds(state), []);
}
