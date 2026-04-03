import assert from "node:assert/strict";

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

function main() {
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
  });
  assert.equal(snapshot.status, "waiting_permission");
  assert.equal(snapshot.current_mode, "debug");
  assert.equal(snapshot.has_pending_permission, true);
  assert.equal(snapshot.lastTransitionDisplayReason, "cancelled");
  assert.equal(snapshot.recentTransitions[0].displayReason, "cancelled");

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
  });
  assert.equal(modeCommandState.timeline[1].turnId, modeCommandState.timeline[0].id);

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
  assert.equal(reviewState.review.summary, "quality summary");

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

  const recipeState = reducer(initialState, {
    type: "recipes_loaded",
    items: [
      { id: "cmake.build.default", tool_name: "compile_project", label: "CMake Build", source: "detected" },
      { id: "cmake.test.default", tool_name: "run_tests", label: "CTest", source: "detected" },
    ],
  });
  assert.equal(recipeState.recipes.length, 2);

  let inlinePermissionState = reducer(initialState, {
    type: "permission_request_inline",
    permission: {
      permission_id: "perm-inline-1",
      tool_name: "edit_file",
      category: "workspace_write",
      reason: "need write permission",
    },
    turnId: "turn-inline",
    stepId: "step-inline-1",
    stepIndex: 1,
  });
  assert.equal(inlinePermissionState.timeline.length, 1);
  assert.equal(inlinePermissionState.timeline[0].kind, "permission");
  assert.equal(inlinePermissionState.timeline[0].id, "perm-inline-1");
  assert.equal(inlinePermissionState.timeline[0].projectionSource, "step_events");
  inlinePermissionState = reducer(inlinePermissionState, {
    type: "permission_item_resolved",
    permissionId: "perm-inline-1",
    approved: true,
  });
  assert.equal(inlinePermissionState.timeline[0].resolved, true);
  assert.equal(inlinePermissionState.timeline[0].approved, true);

  console.log("frontend helper checks passed");
}

main();
