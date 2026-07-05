import assert from "node:assert/strict";

import { createPreviewController } from "../src/app-runtime/preview-controller.js";

const PREVIEW_CHROME = Object.freeze({
  failedNotice: "Preview failed",
  refreshFailedNotice: "Refresh failed",
  openFailedNotice: "Open failed",
  sessionRequiredNotice: "Open a session first",
});

export async function runPreviewControllerTests() {
  const actions = [];
  const openRequests = [];
  const calls = [];
  const controller = createPreviewController({
    dispatch: (action) => actions.push(action),
    getCurrentSessionId: () => "sess-1",
    getPreviewChrome: () => PREVIEW_CHROME,
    rightPanelController: {
      canOpenPreviewSurface: () => true,
      openPreviewSurface: (request) => openRequests.push(request),
    },
    openPreviewSession: async (sessionId, url) => {
      calls.push(["open", sessionId, url]);
      return { preview: { url, tabId: "tab-1" } };
    },
    refreshPreviewSession: async (sessionId, tabId) => {
      calls.push(["refresh", sessionId, tabId]);
      return { preview: { url: "http://localhost:5173/refreshed", tabId } };
    },
    openPreviewExternal: async (url) => {
      calls.push(["external", url]);
      return { ok: true };
    },
  });

  const opened = await controller.openUrl("http://localhost:5173");
  assert.deepEqual(opened, { preview: { url: "http://localhost:5173", tabId: "tab-1" } });
  assert.deepEqual(calls.at(-1), ["open", "sess-1", "http://localhost:5173"]);
  assert.deepEqual(openRequests.at(-1), {
    resourceId: "http://localhost:5173",
    previewSnapshot: { url: "http://localhost:5173", tabId: "tab-1" },
  });

  const refreshed = await controller.refresh({ tab_id: "tab-1", url: "http://localhost:5173" });
  assert.deepEqual(refreshed, {
    preview: { url: "http://localhost:5173/refreshed", tabId: "tab-1" },
  });
  assert.deepEqual(calls.at(-1), ["refresh", "sess-1", "tab-1"]);
  assert.deepEqual(openRequests.at(-1), {
    resourceId: "http://localhost:5173/refreshed",
    previewSnapshot: { url: "http://localhost:5173/refreshed", tabId: "tab-1" },
  });

  assert.deepEqual(await controller.openExternal("http://localhost:5173"), { ok: true });
  assert.deepEqual(calls.at(-1), ["external", "http://localhost:5173"]);

  const noSessionActions = [];
  const noSessionController = createPreviewController({
    dispatch: (action) => noSessionActions.push(action),
    getCurrentSessionId: () => "",
    getPreviewChrome: () => PREVIEW_CHROME,
    rightPanelController: {
      canOpenPreviewSurface: () => true,
      openPreviewSurface: () => {
        throw new Error("should not open");
      },
    },
    openPreviewSession: async () => {
      throw new Error("should not call api");
    },
  });
  assert.equal(await noSessionController.openUrl("http://localhost:5173"), null);
  assert.deepEqual(noSessionActions, [
    { type: "interaction_notice_set", notice: "Open a session first" },
  ]);

  const disabledCalls = [];
  const disabledController = createPreviewController({
    dispatch: (action) => disabledCalls.push(action),
    getCurrentSessionId: () => "sess-1",
    rightPanelController: {
      canOpenPreviewSurface: () => false,
      openPreviewSurface: () => {
        throw new Error("should not open");
      },
    },
    openPreviewSession: async () => {
      throw new Error("should not call api");
    },
  });
  assert.equal(await disabledController.openUrl("http://localhost:5173"), null);
  assert.equal(await disabledController.refresh({ tabId: "tab-1" }), null);
  assert.equal(await disabledController.openExternal("http://localhost:5173"), null);
  assert.deepEqual(disabledCalls, []);

  const failedActions = [];
  const failedController = createPreviewController({
    dispatch: (action) => failedActions.push(action),
    getCurrentSessionId: () => "sess-1",
    getPreviewChrome: () => PREVIEW_CHROME,
    rightPanelController: {
      canOpenPreviewSurface: () => true,
      openPreviewSurface: () => {},
    },
    openPreviewExternal: async () => {
      throw new Error("");
    },
  });
  await assert.rejects(() => failedController.openExternal("http://localhost:5173"));
  assert.deepEqual(failedActions, [
    { type: "interaction_notice_set", notice: "Open failed" },
  ]);
}
