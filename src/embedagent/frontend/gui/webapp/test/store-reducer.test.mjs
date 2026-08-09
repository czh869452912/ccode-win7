import assert from "node:assert/strict";

import { initialState, reducer } from "../src/store.js";

export function runStoreReducerTests() {
  const limitedState = {
    ...initialState,
    terminationReason: "max_turns",
    turnsUsed: 8,
    maxTurns: 8,
  };
  const completed = reducer(limitedState, {
    type: "turn_ended",
    terminationReason: "completed",
    turnsUsed: 9,
    maxTurns: null,
  });
  assert.equal(completed.terminationReason, "completed");
  assert.equal(completed.turnsUsed, 9);
  assert.equal(completed.maxTurns, null);

  const capabilityState = reducer(initialState, {
    type: "session_capabilities_loaded",
    capabilities: { commands: [{ name: "help", usage: "/help", active: true }] },
  });
  assert.equal(capabilityState.sessionCapabilities.commands[0].usage, "/help");

  let contributionState = reducer(initialState, {
    type: "contribution_opened",
    kind: "files",
    label: "Files",
    rendererKey: "file_reference",
  });
  contributionState = reducer(contributionState, {
    type: "contribution_opened",
    kind: "preview",
    label: "Preview",
    rendererKey: "preview",
    resourceId: "http://127.0.0.1:5173",
  });
  assert.deepEqual(contributionState.contribution.items.map((item) => item.kind), ["files", "preview"]);

  const activated = reducer(contributionState, {
    type: "session_activated",
    sessionId: "session-b",
    snapshot: { session_id: "session-b", current_mode: "build" },
    activities: [],
  });
  assert.equal(activated.contribution.sessionId, "session-b");
  assert.deepEqual(activated.contribution.items, []);

  const diff = reducer(activated, {
    type: "diff_surface_opened",
    diffSurface: {
      title: "Patch",
      rawDiff: "--- a/demo.c\n+++ b/demo.c\n",
      files: [{ path: "demo.c", diff: "--- a/demo.c\n+++ b/demo.c\n" }],
    },
  });
  assert.equal(diff.diffSurface.title, "Patch");
  assert.equal(diff.contribution.items[0].rendererKey, "inline_diff");
  assert.equal(diff.contribution.activeId, "diff:current");

  const reset = reducer(diff, {
    type: "workspace_switched",
    bootstrap: { ...initialState.app, bootstrapLoaded: true },
  });
  assert.deepEqual(reset.contribution.items, []);
  assert.equal(reset.thread.currentSessionId, "");
}
