import assert from "node:assert/strict";

import { LOADER_REQUESTS } from "../src/app-runtime/session-loaders.js";
import { deriveSocketMessageEffects } from "../src/app-runtime/socket-message-effects.js";

function makeDeterministicIdFactory() {
  const counts = new Map();
  return (prefix) => {
    const next = (counts.get(prefix) || 0) + 1;
    counts.set(prefix, next);
    return `${prefix}-${next}`;
  };
}
function derive(type, data, options = {}) {
  return deriveSocketMessageEffects({
    type,
    data,
    currentSessionId: options.currentSessionId || "sess-active",
    sessionTransport: options.sessionTransport || { lastAppliedSeq: 4 },
    makeId: options.makeId || makeDeterministicIdFactory(),
    nowIso: options.nowIso || (() => "2026-06-18T00:00:00.000Z"),
  });
}

export function runSocketMessageEffectsTests() {
  const workspaceActive = derive("workspace_changed", {
    has_active_workspace: true,
    active_workspace: { id: "ws-1", path: "D:/work/demo", label: "demo" },
    workspaces: [{ id: "ws-1", path: "D:/work/demo", label: "demo" }],
  });
  assert.equal(workspaceActive.actions[0].type, "workspace_switched");
  assert.equal(workspaceActive.actions[0].bootstrap.hasActiveWorkspace, true);
  assert.deepEqual(workspaceActive.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_ACTIVE_WORKSPACE_DATA, sessionId: "", assumeWorkspace: true },
  ]);

  const workspaceInactive = derive("workspace_changed", { has_active_workspace: false });
  assert.equal(workspaceInactive.actions[0].type, "workspace_switched");
  assert.equal(workspaceInactive.actions[1].type, "source_control_reset");
  assert.deepEqual(workspaceInactive.loaderRequests, []);

  const status = derive("session_status", {
    session_id: "sess-1",
    status: "running",
    current_mode: "build",
  });
  assert.equal(status.actions[0].type, "session_snapshot");
  assert.equal(status.actions[0].snapshot.session_id, "sess-1");
  assert.equal(Object.hasOwn(status.actions[0], "replay" + "StatePatch"), false);
  assert.deepEqual(status.actions[1], { type: "log_event", label: "session_status", detail: "running" });
  assert.deepEqual(status.loaderRequests, [{ name: LOADER_REQUESTS.LOAD_SESSIONS }]);

  const turnEvent = derive("session_event", {
    event_id: "evt-turn",
    seq: 5,
    event_kind: "turn.started",
    payload: { turn_id: "turn-1", user_text: "inspect parser" },
  });
  assert.equal(turnEvent.transportEvents.length, 1);
  assert.equal(turnEvent.transportEvents[0].event_id, "evt-turn");
  assert.deepEqual(turnEvent.actions, [
    {
      type: "turn_started",
      turnId: "turn-1",
      userText: "inspect parser",
      createdAt: "2026-06-18T00:00:00.000Z",
    },
  ]);

  const transitionEvent = derive("session_event", {
    event_id: "evt-transition",
    seq: 5,
    event_kind: "transition.recorded",
    payload: {
      termination_reason: "max_turns",
      display_reason: "max turns reached",
      message: "Stopped after max turns.",
      turns_used: 8,
      max_turns: 8,
    },
  });
  assert.equal(transitionEvent.actions[0].type, "turn_ended");
  assert.equal(transitionEvent.actions[0].terminationDisplayReason, "max turns reached");
  assert.equal(transitionEvent.actions[0].turnsUsed, 8);

  const approvalRequested = derive("session_event", {
    event_id: "evt-approval",
    seq: 7,
    event_kind: "approval.requested",
    payload: {
      request_id: "perm-1",
      interaction_id: "perm-1",
      turn_id: "turn-1",
      tool_name: "edit_file",
      request_kind: "file-change",
      summary: "Edit src/demo.c",
      details: { path: "src/demo.c" },
    },
  });
  assert.equal(approvalRequested.actions[0].type, "interaction_requested");
  assert.equal(approvalRequested.actions[0].kind, "approval.requested");
  assert.equal(approvalRequested.actions[0].requestId, "perm-1");
  assert.equal(approvalRequested.actions[0].payload.toolName, "edit_file");
  assert.deepEqual(approvalRequested.loaderRequests, []);

  const userInputRequested = derive("session_event", {
    event_id: "evt-user-input",
    seq: 8,
    event_kind: "user-input.requested",
    payload: {
      request_id: "ask-1",
      interaction_id: "ask-1",
      turn_id: "turn-1",
      questions: [{ id: "answer", question: "Continue?", options: [{ index: 1, label: "Yes" }] }],
    },
  });
  assert.equal(userInputRequested.actions[0].type, "interaction_requested");
  assert.equal(userInputRequested.actions[0].kind, "user-input.requested");
  assert.equal(userInputRequested.actions[0].requestId, "ask-1");
  assert.deepEqual(userInputRequested.loaderRequests, []);

  const approvalResolved = derive("session_event", {
    event_id: "evt-approval-resolved",
    seq: 9,
    event_kind: "approval.resolved",
    payload: {
      request_id: "perm-1",
      interaction_id: "perm-1",
      turn_id: "turn-1",
      decision: "accept",
    },
  });
  assert.equal(approvalResolved.actions[0].type, "interaction_resolved");
  assert.equal(approvalResolved.actions[0].kind, "approval.resolved");
  assert.equal(approvalResolved.actions[0].requestId, "perm-1");

  const turnEndWithoutSafetyLimit = derive("turn_end", {
    termination_reason: "completed",
    display_reason: "completed",
    message: "Done.",
    turns_used: 10,
  });
  assert.equal(turnEndWithoutSafetyLimit.actions[0].type, "turn_ended");
  assert.equal(turnEndWithoutSafetyLimit.actions[0].maxTurns, null);
  assert.equal(turnEndWithoutSafetyLimit.actions[0].turnsUsed, 10);
  assert.equal(turnEndWithoutSafetyLimit.actions[0].terminationReason, "completed");

  const streamDelta = derive("stream_delta", {
    text: "hello",
    turn_id: "turn-1",
    step_id: "step-1",
    step_index: 2,
  });
  assert.deepEqual(streamDelta.actions, [
    {
      type: "assistant_delta",
      text: "hello",
      turnId: "turn-1",
      stepId: "step-1",
      stepIndex: 2,
      createdAt: "2026-06-18T00:00:00.000Z",
    },
  ]);

  const toolFinish = derive("tool_finish", {
    call_id: "call-1",
    tool_name: "project_write",
    tool_label: "Project Write",
    success: true,
    data: { path: "src/main.c" },
    read_model_invalidations: ["workspace_files"],
    turn_id: "turn-1",
    step_id: "step-1",
    step_index: 1,
  });
  assert.equal(toolFinish.actions[0].type, "tool_finished");
  assert.equal(toolFinish.actions[0].toolName, "project_write");
  assert.deepEqual(toolFinish.actions[0].readModelInvalidations, ["workspace_files"]);
  assert.equal(toolFinish.actions[0].completedAt, "2026-06-18T00:00:00.000Z");
  assert.deepEqual(toolFinish.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_FILE_CHILDREN, path: "." },
  ]);

  const toolFinishWithoutInvalidation = derive("tool_finish", {
    call_id: "call-2",
    tool_name: "edit_file",
    tool_label: "Edit File",
    success: true,
    data: { path: "src/main.c" },
  });
  assert.deepEqual(toolFinishWithoutInvalidation.loaderRequests, []);

  const permission = derive("permission_request", {
    permission_id: "perm-1",
    session_id: "sess-active",
    tool_name: "edit_file",
    category: "workspace_write",
    reason: "Allow edit",
    details: { path: "src/main.c" },
    turn_id: "turn-1",
    step_id: "step-2",
    step_index: 2,
  });
  assert.deepEqual(permission.actions, []);
  assert.deepEqual(permission.transportEvents, []);
  assert.deepEqual(permission.loaderRequests, []);

  const userInput = derive("user_input_request", {
    request_id: "input-1",
    session_id: "sess-active",
    tool_name: "ask_user",
    question: "Which parser mode?",
    options: [{ index: 1, text: "Strict" }],
    turn_id: "turn-1",
  });
  assert.deepEqual(userInput.actions, []);
  assert.deepEqual(userInput.transportEvents, []);
  assert.deepEqual(userInput.loaderRequests, []);

  const rawPermission = derive("permission_request", {
    permission_id: "perm-raw",
    tool_name: "edit_file",
    reason: "Raw request should not create durable activity",
  });
  assert.equal(rawPermission.actions.some((action) => action.type === "append_activity_item"), false);
  assert.equal(rawPermission.actions.some((action) => action.type === "activity_reset"), false);

  const commandDiff = derive("command_result", {
    command_name: "diff",
    success: true,
    message: "diff ready",
    data: { diff: "--- a/src/main.c\n+++ b/src/main.c\n@@ -1 +1 @@\n-int a;\n+int b;\n" },
    turn_id: "turn-1",
  });
  assert.equal(commandDiff.actions[0].type, "command_result");
  assert.equal(commandDiff.actions[0].createdAt, "2026-06-18T00:00:00.000Z");
  assert.equal(commandDiff.actions[1].type, "diff_surface_opened");
  assert.equal(commandDiff.actions[1].diffSurface.title, "Git Diff");
  assert.deepEqual(commandDiff.actions[commandDiff.actions.length - 1], {
    type: "log_event",
    label: "command: /diff",
    detail: "ok",
  });

  const commandResume = derive("command_result", {
    command_name: "resume",
    success: true,
    data: { switch_session_id: "sess-next" },
  });
  assert.deepEqual(commandResume.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_SESSION, sessionId: "sess-next" },
  ]);

  const commandResourcesReload = derive("command_result", {
    command_name: "resources",
    success: true,
    data: { read_model_invalidations: ["capabilities"], counts: { skills: 1 } },
  });
  assert.deepEqual(commandResourcesReload.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_SESSION_CAPABILITIES },
  ]);

  const commandWorkspace = derive("command_result", {
    command_name: "workspace",
    success: true,
    data: { active: "D:/work/demo" },
  });
  assert.equal(commandWorkspace.actions[1].type, "preview_loaded");
  assert.equal(commandWorkspace.actions[1].preview.kind, "workspace");

  const commandRecipes = derive("command_result", {
    command_name: "recipes",
    success: true,
    data: { items: [{ id: "build" }] },
  });
  assert.equal(commandRecipes.actions[1].type, "recipes_loaded");
  assert.deepEqual(commandRecipes.actions[2], { type: "set_inspector", value: "run" });

  const finished = derive("session_finished", {
    session_snapshot: { session_id: "sess-active", status: "completed" },
  });
  assert.equal(finished.actions[0].type, "stream_completed");
  assert.equal(finished.actions[1].type, "session_snapshot");
  assert.deepEqual(finished.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_SESSIONS },
    { name: LOADER_REQUESTS.LOAD_TASKS, sessionId: "sess-active" },
  ]);

  const compacted = derive("message", {
    id: "compact-1",
    type: "CONTEXT_COMPACTED",
    content: "Context compacted.",
    metadata: {
      recent_turns: 2,
      summarized_turns: 5,
      approx_tokens_after: 4096,
      turn_id: "turn-1",
      step_id: "step-3",
      step_index: 3,
    },
  });
  assert.equal(compacted.actions[0].type, "context_compacted");
  assert.equal(compacted.actions[0].summarizedTurns, 5);

  const malformed = deriveSocketMessageEffects();
  assert.deepEqual(malformed, { actions: [], transportEvents: [], loaderRequests: [] });
  assert.deepEqual(derive("unknown_message", { value: true }), {
    actions: [],
    transportEvents: [],
    loaderRequests: [],
  });
}
