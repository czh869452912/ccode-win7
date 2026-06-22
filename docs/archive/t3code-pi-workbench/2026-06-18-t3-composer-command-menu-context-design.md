# T3 Composer Command Menu And Context Design

## Goal

Move the GUI composer from a simple textarea with slash hints toward T3 Code's composer experience.

This is the next highest-value T3 parity slice because the composer is the user's main work surface. The implementation should copy T3's command/context interaction shape while preserving EmbedAgent's current offline, Windows 7, Python 3.8, GUI-app-shell, and minimal Agent Core boundaries.

## Source Design

The target behavior comes from:

- `reference/t3code/apps/web/src/components/chat/ChatComposer.tsx`
- `reference/t3code/apps/web/src/components/chat/ComposerCommandMenu.tsx`
- `reference/t3code/apps/web/src/components/chat/composerSlashCommandSearch.ts`
- `reference/t3code/apps/web/src/components/chat/ComposerPrimaryActions.tsx`
- `reference/t3code/apps/web/src/components/ComposerPromptEditor.tsx`
- `reference/t3code/packages/shared/src/searchRanking.ts`
- `reference/t3code/packages/shared/src/composerTrigger.ts`
- `reference/t3code/packages/client-runtime/src/composerPathSearchState.ts`

The important T3 semantics for this slice are:

- The command menu belongs to the composer, not the global command palette.
- Slash commands are searchable and grouped, instead of rendered as a flat hint bar.
- Path/context triggers let users attach file context near the prompt.
- The primary send/stop action has a compact T3 button shape with explicit disabled/busy states.
- Pending approval/user-input panels remain composer-adjacent and should not be displaced by command overlays.

## Scope

Implement a GUI-local T3-style composer command menu and lightweight context-token flow.

In scope:

- Replace the current inline slash hint list with a composer-owned `ComposerCommandMenu` surface.
- Add a pure trigger/parser helper for `/` slash command search and `@` or path-style file context search.
- Add ranked slash-command search copied from T3's scoring behavior where feasible.
- Add a grouped menu presentation for built-in slash commands and workspace file/path results.
- Insert selected slash commands into the textarea exactly as executable text, matching the current slash command contract.
- Insert selected file contexts as visible text tokens such as `@src/main.c` or equivalent inline path markers without changing backend protocol.
- Add T3-style primary send/stop action visuals and disabled/busy labels while preserving current send/stop behavior.
- Keep the existing `ComposerInteractionPanel` for permission and user input, but ensure the new menu positions around it without overlap.
- Add visual debug fixtures/checks for slash-command menu, path context menu, keyboard navigation, and narrow viewport layout.

Out of scope:

- Image attachments.
- Browser preview annotation cards.
- Provider skills or provider-owned slash commands that require new backend/provider protocol.
- New model selection/provider picker behavior.
- Runtime permission-mode toggles that alter `PermissionPolicy`.
- New backend protocol for structured composer attachments.
- New Agent Core context semantics for file chips.
- Branch/worktree mutation, source-control mutation, checkpoints, staging, commit, push, pull, PR creation, or remote provider integration.
- Electron, runtime Node, Docker, WSL, VS Code, online service, or T3 package imports.

## Architecture

The slice stays in the React GUI webapp and app-shell display/read-model layer.

Add focused frontend modules:

- `webapp/src/components/composer/ComposerCommandMenu.jsx`
- `webapp/src/components/composer/ComposerPrimaryActions.jsx`
- `webapp/src/composer/composer-trigger.js`
- `webapp/src/composer/composer-command-search.js`
- `webapp/src/composer/composer-path-context.js`

`Composer.jsx` should become a composition surface:

- Own textarea value, trigger detection, highlighted menu item, and menu selection callbacks through props/state already owned by `App.jsx`.
- Receive command metadata from the existing `SLASH_COMMAND_HINTS` or a richer derived command list based on `WORKBENCH_COMMANDS`.
- Receive workspace file candidates from existing GUI file-tree state when available.
- Never call Agent Core directly.
- Never write transcript history or workflow state.

No backend route is required for the first slice. If file search needs more than already-loaded tree nodes, use the existing app-shell file loading path only as a follow-up slice.

## User Experience Contract

The visible behavior should follow T3 Code:

- Typing `/` opens a rounded floating command menu above the composer.
- Slash command results show a command label plus short description or slash text.
- Built-in commands are visually grouped.
- Keyboard up/down changes the highlighted item.
- Enter selects the highlighted menu item when the menu is open; otherwise Enter sends the message.
- Escape closes the composer menu before it bubbles to broader app behavior.
- Typing `@` or a path trigger opens a file-context menu using currently known workspace files.
- Selecting a file inserts an inline token/path into the prompt and returns focus to the composer.
- The primary action is a compact T3-style send button when idle and a stop button when running.
- The menu must stay inside the chat column, fit on mobile/narrow layouts, and not overlap pending interaction panels in a confusing way.

This slice improves the composer experience but does not change what the backend receives: the submitted prompt remains text.

## Data Flow

1. `App.jsx` continues to own `state.composer`.
2. `Composer.jsx` detects trigger state from the current text and cursor.
3. Slash trigger state filters ranked command items derived from existing workbench commands.
4. File trigger state filters currently loaded workspace file nodes into path context candidates.
5. Selecting a slash command replaces the trigger range with its slash text.
6. Selecting a file path replaces the trigger range with an inline text marker.
7. Send/stop still call the existing `onSend` / `onStop` props.

The submitted prompt remains plain text and continues through the existing session send path.

## Error Handling

- If no commands match, show a compact empty state.
- If no file paths are loaded or match, show a compact empty state rather than fetching new backend state.
- If the menu is open and the composer becomes disabled by running or pending interaction state, close the menu.
- Malformed file-tree nodes are ignored by the path candidate helper.
- The composer remains usable even when file candidates are unavailable.

No composer-menu error should block existing send/stop behavior.

## Testing

Use focused JavaScript tests under `src/embedagent/frontend/gui/webapp/test/`.

Required tests:

- Trigger helper detects slash command trigger ranges.
- Trigger helper detects file context trigger ranges.
- Slash command search ranks exact, prefix, word-boundary, and substring matches in T3-like order.
- Path context candidate projection flattens current file tree nodes and ignores directories for insertion.
- Selection replaces only the active trigger range.
- `Composer.jsx` source includes `ComposerCommandMenu`, `ComposerPrimaryActions`, and keeps `BranchToolbar`.
- Static checks confirm composer menu code does not call `fetch(`, does not mention transcript writes, and does not import backend/Core modules.
- Visual debug fixture can open slash and file-context menus and assert no horizontal overflow at `1280x720`, `700x640`, and `520x720`.

Required verification:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Visual verification:

```bash
node scripts/gui-visual-debug.mjs --scenario chat,responsive --no-build --output "$env:TEMP\embedagent-t3-composer-command-menu" --viewports 1280x720,700x640,520x720
```

If a dedicated composer-menu scenario is added, include it in the same visual command once implemented.

## Documentation

The implementation should update:

- `docs/development-tracker.md`
- `docs/design-change-log.md`

No global architecture source-of-truth change is expected because this stays inside the existing GUI app-shell presentation/read-model boundary.

## Constraints

- Preserve Python `>=3.8,<3.9`.
- Do not introduce Python 3.9+ syntax in backend or tests.
- Do not add runtime dependencies.
- Do not modify `uv.lock` manually.
- Do not commit `config/config.json`.
- Keep composer command/context state out of transcript history, workflow state, permission policy, runtime reducers, telemetry, source-control checkpoints, provider configuration, extension loading, and Agent Core.
- Continue using official vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`; do not reintroduce `code` or `todos`.
- Keep all T3 parity code Win7/WebView2 109 compatible: plain React/CSS, no browser APIs that require modern Chromium-only behavior without fallback.

## Approval

The user approved this next slice on 2026-06-18 after reviewing the gap assessment. The agreed direction is to copy T3 Code's composer command/context experience first, before source-control mutation or branch/worktree mutation work.
