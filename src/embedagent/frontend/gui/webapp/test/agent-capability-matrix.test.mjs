import assert from "node:assert/strict";

import { buildAppCapabilityModel } from "../src/app-runtime/app-capability-model.js";
import { normalizeAppBootstrap } from "../src/app-shell/model.js";
import { normalizeProtocolCapabilities } from "../src/session-runtime/protocol-normalizer.js";
import { buildSessionCapabilityModel } from "../src/session-runtime/session-capability-model.js";
import {
  capabilitySnapshot,
  modeDescriptor,
  toolDescriptor,
  workflowPackageDescriptor,
} from "./protocol-fixtures.mjs";

const AGENTS = [
  { id: "empty", product: "", mode: "", workflow: "", tools: [] },
  { id: "embedagent.generic", product: "Generic Agent", mode: "explore", workflow: "", tools: ["read_file"] },
  { id: "embedagent.default_c_cpp", product: "C/C++ Agent", mode: "build", workflow: "cpp", tools: ["run_recipe"] },
  { id: "embedagent.python", product: "Python Agent", mode: "build", workflow: "", tools: ["python_check"] },
  { id: "embedagent.html", product: "HTML Agent", mode: "build", workflow: "", tools: ["html_check"] },
  { id: "tests.specialized", product: "Project Inspector", mode: "inspect", workflow: "project", tools: ["project_check"] },
];

export function runAgentCapabilityMatrixTests() {
  for (const fixture of AGENTS) {
    const app = normalizeAppBootstrap({
      app: { shell_version: 1, product_name: fixture.product, protocol: "gui_app_shell_v1" },
      capabilities: { empty_state: { primary: "" } },
    });
    const session = normalizeProtocolCapabilities(capabilitySnapshot({
      modes: fixture.mode ? [modeDescriptor(fixture.mode)] : [],
      tools: fixture.tools.map((name) => toolDescriptor(name)),
      workflow_packages: fixture.workflow
        ? [workflowPackageDescriptor(fixture.workflow)]
        : [],
    }));
    const appModel = buildAppCapabilityModel(app.capabilities);
    const sessionModel = buildSessionCapabilityModel(session);
    assert.equal(app.app.productName, fixture.product);
    assert.equal(Object.keys(sessionModel.toolCatalog).length, fixture.tools.length);
    assert.equal(sessionModel.sessionCapabilities.modes.length, fixture.mode ? 1 : 0);
    assert.equal(
      sessionModel.sessionCapabilities.workflowPackages.length,
      fixture.workflow ? 1 : 0,
    );
    assert.ok(appModel);
  }
}

runAgentCapabilityMatrixTests();
console.log("Agent capability matrix checks passed");
