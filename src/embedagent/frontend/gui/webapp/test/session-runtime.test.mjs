import assert from "node:assert/strict";

import {
  appendSessionEvent,
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
  assert.equal(gap.needsResync, true);

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
}
