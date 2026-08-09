import assert from "node:assert/strict";

import {
  createContributionState,
  reduceContributionState,
} from "../src/client-runtime/reducers/contribution-reducer.js";

export function runContributionSurfaceStoreTests() {
  let state = createContributionState();
  state = reduceContributionState(state, {
    type: "contribution_session_activated",
    sessionId: "session-a",
  });
  state = reduceContributionState(state, {
    type: "contribution_opened",
    kind: "files",
    label: "main.c",
    rendererKey: "file_preview",
    resourceId: "src/main.c",
    filePath: "src/main.c",
    revealLine: 12,
  });
  assert.equal(state.items[0].id, "files:src/main.c");
  assert.equal(state.activeId, "files:src/main.c");

  state = reduceContributionState(state, {
    type: "contribution_opened",
    kind: "preview",
    label: "Preview",
    rendererKey: "preview",
    resourceId: "http://127.0.0.1:5173",
  });
  assert.equal(state.items.length, 2);
  assert.equal(state.activeId, "preview:http://127.0.0.1:5173");

  state = reduceContributionState(state, {
    type: "contribution_opened",
    kind: "terminal",
    label: "Terminal",
    rendererKey: "terminal",
    resourceId: "term-1",
    terminalId: "term-1",
    terminalIds: ["term-1"],
  });
  const terminalId = state.activeId;
  state = reduceContributionState(state, {
    type: "contribution_terminal_split",
    surfaceId: terminalId,
    terminalId: "term-2",
    splitDirection: "vertical",
  });
  assert.deepEqual(state.items.at(-1).terminalIds, ["term-1", "term-2"]);
  assert.equal(state.items.at(-1).activeTerminalId, "term-2");
  assert.equal(state.items.at(-1).splitDirection, "vertical");

  state = reduceContributionState(state, {
    type: "contribution_terminal_closed",
    surfaceId: terminalId,
    terminalId: "term-2",
  });
  assert.deepEqual(state.items.at(-1).terminalIds, ["term-1"]);

  state = reduceContributionState(state, {
    type: "contribution_close_others",
    surfaceId: terminalId,
  });
  assert.deepEqual(state.items.map((item) => item.id), [terminalId]);

  state = reduceContributionState(state, { type: "command_palette_opened" });
  state = reduceContributionState(state, {
    type: "command_palette_query_changed",
    query: "term",
  });
  assert.deepEqual(state.palette, { open: true, query: "term" });

  state = reduceContributionState(state, { type: "contribution_close_all" });
  assert.deepEqual(state.items, []);
  assert.equal(state.activeId, "");
}
