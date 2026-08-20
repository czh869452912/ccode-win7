import assert from "node:assert/strict";

import {
  capRetryAttempt,
  createSessionTransportState,
  isSessionEventEnvelope,
  projectTransportView,
} from "../src/session-runtime/session-transport-state.js";
import { buildSessionActivityRuntime } from "../src/session-runtime/activity-state.js";

function envelope(sessionId, sequence, eventId) {
  return {
    schema_version: 2,
    session_id: sessionId,
    event_id: eventId,
    sequence,
    event_kind: "step.started",
    timestamp: "2026-08-03T00:00:00Z",
    payload: {},
  };
}

export function runSessionRuntimeTests() {
  assert.equal(isSessionEventEnvelope(envelope("s-1", 1, "evt-1")), true);

  const runtime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_permission",
    },
    sessionTransport: createSessionTransportState(),
    activities: [
      {
        id: "int-1-requested",
        kind: "interaction",
        sourceActivityKind: "approval.requested",
        requestId: "int-1",
        status: "pending",
        payload: {
          toolName: "edit_file",
          reason: "need write access",
          details: {},
        },
      },
    ],
  });
  assert.equal(runtime.currentInteraction.interactionId, "int-1");
  assert.equal(runtime.timelineView.some((item) => item.kind === "permission"), false);
  assert.equal(runtime.sessionStatusView.mode, "");

  const reloadRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "running",
      current_mode: "build",
      pending_interaction: null,
    },
    sessionTransport: {
      ...createSessionTransportState(),
      reloadState: "reload_required",
      events: [],
    },
    activities: [],
  });
  assert.equal(reloadRuntime.transportView.reloadState, "reload_required");

  const experienceRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-experience",
      status: "idle",
      current_mode: "build",
      turnExperience: {
        status: "blocked",
        completed: [{ kind: "file_created", path: "README.md" }],
        unverified: [{ kind: "validation_missing", message: "Created files have not been validated." }],
        next_steps: ["Run validation for the changed files."],
      },
    },
    sessionTransport: createSessionTransportState(),
  });
  const experienceRow = experienceRuntime.timelineRows.find((row) => row.id === "turn-experience-summary");
  assert.equal(experienceRow.kind, "system_notice");
  assert.equal(experienceRow.tone, "warning");
  assert.equal(experienceRow.content.includes("Done: file_created README.md"), true);
  assert.equal(experienceRow.content.includes("Next: Run validation for the changed files."), true);

  const transportView = projectTransportView({
    transportState: {
      ...createSessionTransportState({ connectionState: "open" }),
      lastAppliedSeq: 7,
      reloadState: "healthy",
    },
  });
  assert.deepEqual(transportView, {
    connectionState: "open",
    reloadState: "healthy",
    lastAppliedSeq: 7,
  });

  const interactionRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_user_input",
    },
    sessionTransport: createSessionTransportState(),
    activities: [
      {
        id: "int-2-requested",
        kind: "interaction",
        sourceActivityKind: "user-input.requested",
        requestId: "int-2",
        status: "pending",
        payload: {
          questions: [
            {
              id: "answer",
              question: "继续吗？",
              options: [{ index: 1, text: "继续" }],
            },
          ],
        },
      },
    ],
  });
  assert.equal(interactionRuntime.currentInteraction.interactionId, "int-2");
  assert.equal(interactionRuntime.timelineItems.length, 1);
  assert.equal(interactionRuntime.timelineRows.filter((row) => row.kind === "interaction").length, 0);

  const ignoredTransportEventRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "build",
      pending_interaction: null,
    },
    sessionTransport: {
      ...createSessionTransportState(),
      events: [
        {
          schema_version: 2,
          session_id: "sess-1",
          event_id: "evt-ignored",
          sequence: 1,
          event_kind: "approval.requested",
          timestamp: "2026-04-04T00:01:00Z",
          payload: {
            interaction_id: "int-ignored",
            kind: "user_input",
            question: "ignored",
          },
        },
      ],
    },
    activities: [],
  });
  assert.equal(ignoredTransportEventRuntime.timelineItems.length, 0);

  const dedupedInteractionRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_user_input",
    },
    sessionTransport: createSessionTransportState(),
    activities: [
      {
        id: "local-user-input",
        kind: "interaction",
        sourceActivityKind: "user-input.requested",
        requestId: "ask-dedup",
        status: "pending",
        payload: {
          toolName: "ask_user",
          questions: [{ id: "answer", question: "Continue?", options: [] }],
        },
      },
    ],
  });
  assert.equal(
    dedupedInteractionRuntime.timelineItems.filter((item) => item.kind === "interaction").length,
    1,
  );
  assert.equal(dedupedInteractionRuntime.timelineRows.filter((row) => row.kind === "interaction").length, 0);

  const commandRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "build",
      pending_interaction: null,
    },
    sessionTransport: createSessionTransportState(),
    activities: [
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

  const thinkingRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-thinking",
      status: "running",
      current_mode: "build",
    },
    sessionTransport: createSessionTransportState(),
    activities: [
      {
        id: "u-thinking-runtime",
        kind: "user",
        content: "think in runtime",
        turnId: "turn-runtime",
      },
    ],
    activeTurnId: "turn-runtime",
    thinkingActive: true,
  });
  assert.equal(thinkingRuntime.timelineRows.some((row) => row.kind === "working"), true);

  const detachedRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "build",
      pending_interaction: null,
    },
    sessionTransport: createSessionTransportState(),
    activities: [
      { id: "turn-1-user", kind: "user", content: "hello", turnId: "turn-1" },
      { id: "detached-tool", kind: "tool", toolName: "read_file", turnId: "turn-1", stepId: "", status: "success" },
    ],
  });
  assert.equal(detachedRuntime.timelineView[0].trailingTurnItems[0].id, "detached-tool");

  const malformedEnvelope = isSessionEventEnvelope({
    schema_version: 2,
    session_id: "sess-1",
    event_id: "evt-bad",
    sequence: 1,
    event_kind: "",
    timestamp: "2026-04-04T00:02:00Z",
    payload: null,
  });
  assert.equal(malformedEnvelope, false);

  const retryState = capRetryAttempt(200);
  assert.equal(retryState, 20);

  const expiredRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_permission",
      current_mode: "build",
      pending_interaction_valid: false,
      pending_interaction: {
        interaction_id: "int-expired",
        kind: "permission",
        tool_name: "edit_file",
      },
    },
    sessionTransport: createSessionTransportState(),
    activities: [],
  });
  assert.equal(expiredRuntime.currentInteraction, null);
  assert.equal(expiredRuntime.interactionNotice.kind, "expired");

  const restoredExpiredRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "idle",
      current_mode: "build",
      pending_interaction: null,
      restore_stop_reason: "interaction_expired",
    },
    sessionTransport: createSessionTransportState(),
    activities: [],
  });
  assert.equal(restoredExpiredRuntime.currentInteraction, null);
  assert.equal(restoredExpiredRuntime.interactionNotice.kind, "expired");

  const resumedActiveInteractionRuntime = buildSessionActivityRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_user_input",
      current_mode: "build",
      restore_stop_reason: "interaction_expired",
    },
    sessionTransport: createSessionTransportState(),
    activities: [
      {
        id: "int-live-requested",
        kind: "interaction",
        sourceActivityKind: "user-input.requested",
        requestId: "int-live",
        status: "pending",
        payload: {
          questions: [
            {
              id: "answer",
              question: "继续吗？",
              options: [{ index: 1, text: "继续" }],
            },
          ],
        },
      },
    ],
  });
  assert.equal(resumedActiveInteractionRuntime.currentInteraction.interactionId, "int-live");
  assert.equal(resumedActiveInteractionRuntime.interactionNotice, null);
}
