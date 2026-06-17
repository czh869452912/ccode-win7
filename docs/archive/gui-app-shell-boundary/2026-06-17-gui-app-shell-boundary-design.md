# GUI App Shell Boundary Design

## Reader And Action

This design defines the next GUI architecture slice after the T3-style timeline
and interaction workbench work. It is for an engineer who needs to start closing
the gap between the current EmbedAgent GUI and a standalone T3 Code-style app
without coupling GUI product concerns back into Agent Core.

After reading it, the engineer should be able to build the first GUI app-shell
boundary slice, update the relevant tests, and keep Agent Core aligned with the
Pi-inspired direction: small, explicit, replayable, extensible, and not thickened
by shell lifecycle concerns.

## Decision

Introduce a GUI-local app-shell boundary that owns standalone app concerns while
continuing to treat Agent Core as a replaceable local runtime behind the existing
core/protocol contract.

The first slice is called **GUI App Shell Boundary v1**.

It should create a clear product boundary for:

- app bootstrap state
- workspace registry and active workspace selection
- GUI runtime diagnostics
- app-level capabilities and feature flags
- settings and diagnostics surfaces
- workbench command routing for app-level surfaces
- future terminal, source-control, checkpoint, and desktop-lifecycle features

It must not move workflow semantics, session history, tool activation,
permission decisions, transcript reducers, provider behavior, or C/C++ workflow
truth into the GUI.

## Product Direction

Use T3 Code as the standalone app reference at the level of product shape and
local app separation, not as a runtime base.

The desired direction is:

- T3 Code-style local app shell and workbench ergonomics
- EmbedAgent-owned Python/FastAPI/pywebview/WebView2 109 runtime stack
- offline-first deployment
- Windows 7 compatibility
- Python 3.8 compatibility
- Agent Core first, with UI shells as replaceable clients
- Pi-inspired Agent Core simplicity and extension boundaries

The GUI should feel more like an independent local app over time, but that app
must remain a host shell around Core, not a second Agent Core.

## Why This Slice Comes Before Terminal, Source Control, And Checkpoints

The current GUI already has important workbench pieces:

- workspace open and recent workspace state
- session list and activation
- transcript-backed bootstrap loading
- timeline projection
- composer and pending interactions
- right-panel task, artifact, preview, diff, runtime, and permission surfaces
- bottom drawer shell
- command palette and keybindings
- FastAPI plus WebSocket bridge

However, standalone app features are still mostly distributed across
`launcher.py`, `backend/server.py`, `backend/app_host.py`, `webapp/src/App.jsx`,
and the webapp reducer. If terminal, source control, checkpoint, settings, and
desktop diagnostics are added directly into those files, the GUI will become
harder to test and more likely to leak product-shell concerns into Agent Core.

This slice creates a place for those concerns to land.

## Non-Goals

This slice must not:

- add Electron
- require Node at runtime
- require pnpm, Vite Plus, or T3's monorepo tooling in the shipped product
- depend on T3 Code packages
- introduce online auth, cloud relay, SSH, Tailscale, or public provider
  marketplace concepts
- add runtime dependency installation
- add Docker, WSL, or VS Code requirements
- make the GUI own session-history truth
- make the GUI decide active tools or permissions
- make the GUI load project extensions
- make the GUI execute workflow package logic
- add compatibility paths for old GUI-internal contracts

The product has not publicly launched, so the implementation may promote the new
GUI app-shell contract directly and remove superseded internal GUI shapes in the
same change when doing so simplifies the code.

## Boundary Model

### Agent Core Boundary

Agent Core remains responsible for:

- sessions
- transcript-backed history and bootstrap payloads
- workflow state projection
- mode and phase semantics
- task projection
- permission policy and interaction lifecycle
- tool runtime and tool catalogs
- extension manager and workflow packages
- resource reload and project-local extension loading
- provider request snapshots and reducer-backed diagnostics

The GUI reaches this through `CoreInterface` and the existing adapter path.

### GUI App Shell Boundary

The GUI app shell is responsible for:

- app startup state
- active workspace selection
- workspace registry records
- app-level settings shell
- app-level diagnostics shell
- GUI runtime and renderer diagnostics
- workbench layout state
- command palette routing for app-level commands
- feature-capability read models for shell features
- future terminal/source-control/checkpoint app features

The GUI app shell may expose backend API routes and frontend state models, but
it must not become an alternative source of truth for Agent Core state.

### Desktop Host Boundary

`launcher.py` and pywebview remain the desktop host layer.

The host layer owns:

- FastAPI server startup
- pywebview window creation
- WebView2 fixed-runtime discovery
- renderer report output
- headless development mode
- shutdown of hosted app resources

The host layer may pass host diagnostics into the app shell, but it should not
directly own workspace/session/workbench business logic.

## Proposed Backend Shape

Add a small GUI app-shell service under `src/embedagent/frontend/gui/backend/`.

Suggested module:

- `app_shell.py`

Suggested public responsibilities:

- build app bootstrap payloads
- normalize host/runtime diagnostic metadata
- expose app feature capability flags
- provide settings and diagnostics read models
- coordinate with `GUIAppHost` for active workspace state

The existing `GUIAppHost` should continue to own active workspace lifecycle and
Core instance binding. The new app-shell service should compose it rather than
replace it in v1.

Suggested v1 payload shape:

```json
{
  "app": {
    "name": "EmbedAgent",
    "version": "",
    "platform": "win32",
    "shell_version": 1
  },
  "workspaces": [],
  "active_workspace": null,
  "has_active_workspace": false,
  "last_error": "",
  "diagnostics": {
    "renderer": {},
    "host": {},
    "runtime": {}
  },
  "capabilities": {
    "settings": true,
    "diagnostics": true,
    "terminal": false,
    "source_control": false,
    "checkpoints": false
  },
  "settings": {
    "language": "en",
    "density": "compact",
    "confirm_close": true
  }
}
```

This is a GUI app-shell bootstrap payload. It is not a session bootstrap payload
and must not include transcript history, prompts, tool outputs, API keys, raw
file contents, or provider request bodies.

## Proposed Frontend Shape

Add a GUI-local frontend app-shell model under
`src/embedagent/frontend/gui/webapp/src/app-shell/`.

Suggested modules:

- `model.js`
- `reducer.js`
- `commands.js`
- `diagnostics.js`

Responsibilities:

- normalize `/api/app/bootstrap`
- hold app-level settings and diagnostics
- hold app capability flags
- expose selectors for workbench command visibility
- route app-level surfaces such as `settings` and `diagnostics`
- keep app-shell state separate from session runtime projection

The existing `store.js` can continue to own the top-level reducer in v1, but it
should delegate app-shell behavior to these modules instead of growing more
branches for standalone app concerns.

## Workbench Surface Changes

Promote settings and diagnostics to first-class app-level surfaces.

Right panel surfaces should include:

- `settings`
- `diagnostics`

Command palette commands should include:

- `app.settings`
- `app.diagnostics`
- `app.reload`

These commands should not issue slash commands to Agent Core. They should route
inside the app shell. This separation is important: `/permissions`, `/tasks`, or
`/diff` are session/workflow commands; `app.settings` and `app.diagnostics` are
GUI host commands.

## Settings v1

Settings v1 should be intentionally small:

- language
- density
- confirm close
- show diagnostics details

Settings may initially live in memory and be represented in app bootstrap. This
slice should define the shape and frontend behavior first. Durable settings can
be a later slice if needed.

Do not use settings to control Agent Core policy. Permission rules, active
tools, model configuration, and extension loading remain owned by existing Core
and hosted-runtime configuration paths.

## Diagnostics v1

Diagnostics v1 should help development and support without exposing secrets.

It may show:

- GUI shell version
- platform
- WebView renderer metadata
- whether bundled WebView2 fixed runtime was used
- active workspace record
- connection state
- session replay integrity summary
- runtime source and bundled tool readiness when available
- frontend capability flags

It must not show:

- API keys
- raw prompts
- raw tool outputs
- source file contents
- permission payload secrets
- provider request bodies

## Error Handling

App-shell errors should be explicit and frontend-visible:

- no active workspace
- workspace not found
- workspace switch blocked by running session or pending interaction
- renderer unavailable
- app bootstrap failed
- diagnostics unavailable

These are shell errors. They should not be represented as Agent Core session
errors unless a Core operation actually failed.

The frontend should preserve the current behavior that blocks workspace switching
while a session is running or waiting for interaction.

## Data Flow

Startup:

1. `launcher.py` starts the FastAPI backend and pywebview host.
2. `GUIBackend` creates an `AppShellService` with `GUIAppHost`.
3. The frontend calls `/api/app/bootstrap`.
4. The backend returns app shell state plus workspace registry state.
5. The frontend normalizes that payload into app-shell state.
6. If an active workspace exists, the frontend loads sessions, tasks, files,
   artifacts, recipes, tool catalog, and permission context through existing
   workspace/session APIs.

Workspace switch:

1. Frontend checks app-shell/session state to ensure switch is allowed.
2. Frontend calls the workspace app route.
3. `GUIAppHost` activates a workspace and binds a Core instance.
4. `AppShellService` returns the new app bootstrap payload.
5. Frontend resets workspace-scoped state and reloads active workspace data.

Settings or diagnostics surface:

1. User opens command palette or header action.
2. Frontend routes to app-shell surface state.
3. No Agent Core command is issued.
4. The surface renders app-shell state.

## Testing Strategy

Use TDD for implementation.

Backend tests:

- app-shell bootstrap includes app, diagnostics, capabilities, settings, and
  workspace state
- app-shell bootstrap does not include secret or session-history fields
- workspace activation still binds Core only through `GUIAppHost`
- no active workspace still returns app-shell state cleanly

Frontend helper tests:

- bootstrap normalization handles missing fields
- app-shell reducer opens settings and diagnostics surfaces
- app commands are visible without a session
- app commands do not produce slash-command text
- workspace-scoped reset does not erase app-level settings

Existing tests to preserve:

- GUI backend API tests
- GUI app host tests
- GUI runtime tests
- webapp state/workbench tests
- no `code` vocabulary in workbench commands

Build verification:

- `cd src/embedagent/frontend/gui/webapp && npm test`
- `cd src/embedagent/frontend/gui/webapp && npm run build`
- focused Python GUI backend tests
- fast non-GUI Python subset when implementation touches shared protocol or
  adapter code

## Documentation Updates

When implementation lands, update:

- `docs/frontend-protocol.md`
- `docs/overall-solution-architecture.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

The active docs should say that GUI app-shell state is shell-owned diagnostic and
layout/control-plane state. They should not describe it as Agent Core policy or
workflow truth.

## Implementation Slices

### Slice 1: Backend App-Shell Bootstrap

Create the backend app-shell service and update `/api/app/bootstrap` and related
workspace routes to return the richer app shell payload.

### Slice 2: Frontend App-Shell Model

Create frontend normalization and reducer helpers, then route the existing app
bootstrap state through them.

### Slice 3: Settings And Diagnostics Surfaces

Add settings and diagnostics right-panel surfaces, app commands, and minimal UI
rendering.

### Slice 4: Documentation And Cleanup

Update active docs and remove superseded GUI-internal bootstrap assumptions.

## Acceptance Criteria

- The GUI has an explicit app-shell boundary separate from Agent Core.
- `/api/app/bootstrap` returns app-level state, diagnostics, capabilities,
  settings, and workspace registry state.
- Session bootstrap remains the only GUI activation contract for session
  history.
- Settings and diagnostics are app-level surfaces, not Agent Core slash
  commands.
- App-level commands can be used without an active session.
- Agent Core does not import GUI app-shell modules.
- GUI app-shell state does not include prompts, source files, raw tool outputs,
  API keys, provider request bodies, or permission secrets.
- Tests cover backend payload shape and frontend app-shell reducer behavior.
- Existing GUI workbench/session behavior remains intact.

## Open Follow-Up After v1

After this boundary exists, the next standalone app gaps can be tackled without
thickening Core:

- terminal service and terminal bottom drawer
- source-control discovery and branch/worktree toolbar
- checkpoint diff and restore surfaces
- durable GUI settings
- richer desktop lifecycle diagnostics
- release packaging and update/smoke workflows compatible with offline Win7

