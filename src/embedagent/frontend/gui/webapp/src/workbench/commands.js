import { normalizeCommandCapabilities } from "../session-runtime/command-capabilities.js";
import {
  bottomDrawerCommandDefinitions,
  surfaceCommandDefinitions,
} from "./surfaces.js";

export const COMMAND_GROUPS = [
  "app",
  "session",
  "message",
  "mode",
  "surface",
  "workspace",
  "workflow",
  "view",
];

const LOCAL_COMMANDS = [
  { id: "session.new", group: "session", label: "New Session", slash: "/new", visibleWhen: "always" },
  { id: "thread.new", group: "session", label: "New Thread", slash: "", visibleWhen: "always", keywords: ["session", "chat"] },
  { id: "session.refresh", group: "session", label: "Refresh Sessions", slash: "/sessions", visibleWhen: "always" },
  { id: "session.resume", group: "session", label: "Resume Session", slash: "/resume", visibleWhen: "always" },
  { id: "message.send", group: "message", label: "Send Message", slash: "", visibleWhen: "composer_ready" },
  { id: "message.stop", group: "message", label: "Stop Running Turn", slash: "", visibleWhen: "running" },
  { id: "workflow.diff", group: "workflow", label: "Review Diff", slash: "/diff", visibleWhen: "has_session" },
  { id: "view.toggle_right_panel", group: "view", label: "Toggle Right Panel", slash: "", visibleWhen: "always" },
  { id: "view.toggle_bottom_drawer", group: "view", label: "Toggle Bottom Drawer", slash: "", visibleWhen: "always" },
  { id: "palette.open", group: "view", label: "Open Command Palette", slash: "", visibleWhen: "always" },
  { id: "palette.close", group: "view", label: "Close Command Palette", slash: "", visibleWhen: "palette_open" },
];

export const WORKBENCH_COMMANDS = [
  ...LOCAL_COMMANDS,
];

function localWorkbenchCommands() {
  return LOCAL_COMMANDS;
}

function appCommandDefinitions(appCapabilities = null) {
  return Array.isArray(appCapabilities?.appCommands) ? appCapabilities.appCommands : [];
}

function workspaceCommandDefinitions(appCapabilities = null) {
  return Array.isArray(appCapabilities?.workspaceCommands) ? appCapabilities.workspaceCommands : [];
}

function commandFromCapability(item = {}) {
  const id = String(item.id || item.name || "").trim();
  if (!id) return null;
  return {
    id,
    group: String(item.group || "command").trim() || "command",
    label: String(item.label || item.usage || id).trim() || id,
    slash: String(item.slash || item.usage || "").trim(),
    visibleWhen: String(item.visibleWhen || "always").trim() || "always",
    keywords: [item.name, item.summary, item.sourceType, item.sourceId].filter(Boolean),
    dispatch: item.dispatch && typeof item.dispatch === "object" ? item.dispatch : {},
  };
}

export function buildWorkbenchCommands(capabilities = {}, appCapabilities = null) {
  const dynamicCommands = normalizeCommandCapabilities(capabilities).commands
    .map(commandFromCapability)
    .filter(Boolean);
  const commands = [];
  const seen = new Set();
  const builtinCommands = [
    ...appCommandDefinitions(appCapabilities),
    ...localWorkbenchCommands(),
    ...surfaceCommandDefinitions(appCapabilities),
    ...bottomDrawerCommandDefinitions(appCapabilities),
    ...workspaceCommandDefinitions(appCapabilities),
  ];
  for (const command of builtinCommands.concat(dynamicCommands)) {
    if (!command || !command.id || seen.has(command.id)) continue;
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
