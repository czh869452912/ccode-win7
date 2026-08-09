import assert from "node:assert/strict";

import { initialState, runtimeReducer } from "../src/client-runtime/runtime-reducer.js";
import { reduceAppState } from "../src/client-runtime/reducers/app-reducer.js";
import { createSessionState, reduceSessionState } from "../src/client-runtime/reducers/session-reducer.js";
import { createTransportState, reduceTransportState } from "../src/client-runtime/reducers/transport-reducer.js";
import { normalizeProtocolCapabilities } from "../src/session-runtime/protocol-normalizer.js";
import {
  capabilitySnapshot,
  toolDescriptor,
  workflowPackageDescriptor,
} from "./protocol-fixtures.mjs";

export function runClientRuntimeReducerTests() {
  const app = reduceAppState(
    { ...initialState.app, bootstrapLoaded: true },
    { type: "app_shell_settings_changed", patch: { confirm_workspace_switch: false } },
  );
  assert.equal(app.settings.confirm_workspace_switch, false);

  const session = reduceSessionState(createSessionState(), {
    type: "mode_requested",
    mode: "verify",
  });
  assert.equal(session.requestedMode, "verify");
  assert.equal(Object.hasOwn(session, "terminal"), false);

  const transport = reduceTransportState(createTransportState(), {
    type: "terminal_active_set",
    terminalId: "term-a",
  });
  assert.equal(transport.terminal.activeTerminalId, "term-a");
  assert.equal(Object.hasOwn(transport, "snapshot"), false);

  const activated = runtimeReducer(initialState, {
    type: "session_activated",
    sessionId: "matrix-session",
    snapshot: {
      session_id: "matrix-session",
      current_mode: "",
      workflow_state: { workflow: { id: "future-workflow", items: [] } },
    },
    capabilities: normalizeProtocolCapabilities(capabilitySnapshot({
      tools: [toolDescriptor("future_tool", "Future Tool", { renderer_key: "unknown" })],
      workflow_packages: [workflowPackageDescriptor("future-workflow", "Future Workflow")],
    })),
    activities: [{ id: "future-activity", kind: "future_activity", content: "opaque" }],
  });

  assert.equal(activated.thread.currentSessionId, "matrix-session");
  assert.equal(activated.sessionCapabilities.toolCatalog.future_tool.label, "Future Tool");
  assert.equal(activated.sessionCapabilities.workflowPackages[0].id, "future-workflow");
  assert.equal(activated.activities[0].kind, "future_activity");
  assert.equal(activated.snapshot.workflow_state.workflow.id, "future-workflow");
  assert.equal(Object.hasOwn(activated, "tasks"), false);
}

runClientRuntimeReducerTests();
console.log("client runtime reducer checks passed");
