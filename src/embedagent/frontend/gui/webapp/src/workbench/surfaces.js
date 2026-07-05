const DEFAULT_PERSIST_FIELDS = [
  "id",
  "placement",
  "kind",
  "title",
  "resourceId",
  "filePath",
  "terminalId",
  "revealLine",
  "revealRequestId",
];

const TERMINAL_PERSIST_FIELDS = [
  ...DEFAULT_PERSIST_FIELDS,
  "terminalIds",
  "activeTerminalId",
  "splitDirection",
];

function defineSurface(input) {
  return Object.freeze({
    ...input,
    persistFields: Object.freeze((input.persistFields || DEFAULT_PERSIST_FIELDS).slice()),
    keywords: Object.freeze((input.keywords || []).slice()),
  });
}

export const RIGHT_PANEL_SURFACE_REGISTRY = Object.freeze([
  defineSurface({
    kind: "preview",
    placement: "right",
    resourceId: "optional",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    bodyKind: "preview",
    openKind: "workbench.surface",
    launcher: true,
    launcherOrder: 10,
    command: true,
  }),
  defineSurface({
    kind: "diff",
    placement: "right",
    resourceId: "current",
    defaultResourceId: "current",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    bodyKind: "surface_panel",
    openKind: "workbench.surface",
    panelKind: "diff",
    launcher: true,
    launcherOrder: 40,
    command: true,
  }),
  defineSurface({
    kind: "files",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    bodyKind: "files",
    openKind: "workbench.surface",
    launcher: true,
    launcherOrder: 20,
    command: true,
  }),
  defineSurface({
    kind: "file",
    placement: "right",
    resourceId: "file_path",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    bodyKind: "file_preview",
    openKind: "",
    launcher: false,
    launcherOrder: 0,
    command: false,
  }),
  defineSurface({
    kind: "terminal",
    placement: "right",
    resourceId: "terminal_id",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: TERMINAL_PERSIST_FIELDS,
    bodyKind: "terminal",
    openKind: "terminal.right_panel",
    launcher: true,
    launcherOrder: 30,
    command: true,
  }),
  defineSurface({
    kind: "plan",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    bodyKind: "surface_panel",
    openKind: "workbench.surface",
    panelKind: "plan",
    launcher: true,
    launcherOrder: 50,
    command: true,
  }),
  defineSurface({
    kind: "source_control",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    bodyKind: "surface_panel",
    openKind: "workbench.surface",
    panelKind: "source_control",
    launcher: true,
    launcherOrder: 60,
    command: true,
    readOnly: true,
    offline: true,
  }),
  defineSurface({
    kind: "settings",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    bodyKind: "surface_panel",
    openKind: "workbench.surface",
    panelKind: "settings",
    launcher: true,
    launcherOrder: 70,
    command: true,
  }),
  defineSurface({
    kind: "diagnostics",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    bodyKind: "surface_panel",
    openKind: "workbench.surface",
    panelKind: "diagnostics",
    launcher: true,
    launcherOrder: 80,
    command: true,
  }),
]);

export const BOTTOM_DRAWER_SURFACE_REGISTRY = Object.freeze([
  defineSurface({
    kind: "run_output",
    placement: "bottom",
    closeBehavior: "pinned",
    bodyKind: "run_output",
    launcher: true,
    launcherOrder: 10,
    command: true,
  }),
  defineSurface({
    kind: "terminal",
    placement: "bottom",
    closeBehavior: "pinned",
    bodyKind: "terminal",
    launcher: true,
    launcherOrder: 20,
    command: true,
  }),
]);

function normalizeKeywords(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function surfaceCapabilityRecords(appCapabilities, placement) {
  if (!appCapabilities || typeof appCapabilities !== "object") return [];
  const surfaces = appCapabilities.surfaces && typeof appCapabilities.surfaces === "object"
    ? appCapabilities.surfaces
    : {};
  const value =
    placement === "bottom"
      ? (surfaces.bottomDrawer || surfaces.bottom_drawer)
      : (surfaces.rightPanel || surfaces.right_panel);
  if (!Array.isArray(value)) return [];
  return value;
}

function normalizeSurfaceCapabilityRecord(input, placement, index) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const kind = String(input.kind || input.id || "").trim();
  if (!kind) return null;
  const launcherOrder = Number(input.launcherOrder ?? input.launcher_order ?? index);
  return {
    kind,
    title: String(input.title || ""),
    icon: String(input.icon || ""),
    description: String(input.description || ""),
    placement,
    resourceId: String(input.resourceId || input.resource_id || ""),
    defaultResourceId: String(input.defaultResourceId || input.default_resource_id || ""),
    closeBehavior: String(input.closeBehavior || input.close_behavior || ""),
    launcher: input.launcher !== false,
    launcherOrder: Number.isFinite(launcherOrder) ? launcherOrder : index,
    command: input.command !== false,
    commandLabel: String(input.commandLabel || input.command_label || ""),
    slash: String(input.slash || ""),
    visibleWhen: String(input.visibleWhen || input.visible_when || ""),
    readOnly: input.readOnly === true || input.read_only === true,
    offline: input.offline === true,
    keywords: normalizeKeywords(input.keywords),
    dispatch: input.dispatch && typeof input.dispatch === "object" ? { ...input.dispatch } : {},
  };
}

export function surfaceCapabilityDefinitions(appCapabilities, placement) {
  return surfaceCapabilityRecords(appCapabilities, placement)
    .map((item, index) => normalizeSurfaceCapabilityRecord(item, placement, index))
    .filter(Boolean);
}

export function surfaceChromeLabels(appCapabilities = null) {
  const surfaces = appCapabilities?.surfaces && typeof appCapabilities.surfaces === "object"
    ? appCapabilities.surfaces
    : {};
  const chrome = surfaces.chrome && typeof surfaces.chrome === "object" ? surfaces.chrome : {};
  return {
    rightPanelAriaLabel: String(chrome.rightPanelAriaLabel || ""),
    addSurfaceLabel: String(chrome.addSurfaceLabel || ""),
    emptyTitle: String(chrome.emptyTitle || ""),
    emptyBody: String(chrome.emptyBody || ""),
    surfaceActionsLabelPrefix: String(chrome.surfaceActionsLabelPrefix || ""),
    closeLabelPrefix: String(chrome.closeLabelPrefix || ""),
    closeActionLabel: String(chrome.closeActionLabel || ""),
    closeOthersActionLabel: String(chrome.closeOthersActionLabel || ""),
    closeToRightActionLabel: String(chrome.closeToRightActionLabel || ""),
    closeAllActionLabel: String(chrome.closeAllActionLabel || ""),
    defaultIcon: String(chrome.defaultIcon || ""),
    bottomDrawerAriaLabel: String(chrome.bottomDrawerAriaLabel || ""),
    runOutputEmptyMessage: String(chrome.runOutputEmptyMessage || ""),
    terminationReasonPrefix: String(chrome.terminationReasonPrefix || ""),
  };
}

function surfaceDefinitionsForPlacement(placement) {
  return placement === "bottom" ? BOTTOM_DRAWER_SURFACE_REGISTRY : RIGHT_PANEL_SURFACE_REGISTRY;
}

function mergedSurfaceDefinition(definition, capability) {
  return {
    ...definition,
    title: capability.title,
    icon: capability.icon,
    description: capability.description,
    resourceId: capability.resourceId || definition.resourceId,
    defaultResourceId: capability.defaultResourceId || definition.defaultResourceId,
    closeBehavior: capability.closeBehavior || definition.closeBehavior,
    launcher: capability.launcher && definition.launcher !== false,
    launcherOrder: capability.launcherOrder,
    command: capability.command && definition.command !== false,
    commandLabel: capability.commandLabel,
    slash: capability.slash || definition.slash || "",
    visibleWhen: capability.visibleWhen || definition.visibleWhen || "always",
    readOnly: capability.readOnly || definition.readOnly === true,
    offline: capability.offline || definition.offline === true,
    keywords: Object.freeze(Array.from(new Set(capability.keywords || []))),
    dispatch: capability.dispatch && typeof capability.dispatch === "object"
      ? { ...capability.dispatch }
      : {},
    bodyKind: definition.bodyKind || "",
    openKind: definition.openKind || "",
    panelKind: definition.panelKind || "",
  };
}

function hasDisplayTitle(definition) {
  return Boolean(String(definition && definition.title || "").trim());
}

function filterSurfaceDefinitions(definitions, placement, appCapabilities) {
  const capabilities = surfaceCapabilityDefinitions(appCapabilities, placement);
  if (capabilities.length === 0) return [];
  const byKind = new Map(definitions.map((definition) => [definition.kind, definition]));
  return capabilities
    .map((capability) => {
      const definition = byKind.get(capability.kind);
      return definition ? mergedSurfaceDefinition(definition, capability) : null;
    })
    .filter((definition) => definition && definition.launcher && hasDisplayTitle(definition))
    .sort((left, right) => (left.launcherOrder || 0) - (right.launcherOrder || 0));
}

export function rightPanelSurfaceDefinitions() {
  return RIGHT_PANEL_SURFACE_REGISTRY;
}

export function surfaceDefinitionFor(kind, appCapabilities = null) {
  const normalized = String(kind || "");
  const definition = RIGHT_PANEL_SURFACE_REGISTRY.find((item) => item.kind === normalized) || null;
  if (!definition || !appCapabilities) return definition;
  const capability = surfaceCapabilityDefinitions(appCapabilities, "right")
    .find((item) => item.kind === normalized);
  if (!capability) return null;
  const merged = mergedSurfaceDefinition(definition, capability);
  return hasDisplayTitle(merged) ? merged : null;
}

export function rightPanelLauncherSurfaceDefinitions(appCapabilities = null) {
  return filterSurfaceDefinitions(RIGHT_PANEL_SURFACE_REGISTRY, "right", appCapabilities);
}

export function bottomDrawerSurfaceDefinitions(appCapabilities = null) {
  return filterSurfaceDefinitions(BOTTOM_DRAWER_SURFACE_REGISTRY, "bottom", appCapabilities);
}

export function surfaceCommandDefinitions(appCapabilities = null) {
  return rightPanelLauncherSurfaceDefinitions(appCapabilities)
    .filter((definition) => definition.command !== false && definition.commandLabel)
    .map((definition) => ({
      id: `surface.${definition.kind}`,
      group: "surface",
      label: definition.commandLabel,
      description: definition.description,
      slash: definition.slash || "",
      surface: definition.kind,
      visibleWhen: definition.visibleWhen || "always",
      ...(definition.keywords.length > 0 ? { keywords: Array.from(definition.keywords) } : {}),
    }));
}

export function bottomDrawerCommandDefinitions(appCapabilities = null) {
  return bottomDrawerSurfaceDefinitions(appCapabilities)
    .filter((definition) => definition.command !== false && definition.commandLabel)
    .map((definition) => ({
      id: `drawer.${definition.kind}`,
      group: "surface",
      label: definition.commandLabel,
      description: definition.description,
      slash: definition.slash || "",
      drawer: definition.kind,
      dispatch: definition.dispatch && typeof definition.dispatch === "object"
        ? { ...definition.dispatch }
        : {},
      visibleWhen: definition.visibleWhen || "always",
      ...(definition.keywords.length > 0 ? { keywords: Array.from(definition.keywords) } : {}),
    }));
}

export function supportedSurfaceKinds(placement = "right") {
  return surfaceDefinitionsForPlacement(placement).map((definition) => definition.kind);
}

export const DEFAULT_SESSION_KEY = "__global__";

function normalizeSessionId(sessionId) {
  const value = String(sessionId || "").trim();
  return value || DEFAULT_SESSION_KEY;
}

function normalizePlacement(placement) {
  return placement === "bottom" ? "bottom" : "right";
}

function defaultActiveKind() {
  return "";
}

function allowedKinds(placement) {
  return supportedSurfaceKinds(placement);
}

function normalizeFilePath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function basenameForPath(path) {
  const normalized = normalizeFilePath(path);
  if (!normalized) return "";
  const parts = normalized.split("/");
  return parts[parts.length - 1] || normalized;
}

function normalizeRevealLine(line) {
  const value = Number(line);
  if (!Number.isFinite(value)) return null;
  return Math.max(1, Math.trunc(value));
}

function uniqueTerminalIds(ids) {
  const result = [];
  for (const id of ids || []) {
    const value = String(id || "").trim();
    if (value && !result.includes(value)) {
      result.push(value);
    }
  }
  return result;
}

function surfaceIdFor(input) {
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  const filePath = kind === "file" ? normalizeFilePath(input && (input.filePath || input.resourceId)) : "";
  const resourceId = filePath || String((input && input.resourceId) || "");
  return resourceId ? `${placement}:${kind}:${resourceId}` : `${placement}:${kind}`;
}

function makeSurface(input) {
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  const definition = placement === "right" ? surfaceDefinitionFor(kind) : null;
  const filePath =
    kind === "file"
      ? normalizeFilePath(input && (input.filePath || input.resourceId))
      : String((input && input.filePath) || "");
  const resourceId =
    kind === "file"
      ? filePath
      : String((input && input.resourceId) || (definition && definition.defaultResourceId) || "");
  const terminalIds =
    kind === "terminal"
      ? uniqueTerminalIds(
          Array.isArray(input && input.terminalIds)
            ? input.terminalIds
            : [input && (input.terminalId || input.resourceId)],
        )
      : [];
  const activeTerminalId =
    kind === "terminal"
      ? String((input && input.activeTerminalId) || terminalIds[0] || "")
      : "";
  const terminalId =
    kind === "terminal"
      ? String((input && input.terminalId) || resourceId || terminalIds[0] || activeTerminalId)
      : String((input && input.terminalId) || resourceId || "");
  const effectiveResourceId = kind === "terminal" ? terminalId : resourceId;
  const base = {
    id: String(
      (input && input.surfaceId) ||
        surfaceIdFor({ ...input, filePath, resourceId: effectiveResourceId }),
    ),
    placement,
    kind,
    title: String(
      (input && input.title) ||
        (kind === "file" ? basenameForPath(filePath) : titleForSurfaceKind(kind)),
    ),
    resourceId: effectiveResourceId,
    filePath,
    terminalId,
    revealLine: kind === "file" ? normalizeRevealLine(input && input.revealLine) : null,
    revealRequestId:
      kind === "file" && Number.isSafeInteger(Number(input && input.revealRequestId))
        ? Number(input.revealRequestId)
        : 0,
  };
  if (kind === "preview") {
    return {
      ...base,
      previewSnapshot:
        input && input.previewSnapshot && typeof input.previewSnapshot === "object"
          ? { ...input.previewSnapshot }
          : null,
    };
  }
  if (kind !== "terminal") {
    return base;
  }
  const normalizedTerminalIds = terminalIds.length > 0 ? terminalIds : [terminalId].filter(Boolean);
  return {
    ...base,
    terminalIds: normalizedTerminalIds,
    activeTerminalId: activeTerminalId || terminalId,
    ...(input && input.splitDirection === "vertical" ? { splitDirection: "vertical" } : {}),
  };
}

export function titleForSurfaceKind(kind, appCapabilities = null) {
  const definition = surfaceDefinitionFor(kind, appCapabilities);
  return definition && definition.title ? definition.title : "";
}

function emptySessionSurfaces() {
  return {
    right: [],
    bottom: [],
  };
}

function sessionSurfaces(state, sessionId) {
  const key = normalizeSessionId(sessionId);
  return state.surfacesBySession[key] || emptySessionSurfaces();
}

function upsertSurface(items, nextSurface) {
  const existingIndex = items.findIndex((item) => item.id === nextSurface.id);
  if (existingIndex < 0) {
    return items.concat(nextSurface);
  }
  return items.map((item, index) => (index === existingIndex ? nextSurface : item));
}

function removeSurface(items, surfaceId) {
  return items.filter((item) => item.id !== surfaceId);
}

function activeSurfaceFrom(items, activeSurfaceId) {
  return items.find((item) => item.id === activeSurfaceId) || null;
}

function activateRightPanelSurface(panel, surface) {
  const surfaces = Array.isArray(panel && panel.surfaces) ? panel.surfaces : [];
  return {
    ...panel,
    open: surface ? true : surfaces.length > 0 && panel.open === true,
    activeKind: surface ? surface.kind : "",
    activeSurfaceId: surface ? surface.id : null,
  };
}

function setRightPanelSurfaceSelection(panel, surface) {
  return {
    ...panel,
    activeKind: surface ? surface.kind : "",
    activeSurfaceId: surface ? surface.id : null,
  };
}

function rememberRightPanelSession(state, panel, sessionId) {
  const key = normalizeSessionId(sessionId || state.activeSessionKey);
  const existing = sessionSurfaces(state, key);
  return {
    ...state,
    activeSessionKey: key,
    surfacesBySession: {
      ...state.surfacesBySession,
      [key]: {
        ...existing,
        right: Array.isArray(panel && panel.surfaces) ? panel.surfaces : [],
        activeRightSurfaceId: panel ? panel.activeSurfaceId || null : null,
      },
    },
  };
}

function nextActiveAfterClose(items, closedIndex) {
  if (items.length === 0) return null;
  const boundedIndex = Math.max(0, Math.min(closedIndex, items.length - 1));
  return items[boundedIndex] || items[items.length - 1] || null;
}

export function createWorkbenchState() {
  return {
    activeSessionKey: DEFAULT_SESSION_KEY,
    rightPanel: {
      open: true,
      activeKind: "",
      activeSurfaceId: null,
      surfaces: [],
      width: 320,
    },
    bottomDrawer: {
      open: false,
      activeKind: "",
      height: 220,
    },
    commandPalette: {
      open: false,
      query: "",
      selectedIndex: 0,
    },
    layout: {
      density: "compact",
      narrow: false,
    },
    surfacesBySession: {},
  };
}

export function getSessionSurfaces(state, sessionId) {
  return sessionSurfaces(state || createWorkbenchState(), sessionId);
}

export function activateWorkbenchSession(state, sessionId) {
  const current = state || createWorkbenchState();
  const savedCurrent = rememberRightPanelSession(
    current,
    current.rightPanel || createWorkbenchState().rightPanel,
    current.activeSessionKey || DEFAULT_SESSION_KEY,
  );
  const key = normalizeSessionId(sessionId);
  const existing = sessionSurfaces(savedCurrent, key);
  const rightSurfaces = Array.isArray(existing.right) ? existing.right : [];
  const active =
    activeSurfaceFrom(rightSurfaces, existing.activeRightSurfaceId) ||
    rightSurfaces[rightSurfaces.length - 1] ||
    null;
  return {
    ...savedCurrent,
    activeSessionKey: key,
    rightPanel: setRightPanelSurfaceSelection(
      { ...savedCurrent.rightPanel, surfaces: rightSurfaces },
      active,
    ),
  };
}

export function openSurface(state, input) {
  const current = state || createWorkbenchState();
  const surface = makeSurface(input || {});
  const placement = normalizePlacement(surface.placement);
  if (!allowedKinds(placement).includes(surface.kind)) {
    return current;
  }
  if (placement === "right") {
    const key = normalizeSessionId(input && (input.sessionId || current.activeSessionKey));
    const currentItems = current.rightPanel.surfaces || [];
    const filePath =
      surface.kind === "file"
        ? normalizeFilePath(surface.filePath || surface.resourceId)
        : "";
    const existingFile = filePath
      ? currentItems.find(
          (item) =>
            item.kind === "file" &&
            normalizeFilePath(item.filePath || item.resourceId) === filePath,
        )
      : null;
    const nextSurface =
      surface.kind === "file"
        ? makeSurface({
            ...input,
            placement: "right",
            kind: "file",
            filePath,
            resourceId: filePath,
            revealRequestId: Number((existingFile && existingFile.revealRequestId) || 0) + 1,
          })
        : surface;
    const hasPreviewResource = nextSurface.kind === "preview" && Boolean(nextSurface.resourceId);
    const sourceItems =
      nextSurface.kind === "file"
        ? currentItems.filter((item) => item.kind !== "files")
        : hasPreviewResource
          ? currentItems.filter((item) => !(item.kind === "preview" && !item.resourceId))
          : currentItems;
    const surfaces = upsertSurface(sourceItems, nextSurface);
    const nextPanel = activateRightPanelSurface(
      { ...current.rightPanel, surfaces },
      nextSurface,
    );
    return rememberRightPanelSession({
      ...current,
      rightPanel: nextPanel,
    }, nextPanel, key);
  }
  const key = normalizeSessionId(input && input.sessionId);
  const existing = sessionSurfaces(current, key);
  const nextSessionSurfaces = {
    ...existing,
    bottom: upsertSurface(existing.bottom, surface),
  };
  return {
    ...current,
    surfacesBySession: {
      ...current.surfacesBySession,
      [key]: nextSessionSurfaces,
    },
    bottomDrawer: { ...current.bottomDrawer, open: true, activeKind: surface.kind },
  };
}

export function openFileSurface(state, input = {}) {
  const filePath = normalizeFilePath(input.filePath || input.resourceId);
  if (!filePath) return state || createWorkbenchState();
  return openSurface(state, {
    ...input,
    placement: "right",
    kind: "file",
    filePath,
    resourceId: filePath,
    title: basenameForPath(filePath),
  });
}

export function openPreviewSurface(state, input = {}) {
  const previewId = String(input.previewId || input.resourceId || "").trim();
  const title = String(input.title || previewId).trim();
  if (!title) return state || createWorkbenchState();
  return openSurface(state, {
    ...input,
    placement: "right",
    kind: "preview",
    resourceId: previewId,
    title,
  });
}

export function openTerminalSurface(state, input = {}) {
  const terminalId = String(input.terminalId || input.resourceId || "").trim();
  if (!terminalId) return state || createWorkbenchState();
  return openSurface(state, {
    ...input,
    placement: "right",
    kind: "terminal",
    title: input.title || terminalId,
    resourceId: terminalId,
    terminalId,
    terminalIds: [terminalId],
    activeTerminalId: terminalId,
  });
}

export function splitTerminalSurfaceForWorkbench(state, input = {}) {
  return splitTerminalSurface(state, {
    ...input,
    placement: "right",
  });
}

export function activateTerminalPaneForWorkbench(state, input = {}) {
  return activateTerminalPane(state, {
    ...input,
    placement: "right",
  });
}

export function closeTerminalPaneForWorkbench(state, input = {}) {
  return closeTerminalPane(state, {
    ...input,
    placement: "right",
  });
}

export function activateSurface(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  if (placement === "bottom") {
    const kind = String((input && input.kind) || defaultActiveKind(placement));
    if (!allowedKinds(placement).includes(kind)) return current;
    return {
      ...current,
      bottomDrawer: { ...current.bottomDrawer, open: true, activeKind: kind },
    };
  }
  const surfaceId = String((input && input.surfaceId) || "");
  const existing = surfaceId
    ? activeSurfaceFrom(current.rightPanel.surfaces || [], surfaceId)
    : null;
  if (existing) {
    const key = normalizeSessionId(input && (input.sessionId || current.activeSessionKey));
    const nextPanel = activateRightPanelSurface(current.rightPanel, existing);
    return rememberRightPanelSession({
      ...current,
      rightPanel: nextPanel,
    }, nextPanel, key);
  }
  return openSurface(current, {
    placement: "right",
    kind: input && input.kind,
    title: input && input.title,
    resourceId: input && input.resourceId,
    filePath: input && input.filePath,
    terminalId: input && input.terminalId,
  });
}

export function closeSurface(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  const surface = makeSurface(input || {});
  if (placement === "bottom") {
    const key = normalizeSessionId(input && input.sessionId);
    const existing = sessionSurfaces(current, key);
    const nextItems = removeSurface(existing.bottom, surface.id);
    const nextSessionSurfaces = { ...existing, bottom: nextItems };
    return {
      ...current,
      surfacesBySession: {
        ...current.surfacesBySession,
        [key]: nextSessionSurfaces,
      },
      bottomDrawer: {
        ...current.bottomDrawer,
        open: nextItems.length > 0,
        activeKind: nextItems.length > 0 ? nextItems[0].kind : defaultActiveKind(placement),
      },
    };
  }
  const items = current.rightPanel.surfaces || [];
  const closedIndex = Math.max(0, items.findIndex((item) => item.id === surface.id));
  const nextItems = removeSurface(items, surface.id);
  const shouldReplaceActive = current.rightPanel.activeSurfaceId === surface.id;
  const nextActive = shouldReplaceActive
    ? nextActiveAfterClose(nextItems, closedIndex)
    : activeSurfaceFrom(nextItems, current.rightPanel.activeSurfaceId);
  const key = normalizeSessionId(input && (input.sessionId || current.activeSessionKey));
  const nextPanel = activateRightPanelSurface(
    { ...current.rightPanel, surfaces: nextItems },
    nextActive,
  );
  return rememberRightPanelSession({
    ...current,
    rightPanel: nextPanel,
  }, nextPanel, key);
}

export function closeOtherSurfaces(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  if (placement !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const active = activeSurfaceFrom(current.rightPanel.surfaces || [], surfaceId);
  if (!active) return current;
  const key = normalizeSessionId(input && (input.sessionId || current.activeSessionKey));
  const nextPanel = activateRightPanelSurface(
    { ...current.rightPanel, surfaces: [active] },
    active,
  );
  return rememberRightPanelSession({
    ...current,
    rightPanel: nextPanel,
  }, nextPanel, key);
}

export function closeSurfacesToRight(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  if (placement !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const items = current.rightPanel.surfaces || [];
  const index = items.findIndex((item) => item.id === surfaceId);
  if (index < 0) return current;
  const nextItems = items.slice(0, index + 1);
  const active = activeSurfaceFrom(nextItems, surfaceId) || nextItems[nextItems.length - 1] || null;
  const key = normalizeSessionId(input && (input.sessionId || current.activeSessionKey));
  const nextPanel = activateRightPanelSurface(
    { ...current.rightPanel, surfaces: nextItems },
    active,
  );
  return rememberRightPanelSession({
    ...current,
    rightPanel: nextPanel,
  }, nextPanel, key);
}

export function closeAllSurfaces(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  if (placement !== "right") return current;
  const key = normalizeSessionId(input && (input.sessionId || current.activeSessionKey));
  const nextPanel = {
    ...current.rightPanel,
    open: false,
    activeKind: "",
    activeSurfaceId: null,
    surfaces: [],
  };
  return rememberRightPanelSession({
    ...current,
    rightPanel: nextPanel,
  }, nextPanel, key);
}

function splitTerminalSurface(state, input) {
  const current = state || createWorkbenchState();
  if (normalizePlacement(input && input.placement) !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const terminalId = String((input && input.terminalId) || "").trim();
  if (!surfaceId || !terminalId) return current;
  const surfaces = (current.rightPanel.surfaces || []).map((surface) => {
    if (surface.id !== surfaceId || surface.kind !== "terminal") return surface;
    const terminalIds = uniqueTerminalIds([...(surface.terminalIds || []), terminalId]);
    const nextSurface = {
      ...surface,
      terminalIds,
      activeTerminalId: terminalId,
    };
    if (input && input.splitDirection === "vertical") {
      return { ...nextSurface, splitDirection: "vertical" };
    }
    const { splitDirection, ...withoutDirection } = nextSurface;
    return withoutDirection;
  });
  const active = activeSurfaceFrom(surfaces, surfaceId);
  if (!active) return current;
  const key = normalizeSessionId(input && (input.sessionId || current.activeSessionKey));
  const nextPanel = activateRightPanelSurface({ ...current.rightPanel, surfaces }, active);
  return rememberRightPanelSession({
    ...current,
    rightPanel: nextPanel,
  }, nextPanel, key);
}

function activateTerminalPane(state, input) {
  const current = state || createWorkbenchState();
  if (normalizePlacement(input && input.placement) !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const terminalId = String((input && input.terminalId) || "").trim();
  if (!surfaceId || !terminalId) return current;
  const surfaces = (current.rightPanel.surfaces || []).map((surface) =>
    surface.id === surfaceId &&
    surface.kind === "terminal" &&
    Array.isArray(surface.terminalIds) &&
    surface.terminalIds.includes(terminalId)
      ? { ...surface, activeTerminalId: terminalId }
      : surface,
  );
  const active = activeSurfaceFrom(surfaces, surfaceId);
  if (!active) return current;
  const key = normalizeSessionId(input && (input.sessionId || current.activeSessionKey));
  const nextPanel = activateRightPanelSurface({ ...current.rightPanel, surfaces }, active);
  return rememberRightPanelSession({
    ...current,
    rightPanel: nextPanel,
  }, nextPanel, key);
}

function closeTerminalPane(state, input) {
  const current = state || createWorkbenchState();
  if (normalizePlacement(input && input.placement) !== "right") return current;
  const surfaceId = String((input && input.surfaceId) || "");
  const terminalId = String((input && input.terminalId) || "").trim();
  const items = current.rightPanel.surfaces || [];
  const index = items.findIndex((surface) => surface.id === surfaceId && surface.kind === "terminal");
  if (index < 0 || !terminalId) return current;
  const surface = items[index];
  const terminalIds = (surface.terminalIds || []).filter((id) => id !== terminalId);
  if (terminalIds.length === 0) {
    return closeSurface(current, {
      placement: "right",
      surfaceId,
      kind: "terminal",
      resourceId: surface.resourceId,
    });
  }
  const nextSurface = {
    ...surface,
    terminalIds,
    activeTerminalId:
      surface.activeTerminalId === terminalId
        ? terminalIds[terminalIds.length - 1] || terminalIds[0]
        : surface.activeTerminalId,
  };
  const surfaces = items.map((item, itemIndex) => (itemIndex === index ? nextSurface : item));
  const key = normalizeSessionId(input && (input.sessionId || current.activeSessionKey));
  const nextPanel = activateRightPanelSurface({ ...current.rightPanel, surfaces }, nextSurface);
  return rememberRightPanelSession({
    ...current,
    rightPanel: nextPanel,
  }, nextPanel, key);
}

export function reduceWorkbenchState(state, action) {
  const current = state || createWorkbenchState();
  switch (action.type) {
    case "workbench_session_activated":
      return activateWorkbenchSession(current, action.sessionId);
    case "workbench_surface_opened":
      return openSurface(current, action);
    case "workbench_surface_activated":
      return activateSurface(current, action);
    case "workbench_surface_closed":
      return closeSurface(current, action);
    case "workbench_surface_close_others":
      return closeOtherSurfaces(current, action);
    case "workbench_surface_close_to_right":
      return closeSurfacesToRight(current, action);
    case "workbench_surface_close_all":
      return closeAllSurfaces(current, action);
    case "workbench_terminal_surface_split":
      return splitTerminalSurface(current, action);
    case "workbench_terminal_surface_terminal_activated":
      return activateTerminalPane(current, action);
    case "workbench_terminal_surface_terminal_closed":
      return closeTerminalPane(current, action);
    case "workbench_command_palette_opened":
      return {
        ...current,
        commandPalette: { ...current.commandPalette, open: true, query: "", selectedIndex: 0 },
      };
    case "workbench_command_palette_closed":
      return {
        ...current,
        commandPalette: { ...current.commandPalette, open: false, query: "", selectedIndex: 0 },
      };
    case "workbench_command_palette_query_changed":
      return {
        ...current,
        commandPalette: {
          ...current.commandPalette,
          query: String(action.query || ""),
          selectedIndex: 0,
        },
      };
    case "workbench_right_panel_toggled":
      return {
        ...current,
        rightPanel: { ...current.rightPanel, open: !current.rightPanel.open },
      };
    case "workbench_bottom_drawer_toggled":
      return {
        ...current,
        bottomDrawer: { ...current.bottomDrawer, open: !current.bottomDrawer.open },
      };
    default:
      return current;
  }
}
