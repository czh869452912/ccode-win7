import assert from "node:assert/strict";

import { createSocketMessageController } from "../src/app-runtime/socket-message-controller.js";

export function runSocketMessageControllerTests() {
  const deriveInputs = [];
  const executedEffects = [];
  const controller = createSocketMessageController({
    getDiffPanelChrome: () => ({ defaultTitle: "Command Diff" }),
    deriveEffects: (input) => {
      deriveInputs.push(input);
      return { actions: [{ type: input.type }], loaderRequests: [] };
    },
    executeEffects: (effects) => executedEffects.push(effects),
  });

  assert.throws(
    () => controller.handleMessage({ type: "session_event", data: {} }),
    /session_event_requires_runtime_acceptance/,
  );

  const terminalEffects = controller.handleMessage("terminal_event", { event: { line: "ready" } });
  assert.deepEqual(terminalEffects.actions, [{ type: "terminal_event" }]);
  assert.equal(deriveInputs[0].type, "terminal_event");

  const accepted = controller.handleAcceptedSessionEvent({
    event_id: "evt-accepted",
    event_kind: "step.started",
    payload: { step_id: "step-accepted" },
  });
  assert.deepEqual(accepted.actions, [{ type: "session_event" }]);
  assert.deepEqual(executedEffects, [terminalEffects, accepted]);

  const scheduledCallbacks = [];
  const scheduledController = createSocketMessageController({
    scheduleMessage(callback) {
      scheduledCallbacks.push(callback);
      return "scheduled";
    },
    deriveEffects: ({ type }) => ({ actions: [{ type }], loaderRequests: [] }),
    executeEffects: (effects) => executedEffects.push(effects),
  });
  assert.equal(scheduledController.handleMessage("terminal_event", {}), "scheduled");
  assert.equal(scheduledCallbacks.length, 1);
  scheduledCallbacks[0]();
  assert.equal(executedEffects.at(-1).actions[0].type, "terminal_event");
}
