# Interaction Lifecycle Convergence Design

## Purpose

This design defines the official pre-release correction for GUI permission and `ask_user` interaction failures.

The goal is to replace the current facade-only convergence with one real interaction lifecycle:

- Agent Core and hosted runtime own pending interaction truth.
- GUI renders T3-style pending approval and pending user-input read models.
- Permission and user-input responses share one response controller and one backend contract.
- The old public permission/user-input response paths are deleted or demoted to private implementation details.
- The implementation does not preserve old internal pending-interaction state shapes.

This work must preserve Windows 7 compatibility, offline operation, Python 3.8 syntax, and the current C/C++ workflow baseline.

## Problem Statement

Recent cleanup moved GUI `ask_user` and permission responses toward a unified endpoint:

`POST /api/sessions/{session_id}/interactions/{interaction_id}/respond`

The current implementation still has architectural drift:

- `HostedInteractionService.respond_to_interaction()` dispatches back into separate `approve_permission`, `reject_permission`, and `reply_user_input` branches.
- Pending state is stored as separate permission and user-input ticket fields.
- GUI permission response payloads include policy data such as permission category, instead of deriving that from the backend-owned pending permission ticket.
- GUI response busy state is a single app-level string, not a T3-style request-id response tracker.
- `waiting_permission` is not treated consistently as an interruptible running turn, so the Stop action can disappear while an approval is blocking the turn.
- Tests cover `ask_user` response behavior more strongly than permission approval, session memory, stale response, and interrupt behavior.

The observed `interaction_expired` symptom is a result of this drift: when the backend cannot match the submitted interaction id against the current split pending fields, it reports the interaction as expired. Treating that as a button bug would leave the underlying lifecycle split intact.

## Reference Alignment

### T3 Code

T3 separates pending interaction display from response side effects:

- Thread activities are reduced into `PendingApproval` and `PendingUserInput` read models.
- Response state is tracked by request id.
- Approval actions are explicit user intents: cancel turn, decline, always allow for session, approve once.
- Composer panels render read models and call handlers; they do not own provider/runtime state.

EmbedAgent should copy this organization in the GUI without importing T3's full product model. Our source of truth remains `snapshot.pending_interaction`, not a second frontend activity ledger.

### Pi

Pi keeps tool-call interception and user confirmation behind the session/runtime boundary:

- Extensions and tool hooks can request UI input.
- The UI channel is replaceable.
- Non-interactive contexts fail closed for risky actions.
- Session/runtime owns abort and tool execution lifecycle.

EmbedAgent should keep this philosophy: permission decisions, pending tickets, session memory, resume, and cancellation belong to the hosted interaction/Core boundary. GUI submits user intent only.

## Chosen Architecture

Adopt a single hosted interaction lifecycle:

`Core pending interaction -> protocol snapshot -> GUI read model -> response controller -> hosted interaction service -> AgentToolActionService resume/cancel path -> new snapshot/session events`

There will be one product response path for GUI and TUI:

`respond_to_interaction(session_id, interaction_id, payload)`

Permission and user-input interactions remain different kinds, but they are variants of one pending interaction model instead of separate public response subsystems.

## Backend Design

### Pending Interaction Model

Introduce one hosted pending ticket shape inside `HostedInteractionService`.

Required fields:

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

- `question`
- `options`
- `details`

The backend must derive permission category and request kind from the pending ticket. The frontend must not send category as policy truth.

### Response Payload

The official response payload is:

```json
{
  "action": "accept | acceptForSession | decline | cancel | answer",
  "answer": "optional string for user_input",
  "selected_index": "optional number",
  "selected_mode": "optional string",
  "selected_option_text": "optional string"
}
```

Compatibility keys such as `response_kind`, `decision`, `remember`, or frontend-supplied `category` must not remain product contract fields after this slice. Product callers must use `action`, and product routes must reject invalid or stale legacy response shapes.

### Permission Semantics

Permission response actions mean:

- `accept`: approve current request once.
- `acceptForSession`: approve current request and remember the backend-derived permission category for the current session.
- `decline`: reject the current request and let the turn receive a denied permission result.
- `cancel`: interrupt the current turn.

Session memory is updated only when the active pending ticket is a permission ticket and action is `acceptForSession`.

### User Input Semantics

User-input response actions mean:

- `answer`: resolve the active user-input request with the provided answer/selected option fields.
- `cancel`: interrupt the current turn.

This slice keeps the existing single-question `ask_user` behavior. Future T3-style multi-question prompts require a separate protocol change; this slice must not add a placeholder multi-question response field.

### Error Semantics

Backend errors must be structured and stable:

- Unknown or already-resolved interaction id: HTTP 410 `interaction_expired`.
- Interaction id belongs to another active pending interaction: HTTP 409 `interaction_conflict`.
- Invalid action for interaction kind: HTTP 422 `invalid_interaction_response`.
- Missing active session: existing session-not-found/no-active-workspace mapping.

Every successful response returns a serialized session snapshot. For 409 and 410 failures, the GUI response controller reloads the session snapshot and shows a bounded interaction notice without inventing frontend-owned history.

### Deletion/Demotion

The following public paths must be removed from GUI/Core product usage:

- `approve_permission(session_id, permission_id)`
- `reject_permission(session_id, permission_id)`
- `reply_user_input(session_id, request_id, answer, ...)`
- GUI or tests relying on frontend-supplied permission category for remember behavior

If a private helper remains inside `HostedInteractionService`, it must not appear in `CoreInterface`, GUI routes, GUI tests, or TUI service APIs as a first-class product path.

## Frontend Design

### Read Model

Add a focused session-runtime module for interaction projection from session snapshots.

It projects:

- `pendingApprovals: PendingApproval[]`
- `pendingUserInputs: PendingUserInput[]`
- `activePendingApproval`
- `activePendingUserInput`
- `activePendingKind`
- `isInteractionBlocking`
- `isTurnInterruptible`

Because EmbedAgent currently supports one active pending interaction, arrays will contain zero or one item. Arrays are still useful because they match T3's component contracts and avoid another rewrite if multiple pending requests are introduced later.

### Response State

Replace single global `interactionResponseInFlight` string behavior with request-id response tracking:

- `respondingRequestIds: string[]` in React-visible state
- duplicate response for the same id is ignored while in flight
- unrelated future ids are not blocked by stale state
- all response success, conflict, expiry, and failure paths clear the id

### Components

Split the current combined composer interaction panel into focused T3-style modules:

- `ComposerPendingApprovalPanel.jsx`
- `ComposerPendingApprovalActions.jsx`
- `ComposerPendingUserInputPanel.jsx`
- `ComposerInteractionNotice.jsx`

The components receive read models and callbacks only. They do not build permission policy payloads.

Approval actions should match T3's product semantics:

- Cancel turn
- Decline
- Always allow this session
- Approve once

User-input options keep the current single-click submit behavior, and the action flows through the shared response controller.

### Primary Composer Actions

Introduce one front-end session status helper:

- `isTurnRunning(status)`
- `isTurnWaitingForInteraction(status)`
- `isTurnInterruptible(status)`

`waiting_permission` and `waiting_user_input` are interruptible. The Stop/Cancel action must remain available while either pending interaction is active.

The composer input auto-size fix is a separate UI correctness issue and is outside this interaction-lifecycle spec. It should receive its own focused task and tests when scheduled.

## Protocol And Snapshot Design

Session snapshots remain the activation truth:

- `snapshot.pending_interaction`
- `snapshot.pending_interaction_valid`
- `snapshot.status`

No new durable GUI activity ledger is introduced. Raw WebSocket `permission_request` and `user_input_request` messages continue to trigger session reload only; they do not create frontend-owned interaction history.

Every successful response result returns a serialized snapshot. GUI applies that snapshot through the existing reducer path.

## Testing Strategy

### Python Tests

Add or update tests for:

- `HostedInteractionService.respond_to_interaction()` permission `accept`.
- Permission `acceptForSession` updates remembered categories from the backend ticket category.
- Permission `decline` resumes/finishes through the same pending lifecycle.
- Permission `cancel` interrupts the active turn and clears pending interaction.
- User-input `answer` still emits ask_user completion and clears pending interaction.
- Unknown id maps to `interaction_expired`.
- Mismatched active id maps to `interaction_conflict`.
- `CoreInterface`, `InProcessAdapter`, TUI services, and GUI routes expose only the unified response path for interaction resolution.

### Webapp Tests

Add or update tests for:

- Pending snapshot projects into approval read model.
- Pending snapshot projects into user-input read model.
- Approval actions call shared response controller with `accept`, `acceptForSession`, `decline`, and `cancel`.
- Response controller deduplicates by request id.
- 410 expiry reloads session and clears stale UI.
- `waiting_permission` exposes interrupt/stop action.
- Existing `ask_user` option selection continues to work through the shared controller.

### Architecture Guards

Update architecture guard tests to reject:

- GUI route decorators for dedicated approve/reject/reply endpoints.
- GUI webapp calls to old permission/user-input response APIs.
- Frontend permission response payloads that include category as authority.
- Reintroduction of root-level GUI pending permission/user input state outside focused session-runtime modules.

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

If webapp source changes, generated static assets under `src/embedagent/frontend/gui/static/` must be committed.

## Non-Goals

- No backward compatibility for old internal pending-interaction state.
- No new remote service, Docker, WSL, VS Code, or online dependency.
- No visual redesign beyond copying T3's pending interaction organization and interaction semantics.
- No durable frontend-owned timeline or interaction history.
- No multi-question Core `ask_user` behavior in this slice.
- No change to `PermissionPolicy` rule matching except routing session memory through the unified response path.

## Open Implementation Notes

- Prefer deleting old public APIs after migrating tests, not wrapping them indefinitely.
- Keep Python code compatible with 3.8 syntax.
- Keep GUI modules small and T3-style; avoid putting new interaction reducer fields back into root `App.jsx`.
- Make failure states explicit. An expired interaction should become a clear notice and a refreshed snapshot, not a stuck disabled card.
