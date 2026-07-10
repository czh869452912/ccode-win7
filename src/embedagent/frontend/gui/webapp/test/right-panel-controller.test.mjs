import assert from "node:assert/strict";

import {
  createRightPanelController,
  rightPanelSurfaceTitle,
} from "../src/app-runtime/right-panel-controller.js";

const APP_CAPABILITIES = Object.freeze({
  surfaces: {
    rightPanel: [
      {
        id: "preview",
        kind: "preview",
        title: "Live View",
        commandLabel: "Launch view",
        launcher: true,
        launcherOrder: 10,
        command: true,
      },
      {
        id: "file",
        kind: "file",
        title: "File",
        commandLabel: "",
        launcher: false,
        launcherOrder: 25,
        command: false,
      },
      {
        id: "terminal",
        kind: "terminal",
        title: "Terminal",
        commandLabel: "Open terminal",
        launcher: true,
        launcherOrder: 20,
        command: true,
      },
      {
        id: "files",
        kind: "files",
        title: "Files",
        commandLabel: "Open files",
        launcher: true,
        launcherOrder: 30,
        command: true,
      },
    ],
  },
});

const NO_PREVIEW_CAPABILITIES = Object.freeze({
  surfaces: {
    rightPanel: [
      {
        id: "file",
        kind: "file",
        title: "File",
        commandLabel: "",
        launcher: false,
        launcherOrder: 25,
        command: false,
      },
      {
        id: "terminal",
        kind: "terminal",
        title: "Terminal",
        commandLabel: "Open terminal",
        launcher: true,
        launcherOrder: 20,
        command: true,
      },
      {
        id: "files",
        kind: "files",
        title: "Files",
        commandLabel: "Open files",
        launcher: true,
        launcherOrder: 30,
        command: true,
      },
    ],
  },
});

const NO_FILE_CAPABILITIES = Object.freeze({
  surfaces: {
    rightPanel: [
      {
        id: "preview",
        kind: "preview",
        title: "Live View",
        commandLabel: "Launch view",
        launcher: true,
        launcherOrder: 10,
        command: true,
      },
      {
        id: "files",
        kind: "files",
        title: "Files",
        commandLabel: "Open files",
        launcher: true,
        launcherOrder: 30,
        command: true,
      },
    ],
  },
});

export function runRightPanelControllerTests() {
  assert.equal(
    rightPanelSurfaceTitle("preview", "Launch view", APP_CAPABILITIES),
    "Live View",
  );
  assert.equal(rightPanelSurfaceTitle("missing", "Launch view", APP_CAPABILITIES), "Launch view");

  const actions = [];
  const controller = createRightPanelController({
    dispatch: (action) => actions.push(action),
    terminalController: {
      openRightPanelSurface: () => {
        actions.push({ type: "terminal_opened" });
      },
      openSession: (terminalId) => {
        actions.push({ type: "terminal_session_opened", terminalId });
      },
    },
    getAppCapabilities: () => APP_CAPABILITIES,
  });
  controller.openSurface("preview", "Launch view");

  assert.equal(actions.length, 1);
  assert.equal(actions[0].type, "workbench_surface_opened");
  assert.equal(actions[0].kind, "preview");
  assert.equal(actions[0].title, "Live View");

  controller.openSurface("terminal", "Terminal");
  assert.equal(actions.length, 2);
  assert.equal(actions[1].type, "terminal_opened");

  controller.openSurface("file", "File");
  assert.equal(actions.length, 2);
  assert.equal(controller.canOpenPreviewSurface(), true);

  {
    const blockedActions = [];
    const blockedController = createRightPanelController({
      dispatch: (action) => blockedActions.push(action),
      terminalController: {},
      getAppCapabilities: () => NO_FILE_CAPABILITIES,
    });
    const opened = blockedController.openFileSurface({
      filePath: "src/hidden.c",
      title: "hidden.c",
      revealLine: 4,
    });
    assert.equal(opened, false);
    assert.deepEqual(blockedActions, []);
  }

  {
    const blockedActions = [];
    const blockedController = createRightPanelController({
      dispatch: (action) => blockedActions.push(action),
      terminalController: {
        openRightPanelSurface: () => {
          blockedActions.push({ type: "terminal_opened" });
        },
      },
      getAppCapabilities: () => NO_PREVIEW_CAPABILITIES,
    });
    assert.equal(blockedController.canOpenPreviewSurface(), false);
    const opened = blockedController.openPreviewSurface({
      resourceId: "http://127.0.0.1:3000",
      previewSnapshot: { url: "http://127.0.0.1:3000" },
    });
    assert.equal(opened, false);
    assert.deepEqual(blockedActions, []);
  }

  const openedFile = controller.openFileSurface({
    filePath: "src/main.c",
    title: "main.c",
    revealLine: 12,
  });
  assert.equal(openedFile, true);
  assert.deepEqual(actions.at(-1), {
    type: "workbench_surface_opened",
    placement: "right",
    kind: "file",
    title: "main.c",
    resourceId: "src/main.c",
    filePath: "src/main.c",
    revealLine: 12,
  });

  const openedPreview = controller.openPreviewSurface({
    resourceId: "http://127.0.0.1:3000",
    previewSnapshot: { url: "http://127.0.0.1:3000" },
  });
  assert.equal(openedPreview, true);
  assert.deepEqual(actions.at(-1), {
    type: "workbench_surface_opened",
    placement: "right",
    kind: "preview",
    title: "http://127.0.0.1:3000",
    resourceId: "http://127.0.0.1:3000",
    previewSnapshot: { url: "http://127.0.0.1:3000" },
  });

  controller.openFilesSurface();
  assert.equal(actions.at(-1).type, "workbench_surface_opened");
  assert.equal(actions.at(-1).kind, "files");

  controller.activateSurface({
    id: "right:terminal:term-4",
    kind: "terminal",
    activeTerminalId: "term-4",
  });
  assert.deepEqual(actions.slice(-2), [
    {
      type: "workbench_surface_activated",
      placement: "right",
      surfaceId: "right:terminal:term-4",
      kind: "terminal",
    },
    { type: "terminal_session_opened", terminalId: "term-4" },
  ]);

  controller.activateSurface({ id: "right:preview:preview-a", kind: "preview" });
  assert.deepEqual(actions.at(-1), {
    type: "workbench_surface_activated",
    placement: "right",
    surfaceId: "right:preview:preview-a",
    kind: "preview",
  });
}
