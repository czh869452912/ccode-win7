import {
  BOTTOM_DRAWER_SURFACES,
  DEFAULT_SESSION_KEY,
  RIGHT_PANEL_KINDS,
  createWorkbenchState,
  surfaceDefinitionFor,
  titleForSurfaceKind,
} from "./surfaces.js";

export const WORKBENCH_UI_STATE_KEY = "embedagent:workbench-ui-state:v1";

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function asString(value) {
  return String(value || "").trim();
}

function clampNumber(value, fallback, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.max(min, Math.min(max, Math.trunc(number)));
}

function clampOptionalNumber(value, min, max) {
  if (value === null || value === undefined || value === "") return null;
  return clampNumber(value, null, min, max);
}

function normalizePlacement(placement) {
  return placement === "bottom" ? "bottom" : "right";
}

function normalizeFilePath(path) {
  return asString(path).replace(/\\/g, "/").replace(/^\/+/, "");
}

function titleFor(kind, title, resourceId) {
  const explicit = asString(title);
  if (explicit) return explicit;
  if (kind === "file") {
    const parts = normalizeFilePath(resourceId).split("/");
    return parts[parts.length - 1] || "File";
  }
  return titleForSurfaceKind(kind);
}

function surfaceIdFor(placement, kind, resourceId) {
  const idResource = asString(resourceId);
  return idResource ? `${placement}:${kind}:${idResource}` : `${placement}:${kind}`;
}

function uniqueStrings(values) {
  const result = [];
  for (const value of values || []) {
    const item = asString(value);
    if (item && !result.includes(item)) result.push(item);
  }
  return result;
}

function sanitizeSurface(input, fallbackPlacement) {
  const source = asObject(input);
  const placement = normalizePlacement(source.placement || fallbackPlacement);
  const allowed = placement === "bottom" ? BOTTOM_DRAWER_SURFACES : RIGHT_PANEL_KINDS;
  const kind = asString(source.kind);
  if (!allowed.includes(kind)) return null;
  const definition = placement === "right" ? surfaceDefinitionFor(kind) : null;

  const filePath = kind === "file" ? normalizeFilePath(source.filePath || source.resourceId) : "";
  const resourceId =
    kind === "file"
      ? filePath
      : kind === "terminal"
        ? asString(source.terminalId || source.resourceId)
        : asString(source.resourceId);
  const terminalIds =
    kind === "terminal"
      ? uniqueStrings(
          Array.isArray(source.terminalIds)
            ? source.terminalIds
            : [source.terminalId || source.resourceId],
        )
      : [];
  const terminalId =
    kind === "terminal" ? asString(source.terminalId || resourceId || terminalIds[0]) : "";
  const revealLine = kind === "file" ? clampOptionalNumber(source.revealLine, 1, 1000000) : null;
  const revealRequestId = kind === "file" ? clampNumber(source.revealRequestId, 0, 0, 1000000) : 0;

  const base = {
    id: surfaceIdFor(placement, kind, resourceId),
    placement,
    kind,
    title: titleFor(kind, source.title, resourceId),
    resourceId,
    filePath,
    terminalId,
    revealLine,
    revealRequestId,
  };

  if (kind !== "terminal") {
    return definition ? pickSurfaceFields(base, definition.persistFields) : base;
  }
  const normalizedTerminalIds = terminalIds.length > 0 ? terminalIds : [terminalId].filter(Boolean);
  const activeTerminalId = asString(source.activeTerminalId);
  const terminalSurface = {
    ...base,
    terminalIds: normalizedTerminalIds,
    activeTerminalId: normalizedTerminalIds.includes(activeTerminalId)
      ? activeTerminalId
      : normalizedTerminalIds[0] || terminalId,
    ...(source.splitDirection === "vertical" ? { splitDirection: "vertical" } : {}),
  };
  if (!definition) return terminalSurface;
  return pickSurfaceFields(terminalSurface, definition.persistFields);
}

function pickSurfaceFields(surface, fields) {
  const result = {};
  for (const field of fields || []) {
    if (Object.prototype.hasOwnProperty.call(surface, field) && surface[field] !== undefined) {
      result[field] = surface[field];
    }
  }
  return result;
}

function sanitizeSurfaceList(items, placement) {
  if (!Array.isArray(items)) return [];
  const result = [];
  const seen = new Set();
  for (const item of items) {
    const surface = sanitizeSurface(item, placement);
    if (!surface || seen.has(surface.id)) continue;
    seen.add(surface.id);
    result.push(surface);
  }
  return result.slice(-12);
}

function sanitizeSessionSurfaces(value) {
  const source = asObject(value);
  const right = sanitizeSurfaceList(source.right, "right");
  const bottom = sanitizeSurfaceList(source.bottom, "bottom");
  const requestedActive = asString(source.activeRightSurfaceId);
  return {
    right,
    bottom,
    activeRightSurfaceId: right.some((surface) => surface.id === requestedActive)
      ? requestedActive
      : right[right.length - 1]?.id || null,
  };
}

function sanitizeSurfacesBySession(value) {
  const source = asObject(value);
  const result = {};
  for (const [key, surfaces] of Object.entries(source)) {
    const sessionKey = asString(key) || DEFAULT_SESSION_KEY;
    const sanitized = sanitizeSessionSurfaces(surfaces);
    if (sanitized.right.length > 0 || sanitized.bottom.length > 0) {
      result[sessionKey] = sanitized;
    }
  }
  return result;
}

export function parsePersistedWorkbenchUiState(value) {
  const source = asObject(value);
  const base = createWorkbenchState();
  const activeSessionKey = asString(source.activeSessionKey) || DEFAULT_SESSION_KEY;
  const surfacesBySession = sanitizeSurfacesBySession(source.surfacesBySession);
  const activeSession = surfacesBySession[activeSessionKey] || { right: [], activeRightSurfaceId: null };
  const activeRightSurface =
    activeSession.right.find((surface) => surface.id === activeSession.activeRightSurfaceId) ||
    activeSession.right[activeSession.right.length - 1] ||
    null;

  return {
    ...base,
    activeSessionKey,
    rightPanel: {
      ...base.rightPanel,
      open: source.rightPanel?.open === false ? false : base.rightPanel.open,
      width: clampNumber(source.rightPanel?.width, base.rightPanel.width, 220, 720),
      surfaces: activeSession.right,
      activeKind: activeRightSurface ? activeRightSurface.kind : "",
      activeSurfaceId: activeRightSurface ? activeRightSurface.id : null,
    },
    bottomDrawer: {
      ...base.bottomDrawer,
      open: Boolean(source.bottomDrawer?.open),
      activeKind: BOTTOM_DRAWER_SURFACES.includes(source.bottomDrawer?.activeKind)
        ? source.bottomDrawer.activeKind
        : base.bottomDrawer.activeKind,
      height: clampNumber(source.bottomDrawer?.height, base.bottomDrawer.height, 140, 520),
    },
    commandPalette: base.commandPalette,
    surfacesBySession,
  };
}

export function serializeWorkbenchUiState(state) {
  const current = state || createWorkbenchState();
  const activeSessionKey = asString(current.activeSessionKey) || DEFAULT_SESSION_KEY;
  const currentRight = Array.isArray(current.rightPanel?.surfaces) ? current.rightPanel.surfaces : [];
  const currentSurfacesBySession = {
    ...asObject(current.surfacesBySession),
    [activeSessionKey]: {
      ...asObject(current.surfacesBySession && current.surfacesBySession[activeSessionKey]),
      right: currentRight,
      activeRightSurfaceId: current.rightPanel?.activeSurfaceId || null,
    },
  };
  const surfacesBySession = sanitizeSurfacesBySession(currentSurfacesBySession);
  return {
    version: 1,
    activeSessionKey,
    rightPanel: {
      open: current.rightPanel?.open !== false,
      width: clampNumber(current.rightPanel?.width, createWorkbenchState().rightPanel.width, 220, 720),
    },
    bottomDrawer: {
      open: Boolean(current.bottomDrawer?.open),
      activeKind: BOTTOM_DRAWER_SURFACES.includes(current.bottomDrawer?.activeKind)
        ? current.bottomDrawer.activeKind
        : createWorkbenchState().bottomDrawer.activeKind,
      height: clampNumber(current.bottomDrawer?.height, createWorkbenchState().bottomDrawer.height, 140, 520),
    },
    surfacesBySession,
  };
}

function storageOrDefault(storage) {
  if (storage) return storage;
  if (typeof window === "undefined") return null;
  return window.localStorage || null;
}

export function readPersistedWorkbenchUiState(storage) {
  const target = storageOrDefault(storage);
  if (!target) return createWorkbenchState();
  try {
    const raw = target.getItem(WORKBENCH_UI_STATE_KEY);
    if (!raw) return createWorkbenchState();
    return parsePersistedWorkbenchUiState(JSON.parse(raw));
  } catch {
    return createWorkbenchState();
  }
}

export function persistWorkbenchUiState(state, storage) {
  const target = storageOrDefault(storage);
  if (!target) return;
  try {
    target.setItem(WORKBENCH_UI_STATE_KEY, JSON.stringify(serializeWorkbenchUiState(state)));
  } catch {
    // Ignore quota/storage failures; layout memory should never break the workbench.
  }
}
