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
  assert.deepEqual(initial.capabilities.workbenchCommands, []);
  assert.deepEqual(initial.capabilities.commandPalette.groups, []);
  assert.deepEqual(initial.capabilities.commandPalette.labels, {
    rootTitle: "",
    submenuTitle: "",
    searchLabel: "",
    rootPlaceholder: "",
    submenuPlaceholder: "",
    rootEmpty: "",
    submenuEmpty: "",
    commandsSection: "",
    sessionsSection: "",
    workspacesSection: "",
    currentLabel: "",
    missingLabel: "",
    workspaceMeta: "",
    workspaceFallback: "",
    sessionFallbackPrefix: "",
  });
  assert.deepEqual(initial.capabilities.surfaces.rightPanel, []);
  assert.deepEqual(initial.capabilities.surfaces.bottomDrawer, []);
  assert.deepEqual(initial.capabilities.surfaces.chrome, {
    rightPanelAriaLabel: "",
    addSurfaceLabel: "",
    emptyTitle: "",
    emptyBody: "",
    surfaceActionsLabelPrefix: "",
    closeLabelPrefix: "",
    closeActionLabel: "",
    closeOthersActionLabel: "",
    closeToRightActionLabel: "",
    closeAllActionLabel: "",
    defaultIcon: "",
  });
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
  assert.deepEqual(initial.capabilities.threadLifecycle.actions, []);
  assert.deepEqual(initial.capabilities.home.workspace, {
    sectionTitle: "",
    inactiveLabel: "",
    inactivePath: "",
    pathPlaceholder: "",
    openLabel: "",
    openAriaLabel: "",
    recentsLabel: "",
    missingPathLabel: "",
    removeLabel: "",
  });
  assert.deepEqual(initial.capabilities.home.threads, {
    sectionTitle: "",
    newLabel: "",
    emptyTitle: "",
    emptyBody: "",
    activeLabel: "",
    actionsLabelPrefix: "",
  });

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
      app_commands: [
        { id: "app.settings", label: "Preferences", group: "app", order: 10 },
        { id: "app.diagnostics", label: "Health", group: "app", order: 20 },
        { id: "app.reload", label: "Reload Shell", group: "app", order: 30 },
      ],
      workspace_commands: [
        { id: "workspace.open", label: "Open Project", group: "workspace", order: 10 },
      ],
      workbench_commands: [
        { id: "message.send", label: "Send", group: "message", visible_when: "composer_ready", order: 10 },
        { id: "palette.open", label: "Launch", group: "view", order: 20 },
      ],
      command_palette: {
        groups: [
          { id: "workspace", title: "Projects", description: "Project commands", order: 20 },
          { id: "app", title: "Application", description: "Application commands", order: 10 },
        ],
        labels: {
          root_title: "Command launcher",
          submenu_title: "Launcher group",
          search_label: "Search launcher",
          root_placeholder: "Search launcher entries",
          submenu_placeholder: "Search group entries",
          root_empty: "No launcher matches",
          submenu_empty: "No group matches",
          commands_section: "Actions",
          sessions_section: "Threads",
          workspaces_section: "Projects",
          current_label: "Selected",
          missing_label: "Unavailable",
          workspace_meta: "Project",
          workspace_fallback: "Project",
          session_fallback_prefix: "Thread",
        },
      },
      surfaces: {
        chrome: {
          right_panel_aria_label: "Workspace panel",
          add_surface_label: "Add workspace view",
          empty_title: "Open a workspace view",
          empty_body: "Choose a project surface.",
          surface_actions_label_prefix: "View actions for",
          close_label_prefix: "Close view",
          close_action_label: "Close view",
          close_others_action_label: "Close other views",
          close_to_right_action_label: "Close views to the right",
          close_all_action_label: "Close all views",
          default_icon: "V",
        },
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
      home: {
        workspace: {
          section_title: "Projects",
          inactive_label: "No project",
          inactive_path: "Choose a Python project",
          path_placeholder: "Python project path",
          open_label: "Open Project",
          open_aria_label: "Open Python project",
          recents_label: "Recent Python projects",
          missing_path_label: "Missing project path",
          remove_label: "Forget",
        },
        threads: {
          section_title: "Runs",
          new_label: "Start",
          empty_title: "No runs",
          empty_body: "Start a run for this project.",
          active_label: "current",
          actions_label_prefix: "Run actions for",
        },
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
      thread_lifecycle: {
        actions: [
          {
            id: "rename",
            label: "Retitle",
            capability: "rename",
            order: 20,
            prompt_title: "Rename prompt",
            empty_title: "Rename blocked",
            empty_body: "Title required.",
            failure_title: "Rename failed",
          },
          {
            id: "archive",
            label: "Hide",
            capability: "archive",
            order: 30,
            danger: true,
            confirm_title: "Archive prompt",
            success_title: "Archive complete",
            success_body: "Archive body.",
            failure_title: "Archive failed",
          },
          {
            id: "fork",
            label: "Clone",
            capability: "fork",
            order: 10,
            prompt_title: "Fork prompt",
            prompt_initial: "copy",
            failure_title: "Fork failed",
          },
        ],
      },
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
  assert.deepEqual(
    bootstrap.capabilities.appCommands.map((item) => [item.id, item.label]),
    [
      ["app.settings", "Preferences"],
      ["app.diagnostics", "Health"],
      ["app.reload", "Reload Shell"],
    ],
  );
  assert.deepEqual(
    bootstrap.capabilities.workspaceCommands.map((item) => [item.id, item.label]),
    [["workspace.open", "Open Project"]],
  );
  assert.deepEqual(
    bootstrap.capabilities.workbenchCommands.map((item) => [item.id, item.label, item.visibleWhen]),
    [
      ["message.send", "Send", "composer_ready"],
      ["palette.open", "Launch", "always"],
    ],
  );
  assert.deepEqual(
    bootstrap.capabilities.commandPalette.groups.map((item) => [item.id, item.title, item.description]),
    [
      ["app", "Application", "Application commands"],
      ["workspace", "Projects", "Project commands"],
    ],
  );
  assert.equal(bootstrap.capabilities.commandPalette.labels.rootTitle, "Command launcher");
  assert.equal(bootstrap.capabilities.commandPalette.labels.rootPlaceholder, "Search launcher entries");
  assert.equal(bootstrap.capabilities.commandPalette.labels.commandsSection, "Actions");
  assert.equal(bootstrap.capabilities.commandPalette.labels.currentLabel, "Selected");
  assert.equal(bootstrap.capabilities.commandPalette.labels.workspaceMeta, "Project");
  assert.deepEqual(
    bootstrap.capabilities.surfaces.rightPanel.map((item) => item.kind),
    ["settings", "diagnostics", "source_control"],
  );
  assert.equal(bootstrap.capabilities.surfaces.rightPanel[0].title, "Settings");
  assert.equal(bootstrap.capabilities.surfaces.chrome.rightPanelAriaLabel, "Workspace panel");
  assert.equal(bootstrap.capabilities.surfaces.chrome.addSurfaceLabel, "Add workspace view");
  assert.equal(bootstrap.capabilities.surfaces.chrome.emptyTitle, "Open a workspace view");
  assert.equal(bootstrap.capabilities.surfaces.chrome.closeAllActionLabel, "Close all views");
  assert.equal(bootstrap.capabilities.surfaces.chrome.defaultIcon, "V");
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
  assert.equal(bootstrap.capabilities.home.workspace.sectionTitle, "Projects");
  assert.equal(bootstrap.capabilities.home.workspace.inactiveLabel, "No project");
  assert.equal(bootstrap.capabilities.home.workspace.pathPlaceholder, "Python project path");
  assert.equal(bootstrap.capabilities.home.workspace.openLabel, "Open Project");
  assert.equal(bootstrap.capabilities.home.workspace.missingPathLabel, "Missing project path");
  assert.equal(bootstrap.capabilities.home.threads.sectionTitle, "Runs");
  assert.equal(bootstrap.capabilities.home.threads.newLabel, "Start");
  assert.equal(bootstrap.capabilities.home.threads.activeLabel, "current");
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
  assert.deepEqual(
    bootstrap.capabilities.threadLifecycle.actions.map((item) => ({
      id: item.id,
      label: item.label,
      capability: item.capability,
      order: item.order,
      danger: item.danger,
    })),
    [
      { id: "fork", label: "Clone", capability: "fork", order: 10, danger: false },
      { id: "rename", label: "Retitle", capability: "rename", order: 20, danger: false },
      { id: "archive", label: "Hide", capability: "archive", order: 30, danger: true },
    ],
  );
  assert.equal(bootstrap.capabilities.threadLifecycle.actions[0].promptTitle, "Fork prompt");
  assert.equal(bootstrap.capabilities.threadLifecycle.actions[0].promptInitial, "copy");
  assert.equal(bootstrap.capabilities.threadLifecycle.actions[1].promptTitle, "Rename prompt");
  assert.equal(bootstrap.capabilities.threadLifecycle.actions[1].emptyTitle, "Rename blocked");
  assert.equal(bootstrap.capabilities.threadLifecycle.actions[1].emptyBody, "Title required.");
  assert.equal(bootstrap.capabilities.threadLifecycle.actions[2].confirmTitle, "Archive prompt");
  assert.equal(bootstrap.capabilities.threadLifecycle.actions[2].successTitle, "Archive complete");
  assert.equal(bootstrap.capabilities.threadLifecycle.actions[2].successBody, "Archive body.");
  assert.equal(bootstrap.capabilities.threadLifecycle.actions[2].failureTitle, "Archive failed");
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
    app_commands: [{ id: "app.settings", label: "Preferences", group: "app" }],
    workspace_commands: [{ id: "workspace.open", label: "Open Project", group: "workspace" }],
    workbench_commands: [{ id: "palette.open", label: "Launch", group: "view" }],
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
  assert.deepEqual(
    capabilities.appCommands.map((item) => [item.id, item.label, item.group]),
    [["app.settings", "Preferences", "app"]],
  );
  assert.deepEqual(
    capabilities.workspaceCommands.map((item) => [item.id, item.label, item.group]),
    [["workspace.open", "Open Project", "workspace"]],
  );
  assert.deepEqual(
    capabilities.workbenchCommands.map((item) => [item.id, item.label, item.group]),
    [["palette.open", "Launch", "view"]],
  );
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
  assert.deepEqual(emptyCapabilities.workbenchCommands, []);
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
  assert.equal(reset.capabilities.appCommands.some((item) => item.id === "app.settings"), true);

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
