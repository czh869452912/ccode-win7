# GUI Source Control Foundation Design

## Goal

Build the next T3 Code-style standalone GUI slice: a source-control changes
surface for the active workspace, while preserving EmbedAgent's small Agent
Core, offline deployment model, Windows 7 support, and Python 3.8 runtime.

This slice is intentionally a foundation. It should make local Git changes
visible and reviewable in the GUI, but it must not introduce commit/push/pull,
remote provider, or checkpoint mutation flows yet.

## Reference Shape From T3 Code

Use `reference/t3code` as the product-shape reference, not as a dependency.

Relevant reference areas:

- `packages/contracts/src/git.ts`
- `packages/contracts/src/sourceControl.ts`
- `packages/shared/src/git.ts`
- `packages/shared/src/sourceControl.ts`
- `packages/client-runtime/src/vcsStatusState.ts`
- `packages/client-runtime/src/sourceControlDiscoveryState.ts`
- `apps/web/src/sourceControlPresentation.ts`
- `apps/server/src/git/GitManager.ts`
- `apps/server/src/sourceControl/SourceControlDiscovery.ts`

The useful T3 Code shape is:

- VCS status is an app/workspace surface, not a chat transcript feature.
- Client state tracks target workspace, pending/error/data, and refresh
  lifecycle separately from thread detail state.
- Server-side Git status is split into local status and remote/provider status.
- Source-control provider discovery is separate from local Git status.
- Working tree changes are summarized by file path plus insertion/deletion
  counts.
- Diff review is reached by selecting a changed file.
- Higher-risk write flows such as commit, push, pull, PR creation, and
  checkpoint revert are separate action layers.

EmbedAgent should copy that architecture shape, but not T3 Code's stack. This
product must remain Python 3.8, Win7/offline, and dependency-light.

## Current EmbedAgent Baseline

The GUI already has:

- T3 Code-like app shell, project/thread sidebar, timeline, composer, command
  palette, right-panel surfaces, and bottom drawer.
- A GUI app-shell boundary in `backend/app_shell.py` and frontend helpers under
  `webapp/src/app-shell/`.
- A real terminal bottom drawer hosted by the GUI backend and kept outside
  Agent Core.
- A Diff right-panel surface backed by frontend-local diff helpers.
- Existing runtime Git tools: `git_status`, `git_diff`, `git_log`, and
  `git_snapshot`.
- Existing managed-tool resolution for bundled MinGit through
  `ToolContext.resolve_managed_tool_path("git")` and the offline runtime
  contract.

The GUI does not yet have:

- A source-control app-shell capability.
- A GUI-hosted source-control service.
- Source-control HTTP routes.
- Frontend source-control state/reducer/API helpers.
- A T3 Code-like changes list for active workspace files.
- A route from a changed file row into the existing Diff right-panel surface.

## Hard Constraints

1. Windows 7 support is mandatory.
2. Offline deployment is mandatory.
3. Runtime remains Python `>=3.8,<3.9`.
4. Do not add runtime dependencies such as libgit2, dulwich, Electron,
   runtime Node, Docker, WSL, VS Code, or online services.
5. Do not require globally installed Git. Prefer bundled/workspace MinGit and
   only allow system fallback through the same managed-tool policy already used
   by runtime tooling.
6. Do not route GUI source-control reads through Agent Core tool calls.
7. Do not write source-control GUI state into `transcript.jsonl`.
8. Do not let source-control UI state become workflow truth, permission policy,
   extension policy, provider configuration, checkpoint truth, telemetry, or
   runtime reducer truth.
9. Do not introduce remote provider calls, intranet Git calls, push/pull, or PR
   creation in this slice.
10. Do not reintroduce compatibility paths for old frontend vocabulary.

## Scope

### In Scope

- GUI backend `SourceControlService` under
  `src/embedagent/frontend/gui/backend/`.
- Workspace-bound Git executable resolution using existing managed-tool
  discovery patterns.
- Read-only local Git status for the active workspace.
- Read-only file diff for selected workspace paths.
- App-shell capability metadata for the source-control surface and limitations.
- HTTP routes for status, refresh, and file diff.
- Frontend source-control model/API helpers under
  `webapp/src/source-control/`.
- A T3 Code-like changes surface in the existing GUI shell.
- Command palette entry for opening the source-control surface.
- Reuse of the existing Diff right-panel surface when reviewing a selected
  changed file.
- Tests for service parsing, workspace guard, route error mapping, app-shell
  capabilities, and frontend reducer/presentation behavior.
- Documentation updates and archive handoff when the slice closes.

### Out Of Scope

- Stage/unstage.
- Commit.
- Push/pull/fetch.
- Branch switching or worktree creation.
- PR/MR/change-request discovery or creation.
- GitHub/GitLab/Azure DevOps/Bitbucket provider integration.
- Intranet Git operations.
- Checkpoint creation, listing, restore, or deletion.
- Agent Core permission changes.
- Runtime reducer changes.
- C/C++ harness changes.
- Persisted source-control GUI state across app restarts.

Those become later slices after the local read-only boundary exists.

## Product Behavior

### Surface Placement

The source-control surface should feel like T3 Code's local changes workflow:

- A compact changes list for the active workspace.
- Branch and repository state at the top.
- Grouped changed files:
  - staged
  - unstaged
  - untracked
  - conflicted
- File rows show path, status, and insertion/deletion counts when available.
- Selecting a file opens a diff review surface using the existing diff panel.
- Refresh is explicit and safe.
- Empty states are clear:
  - no active workspace
  - Git unavailable
  - not a Git repository
  - clean working tree
  - status failed

The surface is workspace-scoped, not session-scoped. It may be opened while no
session is active, as long as the GUI app host has an active workspace.

### First-Slice Read-Only Rule

This slice must be read-only from Git's perspective:

- `git status` is allowed.
- `git diff` is allowed.
- `git diff --cached` is allowed.
- `git rev-parse` and `git remote get-url` are allowed for local metadata.
- `git ls-files` is allowed if needed to classify untracked files.
- No Git command may mutate refs, index, worktree, remotes, stashes, or config.

If a desired UI action requires Git mutation, it should render as disabled or
be omitted from this slice.

### Diff Behavior

For a selected changed file:

- Modified unstaged file: show `git diff -- <path>`.
- Staged file: show `git diff --cached -- <path>`.
- File with both staged and unstaged changes: expose both scopes in the file
  metadata and default to unstaged.
- Untracked text file: provide a synthetic unified diff only if it can be read
  safely within size limits; otherwise show metadata with an unavailable diff
  reason.
- Deleted file: use Git diff output.
- Binary file: return metadata with a binary/unavailable reason instead of
  trying to render text.

The backend should cap diff output and include truncation metadata. The
frontend should show the capped diff without trying to infer missing content.

## Backend Architecture

Create `src/embedagent/frontend/gui/backend/source_control_service.py`.

Responsibilities:

- Bind to one active workspace root.
- Resolve Git executable through existing managed runtime discovery patterns.
- Run read-only Git commands with timeouts and output caps.
- Keep all path arguments inside the workspace.
- Parse status into a stable JSON shape.
- Produce per-file diffs for selected files.
- Return serializable errors without exposing environment secrets.

The service should be independent from Agent Core and from `ToolRuntime`
execution. It may reuse small utility patterns from `ToolContext` only where
that does not turn source-control UI into an agent tool action.

Suggested public shape:

```python
class SourceControlService(object):
    def __init__(self, workspace_root, git_executable=None, command_runner=None):
        ...

    def status(self):
        ...

    def diff(self, path, scope="unstaged"):
        ...

    def discover(self):
        ...
```

### Command Execution

Use `subprocess.Popen` or `subprocess.run` from the standard library.

Defaults:

- timeout: 5 seconds for status/discovery
- timeout: 10 seconds for diff
- max status output: 512 KiB
- max diff output: 1 MiB
- encoding: UTF-8 with replacement
- `shell=False`

The command environment should prepend managed Git search paths when available,
matching the existing offline bundle behavior. No online calls are allowed.

### Status Shape

```json
{
  "workspace_root": "D:/project",
  "is_repo": true,
  "git_available": true,
  "git_executable": "D:/bundle/bin/git/cmd/git.exe",
  "runtime_source": "bundle",
  "branch": "main",
  "head": "abcdef1",
  "has_primary_remote": true,
  "provider": {
    "kind": "github",
    "name": "GitHub",
    "base_url": "https://github.com"
  },
  "is_dirty": true,
  "counts": {
    "staged": 1,
    "unstaged": 2,
    "untracked": 1,
    "conflicted": 0,
    "total": 4
  },
  "files": [
    {
      "path": "src/main.c",
      "display_path": "src/main.c",
      "status": "modified",
      "index_status": "M",
      "worktree_status": "M",
      "group": "unstaged",
      "insertions": 10,
      "deletions": 2,
      "binary": false,
      "diff_scopes": ["unstaged"]
    }
  ],
  "updated_at": "2026-06-17T00:00:00Z",
  "diagnostics": {
    "status_truncated": false,
    "stats_truncated": false,
    "warnings": []
  }
}
```

Provider detection is local-only and best effort from configured remote URLs.
It must not contact the provider. Unknown or missing remotes are valid.

### Diff Shape

```json
{
  "workspace_root": "D:/project",
  "path": "src/main.c",
  "scope": "unstaged",
  "available": true,
  "binary": false,
  "diff": "diff --git ...",
  "file_count": 1,
  "line_count": 120,
  "truncated": false,
  "reason": "",
  "updated_at": "2026-06-17T00:00:00Z"
}
```

Unavailable reasons:

- `not_a_repo`
- `git_unavailable`
- `path_outside_workspace`
- `path_not_changed`
- `binary_file`
- `file_too_large`
- `diff_too_large`
- `git_failed`

## Backend Routes

Add routes on `GUIBackend` that require an active workspace but do not require
an active session:

- `GET /api/app/source-control/status`
- `POST /api/app/source-control/refresh`
- `GET /api/app/source-control/diff?path=<path>&scope=<scope>`

Error mapping:

- no active workspace: `409 no_active_workspace`
- Git unavailable: `200` with `git_available: false`
- not a repo: `200` with `is_repo: false`
- invalid path/scope: `422`
- command timeout/failure: `200` with diagnostics when a partial safe payload
  can be produced, otherwise `422 source_control_failed`

Returning `200` for normal Git absence keeps the app usable on non-Git
workspaces and offline clean machines.

## Frontend Architecture

Create:

- `webapp/src/source-control/source-control-state.js`
- `webapp/src/source-control/source-control-api.js`
- `webapp/src/source-control/source-control-presentation.js`

Responsibilities:

- Normalize backend status/diff payloads.
- Track `idle | loading | ready | error` request state.
- Track selected file and selected diff scope.
- Group files into staged/unstaged/untracked/conflicted.
- Produce compact labels and status badges.
- Keep source-control state workspace-local and frontend-local.

The root reducer in `webapp/src/store.js` should include a source-control state
slice, and `resetWorkspaceScopedState(...)` should reset it on workspace
switch.

### UI Integration

The first implementation should use existing workbench primitives:

- Add a source-control command to `workbench/commands.js`.
- Add `source_control` as a right-panel surface or sidebar/workbench surface,
  depending on the current shell fit.
- Reuse `components/diff/DiffPanel.jsx` for selected file diffs instead of
  creating a second diff renderer.
- Keep the UI compact: no marketing copy, no explanatory tutorial text, and no
  nested cards.

The exact visual arrangement should follow T3 Code's local-changes shape:
header metadata, grouped file list, selected diff review, and small icon
actions.

## App-Shell Capability Metadata

Extend app-shell capabilities with source-control limitations:

```json
{
  "surfaces": {
    "right_panel": ["settings", "diagnostics", "source_control"]
  },
  "source_control": {
    "enabled": true,
    "vcs": ["git"],
    "read_only": true,
    "remote_providers": false,
    "network": false,
    "checkpoints": false,
    "requires_active_workspace": true
  }
}
```

This is diagnostic/control-plane metadata only. It must not become permission
policy or Agent Core runtime state.

## Testing Plan

### Python Tests

Add `tests/test_gui_source_control_service.py`:

- Git unavailable returns safe discovery/status payload.
- Not-a-repo workspace returns `is_repo: false`.
- Status parser handles staged, unstaged, untracked, deleted, renamed, and
  conflicted porcelain entries.
- Path guard rejects workspace escape.
- Diff rejects invalid scope.
- Diff returns capped/truncated metadata.
- Provider detection is local-only from remote URL strings.

Add `tests/test_gui_source_control_api.py`:

- Routes require active workspace.
- Status route calls the service and returns payload.
- Refresh route returns fresh status.
- Diff route validates path/scope and maps errors.
- Git unavailable and not-a-repo are non-fatal 200 payloads.

Update `tests/test_gui_app_shell.py`:

- Source-control capabilities are present and read-only.

### Frontend Tests

Add `webapp/test/source-control-state.test.mjs`:

- Empty/default state.
- Status normalization.
- File grouping and counts.
- Selected file/scope changes.
- Diff load success/error.
- Workspace reset clears state.

Update existing webapp command/app-shell tests:

- Source-control command visibility.
- Source-control capability normalization.

### Verification Commands

Focused:

```bash
uv run pytest tests/test_gui_source_control_service.py tests/test_gui_source_control_api.py tests/test_gui_app_shell.py -v
uv run ruff check src/embedagent/frontend/gui/backend/source_control_service.py src/embedagent/frontend/gui/backend/server.py tests/test_gui_source_control_service.py tests/test_gui_source_control_api.py tests/test_gui_app_shell.py
cd src/embedagent/frontend/gui/webapp && npm test
cd src/embedagent/frontend/gui/webapp && npm run build
```

Closeout:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Also confirm the implementation does not modify Agent Core ownership files:

- `src/embedagent/query_engine.py`
- `src/embedagent/agent_loop.py`
- `src/embedagent/agent_tool_action_service.py`
- `src/embedagent/extensions.py`
- `src/embedagent/permissions.py`

## Documentation Updates

When implemented, update:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`
- `docs/frontend-protocol.md`
- `docs/modules/frontend-gui.md`

Completed slice docs should be moved to
`docs/archive/gui-source-control-foundation/` after global docs are
synchronized.

## Acceptance Criteria

The slice is complete when:

1. The GUI exposes a source-control changes surface for the active workspace.
2. Local Git status and per-file diff work through GUI-hosted backend routes.
3. The feature remains read-only and local-only.
4. Git absence and non-Git workspaces degrade cleanly.
5. No new runtime dependency is introduced.
6. Win7/offline constraints remain intact.
7. Agent Core, permission policy, workflow truth, transcript truth, and runtime
   reducers remain untouched.
8. Tests, lint, frontend build, fast pytest suite, and docs updates pass.

## Future Slices

Recommended follow-up order:

1. Checkpoint diff presentation: show thread/turn checkpoint diffs using a
   separate read-only checkpoint surface.
2. Source-control write actions: stage/unstage/commit only after explicit
   permission and policy design.
3. Remote provider discovery: optional, trusted, manifest/config gated, with
   `network` permission and offline fallback.
4. Win7 bundle smoke hardening: run the GUI source-control/terminal/diff path
   against the real offline bundle on a clean Win7 target.
