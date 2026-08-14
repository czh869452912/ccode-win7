import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createWorkspaceController } from "../src/app-runtime/workspace-controller.js";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8");
}

function bootstrap(id = "ws-2", active = true) {
  return {
    schema_version: 1,
    app: { shell_version: 1, product_name: "EmbedAgent", protocol: "gui_app_shell_v1" },
    active_workspace: active
      ? { id, path: `D:/work/${id}`, label: id, exists: true }
      : null,
    workspaces: active
      ? [{ id, path: `D:/work/${id}`, label: id, exists: true }]
      : [],
    has_active_workspace: active,
    shell: {
      schema_version: 1,
      commands: [],
      surfaces: [],
      keybindings: [],
      tool_presentations: [],
      timeline_items: [],
      interactions: [],
    },
    settings: { confirm_workspace_switch: true, show_diagnostics_badge: true },
    diagnostics: {},
    last_error: "",
  };
}

export async function runWorkspaceControllerTests() {
  const calls = [];
  const actions = [];
  const protocol = {
    loadAppBootstrap: async () => {
      calls.push(["loadAppBootstrap"]);
      return bootstrap("ws-1");
    },
    openWorkspacePath: async (targetPath) => {
      calls.push(["openWorkspacePath", targetPath]);
      return bootstrap("ws-2");
    },
    activateWorkspace: async (workspaceId) => {
      calls.push(["activateWorkspace", workspaceId]);
      return bootstrap(workspaceId);
    },
    removeWorkspace: async (workspaceId) => {
      calls.push(["removeWorkspace", workspaceId]);
      return bootstrap(workspaceId, false);
    },
  };
  const controller = createWorkspaceController({
    protocol,
    dispatch: (action) => actions.push(action),
    getCurrentSessionId: () => "sess-1",
    getAppState: () => ({ hasActiveWorkspace: true, workspacePathInput: "D:/work/new" }),
    canSwitchWorkspace: () => ({ allowed: true, reason: "" }),
    loadWorkspaceData: async (sessionId, assumeWorkspace, appCapabilities) => {
      calls.push(["loadWorkspaceData", sessionId, assumeWorkspace, appCapabilities]);
    },
  });

  await controller.loadAppBootstrap();
  assert.deepEqual(calls[0], ["loadAppBootstrap"]);
  assert.equal(actions[0].type, "app_bootstrap_loaded");
  assert.equal(actions[0].bootstrap.hasActiveWorkspace, true);
  assert.deepEqual(calls[1].slice(0, 3), ["loadWorkspaceData", "", true]);

  controller.setWorkspacePath("D:/work/typed");
  assert.deepEqual(actions.at(-1), { type: "workspace_path_changed", value: "D:/work/typed" });

  await controller.openWorkspace();
  assert.deepEqual(calls.find((call) => call[0] === "openWorkspacePath"), [
    "openWorkspacePath",
    "D:/work/new",
  ]);
  assert.equal(actions.at(-1).type, "workspace_switched");

  await controller.activateWorkspace("ws-2");
  assert.deepEqual(calls.find((call) => call[0] === "activateWorkspace"), [
    "activateWorkspace",
    "ws-2",
  ]);

  await controller.removeWorkspace("ws-2");
  assert.deepEqual(calls.find((call) => call[0] === "removeWorkspace"), [
    "removeWorkspace",
    "ws-2",
  ]);
  assert.equal(actions.at(-1).type, "source_control_reset");

  const blockedActions = [];
  const blocked = createWorkspaceController({
    protocol,
    dispatch: (action) => blockedActions.push(action),
    getAppState: () => ({ workspacePathInput: "D:/blocked" }),
    canSwitchWorkspace: () => ({ allowed: false, reason: "active_thread" }),
  });
  await blocked.openWorkspace();
  assert.deepEqual(blockedActions[0], {
    type: "workspace_activation_failed",
    error: "active_thread",
  });

  assert.throws(
    () => createWorkspaceController({ protocol: {} }),
    /protocol_method_missing:loadAppBootstrap/,
  );

  const appSource = readSource("App.jsx");
  const browserRuntimeSource = readSource("app-runtime", "browser-app-runtime.js");
  assert.equal(appSource.includes("async function openWorkspace"), false);
  assert.equal(appSource.includes("workspace_path_changed"), false);
  assert.equal(appSource.includes("createWorkspaceController"), false);
  assert.equal(appSource.includes("createWorkspaceFilesController"), false);
  assert.equal(browserRuntimeSource.includes("createWorkspaceController"), true);
  assert.equal(browserRuntimeSource.includes("createWorkspaceFilesController"), true);

  const controllerSource = readSource("app-runtime", "workspace-controller.js");
  assert.equal(controllerSource.includes("export function createWorkspaceController"), true);
  assert.equal(controllerSource.includes("function setWorkspacePath"), true);
  assert.equal(controllerSource.includes('type: "workspace_path_changed"'), true);
  assert.equal(controllerSource.includes("/api/"), false);
  assert.equal(controllerSource.includes("fetchJson"), false);
  assert.equal(controllerSource.includes("protocol"), true);

  assert.equal(appSource.includes("createSessionCommandCapabilityLoader"), false);
  assert.equal(browserRuntimeSource.includes("createSessionCommandCapabilityLoader"), true);
  assert.equal(browserRuntimeSource.includes("loadSessionCommandCapabilities"), true);
}
