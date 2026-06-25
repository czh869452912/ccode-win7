export function createComposerState() {
  return {
    draft: "",
  };
}

export function readComposerDraft(state = {}) {
  if (state.composer && typeof state.composer === "object") {
    return String(state.composer.draft || "");
  }
  return "";
}

export function reduceComposerState(state, action = {}) {
  const current = state && typeof state === "object" ? state : createComposerState();
  switch (action.type) {
    case "set_composer":
      return { ...current, draft: String(action.value || "") };
    case "local_user_message":
    case "workspace_scoped_state_reset":
      return createComposerState();
    default:
      return current;
  }
}
