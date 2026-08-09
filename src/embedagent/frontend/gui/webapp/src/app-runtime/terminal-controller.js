import { readActiveThreadId } from "../session-runtime/thread-state.js";
import { terminalCapabilityEnabled } from "../terminal/terminal-capability.js";
import { nextTerminalId as defaultNextTerminalId } from "../terminal/terminal-labels.js";

const TERMINAL_DIMENSIONS = Object.freeze({ cols: 100, rows: 30 });

function noop() {}

function readState(getState) {
  const state = typeof getState === "function" ? getState() : {};
  return state && typeof state === "object" ? state : {};
}

function readTerminalState(state) {
  return state.terminal || { activeTerminalId: "", terminalIds: [], sessions: {} };
}

function readProtocolMethod(deps, name) {
  const candidate = deps.protocol && deps.protocol[name];
  return typeof candidate === "function" ? candidate.bind(deps.protocol) : null;
}

function terminalCapabilityEnabledForDeps(deps) {
  const capabilities = typeof deps.getAppCapabilities === "function"
    ? deps.getAppCapabilities()
    : deps.appCapabilities;
  return terminalCapabilityEnabled(capabilities);
}

function terminalChromeText(deps, key) {
  const chrome = typeof deps.getTerminalChrome === "function"
    ? deps.getTerminalChrome()
    : deps.terminalChrome;
  return String(chrome?.[key] || "");
}

function normalizeTerminalId(value) {
  return String(value || "").trim();
}

function activeContribution(state) {
  const contribution = state.contribution || {};
  return (contribution.items || []).find((item) => item.id === contribution.activeId) || null;
}

function knownTerminalIds(state) {
  const terminal = readTerminalState(state);
  const contributionIds = (state.contribution?.items || [])
    .filter((item) => item.kind === "terminal")
    .flatMap((item) => item.terminalIds || []);
  return Array.from(new Set([...(terminal.terminalIds || []), ...contributionIds].filter(Boolean)));
}

function nextId(deps, state) {
  const createId = typeof deps.nextTerminalId === "function"
    ? deps.nextTerminalId
    : defaultNextTerminalId;
  return normalizeTerminalId(createId(knownTerminalIds(state)));
}

function errorNotice(error, fallback) {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function createTerminalController(deps = {}) {
  const dispatch = typeof deps.dispatch === "function" ? deps.dispatch : noop;
  const getState = () => readState(deps.getState);
  const contributions = deps.contributionController || {};

  function notice(message) {
    if (message) dispatch({ type: "interaction_notice_set", notice: message });
  }

  function requireSession() {
    const state = getState();
    const sessionId = readActiveThreadId(state);
    if (!sessionId) {
      notice(terminalChromeText(deps, "sessionRequiredNotice"));
      return null;
    }
    return { sessionId, state };
  }

  async function openSession(preferredId = "") {
    if (!terminalCapabilityEnabledForDeps(deps)) return null;
    const context = requireSession();
    if (!context) return null;
    const terminalId = normalizeTerminalId(preferredId) || nextId(deps, context.state);
    const openTerminal = readProtocolMethod(deps, "openTerminal");
    if (!openTerminal || !terminalId) return null;
    try {
      const payload = await openTerminal(context.sessionId, terminalId, TERMINAL_DIMENSIONS);
      dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      dispatch({ type: "terminal_active_set", terminalId });
      return terminalId;
    } catch (error) {
      notice(errorNotice(error, terminalChromeText(deps, "openFailedNotice")));
      return null;
    }
  }

  async function openContribution(preferredId = "") {
    const terminalId = await openSession(preferredId);
    if (!terminalId || typeof contributions.openSurface !== "function") return null;
    const opened = contributions.openSurface("terminal", "", {
      resourceId: terminalId,
      terminalId,
      terminalIds: [terminalId],
      activeTerminalId: terminalId,
    });
    return opened ? terminalId : null;
  }

  async function refresh() {
    if (!terminalCapabilityEnabledForDeps(deps)) return;
    const sessionId = readActiveThreadId(getState());
    const listTerminals = readProtocolMethod(deps, "listTerminals");
    if (!sessionId || !listTerminals) return;
    try {
      const payload = await listTerminals(sessionId);
      dispatch({ type: "terminal_summaries_loaded", terminals: payload.terminals || [] });
    } catch (_) {
      // Refresh is opportunistic; socket events remain authoritative.
    }
  }

  async function write(terminalId, text) {
    if (!terminalCapabilityEnabledForDeps(deps)) return null;
    const sessionId = readActiveThreadId(getState());
    const id = normalizeTerminalId(terminalId);
    const writeTerminal = readProtocolMethod(deps, "writeTerminal");
    if (!sessionId || !id || !writeTerminal) return null;
    try {
      dispatch({ type: "terminal_active_set", terminalId: id });
      await writeTerminal(sessionId, id, text);
      return id;
    } catch (error) {
      notice(errorNotice(error, terminalChromeText(deps, "writeFailedNotice")));
      return null;
    }
  }

  async function runTerminalOperation(methodName, terminalId, fallbackKey) {
    if (!terminalCapabilityEnabledForDeps(deps)) return null;
    const sessionId = readActiveThreadId(getState());
    const id = normalizeTerminalId(terminalId);
    const operation = readProtocolMethod(deps, methodName);
    if (!sessionId || !id || !operation) return null;
    try {
      dispatch({ type: "terminal_active_set", terminalId: id });
      const payload = methodName === "restartTerminal"
        ? await operation(sessionId, id, TERMINAL_DIMENSIONS)
        : await operation(sessionId, id);
      if (payload?.terminal) dispatch({ type: "terminal_snapshot_loaded", snapshot: payload.terminal });
      return id;
    } catch (error) {
      notice(errorNotice(error, terminalChromeText(deps, fallbackKey)));
      return null;
    }
  }

  async function closeContributionTerminal(terminalId) {
    const state = getState();
    const sessionId = readActiveThreadId(state);
    const contribution = activeContribution(state);
    const id = normalizeTerminalId(terminalId);
    const closeTerminal = readProtocolMethod(deps, "closeTerminal");
    if (!sessionId || !contribution || contribution.kind !== "terminal" || !id || !closeTerminal) {
      return null;
    }
    try {
      await closeTerminal(sessionId, id);
      dispatch({ type: "terminal_event", event: { type: "closed", session_id: sessionId, terminal_id: id } });
      dispatch({ type: "contribution_terminal_closed", surfaceId: contribution.id, terminalId: id });
      return id;
    } catch (error) {
      notice(errorNotice(error, terminalChromeText(deps, "closeFailedNotice")));
      return null;
    }
  }

  async function splitContribution(splitDirection = "horizontal") {
    const contribution = activeContribution(getState());
    if (!contribution || contribution.kind !== "terminal") return null;
    const terminalId = await openSession();
    if (!terminalId) return null;
    dispatch({
      type: "contribution_terminal_split",
      surfaceId: contribution.id,
      terminalId,
      splitDirection,
    });
    return terminalId;
  }

  function activateContributionTerminal(terminalId) {
    const contribution = activeContribution(getState());
    const id = normalizeTerminalId(terminalId);
    if (!contribution || contribution.kind !== "terminal" || !id) return null;
    dispatch({ type: "contribution_terminal_activated", surfaceId: contribution.id, terminalId: id });
    dispatch({ type: "terminal_active_set", terminalId: id });
    return id;
  }

  return {
    activateContributionTerminal,
    clearActive: () => runTerminalOperation("clearTerminal", readTerminalState(getState()).activeTerminalId, "clearFailedNotice"),
    clearById: (id) => runTerminalOperation("clearTerminal", id, "clearFailedNotice"),
    closeActive: () => closeContributionTerminal(readTerminalState(getState()).activeTerminalId),
    closeContributionTerminal,
    openContribution,
    openSession,
    refresh,
    restartActive: () => runTerminalOperation("restartTerminal", readTerminalState(getState()).activeTerminalId, "restartFailedNotice"),
    restartById: (id) => runTerminalOperation("restartTerminal", id, "restartFailedNotice"),
    sendActive: (text) => write(readTerminalState(getState()).activeTerminalId, text),
    sendTo: write,
    splitContribution,
    splitContributionVertical: () => splitContribution("vertical"),
  };
}
