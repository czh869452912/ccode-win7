import assert from "node:assert/strict";

import { createWorkspaceFilesController } from "../src/app-runtime/workspace-files-controller.js";
import { workspaceFilesCapabilityEnabled } from "../src/workspace-files/workspace-files-capability.js";

const FILE_SURFACE_CAPABILITIES = {
  contributions: [{ id: "files", rendererKey: "file_reference" }],
};
const FILE_HINT_CAPABILITIES = {
  chrome: { composer: { hints: [{ id: "file", label: "@ files" }] } },
};

export async function runWorkspaceFilesControllerTests() {
  assert.equal(workspaceFilesCapabilityEnabled(FILE_SURFACE_CAPABILITIES), true);
  assert.equal(workspaceFilesCapabilityEnabled(FILE_HINT_CAPABILITIES), true);
  assert.equal(workspaceFilesCapabilityEnabled({ contributions: [] }), false);
  assert.equal(workspaceFilesCapabilityEnabled(null), false);

  const calls = [];
  const actions = [];
  const protocol = {
    loadWorkspaceTree: async (path) => {
      calls.push(path);
      return {
        items: [
          { path: "src", name: "src", kind: "dir", has_children: true },
          { path: "README.md", name: "README.md", kind: "file" },
        ],
      };
    },
  };
  const controller = createWorkspaceFilesController({
    protocol,
    dispatch: (action) => actions.push(action),
    getAppCapabilities: () => FILE_SURFACE_CAPABILITIES,
  });

  await controller.loadFileChildren(".");
  assert.deepEqual(calls, ["."]);
  assert.equal(actions[0].type, "file_tree_loaded");
  assert.equal(actions[0].nodes[0].childrenLoaded, false);

  await controller.loadFileChildren("src");
  assert.equal(calls.at(-1), "src");
  assert.equal(actions.at(-1).type, "file_children_loaded");
  assert.equal(actions.at(-1).path, "src");

  const disabledCalls = [];
  const disabledActions = [];
  const disabledController = createWorkspaceFilesController({
    protocol: {
      loadWorkspaceTree: async (path) => {
        disabledCalls.push(path);
        return { items: [] };
      },
    },
    dispatch: (action) => disabledActions.push(action),
    getAppCapabilities: () => ({ contributions: [] }),
  });
  assert.equal(await disabledController.loadFileChildren("."), null);
  assert.deepEqual(disabledCalls, []);
  await disabledController.loadFileChildren(".", { appCapabilities: FILE_HINT_CAPABILITIES });
  assert.deepEqual(disabledCalls, ["."]);
  assert.equal(disabledActions[0].type, "file_tree_loaded");
}
