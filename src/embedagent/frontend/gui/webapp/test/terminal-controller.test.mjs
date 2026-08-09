import assert from "node:assert/strict";

import { createTerminalController } from "../src/app-runtime/terminal-controller.js";

function baseState(patch = {}) {
  return {
    thread: { currentSessionId: "session-a", sessions: [], historyIntegrity: null },
    terminal: {
      activeTerminalId: "term-1",
      terminalIds: ["term-1"],
      sessions: {},
    },
    contribution: { activeId: "terminal:term-1", items: [{
      id: "terminal:term-1",
      kind: "terminal",
      terminalIds: ["term-1"],
      activeTerminalId: "term-1",
    }] },
    ...patch,
  };
}

function harness(options = {}) {
  let state = options.state || baseState();
  const actions = [];
  const calls = [];
  const opened = [];
  const snapshot = (id) => ({ session_id: "session-a", terminal_id: id, status: "running" });
  const protocol = {
    openTerminal: async (...args) => { calls.push(["open", ...args]); return { terminal: snapshot(args[1]) }; },
    listTerminals: async (...args) => { calls.push(["list", ...args]); return { terminals: [snapshot("term-1")] }; },
    writeTerminal: async (...args) => { calls.push(["write", ...args]); return { ok: true }; },
    clearTerminal: async (...args) => { calls.push(["clear", ...args]); return { terminal: snapshot(args[1]) }; },
    restartTerminal: async (...args) => { calls.push(["restart", ...args]); return { terminal: snapshot(args[1]) }; },
    closeTerminal: async (...args) => { calls.push(["close", ...args]); return { ok: true }; },
  };
  const controller = createTerminalController({
    protocol,
    dispatch: (action) => actions.push(action),
    getState: () => state,
    getAppCapabilities: () => options.enabled === false ? {} : { terminal: { enabled: true } },
    getTerminalChrome: () => ({ sessionRequiredNotice: "Session required" }),
    nextTerminalId: (ids) => `term-${ids.length + 1}`,
    contributionController: {
      openSurface: (...args) => { opened.push(args); return true; },
    },
  });
  return { actions, calls, controller, opened, setState: (next) => { state = next; } };
}

export async function runTerminalControllerTests() {
  const noSession = harness({
    state: baseState({ thread: { currentSessionId: "", sessions: [], historyIntegrity: null } }),
  });
  assert.equal(await noSession.controller.openContribution(), null);
  assert.deepEqual(noSession.actions, [{ type: "interaction_notice_set", notice: "Session required" }]);

  const active = harness();
  assert.equal(await active.controller.openContribution(), "term-2");
  assert.deepEqual(active.calls[0], ["open", "session-a", "term-2", { cols: 100, rows: 30 }]);
  assert.equal(active.opened[0][0], "terminal");
  assert.equal(active.opened[0][2].terminalId, "term-2");

  assert.equal(await active.controller.sendTo("term-1", "pwd\n"), "term-1");
  assert.equal(await active.controller.clearById("term-1"), "term-1");
  assert.equal(await active.controller.restartById("term-1"), "term-1");
  await active.controller.refresh();
  assert.deepEqual(active.calls.slice(-4).map((call) => call[0]), ["write", "clear", "restart", "list"]);

  assert.equal(await active.controller.splitContributionVertical(), "term-2");
  assert.equal(active.actions.at(-1).type, "contribution_terminal_split");
  assert.equal(active.actions.at(-1).splitDirection, "vertical");

  assert.equal(active.controller.activateContributionTerminal("term-1"), "term-1");
  assert.deepEqual(active.actions.slice(-2).map((action) => action.type), [
    "contribution_terminal_activated",
    "terminal_active_set",
  ]);

  assert.equal(await active.controller.closeContributionTerminal("term-1"), "term-1");
  assert.deepEqual(active.actions.slice(-2).map((action) => action.type), [
    "terminal_event",
    "contribution_terminal_closed",
  ]);

  const disabled = harness({ enabled: false });
  assert.equal(await disabled.controller.openSession(), null);
  assert.deepEqual(disabled.calls, []);
}
