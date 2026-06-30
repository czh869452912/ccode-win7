import assert from "node:assert/strict";

import { initialState, reducer } from "../src/store.js";
import { surfaceCommandDefinitions } from "../src/workbench/surfaces.js";
import { buildWorkbenchParityModel } from "../src/workbench/workbench-parity-model.js";

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function sessionWorkspaceState(patch = {}) {
  return {
    ...initialState,
    app: {
      ...initialState.app,
      hasActiveWorkspace: true,
      activeWorkspace: { id: "ws-1", label: "demo", path: "D:/work/demo" },
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
    ...surfaceCommandDefinitions().map((command) => command.id),
    "drawer.run_output",
    "drawer.terminal",
  ]);

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
