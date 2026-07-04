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
  RIGHT_PANEL_SURFACE_REGISTRY,
  activateSurface,
  bottomDrawerCommandDefinitions,
  bottomDrawerSurfaceDefinitions,
  closeAllSurfaces,
  closeOtherSurfaces,
  closeSurface,
  closeSurfacesToRight,
  createWorkbenchState,
  openSurface,
  reduceWorkbenchState,
  rightPanelLauncherSurfaceDefinitions,
  rightPanelSurfaceDefinitions,
  surfaceCommandDefinitions,
  surfaceDefinitionFor,
  supportedSurfaceKinds,
} from "../src/workbench/surfaces.js";

function surface(id, title = id, launcherOrder = 0) {
  return { id, title, launcherOrder };
}

const RIGHT_PANEL_CAPABILITY_DESCRIPTORS = Object.freeze([
  surface("preview", "Preview", 10),
  surface("files", "Files", 20),
  surface("terminal", "Terminal", 30),
  surface("diff", "Diff", 40),
  surface("plan", "Plan", 50),
  surface("source_control", "Source Control", 60),
  surface("settings", "Settings", 70),
  surface("diagnostics", "Diagnostics", 80),
]);

const BOTTOM_DRAWER_CAPABILITY_DESCRIPTORS = Object.freeze([
  surface("run_output", "Run Output", 10),
  surface("terminal", "Terminal", 20),
  surface("logs", "Logs", 30),
]);

function cloneSurfaces(items) {
  return items.map((item) => ({ ...item }));
}

function capabilityIds(items) {
  return items.map((item) => item.id);
}

export function runWorkbenchStateTests() {
  const registryDefinitions = rightPanelSurfaceDefinitions();
  const fullAppCapabilities = {
    appCommands: APP_COMMANDS.map((item) => item.id),
    workspaceCommands: [
      "workspace.open",
      "workspace.refresh",
      "workspace.remove_current",
      "workspace.files",
    ],
    surfaces: {
      rightPanel: cloneSurfaces(RIGHT_PANEL_CAPABILITY_DESCRIPTORS),
      bottomDrawer: cloneSurfaces(BOTTOM_DRAWER_CAPABILITY_DESCRIPTORS),
    },
  };
  assert.equal(registryDefinitions, RIGHT_PANEL_SURFACE_REGISTRY);
  assert.deepEqual(registryDefinitions.map((definition) => definition.kind), supportedSurfaceKinds("right"));
  assert.deepEqual(rightPanelLauncherSurfaceDefinitions().map((definition) => definition.kind), []);
  assert.deepEqual(
    rightPanelLauncherSurfaceDefinitions(fullAppCapabilities).map((definition) => definition.kind),
    capabilityIds(RIGHT_PANEL_CAPABILITY_DESCRIPTORS),
  );
  for (const definition of registryDefinitions) {
    assert.equal(definition.placement, "right");
    assert.equal(typeof definition.kind, "string");
    assert.equal(Boolean(definition.title), true);
    assert.equal(Boolean(definition.resourceId), true);
    assert.equal(Boolean(definition.closeBehavior), true);
    assert.equal(Array.isArray(definition.persistFields), true);
    assert.equal(definition.persistFields.includes("kind"), true);
    assert.equal(definition.persistFields.includes("placement"), true);
    assert.equal(surfaceDefinitionFor(definition.kind), definition);
  }
  assert.equal(surfaceDefinitionFor("missing"), null);
  assert.equal(surfaceDefinitionFor("source_control").readOnly, true);
  assert.equal(surfaceDefinitionFor("source_control").offline, true);
  assert.equal(surfaceDefinitionFor("file").launcher, false);
  assert.equal(surfaceDefinitionFor("file").command, false);
  assert.equal(surfaceDefinitionFor("diff").defaultResourceId, "current");

  assert.equal(supportedSurfaceKinds("right").includes("file"), true);
  assert.equal(supportedSurfaceKinds("bottom").includes("terminal"), true);
  assert.equal(supportedSurfaceKinds("bottom").includes("run_output"), true);
  assert.deepEqual(bottomDrawerSurfaceDefinitions().map((definition) => definition.kind), []);
  assert.deepEqual(
    bottomDrawerSurfaceDefinitions(fullAppCapabilities).map((definition) => definition.kind),
    capabilityIds(BOTTOM_DRAWER_CAPABILITY_DESCRIPTORS),
  );

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
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.settings"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.diagnostics"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.source_control"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "app.reload"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "surface.files"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "surface.preview"), false);
  assert.deepEqual(
    WORKBENCH_COMMANDS.filter((item) => item.group === "surface" && item.surface)
      .map((item) => item.id),
    [],
  );
  assert.deepEqual(
    WORKBENCH_COMMANDS.filter((item) => item.group === "surface" && item.drawer)
      .map((item) => item.id),
    [],
  );
  assert.equal(commandById("surface.preview"), null);
  assert.equal(commandById("surface.preview", {}, fullAppCapabilities).surface, "preview");
  assert.equal(commandById("surface.diff", {}, fullAppCapabilities).surface, "diff");
  assert.equal(commandById("surface.source_control", {}, fullAppCapabilities).surface, "source_control");
  assert.equal(commandById("surface.settings", {}, fullAppCapabilities).surface, "settings");
  assert.equal(commandById("surface.diagnostics", {}, fullAppCapabilities).surface, "diagnostics");
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.open"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.refresh"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "workspace.remove_current"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "thread.new"), true);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id === "drawer.terminal"), false);
  assert.equal(WORKBENCH_COMMANDS.some((item) => item.id.includes("code")), false);
  assert.equal(commandById("message.send").slash, "");

  const visibleWhenIdle = visibleCommands({ hasSession: true, isRunning: false });
  assert.equal(visibleWhenIdle.some((item) => item.id === "app.settings"), false);
  assert.equal(visibleWhenIdle.some((item) => item.id === "app.source_control"), false);
  assert.equal(visibleWhenIdle.some((item) => item.id === "message.send"), true);
  assert.equal(visibleWhenIdle.some((item) => item.id === "message.stop"), false);

  const visibleWithoutSession = visibleCommands({ hasSession: false, isRunning: false });
  assert.equal(visibleWithoutSession.some((item) => item.id === "app.settings"), false);
  assert.equal(visibleWithoutSession.some((item) => item.id === "mode.build"), false);

  const visibleWhenRunning = visibleCommands({ hasSession: true, isRunning: true });
  assert.equal(visibleWhenRunning.some((item) => item.id === "message.stop"), true);

  const limitedAppCapabilities = {
    appCommands: ["app.settings"],
    workspaceCommands: ["workspace.open"],
    surfaces: {
      rightPanel: [surface("settings", "Settings")],
      bottomDrawer: [surface("logs", "Logs")],
    },
  };
  assert.deepEqual(
    rightPanelLauncherSurfaceDefinitions(limitedAppCapabilities).map((item) => item.kind),
    ["settings"],
  );
  assert.deepEqual(
    surfaceCommandDefinitions(limitedAppCapabilities).map((item) => item.id),
    ["surface.settings"],
  );
  assert.deepEqual(
    bottomDrawerCommandDefinitions(limitedAppCapabilities).map((item) => item.id),
    ["drawer.logs"],
  );
  const limitedVisible = visibleCommands({
    hasSession: true,
    hasWorkspace: true,
    isRunning: false,
    appCapabilities: limitedAppCapabilities,
  }).map((item) => item.id);
  assert.equal(limitedVisible.includes("app.settings"), true);
  assert.equal(limitedVisible.includes("app.diagnostics"), false);
  assert.equal(limitedVisible.includes("app.source_control"), false);
  assert.equal(limitedVisible.includes("workspace.open"), true);
  assert.equal(limitedVisible.includes("workspace.refresh"), false);
  assert.equal(limitedVisible.includes("surface.settings"), true);
  assert.equal(limitedVisible.includes("surface.diagnostics"), false);
  assert.equal(limitedVisible.includes("surface.preview"), false);
  assert.equal(limitedVisible.includes("drawer.logs"), true);
  assert.equal(limitedVisible.includes("drawer.terminal"), false);

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
    appCapabilities: fullAppCapabilities,
  });
  assert.equal(settingsCommand.id, "app.settings");
  assert.equal(
    resolveKeybinding(DEFAULT_KEYBINDINGS, "mod+,", {
      paletteOpen: false,
      isRunning: false,
    }),
    null,
  );

  const blocked = resolveKeybinding(DEFAULT_KEYBINDINGS, "enter", {
    paletteOpen: false,
    composerFocused: false,
  });
  assert.equal(blocked, null);
}
