export function createComposerState() {
  return {
    draftsByKey: {},
    activeDraftKey: null,
  };
}

export function draftKeyForSession(sessionId) {
  const value = String(sessionId || "").trim();
  return value ? `session:${value}` : "draft:new";
}

function draftKeyFromAction(action = {}, current = {}) {
  if (action.draftKey) return String(action.draftKey);
  if (action.sessionId) return draftKeyForSession(action.sessionId);
  if (current.activeDraftKey) return current.activeDraftKey;
  return draftKeyForSession("");
}

function readDraftEntry(composer = {}, key = "") {
  const entry = composer.draftsByKey?.[key];
  return entry && typeof entry === "object" ? entry : { draft: "" };
}

export function readComposerDraft(state = {}) {
  if (state.composer && typeof state.composer === "object") {
    const key = state.thread?.currentSessionId
      ? draftKeyForSession(state.thread.currentSessionId)
      : state.composer.activeDraftKey;
    return String(readDraftEntry(state.composer, key).draft || "");
  }
  return "";
}

export function reduceComposerState(state, action = {}) {
  const current = state && typeof state === "object" ? state : createComposerState();
  const draftKey = draftKeyFromAction(action, current);
  switch (action.type) {
    case "set_composer":
      return {
        ...current,
        activeDraftKey: draftKey,
        draftsByKey: {
          ...current.draftsByKey,
          [draftKey]: { draft: String(action.value || "") },
        },
      };
    case "local_user_message":
      return {
        ...current,
        activeDraftKey: draftKey,
        draftsByKey: {
          ...current.draftsByKey,
          [draftKey]: { draft: "" },
        },
      };
    case "workspace_scoped_state_reset":
      return createComposerState();
    default:
      return current;
  }
}
