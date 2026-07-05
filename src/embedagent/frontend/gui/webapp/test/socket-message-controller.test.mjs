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
}
