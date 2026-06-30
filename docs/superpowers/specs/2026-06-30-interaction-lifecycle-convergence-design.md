# Interaction Lifecycle Convergence Design

## Purpose

This design defines the official pre-release correction for GUI/TUI permission and
`ask_user` interaction drift.

The target is architecture convergence, not a new product invention:

- Agent Core keeps durable interaction truth in `Session.pending_interaction`.
- Hosted runtime uses one blocking pending interaction ticket instead of split
  permission/user-input fields.
- Agent and TUI follow Pi's session-owned confirm/input/abort philosophy.
- GUI follows T3 Code's projection plus command-response organization.
- Old public permission/user-input response paths are deleted or demoted behind
  the unified interaction response contract.

This work must preserve Windows 7 compatibility, offline operation, Python 3.8
syntax, and the default C/C++ workflow baseline.

## Problem Statement

Recent cleanup moved GUI `ask_user` and permission responses toward a unified
endpoint:

`POST /api/sessions/{session_id}/interactions/{interaction_id}/respond`

The implementation still has lifecycle split:

- `HostedInteractionService.respond_to_interaction()` routes back into separate
  `approve_permission`, `reject_permission`, and `reply_user_input` public paths.
- `ManagedSession` stores hosted blocking state as `pending_permission` and
  `pending_user_input`, plus separate permission/user-input events and results.
- GUI permission responses include policy data such as `category`; the backend
  should derive permission category from the active pending ticket.
- GUI response busy state is one app-level string, not request-id scoped.
- `waiting_permission` is not consistently treated as an interruptible running
  turn, so Stop/Cancel can disappear while approval blocks the turn.
- TUI also keeps permission and user-input as two local pending state paths.
- Tests cover user-input response more strongly than permission approval,
  session memory, stale response, and interrupt behavior.

The observed `interaction_expired` symptom is a lifecycle symptom: the backend
cannot reliably match the submitted id against the current split hosted pending
state. Treating it as a button bug would keep the same architecture drift.

## Reference Grounding

### Pi For Agent/TUI

Use Pi as the reference for Agent Core and terminal interaction semantics:

- `reference/pi/packages/agent/src/agent-loop.ts` passes `AbortSignal` through
  `beforeToolCall`, tool execution, and result finalization. If the signal is
  aborted while preparing a tool, the loop produces an "Operation aborted" tool
  result instead of taking a separate UI-owned execution path.
- `reference/pi/packages/agent/src/types.ts` defines `beforeToolCall` as a
  runtime hook that can block execution by returning `{ block: true, reason }`.
  Blocking becomes a tool result, not a frontend-maintained pending state.
- `reference/pi/packages/coding-agent/src/core/extensions/types.ts` exposes
  `confirm`, `input`, `select`, `signal`, and `abort()` through runtime/session
  context. UI shells provide interaction surfaces; the session owns operation
  cancellation.
- `reference/pi/packages/coding-agent/src/modes/interactive/interactive-mode.ts`
  calls session abort when interactive input handling needs to cancel the active
  operation.

EmbedAgent adaptation:

- `Session.pending_interaction` plus `AgentKernel.record_pending_*()` and
  `AgentKernel.resolve_pending_interaction()` remain the durable Core truth.
- Hosted runtime may block a live thread while waiting for shell input, but it
  must expose that as one pending interaction ticket.
- TUI should submit interaction decisions through the same unified response
  service used by GUI; it should not keep public `approve/reject/reply` product
  paths.
- Cancel/Stop while waiting for permission or user input must resolve through
  the session-owned interrupt/abort path, not through local UI state mutation.

### T3 Code For GUI

Use T3 Code as the reference for GUI organization:

- `reference/t3code/packages/contracts/src/orchestration.ts` defines
  `ProviderApprovalDecision` as `accept`, `acceptForSession`, `decline`,
  `cancel`; approval response is `thread.approval.respond` with `requestId` and
  `decision`; user input response is `thread.user-input.respond` with
  `requestId` and `answers`.
- `reference/t3code/packages/client-runtime/src/operations/commands.ts` sends
  typed command payloads instead of letting UI components mutate runtime state.
- `reference/t3code/apps/web/src/session-logic.ts` derives open approvals from
  activities and removes them on `approval.resolved` or stale-response failure.
- `reference/t3code/apps/web/src/components/ChatView.tsx` tracks approval and
  user-input response in flight by request id.
- `reference/t3code/apps/web/src/components/chat/ComposerPendingApprovalPanel.tsx`
  and `ComposerPendingApprovalActions.tsx` separate pending approval display
  from the decision buttons.
- `reference/t3code/apps/web/src/components/chat/ComposerPendingUserInputPanel.tsx`
  and `reference/t3code/apps/web/src/pendingUserInput.ts` keep user-input draft
  state local to the composer and submit an `answers` object.

EmbedAgent adaptation:

- GUI must use T3's projection and command-response shape, not T3's persistence
  stack. EmbedAgent's source of truth remains `snapshot.pending_interaction`,
  not a projection database or frontend-owned activity ledger.
- Because EmbedAgent currently supports one active pending interaction, GUI
  read-model arrays contain zero or one item. The array shape is acceptable only
  as a component contract borrowed from T3, not as a new multi-pending runtime
  promise.
- Approval response payloads should use `decision`; user-input payloads should
  use `answers`. Do not invent a third generic `action` vocabulary.

## Chosen Architecture

Adopt one product interaction lifecycle:

`Core pending interaction -> hosted pending ticket -> session snapshot -> shell read model -> response command -> HostedInteractionService.respond_to_interaction() -> Core resume or cancel -> new snapshot/session events`

There is one public product response path for GUI and TUI:

`respond_to_interaction(session_id, interaction_id, payload)`

Permission and user-input remain different interaction kinds, but they are
variants of one pending lifecycle. Old compatibility state shapes are removed
instead of wrapped indefinitely.

## Backend Design

### Core Truth

Do not replace the existing Core durable boundary:

- `Session.pending_interaction`
- `PendingInteraction`
- `AgentKernel.record_pending_permission()`
- `AgentKernel.record_pending_user_input()`
- `AgentKernel.resolve_pending_interaction()`
- `AgentLifecycleJournal` pending operation events

These are the transcript/session truth used by resume and restore. The slice
converges hosted runtime and shell APIs onto this truth.

### Hosted Pending Ticket

Replace `ManagedSession.pending_permission` and
`ManagedSession.pending_user_input` with one hosted pending ticket.

Required hosted ticket fields:

- `interaction_id`
- `kind`: `permission` or `user_input`
- `session_id`
- `tool_name`
- `created_at`
- `turn_id`
- `step_id`
- `step_index`
- `payload`

For `permission`, payload includes:

- `category`
- `reason`
- `details`
- `request_kind`: `command`, `file-read`, or `file-change`

For `user_input`, payload includes:

- `questions`
- `details`

For the current single-question `ask_user` contract, `questions` contains one
question derived from the current `UserInputRequest`:

- `id`: stable question id for the request, for example `answer`
- `question`
- `options`: option labels/descriptions derived from existing `UserInputOption`
- `multi_select`: false

The hosted ticket may keep internal fields needed to map the single submitted
answer back to `UserInputResponse`, but those fields are backend-owned.

### ManagedSession Runtime Fields

`ManagedSession` should converge to:

- `pending_interaction`
- `pending_event`
- `pending_response`
- `remembered_permission_categories`
- `stop_event`

The old split fields should be removed:

- `pending_permission`
- `pending_user_input`
- `pending_result`
- `pending_user_event`
- `pending_user_response`

Implementation may use private helper dataclasses inside
`HostedInteractionService`, but the live session state must not publish separate
permission/user-input pending slots.

### Response Payloads

The official response endpoint remains unified, but payloads follow T3's
kind-specific vocabulary.

Permission response:

```json
{
  "decision": "accept | acceptForSession | decline | cancel"
}
```

User-input response:

```json
{
  "answers": {
    "answer": "selected option or custom answer"
  }
}
```

For the current single-question `ask_user` implementation, the backend maps the
first/known answer value to `UserInputResponse.answer`. If the answer matches a
known option, the backend derives `selected_index`, `selected_mode`, and
`selected_option_text` from the hosted ticket. The frontend must not submit
`selected_mode` or permission `category` as runtime authority.

Compatibility keys such as `response_kind`, frontend-supplied `category`,
`remember`, `selected_mode`, and `selected_option_text` must not remain product
contract fields after this slice. Tests may include rejection coverage for stale
legacy shapes.

### Permission Semantics

Permission decisions mean:

- `accept`: approve current request once.
- `acceptForSession`: approve current request and remember the backend-derived
  permission category for the current session.
- `decline`: reject current request and let the turn receive a denied permission
  result.
- `cancel`: interrupt the current turn.

Session memory is updated only when the active hosted pending ticket is a
permission ticket and decision is `acceptForSession`.

### User-Input Semantics

User-input responses mean:

- `answers`: resolve the active user-input request with answers for the hosted
  pending ticket's questions.
- `cancel` is not a user-input answer payload. Shell cancel/stop should use the
  same session interrupt path as permission `cancel`.

This slice keeps the current single-question Core `ask_user` behavior. Full T3
multi-question user input is a separate protocol and tool-schema change.

### Cancel And Interrupt

Waiting for permission and waiting for user input are active turn states.

Cancel/Stop must:

- set the session stop/abort signal;
- release any hosted pending wait;
- finish or interrupt the pending operation through lifecycle events;
- return a fresh snapshot;
- leave no shell-owned pending state behind.

This follows Pi's signal-owned cancellation model. A cancelled permission should
not be treated as "decline and continue" unless the Core resume path explicitly
chooses that behavior for a safe diagnostic result.

### Error Semantics

Backend errors must be structured and stable:

- Unknown or already-resolved interaction id: HTTP 410 `interaction_expired`.
- Submitted id does not match the current active hosted pending id while another
  pending interaction exists: HTTP 409 `interaction_conflict`.
- Invalid payload for the active interaction kind: HTTP 422
  `invalid_interaction_response`.
- Missing active session: existing session-not-found/no-active-workspace mapping.

Every successful response returns a serialized session snapshot. For 409 and
410 failures, shells reload the session snapshot and show a bounded notice
without inventing frontend-owned history.

### Public API Deletion

Remove from product-facing APIs after callers are migrated:

- `approve_permission(session_id, permission_id)`
- `reject_permission(session_id, permission_id)`
- `reply_user_input(session_id, request_id, answer, ...)`

They must not appear as first-class methods on `CoreInterface`,
`InProcessAdapter`, GUI routes, TUI services, or webapp calls. Private helpers
inside `HostedInteractionService` are allowed only if the public product path is
still `respond_to_interaction()`.

## GUI Design

### Read Model

Reuse or refactor the focused GUI session-runtime interaction module to derive
T3-style read models from `snapshot.pending_interaction`.

Projected shape:

- `pendingApprovals: PendingApproval[]`
- `pendingUserInputs: PendingUserInput[]`
- `activePendingApproval`
- `activePendingUserInput`
- `activePendingKind`
- `isInteractionBlocking`
- `isTurnInterruptible`

The source is only `snapshot.pending_interaction` plus
`snapshot.pending_interaction_valid`. Raw `permission_request` and
`user_input_request` WebSocket messages may trigger reload/current blocking UI
updates, but they must not synthesize durable `interaction.created` history or a
parallel pending ledger.

### Response State

Follow T3's request-id response tracking:

- Track approval response ids and user-input response ids by request id.
- Duplicate response for the same id is ignored while in flight.
- Unrelated future ids are not blocked by stale global state.
- Success, conflict, expiry, and failure paths clear the id.

This replaces the current single global `interactionResponseInFlight` string.

### Components

Split the current combined composer interaction panel into T3-style modules,
using existing project naming conventions:

- `ComposerPendingApprovalPanel.jsx`
- `ComposerPendingApprovalActions.jsx`
- `ComposerPendingUserInputPanel.jsx`
- `ComposerInteractionNotice.jsx` if notice rendering is not already isolated

Components receive read models and callbacks only. They do not build permission
policy payloads.

Approval actions match T3 semantics:

- Cancel turn -> `decision: "cancel"` or shell interrupt path
- Decline -> `decision: "decline"`
- Always allow this session -> `decision: "acceptForSession"`
- Approve once -> `decision: "accept"`

User-input options and custom text update composer-local draft state and submit:

```json
{
  "answers": {
    "answer": "..."
  }
}
```

### Primary Composer Actions

Introduce or centralize one status helper:

- `isTurnRunning(status)`
- `isTurnWaitingForInteraction(status)`
- `isTurnInterruptible(status)`

`waiting_permission` and `waiting_user_input` are interruptible. Stop/Cancel
must remain visible while either pending interaction is active.

The composer input auto-size issue is separate UI correctness work and is out
of scope for this lifecycle convergence slice.

## TUI Design

TUI follows Pi, not GUI-internal state:

- Keep `SessionState.current_snapshot` as the source for pending interaction
  display.
- Replace `SessionState.pending_permission` and
  `SessionState.pending_user_input` with a single derived/current
  `pending_interaction` view if local convenience state is still needed.
- Replace `SessionService.approve()`, `reject()`, and `reply_user_input()` with
  `respond_to_interaction(session_id, interaction_id, payload)`.
- `y`, `yes`, `n`, and `no` are terminal shortcuts that build T3-compatible
  approval decisions.
- Numeric or text answers build the `answers` object for the active user-input
  question.
- `/cancel`, Ctrl-C handling, and Stop-style commands should call the session
  interrupt path, matching Pi's session-owned abort behavior.

TUI must not maintain a second durable interaction stream. It is a shell over
the hosted/Core lifecycle.

## Protocol And Snapshot Design

Session snapshots remain activation truth:

- `snapshot.pending_interaction`
- `snapshot.pending_interaction_valid`
- `snapshot.status`

The pending interaction payload should expose enough shell read-model data for
T3-style GUI/TUI projection:

- common: `interaction_id`, `kind`, `tool_name`, `turn_id`, `step_id`,
  `step_index`, `created_at`
- permission: `category`, `reason`, `details`, `request_kind`
- user_input: `questions`, `details`

No new durable GUI activity ledger is introduced. GUI session activation still
comes from `GET /api/sessions/{id}/bootstrap` and
`SessionHistoryAssembler.build()`.

## Testing Strategy

### Python Tests

Add or update tests for:

- `HostedInteractionService.respond_to_interaction()` permission
  `decision: accept`.
- Permission `acceptForSession` updates remembered categories from the
  backend-owned ticket category.
- Permission `decline` resumes/finishes through the same pending lifecycle.
- Permission `cancel` interrupts the active turn and clears hosted pending
  interaction.
- User-input `answers` still emits ask_user completion and clears pending
  interaction.
- Unknown id maps to `interaction_expired`.
- Mismatched active id maps to `interaction_conflict`.
- Invalid kind/payload maps to `invalid_interaction_response`.
- `CoreInterface`, `InProcessAdapter`, TUI services, and GUI routes expose only
  unified response for product interaction resolution.
- Restored Core `Session.pending_interaction` is rebuilt into one hosted pending
  ticket, not split `pending_permission`/`pending_user_input` state.

### Webapp Tests

Add or update tests for:

- Pending snapshot projects into approval read model.
- Pending snapshot projects into user-input read model with `questions`.
- Approval actions call shared response controller with `accept`,
  `acceptForSession`, `decline`, and `cancel`.
- User-input response submits `answers`, not selected-mode internals.
- Response controller deduplicates by request id.
- 410 expiry reloads session and clears stale UI.
- `waiting_permission` exposes interrupt/stop action.
- Existing single-question `ask_user` option selection continues to work through
  the shared controller.

### Architecture Guards

Update architecture guard tests to reject:

- GUI route decorators for dedicated approve/reject/reply endpoints.
- GUI webapp calls to old permission/user-input response APIs.
- Frontend permission response payloads that include category as authority.
- Product payload builders that emit `response_kind`, `remember`, or
  `selected_mode` as response contract fields.
- Reintroduction of `ManagedSession.pending_permission`,
  `ManagedSession.pending_user_input`, `pending_result`,
  `pending_user_event`, or `pending_user_response`.
- Root-level GUI pending permission/user-input state outside focused
  session-runtime modules.
- TUI service APIs named `approve`, `reject`, or `reply_user_input`.

## Verification Gate

For implementation completion:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

From `src/embedagent/frontend/gui/webapp`:

```bash
npm test
npm run build
```

If webapp source changes, generated static assets under
`src/embedagent/frontend/gui/static/` must be committed.

## Non-Goals

- No backward compatibility for old internal pending-interaction state shapes.
- No new remote service, Docker, WSL, VS Code, or online dependency.
- No new Python dependency or Python 3.9+ syntax.
- No visual redesign beyond adopting T3's pending interaction organization and
  response semantics.
- No durable frontend-owned timeline or interaction history.
- No T3 projection database or multi-pending runtime model in this slice.
- No full multi-question Core `ask_user` behavior in this slice.
- No change to `PermissionPolicy` rule matching except routing session memory
  through the unified response path.

## Implementation Notes

- Migrate tests before deleting public methods so failures point at the old
  contract directly.
- Keep private helper names visibly private if retained.
- Keep GUI modules focused and T3-style; avoid adding new interaction reducer
  fields back into root `App.jsx`.
- Expired or conflicting interaction responses should become a clear notice plus
  refreshed snapshot, not a stuck disabled card.
- Do not copy T3's persistence model or Pi's TypeScript runtime abstractions.
  Copy the lifecycle boundaries that match EmbedAgent's architecture.
