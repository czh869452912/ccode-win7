import {
  createSourceControlState,
  reduceSourceControlState,
} from "../../source-control/source-control-state.js";
import { createTerminalState, reduceTerminalState } from "../../terminal/terminal-state.js";

const TERMINAL_ACTIONS = new Set([
  "terminal_snapshot_loaded",
  "terminal_summaries_loaded",
  "terminal_event",
  "terminal_active_set",
]);

const SOURCE_CONTROL_ACTIONS = new Set([
  "source_control_reset",
  "source_control_load_started",
  "source_control_load_failed",
  "source_control_status_loaded",
  "source_control_file_selected",
  "source_control_diff_started",
  "source_control_diff_failed",
  "source_control_diff_loaded",
]);

export function createTransportState() {
  return {
    sourceControl: createSourceControlState(),
    terminal: createTerminalState(),
  };
}

export function reduceTransportState(state = createTransportState(), action = {}) {
  if (TERMINAL_ACTIONS.has(action.type)) {
    return { ...state, terminal: reduceTerminalState(state.terminal, action) };
  }
  if (SOURCE_CONTROL_ACTIONS.has(action.type)) {
    return { ...state, sourceControl: reduceSourceControlState(state.sourceControl, action) };
  }
  return state;
}

export function isTransportAction(action = {}) {
  return TERMINAL_ACTIONS.has(action.type) || SOURCE_CONTROL_ACTIONS.has(action.type);
}
