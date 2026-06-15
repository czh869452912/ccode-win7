import assert from "node:assert/strict";

import {
  projectT3TimelineRows,
  summarizeChangedFiles,
} from "../src/session-runtime/t3-timeline.js";

export function runT3TimelineTests() {
  const settledRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-1",
        userItem: { id: "u1", kind: "user", content: "inspect demo", turnId: "turn-1" },
        steps: [
          {
            stepId: "step-1",
            stepIndex: 1,
            activityItems: [
              {
                id: "tool-1",
                kind: "tool",
                toolName: "read_file",
                label: "Read File",
                status: "success",
                arguments: { path: "demo.c" },
                turnId: "turn-1",
                stepId: "step-1",
              },
            ],
            assistantItem: {
              id: "a1",
              kind: "assistant",
              content: "done",
              turnId: "turn-1",
              stepId: "step-1",
            },
          },
        ],
        trailingTurnItems: [],
        leadingSystemItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "idle",
    activeTurnId: "",
    currentInteraction: null,
  });

  assert.equal(settledRows[0].kind, "message");
  assert.equal(settledRows[0].role, "user");
  assert.equal(settledRows[1].kind, "turn_fold");
  assert.equal(settledRows[1].workCount, 1);
  assert.equal(settledRows[1].defaultOpen, false);
  assert.equal(settledRows[2].kind, "message");
  assert.equal(settledRows[2].role, "assistant");

  const runningRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-live",
        userItem: { id: "u-live", kind: "user", content: "build", turnId: "turn-live" },
        steps: [
          {
            stepId: "step-live",
            stepIndex: 1,
            activityItems: [
              {
                id: "tool-live",
                kind: "tool",
                toolName: "run_recipe",
                label: "Run Recipe",
                status: "running",
                arguments: { recipe_id: "build" },
                turnId: "turn-live",
                stepId: "step-live",
              },
            ],
            assistantItem: null,
          },
        ],
        trailingTurnItems: [],
        leadingSystemItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "running",
    activeTurnId: "turn-live",
    currentInteraction: null,
  });

  assert.equal(runningRows[1].kind, "work");
  assert.equal(runningRows[1].status, "running");
  assert.equal(runningRows.some((row) => row.kind === "turn_fold"), false);

  const changed = summarizeChangedFiles([
    {
      id: "write-1",
      kind: "tool",
      toolName: "write_file",
      status: "success",
      arguments: { path: "src/demo.c" },
      data: {
        path: "src/demo.c",
        diff_preview: "--- a/src/demo.c\n+++ b/src/demo.c\n@@ -1 +1 @@\n-old\n+new\n",
      },
    },
    {
      id: "cmd-diff",
      kind: "command_result",
      commandName: "diff",
      success: true,
      data: {
        diff: "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n",
      },
    },
  ]);

  assert.equal(changed.files.length, 2);
  assert.deepEqual(changed.files.map((file) => file.path), ["src/demo.c", "README.md"]);
  assert.equal(changed.additions, 2);
  assert.equal(changed.deletions, 2);

  const interruptedRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-interrupted",
        userItem: { id: "u2", kind: "user", content: "stop", turnId: "turn-interrupted" },
        steps: [
          {
            stepId: "step-2",
            stepIndex: 1,
            activityItems: [
              {
                id: "tool-2",
                kind: "tool",
                toolName: "run_recipe",
                status: "error",
                error: "cancelled",
                data: { error_kind: "interrupted" },
                turnId: "turn-interrupted",
                stepId: "step-2",
              },
            ],
            assistantItem: null,
          },
        ],
        trailingTurnItems: [],
        leadingSystemItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "idle",
    activeTurnId: "",
    currentInteraction: null,
  });

  assert.equal(interruptedRows.some((row) => row.kind === "turn_fold"), false);
  assert.equal(interruptedRows[1].tone, "interrupted");
}
