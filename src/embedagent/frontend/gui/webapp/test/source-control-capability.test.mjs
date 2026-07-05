import assert from "node:assert/strict";

import { sourceControlCapabilityEnabled } from "../src/source-control/source-control-capability.js";

export function runSourceControlCapabilityTests() {
  assert.equal(sourceControlCapabilityEnabled({}), false);
  assert.equal(sourceControlCapabilityEnabled({ sourceControl: { enabled: false } }), false);
  assert.equal(sourceControlCapabilityEnabled({ sourceControl: { enabled: true } }), true);
  assert.equal(sourceControlCapabilityEnabled({ source_control: { enabled: true } }), true);
}
