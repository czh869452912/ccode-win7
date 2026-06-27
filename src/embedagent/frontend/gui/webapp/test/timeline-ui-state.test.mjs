import assert from "node:assert/strict";

import {
  createTimelineUiState,
  isRowExpandedByDefault,
  rowDensityFor,
  restoreAnchorScroll,
  rowUiKey,
  toggleTimelineRowDensity,
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
  assert.equal(rowUiKey({ kind: "context_summary", id: "ctx-1", turnId: "turn-1" }), "context_summary:turn-1:ctx-1");
  assert.equal(isRowExpandedByDefault({ kind: "context_summary" }), false);

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
  assert.equal(initial.expanded[rowUiKey(rows[2])], false);
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

  const richRows = [
    { id: "cmd-ok", kind: "command_result", turnId: "turn-1", success: true },
    { id: "cmd-fail", kind: "command_result", turnId: "turn-1", success: false, content: "failed" },
    { id: "review-fail", kind: "review_result", turnId: "turn-1", success: false, findings: [{ id: "f1" }] },
    { id: "ctx-1", kind: "context_summary", turnId: "turn-1" },
    { id: "working-turn-1", kind: "working", turnId: "turn-1" },
  ];
  const richState = createTimelineUiState(richRows);
  assert.equal(rowUiKey(richRows[0]), "command_result:turn-1:cmd-ok");
  assert.equal(rowUiKey(richRows[2]), "review_result:turn-1:review-fail");
  assert.equal(rowUiKey(richRows[3]), "context_summary:turn-1:ctx-1");
  assert.equal(rowUiKey(richRows[4]), "working:turn-1:working-turn-1");
  assert.equal(richState.expanded[rowUiKey(richRows[0])], false);
  assert.equal(richState.expanded[rowUiKey(richRows[1])], true);
  assert.equal(richState.expanded[rowUiKey(richRows[2])], true);
  assert.equal(richState.expanded[rowUiKey(richRows[3])], false);
  assert.equal(richState.expanded[rowUiKey(richRows[4])], false);
  assert.equal(richState.density[rowUiKey(richRows[0])], "compact");
  assert.equal(richState.density[rowUiKey(richRows[1])], "expanded");
  assert.equal(richState.density[rowUiKey(richRows[2])], "expanded");
  assert.equal(richState.density[rowUiKey(richRows[3])], "compact");
  assert.equal(rowDensityFor(richRows[1], richState), "expanded");
  assert.equal(rowDensityFor(richRows[4], { density: { [rowUiKey(richRows[4])]: "normal" } }), "normal");

  const normalCommand = toggleTimelineRowDensity(richState, rowUiKey(richRows[0]), "normal");
  assert.equal(normalCommand.density[rowUiKey(richRows[0])], "normal");
  assert.equal(normalCommand.expanded[rowUiKey(richRows[0])], false);
  assert.equal(normalCommand.touched[rowUiKey(richRows[0])], true);

  const expandedCommand = toggleTimelineRowDensity(normalCommand, rowUiKey(richRows[0]), "expanded");
  assert.equal(expandedCommand.density[rowUiKey(richRows[0])], "expanded");
  assert.equal(expandedCommand.expanded[rowUiKey(richRows[0])], true);

  const preservedDensity = createTimelineUiState(richRows, expandedCommand);
  assert.equal(preservedDensity.density[rowUiKey(richRows[0])], "expanded");
  assert.equal(preservedDensity.expanded[rowUiKey(richRows[0])], true);

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
