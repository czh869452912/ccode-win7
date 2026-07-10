function text(value, fallback = "") {
  if (value == null) return fallback;
  return String(value).trim();
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function listValue(value) {
  return Array.isArray(value) ? value : [];
}

function firstText(...values) {
  for (const value of values) {
    const result = text(value);
    if (result) return result;
  }
  return "";
}

function camelOrSnake(source, camelKey, snakeKey, fallback = "") {
  const data = objectValue(source);
  if (data[camelKey] !== undefined) return data[camelKey];
  if (data[snakeKey] !== undefined) return data[snakeKey];
  return fallback;
}

export function normalizeModeDescriptor(item = {}) {
  const data = objectValue(item);
  const id = firstText(data.id, data.name);
  if (!id) return null;
  const commandId = firstText(camelOrSnake(data, "commandId", "command_id"), `mode.${id}`);
  return {
    id,
    label: firstText(data.label, data.name, id),
    description: text(data.description),
    iconKey: text(camelOrSnake(data, "iconKey", "icon_key")),
    colorToken: text(camelOrSnake(data, "colorToken", "color_token")),
    commandId,
  };
}

export function normalizeCommandDescriptor(item = {}) {
  const data = objectValue(item);
  const id = firstText(data.id, data.name);
  const dispatch = objectValue(data.dispatch);
  const dispatchCommand = text(dispatch.command);
  const label = firstText(
    data.label,
    data.usage,
    data.slash,
    dispatchCommand.startsWith("/") ? dispatchCommand : "",
  );
  if (!id || !label || data.active === false) return null;
  const slash = firstText(
    data.slash,
    data.usage,
    label.startsWith("/") ? label : "",
    dispatchCommand.startsWith("/") ? dispatchCommand : "",
  );
  const usage = slash || label;
  return {
    id,
    name: firstText(data.name, id),
    usage,
    label,
    group: text(data.group),
    dispatch,
    slash,
    summary: text(data.summary),
    shortcut: text(data.shortcut),
    visibleWhen: firstText(data.visibleWhen, data.visible_when, "always"),
    availability: objectValue(data.availability),
    sourceType: text(camelOrSnake(data, "sourceType", "source_type")),
    sourceId: text(camelOrSnake(data, "sourceId", "source_id")),
    active: true,
  };
}

export function normalizeToolDescriptor(item = {}) {
  const data = objectValue(item);
  const name = firstText(data.name, data.id);
  if (!name) return null;
  return {
    name,
    label: firstText(data.label, name),
    iconKey: firstText(camelOrSnake(data, "iconKey", "icon_key"), "wrench"),
    rendererKey: firstText(camelOrSnake(data, "rendererKey", "renderer_key"), "generic"),
    permissionCategory: firstText(
      camelOrSnake(data, "permissionCategory", "permission_category"),
      "other",
    ),
    metadata: objectValue(data.metadata),
  };
}

export function normalizeWorkflowPackageDescriptor(item = {}) {
  const data = objectValue(item);
  const id = firstText(data.id, data.package_id, data.packageId);
  if (!id) return null;
  return {
    id,
    label: firstText(data.label, data.name, id),
    active: Boolean(data.active),
    state: objectValue(data.state),
    metadata: objectValue(data.metadata),
  };
}

export function normalizeAgentApplicationDescriptor(item = {}) {
  const data = objectValue(item);
  const applicationId = firstText(data.applicationId, data.application_id, data.id);
  if (!applicationId) return null;
  return {
    applicationId,
    label: firstText(data.label, data.name, applicationId),
    profileId: text(camelOrSnake(data, "profileId", "profile_id")),
    workflowPackageIds: listValue(
      data.workflowPackageIds || data.workflow_package_ids,
    ).map((value) => text(value)).filter(Boolean),
    active: Boolean(data.active),
    sourceType: text(camelOrSnake(data, "sourceType", "source_type")),
    sourceId: text(camelOrSnake(data, "sourceId", "source_id")),
    default: Boolean(data.default),
    metadata: objectValue(data.metadata),
  };
}

export function normalizeEmptyState(input = {}) {
  const data = objectValue(input);
  return {
    scenarioLabel: firstText(data.scenarioLabel, data.scenario_label),
    primary: firstText(data.primary),
    secondary: firstText(data.secondary),
    pathPlaceholder: firstText(data.pathPlaceholder, data.path_placeholder),
  };
}

function commandFromMode(mode) {
  return {
    id: mode.commandId || `mode.${mode.id}`,
    name: mode.id,
    usage: `/mode ${mode.id}`,
    label: mode.label,
    group: "mode",
    dispatch: { kind: "mode.set", mode: mode.id },
    slash: `/mode ${mode.id}`,
    summary: mode.description,
    shortcut: "",
    visibleWhen: "has_session",
    availability: {},
    sourceType: "capability",
    sourceId: "modes",
    active: true,
  };
}

export function normalizeProtocolCapabilities(input = {}) {
  const data = objectValue(input);
  const modes = listValue(data.modes).map(normalizeModeDescriptor).filter(Boolean);
  const modeCommands = modes.map(commandFromMode);
  const declaredCommands = listValue(data.commands).map(normalizeCommandDescriptor).filter(Boolean);
  const commands = [];
  const seenCommands = new Set();
  for (const command of declaredCommands.concat(modeCommands)) {
    const key = command.id || command.usage;
    if (!key || seenCommands.has(key)) continue;
    seenCommands.add(key);
    commands.push(command);
  }
  const tools = listValue(data.tools).map(normalizeToolDescriptor).filter(Boolean);
  const toolCatalog = {};
  for (const tool of tools) toolCatalog[tool.name] = tool;
  const modeCatalog = {};
  for (const mode of modes) modeCatalog[mode.id] = mode;
  const agentApplication = normalizeAgentApplicationDescriptor(
    data.agentApplication || data.agent_application,
  );
  return {
    version: Number(data.version) || 1,
    modes,
    modeCatalog,
    commands,
    tools,
    toolCatalog,
    workflowPackages: listValue(data.workflowPackages || data.workflow_packages)
      .map(normalizeWorkflowPackageDescriptor)
      .filter(Boolean),
    agentApplication,
    agentApplications: listValue(data.agentApplications || data.agent_applications)
      .map(normalizeAgentApplicationDescriptor)
      .filter(Boolean),
    resources: listValue(data.resources),
    modelProfiles: listValue(data.modelProfiles || data.model_profiles),
    emptyState: normalizeEmptyState(data.emptyState || data.empty_state),
  };
}
