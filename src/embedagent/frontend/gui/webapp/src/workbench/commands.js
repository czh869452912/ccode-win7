function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

export function isTurnInterruptibleStatus(status) {
  return status === "running" || status === "waiting_permission" || status === "waiting_user_input";
}

export function buildCommandVisibilityContext(options = {}) {
  const appState = options.appState && typeof options.appState === "object" ? options.appState : {};
  const contributionState =
    options.contributionState && typeof options.contributionState === "object"
      ? options.contributionState
      : {};
  const currentStatus = options.currentStatus || "idle";
  const hasActiveWorkspace = hasOwn(options, "hasActiveWorkspace")
    ? options.hasActiveWorkspace
    : appState.hasActiveWorkspace;
  const paletteOpen = hasOwn(options, "paletteOpen")
    ? options.paletteOpen
    : contributionState.palette?.open;
  return {
    hasSession: Boolean(options.currentSessionId),
    hasWorkspace: Boolean(hasActiveWorkspace),
    isRunning: isTurnInterruptibleStatus(currentStatus),
    paletteOpen: Boolean(paletteOpen),
    capabilities: options.sessionCapabilities || options.capabilities || {},
    appCapabilities: options.appCapabilities || appState.capabilities || {},
  };
}

export function buildWorkbenchCommands(_capabilities = {}, appCapabilities = null) {
  const declared = Array.isArray(appCapabilities?.workbenchCommands)
    ? appCapabilities.workbenchCommands
    : [];
  return declared.filter((command) => command?.id && command?.label);
}

export function commandById(id, capabilities = {}, appCapabilities = null) {
  return buildWorkbenchCommands(capabilities, appCapabilities).find((item) => item.id === id) || null;
}

function isVisible(command, context) {
  const view = context || {};
  switch (command.visibleWhen) {
    case "always":
      return true;
    case "has_session":
      return Boolean(view.hasSession);
    case "running":
      return Boolean(view.isRunning);
    case "composer_ready":
      return !view.isRunning;
    case "palette_open":
      return Boolean(view.paletteOpen);
    case "has_workspace":
      return Boolean(view.hasWorkspace);
    default:
      return false;
  }
}

export function visibleCommands(context) {
  const view = context || {};
  return buildWorkbenchCommands(
    view.capabilities || view.sessionCapabilities || {},
    view.appCapabilities || null,
  ).filter((command) => isVisible(command, view));
}
