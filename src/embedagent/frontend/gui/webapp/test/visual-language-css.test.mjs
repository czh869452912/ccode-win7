import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STYLE_ROOT = path.join(WEBAPP_ROOT, "src", "styles");

function read(name) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", name), "utf8").replace(/\r\n?/g, "\n");
}

function imports(source) {
  return Array.from(source.matchAll(/@import\s+["']([^"']+)["'];/g), (match) => match[1]);
}

export function runVisualLanguageCssTests() {
  const root = read("styles.css");
  assert.deepEqual(imports(root), [
    "./styles/tokens.css",
    "./styles/base.css",
    "./styles/shell.css",
    "./styles/timeline.css",
    "./styles/composer.css",
    "./styles/overlays.css",
    "./styles/contributions.css",
  ]);
  assert.equal(root.split("\n").filter((line) => line.trim() && !line.startsWith("@import")).length, 0);

  const files = fs.readdirSync(STYLE_ROOT).filter((name) => name.endsWith(".css"));
  assert.deepEqual(files.sort(), [
    "base.css", "composer.css", "contributions.css", "overlays.css", "shell.css",
    "timeline.css", "tokens.css",
  ]);
  for (const file of files) {
    const source = fs.readFileSync(path.join(STYLE_ROOT, file), "utf8");
    assert.equal(source.split(/\r?\n/).length <= 800, true, `${file} exceeds 800 lines`);
  }

  const tokens = read("styles/tokens.css");
  assert.equal(tokens.includes("--bg-canvas: #101112"), true);
  assert.equal(tokens.includes("--color-success"), true);
  assert.equal(tokens.includes("--color-warning"), true);
  assert.equal(tokens.includes("--color-info"), true);

  const shell = read("styles/shell.css");
  const timeline = read("styles/timeline.css");
  const composer = read("styles/composer.css");
  const overlays = read("styles/overlays.css");
  const contributions = read("styles/contributions.css");
  assert.equal(shell.includes(".agent-shell"), true);
  assert.equal(shell.includes(".session-rail"), true);
  assert.equal(shell.includes("@media (max-width: 700px)"), true);
  assert.equal(timeline.includes(".timeline-message-row"), true);
  assert.equal(timeline.includes(".tool-activity-summary"), true);
  assert.equal(composer.includes(".composer-inner"), true);
  assert.equal(composer.includes(".composer-primary-action"), true);
  assert.equal(overlays.includes(".cmd-palette"), true);
  assert.equal(contributions.includes(".contribution-outlet"), true);
  assert.equal(contributions.includes(".terminal-shell-panes.split-vertical"), true);

  const all = [shell, timeline, composer, overlays, contributions].join("\n");
  for (const retired of ["right-panel", "bottom-drawer", "workbench-layout"]) {
    assert.equal(all.includes(retired), false, retired);
  }
}
