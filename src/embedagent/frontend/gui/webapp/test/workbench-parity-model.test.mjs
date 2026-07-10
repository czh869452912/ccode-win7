import assert from "node:assert/strict";

import { initialState, reducer } from "../src/store.js";
import {
  bottomDrawerCommandDefinitions,
  surfaceCommandDefinitions,
} from "../src/workbench/surfaces.js";
import { buildWorkbenchParityModel } from "../src/workbench/workbench-parity-model.js";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function surface(id, title = id, launcherOrder = 0) {
  return { id, title, launcherOrder };
}

function sessionWorkspaceState(patch = {}) {
  return {
    ...initialState,
    app: {
      ...initialState.app,
      hasActiveWorkspace: true,
      activeWorkspace: { id: "ws-1", label: "demo", path: "D:/work/demo" },
      capabilities: {
        appCommands: [
          { id: "app.settings", group: "app", label: "Preferences" },
          { id: "app.diagnostics", group: "app", label: "Health" },
          { id: "app.source_control", group: "app", label: "Changes", surface: "source_control" },
          { id: "app.reload", group: "app", label: "Reload Shell" },
        ],
        workspaceCommands: [
          { id: "workspace.open", group: "workspace", label: "Open Project" },
          { id: "workspace.refresh", group: "workspace", label: "Refresh Projects" },
          { id: "workspace.remove_current", group: "workspace", label: "Forget Project" },
        ],
        surfaces: {
          rightPanel: [
            surface("preview", "Preview", 10),
            surface("files", "Files", 20),
            surface("terminal", "Terminal", 30),
            surface("diff", "Diff", 40),
            surface("plan", "Plan", 50),
            surface("source_control", "Source Control", 60),
            surface("settings", "Settings", 70),
            surface("diagnostics", "Diagnostics", 80),
          ],
          bottomDrawer: [
            surface("run_output", "Run Output", 10),
            surface("terminal", "Terminal", 20),
          ],
        },
        sourceControl: initialState.app.capabilities.sourceControl,
        terminal: initialState.app.capabilities.terminal,
        threadLifecycle: initialState.app.capabilities.threadLifecycle,
      },
    },
    thread: {
      ...initialState.thread,
      currentSessionId: "sess-1",
    },
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "build",
      ...(patch.snapshot || {}),
    },
    ...patch,
  };
}

function openRightSurface(state, kind, extra = {}) {
  return reducer(state, {
    type: "workbench_surface_opened",
    placement: "right",
    kind,
    title: kind,
    ...extra,
  });
}

export function runWorkbenchParityModelTests() {
  let desktop = sessionWorkspaceState();
  desktop = openRightSurface(desktop, "files");
  desktop = openRightSurface(desktop, "diff", { resourceId: "current" });
  const desktopBefore = clone(desktop);

  const desktopModel = buildWorkbenchParityModel(desktop, { width: 1440, height: 900 });

  assert.deepEqual(desktop, desktopBefore);
  assert.equal(desktopModel.centerColumn.maxWidth, 860);
  assert.equal(desktopModel.rightPanel.mode, "sidecar");
  assert.equal(desktopModel.rightPanel.surfaceCount, 2);
  assert.equal(desktopModel.bottomDrawer.mode, "closed");
  assert.equal(desktopModel.composer.mode, "command-ready");
  assert.equal(desktopModel.timeline.density, "compact");
  assert.deepEqual(desktopModel.commandPalette.availableSurfaceCommands, [
    ...surfaceCommandDefinitions(desktop.app.capabilities).map((command) => command.id),
    ...bottomDrawerCommandDefinitions(desktop.app.capabilities).map((command) => command.id),
  ]);

  const undeclaredModel = buildWorkbenchParityModel(
    {
      ...desktop,
      app: {
        ...desktop.app,
        capabilities: null,
      },
    },
    { width: 1440, height: 900 },
  );
  assert.deepEqual(undeclaredModel.commandPalette.availableSurfaceCommands, []);

  const missingSessionCapabilitiesModel = buildWorkbenchParityModel(
    {
      ...desktop,
      sessionCapabilities: null,
    },
    { width: 1440, height: 900 },
  );
  assert.deepEqual(
    missingSessionCapabilitiesModel.commandPalette.availableSurfaceCommands,
    desktopModel.commandPalette.availableSurfaceCommands,
  );

  let narrow = sessionWorkspaceState({ snapshot: { status: "running" } });
  narrow = openRightSurface(narrow, "terminal", {
    terminalId: "term-1",
    resourceId: "term-1",
  });
  narrow = reducer(narrow, { type: "workbench_bottom_drawer_toggled" });

  const narrowModel = buildWorkbenchParityModel(narrow, { width: 900, height: 760 });

  assert.equal(narrowModel.centerColumn.maxWidth, 860);
  assert.equal(narrowModel.rightPanel.mode, "stacked");
  assert.equal(narrowModel.rightPanel.surfaceCount, 1);
  assert.equal(narrowModel.bottomDrawer.mode, "docked");
  assert.equal(narrowModel.composer.mode, "running");
  assert.equal(narrowModel.timeline.density, "compact");

  const waitingPermission = buildWorkbenchParityModel(
    sessionWorkspaceState({ snapshot: { status: "waiting_permission" } }),
    { width: 900, height: 760 },
  );
  assert.equal(waitingPermission.composer.mode, "running");

  let mobile = sessionWorkspaceState({
    snapshot: {
      status: "waiting_user_input",
      pending_interaction_valid: true,
      pending_interaction: {
        interaction_id: "input-1",
        kind: "user_input",
        question: "Pick one",
      },
    },
  });
  mobile = openRightSurface(mobile, "preview", { resourceId: "http://127.0.0.1:5173" });
  mobile = reducer(mobile, { type: "workbench_bottom_drawer_toggled" });

  const mobileModel = buildWorkbenchParityModel(mobile, { width: 390, height: 780 });

  assert.equal(mobileModel.centerColumn.maxWidth, 390);
  assert.equal(mobileModel.rightPanel.mode, "mobile-stacked");
  assert.equal(mobileModel.rightPanel.surfaceCount, 1);
  assert.equal(mobileModel.bottomDrawer.mode, "compact");
  assert.equal(mobileModel.composer.mode, "interaction");
  assert.equal(mobileModel.timeline.density, "compact");
}
