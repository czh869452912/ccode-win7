import assert from "node:assert/strict";

import { createFilePreviewController } from "../src/app-runtime/file-preview-controller.js";

export async function runFilePreviewControllerTests() {
  const actions = [];
  const openRequests = [];
  const requests = [];
  const controller = createFilePreviewController({
    dispatch: (action) => actions.push(action),
    protocol: {
      readFile: async (path) => {
        requests.push(path);
        return { path: "src/main.c", content: "int main(void) { return 0; }\n" };
      },
    },
    getFilePreviewChrome: () => ({
      defaultFileTitle: "Document",
      unavailableMessage: "File unavailable",
    }),
    rightPanelController: {
      normalizeFileSurfacePath: (path) => String(path || "").replace(/\\/g, "/").replace(/^\/+/, ""),
      fileSurfaceTitle: (path) => path.split("/").pop() || "Document",
      openFileSurface: (request) => {
        openRequests.push(request);
        return true;
      },
    },
  });

  const loaded = await controller.openFile("\\src\\main.c", 12);

  assert.deepEqual(openRequests, [{ filePath: "src/main.c", revealLine: 12, title: "main.c" }]);
  assert.deepEqual(requests, ["src/main.c"]);
  assert.equal(loaded.path, "src/main.c");
  assert.deepEqual(actions, [
    { type: "file_preview_load_started", path: "src/main.c" },
    {
      type: "file_preview_loaded",
      path: "src/main.c",
      preview: { title: "src/main.c", content: "int main(void) { return 0; }\n" },
    },
  ]);

  const unavailableActions = [];
  const unavailableRequests = [];
  const unavailableController = createFilePreviewController({
    dispatch: (action) => unavailableActions.push(action),
    protocol: {
      readFile: async (path) => {
        unavailableRequests.push(path);
        return {};
      },
    },
    rightPanelController: {
      normalizeFileSurfacePath: () => "src/blocked.c",
      fileSurfaceTitle: () => "blocked.c",
      openFileSurface: () => false,
    },
  });
  assert.equal(await unavailableController.openFile("src/blocked.c"), null);
  assert.deepEqual(unavailableActions, []);
  assert.deepEqual(unavailableRequests, []);

  const failedActions = [];
  const failedController = createFilePreviewController({
    dispatch: (action) => failedActions.push(action),
    protocol: {
      readFile: async () => {
        throw new Error("");
      },
    },
    getFilePreviewChrome: () => ({ unavailableMessage: "Cannot open file" }),
    rightPanelController: {
      normalizeFileSurfacePath: () => "src/missing.c",
      fileSurfaceTitle: () => "missing.c",
      openFileSurface: () => true,
    },
  });
  assert.equal(await failedController.openFile("src/missing.c"), null);
  assert.deepEqual(failedActions, [
    { type: "file_preview_load_started", path: "src/missing.c" },
    { type: "file_preview_load_failed", path: "src/missing.c", error: "Cannot open file" },
  ]);

  const missingProtocol = createFilePreviewController({
    rightPanelController: { openFileSurface: () => true },
  });
  assert.equal(await missingProtocol.openFile("src/main.c"), null);
}
