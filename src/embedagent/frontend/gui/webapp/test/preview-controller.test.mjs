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
  const protocol = {
    openPreviewSession: async (sessionId, url) => {
      calls.push(["openPreviewSession", sessionId, url]);
      return { preview: { url, tabId: "tab-1" } };
    },
    refreshPreviewSession: async (sessionId, tabId) => {
      calls.push(["refreshPreviewSession", sessionId, tabId]);
      return { preview: { url: "http://localhost:5173/refreshed", tabId } };
    },
    openPreviewExternal: async (url) => {
      calls.push(["openPreviewExternal", url]);
      return { ok: true };
    },
  };
  const controller = createPreviewController({
    protocol,
    dispatch: (action) => actions.push(action),
    getCurrentSessionId: () => "sess-1",
    getPreviewChrome: () => PREVIEW_CHROME,
    contributionController: {
      openPreview: (request) => openRequests.push(request),
    },
  });

  const opened = await controller.openUrl("http://localhost:5173");
  assert.deepEqual(opened, { preview: { url: "http://localhost:5173", tabId: "tab-1" } });
  assert.deepEqual(calls.at(-1), ["openPreviewSession", "sess-1", "http://localhost:5173"]);
  assert.equal(openRequests.at(-1).resourceId, "http://localhost:5173");

  const refreshed = await controller.refresh({ tab_id: "tab-1", url: "http://localhost:5173" });
  assert.equal(refreshed.preview.url, "http://localhost:5173/refreshed");
  assert.deepEqual(calls.at(-1), ["refreshPreviewSession", "sess-1", "tab-1"]);

  assert.deepEqual(await controller.openExternal("http://localhost:5173"), { ok: true });
  assert.deepEqual(calls.at(-1), ["openPreviewExternal", "http://localhost:5173"]);

  const noSessionActions = [];
  const noSessionController = createPreviewController({
    protocol,
    dispatch: (action) => noSessionActions.push(action),
    getCurrentSessionId: () => "",
    getPreviewChrome: () => PREVIEW_CHROME,
    contributionController: {
      openPreview: () => {
        throw new Error("should not open");
      },
    },
  });
  assert.equal(await noSessionController.openUrl("http://localhost:5173"), null);
  assert.deepEqual(noSessionActions, [
    { type: "interaction_notice_set", notice: "Open a session first" },
  ]);

  const disabledCalls = [];
  const disabledController = createPreviewController({
    protocol,
    dispatch: (action) => disabledCalls.push(action),
    getCurrentSessionId: () => "sess-1",
    contributionController: {},
  });
  assert.equal(await disabledController.openUrl("http://localhost:5173"), null);
  assert.equal(await disabledController.refresh({ tabId: "tab-1" }), null);
  assert.equal(await disabledController.openExternal("http://localhost:5173"), null);
  assert.deepEqual(disabledCalls, []);

  const failedActions = [];
  const failedController = createPreviewController({
    protocol: {
      openPreviewExternal: async () => {
        throw new Error("");
      },
    },
    dispatch: (action) => failedActions.push(action),
    getCurrentSessionId: () => "sess-1",
    getPreviewChrome: () => PREVIEW_CHROME,
    contributionController: { openPreview: () => true },
  });
  await assert.rejects(() => failedController.openExternal("http://localhost:5173"));
  assert.deepEqual(failedActions, [{ type: "interaction_notice_set", notice: "Open failed" }]);

  const missingProtocol = createPreviewController({
    contributionController: { openPreview: () => true },
  });
  assert.equal(await missingProtocol.openUrl("http://localhost:5173"), null);
}
