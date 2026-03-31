import test from "node:test";
import assert from "node:assert/strict";

import {
  createTreeNode,
  injectChildren,
  normalizeSessionPayload,
  timelineFromEvents,
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
