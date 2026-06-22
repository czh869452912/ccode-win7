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
  RIGHT_PANEL_KINDS,
  RIGHT_PANEL_SURFACES,
  activateSurface,
  closeAllSurfaces,
  closeOtherSurfaces,
  closeSurface,
  closeSurfacesToRight,
  createWorkbenchState,
  openSurface,
  reduceWorkbenchState,
} from "../src/workbench/surfaces.js";

export function runWorkbenchStateTests() {
  assert.deepEqual(RIGHT_PANEL_KINDS, [
    "preview",
    "diff",
    "files",
    "file",
    "terminal",
    "plan",
    "source_control",
    "settings",
    "diagnostics",
  ]);
  assert.deepEqual(RIGHT_PANEL_SURFACES, [
    "preview",
    "files",
    "terminal",
    "diff",
    "plan",
    "source_control",
    "settings",
    "diagnostics",
  ]);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("terminal"), true);
  assert.equal(BOTTOM_DRAWER_SURFACES.includes("run_output"), true);

  const initial = createWorkbenchState();
  assert.equal(initial.rightPanel.open, true);
  assert.equal(initial.rightPanel.activeSurfaceId, null);
  assert.equal(initial.rightPanel.activeKind, "");
  assert.deepEqual(initial.rightPanel.surfaces, []);
  assert.equal(initial.bottomDrawer.open, false);

  const withFiles = openSurface(initial, {
    placement: "right",
    kind: "files",
    title: "Files",
  });
  assert.notEqual(withFiles, initial);
  assert.equal(withFiles.rightPanel.open, true);
  assert.equal(withFiles.rightPanel.activeKind, "files");
  assert.equal(withFiles.rightPanel.activeSurfaceId, "right:files");
  assert.equal(withFiles.rightPanel.surfaces.length, 1);
  assert.equal(withFiles.rightPanel.surfaces[0].id, "right:files");

  const withFile = openSurface(withFiles, {
    placement: "right",
    kind: "file",
    filePath: "src/main.c",
  });
  assert.equal(withFile.rightPanel.activeKind, "file");
  assert.equal(withFile.rightPanel.activeSurfaceId, "right:file:src/main.c");
  assert.deepEqual(withFile.rightPanel.surfaces.map((surface) => surface.kind), ["file"]);
  assert.equal(withFile.rightPanel.surfaces[0].title, "main.c");
  assert.equal(withFile.rightPanel.surfaces[0].resourceId, "src/main.c");
  assert.equal(withFile.rightPanel.surfaces[0].filePath, "src/main.c");
  assert.equal(withFile.rightPanel.surfaces[0].revealLine, null);
  assert.equal(withFile.rightPanel.surfaces[0].revealRequestId, 1);

  const revealedFile = openSurface(withFile, {
    placement: "right",
    kind: "file",
    filePath: "src/main.c",
    revealLine: 42,
  });
  assert.equal(revealedFile.rightPanel.surfaces.length, 1);
  assert.equal(revealedFile.rightPanel.surfaces[0].revealLine, 42);
  assert.equal(revealedFile.rightPanel.surfaces[0].revealRequestId, 2);

  const resetRevealFile = openSurface(revealedFile, {
    placement: "right",
    kind: "file",
    filePath: "src/main.c",
  });
  assert.equal(resetRevealFile.rightPanel.surfaces[0].revealLine, null);
  assert.equal(resetRevealFile.rightPanel.surfaces[0].revealRequestId, 3);

  const secondFile = openSurface(resetRevealFile, {
    placement: "right",
    kind: "file",
    filePath: "README.md",
  });
  assert.deepEqual(secondFile.rightPanel.surfaces.map((surface) => surface.id), [
    "right:file:src/main.c",
    "right:file:README.md",
  ]);
  assert.equal(secondFile.rightPanel.activeSurfaceId, "right:file:README.md");

  const withPreview = openSurface(withFiles, {
    placement: "right",
    kind: "preview",
    title: "Preview",
  });
  assert.equal(withPreview.rightPanel.activeKind, "preview");
  assert.equal(withPreview.rightPanel.activeSurfaceId, "right:preview");
  assert.equal(withPreview.rightPanel.surfaces.at(-1).title, "Preview");
  assert.equal(withPreview.rightPanel.surfaces.at(-1).resourceId, "");

  const withPreviewUrl = openSurface(withPreview, {
    placement: "right",
    kind: "preview",
    title: "localhost:5173",
    resourceId: "http://127.0.0.1:5173",
  });
  assert.equal(withPreviewUrl.rightPanel.activeSurfaceId, "right:preview:http://127.0.0.1:5173");
  assert.equal(withPreviewUrl.rightPanel.surfaces.at(-1).resourceId, "http://127.0.0.1:5173");
  assert.equal(withPreviewUrl.rightPanel.surfaces.some((surface) => surface.id === "right:preview"), false);

  const withDiff = openSurface(withFiles, {
    placement: "right",
    kind: "diff",
    title: "Diff",
    resourceId: "current",
  });
  assert.equal(withDiff.rightPanel.activeKind, "diff");
  assert.equal(withDiff.rightPanel.activeSurfaceId, "right:diff:current");
  assert.deepEqual(withDiff.rightPanel.surfaces.map((surface) => surface.kind), ["files", "diff"]);

  const reusedDiff = openSurface(withDiff, {
    placement: "right",
    kind: "diff",
    title: "Diff",
    resourceId: "current",
  });
  assert.equal(reusedDiff.rightPanel.surfaces.length, 2);
  assert.equal(reusedDiff.rightPanel.activeSurfaceId, "right:diff:current");

  const activatedFiles = activateSurface(reusedDiff, {
    placement: "right",
    surfaceId: "right:files",
  });
  assert.equal(activatedFiles.rightPanel.activeKind, "files");
  assert.equal(activatedFiles.rightPanel.activeSurfaceId, "right:files");

  const withTerminal = openSurface(activatedFiles, {
    placement: "right",
    kind: "terminal",
    title: "Terminal",
    resourceId: "terminal-1",
  });
  const withPlan = openSurface(withTerminal, {
    placement: "right",
    kind: "plan",
    title: "Plan",
  });
  assert.deepEqual(withPlan.rightPanel.surfaces.map((surface) => surface.kind), [
    "files",
    "diff",
    "terminal",
    "plan",
  ]);

  const closedPlan = closeSurface(withPlan, {
    placement: "right",
    surfaceId: "right:plan",
  });
  assert.equal(closedPlan.rightPanel.activeKind, "terminal");
  assert.equal(closedPlan.rightPanel.activeSurfaceId, "right:terminal:terminal-1");

  const onlyTerminal = closeOtherSurfaces(withPlan, {
    placement: "right",
    surfaceId: "right:terminal:terminal-1",
  });
  assert.deepEqual(onlyTerminal.rightPanel.surfaces.map((surface) => surface.kind), ["terminal"]);
  assert.equal(onlyTerminal.rightPanel.activeKind, "terminal");

  const leftPair = closeSurfacesToRight(withPlan, {
    placement: "right",
    surfaceId: "right:diff:current",
  });
  assert.deepEqual(leftPair.rightPanel.surfaces.map((surface) => surface.kind), ["files", "diff"]);
  assert.equal(leftPair.rightPanel.activeKind, "diff");

  const emptyRight = closeAllSurfaces(withPlan, { placement: "right" });
  assert.deepEqual(emptyRight.rightPanel.surfaces, []);
  assert.equal(emptyRight.rightPanel.activeSurfaceId, null);
  assert.equal(emptyRight.rightPanel.activeKind, "");
  assert.equal(emptyRight.rightPanel.open, false);

  const terminalOne = openSurface(initial, {
    placement: "right",
    kind: "terminal",
    terminalId: "term-1",
    resourceId: "term-1",
  });
  const terminalTwo = openSurface(terminalOne, {
    placement: "right",
    kind: "terminal",
    terminalId: "term-2",
    resourceId: "term-2",
  });
  assert.deepEqual(terminalTwo.rightPanel.surfaces, [
    {
      id: "right:terminal:term-1",
      placement: "right",
      kind: "terminal",
      title: "Terminal",
      resourceId: "term-1",
      filePath: "",
      terminalId: "term-1",
      terminalIds: ["term-1"],
      activeTerminalId: "term-1",
      revealLine: null,
      revealRequestId: 0,
    },
    {
      id: "right:terminal:term-2",
      placement: "right",
      kind: "terminal",
      title: "Terminal",
      resourceId: "term-2",
      filePath: "",
      terminalId: "term-2",
      terminalIds: ["term-2"],
      activeTerminalId: "term-2",
      revealLine: null,
      revealRequestId: 0,
    },
  ]);
  assert.equal(terminalTwo.rightPanel.activeSurfaceId, "right:terminal:term-2");

  const splitTerminal = reduceWorkbenchState(terminalOne, {
    type: "workbench_terminal_surface_split",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-2",
  });
  assert.deepEqual(splitTerminal.rightPanel.surfaces[0].terminalIds, ["term-1", "term-2"]);
  assert.equal(splitTerminal.rightPanel.surfaces[0].activeTerminalId, "term-2");
  assert.equal(splitTerminal.rightPanel.surfaces[0].splitDirection, undefined);
  assert.equal(splitTerminal.rightPanel.activeSurfaceId, "right:terminal:term-1");

  const activatedPane = reduceWorkbenchState(splitTerminal, {
    type: "workbench_terminal_surface_terminal_activated",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.equal(activatedPane.rightPanel.surfaces[0].activeTerminalId, "term-1");

  const closedPane = reduceWorkbenchState(activatedPane, {
    type: "workbench_terminal_surface_terminal_closed",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.deepEqual(closedPane.rightPanel.surfaces[0].terminalIds, ["term-2"]);
  assert.equal(closedPane.rightPanel.surfaces[0].activeTerminalId, "term-2");

  const verticalSplit = reduceWorkbenchState(terminalOne, {
    type: "workbench_terminal_surface_split",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-2",
    splitDirection: "vertical",
  });
  assert.equal(verticalSplit.rightPanel.surfaces[0].splitDirection, "vertical");

  const finalClosedPane = reduceWorkbenchState(terminalOne, {
    type: "workbench_terminal_surface_terminal_closed",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-1",
  });
  assert.deepEqual(finalClosedPane.rightPanel.surfaces, []);
  assert.equal(finalClosedPane.rightPanel.activeSurfaceId, null);
  assert.equal(finalClosedPane.rightPanel.activeKind, "");
  assert.equal(finalClosedPane.rightPanel.open, false);

  const withRunOutput = openSurface(withFiles, {
    sessionId: "sess-1",
    placement: "bottom",
    kind: "run_output",
    title: "Build Output",
  });
  assert.equal(withRunOutput.bottomDrawer.open, true);
  assert.equal(withRunOutput.bottomDrawer.activeKind, "run_output");
  assert.equal(withRunOutput.surfacesBySession["sess-1"].bottom[0].kind, "run_output");

  const reduced = reduceWorkbenchState(initial, {
    type: "workbench_surface_opened",
    sessionId: "sess-2",
    placement: "right",
    kind: "plan",
    title: "Plan",
  });
  assert.equal(reduced.rightPanel.activeKind, "plan");
  assert.equal(reduced.rightPanel.surfaces[0].kind, "plan");

  const appShellSurface = openSurface(initial, {
    placement: "right",
    kind: "settings",
    title: "Settings",
  });
  assert.equal(appShellSurface.rightPanel.activeKind, "settings");
  assert.equal(appShellSurface.rightPanel.activeSurfaceId, "right:settings");
  assert.equal(appShellSurface.rightPanel.surfaces[0].title, "Settings");

  const unknownRightSurface = openSurface(initial, {
    placement: "right",
    kind: "unknown",
    title: "Unknown",
  });
  assert.equal(unknownRightSurface, initial);

  assert.equal(COMMAND_GROUPS.includes("session"), true);
  assert.equal(COMMAND_GROUPS.includes("app"), true);
  assert.equal(COMMAND_GROUPS.includes("surface"), true);
  assert.equal(COMMAND_GROUPS.includes("workspace"), true);
  assert.equal(APP_COMMANDS.some((item) => item.id === "app.settings"), true);
  assert.equal(isAppCommand("app.diagnostics"), true);
  assert.equal(isAppCommand("app.source_control"), true);
  assert.equal(isAppCommand("workspace.open"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.settings"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.diagnostics"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.source_control"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.reload"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "surface.files"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "surface.preview"), true);
  assert.equal(commandById("surface.preview").surface, "preview");
  assert.equal(commandById("surface.diff").surface, "diff");
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.open"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.refresh"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.remove_current"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "thread.new"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "drawer.terminal"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id.includes("code")), false);
  assert.equal(commandById("message.send").slash, "");

  const visibleWhenIdle = visibleCommands({ hasSession: true, isRunning: false });
  assert.equal(visibleWhenIdle.some((item) => item.id === "app.settings"), true);
  assert.equal(visibleWhenIdle.some((item) => item.id === "app.source_control"), true);
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
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+1" && item.commandId === "surface.files"), true);
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+2" && item.commandId === "surface.terminal"), true);
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+3" && item.commandId === "surface.diff"), true);
  assert.equal(DEFAULT_KEYBINDINGS.some((item) => item.key === "mod+4" && item.commandId === "surface.preview"), true);

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
