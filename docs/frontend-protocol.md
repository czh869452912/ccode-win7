# Frontend Protocol

## 1. Purpose

This document describes the current stable contract between Agent Core and frontend shells.

The protocol vocabulary is now:

- `build`, not `code`
- `tasks`, not `todos`
- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`

## 2. Core Boundary

The stable contract boundary is:

- `src/embedagent/protocol/__init__.py`
- `src/embedagent/core/adapter.py`

Frontends should only rely on this boundary, not on internal session or query-engine details.

The core adapter boundary uses `get_inprocess_adapter()` internally for hosted
adapter class lookup. Legacy adapter compatibility accessors such as
`_inprocess_adapter` and `_get_adapter_class()` are not frontend protocol
contracts and have been removed.

### Workbench Shell State

GUI and TUI may keep local workbench shell state for sidebar selection,
right-panel surfaces, bottom drawers, command-palette query, keybindings, and
layout density. This state is not session-history truth and is not an
activation or permission policy.

Frontend shell state must not decide tool visibility, execute tools, approve
permissions, change durable modes, infer transcript history, load extensions,
or mutate workflow state. Those decisions remain owned by Agent Core,
ExtensionManager, PermissionPolicy, SessionHistoryAssembler, and the existing
session/bootstrap protocol.

### GUI App-Shell State

The GUI may expose a local app-shell read model for desktop-host concerns:
recent workspaces, the active workspace record, safe host/runtime/renderer
diagnostics, app-level command metadata, and GUI-local settings. The canonical
app activation bootstrap route is `GET /api/app/bootstrap`; app workspace
routes return the same envelope after mutations.

This state is owned by the GUI host and frontend shell. It is not session
history, workflow truth, tool activation policy, permission policy, extension
loading policy, provider configuration, or transcript state. It must not
include API keys, prompt bodies, source files, raw tool outputs, permission
payload secrets, or transcript entries.

Current app-shell v1 fields include `app`, `workspaces`,
`active_workspace`, `has_active_workspace`, `diagnostics`, `capabilities`,
`settings`, and `last_error`. Diagnostics are safe read-model fields for host,
runtime, renderer, workspace registry, and active-core presence only.
`capabilities.surfaces.bottom_drawer` may include `terminal`, `run_output`,
and `logs`; `capabilities.terminal` describes the GUI terminal limitations
(`enabled`, `pty`, `resize`, `history_persistent`, and `max_buffer_bytes`).
`capabilities.surfaces.right_panel` may include `source_control`, and
`capabilities.source_control` describes the local source-control surface:
`enabled`, `vcs`, `read_only`, `remote_providers`, `network`, `checkpoints`,
and `requires_active_workspace`.

The GUI terminal bottom drawer is app-shell hosted and workspace-bound. It is
implemented with Windows 7-compatible Python stdlib subprocess pipes, not a
full PTY. Its buffer and tab state are frontend/backend GUI display state only:
they are not transcript history, workflow truth, telemetry, provider/runtime
configuration, permission policy, source-control checkpoint state, or Agent
Core state.

The GUI Source Control right-panel is app-shell hosted and active-workspace
bound. It is read-only and local-only in the current contract: the GUI backend
may invoke bundled/workspace MinGit for local `status` and `diff` views, and
the frontend may display file paths, counts, and explicitly requested unified
diff text. These payloads are not app bootstrap diagnostics, transcript
history, workflow truth, telemetry, provider/runtime configuration, permission
policy, checkpoint state, extension loading policy, or Agent Core state. The
current contract does not include remote providers, push/pull, staging, commit,
or checkpoint mutation.

GUI thread lifecycle operations (`rename`, `fork`, and `archive`) are exposed
through session lifecycle endpoints and reflected in session summary/projection
metadata for app thread lists. Frontends may display and invoke these actions,
but they must not persist their own rename/archive/fork sidecar state or treat
these metadata fields as transcript history, workflow truth, tool activation
policy, permission policy, extension loading policy, or source-control
checkpoints.

GUI app-shell settings are local shell preferences unless a later documented
backend contract promotes a specific setting into durable runtime
configuration. They must not be interpreted as Agent Core policy.

## 3. Session Snapshot

Important session snapshot fields include:

- `session_id`
- `status`
- `current_mode`
- `workflow_state`
- `has_pending_permission`
- `pending_permission`
- `has_pending_input`
- `pending_input`
- `pending_interaction`
- `pending_interaction_valid`
- `runtime_source`
- `bundled_tools_ready`
- `workflow`
- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`
- `extensions`
- `extension_diagnostics`
- `runtime_config`
- `compaction_state`
- `recovery_state`
- replay metadata fields

`task_items` is the official frontend task list payload.

`max_turns`, where present in snapshots or turn-end events, is a compatibility projection for the optional loop safety limit. A missing or null value means the default Pi-style continuation path has no fixed turn-count cutoff. Frontends may display the value for diagnostics, but they must not treat it as a required session budget or infer loop policy from it.

`extensions.local_resources` may contain the latest file-only resource reload state, including counts and diagnostics for `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes`. Skill resource entries may include Agent Skills-style metadata such as `name`, `description`, `base_dir`, `disable_model_invocation`, and `prompt_visible`.

`extensions.project_extensions` may contain the hosted adapter's latest project extension load state, including counts, manifest entries, and loader diagnostics for `.embedagent/extensions/<name>/extension.json`.

`extensions.local_resources`, `extensions.project_extensions`, and `extension_diagnostics` are frontend-visible health and diagnostics state, not frontend-owned execution policy.

Future intranet/custom-service/provider/telemetry health, if exposed, belongs in diagnostics/read-model fields such as `extensions`, `extension_diagnostics`, `runtime_config`, or capability projections. Frontends may display service availability, last error, buffered telemetry counts, or source metadata, but must not decide network activation, permission policy, retry policy, extension loading, or telemetry redaction.

Permission context and tool catalog payloads may include `network` and `telemetry` permission categories. Frontends may display those categories and remember approvals through the existing backend-owned permission flow, but they must not reinterpret them as `read` or auto-run them from catalog metadata.

Capability projections are also diagnostics/read-model state. `InProcessAdapter.capability_snapshot()` may expose tools, local file resources, slash commands, workflow package manifests, and model profile metadata for future frontend inspection, but frontends must not treat that projection as active-tool policy or permission state.

Visible skills and prompt files are projected to frontend-adjacent surfaces as local `resource` descriptors plus explicit slash-command descriptors (`skill:<name>` and `prompt:<name>`). There is no first-class frontend `skill` or `prompt` capability kind yet; frontends should continue treating these files as file-only local resources plus optional commands.

`runtime_config` is reducer-backed diagnostics/read-model state. It may expose credential-free model profile metadata, registered tool names, active model-visible tool names, local resource revision metadata, capability counts, and provider snapshot records. Frontends may display this for restore/debug visibility, but they must not use it as active-tool policy, permission state, resource reload authority, or project extension load state.

`compaction_state` is reducer-backed diagnostics/read-model state. It may expose compact boundary counts, latest boundary metadata, token/message counts, preserved message anchors, trigger/phase/window-generation diagnostics, safe file activity paths, evidence refs, extension-summary flag, and diagnostics. Frontends may display this for restore/debug visibility, but they must not use it as context-selection policy, history truth, extension execution policy, permission state, or a trigger for resource reload.

`recovery_state` is reducer-backed diagnostics/read-model state. It may expose recovery marker counts, latest marker metadata, trusted-prefix counts, stop reasons, skip summaries, operation/compaction/runtime summaries, and diagnostics. Frontends may display this for restore/debug visibility, but they must not use it as restore policy, active mode/tool/context policy, extension execution policy, permission state, or a trigger for resource reload.

`workflow` is the generic workflow projection. For the default C/C++ harness, `current_phase`, `discipline_profile`, `current_activity`, `task_summary`, and `task_items` are compatibility fields projected from `workflow`.

Frontend shells should not read or infer default harness internals such as task graph state. They consume the snapshot fields and, where a richer shape is needed, the `workflow` payload.

Session activation additionally depends on one bootstrap payload containing:

- `snapshot`
- `history`
- `plan`
- `permission_context`
- `replay`

`history.integrity.status` is the official history health signal:

- `healthy`
- `partial`
- `unavailable`

## 4. HTTP API Surface

Key routes include:

- `GET /api/app/bootstrap`
- `GET /api/app/workspaces`
- `POST /api/app/workspaces`
- `POST /api/app/workspaces/{workspace_id}/activate`
- `DELETE /api/app/workspaces/{workspace_id}`
- `GET /api/app/source-control/status`
- `POST /api/app/source-control/refresh`
- `GET /api/app/source-control/diff?path=<path>&scope=<scope>`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions`
- `POST /api/sessions/{session_id}/message`
- `POST /api/sessions/{session_id}/mode`
- `POST /api/sessions/{session_id}/cancel`
- `POST /api/sessions/{session_id}/interactions/{interaction_id}/respond`
- `GET /api/sessions/{session_id}/bootstrap`
- `GET /api/sessions/{session_id}/plan`
- `GET /api/sessions/{session_id}/permissions`
- `GET /api/sessions/{session_id}/events`
- `POST /api/sessions/{session_id}/resources/reload`
- `GET /api/sessions/{session_id}/terminals`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/open`
- `GET /api/sessions/{session_id}/terminals/{terminal_id}/snapshot`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/write`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/clear`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/restart`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/resize`
- `POST /api/sessions/{session_id}/terminals/{terminal_id}/close`
- `GET /api/workspace`
- `GET /api/workspace/recipes`
- `GET /api/tool-catalog`
- `GET /api/tasks`
- `GET /api/artifacts`
- file read/tree routes

`GET /api/app/bootstrap` is the GUI app activation bootstrap contract. It
reports app-shell state only. Session activation remains exclusively
`GET /api/sessions/{session_id}/bootstrap`, whose payload contains session
snapshot, structured history, plan, permission context, and replay metadata.

`POST /api/sessions` defaults to `explore` when no mode is supplied. Frontends should not use `build` as the implicit entry mode.

`POST /api/sessions/{session_id}/resume` should preserve the restored session mode unless the caller explicitly supplies a mode override.

`POST /api/sessions/{session_id}/resources/reload` refreshes local file resources for the session and returns the backend resource snapshot. It is not a plugin execution endpoint.

Terminal routes require an active GUI workspace and are scoped by
`session_id` plus a client-chosen `terminal_id`. They expose snapshots,
summaries, limited history buffers, and non-PTY lifecycle operations for the
GUI bottom drawer only. `write` sends user text to the GUI-owned subprocess
stdin; it is not a model tool call, permission approval, transcript append, or
workflow action.

Source-control routes require an active GUI workspace. `status` and `refresh`
return a local Git status read model; `diff` returns a read-only unified diff
for a workspace-contained file path and `unstaged` or `staged` scope. These
routes are GUI display routes, not model tool calls, permission approvals,
transcript appends, workflow actions, remote Git providers, or checkpoint
mutations.

`/skill:<name> [args]` and `/prompt:<name-or-path> [args]` are handled through the normal message submission path, not separate HTTP endpoints. On success the backend expands the workspace-bound Markdown/text resource into the user turn; on failure it emits a normal `command_result` for the resource command. Visible resource commands may appear in `/help` output and command capability snapshots as `skill:<name>` or `prompt:<name>`.

## 5. WebSocket Event Types

Important pushed event types include:

- `session_status`
- `stream_delta`
- `reasoning_delta`
- `thinking_state`
- `tool_start`
- `tool_finish`
- `permission_request`
- `user_input_request`
- `command_result`
- `plan_updated`
- `turn_start`
- `turn_end`
- `session_finished`
- `tasks_refresh`
- `artifacts_refresh`
- `message`
- `session_event`
- `terminal_event`

`GET /api/sessions/{session_id}/events` is transport replay only. Frontend history bootstrap must come from the structured bootstrap payload, not replay-log parsing.

`terminal_event` carries GUI terminal output/lifecycle deltas for the bottom
drawer. It is intentionally not part of session replay/history and must not be
reduced into `Session`, `SessionHistoryAssembler`, `RuntimeConfigReducer`,
`CompactionStateReducer`, or `RecoveryStateReducer`.

Resource reload may appear in replay as `resource.discovered` and `resource.reloaded` event kinds. Frontends may use those for diagnostics or refresh hints, but session history remains transcript/bootstrap-backed.

Reducer-backed `runtime_config.resource_revision` advances from transcript `resource_reloaded` events. `resource.discovered` events remain diagnostics and should not be treated as a new active resource revision by frontend code.

Reducer-backed `compaction_state` advances from transcript `compact_boundary` events. Frontends should not infer compaction from replay transport events, summary text alone, or timeline entries.

Reducer-backed `recovery_state` advances from transcript `recovery_marker` events. Frontends should not infer recovery state from replay transport events, timeline gaps, or session summary fields alone.

All live tool/interaction/command events must preserve the engine-issued execution anchors:

- `turn_id`
- `step_id`
- `step_index`

Frontend shells must treat these as authoritative and must not synthesize replacement step ids.

## 6. Tool Catalog

The frontend-visible tool catalog should represent the official workflow vocabulary used by the product shell.

The UI should not use the catalog to reintroduce deprecated mode/tool naming.

Catalog visibility is computed from workflow-neutral mode contracts plus tools activated by the hosted runtime's shared `ExtensionManager`. This lets the shell display harness tool metadata such as `task_status` while keeping `modes.py` independent from the harness pack design and avoiding a separate frontend-only extension chain.

Catalog entries include tool source metadata:

- `source_type`
- `source_id`

Frontends may display dynamic tool source metadata for diagnostics or future extension management. They must continue to treat tool permission behavior as backend-owned and derive permission prompts only from backend events.

Extension diagnostics are frontend-visible health information. Frontends may display them, but they must not infer extension execution policy from them.

Project extension loader failures are mirrored into `extension_diagnostics`. Frontends may display the health information and project extension source metadata, but permission prompts and execution policy remain backend-owned.

Provider turn snapshot metadata may appear in operation diagnostics as `snapshot_id`, mode/workflow state, registered tool names, active tool names, credential-free model profile metadata, resource revision metadata, safe prompt units such as `local_skill_listing`, and capability counts. Frontends may display this for debugging, but full prompts, skill bodies, prompt bodies, file contents, raw tool outputs, and API keys are not part of the frontend protocol.

Telemetry and intranet sink status, if later surfaced, is frontend-visible health only. Frontend protocols must not carry prompts, source text, raw tool outputs, API keys, approval secrets, or permission tokens for telemetry export.

Compaction metadata may appear in `compaction_state` as safe counts, message ids, file paths, and stored evidence refs. Frontends may display this for debugging, but full compacted prompts, raw file contents, raw tool outputs, and API keys are not part of the frontend protocol.

Recovery metadata may appear in `recovery_state` as safe counts, stop reasons, reducer summaries, and trusted-prefix metadata. Frontends may display this for debugging, but prompts, messages, raw tool outputs, file contents, and API keys are not part of the frontend protocol.

For `task_status`, the official presentation metadata is:

- `progress_renderer_key = "tasks"`
- `result_renderer_key = "tasks"`
- `activity_kind = "task"`

## 7. TUI / GUI Rule

TUI and GUI may present different interaction surfaces, but they must agree on:

- session snapshot meaning
- task payload meaning
- permission context meaning
- mode names

If the shells disagree on those semantics, the protocol is drifting and must be corrected.
