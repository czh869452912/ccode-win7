import assert from "node:assert/strict";

import { createInitialAppLoadController } from "../src/app-runtime/initial-app-load-controller.js";

export async function runInitialAppLoadControllerTests() {
  const calls = [];
  const controller = createInitialAppLoadController({
    loadAppBootstrap: () => {
      calls.push("bootstrap");
      return "bootstrapped";
    },
    loadSessionCommandCapabilities: () => {
      calls.push("capabilities");
      return Promise.reject(new Error("capability warmup failed"));
    },
  });

  const result = controller.start();

  assert.equal(result.bootstrapResult, "bootstrapped");
  assert.deepEqual(calls, ["bootstrap", "capabilities"]);
  assert.equal(await result.commandCapabilitiesResult, null);

  const emptyResult = createInitialAppLoadController().start();
  assert.equal(emptyResult.bootstrapResult, undefined);
  assert.equal(await emptyResult.commandCapabilitiesResult, undefined);
}
