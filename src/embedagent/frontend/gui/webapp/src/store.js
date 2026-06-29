import { injectChildren } from "./state-helpers.js";
import { focusDiffFile } from "./session-runtime/diff-model.js";
import { createComposerState, reduceComposerState } from "./composer/composer-state.js";
import { createAppShellState } from "./app-shell/model.js";
import { reduceAppShellState } from "./app-shell/reducer.js";
import { createSourceControlState, reduceSourceControlState } from "./source-control/source-control-state.js";
import { createTerminalState, reduceTerminalState } from "./terminal/terminal-state.js";
import { createRunOutputState, reduceRunOutputState } from "./session-runtime/run-output-state.js";
import { createThreadState, readActiveThreadId, reduceThreadState } from "./session-runtime/thread-state.js";
import {
  ACTIVITY_ACTION_TYPES,
  createActivityState,
  reduceActivityState,
} from "./session-runtime/activity-reducer.js";
import { createWorkbenchState, reduceWorkbenchState } from "./workbench/surfaces.js";
import { resetWorkspaceScopedState } from "./app-workspaces.js";

export const DEFAULT_MODE = "explore";

export const initialState = {
  sidebarTab: "chats",
  inspectorTab: "tasks",
  inspectorOpen: true,
  lang: "en",
  thread: createThreadState(),
  snapshot: null,
  composer: createComposerState(),
  ...createActivityState(),
  permission: null,
  userInput: null,
  interactionNotice: null,
  tasks: [],
  artifacts: [],
  plan: null,
  review: null,
  recipes: [],
  permissionContext: null,
  preview: null,
  filePreviewsByPath: {},
  diffSurface: null,
  fileTree: [],
  toolCatalog: {},
  sessionCapabilities: { commands: [] },
  requestedMode: DEFAULT_MODE,
  runOutput: createRunOutputState(),
  workbench: createWorkbenchState(),
  app: createAppShellState(),
  sourceControl: createSourceControlState(),
  terminal: createTerminalState(),
};

export function reducer(state, action) {
  if (ACTIVITY_ACTION_TYPES.has(action.type)) {
    const activityPatch = reduceActivityState(state, action);
    const nextState = { ...state, ...activityPatch };
    if (action.type === "local_user_message") {
      return {
        ...nextState,
        composer: reduceComposerState(state.composer, action),
        interactionNotice: null,
      };
    }
    if (action.type === "command_result") {
      return {
        ...nextState,
        review: action.commandName === "review" ? action.data?.review || state.review : state.review,
      };
    }
    return nextState;
  }

  switch (action.type) {
    case "set_sidebar":
      return { ...state, sidebarTab: action.value };
    case "set_inspector":
      return { ...state, inspectorTab: action.value };
    case "toggle_inspector":
      return { ...state, inspectorOpen: !state.inspectorOpen };
    case "set_lang":
      return { ...state, lang: action.value };
    case "set_composer":
      return { ...state, composer: reduceComposerState(state.composer, action) };
    case "app_bootstrap_loaded":
      return {
        ...state,
        app: reduceAppShellState(state.app, {
          type: "app_shell_bootstrap_loaded",
          bootstrap: action.bootstrap || {},
        }),
      };
    case "workspace_path_changed":
      return {
        ...state,
        app: reduceAppShellState(state.app, {
          type: "app_shell_workspace_path_changed",
          value: action.value,
        }),
      };
    case "workspace_activation_started":
      return {
        ...state,
        app: reduceAppShellState(state.app, {
          type: "app_shell_workspace_activation_started",
        }),
      };
    case "workspace_activation_failed":
      return {
        ...state,
        app: reduceAppShellState(state.app, {
          type: "app_shell_workspace_activation_failed",
          error: action.error,
        }),
      };
    case "workspace_switched": {
      const reset = resetWorkspaceScopedState(state);
      return {
        ...reset,
        app: reduceAppShellState(reset.app, {
          type: "app_shell_workspace_switched",
          bootstrap: action.bootstrap || {},
        }),
      };
    }
    case "app_shell_bootstrap_loaded":
    case "app_shell_workspace_path_changed":
    case "app_shell_workspace_activation_started":
    case "app_shell_workspace_activation_failed":
    case "app_shell_workspace_switched":
    case "app_shell_settings_changed":
      return {
        ...state,
        app: reduceAppShellState(state.app, action),
      };
    case "terminal_snapshot_loaded":
    case "terminal_summaries_loaded":
    case "terminal_event":
    case "terminal_active_set":
      return {
        ...state,
        terminal: reduceTerminalState(state.terminal, action),
      };
    case "source_control_reset":
    case "source_control_load_started":
    case "source_control_load_failed":
    case "source_control_status_loaded":
    case "source_control_file_selected":
    case "source_control_diff_started":
    case "source_control_diff_failed":
    case "source_control_diff_loaded":
      return {
        ...state,
        sourceControl: reduceSourceControlState(state.sourceControl, action),
      };
    case "sessions_loaded":
      return { ...state, thread: reduceThreadState(state.thread, action) };
    case "session_activated":
      return {
        ...state,
        thread: reduceThreadState(state.thread, action),
        snapshot: action.snapshot,
        sessionCapabilities: action.capabilities || { commands: [] },
        requestedMode: action.snapshot?.current_mode || state.requestedMode,
        ...reduceActivityState(state, { type: "activity_reset", activities: action.activities }),
        permission:
          action.snapshot?.pending_interaction_valid && action.snapshot?.pending_interaction?.kind === "permission"
            ? action.snapshot.pending_interaction
            : null,
        userInput:
          action.snapshot?.pending_interaction_valid && action.snapshot?.pending_interaction?.kind === "user_input"
            ? action.snapshot.pending_interaction
            : null,
        interactionNotice: null,
        runOutput: reduceRunOutputState(state.runOutput, action),
        plan: null,
        review: null,
        permissionContext: null,
        tasks: Array.isArray(action.snapshot?.task_items) ? action.snapshot.task_items : [],
        inspectorTab:
          action.snapshot?.pending_interaction_valid && action.snapshot?.pending_interaction
            ? "interaction"
            : state.inspectorTab,
        inspectorOpen:
          action.snapshot?.pending_interaction_valid && action.snapshot?.pending_interaction
            ? true
            : state.inspectorOpen,
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_session_activated",
          sessionId: action.sessionId,
        }),
      };
    case "session_snapshot": {
      const snapshot = action.snapshot;
      if (!snapshot) return state;
      const hadActiveInteraction = Boolean(
        state.snapshot?.pending_interaction_valid && state.snapshot?.pending_interaction,
      );
      const hasActiveInteraction = Boolean(
        snapshot.pending_interaction_valid && snapshot.pending_interaction,
      );
      return {
        ...state,
        thread: reduceThreadState(state.thread, action),
        snapshot,
        requestedMode: snapshot.current_mode || state.requestedMode,
        permission:
          snapshot.pending_interaction_valid && snapshot.pending_interaction?.kind === "permission"
            ? snapshot.pending_interaction
            : null,
        userInput:
          snapshot.pending_interaction_valid && snapshot.pending_interaction?.kind === "user_input"
            ? snapshot.pending_interaction
            : null,
        tasks: Array.isArray(snapshot.task_items) ? snapshot.task_items : state.tasks,
        interactionNotice:
          snapshot.pending_interaction_valid && snapshot.pending_interaction
            ? null
            : state.interactionNotice,
        inspectorTab:
          !hadActiveInteraction && hasActiveInteraction
            ? "interaction"
            : state.inspectorTab,
        inspectorOpen:
          !hadActiveInteraction && hasActiveInteraction
            ? true
            : state.inspectorOpen,
      };
    }
    case "permission_request": {
      return {
        ...state,
        permission: action.permission,
        interactionNotice: null,
        thinkingActive: false,
        inspectorTab: action.inspectorTab || "interaction",
        inspectorOpen: true,
      };
    }
    case "permission_cleared":
      return {
        ...state,
        permission: null,
      };
    case "user_input_request": {
      return {
        ...state,
        userInput: action.request,
        interactionNotice: null,
        thinkingActive: false,
        inspectorTab: "interaction",
        inspectorOpen: true,
      };
    }
    case "user_input_answered":
      return {
        ...state,
        userInput: null,
      };
    case "user_input_cleared":
      return {
        ...state,
        userInput: null,
      };
    case "tasks_loaded":
      return { ...state, tasks: action.tasks };
    case "artifacts_loaded":
      return { ...state, artifacts: action.items };
    case "recipes_loaded":
      return { ...state, recipes: action.items || [] };
    case "preview_loaded":
      return {
        ...state,
        preview: action.preview,
        inspectorTab: action.inspectorTab || state.inspectorTab,
      };
    case "file_preview_load_started": {
      const path = String(action.path || "");
      if (!path) return state;
      return {
        ...state,
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          [path]: {
            status: "loading",
            path,
            title: path,
            content: "",
            error: "",
          },
        },
      };
    }
    case "file_preview_loaded": {
      const path = String(action.path || "");
      if (!path) return state;
      const preview = action.preview || {};
      return {
        ...state,
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          [path]: {
            status: "loaded",
            path,
            title: String(preview.title || path),
            content: String(preview.content || ""),
            error: "",
          },
        },
      };
    }
    case "file_preview_load_failed": {
      const path = String(action.path || "");
      if (!path) return state;
      return {
        ...state,
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          [path]: {
            status: "error",
            path,
            title: path,
            content: "",
            error: String(action.error || "File unavailable"),
          },
        },
      };
    }
    case "diff_surface_opened":
      return {
        ...state,
        diffSurface: action.diffSurface || null,
        inspectorTab: "diff",
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_surface_opened",
          placement: "right",
          kind: "diff",
          title: action.diffSurface?.title || "Diff",
          resourceId: "current",
        }),
      };
    case "diff_file_focused":
      return {
        ...state,
        diffSurface: focusDiffFile(state.diffSurface, action.filePath || ""),
      };
    case "plan_loaded":
      return {
        ...state,
        plan: action.plan,
        inspectorTab: action.inspectorTab || state.inspectorTab,
      };
    case "review_loaded":
      return {
        ...state,
        review: action.review,
        inspectorTab: action.inspectorTab || state.inspectorTab,
      };
    case "permission_context_loaded":
      return {
        ...state,
        permissionContext: action.context,
        inspectorTab: action.inspectorTab || state.inspectorTab,
      };
    case "interaction_notice_set":
      return {
        ...state,
        interactionNotice: action.notice || null,
        inspectorTab: "interaction",
        inspectorOpen: true,
      };
    case "interaction_notice_clear":
      return {
        ...state,
        interactionNotice: null,
      };
    case "tool_catalog_loaded":
      return {
        ...state,
        toolCatalog: action.catalog || {},
      };
    case "file_tree_loaded":
      return { ...state, fileTree: action.nodes };
    case "file_children_loaded":
      return { ...state, fileTree: injectChildren(state.fileTree, action.path, action.children) };
    case "mode_requested":
      return { ...state, requestedMode: action.mode };
    case "log_event": {
      return { ...state, runOutput: reduceRunOutputState(state.runOutput, action) };
    }
    case "workbench_surface_opened":
    case "workbench_surface_activated":
    case "workbench_surface_closed":
    case "workbench_surface_close_others":
    case "workbench_surface_close_to_right":
    case "workbench_surface_close_all":
    case "workbench_terminal_surface_split":
    case "workbench_terminal_surface_terminal_activated":
    case "workbench_terminal_surface_terminal_closed":
    case "workbench_command_palette_opened":
    case "workbench_command_palette_closed":
    case "workbench_command_palette_query_changed":
    case "workbench_right_panel_toggled":
    case "workbench_bottom_drawer_toggled":
      return {
        ...state,
        workbench: reduceWorkbenchState(state.workbench, {
          ...action,
          sessionId: action.sessionId || readActiveThreadId(state) || state.workbench?.activeSessionKey,
        }),
      };
    default:
      return state;
  }
}

export const TOOL_LABELS = {
  read_file: (a) => `Read  ${a.path || ""}`,
  write_file: (a) => `Write  ${a.path || ""}`,
  edit_file: (a) => `Edit  ${a.path || ""}`,
  list_dir: (a) => `List  ${a.path || "."}`,
  glob_files: (a) => `Glob "${a.pattern || ""}"`,
  grep_text: (a) => `Grep "${a.pattern || ""}"`,
  author_local_capability: (a) => `Author capability${a.name ? `: ${a.name}` : ""}`,
  ask_user: () => "Ask user",
  list_recipes: () => "List recipes",
  run_recipe: (a) => `Run recipe${a.recipe_id ? `: ${a.recipe_id}` : ""}`,
  report_quality_v2: () => "Quality report",
  task_status: () => "Task status",
  record_failing_evidence: () => "Record failing evidence",
  bash: (a) => `Bash: ${a.command || ""}`,
  git_status: () => "Git status",
  git_diff: (a) => `Git diff${a.path ? `  ${a.path}` : ""}`,
  git_log: () => "Git log",
};

export function toolLabel(toolName, args) {
  const fn = TOOL_LABELS[toolName];
  return fn ? fn(args || {}) : toolName;
}

export const STATUS_ICON = { running: "⋯", success: "✓", error: "✗" };
