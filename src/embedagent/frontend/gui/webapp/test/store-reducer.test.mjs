import assert from "node:assert/strict";

import { initialState, reducer } from "../src/store.js";

export function runStoreReducerTests() {
  const limitedState = {
    ...initialState,
    terminationReason: "max_turns",
    turnsUsed: 8,
    maxTurns: 8,
  };

  const completedState = reducer(limitedState, {
    type: "turn_ended",
    terminationReason: "completed",
    turnsUsed: 9,
    maxTurns: null,
  });

  assert.equal(completedState.terminationReason, "completed");
  assert.equal(completedState.turnsUsed, 9);
  assert.equal(completedState.maxTurns, null);

  const nextUserState = reducer(limitedState, {
    type: "local_user_message",
    text: "continue",
  });

  assert.equal(nextUserState.terminationReason, "");
  assert.equal(nextUserState.maxTurns, null);

  const capabilityState = reducer(initialState, {
    type: "session_capabilities_loaded",
    capabilities: {
      commands: [
        {
          name: "help",
          usage: "/help",
          active: true,
        },
      ],
    },
  });

  assert.equal(capabilityState.sessionCapabilities.commands[0].usage, "/help");
}
