import assert from "node:assert/strict";

import { createWorkspaceFilesController } from "../src/app-runtime/workspace-files-controller.js";
import { workspaceFilesCapabilityEnabled } from "../src/workspace-files/workspace-files-capability.js";

const FILE_SURFACE_CAPABILITIES = {
  surfaces: {
    right_panel: [
      { id: "files", title: "Files" },
    ],
  },
};

const FILE_HINT_CAPABILITIES = {
  chrome: {
    composer: {
      hints: [{ id: "file", label: "@ files" }],
    },
  },
};

export async function runWorkspaceFilesControllerTests() {
  assert.equal(workspaceFilesCapabilityEnabled(FILE_SURFACE_CAPABILITIES), true);
  assert.equal(workspaceFilesCapabilityEnabled(FILE_HINT_CAPABILITIES), true);
  assert.equal(workspaceFilesCapabilityEnabled({ surfaces: { right_panel: [] } }), false);
  assert.equal(workspaceFilesCapabilityEnabled(null), false);

  const calls = [];
  const actions = [];
  const controller = createWorkspaceFilesController({
    fetchJson: async (url) => {
      calls.push(url);
      return {
        items: [
          { path: "src", name: "src", kind: "dir", has_children: true },
          { path: "README.md", name: "README.md", kind: "file" },
        ],
      };
    },
    dispatch: (action) => actions.push(action),
    getAppCapabilities: () => FILE_SURFACE_CAPABILITIES,
  });

  await controller.loadFileChildren(".");
  assert.deepEqual(calls, ["/api/files/tree?path=."]);
  assert.equal(actions[0].type, "file_tree_loaded");
  assert.equal(actions[0].nodes[0].childrenLoaded, false);

  await controller.loadFileChildren("src");
  assert.deepEqual(calls.at(-1), "/api/files/tree?path=src");
  assert.deepEqual(actions.at(-1), {
    type: "file_children_loaded",
    path: "src",
    children: [
      { path: "src", name: "src", kind: "dir", has_children: true },
      { path: "README.md", name: "README.md", kind: "file" },
    ],
  });

  const disabledCalls = [];
  const disabledActions = [];
  const disabledController = createWorkspaceFilesController({
    fetchJson: async (url) => {
      disabledCalls.push(url);
      return { items: [] };
    },
    dispatch: (action) => disabledActions.push(action),
    getAppCapabilities: () => ({ surfaces: { right_panel: [] } }),
  });
  assert.equal(await disabledController.loadFileChildren("."), null);
  assert.deepEqual(disabledCalls, []);
  assert.deepEqual(disabledActions, []);

  await disabledController.loadFileChildren(".", { appCapabilities: FILE_HINT_CAPABILITIES });
  assert.deepEqual(disabledCalls, ["/api/files/tree?path=."]);
  assert.equal(disabledActions[0].type, "file_tree_loaded");
}
