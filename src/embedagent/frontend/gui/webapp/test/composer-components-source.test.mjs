import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8").replace(/\r\n?/g, "\n");
}

function assertNoCoreBoundaryLeak(source, label) {
  assert.equal(source.includes("fetch("), false, `${label} must not fetch`);
  assert.equal(source.includes("transcript"), false, `${label} must not mention transcript state`);
  assert.equal(source.includes("PermissionPolicy"), false, `${label} must not import permission policy`);
  assert.equal(source.includes("embedagent"), false, `${label} must stay in GUI frontend modules`);
}

export function runComposerComponentsSourceTests() {
  const menuSource = readSource("components", "composer", "ComposerCommandMenu.jsx");
  assert.equal(menuSource.includes('data-testid="composer-command-menu"'), true);
  assert.equal(menuSource.includes("composer-menu-group"), true);
  assert.equal(menuSource.includes("composer-menu-item"), true);
  assert.equal(menuSource.includes("composer-menu-empty"), true);
  assert.equal(menuSource.includes("onMouseDown"), true);
  assertNoCoreBoundaryLeak(menuSource, "ComposerCommandMenu");

  const actionsSource = readSource("components", "composer", "ComposerPrimaryActions.jsx");
  assert.equal(actionsSource.includes('data-testid="composer-primary-action"'), true);
  assert.equal(actionsSource.includes('data-testid="composer-stop-action"'), true);
  assert.equal(actionsSource.includes("composer-primary-action"), true);
  assert.equal(actionsSource.includes("composer-stop-action"), true);
  assertNoCoreBoundaryLeak(actionsSource, "ComposerPrimaryActions");

  const interactionPanelSource = readSource("components", "composer", "ComposerInteractionPanel.jsx");
  assert.equal(interactionPanelSource.includes("busy = false"), true);
  assert.equal(interactionPanelSource.includes("disabled={busy}"), true);
  assert.equal(interactionPanelSource.includes("disabled={busy || !hasAnswer}"), true);
  assertNoCoreBoundaryLeak(interactionPanelSource, "ComposerInteractionPanel");
}
