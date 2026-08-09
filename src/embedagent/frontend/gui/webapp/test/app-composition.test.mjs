import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export function runAppCompositionTests() {
  const appSource = fs.readFileSync(path.join(WEBAPP_ROOT, "src", "App.jsx"), "utf8");
  const clientRuntimeSource = fs.readFileSync(
    path.join(WEBAPP_ROOT, "src", "client-runtime", "client-runtime.js"), "utf8");
  const shellRuntimeSource = fs.readFileSync(
    path.join(WEBAPP_ROOT, "src", "client-runtime", "use-agent-shell-runtime.js"), "utf8");
  assert.equal(appSource.includes("fetch("), false);
  assert.equal(appSource.includes("new WebSocket"), false);
  assert.equal(appSource.includes("C/C++"), false);
  assert.equal(appSource.includes("Clang"), false);
  assert.equal(appSource.includes("read_file"), false);
  assert.equal(appSource.includes("run_recipe"), false);
  assert.equal(appSource.includes("report_quality_v2"), false);
  assert.equal(appSource.includes("task_status"), false);
  assert.equal(appSource.includes("createAgentAppProtocolAdapter"), false);
  assert.equal(appSource.includes("createClientRuntime"), false);
  assert.equal(appSource.includes("useAgentShellRuntime"), true);
  assert.equal(appSource.includes("<AgentShell"), true);
  assert.equal(shellRuntimeSource.includes("createClientRuntime"), true);
  for (const factory of [
    "createComposerController",
    "createSessionController",
    "createSocketMessageController",
    "createTerminalController",
    "createWorkbenchCommandController",
    "createWorkspaceController",
  ]) {
    assert.equal(appSource.includes(factory), false, factory);
    assert.equal(clientRuntimeSource.includes(factory), true, factory);
  }
  const appRuntimeImports = appSource.match(/from "\.\/app-runtime\/[^"]+"/g) || [];
  assert.deepEqual(appRuntimeImports, []);
}
