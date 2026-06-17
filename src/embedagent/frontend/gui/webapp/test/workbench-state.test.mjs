import assert from "node:assert/strict";

import {
  APP_COMMANDS,
  isAppCommand,
} from "../src/app-shell/commands.js";
import {
  COMMAND_GROUPS,
  WORKBENCH_COMMANDS,
  commandById,
  visibleCommands,
} from "../src/workbench/commands.js";
import {
  DEFAULT_KEYBINDINGS,
  eventToKey,
  resolveKeybinding,
} from "../src/workbench/keybindings.js";
import {
  BOTTOM_DRAWER_SURFACES,
  RIGHT_PANEL_SURFACES,
  activateSurface,
  closeSurface,
  createWorkbenchState,
  openSurface,
  reduceWorkbenchState,
} from "../src/workbench/surfaces.js";

export function runWorkbenchStateTests() {
  assert.equal(RIGHT_PANEL_SURFACES.includes("tasks"), true);
  assert.equal(RIGHT_PANEL_SURFACES.includes("preview"), true);
  assert.equal(RIGHT_PANEL_SURFACES.includes("settings"), true);
  assert.equal(RIGHT_PANEL_SURFACES.includes("diagnostics"), true);
  assert.equal(RIGHT_PANEL_SURFACES.includes("source_control"), true);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("terminal"), true);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("run_output"), true);

  const initial = createWorkbenchState();
  assert.equal(initial.rightPanel.open, true);
  assert.equal(initial.rightPanel.activeKind, "tasks");
  assert.equal(initial.bottomDrawer.open, false);

  const withPreview = openSurface(initial, {
    sessionId: "sess-1",
    placement: "right",
    kind: "preview",
    title: "README.md",
    resourceId: "README.md",
  });
  assert.notEqual(withPreview, initial);
  assert.equal(withPreview.rightPanel.open, true);
  assert.equal(withPreview.rightPanel.activeKind, "preview");
  assert.equal(withPreview.surfacesBySession["sess-1"].right.length, 1);
  assert.equal(withPreview.surfacesBySession["sess-1"].right[0].resourceId, "README.md");

  const withRunOutput = openSurface(withPreview, {
    sessionId: "sess-1",
    placement: "bottom",
    kind: "run_output",
    title: "Build Output",
  });
  assert.equal(withRunOutput.bottomDrawer.open, true);
  assert.equal(withRunOutput.bottomDrawer.activeKind, "run_output");
  assert.equal(withRunOutput.surfacesBySession["sess-1"].bottom[0].kind, "run_output");

  const activated = activateSurface(withRunOutput, {
    placement: "right",
    kind: "tasks",
  });
  assert.equal(activated.rightPanel.activeKind, "tasks");

  const closed = closeSurface(withRunOutput, {
    sessionId: "sess-1",
    placement: "right",
    kind: "preview",
    resourceId: "README.md",
  });
  assert.equal(closed.surfacesBySession["sess-1"].right.length, 0);
  assert.equal(closed.rightPanel.activeKind, "tasks");

  const reduced = reduceWorkbenchState(initial, {
    type: "workbench_surface_opened",
    sessionId: "sess-2",
    placement: "right",
    kind: "runtime",
    title: "Runtime",
  });
  assert.equal(reduced.rightPanel.activeKind, "runtime");
  assert.equal(reduced.surfacesBySession["sess-2"].right[0].kind, "runtime");

  assert.equal(COMMAND_GROUPS.includes("session"), true);
  assert.equal(COMMAND_GROUPS.includes("app"), true);
  assert.equal(COMMAND_GROUPS.includes("surface"), true);
  assert.equal(COMMAND_GROUPS.includes("workspace"), true);
  assert.equal(APP_COMMANDS.some((item) => item.id === "app.settings"), true);
  assert.equal(isAppCommand("app.diagnostics"), true);
  assert.equal(isAppCommand("workspace.open"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.settings"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.diagnostics"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.reload"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "surface.tasks"), true);
  assert.equal(commandById("surface.source_control").surface, "source_control");
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.open"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.refresh"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.remove_current"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "thread.new"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "drawer.terminal"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id.includes("code")), false);
  assert.equal(commandById("message.send").slash, "");

  const visibleWhenIdle = visibleCommands({ hasSession: true, isRunning: false });
  assert.equal(visibleWhenIdle.some((item) => item.id === "app.settings"), true);
  assert.equal(visibleWhenIdle.some((item) => item.id === "message.send"), true);
  assert.equal(visibleWhenIdle.some((item) => item.id === "message.stop"), false);

  const visibleWithoutSession = visibleCommands({ hasSession: false, isRunning: false });
  assert.equal(visibleWithoutSession.some((item) => item.id === "app.settings"), true);
  assert.equal(visibleWithoutSession.some((item) => item.id === "mode.build"), false);

  const visibleWhenRunning = visibleCommands({ hasSession: true, isRunning: true });
  assert.equal(visibleWhenRunning.some((item) => item.id === "message.stop"), true);

  const syntheticEvent = {
    key: "k",
    ctrlKey: true,
    metaKey: false,
    altKey: false,
    shiftKey: false,
  };
  assert.equal(eventToKey(syntheticEvent), "mod+k");
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+k"), true);
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+," && item.commandId === "app.settings"), true);

  const command = resolveKeybinding(DEFAULT_KEYBINDINGS, "mod+k", {
    paletteOpen: false,
    isRunning: false,
  });
  assert.equal(command.id, "palette.open");

  const settingsCommand = resolveKeybinding(DEFAULT_KEYBINDINGS, "mod+,", {
    paletteOpen: false,
    isRunning: false,
  });
  assert.equal(settingsCommand.id, "app.settings");

  const blocked = resolveKeybinding(DEFAULT_KEYBINDINGS, "enter", {
    paletteOpen: false,
    composerFocused: false,
  });
  assert.equal(blocked, null);
}
