import assert from "node:assert/strict";

import { createTerminalController } from "../src/app-runtime/terminal-controller.js";

const TERMINAL_CHROME = Object.freeze({
  sessionRequiredNotice: "Open a run before using shell.",
  openFailedNotice: "Shell failed to open.",
  writeFailedNotice: "Shell write failed.",
  clearFailedNotice: "Shell clear failed.",
  restartFailedNotice: "Shell restart failed.",
  closeFailedNotice: "Shell close failed.",
});

const APP_CAPABILITIES = Object.freeze({
  surfaces: {
    bottomDrawer: [
      {
        id: "run_output",
        kind: "run_output",
        title: "Run Output",
        commandLabel: "Show Run Output",
        launcher: true,
        launcherOrder: 10,
        command: true,
      },
      {
        id: "terminal",
        kind: "terminal",
        title: "Terminal",
        commandLabel: "Show Terminal",
        launcher: true,
        launcherOrder: 20,
        command: true,
      },
    ],
    rightPanel: [
      {
        id: "terminal",
        kind: "terminal",
        title: "Shell Surface",
        launcher: true,
        launcherOrder: 10,
        command: true,
      },
    ],
  },
});

function baseState(overrides = {}) {
  return {
    thread: {
      sessions: [],
      currentSessionId: "sess-1",
      historyIntegrity: null,
    },
    terminal: {
      activeTerminalId: "term-1",
      terminalIds: ["term-1"],
      sessions: {
        "term-1": { terminalId: "term-1", buffer: "" },
      },
    },
    workbench: {
      rightPanel: {
        surfaces: [],
      },
    },
    ...overrides,
  };
}

function createHarness(options = {}) {
  let state = options.state || baseState();
  const actions = [];
  const apiCalls = [];
  const failures = options.failures || {};
  const appCapabilities =
    Object.prototype.hasOwnProperty.call(options, "appCapabilities")
      ? options.appCapabilities
      : APP_CAPABILITIES;
  const snapshotFor = (terminalId) => ({
    session_id: state.thread.currentSessionId,
    terminal_id: terminalId,
    status: "running",
    history: `history:${terminalId}`,
    sequence: 1,
    cols: 100,
    rows: 30,
  });
  const maybeFail = (name) => {
    if (Object.prototype.hasOwnProperty.call(failures, name)) {
      throw new Error(failures[name]);
    }
  };
  const api = {
    listTerminals: async (sessionId) => {
      apiCalls.push({ name: "listTerminals", args: [sessionId] });
      maybeFail("listTerminals");
      return { terminals: [{ session_id: sessionId, terminal_id: "term-1", status: "running" }] };
    },
    openTerminal: async (sessionId, terminalId, options) => {
      apiCalls.push({ name: "openTerminal", args: [sessionId, terminalId, options] });
      maybeFail("openTerminal");
      return { terminal: snapshotFor(terminalId) };
    },
    writeTerminal: async (sessionId, terminalId, text) => {
      apiCalls.push({ name: "writeTerminal", args: [sessionId, terminalId, text] });
      maybeFail("writeTerminal");
      return { ok: true };
    },
    clearTerminal: async (sessionId, terminalId) => {
      apiCalls.push({ name: "clearTerminal", args: [sessionId, terminalId] });
      maybeFail("clearTerminal");
      return { terminal: { ...snapshotFor(terminalId), history: "" } };
    },
    restartTerminal: async (sessionId, terminalId, options) => {
      apiCalls.push({ name: "restartTerminal", args: [sessionId, terminalId, options] });
      maybeFail("restartTerminal");
      return { terminal: { ...snapshotFor(terminalId), sequence: 2 } };
    },
    closeTerminal: async (sessionId, terminalId) => {
      apiCalls.push({ name: "closeTerminal", args: [sessionId, terminalId] });
      maybeFail("closeTerminal");
      return { ok: true };
    },
  };
  const controller = createTerminalController({
    getState: () => state,
    dispatch: (action) => actions.push(action),
    api,
    nextTerminalId: (ids) => `term-${ids.length + 1}`,
    getAppCapabilities: () => appCapabilities,
    getTerminalChrome: () => TERMINAL_CHROME,
  });
  return {
    actions,
    apiCalls,
    controller,
    setState(nextState) {
      state = nextState;
    },
  };
}

function actionTypes(actions) {
  return actions.map((action) => action.type);
}

export async function runTerminalControllerTests() {
  {
    const harness = createHarness({
      state: baseState({
        thread: { sessions: [], currentSessionId: "", historyIntegrity: null },
      }),
    });
    const result = await harness.controller.ensureOpen();
    assert.equal(result, null);
    assert.deepEqual(harness.apiCalls, []);
    assert.deepEqual(harness.actions, [
      { type: "interaction_notice_set", notice: TERMINAL_CHROME.sessionRequiredNotice },
    ]);
  }

  {
    const harness = createHarness();
    const result = await harness.controller.ensureOpen();
    assert.equal(result, "term-1");
    assert.deepEqual(harness.apiCalls[0], {
      name: "openTerminal",
      args: ["sess-1", "term-1", { cols: 100, rows: 30 }],
    });
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_snapshot_loaded",
      "terminal_active_set",
      "workbench_surface_activated",
    ]);
    assert.deepEqual(harness.actions[2], {
      type: "workbench_surface_activated",
      placement: "bottom",
      kind: "terminal",
    });
  }

  {
    const harness = createHarness();
    const result = await harness.controller.openSession("term-2");
    assert.equal(result, "term-2");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_snapshot_loaded",
      "terminal_active_set",
    ]);
    assert.equal(harness.actions[1].terminalId, "term-2");
  }

  {
    const harness = createHarness({ failures: { openTerminal: "" } });
    const result = await harness.controller.openSession("term-2");
    assert.equal(result, null);
    assert.deepEqual(harness.actions.at(-1), {
      type: "interaction_notice_set",
      notice: TERMINAL_CHROME.openFailedNotice,
    });
  }

  {
    const harness = createHarness();
    await harness.controller.refresh();
    assert.deepEqual(harness.apiCalls[0], { name: "listTerminals", args: ["sess-1"] });
    assert.deepEqual(harness.actions[0], {
      type: "terminal_summaries_loaded",
      terminals: [{ session_id: "sess-1", terminal_id: "term-1", status: "running" }],
    });
  }

  {
    const harness = createHarness({ failures: { listTerminals: "metadata unavailable" } });
    await harness.controller.refresh();
    assert.deepEqual(harness.apiCalls[0], { name: "listTerminals", args: ["sess-1"] });
    assert.deepEqual(harness.actions, []);
  }

  {
    const harness = createHarness();
    await harness.controller.sendTo("term-1", "dir\n");
    assert.deepEqual(harness.actions[0], { type: "terminal_active_set", terminalId: "term-1" });
    assert.deepEqual(harness.apiCalls[0], {
      name: "writeTerminal",
      args: ["sess-1", "term-1", "dir\n"],
    });
  }

  {
    const harness = createHarness({ failures: { writeTerminal: "pipe closed" } });
    await harness.controller.sendTo("term-1", "dir\n");
    assert.deepEqual(harness.actions.at(-1), {
      type: "interaction_notice_set",
      notice: "pipe closed",
    });
  }

  {
    const harness = createHarness();
    await harness.controller.clearById("term-1");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_active_set",
      "terminal_snapshot_loaded",
    ]);
    assert.deepEqual(harness.apiCalls[0], { name: "clearTerminal", args: ["sess-1", "term-1"] });
  }

  {
    const harness = createHarness();
    await harness.controller.restartById("term-1");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_active_set",
      "terminal_snapshot_loaded",
    ]);
    assert.deepEqual(harness.apiCalls[0], {
      name: "restartTerminal",
      args: ["sess-1", "term-1", { cols: 100, rows: 30 }],
    });
  }

  {
    const harness = createHarness();
    await harness.controller.closeActive();
    assert.deepEqual(harness.apiCalls[0], { name: "closeTerminal", args: ["sess-1", "term-1"] });
    assert.deepEqual(harness.actions[0], {
      type: "terminal_event",
      event: { type: "closed", session_id: "sess-1", terminal_id: "term-1" },
    });
  }

  {
    const harness = createHarness();
    await harness.controller.selectBottomDrawerKind("terminal");
    assert.equal(harness.apiCalls[0].name, "openTerminal");
    assert.deepEqual(harness.actions.at(-1), {
      type: "workbench_surface_activated",
      placement: "bottom",
      kind: "terminal",
    });
    assert.equal(harness.actions.some((action) => action.placement === "right"), false);
  }

  {
    const harness = createHarness();
    await harness.controller.selectBottomDrawerKind("run_output");
    assert.deepEqual(harness.apiCalls, []);
    assert.deepEqual(harness.actions[0], {
      type: "workbench_surface_activated",
      placement: "bottom",
      kind: "run_output",
    });
  }

  {
    const harness = createHarness({
      state: baseState({
        terminal: {
          activeTerminalId: "term-1",
          terminalIds: ["term-1"],
          sessions: { "term-1": { terminalId: "term-1" } },
        },
        workbench: {
          rightPanel: {
            surfaces: [
              {
                id: "right:terminal:term-2",
                kind: "terminal",
                terminalId: "term-2",
                terminalIds: ["term-2"],
                activeTerminalId: "term-2",
              },
            ],
          },
        },
      }),
    });
    const result = await harness.controller.openRightPanelSurface();
    assert.equal(result, "term-3");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_snapshot_loaded",
      "terminal_active_set",
      "workbench_surface_opened",
    ]);
    assert.equal(harness.actions[2].kind, "terminal");
    assert.equal(harness.actions[2].placement, "right");
    assert.equal(harness.actions[2].title, "Shell Surface");
    assert.deepEqual(harness.actions[2].terminalIds, ["term-3"]);
    assert.equal(harness.actions.some((action) => action.type === "set_inspector"), false);
  }

  {
    const harness = createHarness({
      appCapabilities: {
        surfaces: {
          bottomDrawer: APP_CAPABILITIES.surfaces.bottomDrawer,
          rightPanel: [],
        },
      },
    });
    const result = await harness.controller.openRightPanelSurface();
    assert.equal(result, null);
    assert.deepEqual(harness.apiCalls, []);
    assert.deepEqual(harness.actions, []);
  }

  {
    const surface = { id: "right:terminal:term-1", kind: "terminal", terminalIds: ["term-1"] };
    const harness = createHarness();
    const result = await harness.controller.splitRightPanelSurface(surface, "vertical");
    assert.equal(result, "term-2");
    assert.deepEqual(harness.actions.at(-1), {
      type: "workbench_terminal_surface_split",
      placement: "right",
      surfaceId: "right:terminal:term-1",
      terminalId: "term-2",
      splitDirection: "vertical",
    });
  }

  {
    const surface = { id: "right:terminal:term-1", kind: "terminal" };
    const harness = createHarness();
    harness.controller.activateRightPanelPane(surface, "term-1");
    assert.deepEqual(harness.actions, [
      {
        type: "workbench_terminal_surface_terminal_activated",
        placement: "right",
        surfaceId: "right:terminal:term-1",
        terminalId: "term-1",
      },
      { type: "terminal_active_set", terminalId: "term-1" },
    ]);
  }

  {
    const surface = { id: "right:terminal:term-1", kind: "terminal" };
    const harness = createHarness();
    const result = await harness.controller.closeRightPanelPane(surface, "term-1");
    assert.equal(result, "term-1");
    assert.deepEqual(actionTypes(harness.actions), [
      "terminal_event",
      "workbench_terminal_surface_terminal_closed",
    ]);
    assert.deepEqual(harness.actions[1], {
      type: "workbench_terminal_surface_terminal_closed",
      placement: "right",
      surfaceId: "right:terminal:term-1",
      terminalId: "term-1",
    });
  }
}
