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
  assert.equal(interactionPanelSource.includes("chrome = {}"), true);
  assert.equal(interactionPanelSource.includes("normalizeComposerInteraction(interaction, notice, chrome)"), true);
  assertNoCoreBoundaryLeak(interactionPanelSource, "ComposerInteractionPanel");

  const approvalPanelSource = readSource("components", "composer", "ComposerPendingApprovalPanel.jsx");
  const approvalActionsSource = readSource("components", "composer", "ComposerPendingApprovalActions.jsx");
  const userInputPanelSource = readSource("components", "composer", "ComposerPendingUserInputPanel.jsx");

  assert.equal(approvalPanelSource.includes("buildPermissionResponse"), false);
  assert.equal(approvalPanelSource.includes("PENDING APPROVAL"), false);
  assert.equal(approvalPanelSource.includes("approval.kicker"), true);
  assert.equal(approvalActionsSource.includes('"acceptForSession"'), true);
  assert.equal(approvalActionsSource.includes('"decline"'), true);
  assert.equal(approvalActionsSource.includes('"cancel"'), true);
  assert.equal(approvalActionsSource.includes("Approve once"), false);
  assert.equal(approvalActionsSource.includes("Always allow this session"), false);
  assert.equal(approvalActionsSource.includes("Cancel turn"), false);
  assert.equal(approvalActionsSource.includes("disabled={busy}"), true);
  assert.equal(userInputPanelSource.includes("buildUserInputResponse"), true);
  assert.equal(userInputPanelSource.includes("INPUT REQUIRED"), false);
  assert.equal(userInputPanelSource.includes("Submit"), false);
  assert.equal(userInputPanelSource.includes("mode:"), false);
  assert.equal(userInputPanelSource.includes("disabled={busy || !answer.trim()}"), true);
  assertNoCoreBoundaryLeak(approvalPanelSource, "ComposerPendingApprovalPanel");
  assertNoCoreBoundaryLeak(approvalActionsSource, "ComposerPendingApprovalActions");
  assertNoCoreBoundaryLeak(userInputPanelSource, "ComposerPendingUserInputPanel");
}
