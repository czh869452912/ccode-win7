import test from "node:test";
import assert from "node:assert/strict";

import {
  createTreeNode,
  describeProjectionBadge,
  injectChildren,
  normalizeSessionPayload,
  timelineFromEvents,
  timelineFromTurns,
} from "../src/state-helpers.js";

test("injectChildren loads nested file tree children in place", () => {
  const root = [createTreeNode({ path: "src", name: "src", kind: "dir", has_children: true })];
  const next = injectChildren(root, "src", [
    { path: "src/pkg", name: "pkg", kind: "dir", has_children: true },
    { path: "src/main.c", name: "main.c", kind: "file", has_children: false },
  ]);
  assert.equal(next[0].childrenLoaded, true);
  assert.equal(next[0].children.length, 2);
  assert.equal(next[0].children[0].path, "src/pkg");
});

test("timelineFromEvents preserves tool lifecycle and final assistant text", () => {
  const events = [
    { event_id: "evt-1", event: "turn_started", payload: { text: "hello" } },
    { event_id: "evt-2", event: "tool_started", payload: { call_id: "call-1", tool_name: "read_file", tool_label: "Read File", progress_renderer_key: "file", result_renderer_key: "file", arguments: { path: "README.md" } } },
    { event_id: "evt-3", event: "tool_finished", payload: { call_id: "call-1", tool_name: "read_file", tool_label: "Read File", progress_renderer_key: "file", result_renderer_key: "file", success: true, data: { path: "README.md" } } },
    { event_id: "evt-4", event: "session_finished", payload: { final_text: "done" } },
  ];
  const timeline = timelineFromEvents(events);
  assert.equal(timeline[0].kind, "user");
  assert.equal(timeline[1].id, "call-1");
  assert.equal(timeline[1].status, "success");
   assert.equal(timeline[1].label, "Read File");
   assert.equal(timeline[1].resultRendererKey, "file");
  assert.equal(timeline[2].kind, "assistant");
  assert.equal(timeline[2].content, "done");
});

test("timelineFromEvents keeps command results for review workflows", () => {
  const timeline = timelineFromEvents([
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
  assert.equal(timeline[0].kind, "command_result");
  assert.equal(timeline[0].commandName, "review");
});

test("normalizeSessionPayload keeps status and mode stable", () => {
  const snapshot = normalizeSessionPayload({
    session_id: "sess-1",
    status: "waiting_permission",
    current_mode: "debug",
    has_pending_permission: true,
  });
  assert.equal(snapshot.session_id, "sess-1");
  assert.equal(snapshot.status, "waiting_permission");
  assert.equal(snapshot.current_mode, "debug");
  assert.equal(snapshot.has_pending_permission, true);
});

test("normalizeSessionPayload preserves display-oriented transition fields", () => {
  const snapshot = normalizeSessionPayload({
    session_id: "sess-2",
    status: "idle",
    last_transition_reason: "aborted",
    last_transition_display_reason: "cancelled",
    last_transition_message: "tool execution interrupted",
    recent_transitions: [
      {
        reason: "aborted",
        display_reason: "cancelled",
        message: "tool execution interrupted",
      },
      {
        reason: "guard_stop",
        display_reason: "guard",
        message: "too many repeated failures",
      },
    ],
  });
  assert.equal(snapshot.lastTransitionReason, "aborted");
  assert.equal(snapshot.lastTransitionDisplayReason, "cancelled");
  assert.equal(snapshot.lastTransitionMessage, "tool execution interrupted");
  assert.equal(snapshot.recentTransitions.length, 2);
  assert.equal(snapshot.recentTransitions[0].displayReason, "cancelled");
  assert.equal(snapshot.recentTransitions[0].display_reason, "cancelled");
});

test("timelineFromTurns expands one user turn into multiple agent steps", () => {
  const timeline = timelineFromTurns([
    {
      turn_id: "turn-1",
      user_text: "analyze demo",
      projection_kind: "step_events",
      steps: [
        {
          step_id: "step-1",
          projection_kind: "recorded_step",
          synthetic: false,
          reasoning: "inspect file",
          tool_calls: [
            {
              call_id: "call-1",
              tool_name: "read_file",
              tool_label: "Read File",
              status: "success",
              arguments: { path: "demo.c" },
              data: { path: "demo.c" },
            },
          ],
          assistant_text: "",
        },
        {
          step_id: "step-2",
          projection_kind: "recorded_step",
          synthetic: false,
          reasoning: "summarize result",
          assistant_text: "done",
          tool_calls: [],
        },
      ],
    },
  ], [], { projectionSource: "step_events" });
  assert.equal(timeline[0].kind, "user");
  assert.equal(timeline[0].projectionSource, "step_events");
  assert.equal(timeline[1].stepId, "step-1");
  assert.equal(timeline[1].kind, "reasoning");
  assert.equal(timeline[1].projectionKind, "recorded_step");
  assert.equal(timeline[1].synthetic, false);
  assert.equal(timeline[2].stepId, "step-1");
  assert.equal(timeline[2].kind, "tool");
  assert.equal(timeline[3].stepId, "step-2");
  assert.equal(timeline[3].kind, "reasoning");
  assert.equal(timeline[4].stepId, "step-2");
  assert.equal(timeline[4].kind, "assistant");
});

test("timelineFromTurns preserves synthetic step projection metadata", () => {
  const timeline = timelineFromTurns([
    {
      turn_id: "turn-legacy",
      user_text: "legacy analyze",
      projection_kind: "turn_events",
      steps: [
        {
          step_id: "turn-legacy-step-1",
          step_index: 1,
          projection_kind: "synthetic_single_step",
          synthetic: true,
          reasoning: "legacy reasoning",
          assistant_text: "legacy done",
          tool_calls: [],
        },
      ],
    },
  ], [], { projectionSource: "turn_events" });
  assert.equal(timeline[0].projectionSource, "turn_events");
  assert.equal(timeline[1].projectionKind, "synthetic_single_step");
  assert.equal(timeline[1].synthetic, true);
  assert.equal(timeline[2].projectionKind, "synthetic_single_step");
  assert.equal(timeline[2].synthetic, true);
});

test("describeProjectionBadge hides recorded steps and labels synthetic projections", () => {
  assert.equal(
    describeProjectionBadge({
      projectionSource: "step_events",
      projectionKind: "recorded_step",
      synthetic: false,
    }),
    null,
  );
  assert.deepEqual(
    describeProjectionBadge({
      projectionSource: "turn_events",
      projectionKind: "synthetic_single_step",
      synthetic: true,
    }),
    {
      label: "synthetic",
      detail: "turn projection",
    },
  );
});
