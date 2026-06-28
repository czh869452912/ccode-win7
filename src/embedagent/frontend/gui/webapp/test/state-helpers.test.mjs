import test from "node:test";
import assert from "node:assert/strict";

import {
  createTreeNode,
  injectChildren,
  normalizeSessionPayload,
  resolveTimelineAnchor,
  resolveVisiblePermission,
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

test("normalizeSessionPayload keeps status, mode, and transition display fields stable", () => {
  const snapshot = normalizeSessionPayload({
    session_id: "sess-1",
    status: "waiting_permission",
    current_mode: "debug",
    pending_interaction_valid: true,
    pending_interaction: {
      interaction_id: "perm-1",
      kind: "permission",
    },
    last_transition_reason: "aborted",
    last_transition_display_reason: "cancelled",
    last_transition_message: "tool execution interrupted",
    recent_transitions: [
      {
        reason: "aborted",
        display_reason: "cancelled",
        message: "tool execution interrupted",
      },
    ],
  });
  assert.equal(snapshot.session_id, "sess-1");
  assert.equal(snapshot.status, "waiting_permission");
  assert.equal(snapshot.current_mode, "debug");
  assert.equal(snapshot.pending_interaction.kind, "permission");
  assert.equal(snapshot.lastTransitionDisplayReason, "cancelled");
  assert.equal(snapshot.recentTransitions[0].displayReason, "cancelled");
});

test("resolveTimelineAnchor prefers explicit, active, then pending local user turns", () => {
  assert.equal(
    resolveTimelineAnchor({
      explicitTurnId: "turn-explicit",
      activeTurnId: "turn-active",
      timeline: [{ id: "user-pending", kind: "user", turnId: "" }],
    }),
    "turn-explicit",
  );
  assert.equal(
    resolveTimelineAnchor({
      explicitTurnId: "",
      activeTurnId: "turn-active",
      timeline: [{ id: "user-pending", kind: "user", turnId: "" }],
    }),
    "turn-active",
  );
  assert.equal(
    resolveTimelineAnchor({
      explicitTurnId: "",
      activeTurnId: "",
      timeline: [
        { id: "cmd-old", kind: "command_result", turnId: "" },
        { id: "user-pending", kind: "user", turnId: "", pendingTurnId: "pending-local" },
      ],
    }),
    "pending-local",
  );
});

test("resolveVisiblePermission uses explicit permission before snapshot fallback", () => {
  const explicit = { permission_id: "perm-explicit" };
  assert.equal(
    resolveVisiblePermission(explicit, {
      pending_interaction_valid: true,
      pending_interaction: { interaction_id: "perm-snapshot", kind: "permission" },
    }),
    explicit,
  );
  assert.deepEqual(
    resolveVisiblePermission(null, {
      pending_interaction_valid: true,
      pending_interaction: {
        interaction_id: "perm-1",
        kind: "permission",
        tool_name: "edit_file",
        category: "workspace_write",
      },
    }),
    {
      interaction_id: "perm-1",
      kind: "permission",
      tool_name: "edit_file",
      category: "workspace_write",
    },
  );
});
