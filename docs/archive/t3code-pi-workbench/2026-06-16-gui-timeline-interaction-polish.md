# GUI Timeline Interaction Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the T3code-style GUI timeline interaction stable, controlled, and visually debuggable through timeline and interaction fixtures.

**Architecture:** Add a frontend-local timeline UI state model for row keys, expansion defaults, toggle persistence, and scroll helper math. Convert T3 timeline rows to controlled expansion props without changing Agent Core. Extend the dev-only visual debug hook and Playwright harness with deterministic `timeline` and `interaction` scenarios.

**Tech Stack:** React 18, plain CSS, Node ESM helper tests, existing Playwright visual harness, Python 3.8 backend GUI focused tests.

---

## File Structure

- Create `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
  - Pure frontend-local model for row keys, expansion defaults, toggles, bottom pinning, and anchor restoration math.
- Create `src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs`
  - Data-only tests for the timeline UI model.
- Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Import and run timeline UI tests.
  - Add source contract checks for controlled `WorkRow`, fixture hook names, and visual scenarios.
- Modify `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - Own local timeline UI state.
  - Capture simple scroll anchors before row toggles.
  - Pass expansion state and toggle callbacks into `TimelineRows`.
- Modify `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - Accept `rowUiState`, `onToggleRow`, and `rowKeyFor`.
  - Pass controlled expansion props into `WorkRow` and turn fold rows.
- Modify `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
  - Remove expansion as hidden local source of truth.
  - Accept `expanded`, `onToggle`, and `rowKey`.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Extend `window.__EMBEDAGENT_VISUAL_DEBUG__` under `?visual_debug=1` with timeline and interaction fixtures.
  - Add frontend-only reducer actions if needed.
- Modify `src/embedagent/frontend/gui/webapp/src/store.js`
  - Add `visual_timeline_fixture_loaded` and `visual_interaction_fixture_loaded` frontend-only actions.
- Modify `scripts/gui-visual-debug.mjs`
  - Add `timeline` and `interaction` to `SCENARIOS`.
  - Add fixture data and scenario runners.
- Modify `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`
  - Cover new visual scenario parsing and fixture hook source contracts.
- Modify `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Add any small state/fixture-visible polish needed for controlled rows and composer interaction screenshots.
- Modify docs:
  - `docs/modules/frontend-gui.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`

---

### Task 1: Add Timeline UI State Model

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
- Create: `src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing timeline UI state tests**

Create `src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs`:

```js
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
```

- [ ] **Step 2: Register the failing test**

Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`:

```js
import { runTimelineUiStateTests } from "./timeline-ui-state.test.mjs";
```

Then near the other frontend helper tests:

```js
  runT3TimelineTests();
  runTimelineUiStateTests();
  runVisualLanguageCssTests();
```

- [ ] **Step 3: Run the test and verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with an import error for `../src/session-runtime/timeline-ui-state.js`.

- [ ] **Step 4: Implement the pure model**

Create `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`:

```js
function stringValue(value, fallback = "") {
  if (value == null) return fallback;
  return String(value);
}

function booleanValue(value, fallback = false) {
  return typeof value === "boolean" ? value : fallback;
}

export function rowUiKey(row) {
  const kind = stringValue(row?.kind, "row");
  if (kind === "work") {
    return [
      "work",
      stringValue(row?.turnId || row?.turn_id),
      stringValue(row?.stepId || row?.step_id),
      stringValue(row?.id || row?.toolName || row?.tool_name),
    ].join(":");
  }
  if (kind === "turn_fold") {
    return [
      "turn_fold",
      stringValue(row?.turnId || row?.turn_id),
      stringValue(row?.id),
    ].join(":");
  }
  return `${kind}:${stringValue(row?.id || row?.turnId || row?.turn_id || "row")}`;
}

function defaultExpanded(row) {
  if (!row) return false;
  if (row.kind === "turn_fold") return booleanValue(row.defaultOpen, false);
  if (row.kind !== "work") return false;
  if (row.tone === "interrupted" || row.tone === "discarded") return true;
  if (row.status === "error" || row.tone === "error") return true;
  if (row.status === "running" || row.tone === "running") return true;
  return false;
}

function collectRows(rows) {
  const collected = [];
  for (const row of rows || []) {
    collected.push(row);
    if (row?.kind === "turn_fold" && Array.isArray(row.entries)) {
      for (const entry of row.entries) collected.push(entry);
    }
  }
  return collected;
}

export function createTimelineUiState(rows = [], previousState = null) {
  const previousExpanded = previousState?.expanded || {};
  const previousTouched = previousState?.touched || {};
  const expanded = {};
  const touched = {};
  for (const row of collectRows(rows)) {
    const key = rowUiKey(row);
    if (!key) continue;
    if (previousTouched[key]) {
      expanded[key] = Boolean(previousExpanded[key]);
      touched[key] = true;
    } else {
      expanded[key] = defaultExpanded(row);
    }
  }
  return { expanded, touched };
}

export function toggleTimelineRow(state, rowKey) {
  const expanded = { ...(state?.expanded || {}) };
  const touched = { ...(state?.touched || {}) };
  expanded[rowKey] = !Boolean(expanded[rowKey]);
  touched[rowKey] = true;
  return { expanded, touched };
}

export function shouldPinToBottom({ scrollTop = 0, clientHeight = 0, scrollHeight = 0, threshold = 16 } = {}) {
  return scrollHeight - (scrollTop + clientHeight) <= threshold;
}

export function restoreAnchorScroll({ before, after, scrollTop = 0 } = {}) {
  if (!before || !after) return scrollTop;
  return scrollTop + (after.top - before.top);
}
```

- [ ] **Step 5: Run the test and verify it passes**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS, ending with `frontend helper checks passed`.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js src/embedagent/frontend/gui/webapp/test/timeline-ui-state.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test(gui): add timeline ui state model"
```

---

### Task 2: Make T3 Work Rows And Turn Folds Controlled

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing source contract checks**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, after the existing `Timeline.jsx` source checks, add:

```js
  const timelineRowsSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "TimelineRows.jsx"),
    "utf8",
  );
  assert.equal(timelineRowsSource.includes("rowUiState"), true);
  assert.equal(timelineRowsSource.includes("onToggleRow"), true);
  assert.equal(timelineRowsSource.includes("rowKeyFor"), true);

  const workRowSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "WorkRow.jsx"),
    "utf8",
  );
  assert.equal(workRowSource.includes("expanded"), true);
  assert.equal(workRowSource.includes("onToggle"), true);
  assert.equal(workRowSource.includes("useState(row.status === \"error\")"), false);
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `TimelineRows.jsx` and `WorkRow.jsx` do not yet use controlled props.

- [ ] **Step 3: Modify `WorkRow.jsx`**

Replace the component signature and remove local expansion state:

```jsx
export default function WorkRow({ row, expanded = false, onToggle = null, rowKey = "" }) {
  const hasDetail = Boolean(
    row.detail || row.commandPreview || (Array.isArray(row.changedFiles) && row.changedFiles.length > 0),
  );
  const icon = TOOL_ICONS[row.toolName] || "*";

  function handleToggle() {
    if (hasDetail && onToggle) onToggle(rowKey);
  }

  return (
    <div className={`t3-work-row ${row.tone || "neutral"}`} data-testid="timeline-work-row" data-row-kind="work" data-row-key={rowKey}>
      <button
        className="t3-work-summary"
        type="button"
        onClick={handleToggle}
        aria-expanded={expanded}
        title={row.toolName || row.label}
      >
        <span className="t3-work-icon" aria-hidden="true">{icon}</span>
        <span className="t3-work-label">{row.label || row.toolName || "Work"}</span>
        {row.commandPreview ? <code className="t3-work-preview">{row.commandPreview}</code> : <span />}
        {Array.isArray(row.changedFiles) && row.changedFiles.length > 0 ? (
          <span className="t3-work-changes">+{row.additions || 0} -{row.deletions || 0}</span>
        ) : null}
        <span className={`t3-work-status ${row.status || "running"}`}>{statusLabel(row)}</span>
      </button>
      {expanded && hasDetail ? (
        <div className="t3-work-detail" data-testid="timeline-work-detail">
          {row.detail ? <pre>{row.detail}</pre> : null}
          {Array.isArray(row.changedFiles) && row.changedFiles.length > 0 ? (
            <div className="t3-work-file-list">
              {row.changedFiles.map((file) => (
                <span key={file.path} className="t3-work-file">{file.path}</span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Modify `TimelineRows.jsx`**

Import `rowUiKey`:

```js
import { rowUiKey as defaultRowUiKey } from "../../session-runtime/timeline-ui-state.js";
```

Change `TurnFoldRow` signature and body:

```jsx
function TurnFoldRow({ row, rowUiState, onToggleRow, rowKeyFor }) {
  const entries = Array.isArray(row.entries) ? row.entries : [];
  const key = rowKeyFor(row);
  const open = Boolean(rowUiState?.expanded?.[key]);
  return (
    <section className="t3-turn-fold-row" data-testid="timeline-turn-fold" data-row-kind="turn_fold" data-row-key={key}>
      <button
        type="button"
        className="t3-turn-fold-summary"
        aria-expanded={open}
        onClick={() => onToggleRow && onToggleRow(key)}
      >
        <span>{row.label || "Worked for this turn"}</span>
        <span>{row.workCount || entries.length} steps</span>
      </button>
      {open ? (
        <div className="t3-turn-fold-body">
          {entries.map((entry) => {
            const entryKey = rowKeyFor(entry);
            return entry.kind === "interaction"
              ? <InteractionRow key={entry.id} row={entry} />
              : (
                <WorkRow
                  key={entry.id}
                  row={entry}
                  rowKey={entryKey}
                  expanded={Boolean(rowUiState?.expanded?.[entryKey])}
                  onToggle={onToggleRow}
                />
              );
          })}
        </div>
      ) : null}
    </section>
  );
}
```

Change default export signature:

```jsx
export default function TimelineRows({
  rows,
  onOpenDiff,
  markdownComponents,
  rowUiState = null,
  onToggleRow = null,
  rowKeyFor = defaultRowUiKey,
}) {
```

Change work and fold render branches:

```jsx
        if (row.kind === "work") {
          const key = rowKeyFor(row);
          return (
            <WorkRow
              key={row.id}
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
              key={row.id}
              row={row}
              rowUiState={rowUiState}
              onToggleRow={onToggleRow}
              rowKeyFor={rowKeyFor}
            />
          );
        }
```

- [ ] **Step 5: Modify `Timeline.jsx` imports and local state**

Add imports:

```js
import {
  createTimelineUiState,
  restoreAnchorScroll,
  rowUiKey,
  shouldPinToBottom,
  toggleTimelineRow,
} from "../session-runtime/timeline-ui-state.js";
```

Inside `Timeline` component, before `return`, add:

```jsx
  const timelineNodeRef = React.useRef(null);
  const pendingAnchorRef = React.useRef(null);
  const [timelineUiState, setTimelineUiState] = React.useState(() => createTimelineUiState(rows || []));

  React.useEffect(() => {
    setTimelineUiState((previous) => createTimelineUiState(rows || [], previous));
  }, [rows]);

  React.useLayoutEffect(() => {
    const pending = pendingAnchorRef.current;
    const node = timelineNodeRef.current;
    if (!pending || !node) return;
    pendingAnchorRef.current = null;
    window.requestAnimationFrame(() => {
      const target = node.querySelector(`[data-row-key="${pending.rowKey}"]`);
      if (!target) return;
      const after = target.getBoundingClientRect();
      node.scrollTop = restoreAnchorScroll({
        before: pending.rect,
        after,
        scrollTop: pending.scrollTop,
      });
    });
  });

  function handleToggleTimelineRow(rowKey) {
    const node = timelineNodeRef.current;
    if (node && !shouldPinToBottom(node)) {
      const target = node.querySelector(`[data-row-key="${rowKey}"]`);
      if (target) {
        pendingAnchorRef.current = {
          rowKey,
          rect: target.getBoundingClientRect(),
          scrollTop: node.scrollTop,
        };
      }
    }
    setTimelineUiState((previous) => toggleTimelineRow(previous, rowKey));
  }
```

If `Timeline` already uses the forwarded `ref` on the scroll container, wire both refs with:

```jsx
  function setTimelineNode(node) {
    timelineNodeRef.current = node;
    if (typeof ref === "function") ref(node);
    else if (ref) ref.current = node;
  }
```

Use `ref={setTimelineNode}` on the timeline scroll container.

Pass controlled props into `TimelineRows`:

```jsx
              <TimelineRows
                rows={rows}
                onOpenDiff={onOpenDiff}
                markdownComponents={markdownComponents}
                rowUiState={timelineUiState}
                onToggleRow={handleToggleTimelineRow}
                rowKeyFor={rowUiKey}
              />
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both PASS.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static/assets/app.css src/embedagent/frontend/gui/static/assets/app.js
git commit -m "feat(gui): control timeline row expansion"
```

---

### Task 3: Add Timeline And Interaction Fixture Hooks

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing source contract checks**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, near existing App source assertions, add:

```js
  assert.equal(appSource.includes("loadTimelineFixture"), true);
  assert.equal(appSource.includes("loadInteractionFixture"), true);
  assert.equal(appSource.includes("visual_timeline_fixture_loaded"), true);
  assert.equal(appSource.includes("visual_interaction_fixture_loaded"), true);
```

Also add store source checks:

```js
  const storeSource = fs.readFileSync(
    webappSourcePath("store.js"),
    "utf8",
  );
  assert.equal(storeSource.includes("visual_timeline_fixture_loaded"), true);
  assert.equal(storeSource.includes("visual_interaction_fixture_loaded"), true);
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the fixture hook names and reducer actions do not exist yet.

- [ ] **Step 3: Add frontend-only reducer actions**

In `src/embedagent/frontend/gui/webapp/src/store.js`, add cases near `append_timeline_item`:

```js
    case "visual_timeline_fixture_loaded":
      return {
        ...state,
        currentSessionId: action.sessionId || "visual-debug-session",
        snapshot: action.snapshot || state.snapshot,
        timeline: Array.isArray(action.timeline) ? action.timeline : [],
        streamingAssistantId: "",
        streamingReasoningId: "",
        thinkingActive: false,
        permission: null,
        userInput: null,
        interactionNotice: null,
        inspectorTab: action.inspectorTab || state.inspectorTab,
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_surface_activated",
          placement: "right",
          kind: action.inspectorTab || state.inspectorTab,
        }),
      };
    case "visual_interaction_fixture_loaded":
      return {
        ...state,
        currentSessionId: action.sessionId || "visual-debug-session",
        permission: action.permission || null,
        userInput: action.userInput || null,
        interactionNotice: null,
        inspectorTab: "interaction",
        inspectorOpen: true,
        workbench: reduceWorkbenchState(state.workbench, {
          type: "workbench_surface_activated",
          placement: "right",
          kind: "interaction",
        }),
      };
```

- [ ] **Step 4: Add fixture data and hook functions in `App.jsx`**

Near the visual debug `useEffect`, add helper functions inside `App`:

```jsx
  function loadTimelineFixture() {
    dispatch({
      type: "visual_timeline_fixture_loaded",
      sessionId: "visual-debug-timeline",
      inspectorTab: "tasks",
      timeline: [
        {
          id: "visual-user-1",
          kind: "user",
          content: "Refine the parser and show the changed files.",
          turnId: "visual-turn-1",
        },
        {
          id: "visual-read-1",
          kind: "tool",
          toolName: "read_file",
          label: "Read File",
          status: "success",
          arguments: { path: "src/parser.c" },
          data: { summary: "Read parser entry point." },
          turnId: "visual-turn-1",
          stepId: "visual-step-1",
          stepIndex: 1,
        },
        {
          id: "visual-edit-1",
          kind: "tool",
          toolName: "edit_file",
          label: "Edit File",
          status: "success",
          arguments: { path: "src/parser.c" },
          data: {
            path: "src/parser.c",
            diff_preview: "--- a/src/parser.c\n+++ b/src/parser.c\n@@ -1 +1,2 @@\n-int parse(void) { return 0; }\n+int parse(void) { return 1; }\n+int parse_extra(void) { return 2; }\n",
          },
          turnId: "visual-turn-1",
          stepId: "visual-step-1",
          stepIndex: 1,
        },
        {
          id: "visual-run-1",
          kind: "tool",
          toolName: "run_recipe",
          label: "Run Recipe",
          status: "error",
          arguments: { recipe_id: "test" },
          error: "test_parser_handles_empty_input failed",
          turnId: "visual-turn-1",
          stepId: "visual-step-2",
          stepIndex: 2,
        },
        {
          id: "visual-assistant-1",
          kind: "assistant",
          content: "Parser change is staged, but one focused test still fails.",
          turnId: "visual-turn-1",
          stepId: "visual-step-2",
          stepIndex: 2,
        },
      ],
    });
  }

  function loadInteractionFixture(kind = "permission") {
    const permission = kind === "permission"
      ? {
          interaction_id: "visual-permission-1",
          tool_name: "edit_file",
          reason: "Allow editing src/parser.c",
          arguments: { path: "src/parser.c" },
          permission_category: "workspace_write",
        }
      : null;
    const userInput = kind === "user_input"
      ? {
          interaction_id: "visual-input-1",
          kind: "user_input",
          question: "Which parser behavior should be preserved?",
          choices: ["Keep strict parsing", "Accept empty input"],
        }
      : null;
    dispatch({
      type: "visual_interaction_fixture_loaded",
      sessionId: "visual-debug-interaction",
      permission,
      userInput,
    });
  }
```

Extend the existing `window.__EMBEDAGENT_VISUAL_DEBUG__` object:

```js
      loadTimelineFixture,
      loadInteractionFixture,
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static/assets/app.css src/embedagent/frontend/gui/static/assets/app.js
git commit -m "feat(gui): add timeline visual fixtures"
```

---

### Task 4: Extend GUI Visual Debug Harness

**Files:**
- Modify: `scripts/gui-visual-debug.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`

- [ ] **Step 1: Add failing visual runner tests**

In `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`, add:

```js
  assert.deepEqual(runner.parseScenarioList("timeline,interaction"), ["timeline", "interaction"]);
  assert.deepEqual(runner.parseScenarioList("all"), ["app", "load", "chat", "diff", "responsive", "timeline", "interaction"]);
  assert.equal(runnerSource.includes("runTimelineScenario"), true);
  assert.equal(runnerSource.includes("runInteractionScenario"), true);
  assert.equal(runnerSource.includes("loadTimelineFixture"), true);
  assert.equal(runnerSource.includes("loadInteractionFixture"), true);
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `timeline` and `interaction` are not known scenarios.

- [ ] **Step 3: Extend `SCENARIOS`**

In `scripts/gui-visual-debug.mjs`, change:

```js
export const SCENARIOS = ["load", "chat", "diff", "responsive", "app"];
```

to:

```js
export const SCENARIOS = ["load", "chat", "diff", "responsive", "app", "timeline", "interaction"];
```

- [ ] **Step 4: Add scenario runners**

Add after `runDiffScenario`:

```js
async function runTimelineScenario(page) {
  await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadTimelineFixture();
  });
  await page.waitForSelector('[data-testid="timeline-user-message"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="changed-files-card"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="timeline-work-row"]', { timeout: 10000 });
  const firstCollapsed = page.locator('[data-testid="timeline-work-row"] button[aria-expanded="false"]').first();
  if (await firstCollapsed.count()) {
    await firstCollapsed.click();
  }
  await page.waitForSelector('[data-testid="timeline-work-detail"]', { timeout: 10000 });
  const rowCount = await page.locator("[data-row-kind]").count();
  const noOverlap = await assertNoOverlap(page);
  if (!noOverlap) throw new Error("Right panel tabs overlap in timeline scenario");
  return {
    rowCount,
    hasChangedFiles: await page.locator('[data-testid="changed-files-card"]').isVisible(),
    hasExpandedDetail: await page.locator('[data-testid="timeline-work-detail"]').first().isVisible(),
    rightTabsDoNotOverlap: noOverlap,
  };
}

async function runInteractionScenario(page) {
  await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadInteractionFixture("permission");
  });
  await page.waitForSelector('[data-testid="composer-interaction-panel"]', { timeout: 10000 });
  const panelText = await page.locator('[data-testid="composer-interaction-panel"]').innerText();
  const noOverlap = await assertNoOverlap(page);
  if (!panelText.includes("edit_file") && !panelText.includes("parser.c")) {
    throw new Error("Interaction fixture did not render permission details");
  }
  if (!noOverlap) throw new Error("Right panel tabs overlap in interaction scenario");
  return {
    hasInteractionPanel: true,
    panelText,
    rightTabsDoNotOverlap: noOverlap,
  };
}
```

If the existing composer interaction panel does not have `data-testid="composer-interaction-panel"`, add that test id to `ComposerInteractionPanel.jsx` in this task and include it in the commit.

- [ ] **Step 5: Wire scenario dispatch**

In `runScenarios`, add:

```js
      } else if (scenario === "timeline") {
        results.timeline = await runTimelineScenario(page);
      } else if (scenario === "interaction") {
        results.interaction = await runInteractionScenario(page);
```

before the `responsive` branch.

- [ ] **Step 6: Update help text**

Change:

```text
--scenario load|chat|diff|responsive|app|all
```

to:

```text
--scenario load|chat|diff|responsive|app|timeline|interaction|all
```

- [ ] **Step 7: Run tests and visual scenarios**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
node scripts/gui-visual-debug.mjs --scenario timeline,interaction --no-build
```

Expected: PASS, screenshots for `timeline.png` and `interaction.png`, console count 0.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add scripts/gui-visual-debug.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs src/embedagent/frontend/gui/webapp/src/components/composer/ComposerInteractionPanel.jsx src/embedagent/frontend/gui/static/assets/app.css src/embedagent/frontend/gui/static/assets/app.js
git commit -m "test(gui): add timeline visual scenarios"
```

If `ComposerInteractionPanel.jsx` did not need a test id change, omit it from `git add`.

---

### Task 5: Polish Styles And Scroll Anchoring Verification

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Optional modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`

- [ ] **Step 1: Add failing style source checks**

In `run-tests.mjs`, add:

```js
  assert.equal(stylesSource.includes(".t3-work-row.error"), true);
  assert.equal(stylesSource.includes(".t3-work-row.running"), true);
  assert.equal(stylesSource.includes("timeline-work-detail"), true);
```

- [ ] **Step 2: Run the test and verify it fails only for missing style contracts**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL if the style contracts are not present.

- [ ] **Step 3: Add focused CSS**

In `styles.css`, add near the T3 timeline override section:

```css
.t3-work-row.error .t3-work-summary {
  color: var(--color-error);
}

.t3-work-row.running .t3-work-summary {
  color: var(--color-warning);
}

.timeline-work-detail,
.t3-work-detail {
  scroll-margin-top: 16px;
}
```

If `timeline-work-detail` is only a test id and not a class, instead add `className="t3-work-detail timeline-work-detail"` in `WorkRow.jsx`.

- [ ] **Step 4: Run full frontend verification**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 5: Run visual harness at key scenarios**

Run:

```bash
cd ../../../../../
node scripts/gui-visual-debug.mjs --scenario timeline,interaction,responsive --no-build
```

Expected: PASS with console count 0.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx src/embedagent/frontend/gui/static/assets/app.css src/embedagent/frontend/gui/static/assets/app.js
git commit -m "style(gui): polish timeline work states"
```

If `WorkRow.jsx` did not change in this task, omit it from `git add`.

---

### Task 6: Documentation And Final Verification

**Files:**
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Update frontend GUI module docs**

In `docs/modules/frontend-gui.md`, update the visual harness section to include:

```markdown
The visual harness now includes deterministic `timeline` and `interaction`
fixtures in addition to app/load/chat/diff/responsive. These fixtures are
enabled only through `?visual_debug=1` and `window.__EMBEDAGENT_VISUAL_DEBUG__`.
They exist to let Codex inspect real rendered GUI states; they are not product
protocol, backend policy, or Agent Core capability.
```

- [ ] **Step 2: Update development tracker**

In `docs/development-tracker.md`, add a recent update row:

```markdown
| 2026-06-16 | GUI timeline interaction polish slice: added controlled timeline row expansion, deterministic timeline/interaction visual fixtures, and visual harness scenarios for Codex-driven GUI debugging without changing Agent Core or product protocol. |
```

- [ ] **Step 3: Update design change log**

Add a new DC entry in `docs/design-change-log.md`:

```markdown
### DC-159

- 日期：2026-06-16
- 变更主题：GUI timeline interaction polish and visual fixture expansion
- 变更摘要：
  - Timeline work row / turn fold expansion became frontend-local controlled UI state.
  - Visual harness gained deterministic timeline and interaction fixture scenarios.
  - The fixture hook remains gated by `?visual_debug=1` and is not product protocol or Agent Core capability.
- 影响范围：
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/timeline/`
  - `scripts/gui-visual-debug.mjs`
  - `docs/modules/frontend-gui.md`
- 关联文档：
  - `docs/archive/t3code-pi-workbench/2026-06-16-gui-timeline-interaction-polish-design.md`
- 是否需要 ADR：否；这是 GUI shell and dev harness refinement.
- 后续动作：
  - Continue later with Diff panel split/wrap review polish.
```

- [ ] **Step 4: Run full verification**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q
node scripts/gui-visual-debug.mjs --scenario app,load,chat,diff,responsive,timeline,interaction --no-build
git diff --check
```

Expected:

- frontend helper checks passed
- Vite build succeeds
- 26 GUI backend tests pass
- visual harness reports console count 0
- `git diff --check` prints no errors

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md src/embedagent/frontend/gui/static/assets/app.css src/embedagent/frontend/gui/static/assets/app.js
git commit -m "docs(gui): document timeline visual fixtures"
```

If static assets did not change after the final build, omit them from `git add`.

---

## Final Closeout

- [ ] **Step 1: Inspect commits**

Run:

```bash
git log --oneline --decorate -8
git status --short --branch
```

Expected: branch contains the task commits and working tree is clean except possible no-content stat refresh warnings. If static files show modified but `git diff --stat` is empty, run `git add <file>` to refresh the index.

- [ ] **Step 2: Summarize verification evidence**

Record the exact commands that passed:

```text
npm test
npm run build
uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q
node scripts/gui-visual-debug.mjs --scenario app,load,chat,diff,responsive,timeline,interaction --no-build
git diff --check
```

- [ ] **Step 3: Request merge decision**

Report:

```text
Timeline interaction polish is implemented and verified. Recommend local merge to main after review.
```
