import { injectChildren, makeEventId, resolveTimelineAnchor } from "./state-helpers.js";
import { focusDiffFile } from "./session-runtime/diff-model.js";
import { createAppShellState } from "./app-shell/model.js";
import { reduceAppShellState } from "./app-shell/reducer.js";
import { createSourceControlState, reduceSourceControlState } from "./source-control/source-control-state.js";
import { createTerminalState, reduceTerminalState } from "./terminal/terminal-state.js";
import { createWorkbenchState, reduceWorkbenchState } from "./workbench/surfaces.js";
import { resetWorkspaceScopedState } from "./app-workspaces.js";

export const DEFAULT_MODE = "explore";

export const initialState = {
  sidebarTab: "chats",
  inspectorTab: "tasks",
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
  interactionNotice: null,
  tasks: [],
  artifacts: [],
  plan: null,
  review: null,
  recipes: [],
  permissionContext: null,
  preview: null,
  filePreviewsByPath: {},
  diffSurface: null,
  fileTree: [],
  toolCatalog: {},
  requestedMode: DEFAULT_MODE,
  connectionState: "connecting",
  eventLog: [],
  terminationReason: "",
  terminationDisplayReason: "",
  terminationMessage: "",
  turnsUsed: 0,
  maxTurns: 8,
  activeTurnId: "",
  activeStepId: "",
  activeStepIndex: 0,
  historyIntegrity: null,
  workbench: createWorkbenchState(),
  app: createAppShellState(),
  sourceControl: createSourceControlState(),
  terminal: createTerminalState(),
};

function liveProjectionMeta() {
  return {
    projectionSource: "step_events",
    projectionKind: "recorded_step",
    synthetic: false,
  };
}

function rawProjectionMeta() {
  return {
    projectionSource: "raw_events",
    projectionKind: "raw_event",
    synthetic: false,
  };
}

function upsertTimelineItem(timeline, nextItem, match) {
  const index = timeline.findIndex(match);
  if (index < 0) {
    return timeline.concat(nextItem);
  }
  return timeline.map((item, currentIndex) =>
    currentIndex === index ? { ...item, ...nextItem } : item,
  );
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
    case "app_bootstrap_loaded":
      return {
        ...state,
        app: reduceAppShellState(state.app, {
          type: "app_shell_bootstrap_loaded",
          bootstrap: action.bootstrap || {},
        }),
      };
    case "workspace_path_changed":
      return {
        ...state,
        app: reduceAppShellState(state.app, {
          type: "app_shell_workspace_path_changed",
          value: action.value,
        }),
      };
    case "workspace_activation_started":
      return {
        ...state,
        app: reduceAppShellState(state.app, {
          type: "app_shell_workspace_activation_started",
        }),
      };
    case "workspace_activation_failed":
      return {
        ...state,
        app: reduceAppShellState(state.app, {
          type: "app_shell_workspace_activation_failed",
          error: action.error,
        }),
      };
    case "workspace_switched": {
      const reset = resetWorkspaceScopedState(state);
      return {
        ...reset,
        app: reduceAppShellState(reset.app, {
          type: "app_shell_workspace_switched",
          bootstrap: action.bootstrap || {},
        }),
      };
    }
    case "app_shell_bootstrap_loaded":
    case "app_shell_workspace_path_changed":
    case "app_shell_workspace_activation_started":
    case "app_shell_workspace_activation_failed":
    case "app_shell_workspace_switched":
    case "app_shell_settings_changed":
      return {
        ...state,
        app: reduceAppShellState(state.app, action),
      };
    case "terminal_snapshot_loaded":
    case "terminal_summaries_loaded":
    case "terminal_event":
    case "terminal_active_set":
      return {
        ...state,
        terminal: reduceTerminalState(state.terminal, action),
      };
    case "source_control_reset":
    case "source_control_load_started":
    case "source_control_load_failed":
    case "source_control_status_loaded":
    case "source_control_file_selected":
    case "source_control_diff_started":
    case "source_control_diff_failed":
    case "source_control_diff_loaded":
      return {
        ...state,
        sourceControl: reduceSourceControlState(state.sourceControl, action),
      };
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
        permission: action.snapshot?.has_pending_permission ? action.snapshot?.pending_permission || null : null,
        userInput:
          action.snapshot?.pending_interaction_valid && action.snapshot?.pending_interaction?.kind === "user_input"
            ? action.snapshot?.pending_user_input || action.snapshot?.pending_interaction || null
            : null,
        interactionNotice: null,
        terminationReason: "",
        terminationDisplayReason: "",
        terminationMessage: "",
        turnsUsed: 0,
        activeTurnId: "",
        activeStepId: "",
        activeStepIndex: 0,
        eventLog: [],
        historyIntegrity: action.historyIntegrity || null,
        plan: null,
        review: null,
        permissionContext: null,
        tasks: Array.isArray(action.snapshot?.task_items) ? action.snapshot.task_items : [],
        inspectorTab:
          action.snapshot?.pending_interaction_valid && action.snapshot?.pending_interaction
            ? "interaction"
            : state.inspectorTab,
        inspectorOpen:
          action.snapshot?.pending_interaction_valid && action.snapshot?.pending_interaction
            ? true
            : state.inspectorOpen,
      };
    case "session_snapshot": {
      const snapshot = action.snapshot;
      if (!snapshot) return state;
      const hadActiveInteraction = Boolean(
        state.snapshot?.pending_interaction_valid && state.snapshot?.pending_interaction,
      );
      const hasActiveInteraction = Boolean(
        snapshot.pending_interaction_valid && snapshot.pending_interaction,
      );
      let historyIntegrity = state.historyIntegrity;
      if (
        historyIntegrity &&
        historyIntegrity.status === "partial" &&
        !snapshot.restore_stop_reason
      ) {
        historyIntegrity = {
          ...historyIntegrity,
          status: "healthy",
          restore_stop_reason: "",
        };
      }
      return {
        ...state,
        currentSessionId: snapshot.session_id || state.currentSessionId,
        snapshot,
        requestedMode: snapshot.current_mode || state.requestedMode,
        permission: snapshot.has_pending_permission ? snapshot.pending_permission || state.permission : null,
        userInput:
          snapshot.pending_interaction_valid && snapshot.pending_interaction?.kind === "user_input"
            ? snapshot.pending_user_input || snapshot.pending_interaction || state.userInput
            : null,
        tasks: Array.isArray(snapshot.task_items) ? snapshot.task_items : state.tasks,
        interactionNotice:
          snapshot.pending_interaction_valid && snapshot.pending_interaction
            ? null
            : state.interactionNotice,
        inspectorTab:
          !hadActiveInteraction && hasActiveInteraction
            ? "interaction"
            : state.inspectorTab,
        inspectorOpen:
          !hadActiveInteraction && hasActiveInteraction
            ? true
            : state.inspectorOpen,
        historyIntegrity,
      };
    }
    case "local_user_message":
      const pendingTurnId = makeEventId("user");
      return {
        ...state,
        timeline: state.timeline
          .map((item) => (item.streaming ? { ...item, streaming: false } : item))
          .concat({
            id: pendingTurnId,
          kind: "user",
          content: action.text,
          turnId: "",
          pendingTurnId,
          createdAt: new Date().toISOString(),
          ...liveProjectionMeta(),
        }),
        composer: "",
        interactionNotice: null,
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
        terminationReason: "",
        activeTurnId: pendingTurnId,
      };
    case "turn_started": {
      const turnId = action.turnId || "";
      let linked = false;
      let linkedAnchor = "";
      const timeline = state.timeline.map((item) => {
        if (!linked && item.kind === "user" && !item.turnId) {
          linked = true;
          linkedAnchor = item.pendingTurnId || item.id || "";
          return {
            ...item,
            turnId,
            pendingTurnId: "",
            content: action.userText || item.content,
            createdAt: item.createdAt || action.createdAt || "",
          };
        }
        return item;
      });
      const reboundTimeline = linkedAnchor
        ? timeline.map((item) =>
            item.turnId === linkedAnchor
              ? { ...item, turnId }
              : item,
          )
        : timeline;
      if (!linked) {
        reboundTimeline.push({
          id: makeEventId("user"),
          kind: "user",
          content: action.userText || "",
          turnId,
          createdAt: action.createdAt || "",
          ...liveProjectionMeta(),
        });
      }
      return {
        ...state,
        timeline: reboundTimeline,
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
        terminationDisplayReason: action.terminationDisplayReason || action.terminationReason || "",
        terminationMessage: action.terminationMessage || "",
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
          createdAt: action.createdAt || "",
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
          createdAt: action.createdAt || "",
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
        timeline: upsertTimelineItem(
          state.timeline,
          {
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
            completedAt: action.completedAt || "",
            ...liveProjectionMeta(),
          },
          (item) => item.kind === "tool" && item.id === action.callId,
        ),
      };
    case "tool_finished":
      return {
        ...state,
        timeline: upsertTimelineItem(
          state.timeline,
          {
            id: action.callId,
            kind: "tool",
            toolName: action.toolName,
            label: action.label || action.toolName,
            arguments: action.arguments || {},
            status: action.success ? "success" : "error",
            data: action.data,
            error: action.error,
            turnId: action.turnId || state.activeTurnId,
            stepId: action.stepId || state.activeStepId,
            stepIndex: action.stepIndex || state.activeStepIndex,
            permissionCategory: action.permissionCategory || "",
            supportsDiffPreview: Boolean(action.supportsDiffPreview),
            progressRendererKey: action.progressRendererKey || "",
            resultRendererKey: action.resultRendererKey || "",
            runtimeSource: action.runtimeSource || "",
            resolvedToolRoots: action.resolvedToolRoots || {},
            createdAt: action.createdAt || "",
            ...liveProjectionMeta(),
          },
          (item) => item.kind === "tool" && item.id === action.callId,
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
          createdAt: action.createdAt || "",
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
    case "visual_timeline_fixture_loaded":
      return {
        ...state,
        currentSessionId: action.sessionId || "visual-debug-session",
        snapshot: action.snapshot || {
          session_id: action.sessionId || "visual-debug-session",
          status: "idle",
          current_mode: state.requestedMode || DEFAULT_MODE,
          pending_interaction_valid: false,
        },
        timeline: Array.isArray(action.timeline) ? action.timeline : [],
        streamingAssistantId: action.streamingAssistantId || "",
        streamingReasoningId: action.streamingReasoningId || "",
        thinkingActive: Boolean(action.thinkingActive),
        permission: null,
        userInput: null,
        interactionNotice: null,
        inspectorTab: action.inspectorTab || state.inspectorTab,
        inspectorOpen: true,
        activeTurnId: action.activeTurnId || "",
        activeStepId: action.activeStepId || "",
        activeStepIndex: action.activeStepIndex || 0,
        historyIntegrity: null,
        app: {
          ...state.app,
          bootstrapLoaded: true,
          hasActiveWorkspace: true,
          activeWorkspace: state.app.activeWorkspace || {
            id: "visual-debug-workspace",
            path: "D:/visual-debug",
            label: "visual-debug",
            exists: true,
            created_at: "",
            last_opened_at: "",
          },
          workspaceError: "",
          activatingWorkspace: false,
        },
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_surface_activated",
          placement: "right",
          kind: action.inspectorTab || state.inspectorTab,
        }),
      };
    case "visual_interaction_fixture_loaded": {
      const pendingInteraction = action.permission || action.userInput || null;
      return {
        ...state,
        currentSessionId: action.sessionId || "visual-debug-session",
        snapshot: {
          ...(state.snapshot || {}),
          session_id: action.sessionId || "visual-debug-session",
          status: pendingInteraction?.kind === "user_input" ? "waiting_user_input" : "waiting_permission",
          current_mode: state.snapshot?.current_mode || state.requestedMode || DEFAULT_MODE,
          pending_interaction_valid: Boolean(pendingInteraction),
          pending_interaction: pendingInteraction,
          pending_permission: action.permission || null,
          pending_user_input: action.userInput || null,
          has_pending_permission: Boolean(action.permission),
        },
        permission: action.permission || null,
        userInput: action.userInput || null,
        interactionNotice: null,
        inspectorTab: "interaction",
        inspectorOpen: true,
        app: {
          ...state.app,
          bootstrapLoaded: true,
          hasActiveWorkspace: true,
          activeWorkspace: state.app.activeWorkspace || {
            id: "visual-debug-workspace",
            path: "D:/visual-debug",
            label: "visual-debug",
            exists: true,
            created_at: "",
            last_opened_at: "",
          },
          workspaceError: "",
          activatingWorkspace: false,
        },
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_surface_activated",
          placement: "right",
          kind: "interaction",
        }),
      };
    }
    case "visual_thread_lifecycle_fixture_loaded": {
      const sessionId = action.sessionId || "visual-thread-active";
      return {
        ...state,
        sidebarTab: "chats",
        currentSessionId: sessionId,
        sessions: Array.isArray(action.sessions) ? action.sessions : [],
        snapshot: {
          ...(state.snapshot || {}),
          session_id: sessionId,
          status: "idle",
          current_mode: state.snapshot?.current_mode || state.requestedMode || DEFAULT_MODE,
          pending_interaction_valid: false,
        },
        permission: null,
        userInput: null,
        interactionNotice: null,
        app: {
          ...state.app,
          bootstrapLoaded: true,
          hasActiveWorkspace: true,
          activeWorkspace: state.app.activeWorkspace || {
            id: "visual-debug-workspace",
            path: "D:/visual-debug",
            label: "visual-debug",
            exists: true,
            created_at: "",
            last_opened_at: "",
          },
          workspaceError: "",
          activatingWorkspace: false,
        },
      };
    }
    case "permission_request":
      return {
        ...state,
        permission: action.permission,
        interactionNotice: null,
        thinkingActive: false,
        inspectorTab: action.inspectorTab || "interaction",
        inspectorOpen: true,
      };
    case "permission_cleared":
      return { ...state, permission: null };
    case "user_input_request": {
      const isModeSwitchProposal = action.request.tool_name === "propose_mode_switch";
      return {
        ...state,
        userInput: action.request,
        interactionNotice: null,
        thinkingActive: false,
        inspectorTab: "interaction",
        inspectorOpen: true,
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
    case "tasks_loaded":
      return { ...state, tasks: action.tasks };
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
    case "file_preview_load_started": {
      const path = String(action.path || "");
      if (!path) return state;
      return {
        ...state,
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          [path]: {
            status: "loading",
            path,
            title: path,
            content: "",
            error: "",
          },
        },
      };
    }
    case "file_preview_loaded": {
      const path = String(action.path || "");
      if (!path) return state;
      const preview = action.preview || {};
      return {
        ...state,
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          [path]: {
            status: "loaded",
            path,
            title: String(preview.title || path),
            content: String(preview.content || ""),
            error: "",
          },
        },
      };
    }
    case "file_preview_load_failed": {
      const path = String(action.path || "");
      if (!path) return state;
      return {
        ...state,
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          [path]: {
            status: "error",
            path,
            title: path,
            content: "",
            error: String(action.error || "File unavailable"),
          },
        },
      };
    }
    case "diff_surface_opened":
      return {
        ...state,
        diffSurface: action.diffSurface || null,
        inspectorTab: "diff",
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_surface_opened",
          placement: "right",
          kind: "diff",
          title: action.diffSurface?.title || "Diff",
          resourceId: "current",
        }),
      };
    case "diff_file_focused":
      return {
        ...state,
        diffSurface: focusDiffFile(state.diffSurface, action.filePath || ""),
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
    case "interaction_notice_set":
      return {
        ...state,
        interactionNotice: action.notice || null,
        inspectorTab: "interaction",
        inspectorOpen: true,
      };
    case "interaction_notice_clear":
      return {
        ...state,
        interactionNotice: null,
      };
    case "session_error":
      return {
        ...state,
        timeline: state.timeline.concat({
          id: action.id || makeEventId("error"),
          kind: "system",
          tone: "error",
          content: action.error || "会话出错",
          turnId: resolveTimelineAnchor({
            explicitTurnId: action.turnId || "",
            activeTurnId: state.activeTurnId,
            timeline: state.timeline,
          }),
          stepId: action.stepId || "",
          stepIndex: action.stepIndex || 0,
          ...rawProjectionMeta(),
        }),
        thinkingActive: false,
        streamingAssistantId: "",
        streamingReasoningId: "",
      };
    case "context_compacted": {
      return {
        ...state,
        timeline: state.timeline.concat({
          id: action.id || makeEventId("context"),
          kind: "compact",
          content: action.content || "",
          recentTurns: action.recentTurns,
          summarizedTurns: action.summarizedTurns,
          approxTokensAfter: action.approxTokensAfter,
          turnId: resolveTimelineAnchor({
            explicitTurnId: action.turnId || "",
            activeTurnId: state.activeTurnId,
            timeline: state.timeline,
          }),
          stepId: action.stepId || "",
          stepIndex: action.stepIndex || 0,
          ...rawProjectionMeta(),
        }),
      };
    }
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
          stepId: action.stepId || "",
          stepIndex: action.stepIndex || 0,
          createdAt: action.createdAt || "",
          ...rawProjectionMeta(),
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
    case "workbench_surface_opened":
    case "workbench_surface_activated":
    case "workbench_surface_closed":
    case "workbench_surface_close_others":
    case "workbench_surface_close_to_right":
    case "workbench_surface_close_all":
    case "workbench_terminal_surface_split":
    case "workbench_terminal_surface_terminal_activated":
    case "workbench_terminal_surface_terminal_closed":
    case "workbench_command_palette_opened":
    case "workbench_command_palette_closed":
    case "workbench_command_palette_query_changed":
    case "workbench_right_panel_toggled":
    case "workbench_bottom_drawer_toggled":
      return { ...state, workbench: reduceWorkbenchState(state.workbench, action) };
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
  list_dir: (a) => `List  ${a.path || "."}`,
  glob_files: (a) => `Glob "${a.pattern || ""}"`,
  grep_text: (a) => `Grep "${a.pattern || ""}"`,
  list_recipes: () => "List recipes",
  run_recipe: (a) => `Run recipe${a.recipe_id ? `: ${a.recipe_id}` : ""}`,
  report_quality_v2: () => "Quality report",
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
};

export function toolLabel(toolName, args) {
  const fn = TOOL_LABELS[toolName];
  return fn ? fn(args || {}) : toolName;
}

export const STATUS_ICON = { running: "⋯", success: "✓", error: "✗" };
