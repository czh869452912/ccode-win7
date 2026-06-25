import assert from "node:assert/strict";

import {
  createThreadState,
  readActiveThreadId,
  readThreadHistoryIntegrity,
  readThreadSessions,
  reduceThreadState,
} from "../src/session-runtime/thread-state.js";

export function runThreadStateTests() {
  const initial = createThreadState();
  assert.deepEqual(initial.sessions, []);
  assert.equal(initial.currentSessionId, "");
  assert.equal(initial.historyIntegrity, null);
  assert.equal(readActiveThreadId({ thread: initial }), "");
  assert.deepEqual(readThreadSessions({ thread: initial }), []);

  const loaded = reduceThreadState(initial, {
    type: "sessions_loaded",
    sessions: [{ session_id: "sess-1" }],
  });
  assert.deepEqual(loaded.sessions, [{ session_id: "sess-1" }]);

  const activated = reduceThreadState(loaded, {
    type: "session_activated",
    sessionId: "sess-1",
    snapshot: { session_id: "sess-1" },
    historyIntegrity: { status: "partial", restore_stop_reason: "gap" },
  });
  assert.equal(activated.currentSessionId, "sess-1");
  assert.deepEqual(activated.historyIntegrity, { status: "partial", restore_stop_reason: "gap" });

  const healed = reduceThreadState(activated, {
    type: "session_snapshot",
    snapshot: { session_id: "sess-1", restore_stop_reason: "" },
  });
  assert.deepEqual(healed.historyIntegrity, {
    status: "healthy",
    restore_stop_reason: "",
  });
  assert.equal(readThreadHistoryIntegrity({ thread: healed }).status, "healthy");
  assert.deepEqual(
    reduceThreadState(healed, { type: "dev_fixture_threads", sessionId: "visual" }),
    healed,
  );

  const switched = reduceThreadState(healed, { type: "workspace_scoped_state_reset" });
  assert.deepEqual(switched, createThreadState());
}
