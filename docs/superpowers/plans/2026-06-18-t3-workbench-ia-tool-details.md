# T3 Workbench IA And Tool Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the GUI closer to T3 Code by removing duplicate left-side file browsing, rendering timeline tool details as structured UI, and verifying primary scroll regions.

**Architecture:** Keep the projector as the work-row normalization boundary and add a `detailModel` consumed by focused timeline components. Keep file browsing in the right-panel surface while the left sidebar owns workspace/thread navigation. Keep all changes in GUI webapp, GUI tests, static assets, and docs.

**Tech Stack:** React, Vite, Node-based frontend tests, existing GUI visual debug harness, Python GUI backend tests where needed.

---

### Task 1: Timeline Tool Detail Model

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`
- Test: `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`

- [ ] Write failing tests for representative tool rows that require a `detailModel`.
- [ ] Run the focused frontend helper tests and confirm the new tests fail because `detailModel` is missing or raw JSON is used.
- [ ] Add minimal projector helpers that build structured detail sections from public args, data, errors, output, diff previews, and changed files.
- [ ] Rerun the focused tests and confirm they pass.

### Task 2: Timeline Tool Detail Rendering

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] Write failing source/component checks that expanded work rows use semantic detail classes and do not default to raw JSON `<pre>` for ordinary tool data.
- [ ] Run frontend tests and confirm failure.
- [ ] Add `ToolDetail` and wire `WorkRow` to render `row.detailModel`, preserving text fallback only for plain string/error details.
- [ ] Add compact CSS for metadata fields, output blocks, diff previews, and changed files.
- [ ] Rerun frontend tests and confirm pass.

### Task 3: Sidebar File Tree Ownership

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] Write failing tests asserting the left sidebar no longer exposes `sidebar-tab--files` or `file-tree-node--*`.
- [ ] Run frontend tests and confirm failure.
- [ ] Remove the left Files tab/render path and file-tree props from `Sidebar`.
- [ ] Keep right-panel Files commands and `FilesSurface` behavior intact.
- [ ] Rerun frontend tests and confirm pass.

### Task 4: Scroll Layout Contract

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `scripts/gui-visual-debug.mjs`
- Test: visual harness output

- [ ] Add visual/debug assertions for scrollable timeline/thread/right-panel/file regions and absence of the left file tree.
- [ ] Run the visual harness and confirm the new assertions fail before CSS/DOM fixes if necessary.
- [ ] Adjust CSS so primary content regions have stable min-height and usable vertical scrolling.
- [ ] Rerun visual harness and confirm pass at desktop and responsive scenarios.

### Task 5: Build Assets And Docs

**Files:**
- Modify: `src/embedagent/frontend/gui/static/assets/app.js`
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] Run `npm test`.
- [ ] Run `npm run build`.
- [ ] Run focused GUI backend tests if frontend protocol assumptions changed.
- [ ] Refresh docs to record the GUI-only boundary and remaining T3 parity gaps.
- [ ] Commit the completed slice.
