# T3-Parity GUI Core And Visual Debug Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the GUI core experience around T3 Code's timeline, pending interaction, and diff behavior while adding a Codex-operable visual debug harness for the real development GUI.

**Architecture:** Keep Agent Core, transcript history, permission policy, tool activation, and workflow ownership unchanged. Add a GUI-local pure projection layer that converts existing bootstrap history, live events, interaction state, and command results into T3-like rows consumed by focused React components. Add a development-only Playwright harness that starts the existing Python GUI backend with a deterministic fake OpenAI-compatible model and records screenshots, traces, DOM assertions, and console errors.

**Tech Stack:** Python 3.8, FastAPI, pywebview/WebView2 109 runtime target, React 18, existing esbuild/Vite Chrome 109 frontend build, Node-based Playwright as a development-only webapp test dependency.

---

## Guardrails

- Use `reference/t3code` as the product interaction reference only. Do not import T3 packages, require Electron, require Node at runtime, or add T3 auth, relay, SSH, Tailscale, remote environment, provider CLI, or pairing flows.
- Preserve the shipped product constraints from `AGENTS.md`: Windows 7 compatibility, offline startup, Python `>=3.8,<3.9`, Chrome/WebView2 109 frontend target, and no runtime dependency installation.
- Keep official vocabulary in new code and tests: use `build`, `tasks`, `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, and `task_items`. Do not add new `code` mode or `manage_todos`/`todos` UI paths.
- Keep GUI projections as read models. They must not decide permission outcomes, activate tools, mutate transcript history, load extensions, or infer workflow policy.
- Keep TUI work as a lower-priority follow-up. The GUI parity and visual debug harness are the first shippable slice.

## Reference Files To Check Before Coding

- T3 reference behavior:
  - `reference/t3code/apps/web/src/components/chat/MessagesTimeline.tsx`
  - `reference/t3code/apps/web/src/components/chat/MessagesTimeline.logic.ts`
  - `reference/t3code/apps/web/src/components/chat/ComposerPendingApprovalPanel.tsx`
  - `reference/t3code/apps/web/src/components/chat/ComposerPendingUserInputPanel.tsx`
  - `reference/t3code/apps/web/src/lib/diffRendering.ts`
  - `reference/t3code/apps/web/src/components/chat/ChangedFilesTree.tsx`
- EmbedAgent current GUI:
  - `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  - `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/DiffView.jsx`
  - `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - `scripts/validate-gui-smoke.py`

## File Structure

Create focused frontend model files near the existing runtime projector:

- Create `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - Owns T3-like GUI row projection.
  - Exports `projectT3TimelineRows`, `normalizeWorkEntry`, `summarizeChangedFiles`, and `isTurnFoldedByDefault`.
  - Has no React imports and no browser APIs.
- Create `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`
  - Owns composer-facing pending permission and user-input normalization.
  - Exports `normalizeComposerInteraction`, `buildPermissionResponse`, `buildUserInputResponse`, and `interactionNoticeView`.
- Create `src/embedagent/frontend/gui/webapp/src/session-runtime/diff-model.js`
  - Owns unified diff file parsing, diff summary extraction, and focused-file state.
  - Exports `parseUnifiedDiffFiles`, `diffSummaryFromTimelineItems`, `createDiffSurfaceState`, and `focusDiffFile`.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  - Keeps existing transport/session projection.
  - Calls the new pure helpers and exposes `t3TimelineRows` beside the existing `timelineView`, `currentInteraction`, and `interactionNotice`.
- Create `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - Renders `message`, `work`, `turn_fold`, `interaction`, `diff_summary`, `working`, and `system_notice` rows.
- Create `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
  - Renders compact one-line work/tool rows and inline details.
- Create `src/embedagent/frontend/gui/webapp/src/components/timeline/ChangedFilesCard.jsx`
  - Renders changed-files summary cards and file focus buttons.
- Modify `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - Becomes the exported wrapper that receives T3-like rows and delegates row rendering.
- Create `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerInteractionPanel.jsx`
  - Renders pending permission, pending user input, and stale/expired/conflict notices inside the composer area.
- Modify `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
  - Accepts `interaction`, `interactionNotice`, `answerValue`, `onAnswerChange`, and `onRespondInteraction`.
  - Keeps normal message input disabled while a backend-owned interaction is active.
- Create `src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx`
  - Renders file list plus focused diff using existing `DiffView`.
- Modify `src/embedagent/frontend/gui/webapp/src/components/DiffView.jsx`
  - Keep existing `diff2html` renderer and add raw fallback for parser/render errors.
- Modify `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - Adds first-class `diff` panel and keeps `interaction` as diagnostics/backup rather than primary pending UI.
- Modify `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
  - Adds `diff` to `RIGHT_PANEL_SURFACES`.
- Modify `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
  - Adds `Diff` label and count badge.
- Modify `src/embedagent/frontend/gui/webapp/src/store.js`
  - Adds diff surface state actions and removes new UI dependence on legacy inspector-only interaction flow.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Wires row projection, composer interaction panel, changed-file focus, and diff surface activation.
- Modify `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Adds compact T3-like timeline, work rows, composer interaction panel, changed-files card, and diff panel styling.
- Add tests:
  - `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs`
  - `src/embedagent/frontend/gui/webapp/test/diff-model.test.mjs`
  - Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` to invoke them.
- Add visual harness:
  - `src/embedagent/frontend/gui/webapp/test/gui-visual-smoke.mjs`
  - `src/embedagent/frontend/gui/webapp/test/gui-visual/fake-openai.mjs`
  - `src/embedagent/frontend/gui/webapp/test/gui-visual/scenarios.mjs`
  - `src/embedagent/frontend/gui/webapp/test/gui-visual/assertions.mjs`
  - Modify `src/embedagent/frontend/gui/webapp/package.json` and `package-lock.json` to add a dev-only `playwright` dependency and `test:visual` script.
- Modify `scripts/validate-gui-smoke.py`
  - Clean up historical `mode=code`, `manage_todos`, and `/api/todos` coverage so the API smoke aligns with official `build`/`tasks` vocabulary.
- Update docs after behavior lands:
  - `docs/modules/frontend-gui.md`
  - `docs/frontend-protocol.md` only if a frontend-facing payload changes.
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/modules/frontend-tui.md` only if the TUI follow-up slice lands.

### Task 1: T3 Timeline Row Projection

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Create: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing projection tests**

Create `test/t3-timeline.test.mjs` with these cases:

```javascript
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
            assistantItem: { id: "a1", kind: "assistant", content: "done", turnId: "turn-1", stepId: "step-1" },
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
              { id: "tool-live", kind: "tool", toolName: "run_recipe", label: "Run Recipe", status: "running", arguments: { recipe_id: "build" }, turnId: "turn-live", stepId: "step-live" },
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
}
```

Modify `test/run-tests.mjs`:

```javascript
import { runT3TimelineTests } from "./t3-timeline.test.mjs";

runT3TimelineTests();
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with an import error for `../src/session-runtime/t3-timeline.js`.

- [ ] **Step 3: Implement the pure row model**

Create `t3-timeline.js` with these exported row kinds and helper boundaries:

```javascript
export const T3_ROW_KINDS = Object.freeze({
  MESSAGE: "message",
  WORK: "work",
  TURN_FOLD: "turn_fold",
  INTERACTION: "interaction",
  DIFF_SUMMARY: "diff_summary",
  WORKING: "working",
  SYSTEM_NOTICE: "system_notice",
});

export function normalizeWorkEntry(item, options = {}) {
  const args = item?.arguments || {};
  const toolName = String(item?.toolName || item?.tool_name || "");
  const status = String(item?.status || "running");
  const changed = summarizeChangedFiles([item]);
  return {
    id: String(item?.id || item?.call_id || toolName || "work"),
    kind: T3_ROW_KINDS.WORK,
    turnId: String(item?.turnId || item?.turn_id || ""),
    stepId: String(item?.stepId || item?.step_id || ""),
    stepIndex: Number(item?.stepIndex || item?.step_index || 0),
    toolName,
    label: String(item?.label || item?.tool_label || toolName || "Work"),
    status,
    tone: status === "error" ? "error" : status === "running" ? "running" : "neutral",
    requestKind: String(item?.permissionCategory || item?.permission_category || ""),
    commandPreview: commandPreviewFor(toolName, args),
    args,
    detail: detailTextFor(item),
    changedFiles: changed.files,
    additions: changed.additions,
    deletions: changed.deletions,
    rawItem: item || {},
  };
}
```

Use normal functions rather than optional browser APIs so the file remains Node-testable and Chrome 109-safe. Include helpers for:

- `commandPreviewFor(toolName, args)`: returns shell command for `run_recipe`/command-like tools and file path for file tools.
- `detailTextFor(item)`: returns bounded string output from `error`, `data.summary`, `data.message`, `data.diff_preview`, or JSON data.
- `summarizeChangedFiles(items)`: derives `{ files, additions, deletions }` from `write_file`, `edit_file`, `git_diff`, `/diff`, and review git evidence.
- `isTurnFoldedByDefault(group, context)`: returns true only for settled non-latest turns with work entries and an assistant response.
- `projectT3TimelineRows({ turnGroups, currentStatus, activeTurnId, currentInteraction, interactionNotice })`: emits row objects in visible order.

- [ ] **Step 4: Wire projection into `projectSessionRuntime`**

Modify `projector.js` after `timelineView` is computed:

```javascript
const timelineView = projectTurnGroups(timelineItems);
const interactionNotice = buildInteractionNotice(snapshot, currentInteraction);
const t3TimelineRows = projectT3TimelineRows({
  turnGroups: timelineView,
  currentStatus: snapshot?.status || "idle",
  activeTurnId: snapshot?.active_turn_id || "",
  currentInteraction,
  interactionNotice,
});
```

Return both `timelineView` and `t3TimelineRows` so existing UI can be migrated safely:

```javascript
return {
  currentInteraction,
  interactionNotice,
  transportView,
  sessionStatusView,
  timelineItems,
  timelineView,
  t3TimelineRows,
};
```

- [ ] **Step 5: Run focused frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat(gui): add t3 timeline row projection"
```

### Task 2: Timeline Parity Components

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/timeline/ChangedFilesCard.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`

- [ ] **Step 1: Add row rendering contract tests**

Extend `test/t3-timeline.test.mjs` with data-only assertions for rendering flags:

```javascript
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
            { id: "tool-2", kind: "tool", toolName: "run_recipe", status: "error", error: "cancelled", data: { error_kind: "interrupted" }, turnId: "turn-interrupted", stepId: "step-2" },
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
```

- [ ] **Step 2: Run tests and confirm current projection needs the interrupted tone**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL until `normalizeWorkEntry` maps `data.error_kind === "interrupted"` to `tone: "interrupted"` and keeps the turn expanded.

- [ ] **Step 3: Implement row components**

Create `TimelineRows.jsx`:

```jsx
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import WorkRow from "./WorkRow.jsx";
import ChangedFilesCard from "./ChangedFilesCard.jsx";

export default function TimelineRows({ rows, onOpenDiff, renderCodeBlock }) {
  return (
    <>
      {(rows || []).map((row) => {
        if (row.kind === "message") {
          return (
            <article key={row.id} className={`t3-message-row ${row.role}`} data-testid={`timeline-message--${row.role}`}>
              {row.role === "assistant" ? (
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={renderCodeBlock ? { code: renderCodeBlock } : undefined}>
                  {row.content || ""}
                </ReactMarkdown>
              ) : (
                <div className="t3-user-bubble">{row.content || ""}</div>
              )}
            </article>
          );
        }
        if (row.kind === "work") return <WorkRow key={row.id} row={row} />;
        if (row.kind === "turn_fold") return <TurnFoldRow key={row.id} row={row} />;
        if (row.kind === "interaction") return <InteractionRow key={row.id} row={row} />;
        if (row.kind === "diff_summary") return <ChangedFilesCard key={row.id} row={row} onOpenDiff={onOpenDiff} />;
        if (row.kind === "working") return <div key={row.id} className="t3-working-row" data-testid="timeline-working-row">{row.label || "Working"}</div>;
        return <div key={row.id} className={`system-card ${row.tone || "context"}`}>{row.content || row.label || ""}</div>;
      })}
    </>
  );
}
```

Create `WorkRow.jsx` with a compact button-like summary and inline details:

```jsx
import React from "react";

const ICONS = {
  read_file: "R",
  list_dir: "L",
  glob_files: "G",
  grep_text: "S",
  write_file: "W",
  edit_file: "E",
  run_recipe: ">",
  report_quality_v2: "Q",
  record_failing_evidence: "!",
  task_status: "T",
  ask_user: "?",
};

export default function WorkRow({ row }) {
  const [open, setOpen] = React.useState(row.status === "error");
  const icon = ICONS[row.toolName] || "*";
  const hasDetail = Boolean(row.detail || row.commandPreview || (row.changedFiles && row.changedFiles.length));
  return (
    <div className={`t3-work-row ${row.tone || "neutral"}`} data-testid="timeline-work-row">
      <button className="t3-work-summary" type="button" onClick={() => hasDetail && setOpen((value) => !value)} aria-expanded={open}>
        <span className="t3-work-icon" aria-hidden="true">{icon}</span>
        <span className="t3-work-label">{row.label}</span>
        {row.commandPreview ? <code className="t3-work-preview">{row.commandPreview}</code> : null}
        <span className={`t3-work-status ${row.status}`}>{row.status}</span>
      </button>
      {open && hasDetail ? (
        <div className="t3-work-detail">
          {row.detail ? <pre>{row.detail}</pre> : null}
        </div>
      ) : null}
    </div>
  );
}
```

Create `ChangedFilesCard.jsx`:

```jsx
import React from "react";

export default function ChangedFilesCard({ row, onOpenDiff }) {
  const files = row.files || row.changedFiles || [];
  if (!files.length) return null;
  return (
    <section className="t3-changed-files-card" data-testid="changed-files-card">
      <button className="t3-changed-files-title" type="button" onClick={() => onOpenDiff && onOpenDiff({ turnId: row.turnId || "", filePath: "" })}>
        <span>{files.length} files changed</span>
        <span className="t3-diff-stats">+{row.additions || 0} -{row.deletions || 0}</span>
      </button>
      <div className="t3-changed-files-list">
        {files.map((file) => (
          <button key={file.path} type="button" className="t3-changed-file" onClick={() => onOpenDiff && onOpenDiff({ turnId: row.turnId || "", filePath: file.path })}>
            <span>{file.path}</span>
            <span>+{file.additions || 0} -{file.deletions || 0}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Replace the visible timeline surface**

Modify `Timeline.jsx` so it accepts `rows` and renders `TimelineRows` when provided. Keep the old grouped renderer behind a fallback for one commit:

```jsx
if (Array.isArray(rows) && rows.length > 0) {
  return (
    <div className="timeline t3-timeline" ref={ref} onScroll={onScroll} role="log" aria-live="polite" aria-atomic="false" aria-label="Conversation">
      <TimelineRows rows={rows} onOpenDiff={onOpenDiff} renderCodeBlock={CodeBlock} />
      {terminationCard && <div className={`system-card ${terminationCard.tone}`}>{terminationCard.content}</div>}
    </div>
  );
}
```

Modify `App.jsx` to pass `rows={runtimeState.t3TimelineRows}` and `onOpenDiff={openDiffSurface}`. Add `openDiffSurface` in Task 4; until Task 4, use a local function that opens the preview tab with any available diff.

- [ ] **Step 5: Style the compact T3-like timeline**

Add CSS classes:

```css
.t3-timeline {
  padding: 16px 18px;
}

.t3-message-row {
  display: flex;
  margin: 10px 0;
}

.t3-message-row.user {
  justify-content: flex-end;
}

.t3-user-bubble {
  max-width: min(720px, 78%);
  border: 1px solid var(--border-default);
  background: var(--bg-subtle);
  border-radius: var(--r-md);
  padding: 8px 10px;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.t3-message-row.assistant {
  max-width: 860px;
  color: var(--text-primary);
}

.t3-work-row {
  margin: 4px 0 4px 18px;
  border-left: 1px solid var(--border-default);
  padding-left: 10px;
}

.t3-work-summary {
  width: 100%;
  min-height: 28px;
  display: grid;
  grid-template-columns: 18px minmax(90px, auto) minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font: inherit;
  cursor: pointer;
  text-align: left;
}

.t3-work-summary:hover {
  color: var(--text-primary);
}

.t3-work-preview,
.t3-work-status {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.t3-work-row.error .t3-work-status,
.t3-work-row.interrupted .t3-work-status {
  color: var(--color-error);
}

.t3-work-detail {
  margin: 4px 0 8px 26px;
  border: 1px solid var(--border-default);
  background: var(--bg-default);
  border-radius: var(--r-sm);
  padding: 8px;
}
```

- [ ] **Step 6: Run tests and static build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both commands PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx src/embedagent/frontend/gui/webapp/src/components/timeline src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs
git commit -m "feat(gui): render t3 style timeline rows"
```

### Task 3: Composer Pending Interaction

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`
- Create: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerInteractionPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Create: `src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write interaction model tests**

Create `test/interaction-model.test.mjs`:

```javascript
import assert from "node:assert/strict";

import {
  buildPermissionResponse,
  buildUserInputResponse,
  normalizeComposerInteraction,
} from "../src/session-runtime/interaction-model.js";

export function runInteractionModelTests() {
  const permission = normalizeComposerInteraction({
    interaction_id: "perm-1",
    kind: "permission",
    tool_name: "write_file",
    category: "file_write",
    reason: "Write src/demo.c",
    details: { path: "src/demo.c" },
  });

  assert.equal(permission.kind, "permission");
  assert.equal(permission.title, "write_file");
  assert.equal(permission.category, "file_write");
  assert.equal(permission.primaryDetail, "Write src/demo.c");
  assert.deepEqual(buildPermissionResponse(true, true), { decision: true, remember: true });
  assert.deepEqual(buildPermissionResponse(false, false), { decision: false, remember: false });

  const input = normalizeComposerInteraction({
    interaction_id: "ask-1",
    kind: "user_input",
    question: "Continue?",
    options: [
      { index: 1, text: "Continue", mode: "" },
      { index: 2, text: "Switch to debug", mode: "debug" },
    ],
  });

  assert.equal(input.kind, "user_input");
  assert.equal(input.question, "Continue?");
  assert.equal(input.options.length, 2);
  assert.deepEqual(buildUserInputResponse(input, input.options[1], ""), {
    answer: "Switch to debug",
    selected_index: 2,
    selected_mode: "debug",
    selected_option_text: "Switch to debug",
  });
  assert.deepEqual(buildUserInputResponse(input, null, "custom"), {
    answer: "custom",
    selected_index: undefined,
    selected_mode: "",
    selected_option_text: "",
  });
}
```

Modify `test/run-tests.mjs`:

```javascript
import { runInteractionModelTests } from "./interaction-model.test.mjs";

runInteractionModelTests();
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with an import error for `interaction-model.js`.

- [ ] **Step 3: Implement `interaction-model.js`**

Use one-question internal normalization for current `ask_user`:

```javascript
export function normalizeComposerInteraction(interaction) {
  if (!interaction || interaction.status === "resolved") return null;
  const kind = String(interaction.kind || "");
  if (kind === "permission") {
    return {
      id: String(interaction.interaction_id || interaction.permission_id || ""),
      kind: "permission",
      title: String(interaction.tool_name || "Permission"),
      category: String(interaction.category || ""),
      primaryDetail: String(interaction.reason || interaction.question || ""),
      details: interaction.details || {},
      raw: interaction,
    };
  }
  if (kind === "user_input") {
    const rawOptions = Array.isArray(interaction.options) ? interaction.options : [];
    return {
      id: String(interaction.interaction_id || interaction.request_id || ""),
      kind: "user_input",
      question: String(interaction.question || ""),
      options: rawOptions.map((option, index) => ({
        index: Number(option.index || index + 1),
        text: String(option.text || option.label || option.value || ""),
        mode: String(option.mode || ""),
        raw: option,
      })),
      allowCustomAnswer: true,
      currentIndex: 1,
      totalCount: 1,
      raw: interaction,
    };
  }
  return {
    id: String(interaction.interaction_id || ""),
    kind: "unknown",
    title: String(kind || "interaction"),
    primaryDetail: String(interaction.reason || interaction.question || ""),
    raw: interaction,
  };
}
```

Also implement:

- `buildPermissionResponse(approved, remember)`.
- `buildUserInputResponse(view, option, customAnswer)`.
- `interactionNoticeView(notice)` mapping `expired` and `conflict` into non-actionable composer notices.

- [ ] **Step 4: Create composer interaction panel**

Create `ComposerInteractionPanel.jsx`:

```jsx
import React from "react";

import {
  buildPermissionResponse,
  buildUserInputResponse,
  interactionNoticeView,
  normalizeComposerInteraction,
} from "../../session-runtime/interaction-model.js";

export default function ComposerInteractionPanel({
  interaction,
  notice,
  answerValue,
  onAnswerChange,
  onRespondInteraction,
}) {
  const noticeView = interactionNoticeView(notice);
  const view = normalizeComposerInteraction(interaction);
  const [remember, setRemember] = React.useState(false);

  React.useEffect(() => {
    function onKeyDown(event) {
      if (!view || view.kind !== "user_input") return;
      const number = Number(event.key);
      if (!number) return;
      const option = view.options.find((item) => item.index === number);
      if (!option) return;
      event.preventDefault();
      onRespondInteraction(buildUserInputResponse(view, option, ""));
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [view, onRespondInteraction]);

  if (noticeView && !view) {
    return (
      <div className={`composer-interaction notice ${noticeView.kind}`} data-testid="composer-interaction-notice">
        <strong>{noticeView.title}</strong>
        <span>{noticeView.body}</span>
      </div>
    );
  }
  if (!view) return null;
  if (view.kind === "permission") {
    return (
      <section className="composer-interaction permission" data-testid="composer-permission-panel">
        <div className="composer-interaction-main">
          <strong>{view.title}</strong>
          <span>{view.primaryDetail}</span>
          {view.category ? <code>{view.category}</code> : null}
        </div>
        <label className="composer-remember">
          <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
          <span>Remember</span>
        </label>
        <button type="button" className="ghost" data-testid="permission-deny-button" onClick={() => onRespondInteraction(buildPermissionResponse(false, false))}>Deny</button>
        <button type="button" className="primary" data-testid="permission-approve-button" onClick={() => onRespondInteraction(buildPermissionResponse(true, remember))}>Approve</button>
      </section>
    );
  }
  if (view.kind === "user_input") {
    return (
      <section className="composer-interaction user-input" data-testid="composer-user-input-panel">
        <div className="composer-interaction-main">
          <strong>{view.question}</strong>
          <span>{view.currentIndex} / {view.totalCount}</span>
        </div>
        <div className="composer-options">
          {view.options.map((option) => (
            <button key={option.index} type="button" className="composer-option" data-testid={`user-input-option-${option.index}`} onClick={() => onRespondInteraction(buildUserInputResponse(view, option, ""))}>
              <kbd>{option.index}</kbd>
              <span>{option.text}</span>
            </button>
          ))}
        </div>
        <div className="composer-custom-answer">
          <input value={answerValue || ""} onChange={(event) => onAnswerChange(event.target.value)} placeholder="Custom answer" data-testid="user-input-custom-answer" />
          <button type="button" className="primary" data-testid="user-input-submit-button" disabled={!String(answerValue || "").trim()} onClick={() => onRespondInteraction(buildUserInputResponse(view, null, answerValue))}>Submit</button>
        </div>
      </section>
    );
  }
  return null;
}
```

- [ ] **Step 5: Wire panel into `Composer.jsx`**

Modify the component signature and render the panel above the input:

```jsx
import ComposerInteractionPanel from "./composer/ComposerInteractionPanel.jsx";

export default function Composer({
  value,
  onChange,
  onSend,
  onStop,
  isRunning,
  currentMode,
  commandHints = [],
  onOpenCommandPalette,
  interaction,
  interactionNotice,
  answerValue,
  onAnswerChange,
  onRespondInteraction,
}) {
  const hasInteraction = Boolean(interaction);
```

Disable normal message sending while `hasInteraction` is true, not while the backend is simply `waiting_user_input`:

```jsx
<ComposerInteractionPanel
  interaction={interaction}
  notice={interactionNotice}
  answerValue={answerValue}
  onAnswerChange={onAnswerChange}
  onRespondInteraction={onRespondInteraction}
/>
<textarea disabled={isRunning || hasInteraction} ... />
```

- [ ] **Step 6: Keep Inspector interaction as backup diagnostics**

In `Inspector.jsx`, leave the `interaction` tab available, but change empty copy or title so the primary action is no longer described as only in Inspector. Do not remove `InteractionPanel` yet; it remains useful for diagnostics and backward compatibility during the cutover.

- [ ] **Step 7: Wire `App.jsx` props**

Pass runtime interaction state into `Composer`:

```jsx
<Composer
  value={state.composer}
  onChange={(v) => dispatch({ type: "set_composer", value: v })}
  onSend={sendMessage}
  onStop={cancelSession}
  isRunning={currentStatus === "running"}
  currentMode={currentMode}
  commandHints={SLASH_COMMAND_HINTS}
  onOpenCommandPalette={() => dispatch({ type: "workbench_command_palette_opened" })}
  interaction={runtimeState.currentInteraction}
  interactionNotice={interactionNotice}
  answerValue={userAnswer}
  onAnswerChange={setUserAnswer}
  onRespondInteraction={respondToInteraction}
/>
```

- [ ] **Step 8: Run focused frontend tests and backend interaction tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd D:/Claude-project/ccode-win7
uv run pytest tests/test_gui_backend_api.py tests/test_gui_runtime.py tests/test_gui_sync.py -v
```

Expected: all commands PASS.

- [ ] **Step 9: Commit Task 3**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js src/embedagent/frontend/gui/webapp/src/components/composer src/embedagent/frontend/gui/webapp/src/components/Composer.jsx src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat(gui): move pending interactions into composer"
```

### Task 4: Diff Parity Surface

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/diff-model.js`
- Create: `src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/DiffView.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Create: `src/embedagent/frontend/gui/webapp/test/diff-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write diff model tests**

Create `test/diff-model.test.mjs`:

```javascript
import assert from "node:assert/strict";

import {
  createDiffSurfaceState,
  focusDiffFile,
  parseUnifiedDiffFiles,
} from "../src/session-runtime/diff-model.js";

export function runDiffModelTests() {
  const diff = "--- a/src/a.c\n+++ b/src/a.c\n@@ -1 +1 @@\n-old\n+new\n--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-before\n+after\n";
  const files = parseUnifiedDiffFiles(diff);
  assert.equal(files.length, 2);
  assert.deepEqual(files.map((file) => file.path), ["src/a.c", "README.md"]);
  assert.equal(files[0].additions, 1);
  assert.equal(files[0].deletions, 1);

  const surface = createDiffSurfaceState({
    title: "Git Diff",
    diff,
    source: "command",
    turnId: "turn-1",
  });
  assert.equal(surface.files.length, 2);
  assert.equal(surface.focusedFilePath, "src/a.c");
  assert.equal(surface.rawDiff, diff);

  const focused = focusDiffFile(surface, "README.md");
  assert.equal(focused.focusedFilePath, "README.md");
  assert.match(focused.focusedDiff, /README\.md/);

  const raw = createDiffSurfaceState({ title: "Raw", diff: "not a unified diff", source: "raw" });
  assert.equal(raw.files.length, 0);
  assert.equal(raw.focusedDiff, "not a unified diff");
}
```

Modify `test/run-tests.mjs`:

```javascript
import { runDiffModelTests } from "./diff-model.test.mjs";

runDiffModelTests();
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL with an import error for `diff-model.js`.

- [ ] **Step 3: Implement `diff-model.js`**

Use a small line-based parser for file sections and keep raw fallback:

```javascript
export function parseUnifiedDiffFiles(diff) {
  const text = String(diff || "");
  const lines = text.split(/\r?\n/);
  const files = [];
  let current = null;
  for (const line of lines) {
    if (line.startsWith("--- ")) {
      if (current) files.push(finishFile(current));
      current = { oldHeader: line, newHeader: "", lines: [line], additions: 0, deletions: 0 };
      continue;
    }
    if (current) {
      current.lines.push(line);
      if (line.startsWith("+++ ")) current.newHeader = line;
      if (line.startsWith("+") && !line.startsWith("+++")) current.additions += 1;
      if (line.startsWith("-") && !line.startsWith("---")) current.deletions += 1;
    }
  }
  if (current) files.push(finishFile(current));
  return files.filter((file) => file.path);
}
```

Also implement:

- `finishFile(section)`: extracts path from `+++ b/path`, falls back to `--- a/path`, strips `a/` or `b/`.
- `createDiffSurfaceState({ title, diff, source, turnId, filePath })`: returns `{ title, source, turnId, rawDiff, files, focusedFilePath, focusedDiff }`.
- `focusDiffFile(surface, filePath)`: returns a new state object with `focusedDiff` set to the selected file section.
- `diffSummaryFromTimelineItems(items)`: can call `summarizeChangedFiles` from `t3-timeline.js` or share the same parsing logic.

- [ ] **Step 4: Add first-class right-panel diff surface**

Modify `workbench/surfaces.js`:

```javascript
export const RIGHT_PANEL_SURFACES = [
  "interaction",
  "tasks",
  "plan",
  "artifacts",
  "run",
  "problems",
  "review",
  "diff",
  "permissions",
  "runtime",
  "preview",
  "log",
];
```

Modify `RightPanelTabs.jsx` labels:

```javascript
diff: "Diff",
```

Modify `store.js` initial state:

```javascript
diffSurface: null,
```

Add reducer actions:

```javascript
case "diff_surface_opened":
  return {
    ...state,
    diffSurface: action.diffSurface || null,
    inspectorTab: "diff",
    workbench: reduceWorkbenchState(state.workbench, { type: "workbench_surface_activated", placement: "right", kind: "diff" }),
  };
case "diff_file_focused":
  return {
    ...state,
    diffSurface: focusDiffFile(state.diffSurface, action.filePath || ""),
  };
```

Import `focusDiffFile` from `./session-runtime/diff-model.js`.

- [ ] **Step 5: Add `DiffPanel.jsx` and raw fallback**

Create `components/diff/DiffPanel.jsx`:

```jsx
import React from "react";

import DiffView from "../DiffView.jsx";

export default function DiffPanel({ surface, onFocusFile }) {
  if (!surface) return <div className="empty-copy">No diff selected.</div>;
  return (
    <section className="diff-panel" data-testid="diff-panel">
      <header className="diff-panel-header">
        <strong>{surface.title || "Diff"}</strong>
        <span>{surface.files.length} files</span>
      </header>
      {surface.files.length > 0 ? (
        <div className="diff-file-list">
          {surface.files.map((file) => (
            <button key={file.path} type="button" className={file.path === surface.focusedFilePath ? "active" : ""} onClick={() => onFocusFile && onFocusFile(file.path)} data-testid={`diff-file--${file.path}`}>
              <span>{file.path}</span>
              <span>+{file.additions} -{file.deletions}</span>
            </button>
          ))}
        </div>
      ) : null}
      <DiffView title={surface.focusedFilePath || surface.title} diff={surface.focusedDiff || surface.rawDiff} />
    </section>
  );
}
```

Modify `DiffView.jsx`:

```jsx
let rendered = "";
try {
  rendered = diffHtml(diff, {
    drawFileList: false,
    matching: "lines",
    outputFormat: "line-by-line",
    highlight: false,
  });
} catch (_) {
  rendered = "";
}

if (!rendered) {
  return (
    <div className="diff-view">
      {title ? <div className="diff-view-title">{title}</div> : null}
      <pre className="diff-raw-fallback">{diff}</pre>
    </div>
  );
}
```

- [ ] **Step 6: Wire diff opening from timeline and commands**

In `App.jsx`, import `createDiffSurfaceState` and add:

```javascript
function openDiffSurface({ title = "Diff", diff = "", turnId = "", filePath = "" } = {}) {
  const surface = createDiffSurfaceState({
    title,
    diff,
    source: "gui",
    turnId,
    filePath,
  });
  dispatch({ type: "diff_surface_opened", diffSurface: surface });
}
```

When `/diff` command result arrives:

```javascript
if (data.command_name === "diff" && typeof data.data?.diff === "string" && data.data.diff) {
  dispatch({
    type: "diff_surface_opened",
    diffSurface: createDiffSurfaceState({
      title: "Git Diff",
      diff: data.data.diff,
      source: "command",
      turnId: data.turn_id || "",
    }),
  });
}
```

In `Inspector.jsx`, render `DiffPanel` for `inspectorTab === "diff"` and pass `state.diffSurface` plus `onFocusDiffFile`.

- [ ] **Step 7: Run focused tests and build**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: both commands PASS.

- [ ] **Step 8: Commit Task 4**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/diff-model.js src/embedagent/frontend/gui/webapp/src/components/diff src/embedagent/frontend/gui/webapp/src/components/DiffView.jsx src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/diff-model.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat(gui): add t3 style diff surface"
```

### Task 5: Codex Visual Debug Harness

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/test/gui-visual-smoke.mjs`
- Create: `src/embedagent/frontend/gui/webapp/test/gui-visual/fake-openai.mjs`
- Create: `src/embedagent/frontend/gui/webapp/test/gui-visual/scenarios.mjs`
- Create: `src/embedagent/frontend/gui/webapp/test/gui-visual/assertions.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/package.json`
- Modify: `src/embedagent/frontend/gui/webapp/package-lock.json`
- Modify: `scripts/validate-gui-smoke.py`
- Modify: `.gitignore` only if the chosen output directory is not already ignored.

- [ ] **Step 1: Add Playwright dev dependency and script**

Run from `src/embedagent/frontend/gui/webapp`:

```bash
npm install --save-dev playwright
```

Modify `package.json` scripts:

```json
{
  "scripts": {
    "test:visual": "node test/gui-visual-smoke.mjs"
  }
}
```

Keep `playwright` in `devDependencies` and let `package-lock.json` record the exact resolved version. Do not add it to Python runtime dependencies, `scripts/offline-runtime-contract.json`, or the shipped bundle manifest.

- [ ] **Step 2: Create fake OpenAI server**

Create `test/gui-visual/fake-openai.mjs`:

```javascript
import http from "node:http";

export function startFakeOpenAI({ port = 0 } = {}) {
  const requests = [];
  const server = http.createServer((req, res) => {
    if (req.method !== "POST" || !req.url.replace(/\/$/, "").endsWith("/v1/chat/completions")) {
      res.writeHead(404);
      res.end();
      return;
    }
    let raw = "";
    req.on("data", (chunk) => { raw += chunk; });
    req.on("end", () => {
      const payload = JSON.parse(raw || "{}");
      requests.push(payload);
      const messages = payload.messages || [];
      const userText = lastUserText(messages).toLowerCase();
      const hasToolResult = messages.some((item) => item.role === "tool");
      const body = completionFor(userText, hasToolResult);
      if (payload.stream) {
        res.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
        });
        for (const chunk of streamChunksFor(body)) {
          res.write(`data: ${JSON.stringify(chunk)}\n\n`);
        }
        res.write("data: [DONE]\n\n");
        res.end();
        return;
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(body));
    });
  });
  return new Promise((resolve) => {
    server.listen(port, "127.0.0.1", () => {
      resolve({
        server,
        requests,
        port: server.address().port,
        close: () => new Promise((done) => server.close(done)),
      });
    });
  });
}

function lastUserText(messages) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === "user") return String(messages[index].content || "");
  }
  return "";
}

function completionFor(userText, hasToolResult) {
  if (!hasToolResult && userText.includes("visual tool")) {
    return toolCall("call-readme", "read_file", { path: "README.md" });
  }
  if (!hasToolResult && userText.includes("visual permission")) {
    return toolCall("call-write", "write_file", { path: "visual-demo.txt", content: "visual debug\n" });
  }
  if (!hasToolResult && userText.includes("visual ask")) {
    return toolCall("call-ask", "ask_user", {
      question: "Continue visual scenario?",
      option_1: "Continue",
      option_2: "Switch to debug",
      option_2_mode: "debug",
    });
  }
  return {
    choices: [
      {
        message: { role: "assistant", content: "Visual scenario complete." },
        finish_reason: "stop",
      },
    ],
  };
}

function streamChunksFor(body) {
  const choice = body.choices?.[0] || {};
  const message = choice.message || {};
  if (Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
    return [
      {
        choices: [
          {
            delta: { tool_calls: message.tool_calls.map((toolCall, index) => ({ index, ...toolCall })) },
            finish_reason: null,
          },
        ],
      },
      { choices: [{ delta: {}, finish_reason: "tool_calls" }] },
    ];
  }
  return [
    { choices: [{ delta: { content: String(message.content || "") }, finish_reason: null }] },
    { choices: [{ delta: {}, finish_reason: "stop" }] },
  ];
}

function toolCall(id, name, args) {
  return {
    choices: [
      {
        message: {
          role: "assistant",
          content: "",
          tool_calls: [
            { id, type: "function", function: { name, arguments: JSON.stringify(args) } },
          ],
        },
        finish_reason: "tool_calls",
      },
    ],
  };
}
```

- [ ] **Step 3: Create scenarios and assertions**

Create `test/gui-visual/assertions.mjs`:

```javascript
export async function assertNoConsoleErrors(page, errors) {
  if (errors.length > 0) {
    throw new Error(`Console errors:\n${errors.join("\n")}`);
  }
  await page.waitForSelector("[data-testid='composer-input']", { timeout: 15000 });
}

export async function sendComposerMessage(page, text) {
  await page.fill("[data-testid='composer-input']", text);
  await page.click("[data-testid='send-button']");
}

export async function expectVisible(page, selector, label) {
  await page.waitForSelector(selector, { state: "visible", timeout: 30000 });
  const visible = await page.locator(selector).first().isVisible();
  if (!visible) throw new Error(`${label} is not visible`);
}
```

Create `test/gui-visual/scenarios.mjs`:

```javascript
import { expectVisible, sendComposerMessage } from "./assertions.mjs";

export const scenarios = [
  {
    name: "normal",
    async run(page) {
      await sendComposerMessage(page, "visual normal");
      await expectVisible(page, "[data-testid='timeline-message--assistant']", "assistant message");
    },
  },
  {
    name: "tool",
    async run(page) {
      await sendComposerMessage(page, "visual tool");
      await expectVisible(page, "[data-testid='timeline-work-row']", "work row");
    },
  },
  {
    name: "ask",
    async run(page) {
      await sendComposerMessage(page, "visual ask");
      await expectVisible(page, "[data-testid='composer-user-input-panel']", "composer user input panel");
      await page.click("[data-testid='user-input-option-1']");
      await expectVisible(page, "[data-testid='timeline-message--assistant']", "assistant after ask");
    },
  },
  {
    name: "permission",
    async run(page) {
      await sendComposerMessage(page, "visual permission");
      await expectVisible(page, "[data-testid='composer-permission-panel']", "composer permission panel");
      await page.click("[data-testid='permission-approve-button']");
      await expectVisible(page, "[data-testid='changed-files-card']", "changed files card");
    },
  },
  {
    name: "diff",
    async run(page) {
      await sendComposerMessage(page, "/diff");
      await expectVisible(page, "[data-testid='diff-panel']", "diff panel");
    },
  },
];
```

- [ ] **Step 4: Create visual smoke runner**

Create `test/gui-visual-smoke.mjs`:

```javascript
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

import { startFakeOpenAI } from "./gui-visual/fake-openai.mjs";
import { assertNoConsoleErrors } from "./gui-visual/assertions.mjs";
import { scenarios } from "./gui-visual/scenarios.mjs";

const repoRoot = fileURLToPath(new URL("../../../../../..", import.meta.url));
const pythonExe = path.join(repoRoot, ".venv", "Scripts", "python.exe");

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}
```

The runner must:

- create an output directory under `build/gui-visual-debug/<timestamp>`
- create a temp workspace with a small `README.md`
- start fake OpenAI on a free port
- make the fake OpenAI server support both regular JSON completions and `text/event-stream` streaming chunks, matching `scripts/validate-gui-smoke.py`
- start `python.exe -m embedagent.frontend.gui.launcher --headless --workspace <temp> --mode build --model gui-visual-model --base-url http://127.0.0.1:<modelPort>/v1 --port <guiPort> --timeout 20 --max-turns 3`
- wait for `http://127.0.0.1:<guiPort>/`
- open Chromium through Playwright at desktop `1400x900` and narrow `760x820`
- attach `page.on("console")` and fail on `error`
- run each scenario on a fresh page or fresh session
- save screenshots as `<output>/<scenario>-desktop.png` and `<output>/<scenario>-narrow.png`
- save `summary.json` with scenario names, screenshot paths, console error count, GUI port, model request count, and workspace path
- close browser, fake model, and Python process in `finally`

Use this process cleanup pattern:

```javascript
function stopProcess(child) {
  if (!child || child.exitCode !== null) return Promise.resolve();
  child.kill();
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      spawn("taskkill", ["/F", "/T", "/PID", String(child.pid)], { stdio: "ignore" });
      resolve();
    }, 5000);
    child.once("exit", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}
```

- [ ] **Step 5: Clean up API smoke vocabulary**

Modify `scripts/validate-gui-smoke.py`:

- Create sessions with `mode=build`, not `mode=code`.
- Remove fake model tool call for `manage_todos`.
- Remove `/api/todos` checks.
- Add a `task_status` or `/tasks` check if an API-level workflow state assertion is still needed.
- Keep existing permission, ask-user, read_file/tool, and `/review` coverage.

Run:

```bash
rg -n "mode=code|manage_todos|/api/todos|todos" scripts/validate-gui-smoke.py
```

Expected: no output.

- [ ] **Step 6: Run visual harness**

Install the Playwright browser once on the development machine:

```bash
cd src/embedagent/frontend/gui/webapp
npx playwright install chromium
```

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run test:visual
```

Expected: PASS, `build/gui-visual-debug/<timestamp>/summary.json` exists, and screenshots exist for normal, tool, ask, permission, and diff scenarios.

- [ ] **Step 7: Run existing GUI smoke**

Run:

```bash
cd D:/Claude-project/ccode-win7
uv run python scripts/validate-gui-smoke.py
```

Expected: PASS and JSON output includes assistant text, tool events, permission request count, user input request count, and review command result.

- [ ] **Step 8: Commit Task 5**

```bash
git add src/embedagent/frontend/gui/webapp/package.json src/embedagent/frontend/gui/webapp/package-lock.json src/embedagent/frontend/gui/webapp/test/gui-visual-smoke.mjs src/embedagent/frontend/gui/webapp/test/gui-visual scripts/validate-gui-smoke.py
git commit -m "test(gui): add codex visual debug harness"
```

### Task 6: Documentation And TUI Follow-Up Notes

**Files:**
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/frontend-protocol.md` only if a payload contract changed.
- Modify: `docs/modules/frontend-tui.md` only if TUI behavior changes in this implementation branch.

- [ ] **Step 1: Document actual GUI behavior**

Update `docs/modules/frontend-gui.md` with:

- T3-like row projection is GUI-local and read-only.
- Timeline rows are derived from bootstrap history plus live session events.
- Pending permission and ask-user are shown in the composer area.
- Diff is a first-class right-panel surface.
- Visual debug harness command is `npm run test:visual` from `src/embedagent/frontend/gui/webapp`.

- [ ] **Step 2: Update tracker and changelog**

Update `docs/development-tracker.md` and `docs/design-change-log.md` with the concrete completed slice:

- T3 parity timeline projection.
- Composer interaction panel.
- Diff surface.
- Codex visual debug harness.
- API smoke vocabulary cleanup from legacy `code`/`todos` paths.

- [ ] **Step 3: Update protocol docs only for real contract changes**

If the implementation only adds frontend-local projection and no backend payload fields, add a short note to `docs/frontend-protocol.md` that no protocol change was required and the GUI consumes existing bootstrap/session-event/interaction/diff payloads.

If any backend payload is changed, document the exact request/response field and add or update backend tests in the same commit.

- [ ] **Step 4: TUI note**

If no TUI code changed, add a tracker note that TUI parity remains the next lower-priority follow-up. Do not claim TUI parity is implemented.

- [ ] **Step 5: Run documentation scan**

Run:

```bash
rg -n "mode=code|manage_todos|todos" docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md docs/frontend-protocol.md src/embedagent/frontend/gui/webapp/src scripts/validate-gui-smoke.py
```

Expected: no output for new claims or legacy GUI smoke vocabulary. Existing historical references outside this file set are not part of this check.

- [ ] **Step 6: Commit Task 6**

```bash
git add docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md docs/frontend-protocol.md docs/modules/frontend-tui.md
git commit -m "docs(gui): document t3 parity visual debug slice"
```

## Final Verification

- [ ] **Step 1: Frontend tests**

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 2: GUI backend tests**

```bash
cd D:/Claude-project/ccode-win7
uv run pytest tests/test_gui_backend_api.py tests/test_gui_runtime.py tests/test_gui_sync.py -v
```

Expected: PASS.

- [ ] **Step 3: Visual harness**

```bash
cd src/embedagent/frontend/gui/webapp
npm run test:visual
```

Expected: PASS and screenshots plus `summary.json` are written under `build/gui-visual-debug/<timestamp>`.

- [ ] **Step 4: API smoke**

```bash
cd D:/Claude-project/ccode-win7
uv run python scripts/validate-gui-smoke.py
```

Expected: PASS.

- [ ] **Step 5: Fast Python subset**

```bash
cd D:/Claude-project/ccode-win7
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS or a report listing exact pre-existing unrelated failures.

- [ ] **Step 6: Static compatibility scan**

```bash
rg -n "mode=code|manage_todos|/api/todos|todos" src/embedagent/frontend/gui/webapp/src scripts/validate-gui-smoke.py
rg -n "\\?\\.|\\?\\?|replaceAll|Array\\.prototype\\.at|structuredClone" src/embedagent/frontend/gui/webapp/src
```

Expected: first command has no output for new GUI code and smoke script. Second command is reviewed manually for Chrome 109 compatibility; optional chaining is already acceptable for the current build target, while unsupported APIs need replacement if found.

## Rollback Plan

- The projection task is additive until `Timeline.jsx` consumes `t3TimelineRows`; if rendering regresses, pass `runtimeState.timelineView` back into the old grouped renderer while keeping tests for the pure projection.
- The composer interaction panel does not change backend endpoints. If it regresses, keep `InteractionPanel` in the inspector and stop passing interaction props to `Composer` until the panel is fixed.
- The diff surface is frontend-local. If it regresses, keep `/diff` opening the old preview panel and preserve `diff-model.js` tests for the next pass.
- The visual harness is development-only. If Playwright installation is unavailable on a machine, keep `scripts/validate-gui-smoke.py` as API-level coverage and record that browser screenshots were not run on that machine.
