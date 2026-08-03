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
  surfaceDefinitionFor,
  splitTerminalSurfaceForWorkbench,
  activateTerminalPaneForWorkbench,
  closeTerminalPaneForWorkbench,
} from "../src/workbench/surfaces.js";
import {
  parsePersistedWorkbenchUiState,
  serializeWorkbenchUiState,
} from "../src/workbench/ui-state.js";

function surfaceIds(state) {
  return state.workbench
    ? state.workbench.rightPanel.surfaces.map((surface) => surface.id)
    : state.rightPanel.surfaces.map((surface) => surface.id);
}

function rightPanel(state) {
  return state.workbench ? state.workbench.rightPanel : state.rightPanel;
}

function serializedTextFor(value) {
  return JSON.stringify(value);
}

export function runRightPanelStoreParityTests() {
  const internalFileDefinition = surfaceDefinitionFor("file", {
    surfaces: {
      rightPanel: [{ id: "files", kind: "files", title: "Files" }],
    },
  });
  assert.equal(internalFileDefinition.bodyKind, "file_preview");
  assert.equal(internalFileDefinition.launcher, false);

  let state = createWorkbenchState();

  const emptyPreviewState = createWorkbenchState();
  assert.equal(openPreviewSurface(emptyPreviewState, {}), emptyPreviewState);

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
    title: "term-2",
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

  const dirtyState = createWorkbenchState();
  const serialized = serializeWorkbenchUiState({
    ...dirtyState,
    activeSessionKey: "thread-dirty",
    rightPanel: {
      ...dirtyState.rightPanel,
      surfaces: [
        {
          id: "right:file:src/main.c",
          placement: "right",
          kind: "file",
          title: "main.c",
          resourceId: "src/main.c",
          filePath: "src/main.c",
          content: "int api_key = 1;",
          rawFileContent: "secret file body",
          api_key: "sk-local",
        },
        {
          id: "right:diff:current",
          placement: "right",
          kind: "diff",
          title: "Diff",
          resourceId: "current",
          rawDiff: "--- secret diff",
          focusedDiff: "token diff",
          files: [{ path: "src/main.c", diff: "password diff" }],
        },
        {
          id: "right:terminal:term-1",
          placement: "right",
          kind: "terminal",
          title: "Terminal",
          resourceId: "term-1",
          terminalId: "term-1",
          terminalIds: ["term-1"],
          activeTerminalId: "term-1",
          output: "TOKEN=abc",
          scrollback: ["secret terminal output"],
        },
        {
          id: "right:preview:preview-a",
          placement: "right",
          kind: "preview",
          title: "Preview",
          resourceId: "preview-a",
          previewSnapshot: { html: "<main>raw html</main>", body: "secret preview body" },
        },
        {
          id: "right:diagnostics",
          placement: "right",
          kind: "diagnostics",
          title: "Diagnostics",
          toolPayload: { raw: "secret tool data" },
          permissionPayload: { token: "approval-secret" },
          secret: "diagnostic secret",
        },
      ],
      activeSurfaceId: "right:diagnostics",
    },
    surfacesBySession: {},
  });
  const persistedText = serializedTextFor(serialized);
  for (const forbidden of [
    "api_key",
    "sk-local",
    "secret file body",
    "--- secret diff",
    "password diff",
    "TOKEN=abc",
    "secret terminal output",
    "raw html",
    "secret preview body",
    "secret tool data",
    "approval-secret",
    "diagnostic secret",
  ]) {
    assert.equal(persistedText.includes(forbidden), false, forbidden);
  }
  const restored = parsePersistedWorkbenchUiState(serialized);
  const restoredText = serializedTextFor(restored);
  for (const forbidden of [
    "\"rawDiff\":",
    "\"focusedDiff\":",
    "\"diffScopes\":",
    "\"output\":",
    "\"scrollback\":",
    "\"previewSnapshot\":",
    "\"toolPayload\":",
    "\"permissionPayload\":",
    "\"secret\":",
  ]) {
    assert.equal(restoredText.includes(forbidden), false);
  }
  assert.deepEqual(
    restored.surfacesBySession["thread-dirty"].right.map((surface) => surface.kind),
    ["file", "diff", "terminal", "preview", "diagnostics"],
  );
}
