# T3 Right Panel Editor/Diff Chrome Design

## Goal

Copy the T3 Code right-panel file and diff surface chrome into the GUI app shell so file previews and diffs feel like the same standalone app experience, while keeping Agent Core minimal and untouched.

## Source Of Truth

T3 Code is the standard answer. The reference files for this slice are:

- `reference/t3code/apps/web/src/components/files/FilePreviewPanel.tsx`
- `reference/t3code/apps/web/src/components/DiffPanelShell.tsx`
- `reference/t3code/apps/web/src/components/DiffPanel.tsx`
- `reference/t3code/apps/web/src/components/RightPanelTabs.tsx`

The slice copies the surface-level chrome and state shape that can be implemented in the current offline React shell. It does not introduce T3's `@pierre/diffs` editor runtime, Electron APIs, browser preview runtime, context menus, or online/editor integrations.

## File Surface

The current `FilePreviewSurface` already owns GUI-local preview state, breadcrumbs, markdown/source mode, and line reveal. This slice changes the visible chrome to match T3's `FilePreviewPanel` more closely:

- a compact `surface-subheader` at the top of the surface
- horizontally scrollable breadcrumbs that keep the current file visible
- icon-style action buttons for open, markdown preview/source toggle, and file explorer
- code/markdown content below the subheader with no nested inspector tabs
- existing file-link reveal behavior retained

The action buttons are app-shell controls. The open action exposes the workspace-relative path to the browser clipboard when available; it does not call external editors. The explorer action opens the existing `files` surface. Markdown toggle keeps the current local markdown/source mode behavior.

## Diff Surface

The current `DiffPanel` already renders a diff surface and file rail. This slice changes the chrome toward T3's `DiffPanelShell` and `DiffPanel`:

- a shared `surface-subheader` shell
- a chip strip that names the current diff selection
- icon-style controls for stacked/split rendering, line wrapping, and whitespace mode
- a collapsible T3-like changed-file rail
- a scrollable patch viewport whose focused file remains visible

The current diff backend remains a local/offline app-shell view over already available diff text. Split mode is a presentation mode over the existing renderer. Whitespace mode is GUI-local display state for this slice and does not ask Agent Core or Git to recompute diffs.

## Boundaries

This is GUI app-shell work only:

- no Agent Core changes
- no transcript/session truth changes
- no workflow state changes
- no permission policy changes
- no source-control mutations
- no runtime dependency on Docker, WSL, VS Code, Electron, Node at runtime, or network services

## Testing

The slice must be test-first:

- webapp source/helper tests lock the new T3 chrome selectors and state strings
- visual debug verifies file and diff surfaces render the subheader controls, scroll correctly, and avoid right-panel tab overlap
- focused Python GUI tests still pass because the backend contract is unchanged

