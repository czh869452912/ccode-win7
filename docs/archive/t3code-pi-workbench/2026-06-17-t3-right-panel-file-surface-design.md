# T3 Right Panel File Surface Design

## Goal

Add the next T3 Code right-panel surface slice by making workspace files open as first-class `file` surfaces in the GUI right panel, instead of loading them into the old Inspector preview state.

This continues the current direction: copy the T3 Code surface model from `reference/t3code`, keep the GUI as an independent app shell, and keep Agent Core minimal, Pi-like, and replaceable.

## Source Design

The target behavior comes from:

- `reference/t3code/apps/web/src/rightPanelStore.ts`
- `reference/t3code/apps/web/src/rightPanelStore.test.ts`
- `reference/t3code/apps/web/src/components/ChatView.tsx`
- `reference/t3code/apps/web/src/components/files/FilePreviewPanel.tsx`
- `reference/t3code/apps/web/src/components/RightPanelTabs.tsx`

The important T3 semantics for this slice are:

- `file` is a right-panel surface kind.
- Opening a file creates a stable surface id derived from the workspace-relative path.
- Reopening the same file reuses the existing surface and increments a reveal request.
- A file surface stores path and reveal metadata only; file content belongs to the file preview feature state.
- Opening a file from the standalone `files` explorer replaces that standalone explorer with peer file surfaces.
- `file` surfaces are opened by file actions, not by the generic add-surface menu.

## Scope

Implement `file` as a local/offline GUI right-panel surface.

In scope:

- Add `file` to the right-panel allowed surface kinds.
- Keep the add-surface menu limited to `diff`, `files`, `terminal`, and `plan`.
- Opening a file from `FilesSurface` opens or reuses a right-panel `file` tab.
- The file tab title is the basename of the workspace-relative file path.
- Store file preview contents in GUI-local state keyed by path.
- Render the active file surface through a new `FilePreviewSurface` component.
- Add focused model tests, source-assertion tests, and a visual debug `file` scenario.
- Update slice tracking docs after implementation.

Out of scope:

- Browser preview surfaces.
- Full T3 editor parity, inline comments, save coordination, markdown task editing, external editor picker, or virtualized large-file rendering.
- Terminal split surfaces.
- Source-control mutations, staging, commits, push, pull, checkpoints, or PR creation.
- New runtime dependencies, T3 package imports, Electron APIs, runtime Node requirements, online services, Docker, WSL, or VS Code integration.
- Agent Core, transcript, workflow, permission, runtime reducer, provider, extension, telemetry, or source-control checkpoint changes.

## Architecture

The feature is GUI-local.

`src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js` owns shallow right-panel surface descriptors:

- `id`
- `kind`
- `title`
- `resourceId`
- `filePath`
- `revealLine`
- `revealRequestId`

The descriptor must not store file contents. File contents live in `src/embedagent/frontend/gui/webapp/src/store.js` under GUI-local preview state keyed by workspace-relative path.

`src/embedagent/frontend/gui/webapp/src/App.jsx` remains the bridge from user action to existing GUI backend routes:

1. Open or reuse the `file` surface immediately.
2. Fetch file contents through the existing `/api/files/{path}` route.
3. Store success or failure in GUI-local file preview state.
4. Render the active surface through `RightPanelSurfaceBody`.

No new backend route is required for the intended slice.

## User Experience Contract

The visible behavior should follow T3 Code:

- Clicking a file in the right-panel file tree turns the right panel into a file tab for that path.
- Reopening the same file does not create duplicates.
- Opening another file adds another file tab to the same right-panel surface list.
- The `files` surface is removed when a file surface is opened from the standalone explorer, matching T3's replacement behavior.
- Closing a file tab uses the existing neighboring-surface fallback.
- The right-panel add menu does not show `file`.
- Empty right-panel actions still offer only `Diff`, `Files`, `Terminal`, and `Plan`.

## Constraints

- Preserve Python `>=3.8,<3.9`.
- Do not introduce Python 3.9+ syntax in backend or tests.
- Do not add runtime dependencies.
- Do not modify `uv.lock` manually.
- Do not commit `config/config.json`.
- Keep GUI file preview state out of transcript history, workflow state, permission policy, runtime reducers, telemetry, source-control checkpoints, provider configuration, extension loading, and Agent Core.
- Continue using official vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`; do not reintroduce `code` or `todos`.

## Testing

Use TDD for the implementation.

Required verification:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Visual verification:

```bash
node scripts/gui-visual-debug.mjs --scenario file --no-build --output "$env:TEMP\embedagent-t3-file-surface" --viewports 1280x720,700x640
```

Focused Python GUI/backend tests should be run if the implementation unexpectedly touches backend behavior. The intended slice should not need backend contract changes.

## Documentation

The implementation should update:

- `docs/development-tracker.md`
- `docs/design-change-log.md`

No global architecture source-of-truth change is expected because the GUI app-shell boundary already exists and this slice stays inside it.

## Approval

The user approved this slice on 2026-06-17 after confirming the direction: directly copy T3 Code's design, do not invent or adjust the design live.
