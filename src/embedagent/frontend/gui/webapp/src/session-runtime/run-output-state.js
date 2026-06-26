export function createRunOutputState() {
  return [];
}

export function readRunOutputEntries(state = {}) {
  return Array.isArray(state.runOutput) ? state.runOutput : createRunOutputState();
}

export function reduceRunOutputState(state, action = {}) {
  const current = Array.isArray(state) ? state : createRunOutputState();
  switch (action.type) {
    case "session_activated":
    case "workspace_scoped_state_reset":
      return createRunOutputState();
    case "log_event": {
      const entry = {
        ts: action.timestamp || Date.now(),
        label: action.label,
        detail: action.detail || "",
      };
      if (current.length >= 200) {
        return [...current.slice(-199), entry];
      }
      return [...current, entry];
    }
    default:
      return current;
  }
}
