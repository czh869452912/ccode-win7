import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readSource(...parts) {
  return fs.readFileSync(path.join(WEBAPP_ROOT, "src", ...parts), "utf8").replace(/\r\n?/g, "\n");
}

export function runPreviewSurfaceSourceTests() {
  const appSource = readSource("App.jsx");
  const previewSurfaceSource = readSource("components", "workbench", "PreviewSurface.jsx");
  const previewControllerSource = readSource("app-runtime", "preview-controller.js");
  const previewModelSource = readSource("session-runtime", "preview-surface-model.js");
  const surfaceBodySource = readSource("components", "workbench", "RightPanelSurfaceBody.jsx");

  assert.equal(appSource.includes("createPreviewController"), true);
  assert.equal(appSource.includes("previewChrome.sessionRequiredNotice"), false);
  assert.equal(appSource.includes("previewChrome.refreshFailedNotice"), false);
  assert.equal(appSource.includes("previewChrome.openFailedNotice"), false);
  assert.equal(previewControllerSource.includes("chrome.sessionRequiredNotice"), true);
  assert.equal(previewControllerSource.includes("chrome.refreshFailedNotice"), true);
  assert.equal(previewControllerSource.includes("chrome.openFailedNotice"), true);
  assert.equal(appSource.includes("previewCapability.localServers"), true);
  assert.equal(surfaceBodySource.includes("previewChrome"), true);
  assert.equal(surfaceBodySource.includes("previewServers"), true);
  assert.equal(previewSurfaceSource.includes("previewChrome"), true);
  assert.equal(previewSurfaceSource.includes("buildPreviewRuntimeState({ snapshot, chrome: previewChrome })"), true);
  assert.equal(previewModelSource.includes("chrome.statusReady"), true);
  assert.equal(previewModelSource.includes("chrome.emptyTitle"), true);

  for (const hardcodedCopy of [
    '"Open a session before using preview."',
    '"Preview failed"',
    '"Preview refresh failed"',
    '"Open preview failed"',
  ]) {
    assert.equal(appSource.includes(hardcodedCopy), false);
  }

  for (const hardcodedCopy of [
    '"Vite dev server"',
    '"Local app"',
    '"Loading..."',
    '"Refresh"',
    '"Loading preview"',
    '"Refresh preview"',
    '"Search or enter URL"',
    '"Preview URL"',
    '"Open in system browser"',
    '"Annotate preview"',
    '"More preview actions"',
    '"Preview unavailable"',
    '"This local page cannot be rendered in the embedded preview."',
    '"The local preview target did not respond."',
    '"Reload"',
    '"Preview failed"',
  ]) {
    assert.equal(previewSurfaceSource.includes(hardcodedCopy), false);
  }

  for (const hardcodedCopy of [
    '"Loading"',
    '"Ready"',
    '"Preview unavailable"',
    '"Idle"',
    '"Local server"',
    '"Local servers"',
    '"No preview open"',
    '"Choose a local server to open in the preview panel."',
    '"Start a local dev server or enter a localhost URL above."',
  ]) {
    assert.equal(previewModelSource.includes(hardcodedCopy), false);
  }
}
