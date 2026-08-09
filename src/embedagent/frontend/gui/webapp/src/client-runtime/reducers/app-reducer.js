import { createAppShellState } from "../../app-shell/model.js";
import { reduceAppShellState } from "../../app-shell/reducer.js";

export function createAppState() {
  return createAppShellState();
}

function mappedAction(action) {
  switch (action.type) {
    case "app_bootstrap_loaded":
      return { type: "app_shell_bootstrap_loaded", bootstrap: action.bootstrap || {} };
    case "workspace_path_changed":
      return { type: "app_shell_workspace_path_changed", value: action.value };
    case "workspace_activation_started":
      return { type: "app_shell_workspace_activation_started" };
    case "workspace_activation_failed":
      return { type: "app_shell_workspace_activation_failed", error: action.error };
    case "workspace_switched":
      return { type: "app_shell_workspace_switched", bootstrap: action.bootstrap || {} };
    default:
      return action;
  }
}

export function reduceAppState(state = createAppState(), action = {}) {
  return reduceAppShellState(state, mappedAction(action));
}
