import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function sourcePath(...parts) {
  return path.join(WEBAPP_ROOT, "src", ...parts);
}

function readSource(...parts) {
  return fs.readFileSync(sourcePath(...parts), "utf8").replace(/\r\n?/g, "\n");
}

export function runCommandPaletteSourceTests() {
  const resultsSource = readSource("components", "workbench", "CommandPaletteResults.jsx");
  assert.equal(resultsSource.includes("export default function CommandPaletteResults"), true);
  assert.equal(resultsSource.includes("cmd-palette-group"), true);
  assert.equal(resultsSource.includes("cmd-palette-row"), true);
  assert.equal(resultsSource.includes("cmd-palette-row-shortcut"), true);
  assert.equal(resultsSource.includes("cmd-palette-row-chevron"), true);
  assert.equal(resultsSource.includes("aria-disabled"), true);
  assert.equal(resultsSource.includes('emptyLabel = ""'), true);
  assert.equal(resultsSource.includes("No matching commands, sessions, or workspaces"), false);
  assert.equal(resultsSource.includes("fetch("), false);
  assert.equal(resultsSource.includes("transcript"), false);
  assert.equal(resultsSource.includes("embedagent"), false);

  const paletteSource = readSource("components", "workbench", "CommandPalette.jsx");
  assert.equal(paletteSource.includes("CommandPaletteResults"), true);
  assert.equal(paletteSource.includes("buildCommandPaletteRootGroups"), true);
  assert.equal(paletteSource.includes("buildCommandPaletteSubmenuGroups"), true);
  assert.equal(paletteSource.includes("flattenPaletteGroups"), true);
  assert.equal(paletteSource.includes("viewKind"), true);
  assert.equal(paletteSource.includes("submenuId"), true);
  assert.equal(paletteSource.includes("handleKeyDown"), true);
  assert.equal(paletteSource.includes('event.key === "ArrowDown"'), true);
  assert.equal(paletteSource.includes('event.key === "ArrowUp"'), true);
  assert.equal(paletteSource.includes('event.key === "Enter"'), true);
  assert.equal(paletteSource.includes('event.key === "Backspace"'), true);
  assert.equal(paletteSource.includes("activateItem"), true);
  assert.equal(paletteSource.includes("onSelectSession"), true);
  assert.equal(paletteSource.includes("onSelectWorkspace"), true);
  assert.equal(paletteSource.includes("visibleCommands"), false);

  const modelSource = readSource("workbench", "command-palette-model.js");
  assert.equal(modelSource.includes("buildCommandPaletteRootGroups"), true);
  assert.equal(modelSource.includes("buildCommandPaletteSubmenuGroups"), true);
  assert.equal(modelSource.includes("fetch("), false);
  assert.equal(modelSource.includes("transcript"), false);

  const runtimeSource = readSource("client-runtime", "use-agent-shell-runtime.js");
  const hostSource = readSource("components", "shell", "ShellOverlayHost.jsx");
  assert.equal(runtimeSource.includes("paletteCommands"), true);
  assert.equal(hostSource.includes("activeWorkspaceId={sessions.activeWorkspace?.id"), true);
  assert.equal(hostSource.includes("sessions={sessions.items}"), true);
  assert.equal(hostSource.includes("currentSessionId={sessions.currentId}"), true);
  assert.equal(hostSource.includes("workspaces={sessions.workspaces}"), true);
  assert.equal(hostSource.includes("keybindings={shell.keybindings}"), true);
  assert.equal(hostSource.includes("DEFAULT_KEYBINDINGS"), false);
  assert.equal(runtimeSource.includes("commandById"), false);
  assert.equal(hostSource.includes("onSelect={actions.selectPaletteCommand}"), true);
  assert.equal(hostSource.includes("onSelectSession={actions.selectPaletteSession}"), true);
  assert.equal(hostSource.includes("onSelectWorkspace={actions.selectPaletteWorkspace}"), true);
}
