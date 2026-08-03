import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SOURCE_ROOT = path.join(WEBAPP_ROOT, "src");
const CONTROLLERS = [
  "file-preview-controller.js",
  "interaction-response-controller.js",
  "session-activation-controller.js",
  "session-controller.js",
  "session-list-controller.js",
  "session-loaders.js",
  "session-transport-controller.js",
  "thread-lifecycle-controller.js",
  "workspace-controller.js",
  "workspace-files-controller.js",
  "preview-controller.js",
  "source-control-controller.js",
  "terminal-controller.js",
];

export function runControllerProtocolOwnershipTests() {
  for (const name of CONTROLLERS) {
    const source = fs.readFileSync(path.join(SOURCE_ROOT, "app-runtime", name), "utf8");
    assert.equal(source.includes("/api/"), false, `${name} must not own API paths`);
    assert.equal(source.includes("fetchJson"), false, `${name} must not accept raw HTTP`);
    assert.equal(source.includes("-api.js"), false, `${name} must not import standalone APIs`);
  }

  for (const relativePath of [
    ["preview", "preview-api.js"],
    ["source-control", "source-control-api.js"],
    ["terminal", "terminal-api.js"],
  ]) {
    assert.equal(
      fs.existsSync(path.join(SOURCE_ROOT, ...relativePath)),
      false,
      `${relativePath.join("/")} must be removed`,
    );
  }
}
