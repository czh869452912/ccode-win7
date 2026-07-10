import assert from "node:assert/strict";

import {
  buildAppCapabilityModel,
  buildAppCapabilityModelFromState,
} from "../src/app-runtime/app-capability-model.js";

export function runAppCapabilityModelTests() {
  const capabilities = {
    keybindings: [{ key: "mod+k", commandId: "palette.open" }],
    commandPalette: { groups: [{ id: "session", title: "Threads" }] },
    chrome: { header: { title: "Header" }, composer: { placeholder: "Ask" } },
    terminal: { chrome: { titlePrefix: "Shell" } },
    sourceControl: { enabled: true, chrome: { title: "Source Control" } },
    preview: {
      chrome: { refreshLabel: "Refresh" },
      localServers: [{ id: "vite", label: "Vite", url: "http://localhost:5173" }],
    },
    surfaces: {
      chrome: {
        filePreview: { loadingMessage: "Loading file" },
        diffPanel: { defaultTitle: "Diff" },
      },
    },
    threadLifecycle: { actions: [{ id: "rename", label: "Rename" }] },
    emptyState: { primary: "Open a project" },
  };

  const model = buildAppCapabilityModel(capabilities);
  assert.equal(model.appCapabilities, capabilities);
  assert.equal(model.keybindings, capabilities.keybindings);
  assert.equal(model.commandPalette, capabilities.commandPalette);
  assert.equal(model.appChrome, capabilities.chrome);
  assert.equal(model.terminalChrome, capabilities.terminal.chrome);
  assert.equal(model.sourceControlCapability, capabilities.sourceControl);
  assert.equal(model.sourceControlChrome, capabilities.sourceControl.chrome);
  assert.equal(model.previewCapability, capabilities.preview);
  assert.equal(model.previewChrome, capabilities.preview.chrome);
  assert.equal(model.previewServers, capabilities.preview.localServers);
  assert.equal(model.surfaceChrome, capabilities.surfaces.chrome);
  assert.equal(model.filePreviewChrome, capabilities.surfaces.chrome.filePreview);
  assert.equal(model.diffPanelChrome, capabilities.surfaces.chrome.diffPanel);
  assert.equal(model.threadLifecycleCapabilities, capabilities.threadLifecycle);
  assert.equal(model.emptyState, capabilities.emptyState);

  const stateModel = buildAppCapabilityModelFromState({ app: { capabilities } });
  assert.equal(stateModel.appCapabilities, capabilities);
  assert.equal(stateModel.threadLifecycleCapabilities, capabilities.threadLifecycle);

  const empty = buildAppCapabilityModel(null);
  assert.deepEqual(empty.keybindings, []);
  assert.deepEqual(empty.commandPalette, {});
  assert.deepEqual(empty.appChrome, {});
  assert.deepEqual(empty.terminalChrome, {});
  assert.deepEqual(empty.sourceControlCapability, {});
  assert.deepEqual(empty.sourceControlChrome, {});
  assert.deepEqual(empty.previewCapability, {});
  assert.deepEqual(empty.previewChrome, {});
  assert.deepEqual(empty.previewServers, []);
  assert.deepEqual(empty.surfaceChrome, {});
  assert.deepEqual(empty.filePreviewChrome, {});
  assert.deepEqual(empty.diffPanelChrome, {});
  assert.deepEqual(empty.threadLifecycleCapabilities, {});
  assert.equal(empty.emptyState, null);

  const emptyStateModel = buildAppCapabilityModelFromState(null);
  assert.deepEqual(emptyStateModel.appCapabilities, {});
}
