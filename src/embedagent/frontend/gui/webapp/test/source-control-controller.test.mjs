import assert from "node:assert/strict";

import { createSourceControlController } from "../src/app-runtime/source-control-controller.js";

const ENABLED_CAPABILITIES = {
  sourceControl: { enabled: true },
};

const DISABLED_CAPABILITIES = {
  sourceControl: { enabled: false },
};

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
  const controller = createSourceControlController({
    dispatch: (action) => actions.push(action),
    getAppCapabilities: () => ENABLED_CAPABILITIES,
    getSourceControlStatus: async () => {
      calls.push("status");
      return { files: [] };
    },
    refreshSourceControlStatus: async () => {
      calls.push("refresh");
      return { files: [{ path: "src/main.c" }] };
    },
    getSourceControlDiff: async (path, scope) => {
      calls.push(`diff:${path}:${scope}`);
      return { available: true, diff: "--- a/src/main.c\n+++ b/src/main.c\n" };
    },
    getSourceControlChrome: () => SOURCE_CONTROL_CHROME,
    getDiffPanelChrome: () => DIFF_PANEL_CHROME,
    hasActiveWorkspace: () => true,
  });

  await controller.loadStatus(false);
  assert.deepEqual(calls, ["status"]);
  assert.equal(actions[0].type, "source_control_load_started");
  assert.equal(actions[1].type, "source_control_status_loaded");

  await controller.loadStatus(true);
  assert.equal(calls.at(-1), "refresh");
  assert.equal(actions.at(-1).status.files[0].path, "src/main.c");

  await controller.openFile({ path: "src/main.c", diffScopes: ["staged"] });
  assert.equal(calls.at(-1), "diff:src/main.c:unstaged");
  assert.equal(actions.at(-4).type, "source_control_file_selected");
  assert.equal(actions.at(-3).type, "source_control_diff_started");
  assert.equal(actions.at(-2).type, "source_control_diff_loaded");
  assert.equal(actions.at(-1).type, "diff_surface_opened");
  assert.equal(actions.at(-1).diffSurface.title, "Patch: src/main.c");

  const scopedActions = [];
  const scopedController = createSourceControlController({
    dispatch: (action) => scopedActions.push(action),
    getAppCapabilities: () => ENABLED_CAPABILITIES,
    getSourceControlDiff: async (path, scope) => ({ available: false, reason: `${path}:${scope}` }),
    getSourceControlChrome: () => SOURCE_CONTROL_CHROME,
    getDiffPanelChrome: () => DIFF_PANEL_CHROME,
    hasActiveWorkspace: () => true,
  });
  await scopedController.openFile({ path: "src/lib.c", diffScopes: ["staged"] }, "");
  assert.equal(scopedActions.at(-1).type, "source_control_diff_failed");
  assert.equal(scopedActions.at(-1).error, "src/lib.c:staged");

  const disabledCalls = [];
  const disabledActions = [];
  const disabledController = createSourceControlController({
    dispatch: (action) => disabledActions.push(action),
    getAppCapabilities: () => DISABLED_CAPABILITIES,
    getSourceControlStatus: async () => {
      disabledCalls.push("status");
      return {};
    },
    hasActiveWorkspace: () => true,
  });

  assert.equal(await disabledController.loadStatus(), null);
  assert.deepEqual(disabledCalls, []);
  assert.deepEqual(disabledActions, [{ type: "source_control_reset" }]);
  assert.equal(await disabledController.openFile({ path: "src/main.c" }), null);
}
