# T3 Command Palette Root And Submenu Design

## Goal

Move the GUI command palette from a flat command filter toward T3 Code's command palette experience.

This is the next highest-value T3 parity slice because the palette is the global command/navigation entry point. The implementation should copy T3's command palette interaction shape while preserving EmbedAgent's offline, Windows 7, Python 3.8, GUI-app-shell, and minimal Agent Core boundaries.

## Source Design

The target behavior comes from:

- `reference/t3code/apps/web/src/components/CommandPalette.tsx`
- `reference/t3code/apps/web/src/components/CommandPaletteResults.tsx`
- `reference/t3code/apps/web/src/components/CommandPalette.logic.ts`
- `reference/t3code/apps/web/src/components/ui/command.tsx`
- `reference/t3code/apps/web/src/keybindings.ts`

Important T3 semantics for this slice:

- The command palette is a modal command surface, not a simple dropdown.
- Results are grouped and have rich rows: icon/leading marker, title, description, trailing metadata, shortcut hint, and submenu chevron.
- The palette has view state: root view and submenu view.
- Root view mixes actions with navigation-ish entries such as recent threads/workspaces.
- Search ranking is applied to structured item search terms rather than one flat string.
- Keyboard handling owns highlight movement, execute, close, and return from submenu.

## Current State

Current GUI implementation:

- `src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx`
  - Flat `visibleCommands(context).filter(matchesQuery)` list.
  - No group model.
  - No submenu view.
  - No row description/timestamp/shortcut/trailing status.
  - No palette-owned keyboard handling for up/down/enter/backspace.
- `src/embedagent/frontend/gui/webapp/src/workbench/commands.js`
  - Existing workbench command metadata.
  - Good source for action items, labels, groups, slash metadata, and visibility.
- `src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js`
  - Existing keybinding truth for shortcut display.
- `src/embedagent/frontend/gui/webapp/src/store.js` / `surfaces.js`
  - Palette state currently tracks `open`, `query`, and `selectedIndex`.
- `App.jsx`
  - Owns command execution and already has access to `state.sessions`, workspace state, current session, current status, and `commandContext`.

## Scope

Implement a GUI-local T3-style command palette root/submenu/results experience.

In scope:

- Add a pure command-palette model helper that projects GUI state into grouped palette items.
- Render grouped root results with T3-like rows: label, description, slash/id metadata, optional shortcut, optional timestamp/status, and submenu chevron.
- Add a submenu view for grouped command categories. Selecting a category opens a second palette view filtered to that group's commands.
- Add recent thread entries using existing `state.sessions` data and current session identity.
- Add workspace entries using existing app-shell workspace registry state.
- Add keyboard support inside the palette:
  - `ArrowDown` / `ArrowUp` changes highlighted item.
  - `Enter` executes highlighted action or opens highlighted submenu.
  - `Escape` closes the palette.
  - `Backspace` with an empty query returns from submenu to root.
- Add stable empty states for root and submenu search.
- Add visual debug coverage for root groups, submenu navigation, keyboard highlight, enter execution, and narrow viewport overflow.
- Keep existing command execution paths: command items still call `onSelect(command)` and route through `executeWorkbenchCommand(commandById(...))`.
- Keep session/workspace entries GUI-local. If an entry maps to an existing app action, execute that existing callback only through `App.jsx` props.

Out of scope:

- Remote clone flows.
- Git URL / GitHub / GitLab / Bitbucket / Azure DevOps providers.
- Real filesystem browse mode.
- Runtime source-control mutation.
- Branch/worktree mutation.
- New backend routes.
- New Agent Core command semantics.
- New transcript, workflow, provider, permission, telemetry, or reducer truth.
- Online services, runtime dependency installation, Electron, Docker, WSL, VS Code, or runtime Node.

## Architecture

Add focused frontend modules:

- `webapp/src/workbench/command-palette-model.js`
  - Defines palette item/group projection and search ranking.
  - Builds root groups from workbench commands, sessions, and workspaces.
  - Builds submenu groups from command group metadata.
  - Stays pure and dependency-free.
- `webapp/src/components/workbench/CommandPaletteResults.jsx`
  - Renders grouped result rows.
  - Does not fetch, execute commands, read App state, or know Agent Core.
- `webapp/src/components/workbench/CommandPalette.jsx`
  - Owns local view stack (`root` / `submenu`) and highlighted item index.
  - Receives projected input data and callbacks through props.
  - Keeps existing modal shell but upgrades layout and keyboard behavior.

Modify:

- `App.jsx`
  - Pass existing sessions, workspace registry, active session/workspace, keybindings, and callbacks needed by palette items.
  - Keep actual execution routing in `App.jsx`.
- `store.js` / `surfaces.js`
  - Keep the existing palette state small. Only add view/query fields if local component state is insufficient for testability.
- `styles.css`
  - Replace flat-list palette styling with T3-like grouped modal/result rows.
- Visual debug fixtures/runner
  - Add deterministic session/workspace data for palette visual checks if existing fixtures are not stable enough.

## User Experience Contract

Root palette:

- Opens centered over the app using the existing `Cmd` button and `mod+k`.
- Input autofocuses.
- Root results are grouped:
  - Commands
  - Sessions
  - Workspaces
  - Views/Surfaces
- Rows show primary text and useful secondary context.
- Shortcuts appear where an existing keybinding maps to the command.
- The highlighted row is visually obvious and keyboard-driven.
- Empty state says no matching commands, sessions, or workspaces.

Submenu:

- Category rows in root can open a submenu view.
- Submenu header shows a back affordance and the submenu title.
- Backspace on an empty submenu query returns to root.
- Escape closes the palette.
- Enter executes the highlighted action.

Execution:

- Command rows execute through existing command IDs.
- Session rows call existing session activation logic.
- Workspace rows call existing workspace activation logic.
- Items that cannot execute in the current state are shown disabled or omitted according to the existing command visibility contract.

## Data Flow

1. `App.jsx` collects current GUI app-shell state:
   - visible commands via `visibleCommands(commandContext)`
   - sessions from `state.sessions`
   - active session id from `state.currentSessionId`
   - workspaces from `state.app.workspaces`
   - active workspace from `state.app.activeWorkspace`
   - keybindings from `DEFAULT_KEYBINDINGS`
2. `CommandPalette.jsx` passes this data into `command-palette-model.js`.
3. Model helper returns grouped root/submenu item descriptors.
4. `CommandPaletteResults.jsx` renders descriptors.
5. Selecting a descriptor calls one of the explicit callbacks supplied by `App.jsx`.
6. `App.jsx` performs existing command/session/workspace actions.

No palette item writes transcript history, workflow state, permission state, provider config, runtime reducers, telemetry, or source-control state directly.

## Error Handling

- Missing sessions/workspaces produce empty groups, not errors.
- Malformed session/workspace records are ignored by the model helper.
- Empty search results render an empty state.
- Disabled actions show disabled rows and do not call callbacks.
- If a selected command id no longer resolves through `commandById`, the palette closes only if App's existing command execution path does so; the palette component does not invent policy.

## Testing

Required focused tests under `src/embedagent/frontend/gui/webapp/test/`:

- `command-palette-model.test.mjs`
  - Builds grouped root items from commands, sessions, and workspaces.
  - Filters/ranks by command label, slash text, session title, workspace label/path, and command group.
  - Produces submenu groups for command categories.
  - Ignores malformed session/workspace entries.
  - Marks current session/workspace rows with trailing metadata.
- `command-palette-source.test.mjs`
  - Confirms `CommandPalette.jsx` uses `CommandPaletteResults`, submenu state, keyboard handlers, and model helpers.
  - Confirms palette components do not call `fetch(`, mention transcript truth, or import backend/Core modules.
- Existing `run-tests.mjs`
  - Registers the new tests.
  - Updates static assertions for the richer palette components.
- `visual-language-css.test.mjs`
  - Asserts grouped palette classes, row metadata, shortcut styling, submenu header, and mobile guardrails.
- `visual-debug-runner.test.mjs`
  - Adds a `palette` visual scenario and asserts root/submenu/keyboard terms exist in the runner.

Required verification:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Visual verification:

```bash
node scripts/gui-visual-debug.mjs --scenario palette,chat,responsive --no-build --output "$env:TEMP\embedagent-t3-command-palette" --viewports 1280x720,700x640,520x720
```

## Documentation

Update after implementation:

- `docs/development-tracker.md`
- `docs/design-change-log.md`

No global architecture source-of-truth change is expected because this stays inside the existing GUI app-shell presentation/read-model boundary.

## Constraints

- Preserve Python `>=3.8,<3.9`.
- Do not introduce Python 3.9+ syntax.
- Do not add runtime dependencies.
- Do not modify `uv.lock` manually.
- Do not commit `config/config.json`.
- Keep command palette data out of transcript history, workflow state, permission policy, runtime reducers, provider configuration, telemetry, source-control checkpoints, and Agent Core.
- Keep all T3 parity code Win7/WebView2 109 compatible.

## Approval

The user approved this next slice on 2026-06-18 after reviewing the remaining T3 parity gaps. The agreed direction is to copy T3 Code's command palette root/submenu/results experience before branch/worktree mutation, source-control mutation, or file editor chrome work.
