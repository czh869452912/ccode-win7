import assert from "node:assert/strict";

import {
  appendSessionEvent,
  capRetryAttempt,
  createSessionEventLog,
} from "../src/session-runtime/event-log.js";
import { projectSessionRuntime } from "../src/session-runtime/projector.js";

export function runSessionRuntimeTests() {
  const initial = createSessionEventLog();
  const first = appendSessionEvent(initial, {
    session_id: "sess-1",
    event_id: "evt-1",
    seq: 1,
    event_kind: "turn.started",
    created_at: "2026-04-04T00:00:00Z",
    payload: { turn_id: "turn-1", user_text: "hello" },
  });
  const gap = appendSessionEvent(first, {
    session_id: "sess-1",
    event_id: "evt-3",
    seq: 3,
    event_kind: "step.started",
    created_at: "2026-04-04T00:00:01Z",
    payload: { turn_id: "turn-1", step_id: "step-1" },
  });
  assert.equal(gap.replayState, "replay_needed");

  const runtime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_permission",
      pending_interaction: {
        interaction_id: "int-1",
        kind: "permission",
        tool_name: "edit_file",
        reason: "need write access",
      },
    },
    eventLog: createSessionEventLog(),
  });
  assert.equal(runtime.currentInteraction.interaction_id, "int-1");
  assert.equal(runtime.timelineView.some((item) => item.kind === "permission"), false);

  const replayRuntime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "running",
      current_mode: "code",
      timeline_replay_status: "reload_required",
      pending_interaction: null,
    },
    eventLog: {
      ...createSessionEventLog(),
      replayState: "reload_required",
      events: [],
    },
    bootstrapTimeline: [],
  });
  assert.equal(replayRuntime.transportView.replayState, "reload_required");

  const interactionRuntime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_user_input",
      pending_interaction: {
        interaction_id: "int-2",
        kind: "user_input",
        question: "继续吗？",
        options: [{ index: 1, text: "继续" }],
      },
    },
    eventLog: {
      ...createSessionEventLog(),
      events: [
        {
          session_id: "sess-1",
          event_id: "evt-10",
          seq: 10,
          event_kind: "interaction.created",
          created_at: "2026-04-04T00:01:00Z",
          payload: {
            interaction_id: "int-2",
            kind: "user_input",
            question: "继续吗？",
          },
        },
      ],
    },
  });
  assert.equal(interactionRuntime.currentInteraction.interaction_id, "int-2");
  assert.equal(interactionRuntime.timelineItems[0].kind, "interaction_requested");

  const commandRuntime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "code",
      pending_interaction: null,
    },
    eventLog: createSessionEventLog(),
    bootstrapTimeline: [
      {
        id: "cmd-1",
        kind: "command_result",
        commandName: "review",
        content: "done",
        turnId: "",
        projectionSource: "raw_events",
      },
    ],
  });
  assert.equal(commandRuntime.timelineView[0].sessionFallbackItems[0].kind, "command_result_fallback");

  const detachedRuntime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "code",
      pending_interaction: null,
    },
    eventLog: createSessionEventLog(),
    bootstrapTimeline: [
      { id: "turn-1-user", kind: "user", content: "hello", turnId: "turn-1" },
      { id: "detached-tool", kind: "tool", toolName: "read_file", turnId: "turn-1", stepId: "", status: "success" },
    ],
  });
  assert.equal(detachedRuntime.timelineView[0].trailingTurnItems[0].id, "detached-tool");

  const malformedEventLog = appendSessionEvent(createSessionEventLog(), {
    session_id: "sess-1",
    event_id: "evt-bad",
    seq: 1,
    event_kind: "",
    created_at: "2026-04-04T00:02:00Z",
    payload: null,
  });
  assert.equal(malformedEventLog.replayState, "degraded");

  const retryState = capRetryAttempt(200);
  assert.equal(retryState, 20);

  const expiredRuntime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_permission",
      current_mode: "code",
      pending_interaction_valid: false,
      pending_interaction: {
        interaction_id: "int-expired",
        kind: "permission",
        tool_name: "edit_file",
      },
    },
    eventLog: createSessionEventLog(),
    bootstrapTimeline: [],
  });
  assert.equal(expiredRuntime.currentInteraction, null);
  assert.equal(expiredRuntime.interactionNotice.kind, "expired");

  const restoredExpiredRuntime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "code",
      pending_interaction: null,
      restore_stop_reason: "interaction_expired",
    },
    eventLog: createSessionEventLog(),
    bootstrapTimeline: [],
  });
  assert.equal(restoredExpiredRuntime.currentInteraction, null);
  assert.equal(restoredExpiredRuntime.interactionNotice.kind, "expired");

  const resumedActiveInteractionRuntime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_user_input",
      current_mode: "code",
      pending_interaction_valid: true,
      pending_interaction: {
        interaction_id: "int-live",
        kind: "user_input",
        question: "继续吗？",
        options: [{ index: 1, text: "继续" }],
      },
      restore_stop_reason: "interaction_expired",
    },
    eventLog: createSessionEventLog(),
    bootstrapTimeline: [],
  });
  assert.equal(resumedActiveInteractionRuntime.currentInteraction.interaction_id, "int-live");
  assert.equal(resumedActiveInteractionRuntime.interactionNotice, null);
}
