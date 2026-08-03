import { normalizeProtocolAppBootstrap } from "../session-runtime/protocol-normalizer.js";

const SECRET_KEY_PARTS = ["api_key", "authorization", "password", "secret", "token"];
const BLOCKED_KEYS = ["prompt", "transcript", "tool_output"];

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function basename(path) {
  const text = String(path || "").replace(/\\/g, "/");
  const parts = text.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : text;
}

function isBlockedKey(key) {
  const lowered = String(key || "").toLowerCase();
  if (BLOCKED_KEYS.includes(lowered)) return true;
  return SECRET_KEY_PARTS.some((part) => lowered.includes(part));
}

function safeValue(value) {
  if (Array.isArray(value)) return value.map(safeValue);
  if (isRecord(value)) {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !isBlockedKey(key))
        .map(([key, item]) => [key, safeValue(item)]),
    );
  }
  return value;
}

function emptyShellDescriptor() {
  return Object.freeze({
    schemaVersion: 1,
    commands: Object.freeze([]),
    surfaces: Object.freeze([]),
    keybindings: Object.freeze([]),
    toolPresentations: Object.freeze([]),
    timelineItems: Object.freeze([]),
    interactions: Object.freeze([]),
  });
}

function surfaceRecord(descriptor) {
  const metadata = isRecord(descriptor.metadata) ? descriptor.metadata : {};
  return Object.freeze({
    id: descriptor.id,
    kind: descriptor.id,
    title: descriptor.label,
    description: String(metadata.description || ""),
    placement: "right",
    rendererKey: descriptor.rendererKey,
    launcher: true,
    launcherOrder: Number(metadata.order || 0),
    command: false,
    commandLabel: "",
    resourceId: String(metadata.resource_id || ""),
    defaultResourceId: String(metadata.default_resource_id || ""),
    closeBehavior: String(metadata.close_behavior || "closable"),
    readOnly: metadata.read_only === true,
    offline: metadata.offline === true,
    keywords: Array.isArray(metadata.keywords) ? metadata.keywords.map(String) : [],
    dispatch: {},
    bodyKind: String(metadata.body_kind || ""),
    panelKind: String(metadata.panel_kind || ""),
    openKind: String(metadata.open_kind || ""),
    activationKind: String(metadata.activation_kind || ""),
  });
}

function commandRecord(descriptor) {
  const availability = isRecord(descriptor.availability) ? descriptor.availability : {};
  const dispatch = isRecord(descriptor.dispatch) ? descriptor.dispatch : {};
  const commandName = dispatch.kind === "session.command"
    ? String(dispatch.command || "")
    : "";
  return Object.freeze({
    id: descriptor.id,
    group: descriptor.group,
    label: descriptor.label,
    description: descriptor.summary,
    slash: commandName ? `/${commandName}` : "",
    visibleWhen: String(availability.visible_when || "always"),
    keywords: [],
    dispatch,
  });
}

function keybindingRecord(descriptor) {
  const when = isRecord(descriptor.when) ? descriptor.when : {};
  return Object.freeze({
    commandId: descriptor.commandId,
    key: descriptor.keys.toLowerCase(),
    when: String(when.context || "always"),
  });
}

export function shellCapabilityModel(shell = emptyShellDescriptor()) {
  if (!isRecord(shell) || shell.schemaVersion !== 1) {
    throw new TypeError("invalid_app_bootstrap:shell");
  }
  for (const key of [
    "commands",
    "surfaces",
    "keybindings",
    "toolPresentations",
    "timelineItems",
    "interactions",
  ]) {
    if (!Array.isArray(shell[key])) throw new TypeError(`invalid_app_bootstrap:shell.${key}`);
  }
  const secondarySurfaces = shell.surfaces
    .filter((item) => item.placement === "secondary")
    .map(surfaceRecord);
  return Object.freeze({
    shell,
    appCommands: Object.freeze([]),
    workspaceCommands: Object.freeze([]),
    workbenchCommands: Object.freeze(shell.commands.map(commandRecord)),
    surfaces: Object.freeze({
      rightPanel: Object.freeze(secondarySurfaces),
      bottomDrawer: Object.freeze([]),
      chrome: Object.freeze({}),
    }),
    keybindings: Object.freeze(shell.keybindings.map(keybindingRecord)),
    commandPalette: Object.freeze({ groups: Object.freeze([]), labels: Object.freeze({}) }),
    chrome: Object.freeze({}),
    home: Object.freeze({}),
    sourceControl: Object.freeze({
      enabled: secondarySurfaces.some((item) => item.rendererKey === "source_control"),
    }),
    terminal: Object.freeze({
      enabled: secondarySurfaces.some((item) => item.rendererKey === "terminal"),
    }),
    preview: Object.freeze({
      enabled: secondarySurfaces.some((item) => item.rendererKey === "preview"),
    }),
    threadLifecycle: Object.freeze({}),
    emptyState: null,
  });
}

export function normalizeWorkspaceRecord(input = {}) {
  if (!isRecord(input)) throw new TypeError("invalid_app_bootstrap:workspace");
  const path = String(input.path || "");
  const label = String(input.label || "").trim() || basename(path) || path;
  return Object.freeze({
    id: String(input.id || ""),
    path,
    label,
    exists: input.exists !== false,
    created_at: String(input.created_at || ""),
    last_opened_at: String(input.last_opened_at || ""),
  });
}

export function normalizeAppSettings(input = {}) {
  if (!isRecord(input)) throw new TypeError("invalid_app_bootstrap:settings");
  return Object.freeze({
    confirm_workspace_switch: input.confirm_workspace_switch !== false,
    show_diagnostics_badge: input.show_diagnostics_badge !== false,
  });
}

export function normalizeAppDiagnostics(input = {}) {
  const safe = safeValue(input || {});
  if (!isRecord(safe)) throw new TypeError("invalid_app_bootstrap:diagnostics");
  return Object.freeze({
    host: Object.freeze(isRecord(safe.host) ? safe.host : {}),
    runtime: Object.freeze(isRecord(safe.runtime) ? safe.runtime : {}),
    renderer: Object.freeze(isRecord(safe.renderer) ? safe.renderer : {}),
    workspace_registry: Object.freeze(
      isRecord(safe.workspace_registry) ? safe.workspace_registry : {},
    ),
    active_core: Object.freeze(isRecord(safe.active_core) ? safe.active_core : {}),
  });
}

function normalizeAppMetadata(input = {}) {
  if (!isRecord(input)) throw new TypeError("invalid_app_bootstrap:app");
  return Object.freeze({
    shellVersion: Number(input.shell_version || 1),
    productName: String(input.product_name || ""),
    protocol: String(input.protocol || "gui_app_shell_v1"),
  });
}

export function createAppShellState() {
  const shell = emptyShellDescriptor();
  return {
    bootstrapLoaded: false,
    app: normalizeAppMetadata(),
    workspaces: [],
    activeWorkspace: null,
    hasActiveWorkspace: false,
    workspacePathInput: "",
    workspaceError: "",
    activatingWorkspace: false,
    diagnostics: normalizeAppDiagnostics(),
    shell,
    capabilities: shellCapabilityModel(shell),
    settings: normalizeAppSettings(),
    lastError: "",
  };
}

export function normalizeAppBootstrap(payload = {}) {
  const protocol = normalizeProtocolAppBootstrap(payload);
  const workspaces = protocol.workspaces
    .map(normalizeWorkspaceRecord)
    .filter((item) => item.id);
  const activeWorkspace = protocol.activeWorkspace
    ? normalizeWorkspaceRecord(protocol.activeWorkspace)
    : null;
  return {
    ...createAppShellState(),
    bootstrapLoaded: true,
    app: normalizeAppMetadata(protocol.app),
    workspaces,
    activeWorkspace: activeWorkspace && activeWorkspace.id ? activeWorkspace : null,
    hasActiveWorkspace: Boolean(protocol.hasActiveWorkspace && activeWorkspace),
    workspaceError: protocol.lastError,
    diagnostics: normalizeAppDiagnostics(protocol.diagnostics),
    shell: protocol.shell,
    capabilities: shellCapabilityModel(protocol.shell),
    settings: normalizeAppSettings(protocol.settings),
    lastError: protocol.lastError,
  };
}
