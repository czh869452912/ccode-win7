import { injectChildren } from "../../state-helpers.js";
import { focusDiffFile } from "../../session-runtime/diff-model.js";
import { createComposerState, reduceComposerState } from "../../composer/composer-state.js";
import { createRunOutputState, reduceRunOutputState } from "../../session-runtime/run-output-state.js";
import {
  createThreadState,
  readActiveThreadId,
  reduceThreadState,
} from "../../session-runtime/thread-state.js";
import { emptyProtocolCapabilities } from "../../session-runtime/protocol-normalizer.js";
import {
  ACTIVITY_ACTION_TYPES,
  createActivityState,
  reduceActivityState,
} from "../../session-runtime/activity-reducer.js";

export const INITIAL_REQUESTED_MODE = "";
export const EMPTY_CAPABILITIES = emptyProtocolCapabilities();

const SESSION_ACTIONS = new Set([
  "set_composer", "sessions_loaded", "session_capabilities_loaded", "session_activated",
  "session_snapshot", "file_preview_load_started", "file_preview_loaded",
  "file_preview_load_failed", "diff_surface_opened", "diff_file_focused", "plan_loaded",
  "interaction_notice_set", "interaction_notice_clear", "file_tree_loaded",
  "file_children_loaded", "mode_requested", "log_event",
]);

export function createSessionState() {
  return {
    thread: createThreadState(),
    snapshot: null,
    composer: createComposerState(),
    ...createActivityState(),
    interactionNotice: null,
    plan: null,
    filePreviewsByPath: {},
    diffSurface: null,
    fileTree: [],
    sessionCapabilities: EMPTY_CAPABILITIES,
    requestedMode: INITIAL_REQUESTED_MODE,
    runOutput: createRunOutputState(),
  };
}

function previewRecord(status, path, preview = {}, error = "") {
  return {
    status,
    path,
    title: String(preview.title || path),
    content: status === "loaded" ? String(preview.content || "") : "",
    error: String(error || ""),
  };
}

export function reduceSessionState(state = createSessionState(), action = {}) {
  if (ACTIVITY_ACTION_TYPES.has(action.type)) {
    const next = { ...state, ...reduceActivityState(state, action) };
    if (action.type !== "local_user_message") return next;
    return {
      ...next,
      composer: reduceComposerState(state.composer, {
        ...action,
        sessionId: action.sessionId || readActiveThreadId(state),
      }),
      interactionNotice: null,
    };
  }
  switch (action.type) {
    case "set_composer":
      return {
        ...state,
        composer: reduceComposerState(state.composer, {
          ...action,
          sessionId: action.sessionId || readActiveThreadId(state),
        }),
      };
    case "sessions_loaded":
      return { ...state, thread: reduceThreadState(state.thread, action) };
    case "session_capabilities_loaded":
      return { ...state, sessionCapabilities: action.capabilities || EMPTY_CAPABILITIES };
    case "session_activated":
      return {
        ...state,
        thread: reduceThreadState(state.thread, action),
        snapshot: action.snapshot,
        sessionCapabilities: action.capabilities || EMPTY_CAPABILITIES,
        requestedMode: action.snapshot?.current_mode || state.requestedMode,
        ...reduceActivityState(state, { type: "activity_reset", activities: action.activities }),
        interactionNotice: null,
        runOutput: reduceRunOutputState(state.runOutput, action),
        plan: null,
      };
    case "session_snapshot": {
      const snapshot = action.snapshot;
      if (!snapshot) return state;
      return {
        ...state,
        thread: reduceThreadState(state.thread, action),
        snapshot,
        requestedMode: snapshot.current_mode || state.requestedMode,
        interactionNotice: snapshot.pending_interaction_valid && snapshot.pending_interaction
          ? null
          : state.interactionNotice,
      };
    }
    case "file_preview_load_started":
    case "file_preview_loaded":
    case "file_preview_load_failed": {
      const path = String(action.path || "");
      if (!path) return state;
      const record = action.type === "file_preview_loaded"
        ? previewRecord("loaded", path, action.preview)
        : action.type === "file_preview_load_failed"
          ? previewRecord("error", path, {}, action.error)
          : previewRecord("loading", path);
      return { ...state, filePreviewsByPath: { ...state.filePreviewsByPath, [path]: record } };
    }
    case "diff_surface_opened":
      return { ...state, diffSurface: action.diffSurface || null };
    case "diff_file_focused":
      return { ...state, diffSurface: focusDiffFile(state.diffSurface, action.filePath || "") };
    case "plan_loaded":
      return { ...state, plan: action.plan };
    case "interaction_notice_set":
      return { ...state, interactionNotice: action.notice || null };
    case "interaction_notice_clear":
      return { ...state, interactionNotice: null };
    case "file_tree_loaded":
      return { ...state, fileTree: action.nodes };
    case "file_children_loaded":
      return { ...state, fileTree: injectChildren(state.fileTree, action.path, action.children) };
    case "mode_requested":
      return { ...state, requestedMode: action.mode };
    case "log_event":
      return { ...state, runOutput: reduceRunOutputState(state.runOutput, action) };
    default:
      return state;
  }
}

export function isSessionAction(action = {}) {
  return ACTIVITY_ACTION_TYPES.has(action.type) || SESSION_ACTIONS.has(action.type);
}
