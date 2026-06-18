const ROOT_COMMAND_LIMIT = 8;
const RECENT_SESSION_LIMIT = 12;

const GROUP_TITLES = {
  app: "App",
  session: "Sessions",
  message: "Message",
  mode: "Mode",
  surface: "Surface",
  workspace: "Workspace",
  workflow: "Workflow",
  view: "View",
};

const GROUP_DESCRIPTIONS = {
  app: "App shell commands",
  session: "Create, refresh, and resume threads",
  message: "Send or stop the current turn",
  mode: "Switch the active agent mode",
  surface: "Open workbench surfaces",
  workspace: "Open or refresh local workspaces",
  workflow: "Run workflow views",
  view: "Toggle workbench layout",
};

function asText(value) {
  return String(value || "").trim();
}

function basename(path) {
  const text = asText(path).replace(/\\/g, "/");
  const parts = text.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : text;
}

function titleCase(value) {
  const text = asText(value);
  if (!text) return "";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function normalizePaletteQuery(query) {
  return asText(query).toLowerCase();
}

export function formatPaletteShortcut(key) {
  const text = asText(key);
  if (!text) return "";
  return text
    .split("+")
    .filter(Boolean)
    .map((part) => {
      if (part === "mod") return "Ctrl";
      if (part === "ctrl") return "Ctrl";
      if (part === "alt") return "Alt";
      if (part === "shift") return "Shift";
      if (part === "escape") return "Esc";
      return part.length === 1 ? part.toUpperCase() : titleCase(part);
    })
    .join("+");
}

function shortcutByCommandId(keybindings = []) {
  const result = {};
  for (const binding of keybindings || []) {
    const commandId = asText(binding && binding.commandId);
    if (!commandId || result[commandId]) continue;
    const formatted = formatPaletteShortcut(binding.key);
    if (formatted) result[commandId] = formatted;
  }
  return result;
}

function commandDescription(command = {}) {
  if (command.slash) return command.slash;
  if (command.surface) return `Open ${command.surface}`;
  if (command.drawer) return `Open ${command.drawer}`;
  return GROUP_DESCRIPTIONS[command.group] || command.id;
}

function searchableText(item = {}) {
  return [
    item.title,
    item.description,
    item.meta,
    item.trailing,
    item.group,
    item.commandId,
    item.sessionId,
    item.workspaceId,
    ...(item.searchTerms || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function rankItem(item, query) {
  const normalized = normalizePaletteQuery(query);
  if (!normalized) return 1;
  const title = asText(item.title).toLowerCase();
  const meta = asText(item.meta).toLowerCase();
  const text = searchableText(item);
  if (title === normalized || meta === normalized) return 100;
  if (title.startsWith(normalized) || meta.startsWith(normalized)) return 80;
  if (text.split(/\s+/).some((part) => part.startsWith(normalized))) return 60;
  if (text.includes(normalized)) return 40;
  return 0;
}

function filterAndRank(items, query) {
  return (items || [])
    .map((item, index) => ({ item, index, score: rankItem(item, query) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => right.score - left.score || left.index - right.index)
    .map((entry) => entry.item);
}

function commandItem(command, shortcutMap) {
  const group = asText(command.group);
  return {
    id: `command:${command.id}`,
    type: "command",
    commandId: asText(command.id),
    group,
    title: asText(command.label) || asText(command.id),
    description: commandDescription(command),
    meta: asText(command.slash || command.id),
    shortcut: shortcutMap[command.id] || "",
    leading: titleCase(group).slice(0, 1) || ">",
    disabled: false,
    searchTerms: [asText(command.slash), ...(command.keywords || [])],
  };
}

function groupCommandItems(commands = [], shortcutMap = {}) {
  const groups = {};
  for (const command of commands || []) {
    if (!command || !command.id) continue;
    const group = asText(command.group) || "commands";
    if (!groups[group]) groups[group] = [];
    groups[group].push(commandItem(command, shortcutMap));
  }
  return groups;
}

function submenuItem(groupId, items) {
  const title = GROUP_TITLES[groupId] || titleCase(groupId);
  return {
    id: `submenu:${groupId}`,
    type: "submenu",
    submenuId: groupId,
    group: groupId,
    title,
    description: GROUP_DESCRIPTIONS[groupId] || `${title} commands`,
    meta: "Commands",
    trailing: String(items.length),
    leading: title.slice(0, 1) || ">",
    disabled: items.length === 0,
    searchTerms: [groupId, title],
  };
}

function sessionTitle(session) {
  const sessionId = asText(session && (session.session_id || session.id));
  return (
    asText(session && session.thread && session.thread.title)
    || asText(session && session.title)
    || asText(session && session.user_goal)
    || asText(session && session.summary_text)
    || `Session ${sessionId.slice(0, 8)}`
  );
}

function sessionItems(sessions = [], currentSessionId = "") {
  return (Array.isArray(sessions) ? sessions : [])
    .filter((session) => session && asText(session.session_id || session.id))
    .slice(0, RECENT_SESSION_LIMIT)
    .map((session) => {
      const sessionId = asText(session.session_id || session.id);
      const mode = asText(session.current_mode || session.mode || "explore");
      const updated = asText(session.updated_at || session.created_at);
      return {
        id: `session:${sessionId}`,
        type: "session",
        sessionId,
        title: sessionTitle(session),
        description: mode,
        meta: updated,
        trailing: sessionId === currentSessionId ? "Current" : "",
        leading: "T",
        disabled: false,
        searchTerms: [sessionId, mode, updated],
      };
    });
}

function workspaceTitle(workspace) {
  return asText(workspace && workspace.label) || basename(workspace && workspace.path) || "Workspace";
}

function workspaceItems(workspaces = [], activeWorkspaceId = "") {
  return (Array.isArray(workspaces) ? workspaces : [])
    .filter((workspace) => workspace && asText(workspace.id))
    .map((workspace) => {
      const workspaceId = asText(workspace.id);
      const exists = workspace.exists !== false;
      return {
        id: `workspace:${workspaceId}`,
        type: "workspace",
        workspaceId,
        title: workspaceTitle(workspace),
        description: asText(workspace.path),
        meta: "Workspace",
        trailing: workspaceId === activeWorkspaceId ? "Current" : exists ? "" : "Missing",
        leading: "W",
        disabled: !exists,
        searchTerms: [workspaceId, workspace.path, workspace.label],
      };
    });
}

function nonEmptyGroup(id, title, items) {
  return items.length > 0 ? { id, title, items } : null;
}

export function buildCommandPaletteRootGroups({
  commands = [],
  sessions = [],
  currentSessionId = "",
  workspaces = [],
  activeWorkspaceId = "",
  keybindings = [],
  query = "",
} = {}) {
  const shortcutMap = shortcutByCommandId(keybindings);
  const commandGroups = groupCommandItems(commands, shortcutMap);
  const submenuItems = Object.keys(commandGroups)
    .sort()
    .map((groupId) => submenuItem(groupId, commandGroups[groupId]));
  const allCommandItems = Object.keys(commandGroups)
    .sort()
    .reduce((items, groupId) => items.concat(commandGroups[groupId]), []);
  const commandRootItems = filterAndRank(submenuItems.concat(allCommandItems), query).slice(0, ROOT_COMMAND_LIMIT);
  const groups = [
    nonEmptyGroup("commands", "Commands", commandRootItems),
    nonEmptyGroup("sessions", "Sessions", filterAndRank(sessionItems(sessions, currentSessionId), query)),
    nonEmptyGroup("workspaces", "Workspaces", filterAndRank(workspaceItems(workspaces, activeWorkspaceId), query)),
  ];
  return groups.filter(Boolean);
}

export function buildCommandPaletteSubmenuGroups({
  commands = [],
  keybindings = [],
  groupId = "",
  query = "",
} = {}) {
  const targetGroup = asText(groupId);
  if (!targetGroup) return [];
  const shortcutMap = shortcutByCommandId(keybindings);
  const items = (commands || [])
    .filter((command) => command && asText(command.group) === targetGroup)
    .map((command) => commandItem(command, shortcutMap));
  const ranked = filterAndRank(items, query);
  const title = GROUP_TITLES[targetGroup] || titleCase(targetGroup);
  return ranked.length > 0 ? [{ id: targetGroup, title, items: ranked }] : [];
}

export function flattenPaletteGroups(groups = []) {
  return (groups || []).reduce((items, group) => items.concat(group.items || []), []);
}
