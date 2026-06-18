# T3 Branch Toolbar Run Context Design

## Goal

Add the next T3 Code parity slice by copying T3's composer-adjacent branch/run-context toolbar into the GUI workbench.

This continues the approved product direction: `reference/t3code` is the design source of truth, the GUI should behave like an independent T3-style app shell, and Agent Core must stay minimal, Pi-like, offline-first, and replaceable.

## Source Design

The target behavior comes from:

- `reference/t3code/apps/web/src/components/BranchToolbar.tsx`
- `reference/t3code/apps/web/src/components/BranchToolbar.logic.ts`
- `reference/t3code/apps/web/src/components/BranchToolbarBranchSelector.tsx`
- `reference/t3code/apps/web/src/components/BranchToolbarEnvModeSelector.tsx`
- `reference/t3code/apps/web/src/components/BranchToolbarEnvironmentSelector.tsx`
- `reference/t3code/apps/web/src/lib/vcsStatusState.ts`
- `reference/t3code/apps/web/src/components/ChatView.tsx`

The important T3 semantics for this slice are:

- The toolbar sits below the composer, not in the global app header.
- It summarizes the send/run context close to the place where the user submits work.
- It shows a local/current checkout mode and branch/source-control status.
- On narrow layouts, the context controls collapse into a compact selector shape.
- Branch/worktree/source-control actions are colocated with this toolbar in T3, but this first parity slice must not introduce mutation semantics that the current GUI backend does not own.

## Scope

Implement a T3-style run-context toolbar for the local/offline GUI.

In scope:

- Add a GUI-only `BranchToolbar` presentation surface under the composer.
- Derive toolbar data from the existing app-shell workspace state and read-only `sourceControl` status.
- Show current workspace label, local checkout mode, current branch or detached head, dirty counts, provider label, and Git availability/repo state.
- Add small disabled or read-only controls that match T3's branch/worktree affordance shape without performing checkout, branch creation, PR checkout, staging, committing, pushing, pulling, or checkpoint mutation.
- Add pure helper tests for label and state derivation, copied from the relevant T3 logic where possible.
- Add CSS and visual harness checks that the toolbar is visible below the composer, wraps safely on narrow viewports, and does not overlap the timeline or composer.
- Update slice tracking docs after implementation.

Out of scope:

- Branch checkout, branch creation, PR checkout, worktree creation, staging, commit, push, pull, sync, checkpoints, or remote provider integration.
- T3 hosted environment switching or cloud environment management.
- Browser preview surfaces.
- Full T3 `vcsStatusState` manager parity.
- New runtime dependencies, T3 package imports, Electron APIs, runtime Node requirements, online services, Docker, WSL, or VS Code integration.
- Agent Core, transcript, workflow state, permission policy, runtime reducers, provider configuration, extension loading, telemetry, source-control checkpoint truth, or C/C++ workflow package changes.

## Architecture

The feature is GUI-local and app-shell owned.

The current backend already exposes read-only local Git status through `SourceControlService` and `/api/app/source-control/status`. The toolbar consumes the same normalized frontend state that the existing Source Control panel uses:

- `src/embedagent/frontend/gui/webapp/src/source-control/source-control-state.js`
- `src/embedagent/frontend/gui/webapp/src/source-control/source-control-presentation.js`

Add a small frontend read model, likely under `src/embedagent/frontend/gui/webapp/src/source-control/` or `src/embedagent/frontend/gui/webapp/src/components/workbench/`, that derives:

- `workspaceLabel`
- `modeLabel`
- `branchLabel`
- `branchTone`
- `providerLabel`
- `changeCountLabel`
- `repoState`
- `disabledReasons`

`App.jsx` should pass `state.app.activeWorkspace` and `state.sourceControl` into the composer area. The new component should not call backend routes directly except for an optional refresh callback already owned by `App.jsx`.

No backend route is required for the intended slice.

## User Experience Contract

The visible behavior should follow T3 Code:

- The toolbar appears directly below the composer in the chat column.
- The toolbar width follows the composer/timeline column, not the full app width.
- The left side communicates the execution context: current checkout/local mode.
- The right side communicates the branch/source-control context.
- If the workspace is a Git repo, show the branch name and dirty-count summary.
- If Git is unavailable, show a muted disabled state.
- If the active workspace is not a repo, show a muted non-repo state.
- If the right panel is narrow or the app is under mobile width, the toolbar wraps into compact rows rather than clipping.
- Read-only or unavailable actions should look intentionally disabled and explain their disabled status with visible text or title attributes.

The implementation copies T3's product shape and placement, not its hosted source-control mutation backend.

## Data Flow

1. App bootstrap and active workspace loading remain unchanged.
2. Existing `loadSourceControlStatus(...)` populates `state.sourceControl`.
3. A pure derivation helper converts workspace/source-control data into toolbar view state.
4. `App.jsx` passes that view state or the raw source data to the toolbar component.
5. The toolbar renders local checkout, branch, repo status, provider, and dirty-count display.
6. Refresh remains app-shell owned and uses the existing read-only source-control refresh path.

The toolbar must not write transcript history, workflow state, permission policy, runtime reducers, telemetry, source-control checkpoints, provider configuration, extension loading state, or Agent Core policy.

## Error Handling

- If there is no active workspace, the toolbar is not rendered.
- If source-control status is loading, render a compact loading state.
- If Git is unavailable, render a disabled Git state.
- If the workspace is not a repo, render a disabled non-repo state.
- If source-control status returns an error, render a muted error state and keep the composer usable.
- Unknown or malformed source-control payloads should normalize through the existing `normalizeSourceControlStatus(...)` path.

No toolbar error should block sending a message or running the agent.

## Testing

Use focused test-first implementation.

Required JavaScript tests under `src/embedagent/frontend/gui/webapp/test/`:

- Toolbar derivation returns "Current checkout" for the default local mode.
- Toolbar derivation returns the current branch when `sourceControl.data.branch` is present.
- Toolbar derivation falls back to a short head/detached label when branch is absent and head is present.
- Dirty-count summary includes staged, unstaged, untracked, and conflicted counts without overflowing into verbose copy.
- Git unavailable and non-repo states produce disabled labels.
- Existing source-control normalization remains compatible with the toolbar.

Required verification:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
npm run build
```

Focused backend tests should be run only if the implementation changes backend source-control code. The default path should avoid backend changes.

Visual verification:

```bash
node scripts/gui-visual-debug.mjs --scenario chat,responsive --no-build --output "$env:TEMP\embedagent-t3-branch-toolbar" --viewports 1280x720,700x640,520x720
```

If the visual harness needs a dedicated fixture for Git status, add it as a dev-only `?visual_debug=1` fixture and keep it out of product protocol.

## Documentation

The implementation should update:

- `docs/development-tracker.md`
- `docs/design-change-log.md`

No global architecture source-of-truth change is expected because the GUI source-control app-shell boundary already exists and this slice stays inside it.

## Constraints

- Preserve Python `>=3.8,<3.9`.
- Do not introduce Python 3.9+ syntax in backend or tests.
- Do not add runtime dependencies.
- Do not modify `uv.lock` manually.
- Do not commit `config/config.json`.
- Keep GUI branch/source-control toolbar state out of transcript history, workflow state, permission policy, runtime reducers, telemetry, source-control checkpoints, provider configuration, extension loading, and Agent Core.
- Continue using official vocabulary: `build`, `tasks`, `current_phase`, `discipline_profile`; do not reintroduce `code` or `todos`.

## Approval

The user approved this slice on 2026-06-18 after confirming that T3 Code is the standard answer and the GUI should directly copy T3 rather than introduce original design.
