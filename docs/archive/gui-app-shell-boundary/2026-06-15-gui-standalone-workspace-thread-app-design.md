# GUI Standalone Workspace And Thread App Design

## Purpose

Turn the GUI from a project-folder-launched session surface into a standalone
Agent IDE app. The app should feel closer to T3 Code: workspaces/projects and
threads are managed inside the GUI, with the left navigation acting as the
primary place to open work, switch context, and resume previous agent threads.

The implementation must copy T3 Code's product shape and interaction language,
not its runtime stack. EmbedAgent still targets Windows 7, offline deployment,
Python 3.8, and a small replaceable GUI shell around Agent Core.

## Current Baseline

The current GUI is bound to one workspace at process startup:

- `src/embedagent/frontend/gui/launcher.py` resolves a workspace path and
  creates one `AgentCoreAdapter`.
- `src/embedagent/frontend/gui/backend/server.py` exposes session, workspace,
  file, task, artifact, permission, and WebSocket APIs against that one core.
- `src/embedagent/frontend/gui/webapp/src/App.jsx` loads sessions, files, tasks,
  recipes, and tool catalog immediately on first render.
- `src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx` shows a
  simple Chats/Files tab set, but it does not manage multiple workspaces.

This makes the GUI behave like a large project-local TUI with a browser shell.
The next slice changes that outer product shape while preserving the single
workspace Agent Core boundary internally.

## Design Goals

- Start the GUI without requiring a project folder.
- Manage recent/open workspaces inside the GUI.
- Present sessions as T3-style threads in the user-facing GUI.
- Keep the backend protocol compatible by continuing to expose current
  workspace sessions through existing `/api/sessions` endpoints in the first
  slice.
- Keep Agent Core simple: one active workspace/core at a time, owned by a GUI
  app host outside Core.
- Add visual debug coverage for no-workspace startup, workspace activation, and
  thread switching.
- Keep all state local and offline; no remote environment registry, cloud
  account, or network control plane.

## Recommended Architecture

Introduce a small GUI app host around the existing core-bound backend.

```text
GUI App Process
  |
  +-- AppHost
      |
      +-- WorkspaceRegistry     user-level recent workspace JSON
      +-- ActiveCoreSlot        zero or one AgentCoreAdapter
      +-- WebSocketFrontend     shared frontend callback bridge
      +-- FastAPI routes
          |
          +-- /api/app/*        app/workspace management
          +-- /api/sessions/*   active workspace session/thread APIs
          +-- /api/files/*      active workspace file APIs
```

The app host owns workspace activation. Agent Core remains workspace-scoped and
does not learn about GUI-level workspace history or switching. This mirrors T3
Code's app-level environment/project/thread model while staying Pi-like:
minimal kernel, explicit replaceable shell, and no hidden global singleton.

## Backend Components

### Workspace Registry

Persist a list of local workspaces in a user-level app data file, not inside any
project directory. The record shape should be intentionally small:

- `id`: stable hash or generated id derived from canonical path
- `path`: canonical absolute path
- `label`: display name, defaulting to folder name
- `created_at`
- `last_opened_at`
- `exists`: computed at read time, not persisted truth

Removing a workspace removes it from the registry only. It must never delete
project files.

### Active Core Slot

The active slot owns the current `AgentCoreAdapter` and its workspace path.
Activation flow:

1. Validate that the path exists and is a directory.
2. Persist/upsert the workspace registry record.
3. If the active workspace is different, shut down the existing core.
4. Create a new core using the same `create_core(...)` path used today.
5. Register the shared `WebSocketFrontend`.
6. Broadcast a `workspace_changed` event.
7. Reset the backend current session id.

Only one active core is supported in the first slice. This avoids multi-core
lifetime bugs, keeps memory bounded, and matches the offline Win7 target.

### App-Level APIs

Add a narrow app management surface:

- `GET /api/app/bootstrap`
  Returns known workspaces, active workspace, app readiness, and safe diagnostics.
- `GET /api/app/workspaces`
  Lists recent workspaces.
- `POST /api/app/workspaces`
  Adds or opens a workspace by local path.
- `POST /api/app/workspaces/{workspace_id}/activate`
  Activates a known workspace.
- `DELETE /api/app/workspaces/{workspace_id}`
  Removes the workspace from the recent list only.

Existing `/api/sessions`, `/api/workspace`, `/api/files`, `/api/tasks`,
`/api/artifacts`, `/api/tool-catalog`, and `/ws` continue to target the active
workspace. If no workspace is active, workspace-bound APIs return a structured
`409 no_active_workspace` response.

## Frontend Experience

### App Startup

The GUI opens as an app even when no workspace argument is provided. If an
active/recent workspace is available, the app may auto-activate the last opened
workspace. If not, it shows a no-workspace state with:

- recent workspace list
- local path input
- open/add workspace action
- clear status if the path is invalid or missing

This is the new first screen; it replaces the assumption that the process was
started from a project directory.

### Sidebar Shape

The left side should move toward T3 Code's structure:

```text
EmbedAgent
[workspace switcher / current project]
[new thread button]

Workspace / Project
  Thread title
  Thread title
  Thread title

Files
  tree...
```

For the first slice, `Thread` is a GUI label over existing `Session` data. The
backend API can remain session-based until a later protocol cleanup.

Thread rows should show:

- title from `user_goal`, `summary_text`, or session id fallback
- mode badge
- status/running marker where available
- last updated time

Workspace rows should show:

- label/folder name
- path as secondary text
- missing-path warning when the directory no longer exists

### Workspace Switching

Switching workspace clears workspace-scoped UI state:

- current thread/session id
- timeline
- tasks
- artifacts
- file tree
- preview/diff surfaces
- permission context

Then the app reloads sessions, files, recipes, tasks, artifacts, and tool
catalog from the newly active workspace. If the current thread is running or
waiting for interaction, the first slice should block switching with a clear
confirmation path or require the user to stop/resolve it first. Silent switching
while a tool is waiting for permission is not allowed.

### Command Palette

Add workspace commands to the existing palette:

- Open Workspace
- Switch Workspace
- Remove Workspace From Recents
- New Thread
- Refresh Threads

The command palette remains a UI convenience, not a second workspace policy
engine.

## Visual Design Language

The interaction language should follow T3 Code closely:

- compact project/thread rows instead of large cards
- strong left navigation hierarchy
- workspace switcher as an app-level control
- thread status indicators embedded in rows
- minimal chrome around the central timeline
- no marketing-style landing page

This is a product and layout direction, not permission to copy T3 Code source or
adopt dependencies that break Windows 7/offline compatibility.

## Error Handling

- No active workspace: workspace-bound APIs return `409 no_active_workspace`;
  frontend shows the workspace picker instead of failing silently.
- Missing workspace path: keep the registry entry visible with a warning and
  disable activation until the path is corrected.
- Core creation failure: keep the previous active workspace running if possible;
  otherwise return to no-active-workspace state with the error message.
- WebSocket reconnect after workspace switch: treat `workspace_changed` as a
  hard boundary and reload app bootstrap plus active thread state.
- Pending permission/user input: do not discard unresolved interactions during
  workspace switch. Require resolution/cancel before activation.

## Testing And Visual Debugging

Add focused backend tests for:

- registry add/list/remove behavior
- no-active-workspace API responses
- activating a workspace creates a core and registers frontend callbacks
- activating a second workspace shuts down the previous core
- invalid paths return structured errors

Add frontend tests for:

- no-workspace state rendering
- workspace list rendering
- switching workspace resets session-scoped state
- thread list still maps existing session payloads correctly

Extend `scripts/gui-visual-debug.mjs` with an app-management scenario:

1. Start GUI without a workspace.
2. Verify no-workspace state.
3. Add/activate a temporary workspace.
4. Verify thread/sidebar/files load.
5. Create or select a thread.
6. Activate a second temporary workspace.
7. Verify stale thread/timeline state is gone.

This makes Codex able to inspect the real standalone GUI flow rather than only
testing a project-bound happy path.

## Non-Goals

- Multiple active workspaces at the same time.
- Multiple GUI windows.
- Remote T3-style environments.
- Cloud sync, account login, or network workspace registry.
- Thread multi-select, drag reorder, archive/delete bulk actions.
- Worktree creation and pull request flows.
- Replacing Agent Core session terminology in all backend protocols.

These are valid future directions after the standalone app host is stable.

## Acceptance Criteria

1. Launching the GUI with no workspace opens a usable app shell.
2. The user can add a local workspace from the GUI.
3. The user can switch between at least two recent local workspaces from the GUI.
4. Threads are visible and manageable from the GUI sidebar for the active
   workspace.
5. Existing session creation, resume, message submit, permissions, files, tasks,
   artifacts, and tool catalog still work in an activated workspace.
6. Workspace switching cannot silently strand an active pending interaction.
7. Visual debug can screenshot and validate no-workspace, active-workspace, and
   workspace-switch states.
8. The change preserves Windows 7/offline constraints and does not add runtime
   dependencies on Docker, WSL, VS Code, online services, or a Node runtime.
