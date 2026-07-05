import { readActiveThreadId } from "../session-runtime/thread-state.js";
import {
  bottomDrawerSurfaceDefinitionFor,
  surfaceDefinitionFor,
} from "../workbench/surfaces.js";

const TERMINAL_DIMENSIONS = Object.freeze({ cols: 100, rows: 30 });
const TERMINAL_SURFACE_KIND = "terminal";

const BOTTOM_DRAWER_ACTIVATION_HANDLERS = Object.freeze(Object.assign(Object.create(null), {
  "terminal.ensure_open": async ({ ensureOpen }) => ensureOpen(),
  "workbench.surface": async ({ dispatch, kind }) => {
    dispatch({ type: "workbench_surface_activated", placement: "bottom", kind });
    return kind;
  },
}));

function noop() {}

function readState(getState) {
  const state = typeof getState === "function" ? getState() : {};
  return state && typeof state === "object" ? state : {};
}

function readTerminalState(state) {
  return state.terminal || { activeTerminalId: "", terminalIds: [], sessions: {} };
}

function readSessionId(state) {
  return readActiveThreadId(state);
}

function readApi(deps, name) {
  const candidate = deps.api && deps.api[name];
  return typeof candidate === "function" ? candidate : null;
}

function noticeFromError(error, fallback) {
  return error && error.message ? error.message : fallback;
}

function dispatchNotice(dispatch, notice) {
  if (!notice) return;
  dispatch({ type: "interaction_notice_set", notice });
}

function readTerminalChrome(deps) {
  const value =
    typeof deps.getTerminalChrome === "function"
      ? deps.getTerminalChrome()
      : deps.terminalChrome;
  return value && typeof value === "object" ? value : {};
}

function terminalChromeText(deps, key) {
  return String(readTerminalChrome(deps)[key] || "");
}

function readAppCapabilities(deps) {
  const value =
    typeof deps.getAppCapabilities === "function"
      ? deps.getAppCapabilities()
      : deps.appCapabilities;
  return value && typeof value === "object" ? value : null;
}

function terminalSurfaceTitle(deps, fallback = "") {
  const definition = rightPanelTerminalSurfaceDefinition(deps);
  return String((definition && definition.title) || fallback || "");
}

function rightPanelTerminalSurfaceDefinition(deps) {
  const appCapabilities = readAppCapabilities(deps);
  return appCapabilities ? surfaceDefinitionFor(TERMINAL_SURFACE_KIND, appCapabilities) : null;
}

function normalizeTerminalId(terminalId) {
  return String(terminalId || "");
}

function uniqueStrings(values) {
  const seen = {};
  const result = [];
  for (const value of values) {
    const normalized = normalizeTerminalId(value);
    if (!normalized || seen[normalized]) continue;
    seen[normalized] = true;
    result.push(normalized);
  }
  return result;
}

function isTerminalSurface(surface) {
  return Boolean(surface && surface.kind === TERMINAL_SURFACE_KIND);
}

function terminalIdsFromSurface(surface) {
  if (!isTerminalSurface(surface)) return [];
  if (Array.isArray(surface.terminalIds)) return surface.terminalIds;
  return [surface.terminalId];
}

function terminalSurfaceActionInput(surface) {
  if (!isTerminalSurface(surface)) return null;
  return {
    placement: "right",
    surfaceId: surface.id,
  };
}

function allKnownTerminalIds(state) {
  const terminal = readTerminalState(state);
  const surfaces = state.workbench?.rightPanel?.surfaces || [];
  const panelIds = surfaces.flatMap(terminalIdsFromSurface);
  return uniqueStrings([...(terminal.terminalIds || []), ...panelIds]);
}

function nextId(deps, ids) {
  if (typeof deps.nextTerminalId === "function") {
    return normalizeTerminalId(deps.nextTerminalId(ids));
  }
  return `terminal-${ids.length + 1}`;
}

export function createTerminalController(deps = {}) {
  const dispatch = typeof deps.dispatch === "function" ? deps.dispatch : noop;
  const getState = () => readState(deps.getState);

  function requireSession() {
    const state = getState();
    const sessionId = readSessionId(state);
    if (!sessionId) {
      dispatchNotice(dispatch, terminalChromeText(deps, "sessionRequiredNotice"));
      return null;
    }
    return { state, sessionId };
  }

  async function ensureOpen(preferredId = "") {
    const context = requireSession();
    if (!context) return null;
    const terminal = readTerminalState(context.state);
    const terminalId =
      normalizeTerminalId(preferredId) ||
      normalizeTerminalId(terminal.activeTerminalId) ||
      nextId(deps, terminal.terminalIds || []);
    const openTerminal = readApi(deps, "openTerminal");
    if (!openTerminal || !terminalId) return null;
    try {
      const payload = await openTerminal(context.sessionId, terminalId, TERMINAL_DIMENSIONS);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      dispatch({ type: "terminal_active_set", terminalId });
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: TERMINAL_SURFACE_KIND });
      return terminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, terminalChromeText(deps, "openFailedNotice")));
      return null;
    }
  }

  async function openSession(terminalId = "") {
    const context = requireSession();
    if (!context) return null;
    const terminal = readTerminalState(context.state);
    const targetTerminalId = normalizeTerminalId(terminalId) || nextId(deps, terminal.terminalIds || []);
    const openTerminal = readApi(deps, "openTerminal");
    if (!openTerminal || !targetTerminalId) return null;
    try {
      const payload = await openTerminal(context.sessionId, targetTerminalId, TERMINAL_DIMENSIONS);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, terminalChromeText(deps, "openFailedNotice")));
      return null;
    }
  }

  async function refresh() {
    const state = getState();
    const sessionId = readSessionId(state);
    if (!sessionId) return;
    const listTerminals = readApi(deps, "listTerminals");
    if (!listTerminals) return;
    try {
      const payload = await listTerminals(sessionId);
      dispatch({ type: "terminal_summaries_loaded", terminals: payload.terminals || [] });
    } catch (_) {
      return;
    }
  }

  async function sendTo(terminalId, text) {
    const state = getState();
    const sessionId = readSessionId(state);
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!sessionId || !targetTerminalId) return null;
    const writeTerminal = readApi(deps, "writeTerminal");
    if (!writeTerminal) return null;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      await writeTerminal(sessionId, targetTerminalId, text);
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, terminalChromeText(deps, "writeFailedNotice")));
      return null;
    }
  }

  async function sendActive(text) {
    const terminal = readTerminalState(getState());
    return sendTo(terminal.activeTerminalId, text);
  }

  async function clearById(terminalId) {
    const state = getState();
    const sessionId = readSessionId(state);
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!sessionId || !targetTerminalId) return null;
    const clearTerminal = readApi(deps, "clearTerminal");
    if (!clearTerminal) return null;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      const payload = await clearTerminal(sessionId, targetTerminalId);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, terminalChromeText(deps, "clearFailedNotice")));
      return null;
    }
  }

  async function clearActive() {
    const terminal = readTerminalState(getState());
    return clearById(terminal.activeTerminalId);
  }

  async function restartById(terminalId) {
    const state = getState();
    const sessionId = readSessionId(state);
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!sessionId || !targetTerminalId) return null;
    const restartTerminal = readApi(deps, "restartTerminal");
    if (!restartTerminal) return null;
    try {
      dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
      const payload = await restartTerminal(sessionId, targetTerminalId, TERMINAL_DIMENSIONS);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, terminalChromeText(deps, "restartFailedNotice")));
      return null;
    }
  }

  async function restartActive() {
    const terminal = readTerminalState(getState());
    return restartById(terminal.activeTerminalId);
  }

  async function closeActive() {
    const state = getState();
    const sessionId = readSessionId(state);
    const terminal = readTerminalState(state);
    const terminalId = normalizeTerminalId(terminal.activeTerminalId);
    if (!sessionId || !terminalId) return null;
    const closeTerminal = readApi(deps, "closeTerminal");
    if (!closeTerminal) return null;
    try {
      await closeTerminal(sessionId, terminalId);
      dispatch({
        type: "terminal_event",
        event: { type: "closed", session_id: sessionId, terminal_id: terminalId },
      });
      return terminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, terminalChromeText(deps, "closeFailedNotice")));
      return null;
    }
  }

  async function selectBottomDrawerKind(kind) {
    const definition = bottomDrawerSurfaceDefinitionFor(kind, readAppCapabilities(deps));
    const handler = definition
      ? BOTTOM_DRAWER_ACTIVATION_HANDLERS[definition.activationKind]
      : null;
    return handler ? handler({ dispatch, ensureOpen, kind }) : null;
  }

  async function openRightPanelSurface(preferredId = "") {
    const definition = rightPanelTerminalSurfaceDefinition(deps);
    if (!definition) return null;
    const state = getState();
    const terminalId = normalizeTerminalId(preferredId) || nextId(deps, allKnownTerminalIds(state));
    const openedTerminalId = await openSession(terminalId);
    if (!openedTerminalId) return null;
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: TERMINAL_SURFACE_KIND,
      title: terminalSurfaceTitle(deps, openedTerminalId),
      resourceId: openedTerminalId,
      terminalId: openedTerminalId,
      terminalIds: [openedTerminalId],
      activeTerminalId: openedTerminalId,
    });
    return openedTerminalId;
  }

  async function splitRightPanelSurface(surface, splitDirection = "horizontal") {
    const surfaceAction = terminalSurfaceActionInput(surface);
    if (!surfaceAction) return null;
    const terminalId = nextId(deps, allKnownTerminalIds(getState()));
    const openedTerminalId = await openSession(terminalId);
    if (!openedTerminalId) return null;
    dispatch({
      type: "workbench_terminal_surface_split",
      ...surfaceAction,
      terminalId: openedTerminalId,
      splitDirection,
    });
    return openedTerminalId;
  }

  function activateRightPanelPane(surface, terminalId) {
    const surfaceAction = terminalSurfaceActionInput(surface);
    if (!surfaceAction) return null;
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!targetTerminalId) return null;
    dispatch({
      type: "workbench_terminal_surface_terminal_activated",
      ...surfaceAction,
      terminalId: targetTerminalId,
    });
    dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
    return targetTerminalId;
  }

  async function closeRightPanelPane(surface, terminalId) {
    const surfaceAction = terminalSurfaceActionInput(surface);
    if (!surfaceAction) return null;
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!targetTerminalId) return null;
    const context = requireSession();
    if (!context) return null;
    const closeTerminal = readApi(deps, "closeTerminal");
    if (!closeTerminal) return null;
    try {
      await closeTerminal(context.sessionId, targetTerminalId);
      dispatch({
        type: "terminal_event",
        event: { type: "closed", session_id: context.sessionId, terminal_id: targetTerminalId },
      });
      dispatch({
        type: "workbench_terminal_surface_terminal_closed",
        ...surfaceAction,
        terminalId: targetTerminalId,
      });
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, terminalChromeText(deps, "closeFailedNotice")));
      return null;
    }
  }

  return {
    ensureOpen,
    openSession,
    refresh,
    sendActive,
    sendTo,
    clearActive,
    clearById,
    restartActive,
    restartById,
    closeActive,
    selectBottomDrawerKind,
    openRightPanelSurface,
    splitRightPanelSurface,
    activateRightPanelPane,
    closeRightPanelPane,
  };
}
