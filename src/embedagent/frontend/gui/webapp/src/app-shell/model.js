import { normalizeProtocolAppBootstrap } from "../session-runtime/protocol-normalizer.js";
import { emptyShellDescriptor, shellCapabilityModel } from "./selectors.js";
import { isRecord, safeValue } from "./validation.js";

function basename(path) {
  const text = String(path || "").replace(/\\/g, "/");
  const parts = text.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : text;
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
    lastFailure: null,
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
    workspaceError: protocol.lastFailure?.code || "",
    diagnostics: normalizeAppDiagnostics(protocol.diagnostics),
    shell: protocol.shell,
    capabilities: shellCapabilityModel(protocol.shell),
    settings: normalizeAppSettings(protocol.settings),
    lastFailure: protocol.lastFailure,
  };
}
