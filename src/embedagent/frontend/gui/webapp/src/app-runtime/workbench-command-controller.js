export function createWorkbenchCommandController({
  dispatch,
  documentObject,
  setTimeoutFn,
  getCurrentMode,
  getActiveWorkspaceId,
  createSession,
  loadSessions,
  loadAppBootstrap,
  removeWorkspace,
  sendMessage,
  cancelSession,
  submitText,
  setMode,
  openRightPanelSurface,
  terminalController,
}) {
  async function execute(command) {
    if (!command) return;
    const dispatchDescriptor =
      command.dispatch && typeof command.dispatch === "object" ? command.dispatch : {};
    switch (dispatchDescriptor.kind) {
      case "mode.set":
        if (dispatchDescriptor.mode) {
          await setMode(dispatchDescriptor.mode);
        }
        return;
      case "command_palette.open":
        dispatch({ type: "workbench_command_palette_opened" });
        return;
      case "command_palette.close":
        dispatch({ type: "workbench_command_palette_closed" });
        return;
      case "session.create":
        await createSession(getCurrentMode());
        return;
      case "sessions.reload":
        await loadSessions();
        return;
      case "workspace.focus_path_input":
        setTimeoutFn(() => {
          documentObject
            .querySelector('[data-testid="sidebar-workspace-path-input"]')
            ?.focus();
        }, 0);
        return;
      case "app_shell.reload":
        await loadAppBootstrap();
        return;
      case "workspace.remove_active_recent": {
        const workspaceId = getActiveWorkspaceId();
        if (workspaceId) {
          await removeWorkspace(workspaceId);
        }
        return;
      }
      case "message.submit":
        await sendMessage();
        return;
      case "turn.cancel":
        await cancelSession();
        return;
      case "workbench.toggle_right_panel":
        dispatch({ type: "workbench_right_panel_toggled" });
        return;
      case "workbench.toggle_bottom_drawer":
        dispatch({ type: "workbench_bottom_drawer_toggled" });
        return;
      case "terminal.ensure_open":
        await terminalController.ensureOpen();
        return;
      default:
        break;
    }
    if (command.surface) {
      openRightPanelSurface(command.surface, command.label);
      return;
    }
    if (command.drawer) {
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: command.drawer });
      return;
    }
    if (command.slash) {
      await submitText(command.slash);
    }
  }

  return { execute };
}
