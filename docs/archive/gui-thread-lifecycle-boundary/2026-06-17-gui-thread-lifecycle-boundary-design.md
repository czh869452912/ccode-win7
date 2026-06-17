# GUI Thread Lifecycle Boundary Design

## Status

Draft for review.

## Context

The GUI now has a T3code-inspired app shell boundary. `/api/app/bootstrap` and
`/api/app/workspaces*` return GUI-owned app-shell state for workspace registry
projection, app diagnostics, app commands, app surfaces, and GUI-local
settings. The React app-shell and app-home read models keep that state separate
from Agent Core session truth.

The sidebar already renders T3code-like thread lifecycle affordances for
`Rename`, `Fork`, and `Archive`, but they are disabled because the backend/Core
does not yet expose persistent lifecycle operations. The current fallback notice
is honest, but it leaves the GUI short of the standalone-app experience: users
can list and resume threads, yet cannot manage them as app-owned records.

This slice closes that gap with a narrow lifecycle boundary. The session
history source of truth remains `transcript.jsonl`, and `Session` / live
snapshots remain the structured session state. Thread lifecycle metadata lives
in summary/projection state used for app lists, not in GUI-only local state and
not in prompt-visible transcript history.

## Goals

1. Make GUI thread `Rename`, `Fork`, and `Archive` real backend-backed actions.
2. Keep the GUI as a consumer of lifecycle APIs, not the owner of session truth.
3. Keep lifecycle state out of provider prompts, workflow policy, tool
   activation, permission decisions, extension loading, and runtime reducers.
4. Preserve offline and Windows 7 compatibility with Python 3.8-compatible code
   and no new runtime dependencies.
5. Keep archived sessions recoverable by explicit reference while hidden from
   normal recent-thread lists.

## Non-Goals

- No bulk archive/delete/multi-select.
- No hard delete of transcript, summary, artifacts, or tool-result files.
- No drag reorder or pinned/favorite threads.
- No source-control checkpoint, Git branch, commit, push, or restore operation.
- No new public plugin, workflow package, provider, or permission policy.
- No new transcript event family for rename/archive/fork in this slice.
- No GUI-local persistence that can diverge from backend session summaries.

## Recommended Approach

Add a small session lifecycle metadata API behind the existing core facade:

```text
GUI React app
  -> GUIBackend /api/sessions/{id}/rename|fork|archive
    -> InProcessAdapter.rename_session|fork_session|archive_session
      -> SessionLifecycleManager
        -> SessionSummaryStore
          -> summary.json + ProjectionDb
```

This gives the desktop shell a real thread-management boundary while keeping the
operation close to existing session summary storage. It avoids making
`GUIBackend` understand summary file layout and avoids introducing a heavier
reducer before the product has a durable need for lifecycle events.

## Alternatives Considered

### GUI-Only Backend Actions

The GUI backend could edit `summary.json` files directly. This would be fast,
but it would make the app shell a second session lifecycle owner. It would also
duplicate projection-db update behavior and make TUI or future shells unable to
reuse the same operations.

### Transcript-Backed Lifecycle Reducer

Rename/archive/fork could become explicit transcript events reduced into a
thread metadata read model. This is attractive long-term, but it is too much
surface for the immediate GUI gap. It would require new event schemas, restore
semantics, projection rules, and more documentation than this narrow slice
needs.

### Session Lifecycle Boundary

The recommended path extends the existing lifecycle/store boundary. It is small
enough to implement and verify in one slice, reusable by frontends, and aligned
with the current architecture: transcript remains history truth; summary and
projection state remain app-list read models.

## Data Model

`summary.json` gains a small `thread` object:

```json
{
  "thread": {
    "title": "Investigate build failure",
    "archived": false,
    "archived_at": "",
    "forked_from": "",
    "forked_at": ""
  }
}
```

Rules:

- `thread.title` is display metadata. It overrides `user_goal` for thread-list
  titles but does not modify transcript messages or resume prompts.
- `thread.archived` hides the session from normal `list_sessions()` results.
- `thread.archived_at` is a UTC timestamp when archived.
- `thread.forked_from` records the source session id on the forked summary.
- `thread.forked_at` records when the fork was created.
- Missing `thread` means legacy default: unarchived, no explicit title, not a
  fork.

`ProjectionDb` carries enough fields for list rendering without reopening every
summary file. Add these columns with guarded additive migration when they are
absent:

- `title`
- `archived`
- `archived_at`
- `forked_from`
- `forked_at`

Schema migration uses additive `ALTER TABLE` guarded by existing column
discovery. Do not drop or rewrite existing rows.

## Lifecycle Semantics

### Rename

Input:

```json
{ "title": "New display title" }
```

Behavior:

- Strip leading/trailing whitespace.
- Reject empty titles.
- Clamp the stored title to 120 characters.
- Load the existing summary by session id.
- Write `thread.title`.
- Preserve existing summary fields.
- Upsert projection metadata.
- Return the updated summary projection.

Rename does not resume the session, mutate transcript, append a user/assistant
message, change mode, or refresh project memory.

### Archive

Input:

```json
{}
```

Behavior:

- Load the existing summary by session id.
- Write `thread.archived = true` and `thread.archived_at = now`.
- Upsert projection metadata.
- If the archived session is currently active, the GUI may clear or switch its
  active session state after the API returns, but the backend lifecycle action
  does not cancel a running agent turn.
- Return the updated summary projection.

Archived sessions remain restorable by explicit id or transcript path. Normal
`list_sessions()` excludes archived sessions unless called with
`include_archived=True`.

### Fork

Input:

```json
{ "title": "Optional fork display title" }
```

Behavior:

- Resolve the source session transcript path from the existing summary store.
- Create a new session id.
- Copy the source transcript to the new session transcript path.
- Restore the copied transcript through the normal restore path or build a
  summary projection from the restored session.
- Write fork metadata to the new summary:
  - `thread.forked_from = source_session_id`
  - `thread.forked_at = now`
  - `thread.title = provided title` if non-empty; otherwise use source title
    plus a short suffix such as `Copy`.
- Keep the source session unchanged.
- Return the new summary projection and `session_id` for GUI activation.

Fork copies durable history; it does not create a Git branch, filesystem
snapshot, checkpoint restore point, or workflow package state clone beyond what
the copied transcript already restores.

## Backend API Contract

Add GUI backend routes:

```text
POST /api/sessions/{session_id}/rename
POST /api/sessions/{session_id}/archive
POST /api/sessions/{session_id}/fork
```

Responses are safe session summary projections:

```json
{
  "session": {
    "session_id": "sess",
    "title": "New display title",
    "current_mode": "explore",
    "updated_at": "2026-06-17T00:00:00Z",
    "summary_ref": ".embedagent/memory/sessions/sess/summary.json",
    "transcript_ref": ".embedagent/memory/sessions/sess/transcript.jsonl",
    "thread": {
      "title": "New display title",
      "archived": false,
      "archived_at": "",
      "forked_from": "",
      "forked_at": ""
    }
  }
}
```

Fork also returns the new id:

```json
{
  "session_id": "new-session-id",
  "session": {}
}
```

Error mapping:

- Missing session: `404 session_not_found`.
- Empty or invalid title: `422 invalid_thread_title`.
- Fork copy/restore failure: `422 session_fork_failed`.

Do not include transcript bodies, prompt bodies, file contents, raw tool
outputs, provider payloads, API keys, or permission details in these responses.

## Core Facade Contract

Add reusable methods on `InProcessAdapter`:

```python
def rename_session(self, session_id: str, title: str) -> Dict[str, Any]: ...
def archive_session(self, session_id: str) -> Dict[str, Any]: ...
def fork_session(self, session_id: str, title: str = "") -> Dict[str, Any]: ...
def list_sessions(self, limit: int = 10, include_archived: bool = False) -> List[Dict[str, Any]]: ...
```

`SessionLifecycleManager` owns the orchestration and delegates file/projection
mutations to `SessionSummaryStore`. This keeps `InProcessAdapter` a facade and
keeps GUI code independent of the store layout.

## App Shell Capability Contract

`AppShellService._capabilities()` exposes thread lifecycle support:

```json
{
  "thread_lifecycle": {
    "rename": true,
    "fork": true,
    "archive": true
  }
}
```

The frontend app-shell normalizer maps `thread_lifecycle` to camelCase
`threadLifecycle`, and `buildAppHomeModel()` enables thread actions only when
these backend-provided capabilities are true.

This is display capability metadata only. It does not grant permissions,
activate tools, load extensions, or change session truth.

## Frontend Behavior

The existing sidebar action rail remains the primary UI surface.

### Rename Flow

- Clicking `Rename` prompts for a new title with a small shell-local dialog or
  browser prompt in the first implementation.
- Submit `POST /api/sessions/{id}/rename`.
- Refresh the session list.
- If the renamed session is current, keep it active.
- Show an interaction notice only on failure.

### Archive Flow

- Clicking `Archive` asks for confirmation.
- Submit `POST /api/sessions/{id}/archive`.
- Refresh the session list.
- If the archived session is current, leave the current timeline visible, refresh
  the session list so the archived thread disappears from normal navigation, and
  show a non-blocking notice that the thread was archived. Do not invent a new
  frontend-only history state.

### Fork Flow

- Clicking `Fork` optionally prompts for a fork title.
- Submit `POST /api/sessions/{id}/fork`.
- Refresh the session list.
- Resume or load the returned new session id through the existing session
  activation/bootstrap path.

The frontend must not store rename/archive/fork state in localStorage or an
app-only sidecar.

## Testing Strategy

Backend unit tests:

- `SessionSummaryStore.rename_session()` writes `thread.title`, preserves
  existing summary fields, and updates list projection.
- `SessionSummaryStore.archive_session()` marks archived and hides the session
  from default `list_summaries()`.
- `SessionSummaryStore.fork_session()` creates a new session id, copies the
  transcript, writes fork metadata, and leaves the source unchanged.
- `SessionLifecycleManager` delegates lifecycle operations.
- `InProcessAdapter` exposes lifecycle facade methods without importing GUI.
- GUI backend routes map success and errors correctly.

Frontend tests:

- App-shell capability normalization includes `threadLifecycle`.
- `buildAppHomeModel()` enables lifecycle actions when capabilities are true and
  keeps them disabled otherwise.
- `handleThreadLifecycleAction()` calls the correct endpoint and refreshes
  sessions.
- Fork activation uses the returned session id.

Verification:

- `uv run pytest tests/test_session_store.py tests/test_services.py tests/test_gui_backend_api.py tests/test_gui_app_shell.py tests/test_gui_app_host.py -v`
- `cd src/embedagent/frontend/gui/webapp && npm test`
- `uv run ruff check src/embedagent/frontend/gui/backend src/embedagent/session_store.py src/embedagent/services/session_lifecycle.py src/embedagent/inprocess_adapter.py tests/`

## Documentation Updates

If implemented, update:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/frontend-protocol.md`
- `docs/modules/frontend-gui.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

The docs state that GUI thread lifecycle operations are summary/projection
metadata and not a new session-history source.

## Open Decisions Resolved For This Slice

- Archived threads are hidden from normal recent-thread lists.
- Archive is non-destructive and reversible only by future explicit UI/API; this
  slice does not add unarchive UI.
- Fork copies transcript history but does not create source-control checkpoints.
- Rename changes display metadata only and does not rewrite user messages.
- No transcript lifecycle events are added in this slice.
