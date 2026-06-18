# T3 Timeline Rich Projection And Responsive Shell Design

## Goal

Make the GUI timeline and workbench shell feel much closer to `reference/t3code` while keeping Agent Core small, workflow-neutral, and independent from GUI display concerns.

The first implementation slice focuses on the most visible current gaps:

- thinking and reasoning content must be visible in the T3-style timeline renderer
- timeline event types need richer frontend formatting instead of falling back to plain system rows
- settled, running, interrupted, and failed turns should fold and expand like T3 Code
- narrow and zoomed layouts should not clip the timeline, composer, header, or right panel
- all changes must stay in the GUI app shell and frontend-local read models

## Current Baseline

The GUI has already moved toward a T3 Code-style workbench:

- `src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js` projects session turn groups into T3-like rows.
- `src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx` renders the newer row model when rows exist.
- `Timeline.jsx` still carries a legacy grouped renderer fallback with richer support for `reasoning`, `compact`, command results, and review cards.
- `App.jsx` owns bootstrap loading, WebSocket handling, active-session event handling, runtime projection, workbench actions, terminal actions, and rendering composition.
- The GUI backend already forwards `reasoning_delta` and `thinking_state` WebSocket events.

The most important bug is therefore frontend-side: live reasoning exists in state, but `projectT3TimelineRows(...)` does not currently project `kind: "reasoning"` into the active T3 row renderer, so thinking appears invisible once the T3 renderer path is active.

## Reference Findings

The relevant T3 Code reference structure is not a one-to-one backend contract. It is a frontend app architecture:

- `reference/t3code/apps/web/src/session-logic.ts` derives work log entries from activity records.
- `reference/t3code/apps/web/src/components/chat/MessagesTimeline.logic.ts` merges messages, work entries, proposed plans, diff summaries, and working indicators into timeline rows.
- `reference/t3code/apps/web/src/components/chat/MessagesTimeline.tsx` keeps row rendering focused and controlled by timeline row state.
- `reference/t3code/apps/web/src/rightPanelStore.ts` keeps workbench surface state frontend-local.

The useful lesson for this repository is the boundary, not the full product scope: GUI should own display read models and surface state, while Agent Core should continue emitting session truth through the existing protocol.

## Product Principles

1. Agent Core remains small and Pi-like.
2. GUI display semantics stay outside Agent Core.
3. `transcript.jsonl -> Session -> SessionHistoryAssembler -> /api/sessions/{id}/bootstrap` remains session-history truth.
4. `timeline.jsonl` remains transport/replay infrastructure.
5. T3 parity is implemented as GUI app-shell read models and components.
6. No new runtime dependency may weaken Windows 7 or offline bundle constraints.
7. Development-only visual fixtures must not become product protocol.

## Scope

### In Scope

- Extend `t3-timeline.js` with explicit row kinds for reasoning/thinking, compact boundaries, command results, review results, and richer system notices.
- Keep work/tool rows as frontend-local projections over existing tool/timeline items.
- Preserve turn folding behavior where settled work is folded behind a summary, while running, failed, interrupted, discarded, and active-turn work remains visible.
- Add a visible active thinking row when the session is running but no reasoning text has arrived yet.
- Make `TimelineRows.jsx` render the new row kinds.
- Move renderer coverage that currently exists only in the legacy grouped renderer into the T3 row renderer path.
- Tighten CSS for zoom and narrow widths using stable grid tracks, `minmax(0, 1fr)`, controlled overflow, and wrapping/truncation where needed.
- Add focused webapp tests for projection, row UI state, and source-level visual fixture contracts.
- Rebuild GUI static assets if webapp source changes.
- Update durable docs for GUI-only T3 parity progress.

### Out Of Scope

- Agent Core changes.
- New product HTTP or WebSocket APIs.
- Permission policy changes.
- Tool execution changes.
- Workflow package changes.
- Transcript, runtime reducer, operation reducer, compaction reducer, or recovery reducer changes.
- Source-control mutations, checkpoints, push/pull, stage, or commit surfaces.
- Electron, Tailwind, shadcn, LegendList, or any dependency copied from T3 Code.
- Full replacement of `App.jsx` in this first slice.

## Recommended Approach

Use a frontend-local T3 timeline read model with controlled rendering and layout polish.

### Option A: Patch Individual Components

Patch `TimelineRows.jsx`, `WorkRow.jsx`, and CSS directly.

Pros:

- Smallest immediate diff.
- Fast for one bug.

Cons:

- Keeps row semantics scattered.
- Does not move the GUI toward T3's architecture.
- Makes future rich event types harder to test.

### Option B: Frontend-Local Row Model Expansion

Extend `t3-timeline.js` as the single GUI projection layer, add row renderers for each visible timeline concept, and keep UI state in `timeline-ui-state.js`.

Pros:

- Matches T3's frontend architecture shape.
- Keeps Agent Core clean.
- Pure projection functions are easy to test.
- Lets rendering become feature-complete without backend protocol creep.

Cons:

- Slightly more frontend code than a one-off patch.

### Option C: Backend-Enriched Timeline Payloads

Add backend snapshot fields or new event kinds specifically for GUI rows.

Pros:

- Could reduce frontend heuristics.

Cons:

- Thickens backend/Core boundaries for display-only semantics.
- Risks creating a second session-history interpretation.
- Conflicts with the project architecture rules.

Recommendation: use Option B.

## Architecture

### Frontend Timeline Domain

`src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js` should become the GUI-owned row projection boundary for the T3 renderer.

It should expose:

- row kind constants
- pure helpers for changed-file summaries and diff stats
- row normalization helpers for work entries
- projection from turn groups to display rows
- no backend calls
- no permission decisions
- no Agent Core imports

The expanded row vocabulary should include:

- `message`
- `work`
- `turn_fold`
- `interaction`
- `diff_summary`
- `thinking`
- `reasoning`
- `compact`
- `command_result`
- `review_result`
- `system_notice`
- `working`

### Timeline UI State

`src/embedagent/frontend/gui/webapp/src/session-runtime/timeline-ui-state.js` remains the owner of frontend-local row expansion state.

It should be extended only when necessary to cover new expandable row kinds:

- `reasoning` defaults open while streaming and collapsed after completion
- `compact` stays compact by default
- `command_result` opens by default on failure if details exist
- `work` keeps the current error/running/interrupted defaults

This state must remain transient GUI state and must not be stored in session history.

### Timeline Rendering

`src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx` should render every row kind emitted by `projectT3TimelineRows(...)`.

Responsibilities:

- route each row kind to a focused component
- pass controlled expansion state
- keep markdown rendering in the message and command/review components
- keep action callbacks, such as `onOpenDiff`, explicit
- avoid querying backend state directly

`WorkRow.jsx` remains focused on one or more tool/work entries. It should not become a generic timeline renderer.

### Active Thinking

Active thinking display should be derived in the GUI from existing state:

- live `reasoning_delta` produces a `reasoning` row
- `thinking_state(active=true)` with no visible reasoning row produces a `thinking` row
- the row disappears or converts naturally when reasoning text, tool activity, or assistant text arrives

No new Core event is needed.

### Responsive Workbench Shell

The first layout pass should fix current zoom/narrow issues without a full redesign:

- header groups may wrap or hide low-priority metadata before clipping controls
- timeline content must use a constrained readable width but never force horizontal overflow
- main center, right panel, and bottom drawer tracks should use `minmax(0, 1fr)` and stable min heights
- composer controls should wrap or compact under narrow width
- right-panel tabs should remain horizontally scrollable instead of squeezing text into overlap

The shell should remain plain CSS and React.

## Data Flow

1. Backend/Core emits the existing session bootstrap and WebSocket events.
2. `App.jsx` updates current frontend state as it does today.
3. `projectSessionRuntime(...)` merges bootstrap timeline, live timeline items, event-log interactions, and snapshot pending interaction state.
4. `projectT3TimelineRows(...)` converts turn groups into display rows.
5. `Timeline.jsx` maintains local expansion/anchor state.
6. `TimelineRows.jsx` renders all row kinds.
7. User interactions update only GUI-local UI state or call existing explicit GUI callbacks.

## Testing Strategy

### Webapp Unit Tests

Extend `src/embedagent/frontend/gui/webapp/test/t3-timeline.test.mjs`:

- reasoning items project to `reasoning` rows
- streaming reasoning defaults visible
- active thinking without reasoning projects to `thinking`
- compact items project to `compact`
- command results project to `command_result`
- review command results project to `review_result`
- interaction rows dedupe against pending snapshot interactions
- failed/running/interrupted work remains outside closed turn folds

Extend `timeline-ui-state.test.mjs`:

- row keys are stable for new row kinds
- reasoning and command-result default expansion behaves as designed
- user toggles survive row updates

### Source Contract Tests

Extend existing webapp tests where appropriate:

- visual debug fixture source exposes timeline and interaction hooks only under visual debug mode
- `TimelineRows.jsx` handles every exported `T3_ROW_KINDS` value
- layout CSS contains the responsive guardrails for center/right/sidebar tracks

### Build And Focused Backend Tests

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
cd ../../../../../
uv run pytest tests/test_gui_workspace_registry.py tests/test_gui_app_host.py tests/test_gui_launcher_app_mode.py tests/test_gui_backend_api.py -q
```

### Rendered Visual QA

Use the existing dev-only visual harness:

```bash
node scripts/gui-visual-debug.mjs --scenario timeline,interaction,responsive --no-build --output "$env:TEMP\embedagent-t3-rich-timeline"
```

If the app server or browser runtime is unavailable, record the blocker and keep the unit/build proof explicit.

## Documentation

Update durable source-of-truth docs after implementation:

- `docs/modules/frontend-gui.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

The docs should state:

- this is GUI app-shell work
- no Agent Core semantics changed
- T3 parity is implemented through frontend-local read models
- visual fixtures are development-only

## Risks And Mitigations

### Risk: T3 Parity Becomes Scope Creep

Mitigation: limit the first implementation slice to timeline projection, renderer coverage, and responsive shell fixes. Keep source-control mutations, checkpointing, mobile, cloud, and remote features out of scope.

### Risk: Frontend Projection Duplicates Session Truth

Mitigation: projection rows are display-only and derived from existing bootstrap/live state. They do not write session history, workflow state, runtime reducers, permission policy, or transcript events.

### Risk: Reasoning Text Exposes Unexpected Provider Content

Mitigation: render only reasoning already present in existing session/bootstrap/live frontend state. Do not add new persistence, diagnostics, or backend export paths.

### Risk: Layout Fixes Regress Desktop Density

Mitigation: test desktop and narrow viewports, keep dense workbench layout, and avoid marketing-style cards or oversized decorative UI.

## Success Criteria

- Live thinking is visible in the active T3 timeline renderer.
- Reasoning content appears as a collapsible T3-style row.
- Compact, command, review, interaction, system, diff, work, and message rows all have rich renderers in the T3 path.
- Running, failed, interrupted, and discarded work is not hidden behind a closed settled-turn fold.
- Timeline and composer remain usable at narrow widths and zoomed desktop sizes.
- Webapp tests and build pass.
- Focused GUI backend tests pass.
- Static GUI assets are rebuilt.
- No Agent Core, permission policy, workflow package, runtime reducer, transcript truth, or offline runtime contract change is needed.
