import { resetWorkspaceScopedState } from "../app-workspaces.js";
import { createAppState, reduceAppState } from "./reducers/app-reducer.js";
import {
  createContributionState,
  reduceContributionState,
} from "./reducers/contribution-reducer.js";
import {
  EMPTY_CAPABILITIES,
  INITIAL_REQUESTED_MODE,
  createSessionState,
  isSessionAction,
  reduceSessionState,
} from "./reducers/session-reducer.js";
import {
  createTransportState,
  isTransportAction,
  reduceTransportState,
} from "./reducers/transport-reducer.js";

export { EMPTY_CAPABILITIES, INITIAL_REQUESTED_MODE };

const APP_ACTIONS = new Set([
  "app_bootstrap_loaded", "workspace_path_changed", "workspace_activation_started",
  "workspace_activation_failed", "app_shell_bootstrap_loaded",
  "app_shell_workspace_switched", "app_shell_workspace_path_changed",
  "app_shell_workspace_activation_started", "app_shell_workspace_activation_failed",
  "app_shell_settings_changed",
]);

const CONTRIBUTION_ACTIONS = new Set([
  "contribution_opened", "contribution_activated", "contribution_closed",
  "contribution_close_others", "contribution_close_after", "contribution_close_all",
  "contribution_terminal_split", "contribution_terminal_activated",
  "contribution_terminal_closed", "command_palette_opened", "command_palette_closed",
  "command_palette_query_changed",
]);

export const initialState = {
  ...createSessionState(),
  ...createTransportState(),
  contribution: createContributionState(),
  app: createAppState(),
};

function sessionSlice(state) {
  const transportKeys = new Set(["app", "contribution", "sourceControl", "terminal"]);
  return Object.fromEntries(Object.entries(state).filter(([key]) => !transportKeys.has(key)));
}

export function runtimeReducer(state, action = {}) {
  if (action.type === "workspace_switched") {
    const reset = resetWorkspaceScopedState(state);
    return {
      ...reset,
      app: reduceAppState(reset.app, action),
      contribution: createContributionState(),
    };
  }

  let next = state;
  if (APP_ACTIONS.has(action.type)) {
    next = { ...next, app: reduceAppState(next.app, action) };
  }
  if (isSessionAction(action)) {
    next = { ...next, ...reduceSessionState(sessionSlice(next), action) };
  }
  if (isTransportAction(action)) {
    next = { ...next, ...reduceTransportState({
      sourceControl: next.sourceControl,
      terminal: next.terminal,
    }, action) };
  }
  if (CONTRIBUTION_ACTIONS.has(action.type)) {
    next = { ...next, contribution: reduceContributionState(next.contribution, action) };
  }
  if (action.type === "session_activated") {
    next = {
      ...next,
      contribution: reduceContributionState(next.contribution, {
        type: "contribution_session_activated",
        sessionId: action.sessionId,
      }),
    };
  } else if (action.type === "diff_surface_opened") {
    next = {
      ...next,
      contribution: reduceContributionState(next.contribution, {
        type: "contribution_opened",
        kind: "diff",
        label: action.diffSurface?.title || "",
        rendererKey: "inline_diff",
        resourceId: "current",
      }),
    };
  }
  return next;
}

export const STATUS_ICON = { running: "⋯", success: "✓", error: "✗" };
