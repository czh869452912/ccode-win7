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

  const appSource = readSource("App.jsx");
  assert.equal(appSource.includes("paletteCommands"), true);
  assert.equal(appSource.includes("activeWorkspaceId"), true);
  assert.equal(appSource.includes("sessions={state.sessions}"), true);
  assert.equal(appSource.includes("currentSessionId={state.currentSessionId}"), true);
  assert.equal(appSource.includes("workspaces={state.app.workspaces}"), true);
  assert.equal(appSource.includes("keybindings={DEFAULT_KEYBINDINGS}"), true);
  assert.equal(appSource.includes("onSelectSession={(sessionId) =>"), true);
  assert.equal(appSource.includes("void loadSession(sessionId)"), true);
  assert.equal(appSource.includes("onSelectWorkspace={(workspaceId) =>"), true);
  assert.equal(appSource.includes("void activateWorkspace(workspaceId)"), true);
}
