# GUI Timeline Interaction Polish Design

## Goal

Make the next GUI slice improve the core day-to-day interaction quality of the T3code-style workbench without thickening Agent Core. The slice should focus on timeline work rows, turn folding, scroll stability, composer-local pending interaction surfaces, and Codex-operable visual fixtures.

## Current Baseline

The GUI now has:

- T3code-style timeline row projection in `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js`.
- Timeline rendering through `components/timeline/TimelineRows.jsx`, `WorkRow.jsx`, and `ChangedFilesCard.jsx`.
- Composer-local permission/user-input surface via `components/composer/ComposerInteractionPanel.jsx`.
- Right-panel Diff surface with file rail and focused diff viewport.
- Dev-only visual harness in `scripts/gui-visual-debug.mjs`, including app/load/chat/diff/responsive scenarios.

The current weak spots are not architecture gaps. They are interaction polish gaps:

- Work row expansion is local to each React component and is not fixture-testable.
- Turn fold behavior is functional but not close enough to T3code for active/running/error cases.
- Scroll anchoring is still mostly "stay at bottom" rather than robust anchoring through folds, streaming, and inserted rows.
- Visual debug fixtures cover diff but not rich timeline or composer interaction states.
- Pending permission/user-input UI has a surface, but the visual harness cannot yet inject and verify it deterministically.

## Product Principles

1. GUI shell follows T3code's interaction language.
2. Agent Core remains Pi-like: small, independent, read-model driven, and not coupled to GUI state.
3. Visual debug fixtures are development-only; they must not become product protocol, backend policy, or runtime dependency.
4. Windows 7/offline constraints remain unchanged. Use React, plain CSS, existing browser dev tooling, and existing test harnesses only.
5. Prefer narrow, reversible frontend-local state over new backend contracts.

## Scope

### In Scope

- Timeline work row expansion model.
- Turn fold defaults and active/running/error behavior.
- Scroll anchoring around fold toggles, streaming messages, new work rows, and composer interaction panels.
- T3-style status text and compact visual affordances for running, success, error, interrupted, and discarded work rows.
- Visual debug fixture hook expansion for timeline and composer interaction scenarios.
- Visual harness scenarios:
  - `timeline`
  - `interaction`
  - optional `diff-tree` if it is small enough after `timeline`
- Tests for the pure row projection and fixture entrypoint contracts.
- Documentation updates for the frontend GUI module and design/change tracker.

### Out Of Scope

- Agent Core changes.
- New HTTP/WebSocket product APIs.
- Real provider/model integration changes.
- Permission policy changes.
- Tool execution changes.
- TUI implementation work.
- Full diff editor features such as split/inline toggle, whitespace ignore, or open-in-editor. Those belong to a later diff polish slice.
- New runtime dependencies, Electron, Tailwind, shadcn, Docker, WSL, or online services.

## Recommended Approach

Use a frontend-local timeline interaction controller rather than pushing UI state into Agent Core.

### Approach A: Component-local polish only

Keep expansion and scroll handling inside `WorkRow`, `TurnFoldRow`, and `Timeline`.

Pros:

- Smallest diff.
- No new helper module.

Cons:

- Hard to test consistently.
- Visual fixtures cannot inspect or drive state cleanly.
- State behavior will stay scattered.

### Approach B: Frontend-local timeline UI model

Add a focused model under `webapp/src/session-runtime/` that derives stable row UI defaults and exposes reducer-style helpers for expansion and anchoring. Components keep rendering simple, and `App.jsx` or `Timeline.jsx` owns the local UI state.

Pros:

- Keeps Core clean.
- Makes behavior testable without a browser.
- Gives visual fixtures stable hooks to open rows, folds, and interaction states.
- Matches the current frontend-local workbench pattern.

Cons:

- Slightly more frontend code.

### Approach C: Backend-driven timeline UI state

Have backend snapshots carry row expansion and anchoring hints.

Pros:

- Could be shared across shells.

Cons:

- Violates the current boundary for UI-local behavior.
- Adds product protocol for display details.
- Risks thickening Agent Core.

Recommendation: use Approach B.

## Architecture

### Timeline UI Model

Create `src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js`.

Responsibilities:

- Build stable row keys from projected T3 rows.
- Compute default expansion state:
  - error/interrupted/discarded work rows open by default
  - running work rows visible and not hidden inside a closed fold
  - settled successful work rows fold when an assistant response follows
  - changed-files cards collapsed to directory summary by default
- Apply explicit user toggles without losing them when new rows stream in.
- Expose small pure functions:
  - `rowUiKey(row)`
  - `createTimelineUiState(rows, previousState)`
  - `toggleTimelineRow(state, rowKey)`
  - `shouldPinToBottom({ scrollTop, clientHeight, scrollHeight })`
  - `restoreAnchorScroll({ before, after, anchor })`

This module must not know about Agent Core, backend APIs, permission policy, or WebSocket events.

### Timeline Components

Modify the timeline component layer to consume the UI model:

- `Timeline.jsx` owns the local timeline UI state.
- `TimelineRows.jsx` passes explicit `expanded`, `onToggle`, and `rowKey` to `WorkRow` and turn fold rows.
- `WorkRow.jsx` becomes controlled by props instead of owning expansion entirely.
- `ChangedFilesCard.jsx` can keep its directory expansion local for this slice, unless it becomes needed for visual fixtures.

### Scroll Anchoring

Keep scroll anchoring inside `Timeline.jsx`:

- If the user is near the bottom, new rows keep the viewport pinned to the bottom.
- If the user is reading above the bottom and a row above changes height, preserve the first visible row anchor.
- Fold toggles should not jump the page unexpectedly.
- The behavior can be implemented with DOM measurements and requestAnimationFrame, but the decision helpers should be pure and tested.

### Visual Fixture Hook

Extend the existing dev-only hook exposed only under `?visual_debug=1`:

```js
window.__EMBEDAGENT_VISUAL_DEBUG__ = {
  openDiffFixture(...),
  loadTimelineFixture(...),
  loadInteractionFixture(...),
};
```

The hook should dispatch frontend-local actions or state fixtures only. It must not call backend tool execution, mutate Agent Core state, or create product protocol expectations.

### Visual Harness Scenarios

Extend `scripts/gui-visual-debug.mjs`:

- `timeline`
  - opens a fixture conversation with one user row, multiple work rows, one changed-files card, one assistant response, and one error row
  - clicks a folded work row
  - verifies expanded detail is visible
  - captures screenshot
  - verifies no right-panel tab overlap and no console warning/error
- `interaction`
  - opens a fixture pending permission or user-input card in the composer
  - verifies it is visible near the composer
  - clicks one safe UI action that does not touch backend policy
  - captures screenshot
- `diff-tree` only if the implementation stays small:
  - expands changed-files directories
  - opens the diff panel from a file row

## Data Flow

1. Existing runtime projection produces `runtimeState.t3TimelineRows`.
2. `Timeline.jsx` derives or updates `timelineUiState` from those rows.
3. Components render rows using controlled expansion props.
4. User toggles update only frontend-local UI state.
5. Visual fixture hooks inject deterministic rows or UI states when `visual_debug=1`.
6. Visual harness drives the real app through Playwright and captures screenshots.

## Testing Strategy

### Unit / Helper Tests

Extend `src/embedagent/frontend/gui/webapp/test/`:

- Add `timeline-ui-state.test.mjs`.
- Cover row key stability.
- Cover default expansion rules for running/error/success work rows.
- Cover toggles surviving row updates.
- Cover bottom pinning threshold.
- Cover anchor restoration math.

### Source Contract Tests

Extend `run-tests.mjs`:

- Assert visual fixture hook names exist.
- Assert timeline scenario is present in `SCENARIOS`.
- Assert `WorkRow` is controlled by props rather than only local state.

### Visual Harness Tests

Extend `visual-debug-runner.test.mjs`:

- `parseScenarioList("timeline,interaction")`.
- Source includes `loadTimelineFixture`.
- Source includes `loadInteractionFixture`.

### Rendered Verification

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q
node scripts/gui-visual-debug.mjs --scenario app,load,chat,diff,responsive,timeline,interaction --no-build
```

## Documentation

Update:

- `docs/modules/frontend-gui.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

The docs must explicitly say the fixture hook is development-only and not a frontend protocol or Agent Core capability.

## Risks

- Overfitting fixture rows to the UI instead of real session projections.
  - Mitigation: keep pure projection tests against realistic row shapes and keep existing chat/diff scenarios.
- Scroll anchoring becoming flaky in Playwright.
  - Mitigation: test pure decision helpers separately and keep visual assertions simple.
- Component state refactor causing regressions in existing timeline rendering.
  - Mitigation: convert one row type at a time and keep screenshots in every implementation task.
- Accidental protocol creep through fixture hooks.
  - Mitigation: expose hooks only under `visual_debug=1` and document that they are development-only.

## Success Criteria

- Timeline work row expansion is controlled, predictable, and tested.
- Running/error rows are visible in the expected T3-style locations.
- Fold toggles and streamed row insertion do not cause obvious viewport jumps.
- `timeline` and `interaction` visual scenarios exist and pass.
- Full visual harness with app/load/chat/diff/responsive/timeline/interaction passes with zero console warning/error.
- No Agent Core, permission policy, workflow package, or runtime dependency changes are required.
