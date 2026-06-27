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
  openRightPanelSurface,
  terminalController,
}) {
  async function execute(command) {
    if (!command) return;
    switch (command.id) {
      case "palette.open":
        dispatch({ type: "workbench_command_palette_opened" });
        return;
      case "palette.close":
        dispatch({ type: "workbench_command_palette_closed" });
        return;
      case "session.new":
      case "thread.new":
        await createSession(getCurrentMode());
        return;
      case "session.refresh":
        await loadSessions();
        return;
      case "workspace.open":
        dispatch({ type: "set_sidebar", value: "chats" });
        setTimeoutFn(() => {
          documentObject
            .querySelector('[data-testid="sidebar-workspace-path-input"]')
            ?.focus();
        }, 0);
        return;
      case "workspace.refresh":
      case "app.reload":
        await loadAppBootstrap();
        return;
      case "workspace.remove_current": {
        const workspaceId = getActiveWorkspaceId();
        if (workspaceId) {
          await removeWorkspace(workspaceId);
        }
        return;
      }
      case "app.settings":
        openRightPanelSurface("settings", command.label);
        return;
      case "app.diagnostics":
        openRightPanelSurface("diagnostics", command.label);
        return;
      case "app.source_control":
        openRightPanelSurface("source_control", command.label);
        return;
      case "message.send":
        await sendMessage();
        return;
      case "message.stop":
        await cancelSession();
        return;
      case "view.toggle_right_panel":
        dispatch({ type: "workbench_right_panel_toggled" });
        return;
      case "view.toggle_bottom_drawer":
        dispatch({ type: "workbench_bottom_drawer_toggled" });
        return;
      default:
        break;
    }
    if (command.surface) {
      openRightPanelSurface(command.surface, command.label);
      return;
    }
    if (command.drawer) {
      if (command.drawer === "terminal") {
        await terminalController.ensureOpen();
        return;
      }
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: command.drawer });
      return;
    }
    if (command.slash) {
      await submitText(command.slash);
    }
  }

  return { execute };
}
