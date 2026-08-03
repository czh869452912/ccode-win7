import assert from "node:assert/strict";

import { createAgentAppProtocolAdapter } from "../src/client-runtime/protocol-adapter.js";

export async function runProtocolEnvelopeAdapterTests() {
  const adapter = createAgentAppProtocolAdapter({
    http: {
      request: async ({ path }) => {
        if (path === "/api/app/bootstrap") {
          return {
            protocol: "app_shell_v1",
            version: 1,
            sequence: 1,
            revision: "shell-1",
            payload: { app: { product_name: "" }, capabilities: {} },
          };
        }
        if (path === "/api/sessions/capabilities") {
          return {
            protocol: "capability_v1",
            version: 1,
            sequence: 2,
            revision: "cap-1",
            payload: { modes: [], tools: [] },
          };
        }
        return {
          protocol: "agent_session_v1",
          version: 1,
          sequence: 3,
          revision: "session-1",
          payload: { session_id: "s-1", history: { activities: [] } },
        };
      },
    },
  });

  const app = await adapter.loadAppBootstrap();
  assert.equal(app.app.product_name, "");
  assert.deepEqual(app.protocolEnvelope, {
    protocol: "app_shell_v1",
    version: 1,
    sequence: 1,
    revision: "shell-1",
  });

  const capabilities = await adapter.loadSessionCapabilities();
  assert.deepEqual(capabilities.protocolEnvelope, {
    protocol: "capability_v1",
    version: 1,
    sequence: 2,
    revision: "cap-1",
  });

  const session = await adapter.loadSessionBootstrap("s-1");
  assert.equal(session.session_id, "s-1");
  assert.equal(session.protocolEnvelope.protocol, "agent_session_v1");
}

runProtocolEnvelopeAdapterTests().then(() => {
  console.log("protocol adapter envelope checks passed");
});
