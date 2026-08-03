import assert from "node:assert/strict";

import { createSocketEffectExecutor } from "../src/app-runtime/socket-effect-executor.js";
import { createSessionTransportState } from "../src/session-runtime/session-transport-state.js";

export async function runSocketEffectExecutorTests() {
  const actions = [];
  const loaderRequests = [];
  const appendedEvents = [];
  const recovered = [];
  const clearedRequestIds = [];
  const controller = {
    applyEvent(event) {
      appendedEvents.push(event);
      return {
        state: { reloadState: "reload_required", lastAppliedSeq: 7 },
        accepted: true,
      };
    },
    recover(sessionId) {
      recovered.push(sessionId);
      return Promise.resolve();
    },
  };
  const execute = createSocketEffectExecutor({
    dispatch: (action) => actions.push(action),
    executeLoaderRequest: (request) => loaderRequests.push(request),
    getSessionTransportController: () => controller,
    getCurrentSessionId: () => "sess-active",
    clearRespondingRequestId: (requestId) => clearedRequestIds.push(requestId),
  });

  execute({
    transportEvents: [
      {
        schema_version: 1,
        session_id: "sess-active",
        event_id: "evt-7",
        sequence: 7,
        event_kind: "turn.started",
        timestamp: "2026-07-26T00:00:07Z",
        payload: { turn_id: "turn-1" },
      },
    ],
    actions: [
      { type: "interaction_resolved", requestId: "ask-1" },
      { type: "session_snapshot", snapshot: { session_id: "sess-active" } },
    ],
    loaderRequests: [{ name: "load_sessions" }],
  });

  assert.equal(appendedEvents.length, 1);
  assert.equal(recovered.length, 1);
  assert.equal(recovered[0], "sess-active");
  assert.deepEqual(clearedRequestIds, ["ask-1"]);
  assert.deepEqual(actions, [
    { type: "interaction_resolved", requestId: "ask-1" },
    { type: "session_snapshot", snapshot: { session_id: "sess-active" } },
  ]);
  assert.deepEqual(loaderRequests, [{ name: "load_sessions" }]);

  let transport = createSessionTransportState();
  const fallbackLoadedSessions = [];
  const unavailableActions = [];
  const fallbackExecute = createSocketEffectExecutor({
    dispatch: (action) => unavailableActions.push(action),
    getSessionTransportController: () => null,
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
        schema_version: 1,
        session_id: "sess-fallback",
        event_id: "evt-1",
        sequence: 1,
        event_kind: "turn.started",
        timestamp: "2026-07-26T00:00:01Z",
        payload: { turn_id: "turn-1" },
      },
      {
        schema_version: 1,
        session_id: "sess-fallback",
        event_id: "evt-3",
        sequence: 3,
        event_kind: "step.started",
        timestamp: "2026-07-26T00:00:03Z",
        payload: { turn_id: "turn-1", step_id: "step-1" },
      },
    ],
    actions: [{ type: "turn_started", turnId: "turn-1" }],
  });

  assert.equal(transport.lastAppliedSeq, 0);
  assert.equal(transport.reloadState, "healthy");
  assert.deepEqual(fallbackLoadedSessions, []);
  assert.deepEqual(unavailableActions, []);

  const rejectedActions = [];
  const reject = createSocketEffectExecutor({
    dispatch: (action) => rejectedActions.push(action),
    getSessionTransportController: () => ({
      applyEvent() {
        return {
          state: { reloadState: "healthy", lastAppliedSeq: 1 },
          accepted: false,
          reason: "duplicate_event",
        };
      },
    }),
  });
  reject({
    transportEvents: [
      {
        schema_version: 1,
        session_id: "sess-active",
        event_id: "evt-1",
        sequence: 1,
        event_kind: "turn.started",
        timestamp: "2026-07-26T00:00:01Z",
        payload: { turn_id: "turn-1" },
      },
    ],
    actions: [{ type: "turn_started", turnId: "turn-1" }],
  });
  assert.deepEqual(rejectedActions, []);
}
