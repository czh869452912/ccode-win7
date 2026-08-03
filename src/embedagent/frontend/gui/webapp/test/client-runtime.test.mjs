import assert from "node:assert/strict";

import { createClientRuntime } from "../src/client-runtime/client-runtime.js";
import { initialState } from "../src/client-runtime/runtime-reducer.js";

function appBootstrap() {
  return {
    schema_version: 1,
    app: { shell_version: 1, product_name: "EmbedAgent", protocol: "gui_app_shell_v1" },
    workspaces: [],
    active_workspace: null,
    has_active_workspace: false,
    shell: {
      schema_version: 1,
      commands: [],
      surfaces: [],
      keybindings: [],
      tool_presentations: [],
      timeline_items: [],
      interactions: [],
    },
    settings: {
      confirm_workspace_switch: true,
      show_diagnostics_badge: true,
    },
    diagnostics: {},
    last_error: "",
  };
}

function createBrowserHarness() {
  let nextTimerId = 1;
  const timers = new Map();
  const listeners = new Map();
  const documentObject = {
    activeElement: null,
    documentElement: { style: { setProperty() {} } },
    querySelector() { return null; },
  };
  const windowObject = {
    document: documentObject,
    location: { search: "" },
    addEventListener(kind, listener) { listeners.set(kind, listener); },
    removeEventListener(kind, listener) {
      if (listeners.get(kind) === listener) listeners.delete(kind);
    },
    setTimeout(callback) {
      const id = nextTimerId;
      nextTimerId += 1;
      timers.set(id, callback);
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
    prompt() { return null; },
    confirm() { return false; },
  };
  return {
    documentObject,
    windowObject,
    getComputedStyleFn: () => ({ getPropertyValue: () => "" }),
    listenerCount: () => listeners.size,
    pendingTimerCount: () => timers.size,
  };
}

export async function runClientRuntimeTests() {
  const calls = [];
  let socketCloseCalls = 0;
  const channel = {
    onMessage() { return () => {}; },
    onStateChange() { return () => {}; },
    close() { socketCloseCalls += 1; },
  };
  const protocol = {
    loadAppBootstrap: async () => { calls.push("loadAppBootstrap"); return appBootstrap(); },
    openWorkspacePath: async () => appBootstrap(),
    activateWorkspace: async () => appBootstrap(),
    removeWorkspace: async () => appBootstrap(),
    listSessions: async () => ({ sessions: [] }),
    loadSessionCapabilities: async () => ({}),
    loadSessionBootstrap: async (sessionId) => ({
      event_cursor: 0,
      snapshot: { session_id: sessionId, status: "idle", current_mode: "explore" },
      history: { activities: [], integrity: {} },
      capabilities: {},
      plan: null,
    }),
    createSession: async () => ({ session_id: "s-new", status: "idle" }),
    setSessionMode: async () => ({}),
    cancelSession: async () => ({}),
    sendSessionMessage: async () => ({}),
    openSessionEvents: () => channel,
  };
  const browser = createBrowserHarness();
  const actions = [];
  const runtime = createClientRuntime({
    protocol,
    dispatch: actions.push.bind(actions),
    getState: () => initialState,
    browser,
  });

  assert.deepEqual(Object.keys(runtime).sort(), ["actions", "close", "start"]);
  assert.deepEqual(Object.keys(runtime.actions), [
    "activateWorkspace",
    "selectSession",
    "createSession",
    "renameSession",
    "archiveSession",
    "forkSession",
    "setMode",
    "cancelSession",
    "submitText",
    "respondToInteraction",
    "executeCommand",
    "openContribution",
  ]);

  await runtime.start();
  await runtime.start();
  assert.deepEqual(calls, ["loadAppBootstrap"]);
  assert.equal(browser.listenerCount(), 1);

  runtime.close();
  runtime.close();
  assert.equal(socketCloseCalls, 1);
  assert.equal(browser.listenerCount(), 0);
  assert.equal(browser.pendingTimerCount(), 0);
  await assert.rejects(runtime.actions.selectSession("s-1"), /client_runtime_closed/);

  let resolveLateBootstrap;
  const lateActions = [];
  const lateRuntime = createClientRuntime({
    protocol: {
      ...protocol,
      loadAppBootstrap: () => new Promise((resolve) => { resolveLateBootstrap = resolve; }),
      openSessionEvents: () => ({
        onMessage() { return () => {}; },
        onStateChange() { return () => {}; },
        close() {},
      }),
    },
    dispatch: lateActions.push.bind(lateActions),
    getState: () => initialState,
    browser: createBrowserHarness(),
  });
  const lateStart = lateRuntime.start();
  const actionCountAtClose = lateActions.length;
  lateRuntime.close();
  resolveLateBootstrap(appBootstrap());
  await lateStart;
  assert.equal(
    lateActions.length,
    actionCountAtClose,
    "closed runtime must ignore late asynchronous state writes",
  );
}
