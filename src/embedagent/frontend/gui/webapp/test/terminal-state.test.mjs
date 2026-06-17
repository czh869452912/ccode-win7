import assert from "node:assert/strict";

import {
  getTerminalLabel,
  nextTerminalId,
  resolveTerminalSessionLabel,
} from "../src/terminal/terminal-labels.js";
import {
  applyTerminalEvent,
  createTerminalState,
  normalizeTerminalSnapshot,
  normalizeTerminalSummary,
  reduceTerminalState,
} from "../src/terminal/terminal-state.js";

export function runTerminalStateTests() {
  assert.equal(getTerminalLabel("term-1"), "Terminal 1");
  assert.equal(getTerminalLabel("terminal-12"), "Terminal 12");
  assert.equal(getTerminalLabel("custom"), "custom");
  assert.equal(resolveTerminalSessionLabel("term-2", { label: "npm test" }), "npm test");
  assert.equal(resolveTerminalSessionLabel("term-2", { label: "   " }), "Terminal 2");
  assert.equal(nextTerminalId([]), "term-1");
  assert.equal(nextTerminalId(["term-1", "term-3"]), "term-2");

  const summary = normalizeTerminalSummary({
    session_id: "sess-1",
    terminal_id: "term-1",
    cwd: "D:/demo",
    status: "running",
    pid: 123,
    label: "Terminal 1",
    updated_at: "2026-06-17T00:00:00Z",
    capabilities: { stdin: true, resize: false, pty: false },
  });
  assert.equal(summary.sessionId, "sess-1");
  assert.equal(summary.terminalId, "term-1");
  assert.equal(summary.capabilities.pty, false);

  const snapshot = normalizeTerminalSnapshot({
    ...summary,
    session_id: "sess-1",
    terminal_id: "term-1",
    history: "hello",
    sequence: 1,
  });
  assert.equal(snapshot.history, "hello");
  assert.equal(snapshot.sequence, 1);

  let state = createTerminalState({ maxBufferChars: 12 });
  state = reduceTerminalState(state, {
    type: "terminal_snapshot_loaded",
    snapshot,
  });
  assert.equal(state.activeTerminalId, "term-1");
  assert.equal(state.sessions["term-1"].buffer, "hello");

  state = applyTerminalEvent(state, {
    type: "output",
    session_id: "sess-1",
    terminal_id: "term-1",
    sequence: 2,
    data: " world",
  });
  state = applyTerminalEvent(state, {
    type: "output",
    session_id: "sess-1",
    terminal_id: "term-1",
    sequence: 3,
    chunk: " and more",
  });
  assert.equal(state.sessions["term-1"].buffer, "rld and more");

  state = applyTerminalEvent(state, {
    type: "cleared",
    session_id: "sess-1",
    terminal_id: "term-1",
    sequence: 4,
  });
  assert.equal(state.sessions["term-1"].buffer, "");

  state = applyTerminalEvent(state, {
    type: "closed",
    session_id: "sess-1",
    terminal_id: "term-1",
    sequence: 5,
  });
  assert.equal(state.sessions["term-1"], undefined);
  assert.equal(state.activeTerminalId, "");
}
