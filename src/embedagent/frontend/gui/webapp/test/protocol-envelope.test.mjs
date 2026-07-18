import assert from "node:assert/strict";

import {
  normalizeProtocolEnvelope,
  protocolEnvelopeIsValid,
} from "../src/session-runtime/protocol-envelope.js";

export function runProtocolEnvelopeTests() {
  const result = normalizeProtocolEnvelope({
    protocol: "agent_session_v1",
    version: 1,
    sequence: 7,
    revision: "rev-1",
    payload: { unknownActivity: { kind: "future" } },
  }, "agent_session_v1");

  assert.equal(protocolEnvelopeIsValid(result), true);
  assert.equal(result.payload.unknownActivity.kind, "future");
  assert.equal(result.sequence, 7);

  const invalid = normalizeProtocolEnvelope({
    protocol: "app_shell_v1",
    version: 1,
    sequence: -1,
    revision: "",
    payload: { prompt: "secret" },
  }, "agent_session_v1");

  assert.equal(protocolEnvelopeIsValid(invalid), false);
  assert.equal(invalid.errors.includes("protocol"), true);
  assert.equal(invalid.errors.includes("sequence"), true);
  assert.equal(invalid.errors.includes("revision"), true);
  assert.equal(invalid.errors.includes("sensitive"), true);
}

runProtocolEnvelopeTests();
console.log("protocol envelope checks passed");
