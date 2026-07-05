import { normalizeCommandCapabilities } from "../session-runtime/command-capabilities.js";
import {
  bottomDrawerCommandDefinitions,
  surfaceCommandDefinitions,
} from "./surfaces.js";

function appCommandDefinitions(appCapabilities = null) {
  return Array.isArray(appCapabilities?.appCommands) ? appCapabilities.appCommands : [];
}

function workspaceCommandDefinitions(appCapabilities = null) {
  return Array.isArray(appCapabilities?.workspaceCommands) ? appCapabilities.workspaceCommands : [];
}

function workbenchCommandDefinitions(appCapabilities = null) {
  return Array.isArray(appCapabilities?.workbenchCommands) ? appCapabilities.workbenchCommands : [];
}

function defaultCommandGroupId(appCapabilities = null) {
  return String(
    appCapabilities?.chrome?.composer?.commandMenu?.defaultCommandGroupId || "",
  ).trim();
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

export function isTurnInterruptibleStatus(status) {
  return status === "running" || status === "waiting_permission" || status === "waiting_user_input";
}

export function buildCommandVisibilityContext(options = {}) {
  const appState = options.appState && typeof options.appState === "object" ? options.appState : {};
  const workbenchState =
    options.workbenchState && typeof options.workbenchState === "object"
      ? options.workbenchState
      : {};
  const currentStatus = options.currentStatus || "idle";
  const hasActiveWorkspace = hasOwn(options, "hasActiveWorkspace")
    ? options.hasActiveWorkspace
    : appState.hasActiveWorkspace;
  const paletteOpen = hasOwn(options, "paletteOpen")
    ? options.paletteOpen
    : workbenchState.commandPalette?.open;
  return {
    hasSession: Boolean(options.currentSessionId),
    hasWorkspace: Boolean(hasActiveWorkspace),
    isRunning: isTurnInterruptibleStatus(currentStatus),
    paletteOpen: Boolean(paletteOpen),
    capabilities: options.sessionCapabilities || options.capabilities || {},
    appCapabilities: options.appCapabilities || appState.capabilities || {},
  };
}

function commandFromCapability(item = {}, appCapabilities = null) {
  const id = String(item.id || item.name || "").trim();
  if (!id) return null;
  const group = String(item.group || defaultCommandGroupId(appCapabilities)).trim();
  return {
    id,
    group,
    label: String(item.label || item.usage || "").trim(),
    slash: String(item.slash || item.usage || "").trim(),
    visibleWhen: String(item.visibleWhen || "always").trim() || "always",
    keywords: [item.name, item.summary, item.sourceType, item.sourceId].filter(Boolean),
    dispatch: item.dispatch && typeof item.dispatch === "object" ? item.dispatch : {},
  };
}

export function buildWorkbenchCommands(capabilities = {}, appCapabilities = null) {
  const dynamicCommands = normalizeCommandCapabilities(capabilities).commands
    .map((command) => commandFromCapability(command, appCapabilities))
    .filter(Boolean);
  const commands = [];
  const seen = new Set();
  const builtinCommands = [
    ...appCommandDefinitions(appCapabilities),
    ...workbenchCommandDefinitions(appCapabilities),
    ...surfaceCommandDefinitions(appCapabilities),
    ...bottomDrawerCommandDefinitions(appCapabilities),
    ...workspaceCommandDefinitions(appCapabilities),
  ];
  for (const command of builtinCommands.concat(dynamicCommands)) {
    if (!command || !command.id || !command.label || seen.has(command.id)) continue;
    seen.add(command.id);
    commands.push(command);
  }
  return commands;
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
