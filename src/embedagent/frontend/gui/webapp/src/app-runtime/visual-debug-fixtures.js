import { createDiffSurfaceState } from "../session-runtime/diff-model.js";

const VISUAL_WORKSPACE = Object.freeze({
  id: "visual-debug-workspace",
  path: "D:/visual-debug",
  label: "visual-debug",
  exists: true,
  created_at: "",
  last_opened_at: "",
});

function surface(id, title, launcherOrder) {
  return { id, title, launcher_order: launcherOrder, command_label: `Open ${title}` };
}

function keybinding(key, commandId, when = "always") {
  return { key, command_id: commandId, when };
}

function visualAppBootstrap() {
  return {
    app: { shell_version: 1, product_name: "EmbedAgent", protocol: "gui_app_shell_v1" },
    workspaces: [VISUAL_WORKSPACE],
    active_workspace: VISUAL_WORKSPACE,
    has_active_workspace: true,
    capabilities: {
      app_commands: [
        { id: "app.settings", label: "Open Settings", group: "app", order: 10, surface: "settings" },
        { id: "app.diagnostics", label: "Open Diagnostics", group: "app", order: 20, surface: "diagnostics" },
        { id: "app.source_control", label: "Open Source Control", group: "app", order: 30, surface: "source_control" },
        { id: "app.reload", label: "Reload App Shell", group: "app", order: 40 },
      ],
      workspace_commands: [
        { id: "workspace.open", label: "Open Workspace", group: "workspace", order: 10 },
        { id: "workspace.refresh", label: "Refresh Workspaces", group: "workspace", order: 20 },
        { id: "workspace.remove_current", label: "Remove Current Workspace From Recents", group: "workspace", order: 30, visible_when: "has_workspace" },
      ],
      workbench_commands: [
        { id: "session.new", label: "New Session", group: "session", order: 10, slash: "/new" },
        { id: "thread.new", label: "New Thread", group: "session", order: 20, keywords: ["session", "chat"] },
        { id: "session.refresh", label: "Refresh Sessions", group: "session", order: 30, slash: "/sessions" },
        { id: "session.resume", label: "Resume Session", group: "session", order: 40, slash: "/resume" },
        { id: "message.send", label: "Send Message", group: "message", order: 10, visible_when: "composer_ready" },
        { id: "message.stop", label: "Stop Running Turn", group: "message", order: 20, visible_when: "running" },
        { id: "view.toggle_right_panel", label: "Toggle Right Panel", group: "view", order: 10 },
        { id: "view.toggle_bottom_drawer", label: "Toggle Bottom Drawer", group: "view", order: 20 },
        { id: "palette.open", label: "Open Command Palette", group: "view", order: 30 },
        { id: "palette.close", label: "Close Command Palette", group: "view", order: 40, visible_when: "palette_open" },
      ],
      command_palette: {
        groups: [
          { id: "app", title: "App", description: "App shell commands", order: 10 },
          { id: "session", title: "Sessions", description: "Create, refresh, and resume threads", order: 20 },
          { id: "message", title: "Message", description: "Send or stop the current turn", order: 30 },
          { id: "mode", title: "Mode", description: "Switch the active agent mode", order: 40 },
          { id: "surface", title: "Surface", description: "Open workbench surfaces", order: 50 },
          { id: "workspace", title: "Workspace", description: "Open or refresh local workspaces", order: 60 },
          { id: "workflow", title: "Workflow", description: "Run workflow views", order: 70 },
          { id: "view", title: "View", description: "Toggle workbench layout", order: 80 },
        ],
        labels: {
          root_title: "Command palette",
          submenu_title: "Command group",
          search_label: "Command search",
          root_placeholder: "Search commands, sessions, workspaces",
          submenu_placeholder: "Search this group",
          root_empty: "No matching commands, sessions, or workspaces",
          submenu_empty: "No matching commands in this group",
          commands_section: "Commands",
          sessions_section: "Sessions",
          workspaces_section: "Workspaces",
          current_label: "Current",
          missing_label: "Missing",
          workspace_meta: "Workspace",
          workspace_fallback: "Workspace",
          session_fallback_prefix: "Session",
        },
      },
      chrome: {
        brand_subtitle: "Local agent workbench",
        sidebar_aria_label: "Sidebar",
        thread_panel_aria_label: "Chats",
        header: {
          command_palette_label: "Command palette",
          command_palette_short_label: "Cmd",
          refresh_label: "Refresh",
          bottom_drawer_label: "Run",
          bottom_drawer_title: "Toggle run output",
          right_panel_label: "Panel",
          right_panel_title: "Toggle right panel",
          turns_label: "turns",
        },
        composer: {
          placeholder: "Message",
          command_palette_label: "Open command palette",
          send_label: "Send",
          stop_label: "Stop",
          hints: {
            command: "/ commands",
            file: "@ files",
            select: "select",
            newline: "Shift+Enter newline",
            "status.running": "running turns disable editing",
            "status.interaction": "interaction pending",
          },
        },
        interaction: {
          pending_approval_kicker: "PENDING APPROVAL",
          input_required_kicker: "INPUT REQUIRED",
          command_approval_summary: "Command approval requested",
          file_read_approval_summary: "File-read approval requested",
          file_change_approval_summary: "File-change approval requested",
          expired_title: "Interaction expired",
          expired_body: "This request is no longer active. Trigger the action again to continue.",
          conflict_title: "Interaction already handled",
          conflict_body: "This request changed in another flow. Refresh the current interaction and try again if needed.",
          approve_once_label: "Approve once",
          decline_label: "Decline",
          cancel_turn_label: "Cancel turn",
          always_allow_session_label: "Always allow this session",
          input_summary: "Input requested",
          custom_answer_placeholder: "Or type a custom answer...",
          submit_label: "Submit",
          mode_label_prefix: "mode:",
        },
        surface_panel: {
          aria_label: "Surface panel",
          settings_title: "Settings",
          confirm_workspace_switch_label: "Confirm workspace switch",
          show_diagnostics_badge_label: "Show diagnostics badge",
          diagnostics_title: "Diagnostics",
          capabilities_title: "Capabilities",
          no_diagnostics: "No app diagnostics loaded.",
          plan_title: "Plan",
          no_plan: "No active plan in this session.",
          diagnostic_groups: {
            host: "Host",
            runtime: "Runtime",
            renderer: "Renderer",
            workspace_registry: "Workspace Registry",
            active_core: "Active Core",
          },
        },
      },
      thread_lifecycle: {
        actions: [
          {
            id: "rename",
            label: "Rename",
            capability: "rename",
            order: 10,
            prompt_title: "Rename thread",
            empty_title: "Rename failed",
            empty_body: "Thread title cannot be empty.",
            failure_title: "Rename failed",
          },
          {
            id: "fork",
            label: "Fork",
            capability: "fork",
            order: 20,
            prompt_title: "Fork thread title",
            prompt_initial: "",
            failure_title: "Fork failed",
          },
          {
            id: "archive",
            label: "Archive",
            capability: "archive",
            order: 30,
            danger: true,
            confirm_title: "Archive this thread?",
            success_title: "Thread archived",
            success_body: "The thread was archived and hidden from the normal thread list.",
            failure_title: "Archive failed",
          },
        ],
      },
      home: {
        workspace: {
          section_title: "Project",
          inactive_label: "No workspace",
          inactive_path: "Open a local project",
          path_placeholder: "Workspace path",
          open_label: "Open",
          open_aria_label: "Open workspace",
          recents_label: "Recent projects",
          missing_path_label: "Missing path",
          remove_label: "Remove",
        },
        threads: {
          section_title: "Threads",
          new_label: "New",
          empty_title: "No threads yet",
          empty_body: "Start one for this project.",
          active_label: "active",
          actions_label_prefix: "Thread actions for",
        },
      },
      surfaces: {
        chrome: {
          right_panel_aria_label: "Right panel",
          add_surface_label: "Add panel surface",
          empty_title: "Open a surface",
          empty_body: "Choose what to show in the right panel.",
          surface_actions_label_prefix: "Surface actions for",
          close_label_prefix: "Close",
          close_action_label: "Close",
          close_others_action_label: "Close others",
          close_to_right_action_label: "Close to the right",
          close_all_action_label: "Close all",
          default_icon: "S",
        },
        right_panel: [
          surface("preview", "Preview", 10),
          surface("files", "Files", 20),
          surface("terminal", "Terminal", 30),
          surface("diff", "Diff", 40),
          surface("plan", "Plan", 50),
          surface("source_control", "Source Control", 60),
          surface("settings", "Settings", 70),
          surface("diagnostics", "Diagnostics", 80),
        ],
        bottom_drawer: [
          surface("run_output", "Run Output", 10),
          surface("terminal", "Terminal", 20),
          surface("logs", "Logs", 30),
        ],
      },
      keybindings: [
        keybinding("mod+k", "palette.open", "not_palette"),
        keybinding("escape", "palette.close", "palette"),
        keybinding("escape", "message.stop", "running"),
        keybinding("mod+b", "view.toggle_right_panel"),
        keybinding("mod+,", "app.settings"),
        keybinding("mod+j", "view.toggle_bottom_drawer"),
        keybinding("mod+1", "surface.files"),
        keybinding("mod+2", "surface.terminal"),
        keybinding("mod+3", "surface.diff"),
        keybinding("mod+4", "surface.preview"),
        keybinding("mod+enter", "message.send", "composer"),
      ],
      terminal: { enabled: true, pty: false, resize: false, history_persistent: false, max_buffer_bytes: 200000 },
      source_control: {
        enabled: true,
        vcs: ["git"],
        read_only: true,
        remote_providers: false,
        network: false,
        checkpoints: false,
        requires_active_workspace: true,
      },
    },
    settings: { confirm_workspace_switch: true, show_diagnostics_badge: true },
  };
}

function ensureVisualWorkspace(dispatch) {
  dispatch({ type: "app_shell_bootstrap_loaded", bootstrap: visualAppBootstrap() });
}

function dispatchTimelineFixture(dispatch, action) {
  ensureVisualWorkspace(dispatch);
  const sessionId = action.sessionId || action.snapshot?.session_id || "visual-debug-session";
  const snapshot = action.snapshot || {
    session_id: sessionId,
    status: "idle",
    current_mode: "explore",
    pending_interaction_valid: false,
  };
  dispatch({
    type: "session_activated",
    sessionId,
    snapshot,
    activities: Array.isArray(action.timeline) ? action.timeline : [],
    historyIntegrity: null,
  });
  for (const [path, preview] of Object.entries(action.previews || {})) {
    dispatch({
      type: "file_preview_loaded",
      path,
      preview: {
        title: preview.title || path,
        content: preview.content || "",
      },
    });
  }
  if (action.activeTurnId || action.activeStepId) {
    dispatch({
      type: "step_started",
      turnId: action.activeTurnId || "",
      stepId: action.activeStepId || "",
      stepIndex: action.activeStepIndex || 0,
    });
  }
  if (action.thinkingActive) {
    dispatch({ type: "thinking_state", active: true });
  }
}

function dispatchInteractionFixture(dispatch, action) {
  ensureVisualWorkspace(dispatch);
  const sessionId = action.sessionId || "visual-debug-interaction";
  const pendingInteraction = action.permission || action.userInput || null;
  dispatch({
    type: "session_activated",
    sessionId,
    snapshot: {
      session_id: sessionId,
      status: pendingInteraction?.kind === "user_input" ? "waiting_user_input" : "waiting_permission",
      current_mode: "explore",
      pending_interaction_valid: Boolean(pendingInteraction),
      pending_interaction: pendingInteraction,
    },
    activities: [],
    historyIntegrity: null,
  });
}

function dispatchThreadFixture(dispatch, action) {
  ensureVisualWorkspace(dispatch);
  const sessionId = action.sessionId || "visual-thread-active";
  dispatch({ type: "sessions_loaded", sessions: Array.isArray(action.sessions) ? action.sessions : [] });
  dispatch({
    type: "session_activated",
    sessionId,
    snapshot: {
      session_id: sessionId,
      status: "idle",
      current_mode: "explore",
      pending_interaction_valid: false,
    },
    activities: [],
    historyIntegrity: null,
  });
}

function dispatchSourceControlFixture(dispatch, action) {
  ensureVisualWorkspace(dispatch);
  dispatch({ type: "source_control_status_loaded", status: action.status || {} });
}

function dispatchFileTreeFixture(dispatch, action) {
  ensureVisualWorkspace(dispatch);
  dispatch({ type: "file_tree_loaded", nodes: Array.isArray(action.nodes) ? action.nodes : [] });
}

function dispatchFilePreviewFixture(dispatch, action) {
  ensureVisualWorkspace(dispatch);
  const path = String(action.path || "README.md");
  const preview = action.preview || {};
  dispatch({
    type: "file_preview_loaded",
    path,
    preview: {
      title: String(preview.title || action.title || path),
      content: String(preview.content || ""),
    },
  });
  dispatch({
    type: "workbench_surface_opened",
    placement: "right",
    kind: "file",
    title: action.title || path,
    resourceId: path,
    filePath: path,
    revealLine: action.revealLine,
  });
}

export function dispatchVisualDebugAction(dispatch, action = {}) {
  if (typeof dispatch !== "function") return;
  switch (action.type) {
    case "dev_fixture_timeline":
      dispatchTimelineFixture(dispatch, action);
      return;
    case "dev_fixture_interaction":
      dispatchInteractionFixture(dispatch, action);
      return;
    case "dev_fixture_threads":
      dispatchThreadFixture(dispatch, action);
      return;
    case "dev_fixture_source_control":
      dispatchSourceControlFixture(dispatch, action);
      return;
    case "dev_fixture_file_tree":
      dispatchFileTreeFixture(dispatch, action);
      return;
    case "dev_fixture_file_preview":
      dispatchFilePreviewFixture(dispatch, action);
      return;
    default:
      dispatch(action);
  }
}

export function buildTimelineFixtureAction({ currentMode = "explore" } = {}) {
  return {
    type: "dev_fixture_timeline",
    sessionId: "visual-debug-timeline",
    timeline: [
      {
        id: "visual-user-1",
        kind: "user",
        content: "Review parser recovery and show the work.",
        turnId: "visual-turn-1",
      },
      {
        id: "visual-compact-1",
        kind: "compact",
        content: "Earlier setup turns were compacted.",
        summarizedTurns: 5,
        recentTurns: 2,
        approxTokensAfter: 3600,
        turnId: "visual-turn-1",
      },
      {
        id: "visual-reasoning-1",
        kind: "reasoning",
        content: "Inspect the parser recovery path, then verify the changed diagnostic flow.",
        streaming: false,
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-read-1",
        kind: "tool",
        toolName: "read_file",
        label: "Read File Complete",
        toolTitle: "Read File",
        itemType: "dynamic_tool_call",
        requestKind: "file-read",
        toolLifecycleStatus: "completed",
        detail: "src/parser.c",
        status: "success",
        arguments: { path: "src/parser.c" },
        data: { summary: "Read parser entry point." },
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-edit-1",
        kind: "tool",
        toolName: "edit_file",
        label: "Edit File Complete",
        toolTitle: "Changed files",
        itemType: "file_change",
        requestKind: "file-change",
        toolLifecycleStatus: "completed",
        detail: "src/parser.c",
        status: "success",
        arguments: { path: "src/parser.c" },
        data: {
          path: "src/parser.c",
          diff_preview: "--- a/src/parser.c\n+++ b/src/parser.c\n@@ -1 +1,2 @@\n-int parse(void) { return 0; }\n+int parse(void) { return 1; }\n+int parse_extra(void) { return 2; }\n",
        },
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-command-1",
        kind: "tool",
        toolName: "pytest",
        label: "Bash Complete",
        toolTitle: "Ran command",
        itemType: "command_execution",
        requestKind: "command",
        toolLifecycleStatus: "completed",
        command: "uv run pytest tests/ -m harness",
        rawCommand: "python -m pytest tests/ -m harness",
        status: "success",
        arguments: { command: "uv run pytest tests/ -m harness" },
        data: { stdout_preview: "12 passed" },
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-mcp-1",
        kind: "tool",
        toolName: "preview_status",
        label: "Tool call complete",
        toolTitle: "t3-code · preview_status",
        itemType: "mcp_tool_call",
        toolLifecycleStatus: "completed",
        toolData: { name: "preview_status", input: { url: "http://localhost:5173" } },
        status: "success",
        arguments: {},
        data: { summary: "Preview is running." },
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-grep-1",
        kind: "tool",
        toolName: "grep_text",
        label: "Search Complete",
        toolTitle: "grep",
        itemType: "dynamic_tool_call",
        requestKind: "file-read",
        toolLifecycleStatus: "completed",
        detail: "line 4 reveal target",
        status: "success",
        arguments: { pattern: "line 4 reveal target", path: "src" },
        data: {
          pattern: "line 4 reveal target",
          match_count: 1,
          matches: [{ path: "src/parser.c", line: 4, text: "line 4 reveal target" }],
        },
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-review-result",
        kind: "command_result",
        commandName: "review",
        success: false,
        content: "Review found one follow-up item in [src/parser.c:4](src/parser.c#L4).",
        data: {
          review: {
            findings: [
              {
                id: "visual-finding-1",
                severity: "medium",
                priority: 2,
                title: "Add EOF recovery fixture",
                body: "The parser recovery path is not covered by a fixture yet.",
                file: "src/parser.c",
                line: 4,
              },
            ],
            residual_risks: ["Visual fixture only checks rendering, not parser behavior."],
          },
        },
        turnId: "visual-turn-1",
      },
      {
        id: "visual-assistant-1",
        kind: "assistant",
        content: "Parser recovery was updated and review found one fixture follow-up.",
        turnId: "visual-turn-1",
        stepId: "visual-step-1",
        stepIndex: 1,
      },
      {
        id: "visual-user-2",
        kind: "user",
        content: "Think through the next verification step.",
        turnId: "visual-turn-2",
      },
    ],
    snapshot: {
      session_id: "visual-debug-timeline",
      status: "running",
      current_mode: currentMode || "explore",
      pending_interaction_valid: false,
    },
    previews: {
      "src/parser.c": {
        kind: "file",
        title: "parser.c",
        content: [
          "int parse_value(void) {",
          "  return 0;",
          "}",
          "line 4 reveal target",
          "void recover(void) {}",
        ].join("\n"),
      },
    },
    activeTurnId: "visual-turn-2",
    activeStepId: "visual-step-2",
    activeStepIndex: 1,
    thinkingActive: true,
  };
}

export function buildLongTimelineFixtureAction({ currentMode = "explore", turnCount = 36 } = {}) {
  const timeline = [];
  for (let index = 0; index < turnCount; index += 1) {
    const turnId = `visual-long-turn-${index + 1}`;
    const stepId = `visual-long-step-${index + 1}`;
    timeline.push({
      id: `visual-long-user-${index + 1}`,
      kind: "user",
      content: `Inspect long timeline item ${index + 1}.`,
      turnId,
    });
    timeline.push({
      id: `visual-long-tool-${index + 1}`,
      kind: "tool",
      toolName: index % 2 === 0 ? "read_file" : "grep_text",
      label: index % 2 === 0 ? "Read File" : "Search",
      status: "success",
      arguments: index % 2 === 0
        ? { path: `src/file_${index + 1}.c` }
        : { pattern: "parse", path: "src" },
      data: index % 2 === 0
        ? { path: `src/file_${index + 1}.c`, content_preview: "int main(void);" }
        : { pattern: "parse", match_count: 1, matches: [{ path: "src/parser.c", line: index + 1, text: "parse();" }] },
      turnId,
      stepId,
      stepIndex: 1,
    });
    timeline.push({
      id: `visual-long-assistant-${index + 1}`,
      kind: "assistant",
      content: `Long timeline item ${index + 1} completed.`,
      turnId,
      stepId,
      stepIndex: 1,
    });
  }
  return {
    type: "dev_fixture_timeline",
    sessionId: "visual-debug-long-timeline",
    timeline,
    snapshot: {
      session_id: "visual-debug-long-timeline",
      status: "idle",
      current_mode: currentMode || "explore",
      pending_interaction_valid: false,
    },
    activeTurnId: "",
    activeStepId: "",
    activeStepIndex: 0,
    thinkingActive: false,
  };
}

export function buildInteractionFixtureAction(kind = "permission") {
  const permission =
    kind === "permission"
      ? {
          interaction_id: "visual-permission-1",
          kind: "permission",
          tool_name: "edit_file",
          category: "workspace_write",
          reason: "Allow editing src/parser.c",
          details: { path: "src/parser.c" },
          turn_id: "visual-turn-1",
          step_id: "visual-step-2",
          step_index: 2,
        }
      : null;
  const userInput =
    kind === "user_input"
      ? {
          interaction_id: "visual-input-1",
          request_id: "visual-input-1",
          kind: "user_input",
          tool_name: "ask_user",
          question: "Which parser behavior should be preserved?",
          options: [
            { index: 1, text: "Keep strict parsing" },
            { index: 2, text: "Accept empty input" },
          ],
          turn_id: "visual-turn-1",
          step_id: "visual-step-2",
          step_index: 2,
        }
      : null;
  return {
    type: "dev_fixture_interaction",
    sessionId: "visual-debug-interaction",
    permission,
    userInput,
  };
}

export function buildThreadLifecycleFixtureAction() {
  return {
    type: "dev_fixture_threads",
    sessionId: "visual-thread-active",
    sessions: [
      {
        session_id: "visual-thread-active",
        user_goal: "Fix parser recovery",
        current_mode: "build",
        updated_at: "2026-06-16T09:30:00Z",
      },
      {
        session_id: "visual-thread-spec",
        summary_text: "Plan tokenizer cleanup",
        current_mode: "spec",
        updated_at: "2026-06-15T17:10:00Z",
      },
      {
        session_id: "visual-thread-verify",
        user_goal: "Verify offline bundle smoke",
        current_mode: "verify",
        updated_at: "2026-06-14T08:00:00Z",
      },
    ],
  };
}

export function buildSourceControlFixtureAction() {
  return {
    type: "dev_fixture_source_control",
    status: {
      workspace_root: "D:/visual-debug/demo",
      is_repo: true,
      git_available: true,
      git_executable: "git",
      runtime_source: "visual-debug-fixture",
      branch: "feature/t3-toolbar",
      head: "abc1234",
      has_primary_remote: true,
      provider: {
        kind: "github",
        name: "GitHub",
        remote_host: "github.com",
      },
      is_dirty: true,
      counts: {
        staged: 1,
        unstaged: 2,
        untracked: 1,
        conflicted: 0,
        total: 4,
      },
      files: [
        {
          path: "src/parser.c",
          display_path: "src/parser.c",
          group: "unstaged",
          status: "modified",
          worktree_status: "M",
          insertions: 12,
          deletions: 4,
          diff_scopes: ["unstaged"],
        },
        {
          path: "src/parser.h",
          display_path: "src/parser.h",
          group: "staged",
          status: "modified",
          index_status: "M",
          insertions: 3,
          deletions: 1,
          diff_scopes: ["staged"],
        },
        {
          path: "tests/parser_recovery_test.c",
          display_path: "tests/parser_recovery_test.c",
          group: "unstaged",
          status: "modified",
          worktree_status: "M",
          insertions: 18,
          deletions: 2,
          diff_scopes: ["unstaged"],
        },
        {
          path: "notes/t3-toolbar.md",
          display_path: "notes/t3-toolbar.md",
          group: "untracked",
          status: "untracked",
          worktree_status: "?",
          insertions: 9,
          deletions: 0,
          diff_scopes: ["untracked"],
        },
      ],
      updated_at: "2026-06-18T09:30:00Z",
    },
  };
}

export function buildComposerFileTreeFixtureAction() {
  return {
    type: "dev_fixture_file_tree",
    nodes: [
      {
        id: "src",
        path: "src",
        name: "src",
        kind: "dir",
        has_children: true,
        childrenLoaded: true,
        children: [
          { id: "src/main.c", path: "src/main.c", name: "main.c", kind: "file", has_children: false },
          { id: "src/parser.c", path: "src/parser.c", name: "parser.c", kind: "file", has_children: false },
          {
            id: "src/include",
            path: "src/include",
            name: "include",
            kind: "dir",
            has_children: true,
            childrenLoaded: true,
            children: [
              { id: "src/include/parser.h", path: "src/include/parser.h", name: "parser.h", kind: "file", has_children: false },
            ],
          },
        ],
      },
      { id: "README.md", path: "README.md", name: "README.md", kind: "file", has_children: false },
    ],
  };
}

export function buildFilePreviewRevealFixtureAction() {
  return {
    type: "dev_fixture_file_preview",
    path: "README.md",
    title: "README.md",
    revealLine: 4,
    preview: {
      kind: "file",
      title: "README.md",
      content: [
        "# Visual Debug Workspace",
        "",
        "line 3",
        "line 4 reveal target",
        "line 5",
        "line 6",
        "",
      ].join("\n"),
    },
  };
}

export function loadPanelOverflowFixture(dispatch) {
  dispatchVisualDebugAction(dispatch, {
    type: "dev_fixture_threads",
    sessionId: "visual-panel-overflow",
    sessions: [{ session_id: "visual-panel-overflow", user_goal: "Panel overflow fixture" }],
  });
  for (const surface of [
    { kind: "files" },
    { kind: "diff", resourceId: "current" },
    { kind: "plan" },
    { kind: "source_control" },
    { kind: "settings" },
    { kind: "diagnostics" },
    { kind: "preview", resourceId: "preview-a" },
    {
      kind: "terminal",
      resourceId: "term-a",
      terminalId: "term-a",
      terminalIds: ["term-a"],
      activeTerminalId: "term-a",
    },
  ]) {
    dispatch({ type: "workbench_surface_opened", placement: "right", ...surface });
  }
}

export function loadSurfaceSwitchingFixture(dispatch) {
  const sessionId = "visual-surface-switching";
  dispatchVisualDebugAction(dispatch, {
    type: "dev_fixture_threads",
    sessionId,
    sessions: [{ session_id: sessionId, user_goal: "Surface switching fixture" }],
  });
  dispatchVisualDebugAction(dispatch, buildFilePreviewRevealFixtureAction());
  dispatchVisualDebugAction(dispatch, buildSourceControlFixtureAction());
  dispatch({
    type: "terminal_snapshot_loaded",
    snapshot: {
      session_id: sessionId,
      terminal_id: "surface-term-a",
      status: "running",
      history: "surface-term-a ready\n",
      cols: 100,
      rows: 30,
    },
  });
  for (const surface of [
    { kind: "files" },
    { kind: "file", resourceId: "README.md", filePath: "README.md", title: "README.md" },
    { kind: "diff", resourceId: "current" },
    { kind: "preview", resourceId: "preview-a" },
    {
      kind: "terminal",
      resourceId: "surface-term-a",
      terminalId: "surface-term-a",
      terminalIds: ["surface-term-a"],
      activeTerminalId: "surface-term-a",
    },
    { kind: "source_control" },
    { kind: "settings" },
    { kind: "diagnostics" },
  ]) {
    dispatch({ type: "workbench_surface_opened", placement: "right", ...surface });
  }
  dispatch({
    type: "diff_surface_opened",
    diffSurface: createDiffSurfaceState({
      title: "Visual Debug Diff",
      diff: "--- a/demo.c\n+++ b/demo.c\n@@ -1,3 +1,3 @@\n int main(void) {\n-    return 0;\n+    return 1;\n }\n",
      source: "visual-debug",
      filePath: "demo.c",
    }),
  });
  dispatch({ type: "workbench_surface_activated", placement: "right", kind: "diagnostics" });
}

export function loadTerminalSplitFixture(dispatch) {
  dispatchVisualDebugAction(dispatch, {
    type: "dev_fixture_threads",
    sessionId: "visual-terminal-split",
    sessions: [{ session_id: "visual-terminal-split", user_goal: "Terminal split fixture" }],
  });
  dispatch({
    type: "terminal_snapshot_loaded",
    snapshot: {
      session_id: "visual-terminal-split",
      terminal_id: "term-a",
      status: "running",
      history: "term-a ready\n",
      cols: 100,
      rows: 30,
    },
  });
  dispatch({
    type: "terminal_snapshot_loaded",
    snapshot: {
      session_id: "visual-terminal-split",
      terminal_id: "term-b",
      status: "running",
      history: "term-b ready\n",
      cols: 100,
      rows: 30,
    },
  });
  dispatch({
    type: "workbench_surface_opened",
    placement: "right",
    kind: "terminal",
    resourceId: "term-a",
    terminalId: "term-a",
    terminalIds: ["term-a", "term-b"],
    activeTerminalId: "term-b",
    splitDirection: "vertical",
  });
}

export function loadTimelineContextFixture(dispatch) {
  dispatchVisualDebugAction(dispatch, {
    type: "dev_fixture_timeline",
    sessionId: "visual-timeline-context",
    activeTurnId: "turn-context-active",
    thinkingActive: true,
    timeline: [
      {
        id: "user-context",
        kind: "user",
        role: "user",
        content: "Build the project",
        turnId: "turn-context-active",
      },
      {
        id: "tool-running",
        kind: "tool",
        toolName: "pytest",
        label: "Pytest",
        status: "running",
        tone: "running",
        arguments: { command: "uv run pytest tests/" },
        turnId: "turn-context-active",
      },
      {
        id: "compact-active",
        kind: "compact",
        content: "Context compacted",
        summarizedTurns: 5,
        recentTurns: 2,
        turnId: "turn-context-active",
      },
    ],
  });
}

export function installVisualDebugFixtures({
  windowObject,
  locationSearch = "",
  dispatch,
  openDiffFixture,
  currentMode = "explore",
} = {}) {
  if (!windowObject || typeof dispatch !== "function") return undefined;
  const params = new URLSearchParams(locationSearch || "");
  if (params.get("visual_debug") !== "1") return undefined;
  windowObject.__EMBEDAGENT_VISUAL_DEBUG__ = {
    openDiffFixture({ title = "Visual Debug Diff", diff = "", filePath = "" } = {}) {
      if (typeof openDiffFixture === "function") {
        openDiffFixture({ title, diff, filePath });
      }
    },
    loadTimelineFixture() {
      dispatchVisualDebugAction(dispatch, buildTimelineFixtureAction({ currentMode }));
    },
    loadSourceControlFixture() {
      dispatchVisualDebugAction(dispatch, buildSourceControlFixtureAction());
    },
    loadComposerFileTreeFixture() {
      dispatchVisualDebugAction(dispatch, buildComposerFileTreeFixtureAction());
    },
    loadFilePreviewRevealFixture() {
      dispatchVisualDebugAction(dispatch, buildFilePreviewRevealFixtureAction());
    },
    loadLongTimelineFixture() {
      dispatchVisualDebugAction(dispatch, buildLongTimelineFixtureAction({ currentMode }));
    },
    loadInteractionFixture(kind = "permission") {
      dispatchVisualDebugAction(dispatch, buildInteractionFixtureAction(kind));
    },
    loadThreadLifecycleFixture() {
      dispatchVisualDebugAction(dispatch, buildThreadLifecycleFixtureAction());
    },
    loadPanelOverflowFixture() {
      loadPanelOverflowFixture(dispatch);
    },
    loadSurfaceSwitchingFixture() {
      loadSurfaceSwitchingFixture(dispatch);
    },
    loadTerminalSplitFixture() {
      loadTerminalSplitFixture(dispatch);
    },
    loadTimelineContextFixture() {
      loadTimelineContextFixture(dispatch);
    },
  };
  return () => {
    if (windowObject.__EMBEDAGENT_VISUAL_DEBUG__) {
      delete windowObject.__EMBEDAGENT_VISUAL_DEBUG__;
    }
  };
}
