import {
  normalizeAgentApplicationDescriptor,
  normalizeEmptyState,
} from "../session-runtime/protocol-normalizer.js";

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

function normalizeThreadLifecycleAction(input = {}, index = 0) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const id = String(input.id || input.kind || "").trim();
  if (!id) return null;
  return {
    id,
    label: String(input.label || id).trim() || id,
    capability: String(input.capability || id).trim() || id,
    order: numberOrDefault(input.order || input.launcher_order || input.launcherOrder, index * 10),
    enabled: input.enabled !== false,
    danger: input.danger === true,
    description: String(input.description || ""),
    promptTitle: String(input.prompt_title || input.promptTitle || ""),
    promptInitial: String(input.prompt_initial || input.promptInitial || ""),
    confirmTitle: String(input.confirm_title || input.confirmTitle || ""),
    emptyTitle: String(input.empty_title || input.emptyTitle || ""),
    emptyBody: String(input.empty_body || input.emptyBody || ""),
    successTitle: String(input.success_title || input.successTitle || ""),
    successBody: String(input.success_body || input.successBody || ""),
    failureTitle: String(input.failure_title || input.failureTitle || ""),
  };
}

function normalizeThreadLifecycleActions(items) {
  if (!Array.isArray(items)) return [];
  const result = [];
  const seen = new Set();
  for (let index = 0; index < items.length; index += 1) {
    const action = normalizeThreadLifecycleAction(items[index], index);
    if (!action || seen.has(action.id)) continue;
    seen.add(action.id);
    result.push(action);
  }
  return result.sort((left, right) => left.order - right.order || left.label.localeCompare(right.label));
}

function normalizeThreadLifecycle(input = {}) {
  const raw = snakeOrCamel(input, "thread_lifecycle", "threadLifecycle", {});
  const value = raw && typeof raw === "object" ? raw : {};
  return {
    actions: normalizeThreadLifecycleActions(value.actions || value.thread_lifecycle_actions),
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
    chrome: normalizeTerminalChrome(value.chrome || {}),
  };
}

function normalizeTerminalChrome(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  return {
    titlePrefix: String(value.title_prefix || value.titlePrefix || ""),
    defaultTitle: String(value.default_title || value.defaultTitle || ""),
    sessionRequiredNotice: String(
      value.session_required_notice || value.sessionRequiredNotice || "",
    ),
    openFailedNotice: String(value.open_failed_notice || value.openFailedNotice || ""),
    writeFailedNotice: String(value.write_failed_notice || value.writeFailedNotice || ""),
    clearFailedNotice: String(value.clear_failed_notice || value.clearFailedNotice || ""),
    restartFailedNotice: String(
      value.restart_failed_notice || value.restartFailedNotice || "",
    ),
    closeFailedNotice: String(value.close_failed_notice || value.closeFailedNotice || ""),
    newLabel: String(value.new_label || value.newLabel || ""),
    newTitle: String(value.new_title || value.newTitle || ""),
    splitLabel: String(value.split_label || value.splitLabel || ""),
    splitTitle: String(value.split_title || value.splitTitle || ""),
    splitVerticalLabel: String(value.split_vertical_label || value.splitVerticalLabel || ""),
    splitVerticalTitle: String(value.split_vertical_title || value.splitVerticalTitle || ""),
    drawerLabel: String(value.drawer_label || value.drawerLabel || ""),
    unavailableMessage: String(value.unavailable_message || value.unavailableMessage || ""),
    commandPlaceholder: String(value.command_placeholder || value.commandPlaceholder || ""),
    clearLabel: String(value.clear_label || value.clearLabel || ""),
    restartLabel: String(value.restart_label || value.restartLabel || ""),
    closeLabel: String(value.close_label || value.closeLabel || ""),
    emptyMessage: String(value.empty_message || value.emptyMessage || ""),
    emptyActionLabel: String(value.empty_action_label || value.emptyActionLabel || ""),
  };
}

function normalizePreviewServer(input = {}) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const url = String(input.url || input.href || "").trim();
  if (!url) return null;
  const port = Number(input.port);
  return {
    label: String(input.label || input.name || "").trim(),
    url,
    port: Number.isFinite(port) && port > 0 ? Math.trunc(port) : null,
  };
}

function normalizePreviewServers(items) {
  if (!Array.isArray(items)) return [];
  const result = [];
  const seen = new Set();
  for (const item of items) {
    const server = normalizePreviewServer(item);
    if (!server || seen.has(server.url)) continue;
    seen.add(server.url);
    result.push(server);
  }
  return result;
}

function normalizePreviewCapability(input = {}) {
  const value = input.preview && typeof input.preview === "object" ? input.preview : {};
  return {
    enabled: value.enabled === true,
    localServers: normalizePreviewServers(value.local_servers || value.localServers),
    chrome: normalizePreviewChrome(value.chrome || {}),
  };
}

function normalizePreviewChrome(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  return {
    refreshLabel: String(value.refresh_label || value.refreshLabel || ""),
    loadingLabel: String(value.loading_label || value.loadingLabel || ""),
    refreshAriaLabel: String(value.refresh_aria_label || value.refreshAriaLabel || ""),
    loadingAriaLabel: String(value.loading_aria_label || value.loadingAriaLabel || ""),
    urlPlaceholder: String(value.url_placeholder || value.urlPlaceholder || ""),
    urlAriaLabel: String(value.url_aria_label || value.urlAriaLabel || ""),
    openExternalLabel: String(value.open_external_label || value.openExternalLabel || ""),
    annotateLabel: String(value.annotate_label || value.annotateLabel || ""),
    moreActionsLabel: String(value.more_actions_label || value.moreActionsLabel || ""),
    unavailableTitle: String(value.unavailable_title || value.unavailableTitle || ""),
    unavailableBody: String(value.unavailable_body || value.unavailableBody || ""),
    unreachableBody: String(value.unreachable_body || value.unreachableBody || ""),
    reloadLabel: String(value.reload_label || value.reloadLabel || ""),
    failedNotice: String(value.failed_notice || value.failedNotice || ""),
    refreshFailedNotice: String(value.refresh_failed_notice || value.refreshFailedNotice || ""),
    openFailedNotice: String(value.open_failed_notice || value.openFailedNotice || ""),
    sessionRequiredNotice: String(
      value.session_required_notice || value.sessionRequiredNotice || "",
    ),
    serversTitle: String(value.servers_title || value.serversTitle || ""),
    emptyTitle: String(value.empty_title || value.emptyTitle || ""),
    serversDescription: String(value.servers_description || value.serversDescription || ""),
    emptyDescription: String(value.empty_description || value.emptyDescription || ""),
    localServerFallbackLabel: String(
      value.local_server_fallback_label || value.localServerFallbackLabel || "",
    ),
    statusLoading: String(value.status_loading || value.statusLoading || ""),
    statusReady: String(value.status_ready || value.statusReady || ""),
    statusFailed: String(value.status_failed || value.statusFailed || ""),
    statusIdle: String(value.status_idle || value.statusIdle || ""),
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

function numberOrDefault(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeKeywords(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function normalizeSurfaceCapability(input = {}, placement = "right") {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const kind = String(input.id || input.kind || "").trim();
  if (!kind) return null;
  const title = String(input.title || kind).trim() || kind;
  return {
    id: kind,
    kind,
    title,
    icon: String(input.icon || "").trim(),
    description: String(input.description || ""),
    placement,
    resourceId: String(input.resource_id || input.resourceId || ""),
    defaultResourceId: String(input.default_resource_id || input.defaultResourceId || ""),
    closeBehavior: String(input.close_behavior || input.closeBehavior || (placement === "bottom" ? "pinned" : "closable")),
    launcher: input.launcher !== false,
    launcherOrder: numberOrDefault(input.launcher_order || input.launcherOrder, 0),
    command: input.command !== false,
    commandLabel: String(input.command_label || input.commandLabel || ""),
    slash: String(input.slash || ""),
    visibleWhen: String(input.visible_when || input.visibleWhen || "always"),
    readOnly: input.read_only === true || input.readOnly === true,
    offline: input.offline === true,
    keywords: normalizeKeywords(input.keywords),
  };
}

function normalizeSurfaceChrome(input = {}) {
  const surfaces = input.surfaces && typeof input.surfaces === "object" ? input.surfaces : {};
  const raw = surfaces.chrome || surfaces.surface_chrome || {};
  const value = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  return {
    rightPanelAriaLabel: String(value.right_panel_aria_label || value.rightPanelAriaLabel || ""),
    addSurfaceLabel: String(value.add_surface_label || value.addSurfaceLabel || ""),
    emptyTitle: String(value.empty_title || value.emptyTitle || ""),
    emptyBody: String(value.empty_body || value.emptyBody || ""),
    surfaceActionsLabelPrefix: String(
      value.surface_actions_label_prefix || value.surfaceActionsLabelPrefix || "",
    ),
    closeLabelPrefix: String(value.close_label_prefix || value.closeLabelPrefix || ""),
    closeActionLabel: String(value.close_action_label || value.closeActionLabel || ""),
    closeOthersActionLabel: String(
      value.close_others_action_label || value.closeOthersActionLabel || "",
    ),
    closeToRightActionLabel: String(
      value.close_to_right_action_label || value.closeToRightActionLabel || "",
    ),
    closeAllActionLabel: String(value.close_all_action_label || value.closeAllActionLabel || ""),
    defaultIcon: String(value.default_icon || value.defaultIcon || ""),
  };
}

function normalizeSurfaceCapabilityList(items, placement) {
  if (!Array.isArray(items)) return [];
  const result = [];
  const seen = new Set();
  for (const item of items) {
    const surface = normalizeSurfaceCapability(item, placement);
    if (!surface || seen.has(surface.kind)) continue;
    seen.add(surface.kind);
    result.push(surface);
  }
  return result;
}

function normalizeKeybinding(input = {}) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const key = String(input.key || "").trim().toLowerCase();
  const commandId = String(input.command_id || input.commandId || "").trim();
  if (!key || !commandId) return null;
  return {
    key,
    commandId,
    when: String(input.when || "always").trim() || "always",
  };
}

function normalizeKeybindings(items) {
  if (!Array.isArray(items)) return [];
  const result = [];
  const seen = new Set();
  for (const item of items) {
    const binding = normalizeKeybinding(item);
    const id = binding ? `${binding.key}:${binding.commandId}:${binding.when}` : "";
    if (!binding || seen.has(id)) continue;
    seen.add(id);
    result.push(binding);
  }
  return result;
}

function normalizeAppCommandDescriptor(input = {}, defaultGroup = "app", index = 0) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const id = String(input.id || input.name || "").trim();
  if (!id) return null;
  const label = String(input.label || id).trim() || id;
  return {
    id,
    group: String(input.group || defaultGroup).trim() || defaultGroup,
    label,
    slash: String(input.slash || ""),
    surface: String(input.surface || ""),
    drawer: String(input.drawer || ""),
    visibleWhen: String(input.visible_when || input.visibleWhen || "always").trim() || "always",
    order: numberOrDefault(input.order || input.launcher_order || input.launcherOrder, index * 10),
    keywords: normalizeKeywords(input.keywords),
    description: String(input.description || ""),
    dispatch: input.dispatch && typeof input.dispatch === "object" ? { ...input.dispatch } : {},
  };
}

function normalizeAppCommandDescriptors(items, defaultGroup) {
  if (!Array.isArray(items)) return [];
  const result = [];
  const seen = new Set();
  for (let index = 0; index < items.length; index += 1) {
    const command = normalizeAppCommandDescriptor(items[index], defaultGroup, index);
    if (!command || seen.has(command.id)) continue;
    seen.add(command.id);
    result.push(command);
  }
  return result.sort((left, right) => left.order - right.order || left.label.localeCompare(right.label));
}

function normalizePaletteGroupDescriptor(input = {}, index = 0) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const id = String(input.id || input.group || "").trim();
  if (!id) return null;
  return {
    id,
    title: String(input.title || id).trim() || id,
    description: String(input.description || ""),
    order: numberOrDefault(input.order || input.launcher_order || input.launcherOrder, index * 10),
    leading: String(input.leading || input.icon || "").trim(),
    meta: String(input.meta || ""),
    keywords: normalizeKeywords(input.keywords),
  };
}

function normalizePaletteGroups(items) {
  if (!Array.isArray(items)) return [];
  const result = [];
  const seen = new Set();
  for (let index = 0; index < items.length; index += 1) {
    const group = normalizePaletteGroupDescriptor(items[index], index);
    if (!group || seen.has(group.id)) continue;
    seen.add(group.id);
    result.push(group);
  }
  return result.sort((left, right) => left.order - right.order || left.title.localeCompare(right.title));
}

function normalizeCommandPalette(input = {}) {
  const value = input.command_palette || input.commandPalette || {};
  const palette = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const labels = palette.labels && typeof palette.labels === "object" && !Array.isArray(palette.labels)
    ? palette.labels
    : {};
  return {
    groups: normalizePaletteGroups(palette.groups || palette.command_groups || palette.commandGroups),
    labels: {
      rootTitle: String(labels.root_title || labels.rootTitle || ""),
      submenuTitle: String(labels.submenu_title || labels.submenuTitle || ""),
      searchLabel: String(labels.search_label || labels.searchLabel || ""),
      rootPlaceholder: String(labels.root_placeholder || labels.rootPlaceholder || ""),
      submenuPlaceholder: String(labels.submenu_placeholder || labels.submenuPlaceholder || ""),
      rootEmpty: String(labels.root_empty || labels.rootEmpty || ""),
      submenuEmpty: String(labels.submenu_empty || labels.submenuEmpty || ""),
      commandsSection: String(labels.commands_section || labels.commandsSection || ""),
      sessionsSection: String(labels.sessions_section || labels.sessionsSection || ""),
      workspacesSection: String(labels.workspaces_section || labels.workspacesSection || ""),
      currentLabel: String(labels.current_label || labels.currentLabel || ""),
      missingLabel: String(labels.missing_label || labels.missingLabel || ""),
      workspaceMeta: String(labels.workspace_meta || labels.workspaceMeta || ""),
      workspaceFallback: String(labels.workspace_fallback || labels.workspaceFallback || ""),
      sessionFallbackPrefix: String(labels.session_fallback_prefix || labels.sessionFallbackPrefix || ""),
    },
  };
}

function normalizeHeaderChrome(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  return {
    commandPaletteLabel: String(value.command_palette_label || value.commandPaletteLabel || ""),
    commandPaletteShortLabel: String(
      value.command_palette_short_label || value.commandPaletteShortLabel || "",
    ),
    refreshLabel: String(value.refresh_label || value.refreshLabel || ""),
    bottomDrawerLabel: String(value.bottom_drawer_label || value.bottomDrawerLabel || ""),
    bottomDrawerTitle: String(value.bottom_drawer_title || value.bottomDrawerTitle || ""),
    rightPanelLabel: String(value.right_panel_label || value.rightPanelLabel || ""),
    rightPanelTitle: String(value.right_panel_title || value.rightPanelTitle || ""),
    turnsLabel: String(value.turns_label || value.turnsLabel || ""),
  };
}

function normalizeComposerHints(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  return Object.fromEntries(
    Object.entries(value)
      .map(([key, item]) => [String(key || ""), String(item || "")])
      .filter(([key]) => key),
  );
}

function normalizeComposerChrome(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  return {
    placeholder: String(value.placeholder || ""),
    commandPaletteLabel: String(value.command_palette_label || value.commandPaletteLabel || ""),
    sendLabel: String(value.send_label || value.sendLabel || ""),
    stopLabel: String(value.stop_label || value.stopLabel || ""),
    hints: normalizeComposerHints(value.hints),
  };
}

function normalizeInteractionChrome(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  return {
    pendingApprovalKicker: String(
      value.pending_approval_kicker || value.pendingApprovalKicker || "",
    ),
    inputRequiredKicker: String(value.input_required_kicker || value.inputRequiredKicker || ""),
    commandApprovalSummary: String(
      value.command_approval_summary || value.commandApprovalSummary || "",
    ),
    fileReadApprovalSummary: String(
      value.file_read_approval_summary || value.fileReadApprovalSummary || "",
    ),
    fileChangeApprovalSummary: String(
      value.file_change_approval_summary || value.fileChangeApprovalSummary || "",
    ),
    expiredTitle: String(value.expired_title || value.expiredTitle || ""),
    expiredBody: String(value.expired_body || value.expiredBody || ""),
    conflictTitle: String(value.conflict_title || value.conflictTitle || ""),
    conflictBody: String(value.conflict_body || value.conflictBody || ""),
    approveOnceLabel: String(value.approve_once_label || value.approveOnceLabel || ""),
    declineLabel: String(value.decline_label || value.declineLabel || ""),
    cancelTurnLabel: String(value.cancel_turn_label || value.cancelTurnLabel || ""),
    alwaysAllowSessionLabel: String(
      value.always_allow_session_label || value.alwaysAllowSessionLabel || "",
    ),
    inputSummary: String(value.input_summary || value.inputSummary || ""),
    customAnswerPlaceholder: String(
      value.custom_answer_placeholder || value.customAnswerPlaceholder || "",
    ),
    submitLabel: String(value.submit_label || value.submitLabel || ""),
    modeLabelPrefix: String(value.mode_label_prefix || value.modeLabelPrefix || ""),
  };
}

function normalizeSurfacePanelChrome(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  const groups = value.diagnostic_groups || value.diagnosticGroups || {};
  return {
    ariaLabel: String(value.aria_label || value.ariaLabel || ""),
    settingsTitle: String(value.settings_title || value.settingsTitle || ""),
    confirmWorkspaceSwitchLabel: String(
      value.confirm_workspace_switch_label || value.confirmWorkspaceSwitchLabel || "",
    ),
    showDiagnosticsBadgeLabel: String(
      value.show_diagnostics_badge_label || value.showDiagnosticsBadgeLabel || "",
    ),
    diagnosticsTitle: String(value.diagnostics_title || value.diagnosticsTitle || ""),
    capabilitiesTitle: String(value.capabilities_title || value.capabilitiesTitle || ""),
    noDiagnostics: String(value.no_diagnostics || value.noDiagnostics || ""),
    planTitle: String(value.plan_title || value.planTitle || ""),
    noPlan: String(value.no_plan || value.noPlan || ""),
    diagnosticGroups:
      groups && typeof groups === "object" && !Array.isArray(groups)
        ? Object.fromEntries(
            Object.entries(groups)
              .map(([key, item]) => [String(key || ""), String(item || "")])
              .filter(([key]) => key),
          )
        : {},
  };
}

function normalizeChrome(input = {}) {
  const value = input.chrome && typeof input.chrome === "object" && !Array.isArray(input.chrome)
    ? input.chrome
    : {};
  return {
    brandSubtitle: String(value.brand_subtitle || value.brandSubtitle || ""),
    sidebarAriaLabel: String(value.sidebar_aria_label || value.sidebarAriaLabel || ""),
    threadPanelAriaLabel: String(value.thread_panel_aria_label || value.threadPanelAriaLabel || ""),
    header: normalizeHeaderChrome(value.header),
    composer: normalizeComposerChrome(value.composer),
    interaction: normalizeInteractionChrome(value.interaction),
    surfacePanel: normalizeSurfacePanelChrome(value.surface_panel || value.surfacePanel),
  };
}

function normalizeHomeWorkspaceCopy(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  return {
    sectionTitle: String(value.section_title || value.sectionTitle || ""),
    inactiveLabel: String(value.inactive_label || value.inactiveLabel || ""),
    inactivePath: String(value.inactive_path || value.inactivePath || ""),
    pathPlaceholder: String(value.path_placeholder || value.pathPlaceholder || ""),
    openLabel: String(value.open_label || value.openLabel || ""),
    openAriaLabel: String(value.open_aria_label || value.openAriaLabel || ""),
    recentsLabel: String(value.recents_label || value.recentsLabel || ""),
    missingPathLabel: String(value.missing_path_label || value.missingPathLabel || ""),
    removeLabel: String(value.remove_label || value.removeLabel || ""),
  };
}

function normalizeHomeThreadsCopy(input = {}) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  return {
    sectionTitle: String(value.section_title || value.sectionTitle || ""),
    newLabel: String(value.new_label || value.newLabel || ""),
    emptyTitle: String(value.empty_title || value.emptyTitle || ""),
    emptyBody: String(value.empty_body || value.emptyBody || ""),
    activeLabel: String(value.active_label || value.activeLabel || ""),
    actionsLabelPrefix: String(value.actions_label_prefix || value.actionsLabelPrefix || ""),
  };
}

function normalizeHomeCopy(input = {}) {
  const value = input.home && typeof input.home === "object" && !Array.isArray(input.home) ? input.home : {};
  return {
    workspace: normalizeHomeWorkspaceCopy(value.workspace),
    threads: normalizeHomeThreadsCopy(value.threads),
  };
}

export function normalizeAppCapabilities(input = {}) {
  const surfaces = input.surfaces && typeof input.surfaces === "object" ? input.surfaces : {};
  return {
    appCommands: normalizeAppCommandDescriptors(
      Array.isArray(input.app_commands) ? input.app_commands : input.appCommands,
      "app",
    ),
    workspaceCommands: normalizeAppCommandDescriptors(
      Array.isArray(input.workspace_commands) ? input.workspace_commands : input.workspaceCommands,
      "workspace",
    ),
    workbenchCommands: normalizeAppCommandDescriptors(
      Array.isArray(input.workbench_commands) ? input.workbench_commands : input.workbenchCommands,
      "workbench",
    ),
    commandPalette: normalizeCommandPalette(input),
    chrome: normalizeChrome(input),
    home: normalizeHomeCopy(input),
    surfaces: {
      rightPanel: normalizeSurfaceCapabilityList(
        Array.isArray(surfaces.right_panel) ? surfaces.right_panel : surfaces.rightPanel,
        "right",
      ),
      bottomDrawer: normalizeSurfaceCapabilityList(
        Array.isArray(surfaces.bottom_drawer) ? surfaces.bottom_drawer : surfaces.bottomDrawer,
        "bottom",
      ),
      chrome: normalizeSurfaceChrome(input),
    },
    keybindings: normalizeKeybindings(input.keybindings || input.key_bindings),
    agentApplication: normalizeAgentApplicationDescriptor(
      input.agentApplication || input.agent_application,
    ),
    agentApplications: Array.isArray(input.agentApplications)
      ? input.agentApplications.map(normalizeAgentApplicationDescriptor).filter(Boolean)
      : Array.isArray(input.agent_applications)
        ? input.agent_applications.map(normalizeAgentApplicationDescriptor).filter(Boolean)
        : [],
    emptyState: normalizeEmptyState(input.emptyState || input.empty_state),
    sourceControl: normalizeSourceControlCapability(input),
    terminal: normalizeTerminalCapability(input),
    preview: normalizePreviewCapability(input),
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
