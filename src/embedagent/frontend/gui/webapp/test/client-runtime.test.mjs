import assert from "node:assert/strict";

import { createBrowserAppRuntime } from "../src/app-runtime/browser-app-runtime.js";
import { initialState } from "../src/client-runtime/runtime-reducer.js";

function appBootstrap() {
  return {
    schema_version: 2,
    app: { shell_version: 1, product_name: "EmbedAgent", protocol: "gui_app_shell_v1" },
    workspaces: [],
    active_workspace: null,
    has_active_workspace: false,
    shell: {
      schema_version: 2,
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
    last_failure: null,
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
  let receiveSocketMessage = () => {};
  const channel = {
    onMessage(callback) { receiveSocketMessage = callback; return () => {}; },
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
      schema_version: 2,
      event_cursor: 0,
      thread: {
        id: sessionId,
        title: "Session",
        archived: false,
        current_mode: "explore",
        status: "idle",
        updated_at: "2026-08-13T00:00:00Z",
        pending_interaction: false,
      },
      snapshot: { session_id: sessionId, status: "idle", current_mode: "explore" },
      history: { activities: [], integrity: {} },
      capabilities: {
        schema_version: 2,
        modes: [],
        commands: [],
        tools: [],
        workflow_packages: [],
        agent_application: {},
        agent_applications: [],
        resources: [],
        model_profiles: [],
        empty_state: {},
      },
      plan: null,
      permission_context: {},
    }),
    createSession: async () => ({ session_id: "s-new", status: "idle" }),
    setSessionMode: async () => ({}),
    cancelSession: async () => ({}),
    sendSessionMessage: async () => ({}),
    openSessionEvents: () => channel,
  };
  const browser = createBrowserHarness();
  const actions = [];
  const runtime = createBrowserAppRuntime({
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
    "dispatchAction",
  ]);

  await runtime.start();
  await runtime.start();
  assert.deepEqual(calls, ["loadAppBootstrap"]);
  assert.equal(browser.listenerCount(), 1);

  await runtime.actions.selectSession("s-1");
  assert.equal(actions.some((action) => action.type === "session_activated"), true);
  receiveSocketMessage({
    type: "session_event",
    data: {
      schema_version: 2,
      event_id: "event-1",
      session_id: "s-1",
      sequence: 1,
      event_kind: "assistant.delta",
      timestamp: "2026-08-13T00:00:01Z",
      payload: { text: "hello" },
    },
  });
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(actions.some((action) => action.type === "assistant_delta"), true);

  runtime.close();
  runtime.close();
  assert.equal(socketCloseCalls, 1);
  assert.equal(browser.listenerCount(), 0);
  assert.equal(browser.pendingTimerCount(), 0);
  await assert.rejects(runtime.actions.selectSession("s-1"), /browser_app_runtime_closed/);

  let resolveLateBootstrap;
  const lateActions = [];
  const lateRuntime = createBrowserAppRuntime({
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
