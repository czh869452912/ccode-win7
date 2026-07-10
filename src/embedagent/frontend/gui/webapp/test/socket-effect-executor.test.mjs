import assert from "node:assert/strict";

import { createSocketEffectExecutor } from "../src/app-runtime/socket-effect-executor.js";
import { createSessionTransportState } from "../src/session-runtime/session-transport-state.js";

export async function runSocketEffectExecutorTests() {
  const actions = [];
  const loaderRequests = [];
  const appendedEvents = [];
  const recovered = [];
  const controller = {
    appendEvent(event) {
      appendedEvents.push(event);
      return { reloadState: "reload_required", lastAppliedSeq: 7 };
    },
    recover(sessionId, transportState) {
      recovered.push({ sessionId, transportState });
      return Promise.resolve();
    },
  };
  const execute = createSocketEffectExecutor({
    dispatch: (action) => actions.push(action),
    executeLoaderRequest: (request) => loaderRequests.push(request),
    getSessionTransportController: () => controller,
    getCurrentSessionId: () => "sess-active",
  });

  execute({
    transportEvents: [
      {
        event_id: "evt-7",
        seq: 7,
        event_kind: "turn.started",
        payload: { turn_id: "turn-1" },
      },
    ],
    actions: [{ type: "session_snapshot", snapshot: { session_id: "sess-active" } }],
    loaderRequests: [{ name: "load_sessions" }],
  });

  assert.equal(appendedEvents.length, 1);
  assert.equal(recovered.length, 1);
  assert.equal(recovered[0].sessionId, "sess-active");
  assert.equal(recovered[0].transportState.reloadState, "reload_required");
  assert.deepEqual(actions, [{ type: "session_snapshot", snapshot: { session_id: "sess-active" } }]);
  assert.deepEqual(loaderRequests, [{ name: "load_sessions" }]);

  let transport = createSessionTransportState();
  const fallbackLoadedSessions = [];
  const fallbackExecute = createSocketEffectExecutor({
    getSessionTransportState: () => transport,
    updateSessionTransportState: (updater) => {
      transport = updater(transport);
      return transport;
    },
    getCurrentSessionId: () => "sess-fallback",
    loadSession: (sessionId) => {
      fallbackLoadedSessions.push(sessionId);
      return Promise.resolve();
    },
  });

  fallbackExecute({
    transportEvents: [
      {
        event_id: "evt-1",
        seq: 1,
        event_kind: "turn.started",
        payload: { turn_id: "turn-1" },
      },
      {
        event_id: "evt-3",
        seq: 3,
        event_kind: "step.started",
        payload: { turn_id: "turn-1", step_id: "step-1" },
      },
    ],
  });

  assert.equal(transport.lastAppliedSeq, 1);
  assert.equal(transport.reloadState, "reload_required");
  assert.deepEqual(fallbackLoadedSessions, ["sess-fallback"]);
}
