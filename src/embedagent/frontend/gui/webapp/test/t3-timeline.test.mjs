import assert from "node:assert/strict";

import {
  T3_ROW_KINDS,
  buildChangedFilesTree,
  buildWorkPresentation,
  projectT3TimelineRows,
  summarizeChangedFiles,
  summarizeDiffStats,
} from "../src/session-runtime/t3-timeline.js";

export function runT3TimelineTests() {
  {
    const rows = projectT3TimelineRows({
      currentStatus: "idle",
      activeTurnId: "",
      turnGroups: [
        {
          turnId: "turn-settled",
          startedAt: "2026-06-22T00:00:00.000Z",
          completedAt: "2026-06-22T00:00:08.000Z",
          userItem: {
            id: "user-settled",
            kind: "user",
            role: "user",
            content: "inspect",
            createdAt: "2026-06-22T00:00:00.000Z",
            turnId: "turn-settled",
          },
          steps: [
            {
              activityItems: [
                {
                  id: "reasoning-settled",
                  kind: "reasoning",
                  content: "I will inspect files.",
                  createdAt: "2026-06-22T00:00:01.000Z",
                  turnId: "turn-settled",
                },
                {
                  id: "tool-read",
                  kind: "tool",
                  toolName: "read_file",
                  label: "Read File",
                  status: "success",
                  createdAt: "2026-06-22T00:00:02.000Z",
                  completedAt: "2026-06-22T00:00:03.000Z",
                  args: { path: "src/main.c" },
                  turnId: "turn-settled",
                },
                {
                  id: "compact-settled",
                  kind: "compact",
                  content: "Context compacted",
                  summarizedTurns: 4,
                  recentTurns: 2,
                  createdAt: "2026-06-22T00:00:04.000Z",
                  turnId: "turn-settled",
                },
              ],
              assistantItem: {
                id: "assistant-settled",
                kind: "assistant",
                role: "assistant",
                content: "done",
                createdAt: "2026-06-22T00:00:08.000Z",
                completedAt: "2026-06-22T00:00:08.000Z",
                turnId: "turn-settled",
              },
            },
          ],
        },
      ],
    });
    assert.deepEqual(rows.map((row) => row.kind), ["message", "turn_fold", "message"]);
    const fold = rows.find((row) => row.kind === "turn_fold");
    assert.equal(fold.label, "");
    assert.equal(fold.createdAt, "2026-06-22T00:00:00.000Z");
    assert.equal(fold.completedAt, "2026-06-22T00:00:08.000Z");
    assert.equal(fold.interrupted, false);
    assert.equal(fold.entries.some((entry) => entry.kind === "work"), true);
    assert.equal(fold.entries.some((entry) => entry.kind === "context_summary"), true);
    assert.equal(rows.some((row) => row.kind === "compact"), false);
  }

  {
    const rows = projectT3TimelineRows({
      currentStatus: "running",
      activeTurnId: "turn-active",
      thinkingActive: true,
      turnGroups: [
        {
          turnId: "turn-active",
          startedAt: "2026-06-22T00:01:00.000Z",
          userItem: {
            id: "user-active",
            kind: "user",
            role: "user",
            content: "build",
            createdAt: "2026-06-22T00:01:00.000Z",
            turnId: "turn-active",
          },
          steps: [
            {
              activityItems: [
                {
                  id: "tool-running",
                  kind: "tool",
                  toolName: "pytest",
                  label: "Pytest",
                  status: "running",
                  tone: "running",
                  createdAt: "2026-06-22T00:01:03.000Z",
                  turnId: "turn-active",
                },
                {
                  id: "compact-active",
                  kind: "compact",
                  content: "Context compacted",
                  createdAt: "2026-06-22T00:01:04.000Z",
                  turnId: "turn-active",
                },
              ],
            },
          ],
        },
      ],
    });
    assert.deepEqual(rows.map((row) => row.kind), ["message", "work", "system_notice", "working"]);
    assert.equal(rows.find((row) => row.kind === "system_notice").placement, "active_turn_boundary");
    assert.equal(rows.find((row) => row.kind === "work").status, "running");
  }

  {
    const rows = projectT3TimelineRows({
      currentStatus: "idle",
      activeTurnId: "",
      turnGroups: [
        {
          turnId: "turn-failed",
          userItem: {
            id: "user-failed",
            kind: "user",
            role: "user",
            content: "verify",
            createdAt: "2026-06-22T00:02:00.000Z",
            turnId: "turn-failed",
          },
          steps: [
            {
              activityItems: [
                {
                  id: "tool-failed",
                  kind: "tool",
                  toolName: "pytest",
                  label: "Pytest",
                  status: "error",
                  tone: "error",
                  createdAt: "2026-06-22T00:02:02.000Z",
                  turnId: "turn-failed",
                },
              ],
              assistantItem: {
                id: "assistant-failed",
                kind: "assistant",
                role: "assistant",
                content: "build failed",
                createdAt: "2026-06-22T00:02:05.000Z",
                turnId: "turn-failed",
              },
            },
          ],
        },
      ],
    });
    assert.deepEqual(rows.map((row) => row.kind), ["message", "work", "message"]);
    assert.equal(rows.some((row) => row.kind === "turn_fold"), false);
  }

  {
    const rows = projectT3TimelineRows({
      currentStatus: "idle",
      activeTurnId: "",
      turnGroups: [
        {
          turnId: "turn-recovered",
          startedAt: "2026-06-22T00:03:00.000Z",
          completedAt: "2026-06-22T00:03:12.000Z",
          userItem: {
            id: "user-recovered",
            kind: "user",
            role: "user",
            content: "inspect after a recoverable tool error",
            createdAt: "2026-06-22T00:03:00.000Z",
            turnId: "turn-recovered",
          },
          steps: [
            {
              stepId: "step-recovered-error",
              stepIndex: 1,
              activityItems: [
                {
                  id: "tool-recovered-error",
                  kind: "tool",
                  toolName: "grep_text",
                  label: "Search",
                  status: "error",
                  tone: "error",
                  error: "decode failed",
                  createdAt: "2026-06-22T00:03:02.000Z",
                  completedAt: "2026-06-22T00:03:03.000Z",
                  turnId: "turn-recovered",
                  stepId: "step-recovered-error",
                  stepIndex: 1,
                },
              ],
            },
            {
              stepId: "step-recovered-success",
              stepIndex: 2,
              activityItems: [
                {
                  id: "tool-recovered-success",
                  kind: "tool",
                  toolName: "read_file",
                  label: "Read File",
                  status: "success",
                  createdAt: "2026-06-22T00:03:05.000Z",
                  completedAt: "2026-06-22T00:03:06.000Z",
                  turnId: "turn-recovered",
                  stepId: "step-recovered-success",
                  stepIndex: 2,
                },
              ],
              assistantItem: {
                id: "assistant-recovered",
                kind: "assistant",
                role: "assistant",
                content: "done after recovery",
                createdAt: "2026-06-22T00:03:12.000Z",
                completedAt: "2026-06-22T00:03:12.000Z",
                turnId: "turn-recovered",
                stepId: "step-recovered-success",
                stepIndex: 2,
              },
            },
          ],
        },
      ],
    });
    assert.deepEqual(rows.map((row) => row.kind), ["message", "turn_fold", "message"]);
    const fold = rows.find((row) => row.kind === "turn_fold");
    assert.equal(fold.label, "");
    assert.equal(fold.createdAt, "2026-06-22T00:03:00.000Z");
    assert.equal(fold.completedAt, "2026-06-22T00:03:12.000Z");
    assert.equal(fold.interrupted, false);
    assert.equal(fold.workCount, 2);
    assert.equal(fold.entries.some((entry) => entry.status === "error"), true);
  }

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

  const timedFoldRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-timed",
        userItem: {
          id: "u-timed",
          kind: "user",
          content: "timed",
          turnId: "turn-timed",
          createdAt: "2026-06-18T00:00:00.000Z",
        },
        steps: [
          {
            stepId: "step-timed",
            stepIndex: 1,
            activityItems: [
              {
                id: "tool-timed",
                kind: "tool",
                toolName: "read_file",
                status: "success",
                createdAt: "2026-06-18T00:00:01.000Z",
                completedAt: "2026-06-18T00:00:03.000Z",
                turnId: "turn-timed",
                stepId: "step-timed",
              },
            ],
            assistantItem: {
              id: "a-timed",
              kind: "assistant",
              content: "timed done",
              createdAt: "2026-06-18T00:00:04.000Z",
              turnId: "turn-timed",
              stepId: "step-timed",
            },
          },
        ],
        trailingTurnItems: [],
        leadingSystemItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "idle",
  });
  assert.equal(timedFoldRows[1].kind, T3_ROW_KINDS.TURN_FOLD);
  assert.equal(timedFoldRows[1].label, "");
  assert.equal(timedFoldRows[1].createdAt, "2026-06-18T00:00:00.000Z");
  assert.equal(timedFoldRows[1].completedAt, "2026-06-18T00:00:04.000Z");

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
                toolName: "pytest",
                label: "Pytest",
                status: "running",
                arguments: { command: "uv run pytest tests/" },
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

  const grepRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-grep-link",
        userItem: { id: "u-grep-link", kind: "user", content: "find parser", turnId: "turn-grep-link" },
        steps: [
          {
            stepId: "step-grep-link",
            stepIndex: 1,
            activityItems: [
              {
                id: "grep-link",
                kind: "tool",
                toolName: "grep_text",
                status: "success",
                arguments: { pattern: "parse", path: "src" },
                data: {
                  pattern: "parse",
                  match_count: 1,
                  matches: [{ path: "src/parser.c", line: 4, text: "line 4 reveal target" }],
                },
                turnId: "turn-grep-link",
                stepId: "step-grep-link",
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
    activeTurnId: "turn-grep-link",
  });
  const grepWork = grepRows.find((row) => row.id === "grep-link");
  const matchSection = grepWork.detailModel.sections.find((section) => section.kind === "matches");
  assert.equal(matchSection.items[0].path, "src/parser.c");
  assert.equal(matchSection.items[0].line, 4);
  assert.equal(matchSection.items[0].displayLine, "4");

  const metadataRows = projectT3TimelineRows({
    toolCatalog: {
      pytest: {
        name: "pytest",
        label: "Pytest",
        iconKey: "terminal",
        rendererKey: "command",
        permissionCategory: "command",
        metadata: { previewArg: "command" },
      },
    },
    turnGroups: [
      {
        turnId: "turn-python-tool",
        userItem: {
          id: "u-python-tool",
          kind: "user",
          content: "run python tests",
          turnId: "turn-python-tool",
        },
        steps: [
          {
            stepId: "step-python-tool",
            stepIndex: 1,
            activityItems: [
              {
                id: "pytest-call",
                kind: "tool",
                toolName: "pytest",
                status: "success",
                arguments: { command: "uv run pytest tests/python" },
                turnId: "turn-python-tool",
                stepId: "step-python-tool",
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
    activeTurnId: "turn-python-tool",
  });
  const metadataWork = metadataRows.find((row) => row.id === "pytest-call");
  assert.equal(metadataWork.label, "Pytest");
  assert.equal(metadataWork.requestKind, "command");
  assert.equal(metadataWork.commandPreview, "uv run pytest tests/python");
  assert.equal(metadataWork.presentation.heading, "Pytest");
  assert.equal(metadataWork.presentation.iconName, "terminal");

  const catalogDrivenRows = projectT3TimelineRows({
    toolCatalog: {
      bash: {
        name: "bash",
        label: "Shell",
        iconKey: "terminal",
        rendererKey: "command",
        permissionCategory: "shell_exec",
        metadata: { preview_arg: "command" },
      },
      read_file: {
        name: "read_file",
        label: "Read File",
        iconKey: "eye",
        rendererKey: "file",
        permissionCategory: "read",
        metadata: { preview_arg: "path" },
      },
    },
    turnGroups: [
      {
        turnId: "turn-catalog-preview",
        userItem: {
          id: "u-catalog-preview",
          kind: "user",
          content: "inspect catalog preview",
          turnId: "turn-catalog-preview",
        },
        steps: [
          {
            stepId: "step-catalog-preview",
            stepIndex: 1,
            activityItems: [
              {
                id: "bash-catalog-preview",
                kind: "tool",
                toolName: "bash",
                status: "success",
                arguments: { command: "uv run pytest tests/catalog" },
                turnId: "turn-catalog-preview",
                stepId: "step-catalog-preview",
              },
              {
                id: "read-catalog-preview",
                kind: "tool",
                toolName: "read_file",
                status: "success",
                arguments: { path: "src/from-catalog.c" },
                turnId: "turn-catalog-preview",
                stepId: "step-catalog-preview",
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
    activeTurnId: "turn-catalog-preview",
  });
  const bashCatalogPreview = catalogDrivenRows.find((row) => row.id === "bash-catalog-preview");
  assert.equal(bashCatalogPreview.requestKind, "command");
  assert.equal(bashCatalogPreview.commandPreview, "uv run pytest tests/catalog");
  const readCatalogPreview = catalogDrivenRows.find((row) => row.id === "read-catalog-preview");
  assert.equal(readCatalogPreview.requestKind, "file-read");
  assert.equal(readCatalogPreview.commandPreview, "src/from-catalog.c");

  const undeclaredBuiltInRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-undeclared-preview",
        userItem: {
          id: "u-undeclared-preview",
          kind: "user",
          content: "inspect undeclared preview",
          turnId: "turn-undeclared-preview",
        },
        steps: [
          {
            stepId: "step-undeclared-preview",
            stepIndex: 1,
            activityItems: [
              {
                id: "bash-undeclared-preview",
                kind: "tool",
                toolName: "bash",
                status: "success",
                arguments: { command: "uv run pytest tests/undeclared" },
                turnId: "turn-undeclared-preview",
                stepId: "step-undeclared-preview",
              },
              {
                id: "read-undeclared-preview",
                kind: "tool",
                toolName: "read_file",
                status: "success",
                arguments: { path: "src/undeclared.c" },
                turnId: "turn-undeclared-preview",
                stepId: "step-undeclared-preview",
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
    activeTurnId: "turn-undeclared-preview",
  });
  const undeclaredBash = undeclaredBuiltInRows.find((row) => row.id === "bash-undeclared-preview");
  assert.equal(undeclaredBash.requestKind, "");
  assert.equal(undeclaredBash.commandPreview, "");
  const undeclaredRead = undeclaredBuiltInRows.find((row) => row.id === "read-undeclared-preview");
  assert.equal(undeclaredRead.requestKind, "");
  assert.equal(undeclaredRead.commandPreview, "");

  const actionPresentationRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-action-presentation",
        userItem: {
          id: "u-action-presentation",
          kind: "user",
          content: "inspect action presentation",
          turnId: "turn-action-presentation",
        },
        steps: [
          {
            stepId: "step-action-presentation",
            stepIndex: 1,
            activityItems: [
              {
                id: "cmd-action",
                kind: "tool",
                label: "Bash Complete",
                toolTitle: "Ran command",
                itemType: "command_execution",
                requestKind: "command",
                toolLifecycleStatus: "completed",
                command: "uv run pytest tests/",
                rawCommand: "python -m pytest tests/",
                status: "success",
                turnId: "turn-action-presentation",
                stepId: "step-action-presentation",
              },
              {
                id: "read-action",
                kind: "tool",
                label: "Read File Complete",
                toolTitle: "Read File",
                itemType: "dynamic_tool_call",
                requestKind: "file-read",
                toolLifecycleStatus: "completed",
                detail: "src/main.c",
                status: "success",
                turnId: "turn-action-presentation",
                stepId: "step-action-presentation",
              },
              {
                id: "mcp-action",
                kind: "tool",
                label: "Tool call complete",
                toolTitle: "t3-code · preview_status",
                itemType: "mcp_tool_call",
                toolData: { name: "preview_status", input: { url: "http://localhost:5173" } },
                status: "success",
                turnId: "turn-action-presentation",
                stepId: "step-action-presentation",
              },
              {
                id: "warn-action",
                kind: "tool",
                label: "Runtime warning",
                sourceActivityKind: "runtime.warning",
                status: "success",
                detail: "stale pending user-input request",
                turnId: "turn-action-presentation",
                stepId: "step-action-presentation",
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
    activeTurnId: "turn-action-presentation",
  });

  const actionRows = actionPresentationRows.filter((row) => row.kind === T3_ROW_KINDS.WORK);
  assert.equal(actionRows.length, 4);
  const commandPresentation = actionRows.find((row) => row.id === "cmd-action").presentation;
  assert.equal(commandPresentation.heading, "Ran command");
  assert.equal(commandPresentation.preview, "uv run pytest tests/");
  assert.equal(commandPresentation.iconName, "terminal");
  assert.equal(commandPresentation.statusIndicator, "success");
  assert.equal(commandPresentation.expandedBody.includes("python -m pytest tests/"), true);
  assert.equal(commandPresentation.expandedBody.includes("uv run pytest tests/"), false);

  const readPresentation = actionRows.find((row) => row.id === "read-action").presentation;
  assert.equal(readPresentation.heading, "Read File");
  assert.equal(readPresentation.preview, "src/main.c");
  assert.equal(readPresentation.iconName, "eye");

  const mcpPresentation = actionRows.find((row) => row.id === "mcp-action").presentation;
  assert.equal(mcpPresentation.heading, "T3-code · preview_status");
  assert.equal(mcpPresentation.iconName, "wrench");
  assert.equal(mcpPresentation.expandedBody.includes("MCP call"), true);
  assert.equal(mcpPresentation.expandedBody.includes("preview_status"), true);

  const warningPresentation = actionRows.find((row) => row.id === "warn-action").presentation;
  assert.equal(warningPresentation.iconName, "x");
  assert.equal(warningPresentation.statusIndicator, "success");
  assert.equal(warningPresentation.headingTone, "warning");

  assert.deepEqual(
    buildWorkPresentation({
      label: "Search Complete",
      toolTitle: "grep",
      itemType: "web_search",
      detail: "TODO",
      status: "running",
      toolLifecycleStatus: "inProgress",
    }),
    {
      heading: "Grep",
      preview: "TODO",
      iconName: "globe",
      statusIndicator: "neutral",
      headingTone: "normal",
      iconTone: "normal",
      canExpand: true,
      expandedBody: "TODO",
    },
  );
  assert.deepEqual(
    buildWorkPresentation({}),
    {
      heading: "",
      preview: "",
      iconName: "",
      statusIndicator: "",
      headingTone: "normal",
      iconTone: "normal",
      canExpand: false,
      expandedBody: "",
    },
  );

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
                toolName: "workflow_task",
                label: "Workflow Task",
                status: "error",
                error: "task failed",
                arguments: { recipe_id: "python-test", target: "parser" },
                data: {
                  recipe_id: "python-test",
                  command: "uv run pytest tests/parser",
                  exit_code: 1,
                  stdout_preview: "Running parser tests",
                  stderr_preview: "parser test failed",
                },
                turnId: "turn-detail",
                stepId: "step-detail",
                stepIndex: 1,
              },
              {
                id: "summary-detail",
                kind: "tool",
                toolName: "custom_agent_report",
                label: "Custom Agent Report",
                status: "success",
                data: {
                  summary: "custom agent summary",
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
  assert.equal(detailWorkRows.length, 5);
  const readDetail = detailWorkRows.find((row) => row.toolName === "read_file").detailModel;
  assert.equal(readDetail.kind, "tool_detail");
  assert.equal(readDetail.fields.find((field) => field.key === "path").value, "src/parser.c");
  assert.equal(readDetail.fields.find((field) => field.key === "lines").value, "12");
  assert.equal(readDetail.fields.find((field) => field.key === "path").label, "");
  const readPreviewSection = readDetail.sections.find((section) => section.kind === "preview");
  assert.equal(readPreviewSection.content, "int parse(void);");
  assert.equal(readPreviewSection.title, "");
  assert.equal(readDetail.rawJson, undefined);

  const grepDetail = detailWorkRows.find((row) => row.toolName === "grep_text").detailModel;
  assert.equal(grepDetail.fields.find((field) => field.key === "pattern").value, "parse");
  assert.equal(grepDetail.sections.find((section) => section.kind === "matches").items.length, 2);
  assert.equal(grepDetail.sections.find((section) => section.kind === "matches").title, "");

  const editDetail = detailWorkRows.find((row) => row.toolName === "edit_file").detailModel;
  assert.equal(editDetail.sections.find((section) => section.kind === "diff").content.includes("@@ -1 +1 @@"), true);
  assert.equal(editDetail.sections.find((section) => section.kind === "diff").title, "");
  assert.equal(detailWorkRows.find((row) => row.toolName === "edit_file").changedFiles[0].path, "src/parser.c");

  const recipeDetail = detailWorkRows.find((row) => row.toolName === "workflow_task").detailModel;
  assert.equal(recipeDetail.fields.find((field) => field.key === "recipe").value, "python-test");
  assert.equal(recipeDetail.fields.find((field) => field.key === "exit").value, "1");
  assert.equal(recipeDetail.sections.find((section) => section.kind === "stderr").content.includes("failed"), true);
  assert.equal(recipeDetail.sections.find((section) => section.kind === "stderr").title, "");

  const summaryDetail = detailWorkRows.find((row) => row.toolName === "custom_agent_report").detailModel;
  const summarySection = summaryDetail.sections.find((section) => section.kind === "summary");
  assert.equal(summarySection.content, "custom agent summary");
  assert.equal(summarySection.title, "");

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

  const catalogChanged = summarizeChangedFiles(
    [
      {
        id: "catalog-write-1",
        kind: "tool",
        toolName: "write_file",
        status: "success",
        arguments: { path: "src/catalog-driven.c" },
        data: { additions: 1 },
      },
    ],
    {
      toolCatalog: {
        write_file: {
          name: "write_file",
          metadata: { changed_path_arg: "path" },
        },
      },
    },
  );
  assert.deepEqual(catalogChanged.files.map((file) => file.path), ["src/catalog-driven.c"]);
  assert.equal(catalogChanged.additions, 1);

  const undeclaredChanged = summarizeChangedFiles([
    {
      id: "undeclared-write-1",
      kind: "tool",
      toolName: "write_file",
      status: "success",
      arguments: { path: "src/undeclared-write.c" },
      data: { additions: 1 },
    },
  ]);
  assert.deepEqual(undeclaredChanged.files, []);

  const catalogDiffRows = projectT3TimelineRows({
    toolCatalog: {
      write_file: {
        name: "write_file",
        metadata: { changed_path_arg: "path" },
      },
    },
    turnGroups: [
      {
        turnId: "turn-catalog-changed-files",
        userItem: { id: "u-catalog-changed", kind: "user", content: "write", turnId: "turn-catalog-changed-files" },
        steps: [
          {
            stepId: "step-catalog-changed",
            stepIndex: 1,
            activityItems: [
              {
                id: "catalog-write-row",
                kind: "tool",
                toolName: "write_file",
                status: "success",
                arguments: { path: "src/catalog-row.c" },
                data: { additions: 1 },
                turnId: "turn-catalog-changed-files",
                stepId: "step-catalog-changed",
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
  });
  const catalogDiffSummary = catalogDiffRows.find((row) => row.kind === T3_ROW_KINDS.DIFF_SUMMARY);
  assert.deepEqual(catalogDiffSummary.files.map((file) => file.path), ["src/catalog-row.c"]);

  const undeclaredDiffRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-undeclared-changed-files",
        userItem: { id: "u-undeclared-changed", kind: "user", content: "write", turnId: "turn-undeclared-changed-files" },
        steps: [
          {
            stepId: "step-undeclared-changed",
            stepIndex: 1,
            activityItems: [
              {
                id: "undeclared-write-row",
                kind: "tool",
                toolName: "write_file",
                status: "success",
                arguments: { path: "src/undeclared-row.c" },
                data: { additions: 1 },
                turnId: "turn-undeclared-changed-files",
                stepId: "step-undeclared-changed",
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
  });
  assert.equal(undeclaredDiffRows.some((row) => row.kind === T3_ROW_KINDS.DIFF_SUMMARY), false);

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
                toolName: "pytest",
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

  const experienceRows = projectT3TimelineRows({
    turnGroups: [],
    currentStatus: "idle",
    turnExperience: {
      status: "blocked",
      completed: [{ kind: "file_created", path: "README.md" }],
      unverified: [{ kind: "validation_missing", message: "Created files have not been validated." }],
      next_steps: ["Run validation for the changed files."],
    },
  });
  assert.equal(experienceRows.length, 1);
  assert.equal(experienceRows[0].kind, "system_notice");
  assert.equal(experienceRows[0].content.includes("Unverified: validation_missing Created files have not been validated."), true);

  const reviewNameOnlyRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-review-name-only",
        userItem: { id: "u-review-name-only", kind: "user", content: "run review command", turnId: "turn-review-name-only" },
        leadingSystemItems: [],
        steps: [],
        trailingTurnItems: [
          {
            id: "review-name-only",
            kind: "command_result",
            commandName: "review",
            success: true,
            content: "Command completed without structured review payload.",
            turnId: "turn-review-name-only",
          },
        ],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "idle",
  });
  const reviewNameOnlyRow = reviewNameOnlyRows.find((row) => row.id === "review-name-only");
  assert.ok(reviewNameOnlyRow);
  assert.equal(reviewNameOnlyRow.kind, T3_ROW_KINDS.COMMAND_RESULT);
  assert.equal(reviewNameOnlyRow.label, "");
  assert.equal(reviewNameOnlyRows.some((row) => row.kind === T3_ROW_KINDS.REVIEW_RESULT), false);

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

  const richFold = richRows.find((row) => row.kind === T3_ROW_KINDS.TURN_FOLD);
  assert.ok(richFold);
  assert.equal(richFold.workCount, 1);
  assert.equal(richFold.reasoningCount, 1);
  assert.deepEqual(
    richFold.entries.map((entry) => entry.kind),
    [T3_ROW_KINDS.CONTEXT_SUMMARY, "reasoning", T3_ROW_KINDS.WORK],
  );
  assert.equal(richFold.entries[0].content, "older turns summarized");
  assert.equal(richFold.entries[1].wordCount, 6);
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
  assert.equal(thinkingRows.some((row) => row.kind === T3_ROW_KINDS.WORKING), true);
  const thinkingRow = thinkingRows.find((row) => row.kind === T3_ROW_KINDS.WORKING);
  assert.equal(thinkingRow.turnId, "turn-thinking");
  assert.equal(thinkingRow.label, undefined);

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
  assert.equal(streamingReasoningRows.some((row) => row.kind === "reasoning"), false);
  assert.equal(streamingReasoningRows.some((row) => row.kind === T3_ROW_KINDS.WORKING), true);

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
  assert.equal(priorReasoningActiveThinkingRows.some((row) => row.kind === T3_ROW_KINDS.WORKING), true);

  const interleavedRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-interleaved",
        userItem: {
          id: "u-interleaved",
          kind: "user",
          content: "inspect and summarize",
          turnId: "turn-interleaved",
        },
        leadingSystemItems: [],
        steps: [
          {
            stepId: "step-1",
            stepIndex: 1,
            activityItems: [
              {
                id: "reason-1",
                kind: "reasoning",
                content: "Need to inspect the entry point.",
                streaming: false,
                turnId: "turn-interleaved",
                stepId: "step-1",
                stepIndex: 1,
              },
              {
                id: "tool-1",
                kind: "tool",
                toolName: "read_file",
                label: "Read File",
                status: "success",
                arguments: { path: "src/main.c" },
                turnId: "turn-interleaved",
                stepId: "step-1",
                stepIndex: 1,
              },
            ],
            assistantItem: {
              id: "assistant-1",
              kind: "assistant",
              content: "I found the entry point.",
              turnId: "turn-interleaved",
              stepId: "step-1",
              stepIndex: 1,
            },
          },
          {
            stepId: "step-2",
            stepIndex: 2,
            activityItems: [
              {
                id: "reason-2",
                kind: "reasoning",
                content: "Now inspect the helper.",
                streaming: false,
                turnId: "turn-interleaved",
                stepId: "step-2",
                stepIndex: 2,
              },
              {
                id: "tool-2",
                kind: "tool",
                toolName: "grep_text",
                label: "Search",
                status: "success",
                arguments: { pattern: "helper" },
                turnId: "turn-interleaved",
                stepId: "step-2",
                stepIndex: 2,
              },
            ],
            assistantItem: {
              id: "assistant-2",
              kind: "assistant",
              content: "The helper is called from main.",
              turnId: "turn-interleaved",
              stepId: "step-2",
              stepIndex: 2,
            },
          },
        ],
        trailingTurnItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "running",
    activeTurnId: "turn-interleaved",
  });
  assert.deepEqual(
    interleavedRows.map((row) => row.id),
    [
      "u-interleaved",
      "reason-1",
      "tool-1",
      "assistant-1",
      "reason-2",
      "tool-2",
      "assistant-2",
    ],
  );

  const multiCycleRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-multi-cycle",
        userItem: {
          id: "u-multi-cycle",
          kind: "user",
          content: "inspect, search, explain, then continue",
          turnId: "turn-multi-cycle",
        },
        leadingSystemItems: [],
        steps: [
          {
            stepId: "cycle-step-1",
            stepIndex: 1,
            activityItems: [
              {
                id: "cycle-thinking-1",
                kind: "reasoning",
                content: "First decide what to inspect.",
                streaming: false,
                turnId: "turn-multi-cycle",
                stepId: "cycle-step-1",
                stepIndex: 1,
              },
              {
                id: "cycle-tool-1",
                kind: "tool",
                toolName: "read_file",
                label: "Read File",
                status: "success",
                arguments: { path: "src/main.c" },
                turnId: "turn-multi-cycle",
                stepId: "cycle-step-1",
                stepIndex: 1,
              },
              {
                id: "cycle-tool-2",
                kind: "tool",
                toolName: "grep_text",
                label: "Search",
                status: "success",
                arguments: { pattern: "TODO" },
                turnId: "turn-multi-cycle",
                stepId: "cycle-step-1",
                stepIndex: 1,
              },
            ],
            assistantItem: {
              id: "cycle-output-1",
              kind: "assistant",
              content: "The first pass found one TODO.",
              turnId: "turn-multi-cycle",
              stepId: "cycle-step-1",
              stepIndex: 1,
            },
          },
          {
            stepId: "cycle-step-2",
            stepIndex: 2,
            activityItems: [
              {
                id: "cycle-thinking-2",
                kind: "reasoning",
                content: "Now inspect the helper before the final answer.",
                streaming: false,
                turnId: "turn-multi-cycle",
                stepId: "cycle-step-2",
                stepIndex: 2,
              },
              {
                id: "cycle-tool-3",
                kind: "tool",
                toolName: "read_file",
                label: "Read File",
                status: "success",
                arguments: { path: "src/helper.c" },
                turnId: "turn-multi-cycle",
                stepId: "cycle-step-2",
                stepIndex: 2,
              },
              {
                id: "cycle-thinking-3",
                kind: "reasoning",
                content: "Synthesize the result.",
                streaming: false,
                turnId: "turn-multi-cycle",
                stepId: "cycle-step-2",
                stepIndex: 2,
              },
            ],
            assistantItem: {
              id: "cycle-output-2",
              kind: "assistant",
              content: "The helper confirms the final behavior.",
              turnId: "turn-multi-cycle",
              stepId: "cycle-step-2",
              stepIndex: 2,
            },
          },
        ],
        trailingTurnItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "running",
    activeTurnId: "turn-multi-cycle",
  });
  assert.deepEqual(
    multiCycleRows.map((row) => row.id),
    [
      "u-multi-cycle",
      "cycle-thinking-1",
      "cycle-tool-1",
      "cycle-tool-2",
      "cycle-output-1",
      "cycle-thinking-2",
      "cycle-tool-3",
      "cycle-thinking-3",
      "cycle-output-2",
    ],
  );

  const settledInterleavedRows = projectT3TimelineRows({
    turnGroups: [
      {
        turnId: "turn-settled-interleaved",
        userItem: {
          id: "u-settled-interleaved",
          kind: "user",
          content: "inspect twice and summarize",
          turnId: "turn-settled-interleaved",
        },
        leadingSystemItems: [],
        steps: [
          {
            stepId: "step-settled-1",
            stepIndex: 1,
            activityItems: [
              {
                id: "tool-settled-1",
                kind: "tool",
                toolName: "read_file",
                label: "Read File",
                status: "success",
                arguments: { path: "src/main.c" },
                turnId: "turn-settled-interleaved",
                stepId: "step-settled-1",
                stepIndex: 1,
              },
            ],
            assistantItem: {
              id: "assistant-settled-commentary",
              kind: "assistant",
              content: "I found main.",
              turnId: "turn-settled-interleaved",
              stepId: "step-settled-1",
              stepIndex: 1,
            },
          },
          {
            stepId: "step-settled-2",
            stepIndex: 2,
            activityItems: [
              {
                id: "tool-settled-2",
                kind: "tool",
                toolName: "grep_text",
                label: "Search",
                status: "success",
                arguments: { pattern: "helper" },
                turnId: "turn-settled-interleaved",
                stepId: "step-settled-2",
                stepIndex: 2,
              },
            ],
            assistantItem: {
              id: "assistant-settled-terminal",
              kind: "assistant",
              content: "Main calls helper.",
              turnId: "turn-settled-interleaved",
              stepId: "step-settled-2",
              stepIndex: 2,
            },
          },
        ],
        trailingTurnItems: [],
        sessionFallbackItems: [],
      },
    ],
    currentStatus: "idle",
    activeTurnId: "",
  });
  assert.deepEqual(
    settledInterleavedRows.map((row) => row.id),
    ["u-settled-interleaved", "turn-fold-turn-settled-interleaved", "assistant-settled-terminal"],
  );
  assert.deepEqual(
    settledInterleavedRows[1].entries.map((entry) => entry.id),
    ["tool-settled-1", "assistant-settled-commentary", "tool-settled-2"],
  );

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
