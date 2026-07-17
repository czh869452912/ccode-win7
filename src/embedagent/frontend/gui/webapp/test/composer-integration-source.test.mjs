import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8").replace(/\r\n?/g, "\n");
}

export function runComposerIntegrationSourceTests() {
  const composerSource = readSource("components", "Composer.jsx");
  assert.equal(composerSource.includes("buildComposerInteractionModel"), true);
  assert.equal(composerSource.includes("moveComposerMenuIndex"), true);
  assert.equal(composerSource.includes("selectComposerMenuItem"), true);
  assert.equal(composerSource.includes("detectComposerTrigger"), false);
  assert.equal(composerSource.includes("replaceComposerTrigger"), false);
  assert.equal(composerSource.includes("ComposerCommandMenu"), true);
  assert.equal(composerSource.includes("ComposerPrimaryActions"), true);
  assert.equal(composerSource.includes("BranchToolbar"), true);
  assert.equal(composerSource.includes("ComposerInteractionPanel"), true);
  assert.equal(composerSource.includes("interactionChrome = {}"), true);
  assert.equal(composerSource.includes("chrome={interactionChrome}"), true);
  assert.equal(composerSource.includes("chrome={chrome.interaction || {}}"), false);
  assert.equal(composerSource.includes("dismissedTriggerKey"), true);
  assert.equal(composerSource.includes("composer-hints"), false);
  assert.equal(composerSource.includes('className="composer-hint"'), false);
  assert.equal(composerSource.includes("commandHints"), false);
  assert.equal(composerSource.includes("fetch("), false);
  assert.equal(composerSource.includes("transcript"), false);
  assert.equal(composerSource.includes("PermissionPolicy"), false);

  const interactionModelSource = readSource("composer", "composer-interaction-model.js");
  assert.equal(interactionModelSource.includes("detectComposerTrigger"), true);
  assert.equal(interactionModelSource.includes("replaceComposerTrigger"), true);
  assert.equal(interactionModelSource.includes("buildComposerCommandItems"), true);
  assert.equal(interactionModelSource.includes("searchComposerCommandItems"), true);
  assert.equal(interactionModelSource.includes("flattenComposerPathCandidates"), true);
  assert.equal(interactionModelSource.includes("searchComposerPathCandidates"), true);
  assert.equal(interactionModelSource.includes("fetch("), false);
  assert.equal(interactionModelSource.includes("transcript"), false);
  assert.equal(interactionModelSource.includes("PermissionPolicy"), false);
  assert.equal(interactionModelSource.includes("commandsFromHints"), false);
  assert.equal(interactionModelSource.includes("commandHints"), false);
  assert.equal(interactionModelSource.includes('group: "command"'), false);

  const appSource = readSource("App.jsx");
  assert.equal(appSource.includes("visibleCommands"), true);
  assert.equal(appSource.includes("composerCommands"), true);
  assert.equal(appSource.includes("commands={composerCommands}"), true);
  assert.equal(appSource.includes("fileTree={state.fileTree}"), true);
  assert.equal(
    appSource.includes("interactionChrome={appChrome.interaction || {}}"),
    true,
  );
  assert.equal(appSource.includes("EMPTY_COMMAND_HINTS"), false);
  assert.equal(appSource.includes("commandHints"), false);
}
