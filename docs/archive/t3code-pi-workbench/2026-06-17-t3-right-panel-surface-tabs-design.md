# T3 Right Panel Surface Tabs Design

## Goal

Move the GUI right panel from a fixed inspector-tab list toward the T3 Code surface-tab model, using `reference/t3code` as the design source of truth while preserving EmbedAgent's offline Windows 7 runtime and minimal Agent Core boundary.

## Source Design

The target interaction and layout come from:

- `reference/t3code/apps/web/src/components/RightPanelTabs.tsx`
- `reference/t3code/apps/web/src/components/AppSidebarLayout.tsx`
- `reference/t3code/apps/web/src/components/ThreadTerminalDrawer.tsx`
- `reference/t3code/apps/web/src/components/DiffPanel.tsx`
- `reference/t3code/apps/web/src/components/files/FileBrowserPanel.tsx`

This slice must copy the T3 surface concept rather than inventing a new panel design. A right panel contains an ordered list of open surfaces, an active surface id, close controls, an add-surface affordance, and an empty state for opening supported surfaces.

## Scope

Implement the first T3-style right-panel surface tab slice for local/offline GUI surfaces:

- `diff`
- `files`
- `terminal`
- `plan`

The slice replaces the current fixed right-panel tab strip with a surface list model. Existing EmbedAgent content panes can remain as the body implementations for this slice; the visible tab and surface behavior should follow T3.

Out of scope:

- Browser preview surfaces
- Cloud auth, hosted environments, provider account flows, and online relay behavior
- Source-control mutations, staging, commits, push, pull, checkpoints, or PR creation
- Electron-specific APIs, runtime Node requirements, xterm.js runtime dependency, or T3 package imports
- Agent Core changes beyond consuming existing frontend/core contracts

## Architecture

The GUI remains an app shell over the Agent Core. The surface tab model lives entirely in `src/embedagent/frontend/gui/webapp/src/workbench/` and React components under `src/embedagent/frontend/gui/webapp/src/components/workbench/`.

Agent Core continues to expose session bootstrap, snapshots, task projection, artifacts, file tree, terminal service, and diff/source-control data through existing backend routes. The right-panel surface state is GUI-local UI state and must not write transcript history, workflow state, permission policy, runtime reducers, source-control checkpoints, or extension loading state.

The implementation should adapt T3's typed `RightPanelSurface` idea to this JavaScript webapp:

- Each surface has a stable `id`
- Each surface has a `kind`
- Resource-specific surfaces may carry a `resourceId`, `filePath`, or active terminal id
- The active surface is selected by `activeSurfaceId`
- Closing active surfaces activates a neighboring surface using T3-like ordering behavior
- The add button opens supported local surfaces only

## Components

### Surface Model

`src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js` should become the single GUI-local model for right-panel surfaces.

It should provide:

- T3-style surface constructors for `diff`, `files`, `terminal`, and `plan`
- `createWorkbenchState()` with `rightPanel.surfaces`, `rightPanel.activeSurfaceId`, and `rightPanel.open`
- pure reducers for open, activate, close, close-others, close-to-right, and close-all
- stable fallback behavior when a requested surface kind is unavailable

### Right Panel Tabs

`src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx` should visually follow T3's `RightPanelTabs.tsx` structure:

- Horizontal top tabbar
- Compact surface tabs with icon, title, active state, and close button
- Add-surface button at the end of the tabbar
- Empty state that offers `Diff`, `Files`, `Terminal`, and `Plan`
- No fixed vertical list of all inspector categories

Because this project intentionally avoids adding new webapp dependencies for this slice, icons may use existing CSS/text treatment or small inline labels. Do not add `lucide-react`, Base UI, Tailwind, or T3 workspace packages.

### Body Projection

The right-panel body should continue rendering existing EmbedAgent panes through `Inspector` for this slice:

- `diff` maps to the current diff surface
- `files` maps to existing preview/file tree behavior where available
- `terminal` maps to existing terminal state, but can initially open the bottom drawer terminal or show a local terminal handoff panel if the current terminal component remains bottom-drawer owned
- `plan` maps to the current plan pane

This keeps the slice focused on the T3 surface shell behavior. Deeper T3 terminal split layout and file-browser parity can follow in later slices.

## Data Flow

1. App bootstrap and session bootstrap continue loading through existing routes.
2. `App.jsx` derives right-panel surface props from `state.workbench.rightPanel`.
3. User actions dispatch workbench reducer actions:
   - open surface
   - activate surface
   - close surface
   - close other surfaces
   - close surfaces to right
   - close all surfaces
4. Active surface kind controls which existing `Inspector` pane is shown.
5. Surface state remains in memory and is scoped to the GUI app shell.

## Error Handling

Unavailable local surfaces should fail closed in the UI:

- If no workspace is active, `files` and `diff` are disabled or open to an empty state.
- If no terminal session exists, `terminal` opens a surface with the existing new-terminal action.
- If no plan exists, `plan` opens the existing empty plan view.
- Unknown surface kinds are ignored by the reducer.

No surface action should call Agent Core directly except through already existing UI actions such as loading a diff, opening a file, or opening a terminal.

## Testing

Use TDD for behavior changes.

Add focused tests under `src/embedagent/frontend/gui/webapp/test/` for:

- opening a right-panel surface creates or reuses a stable surface
- activating a surface changes `activeSurfaceId`
- closing the active surface selects the next or previous remaining surface
- close-others, close-to-right, and close-all match T3-style tab behavior
- right-panel rendering no longer exposes the old fixed inspector tab list

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Then run focused Python GUI/backend tests only if backend contracts are touched. This slice should not require backend contract changes.

## Documentation

If implementation changes source-of-truth architecture assumptions, update:

- `docs/frontend-protocol.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

For the intended first slice, durable docs should only need a tracker/change-log note because the GUI app-shell boundary is already documented.

## Constraints

- Preserve Python `>=3.8,<3.9`
- Do not introduce runtime dependencies on Docker, WSL, VS Code, Electron, Node runtime, online services, or T3 packages
- Do not change Agent Core ownership
- Do not reintroduce `code` mode, `todos`, or stale harness/core compatibility aliases
- Keep GUI surface state out of transcript, workflow state, permission policy, runtime reducers, telemetry, source-control checkpoints, and extension loading

## Approval

The user approved this direction on 2026-06-17 with the constraint: copy T3 Code's design directly, do not invent or live-adjust the design. Engineering adaptation is allowed only to satisfy EmbedAgent's Windows 7, offline, Python 3.8, and minimal Agent Core constraints.
