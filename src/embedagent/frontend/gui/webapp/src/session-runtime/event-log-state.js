export function createEventLogState() {
  return [];
}

export function readEventLogEntries(state = {}) {
  return Array.isArray(state.eventLog) ? state.eventLog : createEventLogState();
}

export function reduceEventLogState(state, action = {}) {
  const current = Array.isArray(state) ? state : createEventLogState();
  switch (action.type) {
    case "session_activated":
    case "workspace_scoped_state_reset":
      return createEventLogState();
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
