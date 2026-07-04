const ROOT_COMMAND_LIMIT = 8;
const RECENT_SESSION_LIMIT = 12;

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

function paletteGroupDescriptors(commandPalette = {}) {
  const groups = Array.isArray(commandPalette?.groups) ? commandPalette.groups : [];
  const result = {};
  for (const group of groups) {
    const id = asText(group?.id);
    if (!id || result[id]) continue;
    result[id] = {
      id,
      title: asText(group.title),
      description: asText(group.description),
      order: Number.isFinite(Number(group.order)) ? Number(group.order) : 0,
      leading: asText(group.leading),
      meta: asText(group.meta),
      keywords: Array.isArray(group.keywords) ? group.keywords.map(asText).filter(Boolean) : [],
    };
  }
  return result;
}

function paletteLabels(commandPalette = {}) {
  const labels = commandPalette?.labels && typeof commandPalette.labels === "object"
    ? commandPalette.labels
    : {};
  return {
    commandsSection: asText(labels.commandsSection),
    sessionsSection: asText(labels.sessionsSection),
    workspacesSection: asText(labels.workspacesSection),
    currentLabel: asText(labels.currentLabel),
    missingLabel: asText(labels.missingLabel),
    workspaceMeta: asText(labels.workspaceMeta),
    workspaceFallback: asText(labels.workspaceFallback),
    sessionFallbackPrefix: asText(labels.sessionFallbackPrefix),
    sessionLeading: asText(labels.sessionLeading),
    workspaceLeading: asText(labels.workspaceLeading),
  };
}

function groupDescriptor(groupId, descriptors) {
  const id = asText(groupId);
  return descriptors[id] || {
    id,
    title: "",
    description: "",
    order: 1000,
    leading: "",
    meta: "",
    keywords: [],
  };
}

function sortedCommandGroupIds(groups, descriptors) {
  return Object.keys(groups).sort((left, right) => {
    const leftDescriptor = groupDescriptor(left, descriptors);
    const rightDescriptor = groupDescriptor(right, descriptors);
    return leftDescriptor.order - rightDescriptor.order || left.localeCompare(right);
  });
}

function commandDescription(command = {}, descriptor = {}) {
  if (command.description) return command.description;
  if (command.slash) return command.slash;
  return descriptor.description || "";
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

function commandItem(command, shortcutMap, groupDescriptors) {
  const group = asText(command.group);
  const descriptor = groupDescriptor(group, groupDescriptors);
  const title = asText(command.label);
  return {
    id: `command:${command.id}`,
    type: "command",
    commandId: asText(command.id),
    group,
    title,
    description: commandDescription(command, descriptor),
    meta: asText(command.slash),
    shortcut: shortcutMap[command.id] || "",
    leading: descriptor.leading,
    disabled: false,
    searchTerms: [asText(command.slash), descriptor.title, ...(descriptor.keywords || []), ...(command.keywords || [])],
  };
}

function groupCommandItems(commands = [], shortcutMap = {}, groupDescriptors = {}) {
  const groups = {};
  for (const command of commands || []) {
    if (!command || !command.id || !asText(command.label)) continue;
    const group = asText(command.group);
    if (!group || !groupDescriptor(group, groupDescriptors).title) continue;
    if (!groups[group]) groups[group] = [];
    groups[group].push(commandItem(command, shortcutMap, groupDescriptors));
  }
  return groups;
}

function submenuItem(groupId, items, groupDescriptors) {
  const descriptor = groupDescriptor(groupId, groupDescriptors);
  const title = descriptor.title;
  if (!title) return null;
  return {
    id: `submenu:${groupId}`,
    type: "submenu",
    submenuId: groupId,
    group: groupId,
    title,
    description: descriptor.description,
    meta: descriptor.meta,
    trailing: String(items.length),
    leading: descriptor.leading,
    disabled: items.length === 0,
    searchTerms: [groupId, title, descriptor.description, ...(descriptor.keywords || [])],
  };
}

function sessionTitle(session, labels = {}) {
  const sessionId = asText(session && (session.session_id || session.id));
  const fallbackPrefix = asText(labels.sessionFallbackPrefix);
  const fallback = fallbackPrefix ? `${fallbackPrefix} ${sessionId.slice(0, 8)}` : sessionId.slice(0, 8);
  return (
    asText(session && session.thread && session.thread.title)
    || asText(session && session.title)
    || asText(session && session.user_goal)
    || asText(session && session.summary_text)
    || fallback
  );
}

function sessionItems(sessions = [], currentSessionId = "", labels = {}) {
  return (Array.isArray(sessions) ? sessions : [])
    .filter((session) => session && asText(session.session_id || session.id))
    .slice(0, RECENT_SESSION_LIMIT)
    .map((session) => {
      const sessionId = asText(session.session_id || session.id);
      const mode = asText(session.current_mode || session.mode);
      const updated = asText(session.updated_at || session.created_at);
      return {
        id: `session:${sessionId}`,
        type: "session",
        sessionId,
        title: sessionTitle(session, labels),
        description: mode,
        meta: updated,
        trailing: sessionId === currentSessionId ? labels.currentLabel : "",
        leading: labels.sessionLeading,
        disabled: false,
        searchTerms: [sessionId, mode, updated],
      };
    });
}

function workspaceTitle(workspace, labels = {}) {
  return asText(workspace && workspace.label) || basename(workspace && workspace.path) || labels.workspaceFallback;
}

function workspaceItems(workspaces = [], activeWorkspaceId = "", labels = {}) {
  return (Array.isArray(workspaces) ? workspaces : [])
    .filter((workspace) => workspace && asText(workspace.id))
    .map((workspace) => {
      const workspaceId = asText(workspace.id);
      const exists = workspace.exists !== false;
      return {
        id: `workspace:${workspaceId}`,
        type: "workspace",
        workspaceId,
        title: workspaceTitle(workspace, labels),
        description: asText(workspace.path),
        meta: labels.workspaceMeta,
        trailing: workspaceId === activeWorkspaceId ? labels.currentLabel : exists ? "" : labels.missingLabel,
        leading: labels.workspaceLeading,
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
  commandPalette = null,
  query = "",
} = {}) {
  const shortcutMap = shortcutByCommandId(keybindings);
  const groupDescriptors = paletteGroupDescriptors(commandPalette || {});
  const labels = paletteLabels(commandPalette || {});
  const commandGroups = groupCommandItems(commands, shortcutMap, groupDescriptors);
  const commandGroupIds = sortedCommandGroupIds(commandGroups, groupDescriptors);
  const submenuItems = commandGroupIds
    .map((groupId) => submenuItem(groupId, commandGroups[groupId], groupDescriptors))
    .filter(Boolean);
  const allCommandItems = commandGroupIds
    .reduce((items, groupId) => items.concat(commandGroups[groupId]), []);
  const commandRootItems = filterAndRank(submenuItems.concat(allCommandItems), query).slice(0, ROOT_COMMAND_LIMIT);
  const groups = [
    nonEmptyGroup("commands", labels.commandsSection, commandRootItems),
    nonEmptyGroup("sessions", labels.sessionsSection, filterAndRank(sessionItems(sessions, currentSessionId, labels), query)),
    nonEmptyGroup("workspaces", labels.workspacesSection, filterAndRank(workspaceItems(workspaces, activeWorkspaceId, labels), query)),
  ];
  return groups.filter(Boolean);
}

export function buildCommandPaletteSubmenuGroups({
  commands = [],
  keybindings = [],
  commandPalette = null,
  groupId = "",
  query = "",
} = {}) {
  const targetGroup = asText(groupId);
  if (!targetGroup) return [];
  const shortcutMap = shortcutByCommandId(keybindings);
  const groupDescriptors = paletteGroupDescriptors(commandPalette || {});
  const descriptor = groupDescriptor(targetGroup, groupDescriptors);
  const title = descriptor.title;
  if (!title) return [];
  const items = (commands || [])
    .filter((command) => command && asText(command.group) === targetGroup && asText(command.label))
    .map((command) => commandItem(command, shortcutMap, groupDescriptors));
  const ranked = filterAndRank(items, query);
  return ranked.length > 0 ? [{ id: targetGroup, title, items: ranked }] : [];
}

export function flattenPaletteGroups(groups = []) {
  return (groups || []).reduce((items, group) => items.concat(group.items || []), []);
}
