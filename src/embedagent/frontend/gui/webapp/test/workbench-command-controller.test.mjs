import assert from "node:assert/strict";

import { createWorkbenchCommandController } from "../src/app-runtime/workbench-command-controller.js";

function createHarness(overrides = {}) {
  const actions = [];
  const calls = [];
  const focusedSelectors = [];
  const controller = createWorkbenchCommandController({
    dispatch: (action) => actions.push(action),
    documentObject: {
      querySelector: (selector) => {
        focusedSelectors.push(selector);
        return { focus: () => calls.push(["focus", selector]) };
      },
    },
    setTimeoutFn: (callback) => callback(),
    getCurrentMode: () => "build",
    getActiveWorkspaceId: () => "workspace-1",
    createSession: async (mode) => calls.push(["createSession", mode]),
    loadSessions: async () => calls.push(["loadSessions"]),
    loadAppBootstrap: async () => calls.push(["loadAppBootstrap"]),
    removeWorkspace: async (workspaceId) => calls.push(["removeWorkspace", workspaceId]),
    sendMessage: async () => calls.push(["sendMessage"]),
    cancelSession: async () => calls.push(["cancelSession"]),
    submitText: async (text) => calls.push(["submitText", text]),
    setMode: async (mode) => calls.push(["setMode", mode]),
    openRightPanelSurface: (surface, label) => calls.push(["openSurface", surface, label]),
    terminalController: {
      ensureOpen: async () => calls.push(["ensureTerminal"]),
    },
    ...overrides,
  });
  return { actions, calls, focusedSelectors, controller };
}

export async function runWorkbenchCommandControllerTests() {
  const harness = createHarness();

  await harness.controller.execute({ id: "custom.palette", dispatch: { kind: "command_palette.open" } });
  await harness.controller.execute({ id: "custom.session", dispatch: { kind: "session.create" } });
  await harness.controller.execute({ id: "custom.workspace", dispatch: { kind: "workspace.focus_path_input" } });
  await harness.controller.execute({ id: "custom.reload", dispatch: { kind: "app_shell.reload" } });
  await harness.controller.execute({ id: "custom.remove", dispatch: { kind: "workspace.remove_active_recent" } });
  await harness.controller.execute({ id: "custom.mode", dispatch: { kind: "mode.set", mode: "verify" } });

  assert.deepEqual(harness.actions, [{ type: "workbench_command_palette_opened" }]);
  assert.deepEqual(harness.focusedSelectors, ['[data-testid="sidebar-workspace-path-input"]']);
  assert.deepEqual(harness.calls, [
    ["createSession", "build"],
    ["focus", '[data-testid="sidebar-workspace-path-input"]'],
    ["loadAppBootstrap"],
    ["removeWorkspace", "workspace-1"],
    ["setMode", "verify"],
  ]);

  const fallbackHarness = createHarness();
  await fallbackHarness.controller.execute({ id: "custom.surface", surface: "preview", label: "Preview" });
  await fallbackHarness.controller.execute({ id: "custom.drawer", drawer: "terminal" });
  await fallbackHarness.controller.execute({ id: "custom.slash", slash: "/review" });
  assert.deepEqual(fallbackHarness.calls, [
    ["openSurface", "preview", "Preview"],
    ["ensureTerminal"],
    ["submitText", "/review"],
  ]);
}
