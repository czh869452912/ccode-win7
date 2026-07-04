import assert from "node:assert/strict";

import {
  canSwitchWorkspace,
  normalizeAppBootstrap,
  normalizeWorkspaceRecord,
  resetWorkspaceScopedState,
} from "../src/app-workspaces.js";
import { createComposerState, readComposerDraft } from "../src/composer/composer-state.js";

export function runAppWorkspaceTests() {
  const workspace = normalizeWorkspaceRecord({
    id: "ws-1",
    path: "D:/work/demo",
    label: "",
    exists: true,
    created_at: "2026-06-15T10:00:00Z",
    last_opened_at: "2026-06-15T11:00:00Z",
  });
  assert.equal(workspace.id, "ws-1");
  assert.equal(workspace.label, "demo");
  assert.equal(workspace.exists, true);

  const bootstrap = normalizeAppBootstrap({
    workspaces: [workspace],
    active_workspace: workspace,
    has_active_workspace: true,
    last_error: "",
  });
  assert.equal(bootstrap.workspaces.length, 1);
  assert.equal(bootstrap.activeWorkspace.id, "ws-1");
  assert.equal(bootstrap.hasActiveWorkspace, true);

  const idleSwitch = canSwitchWorkspace({
    snapshot: { status: "idle", pending_interaction_valid: false },
  });
  assert.equal(idleSwitch.allowed, true);

  const runningSwitch = canSwitchWorkspace({
    snapshot: { status: "running", pending_interaction_valid: false },
  });
  assert.equal(runningSwitch.allowed, false);
  assert.equal(runningSwitch.reason, "active_thread");

  const pendingSwitch = canSwitchWorkspace({
    snapshot: {
      status: "waiting_user_input",
      pending_interaction_valid: true,
      pending_interaction: { interaction_id: "ask-1" },
    },
  });
  assert.equal(pendingSwitch.allowed, false);
  assert.equal(pendingSwitch.reason, "pending_interaction");

  const reset = resetWorkspaceScopedState({
    thread: {
      sessions: [{ session_id: "sess-1" }],
      currentSessionId: "sess-1",
      historyIntegrity: { status: "partial" },
    },
    composer: createComposerState(),
    snapshot: { session_id: "sess-1" },
    activities: [{ id: "row-1" }],
    tasks: [{ id: 1 }],
    artifacts: [{ id: "a" }],
    preview: { title: "README.md" },
    diffSurface: { title: "Diff" },
    fileTree: [{ id: "src" }],
    permissionContext: { session_id: "sess-1" },
    runOutput: [{ label: "old" }],
    activeTurnId: "turn-1",
    sourceControl: { status: "ready", selectedPath: "src/main.c" },
  });
  assert.deepEqual(reset.thread.sessions, []);
  assert.equal(reset.thread.currentSessionId, "");
  assert.equal(reset.thread.historyIntegrity, null);
  assert.equal(readComposerDraft(reset), "");
  assert.equal(reset.snapshot, null);
  assert.deepEqual(reset.activities, []);
  assert.deepEqual(reset.tasks, []);
  assert.deepEqual(reset.artifacts, []);
  assert.equal(reset.preview, null);
  assert.equal(reset.diffSurface, null);
  assert.deepEqual(reset.fileTree, []);
  assert.equal(reset.permissionContext, null);
  assert.deepEqual(reset.runOutput, []);
  assert.equal(reset.activeTurnId, "");
  assert.equal(reset.sourceControl.status, "idle");
  assert.equal(reset.sourceControl.selectedPath, "");
}
