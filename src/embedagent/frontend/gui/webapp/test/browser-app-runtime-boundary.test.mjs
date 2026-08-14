import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { createBrowserAppRuntime } from "../src/app-runtime/browser-app-runtime.js";

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

export function runBrowserAppRuntimeBoundaryTests() {
  assert.equal(typeof createBrowserAppRuntime, "function");

  const sessionRuntimeSource = source("../src/session-runtime/session-client-runtime.js");
  for (const token of [
    "window",
    "document",
    "workspace",
    "terminal",
    "preview",
    "sourceControl",
    "source-control",
  ]) {
    assert.equal(sessionRuntimeSource.includes(token), false, `session runtime owns ${token}`);
  }

  const browserRuntimeSource = source("../src/app-runtime/browser-app-runtime.js");
  assert.equal(browserRuntimeSource.includes("new SessionClientRuntime"), true);
  for (const controller of [
    "createWorkspaceController",
    "createTerminalController",
    "createPreviewController",
    "createSourceControlController",
  ]) {
    assert.equal(browserRuntimeSource.includes(controller), true, controller);
  }
  for (const retiredSyncOwner of [
    "createSessionActivationController",
    "createSessionTransportHandle",
    "applySessionTransportEvent",
  ]) {
    assert.equal(browserRuntimeSource.includes(retiredSyncOwner), false, retiredSyncOwner);
  }

  const hookSource = source("../src/client-runtime/use-agent-shell-runtime.js");
  assert.equal(hookSource.includes("createBrowserAppRuntime"), true);
  assert.equal(hookSource.includes("createClientRuntime"), false);

  assert.throws(
    () => readFileSync(fileURLToPath(new URL("../src/client-runtime/client-runtime.js", import.meta.url))),
    /ENOENT/,
  );
}
