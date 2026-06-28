import assert from "node:assert/strict";

import { reducer } from "../src/store.js";
import {
  WORKBENCH_UI_STATE_KEY,
  parsePersistedWorkbenchUiState,
  persistWorkbenchUiState,
  readPersistedWorkbenchUiState,
  serializeWorkbenchUiState,
} from "../src/workbench/ui-state.js";

function createMemoryStorage(seed = {}) {
  const entries = { ...seed };
  return {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(entries, key) ? entries[key] : null;
    },
    setItem(key, value) {
      entries[key] = String(value);
    },
    removeItem(key) {
      delete entries[key];
    },
    entries,
  };
}

export function runWorkbenchUiStateTests() {
  const parsed = parsePersistedWorkbenchUiState({
    rightPanel: {
      open: false,
      activeSurfaceId: "right:file:src/main.c",
      width: 420,
      commandPalette: { open: true, query: "do not keep" },
    },
    bottomDrawer: {
      open: true,
      activeKind: "terminal",
      height: 260,
    },
    surfacesBySession: {
      "sess-1": {
        right: [
          {
            id: "untrusted-id",
            placement: "right",
            kind: "file",
            title: "main.c",
            resourceId: "src/main.c",
            filePath: "src/main.c",
            revealLine: null,
            content: "must not persist",
            toolData: { secret: true },
          },
          {
            id: "right:unknown",
            placement: "right",
            kind: "unknown",
            title: "Nope",
          },
        ],
        activeRightSurfaceId: "right:file:src/main.c",
      },
    },
  });

  assert.equal(parsed.rightPanel.open, false);
  assert.equal(parsed.rightPanel.width, 420);
  assert.equal(parsed.bottomDrawer.open, true);
  assert.equal(parsed.bottomDrawer.activeKind, "terminal");
  assert.equal(parsed.commandPalette.open, false);
  assert.equal(parsed.commandPalette.query, "");
  assert.equal(parsed.surfacesBySession["sess-1"].right.length, 1);
  assert.deepEqual(parsed.surfacesBySession["sess-1"].right[0], {
    id: "right:file:src/main.c",
    placement: "right",
    kind: "file",
    title: "main.c",
    resourceId: "src/main.c",
    filePath: "src/main.c",
    terminalId: "",
    revealLine: null,
    revealRequestId: 0,
  });

  let state = {
    thread: {
      sessions: [],
      currentSessionId: "sess-1",
      historyIntegrity: null,
    },
    workbench: parsePersistedWorkbenchUiState({}),
  };
  state = reducer(state, {
    type: "workbench_surface_opened",
    placement: "right",
    kind: "files",
    title: "Files",
  });
  state = reducer(state, {
    type: "workbench_surface_opened",
    placement: "right",
    kind: "file",
    filePath: "README.md",
  });
  assert.deepEqual(state.workbench.surfacesBySession["sess-1"].right.map((item) => item.id), [
    "right:file:README.md",
  ]);

  state = reducer(state, {
    type: "session_activated",
    sessionId: "sess-2",
    snapshot: { session_id: "sess-2", current_mode: "explore" },
    activities: [],
  });
  assert.equal(state.workbench.activeSessionKey, "sess-2");
  assert.deepEqual(state.workbench.rightPanel.surfaces, []);

  state = reducer(state, {
    type: "workbench_surface_opened",
    placement: "right",
    kind: "diff",
    title: "Diff",
    resourceId: "current",
  });
  assert.deepEqual(state.workbench.surfacesBySession["sess-2"].right.map((item) => item.id), [
    "right:diff:current",
  ]);

  state = reducer(state, {
    type: "session_activated",
    sessionId: "sess-1",
    snapshot: { session_id: "sess-1", current_mode: "explore" },
    activities: [],
  });
  assert.equal(state.workbench.activeSessionKey, "sess-1");
  assert.deepEqual(state.workbench.rightPanel.surfaces.map((item) => item.id), [
    "right:file:README.md",
  ]);
  assert.equal(state.workbench.rightPanel.activeSurfaceId, "right:file:README.md");

  const serialized = serializeWorkbenchUiState(state.workbench);
  assert.equal(serialized.commandPalette, undefined);
  assert.equal(serialized.rightPanel.open, true);
  assert.equal(serialized.surfacesBySession["sess-1"].right[0].content, undefined);
  assert.equal(serialized.surfacesBySession["sess-1"].right[0].kind, "file");

  const storage = createMemoryStorage();
  persistWorkbenchUiState(state.workbench, storage);
  assert.equal(Boolean(storage.entries[WORKBENCH_UI_STATE_KEY]), true);
  const restored = readPersistedWorkbenchUiState(storage);
  assert.equal(restored.activeSessionKey, "sess-1");
  assert.equal(restored.surfacesBySession["sess-1"].right[0].id, "right:file:README.md");
  assert.equal(restored.surfacesBySession["sess-1"].right[0].revealLine, null);

  const brokenStorage = createMemoryStorage({
    [WORKBENCH_UI_STATE_KEY]: "{broken",
  });
  const fallback = readPersistedWorkbenchUiState(brokenStorage);
  assert.deepEqual(fallback.rightPanel.surfaces, []);
  assert.equal(fallback.commandPalette.query, "");
}
