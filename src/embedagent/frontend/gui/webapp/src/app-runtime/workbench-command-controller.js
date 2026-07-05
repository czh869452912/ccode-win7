import { commandById } from "../workbench/commands.js";

const COMMAND_DISPATCH_HANDLERS = Object.freeze(Object.assign(Object.create(null), {
  "mode.set": async ({ setMode }, dispatchDescriptor) => {
    if (dispatchDescriptor.mode) {
      await setMode(dispatchDescriptor.mode);
    }
  },
  "command_palette.open": async ({ dispatch }) => {
    dispatch({ type: "workbench_command_palette_opened" });
  },
  "command_palette.close": async ({ dispatch }) => {
    dispatch({ type: "workbench_command_palette_closed" });
  },
  "session.create": async ({ createSession, getCurrentMode }) => {
    await createSession(getCurrentMode());
  },
  "sessions.reload": async ({ loadSessions }) => {
    await loadSessions();
  },
  "workspace.focus_path_input": async ({ documentObject, setTimeoutFn }) => {
    setTimeoutFn(() => {
      documentObject
        .querySelector('[data-testid="sidebar-workspace-path-input"]')
        ?.focus();
    }, 0);
  },
  "app_shell.reload": async ({ loadAppBootstrap }) => {
    await loadAppBootstrap();
  },
  "workspace.remove_active_recent": async ({ getActiveWorkspaceId, removeWorkspace }) => {
    const workspaceId = getActiveWorkspaceId();
    if (workspaceId) {
      await removeWorkspace(workspaceId);
    }
  },
  "message.submit": async ({ sendMessage }) => {
    await sendMessage();
  },
  "turn.cancel": async ({ cancelSession }) => {
    await cancelSession();
  },
  "workbench.toggle_right_panel": async ({ dispatch }) => {
    dispatch({ type: "workbench_right_panel_toggled" });
  },
  "workbench.toggle_bottom_drawer": async ({ dispatch }) => {
    dispatch({ type: "workbench_bottom_drawer_toggled" });
  },
  "terminal.ensure_open": async ({ terminalController }) => {
    await terminalController.ensureOpen();
  },
}));

function selectedCommandId(command) {
  if (typeof command === "string") return command;
  return String(command?.id || command?.commandId || "").trim();
}

export function createWorkbenchCommandController({
  dispatch,
  documentObject,
  setTimeoutFn,
  getCurrentMode,
  getActiveWorkspaceId,
  getSessionCapabilities,
  getAppCapabilities,
  createSession,
  loadSessions,
  loadSession,
  loadAppBootstrap,
  activateWorkspace,
  removeWorkspace,
  sendMessage,
  cancelSession,
  submitText,
  setMode,
  openRightPanelSurface,
  terminalController,
}) {
  const context = {
    cancelSession,
    createSession,
    dispatch,
    documentObject,
    getActiveWorkspaceId,
    getCurrentMode,
    loadAppBootstrap,
    loadSessions,
    removeWorkspace,
    sendMessage,
    setMode,
    setTimeoutFn,
    terminalController,
  };
  const readSessionCapabilities =
    typeof getSessionCapabilities === "function" ? getSessionCapabilities : () => ({});
  const readAppCapabilities =
    typeof getAppCapabilities === "function" ? getAppCapabilities : () => ({});

  function openPalette() {
    dispatch({ type: "workbench_command_palette_opened" });
  }

  function closePalette() {
    dispatch({ type: "workbench_command_palette_closed" });
  }

  function updatePaletteQuery(query) {
    dispatch({ type: "workbench_command_palette_query_changed", query });
  }

  function toggleRightPanel() {
    dispatch({ type: "workbench_right_panel_toggled" });
  }

  function toggleBottomDrawer() {
    dispatch({ type: "workbench_bottom_drawer_toggled" });
  }

  async function execute(command) {
    if (!command) return;
    const dispatchDescriptor =
      command.dispatch && typeof command.dispatch === "object" ? command.dispatch : {};
    const handler = COMMAND_DISPATCH_HANDLERS[dispatchDescriptor.kind];
    if (handler) {
      await handler(context, dispatchDescriptor);
      return;
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

  async function selectPaletteCommand(command) {
    closePalette();
    await execute(commandById(
      selectedCommandId(command),
      readSessionCapabilities(),
      readAppCapabilities(),
    ));
  }

  async function selectPaletteSession(sessionId) {
    closePalette();
    if (sessionId && typeof loadSession === "function") {
      await loadSession(sessionId);
    }
  }

  async function selectPaletteWorkspace(workspaceId) {
    closePalette();
    if (workspaceId && typeof activateWorkspace === "function") {
      await activateWorkspace(workspaceId);
    }
  }

  return {
    closePalette,
    execute,
    openPalette,
    selectPaletteCommand,
    selectPaletteSession,
    selectPaletteWorkspace,
    toggleBottomDrawer,
    toggleRightPanel,
    updatePaletteQuery,
  };
}
