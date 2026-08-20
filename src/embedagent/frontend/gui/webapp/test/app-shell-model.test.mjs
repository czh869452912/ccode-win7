import assert from "node:assert/strict";

import {
  createAppShellState,
  normalizeAppBootstrap,
  normalizeAppSettings,
  normalizeWorkspaceRecord,
} from "../src/app-shell/model.js";

function command(id = "session.new") {
  return {
    id,
    label: "New Session",
    group: "session",
    dispatch: { kind: "session.create" },
    shortcut: "",
    availability: {},
    summary: "",
    source_type: "product",
    source_id: "minimal_shell",
  };
}

function surface(id = "preview") {
  return {
    id,
    label: "Preview",
    placement: "secondary",
    renderer_key: "preview",
    availability: {},
    metadata: {},
  };
}

function emptyShell() {
  return {
    schema_version: 2,
    commands: [],
    surfaces: [],
    keybindings: [],
    tool_presentations: [],
    timeline_items: [],
    interactions: [],
  };
}

function appBootstrap(patch = {}) {
  return {
    schema_version: 2,
    app: {
      shell_version: 1,
      product_name: "EmbedAgent",
      protocol: "gui_app_shell_v1",
    },
    workspaces: [],
    active_workspace: null,
    has_active_workspace: false,
    shell: emptyShell(),
    settings: {
      confirm_workspace_switch: true,
      show_diagnostics_badge: true,
    },
    diagnostics: {},
    last_error: "",
    ...patch,
  };
}

export function runAppShellModelTests() {
  const initial = createAppShellState();
  assert.equal(initial.bootstrapLoaded, false);
  assert.deepEqual(initial.shell.commands, []);
  assert.deepEqual(initial.capabilities.workbenchCommands, []);
  assert.deepEqual(initial.capabilities.contributions, []);
  assert.deepEqual(initial.capabilities.keybindings, []);

  const empty = normalizeAppBootstrap(appBootstrap());
  assert.equal(empty.bootstrapLoaded, true);
  assert.deepEqual(empty.shell.commands, []);
  assert.deepEqual(empty.capabilities.workbenchCommands, []);
  assert.deepEqual(empty.capabilities.contributions, []);
  assert.deepEqual(empty.capabilities.keybindings, []);

  const populated = normalizeAppBootstrap(appBootstrap({
    workspaces: [
      {
        id: "ws-1",
        path: "D:/work/demo",
        label: "demo",
        exists: true,
        created_at: "",
        last_opened_at: "",
      },
    ],
    active_workspace: {
      id: "ws-1",
      path: "D:/work/demo",
      label: "demo",
      exists: true,
      created_at: "",
      last_opened_at: "",
    },
    has_active_workspace: true,
    shell: {
      ...emptyShell(),
      commands: [command()],
      surfaces: [surface()],
      keybindings: [
        { command_id: "session.new", keys: "ctrl+n", when: {} },
      ],
    },
  }));
  assert.equal(populated.activeWorkspace.id, "ws-1");
  assert.deepEqual(
    populated.capabilities.workbenchCommands.map((item) => item.id),
    ["session.new"],
  );
  assert.deepEqual(
    populated.capabilities.contributions.map((item) => item.id),
    ["preview"],
  );
  assert.deepEqual(populated.capabilities.keybindings, [
    { commandId: "session.new", key: "ctrl+n", when: "always" },
  ]);

  assert.throws(
    () => normalizeAppBootstrap(appBootstrap({ shell: { commands: [{}] } })),
    /invalid_app_bootstrap/,
  );
  assert.throws(
    () => normalizeAppBootstrap({
      ...appBootstrap(),
      hasActiveWorkspace: false,
    }),
    /invalid_app_bootstrap/,
  );
  assert.throws(
    () => normalizeAppBootstrap({
      ...appBootstrap(),
      shell: { ...emptyShell(), commands: [command(), command()] },
    }),
    /duplicate_shell_command/,
  );

  const safe = normalizeAppBootstrap(appBootstrap({
    diagnostics: {
      host: { platform: "win32", api_key: "secret" },
      runtime: { authorization: "secret" },
    },
  }));
  assert.equal(JSON.stringify(safe).includes("secret"), false);

  assert.deepEqual(normalizeAppSettings({ confirm_workspace_switch: false }), {
    confirm_workspace_switch: false,
    show_diagnostics_badge: true,
  });
  assert.deepEqual(
    normalizeWorkspaceRecord({ id: "ws", path: "D:/work/demo" }),
    {
      id: "ws",
      path: "D:/work/demo",
      label: "demo",
      exists: true,
      created_at: "",
      last_opened_at: "",
    },
  );
}
