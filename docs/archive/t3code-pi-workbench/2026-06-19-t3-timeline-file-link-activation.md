# T3 Timeline File Link Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Match T3code's file-link behavior by letting timeline markdown links, grep matches, tool file rows, and review findings open the right-panel file preview at the requested line.

**Architecture:** Keep this GUI app-shell only. Reuse the existing `App.openFile(path, line)` and `workbench_surface_opened` reveal-line path, and pass an `onOpenFile` callback down through the timeline component tree. Do not change Agent Core, session transcript truth, workflow state, permission policy, or backend protocol.

**Tech Stack:** React, existing T3 timeline projector, right-panel file surface, Node frontend helper tests, GUI visual debug harness, existing static asset build.

---

## File Structure

- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Pass `openFile` into `<Timeline />`.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - Accept `onOpenFile`, wire it into markdown link handling and `<TimelineRows />`.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
  - Thread `onOpenFile` through `TimelineRowSwitch`, `WorkGroupSection`, `TurnFoldRow`, `CommandResultRow`, and `ReviewResultRow`.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
  - Pass `onOpenFile` into `ToolDetail`.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx`
  - Render file-like match, file, changed-file rows as buttons when a path is present.
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
  - Preserve numeric `line` values in match/detail/finding models instead of converting all line values to display strings.
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
  - Add a timeline fixture with a grep match, markdown file link, review finding, and preloaded file preview content.
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
  - Load the fixture preview content in the visual timeline action only; do not introduce runtime side effects.
- Modify: `scripts/gui-visual-debug.mjs`
  - Click a timeline file link and assert the right-panel file surface reveals the requested line.
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Add T3-like quiet hover/focus styling for timeline file link buttons.
- Test: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`
- Build output: `src/embedagent/frontend/gui/static/assets/app.js`
- Build output: `src/embedagent/frontend/gui/static/assets/app.css`
- Docs: `docs/modules/frontend-gui.md`
- Docs: `docs/development-tracker.md`
- Docs: `docs/design-change-log.md`

---

### Task 1: Preserve File-Link Targets In Timeline Models

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- Test: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`

- [ ] **Step 1: Write the failing projector test**

Add a `grep_text` work item assertion inside `runT3TimelineTests()`:

```js
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
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `matchItems()` currently stores `line` as a string and does not expose `displayLine`.

- [ ] **Step 3: Implement the minimal model change**

In `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`, add helpers near `stringValue()`:

```js
function lineNumberValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.max(1, Math.trunc(number));
}

function lineDisplayValue(value) {
  const number = lineNumberValue(value);
  return number === null ? "" : String(number);
}
```

Update the object branch in `matchItems(data)`:

```js
      const line = lineNumberValue(item.line);
      return {
        id: stringValue(item.id || `${item.path || "match"}-${line || index}`),
        path: stringValue(item.path),
        line,
        displayLine: lineDisplayValue(item.line),
        text: truncateText(item.text || item.content || item.preview || "", 320),
      };
```

Keep the non-object branch unchanged except add:

```js
      displayLine: "",
```

- [ ] **Step 4: Run test and confirm pass**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 5: Commit this model-only step**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs
git commit -m "test: preserve timeline file link targets"
```

---

### Task 2: Wire `onOpenFile` Through The Timeline Tree

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing source checks**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, extend the existing source checks:

```js
  const timelineSource = fs.readFileSync(
    webappSourcePath("components", "Timeline.jsx"),
    "utf8",
  );
  assert.equal(timelineSource.includes("onOpenFile"), true);
  assert.equal(timelineSource.includes("handleTimelineFileLink"), true);
  assert.equal(timelineSource.includes("parseTimelineFileHref"), true);

  const timelineRowsSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "TimelineRows.jsx"),
    "utf8",
  );
  assert.equal(timelineRowsSource.includes("onOpenFile"), true);

  const workRowSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "WorkRow.jsx"),
    "utf8",
  );
  assert.equal(workRowSource.includes("onOpenFile"), true);
```

Also extend the existing `appSource` checks:

```js
  assert.equal(appSource.includes("onOpenFile={openFile}"), true);
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the callback is only wired into the right panel, not the timeline.

- [ ] **Step 3: Wire App to Timeline**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`, update the `<Timeline />` call:

```jsx
              onOpenDiff={openDiffSurface}
              onOpenFile={openFile}
```

- [ ] **Step 4: Add file href parsing and markdown link handling**

In `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`, add these helpers above `const Timeline = forwardRef(...)`:

```js
function parseTimelineFileHref(href) {
  const value = String(href || "").trim();
  if (!value || /^[a-z][a-z0-9+.-]*:/i.test(value) || value.startsWith("#")) return null;
  const [pathPart, hashPart = ""] = value.split("#", 2);
  const normalizedPath = pathPart.replace(/\\/g, "/").replace(/^\/+/, "");
  if (!normalizedPath) return null;
  const lineMatch = hashPart.match(/(?:^|[&?])L?(\d+)\b/i) || hashPart.match(/^L?(\d+)$/i);
  const line = lineMatch ? Number(lineMatch[1]) : undefined;
  return { path: normalizedPath, line: Number.isFinite(line) ? line : undefined };
}
```

Update the `Timeline` props destructuring to include `onOpenFile`.

Inside `Timeline`, add:

```js
  function handleTimelineFileLink(event, href) {
    const target = parseTimelineFileHref(href);
    if (!target || !onOpenFile) return false;
    event.preventDefault();
    onOpenFile(target.path, target.line);
    return true;
  }
```

Update `markdownComponents.a`:

```jsx
    a(props) {
      const target = parseTimelineFileHref(props.href);
      if (target) {
        return (
          <button
            type="button"
            className="timeline-file-link"
            data-testid={`timeline-file-link--${target.path}`}
            onClick={(event) => handleTimelineFileLink(event, props.href)}
          >
            {props.children}
          </button>
        );
      }
      return <a {...props} target="_blank" rel="noopener noreferrer" />;
    },
```

- [ ] **Step 5: Thread callback through timeline components**

In `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`, add `onOpenFile` to:

```jsx
function WorkGroupSection({ rows, rowUiState, onToggleRow, rowKeyFor, onOpenFile }) { ... }
function TurnFoldRow({ row, rowUiState, onToggleRow, rowKeyFor, onOpenFile }) { ... }
function CommandResultRow({ row, markdownComponents, rowUiState, onToggleRow, rowKeyFor }) { ... }
function ReviewResultRow({ row, markdownComponents, rowUiState, onToggleRow, rowKeyFor, onOpenFile }) { ... }
function TimelineRowSwitch({ row, onOpenDiff, onOpenFile, markdownComponents, rowUiState, onToggleRow, rowKeyFor }) { ... }
export default function TimelineRows({ rows, onOpenDiff, onOpenFile, markdownComponents, ... }) { ... }
```

Pass it into every nested `<WorkRow />`, `<TimelineRowSwitch />`, and `<ReviewResultRow />` that can contain file rows or markdown content:

```jsx
              onOpenFile={onOpenFile}
```

In `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`, update the signature and `ToolDetail` call:

```jsx
export default function WorkRow({ row, expanded = false, onToggle = null, rowKey = "", onOpenFile = null }) {
```

```jsx
          {row.detailModel ? <ToolDetail model={row.detailModel} onOpenFile={onOpenFile} /> : null}
```

- [ ] **Step 6: Run test and confirm pass**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 7: Commit the callback wiring**

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: wire timeline file open callback"
```

---

### Task 3: Make Timeline Detail Rows Clickable

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing source checks**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, extend `ToolDetail.jsx` checks:

```js
  const toolDetailSource = fs.readFileSync(
    webappSourcePath("components", "timeline", "ToolDetail.jsx"),
    "utf8",
  );
  assert.equal(toolDetailSource.includes("timeline-file-link"), true);
  assert.equal(toolDetailSource.includes("data-testid={`timeline-tool-file-link--"), true);
  assert.equal(toolDetailSource.includes("onOpenFile(item.path, item.line || undefined)"), true);
```

Extend `TimelineRows.jsx` checks:

```js
  assert.equal(timelineRowsSource.includes("onOpenFile={onOpenFile}"), true);
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because `ToolDetail` renders path text, not clickable T3-style file links.

- [ ] **Step 3: Implement clickable detail rows**

In `src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx`, replace `MatchItems` with:

```jsx
function FileTargetButton({ item, onOpenFile, children }) {
  if (!item?.path || !onOpenFile) return <span className="t3-tool-detail-item-path">{children}</span>;
  return (
    <button
      type="button"
      className="t3-tool-detail-item-path timeline-file-link"
      data-testid={`timeline-tool-file-link--${item.path}`}
      onClick={() => onOpenFile(item.path, item.line || undefined)}
    >
      {children}
    </button>
  );
}

function MatchItems({ items = [], onOpenFile = null }) {
  return (
    <div className="t3-tool-detail-list">
      {items.map((item) => {
        const label = [item.path, item.displayLine || item.line ? `:${item.displayLine || item.line}` : ""]
          .filter(Boolean)
          .join("") || "match";
        return (
          <div key={item.id || `${item.path}-${item.line}-${item.text}`} className="t3-tool-detail-item">
            <FileTargetButton item={item} onOpenFile={onOpenFile}>{label}</FileTargetButton>
            {item.text ? <code>{item.text}</code> : null}
          </div>
        );
      })}
    </div>
  );
}
```

Update `FileItems` similarly:

```jsx
function FileItems({ items = [], onOpenFile = null }) {
  return (
    <div className="t3-tool-detail-files">
      {items.map((item) => (
        <FileTargetButton key={item.id || item.path} item={item} onOpenFile={onOpenFile}>
          {item.path}
          {item.additions || item.deletions ? (
            <small> +{item.additions || 0} -{item.deletions || 0}</small>
          ) : null}
        </FileTargetButton>
      ))}
    </div>
  );
}
```

Update `Section` and exported component signatures:

```jsx
function Section({ section, onOpenFile }) {
```

```jsx
      {section.kind === "matches" ? <MatchItems items={section.items || []} onOpenFile={onOpenFile} /> : null}
      {section.kind === "files" || section.kind === "changed_files" ? <FileItems items={section.items || []} onOpenFile={onOpenFile} /> : null}
```

```jsx
export default function ToolDetail({ model, onOpenFile = null }) {
```

```jsx
        <Section key={`${section.kind || "section"}-${index}`} section={section} onOpenFile={onOpenFile} />
```

- [ ] **Step 4: Make review findings clickable**

In `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx`, update the finding meta block inside `ReviewResultRow`:

```jsx
              <div className="t3-review-finding-meta">
                {finding.file && onOpenFile ? (
                  <button
                    type="button"
                    className="timeline-file-link"
                    data-testid={`timeline-review-file-link--${finding.file}`}
                    onClick={() => onOpenFile(finding.file, finding.line || undefined)}
                  >
                    {[finding.severity, finding.file, finding.line ? `:${finding.line}` : ""].filter(Boolean).join(" ")}
                  </button>
                ) : (
                  [finding.severity, finding.file, finding.line ? `:${finding.line}` : ""].filter(Boolean).join(" ")
                )}
              </div>
```

- [ ] **Step 5: Add quiet T3-style CSS**

In `src/embedagent/frontend/gui/webapp/src/styles.css`, add:

```css
.timeline-file-link {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--accent);
  font: inherit;
  padding: 0;
  text-align: left;
  cursor: pointer;
}

.timeline-file-link:hover,
.timeline-file-link:focus-visible {
  color: var(--accent-strong);
  text-decoration: underline;
  outline: none;
}
```

- [ ] **Step 6: Run test and confirm pass**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 7: Commit clickable rows**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat: open files from timeline details"
```

---

### Task 4: Add Visual Fixture And Browser Verification

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `scripts/gui-visual-debug.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`

- [ ] **Step 1: Add failing fixture tests**

In `src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs`, assert the timeline fixture includes link targets and preview content:

```js
  assert.equal(timelineAction.previews["src/parser.c"].content.includes("line 4 reveal target"), true);
  assert.equal(
    timelineAction.timeline.some((item) => item.data?.matches?.some((match) => match.path === "src/parser.c" && match.line === 4)),
    true,
  );
  assert.equal(
    timelineAction.timeline.some((item) => String(item.content || "").includes("[src/parser.c:4](src/parser.c#L4)")),
    true,
  );
```

In `src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs`, add:

```js
  assert.equal(runnerSource.includes("timeline-tool-file-link--src/parser.c"), true);
  assert.equal(runnerSource.includes("timelineLinkRevealState"), true);
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: FAIL because the fixture and runner do not yet expose or click a timeline file link.

- [ ] **Step 3: Add fixture preview content**

In `buildTimelineFixtureAction()` in `src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js`, add a `previews` object to the returned action:

```js
    previews: {
      "src/parser.c": {
        kind: "file",
        title: "parser.c",
        content: [
          "int parse_value(void) {",
          "  return 0;",
          "}",
          "line 4 reveal target",
          "void recover(void) {}",
        ].join("\n"),
      },
    },
```

Update the grep fixture data to include:

```js
matches: [{ path: "src/parser.c", line: 4, text: "line 4 reveal target" }]
```

Update an assistant or command result markdown body to include:

```md
[src/parser.c:4](src/parser.c#L4)
```

Update the review finding to include:

```js
file: "src/parser.c",
line: 4,
```

- [ ] **Step 4: Load previews into store for the visual action**

In `src/embedagent/frontend/gui/webapp/src/store.js`, inside `case "visual_timeline_fixture_loaded":`, merge `action.previews` into `filePreviewsByPath`:

```js
      const previewEntries = Object.entries(action.previews || {}).reduce((acc, [path, preview]) => {
        acc[path] = {
          status: "loaded",
          path,
          title: preview.title || path,
          content: preview.content || "",
          kind: preview.kind || "file",
          error: "",
        };
        return acc;
      }, {});
```

Then include:

```js
        filePreviewsByPath: {
          ...state.filePreviewsByPath,
          ...previewEntries,
        },
```

- [ ] **Step 5: Extend visual runner**

In `scripts/gui-visual-debug.mjs`, after expanding the timeline fixture in `runTimelineScenario(page)`, click the grep detail link or markdown link:

```js
  const fileLink = page.locator('[data-testid="timeline-tool-file-link--src/parser.c"]').first();
  if (await fileLink.count()) {
    await fileLink.click();
  } else {
    await page.locator('[data-testid="timeline-file-link--src/parser.c"]').first().click();
  }
  await page.waitForSelector('[data-testid="right-panel-file-surface"]', { timeout: 10000 });
  await page.waitForSelector('[data-file-link-reveal]', { timeout: 10000 });
  const timelineLinkRevealState = await page.evaluate(() => {
    const revealed = Array.from(document.querySelectorAll("[data-file-link-reveal]"));
    const target = document.querySelector('[data-file-line="4"]');
    const gutter = document.querySelector('[data-file-line-number="4"]');
    return {
      count: revealed.length,
      targetText: target?.textContent || "",
      gutterText: gutter?.textContent || "",
    };
  });
  if (timelineLinkRevealState.count !== 2 || !timelineLinkRevealState.targetText.includes("line 4 reveal target")) {
    throw new Error(`Timeline file link did not reveal target line: ${JSON.stringify(timelineLinkRevealState)}`);
  }
```

Return `timelineLinkRevealState` in the timeline result object.

- [ ] **Step 6: Run tests and visual scenario**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
cd ../../../../../
node scripts/gui-visual-debug.mjs --scenario timeline --output "$env:TEMP\embedagent-timeline-file-link-visual"
```

Expected: PASS, with `results.timeline.timelineLinkRevealState.count === 2`.

- [ ] **Step 7: Commit fixture and visual verification**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js src/embedagent/frontend/gui/webapp/src/store.js scripts/gui-visual-debug.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-fixtures.test.mjs src/embedagent/frontend/gui/webapp/test/visual-debug-runner.test.mjs
git commit -m "test: verify timeline file link reveal"
```

---

### Task 5: Build Assets And Update Documentation

**Files:**
- Modify: `src/embedagent/frontend/gui/static/assets/app.js`
- Modify: `src/embedagent/frontend/gui/static/assets/app.css`
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Build static assets**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: PASS and generated static assets update under `src/embedagent/frontend/gui/static/assets/`.

- [ ] **Step 2: Run final verification**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
cd ../../../../../
uv run pytest tests/test_gui_backend_api.py tests/test_gui_runtime.py -v
node scripts/gui-visual-debug.mjs --scenario timeline,file --output "$env:TEMP\embedagent-t3-file-link-final"
```

Expected:
- `npm test` passes.
- Python GUI backend/runtime tests pass.
- Visual runner reports no console warnings/errors.
- `results.timeline.timelineLinkRevealState.count === 2`.
- `results.file.revealState.count === 2`.

- [ ] **Step 3: Update docs**

Update:

```md
docs/modules/frontend-gui.md
docs/development-tracker.md
docs/design-change-log.md
```

Record that timeline markdown links, grep match rows, changed-file rows, and review findings can open the right-panel file preview with T3-style line reveal. State explicitly that this is GUI-local app-shell behavior and does not write transcript history, change workflow state, or touch Agent Core.

- [ ] **Step 4: Final commit**

```bash
git add src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css docs/modules/frontend-gui.md docs/development-tracker.md docs/design-change-log.md
git commit -m "docs: record T3 timeline file link parity"
```

---

## Self-Review

- Spec coverage: This plan directly follows T3code's pattern of routing file links into `openFile(..., line)` and reuses the already-landed right-panel reveal behavior.
- Boundaries: All implementation work is under the GUI app-shell, frontend tests, visual debug harness, generated static assets, and docs. No Agent Core, backend protocol, workflow package, permission policy, or transcript reducer changes are required.
- Placeholders: No TBD/TODO steps; every task has exact files, code shape, commands, and expected outcomes.
- Risk: The markdown href parser is intentionally narrow. It should treat remote URLs and hash-only anchors as normal browser links and only capture workspace-relative file paths.

