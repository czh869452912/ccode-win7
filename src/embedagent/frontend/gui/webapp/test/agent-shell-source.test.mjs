import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function source(...parts) {
  return fs.readFileSync(path.join(ROOT, "src", ...parts), "utf8");
}

export function runAgentShellSourceTests() {
  const appSource = source("App.jsx");
  const shellSource = source("components", "shell", "AgentShell.jsx");
  const railSource = source("components", "shell", "SessionRail.jsx");

  assert.equal(appSource.includes("<AgentShell"), true);
  assert.equal(appSource.includes("<RightPanelTabs"), false);
  assert.equal(appSource.includes("<BottomDrawer"), false);
  assert.equal(appSource.includes("<AppSidebarLayout"), false);
  assert.equal(appSource.includes("<Timeline"), false);
  assert.equal(appSource.includes("<Composer"), false);

  assert.equal(railSource.includes('aria-label="Sessions"'), true);
  assert.equal(railSource.includes("aria-expanded={"), true);
  assert.equal(railSource.includes("PanelLeftClose"), true);
  assert.equal(railSource.includes("MoreHorizontal"), true);
  assert.equal(railSource.includes("onSelectSession"), true);

  for (const coreRegion of [
    "SessionRail",
    "SessionTimeline",
    "SessionComposer",
    "SessionStatusFooter",
  ]) {
    assert.equal(shellSource.includes(coreRegion), true);
  }
  assert.equal(shellSource.includes("RightPanel"), false);
  assert.equal(shellSource.includes("BottomDrawer"), false);
}
