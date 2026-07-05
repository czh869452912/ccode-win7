import assert from "node:assert/strict";

import { createActiveWorkspaceDataLoader } from "../src/app-runtime/active-workspace-data-loader.js";

export async function runActiveWorkspaceDataLoaderTests() {
  const calls = [];
  const fallbackCapabilities = { sourceControl: { enabled: true } };
  const declaredCapabilities = { sourceControl: { enabled: false } };
  const loader = createActiveWorkspaceDataLoader({
    getAppCapabilities: () => fallbackCapabilities,
    loadSessions: async () => calls.push(["sessions"]),
    loadSessionCommandCapabilities: async () => calls.push(["capabilities"]),
    loadFileChildren: async (path, options = {}) =>
      calls.push(["files", path, options.appCapabilities]),
    loadStatus: async (refresh, assumeWorkspace, appCapabilities) =>
      calls.push(["source_control", refresh, assumeWorkspace, appCapabilities]),
  });

  await loader.loadActiveWorkspaceData("sess-active", true, declaredCapabilities);

  assert.deepEqual(calls, [
    ["sessions"],
    ["capabilities"],
    ["files", ".", declaredCapabilities],
    ["source_control", false, true, declaredCapabilities],
  ]);

  calls.length = 0;
  await loader.loadActiveWorkspaceData("sess-active", false);

  assert.deepEqual(calls, [
    ["sessions"],
    ["capabilities"],
    ["files", ".", fallbackCapabilities],
    ["source_control", false, false, fallbackCapabilities],
  ]);
}
