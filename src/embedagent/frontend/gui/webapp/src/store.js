import { injectChildren, makeEventId, resolveTimelineAnchor } from "./state-helpers.js";

export const initialState = {
  sidebarTab: "chats",
  inspectorTab: "todos",
  inspectorOpen: true,
  lang: "en",
  sessions: [],
  currentSessionId: "",
  snapshot: null,
  composer: "",
  timeline: [],
  streamingAssistantId: "",
  streamingReasoningId: "",
  thinkingActive: false,
  permission: null,
  userInput: null,
  todos: [],
  artifacts: [],
  plan: null,
  review: null,
  recipes: [],
  permissionContext: null,
  preview: null,
  fileTree: [],
  toolCatalog: {},
  requestedMode: "code",
  connectionState: "connecting",
  eventLog: [],
  terminationReason: "",
  turnsUsed: 0,
  maxTurns: 8,
  activeTurnId: "",
  activeStepId: "",
  activeStepIndex: 0,
};

function liveProjectionMeta() {
  return {
    projectionSource: "step_events",
    projectionKind: "recorded_step",
    synthetic: false,
  };
}

export function reducer(state, action) {
  switch (action.type) {
    case "set_sidebar":
      return { ...state, sidebarTab: action.value };
    case "set_inspector":
      return { ...state, inspectorTab: action.value };
    case "toggle_inspector":
      return { ...state, inspectorOpen: !state.inspectorOpen };
    case "set_lang":
      return { ...state, lang: action.value };
    case "set_composer":
      return { ...state, composer: action.value };
    case "set_connection":
      return { ...state, connectionState: action.value };
    case "sessions_loaded":
      return { ...state, sessions: action.sessions };
    case "session_activated":
      return {
        ...state,
        currentSessionId: action.sessionId,
        snapshot: action.snapshot,
        requestedMode: action.snapshot?.current_mode || state.requestedMode,
        timeline: action.timeline,
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
        permission: null,
        userInput: null,
        terminationReason: "",
        turnsUsed: 0,
        activeTurnId: "",
        activeStepId: "",
        activeStepIndex: 0,
        plan: null,
        review: null,
        permissionContext: null,
      };
    case "session_snapshot": {
      const snapshot = action.snapshot;
      if (!snapshot) return state;
      return {
        ...state,
        currentSessionId: snapshot.session_id || state.currentSessionId,
        snapshot,
        requestedMode: snapshot.current_mode || state.requestedMode,
      };
    }
    case "local_user_message":
      return {
        ...state,
        timeline: state.timeline
          .map((item) => (item.streaming ? { ...item, streaming: false } : item))
          .concat({
            id: makeEventId("user"),
            kind: "user",
            content: action.text,
            turnId: "",
            ...liveProjectionMeta(),
          }),
        composer: "",
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
        terminationReason: "",
      };
    case "turn_started": {
      const turnId = action.turnId || "";
      let linked = false;
      const timeline = state.timeline.map((item) => {
        if (!linked && item.kind === "user" && !item.turnId) {
          linked = true;
          return {
            ...item,
            turnId,
            content: action.userText || item.content,
          };
        }
        return item;
      });
      if (!linked) {
        timeline.push({
          id: makeEventId("user"),
          kind: "user",
          content: action.userText || "",
          turnId,
          ...liveProjectionMeta(),
        });
      }
      return {
        ...state,
        timeline,
        activeTurnId: turnId,
      };
    }
    case "step_started":
      return {
        ...state,
        activeTurnId: action.turnId || state.activeTurnId,
        activeStepId: action.stepId || "",
        activeStepIndex: action.stepIndex || 0,
        streamingAssistantId: "",
        streamingReasoningId: "",
      };
    case "turn_ended":
      return {
        ...state,
        terminationReason: action.terminationReason || "",
        turnsUsed: action.turnsUsed || 0,
        maxTurns: action.maxTurns || state.maxTurns,
      };
    case "assistant_delta": {
      let timeline = state.timeline.slice();
      const turnId = action.turnId || state.activeTurnId;
      const stepId = action.stepId || state.activeStepId;
      const stepIndex = action.stepIndex || state.activeStepIndex;
      let id = state.streamingAssistantId;
      const existing = id ? timeline.find((item) => item.id === id) : null;
      if (!id || (existing && existing.stepId !== stepId)) {
        id = makeEventId("assistant");
        timeline.push({
          id,
          kind: "assistant",
          content: action.text,
          streaming: true,
          turnId,
          stepId,
          stepIndex,
          ...liveProjectionMeta(),
        });
      } else {
        timeline = timeline.map((item) =>
          item.id === id
            ? { ...item, content: `${item.content || ""}${action.text}`, streaming: true }
            : item,
        );
      }
      return { ...state, timeline, streamingAssistantId: id, thinkingActive: false };
    }
    case "reasoning_delta": {
      let timeline = state.timeline.slice();
      const turnId = action.turnId || state.activeTurnId;
      const stepId = action.stepId || state.activeStepId;
      const stepIndex = action.stepIndex || state.activeStepIndex;
      let id = state.streamingReasoningId;
      const existing = id ? timeline.find((item) => item.id === id) : null;
      if (!id || (existing && existing.stepId !== stepId)) {
        id = makeEventId("thinking");
        timeline.push({
          id,
          kind: "reasoning",
          content: action.text,
          open: false,
          streaming: true,
          turnId,
          stepId,
          stepIndex,
          ...liveProjectionMeta(),
        });
      } else {
        timeline = timeline.map((item) =>
          item.id === id
            ? { ...item, content: `${item.content || ""}${action.text}`, streaming: true }
            : item,
        );
      }
      return { ...state, timeline, streamingReasoningId: id };
    }
    case "thinking_state": {
      const timeline = state.timeline.map((item) => {
        if (item.id === state.streamingReasoningId) {
          return { ...item, streaming: Boolean(action.active) };
        }
        if (item.id === state.streamingAssistantId) {
          return { ...item, streaming: Boolean(action.active) ? item.streaming : false };
        }
        return item;
      });
      return { ...state, thinkingActive: Boolean(action.active), timeline };
    }
    case "tool_started":
      return {
        ...state,
        thinkingActive: false,
        timeline: state.timeline.concat({
          id: action.callId,
          kind: "tool",
          toolName: action.toolName,
          label: action.label || action.toolName,
          arguments: action.arguments,
          status: "running",
          turnId: action.turnId || state.activeTurnId,
          stepId: action.stepId || state.activeStepId,
          stepIndex: action.stepIndex || state.activeStepIndex,
          data: null,
          error: "",
          permissionCategory: action.permissionCategory || "",
          supportsDiffPreview: Boolean(action.supportsDiffPreview),
          progressRendererKey: action.progressRendererKey || "",
          resultRendererKey: action.resultRendererKey || "",
          runtimeSource: action.runtimeSource || "",
          resolvedToolRoots: action.resolvedToolRoots || {},
          ...liveProjectionMeta(),
        }),
      };
    case "tool_finished":
      return {
        ...state,
        timeline: state.timeline.map((item) =>
          item.id === action.callId
            ? {
                ...item,
                status: action.success ? "success" : "error",
                data: action.data,
                error: action.error,
                label: action.label || item.label,
                turnId: action.turnId || item.turnId,
                stepId: action.stepId || item.stepId,
                stepIndex: action.stepIndex || item.stepIndex,
                permissionCategory: action.permissionCategory || item.permissionCategory,
                supportsDiffPreview:
                  action.supportsDiffPreview === undefined
                    ? item.supportsDiffPreview
                    : Boolean(action.supportsDiffPreview),
                progressRendererKey: action.progressRendererKey || item.progressRendererKey,
                resultRendererKey: action.resultRendererKey || item.resultRendererKey,
                runtimeSource: action.runtimeSource || item.runtimeSource || "",
                resolvedToolRoots: action.resolvedToolRoots || item.resolvedToolRoots || {},
              }
            : item,
        ),
      };
    case "step_ended": {
      const turnId = action.turnId || state.activeTurnId;
      const stepId = action.stepId || state.activeStepId;
      const stepIndex = action.stepIndex || state.activeStepIndex;
      let timeline = state.timeline.map((item) => {
        if ((item.id === state.streamingAssistantId || item.id === state.streamingReasoningId) && item.stepId === stepId) {
          return { ...item, streaming: false };
        }
        return item;
      });
      const hasAssistant = timeline.some((item) => item.kind === "assistant" && item.stepId === stepId);
      if (!hasAssistant && action.assistantText) {
        timeline = timeline.concat({
          id: makeEventId("assistant"),
          kind: "assistant",
          content: action.assistantText,
          turnId,
          stepId,
          stepIndex,
          streaming: false,
          ...liveProjectionMeta(),
        });
      }
      return {
        ...state,
        timeline,
        streamingAssistantId: "",
        streamingReasoningId: "",
        activeTurnId: turnId,
        activeStepId: stepId,
        activeStepIndex: stepIndex,
      };
    }
    case "append_timeline_item":
      return { ...state, timeline: state.timeline.concat(action.item) };
    case "permission_request":
      return { ...state, permission: action.permission, thinkingActive: false };
    case "permission_cleared":
      return { ...state, permission: null };
    case "user_input_request": {
      const isModeSwitchProposal = action.request.tool_name === "propose_mode_switch";
      return {
        ...state,
        userInput: action.request,
        thinkingActive: false,
        timeline: state.timeline.concat(
          isModeSwitchProposal
            ? {
                id: makeEventId("mode_switch"),
                kind: "mode_switch_proposal",
                request: action.request,
                answered: false,
                turnId: action.request?.turn_id || state.activeTurnId,
                stepId: action.request?.step_id || state.activeStepId,
                stepIndex: action.request?.step_index || state.activeStepIndex,
                ...liveProjectionMeta(),
              }
            : {
                id: makeEventId("user_input"),
                kind: "user_input",
                request: action.request,
                answered: false,
                turnId: action.request?.turn_id || state.activeTurnId,
                stepId: action.request?.step_id || state.activeStepId,
                stepIndex: action.request?.step_index || state.activeStepIndex,
                ...liveProjectionMeta(),
              },
        ),
      };
    }
    case "user_input_answered":
      return {
        ...state,
        userInput: null,
        timeline: state.timeline.map((item) =>
          (item.kind === "user_input" || item.kind === "mode_switch_proposal") &&
          item.request?.request_id === action.requestId
            ? { ...item, answered: true, answerText: action.answerText }
            : item,
        ),
      };
    case "user_input_cleared":
      return {
        ...state,
        userInput: null,
        timeline: state.timeline.map((item) =>
          (item.kind === "user_input" || item.kind === "mode_switch_proposal") && !item.answered
            ? { ...item, answered: true }
            : item,
        ),
      };
    case "permission_request_inline":
      // Inline permission — we only need to track the ID for potential cleanup; modal stays null
      return state;
    case "permission_item_resolved":
      return {
        ...state,
        timeline: state.timeline.map((item) =>
          item.kind === "permission" && item.id === action.permissionId
            ? { ...item, resolved: true, approved: action.approved }
            : item,
        ),
      };
    case "todos_loaded":
      return { ...state, todos: action.todos };
    case "artifacts_loaded":
      return { ...state, artifacts: action.items };
    case "recipes_loaded":
      return { ...state, recipes: action.items || [] };
    case "preview_loaded":
      return {
        ...state,
        preview: action.preview,
        inspectorTab: action.inspectorTab || state.inspectorTab,
      };
    case "plan_loaded":
      return {
        ...state,
        plan: action.plan,
        inspectorTab: action.inspectorTab || state.inspectorTab,
      };
    case "review_loaded":
      return {
        ...state,
        review: action.review,
        inspectorTab: action.inspectorTab || state.inspectorTab,
      };
    case "permission_context_loaded":
      return {
        ...state,
        permissionContext: action.context,
        inspectorTab: action.inspectorTab || state.inspectorTab,
      };
    case "tool_catalog_loaded":
      return {
        ...state,
        toolCatalog: action.catalog || {},
      };
    case "command_result": {
      const turnId = resolveTimelineAnchor({
        explicitTurnId: action.turnId || "",
        activeTurnId: state.activeTurnId,
        timeline: state.timeline,
      });
      const clearTimeline = Boolean(action.data?.clear_timeline);
      const timeline = clearTimeline
          ? []
          : state.timeline.concat({
              id: action.id || makeEventId("cmd"),
              kind: "command_result",
              commandName: action.commandName,
              content: action.message,
              data: action.data || {},
              success: action.success,
              turnId,
              ...liveProjectionMeta(),
            });
      return {
        ...state,
        timeline,
        thinkingActive: false,
        streamingAssistantId: "",
        streamingReasoningId: "",
        review: action.commandName === "review" ? action.data?.review || state.review : state.review,
      };
    }
    case "file_tree_loaded":
      return { ...state, fileTree: action.nodes };
    case "file_children_loaded":
      return { ...state, fileTree: injectChildren(state.fileTree, action.path, action.children) };
    case "mode_requested":
      return { ...state, requestedMode: action.mode };
    case "stream_completed":
      return {
        ...state,
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
        timeline: state.timeline.map((item) => (item.streaming ? { ...item, streaming: false } : item)),
      };
    case "log_event": {
      const entry = { ts: Date.now(), label: action.label, detail: action.detail || "" };
      const eventLog =
        state.eventLog.length >= 200
          ? [...state.eventLog.slice(-199), entry]
          : [...state.eventLog, entry];
      return { ...state, eventLog };
    }
    default:
      return state;
  }
}

export const TOOL_LABELS = {
  read_file: (a) => `Read  ${a.path || ""}`,
  write_file: (a) => `Write  ${a.path || ""}`,
  create_file: (a) => `Create  ${a.path || ""}`,
  edit_file: (a) => `Edit  ${a.path || ""}`,
  patch_file: (a) => `Patch  ${a.path || ""}`,
  delete_file: (a) => `Delete  ${a.path || ""}`,
  list_files: (a) => `List  ${a.path || "."}`,
  search_files: (a) => `Search "${a.pattern || a.query || ""}"`,
  grep: (a) => `Grep "${a.pattern || ""}"`,
  run_command: (a) => `Shell: ${a.command || ""}`,
  bash: (a) => `Shell: ${a.command || ""}`,
  shell: (a) => `Shell: ${a.command || ""}`,
  execute: (a) => `Run: ${a.command || ""}`,
  git_status: () => "Git status",
  git_diff: (a) => `Git diff${a.path ? `  ${a.path}` : ""}`,
  git_commit: (a) => `Git commit: ${a.message || ""}`,
  git_add: (a) => `Git add ${a.path || "."}`,
  git_log: () => "Git log",
  compile: (a) => `Compile ${a.target || a.file || ""}`,
  build: (a) => `Build ${a.target || ""}`,
  run_tests: (a) => `Run tests${a.target ? `: ${a.target}` : ""}`,
};

export function toolLabel(toolName, args) {
  const fn = TOOL_LABELS[toolName];
  return fn ? fn(args || {}) : toolName;
}

export const STATUS_ICON = { running: "⋯", success: "✓", error: "✗" };
