# Interaction Response Async Implementation Plan

> **Closeout:** Implemented and archived on 2026-07-20 in commit `6ce5e033`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GUI interaction responses acknowledge quickly while preserving Host-owned lifecycle state, backend event truth, and dynamic frontend capability adaptation.

**Architecture:** Keep `HostedInteractionService` as the single response coordinator. Command-owned waits remain in `HostedCommandService`; Core recovery continues through `AgentSession` and the existing `_run_turn(..., resume_pending=True)` path. HTTP returns a generic acknowledgement without a snapshot; backend session events and bootstrap snapshots remain the only asynchronous state source.

**Tech Stack:** Python 3.8, dataclass-based Hosted runtime, FastAPI route adapters, React webapp, existing WebSocket `session_event` transport, pytest, Node helper tests.

---

## File Map

- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_runtime.py` for internal one-time resolution-claim state.
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py` for atomic claim, non-blocking command/Core paths, coordinator cleanup, and cancellation.
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_command_service.py` only to clear the interaction claim at its existing terminal cleanup boundary.
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py` only to clear coordinator state on Core worker terminal/error paths and to emit safe lifecycle metadata through existing event helpers.
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py` to serialize `accepted` responses without inventing a snapshot.
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js` to keep resolving state after accepted acknowledgements and avoid fallback reloads.
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/responding-request-ids-handle.js` with a generic `clear` operation.
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-effect-executor.js` to clear resolving ids for generic `interaction_resolved` actions.
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx` only to pass the existing handle's `clear` function into the socket effect controller; do not add interaction policy there.
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js` and `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js` to preserve the generic `interaction_resolved` request id; do not add tool-name branches.
- Test: `tests/test_hosted_interaction_service.py` for pure claim/ack/cancel helpers.
- Test: `tests/test_inprocess_adapter_frontend_api.py` for Core/command integration and concurrency.
- Test: `tests/test_host_agent_facade.py` for hosted facade resume timing and lifecycle state.
- Test: `tests/test_gui_backend_api.py` for HTTP response envelopes and errors.
- Test: `src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs` and `src/embedagent/frontend/gui/webapp/test/run-tests.mjs` for dynamic accepted/resolved behavior.
- Test: `src/embedagent/frontend/gui/webapp/test/socket-effect-executor.test.mjs` for generic resolving-id cleanup.

## Task 1: Lock the Response Contract With Failing Tests

**Files:**
- Test: `tests/test_gui_backend_api.py`
- Test: `tests/test_hosted_interaction_service.py`
- Modify later: `src/embedagent/frontend/gui/backend/protocol_payloads.py`

- [ ] **Step 1: Add the accepted-envelope test.**

Add a backend serialization test with a payload equivalent to:

```python
def test_serialize_accepted_interaction_response_omits_snapshot():
    result = serialize_interaction_response(
        {
            "session_id": "sess-1",
            "interaction_id": "ask-1",
            "status": "accepted",
            "snapshot": None,
        },
        session_id="sess-1",
        interaction_id="ask-1",
    )
    assert result == {
        "session_id": "sess-1",
        "interaction_id": "ask-1",
        "status": "accepted",
        "snapshot": None,
    }
```

- [ ] **Step 2: Add the resolved-envelope compatibility test.**

Assert that a `resolved` payload still serializes its session snapshot exactly
as the current route contract does.

- [ ] **Step 3: Add pure claim tests.**

Cover first response acceptance, duplicate same-id rejection, mismatched-id
rejection, and expiry after terminal cleanup. Use a `ManagedSession` fixture;
do not instantiate a GUI or register tool names.

- [ ] **Step 4: Run the focused tests and confirm they fail for the new behavior.**

Run:

```powershell
uv run pytest tests/test_gui_backend_api.py tests/test_hosted_interaction_service.py -v
```

Expected: the new accepted/claim assertions fail before implementation, while
unrelated existing tests remain collected.

## Task 2: Add a Host-Local One-Time Resolution Claim

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/runtime/session_runtime.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py`
- Test: `tests/test_hosted_interaction_service.py`

- [ ] **Step 1: Add one internal claim field to `ManagedSession`.**

Add `pending_resolution_claim_id: str = ""`. This is Host-local coordination
state, not a protocol field, capability descriptor, or session-history source.

- [ ] **Step 2: Implement the atomic claim helper.**

Add a private helper in `HostedInteractionService` that, while holding
`state.lock`, performs these checks in order:

```python
if state.pending_interaction is None:
    raise ValueError("interaction_expired")
if state.pending_interaction.interaction_id != ticket.interaction_id:
    raise ValueError("interaction_conflict")
if state.pending_resolution_claim_id:
    raise ValueError("interaction_conflict")
state.pending_resolution_claim_id = ticket.interaction_id
```

Return the current `pending_event` and ticket kind to the caller. Do not expose
the claim id in the GUI payload.

- [ ] **Step 3: Add terminal claim cleanup.**

Clear `pending_resolution_claim_id` only from the existing terminal lifecycle
boundaries: `clear_pending_interaction`, successful Core worker completion, and
Core worker error cleanup. Do not clear it merely when an HTTP acknowledgement
is returned.

- [ ] **Step 4: Run claim tests.**

Run:

```powershell
uv run pytest tests/test_hosted_interaction_service.py -v
```

Expected: all claim tests pass and no new public adapter method exists.

## Task 3: Make Core and Command Responses Non-Blocking

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_command_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`
- Test: `tests/test_host_agent_facade.py`

- [ ] **Step 1: Add the generic accepted-result constructor.**

Return a mapping containing only `session_id`, `interaction_id`, and
`status: "accepted"` for asynchronous paths. Keep the existing resolved
snapshot mapping for genuinely synchronous terminal paths.

- [ ] **Step 2: Move lease waiting into a coordinator worker.**

Change `_start_resume_worker` so the HTTP caller schedules a daemon coordinator
that waits for the original active submit to release, then starts exactly one
`_run_turn(..., resume_pending=True)`. The coordinator must:

- re-check the claimed interaction id before starting;
- set `active_thread`/`active_thread_is_worker` under `state.lock`;
- clear those fields if `Thread.start()` fails;
- route runtime exceptions through the existing `session_error` event path.

The HTTP path must not call `_wait_for_active_submit_release`.

- [ ] **Step 3: Remove command wait polling from the response path.**

When `pending_event` exists, write the resolution, signal the event, and return
the accepted mapping. Leave command execution and terminal cleanup in
`HostedCommandService`; clear the claim where that service already clears
`pending_event` and `pending_response`.

- [ ] **Step 4: Preserve existing Core resume inputs.**

Keep permission resolution as `{"approved": bool(...)}` and user input
resolution as the existing generic answer/index/mode payload. Do not add
tool-specific branches or construct `QueryEngine`.

- [ ] **Step 5: Add delayed-execution timing tests.**

Use a fake model/recipe that waits at least 0.2 seconds after acceptance. Assert
that `respond_to_interaction` returns `status == "accepted"` under a small
acknowledgement threshold, while polling the session later reaches the expected
terminal state.

- [ ] **Step 6: Add concurrent-response tests.**

Submit two responses for the same interaction from separate threads. Assert one
is accepted and the other returns `interaction_conflict` or
`interaction_expired`; assert the session does not enter error and the model is
resumed once.

- [ ] **Step 7: Run focused Host tests.**

```powershell
uv run pytest tests/test_hosted_interaction_service.py tests/test_inprocess_adapter_frontend_api.py tests/test_host_agent_facade.py -v
```

Expected: accepted responses return promptly, terminal polling remains
necessary, and existing command/Core lifecycle assertions stay green.

## Task 4: Make Cancellation Lifecycle-Complete

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_command_service.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Add a normal Core permission-cancel test.**

Create a permission wait through a regular Core turn (no HostedCommandService
`pending_event`), submit `decision: "cancel"`, and assert the pending
interaction is cleared, the session reaches a terminal cancelled state, and the
next turn starts with a cleared stop signal.

- [ ] **Step 2: Add a normal Core user-input-cancel test.**

Use the same lifecycle path for `ask_user`; do not invent a user-input answer
payload for cancel.

- [ ] **Step 3: Route both cancel branches through the existing lifecycle.**

For command waits, set the abort signal and release the event. For Core waits,
schedule the existing pending-resume/interrupt path rather than returning a
snapshot with the pending ticket still present. Only clear hosted state after
the terminal lifecycle event.

- [ ] **Step 4: Run cancellation tests.**

```powershell
uv run pytest tests/test_inprocess_adapter_frontend_api.py -k "cancel or interaction" -v
```

Expected: no `pending_interaction` remains after cancellation and subsequent
turns are not aborted by a stale stop signal.

## Task 5: Update Backend Serialization and Route Assertions

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Test: `tests/test_gui_backend_api.py`
- Test: `tests/test_agent_app_protocol.py` only if the protocol envelope has a
  direct response assertion.

- [ ] **Step 1: Preserve optional snapshot semantics.**

Make `serialize_interaction_response` preserve `status: "accepted"` and
`snapshot: None` without falling back to `status: "resolved"` or serializing a
synthetic snapshot.

- [ ] **Step 2: Verify route ownership.**

Keep `routes_sessions.py` as the only interaction response route and
`CoreInterface.respond_to_interaction` as the only protocol facade. Do not add
GUI-specific route helpers or an alternate command endpoint.

- [ ] **Step 3: Run backend API tests.**

```powershell
uv run pytest tests/test_gui_backend_api.py tests/test_agent_app_protocol.py -v
```

Expected: accepted responses omit snapshots, resolved responses preserve them,
and all structured error mappings remain unchanged.

## Task 6: Update the Dynamic Webapp Response Bridge

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js` only to preserve the existing generic `interaction_resolved` request id.
- Test: `src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add an accepted response test.**

Resolve the mocked HTTP response with `{status: "accepted", snapshot: null}`.
Assert that no `loadSession` request is made, the interaction id remains in the
resolving set, and the controller emits only the existing response log event.

- [ ] **Step 2: Add a resolved response test.**

Assert that `{status: "resolved", snapshot: {...}}` dispatches the normalized
snapshot and clears the resolving id after the response lifecycle completes.

- [ ] **Step 3: Clear resolving ids from backend events.**

Add `clear(requestId)` to `responding-request-ids-handle.js`. Pass that handle
method through `App.jsx` into `socket-effect-executor.js`; when the executor
sees an action with `type: "interaction_resolved"`, call `clear` with its
generic `requestId` before dispatching the action. Preserve the existing
`socket-message-effects.js` and activity reducer request-id projection. Do not
add branches for `ask_user`, `write_file`, `run_recipe`, or other tool names.
An unknown interaction kind remains a generic event.

- [ ] **Step 4: Preserve recovery behavior.**

On reconnect/bootstrap, synchronize resolving ids against the backend pending
interaction/session state. Do not infer completion from the accepted ack.

- [ ] **Step 5: Run webapp tests.**

```powershell
npm test
```

Expected: accepted keeps the generic resolving state, resolved clears it, and
existing dynamic capability tests remain unchanged.

## Task 7: Add Safe Lifecycle Diagnostics

**Files:**
- Modify: `packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`
- Test: `tests/test_telemetry.py` only if diagnostics are routed through the
  existing safe envelope helper.

- [ ] **Step 1: Record only safe timing metadata.**

Use existing lifecycle/session event metadata for interaction id, turn id, step
id, pending-event presence, lease wait duration, schedule/start/finish times,
terminal reason, and safe error category.

- [ ] **Step 2: Add a redaction assertion.**

Assert that diagnostics do not contain request payload bodies, prompt text,
source paths beyond existing safe identifiers, raw tool output, credentials,
or permission secrets.

- [ ] **Step 3: Run diagnostics tests.**

```powershell
uv run pytest tests/test_telemetry.py tests/test_inprocess_adapter_frontend_api.py -k "interaction or diagnostic" -v
```

Expected: only credential-free metadata is emitted.

## Task 8: Full Verification and Documentation Closure

**Files:**
- Modify only if required by implementation: `docs/frontend-protocol.md`,
  `docs/overall-solution-architecture.md`, or
  `docs/development-tracker.md`.
- Generated assets: `src/embedagent/frontend/gui/static/` only if webapp source
  changes and `npm run build` changes them.

- [ ] **Step 1: Run focused architecture gates.**

```powershell
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
```

Expected: no new boundary failures. Existing ignored `__pycache__` directory
presence and Windows symlink privilege failures must be reported separately,
not masked by implementation changes.

- [ ] **Step 2: Run the fast suite.**

```powershell
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: interaction changes introduce no new failures; environment-only
failures remain explicitly classified.

- [ ] **Step 3: Run lint.**

```powershell
uv run --locked python scripts/lint.py
```

Expected: ruff and black checks pass.

- [ ] **Step 4: Run the GUI gate when webapp source changed.**

```powershell
npm test
npm run build
```

Expected: helper tests and build pass, with generated static assets matching
the source change.

- [ ] **Step 5: Review the final diff and architecture boundaries.**

Confirm that no static frontend registry, QueryEngine facade, Core-to-GUI
dependency, duplicate session-history path, or workflow-specific renderer
branch was introduced.

- [ ] **Step 6: Commit implementation slices separately.**

Use focused commits in this order: Host claim/coordinator, cancellation and
diagnostics, protocol/backend acknowledgement, webapp bridge, tests/docs.

## Handoff

After this plan is approved, implement it with
`superpowers:executing-plans` or `superpowers:subagent-driven-development`.
Do not begin implementation from this document until the user selects the
execution approach.

## Closeout Notes

The implementation followed the approved Host boundary and dynamic frontend
constraints. A small number of plan file-map entries were satisfied by the
existing protocol serializer/event projection rather than requiring new
protocol source files. The completed verification results and known
environment-only failures are recorded in `docs/development-tracker.md`.
