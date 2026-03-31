import assert from "node:assert/strict";

import { initialState, reducer } from "../src/store.js";
import {
  createTreeNode,
  injectChildren,
  normalizeSessionPayload,
  timelineFromEvents,
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
  });
  assert.equal(snapshot.status, "waiting_permission");
  assert.equal(snapshot.current_mode, "debug");
  assert.equal(snapshot.has_pending_permission, true);

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

  console.log("frontend helper checks passed");
}

main();
