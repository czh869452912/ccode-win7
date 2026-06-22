const SECRET_KEY_PARTS = ["api_key", "authorization", "password", "secret", "token"];
const BLOCKED_KEYS = ["prompt", "transcript", "tool_output"];

function basename(path) {
  const text = String(path || "").replace(/\\/g, "/");
  const parts = text.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : text;
}

function snakeOrCamel(input, snake, camel, fallback) {
  if (!input || typeof input !== "object") return fallback;
  if (Object.prototype.hasOwnProperty.call(input, snake)) return input[snake];
  if (Object.prototype.hasOwnProperty.call(input, camel)) return input[camel];
  return fallback;
}

function isBlockedKey(key) {
  const lowered = String(key || "").toLowerCase();
  if (BLOCKED_KEYS.includes(lowered)) return true;
  return SECRET_KEY_PARTS.some((part) => lowered.includes(part));
}

function safeValue(value) {
  if (Array.isArray(value)) return value.map(safeValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !isBlockedKey(key))
        .map(([key, item]) => [key, safeValue(item)]),
    );
  }
  return value;
}

export function normalizeWorkspaceRecord(input = {}) {
  const path = String(input.path || "");
  const label = String(input.label || "").trim() || basename(path) || path || "Workspace";
  return {
    id: String(input.id || ""),
    path,
    label,
    exists: input.exists !== false,
    created_at: String(input.created_at || input.createdAt || ""),
    last_opened_at: String(input.last_opened_at || input.lastOpenedAt || ""),
  };
}

export function normalizeAppSettings(input = {}) {
  const confirm = snakeOrCamel(input, "confirm_workspace_switch", "confirmWorkspaceSwitch", true);
  const diagnostics = snakeOrCamel(input, "show_diagnostics_badge", "showDiagnosticsBadge", true);
  return {
    confirm_workspace_switch: Boolean(confirm),
    show_diagnostics_badge: Boolean(diagnostics),
  };
}

function normalizeThreadLifecycle(input = {}) {
  const raw = snakeOrCamel(input, "thread_lifecycle", "threadLifecycle", {});
  const value = raw && typeof raw === "object" ? raw : {};
  return {
    rename: value.rename === true,
    fork: value.fork === true,
    archive: value.archive === true,
  };
}

function normalizeTerminalCapability(input = {}) {
  const value = input.terminal && typeof input.terminal === "object" ? input.terminal : {};
  return {
    enabled: value.enabled === true,
    pty: value.pty === true,
    resize: value.resize === true,
    historyPersistent:
      value.history_persistent === true || value.historyPersistent === true,
    maxBufferBytes: Number(value.max_buffer_bytes || value.maxBufferBytes || 0),
  };
}

function normalizeSourceControlCapability(input = {}) {
  const raw = input.source_control || input.sourceControl || {};
  const value = raw && typeof raw === "object" ? raw : {};
  return {
    enabled: value.enabled === true,
    vcs: Array.isArray(value.vcs) ? value.vcs.map(String) : [],
    readOnly: value.read_only !== false && value.readOnly !== false,
    remoteProviders:
      value.remote_providers === true || value.remoteProviders === true,
    network: value.network === true,
    checkpoints: value.checkpoints === true,
    requiresActiveWorkspace:
      value.requires_active_workspace === true || value.requiresActiveWorkspace === true,
  };
}

export function normalizeAppCapabilities(input = {}) {
  const surfaces = input.surfaces && typeof input.surfaces === "object" ? input.surfaces : {};
  return {
    appCommands: Array.isArray(input.app_commands)
      ? input.app_commands.map(String)
      : Array.isArray(input.appCommands)
        ? input.appCommands.map(String)
        : ["app.settings", "app.diagnostics", "app.source_control", "app.reload"],
    workspaceCommands: Array.isArray(input.workspace_commands)
      ? input.workspace_commands.map(String)
      : Array.isArray(input.workspaceCommands)
        ? input.workspaceCommands.map(String)
        : ["workspace.open", "workspace.refresh", "workspace.remove_current"],
    surfaces: {
      rightPanel: Array.isArray(surfaces.right_panel)
        ? surfaces.right_panel.map(String)
        : Array.isArray(surfaces.rightPanel)
          ? surfaces.rightPanel.map(String)
          : ["settings", "diagnostics", "source_control"],
      bottomDrawer: Array.isArray(surfaces.bottom_drawer)
        ? surfaces.bottom_drawer.map(String)
        : Array.isArray(surfaces.bottomDrawer)
          ? surfaces.bottomDrawer.map(String)
          : [],
    },
    sourceControl: normalizeSourceControlCapability(input),
    terminal: normalizeTerminalCapability(input),
    threadLifecycle: normalizeThreadLifecycle(input),
  };
}

export function normalizeAppDiagnostics(input = {}) {
  const safe = safeValue(input || {});
  return {
    host: safe.host && typeof safe.host === "object" ? safe.host : {},
    runtime: safe.runtime && typeof safe.runtime === "object" ? safe.runtime : {},
    renderer: safe.renderer && typeof safe.renderer === "object" ? safe.renderer : {},
    workspace_registry:
      safe.workspace_registry && typeof safe.workspace_registry === "object"
        ? safe.workspace_registry
        : safe.workspaceRegistry && typeof safe.workspaceRegistry === "object"
          ? safe.workspaceRegistry
          : {},
    active_core:
      safe.active_core && typeof safe.active_core === "object"
        ? safe.active_core
        : safe.activeCore && typeof safe.activeCore === "object"
          ? safe.activeCore
          : {},
  };
}

function normalizeAppMetadata(input = {}) {
  return {
    shellVersion: Number(input.shell_version || input.shellVersion || 1),
    productName: String(input.product_name || input.productName || "EmbedAgent"),
    protocol: String(input.protocol || "gui_app_shell_v1"),
  };
}

export function createAppShellState() {
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
    capabilities: normalizeAppCapabilities(),
    settings: normalizeAppSettings(),
    lastError: "",
  };
}

export function normalizeAppBootstrap(payload = {}) {
  const workspaces = Array.isArray(payload.workspaces)
    ? payload.workspaces.map(normalizeWorkspaceRecord).filter((item) => item.id)
    : [];
  const activePayload = payload.active_workspace || payload.activeWorkspace || null;
  const activeWorkspace = activePayload ? normalizeWorkspaceRecord(activePayload) : null;
  const hasActiveWorkspace = Boolean(
    snakeOrCamel(payload, "has_active_workspace", "hasActiveWorkspace", false) && activeWorkspace,
  );
  const lastError = String(snakeOrCamel(payload, "last_error", "lastError", "") || "");
  return {
    ...createAppShellState(),
    bootstrapLoaded: true,
    app: normalizeAppMetadata(payload.app || {}),
    workspaces,
    activeWorkspace: activeWorkspace && activeWorkspace.id ? activeWorkspace : null,
    hasActiveWorkspace,
    workspaceError: lastError,
    diagnostics: normalizeAppDiagnostics(payload.diagnostics || {}),
    capabilities: normalizeAppCapabilities(payload.capabilities || {}),
    settings: normalizeAppSettings(payload.settings || {}),
    lastError,
  };
}
