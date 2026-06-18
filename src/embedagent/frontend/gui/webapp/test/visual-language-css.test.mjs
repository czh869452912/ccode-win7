import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STYLES_PATH = path.join(WEBAPP_ROOT, "src", "styles.css");

function readStyles() {
  return fs.readFileSync(STYLES_PATH, "utf8");
}

function extractRootBlock(source) {
  const match = source.match(/:root\s*\{([\s\S]*?)\n\}/);
  return match ? match[1] : "";
}

function assertIncludes(source, needle, label) {
  assert.equal(source.includes(needle), true, label);
}

function assertNotIncludes(source, needle, label) {
  assert.equal(source.includes(needle), false, label);
}

export function runVisualLanguageCssTests() {
  const styles = readStyles();
  const root = extractRootBlock(styles);

  assertIncludes(root, "--bg-canvas: #0f0f10;", "canvas should use T3 neutral dark");
  assertIncludes(root, "--bg-default: #151516;", "default surface should use T3 neutral dark");
  assertIncludes(root, "--bg-subtle: #1c1c1e;", "subtle surface should use T3 neutral dark");
  assertIncludes(root, "--border-default: rgba(255,255,255,.08);", "border should be soft");
  assertIncludes(root, "--border-focus: rgba(255,255,255,.24);", "focus should be neutral");
  assertIncludes(root, "--r-lg: 18px;", "large radius should match T3 composer language");
  assertIncludes(root, "--surface-shadow:", "surface shadow token should exist");
  assertNotIncludes(root, "#0d1117", "root should no longer use GitHub canvas token");
  assertNotIncludes(root, "#161b22", "root should no longer use GitHub default token");

  assertIncludes(styles, ".timeline-shell", "timeline shell should constrain chat column");
  assertIncludes(styles, "max-width: 860px;", "timeline shell should use a T3-like centered width");
  assertIncludes(styles, ".composer::before", "composer should have a top fade like T3");
  assertIncludes(styles, "border-radius: var(--r-lg);", "composer should use the large radius token");
  assertIncludes(styles, ".branch-toolbar", "branch toolbar should be styled");
  assertIncludes(styles, ".branch-toolbar-context", "branch toolbar context group should be styled");
  assertIncludes(styles, ".branch-toolbar-branch", "branch toolbar branch group should be styled");
  assertIncludes(styles, ".branch-toolbar-button", "branch toolbar controls should be styled");
  assertIncludes(styles, "@media (max-width: 720px)", "mobile guardrails should exist");
  assertIncludes(styles, ".right-panel-surface-tab.active", "right panel active surface styling should remain explicit");
  assertIncludes(styles, ".right-panel-tab-scroll", "right panel should use a horizontally scrollable surface tab list");
  assertIncludes(styles, ".right-panel-add-menu-popup", "right panel add-surface menu should be styled");
  assertIncludes(styles, ".right-panel-empty-card", "right panel empty-state surface cards should be styled");
  assertIncludes(styles, ".right-panel-files-surface", "right panel files surface should own a bounded shell");
  assertIncludes(styles, ".diff-panel", "diff panel should keep a dedicated shell");
  assertIncludes(
    styles,
    "background: var(--bg-panel);",
    "panel shells should use a Win7-safe neutral surface token",
  );
}
