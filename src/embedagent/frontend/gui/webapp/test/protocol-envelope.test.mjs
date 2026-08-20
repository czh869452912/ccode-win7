import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  normalizeProtocolEnvelope,
  normalizeSessionEventEnvelope,
  protocolEnvelopeIsValid,
} from "../src/session-runtime/protocol-envelope.js";
import { isSessionEventEnvelope } from "../src/session-runtime/session-transport-state.js";
import { FRONTEND_PROTOCOL_SCHEMA_VERSION } from "../src/session-runtime/protocol-version.js";

const FIXTURE_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../../../tests/fixtures/frontend_protocol",
);

function readFixture(name) {
  return JSON.parse(fs.readFileSync(path.join(FIXTURE_ROOT, name), "utf8"));
}

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

  const wireEvent = readFixture("session_event.json");
  const event = normalizeSessionEventEnvelope(wireEvent);
  assert.equal(event.schemaVersion, FRONTEND_PROTOCOL_SCHEMA_VERSION);
  assert.equal(event.eventId, "event-5");
  assert.equal(event.sequence, 5);
  assert.equal(event.eventKind, "session.snapshot");
  assert.equal(isSessionEventEnvelope(wireEvent), true);

  assert.throws(
    () => normalizeSessionEventEnvelope({ ...wireEvent, schema_version: 1 }),
    /invalid_session_event:schema_version/,
  );
  assert.throws(
    () => normalizeSessionEventEnvelope({ ...wireEvent, eventId: "event-5" }),
    /invalid_session_event:root.eventId/,
  );
  assert.equal(
    isSessionEventEnvelope({ ...wireEvent, prompt: "must never cross the wire" }),
    false,
  );
  assert.throws(
    () => normalizeSessionEventEnvelope({ ...wireEvent, payload: { token: "secret" } }),
    /invalid_session_event:payload/,
  );
}

runProtocolEnvelopeTests();
console.log("protocol envelope checks passed");
