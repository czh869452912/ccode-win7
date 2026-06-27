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
    title: "Preview",
    icon: "B",
    description: "Open a local browser preview.",
    placement: "right",
    resourceId: "optional",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    launcher: true,
    launcherOrder: 10,
    command: true,
    slash: "/preview",
    visibleWhen: "always",
    keywords: ["browser", "localhost", "web"],
  }),
  defineSurface({
    kind: "diff",
    title: "Diff",
    icon: "D",
    description: "Review local changes.",
    placement: "right",
    resourceId: "current",
    defaultResourceId: "current",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    launcher: true,
    launcherOrder: 40,
    command: true,
    slash: "/diff",
    visibleWhen: "always",
    keywords: ["git", "changes", "diff"],
    inspectorKind: "diff",
  }),
  defineSurface({
    kind: "files",
    title: "Files",
    icon: "F",
    description: "Browse workspace files.",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    launcher: true,
    launcherOrder: 20,
    command: true,
    slash: "/workspace",
    visibleWhen: "always",
  }),
  defineSurface({
    kind: "file",
    title: "File",
    icon: "F",
    description: "View a workspace file.",
    placement: "right",
    resourceId: "file_path",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    launcher: false,
    launcherOrder: 0,
    command: false,
  }),
  defineSurface({
    kind: "terminal",
    title: "Terminal",
    icon: "T",
    description: "Use a shell in this workspace.",
    placement: "right",
    resourceId: "terminal_id",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: TERMINAL_PERSIST_FIELDS,
    launcher: true,
    launcherOrder: 30,
    command: true,
    slash: "",
    visibleWhen: "has_session",
  }),
  defineSurface({
    kind: "plan",
    title: "Plan",
    icon: "P",
    description: "Inspect the current plan.",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    launcher: true,
    launcherOrder: 50,
    command: true,
    slash: "/plan",
    visibleWhen: "always",
    inspectorKind: "plan",
  }),
  defineSurface({
    kind: "source_control",
    title: "Source Control",
    icon: "S",
    description: "Review local Git status.",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    launcher: true,
    launcherOrder: 60,
    command: true,
    slash: "",
    visibleWhen: "always",
    readOnly: true,
    offline: true,
    inspectorKind: "source_control",
    keywords: ["git", "changes", "local"],
  }),
  defineSurface({
    kind: "settings",
    title: "Settings",
    icon: "G",
    description: "Adjust app-shell preferences.",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    launcher: true,
    launcherOrder: 70,
    command: true,
    slash: "",
    visibleWhen: "always",
    inspectorKind: "settings",
  }),
  defineSurface({
    kind: "diagnostics",
    title: "Diagnostics",
    icon: "I",
    description: "Inspect app-shell health.",
    placement: "right",
    resourceId: "singleton",
    defaultResourceId: "",
    closeBehavior: "closable",
    persistFields: DEFAULT_PERSIST_FIELDS,
    launcher: true,
    launcherOrder: 80,
    command: true,
    slash: "",
    visibleWhen: "always",
    inspectorKind: "diagnostics",
  }),
]);

export function rightPanelSurfaceDefinitions() {
  return RIGHT_PANEL_SURFACE_REGISTRY;
}

export function surfaceDefinitionFor(kind) {
  const normalized = String(kind || "");
  return RIGHT_PANEL_SURFACE_REGISTRY.find((definition) => definition.kind === normalized) || null;
}

export function rightPanelLauncherSurfaceDefinitions() {
  return RIGHT_PANEL_SURFACE_REGISTRY
    .filter((definition) => definition.launcher)
    .slice()
    .sort((left, right) => (left.launcherOrder || 0) - (right.launcherOrder || 0));
}

export function surfaceCommandDefinitions() {
  return rightPanelLauncherSurfaceDefinitions()
    .filter((definition) => definition.command !== false)
    .map((definition) => ({
      id: `surface.${definition.kind}`,
      group: "surface",
      label: `Open ${definition.title}`,
      slash: definition.slash || "",
      surface: definition.kind,
      visibleWhen: definition.visibleWhen || "always",
      ...(definition.keywords.length > 0 ? { keywords: Array.from(definition.keywords) } : {}),
    }));
}

export const RIGHT_PANEL_KINDS = RIGHT_PANEL_SURFACE_REGISTRY.map((definition) => definition.kind);
export const RIGHT_PANEL_SURFACES = rightPanelLauncherSurfaceDefinitions()
  .map((definition) => definition.kind);
export const BOTTOM_DRAWER_SURFACES = ["terminal", "run_output", "logs"];

export const DEFAULT_SESSION_KEY = "__global__";

function normalizeSessionId(sessionId) {
  const value = String(sessionId || "").trim();
  return value || DEFAULT_SESSION_KEY;
}

function normalizePlacement(placement) {
  return placement === "bottom" ? "bottom" : "right";
}

function defaultActiveKind(placement) {
  return placement === "bottom" ? "run_output" : "";
}

function allowedKinds(placement) {
  return placement === "bottom" ? BOTTOM_DRAWER_SURFACES : RIGHT_PANEL_KINDS;
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

export function titleForSurfaceKind(kind) {
  const definition = surfaceDefinitionFor(kind);
  return definition ? definition.title : String(kind || "");
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
    sidebar: {
      activeSection: "threads",
      projectSection: "files",
    },
    rightPanel: {
      open: true,
      activeKind: "",
      activeSurfaceId: null,
      surfaces: [],
      width: 320,
    },
    bottomDrawer: {
      open: false,
      activeKind: "run_output",
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
    title: basenameForPath(filePath) || "File",
  });
}

export function openPreviewSurface(state, input = {}) {
  const previewId = String(input.previewId || input.resourceId || "").trim();
  return openSurface(state, {
    ...input,
    placement: "right",
    kind: "preview",
    resourceId: previewId,
    title: input.title || "Preview",
  });
}

export function openTerminalSurface(state, input = {}) {
  const terminalId = String(input.terminalId || input.resourceId || "").trim();
  if (!terminalId) return state || createWorkbenchState();
  return openSurface(state, {
    ...input,
    placement: "right",
    kind: "terminal",
    title: input.title || "Terminal",
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
