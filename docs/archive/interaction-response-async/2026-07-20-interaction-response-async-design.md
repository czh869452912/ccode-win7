# Interaction Response Async Design

**Status:** Implemented and closed on 2026-07-20; commit `6ce5e033`.

## Goal

Make GUI `ask_user` and permission responses return quickly while preserving
backend-owned interaction state, transcript/session truth, and dynamically
declared frontend capabilities.

## Scope

This slice covers the unified interaction response route, hosted interaction
coordination, asynchronous Core and command recovery, cancellation, response
ordering, diagnostics, and regression tests.

It does not add new tools, workflow packages, frontend registries, public Core
APIs, remote services, or a second session-history source.

## Constraints

- `HostedInteractionService` remains the Host interaction boundary.
- `HostedCommandService` remains the owner of command-owned execution.
- `AgentSession`/Core remains the owner of Core pending-interaction lifecycle.
- GUI consumes protocol projections and backend session events; it does not
  own permission policy, workflow state, or interaction completion policy.
- No renderer-side registration keyed by tool name, workflow name, or future
  interaction type is introduced.
- Diagnostics remain credential-free and must not include prompts, source
  files, raw tool output, permission secrets, or API keys.
- Python 3.8 and Windows 7/offline constraints remain unchanged.

## Response Contract

`POST /api/sessions/{session_id}/interactions/{interaction_id}/respond` keeps
the existing unified route and response envelope.

Successful responses use a generic JSON `status`:

- `accepted`: the resolution was atomically accepted and asynchronous
  recovery is scheduled or signalled. The response contains `session_id` and
  `interaction_id`, but no session snapshot.
- `resolved`: the interaction and its recovery have completed synchronously;
  the response may contain the resulting snapshot.

HTTP 200 remains the transport status for both successful states. The GUI does
not branch on HTTP 202 or on tool/workflow names.

Structured `409`, `410`, and `422` error behavior remains unchanged for
conflict, expiry, and invalid payloads.

## Host State Machine

`HostedInteractionService` must claim an interaction exactly once while
holding `ManagedSession.lock`. A second response cannot start a second resume
worker; it receives the existing conflict/expired error contract.

For a Core interaction with no `pending_event`, the response handler records
the resolution and schedules one session-owned resume coordinator. The
coordinator waits for the original submit lease to release, then invokes the
existing `_run_turn(..., resume_pending=True)` path. The HTTP request returns
`accepted` without waiting for model/tool execution.

For a HostedCommandService interaction with `pending_event`, the response
handler records the resolution and signals the event. The existing command
worker continues its command-owned resume path. The response handler does not
call `wait_for_command_resolution()`.

Both paths use the same single-claim and single-active-worker invariant.
Worker start failures clear active-thread state and emit the standard
`session_error` event through the existing event boundary.

Cancellation is a lifecycle operation, not a UI-only cleanup:

1. Set the session abort signal.
2. Release a command-owned pending wait when present.
3. Resolve or interrupt the Core pending interaction through its existing
   resume/interrupt path.
4. Clear hosted pending state only after the lifecycle operation has reached a
   terminal result.
5. Leave the next turn with a cleared stop signal.

## GUI Behavior

`interaction-response-controller.js` consumes only the generic response
envelope:

- On `accepted`, it keeps the interaction resolving/busy marker until a
  backend `interaction.resolved`, terminal session event, or recovery result
  clears it.
- On `resolved`, it clears the marker and accepts the returned snapshot.
- On structured errors, it uses the existing reload/notice path.

The accepted response never applies a session snapshot. Backend session
events and session snapshots are the only asynchronous execution truth. The
frontend must not synthesize an interaction history item from the accepted
acknowledgement.

Interaction rendering continues to use backend pending-interaction payloads,
app-shell copy, session capabilities, and generic event descriptors. No static
tool, recipe, workflow, or interaction-type registration is added.

## Event Ordering and Recovery

The HTTP acknowledgement and WebSocket event streams are intentionally
separated: an acknowledgement confirms acceptance only, while backend events
describe progress and completion. This removes the stale HTTP snapshot race.

Disconnect/reconnect recovery continues through the existing session bootstrap
and replay path. A reconnect must not infer completion from the accepted ack.

## Safe Diagnostics

The host may record safe lifecycle metadata for one interaction:

- `interaction_id`, `turn_id`, and `step_id`
- response received, claim, schedule, start, and finish timestamps
- `pending_event_present`
- lease wait duration
- terminal reason and safe error category

No request bodies, prompt text, file contents, raw observations, credentials,
or permission secrets are recorded.

## Verification Plan

Focused Host tests cover:

- one-time interaction claim and concurrent duplicate responses;
- non-blocking Core resume;
- non-blocking command permission response;
- normal and command cancellation cleanup;
- worker start failure cleanup.

GUI backend tests cover `accepted` without snapshot, `resolved` with snapshot,
and structured 409/410/422 responses.

Webapp tests cover accepted busy-state retention, resolved cleanup, event-driven
completion, stale-response immunity, and bootstrap recovery.

An integration test uses delayed model/recipe execution and asserts that the
response endpoint returns under a small fixed acknowledgement threshold while
the eventual session state and lifecycle events are correct.

Required gates remain:

```text
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
uv run pytest tests/ -m "not slow and not gui" -v
uv run --locked python scripts/lint.py
```

If webapp source changes, also run `npm test` and `npm run build`, committing
the generated GUI static assets.

## Non-Goals

- No new frontend static registry or tool-name switch table.
- No movement of command execution into Core or the renderer.
- No replacement of transcript/session events with an acknowledgement log.
- No new public `HookBus`, Core facade, remote registry, or runtime dependency.

## Closeout

- Host claim/coordinator, command and Core asynchronous acknowledgement, cancel
  cleanup, safe lifecycle diagnostics, generic frontend resolved-event cleanup,
  regression tests, and generated GUI assets are implemented.
- The accepted response intentionally carries no session snapshot. Backend
  resolved events and subsequent snapshots remain authoritative.
- Verification passed for the focused Host/GUI suites, webapp tests and build,
  and Python lint. The full fast suite retained only previously classified
  environment/baseline failures: stale package `__pycache__` directories,
  Windows symbolic-link privilege errors, a machine-sensitive performance
  threshold, and the nested HYGN aggregate failure.
