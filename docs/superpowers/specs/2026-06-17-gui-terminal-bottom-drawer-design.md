# GUI Terminal Bottom Drawer Design

## Goal

Build the next T3 Code-style standalone GUI slice: a real thread-scoped
terminal bottom drawer, while preserving EmbedAgent's hard runtime baseline.

Windows 7 support is a release-blocking constraint. If terminal completeness
conflicts with Windows 7, offline deployment, Python 3.8, or the current small
dependency surface, this slice must choose the smaller compatible behavior.

## Reference Shape From T3 Code

Use `reference/t3code` as the product-shape reference, not as code to copy.

Relevant reference areas:

- `apps/web/src/components/ThreadTerminalDrawer.tsx`
- `apps/web/src/terminalUiStateStore.ts`
- `apps/web/src/terminalSessionState.ts`
- `packages/contracts/src/terminal.ts`
- `packages/shared/src/terminalLabels.ts`
- `apps/server/src/terminal/Services/Manager.ts`

The useful T3 Code shape is:

- terminal drawer is thread-scoped
- terminal ids are client-chosen `term-N`, starting at `term-1`
- frontend owns drawer UI state: open/closed, height, active terminal, tabs,
  groups/splits
- backend owns terminal session truth: status, cwd, pid, history, label,
  output stream, exit/error state
- attach first sends a snapshot, then streams output/lifecycle events
- terminal labels prefer backend summary labels, falling back to `Terminal N`
- the UI can clear, close, restart, create another terminal, and later resize

EmbedAgent should copy that architecture shape, but not its stack. T3 Code uses
PTY-oriented server infrastructure and xterm surfaces. EmbedAgent's first slice
must stay compatible with Windows 7 and the existing offline bundle.

## Current EmbedAgent Baseline

The GUI already has:

- T3-style app shell and workbench layout
- `BOTTOM_DRAWER_SURFACES = ["terminal", "run_output", "logs"]`
- a placeholder `BottomDrawer.jsx` that shows run output/log lines
- app-shell capabilities and settings under `AppShellService`
- a WebSocket channel already used for session events
- static webapp build targeting Chrome/WebView2 109

The GUI does not yet have:

- terminal backend session registry
- terminal HTTP/WebSocket routes
- thread-scoped terminal summaries or snapshots
- terminal output buffering
- terminal write/clear/close actions
- terminal drawer tabs or active terminal state

## Hard Constraints

1. Windows 7 remains mandatory.
2. Offline deployment remains mandatory.
3. Runtime remains Python `>=3.8,<3.9`.
4. Do not add runtime dependencies such as `node-pty`, `pywinpty`, `pexpect`,
   Electron, Docker, WSL, VS Code, or external services.
5. Do not depend on ConPTY, Windows Terminal APIs, pseudo consoles, or a modern
   Windows-only terminal stack.
6. Do not add runtime Node.js requirements.
7. Do not execute terminal commands through Agent Core tools.
8. Do not write terminal output into `transcript.jsonl`.
9. Do not let terminal UI state become workflow truth, permission policy,
   extension policy, source-control policy, or checkpoint policy.

## Scope

### In Scope

- GUI backend terminal service under `src/embedagent/frontend/gui/backend/`
- thread/session-scoped terminal ids: `term-1`, `term-2`, ...
- safe terminal cwd resolution inside the active workspace
- backend terminal session registry, snapshots, summaries, output history, and
  lifecycle state
- stdlib subprocess-backed shell process with stdout/stderr reader threads
- terminal actions:
  - list summaries
  - open or attach
  - write input
  - clear history
  - restart
  - close one terminal or all terminals for a session
  - resize route accepted as a no-op diagnostic for this slice
- terminal event stream over the existing GUI WebSocket connection
- frontend terminal model/reducer for summaries, buffers, status, active
  terminal, and event application
- bottom drawer UI that renders T3 Code-like terminal tabs, toolbar, status,
  output buffer, and a command input
- app-shell capability metadata for terminal availability and limitations
- tests for backend service/routes and frontend pure terminal model
- documentation updates

### Out Of Scope

- Full PTY emulation
- xterm.js or other new frontend dependencies
- ANSI color parsing beyond safe plain-text display
- process tree detection
- true terminal resize
- split panes
- terminal context injection into composer prompts
- terminal link detection/open-in-editor
- persisted terminal history across GUI restarts
- source-control commands
- checkpoint creation or restore
- Agent Core permission changes
- C/C++ harness tool changes

Those are future slices after this boundary exists.

## Product Behavior

### Drawer

The bottom drawer gains a real `terminal` surface. It should feel like T3 Code:

- compact tab rail for terminal sessions
- `+` action creates the next client-side id (`term-1`, `term-2`, ...)
- active terminal tab shows backend label or `Terminal N`
- toolbar shows status, cwd, and close/clear/restart actions
- output area uses a monospace scrollable buffer
- input row sends raw text to the terminal process
- Enter submits input with a trailing newline
- clear empties displayed/backend history but does not kill the process
- close terminates the terminal session
- restart closes and reopens the same terminal id in the same cwd

Because this first slice uses pipes rather than a PTY, interactive behavior is
best-effort. Programs that require a real TTY may not render correctly. That is
acceptable only if the UI and docs are honest about the limitation.

### Session Identity

The GUI treats terminal sessions as session/thread scoped:

- terminal key: `(session_id, terminal_id)`
- terminal ids are always supplied by the frontend
- backend rejects empty or oversized ids
- backend never allocates ids
- frontend `nextTerminalId(existingIds)` chooses the lowest unused `term-N`

This mirrors the T3 Code client-chosen id contract and avoids hidden backend UI
state allocation.

### Shell Selection

The backend chooses a Windows 7-compatible shell:

1. Use `COMSPEC` when it points to an existing executable.
2. Fall back to `cmd.exe`.
3. Optionally allow PowerShell only when explicitly configured later.

This slice should not prefer `pwsh.exe`, Windows Terminal, ConPTY, or any
modern terminal-only path.

On non-Windows development hosts, use `/bin/sh` when available. This is only to
keep tests and developer workflows portable; the product runtime target remains
Windows 7.

### Cwd Rules

Terminal cwd must stay inside the active workspace:

- empty cwd defaults to active workspace root
- relative cwd resolves under active workspace root
- absolute cwd is accepted only if it is inside active workspace root
- missing cwd returns `terminal_cwd_not_found`
- file cwd returns `terminal_cwd_not_directory`
- workspace escape returns `terminal_cwd_outside_workspace`

This is a GUI-hosted safety boundary. It is not an Agent Core permission rule.

## Backend Architecture

Create `src/embedagent/frontend/gui/backend/terminal_service.py`.

Responsibilities:

- own in-memory terminal sessions for one GUI backend process
- validate session id, terminal id, cwd, cols, and rows
- start subprocesses with `stdin`, `stdout`, and `stderr` pipes
- read stdout/stderr on background daemon threads
- append output to a bounded string buffer
- emit terminal events through a callback supplied by `GUIBackend`
- produce serializable snapshots and summaries
- terminate processes on close and backend shutdown

Suggested public shape:

```python
class TerminalService(object):
    def list_sessions(self, session_id=None):
        ...

    def open_or_attach(self, session_id, terminal_id, cwd="", cols=80, rows=24):
        ...

    def write(self, session_id, terminal_id, data):
        ...

    def clear(self, session_id, terminal_id):
        ...

    def restart(self, session_id, terminal_id, cwd="", cols=80, rows=24):
        ...

    def resize(self, session_id, terminal_id, cols, rows):
        ...

    def close(self, session_id, terminal_id=""):
        ...

    def shutdown(self):
        ...
```

Use `threading.RLock` around registry mutations. Keep event callbacks outside
the lock when possible.

### Snapshot Shape

```json
{
  "session_id": "session-123",
  "terminal_id": "term-1",
  "cwd": "D:/project",
  "status": "running",
  "pid": 1234,
  "history": "...",
  "exit_code": null,
  "label": "Terminal 1",
  "updated_at": "2026-06-17T00:00:00Z",
  "sequence": 4,
  "capabilities": {
    "stdin": true,
    "resize": false,
    "pty": false
  }
}
```

Status values:

- `starting`
- `running`
- `exited`
- `error`
- `closed`

### Event Shape

```json
{
  "type": "terminal_event",
  "event": {
    "type": "output",
    "session_id": "session-123",
    "terminal_id": "term-1",
    "sequence": 5,
    "data": "hello\n"
  }
}
```

Event types:

- `snapshot`
- `started`
- `output`
- `cleared`
- `restarted`
- `exited`
- `closed`
- `error`
- `resized`

### HTTP API

Add routes under the existing GUI backend:

- `GET /api/sessions/{session_id}/terminals`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/open`
- `GET /api/sessions/{session_id}/terminals/{terminal_id}/snapshot`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/write`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/clear`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/restart`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/resize`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/close`

These routes require an active workspace, but they do not require an active
Agent Core session engine. They use the session id as a thread key for GUI
terminal grouping.

Error mapping:

- no active workspace -> `409`
- invalid terminal id -> `422`
- cwd missing/outside/not directory -> `422`
- terminal not found -> `404`
- terminal not running on write -> `409`

## Frontend Architecture

Create a focused terminal model under:

- `src/embedagent/frontend/gui/webapp/src/terminal/terminal-labels.js`
- `src/embedagent/frontend/gui/webapp/src/terminal/terminal-state.js`
- `src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js`

Responsibilities:

- `getTerminalLabel(terminalId)`
- `nextTerminalId(existingIds)`
- normalize snapshots/summaries/events
- reduce events into terminal state
- keep buffers bounded
- keep active terminal valid when tabs close
- expose a small API wrapper around terminal HTTP routes

Modify `BottomDrawer.jsx` so `activeKind === "terminal"` renders the terminal
surface; `run_output` and `logs` keep existing behavior.

Modify `App.jsx` only as the composition layer:

- ensure terminal drawer opens through existing workbench surface actions
- create/attach `term-1` when a session is active and terminal drawer opens
- subscribe to existing WebSocket messages and feed `terminal_event` into the
  terminal reducer
- pass terminal state/actions into `BottomDrawer`

Do not put terminal state into Agent Core snapshots or app-shell bootstrap.
Only app-shell capabilities should advertise whether the GUI host supports the
terminal surface.

## App-Shell Capability

Extend `AppShellService._capabilities()` with:

```json
{
  "terminal": {
    "enabled": true,
    "pty": false,
    "resize": false,
    "history_persistent": false,
    "max_buffer_bytes": 131072
  }
}
```

This is a capability description for the GUI shell. It is not permission
policy, tool policy, or an Agent Core capability.

## Win7 Compatibility Plan

This slice must pass a compatibility checklist before implementation is called
complete:

- all Python code uses Python 3.8 syntax
- backend uses only standard library process/threading/queue/subprocess APIs
- no ConPTY imports, no pywinpty, no pty module on Windows path
- default Windows shell is `COMSPEC` or `cmd.exe`
- no frontend dependency additions
- webapp continues to build for Chrome/WebView2 109
- terminal routes work without network beyond localhost
- process cleanup uses conservative `terminate` then best-effort `kill`
- docs state that pipe-backed terminal is not a full PTY

## Security And Safety

This is a local GUI feature. Still, it launches arbitrary shell commands typed
by the user. Keep the boundary explicit:

- terminal starts only after explicit user UI action
- no model/tool can write to terminal through this feature in this slice
- terminal output is not sent to the model
- terminal output is not stored in transcript
- terminal output is not telemetry
- terminal cwd is workspace-bound
- no shell command is launched by app bootstrap
- closing workspace or backend shutdown closes terminals

Future model-visible terminal context must be a separate reviewed slice.

## Testing Strategy

### Backend Unit Tests

Add tests in `tests/test_gui_terminal_service.py`:

- validates `term-N` ids and rejects empty/unsafe ids
- resolves cwd inside workspace and rejects escapes
- opens a short-lived process and captures output
- write sends input to a running process in a deterministic fake process
- clear empties history and emits `cleared`
- close terminates/removes one terminal
- close all removes all terminals for a session
- resize returns a snapshot/event but advertises `resize: false`
- shutdown terminates all processes

Where real subprocess behavior would be flaky, inject a small fake process
factory into `TerminalService`.

### Backend API Tests

Extend `tests/test_gui_backend_api.py` or add
`tests/test_gui_terminal_api.py`:

- no active workspace returns 409
- open returns snapshot with `pty: false`
- terminal output events are broadcast as `terminal_event`
- cwd outside workspace returns 422
- write to missing terminal returns 404
- close returns closed payload

### Frontend Tests

Add `src/embedagent/frontend/gui/webapp/test/terminal-state.test.mjs`:

- `nextTerminalId(["term-1"]) === "term-2"`
- labels use `Terminal N`
- event reducer applies snapshot/output/cleared/exited/closed/error
- buffer is bounded
- active terminal falls back after close

Add a `BottomDrawer` helper test only if existing test harness can render it
without a browser. Otherwise keep render coverage in visual harness.

### Build And Regression

Minimum verification for the implementation slice:

- `uv run pytest tests/test_gui_terminal_service.py tests/test_gui_terminal_api.py tests/test_gui_backend_api.py tests/test_gui_app_shell.py -v`
- `cd src/embedagent/frontend/gui/webapp && npm test`
- `cd src/embedagent/frontend/gui/webapp && npm run build`
- `uv run ruff check src/embedagent/frontend/gui/backend tests/test_gui_terminal_service.py tests/test_gui_terminal_api.py`
- `uv run pytest tests/ -m "not slow and not gui" -v`

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

The docs must say that GUI terminal is a hosted app-shell capability with a
Win7-compatible pipe-backed backend in this slice, not an Agent Core terminal
tool, not a PTY, not transcript truth, not telemetry, and not source-control or
checkpoint policy.

## Acceptance Criteria

- GUI app-shell advertises terminal capability and limitations.
- A user can open the terminal bottom drawer for an active session.
- The drawer creates or attaches `term-1`.
- Backend returns a terminal snapshot and streams output events.
- User input can be written to the shell process.
- Clear, restart, and close work through backend routes.
- Cwd is workspace-bound.
- Terminal output stays out of transcript/session history.
- Implementation adds no runtime dependencies.
- Webapp build still targets WebView2 109-compatible output.
- Tests cover backend service, backend routes, frontend terminal state, and
  existing GUI app-shell behavior.

## Later Slices

After this boundary lands, possible follow-up slices are:

- terminal context selection into composer prompt text
- terminal link detection and open-in-editor
- source-control read model and branch/status toolbar
- checkpoint diff and restore surface
- optional real PTY adapter only if a Win7/offline-compatible bundled strategy
  is proven and documented

