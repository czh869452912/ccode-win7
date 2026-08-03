import assert from "node:assert/strict";

import { shellCapabilityModel } from "../src/app-shell/model.js";
import {
  buildCommandVisibilityContext,
  buildWorkbenchCommands,
  commandById,
  visibleCommands,
} from "../src/workbench/commands.js";
import { resolveKeybinding } from "../src/workbench/keybindings.js";
import {
  createWorkbenchState,
  openSurface,
  rightPanelLauncherSurfaceDefinitions,
  surfaceDefinitionFor,
} from "../src/workbench/surfaces.js";

function shellDescriptor() {
  return {
    schemaVersion: 1,
    commands: [
      {
        id: "session.new",
        label: "New Session",
        group: "session",
        dispatch: { kind: "session.create" },
        availability: {},
        summary: "",
      },
      {
        id: "shell.preview",
        label: "Open Preview",
        group: "shell",
        dispatch: { kind: "shell.surface", surface_id: "preview" },
        availability: { visible_when: "has_workspace" },
        summary: "",
      },
    ],
    surfaces: [
      {
        id: "preview",
        label: "Preview",
        placement: "secondary",
        rendererKey: "preview",
        availability: {},
        metadata: {},
      },
    ],
    keybindings: [
      { commandId: "session.new", keys: "ctrl+n", when: {} },
    ],
    toolPresentations: [],
    timelineItems: [],
    interactions: [],
  };
}

export function runWorkbenchStateTests() {
  const capabilities = shellCapabilityModel(shellDescriptor());

  assert.deepEqual(
    buildWorkbenchCommands(
      {
        commands: [
          { id: "undeclared.dynamic", label: "Must Not Appear", active: true },
        ],
      },
      capabilities,
    ).map((item) => item.id),
    ["session.new", "shell.preview"],
  );
  assert.equal(commandById("undeclared.dynamic", {}, capabilities), null);
  assert.equal(commandById("session.new", {}, capabilities).label, "New Session");

  assert.deepEqual(
    visibleCommands(
      buildCommandVisibilityContext({
        appCapabilities: capabilities,
        hasActiveWorkspace: false,
      }),
    ).map((item) => item.id),
    ["session.new"],
  );
  assert.deepEqual(
    visibleCommands(
      buildCommandVisibilityContext({
        appCapabilities: capabilities,
        hasActiveWorkspace: true,
      }),
    ).map((item) => item.id),
    ["session.new", "shell.preview"],
  );

  assert.equal(
    resolveKeybinding(capabilities.keybindings, "ctrl+n", {
      appCapabilities: capabilities,
    }).id,
    "session.new",
  );
  assert.equal(
    resolveKeybinding(
      [{ commandId: "undeclared.dynamic", key: "ctrl+d", when: "always" }],
      "ctrl+d",
      { appCapabilities: capabilities },
    ),
    null,
  );

  const surfaces = rightPanelLauncherSurfaceDefinitions(capabilities);
  assert.deepEqual(surfaces.map((item) => item.kind), ["preview"]);
  assert.equal(surfaceDefinitionFor("preview"), null);
  assert.equal(surfaceDefinitionFor("terminal", capabilities), null);
  const preview = surfaceDefinitionFor("preview", capabilities);
  assert.equal(preview.bodyKind, "preview");
  assert.equal(preview.title, "Preview");

  const opened = openSurface(createWorkbenchState(), {
    placement: "right",
    kind: "preview",
    surfaceDefinition: preview,
  });
  assert.equal(opened.rightPanel.surfaces.length, 1);
  assert.equal(opened.rightPanel.surfaces[0].kind, "preview");

  const emptyCapabilities = shellCapabilityModel({
    schemaVersion: 1,
    commands: [],
    surfaces: [],
    keybindings: [],
    toolPresentations: [],
    timelineItems: [],
    interactions: [],
  });
  assert.deepEqual(buildWorkbenchCommands({}, emptyCapabilities), []);
  assert.deepEqual(rightPanelLauncherSurfaceDefinitions(emptyCapabilities), []);
}
