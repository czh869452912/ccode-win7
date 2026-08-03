import assert from "node:assert/strict";

import { LOADER_REQUESTS } from "../src/app-runtime/session-loaders.js";
import { deriveSocketMessageEffects } from "../src/app-runtime/socket-message-effects.js";
import {
  createActivityState,
  reduceActivityState,
} from "../src/session-runtime/activity-reducer.js";
import {
  applySessionTransportEvent,
  createSessionTransportState,
} from "../src/session-runtime/session-transport-state.js";
import { summarizeChangedFiles } from "../src/session-runtime/t3-timeline.js";

function envelope(eventKind, payload, sequence = 1) {
  return {
    schema_version: 1,
    event_id: `evt-${sequence}`,
    session_id: "sess-active",
    sequence,
    event_kind: eventKind,
    timestamp: `2026-07-26T00:00:0${sequence}Z`,
    payload,
  };
}

function derive(type, data, options = {}) {
  return deriveSocketMessageEffects({
    type,
    data,
    currentSessionId: options.currentSessionId || "sess-active",
    sessionTransport: options.sessionTransport || createSessionTransportState(),
    makeId: options.makeId,
    nowIso: options.nowIso || (() => "2026-07-26T00:00:00Z"),
    diffPanelChrome: options.diffPanelChrome || {},
  });
}

function deriveEvent(eventKind, payload, sequence = 1, options = {}) {
  return derive("session_event", envelope(eventKind, payload, sequence), options);
}

export function runSocketMessageEffectsTests() {
  const status = deriveEvent("session.status", {
    session_snapshot: {
      session_id: "sess-active",
      status: "running",
      current_mode: "build",
    },
  });
  assert.equal(status.actions[0].type, "session_snapshot");
  assert.equal(status.actions[0].snapshot.session_id, "sess-active");
  assert.deepEqual(status.loaderRequests, [{ name: LOADER_REQUESTS.LOAD_SESSIONS }]);

  const transition = deriveEvent("transition.recorded", {
    termination_reason: "completed",
    display_reason: "completed",
    message: "Done.",
    turns_used: 10,
  });
  assert.deepEqual(transition.actions[0], {
    type: "turn_ended",
    terminationReason: "completed",
    terminationDisplayReason: "completed",
    terminationMessage: "Done.",
    turnsUsed: 10,
    maxTurns: null,
  });

  const stream = deriveEvent("assistant.delta", {
    text: "hello",
    turn_id: "turn-1",
    step_id: "step-1",
    step_index: 2,
  });
  assert.deepEqual(stream.actions, [
    {
      type: "assistant_delta",
      text: "hello",
      turnId: "turn-1",
      stepId: "step-1",
      stepIndex: 2,
      createdAt: "2026-07-26T00:00:01Z",
    },
  ]);

  const command = deriveEvent("command.result", {
    command_name: "custom_patch",
    success: true,
    message: "diff ready",
    log_label: "Patch ready",
    log_detail: "2 lines changed",
    data: {
      switch_session_id: "sess-next",
      read_model_invalidations: ["capabilities"],
      diff: "--- a/src/main.c\n+++ b/src/main.c\n@@ -1 +1 @@\n-old\n+new\n",
    },
    turn_id: "turn-1",
  });
  assert.equal(command.actions[0].type, "command_result");
  assert.equal(command.actions[0].createdAt, "2026-07-26T00:00:01Z");
  assert.equal(command.actions[1].type, "diff_surface_opened");
  assert.deepEqual(command.actions[2], {
    type: "log_event",
    label: "Patch ready",
    detail: "2 lines changed",
  });
  assert.deepEqual(command.loaderRequests, [
    { name: LOADER_REQUESTS.LOAD_SESSION, sessionId: "sess-next" },
    { name: LOADER_REQUESTS.LOAD_SESSION_CAPABILITIES },
  ]);

  const noCommandLog = deriveEvent("command.result", {
    command_name: "custom",
    success: true,
    message: "ok",
    data: {},
  });
  assert.deepEqual(noCommandLog.actions.map((action) => action.type), ["command_result"]);

  let transport = createSessionTransportState();
  let activity = createActivityState();
  let pendingInteraction = null;
  const sequence = [
    envelope(
      "turn.started",
      { turn_id: "turn-1", user_text: "Edit parser" },
      1,
    ),
    envelope(
      "tool.started",
      {
        call_id: "call-1",
        tool_name: "project_write",
        tool_label: "Project Write",
        arguments: { path: "src/parser.c" },
        turn_id: "turn-1",
        step_id: "step-1",
        step_index: 1,
      },
      2,
    ),
    envelope(
      "tool.finished",
      {
        call_id: "call-1",
        tool_name: "project_write",
        tool_label: "Project Write",
        success: false,
        error: "path does not exist",
        failure: {
          code: "path_missing",
          message: "path does not exist",
          retryable: false,
          source: "project_write",
        },
        data: {
          path: "src/parser.c",
          diff_preview:
            "--- a/src/parser.c\n+++ b/src/parser.c\n@@ -1 +1,2 @@\n-old\n+new\n+line\n",
        },
        read_model_invalidations: ["workspace_files", "source_control"],
        turn_id: "turn-1",
        step_id: "step-1",
        step_index: 1,
      },
      3,
    ),
    envelope(
      "approval.requested",
      {
        request_id: "perm-1",
        interaction_id: "perm-1",
        turn_id: "turn-1",
        request_kind: "file-change",
        summary: "Approve parser edit",
      },
      4,
    ),
    envelope(
      "approval.resolved",
      {
        request_id: "perm-1",
        interaction_id: "perm-1",
        turn_id: "turn-1",
        decision: "decline",
      },
      5,
    ),
    envelope(
      "session.finished",
      {
        session_snapshot: { session_id: "sess-active", status: "idle" },
      },
      6,
    ),
  ];

  for (const event of sequence) {
    const application = applySessionTransportEvent(transport, event);
    assert.equal(application.accepted, true);
    transport = application.state;
    const effects = derive("session_event", event, { sessionTransport: transport });
    for (const action of effects.actions) {
      activity = reduceActivityState(activity, action);
      if (action.type === "interaction_requested") pendingInteraction = action;
      if (action.type === "interaction_resolved") pendingInteraction = null;
    }
  }

  const toolRow = activity.activities.find((item) => item.kind === "tool");
  const diffSummary = summarizeChangedFiles([toolRow]);
  assert.equal(transport.lastAppliedSeq, 6);
  assert.equal(toolRow.status, "failed");
  assert.equal(toolRow.failure.code, "path_missing");
  assert.equal(pendingInteraction, null);
  assert.equal(diffSummary.additions, 2);
  assert.equal(diffSummary.deletions, 1);
  assert.deepEqual(toolRow.arguments, { path: "src/parser.c" });

  for (const legacyType of [
    "session_status",
    "stream_delta",
    "reasoning_delta",
    "thinking_state",
    "tool_start",
    "tool_finish",
    "command_result",
    "session_error",
    "plan_updated",
    "turn_start",
    "turn_end",
    "step_start",
    "step_end",
    "session_finished",
    "message",
  ]) {
    assert.deepEqual(derive(legacyType, { value: true }), {
      actions: [],
      transportEvents: [],
      loaderRequests: [],
    });
  }
}
