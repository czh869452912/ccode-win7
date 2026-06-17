import {
  createAppShellState,
  normalizeAppBootstrap,
  normalizeAppSettings,
} from "./model.js";

export function resetAppShellWorkspaceState(state = {}) {
  const current = { ...createAppShellState(), ...(state || {}) };
  return {
    ...current,
    activeWorkspace: null,
    hasActiveWorkspace: false,
    workspacePathInput: "",
    workspaceError: "",
    activatingWorkspace: false,
  };
}

export function reduceAppShellState(state = createAppShellState(), action = {}) {
  const current = { ...createAppShellState(), ...(state || {}) };
  switch (action.type) {
    case "app_shell_bootstrap_loaded": {
      const bootstrap = normalizeAppBootstrap(action.bootstrap || {});
      return {
        ...current,
        ...bootstrap,
        workspacePathInput: current.workspacePathInput,
        activatingWorkspace: false,
      };
    }
    case "app_shell_workspace_path_changed":
      return {
        ...current,
        workspacePathInput: action.value || "",
        workspaceError: "",
      };
    case "app_shell_workspace_activation_started":
      return {
        ...current,
        activatingWorkspace: true,
        workspaceError: "",
      };
    case "app_shell_workspace_activation_failed":
      return {
        ...current,
        activatingWorkspace: false,
        workspaceError: action.error || "workspace_open_failed",
      };
    case "app_shell_workspace_switched": {
      const bootstrap = normalizeAppBootstrap(action.bootstrap || {});
      return {
        ...resetAppShellWorkspaceState(current),
        ...bootstrap,
        workspacePathInput: "",
        activatingWorkspace: false,
      };
    }
    case "app_shell_settings_changed":
      return {
        ...current,
        settings: normalizeAppSettings({
          ...current.settings,
          ...(action.patch || {}),
        }),
      };
    default:
      return current;
  }
}
