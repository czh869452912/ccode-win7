import { injectChildren } from "./state-helpers.js";
import { focusDiffFile } from "./session-runtime/diff-model.js";
import { createComposerState, reduceComposerState } from "./composer/composer-state.js";
import { createAppShellState } from "./app-shell/model.js";
import { reduceAppShellState } from "./app-shell/reducer.js";
import { createSourceControlState, reduceSourceControlState } from "./source-control/source-control-state.js";
import { createTerminalState, reduceTerminalState } from "./terminal/terminal-state.js";
import { createRunOutputState, reduceRunOutputState } from "./session-runtime/run-output-state.js";
import { createThreadState, readActiveThreadId, reduceThreadState } from "./session-runtime/thread-state.js";
import { normalizeProtocolCapabilities } from "./session-runtime/protocol-normalizer.js";
import {
  ACTIVITY_ACTION_TYPES,
  createActivityState,
  reduceActivityState,
} from "./session-runtime/activity-reducer.js";
import { createWorkbenchState, reduceWorkbenchState } from "./workbench/surfaces.js";
import { sanitizeWorkbenchUiStateForAppCapabilities } from "./workbench/ui-state.js";
import { resetWorkspaceScopedState } from "./app-workspaces.js";

export const INITIAL_REQUESTED_MODE = "";
export const EMPTY_CAPABILITIES = normalizeProtocolCapabilities({});

export const initialState = {
  sidebarTab: "chats",
  thread: createThreadState(),
  snapshot: null,
  composer: createComposerState(),
  ...createActivityState(),
  interactionNotice: null,
  tasks: [],
  plan: null,
  filePreviewsByPath: {},
  diffSurface: null,
  fileTree: [],
  sessionCapabilities: EMPTY_CAPABILITIES,
  requestedMode: INITIAL_REQUESTED_MODE,
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
        composer: reduceComposerState(state.composer, {
          ...action,
          sessionId: action.sessionId || readActiveThreadId(state),
        }),
        interactionNotice: null,
      };
    }
    if (action.type === "command_result") {
      return nextState;
    }
    return nextState;
  }

  switch (action.type) {
    case "set_sidebar":
      return { ...state, sidebarTab: action.value };
    case "set_composer":
      return {
        ...state,
        composer: reduceComposerState(state.composer, {
          ...action,
          sessionId: action.sessionId || readActiveThreadId(state),
        }),
      };
    case "app_bootstrap_loaded": {
      const app = reduceAppShellState(state.app, {
        type: "app_shell_bootstrap_loaded",
        bootstrap: action.bootstrap || {},
      });
      return {
        ...state,
        app,
        workbench: sanitizeWorkbenchUiStateForAppCapabilities(state.workbench, app.capabilities),
      };
    }
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
      const app = reduceAppShellState(reset.app, {
        type: "app_shell_workspace_switched",
        bootstrap: action.bootstrap || {},
      });
      return {
        ...reset,
        app,
        workbench: sanitizeWorkbenchUiStateForAppCapabilities(reset.workbench, app.capabilities),
      };
    }
    case "app_shell_bootstrap_loaded": {
      const app = reduceAppShellState(state.app, action);
      return {
        ...state,
        app,
        workbench: sanitizeWorkbenchUiStateForAppCapabilities(state.workbench, app.capabilities),
      };
    }
    case "app_shell_workspace_switched": {
      const app = reduceAppShellState(state.app, action);
      return {
        ...state,
        app,
        workbench: sanitizeWorkbenchUiStateForAppCapabilities(state.workbench, app.capabilities),
      };
    }
    case "app_shell_workspace_path_changed":
    case "app_shell_workspace_activation_started":
    case "app_shell_workspace_activation_failed":
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
    case "session_capabilities_loaded":
      return {
        ...state,
        sessionCapabilities: action.capabilities || EMPTY_CAPABILITIES,
      };
    case "session_activated":
      return {
        ...state,
        thread: reduceThreadState(state.thread, action),
        snapshot: action.snapshot,
        sessionCapabilities: action.capabilities || EMPTY_CAPABILITIES,
        requestedMode: action.snapshot?.current_mode || state.requestedMode,
        ...reduceActivityState(state, { type: "activity_reset", activities: action.activities }),
        interactionNotice: null,
        runOutput: reduceRunOutputState(state.runOutput, action),
        plan: null,
        tasks: Array.isArray(action.snapshot?.task_items) ? action.snapshot.task_items : [],
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_session_activated",
          sessionId: action.sessionId,
        }),
      };
    case "session_snapshot": {
      const snapshot = action.snapshot;
      if (!snapshot) return state;
      return {
        ...state,
        thread: reduceThreadState(state.thread, action),
        snapshot,
        requestedMode: snapshot.current_mode || state.requestedMode,
        tasks: Array.isArray(snapshot.task_items) ? snapshot.task_items : state.tasks,
        interactionNotice:
          snapshot.pending_interaction_valid && snapshot.pending_interaction
            ? null
            : state.interactionNotice,
      };
    }
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
            error: String(action.error || ""),
          },
        },
      };
    }
    case "diff_surface_opened":
      return {
        ...state,
        diffSurface: action.diffSurface || null,
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_surface_opened",
          placement: "right",
          kind: "diff",
          title: action.diffSurface?.title || "diff",
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
      };
    case "interaction_notice_set":
      return {
        ...state,
        interactionNotice: action.notice || null,
      };
    case "interaction_notice_clear":
      return {
        ...state,
        interactionNotice: null,
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

export const STATUS_ICON = { running: "⋯", success: "✓", error: "✗" };
