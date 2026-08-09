import assert from "node:assert/strict";

import { createWorkbenchCommandController } from "../src/app-runtime/workbench-command-controller.js";

function createHarness(overrides = {}) {
  const actions = [];
  const calls = [];
  const focusedSelectors = [];
  const prompts = [];
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
    getCurrentSessionId: () => "session-1",
    getShellDescriptor: () => ({
      surfaces: [
        { id: "session.commands", label: "Commands", placement: "overlay", rendererKey: "command_palette" },
        { id: "session.composer", label: "Composer", placement: "overlay", rendererKey: "composer" },
        { id: "preview", label: "Preview", placement: "secondary", rendererKey: "preview" },
      ],
    }),
    createSession: async (mode) => calls.push(["createSession", mode]),
    renameSession: async (sessionId, command) => calls.push(["renameSession", sessionId, command.label]),
    archiveSession: async (sessionId, command) => calls.push(["archiveSession", sessionId, command.label]),
    forkSession: async (sessionId, command) => calls.push(["forkSession", sessionId, command.label]),
    cancelSession: async () => calls.push(["cancelSession"]),
    submitText: async (text) => calls.push(["submitText", text]),
    setMode: async (mode) => calls.push(["setMode", mode]),
    openContributionSurface: (surface, label) => calls.push(["openSurface", surface, label]),
    prompt: (label, initial) => {
      prompts.push([label, initial]);
      return "verify";
    },
    ...overrides,
  });
  return { actions, calls, focusedSelectors, prompts, controller };
}

export async function runWorkbenchCommandControllerTests() {
  const harness = createHarness();

  await harness.controller.execute({ id: "session.new", label: "New", dispatch: { kind: "session.create" } });
  await harness.controller.execute({ id: "session.select", label: "Select", dispatch: { kind: "session.select" } });
  await harness.controller.execute({ id: "session.rename", label: "Rename", dispatch: { kind: "session.rename" } });
  await harness.controller.execute({ id: "session.archive", label: "Archive", dispatch: { kind: "session.archive" } });
  await harness.controller.execute({ id: "session.fork", label: "Fork", dispatch: { kind: "session.fork" } });
  await harness.controller.execute({ id: "session.cancel", label: "Cancel", dispatch: { kind: "session.cancel" } });
  await harness.controller.execute({ id: "session.mode", label: "Mode", dispatch: { kind: "session.mode" } });
  await harness.controller.execute({ id: "workflow.review", dispatch: { kind: "session.command", command: "review" } });
  await harness.controller.execute({ id: "workspace.open", dispatch: { kind: "workspace.open" } });
  await harness.controller.execute({
    id: "shell.commands",
    dispatch: { kind: "shell.surface", surface_id: "session.commands" },
  });
  await harness.controller.execute({
    id: "shell.composer",
    dispatch: { kind: "shell.surface", surface_id: "session.composer" },
  });
  await harness.controller.execute({
    id: "shell.preview",
    dispatch: { kind: "shell.surface", surface_id: "preview" },
  });

  assert.deepEqual(harness.actions, [
    { type: "command_palette_opened" },
    { type: "command_palette_opened" },
  ]);
  assert.deepEqual(harness.focusedSelectors, [
    '[data-testid="sidebar-workspace-path-input"]',
    '[data-testid="composer-input"]',
  ]);
  assert.deepEqual(harness.prompts, [["Mode", "build"]]);
  assert.deepEqual(harness.calls, [
    ["createSession", "build"],
    ["renameSession", "session-1", "Rename"],
    ["archiveSession", "session-1", "Archive"],
    ["forkSession", "session-1", "Fork"],
    ["cancelSession"],
    ["setMode", "verify"],
    ["submitText", "/review"],
    ["focus", '[data-testid="sidebar-workspace-path-input"]'],
    ["focus", '[data-testid="composer-input"]'],
    ["openSurface", "preview", "Preview"],
  ]);

  await assert.rejects(
    () => harness.controller.execute({ id: "legacy", dispatch: { kind: "app_shell.reload" } }),
    /unsupported_shell_dispatch/,
  );
}
