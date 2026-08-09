function text(value) {
  return String(value || "").trim();
}

function contributionId(action) {
  const explicit = text(action.surfaceId || action.id);
  if (explicit) return explicit;
  const kind = text(action.kind || action.surfaceId);
  const resource = text(action.resourceId || action.filePath || action.terminalId);
  return resource ? `${kind}:${resource}` : kind;
}

function normalizeContribution(action) {
  const kind = text(action.kind || action.surfaceId);
  const id = contributionId(action);
  return {
    id,
    kind,
    label: text(action.label || action.title || kind),
    rendererKey: text(action.rendererKey || action.renderer_key || kind || "descriptor"),
    resourceId: text(action.resourceId),
    filePath: text(action.filePath),
    revealLine: action.revealLine,
    previewSnapshot: action.previewSnapshot || null,
    terminalId: text(action.terminalId),
    terminalIds: Array.isArray(action.terminalIds)
      ? action.terminalIds.map(text).filter(Boolean)
      : [],
    activeTerminalId: text(action.activeTerminalId || action.terminalId),
    splitDirection: text(action.splitDirection || "horizontal"),
  };
}

function activate(items, activeId) {
  return items.some((item) => item.id === activeId) ? activeId : (items[0]?.id || "");
}

export function createContributionState() {
  return {
    sessionId: "",
    items: [],
    activeId: "",
    palette: { open: false, query: "" },
  };
}

export function reduceContributionState(state = createContributionState(), action = {}) {
  switch (action.type) {
    case "contribution_session_activated":
      return { ...createContributionState(), sessionId: text(action.sessionId) };
    case "contribution_opened": {
      const contribution = normalizeContribution(action);
      if (!contribution.id || !contribution.kind) return state;
      const existing = state.items.findIndex((item) => item.id === contribution.id);
      const items = state.items.slice();
      if (existing >= 0) items[existing] = { ...items[existing], ...contribution };
      else items.push(contribution);
      return { ...state, items, activeId: contribution.id };
    }
    case "contribution_activated": {
      const requested = text(action.surfaceId || action.id);
      return { ...state, activeId: activate(state.items, requested) };
    }
    case "contribution_closed": {
      const requested = text(action.surfaceId || action.id);
      const index = state.items.findIndex((item) => item.id === requested);
      if (index < 0) return state;
      const items = state.items.filter((item) => item.id !== requested);
      const fallback = items[Math.min(index, Math.max(0, items.length - 1))]?.id || "";
      return { ...state, items, activeId: state.activeId === requested ? fallback : state.activeId };
    }
    case "contribution_close_others": {
      const requested = text(action.surfaceId || action.id);
      const active = state.items.find((item) => item.id === requested);
      return active ? { ...state, items: [active], activeId: active.id } : state;
    }
    case "contribution_close_after": {
      const requested = text(action.surfaceId || action.id);
      const index = state.items.findIndex((item) => item.id === requested);
      if (index < 0) return state;
      const items = state.items.slice(0, index + 1);
      return { ...state, items, activeId: activate(items, state.activeId) };
    }
    case "contribution_close_all":
      return { ...state, items: [], activeId: "" };
    case "contribution_terminal_split": {
      const requested = text(action.surfaceId || state.activeId);
      const terminalId = text(action.terminalId);
      if (!terminalId) return state;
      const items = state.items.map((item) => item.id === requested
        ? {
            ...item,
            terminalIds: Array.from(new Set([...(item.terminalIds || []), terminalId])),
            activeTerminalId: terminalId,
            splitDirection: text(action.splitDirection || item.splitDirection || "horizontal"),
          }
        : item);
      return { ...state, items };
    }
    case "contribution_terminal_activated": {
      const requested = text(action.surfaceId || state.activeId);
      const terminalId = text(action.terminalId);
      return {
        ...state,
        items: state.items.map((item) => item.id === requested
          ? { ...item, activeTerminalId: terminalId }
          : item),
      };
    }
    case "contribution_terminal_closed": {
      const requested = text(action.surfaceId || state.activeId);
      const terminalId = text(action.terminalId);
      return {
        ...state,
        items: state.items.map((item) => {
          if (item.id !== requested) return item;
          const terminalIds = (item.terminalIds || []).filter((id) => id !== terminalId);
          return {
            ...item,
            terminalIds,
            activeTerminalId: item.activeTerminalId === terminalId
              ? (terminalIds[0] || "")
              : item.activeTerminalId,
          };
        }),
      };
    }
    case "command_palette_opened":
      return { ...state, palette: { ...state.palette, open: true } };
    case "command_palette_closed":
      return { ...state, palette: { open: false, query: "" } };
    case "command_palette_query_changed":
      return { ...state, palette: { ...state.palette, query: String(action.query || "") } };
    default:
      return state;
  }
}
