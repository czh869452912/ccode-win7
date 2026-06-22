# T3 Timeline Rich Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the active T3-style GUI timeline render thinking, reasoning, compact, command, and review activity with rich formatting while preserving Agent Core as a small protocol producer.

**Architecture:** Keep this slice entirely in the GUI app shell. `session-runtime/t3-timeline.js` becomes the frontend-local row projection boundary, `timeline-ui-state.js` owns transient expansion defaults, and `TimelineRows.jsx` renders all projected row kinds without new backend/Core APIs.

**Tech Stack:** React 18, plain JavaScript ES modules, plain CSS, existing Node webapp tests, existing Playwright visual debug harness, existing Python GUI backend tests.

---

## File Structure

- Modify `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - Add failing projection coverage for `reasoning`, `thinking`, `compact`, `command_result`, `review_result`, and fold entries that contain non-tool activity.
- Modify `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
  - Add failing coverage that `projectSessionRuntime(...)` receives GUI-local `activeTurnId` and `thinkingActive` from `App.jsx` state.
- Modify `src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs`
  - Add failing expansion-key/default coverage for the new row kinds.
- Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Add source-contract assertions for the new row renderers, App runtime bridge, visual fixture fields, and responsive CSS guardrails.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - Expand the T3 row vocabulary and project rich row types from existing frontend timeline items.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  - Accept `activeTurnId` and `thinkingActive`, pass them into `projectT3TimelineRows(...)`, and leave backend snapshot shape unchanged.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
  - Add stable keys and expansion defaults for reasoning, compact, command result, review result, and thinking rows.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Pass reducer-owned `activeTurnId` and `thinkingActive` into `projectSessionRuntime(...)`.
  - Enrich the dev-only visual timeline fixture with rich timeline row kinds.
- Modify `src/embedagent/frontend/gui/webapp/src/store.js`
  - Let `visual_timeline_fixture_loaded` set `activeTurnId`, `activeStepId`, `activeStepIndex`, `streamingReasoningId`, and `thinkingActive` from fixture actions.
- Modify `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - Render the new row kinds and make turn folds render all nested row kinds through one row switch.
- Modify `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Add rich timeline row styling and responsive shell guardrails for zoomed/narrow layouts.
- Modify `scripts/gui-visual-debug.mjs`
  - Strengthen the `timeline` and `responsive` scenarios to assert rich row visibility and non-overlap.
- Modify `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`
  - Add source-level checks that the visual harness looks for rich row test ids.
- Modify docs:
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`

## Constraints For Every Task

- Do not modify Agent Core, providers, tool execution, permissions, transcript reducers, operation reducers, workflow packages, or backend session APIs.
- Do not add npm or Python runtime dependencies.
- Do not copy cloud, auth, remote sync, marketplace, or multi-device pieces from `reference/t3code`.
- Keep all new display semantics GUI-local and derived from existing bootstrap/timeline/WebSocket state.
- Use only JavaScript syntax already accepted by the existing webapp build.
- Keep documentation wording explicit that this is GUI app-shell display/read-model work, not new session-history truth.

## Task 1: Add Failing Rich Row Projection Tests

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`

- [ ] **Step 1: Add row-kind import coverage**

Modify the import at the top of `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`:

```js
import {
  T3_ROW_KINDS,
  buildChangedFilesTree,
  projectT3TimelineRows,
  summarizeChangedFiles,
  summarizeDiffStats,
} from "../src/session-runtime/t3-timeline.js";
```

- [ ] **Step 2: Add failing rich activity projection assertions**

Append this block inside `runT3TimelineTests()` after the existing `systemRows` assertions and before the `tree` assertions:

```js
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
```

- [ ] **Step 3: Add failing active thinking projection assertions**

Append this block immediately after the rich row assertions:

```js
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
```

- [ ] **Step 4: Run the failing projection tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `T3_ROW_KINDS.COMPACT`, `THINKING`, `REASONING`, `COMMAND_RESULT`, and `REVIEW_RESULT` are not projected yet.

## Task 2: Implement Rich T3 Timeline Projection

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- Test: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`

- [ ] **Step 1: Expand the row vocabulary**

Modify `T3_ROW_KINDS` in `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js` to:

```js
export const T3_ROW_KINDS = Object.freeze({
  MESSAGE: "message",
  WORK: "work",
  TURN_FOLD: "turn_fold",
  INTERACTION: "interaction",
  DIFF_SUMMARY: "diff_summary",
  THINKING: "thinking",
  REASONING: "reasoning",
  COMPACT: "compact",
  COMMAND_RESULT: "command_result",
  REVIEW_RESULT: "review_result",
  WORKING: "working",
  SYSTEM_NOTICE: "system_notice",
});
```

- [ ] **Step 2: Add rich row helper functions**

Add these helpers after `messageRow(...)` and before `systemNoticeRow(...)`:

```js
function wordCountFor(text) {
  return stringValue(text).split(/\s+/).filter(Boolean).length;
}

function reasoningRow(item) {
  const content = stringValue(item?.content || item?.text || item?.summary);
  return {
    id: stringValue(item?.id || `reasoning-${item?.turnId || item?.turn_id || "row"}`),
    kind: T3_ROW_KINDS.REASONING,
    turnId: stringValue(item?.turnId || item?.turn_id),
    stepId: stringValue(item?.stepId || item?.step_id),
    stepIndex: numberValue(item?.stepIndex || item?.step_index),
    label: stringValue(item?.label || "Thinking"),
    content,
    wordCount: wordCountFor(content),
    streaming: Boolean(item?.streaming),
    rawItem: item || {},
  };
}

function compactRow(item) {
  return {
    id: stringValue(item?.id || `compact-${item?.turnId || item?.turn_id || "row"}`),
    kind: T3_ROW_KINDS.COMPACT,
    turnId: stringValue(item?.turnId || item?.turn_id),
    tone: stringValue(item?.tone || "context"),
    content: stringValue(item?.content || item?.summary || "Context compacted"),
    summarizedTurns:
      item?.summarizedTurns !== undefined
        ? numberValue(item.summarizedTurns)
        : item?.summarized_turns !== undefined
          ? numberValue(item.summarized_turns)
          : undefined,
    recentTurns:
      item?.recentTurns !== undefined
        ? numberValue(item.recentTurns)
        : item?.recent_turns !== undefined
          ? numberValue(item.recent_turns)
          : undefined,
    approxTokensAfter:
      item?.approxTokensAfter !== undefined
        ? numberValue(item.approxTokensAfter)
        : item?.approx_tokens_after !== undefined
          ? numberValue(item.approx_tokens_after)
          : undefined,
    rawItem: item || {},
  };
}

function commandResultContent(item) {
  return stringValue(
    item?.content ||
      item?.message ||
      item?.summary ||
      item?.data?.message ||
      item?.data?.summary ||
      "",
  );
}

function commandResultRow(item) {
  const commandName = stringValue(item?.commandName || item?.command_name || "command");
  return {
    id: stringValue(item?.id || `command-${commandName}-${item?.turnId || item?.turn_id || "row"}`),
    kind: T3_ROW_KINDS.COMMAND_RESULT,
    turnId: stringValue(item?.turnId || item?.turn_id),
    commandName,
    label: `/${commandName}`,
    success: item?.success !== false,
    tone: item?.success === false ? "error" : "context",
    content: commandResultContent(item),
    data: item?.data || {},
    rawItem: item || {},
  };
}

function normalizeReviewFinding(finding, index) {
  return {
    id: stringValue(finding?.id || `finding-${index + 1}`),
    severity: stringValue(finding?.severity || ""),
    priority: finding?.priority !== undefined ? numberValue(finding.priority) : undefined,
    title: stringValue(finding?.title || finding?.message || "Review finding"),
    body: stringValue(finding?.body || finding?.detail || finding?.description || ""),
    file: stringValue(finding?.file || finding?.path || ""),
    line: finding?.line !== undefined ? numberValue(finding.line) : undefined,
  };
}

function reviewResultRow(item) {
  const review = item?.data?.review || item?.review || {};
  const findings = Array.isArray(review.findings)
    ? review.findings.map((finding, index) => normalizeReviewFinding(finding, index))
    : [];
  const residualRisks = Array.isArray(review.residual_risks)
    ? review.residual_risks.map((risk) => stringValue(risk)).filter(Boolean)
    : Array.isArray(review.residualRisks)
      ? review.residualRisks.map((risk) => stringValue(risk)).filter(Boolean)
      : [];
  return {
    ...commandResultRow(item),
    kind: T3_ROW_KINDS.REVIEW_RESULT,
    commandName: "review",
    label: "/review",
    findings,
    residualRisks,
  };
}

function thinkingRow({ activeTurnId, idSuffix = "active" } = {}) {
  return {
    id: `thinking-${activeTurnId || idSuffix || "active"}`,
    kind: T3_ROW_KINDS.THINKING,
    turnId: stringValue(activeTurnId),
    label: "Thinking",
    streaming: true,
  };
}
```

- [ ] **Step 3: Add item-to-row routing**

Add this helper after `interactionRow(...)`:

```js
function activityRowForItem(item) {
  if (!item) return null;
  if (item.kind === "tool") return normalizeWorkEntry(item);
  if (item.kind === "interaction_requested" || item.kind === "interaction_resolved") {
    return interactionRow(item);
  }
  if (item.kind === "reasoning") return reasoningRow(item);
  if (item.kind === "compact") return compactRow(item);
  if (item.kind === "command_result" || item.kind === "command_result_fallback") {
    const commandName = stringValue(item?.commandName || item?.command_name);
    if (commandName === "review" || item?.data?.review || item?.review) {
      return reviewResultRow(item);
    }
    return commandResultRow(item);
  }
  if (item.kind === "system") return systemNoticeRow(item);
  return null;
}
```

Then replace the body of `pushLooseItem(...)` with:

```js
function pushLooseItem(push, item) {
  if (!item) return;
  if (item.kind === "assistant") push(messageRow(item, "assistant"));
  else if (item.kind === "user") push(messageRow(item, "user"));
  else {
    const row = activityRowForItem(item);
    push(row || systemNoticeRow(item));
  }
}
```

- [ ] **Step 4: Replace `turnWorkEntries(...)` with `turnActivityEntries(...)`**

Replace the existing `turnWorkEntries(group)` function with:

```js
function turnActivityEntries(group) {
  const entries = [];
  function pushActivity(item) {
    const row = activityRowForItem(item);
    if (row) entries.push(row);
  }
  for (const step of group?.steps || []) {
    for (const item of step?.activityItems || []) {
      pushActivity(item);
    }
  }
  for (const item of group?.trailingTurnItems || []) {
    pushActivity(item);
  }
  for (const item of group?.detachedItems || []) {
    pushActivity(item);
  }
  return entries;
}
```

Replace every call to `turnWorkEntries(group)` with `turnActivityEntries(group)`.

- [ ] **Step 5: Update fold defaults and counts**

Replace `isTurnFoldedByDefault(...)` with:

```js
function isTurnFoldedByDefault(group, context) {
  const entries = turnActivityEntries(group);
  const workEntries = entries.filter((entry) => entry.kind === T3_ROW_KINDS.WORK);
  if (entries.length === 0) return false;
  if (hasInterruptedWork(workEntries)) return false;
  if (workEntries.some((entry) => entry.status === "running" || entry.tone === "running")) return false;
  if (workEntries.some((entry) => entry.status === "error" || entry.tone === "error")) return false;
  if (entries.some((entry) => entry.kind === T3_ROW_KINDS.REASONING && entry.streaming)) return false;
  if (context.currentStatus === "running" && group?.turnId && group.turnId === context.activeTurnId) {
    return false;
  }
  return assistantRowsForTurn(group).length > 0;
}
```

Inside `projectT3TimelineRows(...)`, update the fold object to:

```js
        pushRow({
          id: `turn-fold-${group.turnId || rows.length}`,
          kind: T3_ROW_KINDS.TURN_FOLD,
          turnId: stringValue(group.turnId),
          label: "Worked for this turn",
          workCount: entries.filter((entry) => entry.kind === T3_ROW_KINDS.WORK).length,
          reasoningCount: entries.filter((entry) => entry.kind === T3_ROW_KINDS.REASONING).length,
          entryCount: entries.length,
          defaultOpen: false,
          entries,
        });
```

- [ ] **Step 6: Add thinking projection**

Modify the `projectT3TimelineRows(...)` signature to include `thinkingActive`:

```js
export function projectT3TimelineRows({
  turnGroups = [],
  currentStatus = "idle",
  activeTurnId = "",
  currentInteraction = null,
  interactionNotice = null,
  thinkingActive = false,
} = {}) {
```

Add these helpers before the final `if (currentStatus === "running" && rows.length === 0)` block:

```js
  const hasVisibleReasoning = rows.some(
    (row) =>
      row.kind === T3_ROW_KINDS.REASONING ||
      (row.kind === T3_ROW_KINDS.TURN_FOLD &&
        Array.isArray(row.entries) &&
        row.entries.some((entry) => entry.kind === T3_ROW_KINDS.REASONING)),
  );
  const hasActiveTurnRow = rows.some(
    (row) =>
      row.turnId === activeTurnId ||
      (row.kind === T3_ROW_KINDS.TURN_FOLD &&
        Array.isArray(row.entries) &&
        row.entries.some((entry) => entry.turnId === activeTurnId)),
  );
  if (currentStatus === "running" && thinkingActive && !hasVisibleReasoning && (activeTurnId || hasActiveTurnRow)) {
    pushRow(thinkingRow({ activeTurnId, idSuffix: rows.length }));
  }
```

Leave the existing generic `working` fallback in place after this new block.

- [ ] **Step 7: Run projection tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: projection assertions from Task 1 now pass or reveal only runtime bridge/UI-state failures from later tasks.

- [ ] **Step 8: Commit projection changes**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs
git commit -m "feat: project rich t3 timeline rows"
```

## Task 3: Bridge GUI Thinking State Into Runtime Projection

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`

- [ ] **Step 1: Add failing runtime bridge test**

Append this block inside `runSessionRuntimeTests()` in `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`:

```js
  const thinkingRuntime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-thinking",
      status: "running",
      current_mode: "build",
    },
    eventLog: createSessionEventLog(),
    bootstrapTimeline: [
      {
        id: "u-thinking-runtime",
        kind: "user",
        content: "think in runtime",
        turnId: "turn-runtime",
      },
    ],
    activeTurnId: "turn-runtime",
    thinkingActive: true,
  });
  assert.equal(thinkingRuntime.t3TimelineRows.some((row) => row.kind === "thinking"), true);
```

- [ ] **Step 2: Run failing runtime bridge test**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `projectSessionRuntime(...)` ignores `activeTurnId` and `thinkingActive`.

- [ ] **Step 3: Update `projectSessionRuntime(...)` signature and call**

Modify the export signature in `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`:

```js
export function projectSessionRuntime({
  snapshot,
  eventLog,
  bootstrapTimeline = [],
  defaultMode = "explore",
  activeTurnId = "",
  thinkingActive = false,
} = {}) {
```

Modify the `projectT3TimelineRows(...)` call:

```js
    t3TimelineRows: projectT3TimelineRows({
      turnGroups: timelineView,
      currentStatus: snapshot?.status || "idle",
      activeTurnId: activeTurnId || snapshot?.active_turn_id || "",
      currentInteraction,
      interactionNotice,
      thinkingActive,
    }),
```

- [ ] **Step 4: Update `App.jsx` runtime projection call**

Modify the `useMemo` call in `src/embedagent/frontend/gui/webapp/src/App.jsx`:

```js
  const runtimeState = useMemo(
    () =>
      projectSessionRuntime({
        snapshot: state.snapshot,
        eventLog: sessionEventLog,
        bootstrapTimeline: state.timeline,
        defaultMode: DEFAULT_MODE,
        activeTurnId: state.activeTurnId,
        thinkingActive: state.thinkingActive,
      }),
    [sessionEventLog, state.activeTurnId, state.snapshot, state.thinkingActive, state.timeline],
  );
```

- [ ] **Step 5: Run runtime tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: runtime bridge test passes.

- [ ] **Step 6: Commit runtime bridge changes**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs
git commit -m "feat: bridge gui thinking state into t3 runtime"
```

## Task 4: Extend Timeline UI State For Rich Rows

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`

- [ ] **Step 1: Add failing UI-state assertions**

Append these assertions inside `runTimelineUiStateTests()`:

```js
  const richRows = [
    { id: "reason-done", kind: "reasoning", turnId: "turn-1", stepId: "step-1", streaming: false },
    { id: "reason-stream", kind: "reasoning", turnId: "turn-1", stepId: "step-2", streaming: true },
    { id: "cmd-ok", kind: "command_result", turnId: "turn-1", success: true },
    { id: "cmd-fail", kind: "command_result", turnId: "turn-1", success: false, content: "failed" },
    { id: "review-fail", kind: "review_result", turnId: "turn-1", success: false, findings: [{ id: "f1" }] },
    { id: "compact-1", kind: "compact", turnId: "turn-1" },
    { id: "thinking-turn-1", kind: "thinking", turnId: "turn-1" },
  ];
  const richState = createTimelineUiState(richRows);
  assert.equal(rowUiKey(richRows[0]), "reasoning:turn-1:step-1:reason-done");
  assert.equal(rowUiKey(richRows[2]), "command_result:turn-1:cmd-ok");
  assert.equal(rowUiKey(richRows[4]), "review_result:turn-1:review-fail");
  assert.equal(rowUiKey(richRows[5]), "compact:turn-1:compact-1");
  assert.equal(rowUiKey(richRows[6]), "thinking:turn-1:thinking-turn-1");
  assert.equal(richState.expanded[rowUiKey(richRows[0])], false);
  assert.equal(richState.expanded[rowUiKey(richRows[1])], true);
  assert.equal(richState.expanded[rowUiKey(richRows[2])], false);
  assert.equal(richState.expanded[rowUiKey(richRows[3])], true);
  assert.equal(richState.expanded[rowUiKey(richRows[4])], true);
  assert.equal(richState.expanded[rowUiKey(richRows[5])], false);
  assert.equal(richState.expanded[rowUiKey(richRows[6])], true);
```

- [ ] **Step 2: Run failing UI-state test**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because rich row keys/defaults are not defined.

- [ ] **Step 3: Implement row keys for new row kinds**

Modify `rowUiKey(row)` in `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js` by adding these branches after the `turn_fold` branch:

```js
  if (kind === "reasoning") {
    return [
      "reasoning",
      stringValue(row?.turnId || row?.turn_id),
      stringValue(row?.stepId || row?.step_id),
      stringValue(row?.id),
    ].join(":");
  }
  if (kind === "command_result" || kind === "review_result" || kind === "compact" || kind === "thinking") {
    return [
      kind,
      stringValue(row?.turnId || row?.turn_id),
      stringValue(row?.id || "row"),
    ].join(":");
  }
```

- [ ] **Step 4: Implement expansion defaults**

Modify `defaultExpanded(row)` in the same file:

```js
function defaultExpanded(row) {
  if (!row) return false;
  if (row.kind === "turn_fold") return booleanValue(row.defaultOpen, false);
  if (row.kind === "thinking") return true;
  if (row.kind === "reasoning") return Boolean(row.streaming);
  if (row.kind === "command_result") {
    return row.success === false && Boolean(row.content || row.detail || row.data);
  }
  if (row.kind === "review_result") {
    return row.success === false || (Array.isArray(row.findings) && row.findings.length > 0);
  }
  if (row.kind === "compact") return false;
  if (row.kind !== "work") return false;
  if (row.tone === "interrupted" || row.tone === "discarded") return true;
  if (row.status === "error" || row.tone === "error") return true;
  if (row.status === "running" || row.tone === "running") return true;
  return false;
}
```

- [ ] **Step 5: Run UI-state tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: UI-state assertions pass.

- [ ] **Step 6: Commit UI-state changes**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs
git commit -m "feat: control rich timeline row expansion"
```

## Task 5: Render Rich Rows In The T3 Timeline

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`

- [ ] **Step 1: Add source-contract renderer assertions**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, after the existing `timelineRowsSource` assertions, add:

```js
  assert.equal(timelineRowsSource.includes("ReasoningRow"), true);
  assert.equal(timelineRowsSource.includes("ThinkingRow"), true);
  assert.equal(timelineRowsSource.includes("CompactRow"), true);
  assert.equal(timelineRowsSource.includes("CommandResultRow"), true);
  assert.equal(timelineRowsSource.includes("ReviewResultRow"), true);
  assert.equal(timelineRowsSource.includes("TimelineRowSwitch"), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-reasoning-row"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-thinking-row"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-compact-row"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-command-result-row"'), true);
  assert.equal(timelineRowsSource.includes('data-testid="timeline-review-result-row"'), true);
```

- [ ] **Step 2: Run failing renderer source test**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the new renderer names and test ids do not exist.

- [ ] **Step 3: Add rich row renderer components**

In `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`, add these components after `InteractionRow(...)`:

```jsx
function ExpandableShell({ row, rowKeyFor, rowUiState, onToggleRow, className, testId, label, meta, children }) {
  const key = rowKeyFor(row);
  const open = Boolean(rowUiState?.expanded?.[key]);
  return (
    <section className={className} data-testid={testId} data-row-kind={row.kind} data-row-key={key}>
      <button
        type="button"
        className="t3-rich-row-summary"
        aria-expanded={open}
        onClick={() => onToggleRow && onToggleRow(key)}
      >
        <span className="t3-rich-row-label">{label}</span>
        {meta ? <span className="t3-rich-row-meta">{meta}</span> : null}
      </button>
      {open ? <div className="t3-rich-row-body">{children}</div> : null}
    </section>
  );
}

function ReasoningRow({ row, rowUiState, onToggleRow, rowKeyFor }) {
  const meta = row.streaming ? "streaming" : `${row.wordCount || 0} words`;
  return (
    <ExpandableShell
      row={row}
      rowUiState={rowUiState}
      onToggleRow={onToggleRow}
      rowKeyFor={rowKeyFor}
      className={`t3-reasoning-row${row.streaming ? " streaming" : ""}`}
      testId="timeline-reasoning-row"
      label={row.label || "Thinking"}
      meta={meta}
    >
      <pre>{row.content || ""}</pre>
    </ExpandableShell>
  );
}

function ThinkingRow({ row }) {
  return (
    <div className="t3-thinking-row" data-testid="timeline-thinking-row" data-row-kind="thinking" aria-live="polite">
      <span className="t3-thinking-pulse" aria-hidden="true" />
      <span>{row.label || "Thinking"}</span>
    </div>
  );
}

function CompactRow({ row }) {
  const parts = [];
  if (row.summarizedTurns !== undefined) parts.push(`${row.summarizedTurns} summarized`);
  if (row.recentTurns !== undefined) parts.push(`${row.recentTurns} retained`);
  if (row.approxTokensAfter !== undefined) parts.push(`~${Number(row.approxTokensAfter).toLocaleString()} tokens`);
  return (
    <div className="t3-compact-row system-card context" data-testid="timeline-compact-row" data-row-kind="compact" role="status">
      <span>{row.content || "Context compacted"}</span>
      {parts.length > 0 ? <span className="t3-rich-row-meta">{parts.join(" / ")}</span> : null}
    </div>
  );
}

function CommandResultRow({ row, markdownComponents, rowUiState, onToggleRow, rowKeyFor }) {
  return (
    <ExpandableShell
      row={row}
      rowUiState={rowUiState}
      onToggleRow={onToggleRow}
      rowKeyFor={rowKeyFor}
      className={`t3-command-result-row ${row.success === false ? "error" : "success"}`}
      testId="timeline-command-result-row"
      label={row.label || `/${row.commandName || "command"}`}
      meta={row.success === false ? "failed" : "completed"}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        className="markdown-body"
        components={markdownComponents}
      >
        {row.content || ""}
      </ReactMarkdown>
    </ExpandableShell>
  );
}

function ReviewResultRow({ row, markdownComponents, rowUiState, onToggleRow, rowKeyFor }) {
  const findingCount = Array.isArray(row.findings) ? row.findings.length : 0;
  return (
    <ExpandableShell
      row={row}
      rowUiState={rowUiState}
      onToggleRow={onToggleRow}
      rowKeyFor={rowKeyFor}
      className={`t3-review-result-row ${row.success === false ? "error" : "success"}`}
      testId="timeline-review-result-row"
      label="/review"
      meta={findingCount === 1 ? "1 finding" : `${findingCount} findings`}
    >
      {row.content ? (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex]}
          className="markdown-body"
          components={markdownComponents}
        >
          {row.content}
        </ReactMarkdown>
      ) : null}
      {findingCount > 0 ? (
        <div className="t3-review-findings">
          {row.findings.map((finding) => (
            <article key={finding.id} className="t3-review-finding">
              <div className="t3-review-finding-title">{finding.title}</div>
              <div className="t3-review-finding-meta">
                {[finding.severity, finding.file, finding.line ? `:${finding.line}` : ""].filter(Boolean).join(" ")}
              </div>
              {finding.body ? <p>{finding.body}</p> : null}
            </article>
          ))}
        </div>
      ) : null}
      {Array.isArray(row.residualRisks) && row.residualRisks.length > 0 ? (
        <ul className="t3-review-risks">
          {row.residualRisks.map((risk) => <li key={risk}>{risk}</li>)}
        </ul>
      ) : null}
    </ExpandableShell>
  );
}
```

- [ ] **Step 4: Add a recursive row switch**

Add this function before the default export:

```jsx
function TimelineRowSwitch({
  row,
  onOpenDiff,
  markdownComponents,
  rowUiState,
  onToggleRow,
  rowKeyFor,
}) {
  if (row.kind === "message") {
    return <MessageRow row={row} markdownComponents={markdownComponents} />;
  }
  if (row.kind === "work") {
    const key = rowKeyFor(row);
    return (
      <WorkRow
        row={row}
        rowKey={key}
        expanded={Boolean(rowUiState?.expanded?.[key])}
        onToggle={onToggleRow}
      />
    );
  }
  if (row.kind === "turn_fold") {
    return (
      <TurnFoldRow
        row={row}
        rowUiState={rowUiState}
        onToggleRow={onToggleRow}
        rowKeyFor={rowKeyFor}
        onOpenDiff={onOpenDiff}
        markdownComponents={markdownComponents}
      />
    );
  }
  if (row.kind === "interaction") return <InteractionRow row={row} />;
  if (row.kind === "diff_summary") return <ChangedFilesCard row={row} onOpenDiff={onOpenDiff} />;
  if (row.kind === "reasoning") {
    return <ReasoningRow row={row} rowUiState={rowUiState} onToggleRow={onToggleRow} rowKeyFor={rowKeyFor} />;
  }
  if (row.kind === "thinking") return <ThinkingRow row={row} />;
  if (row.kind === "compact") return <CompactRow row={row} />;
  if (row.kind === "command_result") {
    return (
      <CommandResultRow
        row={row}
        markdownComponents={markdownComponents}
        rowUiState={rowUiState}
        onToggleRow={onToggleRow}
        rowKeyFor={rowKeyFor}
      />
    );
  }
  if (row.kind === "review_result") {
    return (
      <ReviewResultRow
        row={row}
        markdownComponents={markdownComponents}
        rowUiState={rowUiState}
        onToggleRow={onToggleRow}
        rowKeyFor={rowKeyFor}
      />
    );
  }
  if (row.kind === "working") {
    return (
      <div className="t3-working-row" data-testid="timeline-working-row" data-row-kind="working">
        {row.label || "Working"}
      </div>
    );
  }
  return <SystemNoticeRow row={row} />;
}
```

- [ ] **Step 5: Make turn folds use the row switch**

Modify `TurnFoldRow(...)` signature:

```jsx
function TurnFoldRow({ row, rowUiState, onToggleRow, rowKeyFor, onOpenDiff, markdownComponents }) {
```

Replace the body mapping inside `.t3-turn-fold-body` with:

```jsx
          {entries.map((entry) => (
            <TimelineRowSwitch
              key={entry.id}
              row={entry}
              onOpenDiff={onOpenDiff}
              markdownComponents={markdownComponents}
              rowUiState={rowUiState}
              onToggleRow={onToggleRow}
              rowKeyFor={rowKeyFor}
            />
          ))}
```

- [ ] **Step 6: Replace the default export body with the row switch**

Replace the `(rows || []).map(...)` body in the default export with:

```jsx
      {(rows || []).map((row) => (
        <TimelineRowSwitch
          key={row.id}
          row={row}
          onOpenDiff={onOpenDiff}
          markdownComponents={markdownComponents}
          rowUiState={rowUiState}
          onToggleRow={onToggleRow}
          rowKeyFor={rowKeyFor}
        />
      ))}
```

- [ ] **Step 7: Run renderer tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: renderer source-contract assertions pass.

- [ ] **Step 8: Commit renderer changes**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: render rich t3 timeline rows"
```

## Task 6: Enrich The Visual Timeline Fixture

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing fixture source assertions**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, after the existing `appSource.includes("loadTimelineFixture")` assertions, add:

```js
  assert.equal(appSource.includes('kind: "reasoning"'), true);
  assert.equal(appSource.includes('kind: "compact"'), true);
  assert.equal(appSource.includes('commandName: "review"'), true);
  assert.equal(appSource.includes("thinkingActive: true"), true);
  assert.equal(appSource.includes("activeTurnId: state.activeTurnId"), true);
  assert.equal(appSource.includes("thinkingActive: state.thinkingActive"), true);
```

After the existing `storeSource.includes("visual_timeline_fixture_loaded")` assertion, add:

```js
  assert.equal(storeSource.includes("action.activeTurnId"), true);
  assert.equal(storeSource.includes("action.thinkingActive"), true);
  assert.equal(storeSource.includes("action.streamingReasoningId"), true);
```

- [ ] **Step 2: Run failing fixture source tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL until fixture data and store fields are added.

- [ ] **Step 3: Update `visual_timeline_fixture_loaded` reducer fields**

In `src/embedagent/frontend/gui/webapp/src/store.js`, inside the `visual_timeline_fixture_loaded` returned state, replace:

```js
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
```

with:

```js
        streamingAssistantId: action.streamingAssistantId || "",
        streamingReasoningId: action.streamingReasoningId || "",
        thinkingActive: Boolean(action.thinkingActive),
```

Then replace:

```js
        historyIntegrity: null,
```

with:

```js
        activeTurnId: action.activeTurnId || "",
        activeStepId: action.activeStepId || "",
        activeStepIndex: action.activeStepIndex || 0,
        historyIntegrity: null,
```

- [ ] **Step 4: Enrich `loadTimelineFixture()` in `App.jsx`**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`, update the `dispatch({ type: "visual_timeline_fixture_loaded", ... })` payload in `loadTimelineFixture()` so the fixture timeline includes these items in order:

```js
        timeline: [
          {
            id: "visual-user-1",
            kind: "user",
            content: "Review parser recovery and show the work.",
            turnId: "visual-turn-1",
          },
          {
            id: "visual-compact-1",
            kind: "compact",
            content: "Earlier setup turns were compacted.",
            summarizedTurns: 5,
            recentTurns: 2,
            approxTokensAfter: 3600,
            turnId: "visual-turn-1",
          },
          {
            id: "visual-reasoning-1",
            kind: "reasoning",
            content: "Inspect the parser recovery path, then verify the changed diagnostic flow.",
            streaming: false,
            turnId: "visual-turn-1",
            stepId: "visual-step-1",
            stepIndex: 1,
          },
          {
            id: "visual-tool-read",
            kind: "tool",
            toolName: "read_file",
            label: "Read File",
            status: "success",
            arguments: { path: "src/parser.c" },
            data: { path: "src/parser.c", content: "int parse(void);" },
            turnId: "visual-turn-1",
            stepId: "visual-step-1",
            stepIndex: 1,
          },
          {
            id: "visual-tool-edit",
            kind: "tool",
            toolName: "edit_file",
            label: "Edit File",
            status: "success",
            arguments: { path: "src/parser.c" },
            data: {
              path: "src/parser.c",
              diff_preview: [
                "--- a/src/parser.c",
                "+++ b/src/parser.c",
                "@@ -1 +1 @@",
                "-return 0;",
                "+return recover();",
                "",
              ].join("\\n"),
            },
            turnId: "visual-turn-1",
            stepId: "visual-step-1",
            stepIndex: 1,
          },
          {
            id: "visual-review-result",
            kind: "command_result",
            commandName: "review",
            success: false,
            content: "Review found one follow-up item.",
            data: {
              review: {
                findings: [
                  {
                    id: "visual-finding-1",
                    severity: "medium",
                    priority: 2,
                    title: "Add EOF recovery fixture",
                    body: "The parser recovery path is not covered by a fixture yet.",
                    file: "tests/parser_recovery_test.c",
                    line: 18,
                  },
                ],
                residual_risks: ["Visual fixture only checks rendering, not parser behavior."],
              },
            },
            turnId: "visual-turn-1",
          },
          {
            id: "visual-assistant-1",
            kind: "assistant",
            content: "Parser recovery was updated and review found one fixture follow-up.",
            turnId: "visual-turn-1",
            stepId: "visual-step-1",
            stepIndex: 1,
          },
          {
            id: "visual-user-2",
            kind: "user",
            content: "Think through the next verification step.",
            turnId: "visual-turn-2",
          },
        ],
        snapshot: {
          session_id: "visual-debug-session",
          status: "running",
          current_mode: state.requestedMode || DEFAULT_MODE,
          pending_interaction_valid: false,
        },
        activeTurnId: "visual-turn-2",
        activeStepId: "visual-step-2",
        activeStepIndex: 1,
        thinkingActive: true,
```

Keep any existing `sessionId` and `inspectorTab` fields in the same action payload.

- [ ] **Step 5: Run fixture source tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: fixture source assertions pass.

- [ ] **Step 6: Commit fixture changes**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test: enrich t3 timeline visual fixture"
```

## Task 7: Add Rich Timeline CSS And Responsive Guardrails

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`

- [ ] **Step 1: Add failing CSS source assertions**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, after the existing `stylesSource` timeline assertions, add:

```js
  assert.equal(stylesSource.includes(".t3-reasoning-row"), true);
  assert.equal(stylesSource.includes(".t3-thinking-row"), true);
  assert.equal(stylesSource.includes(".t3-compact-row"), true);
  assert.equal(stylesSource.includes(".t3-command-result-row"), true);
  assert.equal(stylesSource.includes(".t3-review-result-row"), true);
  assert.equal(stylesSource.includes("overflow-wrap: anywhere"), true);
  assert.equal(stylesSource.includes("grid-template-columns: minmax(0, 1fr)"), true);
  assert.equal(stylesSource.includes("@media (max-width: 560px)"), true);
```

- [ ] **Step 2: Run failing CSS source tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL until the CSS classes and guardrails exist.

- [ ] **Step 3: Add rich row CSS**

Append this block near the existing `.t3-work-row` and `.t3-turn-fold-row` styles in `src/embedagent/frontend/gui/webapp/src/styles.css`:

```css
.t3-reasoning-row,
.t3-command-result-row,
.t3-review-result-row {
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: var(--surface-muted);
  max-width: 100%;
  overflow: hidden;
}

.t3-rich-row-summary {
  width: 100%;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  border: 0;
  background: transparent;
  color: var(--text-primary);
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
}

.t3-rich-row-label,
.t3-rich-row-meta {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.t3-rich-row-meta {
  color: var(--text-muted);
  font-size: 12px;
}

.t3-rich-row-body {
  border-top: 1px solid var(--border-subtle);
  padding: 10px;
  overflow-wrap: anywhere;
}

.t3-reasoning-row pre {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
}

.t3-thinking-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 13px;
  padding: 6px 2px;
}

.t3-thinking-pulse {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--accent);
  animation: t3-thinking-pulse 1.15s ease-in-out infinite;
}

@keyframes t3-thinking-pulse {
  0%, 100% { opacity: 0.35; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1); }
}

.t3-compact-row {
  display: flex;
  min-width: 0;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.t3-command-result-row.error,
.t3-review-result-row.error {
  border-color: var(--danger-border);
}

.t3-review-findings,
.t3-review-risks {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.t3-review-finding {
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px;
  background: var(--surface);
}

.t3-review-finding-title {
  font-weight: 600;
  overflow-wrap: anywhere;
}

.t3-review-finding-meta {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  margin-top: 2px;
}
```

- [ ] **Step 4: Add responsive shell guardrails**

Append this block near the existing responsive media queries in `src/embedagent/frontend/gui/webapp/src/styles.css`:

```css
.app-main,
.workbench-main,
.workbench-center,
.timeline,
.timeline-shell,
.composer-shell,
.right-panel,
.bottom-drawer {
  min-width: 0;
}

.timeline-shell {
  width: min(100%, 820px);
  max-width: 820px;
}

.t3-timeline .timeline-shell,
.t3-message-row,
.t3-work-row,
.t3-turn-fold-row,
.changed-files-card,
.system-card {
  max-width: 100%;
  overflow-wrap: anywhere;
}

.right-panel-tabs {
  min-width: 0;
  overflow-x: auto;
}

.workbench-header,
.header-status-group,
.header-action-group {
  min-width: 0;
}

@media (max-width: 860px) {
  .workspace-header-label,
  .header-status-group .meta-text {
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .header-action-group {
    gap: 4px;
  }
}

@media (max-width: 560px) {
  .workspace-header-label,
  .status-label {
    display: none;
  }

  .composer-actions {
    flex-wrap: wrap;
  }

  .t3-rich-row-summary {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

If an identical selector already exists, merge the declarations into the existing block instead of duplicating contradictory rules.

- [ ] **Step 5: Run CSS source tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: CSS source assertions pass.

- [ ] **Step 6: Commit CSS changes**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "style: polish rich t3 timeline responsiveness"
```

## Task 8: Strengthen Visual Debug Harness Checks

**Files:**
- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`

- [ ] **Step 1: Add failing visual harness source assertions**

In `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`, add these assertions to `runVisualDebugRunnerTests()` after the existing `loadTimelineFixture` assertion:

```js
  assert.equal(runnerSource.includes("timeline-reasoning-row"), true);
  assert.equal(runnerSource.includes("timeline-thinking-row"), true);
  assert.equal(runnerSource.includes("timeline-review-result-row"), true);
```

- [ ] **Step 2: Run failing visual harness tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the visual runner does not inspect rich rows.

- [ ] **Step 3: Update `runTimelineScenario(...)` checks**

In `scripts/gui-visual-debug.mjs`, inside `runTimelineScenario(page)`, add waits after the existing changed-files wait:

```js
  await page.waitForSelector('[data-testid="timeline-reasoning-row"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="timeline-review-result-row"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="timeline-thinking-row"]', { timeout: 10000 });
```

Update the returned object:

```js
  return {
    rowCount,
    hasChangedFiles: await page.locator('[data-testid="changed-files-card"]').isVisible(),
    hasReasoning: await page.locator('[data-testid="timeline-reasoning-row"]').first().isVisible(),
    hasReview: await page.locator('[data-testid="timeline-review-result-row"]').first().isVisible(),
    hasThinking: await page.locator('[data-testid="timeline-thinking-row"]').first().isVisible(),
    hasExpandedDetail: await page.locator('[data-testid="timeline-work-detail"]').first().isVisible(),
    rightTabsDoNotOverlap: noOverlap,
  };
```

- [ ] **Step 4: Run visual harness source tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: visual harness source assertions pass.

- [ ] **Step 5: Commit visual harness changes**

Run:

```bash
git add scripts/gui-visual-debug.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs
git commit -m "test: assert rich timeline visual rows"
```

## Task 9: Update Durable GUI Documentation

**Files:**
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Update frontend GUI module docs**

In `docs/modules/frontend-gui.md`, add a short subsection under the GUI app-shell/timeline area:

```markdown
### T3 Timeline Rich Projection

- The React webapp owns a frontend-local T3 timeline row projection in `webapp/src/session-runtime/t3-timeline.js`.
- Thinking, reasoning, compact boundaries, command results, review results, tool/work rows, diff summaries, interactions, and system notices are display rows derived from existing session bootstrap/timeline/WebSocket state.
- `TimelineRows.jsx` renders these rows; `timeline-ui-state.js` owns transient expansion state only.
- This projection is not session-history truth, does not write `transcript.jsonl`, does not read `timeline.jsonl` as history, and does not change Agent Core, workflow packages, permission policy, or runtime reducers.
```

- [ ] **Step 2: Update development tracker**

At the top of section `## 2. 当前阶段` in `docs/development-tracker.md`, insert:

```markdown
### 2026-06-18 - T3 Timeline Rich Projection

- GUI T3-style timeline now projects and renders thinking, reasoning, compact, command-result, and review-result rows in the active row renderer instead of relying on the legacy grouped fallback.
- `projectSessionRuntime(...)` receives GUI-local `activeTurnId` / `thinkingActive` state so live `thinking_state` and `reasoning_delta` events are visible without new backend protocol.
- Timeline expansion defaults and visual fixtures now cover rich row kinds, and responsive CSS guardrails reduce clipping under narrow or zoomed layouts.
- This slice remains GUI app-shell display/read-model work only: no transcript writes, workflow-state ownership, permission/runtime reducer changes, provider configuration, extension loading, source-control checkpoints, or Agent Core policy changes.
```

Also update the header date line:

```markdown
> 更新日期：2026-06-18（T3 timeline rich projection）
```

- [ ] **Step 3: Update design change log**

At the top of `## 3. 当前变更记录` in `docs/design-change-log.md`, insert:

```markdown
### DC-171

- 日期：2026-06-18
- 变更主题：GUI T3 Code-style rich timeline projection
- 变更摘要：
  - React webapp 的 T3 timeline row projection 现在覆盖 thinking、reasoning、compact、command result、review result、tool/work、diff summary、interaction 和 system notice。
  - live thinking/reasoning display 由 GUI reducer state 传入 `projectSessionRuntime(...)`，不新增 backend/Core 协议。
  - `TimelineRows.jsx` 成为 active T3 row renderer 的富格式入口，legacy grouped renderer 不再是 reasoning/compact/command/review 的唯一显示路径。
  - 该变更只影响 GUI-local projection、presentation、visual debug harness 和文档，不写 transcript、workflow state、permission/runtime reducers、telemetry、provider config、extension loading、source-control checkpoints 或 Agent Core policy。
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/store.js`
  - `src/embedagent/frontend/gui/webapp/src/styles.css`
  - `scripts/gui-visual-debug.mjs`
  - `src/embedagent/frontend/gui/webapp/test/`
- 关联文档：
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-timeline-rich-projection-design.md`
  - `docs/archive/t3code-pi-workbench/2026-06-18-t3-timeline-rich-projection.md`
- 是否需要 ADR：否；属于已批准的 GUI/T3 Code parity program 内部 timeline rendering slice，不改变 Agent Core public architecture。
- 后续动作：
  - 继续拆分 `App.jsx` 的 session runtime bridge、visual debug hooks、workbench shell composition，让 GUI 架构继续靠近 T3 Code 的 frontend-owned domain model，同时保持 Agent Core 小核心。
```

- [ ] **Step 4: Run docs diff check**

Run:

```bash
git diff -- docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md
```

Expected: diff only contains the three documentation updates above.

- [ ] **Step 5: Commit docs changes**

Run:

```bash
git add docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record rich t3 timeline projection"
```

## Task 10: Build, Visual QA, And Final Verification

**Files:**
- Verify generated/static GUI assets as required by the existing webapp build.

- [ ] **Step 1: Run webapp unit/source tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 2: Build the webapp**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: PASS and updated static GUI assets if the build output is tracked.

- [ ] **Step 3: Run focused Python GUI backend/app-shell tests**

Run from repository root:

```bash
uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q
```

Expected: PASS.

- [ ] **Step 4: Run timeline/responsive visual QA**

Run from repository root:

```powershell
node scripts/gui-visual-debug.mjs --scenario timeline,responsive --no-build --output "$env:TEMP\embedagent-t3-rich-timeline"
```

Expected:

- PASS with screenshots in `$env:TEMP\embedagent-t3-rich-timeline`.
- Timeline screenshot contains reasoning, thinking, review result, changed-files card, and expanded work detail.
- Responsive screenshots do not show header, right-panel tabs, timeline rows, or composer controls overlapping.

- [ ] **Step 5: Inspect final git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only intended source, test, docs, and build-output files are changed.

- [ ] **Step 6: Final commit if build output changed**

If `npm run build` changed tracked static assets, include them in a final commit:

```bash
git add src/embedagent/frontend/gui/webapp/dist src/embedagent/frontend/gui/static
git commit -m "build: refresh gui static assets"
```

If no build output changed, do not create an empty commit.

## Completion Criteria

- Active T3 timeline rows show reasoning text as a collapsible rich row.
- Active thinking is visible while the session is running before reasoning text arrives.
- Compact, command result, and review result items no longer fall back to plain system notices.
- Settled successful turns can fold work/reasoning entries; running, failed, interrupted, or streaming work remains visible.
- No Agent Core, permission, workflow, transcript, reducer, or backend protocol changes were needed.
- Webapp tests, build, focused Python GUI tests, and visual timeline/responsive QA pass.
- Durable docs explicitly record that the feature is GUI-local display/read-model work.
