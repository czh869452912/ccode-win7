import assert from "node:assert/strict";

import {
  buildPreviewEmptyStateModel,
  buildPreviewRuntimeState,
  formatPreviewUrlDisplay,
  normalizePreviewUrl,
  previewSnapshotFromApi,
} from "../src/session-runtime/preview-surface-model.js";

export function runPreviewSurfaceModelTests() {
  assert.equal(normalizePreviewUrl("localhost:5173"), "http://localhost:5173");
  assert.equal(normalizePreviewUrl("127.0.0.1:8000/docs"), "http://127.0.0.1:8000/docs");
  assert.equal(normalizePreviewUrl("https://example.test/path"), "https://example.test/path");
  assert.equal(normalizePreviewUrl("  "), "");

  assert.equal(formatPreviewUrlDisplay("http://127.0.0.1:5173/"), "127.0.0.1:5173");
  assert.equal(formatPreviewUrlDisplay("https://example.test/docs"), "example.test/docs");
  assert.equal(formatPreviewUrlDisplay("not a url"), "not a url");

  const snapshot = previewSnapshotFromApi({
    thread_id: "sess-1",
    tab_id: "preview-1",
    url: "http://localhost:5173",
    status: "success",
    title: "Local App",
    can_go_back: true,
    can_go_forward: false,
    error_code: 0,
    error_description: "",
    updated_at: "2026-06-19T00:00:00Z",
  });
  assert.deepEqual(snapshot, {
    threadId: "sess-1",
    tabId: "preview-1",
    url: "http://localhost:5173",
    status: "success",
    title: "Local App",
    canGoBack: true,
    canGoForward: false,
    errorCode: 0,
    errorDescription: "",
    updatedAt: "2026-06-19T00:00:00Z",
  });

  const chrome = {
    statusLoading: "Preview loading",
    statusReady: "Preview ready",
    statusFailed: "Preview offline",
    statusIdle: "Preview idle",
    emptyTitle: "No active preview",
    serversTitle: "Detected servers",
    emptyDescription: "Enter a local URL.",
    serversDescription: "Choose a detected server.",
    localServerFallbackLabel: "Server",
  };

  assert.deepEqual(buildPreviewRuntimeState({ snapshot, chrome }), {
    hasSnapshot: true,
    loading: false,
    unreachable: false,
    canRefresh: true,
    canOpenExternal: true,
    displayTitle: "Local App",
    statusLabel: "Preview ready",
  });
  assert.equal(
    buildPreviewRuntimeState({
      snapshot: { ...snapshot, status: "loading" },
      chrome,
    }).statusLabel,
    "Preview loading",
  );
  assert.equal(buildPreviewRuntimeState({ snapshot, chrome }).statusLabel, "Preview ready");
  assert.deepEqual(
    buildPreviewRuntimeState({
      snapshot: {
        ...snapshot,
        status: "failed",
        title: "",
        errorDescription: "connection refused",
      },
      chrome,
    }),
    {
      hasSnapshot: true,
      loading: false,
      unreachable: true,
      canRefresh: true,
      canOpenExternal: true,
      displayTitle: "localhost:5173",
      statusLabel: "connection refused",
    },
  );

  const empty = buildPreviewEmptyStateModel({ servers: [], chrome });
  assert.equal(empty.hasServers, false);
  assert.equal(empty.title, "No active preview");
  assert.deepEqual(empty.servers, []);
  const customEmpty = buildPreviewEmptyStateModel({ servers: [], chrome });
  assert.equal(customEmpty.hasServers, false);
  assert.equal(customEmpty.title, "No active preview");
  assert.equal(customEmpty.description, "Enter a local URL.");

  const withServers = buildPreviewEmptyStateModel({
    chrome,
    servers: [
      { label: "Vite dev server", url: "localhost:5173", port: 5173 },
      { label: "", url: "http://127.0.0.1:8080/docs", port: 8080 },
      null,
    ],
  });
  assert.equal(withServers.hasServers, true);
  assert.equal(withServers.title, "Detected servers");
  assert.equal(withServers.description, "Choose a detected server.");
  assert.deepEqual(withServers.servers, [
    {
      id: "http://localhost:5173",
      label: "Vite dev server",
      url: "http://localhost:5173",
      displayUrl: "localhost:5173",
      port: 5173,
    },
    {
      id: "http://127.0.0.1:8080/docs",
      label: "Server",
      url: "http://127.0.0.1:8080/docs",
      displayUrl: "127.0.0.1:8080/docs",
      port: 8080,
    },
  ]);
}
