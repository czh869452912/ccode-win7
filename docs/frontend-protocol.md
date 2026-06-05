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
- replay metadata fields

`task_items` is the official frontend task list payload.

`extensions.local_resources` may contain the latest file-only resource reload state, including counts and diagnostics for `.embedagent/skills`, `.embedagent/prompts`, and `.embedagent/recipes`.

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
- `GET /api/workspace`
- `GET /api/workspace/recipes`
- `GET /api/tool-catalog`
- `GET /api/tasks`
- `GET /api/artifacts`
- file read/tree routes

`POST /api/sessions` defaults to `explore` when no mode is supplied. Frontends should not use `build` as the implicit entry mode.

`POST /api/sessions/{session_id}/resume` should preserve the restored session mode unless the caller explicitly supplies a mode override.

`POST /api/sessions/{session_id}/resources/reload` refreshes local file resources for the session and returns the backend resource snapshot. It is not a plugin execution endpoint.

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

`GET /api/sessions/{session_id}/events` is transport replay only. Frontend history bootstrap must come from the structured bootstrap payload, not replay-log parsing.

Resource reload may appear in replay as `resource.discovered` and `resource.reloaded` event kinds. Frontends may use those for diagnostics or refresh hints, but session history remains transcript/bootstrap-backed.

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
