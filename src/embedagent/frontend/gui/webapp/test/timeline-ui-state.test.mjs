import assert from "node:assert/strict";

import {
  createTimelineUiState,
  restoreAnchorScroll,
  rowUiKey,
  shouldPinToBottom,
  toggleTimelineRow,
} from "../src/session-runtime/timeline-ui-state.js";

export function runTimelineUiStateTests() {
  const workRow = {
    id: "tool-1",
    kind: "work",
    turnId: "turn-1",
    stepId: "step-1",
    toolName: "read_file",
    status: "success",
  };
  assert.equal(rowUiKey(workRow), "work:turn-1:step-1:tool-1");
  assert.equal(rowUiKey({ id: "fold-1", kind: "turn_fold", turnId: "turn-1" }), "turn_fold:turn-1:fold-1");
  assert.equal(rowUiKey({ id: "message-1", kind: "message", role: "assistant" }), "message:message-1");

  const rows = [
    { id: "tool-ok", kind: "work", turnId: "turn-1", stepId: "step-1", status: "success" },
    { id: "tool-error", kind: "work", turnId: "turn-1", stepId: "step-2", status: "error", tone: "error" },
    { id: "tool-running", kind: "work", turnId: "turn-2", stepId: "step-3", status: "running", tone: "running" },
    {
      id: "fold-1",
      kind: "turn_fold",
      turnId: "turn-3",
      defaultOpen: false,
      entries: [{ id: "fold-tool", kind: "work", status: "success" }],
    },
  ];
  const initial = createTimelineUiState(rows);
  assert.equal(initial.expanded[rowUiKey(rows[0])], false);
  assert.equal(initial.expanded[rowUiKey(rows[1])], true);
  assert.equal(initial.expanded[rowUiKey(rows[2])], true);
  assert.equal(initial.expanded[rowUiKey(rows[3])], false);

  const toggled = toggleTimelineRow(initial, rowUiKey(rows[0]));
  assert.equal(toggled.expanded[rowUiKey(rows[0])], true);
  assert.equal(toggled.touched[rowUiKey(rows[0])], true);

  const updated = createTimelineUiState(
    rows.concat({ id: "assistant-1", kind: "message", role: "assistant" }),
    toggled,
  );
  assert.equal(updated.expanded[rowUiKey(rows[0])], true);
  assert.equal(updated.touched[rowUiKey(rows[0])], true);

  assert.equal(shouldPinToBottom({ scrollTop: 90, clientHeight: 100, scrollHeight: 200 }), true);
  assert.equal(shouldPinToBottom({ scrollTop: 40, clientHeight: 100, scrollHeight: 200 }), false);
  assert.equal(
    restoreAnchorScroll({
      before: { top: 120 },
      after: { top: 160 },
      scrollTop: 300,
    }),
    340,
  );
}
