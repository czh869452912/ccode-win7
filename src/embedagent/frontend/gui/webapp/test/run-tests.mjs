import assert from "node:assert/strict";

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
    { event_id: "evt-2", event: "tool_started", payload: { call_id: "call-1", tool_name: "read_file", arguments: { path: "README.md" } } },
    { event_id: "evt-3", event: "tool_finished", payload: { call_id: "call-1", tool_name: "read_file", success: true, data: { path: "README.md" } } },
    { event_id: "evt-4", event: "session_finished", payload: { final_text: "done" } },
  ]);
  assert.equal(timeline[1].id, "call-1");
  assert.equal(timeline[1].status, "success");
  assert.equal(timeline[2].content, "done");

  const snapshot = normalizeSessionPayload({
    session_id: "sess-1",
    status: "waiting_permission",
    current_mode: "debug",
    has_pending_permission: true,
  });
  assert.equal(snapshot.status, "waiting_permission");
  assert.equal(snapshot.current_mode, "debug");
  assert.equal(snapshot.has_pending_permission, true);

  console.log("frontend helper checks passed");
}

main();
