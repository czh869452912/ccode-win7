# GUI Event-Sourced Session Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the GUI active-session runtime around an event log + projector model so Timeline, Inspector, transport recovery, and restore semantics stay consistent under live updates, reconnects, and pending interactions.

**Architecture:** Keep Agent Core as product truth, but introduce a GUI-specific `session_event` protocol, a unified back-end `InteractionTicket`, and a front-end `SessionEventLogStore` + `SessionProjector`. Inspector becomes the only active interaction surface, Timeline becomes read-only history, and HTTP/WebSocket split into bootstrap/recovery versus incremental event transport.

**Tech Stack:** Python 3.8, FastAPI, unittest, React 18, esbuild, node:test, existing GUI build pipeline in `src/embedagent/frontend/gui/webapp`

---

## File Structure

### Back-End Runtime And Protocol

- Create: `src/embedagent/frontend/gui/backend/session_events.py`
  - Normalize internal callback payloads into GUI `session_event` envelopes.
  - Hold event-kind mapping, envelope builders, and event replay serialization helpers.

- Modify: `src/embedagent/inprocess_adapter.py`
  - Replace split `PermissionTicket` / `UserInputTicket` GUI exposure with one `InteractionTicket`.
  - Add `respond_to_interaction()` and stable restore semantics.
  - Attach persisted timeline metadata (`event_id`, `seq`, `created_at`) to emitted GUI callback payloads.

- Modify: `src/embedagent/session_timeline.py`
  - Add `load_events_after(session_id, after_seq, limit)` for replay-after-seq.
  - Surface append/truncate/fsync failures as structured diagnostics instead of silent `pass`.

- Modify: `src/embedagent/frontend/gui/backend/bridge.py`
  - Replace raw bool dispatch result with a small structured result that carries failure reasons.

- Modify: `src/embedagent/frontend/gui/backend/server.py`
  - Emit normalized `session_event` WebSocket messages.
  - Add `GET /api/sessions/{session_id}/events`.
  - Add `POST /api/sessions/{session_id}/interactions/{interaction_id}/respond`.
  - Map `ValueError` / interaction conflicts / malformed payloads to 404/409/410/422/503 responses.

- Create: `tests/test_gui_backend_api.py`
  - FastAPI `TestClient` coverage for the new events and interaction response endpoints.

- Modify: `tests/test_gui_runtime.py`
  - Cover GUI event envelope serialization and dispatcher degradation.

- Modify: `tests/test_inprocess_adapter_frontend_api.py`
  - Cover unified interaction snapshots, replay-after-seq, and response API behavior.

- Modify: `tests/test_session_restore.py`
  - Cover restore behavior for valid interaction IDs and explicit expiration when IDs cannot be trusted.

### Front-End Active Session Runtime

- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js`
  - Own append-only per-session event state, seq tracking, duplicate suppression, and `needsResync`.

- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  - Project bootstrap data + event log into `timelineView`, `currentInteraction`, `transportView`, and status read models.

- Create: `src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx`
  - Render the active interaction in Inspector for permission, ask-user, and mode-switch proposal variants.

- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
  - Replace per-message reducer patching with event-log append + projector recomputation.
  - Move interaction response submission to the new HTTP endpoint.
  - Add WebSocket parse guards, reconnect, and replay-after-seq recovery.

- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
  - Reduce state to shell-level UI state, session bootstrap caches, and projected read models.
  - Remove active-session truth fields such as `permission`, `userInput`, `activeTurnId`, `activeStepId`, and streaming IDs.

- Modify: `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
  - Keep bootstrap normalization and static helper utilities only.
  - Remove live projection responsibilities that move into `session-runtime/projector.js`.

- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  - Render read-only interaction history rows instead of actionable permission/user-input controls.

- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
  - Replace split pending permission and pending input panels with one `InteractionPanel`.

- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
  - Style the new Inspector interaction panel and the read-only timeline interaction summaries.

- Create: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
  - Cover projector determinism, current-interaction extraction, and seq-gap resync behavior.

- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  - Import and execute the new `session-runtime.test.mjs` module alongside existing helper checks.

### Generated Assets And Documentation

- Modify: `src/embedagent/frontend/gui/static/assets/app.js`
  - Regenerated bundle output from `npm run build`.

- Modify: `src/embedagent/frontend/gui/static/assets/app.css`
  - Regenerated style output from `npm run build`.

- Modify: `src/embedagent/frontend/gui/static/index.html`
  - Regenerated GUI static shell from `npm run build`.

- Modify: `docs/frontend-protocol.md`
  - Document `session_event`, event replay endpoint, and unified interaction response contract.

- Modify: `docs/development-tracker.md`
  - Record the new GUI active-session runtime slice and verification status.

- Modify: `docs/design-change-log.md`
  - Record the switch from mixed GUI state to event-sourced active-session runtime.

## Task 1: Unify Back-End Interaction State And Response API

**Files:**
- Create: `tests/test_gui_backend_api.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Write the failing tests for unified interactions**

```python
from fastapi.testclient import TestClient
import unittest

from embedagent.frontend.gui.backend.server import GUIBackend


class _FakeCore(object):
    def __init__(self):
        self.respond_calls = []

    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        return None

    def respond_to_interaction(self, session_id, interaction_id, payload):
        self.respond_calls.append((session_id, interaction_id, payload))
        return {
            "session_id": session_id,
            "interaction_id": interaction_id,
            "status": "resolved",
        }


class TestGuiBackendApi(unittest.TestCase):
    def test_post_interaction_response_uses_unified_endpoint(self):
        backend = GUIBackend(_FakeCore(), static_dir=".")
        client = TestClient(backend.app)
        response = client.post(
            "/api/sessions/sess-1/interactions/int-1/respond",
            json={
                "response_kind": "approve",
                "decision": True,
                "client_request_id": "cli-1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["interaction_id"], "int-1")


class TestInProcessAdapterFrontendApis(unittest.TestCase):
    def test_snapshot_exposes_pending_interaction(self):
        refreshed = self.adapter.get_session_snapshot(str(self.snapshot.get("session_id") or ""))
        self.assertIn("pending_interaction", refreshed)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_backend_api tests.test_inprocess_adapter_frontend_api -v
```

Expected:

- `AttributeError` for the missing interaction response route or core method
- snapshot assertions fail because `pending_interaction` is not exposed yet

- [ ] **Step 3: Implement `InteractionTicket` and the response route**

```python
@dataclass
class InteractionTicket:
    interaction_id: str
    session_id: str
    kind: str
    tool_name: str
    question: str
    options: List[Dict[str, Any]]
    category: str
    reason: str
    details: Dict[str, Any]
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "session_id": self.session_id,
            "kind": self.kind,
            "tool_name": self.tool_name,
            "question": self.question,
            "options": self.options,
            "category": self.category,
            "reason": self.reason,
            "details": self.details,
            "status": self.status,
        }


def respond_to_interaction(self, session_id: str, interaction_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    state = self._require_session(session_id)
    with state.lock:
        ticket = state.pending_interaction
        if ticket is None:
            raise ValueError("interaction_gone")
        if ticket.interaction_id != interaction_id:
            raise ValueError("interaction_conflict")
    return self._resolve_interaction(state, ticket, payload)


def _resolve_interaction(self, state: ManagedSession, ticket: InteractionTicket, payload: Dict[str, Any]) -> Dict[str, Any]:
    remember = bool(payload.get("remember"))
    if ticket.kind == "permission":
        approved = bool(payload.get("decision"))
        self._finalize_permission_ticket(state, ticket, approved, remember)
        return {"session_id": state.session.session_id, "interaction_id": ticket.interaction_id, "status": "resolved"}
    answer = str(payload.get("answer") or "").strip()
    self._finalize_user_input_ticket(state, ticket, answer, payload)
    return {"session_id": state.session.session_id, "interaction_id": ticket.interaction_id, "status": "resolved"}


def _finalize_permission_ticket(self, state: ManagedSession, ticket: InteractionTicket, approved: bool, remember: bool) -> None:
    if remember and approved and ticket.category:
        state.remembered_permission_categories.add(ticket.category)
    if state.pending_event is not None:
        state.pending_result = approved
        state.pending_event.set()
    state.pending_interaction = None


def _finalize_user_input_ticket(self, state: ManagedSession, ticket: InteractionTicket, answer: str, payload: Dict[str, Any]) -> None:
    if state.pending_user_event is not None:
        state.pending_user_response = UserInputResponse(
            answer=answer,
            selected_index=payload.get("selected_index"),
            selected_mode=str(payload.get("selected_mode") or ""),
            selected_option_text=str(payload.get("selected_option_text") or ""),
        )
        state.pending_user_event.set()
    state.pending_interaction = None
```

```python
@app.post("/api/sessions/{session_id}/interactions/{interaction_id}/respond")
async def respond_to_interaction(session_id: str, interaction_id: str, request: Dict[str, Any]):
    try:
        return self.core.respond_to_interaction(session_id, interaction_id, request)
    except ValueError as exc:
        code = str(exc)
        if code == "interaction_conflict":
            raise HTTPException(status_code=409, detail=code)
        if code == "interaction_gone":
            raise HTTPException(status_code=410, detail=code)
        if code == "session_not_found":
            raise HTTPException(status_code=404, detail=code)
        raise HTTPException(status_code=422, detail=code)
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_backend_api tests.test_inprocess_adapter_frontend_api -v
```

Expected:

- both test modules report `OK`
- the backend route returns HTTP 200 for a valid interaction response payload

- [ ] **Step 5: Commit the unified interaction API**

```bash
git add tests/test_gui_backend_api.py src/embedagent/inprocess_adapter.py src/embedagent/frontend/gui/backend/server.py tests/test_inprocess_adapter_frontend_api.py
git commit -m "feat(gui): unify pending interaction API"
```

## Task 2: Emit Normalized `session_event` Envelopes And Replay-After-Seq

**Files:**
- Create: `src/embedagent/frontend/gui/backend/session_events.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/session_timeline.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `tests/test_gui_runtime.py`
- Modify: `tests/test_gui_backend_api.py`

- [ ] **Step 1: Write the failing tests for event envelopes and replay**

```python
class TestWebSocketFrontend(unittest.TestCase):
    def test_on_turn_event_wraps_payload_as_session_event(self):
        frontend = WebSocketFrontend()
        dispatched = []
        frontend._dispatch_message = lambda message: dispatched.append(message) or True
        frontend.on_turn_event(
            "tool_started",
            {
                "_timeline_event": {
                    "event_id": "evt-1",
                    "seq": 3,
                    "created_at": "2026-04-04T00:00:00Z",
                    "event": "tool_started",
                },
                "session_id": "sess-1",
                "tool_name": "read_file",
                "arguments": {"path": "README.md"},
            },
        )
        self.assertEqual(dispatched[0]["type"], "session_event")
        self.assertEqual(dispatched[0]["data"]["event_kind"], "tool.started")
        self.assertEqual(dispatched[0]["data"]["seq"], 3)


class TestGuiBackendApi(unittest.TestCase):
    def test_get_session_events_replays_only_entries_after_seq(self):
        backend = GUIBackend(_FakeCoreWithTimeline(), static_dir=".")
        client = TestClient(backend.app)
        response = client.get("/api/sessions/sess-1/events?after_seq=2")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["seq"] for item in payload["events"]], [3, 4])


class _FakeCoreWithTimeline(object):
    def register_frontend(self, frontend):
        self.frontend = frontend

    def shutdown(self):
        return None

    def load_session_events_after(self, session_id, after_seq, limit=200):
        return [
            {"event_id": "evt-3", "seq": 3, "created_at": "2026-04-04T00:00:03Z", "event_kind": "tool.started", "payload": {"tool_name": "read_file"}},
            {"event_id": "evt-4", "seq": 4, "created_at": "2026-04-04T00:00:04Z", "event_kind": "tool.finished", "payload": {"tool_name": "read_file", "success": True}},
        ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_runtime tests.test_gui_backend_api -v
```

Expected:

- envelope test fails because `on_turn_event()` still emits raw event names
- replay test fails because `/api/sessions/{id}/events` does not exist yet

- [ ] **Step 3: Implement event mapping and replay-after-seq**

```python
GUI_EVENT_KIND_MAP = {
    "turn_start": "turn.started",
    "step_start": "step.started",
    "reasoning_delta": "step.reasoning_delta",
    "tool_started": "tool.started",
    "tool_finished": "tool.finished",
    "permission_required": "interaction.created",
    "user_input_required": "interaction.created",
    "turn_end": "transition.recorded",
    "session_error": "session.error",
    "session_finished": "session.finished",
}


def build_session_event(session_id: str, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    meta = dict(payload.pop("_timeline_event", {}))
    return {
        "type": "session_event",
        "data": {
            "session_id": session_id,
            "event_id": meta.get("event_id", ""),
            "seq": int(meta.get("seq", 0) or 0),
            "created_at": meta.get("created_at", ""),
            "event_kind": GUI_EVENT_KIND_MAP.get(event_name, event_name.replace("_", ".")),
            "payload": payload,
        },
    }
```

```python
def load_events_after(self, session_id: str, after_seq: int, limit: int = 200) -> List[Dict[str, Any]]:
    events = self.load_events(session_id, limit=self.max_events)
    filtered = [item for item in events if int(item.get("seq") or 0) > after_seq]
    if limit > 0:
        filtered = filtered[:limit]
    return filtered
```

```python
record = self.timeline_store.append_event(session_id, event_name, payload)
delivery_payload = dict(payload)
delivery_payload["session_id"] = session_id
delivery_payload["_timeline_event"] = {
    "event_id": record.get("event_id", ""),
    "seq": record.get("seq", 0),
    "created_at": record.get("created_at", ""),
    "event": record.get("event", event_name),
}
handler(event_name, session_id, delivery_payload)
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_runtime tests.test_gui_backend_api -v
```

Expected:

- `WebSocketFrontend` dispatches `type=session_event`
- `/api/sessions/{id}/events` returns only events with `seq > after_seq`

- [ ] **Step 5: Commit the event protocol slice**

```bash
git add src/embedagent/frontend/gui/backend/session_events.py src/embedagent/inprocess_adapter.py src/embedagent/session_timeline.py src/embedagent/frontend/gui/backend/server.py tests/test_gui_runtime.py tests/test_gui_backend_api.py
git commit -m "feat(gui): add session event protocol and replay api"
```

## Task 3: Add The Front-End Event Log Store And Pure Projector

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js`
- Create: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Create: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write the failing front-end runtime tests**

```javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  appendSessionEvent,
  createSessionEventLog,
} from "../src/session-runtime/event-log.js";
import { projectSessionRuntime } from "../src/session-runtime/projector.js";

test("appendSessionEvent marks seq gaps for resync", () => {
  const initial = createSessionEventLog();
  const first = appendSessionEvent(initial, {
    session_id: "sess-1",
    event_id: "evt-1",
    seq: 1,
    event_kind: "turn.started",
    created_at: "2026-04-04T00:00:00Z",
    payload: { turn_id: "turn-1", user_text: "hello" },
  });
  const gap = appendSessionEvent(first, {
    session_id: "sess-1",
    event_id: "evt-3",
    seq: 3,
    event_kind: "step.started",
    created_at: "2026-04-04T00:00:01Z",
    payload: { turn_id: "turn-1", step_id: "step-1" },
  });
  assert.equal(gap.needsResync, true);
});

test("projectSessionRuntime exposes currentInteraction separately from timeline history", () => {
  const runtime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_permission",
      pending_interaction: {
        interaction_id: "int-1",
        kind: "permission",
        tool_name: "edit_file",
        reason: "need write access",
      },
    },
    eventLog: createSessionEventLog(),
  });
  assert.equal(runtime.currentInteraction.interaction_id, "int-1");
  assert.equal(runtime.timelineView.some((item) => item.kind === "permission"), false);
});
```

- [ ] **Step 2: Run the webapp tests to verify they fail**

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
```

Expected:

- failure with `Cannot find module '../src/session-runtime/event-log.js'`
- failure with `Cannot find module '../src/session-runtime/projector.js'`

- [ ] **Step 3: Implement the event log and projector**

```javascript
export function createSessionEventLog() {
  return {
    events: [],
    eventIds: new Set(),
    lastAppliedSeq: 0,
    needsResync: false,
    connectionState: "connecting",
  };
}

export function appendSessionEvent(log, event) {
  if (!event || !event.event_id) return log;
  if (log.eventIds.has(event.event_id)) return log;
  const seq = Number(event.seq || 0);
  if (log.lastAppliedSeq && seq !== log.lastAppliedSeq + 1) {
    return { ...log, needsResync: true };
  }
  const nextIds = new Set(log.eventIds);
  nextIds.add(event.event_id);
  return {
    ...log,
    events: log.events.concat(event),
    eventIds: nextIds,
    lastAppliedSeq: seq,
  };
}
```

```javascript
export function projectSessionRuntime({ snapshot, eventLog }) {
  const currentInteraction =
    snapshot?.pending_interaction && snapshot.pending_interaction.status !== "resolved"
      ? snapshot.pending_interaction
      : null;

  return {
    currentInteraction,
    transportView: {
      connectionState: eventLog.connectionState,
      needsResync: eventLog.needsResync,
      lastAppliedSeq: eventLog.lastAppliedSeq,
    },
    sessionStatusView: {
      sessionId: snapshot?.session_id || "",
      status: snapshot?.status || "idle",
      mode: snapshot?.current_mode || "code",
    },
    timelineView: [],
  };
}
```

- [ ] **Step 4: Run the webapp tests again to verify they pass**

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
```

Expected:

- `frontend helper checks passed`
- new `session-runtime` tests print `ok`

- [ ] **Step 5: Commit the front-end runtime foundations**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "feat(gui): add event log store and projector"
```

## Task 4: Migrate App, Timeline, And Inspector To The Projected Runtime

**Files:**
- Create: `src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`

- [ ] **Step 1: Write the failing projection tests for read-only Timeline and Inspector-only interaction**

```javascript
test("projectSessionRuntime records interaction history without exposing inline timeline controls", () => {
  const runtime = projectSessionRuntime({
    snapshot: {
      session_id: "sess-1",
      status: "waiting_user_input",
      pending_interaction: {
        interaction_id: "int-2",
        kind: "user_input",
        question: "继续吗？",
        options: [{ index: 1, text: "继续" }],
      },
    },
    eventLog: {
      ...createSessionEventLog(),
      events: [
        {
          session_id: "sess-1",
          event_id: "evt-10",
          seq: 10,
          event_kind: "interaction.created",
          created_at: "2026-04-04T00:01:00Z",
          payload: {
            interaction_id: "int-2",
            kind: "user_input",
            question: "继续吗？",
          },
        },
      ],
    },
  });
  assert.equal(runtime.currentInteraction.interaction_id, "int-2");
  assert.equal(runtime.timelineView[0].kind, "interaction_requested");
});
```

- [ ] **Step 2: Run the webapp tests to verify they fail**

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
```

Expected:

- projector test fails because `timelineView` is still empty
- App / Inspector / Timeline still depend on reducer-local `permission` and `userInput` state

- [ ] **Step 3: Wire the UI to the projected runtime**

```javascript
function InteractionPanel({ interaction, onRespond, onAnswerChange, answerValue }) {
  if (!interaction) return null;
  if (interaction.kind === "permission") {
    return (
      <div className="prompt-panel" role="dialog">
        <h3>{interaction.tool_name}</h3>
        <p>{interaction.reason}</p>
        <div className="permission-actions">
          <button className="ghost btn-deny" onClick={() => onRespond({ response_kind: "deny", decision: false })}>Deny</button>
          <button className="primary" onClick={() => onRespond({ response_kind: "approve", decision: true })}>Approve</button>
        </div>
      </div>
    );
  }
  return (
    <div className="prompt-panel" role="dialog">
      <p>{interaction.question}</p>
      <textarea value={answerValue} onChange={(event) => onAnswerChange(event.target.value)} />
      <button className="primary" onClick={() => onRespond({ response_kind: "answer", answer: answerValue })}>Submit</button>
    </div>
  );
}
```

```javascript
async function respondToInteraction(interaction, payload) {
  const body = {
    ...payload,
    client_request_id: makeEventId("cli"),
  };
  await fetchJson(
    `/api/sessions/${encodeURIComponent(interaction.session_id)}/interactions/${encodeURIComponent(interaction.interaction_id)}/respond`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}
```

```javascript
{timelineView.map((item) =>
  item.kind === "interaction_requested" ? (
    <div key={item.id} className="permission-card resolved">
      <span className="permission-action">{item.label}</span>
      <span className="permission-verdict">Pending in Inspector</span>
    </div>
  ) : (
    <TimelineItem key={item.id} item={item} toolCatalog={toolCatalog} lang={lang} />
  )
)}
```

- [ ] **Step 4: Run the tests again to verify the UI now follows the projector**

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
```

Expected:

- interaction projection tests pass
- no test depends on inline timeline approval widgets anymore

- [ ] **Step 5: Commit the UI migration**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/state-helpers.js src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs
git commit -m "feat(gui): project active session ui from event runtime"
```

## Task 5: Add Resync, Restore, And Degraded-State Handling

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/bridge.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/session_timeline.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Modify: `tests/test_gui_runtime.py`
- Modify: `tests/test_session_restore.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`

- [ ] **Step 1: Write the failing degradation and restore tests**

```python
class TestSessionRestore(unittest.TestCase):
    def test_restore_expires_gui_interaction_when_id_cannot_be_trusted(self):
        events_without_real_interaction_id = [
            {"type": "pending_interaction", "payload": {"interaction_id": "", "kind": "permission", "tool_name": "edit_file"}},
        ]
        result = self.restorer.restore(events_without_real_interaction_id)
        self.assertIsNone(result.session.pending_interaction)
        self.assertEqual(result.stop_reason, "interaction_expired")


class TestThreadsafeAsyncDispatcher(unittest.TestCase):
    def test_dispatch_reports_closed_loop_reason(self):
        dispatcher = ThreadsafeAsyncDispatcher()
        loop = asyncio.new_event_loop()
        loop.close()
        dispatcher.set_loop(loop)
        result = dispatcher.dispatch(lambda: self._noop())
        self.assertEqual(result.reason, "loop_closed")
```

```javascript
test("appendSessionEvent keeps the runtime in resync mode after malformed payloads", () => {
  const next = appendSessionEvent(createSessionEventLog(), {
    session_id: "sess-1",
    event_id: "evt-1",
    seq: 1,
    event_kind: "",
    created_at: "2026-04-04T00:00:00Z",
    payload: null,
  });
  assert.equal(next.needsResync, true);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_runtime tests.test_session_restore tests.test_inprocess_adapter_frontend_api -v
```

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
```

Expected:

- dispatcher test fails because `dispatch()` still returns `bool`
- restore test fails because fallback IDs still keep a synthetic pending interaction alive
- front-end event-log test fails because malformed events are not forcing resync

- [ ] **Step 3: Implement recovery and explicit expiration**

```python
@dataclass(frozen=True)
class DispatchResult(object):
    queued: bool
    reason: str = ""


def dispatch(self, coroutine_factory):
    with self._lock:
        loop = self._loop
    if loop is None:
        return DispatchResult(False, "loop_missing")
    if loop.is_closed():
        return DispatchResult(False, "loop_closed")
    loop.call_soon_threadsafe(lambda: asyncio.create_task(coroutine_factory()))
    return DispatchResult(True, "")
```

```python
if session.pending_interaction is not None:
    interaction_id = str(session.pending_interaction.interaction_id or "").strip()
    if not interaction_id:
        state.pending_interaction = None
        self._emit(
            event_handler,
            "interaction_expired",
            session.session_id,
            {"reason": "missing_interaction_id"},
        )
    else:
        state.pending_interaction = InteractionTicket(
            interaction_id=interaction_id,
            session_id=session.session_id,
            kind=session.pending_interaction.kind,
            tool_name=session.pending_interaction.tool_name,
            question=str(request_payload.get("question") or ""),
            options=list(request_payload.get("options") or []),
            category=str(permission_payload.get("category") or ""),
            reason=str(permission_payload.get("reason") or ""),
            details=dict(permission_payload.get("details") or {}),
        )
```

```javascript
if (!event.event_kind || typeof event.payload !== "object" || event.payload === null) {
  return { ...log, needsResync: true };
}

const [runtimeState, setRuntimeState] = useState(() =>
  projectSessionRuntime({ snapshot: null, eventLog: createSessionEventLog() }),
);

socket.onerror = () => {
  setRuntimeState((current) => ({
    ...current,
    transportView: { ...current.transportView, connectionState: "degraded", needsResync: true },
  }));
};

async function replayEventsAfter(sessionId, afterSeq) {
  return fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/events?after_seq=${afterSeq}`);
}
```

- [ ] **Step 4: Run the degradation and restore tests again**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_runtime tests.test_session_restore tests.test_inprocess_adapter_frontend_api -v
```

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
```

Expected:

- dispatcher tests pass with `DispatchResult`
- restore tests show explicit expiration instead of synthetic fallback IDs
- front-end tests pass with `needsResync === true` on malformed events

- [ ] **Step 5: Commit recovery and restore handling**

```bash
git add src/embedagent/frontend/gui/backend/bridge.py src/embedagent/frontend/gui/backend/server.py src/embedagent/inprocess_adapter.py src/embedagent/session_timeline.py src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js tests/test_gui_runtime.py tests/test_session_restore.py tests/test_inprocess_adapter_frontend_api.py src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs
git commit -m "fix(gui): add resync and explicit interaction expiry"
```

## Task 6: Update Docs, Rebuild Static Assets, And Run Final Verification

**Files:**
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `src/embedagent/frontend/gui/static/assets/app.js`
- Modify: `src/embedagent/frontend/gui/static/assets/app.css`
- Modify: `src/embedagent/frontend/gui/static/index.html`

- [ ] **Step 1: Update the protocol and project tracking docs**

```markdown
## Session Event Transport

- WebSocket emits `type=session_event`
- `event_id`, `seq`, `created_at`, `event_kind`, and `payload` are required
- `GET /api/sessions/{session_id}/events?after_seq=N` replays missed events
- `POST /api/sessions/{session_id}/interactions/{interaction_id}/respond` is the only GUI interaction response path
```

```markdown
- 2026-04-04: GUI active-session runtime switched from mixed reducer/snapshot state to event-log + projector semantics.
- Timeline interaction controls removed; Inspector is the single active interaction surface.
```

- [ ] **Step 2: Rebuild the tracked GUI static bundle**

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' run build
```

Expected:

- `src/embedagent/frontend/gui/static/assets/app.js` regenerated
- `src/embedagent/frontend/gui/static/assets/app.css` regenerated
- `src/embedagent/frontend/gui/static/index.html` regenerated

- [ ] **Step 3: Run the focused full verification pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gui_runtime tests.test_gui_backend_api tests.test_inprocess_adapter_frontend_api tests.test_session_restore tests.test_gui_sync -v
```

Run in `src/embedagent/frontend/gui/webapp`:

```powershell
& 'C:\Program Files\nodejs\npm.cmd' test
```

Expected:

- all listed Python test modules report `OK`
- webapp tests report `frontend helper checks passed` and pass all `node:test` suites

- [ ] **Step 4: Inspect the final diff before commit**

Run:

```powershell
git diff -- src/embedagent/frontend/gui/backend/session_events.py src/embedagent/inprocess_adapter.py src/embedagent/session_timeline.py src/embedagent/frontend/gui/backend/bridge.py src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/state-helpers.js src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs docs/frontend-protocol.md docs/development-tracker.md docs/design-change-log.md src/embedagent/frontend/gui/static/index.html src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css
```

Expected:

- diff shows one coherent GUI runtime slice
- no inline timeline approval/input controls remain
- docs reflect the new event-sourced runtime and replay endpoint

- [ ] **Step 5: Commit the completed GUI runtime slice**

```bash
git add docs/frontend-protocol.md docs/development-tracker.md docs/design-change-log.md src/embedagent/frontend/gui/backend/session_events.py src/embedagent/inprocess_adapter.py src/embedagent/session_timeline.py src/embedagent/frontend/gui/backend/bridge.py src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/gui/webapp/src/session-runtime/event-log.js src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/state-helpers.js src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx src/embedagent/frontend/gui/webapp/src/styles.css src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs src/embedagent/frontend/gui/static/index.html src/embedagent/frontend/gui/static/assets/app.js src/embedagent/frontend/gui/static/assets/app.css
git commit -m "feat(gui): event-source active session runtime"
```

## Coverage Check

- Spec §§6-9 (runtime model, event envelope, front-end architecture, interaction command model) are covered by Tasks 1-4.
- Spec §§10-12 (transport, back-end changes, restore/degraded semantics) are covered by Tasks 2 and 5.
- Spec §13 (migration plan) is implemented directly by Tasks 1-6 in the same order.
- Spec §14 (tests) is covered by the targeted Python and webapp test additions in every task.
- Spec §§15-18 (acceptance, non-goals, implementation entry files, decision) are enforced by Task 6 verification and the file scope listed above.
