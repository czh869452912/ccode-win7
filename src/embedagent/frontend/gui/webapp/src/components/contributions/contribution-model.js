import {
  buildCommandVisibilityContext,
  isTurnInterruptibleStatus,
  visibleCommands,
} from "../../workbench/commands.js";
import { buildAppCapabilityModelFromState } from "../../app-runtime/app-capability-model.js";
import { buildSessionCapabilityModelFromState } from "../../session-runtime/session-capability-model.js";

const CENTER_MAX_WIDTH = 860;
const MOBILE_BREAKPOINT = 720;

function widthOf(viewport) {
  const width = Number(viewport?.width);
  return Number.isFinite(width) ? Math.max(0, Math.trunc(width)) : 0;
}

function currentSessionId(state) {
  return String(state?.thread?.currentSessionId || state?.snapshot?.session_id || "");
}

function currentStatus(state) {
  return String(state?.snapshot?.status || "idle");
}

function composerMode(state, status) {
  if (state?.snapshot?.pending_interaction_valid && state.snapshot.pending_interaction) {
    return "interaction";
  }
  if (isTurnInterruptibleStatus(status)) return "running";
  return currentSessionId(state) ? "command-ready" : "empty";
}

function surfaceCommands(state, status) {
  const app = buildAppCapabilityModelFromState(state);
  const session = buildSessionCapabilityModelFromState(state);
  return visibleCommands(buildCommandVisibilityContext({
    currentSessionId: currentSessionId(state),
    currentStatus: status,
    hasActiveWorkspace: Boolean(state?.app?.hasActiveWorkspace),
    paletteOpen: Boolean(state?.contribution?.palette?.open),
    appCapabilities: app.appCapabilities,
    sessionCapabilities: session.sessionCapabilities,
  }))
    .filter((command) => command?.dispatch?.kind === "shell.surface")
    .map((command) => command.id);
}

export function buildContributionModel(state, viewport = {}) {
  const width = widthOf(viewport);
  const status = currentStatus(state);
  const items = Array.isArray(state?.contribution?.items) ? state.contribution.items : [];
  return {
    centerColumn: {
      maxWidth: width > 0 ? Math.min(CENTER_MAX_WIDTH, width) : CENTER_MAX_WIDTH,
    },
    contribution: {
      mode: items.length === 0 ? "closed" : (width <= MOBILE_BREAKPOINT ? "sheet" : "overlay"),
      count: items.length,
    },
    composer: { mode: composerMode(state, status) },
    timeline: { density: "compact" },
    commandPalette: { availableSurfaceCommands: surfaceCommands(state, status) },
  };
}
