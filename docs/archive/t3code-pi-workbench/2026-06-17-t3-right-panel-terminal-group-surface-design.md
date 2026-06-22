# T3 Right Panel Terminal Group Surface Design

## Goal

Add the next T3 Code right-panel surface slice by making terminal surfaces own their terminal group state in the right panel, including split panes and active pane selection.

This continues the approved direction: copy T3 Code's right-panel design from `reference/t3code`, keep the GUI as an independent app shell, and keep Agent Core minimal, Pi-like, and replaceable.

## Source Design

The target behavior comes from:

- `reference/t3code/apps/web/src/rightPanelStore.ts`
- `reference/t3code/apps/web/src/rightPanelStore.test.ts`
- `reference/t3code/apps/web/src/components/ChatView.tsx`
- `reference/t3code/apps/web/src/components/ThreadTerminalDrawer.tsx`
- `reference/t3code/apps/web/src/terminalUiStateStore.ts`

The important T3 semantics for this slice are:

- A terminal right-panel surface is resource-specific, with an id derived from the first terminal session id.
- A terminal surface stores `terminalIds`, `activeTerminalId`, and optional `splitDirection`.
- Opening a terminal creates one surface per terminal session.
- Splitting a terminal adds a new terminal id to the existing terminal surface and activates it.
- Activating a terminal pane updates only that terminal surface's `activeTerminalId`.
- Closing a terminal pane removes it from the surface; closing the final pane removes the surface while keeping the right panel open.
- Vertical split stores `splitDirection: "vertical"`; the absence of that field means the default horizontal split.
- The right-panel terminal panel uses the same terminal runtime sessions as the drawer, but the right-panel surface state is not the bottom drawer state.

## Scope

Implement T3-style right-panel terminal group surfaces for the local/offline GUI.

In scope:

- Extend `terminal` right-panel surface descriptors with `terminalIds`, `activeTerminalId`, and optional `splitDirection`.
- Add pure workbench reducer actions for opening terminal surfaces, splitting terminal panes, activating terminal panes, and closing terminal panes.
- Route right-panel terminal actions through the existing GUI terminal backend APIs.
- Render right-panel terminal surfaces as surface-scoped groups or panes instead of a single global active terminal view.
- Keep bottom drawer terminal behavior intact.
- Add focused model tests mirroring the relevant T3 right-panel terminal tests.
- Add a visual debug `terminal` scenario that validates the right-panel terminal surface and split layout.
- Update slice tracking docs after implementation.

Out of scope:

- Browser preview surfaces.
- Full T3 `terminalUiStateStore` parity for all drawer grouping behavior.
- xterm.js, full PTY behavior, terminal resize protocol, shell link previews, or terminal link routing.
- New backend terminal runtime semantics beyond opening, writing, clearing, restarting, and closing existing GUI terminal sessions.
- Source-control mutations, staging, commits, push, pull, checkpoints, or PR creation.
- New runtime dependencies, T3 package imports, Electron APIs, runtime Node requirements, online services, Docker, WSL, or VS Code integration.
- Agent Core, transcript, workflow, permission, runtime reducer, provider, extension, telemetry, or source-control checkpoint changes.

## Architecture

The feature is GUI-local and app-shell owned.

`src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js` owns shallow right-panel terminal surface descriptors:

- `id`
- `placement`
- `kind`
- `title`
- `resourceId`
- `terminalId`
- `terminalIds`
- `activeTerminalId`
- `splitDirection`

The descriptor stores terminal identity and panel layout only. Terminal process state, status, cwd, output buffer, and capabilities continue to live in `src/embedagent/frontend/gui/webapp/src/terminal/terminal-state.js` and the existing GUI backend terminal service.

`src/embedagent/frontend/gui/webapp/src/App.jsx` remains the bridge between right-panel UI actions and existing terminal routes:

1. Opening a right-panel terminal chooses or creates a terminal id.
2. The GUI backend opens that terminal for the current session.
3. The terminal snapshot updates GUI-local terminal runtime state.
4. The workbench reducer opens or updates the right-panel terminal surface.
5. Splitting creates another backend terminal session, then appends that id to the active terminal surface.
6. Activating a pane updates the surface's active terminal id and may also select that terminal in the shared runtime state for write/clear/restart calls.
7. Closing a pane closes the backend terminal session and removes that id from the surface.

Opening a right-panel terminal must not automatically open the bottom drawer. The right panel and bottom drawer may share backend terminal sessions, but they remain separate GUI surfaces.

No new backend route is required for the intended slice.

## User Experience Contract

The visible behavior should follow T3 Code:

- The right-panel add menu's `Terminal` action opens a terminal surface tab.
- Each standalone new terminal surface has a stable id based on its first terminal id.
- The terminal tab title is derived from the active terminal label where possible and otherwise remains `Terminal`.
- The terminal surface body shows the surface's terminal panes, not every known terminal session.
- The active pane is visually distinct.
- Split horizontal adds a terminal pane using the default split orientation.
- Split vertical adds a terminal pane and records `splitDirection: "vertical"` on the surface.
- Closing a non-final pane leaves the surface open and activates a remaining pane.
- Closing the final pane removes the terminal surface and leaves the right panel open.
- Existing right-panel close, close others, close to right, and close all behavior remains unchanged for the terminal surface as a whole.
- Bottom drawer terminal tabs continue to work as before.

Because this project must remain Windows 7/offline compatible, the terminal rendering remains a plain WebView2-compatible React/CSS surface over stdlib subprocess pipe output. The slice copies T3's surface and pane semantics, not T3's hosted terminal infrastructure or package stack.

## Data Flow

1. App/session bootstrap continue loading through existing routes.
2. `App.jsx` passes the active right-panel terminal surface to `RightPanelSurfaceBody`.
3. `RightPanelSurfaceBody` renders a right-panel terminal group component.
4. The terminal group component derives pane summaries and buffers from GUI-local terminal state by `surface.terminalIds`.
5. Pane toolbar actions call app-level handlers for new, split, split vertical, activate, send, clear, restart, and close.
6. Backend terminal responses and WebSocket terminal events update `terminal-state.js`.
7. Workbench terminal surface reducer actions update only right-panel surface layout state.

## Error Handling

Terminal failures remain visible as GUI notices and local pane empty states:

- If no session is active, opening or splitting a terminal reports the existing "open a session" notice and leaves right-panel state unchanged.
- If backend terminal open fails, the terminal surface is not created or split.
- If closing the backend terminal fails, the pane remains in the surface and a notice is shown.
- If a surface references a terminal id that is missing from terminal runtime state, the pane shows a local unavailable/closed state and remains closeable.
- Unknown terminal surface actions are ignored by the reducer.

No terminal failure should write transcript history, workflow state, permission policy, runtime reducers, telemetry, source-control checkpoints, provider configuration, extension loading state, or Agent Core policy.

## Testing

Use TDD for the implementation.

Required JavaScript tests under `src/embedagent/frontend/gui/webapp/test/`:

- Opening two terminal surfaces creates one surface per terminal session.
- Splitting a terminal pane appends the new terminal id to the existing surface and activates it.
- Activating a terminal pane changes only that surface's `activeTerminalId`.
- Closing a non-final pane removes it and chooses a remaining active pane.
- Closing the final pane removes the surface while keeping the right panel open.
- Vertical split records `splitDirection: "vertical"`.
- Right-panel terminal rendering consumes `surface.terminalIds` rather than the global terminal id list.
- Bottom drawer terminal rendering remains source-compatible with the existing terminal state.

Required verification:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Focused Python GUI/backend tests should be run because the implementation will use existing terminal backend routes:

```bash
uv run pytest tests/test_gui_terminal_api.py tests/test_gui_app_shell.py -v
```

Visual verification:

```bash
node scripts/gui-visual-debug.mjs --scenario terminal --no-build --output "$env:TEMP\embedagent-t3-terminal-surface" --viewports 1280x720,700x640
```

The final implementation should also keep the existing file and diff visual scenarios passing when practical:

```bash
node scripts/gui-visual-debug.mjs --scenario terminal,file,diff --no-build --output "$env:TEMP\embedagent-t3-terminal-surface" --viewports 1280x720,700x640
```

## Documentation

The implementation should update:

- `docs/development-tracker.md`
- `docs/design-change-log.md`

No global architecture source-of-truth change is expected because the GUI terminal app-shell boundary already exists and this slice stays inside it.

## Constraints

- Preserve Python `>=3.8,<3.9`.
- Do not introduce Python 3.9+ syntax in backend or tests.
- Do not add runtime dependencies.
- Do not modify `uv.lock` manually.
- Do not commit `config/config.json`.
- Keep GUI terminal surface state out of transcript history, workflow state, permission policy, runtime reducers, telemetry, source-control checkpoints, provider configuration, extension loading, and Agent Core.
- Continue using official vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`; do not reintroduce `code` or `todos`.

## Approval

The user approved this slice on 2026-06-17 after confirming the direction: directly copy T3 Code's right-panel terminal design, do not invent or adjust the design live.
