import assert from "node:assert/strict";

import {
  buildSessionActivityRuntime,
  normalizeHistoryActivities,
} from "../src/session-runtime/activity-state.js";
import {
  createActivityState,
  reduceActivityState,
} from "../src/session-runtime/activity-reducer.js";
import { createSessionTransportState } from "../src/session-runtime/session-transport-state.js";

export function runActivityStateTests() {
  let activity = createActivityState();
  activity = reduceActivityState(activity, {
    type: "local_user_message",
    text: "Inspect parser",
    createdAt: "2026-06-27T00:00:00.000Z",
  });
  assert.equal(activity.timeline.length, 1);
  assert.equal(activity.timeline[0].kind, "user");
  assert.equal(activity.activeTurnId, activity.timeline[0].pendingTurnId);

  activity = reduceActivityState(activity, {
    type: "turn_started",
    turnId: "turn-1",
    userText: "Inspect parser",
    createdAt: "2026-06-27T00:00:01.000Z",
  });
  assert.equal(activity.timeline[0].turnId, "turn-1");

  activity = reduceActivityState(activity, {
    type: "step_started",
    turnId: "turn-1",
    stepId: "step-1",
    stepIndex: 1,
  });
  activity = reduceActivityState(activity, {
    type: "reasoning_delta",
    text: "Read parser entry point",
    createdAt: "2026-06-27T00:00:02.000Z",
  });
  activity = reduceActivityState(activity, {
    type: "tool_started",
    callId: "call-1",
    toolName: "read_file",
    label: "Read File",
    arguments: { path: "src/parser.c" },
  });
  activity = reduceActivityState(activity, {
    type: "tool_finished",
    callId: "call-1",
    toolName: "read_file",
    label: "Read File",
    success: true,
    data: { path: "src/parser.c" },
  });
  activity = reduceActivityState(activity, {
    type: "assistant_delta",
    text: "Parser inspected.",
    createdAt: "2026-06-27T00:00:03.000Z",
  });
  activity = reduceActivityState(activity, {
    type: "step_ended",
    turnId: "turn-1",
    stepId: "step-1",
    stepIndex: 1,
  });
  assert.equal(activity.timeline.filter((item) => item.kind === "reasoning").length, 1);
  assert.equal(activity.timeline.filter((item) => item.kind === "tool").length, 1);
  assert.equal(activity.timeline.filter((item) => item.kind === "assistant").length, 1);
  assert.equal(activity.streamingAssistantId, "");

  activity = reduceActivityState(activity, {
    type: "context_compacted",
    content: "Context compacted.",
    recentTurns: 2,
    summarizedTurns: 4,
    approxTokensAfter: 4096,
  });
  activity = reduceActivityState(activity, {
    type: "session_error",
    error: "loop stopped",
  });
  activity = reduceActivityState(activity, {
    type: "stream_completed",
  });
  assert.equal(activity.timeline.some((item) => item.kind === "compact"), true);
  assert.equal(activity.timeline.some((item) => item.kind === "system" && item.tone === "error"), true);
  assert.equal(activity.thinkingActive, false);

  const activities = normalizeHistoryActivities([
    {
      kind: "user",
      id: "u-1",
      turn_id: "turn-1",
      content: "Inspect parser",
      projection_source: "session_state",
    },
    {
      kind: "reasoning",
      id: "r-1",
      turn_id: "turn-1",
      step_id: "step-1",
      step_index: 1,
      content: "Read parser entry point",
      projection_source: "session_state",
    },
    {
      kind: "tool",
      id: "tool-call-1",
      turn_id: "turn-1",
      step_id: "step-1",
      step_index: 1,
      tool_name: "read_file",
      tool_label: "Read File",
      call_id: "call-1",
      arguments: { path: "src/parser.c" },
      status: "success",
      data: { path: "src/parser.c" },
      projection_source: "session_state",
    },
    {
      kind: "assistant",
      id: "a-1",
      turn_id: "turn-1",
      step_id: "step-1",
      step_index: 1,
      content: "Parser inspected.",
      projection_source: "session_state",
    },
  ]);

  assert.equal(activities.length, 4);
  assert.equal(activities[0].kind, "user");
  assert.equal(activities[0].turnId, "turn-1");
  assert.equal(activities[1].stepId, "step-1");
  assert.equal(activities[2].kind, "tool");
  assert.equal(activities[2].toolName, "read_file");
  assert.equal(activities[2].projectionSource, "session_state");
  assert.equal(activities[3].content, "Parser inspected.");

  const runtime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "build",
    },
    sessionTransport: createSessionTransportState(),
    activities,
  });

  assert.equal(runtime.timelineItems.length, 4);
  assert.equal(runtime.timelineView.length, 1);
  assert.equal(runtime.timelineView[0].userItem.content, "Inspect parser");
  assert.equal(runtime.timelineView[0].steps[0].activityItems[0].kind, "reasoning");
  assert.equal(runtime.timelineView[0].steps[0].activityItems[1].toolName, "read_file");
  assert.equal(
    runtime.t3TimelineRows.some((row) => row.kind === "message" && row.role === "user"),
    true,
  );
  assert.equal(
    runtime.t3TimelineRows.some(
      (row) => row.kind === "turn_fold" && row.entries.some((entry) => entry.kind === "work"),
    ),
    true,
  );

  const pendingRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_user_input",
      pending_interaction_valid: true,
      pending_interaction: {
        interaction_id: "ask-1",
        kind: "user_input",
        question: "Continue?",
      },
      restore_stop_reason: "interaction_expired",
    },
    sessionTransport: createSessionTransportState(),
    activities: [],
  });
  assert.equal(pendingRuntime.currentInteraction.interaction_id, "ask-1");
  assert.equal(pendingRuntime.interactionNotice, null);
  assert.equal(
    pendingRuntime.t3TimelineRows.filter((row) => row.kind === "interaction").length,
    1,
  );
}
