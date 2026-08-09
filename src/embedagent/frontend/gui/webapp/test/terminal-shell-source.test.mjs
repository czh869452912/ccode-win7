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
  const rendererSource = readSource("components", "contributions", "renderer-registry.js");
  const cssSource = readSource("styles", "contributions.css");

  assert.equal(shellSource.includes("export default function TerminalShell"), true);
  assert.equal(shellSource.includes("right-panel"), false);
  assert.equal(shellSource.includes("drawer"), false);
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
  assert.equal(rendererSource.includes("TerminalShell"), true);
  assert.equal(rendererSource.includes("terminalChrome"), true);
  assert.equal(cssSource.includes(".terminal-shell"), true);
  assert.equal(cssSource.includes(".terminal-shell-panes.split-vertical"), true);
}
