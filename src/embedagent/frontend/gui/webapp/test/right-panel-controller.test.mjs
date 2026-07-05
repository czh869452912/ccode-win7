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
    },
    getAppCapabilities: () => APP_CAPABILITIES,
  });
  controller.openSurface("preview", "Launch view");

  assert.equal(actions.length, 1);
  assert.equal(actions[0].type, "workbench_surface_opened");
  assert.equal(actions[0].kind, "preview");
  assert.equal(actions[0].title, "Live View");
}
