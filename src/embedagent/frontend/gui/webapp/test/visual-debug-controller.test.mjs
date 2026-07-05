import assert from "node:assert/strict";

import { createVisualDebugController } from "../src/app-runtime/visual-debug-controller.js";

export function runVisualDebugControllerTests() {
  const calls = [];
  const cleanup = () => {
    calls.push({ cleanup: true });
  };
  const windowObject = { location: { search: "?visual_debug=1&scenario=timeline" } };
  const dispatch = () => {};
  const openDiffFixture = () => {};
  const controller = createVisualDebugController({
    windowObject,
    dispatch,
    openDiffFixture,
    getCurrentMode: () => "verify",
    installFixtures: (payload) => {
      calls.push(payload);
      return cleanup;
    },
  });

  assert.equal(controller.install(), cleanup);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].windowObject, windowObject);
  assert.equal(calls[0].locationSearch, "?visual_debug=1&scenario=timeline");
  assert.equal(calls[0].dispatch, dispatch);
  assert.equal(calls[0].openDiffFixture, openDiffFixture);
  assert.equal(calls[0].currentMode, "verify");

  const explicitSearchCalls = [];
  createVisualDebugController({
    windowObject,
    getLocationSearch: () => "?visual_debug=0",
    getCurrentMode: () => "",
    installFixtures: (payload) => explicitSearchCalls.push(payload),
  }).install();
  assert.equal(explicitSearchCalls[0].locationSearch, "?visual_debug=0");
  assert.equal(explicitSearchCalls[0].currentMode, "explore");
}
