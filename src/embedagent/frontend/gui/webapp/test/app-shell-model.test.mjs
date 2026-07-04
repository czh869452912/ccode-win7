import assert from "node:assert/strict";

import { formatDiagnosticsRows } from "../src/app-shell/diagnostics.js";
import {
  createAppShellState,
  normalizeAppBootstrap,
  normalizeAppCapabilities,
  normalizeAppDiagnostics,
  normalizeAppSettings,
} from "../src/app-shell/model.js";
import {
  reduceAppShellState,
  resetAppShellWorkspaceState,
} from "../src/app-shell/reducer.js";

function surface(id, title = id, extra = {}) {
  return { id, title, ...extra };
}

export function runAppShellModelTests() {
  const initial = createAppShellState();
  assert.equal(initial.bootstrapLoaded, false);
  assert.equal(initial.app.shellVersion, 1);
  assert.equal(initial.app.protocol, "gui_app_shell_v1");
  assert.deepEqual(initial.workspaces, []);
  assert.equal(initial.activeWorkspace, null);
  assert.equal(initial.hasActiveWorkspace, false);
  assert.equal(initial.settings.confirm_workspace_switch, true);
  assert.equal(initial.settings.show_diagnostics_badge, true);
  assert.deepEqual(initial.diagnostics.host, {});
  assert.deepEqual(initial.capabilities.appCommands, []);
  assert.deepEqual(initial.capabilities.workspaceCommands, []);
  assert.deepEqual(initial.capabilities.surfaces.rightPanel, []);
  assert.deepEqual(initial.capabilities.surfaces.bottomDrawer, []);
  assert.deepEqual(initial.capabilities.keybindings, []);
  assert.equal(initial.capabilities.agentApplication, null);
  assert.deepEqual(initial.capabilities.agentApplications, []);
  assert.deepEqual(initial.capabilities.emptyState, {
    scenarioLabel: "",
    primary: "",
    secondary: "",
    pathPlaceholder: "",
  });
  assert.equal(initial.capabilities.terminal.enabled, false);
  assert.equal(initial.capabilities.terminal.pty, false);
  assert.equal(initial.capabilities.terminal.resize, false);
  assert.equal(initial.capabilities.sourceControl.enabled, false);
  assert.equal(initial.capabilities.sourceControl.readOnly, true);
  assert.equal(initial.capabilities.threadLifecycle.rename, false);
  assert.equal(initial.capabilities.threadLifecycle.fork, false);
  assert.equal(initial.capabilities.threadLifecycle.archive, false);

  const bootstrap = normalizeAppBootstrap({
    app: {
      shell_version: 1,
      product_name: "EmbedAgent",
      protocol: "gui_app_shell_v1",
    },
    workspaces: [
      {
        id: "ws-1",
        path: "D:/work/demo",
        label: "",
        exists: true,
        created_at: "2026-06-17T10:00:00Z",
        last_opened_at: "2026-06-17T11:00:00Z",
      },
    ],
    active_workspace: {
      id: "ws-1",
      path: "D:/work/demo",
      label: "Demo",
      exists: true,
    },
    has_active_workspace: true,
    diagnostics: {
      host: {
        platform: "win32",
        api_key: "sk-secret",
        nested: { token: "secret-token", safe: "ok" },
      },
      runtime: { runtime_source: "bundle" },
      renderer: { renderer: "edgechromium" },
      workspace_registry: { count: 1 },
      active_core: { present: true },
    },
    capabilities: {
      app_commands: ["app.settings", "app.diagnostics", "app.reload"],
      workspace_commands: ["workspace.open"],
      surfaces: {
        right_panel: [
          surface("settings", "Settings", { launcher_order: 10 }),
          surface("diagnostics", "Diagnostics", { launcher_order: 20 }),
          surface("source_control", "Source Control", { launcher_order: 30 }),
        ],
        bottom_drawer: [surface("terminal", "Terminal", { launcher_order: 10 })],
      },
      keybindings: [
        { key: "MOD+K", command_id: "palette.open", when: "not_palette" },
        { key: "mod+,", command_id: "app.settings", when: "always" },
      ],
      agentApplication: {
        applicationId: "tests.python",
        label: "Python Agent",
        profileId: "tests.python.profile",
        workflowPackageIds: ["tests.python.workflow"],
        active: true,
      },
      agentApplications: [
        {
          applicationId: "tests.python",
          label: "Python Agent",
          profileId: "tests.python.profile",
          workflowPackageIds: ["tests.python.workflow"],
          active: true,
        },
      ],
      emptyState: {
        scenario_label: "Python workspace",
        primary: "Open a Python project",
      },
      source_control: {
        enabled: true,
        vcs: ["git"],
        read_only: true,
        remote_providers: false,
        network: false,
        checkpoints: false,
        requires_active_workspace: true,
      },
      terminal: {
        enabled: true,
        pty: false,
        resize: false,
        history_persistent: false,
        max_buffer_bytes: 131072,
      },
      thread_lifecycle: { rename: true, fork: true, archive: true },
    },
    settings: {
      confirm_workspace_switch: false,
      show_diagnostics_badge: true,
      ignored_setting: true,
    },
    last_error: "warning",
  });
  assert.equal(bootstrap.bootstrapLoaded, true);
  assert.equal(bootstrap.app.productName, "EmbedAgent");
  assert.equal(bootstrap.workspaces[0].label, "demo");
  assert.equal(bootstrap.activeWorkspace.label, "Demo");
  assert.equal(bootstrap.hasActiveWorkspace, true);
  assert.equal(bootstrap.lastError, "warning");
  assert.equal(bootstrap.settings.confirm_workspace_switch, false);
  assert.equal(bootstrap.settings.ignored_setting, undefined);
  assert.equal(bootstrap.capabilities.appCommands.includes("app.reload"), true);
  assert.equal(bootstrap.capabilities.workspaceCommands.includes("workspace.open"), true);
  assert.deepEqual(
    bootstrap.capabilities.surfaces.rightPanel.map((item) => item.kind),
    ["settings", "diagnostics", "source_control"],
  );
  assert.equal(bootstrap.capabilities.surfaces.rightPanel[0].title, "Settings");
  assert.deepEqual(
    bootstrap.capabilities.surfaces.bottomDrawer.map((item) => item.kind),
    ["terminal"],
  );
  assert.deepEqual(bootstrap.capabilities.keybindings, [
    { key: "mod+k", commandId: "palette.open", when: "not_palette" },
    { key: "mod+,", commandId: "app.settings", when: "always" },
  ]);
  assert.equal(bootstrap.capabilities.agentApplication.applicationId, "tests.python");
  assert.equal(bootstrap.capabilities.agentApplications[0].profileId, "tests.python.profile");
  assert.equal(bootstrap.capabilities.emptyState.scenarioLabel, "Python workspace");
  assert.equal(bootstrap.capabilities.emptyState.primary, "Open a Python project");
  assert.equal(bootstrap.capabilities.sourceControl.enabled, true);
  assert.deepEqual(bootstrap.capabilities.sourceControl.vcs, ["git"]);
  assert.equal(bootstrap.capabilities.sourceControl.readOnly, true);
  assert.equal(bootstrap.capabilities.sourceControl.remoteProviders, false);
  assert.equal(bootstrap.capabilities.sourceControl.network, false);
  assert.equal(bootstrap.capabilities.sourceControl.checkpoints, false);
  assert.equal(bootstrap.capabilities.sourceControl.requiresActiveWorkspace, true);
  assert.equal(bootstrap.capabilities.terminal.enabled, true);
  assert.equal(bootstrap.capabilities.terminal.pty, false);
  assert.equal(bootstrap.capabilities.terminal.resize, false);
  assert.equal(bootstrap.capabilities.terminal.historyPersistent, false);
  assert.equal(bootstrap.capabilities.terminal.maxBufferBytes, 131072);
  assert.equal(bootstrap.capabilities.threadLifecycle.rename, true);
  assert.equal(bootstrap.capabilities.threadLifecycle.fork, true);
  assert.equal(bootstrap.capabilities.threadLifecycle.archive, true);
  assert.equal(bootstrap.diagnostics.host.platform, "win32");
  assert.equal(bootstrap.diagnostics.host.api_key, undefined);
  assert.equal(bootstrap.diagnostics.host.nested.token, undefined);
  assert.equal(bootstrap.diagnostics.host.nested.safe, "ok");

  const sanitizedDiagnostics = normalizeAppDiagnostics({
    host: { authorization: "Bearer abc", safe: "ok" },
    runtime: { token: "hidden", runtime_source: "bundle" },
    prompt: "hidden prompt",
  });
  assert.equal(sanitizedDiagnostics.host.authorization, undefined);
  assert.equal(sanitizedDiagnostics.host.safe, "ok");
  assert.equal(sanitizedDiagnostics.runtime.token, undefined);
  assert.equal(sanitizedDiagnostics.runtime.runtime_source, "bundle");
  assert.equal(sanitizedDiagnostics.prompt, undefined);

  const settings = normalizeAppSettings({
    confirm_workspace_switch: 0,
    show_diagnostics_badge: 1,
    extra: false,
  });
  assert.equal(settings.confirm_workspace_switch, false);
  assert.equal(settings.show_diagnostics_badge, true);
  assert.equal(settings.extra, undefined);

  const capabilities = normalizeAppCapabilities({
    app_commands: ["app.settings"],
    workspace_commands: ["workspace.open"],
    surfaces: {
      right_panel: [surface("settings", "Settings")],
      bottom_drawer: [surface("logs", "Logs")],
    },
    key_bindings: [{ key: "mod+k", command_id: "palette.open" }],
    agent_application: { application_id: "tests.generic", label: "Generic Agent" },
    agent_applications: [{ application_id: "tests.generic", label: "Generic Agent" }],
    empty_state: { scenario_label: "Generic workspace" },
    terminal: { enabled: true, pty: false, resize: false },
  });
  assert.deepEqual(capabilities.appCommands, ["app.settings"]);
  assert.deepEqual(capabilities.workspaceCommands, ["workspace.open"]);
  assert.deepEqual(capabilities.surfaces.rightPanel.map((item) => item.kind), ["settings"]);
  assert.deepEqual(capabilities.surfaces.bottomDrawer.map((item) => item.kind), ["logs"]);
  assert.deepEqual(capabilities.keybindings, [
    { key: "mod+k", commandId: "palette.open", when: "always" },
  ]);
  assert.equal(capabilities.agentApplication.applicationId, "tests.generic");
  assert.equal(capabilities.agentApplications[0].label, "Generic Agent");
  assert.equal(capabilities.emptyState.scenarioLabel, "Generic workspace");
  assert.equal(capabilities.terminal.enabled, true);
  assert.equal(capabilities.terminal.pty, false);
  assert.equal(capabilities.terminal.resize, false);

  const emptyCapabilities = normalizeAppCapabilities({});
  assert.deepEqual(emptyCapabilities.appCommands, []);
  assert.deepEqual(emptyCapabilities.workspaceCommands, []);
  assert.deepEqual(emptyCapabilities.surfaces.rightPanel, []);
  assert.deepEqual(emptyCapabilities.surfaces.bottomDrawer, []);
  assert.deepEqual(emptyCapabilities.keybindings, []);
  assert.equal(emptyCapabilities.agentApplication, null);
  assert.deepEqual(emptyCapabilities.agentApplications, []);
  assert.deepEqual(emptyCapabilities.emptyState, {
    scenarioLabel: "",
    primary: "",
    secondary: "",
    pathPlaceholder: "",
  });

  const reduced = reduceAppShellState(initial, {
    type: "app_shell_bootstrap_loaded",
    bootstrap,
  });
  assert.equal(reduced.bootstrapLoaded, true);
  assert.equal(reduced.activeWorkspace.id, "ws-1");
  assert.equal(reduced.workspaceError, "warning");

  const withInput = reduceAppShellState(reduced, {
    type: "app_shell_workspace_path_changed",
    value: "D:/next",
  });
  assert.equal(withInput.workspacePathInput, "D:/next");
  assert.equal(withInput.workspaceError, "");

  const withSettings = reduceAppShellState(withInput, {
    type: "app_shell_settings_changed",
    patch: { confirm_workspace_switch: true, unknown: false },
  });
  assert.equal(withSettings.settings.confirm_workspace_switch, true);
  assert.equal(withSettings.settings.unknown, undefined);

  const reset = resetAppShellWorkspaceState({
    ...withSettings,
    activatingWorkspace: true,
    workspaceError: "old",
    workspacePathInput: "D:/old",
  });
  assert.equal(reset.activeWorkspace, null);
  assert.equal(reset.hasActiveWorkspace, false);
  assert.equal(reset.activatingWorkspace, false);
  assert.equal(reset.workspaceError, "");
  assert.equal(reset.workspacePathInput, "");
  assert.equal(reset.settings.confirm_workspace_switch, true);
  assert.equal(reset.capabilities.appCommands.includes("app.settings"), true);

  const rows = formatDiagnosticsRows({
    host: { platform: "win32", headless: false },
    runtime: { runtime_source: "bundle" },
    renderer: { renderer: "edgechromium" },
    workspace_registry: { count: 1 },
    active_core: { present: true },
  });
  assert.deepEqual(
    rows.map((row) => row.key),
    [
      "platform",
      "headless",
      "runtime_source",
      "renderer",
      "count",
      "present",
    ],
  );
  assert.equal(rows[0].group, "host");
  assert.equal(rows[0].value, "win32");
}
