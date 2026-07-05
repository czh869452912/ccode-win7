import {
  DEFAULT_SESSION_KEY,
  createWorkbenchState,
  persistedSurfaceDefinitions,
  persistedSurfaceFrom,
  supportedSurfaceKinds,
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

function normalizePlacement(placement) {
  return placement === "bottom" ? "bottom" : "right";
}

function sanitizeSurfaceList(items, placement) {
  if (!Array.isArray(items)) return [];
  const result = [];
  const seen = new Set();
  for (const item of items) {
    const surface = persistedSurfaceFrom(item, placement);
    if (!surface || seen.has(surface.id)) continue;
    seen.add(surface.id);
    result.push(surface);
  }
  return result.slice(-12);
}

function appCapabilitySurfaceKinds(placement, appCapabilities) {
  return persistedSurfaceDefinitions(appCapabilities, placement)
    .map((definition) => definition.kind);
}

function filterSurfacesByAppCapabilities(items, placement, appCapabilities) {
  const allowed = new Set(appCapabilitySurfaceKinds(placement, appCapabilities));
  return (items || []).filter((surface) => allowed.has(surface.kind));
}

function sanitizeSessionSurfaces(value, appCapabilities = null) {
  const source = asObject(value);
  const right = appCapabilities
    ? filterSurfacesByAppCapabilities(sanitizeSurfaceList(source.right, "right"), "right", appCapabilities)
    : sanitizeSurfaceList(source.right, "right");
  const bottom = appCapabilities
    ? filterSurfacesByAppCapabilities(sanitizeSurfaceList(source.bottom, "bottom"), "bottom", appCapabilities)
    : sanitizeSurfaceList(source.bottom, "bottom");
  const requestedActive = asString(source.activeRightSurfaceId);
  return {
    right,
    bottom,
    activeRightSurfaceId: right.some((surface) => surface.id === requestedActive)
      ? requestedActive
      : right[right.length - 1]?.id || null,
  };
}

function sanitizeSurfacesBySession(value, appCapabilities = null) {
  const source = asObject(value);
  const result = {};
  for (const [key, surfaces] of Object.entries(source)) {
    const sessionKey = asString(key) || DEFAULT_SESSION_KEY;
    const sanitized = sanitizeSessionSurfaces(surfaces, appCapabilities);
    if (sanitized.right.length > 0 || sanitized.bottom.length > 0) {
      result[sessionKey] = sanitized;
    }
  }
  return result;
}

function currentSessionSurfacesForState(current, activeSessionKey) {
  const currentRight = Array.isArray(current.rightPanel?.surfaces) ? current.rightPanel.surfaces : [];
  return {
    ...asObject(current.surfacesBySession),
    [activeSessionKey]: {
      ...asObject(current.surfacesBySession && current.surfacesBySession[activeSessionKey]),
      right: currentRight,
      activeRightSurfaceId: current.rightPanel?.activeSurfaceId || null,
    },
  };
}

export function sanitizeWorkbenchUiStateForAppCapabilities(state, appCapabilities) {
  const current = state || createWorkbenchState();
  const activeSessionKey = asString(current.activeSessionKey) || DEFAULT_SESSION_KEY;
  const surfacesBySession = sanitizeSurfacesBySession(
    currentSessionSurfacesForState(current, activeSessionKey),
    appCapabilities || {},
  );
  const activeSession = surfacesBySession[activeSessionKey] || { right: [], activeRightSurfaceId: null };
  const activeRightSurface =
    activeSession.right.find((surface) => surface.id === activeSession.activeRightSurfaceId) ||
    activeSession.right[activeSession.right.length - 1] ||
    null;
  const allowedBottomKinds = appCapabilitySurfaceKinds("bottom", appCapabilities || {});
  const requestedBottomKind = asString(current.bottomDrawer?.activeKind);
  const activeBottomKind = allowedBottomKinds.includes(requestedBottomKind)
    ? requestedBottomKind
    : allowedBottomKinds[0] || "";
  return {
    ...current,
    activeSessionKey,
    rightPanel: {
      ...current.rightPanel,
      surfaces: activeSession.right,
      activeKind: activeRightSurface ? activeRightSurface.kind : "",
      activeSurfaceId: activeRightSurface ? activeRightSurface.id : null,
    },
    bottomDrawer: {
      ...current.bottomDrawer,
      open: Boolean(current.bottomDrawer?.open && allowedBottomKinds.length > 0),
      activeKind: activeBottomKind,
    },
    surfacesBySession,
  };
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
      activeKind: supportedSurfaceKinds("bottom").includes(source.bottomDrawer?.activeKind)
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
  const surfacesBySession = sanitizeSurfacesBySession(
    currentSessionSurfacesForState(current, activeSessionKey),
  );
  return {
    version: 1,
    activeSessionKey,
    rightPanel: {
      open: current.rightPanel?.open !== false,
      width: clampNumber(current.rightPanel?.width, createWorkbenchState().rightPanel.width, 220, 720),
    },
    bottomDrawer: {
      open: Boolean(current.bottomDrawer?.open),
      activeKind: supportedSurfaceKinds("bottom").includes(current.bottomDrawer?.activeKind)
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
