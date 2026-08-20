import { FRONTEND_PROTOCOL_SCHEMA_VERSION } from "./protocol-version.js";

const CURRENT_SCHEMA_VERSION = FRONTEND_PROTOCOL_SCHEMA_VERSION;

function invalid(scope, field) {
  throw new Error(`invalid_${scope}:${field}`);
}

function record(value, scope, field) {
  if (!value || typeof value !== "object" || Array.isArray(value)) invalid(scope, field);
  return value;
}

function array(value, scope, field) {
  if (!Array.isArray(value)) invalid(scope, field);
  return value;
}

function exact(data, allowed, scope, field) {
  for (const key of Object.keys(data)) {
    if (!allowed.has(key)) invalid(scope, `${field}.${key}`);
  }
}

function requiredText(value, scope, field) {
  if (typeof value !== "string" || !value.trim()) invalid(scope, field);
  return value.trim();
}

function optionalText(value, scope, field) {
  if (value === undefined || value === null) return "";
  if (typeof value !== "string") invalid(scope, field);
  return value.trim();
}

function mapping(value, scope, field) {
  return record(value, scope, field);
}

function schemaVersion(value, scope, field = "schema_version") {
  if (value !== CURRENT_SCHEMA_VERSION) invalid(scope, field);
  return value;
}

function bool(value, scope, field) {
  if (typeof value !== "boolean") invalid(scope, field);
  return value;
}

function normalizeFailure(value, scope, field) {
  const data = record(value, scope, field);
  exact(
    data,
    new Set([
      "code",
      "message",
      "retryable",
      "source",
      "phase",
      "kind",
      "correlation_id",
      "safe_message",
      "exception_type",
    ]),
    scope,
    field,
  );
  return Object.freeze({
    code: requiredText(data.code, scope, `${field}.code`),
    message: requiredText(data.message, scope, `${field}.message`),
    retryable: bool(data.retryable, scope, `${field}.retryable`),
    source: requiredText(data.source, scope, `${field}.source`),
    phase: requiredText(data.phase, scope, `${field}.phase`),
    kind: requiredText(data.kind, scope, `${field}.kind`),
    correlationId: optionalText(data.correlation_id, scope, `${field}.correlation_id`),
    safeMessage: optionalText(data.safe_message, scope, `${field}.safe_message`),
    exceptionType: optionalText(data.exception_type, scope, `${field}.exception_type`),
  });
}

function uniqueIds(items, scope, kind) {
  const ids = new Set();
  for (const item of items) {
    if (ids.has(item.id)) invalid(scope, `duplicate_${kind}:${item.id}`);
    ids.add(item.id);
  }
  return ids;
}

export function normalizeModeDescriptor(value) {
  const scope = "capability_snapshot";
  const data = record(value, scope, "mode");
  exact(
    data,
    new Set(["id", "label", "description", "icon_key", "color_token", "command_id"]),
    scope,
    "mode",
  );
  return Object.freeze({
    id: requiredText(data.id, scope, "mode.id"),
    label: requiredText(data.label, scope, "mode.label"),
    description: optionalText(data.description, scope, "mode.description"),
    iconKey: optionalText(data.icon_key, scope, "mode.icon_key"),
    colorToken: optionalText(data.color_token, scope, "mode.color_token"),
    commandId: requiredText(data.command_id, scope, "mode.command_id"),
  });
}

export function normalizeCommandDescriptor(value, scope = "capability_snapshot") {
  const data = record(value, scope, "command");
  exact(
    data,
    new Set(["id", "label", "group", "dispatch", "shortcut", "availability", "summary", "source_type", "source_id"]),
    scope,
    "command",
  );
  const id = requiredText(data.id, scope, "command.id");
  const label = requiredText(data.label, scope, "command.label");
  const dispatch = mapping(data.dispatch, scope, "command.dispatch");
  const availability = mapping(data.availability, scope, "command.availability");
  const slash = typeof dispatch.command === "string" && dispatch.command.startsWith("/")
    ? dispatch.command
    : label.startsWith("/")
      ? label
      : "";
  return Object.freeze({
    id,
    name: id,
    usage: slash || label,
    label,
    group: requiredText(data.group, scope, "command.group"),
    dispatch,
    slash,
    summary: optionalText(data.summary, scope, "command.summary"),
    shortcut: optionalText(data.shortcut, scope, "command.shortcut"),
    visibleWhen: "always",
    availability,
    sourceType: optionalText(data.source_type, scope, "command.source_type"),
    sourceId: optionalText(data.source_id, scope, "command.source_id"),
    active: true,
  });
}

export function normalizeToolDescriptor(value, scope = "capability_snapshot") {
  const data = record(value, scope, "tool");
  exact(
    data,
    new Set(["name", "label", "icon_key", "renderer_key", "permission_category", "metadata"]),
    scope,
    "tool",
  );
  const iconKey = optionalText(data.icon_key, scope, "tool.icon_key");
  return Object.freeze({
    name: requiredText(data.name, scope, "tool.name"),
    label: requiredText(data.label, scope, "tool.label"),
    iconKey: iconKey || "wrench",
    iconKeyDeclared: Boolean(iconKey),
    rendererKey: requiredText(data.renderer_key, scope, "tool.renderer_key"),
    permissionCategory: requiredText(
      data.permission_category,
      scope,
      "tool.permission_category",
    ),
    metadata: mapping(data.metadata, scope, "tool.metadata"),
  });
}

export function normalizeWorkflowPackageDescriptor(value) {
  const scope = "capability_snapshot";
  const data = record(value, scope, "workflow_package");
  exact(
    data,
    new Set(["id", "label", "active", "state", "metadata"]),
    scope,
    "workflow_package",
  );
  return Object.freeze({
    id: requiredText(data.id, scope, "workflow_package.id"),
    label: requiredText(data.label, scope, "workflow_package.label"),
    active: bool(data.active, scope, "workflow_package.active"),
    state: mapping(data.state, scope, "workflow_package.state"),
    metadata: mapping(data.metadata, scope, "workflow_package.metadata"),
  });
}

export function normalizeAgentApplicationDescriptor(value) {
  const scope = "capability_snapshot";
  if (value === undefined || value === null) return null;
  const data = record(value, scope, "agent_application");
  if (Object.keys(data).length === 0) return null;
  exact(
    data,
    new Set([
      "id",
      "label",
      "profile_id",
      "workflow_package_ids",
      "active",
      "source_type",
      "source_id",
      "default",
      "metadata",
    ]),
    scope,
    "agent_application",
  );
  const workflowPackageIds = array(
    data.workflow_package_ids,
    scope,
    "agent_application.workflow_package_ids",
  ).map((item) => requiredText(item, scope, "agent_application.workflow_package_ids"));
  return Object.freeze({
    applicationId: requiredText(data.id, scope, "agent_application.id"),
    label: requiredText(data.label, scope, "agent_application.label"),
    profileId: optionalText(data.profile_id, scope, "agent_application.profile_id"),
    workflowPackageIds,
    active: bool(data.active, scope, "agent_application.active"),
    sourceType: optionalText(data.source_type, scope, "agent_application.source_type"),
    sourceId: optionalText(data.source_id, scope, "agent_application.source_id"),
    default: bool(data.default, scope, "agent_application.default"),
    metadata: mapping(data.metadata, scope, "agent_application.metadata"),
  });
}

export function normalizeEmptyState(value) {
  const scope = "capability_snapshot";
  if (value === undefined || value === null) {
    return Object.freeze({
      scenarioLabel: "",
      primary: "",
      secondary: "",
      pathPlaceholder: "",
    });
  }
  const data = record(value, scope, "empty_state");
  exact(
    data,
    new Set(["scenario_label", "primary", "secondary", "path_placeholder"]),
    scope,
    "empty_state",
  );
  return Object.freeze({
    scenarioLabel: optionalText(data.scenario_label, scope, "empty_state.scenario_label"),
    primary: optionalText(data.primary, scope, "empty_state.primary"),
    secondary: optionalText(data.secondary, scope, "empty_state.secondary"),
    pathPlaceholder: optionalText(data.path_placeholder, scope, "empty_state.path_placeholder"),
  });
}

export function normalizeAppAgentApplicationDescriptor(value) {
  const data = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const applicationId = String(
    data.applicationId || data.application_id || data.id || "",
  ).trim();
  if (!applicationId) return null;
  const workflowPackageIds = Array.isArray(data.workflowPackageIds)
    ? data.workflowPackageIds
    : Array.isArray(data.workflow_package_ids)
      ? data.workflow_package_ids
      : [];
  return {
    applicationId,
    label: String(data.label || data.name || applicationId),
    profileId: String(data.profileId || data.profile_id || ""),
    workflowPackageIds: workflowPackageIds.map((item) => String(item)).filter(Boolean),
    active: Boolean(data.active),
    sourceType: String(data.sourceType || data.source_type || ""),
    sourceId: String(data.sourceId || data.source_id || ""),
    default: Boolean(data.default),
    metadata: data.metadata && typeof data.metadata === "object" ? data.metadata : {},
  };
}

export function normalizeAppEmptyState(value) {
  const data = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  return {
    scenarioLabel: String(data.scenarioLabel || data.scenario_label || "").trim(),
    primary: String(data.primary || "").trim(),
    secondary: String(data.secondary || "").trim(),
    pathPlaceholder: String(data.pathPlaceholder || data.path_placeholder || "").trim(),
  };
}

function commandFromMode(mode) {
  return Object.freeze({
    id: mode.commandId,
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
  });
}

export function normalizeProtocolCapabilities(value) {
  const scope = "capability_snapshot";
  const data = record(value, scope, "root");
  exact(
    data,
    new Set([
      "schema_version",
      "modes",
      "commands",
      "tools",
      "workflow_packages",
      "agent_application",
      "agent_applications",
      "resources",
      "model_profiles",
      "empty_state",
    ]),
    scope,
    "root",
  );
  const version = schemaVersion(data.schema_version, scope);
  const modes = array(data.modes, scope, "modes").map(normalizeModeDescriptor);
  const declaredCommands = array(data.commands, scope, "commands").map(normalizeCommandDescriptor);
  const commands = [];
  const seenCommands = new Set();
  for (const command of declaredCommands.concat(modes.map(commandFromMode))) {
    if (seenCommands.has(command.id)) continue;
    seenCommands.add(command.id);
    commands.push(command);
  }
  const tools = array(data.tools, scope, "tools").map(normalizeToolDescriptor);
  const toolCatalog = Object.fromEntries(tools.map((tool) => [tool.name, tool]));
  const modeCatalog = Object.fromEntries(modes.map((mode) => [mode.id, mode]));
  const agentApplicationRecord = record(
    data.agent_application,
    scope,
    "agent_application",
  );
  const agentApplication = Object.keys(agentApplicationRecord).length
    ? normalizeAgentApplicationDescriptor(agentApplicationRecord)
    : null;
  const resources = array(data.resources, scope, "resources").map((item) =>
    record(item, scope, "resources"));
  const modelProfiles = array(data.model_profiles, scope, "model_profiles").map((item) =>
    record(item, scope, "model_profiles"));
  return Object.freeze({
    schemaVersion: version,
    version,
    modes,
    modeCatalog,
    commands,
    tools,
    toolCatalog,
    workflowPackages: array(data.workflow_packages, scope, "workflow_packages")
      .map(normalizeWorkflowPackageDescriptor),
    agentApplication,
    agentApplications: array(data.agent_applications, scope, "agent_applications")
      .map(normalizeAgentApplicationDescriptor),
    resources,
    modelProfiles,
    emptyState: normalizeEmptyState(data.empty_state),
  });
}

export function emptyProtocolCapabilities() {
  return normalizeProtocolCapabilities({
    schema_version: FRONTEND_PROTOCOL_SCHEMA_VERSION,
    modes: [],
    commands: [],
    tools: [],
    workflow_packages: [],
    agent_application: {},
    agent_applications: [],
    resources: [],
    model_profiles: [],
    empty_state: {},
  });
}

function normalizeThread(value, scope) {
  const data = record(value, scope, "thread");
  exact(
    data,
    new Set([
      "id",
      "title",
      "archived",
      "current_mode",
      "status",
      "updated_at",
      "pending_interaction",
    ]),
    scope,
    "thread",
  );
  return Object.freeze({
    id: requiredText(data.id, scope, "thread.id"),
    title: optionalText(data.title, scope, "thread.title"),
    archived: bool(data.archived, scope, "thread.archived"),
    currentMode: optionalText(data.current_mode, scope, "thread.current_mode"),
    status: optionalText(data.status, scope, "thread.status"),
    updatedAt: optionalText(data.updated_at, scope, "thread.updated_at"),
    pendingInteraction: bool(data.pending_interaction, scope, "thread.pending_interaction"),
  });
}

function normalizeShellDescriptor(value, scope) {
  const data = record(value, scope, "shell");
  exact(
    data,
    new Set([
      "schema_version",
      "commands",
      "surfaces",
      "keybindings",
      "tool_presentations",
      "timeline_items",
      "interactions",
    ]),
    scope,
    "shell",
  );
  const commands = array(data.commands, scope, "shell.commands").map((item) =>
    normalizeCommandDescriptor(item, scope));
  schemaVersion(data.schema_version, scope, "shell.schema_version");
  const surfaces = array(data.surfaces, scope, "shell.surfaces").map((value) => {
    const item = record(value, scope, "shell.surface");
    exact(
      item,
      new Set(["id", "label", "placement", "renderer_key", "availability", "metadata"]),
      scope,
      "shell.surface",
    );
    const placement = requiredText(item.placement, scope, "shell.surface.placement");
    if (placement !== "overlay" && placement !== "secondary") {
      invalid(scope, "shell.surface.placement");
    }
    return Object.freeze({
      id: requiredText(item.id, scope, "shell.surface.id"),
      label: requiredText(item.label, scope, "shell.surface.label"),
      placement,
      rendererKey: requiredText(item.renderer_key, scope, "shell.surface.renderer_key"),
      availability: mapping(item.availability, scope, "shell.surface.availability"),
      metadata: mapping(item.metadata, scope, "shell.surface.metadata"),
    });
  });
  const keybindings = array(data.keybindings, scope, "shell.keybindings").map((value) => {
    const item = record(value, scope, "shell.keybinding");
    exact(item, new Set(["command_id", "keys", "when"]), scope, "shell.keybinding");
    return Object.freeze({
      commandId: requiredText(item.command_id, scope, "shell.keybinding.command_id"),
      keys: requiredText(item.keys, scope, "shell.keybinding.keys"),
      when: mapping(item.when, scope, "shell.keybinding.when"),
    });
  });
  const timelineItems = array(data.timeline_items, scope, "shell.timeline_items").map((value) => {
    const item = record(value, scope, "shell.timeline_item");
    exact(item, new Set(["event_kind", "renderer_key", "priority"]), scope, "shell.timeline_item");
    if (!Number.isInteger(item.priority)) invalid(scope, "shell.timeline_item.priority");
    return Object.freeze({
      eventKind: requiredText(item.event_kind, scope, "shell.timeline_item.event_kind"),
      rendererKey: requiredText(item.renderer_key, scope, "shell.timeline_item.renderer_key"),
      priority: item.priority,
    });
  });
  const interactions = array(data.interactions, scope, "shell.interactions").map((value) => {
    const item = record(value, scope, "shell.interaction");
    exact(item, new Set(["kind", "renderer_key"]), scope, "shell.interaction");
    return Object.freeze({
      kind: requiredText(item.kind, scope, "shell.interaction.kind"),
      rendererKey: requiredText(item.renderer_key, scope, "shell.interaction.renderer_key"),
    });
  });
  const commandIds = uniqueIds(commands, scope, "shell_command");
  uniqueIds(surfaces, scope, "shell_surface");
  for (const command of commands) {
    if (typeof command.dispatch.kind !== "string" || !command.dispatch.kind.trim()) {
      invalid(scope, `shell_command_dispatch_kind:${command.id}`);
    }
  }
  for (const keybinding of keybindings) {
    if (!commandIds.has(keybinding.commandId)) {
      invalid(scope, `unknown_keybinding_command:${keybinding.commandId}`);
    }
  }
  return Object.freeze({
    schemaVersion: data.schema_version,
    commands,
    surfaces,
    keybindings,
    toolPresentations: array(data.tool_presentations, scope, "shell.tool_presentations")
      .map((item) => normalizeToolDescriptor(item, scope)),
    timelineItems,
    interactions,
  });
}

export function normalizeProtocolAppBootstrap(value) {
  const scope = "app_bootstrap";
  const data = record(value, scope, "root");
  exact(
    data,
    new Set([
      "schema_version",
      "app",
      "workspaces",
      "active_workspace",
      "has_active_workspace",
      "shell",
      "settings",
      "diagnostics",
      "last_failure",
      "removed",
    ]),
    scope,
    "root",
  );
  const activeWorkspace = data.active_workspace === null
    ? null
    : mapping(data.active_workspace, scope, "active_workspace");
  return Object.freeze({
    schemaVersion: schemaVersion(data.schema_version, scope),
    app: mapping(data.app, scope, "app"),
    workspaces: array(data.workspaces, scope, "workspaces").map((item) =>
      record(item, scope, "workspaces")),
    activeWorkspace,
    hasActiveWorkspace: bool(data.has_active_workspace, scope, "has_active_workspace"),
    shell: normalizeShellDescriptor(data.shell, scope),
    settings: mapping(data.settings, scope, "settings"),
    diagnostics: mapping(data.diagnostics, scope, "diagnostics"),
    lastFailure: data.last_failure === null || data.last_failure === undefined
      ? null
      : normalizeFailure(data.last_failure, scope, "last_failure"),
    removed: data.removed === undefined ? undefined : bool(data.removed, scope, "removed"),
  });
}

export function normalizeSessionBootstrap(value) {
  const scope = "session_bootstrap";
  const data = record(value, scope, "root");
  exact(
    data,
    new Set([
      "schema_version",
      "event_cursor",
      "thread",
      "snapshot",
      "history",
      "capabilities",
      "plan",
      "permission_context",
    ]),
    scope,
    "root",
  );
  if (!Object.hasOwn(data, "event_cursor") || !Number.isInteger(data.event_cursor)
      || data.event_cursor < 0) {
    invalid(scope, "event_cursor");
  }
  const history = record(data.history, scope, "history");
  exact(history, new Set(["activities", "integrity"]), scope, "history");
  const plan = data.plan === null ? null : mapping(data.plan, scope, "plan");
  return Object.freeze({
    schemaVersion: schemaVersion(data.schema_version, scope),
    eventCursor: data.event_cursor,
    thread: normalizeThread(data.thread, scope),
    snapshot: mapping(data.snapshot, scope, "snapshot"),
    history: Object.freeze({
      activities: array(history.activities, scope, "history.activities"),
      integrity: mapping(history.integrity, scope, "history.integrity"),
    }),
    capabilities: normalizeProtocolCapabilities(data.capabilities),
    plan,
    permissionContext: mapping(data.permission_context, scope, "permission_context"),
  });
}
