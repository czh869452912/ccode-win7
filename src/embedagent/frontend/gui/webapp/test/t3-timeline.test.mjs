import assert from "node:assert/strict";

import {
  T3_ROW_KINDS,
  buildChangedFilesTree,
  projectT3TimelineRows,
  summarizeChangedFiles,
  summarizeDiffStats,
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

  const detailRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-detail",
        userItem: { id: "u-detail", kind: "user", content: "inspect tools", turnId: "turn-detail" },
        steps: [
          {
            stepId: "step-detail",
            stepIndex: 1,
            activityItems: [
              {
                id: "read-detail",
                kind: "tool",
                toolName: "read_file",
                label: "Read File",
                status: "success",
                arguments: { path: "src/parser.c", _permission_category: "read" },
                data: {
                  path: "src/parser.c",
                  line_count: 12,
                  content_preview: "int parse(void);",
                },
                turnId: "turn-detail",
                stepId: "step-detail",
                stepIndex: 1,
              },
              {
                id: "grep-detail",
                kind: "tool",
                toolName: "grep_text",
                label: "Search",
                status: "success",
                arguments: { pattern: "parse", path: "src" },
                data: {
                  pattern: "parse",
                  path: "src",
                  match_count: 2,
                  matches: [
                    { path: "src/parser.c", line: 7, text: "int parse(void);" },
                    { path: "src/parser_test.c", line: 21, text: "assert(parse());" },
                  ],
                },
                turnId: "turn-detail",
                stepId: "step-detail",
                stepIndex: 1,
              },
              {
                id: "edit-detail",
                kind: "tool",
                toolName: "edit_file",
                label: "Edit File",
                status: "success",
                arguments: { path: "src/parser.c" },
                data: {
                  path: "src/parser.c",
                  diff_preview: "--- a/src/parser.c\n+++ b/src/parser.c\n@@ -1 +1 @@\n-old\n+new\n",
                },
                turnId: "turn-detail",
                stepId: "step-detail",
                stepIndex: 1,
              },
              {
                id: "recipe-detail",
                kind: "tool",
                toolName: "run_recipe",
                label: "Run Recipe",
                status: "error",
                error: "build failed",
                arguments: { recipe_id: "build-debug", target: "parser" },
                data: {
                  recipe_id: "build-debug",
                  command: "clang -Wall src/parser.c",
                  exit_code: 1,
                  stdout_preview: "Compiling parser",
                  stderr_preview: "parser.c:7: error: expected ';'",
                },
                turnId: "turn-detail",
                stepId: "step-detail",
                stepIndex: 1,
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
    activeTurnId: "turn-detail",
  });

  const detailWorkRows = detailRows.filter((row) => row.kind === T3_ROW_KINDS.WORK);
  assert.equal(detailWorkRows.length, 4);
  const readDetail = detailWorkRows.find((row) => row.toolName === "read_file").detailModel;
  assert.equal(readDetail.kind, "tool_detail");
  assert.equal(readDetail.fields.find((field) => field.label === "path").value, "src/parser.c");
  assert.equal(readDetail.fields.find((field) => field.label === "lines").value, "12");
  assert.equal(readDetail.sections.find((section) => section.kind === "preview").content, "int parse(void);");
  assert.equal(readDetail.rawJson, undefined);

  const grepDetail = detailWorkRows.find((row) => row.toolName === "grep_text").detailModel;
  assert.equal(grepDetail.fields.find((field) => field.label === "pattern").value, "parse");
  assert.equal(grepDetail.sections.find((section) => section.kind === "matches").items.length, 2);

  const editDetail = detailWorkRows.find((row) => row.toolName === "edit_file").detailModel;
  assert.equal(editDetail.sections.find((section) => section.kind === "diff").content.includes("@@ -1 +1 @@"), true);
  assert.equal(detailWorkRows.find((row) => row.toolName === "edit_file").changedFiles[0].path, "src/parser.c");

  const recipeDetail = detailWorkRows.find((row) => row.toolName === "run_recipe").detailModel;
  assert.equal(recipeDetail.fields.find((field) => field.label === "recipe").value, "build-debug");
  assert.equal(recipeDetail.fields.find((field) => field.label === "exit").value, "1");
  assert.equal(recipeDetail.sections.find((section) => section.kind === "stderr").content.includes("expected"), true);

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

  const systemRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-system",
        userItem: { id: "u-system", kind: "user", content: "show context", turnId: "turn-system" },
        leadingSystemItems: [
          {
            id: "sys-1",
            kind: "system",
            tone: "context",
            content: "history partially restored",
            turnId: "turn-system",
          },
        ],
        steps: [],
        detachedItems: [
          {
            id: "detached-tool",
            kind: "tool",
            toolName: "grep_text",
            label: "Search",
            status: "success",
            arguments: { pattern: "main" },
            turnId: "turn-system",
          },
        ],
        trailingTurnItems: [],
        sessionFallbackItems: [],
      },
    ],
  });

  assert.equal(systemRows[1].kind, "system_notice");
  assert.equal(systemRows[1].content, "history partially restored");
  assert.equal(systemRows[2].kind, "work");
  assert.equal(systemRows[2].id, "detached-tool");

  const richRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-rich",
        userItem: { id: "u-rich", kind: "user", content: "review parser", turnId: "turn-rich" },
        leadingSystemItems: [
          {
            id: "compact-rich",
            kind: "compact",
            content: "older turns summarized",
            summarizedTurns: 6,
            recentTurns: 3,
            approxTokensAfter: 4200,
            turnId: "turn-rich",
          },
        ],
        steps: [
          {
            stepId: "step-rich",
            stepIndex: 1,
            activityItems: [
              {
                id: "reason-rich",
                kind: "reasoning",
                content: "Inspect parser recovery path before editing.",
                streaming: false,
                turnId: "turn-rich",
                stepId: "step-rich",
                stepIndex: 1,
              },
              {
                id: "tool-rich",
                kind: "tool",
                toolName: "read_file",
                label: "Read File",
                status: "success",
                arguments: { path: "src/parser.c" },
                turnId: "turn-rich",
                stepId: "step-rich",
                stepIndex: 1,
              },
            ],
            assistantItem: {
              id: "a-rich",
              kind: "assistant",
              content: "Parser recovery reviewed.",
              turnId: "turn-rich",
              stepId: "step-rich",
              stepIndex: 1,
            },
          },
        ],
        trailingTurnItems: [
          {
            id: "cmd-rich",
            kind: "command_result",
            commandName: "diff",
            success: true,
            content: "Diff is clean.",
            turnId: "turn-rich",
          },
          {
            id: "review-rich",
            kind: "command_result",
            commandName: "review",
            success: false,
            content: "Review found one issue.",
            data: {
              review: {
                findings: [
                  {
                    id: "finding-1",
                    severity: "high",
                    priority: 1,
                    title: "Parser can drop EOF",
                    body: "EOF handling should preserve diagnostics.",
                    file: "src/parser.c",
                    line: 42,
                  },
                ],
                residual_risks: ["No integration fixture covers EOF recovery."],
              },
            },
            turnId: "turn-rich",
          },
        ],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "idle",
    activeTurnId: "",
  });

  assert.equal(richRows[1].kind, T3_ROW_KINDS.COMPACT);
  const richFold = richRows.find((row) => row.kind === T3_ROW_KINDS.TURN_FOLD);
  assert.ok(richFold);
  assert.equal(richFold.workCount, 1);
  assert.equal(richFold.reasoningCount, 1);
  assert.deepEqual(
    richFold.entries.map((entry) => entry.kind),
    [T3_ROW_KINDS.REASONING, T3_ROW_KINDS.WORK],
  );
  assert.equal(richFold.entries[0].content, "Inspect parser recovery path before editing.");
  assert.equal(richFold.entries[0].wordCount, 6);
  assert.equal(richRows.some((row) => row.kind === T3_ROW_KINDS.COMMAND_RESULT), true);
  const reviewRow = richRows.find((row) => row.kind === T3_ROW_KINDS.REVIEW_RESULT);
  assert.ok(reviewRow);
  assert.equal(reviewRow.success, false);
  assert.equal(reviewRow.findings.length, 1);
  assert.equal(reviewRow.findings[0].title, "Parser can drop EOF");

  const thinkingRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-thinking",
        userItem: { id: "u-thinking", kind: "user", content: "think first", turnId: "turn-thinking" },
        leadingSystemItems: [],
        steps: [],
        trailingTurnItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "running",
    activeTurnId: "turn-thinking",
    thinkingActive: true,
  });
  assert.equal(thinkingRows.some((row) => row.kind === T3_ROW_KINDS.THINKING), true);
  const thinkingRow = thinkingRows.find((row) => row.kind === T3_ROW_KINDS.THINKING);
  assert.equal(thinkingRow.turnId, "turn-thinking");
  assert.equal(thinkingRow.label, "Thinking");

  const streamingReasoningRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-stream",
        userItem: { id: "u-stream", kind: "user", content: "stream", turnId: "turn-stream" },
        leadingSystemItems: [],
        steps: [
          {
            stepId: "step-stream",
            stepIndex: 1,
            activityItems: [
              {
                id: "reason-stream",
                kind: "reasoning",
                content: "Streaming hidden chain summary",
                streaming: true,
                turnId: "turn-stream",
                stepId: "step-stream",
                stepIndex: 1,
              },
            ],
            assistantItem: null,
          },
        ],
        trailingTurnItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "running",
    activeTurnId: "turn-stream",
    thinkingActive: true,
  });
  assert.equal(streamingReasoningRows.some((row) => row.kind === T3_ROW_KINDS.THINKING), false);
  const streamingReasoning = streamingReasoningRows.find((row) => row.kind === T3_ROW_KINDS.REASONING);
  assert.ok(streamingReasoning);
  assert.equal(streamingReasoning.streaming, true);

  const priorReasoningActiveThinkingRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-prior",
        userItem: { id: "u-prior", kind: "user", content: "prior", turnId: "turn-prior" },
        leadingSystemItems: [],
        steps: [
          {
            stepId: "step-prior",
            stepIndex: 1,
            activityItems: [
              {
                id: "reason-prior",
                kind: "reasoning",
                content: "Prior completed reasoning",
                streaming: false,
                turnId: "turn-prior",
                stepId: "step-prior",
                stepIndex: 1,
              },
            ],
            assistantItem: {
              id: "a-prior",
              kind: "assistant",
              content: "prior done",
              turnId: "turn-prior",
              stepId: "step-prior",
              stepIndex: 1,
            },
          },
        ],
        trailingTurnItems: [],
        sessionFallbackItems: [],
      },
      {
        turnId: "turn-active-thinking",
        userItem: {
          id: "u-active-thinking",
          kind: "user",
          content: "think now",
          turnId: "turn-active-thinking",
        },
        leadingSystemItems: [],
        steps: [],
        trailingTurnItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "running",
    activeTurnId: "turn-active-thinking",
    thinkingActive: true,
  });
  assert.equal(priorReasoningActiveThinkingRows.some((row) => row.kind === T3_ROW_KINDS.THINKING), true);

  const tree = buildChangedFilesTree([
    { path: "src/app/main.c", additions: 2, deletions: 1 },
    { path: "src/app/util.c", additions: 1, deletions: 0 },
    { path: "README.md", additions: 0, deletions: 1 },
  ]);
  assert.equal(tree.length, 2);
  assert.equal(tree[0].kind, "directory");
  assert.equal(tree[0].name, "src/app");
  assert.equal(tree[0].stat.additions, 3);
  assert.equal(tree[0].stat.deletions, 1);
  assert.deepEqual(tree[0].children.map((node) => node.path), ["src/app/main.c", "src/app/util.c"]);
  assert.equal(tree[1].kind, "file");
  assert.equal(tree[1].path, "README.md");

  assert.deepEqual(
    summarizeDiffStats([
      { path: "a.c", additions: 3, deletions: 0 },
      { path: "b.c", additions: 0, deletions: 2 },
    ]),
    { additions: 3, deletions: 2 },
  );
}
