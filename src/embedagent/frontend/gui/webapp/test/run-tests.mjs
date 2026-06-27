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
} from "../src/state-helpers.js";
import { runDiffModelTests } from "./diff-model.test.mjs";
import { runInteractionModelTests } from "./interaction-model.test.mjs";
import { runActivityStateTests } from "./activity-state.test.mjs";
import { runSessionRuntimeTests } from "./session-runtime.test.mjs";
import { runT3TimelineTests } from "./t3-timeline.test.mjs";
import { runSourceControlStateTests } from "./source-control-state.test.mjs";
import { runTerminalStateTests } from "./terminal-state.test.mjs";
import { runTerminalControllerTests } from "./terminal-controller.test.mjs";
import { runTimelineUiStateTests } from "./timeline-ui-state.test.mjs";
import { runVisualLanguageCssTests } from "./visual-language-css.test.mjs";
import { runVisualDebugRunnerTests } from "./visual-debug-runner.test.mjs";
import { runWebSocketLifecycleTests } from "./websocket-lifecycle.test.mjs";
import { runSessionLoadersTests } from "./session-loaders.test.mjs";
import { runSessionActivationControllerTests } from "./session-activation-controller.test.mjs";
import { runSessionTransportControllerTests } from "./session-transport-controller.test.mjs";
import { runSocketMessageEffectsTests } from "./socket-message-effects.test.mjs";
import { runVisualDebugFixturesTests } from "./visual-debug-fixtures.test.mjs";
import { runWorkbenchParityModelTests } from "./workbench-parity-model.test.mjs";
import { runWorkbenchStateTests } from "./workbench-state.test.mjs";
import { runWorkbenchUiStateTests } from "./workbench-ui-state.test.mjs";
import { runAppShellModelTests } from "./app-shell-model.test.mjs";
import { runAppWorkspaceTests } from "./app-workspaces.test.mjs";
import { runAppHomeModelTests } from "./app-home-model.test.mjs";
import { runBranchToolbarModelTests } from "./branch-toolbar-model.test.mjs";
import { runCommandPaletteModelTests } from "./command-palette-model.test.mjs";
import { runCommandPaletteSourceTests } from "./command-palette-source.test.mjs";
import { runComposerCommandSearchTests } from "./composer-command-search.test.mjs";
import { runComposerComponentsSourceTests } from "./composer-components-source.test.mjs";
import { runComposerIntegrationSourceTests } from "./composer-integration-source.test.mjs";
import { runComposerInteractionModelTests } from "./composer-interaction-model.test.mjs";
import { runComposerPathContextTests } from "./composer-path-context.test.mjs";
import { runComposerStateTests } from "./composer-state.test.mjs";
import { runComposerTriggerTests } from "./composer-trigger.test.mjs";
import { runFilePreviewModelTests } from "./file-preview-model.test.mjs";
import { runPreviewSurfaceModelTests } from "./preview-surface-model.test.mjs";
import { runPreviewApiTests } from "./preview-api.test.mjs";
import { runRightPanelStoreParityTests } from "./right-panel-store-parity.test.mjs";
import { runRightPanelTabsSourceTests } from "./right-panel-tabs-source.test.mjs";
import { runTerminalShellSourceTests } from "./terminal-shell-source.test.mjs";
import { runThreadStateTests } from "./thread-state.test.mjs";
import { runRunOutputStateTests } from "./run-output-state.test.mjs";
import { runStoreReducerTests } from "./store-reducer.test.mjs";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function webappSourcePath(...parts) {
  return path.join(WEBAPP_ROOT, "src", ...parts);
}

function readWebappSourceText(...parts) {
  return fs.readFileSync(webappSourcePath(...parts), "utf8").replace(/\r\n?/g, "\n");
}

async function main() {
  assert.equal(initialState.requestedMode, "explore");
  assert.equal(initialState.maxTurns, null);
  assert.equal(initialState.app.bootstrapLoaded, false);
  assert.equal(initialState.app.app.protocol, "gui_app_shell_v1");
  assert.equal(initialState.app.settings.confirm_workspace_switch, true);
  assert.equal(initialState.app.hasActiveWorkspace, false);
  assert.equal(initialState.app.activeWorkspace, null);
  const storeTerminalSurface = reducer(initialState, {
    type: "workbench_surface_opened",
    placement: "right",
    kind: "terminal",
    terminalId: "term-1",
    resourceId: "term-1",
  });
  const storeSplitTerminalSurface = reducer(storeTerminalSurface, {
    type: "workbench_terminal_surface_split",
    placement: "right",
    surfaceId: "right:terminal:term-1",
    terminalId: "term-2",
  });
  assert.deepEqual(storeSplitTerminalSurface.workbench.rightPanel.surfaces[0].terminalIds, [
    "term-1",
    "term-2",
  ]);

  for (const kind of ["settings", "diagnostics", "source_control"]) {
    const appShellSurfaceState = reducer(initialState, {
      type: "workbench_surface_opened",
      placement: "right",
      kind,
    });
    assert.equal(appShellSurfaceState.workbench.rightPanel.activeKind, kind);
    assert.equal(appShellSurfaceState.workbench.rightPanel.surfaces.length, 1);
    assert.equal(appShellSurfaceState.workbench.rightPanel.surfaces[0].kind, kind);
    assert.equal(appShellSurfaceState.workbench.rightPanel.activeSurfaceId, `right:${kind}`);
  }

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

  const appSettingsState = reducer(appLoadedState, {
    type: "app_shell_settings_changed",
    patch: { confirm_workspace_switch: false, unknown: true },
  });
  assert.equal(appSettingsState.app.settings.confirm_workspace_switch, false);
  assert.equal(appSettingsState.app.settings.unknown, undefined);

  const directAppLoadedState = reducer(initialState, {
    type: "app_shell_bootstrap_loaded",
    bootstrap: {
      app: { shell_version: 1, product_name: "EmbedAgent", protocol: "gui_app_shell_v1" },
      workspaces: [],
      active_workspace: null,
      has_active_workspace: false,
      diagnostics: { host: { platform: "win32" } },
      capabilities: { app_commands: ["app.settings"] },
      settings: { confirm_workspace_switch: true },
    },
  });
  assert.equal(directAppLoadedState.app.bootstrapLoaded, true);
  assert.equal(directAppLoadedState.app.diagnostics.host.platform, "win32");

  const switchedWorkspaceState = reducer(
    {
      ...appSettingsState,
      thread: {
        sessions: [{ session_id: "sess-old" }],
        currentSessionId: "sess-old",
        historyIntegrity: { status: "partial" },
      },
      composer: { draft: "old draft" },
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
  assert.equal(switchedWorkspaceState.thread.currentSessionId, "");
  assert.deepEqual(switchedWorkspaceState.thread.sessions, []);
  assert.equal(switchedWorkspaceState.thread.historyIntegrity, null);
  assert.equal(switchedWorkspaceState.composer.draft, "");
  assert.deepEqual(switchedWorkspaceState.timeline, []);
  assert.deepEqual(switchedWorkspaceState.fileTree, []);
  assert.equal(switchedWorkspaceState.app.hasActiveWorkspace, false);
  assert.equal(switchedWorkspaceState.app.settings.confirm_workspace_switch, true);

  const sessionsState = reducer(initialState, {
    type: "sessions_loaded",
    sessions: [
      { session_id: "sess-active", user_goal: "Fix parser recovery" },
      { session_id: "sess-followup", user_goal: "Verify parser recovery" },
    ],
  });
  const activatedThreadState = reducer(sessionsState, {
    type: "session_activated",
    sessionId: "sess-active",
    snapshot: {
      session_id: "sess-active",
      current_mode: "build",
      pending_interaction_valid: false,
    },
    timeline: [],
  });
  assert.equal(activatedThreadState.thread.currentSessionId, "sess-active");
  assert.equal(activatedThreadState.thread.sessions.length, 2);

  const fileTreeState = reducer(initialState, {
    type: "file_tree_loaded",
    nodes: [
      {
        id: "src",
        path: "src",
        name: "src",
        kind: "dir",
        childrenLoaded: true,
        children: [{ id: "src/parser.c", path: "src/parser.c", name: "parser.c", kind: "file" }],
      },
    ],
  });
  assert.equal(fileTreeState.fileTree[0].children[0].path, "src/parser.c");

  const root = [createTreeNode({ path: "src", name: "src", kind: "dir", has_children: true })];
  const next = injectChildren(root, "src", [
    { path: "src/pkg", name: "pkg", kind: "dir", has_children: true },
    { path: "src/main.c", name: "main.c", kind: "file", has_children: false },
  ]);
  assert.equal(next[0].childrenLoaded, true);
  assert.equal(next[0].children[0].path, "src/pkg");

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
    pending_interaction_valid: false,
  });
  assert.equal(snapshot.status, "waiting_permission");
  assert.equal(snapshot.current_mode, "debug");
  assert.equal(snapshot.has_pending_permission, true);
  assert.equal(snapshot.lastTransitionDisplayReason, "cancelled");
  assert.equal(snapshot.recentTransitions[0].displayReason, "cancelled");
  assert.equal(Object.hasOwn(snapshot, "timeline" + "_replay_status"), false);
  assert.equal(Object.hasOwn(snapshot, "timeline" + "_first_seq"), false);
  assert.equal(Object.hasOwn(snapshot, "timeline" + "_last_seq"), false);
  assert.equal(Object.hasOwn(snapshot, "timeline" + "_integrity"), false);
  assert.equal(snapshot.pending_interaction_valid, false);

  const defaultModeSnapshot = normalizeSessionPayload({ session_id: "sess-default" });
  assert.equal(defaultModeSnapshot.current_mode, "explore");

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
  assert.equal(diffSurfaceState.workbench.rightPanel.activeSurfaceId, "right:diff:current");
  assert.equal(diffSurfaceState.diffSurface.title, "Git Diff");

  const filePreviewLoadingState = reducer(initialState, {
    type: "file_preview_load_started",
    path: "src/main.c",
  });
  assert.equal(filePreviewLoadingState.filePreviewsByPath["src/main.c"].status, "loading");
  assert.equal(filePreviewLoadingState.filePreviewsByPath["src/main.c"].path, "src/main.c");
  assert.equal(filePreviewLoadingState.preview, null);

  const filePreviewLoadedState = reducer(filePreviewLoadingState, {
    type: "file_preview_loaded",
    path: "src/main.c",
    preview: { kind: "file", title: "main.c", content: "int main(void) { return 0; }" },
  });
  assert.equal(filePreviewLoadedState.filePreviewsByPath["src/main.c"].status, "loaded");
  assert.equal(filePreviewLoadedState.filePreviewsByPath["src/main.c"].title, "main.c");
  assert.equal(filePreviewLoadedState.filePreviewsByPath["src/main.c"].content.includes("return 0"), true);
  assert.equal(filePreviewLoadedState.preview, null);

  const filePreviewFailedState = reducer(filePreviewLoadedState, {
    type: "file_preview_load_failed",
    path: "src/main.c",
    error: "not found",
  });
  assert.equal(filePreviewFailedState.filePreviewsByPath["src/main.c"].status, "error");
  assert.equal(filePreviewFailedState.filePreviewsByPath["src/main.c"].error, "not found");

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

  const clearedPermissionState = reducer(pendingPermissionState, {
    type: "permission_cleared",
  });
  assert.equal(clearedPermissionState.permission, null);
  assert.equal(clearedPermissionState.timeline.length, 0);

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
  assert.equal(pendingUserInputState.timeline.length, 0);

  const answeredUserInputState = reducer(pendingUserInputState, {
    type: "user_input_answered",
    requestId: "ask-panel-1",
    answerText: "继续",
  });
  assert.equal(answeredUserInputState.userInput, null);
  assert.equal(answeredUserInputState.timeline.length, 0);

  const recipeState = reducer(initialState, {
    type: "recipes_loaded",
    items: [
      { id: "cmake.build.default", tool_name: "run_recipe", recipe_action: "build", label: "CMake Build", source: "detected" },
      { id: "cmake.test.default", tool_name: "run_recipe", recipe_action: "test", label: "CTest", source: "detected" },
    ],
  });
  assert.equal(recipeState.recipes.length, 2);

  const activatedState = reducer(
    {
      ...initialState,
      runOutput: [{ ts: 1, label: "stale-session", detail: "" }],
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
  assert.equal(activatedState.runOutput.length, 0);
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
  assert.equal(dedupedToolState.thread.historyIntegrity.status, "partial");

  const timelineSource = fs.readFileSync(
    webappSourcePath("components", "Timeline.jsx"),
    "utf8",
  );
  assert.equal(timelineSource.includes("TimelineRows"), true);
  assert.equal(timelineSource.includes("function TurnGroup"), false);
  assert.equal(timelineSource.includes("onOpenFile"), true);
  assert.equal(timelineSource.includes("handleTimelineFileLink"), true);
  assert.equal(timelineSource.includes("parseTimelineFileHref"), true);
  assert.equal(timelineSource.includes("history partially restored"), true);
  assert.equal(timelineSource.includes("session history unavailable"), true);

  const timelineRowsSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "TimelineRows.jsx"),
    "utf8",
  );
  assert.equal(timelineRowsSource.includes("rowUiState"), true);
  assert.equal(timelineRowsSource.includes("rowDensityFor"), true);
  assert.equal(timelineRowsSource.includes("density={"), true);
  assert.equal(timelineRowsSource.includes("data-density"), true);
  assert.equal(timelineRowsSource.includes("onToggleRow"), true);
  assert.equal(timelineRowsSource.includes("onOpenFile"), true);
  assert.equal(timelineRowsSource.includes("rowKeyFor"), true);
  assert.equal(timelineRowsSource.includes("ReasoningRow"), true);
  assert.equal(timelineRowsSource.includes("ThinkingRow"), true);
  assert.equal(timelineRowsSource.includes("ContextSummaryRow"), true);
  assert.equal(timelineRowsSource.includes("CommandResultRow"), true);
  assert.equal(timelineRowsSource.includes("ReviewResultRow"), true);
  assert.equal(timelineRowsSource.includes("TimelineRowSwitch"), true);
  assert.equal(timelineRowsSource.includes("MAX_VISIBLE_WORK_LOG_ENTRIES"), true);
  assert.equal(timelineRowsSource.includes("WorkGroupSection"), true);
  assert.equal(timelineRowsSource.includes("findNearestVerticalScroller"), true);
  assert.equal(timelineRowsSource.includes("timeline-work-overflow-toggle"), true);
  assert.equal(timelineRowsSource.includes("WorkingTimer"), true);
  assert.equal(timelineRowsSource.includes("formatWorkingTimer"), true);
  assert.equal(timelineRowsSource.includes("timeline-working-dots"), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-reasoning-row"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-thinking-row"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-context-summary-row"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-command-result-row"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-review-result-row"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-work-group"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-working-row"'), true);

  const workRowSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "WorkRow.jsx"),
    "utf8",
  );
  assert.equal(workRowSource.includes("expanded"), true);
  assert.equal(workRowSource.includes("density"), true);
  assert.equal(workRowSource.includes("data-density"), true);
  assert.equal(workRowSource.includes("onToggle"), true);
  assert.equal(workRowSource.includes("onOpenFile"), true);
  assert.equal(workRowSource.includes("useState(row.status === \"error\")"), false);
  assert.equal(workRowSource.includes("ToolDetail"), true);
  assert.equal(workRowSource.includes("row.detailModel"), true);
  assert.equal(workRowSource.includes("WORK_ENTRY_ICONS"), true);
  assert.equal(workRowSource.includes("row.presentation"), true);
  assert.equal(workRowSource.includes("data-icon-name={presentation.iconName}"), true);
  assert.equal(workRowSource.includes("data-status-indicator={presentation.statusIndicator}"), true);
  assert.equal(workRowSource.includes("presentation.expandedBody"), true);
  assert.equal(workRowSource.includes("TOOL_ICONS"), false);
  assert.equal(workRowSource.includes("<pre>{row.detail}</pre>"), false);
  assert.equal(fs.existsSync(webappSourcePath("components", "timeline", "ToolDetail.jsx")), true);
  const toolDetailSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "ToolDetail.jsx"),
    "utf8",
  );
  assert.equal(toolDetailSource.includes("timeline-file-link"), true);
  assert.equal(toolDetailSource.includes("data-testid={`timeline-tool-file-link--"), true);
  assert.equal(toolDetailSource.includes("onOpenFile(item.path, item.line || undefined)"), true);
  assert.equal(timelineRowsSource.includes("onOpenFile={onOpenFile}"), true);

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
  assert.equal(inspectorSource.includes("formatDiagnosticsRows"), true);
  assert.equal(inspectorSource.includes("SettingsPanel"), true);
  assert.equal(inspectorSource.includes("DiagnosticsPanel"), true);
  assert.equal(inspectorSource.includes("appShell"), true);
  assert.equal(inspectorSource.includes("onAppSettingsChange"), true);
  assert.equal(inspectorSource.includes("SourceControlPanel"), true);
  assert.equal(inspectorSource.includes("sourceControl={sourceControl}"), true);
  assert.equal(inspectorSource.includes("todo-row"), false);
  assert.equal(inspectorSource.includes("todo-mark"), false);

  const stylesSource = readWebappSourceText("styles.css");
  assert.equal(stylesSource.includes("todo-"), false);
  assert.equal(stylesSource.includes("mode-code"), false);
  assert.equal(stylesSource.includes("mode-build"), true);
  assert.equal(stylesSource.includes(".t3-work-row.error"), true);
  assert.equal(stylesSource.includes(".t3-work-row.running"), true);
  assert.equal(stylesSource.includes(".t3-work-row.density-compact"), true);
  assert.equal(stylesSource.includes(".t3-work-row.density-normal"), true);
  assert.equal(stylesSource.includes(".t3-work-row.density-expanded"), true);
  assert.equal(stylesSource.includes(".t3-command-result-row.density-expanded"), true);
  assert.equal(stylesSource.includes("timeline-work-detail"), true);
  assert.equal(stylesSource.includes(".t3-tool-detail-grid"), true);
  assert.equal(stylesSource.includes(".t3-tool-detail-section"), true);
  assert.equal(stylesSource.includes(".t3-reasoning-row"), true);
  assert.equal(stylesSource.includes(".t3-thinking-row"), true);
  assert.equal(stylesSource.includes(".t3-context-summary-row"), true);
  assert.equal(stylesSource.includes(".t3-command-result-row"), true);
  assert.equal(stylesSource.includes(".t3-review-result-row"), true);
  assert.equal(stylesSource.includes(".timeline-work-group"), true);
  assert.equal(stylesSource.includes(".timeline-work-overflow-toggle"), true);
  assert.equal(stylesSource.includes(".timeline-working-dots"), true);
  assert.equal(stylesSource.includes("scrollbar-gutter: stable both-edges"), true);
  assert.equal(stylesSource.includes(".file-preview-breadcrumbs"), true);
  assert.equal(stylesSource.includes(".file-preview-gutter"), true);
  assert.equal(stylesSource.includes(".file-preview-mode-toggle"), true);
  assert.equal(stylesSource.includes(".file-preview-code"), true);
  assert.equal(stylesSource.includes("scrollbar-width: thin"), true);
  assert.equal(stylesSource.includes("minmax(360px, 1fr)"), false);
  assert.equal(stylesSource.includes(".workbench-main-slot {\n  display: flex;"), true);
  assert.equal(stylesSource.includes("height: 100%;\n  min-height: 0;\n  min-width: 0;"), true);
  assert.equal(stylesSource.includes(".right-panel-empty-state"), true);
  assert.equal(stylesSource.includes("overflow: auto;\n  padding: var(--sp-4);"), true);
  assert.equal(stylesSource.includes(".right-panel-surface-tab {\n  position: relative;\n  flex: 0 0 auto;\n  width: clamp(96px, 13vw, 176px);"), true);
  assert.equal(stylesSource.includes("overflow-wrap: anywhere"), true);
  assert.equal(stylesSource.includes("grid-template-columns: minmax(0, 1fr)"), true);
  assert.equal(stylesSource.includes("@media (max-width: 560px)"), true);
  assert.equal(stylesSource.includes(".app-settings-grid"), true);
  assert.equal(stylesSource.includes(".diagnostics-table"), true);
  assert.equal(stylesSource.includes(".source-control-panel"), true);
  assert.equal(stylesSource.includes(".source-control-file.active"), true);
  assert.equal(stylesSource.includes(".right-panel-file-surface"), true);
  assert.equal(stylesSource.includes(".right-panel-file-content"), true);
  assert.equal(stylesSource.includes(".right-panel-preview-surface"), true);
  assert.equal(stylesSource.includes(".preview-chrome-row"), true);
  assert.equal(stylesSource.includes(".preview-local-server-card"), true);

  const appSource = fs.readFileSync(
    webappSourcePath("App.jsx"),
    "utf8",
  );
  assert.equal(appSource.includes("createTerminalController"), true);
  assert.equal(appSource.includes("stateRef.current = state"), true);
  assert.equal(appSource.includes("terminalController.ensureOpen"), true);
  assert.equal(appSource.includes("terminalController.openSession"), true);
  assert.equal(appSource.includes("terminalController.openRightPanelSurface"), true);
  assert.equal(appSource.includes("terminalController.splitRightPanelSurface"), true);
  assert.equal(appSource.includes("terminalController.closeRightPanelPane"), true);
  assert.equal(appSource.includes("async function ensureTerminalOpen"), false);
  assert.equal(appSource.includes("async function openTerminalSession"), false);
  assert.equal(appSource.includes("async function refreshTerminals"), false);
  assert.equal(appSource.includes("async function sendTerminalInput"), false);
  assert.equal(appSource.includes("async function sendTerminalInputTo"), false);
  assert.equal(appSource.includes("async function clearActiveTerminal"), false);
  assert.equal(appSource.includes("async function clearTerminalById"), false);
  assert.equal(appSource.includes("async function restartActiveTerminal"), false);
  assert.equal(appSource.includes("async function restartTerminalById"), false);
  assert.equal(appSource.includes("async function closeActiveTerminal"), false);
  assert.equal(appSource.includes("async function openRightPanelTerminalSurface"), false);
  assert.equal(appSource.includes("async function splitRightPanelTerminalSurface"), false);
  assert.equal(appSource.includes("function activateRightPanelTerminalPane"), false);
  assert.equal(appSource.includes("async function closeRightPanelTerminalPane"), false);
  assert.equal(appSource.includes("function allKnownTerminalIds"), false);
  assert.equal(appSource.includes("AppSidebarLayout"), true);
  assert.equal(appSource.includes("WorkbenchHeader"), true);
  assert.equal(appSource.includes("currentSessionId: currentSessionIdRef.current"), true);
  assert.equal(appSource.includes("loadAppBootstrap"), true);
  assert.equal(appSource.includes("openWorkspace"), true);
  assert.equal(appSource.includes("activateWorkspace"), true);
  assert.equal(appSource.includes("deriveSocketMessageEffects"), true);
  assert.equal(appSource.includes("executeSocketEffects"), true);
  assert.equal(appSource.includes("executeLoaderRequest"), true);
  assert.equal(appSource.includes("installVisualDebugFixtures"), true);
  assert.equal(appSource.includes("createLoaderRequestExecutor"), true);
  assert.equal(appSource.includes("deriveSessionActivation"), false);
  assert.equal(appSource.includes("function connectWebSocket"), false);
  assert.equal(appSource.includes("function recoverSessionTransport"), false);
  assert.equal(appSource.includes("function executeLoaderRequest(request = {})"), false);
  assert.equal(appSource.includes("request.name === LOADER_REQUESTS"), false);
  assert.equal(appSource.includes('type: "set_connection"'), false);
  assert.equal(appSource.includes("__EMBEDAGENT_VISUAL_DEBUG__"), false);
  assert.equal(appSource.includes("visual_timeline_fixture_loaded"), false);
  assert.equal(appSource.includes("activeTurnId: state.activeTurnId"), true);
  assert.equal(appSource.includes("thinkingActive: state.thinkingActive"), true);
  for (const directSessionFunction of [
    "async function createSession",
    "async function renameThread",
    "async function archiveThread",
    "async function forkThread",
    "async function setMode",
    "async function cancelSession",
    "async function submitText",
  ]) {
    assert.equal(appSource.includes(directSessionFunction), false);
  }
  assert.equal(appSource.includes("createSessionController"), true);
  assert.equal(appSource.includes("createThreadLifecycleController"), true);
  const directCommandIdCases = (appSource.match(/command\.id ===/g) || []).length;
  assert.ok(directCommandIdCases <= 2);
  const sessionControllerSource = fs.readFileSync(
    webappSourcePath("app-runtime", "session-controller.js"),
    "utf8",
  );
  assert.equal(sessionControllerSource.includes("export function createSessionController"), true);
  assert.equal(sessionControllerSource.includes("no_active_workspace"), true);
  assert.equal(sessionControllerSource.includes("/api/sessions?mode="), true);
  assert.equal(sessionControllerSource.includes("/message"), true);
  assert.equal(sessionControllerSource.includes("import React"), false);
  const threadLifecycleControllerSource = fs.readFileSync(
    webappSourcePath("app-runtime", "thread-lifecycle-controller.js"),
    "utf8",
  );
  assert.equal(threadLifecycleControllerSource.includes("export function createThreadLifecycleController"), true);
  assert.equal(threadLifecycleControllerSource.includes("/rename"), true);
  assert.equal(threadLifecycleControllerSource.includes("/archive"), true);
  assert.equal(threadLifecycleControllerSource.includes("/fork"), true);
  assert.equal(threadLifecycleControllerSource.includes("import React"), false);
  const rightPanelControllerSource = fs.readFileSync(
    webappSourcePath("app-runtime", "right-panel-controller.js"),
    "utf8",
  );
  assert.equal(rightPanelControllerSource.includes("export function createRightPanelController"), true);
  assert.equal(rightPanelControllerSource.includes("rightPanelSurfaceTitle"), true);
  assert.equal(rightPanelControllerSource.includes("terminalController.openRightPanelSurface"), true);
  assert.equal(rightPanelControllerSource.includes("import React"), false);
  const workbenchCommandControllerSource = fs.readFileSync(
    webappSourcePath("app-runtime", "workbench-command-controller.js"),
    "utf8",
  );
  assert.equal(workbenchCommandControllerSource.includes("export function createWorkbenchCommandController"), true);
  assert.equal(workbenchCommandControllerSource.includes('case "app.settings"'), true);
  assert.equal(workbenchCommandControllerSource.includes('case "app.diagnostics"'), true);
  assert.equal(workbenchCommandControllerSource.includes('case "app.source_control"'), true);
  assert.equal(workbenchCommandControllerSource.includes('case "app.reload"'), true);
  assert.equal(workbenchCommandControllerSource.includes('case "surface.preview"'), false);
  assert.equal(workbenchCommandControllerSource.includes("command.surface"), true);
  assert.equal(workbenchCommandControllerSource.includes("import React"), false);
  assert.equal(appSource.includes("getSourceControlStatus"), true);
  assert.equal(appSource.includes("loadSourceControlStatus"), true);
  assert.equal(appSource.includes("openSourceControlFile"), true);
  assert.equal(appSource.includes("buildBranchToolbarModel"), true);
  assert.equal(appSource.includes("branchToolbarModel"), true);
  assert.equal(appSource.includes("onRefreshSourceControl"), true);
  assert.equal(appSource.includes("RightPanelSurfaceBody"), true);
  assert.equal(appSource.includes("onOpenFile={openFile}"), true);
  assert.equal(appSource.includes("activeRightPanelSurface"), true);
  assert.equal(appSource.includes("workbench_surface_close_others"), true);
  assert.equal(appSource.includes("workbench_surface_close_to_right"), true);
  assert.equal(appSource.includes("workbench_surface_close_all"), true);
  assert.equal(appSource.includes("file_preview_load_started"), true);
  assert.equal(appSource.includes("file_preview_loaded"), true);
  assert.equal(appSource.includes("file_preview_load_failed"), true);
  assert.equal(appSource.includes('kind: "file"'), true);
  assert.equal(appSource.includes('preview: { kind: "file"'), false);
  assert.equal(appSource.includes("showTabs={false}"), false);
  assert.equal(appSource.includes("activeKind={state.inspectorTab}"), false);
  assert.equal(appSource.includes("appShell: state.app"), true);
  assert.equal(appSource.includes("projectSessionRuntime"), false);
  assert.equal(appSource.includes("buildSessionActivityRuntime"), true);

  const visualFixturesSource = fs.readFileSync(
    webappSourcePath("app-runtime", "visual-debug-fixtures.js"),
    "utf8",
  );
  assert.equal(visualFixturesSource.includes("buildLongTimelineFixtureAction"), true);
  assert.equal(visualFixturesSource.includes("loadLongTimelineFixture"), true);

  const socketMessageEffectsSource = fs.readFileSync(
    webappSourcePath("app-runtime", "socket-message-effects.js"),
    "utf8",
  );
  assert.equal(socketMessageEffectsSource.includes("deriveSocketMessageEffects"), true);
  assert.equal(socketMessageEffectsSource.includes("LOADER_REQUESTS"), true);
  assert.equal(socketMessageEffectsSource.includes('from "./session-loaders.js"'), true);
  assert.equal(socketMessageEffectsSource.includes("export const LOADER_REQUESTS"), false);
  assert.equal(socketMessageEffectsSource.includes("workspace_changed"), true);
  assert.equal(socketMessageEffectsSource.includes("terminal_event"), true);
  assert.equal(socketMessageEffectsSource.includes("session_event"), true);
  assert.equal(socketMessageEffectsSource.includes("permission_request"), true);
  assert.equal(socketMessageEffectsSource.includes("user_input_request"), true);
  assert.equal(socketMessageEffectsSource.includes("command_result"), true);
  assert.equal(socketMessageEffectsSource.includes('event_kind: "interaction.created"'), false);
  assert.equal(socketMessageEffectsSource.includes("fetch("), false);

  assert.equal(socketMessageEffectsSource.includes("new WebSocket"), false);
  assert.equal(socketMessageEffectsSource.includes("useEffect"), false);

  const sessionLoadersSource = fs.readFileSync(
    webappSourcePath("app-runtime", "session-loaders.js"),
    "utf8",
  );
  assert.equal(sessionLoadersSource.includes("createLoaderRequestExecutor"), true);
  assert.equal(sessionLoadersSource.includes("deriveSessionActivation"), true);
  assert.equal(sessionLoadersSource.includes("LOADER_REQUESTS"), true);
  assert.equal(sessionLoadersSource.includes("normalizeHistoryActivities"), true);
  assert.equal(sessionLoadersSource.includes("history.activities"), true);
  assert.equal(sessionLoadersSource.includes("timelineFromTurns"), false);
  assert.equal(sessionLoadersSource.includes("normalizeSessionPayload"), true);
  assert.equal(sessionLoadersSource.includes("fetch("), false);
  assert.equal(sessionLoadersSource.includes("new WebSocket"), false);
  assert.equal(sessionLoadersSource.includes("useEffect"), false);
  assert.equal(sessionLoadersSource.includes("import React"), false);

  const stateHelpersSource = fs.readFileSync(
    webappSourcePath("state-helpers.js"),
    "utf8",
  );
  assert.equal(stateHelpersSource.includes("timelineFromEvents"), false);
  assert.equal(stateHelpersSource.includes("timelineFromTurns"), false);
  assert.equal(stateHelpersSource.includes("summarizeTimelineProjection"), false);

  const sessionRuntimeFiles = fs.readdirSync(webappSourcePath("session-runtime"));
  assert.equal(sessionRuntimeFiles.includes("projector.js"), false);

  const terminalControllerSource = fs.readFileSync(
    webappSourcePath("app-runtime", "terminal-controller.js"),
    "utf8",
  );
  assert.equal(terminalControllerSource.includes("createTerminalController"), true);
  assert.equal(terminalControllerSource.includes("TERMINAL_DIMENSIONS"), true);
  assert.equal(terminalControllerSource.includes("Open a session before using the terminal."), true);
  assert.equal(terminalControllerSource.includes("workbench_surface_opened"), true);
  assert.equal(terminalControllerSource.includes("workbench_terminal_surface_split"), true);
  assert.equal(terminalControllerSource.includes("workbench_terminal_surface_terminal_closed"), true);
  assert.equal(terminalControllerSource.includes("fetch("), false);
  assert.equal(terminalControllerSource.includes("new WebSocket"), false);
  assert.equal(terminalControllerSource.includes("useEffect"), false);
  assert.equal(terminalControllerSource.includes("import React"), false);
  assert.equal(terminalControllerSource.includes("from \"../terminal/terminal-api"), false);
  assert.equal(terminalControllerSource.includes("from \"../terminal/terminal-state"), false);
  assert.equal(terminalControllerSource.includes("embedagent"), false);

  const terminalApiSource = fs.readFileSync(
    webappSourcePath("terminal", "terminal-api.js"),
    "utf8",
  );
  assert.equal(terminalApiSource.includes("/api/sessions/"), true);
  assert.equal(terminalApiSource.includes("fetch("), true);

  const visualDebugFixturesSource = fs.readFileSync(
    webappSourcePath("app-runtime", "visual-debug-fixtures.js"),
    "utf8",
  );
  assert.equal(visualDebugFixturesSource.includes("__EMBEDAGENT_VISUAL_DEBUG__"), true);
  assert.equal(visualDebugFixturesSource.includes("visual_debug"), true);
  assert.equal(visualDebugFixturesSource.includes("loadTimelineFixture"), true);
  assert.equal(visualDebugFixturesSource.includes("loadInteractionFixture"), true);
  assert.equal(visualDebugFixturesSource.includes("loadThreadLifecycleFixture"), true);
  assert.equal(visualDebugFixturesSource.includes("visual_timeline_fixture_loaded"), false);
  assert.equal(visualDebugFixturesSource.includes("dev_fixture_timeline"), true);
  assert.equal(visualDebugFixturesSource.includes('kind: "reasoning"'), true);
  assert.equal(visualDebugFixturesSource.includes('kind: "compact"'), true);
  assert.equal(visualDebugFixturesSource.includes('commandName: "review"'), true);
  assert.equal(visualDebugFixturesSource.includes("thinkingActive: true"), true);

  const storeSource = fs.readFileSync(
    webappSourcePath("store.js"),
    "utf8",
  );
  assert.equal(storeSource.includes("createTerminalState"), true);
  assert.equal(storeSource.includes("reduceTerminalState"), true);
  assert.equal(storeSource.includes("terminal_snapshot_loaded"), true);
  assert.equal(storeSource.includes("connectionState:"), false);
  assert.equal(storeSource.includes('"set_connection"'), false);
  assert.equal(storeSource.includes("visual_timeline_fixture_loaded"), false);
  assert.equal(storeSource.includes("visual_interaction_fixture_loaded"), false);
  assert.equal(storeSource.includes("visual_thread_lifecycle_fixture_loaded"), false);
  assert.equal(storeSource.includes("visual_composer_file_tree_fixture_loaded"), false);
  assert.equal(storeSource.includes("visual_file_preview_reveal_fixture_loaded"), false);
  assert.equal(storeSource.includes("visual_source_control_fixture_loaded"), false);
  assert.equal(storeSource.includes("filePreviewsByPath"), true);
  assert.equal(storeSource.includes("file_preview_load_started"), true);
  assert.equal(storeSource.includes("file_preview_loaded"), true);
  assert.equal(storeSource.includes("file_preview_load_failed"), true);
  assert.equal(storeSource.includes("reduceActivityState"), true);
  assert.equal(storeSource.includes('case "assistant_delta":'), false);
  assert.equal(storeSource.includes('case "tool_started":'), false);
  assert.equal(storeSource.includes('case "tool_finished":'), false);

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
  assert.equal(sidebarSource.includes('data-testid="sidebar-tab--files"'), false);
  assert.equal(sidebarSource.includes("file-tree-node--"), false);
  assert.equal(sidebarSource.includes("react-arborist"), false);
  assert.equal(sidebarSource.includes("onLoadFileChildren"), false);
  assert.equal(sidebarSource.includes("onOpenFile"), false);
  assert.equal(fs.existsSync(webappSourcePath("session-runtime", "app-home-model.js")), true);
  const appHomeModelSource = fs.readFileSync(
    webappSourcePath("session-runtime", "app-home-model.js"),
    "utf8",
  );
  assert.equal(appHomeModelSource.includes("THREAD_LIFECYCLE_ACTIONS"), true);
  assert.equal(appHomeModelSource.includes("buildThreadLifecycleActions"), true);
  assert.equal(appHomeModelSource.includes("session.thread?.title"), true);
  assert.equal(sidebarSource.includes("Threads"), true);

  const workbenchHeaderSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "WorkbenchHeader.jsx"),
    "utf8",
  );
  assert.equal(workbenchHeaderSource.includes("mode-code"), false);
  assert.equal(workbenchHeaderSource.includes("mode-${currentMode}"), true);
  assert.equal(workbenchHeaderSource.includes("header-status-group"), true);
  assert.equal(workbenchHeaderSource.includes("header-action-group"), true);
  assert.equal(workbenchHeaderSource.includes("turns {turnsUsed}/{maxTurns}"), true);
  assert.equal(workbenchHeaderSource.includes("turnsUsed > 0 && maxTurns != null"), true);

  const appSidebarLayoutSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "AppSidebarLayout.jsx"),
    "utf8",
  );
  assert.equal(appSidebarLayoutSource.includes("workbench-layout"), true);

  const rightPanelTabsSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "RightPanelTabs.jsx"),
    "utf8",
  );
  assert.equal(rightPanelTabsSource.includes("right-panel-empty-state"), true);
  assert.equal(rightPanelTabsSource.includes("right-panel-add-surface"), true);
  assert.equal(rightPanelTabsSource.includes("right-panel-add-menu-popup"), true);
  assert.equal(rightPanelTabsSource.includes("scrollIntoView"), true);
  assert.equal(rightPanelTabsSource.includes("data-right-panel-tab-list"), true);
  assert.equal(rightPanelTabsSource.includes("onCloseOtherSurfaces"), true);
  assert.equal(rightPanelTabsSource.includes("onCloseSurfacesToRight"), true);
  assert.equal(rightPanelTabsSource.includes("onCloseAllSurfaces"), true);
  assert.equal(rightPanelTabsSource.includes("RIGHT_PANEL_SURFACES.map"), false);
  assert.equal(rightPanelTabsSource.includes("rightPanelLauncherSurfaceDefinitions"), true);
  assert.equal(rightPanelTabsSource.includes("surfaceDefinitionFor"), true);
  assert.equal(rightPanelTabsSource.includes("SURFACE_COPY"), false);
  assert.equal(rightPanelTabsSource.includes("right-panel-surface-tab--file"), true);
  assert.equal(rightPanelTabsSource.includes("right-panel-surface-tab--preview"), true);
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
  assert.equal(diffPanelSource.includes("surface-subheader"), true);
  assert.equal(diffPanelSource.includes('data-testid="diff-mode-toggle--stacked"'), true);
  assert.equal(diffPanelSource.includes('data-testid="diff-mode-toggle--split"'), true);
  assert.equal(diffPanelSource.includes('data-testid="diff-wrap-toggle"'), true);
  assert.equal(diffPanelSource.includes('data-testid="diff-whitespace-toggle"'), true);
  assert.equal(diffPanelSource.includes("collapsedDiffFilePaths"), true);
  assert.equal(diffPanelSource.includes("diff-selection-chip-strip"), true);

  const sourceControlPanelSource = fs.readFileSync(
    webappSourcePath("components", "source-control", "SourceControlPanel.jsx"),
    "utf8",
  );
  assert.equal(sourceControlPanelSource.includes('data-testid="source-control-panel"'), true);
  assert.equal(sourceControlPanelSource.includes("groupSourceControlFiles"), true);
  assert.equal(sourceControlPanelSource.includes("fileStatusLabel"), true);
  assert.equal(sourceControlPanelSource.includes("onRefresh"), true);

  const branchToolbarSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "BranchToolbar.jsx"),
    "utf8",
  );
  assert.equal(branchToolbarSource.includes('data-testid="branch-toolbar"'), true);
  assert.equal(branchToolbarSource.includes('data-testid="branch-toolbar-mode"'), true);
  assert.equal(branchToolbarSource.includes('data-testid="branch-toolbar-branch"'), true);
  assert.equal(branchToolbarSource.includes("onRefresh"), true);
  assert.equal(branchToolbarSource.includes("fetch("), false);
  assert.equal(branchToolbarSource.includes("transcript"), false);

  const bottomDrawerSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "BottomDrawer.jsx"),
    "utf8",
  );
  assert.equal(bottomDrawerSource.includes("TerminalShell"), true);
  assert.equal(bottomDrawerSource.includes("run_output"), true);
  assert.equal(bottomDrawerSource.includes("export function TerminalSurface"), false);

  const filesSurfaceSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "FilesSurface.jsx"),
    "utf8",
  );
  assert.equal(filesSurfaceSource.includes("react-arborist"), true);
  assert.equal(filesSurfaceSource.includes('data-testid="right-panel-files-surface"'), true);
  assert.equal(filesSurfaceSource.includes('data-testid="right-panel-file-tree-scroll"'), true);
  assert.equal(filesSurfaceSource.includes("right-panel-file-node--"), true);
  assert.equal(filesSurfaceSource.includes("onLoadFileChildren"), true);

  const rightPanelSurfaceBodySource = fs.readFileSync(
    webappSourcePath("components", "workbench", "RightPanelSurfaceBody.jsx"),
    "utf8",
  );
  assert.equal(rightPanelSurfaceBodySource.includes("FilesSurface"), true);
  assert.equal(rightPanelSurfaceBodySource.includes("FilePreviewSurface"), true);
  assert.equal(rightPanelSurfaceBodySource.includes("PreviewSurface"), true);
  assert.equal(rightPanelSurfaceBodySource.includes("TerminalShell"), true);
  assert.equal(rightPanelSurfaceBodySource.includes("Inspector"), true);
  assert.equal(rightPanelSurfaceBodySource.includes('surface.kind === "file"'), true);
  assert.equal(rightPanelSurfaceBodySource.includes('surface.kind === "preview"'), true);
  assert.equal(rightPanelSurfaceBodySource.includes("surface.kind === \"terminal\""), true);
  assert.equal(rightPanelSurfaceBodySource.includes("filePreviewsByPath"), true);

  const terminalShellSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "TerminalShell.jsx"),
    "utf8",
  );
  assert.equal(terminalShellSource.includes('data-testid={isRightPanel ? "right-panel-terminal-surface" : "terminal-drawer"}'), true);
  assert.equal(terminalShellSource.includes("surface.terminalIds"), true);
  assert.equal(terminalShellSource.includes("splitDirection"), true);
  assert.equal(terminalShellSource.includes("onSplitVertical"), true);
  assert.equal(rightPanelSurfaceBodySource.includes("RightPanelTerminalSurface"), false);
  assert.equal(rightPanelSurfaceBodySource.includes("projectName={projectName}"), true);

  const filePreviewSurfaceSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "FilePreviewSurface.jsx"),
    "utf8",
  );
  assert.equal(filePreviewSurfaceSource.includes('data-testid="right-panel-file-surface"'), true);
  assert.equal(filePreviewSurfaceSource.includes("right-panel-file-loading"), true);
  assert.equal(filePreviewSurfaceSource.includes("right-panel-file-error"), true);
  assert.equal(filePreviewSurfaceSource.includes("right-panel-file-content"), true);
  assert.equal(filePreviewSurfaceSource.includes("fileBreadcrumbs"), true);
  assert.equal(filePreviewSurfaceSource.includes("numberFileLines"), true);
  assert.equal(filePreviewSurfaceSource.includes("isMarkdownPreviewFile"), true);
  assert.equal(filePreviewSurfaceSource.includes("filePreviewMeta"), true);
  assert.equal(filePreviewSurfaceSource.includes("fileRevealLine"), true);
  assert.equal(filePreviewSurfaceSource.includes("data-file-link-reveal"), true);
  assert.equal(filePreviewSurfaceSource.includes("data-file-line-number"), true);
  assert.equal(filePreviewSurfaceSource.includes("scrollIntoView"), true);
  assert.equal(filePreviewSurfaceSource.includes("ReactMarkdown"), true);
  assert.equal(filePreviewSurfaceSource.includes('data-testid="file-preview-breadcrumbs"'), true);
  assert.equal(filePreviewSurfaceSource.includes('data-testid="file-preview-gutter"'), true);
  assert.equal(filePreviewSurfaceSource.includes('data-testid="file-preview-mode-toggle"'), true);
  assert.equal(filePreviewSurfaceSource.includes('data-testid="file-preview-markdown"'), true);
  assert.equal(filePreviewSurfaceSource.includes("surface-subheader"), true);
  assert.equal(filePreviewSurfaceSource.includes('data-testid="file-preview-open-action"'), true);
  assert.equal(filePreviewSurfaceSource.includes('data-testid="file-preview-explorer-toggle"'), true);
  assert.equal(filePreviewSurfaceSource.includes("file-preview-action-icon"), true);
  assert.equal(filePreviewSurfaceSource.includes("breadcrumbRef"), true);
  assert.equal(filePreviewSurfaceSource.includes("onOpenFilesSurface"), true);

  const previewSurfaceSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "PreviewSurface.jsx"),
    "utf8",
  );
  assert.equal(previewSurfaceSource.includes('data-testid="right-panel-preview-surface"'), true);
  assert.equal(previewSurfaceSource.includes('data-testid="preview-url-input"'), true);
  assert.equal(previewSurfaceSource.includes('data-testid="preview-local-server-card"'), true);
  assert.equal(previewSurfaceSource.includes("PreviewChromeRow"), true);
  assert.equal(previewSurfaceSource.includes("PreviewEmptyState"), true);
  assert.equal(previewSurfaceSource.includes("PreviewUnreachable"), true);
  assert.equal(previewSurfaceSource.includes("buildPreviewRuntimeState"), true);
  assert.equal(previewSurfaceSource.includes("onRefresh"), true);
  assert.equal(previewSurfaceSource.includes("onOpenExternal"), true);
  assert.equal(previewSurfaceSource.includes("onOpenUrl"), true);

  const previewApiSource = fs.readFileSync(
    webappSourcePath("preview", "preview-api.js"),
    "utf8",
  );
  assert.equal(previewApiSource.includes("/api/sessions/"), true);
  assert.equal(previewApiSource.includes("/preview/open"), true);
  assert.equal(previewApiSource.includes("/api/app/preview/open-external"), true);

  const repoRoot = path.resolve(WEBAPP_ROOT, "..", "..", "..", "..", "..");
  const visualDebugSource = fs.readFileSync(
    path.join(repoRoot, "scripts", "gui-visual-debug.mjs"),
    "utf8",
  );
  assert.equal(visualDebugSource.includes('"terminal"'), true);
  assert.equal(visualDebugSource.includes('"preview"'), true);
  assert.equal(visualDebugSource.includes("runPreviewScenario"), true);
  assert.equal(visualDebugSource.includes("right-panel-preview-surface"), true);
  assert.equal(visualDebugSource.includes("runTerminalScenario"), true);
  assert.equal(visualDebugSource.includes("right-panel-terminal-surface"), true);
  assert.equal(visualDebugSource.includes("loadLongTimelineFixture"), true);
  assert.equal(visualDebugSource.includes("requireScrollable: true"), true);

  const commandPaletteSource = fs.readFileSync(
    webappSourcePath("components", "workbench", "CommandPalette.jsx"),
    "utf8",
  );
  assert.equal(commandPaletteSource.includes("CommandPaletteResults"), true);
  assert.equal(commandPaletteSource.includes("buildCommandPaletteRootGroups"), true);
  assert.equal(commandPaletteSource.includes("visibleCommands"), false);
  assert.equal(commandPaletteSource.includes("cmd-palette"), true);

  const composerSource = fs.readFileSync(
    webappSourcePath("components", "Composer.jsx"),
    "utf8",
  );
  assert.equal(composerSource.includes("onOpenCommandPalette"), true);
  assert.equal(composerSource.includes("ComposerInteractionPanel"), true);
  assert.equal(composerSource.includes("BranchToolbar"), true);
  assert.equal(composerSource.includes("branchToolbar"), true);
  assert.equal(composerSource.includes("onRefreshSourceControl"), true);

  const sessionActivationControllerSource = fs.readFileSync(
    webappSourcePath("app-runtime", "session-activation-controller.js"),
    "utf8",
  );
  assert.equal(sessionActivationControllerSource.includes("deriveSessionActivation"), true);
  assert.equal(sessionActivationControllerSource.includes("/bootstrap"), true);

  const sessionTransportControllerSource = fs.readFileSync(
    webappSourcePath("app-runtime", "session-transport-controller.js"),
    "utf8",
  );
  assert.equal(sessionTransportControllerSource.includes("shouldReconnectSocket"), true);
  assert.equal(sessionTransportControllerSource.includes("appendSessionTransportEvent"), true);
  assert.equal(sessionTransportControllerSource.includes("/events?after_seq"), false);

  runWorkbenchStateTests();
  runWorkbenchParityModelTests();
  runWorkbenchUiStateTests();
  runRightPanelTabsSourceTests();
  runRightPanelStoreParityTests();
  runAppShellModelTests();
  runAppWorkspaceTests();
  runAppHomeModelTests();
  runBranchToolbarModelTests();
  runCommandPaletteModelTests();
  runCommandPaletteSourceTests();
  runThreadStateTests();
  runRunOutputStateTests();
  runStoreReducerTests();
  runComposerTriggerTests();
  runComposerCommandSearchTests();
  runComposerPathContextTests();
  runComposerInteractionModelTests();
  runComposerStateTests();
  runComposerComponentsSourceTests();
  runComposerIntegrationSourceTests();
  runSourceControlStateTests();
  runTerminalStateTests();
  await runTerminalControllerTests();
  runTerminalShellSourceTests();
  runActivityStateTests();
  runSessionRuntimeTests();
  runT3TimelineTests();
  runTimelineUiStateTests();
  runVisualLanguageCssTests();
  runInteractionModelTests();
  runDiffModelTests();
  runFilePreviewModelTests();
  runPreviewSurfaceModelTests();
  await runPreviewApiTests();
  runWebSocketLifecycleTests();
  await runSessionLoadersTests();
  await runSessionActivationControllerTests();
  await runSessionTransportControllerTests();
  runSocketMessageEffectsTests();
  runVisualDebugFixturesTests();
  await runVisualDebugRunnerTests();

  console.log("frontend helper checks passed");
}

await main();
