const TERMINAL_DIMENSIONS = Object.freeze({ cols: 100, rows: 30 });
const SESSION_NOTICE = "Open a session before using the terminal.";

function noop() {}

function readState(getState) {
  const state = typeof getState === "function" ? getState() : {};
  return state && typeof state === "object" ? state : {};
}

function readTerminalState(state) {
  return state.terminal || { activeTerminalId: "", terminalIds: [], sessions: {} };
}

function readSessionId(state) {
  return String(state.currentSessionId || "");
}

function readApi(deps, name) {
  const candidate = deps.api && deps.api[name];
  return typeof candidate === "function" ? candidate : null;
}

function noticeFromError(error, fallback) {
  return error && error.message ? error.message : fallback;
}

function dispatchNotice(dispatch, notice) {
  dispatch({ type: "interaction_notice_set", notice });
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

function terminalIdsFromSurface(surface) {
  if (!surface || surface.kind !== "terminal") return [];
  if (Array.isArray(surface.terminalIds)) return surface.terminalIds;
  return [surface.terminalId];
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
      dispatchNotice(dispatch, SESSION_NOTICE);
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
      dispatch({ type: "workbench_surface_activated", placement: "bottom", kind: "terminal" });
      return terminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, "Terminal failed to open."));
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
      dispatchNotice(dispatch, noticeFromError(error, "Terminal failed to open."));
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
      dispatchNotice(dispatch, noticeFromError(error, "Terminal write failed."));
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
      dispatchNotice(dispatch, noticeFromError(error, "Terminal clear failed."));
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
      dispatchNotice(dispatch, noticeFromError(error, "Terminal restart failed."));
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
      dispatchNotice(dispatch, noticeFromError(error, "Terminal close failed."));
      return null;
    }
  }

  async function selectBottomDrawerKind(kind) {
    if (kind === "terminal") {
      return ensureOpen();
    }
    dispatch({ type: "workbench_surface_activated", placement: "bottom", kind });
    return kind;
  }

  async function openRightPanelSurface(preferredId = "") {
    const state = getState();
    const terminalId = normalizeTerminalId(preferredId) || nextId(deps, allKnownTerminalIds(state));
    const openedTerminalId = await openSession(terminalId);
    if (!openedTerminalId) return null;
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: "terminal",
      title: "Terminal",
      resourceId: openedTerminalId,
      terminalId: openedTerminalId,
      terminalIds: [openedTerminalId],
      activeTerminalId: openedTerminalId,
    });
    dispatch({ type: "set_inspector", value: "terminal" });
    return openedTerminalId;
  }

  async function splitRightPanelSurface(surface, splitDirection = "horizontal") {
    if (!surface || surface.kind !== "terminal") return null;
    const terminalId = nextId(deps, allKnownTerminalIds(getState()));
    const openedTerminalId = await openSession(terminalId);
    if (!openedTerminalId) return null;
    dispatch({
      type: "workbench_terminal_surface_split",
      placement: "right",
      surfaceId: surface.id,
      terminalId: openedTerminalId,
      splitDirection,
    });
    return openedTerminalId;
  }

  function activateRightPanelPane(surface, terminalId) {
    if (!surface || surface.kind !== "terminal") return null;
    const targetTerminalId = normalizeTerminalId(terminalId);
    if (!targetTerminalId) return null;
    dispatch({
      type: "workbench_terminal_surface_terminal_activated",
      placement: "right",
      surfaceId: surface.id,
      terminalId: targetTerminalId,
    });
    dispatch({ type: "terminal_active_set", terminalId: targetTerminalId });
    return targetTerminalId;
  }

  async function closeRightPanelPane(surface, terminalId) {
    if (!surface || surface.kind !== "terminal") return null;
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
        placement: "right",
        surfaceId: surface.id,
        terminalId: targetTerminalId,
      });
      return targetTerminalId;
    } catch (error) {
      dispatchNotice(dispatch, noticeFromError(error, "Terminal close failed."));
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
