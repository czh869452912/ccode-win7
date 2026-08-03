import assert from "node:assert/strict";

import { createSourceControlController } from "../src/app-runtime/source-control-controller.js";

const ENABLED_CAPABILITIES = { sourceControl: { enabled: true } };
const DISABLED_CAPABILITIES = { sourceControl: { enabled: false } };
const SOURCE_CONTROL_CHROME = {
  statusUnavailableNotice: "Status unavailable",
  diffUnavailableNotice: "Diff unavailable",
};
const DIFF_PANEL_CHROME = {
  sourceControlTitleTemplate: "Patch: {path}",
  defaultTitle: "Diff",
};

export async function runSourceControlControllerTests() {
  const calls = [];
  const actions = [];
  const protocol = {
    getSourceControlStatus: async () => {
      calls.push("getSourceControlStatus");
      return { files: [] };
    },
    refreshSourceControlStatus: async () => {
      calls.push("refreshSourceControlStatus");
      return { files: [{ path: "src/main.c" }] };
    },
    getSourceControlDiff: async (path, scope) => {
      calls.push(["getSourceControlDiff", path, scope]);
      return { available: true, diff: "--- a/src/main.c\n+++ b/src/main.c\n" };
    },
  };
  const controller = createSourceControlController({
    protocol,
    dispatch: (action) => actions.push(action),
    getAppCapabilities: () => ENABLED_CAPABILITIES,
    getSourceControlChrome: () => SOURCE_CONTROL_CHROME,
    getDiffPanelChrome: () => DIFF_PANEL_CHROME,
    hasActiveWorkspace: () => true,
  });

  await controller.loadStatus(false);
  assert.deepEqual(calls, ["getSourceControlStatus"]);
  assert.equal(actions[0].type, "source_control_load_started");
  assert.equal(actions[1].type, "source_control_status_loaded");

  await controller.loadStatus(true);
  assert.equal(calls.at(-1), "refreshSourceControlStatus");
  assert.equal(actions.at(-1).status.files[0].path, "src/main.c");

  await controller.openFile({ path: "src/main.c", diffScopes: ["staged"] });
  assert.deepEqual(calls.at(-1), ["getSourceControlDiff", "src/main.c", "unstaged"]);
  assert.equal(actions.at(-1).type, "diff_surface_opened");
  assert.equal(actions.at(-1).diffSurface.title, "Patch: src/main.c");

  const scopedActions = [];
  const scopedController = createSourceControlController({
    protocol: {
      getSourceControlDiff: async (path, scope) => ({ available: false, reason: `${path}:${scope}` }),
    },
    dispatch: (action) => scopedActions.push(action),
    getAppCapabilities: () => ENABLED_CAPABILITIES,
    getSourceControlChrome: () => SOURCE_CONTROL_CHROME,
    getDiffPanelChrome: () => DIFF_PANEL_CHROME,
    hasActiveWorkspace: () => true,
  });
  await scopedController.openFile({ path: "src/lib.c", diffScopes: ["staged"] }, "");
  assert.equal(scopedActions.at(-1).error, "src/lib.c:staged");

  const disabledCalls = [];
  const disabledActions = [];
  const disabledController = createSourceControlController({
    protocol: {
      getSourceControlStatus: async () => {
        disabledCalls.push("status");
        return {};
      },
    },
    dispatch: (action) => disabledActions.push(action),
    getAppCapabilities: () => DISABLED_CAPABILITIES,
    hasActiveWorkspace: () => true,
  });
  assert.equal(await disabledController.loadStatus(), null);
  assert.deepEqual(disabledCalls, []);
  assert.deepEqual(disabledActions, [{ type: "source_control_reset" }]);

  const missingProtocol = createSourceControlController({
    getAppCapabilities: () => ENABLED_CAPABILITIES,
  });
  assert.equal(await missingProtocol.loadStatus(), null);
  assert.equal(await missingProtocol.openFile({ path: "src/main.c" }), null);
}
