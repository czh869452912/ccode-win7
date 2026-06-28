import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createWorkspaceController } from "../src/app-runtime/workspace-controller.js";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8");
}

export async function runWorkspaceControllerTests() {
  const calls = [];
  const actions = [];
  const controller = createWorkspaceController({
    fetchJson: async (url, options = {}) => {
      calls.push(["fetchJson", url, options.method || "GET", options.body || ""]);
      if (url === "/api/app/bootstrap") {
        return {
          active_workspace: { id: "ws-1", path: "D:/work/demo", label: "demo" },
          workspaces: [{ id: "ws-1", path: "D:/work/demo", label: "demo" }],
          has_active_workspace: true,
        };
      }
      if (url === "/api/app/workspaces") {
        return {
          active_workspace: { id: "ws-2", path: "D:/work/new", label: "new" },
          workspaces: [{ id: "ws-2", path: "D:/work/new", label: "new" }],
          has_active_workspace: true,
        };
      }
      if (url === "/api/app/workspaces/ws-2/activate") {
        return {
          active_workspace: { id: "ws-2", path: "D:/work/new", label: "new" },
          workspaces: [{ id: "ws-2", path: "D:/work/new", label: "new" }],
          has_active_workspace: true,
        };
      }
      if (url === "/api/app/workspaces/ws-2") {
        return { workspaces: [], active_workspace: null, has_active_workspace: false };
      }
      throw new Error(`unexpected url ${url}`);
    },
    dispatch: (action) => actions.push(action),
    getCurrentSessionId: () => "sess-1",
    getAppState: () => ({
      hasActiveWorkspace: true,
      workspacePathInput: "D:/work/new",
    }),
    canSwitchWorkspace: () => ({ allowed: true, reason: "" }),
    loadWorkspaceData: async (sessionId, assumeWorkspace) => {
      calls.push(["loadWorkspaceData", sessionId, assumeWorkspace]);
    },
  });

  await controller.loadAppBootstrap();
  assert.equal(actions[0].type, "app_bootstrap_loaded");
  assert.equal(actions[0].bootstrap.hasActiveWorkspace, true);
  assert.deepEqual(calls[1], ["loadWorkspaceData", "", true]);

  await controller.openWorkspace();
  assert.equal(actions.at(-1).type, "workspace_switched");
  assert.deepEqual(calls.find((call) => call[1] === "/api/app/workspaces").slice(0, 4), [
    "fetchJson",
    "/api/app/workspaces",
    "POST",
    JSON.stringify({ path: "D:/work/new" }),
  ]);

  await controller.activateWorkspace("ws-2");
  assert.equal(calls.some((call) => call[1] === "/api/app/workspaces/ws-2/activate"), true);

  await controller.removeWorkspace("ws-2");
  assert.equal(actions.at(-1).type, "source_control_reset");

  const blockedActions = [];
  const blocked = createWorkspaceController({
    fetchJson: async () => ({}),
    dispatch: (action) => blockedActions.push(action),
    getAppState: () => ({ workspacePathInput: "D:/blocked" }),
    canSwitchWorkspace: () => ({ allowed: false, reason: "active_thread" }),
  });
  await blocked.openWorkspace();
  assert.deepEqual(blockedActions[0], {
    type: "workspace_activation_failed",
    error: "active_thread",
  });

  const appSource = readSource("App.jsx");
  assert.equal(appSource.includes("async function openWorkspace"), false);
  assert.equal(appSource.includes("async function activateWorkspace"), false);
  assert.equal(appSource.includes("async function removeWorkspace"), false);
  assert.equal(appSource.includes("async function loadAppBootstrap"), false);
  assert.equal(appSource.includes("createWorkspaceController"), true);

  const controllerSource = readSource("app-runtime", "workspace-controller.js");
  assert.equal(controllerSource.includes("export function createWorkspaceController"), true);
  assert.equal(controllerSource.includes("/api/app/bootstrap"), true);
  assert.equal(controllerSource.includes("/api/app/workspaces"), true);
  assert.equal(controllerSource.includes("import React"), false);
}
