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
- `runtime_source`
- `bundled_tools_ready`
- `current_phase`
- `discipline_profile`
- `current_activity`
- `task_summary`
- `task_items`
- replay metadata fields

`task_items` is the official frontend task list payload.

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
- `GET /api/workspace`
- `GET /api/workspace/recipes`
- `GET /api/tool-catalog`
- `GET /api/tasks`
- `GET /api/artifacts`
- file read/tree routes

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

## 6. Tool Catalog

The frontend-visible tool catalog should represent the official workflow vocabulary used by the product shell.

The UI should not use the catalog to reintroduce deprecated mode/tool naming.

## 7. TUI / GUI Rule

TUI and GUI may present different interaction surfaces, but they must agree on:

- session snapshot meaning
- task payload meaning
- permission context meaning
- mode names

If the shells disagree on those semantics, the protocol is drifting and must be corrected.
