import assert from "node:assert/strict";

import {
  createEventLogState,
  readEventLogEntries,
  reduceEventLogState,
} from "../src/session-runtime/event-log-state.js";

export function runEventLogStateTests() {
  const initial = createEventLogState();
  assert.deepEqual(initial, []);
  assert.deepEqual(readEventLogEntries({ eventLog: initial }), []);

  const appended = reduceEventLogState(initial, {
    type: "log_event",
    label: "session_event",
    detail: "turn_started",
    timestamp: 1,
  });
  assert.deepEqual(appended, [{ ts: 1, label: "session_event", detail: "turn_started" }]);

  let capped = initial;
  for (let index = 0; index < 205; index += 1) {
    capped = reduceEventLogState(capped, {
      type: "log_event",
      label: `event-${index}`,
      timestamp: index,
    });
  }
  assert.equal(capped.length, 200);
  assert.equal(capped[0].label, "event-5");
  assert.equal(capped[199].label, "event-204");

  assert.deepEqual(
    reduceEventLogState(appended, { type: "session_activated" }),
    createEventLogState(),
  );
  assert.deepEqual(
    reduceEventLogState(appended, { type: "workspace_scoped_state_reset" }),
    createEventLogState(),
  );
}
