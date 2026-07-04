import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8").replace(/\r\n?/g, "\n");
}

export function runTerminalShellSourceTests() {
  const shellSource = readSource("components", "workbench", "TerminalShell.jsx");
  const bottomDrawerSource = readSource("components", "workbench", "BottomDrawer.jsx");
  const surfaceBodySource = readSource("components", "workbench", "RightPanelSurfaceBody.jsx");
  const cssSource = readSource("styles.css");

  assert.equal(shellSource.includes("export default function TerminalShell"), true);
  assert.equal(shellSource.includes("owner === \"right-panel\""), true);
  assert.equal(shellSource.includes("owner === \"drawer\""), true);
  assert.equal(shellSource.includes("splitDirection === \"vertical\""), true);
  assert.equal(shellSource.includes("terminal-shell-pane"), true);
  assert.equal(shellSource.includes("terminalChrome.newLabel"), true);
  assert.equal(shellSource.includes("chrome.commandPlaceholder"), true);
  assert.equal(shellSource.includes("onSplitVertical"), true);
  assert.equal(shellSource.includes("onClose(terminalId)"), true);
  for (const hardcodedCopy of [
    '"Terminal"',
    '"New terminal"',
    '"Split terminal horizontally"',
    '"Split terminal vertically"',
    '"Terminal session is unavailable."',
    '"Type a command"',
    '"No terminal sessions for this thread yet."',
    '"Drawer"',
    ">New<",
    ">Clear<",
    ">Restart<",
    ">Close<",
  ]) {
    assert.equal(shellSource.includes(hardcodedCopy), false);
  }
  assert.equal(bottomDrawerSource.includes("TerminalShell"), true);
  assert.equal(bottomDrawerSource.includes("terminalChrome"), true);
  assert.equal(bottomDrawerSource.includes("export function TerminalSurface"), false);
  assert.equal(surfaceBodySource.includes("TerminalShell"), true);
  assert.equal(surfaceBodySource.includes("terminalChrome"), true);
  assert.equal(surfaceBodySource.includes("RightPanelTerminalSurface"), false);
  assert.equal(cssSource.includes(".terminal-shell"), true);
  assert.equal(cssSource.includes(".terminal-shell-panes.split-vertical"), true);
}
