export { normalizeAppBootstrap, normalizeWorkspaceRecord } from "./app-shell/model.js";
import { createComposerState } from "./composer/composer-state.js";
import { createSourceControlState } from "./source-control/source-control-state.js";
import { reduceRunOutputState } from "./session-runtime/run-output-state.js";
import { createThreadState } from "./session-runtime/thread-state.js";
import { createTerminalState } from "./terminal/terminal-state.js";
import { emptyProtocolCapabilities } from "./session-runtime/protocol-normalizer.js";

const EMPTY_CAPABILITIES = emptyProtocolCapabilities();

export function canSwitchWorkspace(state = {}) {
  const snapshot = state.snapshot || {};
  const status = String(snapshot.status || "");
  if (snapshot.pending_interaction_valid && snapshot.pending_interaction) {
    return { allowed: false, reason: "pending_interaction" };
  }
  if (status === "running" || status === "waiting_permission" || status === "waiting_user_input") {
    return { allowed: false, reason: "active_thread" };
  }
  return { allowed: true, reason: "" };
}

export function resetWorkspaceScopedState(state = {}) {
  return {
    ...state,
    thread: createThreadState(),
    snapshot: null,
    composer: createComposerState(),
    activities: [],
    streamingAssistantId: "",
    streamingReasoningId: "",
    thinkingActive: false,
    interactionNotice: null,
    tasks: [],
    plan: null,
    filePreviewsByPath: {},
    diffSurface: null,
    fileTree: [],
    sessionCapabilities: EMPTY_CAPABILITIES,
    runOutput: reduceRunOutputState(state.runOutput, { type: "workspace_scoped_state_reset" }),
    terminationReason: "",
    terminationDisplayReason: "",
    terminationMessage: "",
    turnsUsed: 0,
    activeTurnId: "",
    activeStepId: "",
    activeStepIndex: 0,
    sourceControl: createSourceControlState(),
    terminal: createTerminalState(),
  };
}
