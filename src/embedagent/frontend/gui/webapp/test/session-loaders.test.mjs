import assert from "node:assert/strict";

import {
  LOADER_REQUESTS,
  createLoaderRequestExecutor,
  deriveSessionActivation,
  loadSessionCommandCapabilities,
} from "../src/app-runtime/session-loaders.js";

function createRecordedLoaders() {
  const calls = [];
  const record = (name) => (...args) => {
    calls.push({ name, args });
    return `${name}:done`;
  };
  return {
    calls,
    loaders: {
      loadAppBootstrap: record("loadAppBootstrap"),
      loadActiveWorkspaceData: record("loadActiveWorkspaceData"),
      loadSessions: record("loadSessions"),
      loadSession: record("loadSession"),
      loadTasks: record("loadTasks"),
      loadArtifacts: record("loadArtifacts"),
      loadPermissionContext: record("loadPermissionContext"),
      loadFileChildren: record("loadFileChildren"),
      loadSessionCommandCapabilities: record("loadSessionCommandCapabilities"),
    },
  };
}

async function flush(result) {
  return await result;
}

export async function runSessionLoadersTests() {
  const { calls, loaders } = createRecordedLoaders();
  const execute = createLoaderRequestExecutor(loaders);

  assert.equal(await flush(execute({ name: LOADER_REQUESTS.LOAD_APP_BOOTSTRAP })), "loadAppBootstrap:done");
  assert.equal(calls.at(-1).name, "loadAppBootstrap");

  await execute({
    name: LOADER_REQUESTS.LOAD_ACTIVE_WORKSPACE_DATA,
    sessionId: "sess-1",
    assumeWorkspace: true,
  });
  assert.deepEqual(calls.at(-1), {
    name: "loadActiveWorkspaceData",
    args: ["sess-1", true],
  });

  await execute({ name: LOADER_REQUESTS.LOAD_SESSIONS });
  assert.deepEqual(calls.at(-1), { name: "loadSessions", args: [] });

  await execute({ name: LOADER_REQUESTS.LOAD_SESSION, sessionId: "sess-2" });
  assert.deepEqual(calls.at(-1), { name: "loadSession", args: ["sess-2"] });

  await execute({ name: LOADER_REQUESTS.LOAD_TASKS, sessionId: "sess-3" });
  assert.deepEqual(calls.at(-1), { name: "loadTasks", args: ["sess-3"] });

  await execute({ name: LOADER_REQUESTS.LOAD_ARTIFACTS });
  assert.deepEqual(calls.at(-1), { name: "loadArtifacts", args: [] });

  await execute({ name: LOADER_REQUESTS.LOAD_PERMISSION_CONTEXT, sessionId: "sess-4" });
  assert.deepEqual(calls.at(-1), { name: "loadPermissionContext", args: ["sess-4"] });

  await execute({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN });
  assert.deepEqual(calls.at(-1), { name: "loadFileChildren", args: ["."] });

  await execute({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN, path: "src" });
  assert.deepEqual(calls.at(-1), { name: "loadFileChildren", args: ["src"] });

  await execute({ name: LOADER_REQUESTS.LOAD_SESSION_CAPABILITIES });
  assert.deepEqual(calls.at(-1), { name: "loadSessionCommandCapabilities", args: [] });

  const beforeNoOps = calls.length;
  await execute({ name: "unknown_loader" });
  await execute({});
  await execute(null);
  await execute({ name: LOADER_REQUESTS.LOAD_SESSION });
  await execute({ name: LOADER_REQUESTS.LOAD_TASKS });
  await execute({ name: LOADER_REQUESTS.LOAD_PERMISSION_CONTEXT });
  assert.equal(calls.length, beforeNoOps);

  const missingOptionalExecutor = createLoaderRequestExecutor({});
  assert.equal(await missingOptionalExecutor({ name: LOADER_REQUESTS.LOAD_APP_BOOTSTRAP }), undefined);
  assert.equal(await missingOptionalExecutor({ name: LOADER_REQUESTS.LOAD_FILE_CHILDREN }), undefined);

  const activation = deriveSessionActivation(
    {
      snapshot: {
        session_id: "sess-bootstrap",
        status: "waiting_permission",
        current_mode: "debug",
        pending_interaction_valid: true,
        pending_interaction: {
          interaction_id: "perm-bootstrap",
          kind: "permission",
        },
      },
      history: {
        history_source: "step_events",
        integrity: { status: "healthy", event_count: 12 },
        activities: [
          {
            kind: "user",
            id: "activity-user",
            turn_id: "turn-1",
            content: "Inspect parser",
            projection_source: "session_state",
          },
          {
            kind: "tool",
            id: "activity-tool",
            turn_id: "turn-1",
            step_id: "step-1",
            step_index: 1,
            tool_name: "read_file",
            call_id: "call-1",
            arguments: { path: "src/parser.c" },
            status: "success",
            projection_source: "session_state",
          },
        ],
        turns: [
          {
            turn_id: "turn-1",
            user_text: "Inspect parser",
            steps: [
              {
                step_id: "step-1",
                step_index: 1,
                reasoning: "Read parser entry point",
                assistant_text: "Parser inspected.",
                tool_calls: [
                  {
                    call_id: "call-1",
                    tool_name: "read_file",
                    tool_label: "Read File",
                    status: "success",
                    arguments: { path: "src/parser.c" },
                  },
                ],
              },
            ],
          },
        ],
      },
      plan: { title: "Parser plan", steps: [] },
      permission_context: { session_id: "sess-bootstrap", rules: [{ category: "workspace_write" }] },
      capabilities: {
        commands: [
          {
            name: "resources",
            usage: "/resources [reload]",
            summary: "Reload resources",
            active: true,
          },
        ],
      },
    },
    "sess-bootstrap",
  );

  assert.equal(activation.sessionId, "sess-bootstrap");
  assert.equal(activation.snapshot.session_id, "sess-bootstrap");
  assert.equal(activation.snapshot.current_mode, "debug");
  assert.equal(activation.snapshot.status, "waiting_permission");
  assert.equal(activation.activities.length, 2);
  assert.equal(activation.activities[0].kind, "user");
  assert.equal(activation.activities[0].projectionSource, "session_state");
  assert.equal(activation.activities[1].toolName, "read_file");
  assert.equal(activation.activities[1].projectionSource, "session_state");
  assert.deepEqual(activation.historyIntegrity, { status: "healthy", event_count: 12 });
  assert.equal(activation.plan.title, "Parser plan");
  assert.equal(activation.permissionContext.rules[0].category, "workspace_write");
  assert.equal(activation.capabilities.commands[0].usage, "/resources [reload]");

  const sparseActivation = deriveSessionActivation(null, "sess-empty");
  assert.equal(sparseActivation.sessionId, "sess-empty");
  assert.equal(sparseActivation.snapshot.session_id, "");
  assert.deepEqual(sparseActivation.activities, []);
  assert.equal(sparseActivation.historyIntegrity, null);
  assert.equal(sparseActivation.plan, null);
  assert.equal(sparseActivation.permissionContext, null);
  assert.deepEqual(sparseActivation.capabilities, { commands: [] });

  const capabilityActions = [];
  const loadedCapabilities = await loadSessionCommandCapabilities({
    fetchJson: async (url) => {
      assert.equal(url, "/api/sessions/capabilities");
      return {
        commands: [
          {
            name: "help",
            usage: "/help",
            summary: "Show commands",
            active: true,
          },
        ],
      };
    },
    dispatch: (action) => capabilityActions.push(action),
  });
  assert.equal(loadedCapabilities.commands[0].usage, "/help");
  assert.deepEqual(capabilityActions, [
    {
      type: "session_capabilities_loaded",
      capabilities: loadedCapabilities,
    },
  ]);
}
