import assert from "node:assert/strict";

import {
  buildPreviewEmptyStateModel,
  formatPreviewUrlDisplay,
  normalizePreviewUrl,
} from "../src/session-runtime/preview-surface-model.js";

export function runPreviewSurfaceModelTests() {
  assert.equal(normalizePreviewUrl("localhost:5173"), "http://localhost:5173");
  assert.equal(normalizePreviewUrl("127.0.0.1:8000/docs"), "http://127.0.0.1:8000/docs");
  assert.equal(normalizePreviewUrl("https://example.test/path"), "https://example.test/path");
  assert.equal(normalizePreviewUrl("  "), "");

  assert.equal(formatPreviewUrlDisplay("http://127.0.0.1:5173/"), "127.0.0.1:5173");
  assert.equal(formatPreviewUrlDisplay("https://example.test/docs"), "example.test/docs");
  assert.equal(formatPreviewUrlDisplay("not a url"), "not a url");

  const empty = buildPreviewEmptyStateModel({ servers: [] });
  assert.equal(empty.hasServers, false);
  assert.equal(empty.title, "No preview open");
  assert.deepEqual(empty.servers, []);

  const withServers = buildPreviewEmptyStateModel({
    servers: [
      { label: "Vite dev server", url: "localhost:5173", port: 5173 },
      { label: "", url: "http://127.0.0.1:8080/docs", port: 8080 },
      null,
    ],
  });
  assert.equal(withServers.hasServers, true);
  assert.equal(withServers.title, "Local servers");
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
      label: "127.0.0.1:8080/docs",
      url: "http://127.0.0.1:8080/docs",
      displayUrl: "127.0.0.1:8080/docs",
      port: 8080,
    },
  ]);
}
