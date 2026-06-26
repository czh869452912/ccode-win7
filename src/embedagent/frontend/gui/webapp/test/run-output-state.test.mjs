import assert from "node:assert/strict";

import {
  createRunOutputState,
  readRunOutputEntries,
  reduceRunOutputState,
} from "../src/session-runtime/run-output-state.js";

export function runRunOutputStateTests() {
  const initial = createRunOutputState();
  assert.deepEqual(initial, []);
  assert.deepEqual(readRunOutputEntries({ runOutput: initial }), []);

  const appended = reduceRunOutputState(initial, {
    type: "log_event",
    label: "session_event",
    detail: "turn_started",
    timestamp: 1,
  });
  assert.deepEqual(appended, [{ ts: 1, label: "session_event", detail: "turn_started" }]);

  let capped = initial;
  for (let index = 0; index < 205; index += 1) {
    capped = reduceRunOutputState(capped, {
      type: "log_event",
      label: `event-${index}`,
      timestamp: index,
    });
  }
  assert.equal(capped.length, 200);
  assert.equal(capped[0].label, "event-5");
  assert.equal(capped[199].label, "event-204");

  assert.deepEqual(
    reduceRunOutputState(appended, { type: "session_activated" }),
    createRunOutputState(),
  );
  assert.deepEqual(
    reduceRunOutputState(appended, { type: "workspace_scoped_state_reset" }),
    createRunOutputState(),
  );
}


