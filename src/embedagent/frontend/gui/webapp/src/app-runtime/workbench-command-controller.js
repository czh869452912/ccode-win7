import { commandById } from "../workbench/commands.js";

function focusSelector({ documentObject, setTimeoutFn }, selector) {
  setTimeoutFn(() => documentObject.querySelector(selector)?.focus(), 0);
}

function currentSessionId(context) {
  return String(context.getCurrentSessionId?.() || "").trim();
}

function requireCurrentSession(context) {
  const sessionId = currentSessionId(context);
  if (!sessionId) throw new Error("shell_command_requires_session");
  return sessionId;
}

function surfaceById(context, surfaceId) {
  const descriptor = context.getShellDescriptor?.() || {};
  const surfaces = Array.isArray(descriptor.surfaces) ? descriptor.surfaces : [];
  return surfaces.find((item) => item?.id === surfaceId) || null;
}

async function openRegisteredSurface(context, dispatchDescriptor) {
  const surfaceId = String(dispatchDescriptor.surface_id || "").trim();
  const surface = surfaceById(context, surfaceId);
  if (!surface) throw new Error(`unknown_shell_surface:${surfaceId}`);
  if (surface.rendererKey === "command_palette") {
    context.dispatch({ type: "command_palette_opened" });
    return;
  }
  if (surface.rendererKey === "composer" || surface.rendererKey === "interaction") {
    focusSelector(context, '[data-testid="composer-input"]');
    return;
  }
  if (surface.placement === "secondary") {
    context.openContributionSurface(surface.id, surface.label);
    return;
  }
  throw new Error(`unsupported_shell_renderer:${surface.rendererKey}`);
}

const COMMAND_DISPATCH_HANDLERS = Object.freeze(Object.assign(Object.create(null), {
  "session.create": async ({ createSession, getCurrentMode }) => {
    await createSession(getCurrentMode());
  },
  "session.select": async ({ dispatch }) => {
    dispatch({ type: "command_palette_opened" });
  },
  "session.rename": async (context, _dispatchDescriptor, command) => {
    await context.renameSession(requireCurrentSession(context), command);
  },
  "session.archive": async (context, _dispatchDescriptor, command) => {
    await context.archiveSession(requireCurrentSession(context), command);
  },
  "session.fork": async (context, _dispatchDescriptor, command) => {
    await context.forkSession(requireCurrentSession(context), command);
  },
  "session.cancel": async ({ cancelSession }) => {
    await cancelSession();
  },
  "session.mode": async (context, dispatchDescriptor, command) => {
    const selected = String(dispatchDescriptor.mode || context.prompt?.(
      command.label,
      context.getCurrentMode(),
    ) || "").trim();
    if (selected) await context.setMode(selected);
  },
  "session.command": async ({ submitText }, dispatchDescriptor) => {
    const name = String(dispatchDescriptor.command || "").trim();
    if (!name) throw new Error("shell_command_dispatch_invalid");
    await submitText(`/${name}`);
  },
  "workspace.open": async (context) => {
    focusSelector(context, '[data-testid="sidebar-workspace-path-input"]');
  },
  "shell.surface": openRegisteredSurface,
  "interaction.respond": async (context) => {
    focusSelector(context, '[data-testid="composer-input"]');
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
  getCurrentSessionId,
  getShellDescriptor,
  getSessionCapabilities,
  getAppCapabilities,
  createSession,
  loadSession,
  activateWorkspace,
  cancelSession,
  renameSession,
  archiveSession,
  forkSession,
  submitText,
  setMode,
  openContributionSurface,
  prompt,
}) {
  const context = {
    archiveSession,
    cancelSession,
    createSession,
    dispatch,
    documentObject,
    getCurrentMode,
    getCurrentSessionId,
    getShellDescriptor,
    forkSession,
    openContributionSurface,
    prompt,
    renameSession,
    setMode,
    setTimeoutFn,
    submitText,
  };
  const readSessionCapabilities =
    typeof getSessionCapabilities === "function" ? getSessionCapabilities : () => ({});
  const readAppCapabilities =
    typeof getAppCapabilities === "function" ? getAppCapabilities : () => ({});

  function openPalette() {
    dispatch({ type: "command_palette_opened" });
  }

  function closePalette() {
    dispatch({ type: "command_palette_closed" });
  }

  function updatePaletteQuery(query) {
    dispatch({ type: "command_palette_query_changed", query });
  }

  async function execute(command) {
    if (!command) return;
    const dispatchDescriptor =
      command.dispatch && typeof command.dispatch === "object" ? command.dispatch : {};
    const handler = COMMAND_DISPATCH_HANDLERS[dispatchDescriptor.kind];
    if (!handler) throw new Error(`unsupported_shell_dispatch:${dispatchDescriptor.kind || ""}`);
    await handler(context, dispatchDescriptor, command);
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
    updatePaletteQuery,
  };
}
