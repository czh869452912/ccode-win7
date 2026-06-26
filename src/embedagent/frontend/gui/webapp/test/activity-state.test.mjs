import assert from "node:assert/strict";

import {
  buildSessionActivityRuntime,
  normalizeHistoryActivities,
} from "../src/session-runtime/activity-state.js";
import { createSessionTransportState } from "../src/session-runtime/session-transport-state.js";

export function runActivityStateTests() {
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
