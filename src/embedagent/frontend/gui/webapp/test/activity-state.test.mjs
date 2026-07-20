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
  assert.equal(activity.activities.length, 1);
  assert.equal(activity.activities[0].kind, "user");
  assert.equal(activity.activeTurnId, activity.activities[0].pendingTurnId);

  activity = reduceActivityState(activity, {
    type: "turn_started",
    turnId: "turn-1",
    userText: "Inspect parser",
    createdAt: "2026-06-27T00:00:01.000Z",
  });
  assert.equal(activity.activities[0].turnId, "turn-1");

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
    createdAt: "2026-06-27T00:00:02.500Z",
  });
  activity = reduceActivityState(activity, {
    type: "tool_finished",
    callId: "call-1",
    toolName: "read_file",
    label: "Read File",
    success: true,
    data: { path: "src/parser.c" },
    completedAt: "2026-06-27T00:00:02.900Z",
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
  assert.equal(activity.activities.filter((item) => item.kind === "reasoning").length, 1);
  assert.equal(activity.activities.filter((item) => item.kind === "tool").length, 1);
  assert.equal(activity.activities.filter((item) => item.kind === "assistant").length, 1);
  const toolActivity = activity.activities.find((item) => item.kind === "tool");
  assert.equal(toolActivity.createdAt, "2026-06-27T00:00:02.500Z");
  assert.equal(toolActivity.completedAt, "2026-06-27T00:00:02.900Z");
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
  assert.equal(activity.activities.some((item) => item.kind === "compact"), true);
  assert.equal(activity.activities.some((item) => item.kind === "system" && item.tone === "error"), true);
  assert.equal(activity.thinkingActive, false);

  let interactionActivity = reduceActivityState(createActivityState(), {
    type: "interaction_requested",
    id: "evt-approval",
    kind: "approval.requested",
    requestId: "perm-1",
    turnId: "turn-1",
    createdAt: "2026-07-02T10:00:00.000Z",
    payload: { summary: "Edit src/demo.c", toolName: "edit_file" },
  });
  assert.equal(interactionActivity.activities[0].kind, "interaction");
  assert.equal(interactionActivity.activities[0].sourceActivityKind, "approval.requested");
  assert.equal(interactionActivity.activities[0].requestId, "perm-1");
  assert.equal(interactionActivity.activities[0].status, "pending");

  interactionActivity = reduceActivityState(interactionActivity, {
    type: "interaction_resolved",
    id: "evt-approval-resolved",
    kind: "approval.resolved",
    requestId: "perm-1",
    turnId: "turn-1",
    createdAt: "2026-07-02T10:01:00.000Z",
    payload: { decision: "accept" },
  });
  assert.equal(interactionActivity.activities[0].status, "resolved");
  assert.equal(interactionActivity.activities[0].resolvedAt, "2026-07-02T10:01:00.000Z");

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
      restore_stop_reason: "interaction_expired",
    },
    sessionTransport: createSessionTransportState(),
    activities: [
      {
        id: "ask-1-requested",
        kind: "interaction",
        sourceActivityKind: "user-input.requested",
        requestId: "ask-1",
        status: "pending",
        payload: {
          questions: [{ id: "answer", question: "Continue?", options: [] }],
        },
      },
    ],
  });
  assert.equal(pendingRuntime.currentInteraction.interactionId, "ask-1");
  assert.equal(pendingRuntime.interactionNotice, null);
  assert.equal(
    pendingRuntime.t3TimelineRows.filter((row) => row.kind === "interaction").length,
    0,
  );
  assert.equal(
    pendingRuntime.t3TimelineRows.filter((row) => row.kind === "system_notice").length,
    0,
  );

  const snapshotPendingRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_user_input",
      pending_interaction_valid: true,
      pending_interaction: {
        interaction_id: "ask-snapshot",
        kind: "user_input",
        tool_name: "ask_user",
        questions: [
          {
            id: "answer",
            question: "Choose target?",
            options: [{ index: 1, label: "Python" }],
          },
        ],
      },
    },
    sessionTransport: createSessionTransportState(),
    activities: [],
  });
  assert.equal(snapshotPendingRuntime.currentInteraction.interactionId, "ask-snapshot");
  assert.equal(snapshotPendingRuntime.currentInteraction.question, "Choose target?");
  assert.equal(snapshotPendingRuntime.currentInteraction.options[0].label, "Python");
  assert.equal(snapshotPendingRuntime.interactionNotice, null);

  const denseActivities = [
    {
      id: "u-dense",
      kind: "user",
      turn_id: "turn-dense",
      content: "Review parser and compact context",
    },
    {
      id: "compact-dense",
      kind: "compact",
      turn_id: "turn-dense",
      content: "Older parser work summarized.",
      summarized_turns: 9,
      recent_turns: 3,
      approx_tokens_after: 5200,
    },
    ...Array.from({ length: 6 }, (_, index) => ({
      id: `tool-dense-${index + 1}`,
      kind: "tool",
      turn_id: "turn-dense",
      step_id: `step-dense-${index + 1}`,
      step_index: index + 1,
      tool_name: index % 2 === 0 ? "read_file" : "grep_text",
      tool_label: index % 2 === 0 ? "Read File" : "Search",
      status: "success",
      arguments: index % 2 === 0
        ? { path: `src/file_${index + 1}.c` }
        : { pattern: "parse", path: "src" },
      data: index % 2 === 0
        ? { path: `src/file_${index + 1}.c`, content_preview: "int main(void);" }
        : { matches: [{ path: "src/parser.c", line: index + 1, text: "parse();" }] },
    })),
    {
      id: "review-dense",
      kind: "command_result",
      command_name: "review",
      turn_id: "turn-dense",
      success: false,
      content: "Review found one parser issue in [src/parser.c:42](src/parser.c#L42).",
      data: {
        review: {
          findings: [
            {
              id: "finding-dense",
              severity: "high",
              title: "Parser can drop EOF",
              body: "EOF handling should preserve diagnostics.",
              file: "src/parser.c",
              line: 42,
            },
          ],
        },
      },
    },
    {
      id: "a-dense",
      kind: "assistant",
      turn_id: "turn-dense",
      step_id: "step-dense-6",
      step_index: 6,
      content: "Parser review complete.",
    },
  ];
  const denseRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-dense",
      status: "idle",
      current_mode: "build",
    },
    sessionTransport: createSessionTransportState(),
    activities: denseActivities,
  });
  const denseFold = denseRuntime.t3TimelineRows.find((row) => row.kind === "turn_fold");
  assert.ok(denseFold);
  assert.equal(denseFold.entries.filter((entry) => entry.kind === "work").length, 6);
  assert.equal(denseFold.entries.some((entry) => entry.kind === "context_summary"), true);
  const denseReview = denseRuntime.t3TimelineRows.find((row) => row.kind === "review_result");
  assert.ok(denseReview);
  assert.equal(denseReview.findings[0].file, "src/parser.c");
  assert.equal(denseReview.findings[0].line, 42);
}
