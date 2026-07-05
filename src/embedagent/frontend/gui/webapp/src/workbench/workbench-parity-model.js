import {
  buildCommandVisibilityContext,
  isTurnInterruptibleStatus,
  visibleCommands,
} from "./commands.js";

const T3_CENTER_MAX_WIDTH = 860;
const NARROW_BREAKPOINT = 980;
const MOBILE_BREAKPOINT = 720;

function numeric(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function viewportWidth(viewport) {
  return Math.max(0, Math.trunc(numeric(viewport && viewport.width, 0)));
}

function currentStatus(state) {
  return String((state && state.snapshot && state.snapshot.status) || "idle");
}

function currentSessionId(state) {
  return String(
    (state && state.thread && state.thread.currentSessionId) ||
      (state && state.snapshot && state.snapshot.session_id) ||
      "",
  );
}

function hasActiveWorkspace(state) {
  return Boolean(state && state.app && state.app.hasActiveWorkspace);
}

function hasInteraction(state) {
  return Boolean(
    state &&
      state.snapshot &&
      state.snapshot.pending_interaction_valid &&
      state.snapshot.pending_interaction,
  );
}

function rightPanelMode(state, width) {
  const panel = (state && state.workbench && state.workbench.rightPanel) || {};
  if (panel.open === false || (Array.isArray(panel.surfaces) && panel.surfaces.length === 0)) {
    return "closed";
  }
  if (width <= MOBILE_BREAKPOINT) return "mobile-stacked";
  if (width <= NARROW_BREAKPOINT) return "stacked";
  return "sidecar";
}

function bottomDrawerMode(state, width) {
  const drawer = (state && state.workbench && state.workbench.bottomDrawer) || {};
  if (!drawer.open) return "closed";
  if (width <= MOBILE_BREAKPOINT) return "compact";
  return "docked";
}

function composerMode(state, status) {
  if (hasInteraction(state)) return "interaction";
  if (isTurnInterruptibleStatus(status)) return "running";
  if (currentSessionId(state)) return "command-ready";
  return "empty";
}

function timelineDensity(width) {
  if (width <= MOBILE_BREAKPOINT) return "compact";
  if (width <= NARROW_BREAKPOINT) return "compact";
  return "compact";
}

function surfaceCommands(state, status) {
  const commands = visibleCommands(buildCommandVisibilityContext({
    currentSessionId: currentSessionId(state),
    currentStatus: status,
    hasActiveWorkspace: hasActiveWorkspace(state),
    paletteOpen: Boolean(
      state && state.workbench && state.workbench.commandPalette && state.workbench.commandPalette.open,
    ),
    appCapabilities: state && state.app ? state.app.capabilities : null,
    sessionCapabilities: state ? state.sessionCapabilities : null,
  }));
  return commands
    .filter((command) => command && (command.group === "surface" || command.drawer))
    .map((command) => command.id);
}

export function buildWorkbenchParityModel(state, viewport = {}) {
  const width = viewportWidth(viewport);
  const status = currentStatus(state);
  const rightPanel =
    (state && state.workbench && state.workbench.rightPanel) || { surfaces: [], open: false };

  return {
    centerColumn: {
      maxWidth: width > 0 ? Math.min(T3_CENTER_MAX_WIDTH, width) : T3_CENTER_MAX_WIDTH,
    },
    rightPanel: {
      mode: rightPanelMode(state, width),
      surfaceCount: Array.isArray(rightPanel.surfaces) ? rightPanel.surfaces.length : 0,
    },
    bottomDrawer: {
      mode: bottomDrawerMode(state, width),
    },
    composer: {
      mode: composerMode(state, status),
    },
    timeline: {
      density: timelineDensity(width),
    },
    commandPalette: {
      availableSurfaceCommands: surfaceCommands(state, status),
    },
  };
}
