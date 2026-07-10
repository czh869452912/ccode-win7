import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8").replace(/\r\n?/g, "\n");
}

export function runRightPanelTabsSourceTests() {
  const tabsSource = readSource("components", "workbench", "RightPanelTabs.jsx");
  const commandsSource = readSource("workbench", "commands.js");
  const surfacesSource = readSource("workbench", "surfaces.js");
  const floatingMenuSource = readSource("components", "workbench", "FloatingMenu.jsx");
  const cssSource = readSource("styles.css");

  assert.equal(tabsSource.includes("FloatingMenu"), true);
  assert.equal(tabsSource.includes("right-panel-add-menu-popup"), true);
  assert.equal(tabsSource.includes("right-panel-tab-menu-popup"), true);
  assert.equal(tabsSource.includes("createPortal"), false);
  assert.equal(floatingMenuSource.includes("createPortal"), true);
  assert.equal(floatingMenuSource.includes("document.body"), true);
  assert.equal(floatingMenuSource.includes("Escape"), true);
  assert.equal(floatingMenuSource.includes("getBoundingClientRect"), true);
  assert.equal(tabsSource.includes("SURFACE_COPY"), false);
  assert.equal(tabsSource.includes("rightPanelLauncherSurfaceDefinitions"), true);
  assert.equal(tabsSource.includes("surfaceDefinitionFor"), true);
  assert.equal(tabsSource.includes("RIGHT_PANEL_SURFACES"), false);
  assert.equal(commandsSource.includes("surfaceCommandDefinitions"), true);
  assert.equal(commandsSource.includes('id: "surface.preview"'), false);
  assert.equal(commandsSource.includes('id: "surface.diff"'), false);
  assert.equal(surfacesSource.includes("RIGHT_PANEL_SURFACE_REGISTRY"), true);
  assert.equal(surfacesSource.includes("persistFields"), true);
  assert.equal(surfacesSource.includes("closeBehavior"), true);
  assert.equal(surfacesSource.includes('title: "Preview"'), false);
  assert.equal(surfacesSource.includes('title: "Diff"'), false);
  assert.equal(surfacesSource.includes('title: "Files"'), false);
  assert.equal(surfacesSource.includes('title: "Terminal"'), false);
  assert.equal(surfacesSource.includes('title: "Run Output"'), false);
  assert.equal(surfacesSource.includes('commandLabel: "Open Terminal"'), false);
  assert.equal(surfacesSource.includes('description: "'), false);
  assert.equal(surfacesSource.includes("titleForSurfaceKind(kind, appCapabilities = null)"), true);

  const tabScrollRule = /\.right-panel-tab-scroll\s*\{[\s\S]*?\}/.exec(cssSource)?.[0] || "";
  assert.equal(tabScrollRule.includes("overflow-y: hidden"), true);
  assert.equal(tabScrollRule.includes("overflow-y: visible"), false);
  assert.equal(cssSource.includes(".floating-menu-layer"), true);
  assert.equal(cssSource.includes(".right-panel-tab-strip"), true);
}
