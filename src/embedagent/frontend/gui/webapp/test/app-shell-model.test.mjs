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
  assert.deepEqual(initial.capabilities.chrome, {
    brandSubtitle: "",
    sidebarAriaLabel: "",
    threadPanelAriaLabel: "",
    header: {
      commandPaletteLabel: "",
      commandPaletteShortLabel: "",
      refreshLabel: "",
      bottomDrawerLabel: "",
      bottomDrawerTitle: "",
      rightPanelLabel: "",
      rightPanelTitle: "",
      turnsLabel: "",
    },
    composer: {
      placeholder: "",
      commandPaletteLabel: "",
      sendLabel: "",
      stopLabel: "",
      hints: {},
      commandMenu: {
        pathGroupLabel: "",
        commandGroupFallbackLabel: "",
        pathEmptyText: "",
        commandEmptyText: "",
        defaultEmptyText: "",
        pathAriaLabel: "",
        commandAriaLabel: "",
        pathItemKindLabel: "",
        commandItemKindLabel: "",
      },
    },
    interaction: {
      pendingApprovalKicker: "",
      inputRequiredKicker: "",
      commandApprovalSummary: "",
      fileReadApprovalSummary: "",
      fileChangeApprovalSummary: "",
      expiredTitle: "",
      expiredBody: "",
      conflictTitle: "",
      conflictBody: "",
      approveOnceLabel: "",
      declineLabel: "",
      cancelTurnLabel: "",
      alwaysAllowSessionLabel: "",
      inputSummary: "",
      customAnswerPlaceholder: "",
      submitLabel: "",
      modeLabelPrefix: "",
    },
    surfacePanel: {
      ariaLabel: "",
      settingsTitle: "",
      confirmWorkspaceSwitchLabel: "",
      showDiagnosticsBadgeLabel: "",
      diagnosticsTitle: "",
      capabilitiesTitle: "",
      noDiagnostics: "",
      planTitle: "",
      noPlan: "",
      diagnosticGroups: {},
    },
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
    bottomDrawerAriaLabel: "",
    runOutputEmptyMessage: "",
    terminationReasonPrefix: "",
    filePreview: {
      defaultFileTitle: "",
      defaultProjectLabel: "",
      loadingMessage: "",
      unavailableMessage: "",
      retryLabel: "",
      copyPathTitleTemplate: "",
      showMarkdownSourceLabel: "",
      showRenderedMarkdownLabel: "",
      showFileExplorerLabel: "",
      metadataSeparator: "",
      lineSingularLabel: "",
      linePluralLabel: "",
      plainLanguageLabel: "",
      languageLabels: {},
    },
    diffPanel: {
      defaultTitle: "",
      emptyMessage: "",
      selectionAriaLabel: "",
      controlsAriaLabel: "",
      stackedTitle: "",
      splitTitle: "",
      enableWordWrapTitle: "",
      disableWordWrapTitle: "",
      hideWhitespaceTitle: "",
      showWhitespaceTitle: "",
      changedFilesAriaLabel: "",
      filesLabel: "",
      expandFileLabelTemplate: "",
      collapseFileLabelTemplate: "",
      expandDiffLabel: "",
      sourceControlTitleTemplate: "",
    },
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
  assert.deepEqual(initial.capabilities.terminal.chrome, {
    titlePrefix: "",
    defaultTitle: "",
    sessionRequiredNotice: "",
    openFailedNotice: "",
    writeFailedNotice: "",
    clearFailedNotice: "",
    restartFailedNotice: "",
    closeFailedNotice: "",
    newLabel: "",
    newTitle: "",
    splitLabel: "",
    splitTitle: "",
    splitVerticalLabel: "",
    splitVerticalTitle: "",
    drawerLabel: "",
    unavailableMessage: "",
    commandPlaceholder: "",
    clearLabel: "",
    restartLabel: "",
    closeLabel: "",
    emptyMessage: "",
    emptyActionLabel: "",
  });
  assert.equal(initial.capabilities.preview.enabled, false);
  assert.deepEqual(initial.capabilities.preview.localServers, []);
  assert.equal(initial.capabilities.preview.chrome.refreshLabel, "");
  assert.equal(initial.capabilities.preview.chrome.emptyTitle, "");
  assert.equal(initial.capabilities.sourceControl.enabled, false);
  assert.equal(initial.capabilities.sourceControl.readOnly, true);
  assert.deepEqual(initial.capabilities.sourceControl.chrome, {
    title: "",
    statusUnavailableNotice: "",
    diffUnavailableNotice: "",
    loadingMessage: "",
    gitUnavailableMessage: "",
    notRepositoryMessage: "",
    cleanMessage: "",
    noBranchLabel: "",
    runtimeGitLabel: "",
    missingRuntimeLabel: "",
    refreshLabel: "",
    countLabels: {},
    groupLabels: {},
    providerLabels: {},
    branchToolbar: {
      defaultWorkspaceLabel: "",
      loadingLabel: "",
      errorLabel: "",
      gitUnavailableLabel: "",
      notRepositoryLabel: "",
      unknownRefLabel: "",
      detachedPrefix: "",
      cleanLabel: "",
      changeSingular: "",
      changePlural: "",
      conflictSingular: "",
      conflictPlural: "",
      currentCheckoutLabel: "",
      currentCheckoutDescription: "",
      gitUnavailableReason: "",
      notRepositoryReason: "",
      errorReasonFallback: "",
      readOnlyActionTitle: "",
      worktreeActionLabel: "",
      branchActionLabel: "",
      refreshLabel: "",
      refreshTitle: "",
      metadataSeparator: "",
    },
  });
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
      chrome: {
        brand_subtitle: "Python agent workbench",
        sidebar_aria_label: "Project sidebar",
        thread_panel_aria_label: "Runs",
        header: {
          command_palette_label: "Launcher",
          command_palette_short_label: "Go",
          refresh_label: "Refresh runs",
          bottom_drawer_label: "Output",
          bottom_drawer_title: "Toggle output",
          right_panel_label: "Views",
          right_panel_title: "Toggle views",
          turns_label: "steps",
        },
        composer: {
          placeholder: "Ask the Python agent",
          command_palette_label: "Open launcher",
          send_label: "Send prompt",
          stop_label: "Stop prompt",
          command_menu: {
            path_group_label: "Project files",
            command_group_fallback_label: "Action",
            path_empty_text: "No project files",
            command_empty_text: "No actions",
            default_empty_text: "Nothing here",
            path_aria_label: "Project file suggestions",
            command_aria_label: "Action suggestions",
            path_item_kind_label: "path",
            command_item_kind_label: "action",
          },
          hints: {
            command: "/ actions",
            file: "@ paths",
          },
        },
        interaction: {
          pending_approval_kicker: "APPROVAL",
          input_required_kicker: "ANSWER",
          command_approval_summary: "Command summary",
          file_read_approval_summary: "Read summary",
          file_change_approval_summary: "Change summary",
          expired_title: "Request expired",
          expired_body: "Request body.",
          conflict_title: "Request handled",
          conflict_body: "Conflict body.",
          approve_once_label: "Approve action",
          decline_label: "Decline action",
          cancel_turn_label: "Cancel run",
          always_allow_session_label: "Always allow",
          input_summary: "Input summary",
          custom_answer_placeholder: "Custom answer",
          submit_label: "Send answer",
          mode_label_prefix: "mode",
        },
        surface_panel: {
          aria_label: "View panel",
          settings_title: "Preferences",
          confirm_workspace_switch_label: "Confirm project switch",
          show_diagnostics_badge_label: "Show health badge",
          diagnostics_title: "Health",
          capabilities_title: "Declared capabilities",
          no_diagnostics: "No health rows.",
          plan_title: "Run plan",
          no_plan: "No run plan.",
          diagnostic_groups: {
            host: "Host process",
          },
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
          bottom_drawer_aria_label: "Output drawer",
          run_output_empty_message: "No output yet.",
          termination_reason_prefix: "finished",
          file_preview: {
            default_file_title: "Document",
            default_project_label: "Project",
            loading_message: "Opening file",
            unavailable_message: "Document unavailable",
            retry_label: "Reload file",
            copy_path_title_template: "Copy path for {title}",
            show_markdown_source_label: "Show source",
            show_rendered_markdown_label: "Show preview",
            show_file_explorer_label: "Open explorer",
            metadata_separator: " | ",
            line_singular_label: "row",
            line_plural_label: "rows",
            plain_language_label: "Plain text",
            language_labels: {
              markdown: "Markdown doc",
              python: "Python file",
            },
          },
          diff_panel: {
            default_title: "Patch",
            empty_message: "No patch selected.",
            selection_aria_label: "Patch tabs",
            controls_aria_label: "Patch controls",
            stacked_title: "Unified view",
            split_title: "Side by side",
            enable_word_wrap_title: "Wrap patch lines",
            disable_word_wrap_title: "Unwrap patch lines",
            hide_whitespace_title: "Ignore whitespace",
            show_whitespace_title: "Show whitespace",
            changed_files_aria_label: "Patch files",
            files_label: "Paths",
            expand_file_label_template: "Open {path}",
            collapse_file_label_template: "Close {path}",
            expand_diff_label: "Show patch",
            source_control_title_template: "Patch: {path}",
          },
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
        chrome: {
          title: "Git Changes",
          status_unavailable_notice: "Git status failed.",
          diff_unavailable_notice: "No diff available.",
          loading_message: "Checking changes...",
          git_unavailable_message: "Git missing.",
          not_repository_message: "Not a Git repository.",
          clean_message: "Working tree clean.",
          no_branch_label: "No ref",
          runtime_git_label: "git",
          missing_runtime_label: "missing",
          refresh_label: "Reload",
          count_labels: {
            files: "paths",
            staged: "indexed",
            changed: "modified",
            untracked: "new",
          },
          group_labels: {
            staged: "Indexed",
            unstaged: "Modified",
            untracked: "New files",
            conflicted: "Conflicted",
            fallback: "Modified",
          },
          provider_labels: {
            github: "GitHub",
            local: "Local Git",
            fallback: "Local provider",
          },
          branch_toolbar: {
            default_workspace_label: "Project",
            loading_label: "Scanning Git",
            error_label: "Git check failed",
            git_unavailable_label: "Git missing",
            not_repository_label: "Not a repository",
            unknown_ref_label: "Unknown checkout",
            detached_prefix: "at",
            clean_label: "Settled",
            change_singular: "delta",
            change_plural: "deltas",
            conflict_singular: "collision",
            conflict_plural: "collisions",
            current_checkout_label: "Checkout",
            current_checkout_description: "Use the active checkout.",
            git_unavailable_reason: "No local Git runtime.",
            not_repository_reason: "Open a repository workspace.",
            error_reason_fallback: "Git status failed.",
            read_only_action_title: "Read-only shell action.",
            worktree_action_label: "Tree",
            branch_action_label: "Ref",
            refresh_label: "Poll",
            refresh_title: "Poll Git status",
            metadata_separator: " / ",
          },
        },
      },
      terminal: {
        enabled: true,
        pty: false,
        resize: false,
        history_persistent: false,
        max_buffer_bytes: 131072,
        chrome: {
          title_prefix: "Shell",
          default_title: "Shell",
          session_required_notice: "Open a run before using shell.",
          open_failed_notice: "Shell failed to open.",
          write_failed_notice: "Shell write failed.",
          clear_failed_notice: "Shell clear failed.",
          restart_failed_notice: "Shell restart failed.",
          close_failed_notice: "Shell close failed.",
          new_label: "New shell",
          new_title: "Create shell",
          split_label: "Split shell",
          split_title: "Split shell horizontally",
          split_vertical_label: "Split V",
          split_vertical_title: "Split shell vertically",
          drawer_label: "Shell drawer",
          unavailable_message: "Shell session unavailable.",
          command_placeholder: "Type shell command",
          clear_label: "Clear shell",
          restart_label: "Restart shell",
          close_label: "Close shell",
          empty_message: "No shell sessions.",
          empty_action_label: "Start shell",
        },
      },
      preview: {
        enabled: true,
        local_servers: [
          { label: "Django dev server", url: "localhost:8000", port: 8000 },
        ],
        chrome: {
          refresh_label: "Reload preview",
          loading_label: "Loading preview",
          refresh_aria_label: "Reload embedded preview",
          loading_aria_label: "Preview is loading",
          url_placeholder: "Preview URL",
          url_aria_label: "Preview address",
          open_external_label: "Open outside",
          annotate_label: "Mark up preview",
          more_actions_label: "More preview options",
          unavailable_title: "Preview not available",
          unavailable_body: "Embedded preview cannot render this page.",
          unreachable_body: "The preview target is not reachable.",
          reload_label: "Try again",
          failed_notice: "Preview request failed.",
          refresh_failed_notice: "Preview reload failed.",
          open_failed_notice: "Preview external open failed.",
          session_required_notice: "Open a run before preview.",
          servers_title: "Detected servers",
          empty_title: "No active preview",
          servers_description: "Choose a server.",
          empty_description: "Start a server or enter a URL.",
          local_server_fallback_label: "Server",
          status_loading: "Loading",
          status_ready: "Ready",
          status_failed: "Unavailable",
          status_idle: "Idle",
        },
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
  assert.equal(bootstrap.capabilities.chrome.brandSubtitle, "Python agent workbench");
  assert.equal(bootstrap.capabilities.chrome.sidebarAriaLabel, "Project sidebar");
  assert.equal(bootstrap.capabilities.chrome.header.commandPaletteShortLabel, "Go");
  assert.equal(bootstrap.capabilities.chrome.header.turnsLabel, "steps");
  assert.equal(bootstrap.capabilities.chrome.composer.placeholder, "Ask the Python agent");
  assert.equal(bootstrap.capabilities.chrome.composer.commandMenu.pathGroupLabel, "Project files");
  assert.equal(bootstrap.capabilities.chrome.composer.commandMenu.commandGroupFallbackLabel, "Action");
  assert.equal(bootstrap.capabilities.chrome.composer.commandMenu.commandEmptyText, "No actions");
  assert.equal(bootstrap.capabilities.chrome.composer.commandMenu.commandItemKindLabel, "action");
  assert.equal(bootstrap.capabilities.chrome.composer.hints.command, "/ actions");
  assert.equal(bootstrap.capabilities.chrome.interaction.pendingApprovalKicker, "APPROVAL");
  assert.equal(bootstrap.capabilities.chrome.interaction.commandApprovalSummary, "Command summary");
  assert.equal(bootstrap.capabilities.chrome.interaction.alwaysAllowSessionLabel, "Always allow");
  assert.equal(bootstrap.capabilities.chrome.interaction.customAnswerPlaceholder, "Custom answer");
  assert.equal(bootstrap.capabilities.chrome.surfacePanel.ariaLabel, "View panel");
  assert.equal(bootstrap.capabilities.chrome.surfacePanel.diagnosticGroups.host, "Host process");
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
  assert.equal(bootstrap.capabilities.surfaces.chrome.bottomDrawerAriaLabel, "Output drawer");
  assert.equal(bootstrap.capabilities.surfaces.chrome.runOutputEmptyMessage, "No output yet.");
  assert.equal(bootstrap.capabilities.surfaces.chrome.terminationReasonPrefix, "finished");
  assert.equal(bootstrap.capabilities.surfaces.chrome.filePreview.defaultFileTitle, "Document");
  assert.equal(bootstrap.capabilities.surfaces.chrome.filePreview.defaultProjectLabel, "Project");
  assert.equal(bootstrap.capabilities.surfaces.chrome.filePreview.loadingMessage, "Opening file");
  assert.equal(
    bootstrap.capabilities.surfaces.chrome.filePreview.copyPathTitleTemplate,
    "Copy path for {title}",
  );
  assert.equal(bootstrap.capabilities.surfaces.chrome.filePreview.languageLabels.markdown, "Markdown doc");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.defaultTitle, "Patch");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.emptyMessage, "No patch selected.");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.selectionAriaLabel, "Patch tabs");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.controlsAriaLabel, "Patch controls");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.stackedTitle, "Unified view");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.splitTitle, "Side by side");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.enableWordWrapTitle, "Wrap patch lines");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.disableWordWrapTitle, "Unwrap patch lines");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.hideWhitespaceTitle, "Ignore whitespace");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.showWhitespaceTitle, "Show whitespace");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.changedFilesAriaLabel, "Patch files");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.filesLabel, "Paths");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.expandFileLabelTemplate, "Open {path}");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.collapseFileLabelTemplate, "Close {path}");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.expandDiffLabel, "Show patch");
  assert.equal(bootstrap.capabilities.surfaces.chrome.diffPanel.sourceControlTitleTemplate, "Patch: {path}");
  assert.deepEqual(
    bootstrap.capabilities.surfaces.bottomDrawer.map((item) => item.kind),
    ["terminal"],
  );
  assert.equal(bootstrap.capabilities.terminal.chrome.titlePrefix, "Shell");
  assert.equal(bootstrap.capabilities.terminal.chrome.newLabel, "New shell");
  assert.equal(bootstrap.capabilities.terminal.chrome.openFailedNotice, "Shell failed to open.");
  assert.equal(bootstrap.capabilities.terminal.chrome.commandPlaceholder, "Type shell command");
  assert.equal(bootstrap.capabilities.preview.enabled, true);
  assert.deepEqual(bootstrap.capabilities.preview.localServers, [
    {
      label: "Django dev server",
      url: "localhost:8000",
      port: 8000,
    },
  ]);
  assert.equal(bootstrap.capabilities.preview.chrome.refreshLabel, "Reload preview");
  assert.equal(bootstrap.capabilities.preview.chrome.openExternalLabel, "Open outside");
  assert.equal(bootstrap.capabilities.preview.chrome.sessionRequiredNotice, "Open a run before preview.");
  assert.equal(bootstrap.capabilities.preview.chrome.emptyTitle, "No active preview");
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
  assert.equal(bootstrap.capabilities.sourceControl.chrome.title, "Git Changes");
  assert.equal(
    bootstrap.capabilities.sourceControl.chrome.statusUnavailableNotice,
    "Git status failed.",
  );
  assert.equal(
    bootstrap.capabilities.sourceControl.chrome.diffUnavailableNotice,
    "No diff available.",
  );
  assert.equal(bootstrap.capabilities.sourceControl.chrome.loadingMessage, "Checking changes...");
  assert.equal(bootstrap.capabilities.sourceControl.chrome.noBranchLabel, "No ref");
  assert.equal(bootstrap.capabilities.sourceControl.chrome.countLabels.files, "paths");
  assert.equal(bootstrap.capabilities.sourceControl.chrome.groupLabels.unstaged, "Modified");
  assert.equal(
    bootstrap.capabilities.sourceControl.chrome.providerLabels.fallback,
    "Local provider",
  );
  assert.equal(
    bootstrap.capabilities.sourceControl.chrome.branchToolbar.defaultWorkspaceLabel,
    "Project",
  );
  assert.equal(bootstrap.capabilities.sourceControl.chrome.branchToolbar.detachedPrefix, "at");
  assert.equal(
    bootstrap.capabilities.sourceControl.chrome.branchToolbar.currentCheckoutLabel,
    "Checkout",
  );
  assert.equal(
    bootstrap.capabilities.sourceControl.chrome.branchToolbar.metadataSeparator,
    " / ",
  );
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
    chrome: {
      brand_subtitle: "Generic shell",
      composer: { placeholder: "Ask" },
    },
    terminal: {
      enabled: true,
      pty: false,
      resize: false,
      chrome: {
        title_prefix: "Console",
        default_title: "Console",
        new_label: "New console",
      },
    },
    preview: {
      enabled: true,
      local_servers: [{ label: "Flask", url: "localhost:5000", port: 5000 }],
      chrome: {
        refresh_label: "Refresh preview",
        empty_title: "No preview",
      },
    },
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
  assert.equal(capabilities.chrome.brandSubtitle, "Generic shell");
  assert.equal(capabilities.chrome.composer.placeholder, "Ask");
  assert.equal(capabilities.terminal.enabled, true);
  assert.equal(capabilities.terminal.pty, false);
  assert.equal(capabilities.terminal.resize, false);
  assert.equal(capabilities.terminal.chrome.titlePrefix, "Console");
  assert.equal(capabilities.terminal.chrome.defaultTitle, "Console");
  assert.equal(capabilities.terminal.chrome.newLabel, "New console");
  assert.equal(capabilities.preview.enabled, true);
  assert.deepEqual(capabilities.preview.localServers, [
    { label: "Flask", url: "localhost:5000", port: 5000 },
  ]);
  assert.equal(capabilities.preview.chrome.refreshLabel, "Refresh preview");
  assert.equal(capabilities.preview.chrome.emptyTitle, "No preview");

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
  assert.equal(emptyCapabilities.preview.enabled, false);
  assert.deepEqual(emptyCapabilities.preview.localServers, []);

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
