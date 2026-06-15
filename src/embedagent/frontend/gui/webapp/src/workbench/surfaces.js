export const RIGHT_PANEL_SURFACES = [
  "interaction",
  "tasks",
  "plan",
  "artifacts",
  "run",
  "problems",
  "review",
  "permissions",
  "runtime",
  "preview",
  "log",
];

export const BOTTOM_DRAWER_SURFACES = ["terminal", "run_output", "logs"];

const DEFAULT_SESSION_KEY = "__global__";

function normalizeSessionId(sessionId) {
  const value = String(sessionId || "").trim();
  return value || DEFAULT_SESSION_KEY;
}

function normalizePlacement(placement) {
  return placement === "bottom" ? "bottom" : "right";
}

function defaultActiveKind(placement) {
  return placement === "bottom" ? "run_output" : "tasks";
}

function allowedKinds(placement) {
  return placement === "bottom" ? BOTTOM_DRAWER_SURFACES : RIGHT_PANEL_SURFACES;
}

function makeSurface(input) {
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  return {
    id: `${placement}:${kind}:${String((input && input.resourceId) || "")}`,
    placement,
    kind,
    title: String((input && input.title) || kind),
    resourceId: String((input && input.resourceId) || ""),
  };
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

function removeSurface(items, surface) {
  return items.filter((item) => item.id !== surface.id);
}

export function createWorkbenchState() {
  return {
    sidebar: {
      activeSection: "threads",
      projectSection: "files",
    },
    rightPanel: {
      open: true,
      activeKind: "tasks",
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

export function openSurface(state, input) {
  const current = state || createWorkbenchState();
  const surface = makeSurface(input || {});
  const placement = normalizePlacement(surface.placement);
  if (!allowedKinds(placement).includes(surface.kind)) {
    return current;
  }
  const key = normalizeSessionId(input && input.sessionId);
  const existing = sessionSurfaces(current, key);
  const nextSessionSurfaces = {
    ...existing,
    [placement]: upsertSurface(existing[placement], surface),
  };
  return {
    ...current,
    surfacesBySession: {
      ...current.surfacesBySession,
      [key]: nextSessionSurfaces,
    },
    rightPanel:
      placement === "right"
        ? { ...current.rightPanel, open: true, activeKind: surface.kind }
        : current.rightPanel,
    bottomDrawer:
      placement === "bottom"
        ? { ...current.bottomDrawer, open: true, activeKind: surface.kind }
        : current.bottomDrawer,
  };
}

export function activateSurface(state, input) {
  const current = state || createWorkbenchState();
  const placement = normalizePlacement(input && input.placement);
  const kind = String((input && input.kind) || defaultActiveKind(placement));
  if (!allowedKinds(placement).includes(kind)) {
    return current;
  }
  if (placement === "bottom") {
    return {
      ...current,
      bottomDrawer: { ...current.bottomDrawer, open: true, activeKind: kind },
    };
  }
  return {
    ...current,
    rightPanel: { ...current.rightPanel, open: true, activeKind: kind },
  };
}

export function closeSurface(state, input) {
  const current = state || createWorkbenchState();
  const surface = makeSurface(input || {});
  const placement = normalizePlacement(surface.placement);
  const key = normalizeSessionId(input && input.sessionId);
  const existing = sessionSurfaces(current, key);
  const nextItems = removeSurface(existing[placement], surface);
  const nextSessionSurfaces = {
    ...existing,
    [placement]: nextItems,
  };
  const nextState = {
    ...current,
    surfacesBySession: {
      ...current.surfacesBySession,
      [key]: nextSessionSurfaces,
    },
  };
  if (placement === "bottom") {
    return {
      ...nextState,
      bottomDrawer: {
        ...nextState.bottomDrawer,
        open: nextItems.length > 0,
        activeKind: nextItems.length > 0 ? nextItems[0].kind : defaultActiveKind(placement),
      },
    };
  }
  return {
    ...nextState,
    rightPanel: {
      ...nextState.rightPanel,
      activeKind: nextItems.length > 0 ? nextItems[0].kind : defaultActiveKind(placement),
    },
  };
}

export function reduceWorkbenchState(state, action) {
  const current = state || createWorkbenchState();
  switch (action.type) {
    case "workbench_surface_opened":
      return openSurface(current, action);
    case "workbench_surface_activated":
      return activateSurface(current, action);
    case "workbench_surface_closed":
      return closeSurface(current, action);
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
