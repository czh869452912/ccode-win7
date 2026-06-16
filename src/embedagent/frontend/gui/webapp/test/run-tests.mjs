import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { initialState, reducer } from "../src/store.js";
import {
  createTreeNode,
  injectChildren,
  normalizeSessionPayload,
  resolveTimelineAnchor,
  resolveVisiblePermission,
  timelineFromEvents,
  timelineFromTurns,
} from "../src/state-helpers.js";
import { runDiffModelTests } from "./diff-model.test.mjs";
import { runInteractionModelTests } from "./interaction-model.test.mjs";
import { runSessionRuntimeTests } from "./session-runtime.test.mjs";
import { runT3TimelineTests } from "./t3-timeline.test.mjs";
import { runTimelineUiStateTests } from "./timeline-ui-state.test.mjs";
import { runVisualLanguageCssTests } from "./visual-language-css.test.mjs";
import { runVisualDebugRunnerTests } from "./visual-debug-runner.test.mjs";
import { runWebSocketLifecycleTests } from "./websocket-lifecycle.test.mjs";
import { runWorkbenchStateTests } from "./workbench-state.test.mjs";
import { runAppWorkspaceTests } from "./app-workspaces.test.mjs";
import { runAppHomeModelTests } from "./app-home-model.test.mjs";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function webappSourcePath(...parts) {
  return path.join(WEBAPP_ROOT, "src", ...parts);
}

async function main() {
  assert.equal(initialState.requestedMode, "explore");
  assert.equal(initialState.app.bootstrapLoaded, false);
  assert.equal(initialState.app.hasActiveWorkspace, false);
  assert.equal(initialState.app.activeWorkspace, null);

  const appLoadedState = reducer(initialState, {
    type: "app_bootstrap_loaded",
    bootstrap: {
      workspaces: [
        {
          id: "ws-1",
          path: "D:/work/demo",
          label: "demo",
          exists: true,
          created_at: "",
          last_opened_at: "",
        },
      ],
      activeWorkspace: {
        id: "ws-1",
        path: "D:/work/demo",
        label: "demo",
        exists: true,
        created_at: "",
        last_opened_at: "",
      },
      hasActiveWorkspace: true,
      lastError: "",
    },
  });
  assert.equal(appLoadedState.app.bootstrapLoaded, true);
  assert.equal(appLoadedState.app.activeWorkspace.id, "ws-1");
  assert.equal(appLoadedState.app.hasActiveWorkspace, true);

  const switchedWorkspaceState = reducer(
    {
      ...appLoadedState,
      currentSessionId: "sess-old",
      sessions: [{ session_id: "sess-old" }],
      timeline: [{ id: "row-old" }],
      fileTree: [{ id: "src" }],
    },
    {
      type: "workspace_switched",
      bootstrap: {
        workspaces: [],
        activeWorkspace: null,
        hasActiveWorkspace: false,
        lastError: "",
      },
    },
  );
  assert.equal(switchedWorkspaceState.currentSessionId, "");
  assert.deepEqual(switchedWorkspaceState.sessions, []);
  assert.deepEqual(switchedWorkspaceState.timeline, []);
  assert.deepEqual(switchedWorkspaceState.fileTree, []);
  assert.equal(switchedWorkspaceState.app.hasActiveWorkspace, false);

  const threadLifecycleFixtureState = reducer(initialState, {
    type: "visual_thread_lifecycle_fixture_loaded",
    sessionId: "visual-thread-active",
    sessions: [
      { session_id: "visual-thread-active", user_goal: "Fix parser recovery" },
      { session_id: "visual-thread-followup", user_goal: "Verify parser recovery" },
    ],
  });
  assert.equal(threadLifecycleFixtureState.sidebarTab, "chats");
  assert.equal(threadLifecycleFixtureState.currentSessionId, "visual-thread-active");
  assert.equal(threadLifecycleFixtureState.sessions.length, 2);
  assert.equal(threadLifecycleFixtureState.app.hasActiveWorkspace, true);

  const root = [createTreeNode({ path: "src", name: "src", kind: "dir", has_children: true })];
  const next = injectChildren(root, "src", [
    { path: "src/pkg", name: "pkg", kind: "dir", has_children: true },
    { path: "src/main.c", name: "main.c", kind: "file", has_children: false },
  ]);
  assert.equal(next[0].childrenLoaded, true);
  assert.equal(next[0].children[0].path, "src/pkg");

  const timeline = timelineFromEvents([
    { event_id: "evt-1", event: "turn_started", payload: { text: "hello" } },
    { event_id: "evt-2", event: "tool_started", payload: { call_id: "call-1", tool_name: "read_file", tool_label: "Read File", progress_renderer_key: "file", result_renderer_key: "file", arguments: { path: "README.md" } } },
    { event_id: "evt-3", event: "tool_finished", payload: { call_id: "call-1", tool_name: "read_file", tool_label: "Read File", progress_renderer_key: "file", result_renderer_key: "file", success: true, data: { path: "README.md" } } },
    { event_id: "evt-4", event: "session_finished", payload: { final_text: "done" } },
  ]);
  assert.equal(timeline[1].id, "call-1");
  assert.equal(timeline[1].status, "success");
  assert.equal(timeline[1].label, "Read File");
  assert.equal(timeline[1].resultRendererKey, "file");
  assert.equal(timeline[2].content, "done");

  const reviewTimeline = timelineFromEvents([
    {
      event_id: "evt-review",
      event: "command_result",
      payload: {
        command_name: "review",
        success: true,
        message: "## Review Findings",
        data: {
          review: {
            findings: [{ id: "f1", severity: "high", priority: 1, title: "Build failed", body: "compile failed" }],
          },
        },
      },
    },
  ]);
  assert.equal(reviewTimeline[0].commandName, "review");
  assert.equal(reviewTimeline[0].data.review.findings[0].title, "Build failed");

  const snapshot = normalizeSessionPayload({
    session_id: "sess-1",
    status: "waiting_permission",
    current_mode: "debug",
    has_pending_permission: true,
    last_transition_reason: "aborted",
    last_transition_display_reason: "cancelled",
    last_transition_message: "tool execution interrupted",
    recent_transitions: [
      { reason: "aborted", display_reason: "cancelled", message: "tool execution interrupted" },
    ],
    timeline_replay_status: "degraded",
    timeline_first_seq: 3,
    timeline_last_seq: 9,
    timeline_integrity: "degraded",
    pending_interaction_valid: false,
  });
  assert.equal(snapshot.status, "waiting_permission");
  assert.equal(snapshot.current_mode, "debug");
  assert.equal(snapshot.has_pending_permission, true);
  assert.equal(snapshot.lastTransitionDisplayReason, "cancelled");
  assert.equal(snapshot.recentTransitions[0].displayReason, "cancelled");
  assert.equal(snapshot.timeline_replay_status, "degraded");
  assert.equal(snapshot.timeline_first_seq, 3);
  assert.equal(snapshot.timeline_last_seq, 9);
  assert.equal(snapshot.timeline_integrity, "degraded");
  assert.equal(snapshot.pending_interaction_valid, false);

  const defaultModeSnapshot = normalizeSessionPayload({ session_id: "sess-default" });
  assert.equal(defaultModeSnapshot.current_mode, "explore");

  const structuredTimeline = timelineFromTurns([
    {
      turn_id: "turn-1",
      user_text: "analyze demo",
      steps: [
        {
          step_id: "step-1",
          reasoning: "inspect file",
          tool_calls: [
            {
              call_id: "call-1",
              tool_name: "read_file",
              tool_label: "Read File",
              status: "success",
              arguments: { path: "demo.c" },
            },
          ],
        },
        {
          step_id: "step-2",
          reasoning: "summarize",
          assistant_text: "done",
          tool_calls: [],
        },
      ],
    },
  ]);
  assert.equal(structuredTimeline[1].stepId, "step-1");
  assert.equal(structuredTimeline[4].stepId, "step-2");

  const pendingTurnAnchor = resolveTimelineAnchor({
    explicitTurnId: "",
    activeTurnId: "",
    timeline: [
      { id: "cmd-old", kind: "command_result", turnId: "" },
      { id: "user-pending", kind: "user", turnId: "", content: "/mode debug" },
    ],
  });
  assert.equal(pendingTurnAnchor, "user-pending");

  const visiblePermission = resolveVisiblePermission(null, {
    has_pending_permission: true,
    pending_permission: {
      permission_id: "perm-1",
      tool_name: "edit_file",
      category: "workspace_write",
      reason: "需要写入",
    },
  });
  assert.equal(visiblePermission.permission_id, "perm-1");

  let liveState = reducer(initialState, {
    type: "local_user_message",
    text: "inspect demo",
  });
  liveState = reducer(liveState, {
    type: "turn_started",
    turnId: "turn-live",
    userText: "inspect demo",
  });
  liveState = reducer(liveState, {
    type: "step_started",
    turnId: "turn-live",
    stepId: "step-live-1",
    stepIndex: 1,
  });
  liveState = reducer(liveState, {
    type: "reasoning_delta",
    text: "inspect file",
    turnId: "turn-live",
    stepId: "step-live-1",
    stepIndex: 1,
  });
  liveState = reducer(liveState, {
    type: "tool_started",
    callId: "call-live-1",
    toolName: "read_file",
    label: "Read File",
    arguments: { path: "demo.c" },
    turnId: "turn-live",
    stepId: "step-live-1",
    stepIndex: 1,
  });
  liveState = reducer(liveState, {
    type: "tool_finished",
    callId: "call-live-1",
    success: true,
    error: "",
    data: { path: "demo.c" },
    label: "Read File",
    turnId: "turn-live",
    stepId: "step-live-1",
    stepIndex: 1,
  });
  liveState = reducer(liveState, {
    type: "assistant_delta",
    text: "done",
    turnId: "turn-live",
    stepId: "step-live-1",
    stepIndex: 1,
  });
  liveState = reducer(liveState, {
    type: "step_ended",
    turnId: "turn-live",
    stepId: "step-live-1",
    stepIndex: 1,
    assistantText: "done",
  });
  assert.equal(liveState.timeline[0].turnId, "turn-live");
  assert.equal(liveState.timeline[1].stepId, "step-live-1");
  assert.equal(liveState.timeline[2].stepId, "step-live-1");
  assert.equal(liveState.timeline[3].stepId, "step-live-1");
  assert.equal(liveState.timeline[1].projectionSource, "step_events");
  assert.equal(liveState.timeline[1].projectionKind, "recorded_step");
  assert.equal(liveState.timeline[1].synthetic, false);
  assert.equal(liveState.timeline[2].projectionSource, "step_events");
  assert.equal(liveState.timeline[3].projectionSource, "step_events");
  assert.equal(liveState.timeline.length, 4);

  let streamedAssistantState = reducer(initialState, {
    type: "local_user_message",
    text: "visual ask",
  });
  streamedAssistantState = reducer(streamedAssistantState, {
    type: "turn_started",
    turnId: "turn-stream",
    userText: "visual ask",
  });
  streamedAssistantState = reducer(streamedAssistantState, {
    type: "step_started",
    turnId: "turn-stream",
    stepId: "step-stream",
    stepIndex: 2,
  });
  streamedAssistantState = reducer(streamedAssistantState, {
    type: "assistant_delta",
    text: "ask flow ok",
    turnId: "turn-stream",
    stepId: "step-stream",
    stepIndex: 2,
  });
  streamedAssistantState = reducer(streamedAssistantState, {
    type: "step_ended",
    turnId: "turn-stream",
    stepId: "step-stream",
    stepIndex: 2,
    assistantText: "ask flow ok",
  });
  assert.equal(
    streamedAssistantState.timeline.filter((item) => item.kind === "assistant").length,
    1,
  );
  assert.equal(streamedAssistantState.timeline[1].content, "ask flow ok");

  let modeCommandState = reducer(initialState, {
    type: "local_user_message",
    text: "/mode debug",
  });
  modeCommandState = reducer(modeCommandState, {
    type: "command_result",
    id: "cmd-mode",
    commandName: "mode",
    success: true,
    message: "已切换到 `debug` 模式。",
    data: {
      current_mode: "debug",
    },
    turnId: "turn-mode",
  });
  assert.equal(modeCommandState.timeline[1].turnId, "turn-mode");
  assert.equal(modeCommandState.timeline[1].projectionSource, "raw_events");
  assert.equal(modeCommandState.timeline[1].projectionKind, "raw_event");
  assert.equal(modeCommandState.timeline[1].synthetic, false);

  let reboundTurnState = reducer(initialState, {
    type: "local_user_message",
    text: "/mode debug 继续分析",
  });
  reboundTurnState = reducer(reboundTurnState, {
    type: "command_result",
    id: "cmd-mode-and-run",
    commandName: "mode",
    success: true,
    message: "已切换到 `debug` 模式。继续处理后续消息。",
    data: {
      current_mode: "debug",
    },
  });
  const provisionalTurnId = reboundTurnState.timeline[1].turnId;
  reboundTurnState = reducer(reboundTurnState, {
    type: "turn_started",
    turnId: "turn-after-mode",
    userText: "继续分析",
  });
  assert.notEqual(provisionalTurnId, "");
  assert.equal(reboundTurnState.timeline[0].turnId, "turn-after-mode");
  assert.equal(reboundTurnState.timeline[1].turnId, "turn-after-mode");

  const reviewState = reducer(initialState, {
    type: "command_result",
    id: "cmd-review",
    commandName: "review",
    success: true,
    message: "## Review Findings",
    data: {
      review: {
        summary: "quality summary",
        findings: [{ id: "f1", severity: "high", priority: 1, title: "Build failed" }],
      },
    },
  });
  assert.equal(reviewState.timeline.length, 1);
  assert.equal(reviewState.timeline[0].kind, "command_result");
  assert.equal(reviewState.timeline[0].projectionSource, "raw_events");
  assert.equal(reviewState.review.summary, "quality summary");

  const diffSurfaceState = reducer(initialState, {
    type: "diff_surface_opened",
    diffSurface: {
      title: "Git Diff",
      rawDiff: "--- a/demo.c\n+++ b/demo.c\n",
      files: [{ path: "demo.c", diff: "--- a/demo.c\n+++ b/demo.c\n" }],
      focusedFilePath: "demo.c",
      focusedDiff: "--- a/demo.c\n+++ b/demo.c\n",
    },
  });
  assert.equal(diffSurfaceState.inspectorTab, "diff");
  assert.equal(diffSurfaceState.workbench.rightPanel.activeKind, "diff");
  assert.equal(diffSurfaceState.diffSurface.title, "Git Diff");

  const sessionErrorState = reducer(initialState, {
    type: "session_error",
    error: "loop exploded",
    turnId: "turn-error",
    stepId: "step-error",
    stepIndex: 3,
  });
  assert.equal(sessionErrorState.timeline.length, 1);
  assert.equal(sessionErrorState.timeline[0].kind, "system");
  assert.equal(sessionErrorState.timeline[0].tone, "error");
  assert.equal(sessionErrorState.timeline[0].content, "loop exploded");
  assert.equal(sessionErrorState.timeline[0].turnId, "turn-error");
  assert.equal(sessionErrorState.timeline[0].stepId, "step-error");
  assert.equal(sessionErrorState.timeline[0].stepIndex, 3);
  assert.equal(sessionErrorState.timeline[0].projectionSource, "raw_events");
  assert.equal(sessionErrorState.timeline[0].projectionKind, "raw_event");
  assert.equal(sessionErrorState.timeline[0].synthetic, false);

  const compactedState = reducer(initialState, {
    type: "context_compacted",
    recentTurns: 2,
    summarizedTurns: 5,
    approxTokensAfter: 8000,
    turnId: "turn-compact",
    stepId: "step-compact",
    stepIndex: 4,
  });
  assert.equal(compactedState.timeline.length, 1);
  assert.equal(compactedState.timeline[0].kind, "compact");
  assert.equal(compactedState.timeline[0].recentTurns, 2);
  assert.equal(compactedState.timeline[0].summarizedTurns, 5);
  assert.equal(compactedState.timeline[0].approxTokensAfter, 8000);
  assert.equal(compactedState.timeline[0].turnId, "turn-compact");
  assert.equal(compactedState.timeline[0].stepId, "step-compact");
  assert.equal(compactedState.timeline[0].stepIndex, 4);
  assert.equal(compactedState.timeline[0].projectionSource, "raw_events");
  assert.equal(compactedState.timeline[0].projectionKind, "raw_event");
  assert.equal(compactedState.timeline[0].synthetic, false);

  const permissionState = reducer(initialState, {
    type: "permission_context_loaded",
    context: {
      session_id: "sess-1",
      remembered_categories: ["workspace_write"],
      rules: [{ decision: "ask", category: "workspace_write", reason: "write" }],
    },
    inspectorTab: "permissions",
  });
  assert.equal(permissionState.inspectorTab, "permissions");
  assert.deepEqual(permissionState.permissionContext.remembered_categories, ["workspace_write"]);

  const pendingPermissionState = reducer(initialState, {
    type: "permission_request",
    permission: {
      permission_id: "perm-panel-1",
      tool_name: "edit_file",
      category: "workspace_write",
      reason: "need write permission",
    },
    inspectorTab: "interaction",
  });
  assert.equal(pendingPermissionState.permission.permission_id, "perm-panel-1");
  assert.equal(pendingPermissionState.inspectorTab, "interaction");
  assert.equal(pendingPermissionState.timeline.length, 0);

  const pendingUserInputState = reducer(initialState, {
    type: "user_input_request",
    request: {
      request_id: "ask-panel-1",
      tool_name: "ask_user",
      question: "继续吗？",
      options: [{ index: 1, text: "继续" }],
    },
  });
  assert.equal(pendingUserInputState.userInput.request_id, "ask-panel-1");
  assert.equal(pendingUserInputState.inspectorTab, "interaction");
  assert.equal(pendingUserInputState.inspectorOpen, true);

  const recipeState = reducer(initialState, {
    type: "recipes_loaded",
    items: [
      { id: "cmake.build.default", tool_name: "run_recipe", recipe_action: "build", label: "CMake Build", source: "detected" },
      { id: "cmake.test.default", tool_name: "run_recipe", recipe_action: "test", label: "CTest", source: "detected" },
    ],
  });
  assert.equal(recipeState.recipes.length, 2);

  const resolvedPermissionState = reducer(pendingPermissionState, {
    type: "permission_cleared",
  });
  assert.equal(resolvedPermissionState.permission, null);

  const activatedState = reducer(
    {
      ...initialState,
      eventLog: [{ ts: 1, label: "stale-session", detail: "" }],
    },
    {
      type: "session_activated",
      sessionId: "sess-2",
      snapshot: {
        session_id: "sess-2",
        current_mode: "build",
        has_pending_permission: false,
        pending_interaction_valid: true,
        pending_interaction: {
          interaction_id: "ask-existing",
          kind: "user_input",
          question: "继续吗？",
        },
      },
      timeline: [],
    },
  );
  assert.equal(activatedState.eventLog.length, 0);
  assert.equal(activatedState.inspectorTab, "interaction");
  assert.equal(activatedState.inspectorOpen, true);

  const bootstrapToolState = reducer(initialState, {
    type: "session_activated",
    sessionId: "sess-bootstrap",
    snapshot: {
      session_id: "sess-bootstrap",
      current_mode: "build",
      has_pending_permission: false,
      pending_interaction_valid: false,
    },
    timeline: [
      {
        id: "call-bootstrap-1",
        kind: "tool",
        toolName: "read_file",
        label: "Read File",
        arguments: { path: "demo.c" },
        status: "running",
        turnId: "turn-bootstrap",
        stepId: "step-bootstrap",
        stepIndex: 1,
        projectionSource: "session_state",
        projectionKind: "recorded_step",
        synthetic: false,
      },
    ],
    historyIntegrity: {
      status: "partial",
      restore_stop_reason: "pending_resolution_identity_mismatch",
    },
  });
  const dedupedToolState = reducer(bootstrapToolState, {
    type: "tool_started",
    callId: "call-bootstrap-1",
    toolName: "read_file",
    label: "Read File",
    arguments: { path: "demo.c" },
    turnId: "turn-bootstrap",
    stepId: "step-bootstrap",
    stepIndex: 1,
  });
  assert.equal(
    dedupedToolState.timeline.filter((item) => item.id === "call-bootstrap-1").length,
    1,
  );
  assert.equal(dedupedToolState.historyIntegrity.status, "partial");

  const timelineSource = fs.readFileSync(
    webappSourcePath("components", "Timeline.jsx"),
    "utf8",
  );
  assert.equal(timelineSource.includes("pre(props)"), true);
  assert.equal(timelineSource.includes("if (inline)"), true);
  assert.equal(timelineSource.includes("history partially restored"), true);
  assert.equal(timelineSource.includes("session history unavailable"), true);

  const timelineRowsSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "TimelineRows.jsx"),
    "utf8",
  );
  assert.equal(timelineRowsSource.includes("rowUiState"), true);
  assert.equal(timelineRowsSource.includes("onToggleRow"), true);
  assert.equal(timelineRowsSource.includes("rowKeyFor"), true);

  const workRowSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "WorkRow.jsx"),
    "utf8",
  );
  assert.equal(workRowSource.includes("expanded"), true);
  assert.equal(workRowSource.includes("onToggle"), true);
  assert.equal(workRowSource.includes("useState(row.status === \"error\")"), false);

  const interactionPanelSource = fs.readFileSync(
    webappSourcePath("components", "InteractionPanel.jsx"),
    "utf8",
  );
  assert.equal(interactionPanelSource.includes("notice?.kind"), true);

  const inspectorSource = fs.readFileSync(
    webappSourcePath("components", "Inspector.jsx"),
    "utf8",
  );
  assert.equal(inspectorSource.includes("RIGHT_PANEL_SURFACES"), true);
  assert.equal(inspectorSource.includes("showTabs = true"), true);
  assert.equal(inspectorSource.includes("{showTabs ? ("), true);
  assert.equal(inspectorSource.includes('{inspectorTab === "interaction"'), true);
  assert.equal(inspectorSource.includes('{inspectorTab === "diff"'), true);
  assert.equal(inspectorSource.includes("todo-row"), false);
  assert.equal(inspectorSource.includes("todo-mark"), false);

  const stylesSource = fs.readFileSync(
    webappSourcePath("styles.css"),
    "utf8",
  );
  assert.equal(stylesSource.includes("todo-"), false);
  assert.equal(stylesSource.includes("mode-code"), false);
  assert.equal(stylesSource.includes("mode-build"), true);
  assert.equal(stylesSource.includes(".t3-work-row.error"), true);
  assert.equal(stylesSource.includes(".t3-work-row.running"), true);
  assert.equal(stylesSource.includes("timeline-work-detail"), true);

  const appSource = fs.readFileSync(
    webappSourcePath("App.jsx"),
    "utf8",
  );
  assert.equal(appSource.includes("AppSidebarLayout"), true);
  assert.equal(appSource.includes("WorkbenchHeader"), true);
  assert.equal(appSource.includes("showTabs={false}"), true);
  assert.equal(appSource.includes("data.session_id || currentSessionIdRef.current || \"\""), true);
  assert.equal(appSource.includes("const activeSessionId = currentSessionIdRef.current;"), true);
  assert.equal(appSource.includes("loadAppBootstrap"), true);
  assert.equal(appSource.includes("openWorkspace"), true);
  assert.equal(appSource.includes("activateWorkspace"), true);
  assert.equal(appSource.includes("workspace_changed"), true);
  assert.equal(appSource.includes("no_active_workspace"), true);
  assert.equal(appSource.includes("__EMBEDAGENT_VISUAL_DEBUG__"), true);
  assert.equal(appSource.includes("visual_debug"), true);
  assert.equal(appSource.includes("loadTimelineFixture"), true);
  assert.equal(appSource.includes("loadInteractionFixture"), true);
  assert.equal(appSource.includes("loadThreadLifecycleFixture"), true);
  assert.equal(appSource.includes("visual_timeline_fixture_loaded"), true);
  assert.equal(appSource.includes("visual_interaction_fixture_loaded"), true);
  assert.equal(appSource.includes("visual_thread_lifecycle_fixture_loaded"), true);

  const storeSource = fs.readFileSync(
    webappSourcePath("store.js"),
    "utf8",
  );
  assert.equal(storeSource.includes("visual_timeline_fixture_loaded"), true);
  assert.equal(storeSource.includes("visual_interaction_fixture_loaded"), true);
  assert.equal(storeSource.includes("visual_thread_lifecycle_fixture_loaded"), true);

  const noWorkspaceSource = fs.readFileSync(
    webappSourcePath("components", "NoWorkspaceState.jsx"),
    "utf8",
  );
  assert.equal(noWorkspaceSource.includes('data-testid="no-workspace-state"'), true);
  assert.equal(noWorkspaceSource.includes('data-testid="workspace-path-input"'), true);
  assert.equal(noWorkspaceSource.includes('data-testid="open-workspace-button"'), true);

  const sidebarSource = fs.readFileSync(
    webappSourcePath("components", "Sidebar.jsx"),
    "utf8",
  );
  assert.equal(sidebarSource.includes('data-testid="workspace-switcher"'), true);
  assert.equal(sidebarSource.includes('data-testid="workspace-current-card"'), true);
  assert.equal(sidebarSource.includes('data-testid={`workspace-row--'), true);
  assert.equal(sidebarSource.includes('data-testid="thread-list"'), true);
  assert.equal(sidebarSource.includes('data-testid="thread-lifecycle-panel"'), true);
  assert.equal(sidebarSource.includes('data-testid="thread-empty-state"'), true);
  assert.equal(sidebarSource.includes('data-testid={`thread-action--'), true);
  assert.equal(sidebarSource.includes("onThreadLifecycleAction"), true);
  assert.equal(sidebarSource.includes("appHome?.workspace"), true);
  assert.equal(sidebarSource.includes("appHome?.threads"), true);
  assert.equal(sidebarSource.includes("new Date("), false);
  assert.equal(sidebarSource.includes("state.sessions.map"), false);
  assert.equal(fs.existsSync(webappSourcePath("session-runtime", "app-home-model.js")), true);
  const appHomeModelSource = fs.readFileSync(
    webappSourcePath("session-runtime", "app-home-model.js"),
    "utf8",
  );
  assert.equal(appHomeModelSource.includes("THREAD_LIFECYCLE_ACTIONS"), true);
  assert.equal(appHomeModelSource.includes("buildThreadLifecycleActions"), true);
  assert.equal(sidebarSource.includes("Threads"), true);

  const workbenchHeaderSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "WorkbenchHeader.jsx"),
    "utf8",
  );
  assert.equal(workbenchHeaderSource.includes("mode-code"), false);
  assert.equal(workbenchHeaderSource.includes("mode-${currentMode}"), true);
  assert.equal(workbenchHeaderSource.includes("header-status-group"), true);
  assert.equal(workbenchHeaderSource.includes("header-action-group"), true);

  const appSidebarLayoutSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "AppSidebarLayout.jsx"),
    "utf8",
  );
  assert.equal(appSidebarLayoutSource.includes("workbench-layout"), true);

  const rightPanelTabsSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "RightPanelTabs.jsx"),
    "utf8",
  );
  assert.equal(rightPanelTabsSource.includes("RIGHT_PANEL_SURFACES"), true);
  assert.equal(rightPanelTabsSource.includes("diff: \"Diff\""), true);
  assert.equal(rightPanelTabsSource.includes("todos"), false);

  const changedFilesCardSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "ChangedFilesCard.jsx"),
    "utf8",
  );
  assert.equal(changedFilesCardSource.includes("buildChangedFilesTree"), true);
  assert.equal(changedFilesCardSource.includes('data-testid="changed-files-tree"'), true);
  assert.equal(changedFilesCardSource.includes("View diff"), true);

  const diffPanelSource = fs.readFileSync(
    webappSourcePath("components", "diff", "DiffPanel.jsx"),
    "utf8",
  );
  assert.equal(diffPanelSource.includes('data-testid="diff-file-rail"'), true);
  assert.equal(diffPanelSource.includes("diff-panel-viewport"), true);

  const bottomDrawerSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "BottomDrawer.jsx"),
    "utf8",
  );
  assert.equal(bottomDrawerSource.includes("run_output"), true);

  const commandPaletteSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "CommandPalette.jsx"),
    "utf8",
  );
  assert.equal(commandPaletteSource.includes("visibleCommands"), true);
  assert.equal(commandPaletteSource.includes("cmd-palette"), true);

  const composerSource = fs.readFileSync(
    webappSourcePath("components", "Composer.jsx"),
    "utf8",
  );
  assert.equal(composerSource.includes("onOpenCommandPalette"), true);
  assert.equal(composerSource.includes("ComposerInteractionPanel"), true);

  runWorkbenchStateTests();
  runAppWorkspaceTests();
  runAppHomeModelTests();
  runSessionRuntimeTests();
  runT3TimelineTests();
  runTimelineUiStateTests();
  runVisualLanguageCssTests();
  runInteractionModelTests();
  runDiffModelTests();
  runWebSocketLifecycleTests();
  await runVisualDebugRunnerTests();

  console.log("frontend helper checks passed");
}

await main();
