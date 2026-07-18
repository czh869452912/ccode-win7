import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export function runAppCompositionTests() {
  const appSource = fs.readFileSync(path.join(WEBAPP_ROOT, "src", "App.jsx"), "utf8");
  assert.equal(appSource.includes("fetch("), false);
  assert.equal(appSource.includes("new WebSocket"), false);
  assert.equal(appSource.includes("C/C++"), false);
  assert.equal(appSource.includes("Clang"), false);
  assert.equal(appSource.includes("read_file"), false);
  assert.equal(appSource.includes("run_recipe"), false);
  assert.equal(appSource.includes("report_quality_v2"), false);
  assert.equal(appSource.includes("task_status"), false);
  assert.equal(appSource.includes("createAgentAppProtocolAdapter"), false);
}

runAppCompositionTests();
console.log("app composition checks passed");
