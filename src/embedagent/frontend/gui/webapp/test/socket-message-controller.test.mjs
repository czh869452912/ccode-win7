import assert from "node:assert/strict";

import { createSocketMessageController } from "../src/app-runtime/socket-message-controller.js";

export function runSocketMessageControllerTests() {
  const deriveInputs = [];
  const executedEffects = [];
  const expectedEffects = {
    actions: [{ type: "session_snapshot", snapshot: { session_id: "sess-active" } }],
    transportEvents: [],
    loaderRequests: [],
  };
  const controller = createSocketMessageController({
    getCurrentSessionId: () => "sess-active",
    getSessionTransportState: () => ({ lastAppliedSeq: 4 }),
    getDiffPanelChrome: () => ({ defaultTitle: "Command Diff" }),
    makeId: (prefix) => `${prefix}-stable`,
    nowIso: () => "2026-07-05T00:00:00.000Z",
    deriveEffects: (input) => {
      deriveInputs.push(input);
      return expectedEffects;
    },
    executeEffects: (effects) => executedEffects.push(effects),
  });

  const returnedEffects = controller.handleMessage({
    type: "session_event",
    data: { event_id: "evt-1", event_kind: "turn.started" },
  });

  assert.equal(returnedEffects, expectedEffects);
  assert.deepEqual(executedEffects, [expectedEffects]);
  assert.equal(deriveInputs.length, 1);
  assert.equal(deriveInputs[0].type, "session_event");
  assert.deepEqual(deriveInputs[0].data, {
    event_id: "evt-1",
    event_kind: "turn.started",
  });
  assert.equal(deriveInputs[0].currentSessionId, "sess-active");
  assert.deepEqual(deriveInputs[0].sessionTransport, { lastAppliedSeq: 4 });
  assert.deepEqual(deriveInputs[0].diffPanelChrome, { defaultTitle: "Command Diff" });
  assert.equal(deriveInputs[0].makeId("cmd"), "cmd-stable");
  assert.equal(deriveInputs[0].nowIso(), "2026-07-05T00:00:00.000Z");

  const acceptedEffects = [];
  const acceptedController = createSocketMessageController({
    deriveEffects: ({ data }) => ({
      actions: [{ type: "step_started", stepId: data.payload.step_id }],
      transportEvents: [data],
      loaderRequests: [{ name: "load_sessions" }],
    }),
    executeEffects: (effects) => acceptedEffects.push(effects),
  });
  acceptedController.handleAcceptedSessionEvent({
    event_id: "evt-accepted",
    event_kind: "step.started",
    payload: { step_id: "step-accepted" },
  });
  assert.deepEqual(acceptedEffects, [
    {
      actions: [{ type: "step_started", stepId: "step-accepted" }],
      transportEvents: [],
      loaderRequests: [{ name: "load_sessions" }],
    },
  ]);

  const tupleControllerInputs = [];
  const tupleController = createSocketMessageController({
    deriveEffects: (input) => {
      tupleControllerInputs.push(input);
      return { actions: [], transportEvents: [], loaderRequests: [] };
    },
    executeEffects: () => {},
  });
  tupleController.handleMessage("terminal_event", { event: { line: "ready" } });
  assert.equal(tupleControllerInputs[0].type, "terminal_event");
  assert.deepEqual(tupleControllerInputs[0].data, { event: { line: "ready" } });

  const scheduledCallbacks = [];
  const scheduledEffects = {
    actions: [{ type: "log_event", event: { id: "evt-scheduled" } }],
    transportEvents: [],
    loaderRequests: [],
  };
  const scheduledController = createSocketMessageController({
    scheduleMessage: (callback) => {
      scheduledCallbacks.push(callback);
      return "scheduled";
    },
    deriveEffects: () => scheduledEffects,
    executeEffects: (effects) => executedEffects.push(effects),
  });

  const scheduledResult = scheduledController.handleMessage({
    type: "session_event",
    data: { event_id: "evt-scheduled" },
  });

  assert.equal(scheduledResult, "scheduled");
  assert.equal(scheduledCallbacks.length, 1);
  assert.deepEqual(executedEffects, [expectedEffects]);
  scheduledCallbacks[0]();
  assert.deepEqual(executedEffects, [expectedEffects, scheduledEffects]);
}
