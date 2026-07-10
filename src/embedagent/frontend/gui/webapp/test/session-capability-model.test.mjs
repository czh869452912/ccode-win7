import assert from "node:assert/strict";

import {
  buildSessionCapabilityModel,
  buildSessionCapabilityModelFromState,
} from "../src/session-runtime/session-capability-model.js";

export function runSessionCapabilityModelTests() {
  const capabilities = {
    modeCatalog: { build: { id: "build", label: "Build" } },
    toolCatalog: { read_file: { name: "read_file", label: "Read File" } },
    emptyState: { primary: "Select a project" },
    commands: [{ id: "mode.build" }],
  };

  const model = buildSessionCapabilityModel(capabilities);
  assert.equal(model.sessionCapabilities, capabilities);
  assert.equal(model.modeCatalog, capabilities.modeCatalog);
  assert.equal(model.toolCatalog, capabilities.toolCatalog);
  assert.equal(model.emptyState, capabilities.emptyState);

  const stateModel = buildSessionCapabilityModelFromState({ sessionCapabilities: capabilities });
  assert.equal(stateModel.sessionCapabilities, capabilities);
  assert.equal(stateModel.modeCatalog, capabilities.modeCatalog);
  assert.equal(stateModel.toolCatalog, capabilities.toolCatalog);

  const empty = buildSessionCapabilityModel(null);
  assert.deepEqual(empty.sessionCapabilities, {});
  assert.deepEqual(empty.modeCatalog, {});
  assert.deepEqual(empty.toolCatalog, {});
  assert.equal(empty.emptyState, null);

  const emptyStateModel = buildSessionCapabilityModelFromState(null);
  assert.deepEqual(emptyStateModel.sessionCapabilities, {});
}
