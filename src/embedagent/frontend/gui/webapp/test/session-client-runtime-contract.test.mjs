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
    this.bootstrapCalls = [];
    this.closed = false;
  }

  async takeResponse(operation) {
    this.bootstrapCalls.push(operation);
    const response = this.responses.shift();
    const callback = this.duringBootstrap;
    this.duringBootstrap = null;
    if (callback) await callback();
    if (response instanceof Error) throw response;
    return clone(response);
  }

  async loadSessionBootstrap(reference, options) {
    return this.takeResponse(["activate", reference, options]);
  }

  async createSession(mode, options) {
    return this.takeResponse(["create", mode, options]);
  }

  async setSessionMode(sessionId, mode, options) {
    return this.takeResponse(["mode", sessionId, mode, options]);
  }

  async cancelSession(sessionId, options) {
    return this.takeResponse(["cancel", sessionId, options]);
  }

  async respondToInteraction(sessionId, interactionId, payload, options) {
    return this.takeResponse([
      "interaction_response",
      sessionId,
      interactionId,
      payload,
      options,
    ]);
  }

  close() {
    this.closed = true;
  }
}

async function runCase(contract, testCase) {
  const actions = [];
  const observations = [];
  let runtime;
  let dispatchInjections = [];
  const dispatchPromises = [];
  const transport = new FixtureTransport();
  runtime = new SessionClientRuntime({
    transport,
    dispatch(action) {
      assertDeeplyFrozen(action);
      actions.push(action);
      const observed = observable(action);
      for (const injection of dispatchInjections) {
        if (injection.used) continue;
        if (
          !Object.entries(injection.match).every(
            ([key, value]) => observed[key] === value,
          )
        ) {
          continue;
        }
        injection.used = true;
        if (injection.observation) {
          observations.push({
            name: injection.observation,
            cursor: runtime.cursor,
            lifecycle: runtime.lifecycle,
            terminal_status: runtime.terminalOutcome?.status || null,
          });
        }
        for (const eventName of injection.events) {
          dispatchPromises.push(
            runtime.acceptSessionEvent(clone(contract.events[eventName])),
          );
        }
        if (injection.error) throw new Error(injection.error);
      }
    },
  });

  async function drainDispatchPromises() {
    while (dispatchPromises.length > 0) {
      await dispatchPromises.shift();
    }
  }

  assert.equal(runtime.lifecycle, testCase.initial.lifecycle);
  assert.equal(runtime.generation, testCase.initial.generation);
  assert.equal(runtime.cursor, testCase.initial.cursor);

  for (const operation of testCase.operations) {
    dispatchInjections = (operation.dispatch_injections || []).map((item) => ({
      match: clone(item.match),
      events: [...item.events],
      observation: String(item.observation || ""),
      error: String(item.error || ""),
      used: false,
    }));
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
      await drainDispatchPromises();
      continue;
    }
    if (
      operation.kind === "bootstrap_operation" ||
      operation.kind === "bootstrap_operation_raw"
    ) {
      const response = operation.request_error
        ? Object.assign(new Error("request failed"), {
            code: operation.request_error,
          })
        : contract.bootstraps[operation.bootstrap];
      transport.responses.push(response);
      if (operation.recovery_bootstrap) {
        transport.responses.push(contract.bootstraps[operation.recovery_bootstrap]);
      }
      if (
        operation.during_events ||
        operation.during_activation ||
        operation.during_close
      ) {
        transport.duringBootstrap = async () => {
          for (const eventName of operation.during_events || []) {
            await runtime.acceptSessionEvent(clone(contract.events[eventName]));
          }
          if (operation.during_activation) {
            const nested = operation.during_activation;
            const nestedResponse = nested.request_error
              ? Object.assign(new Error("nested activation failed"), {
                  code: nested.request_error,
                })
              : contract.bootstraps[nested.bootstrap];
            transport.responses.push(nestedResponse);
            await runtime.activateSession(nested.session_id);
          }
          if (operation.during_close) runtime.close();
        };
      }

      const invoke = () => {
        if (operation.operation === "interaction_response") {
          return runtime.respondToInteraction(
            operation.session_id,
            "approval-1",
            { decision: "accept" },
          );
        }
        if (operation.operation === "create") {
          return runtime.createSession("explore");
        }
        if (operation.operation === "mode") {
          return runtime.setSessionMode(operation.session_id, "verify");
        }
        if (operation.operation === "cancel") {
          return runtime.cancelSession(operation.session_id);
        }
        throw new Error(
          `unknown bootstrap fixture operation:${operation.operation}`,
        );
      };

      if (operation.expect_error) {
        await assert.rejects(invoke);
      } else if (operation.expect_stale) {
        assert.equal(await invoke(), null);
      } else {
        await invoke();
      }
      await drainDispatchPromises();
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
      if (operation.recovery_during_events) {
        transport.duringBootstrap = async () => {
          for (const eventName of operation.recovery_during_events) {
            await runtime.acceptSessionEvent(clone(contract.events[eventName]));
          }
        };
      }
      await runtime.acceptSessionEvent(clone(contract.events[operation.event]));
      await drainDispatchPromises();
      continue;
    }
    if (operation.kind === "close") {
      runtime.close();
      await drainDispatchPromises();
      continue;
    }
    throw new Error(`unknown fixture operation:${operation.kind}`);
  }

  return { actions: actions.map(observable), observations, runtime, transport };
}

export async function runSessionClientRuntimeContractTests() {
  const contract = JSON.parse(await readFile(CONTRACT_PATH, "utf8"));
  assert.equal(contract.schema_version, 1);

  for (const testCase of contract.cases) {
    const result = await runCase(contract, testCase);
    assert.deepEqual(result.actions, testCase.actions, testCase.name);
    assert.deepEqual(
      result.observations,
      testCase.observations || [],
      `${testCase.name}:observations`,
    );
    if (testCase.final) {
      assert.deepEqual(
        {
          session_id: result.runtime.sessionId,
          cursor: result.runtime.cursor,
          generation: result.runtime.generation,
          lifecycle: result.runtime.lifecycle,
          terminal_status: result.runtime.terminalOutcome?.status || null,
        },
        testCase.final,
        `${testCase.name}:final`,
      );
    }
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
      schema_version: 2,
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
