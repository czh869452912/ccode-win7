import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { SessionClientRuntime } from "../src/session-runtime/session-client-runtime.js";

const CONTRACT_PATH = fileURLToPath(
  new URL("../../../../../../tests/fixtures/session_client_runtime/contract.json", import.meta.url),
);

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function assertDeeplyFrozen(value) {
  if (!value || typeof value !== "object") return;
  assert.equal(Object.isFrozen(value), true);
  for (const child of Object.values(value)) assertDeeplyFrozen(child);
}

function observable(action) {
  if (action.kind === "session_activated") {
    return {
      kind: action.kind,
      session_id: action.session_id,
      cursor: action.cursor,
      generation: action.generation,
      reason: action.reason,
    };
  }
  if (action.kind === "session_event") {
    return {
      kind: action.kind,
      session_id: action.event.session_id,
      sequence: action.event.sequence,
      event_kind: action.event.event_kind,
      lifecycle: action.lifecycle,
    };
  }
  if (action.kind === "protocol_failed") {
    return {
      kind: action.kind,
      session_id: action.session_id,
      generation: action.generation,
      code: action.failure.code,
    };
  }
  return { kind: action.kind };
}

class FixtureTransport {
  constructor() {
    this.responses = [];
    this.duringBootstrap = null;
    this.closed = false;
  }

  async loadSessionBootstrap() {
    const response = this.responses.shift();
    const callback = this.duringBootstrap;
    this.duringBootstrap = null;
    if (callback) await callback();
    if (response instanceof Error) throw response;
    return clone(response);
  }

  close() {
    this.closed = true;
  }
}

async function runCase(contract, testCase) {
  const actions = [];
  let runtime;
  const transport = new FixtureTransport();
  runtime = new SessionClientRuntime({
    transport,
    dispatch(action) {
      assertDeeplyFrozen(action);
      actions.push(action);
    },
  });

  assert.equal(runtime.lifecycle, testCase.initial.lifecycle);
  assert.equal(runtime.generation, testCase.initial.generation);
  assert.equal(runtime.cursor, testCase.initial.cursor);

  for (const operation of testCase.operations) {
    if (operation.kind === "activate" || operation.kind === "activate_raw") {
      transport.responses.push(contract.bootstraps[operation.bootstrap]);
      if (operation.during_event) {
        transport.duringBootstrap = () =>
          runtime.acceptSessionEvent(clone(contract.events[operation.during_event]));
      }
      if (operation.during_activation) {
        const nested = operation.during_activation;
        transport.responses.push(contract.bootstraps[nested.bootstrap]);
        transport.duringBootstrap = () => runtime.activateSession(nested.session_id);
      }
      await runtime.activateSession(operation.session_id);
      continue;
    }
    if (operation.kind === "event") {
      if (operation.recovery_bootstrap) {
        transport.responses.push(contract.bootstraps[operation.recovery_bootstrap]);
      }
      if (operation.recovery_error) {
        const error = new Error("recovery failed");
        error.code = operation.recovery_error;
        transport.responses.push(error);
      }
      await runtime.acceptSessionEvent(clone(contract.events[operation.event]));
      continue;
    }
    if (operation.kind === "close") {
      runtime.close();
      continue;
    }
    throw new Error(`unknown fixture operation:${operation.kind}`);
  }

  return { actions: actions.map(observable), runtime, transport };
}

export async function runSessionClientRuntimeContractTests() {
  const contract = JSON.parse(await readFile(CONTRACT_PATH, "utf8"));
  assert.equal(contract.schema_version, 1);

  for (const testCase of contract.cases) {
    const result = await runCase(contract, testCase);
    assert.deepEqual(result.actions, testCase.actions, testCase.name);
  }

  const raceActions = [];
  const raceTransport = new FixtureTransport();
  const raceRuntime = new SessionClientRuntime({
    transport: raceTransport,
    dispatch: (action) => raceActions.push(action),
  });
  raceTransport.responses.push(contract.bootstraps.session_1_cursor_1);
  await raceRuntime.activateSession("session-1");
  await raceRuntime.acceptSessionEvent(clone(contract.events.approval_requested));

  const cursor3 = clone(contract.bootstraps.session_1_cursor_2);
  cursor3.event_cursor = 3;
  raceTransport.respondToInteraction = async () => {
    await raceRuntime.acceptSessionEvent(clone(contract.events.approval_resolved));
    await raceRuntime.acceptSessionEvent({
      schema_version: 1,
      event_id: "session-finished-4",
      session_id: "session-1",
      sequence: 4,
      event_kind: "session.finished",
      timestamp: "2026-08-13T00:00:04Z",
      payload: {
        final_text: "done",
        outcome: { kind: "completed", reason: "completed" },
      },
    });
    return cursor3;
  };

  await raceRuntime.respondToInteraction(
    "session-1",
    "approval-1",
    { decision: "accept" },
  );
  await raceRuntime.acceptSessionEvent(clone(contract.events.session_1_sequence_5));

  assert.equal(raceRuntime.cursor, 5);
  assert.equal(raceRuntime.lifecycle, "ready");
  assert.equal(raceRuntime.terminalOutcome.status, "completed");
  assert.equal(
    raceActions.filter((action) => action.reason === "recovery").length,
    0,
  );

  for (const method of [
    "createSession",
    "setSessionMode",
    "cancelSession",
    "respondToInteraction",
  ]) {
    assert.equal(typeof raceRuntime[method], "function", method);
  }

  const rollbackTransport = new FixtureTransport();
  const rollbackRuntime = new SessionClientRuntime({ transport: rollbackTransport });
  rollbackTransport.responses.push(contract.bootstraps.session_1_cursor_1);
  await rollbackRuntime.activateSession("session-1");
  rollbackTransport.setSessionMode = async () => {
    await rollbackRuntime.acceptSessionEvent(
      clone(contract.events.session_1_sequence_2),
    );
    throw new Error("request failed");
  };

  await assert.rejects(
    () => rollbackRuntime.setSessionMode("session-1", "verify"),
    /request failed/,
  );
  assert.equal(rollbackRuntime.sessionId, "session-1");
  assert.equal(rollbackRuntime.cursor, 2);
  assert.equal(rollbackRuntime.lifecycle, "ready");
  assert.equal(rollbackRuntime.generation, 2);

  const staleTransport = new FixtureTransport();
  const staleRuntime = new SessionClientRuntime({ transport: staleTransport });
  staleTransport.responses.push(contract.bootstraps.session_1_cursor_1);
  await staleRuntime.activateSession("session-1");
  staleTransport.setSessionMode = async () => {
    staleTransport.responses.push(contract.bootstraps.session_2_cursor_0);
    await staleRuntime.activateSession("session-2");
    return clone(contract.bootstraps.session_1_cursor_2);
  };

  assert.equal(await staleRuntime.setSessionMode("session-1", "verify"), null);
  assert.equal(staleRuntime.sessionId, "session-2");
  assert.equal(staleRuntime.cursor, 0);
  assert.equal(staleRuntime.generation, 3);

  const transport = new FixtureTransport();
  const runtime = new SessionClientRuntime({ transport });
  runtime.close();
  assert.equal(transport.closed, true);
  await assert.rejects(() => runtime.activateSession("session-1"), /runtime_closed/);
}
