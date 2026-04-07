# Session History Single-Source Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the product over to one session-history architecture where transcript-backed session state is the only source for GUI history and replay logs are transport-only.

**Architecture:** Add a dedicated `SessionHistoryAssembler` that serializes `Session` into a stable GUI history DTO, persist a narrow immutable `ToolPresentationSnapshot` with durable tool-call history, and route session reads through one `_ensure_session_active()` materialization hook. Replace split GUI activation with one bootstrap API and make frontend bootstrap-to-live updates idempotent by `turn_id` / `step_id` / `call_id`.

**Tech Stack:** Python 3.8, existing `Session` / `QueryEngine` / `SessionRestorer` / `TranscriptStore`, FastAPI GUI backend, React GUI frontend, targeted `pytest` plus existing webapp node test runner.

---

## File Structure

**New/updated ownership map**

- Create: `src/embedagent/session_history.py`
  Builds the canonical structured history DTO from a materialized `Session`, including integrity state and tool presentation fallbacks.
- Modify: `src/embedagent/session.py`
  Introduce a narrow `ToolPresentationSnapshot` model and store it on `ToolCallRecord`.
- Modify: `src/embedagent/query_engine.py`
  Persist `ToolPresentationSnapshot` into transcript `tool_call` events and live `Session` state.
- Modify: `src/embedagent/session_restore.py`
  Restore `ToolPresentationSnapshot` from transcript into `Session`.
- Modify: `src/embedagent/inprocess_adapter.py`
  Add `_ensure_session_active()`, build bootstrap/history payloads from `SessionHistoryAssembler`, remove replay-log parsing from history reads.
- Modify: `src/embedagent/core/adapter.py`
  Expose bootstrap/history API to GUI core.
- Modify: `src/embedagent/frontend/gui/backend/server.py`
  Add `GET /api/sessions/{id}/bootstrap`, stop using `/timeline` as GUI bootstrap.
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
  Switch session activation to bootstrap-only.
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
  Make delayed live updates idempotent against bootstrap history.
- Modify: `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
  Delete raw-fallback bootstrap helpers and switch to structured-history-only bootstrap helpers.
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
  Remove raw-fallback notice/badge rendering and add partial-history/unavailable-history UI.
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
  Keep runtime overlay role narrow: merge bootstrap history with interaction/replay overlays only.
- Test: `tests/test_session_restore.py`
  Lock partial restore and integrity behavior.
- Test: `tests/test_inprocess_adapter_frontend_api.py`
  Lock active-session, resumed-session, trimmed-timeline, and bootstrap behavior.
- Test: `tests/test_gui_backend_api.py`
  Lock bootstrap endpoint shape.
- Test: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`
  Lock partial-history and runtime overlay behavior.
- Test: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  Keep the webapp helper suite green after activation-flow changes.
- Docs: `README.md`, `AGENTS.md`, `docs/overall-solution-architecture.md`, `docs/frontend-protocol.md`, `docs/tool-contracts.md`, `docs/agent-harness-v2.md`, `docs/development-tracker.md`, `docs/design-change-log.md`

---

### Task 1: Persist Stable Tool Presentation History

**Files:**
- Create: `src/embedagent/session_history.py`
- Modify: `src/embedagent/session.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/session_restore.py`
- Test: `tests/test_session_restore.py`
- Test: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Write the failing restore and query-engine tests**

```python
# tests/test_session_restore.py
def test_restore_preserves_tool_presentation_snapshot(self):
    session_id = "sess-tool-presentation"
    self.store.append_event(session_id, "session_meta", {"current_mode": "build"})
    self.store.append_event(
        session_id,
        "message",
        {"role": "user", "content": "读取文件", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
    )
    self.store.append_event(
        session_id,
        "step_started",
        {"turn_id": "t-1", "step_id": "s-1", "step_index": 1},
    )
    self.store.append_event(
        session_id,
        "tool_call",
        {
            "turn_id": "t-1",
            "step_id": "s-1",
            "call_id": "call-read-1",
            "tool_name": "read_file",
            "arguments": {"path": "src/demo.c"},
            "presentation": {
                "tool_label": "Read File",
                "permission_category": "read",
                "supports_diff_preview": False,
                "progress_renderer_key": "file",
                "result_renderer_key": "file",
            },
        },
    )
    result = SessionRestorer().restore(self.store.load_events(session_id))
    record = result.session.turns[0].steps[0].tool_calls[0]
    assert record.presentation.tool_label == "Read File"
    assert record.presentation.permission_category == "read"

# tests/test_query_engine_refactor.py
def test_query_engine_writes_tool_presentation_into_tool_call_event(self):
    session = Session()
    engine = QueryEngine(
        client=ToolClient(),
        tools=self.tools,
        transcript_store=self.transcript_store,
    )
    engine.submit_turn("读取文件", stream=False, session=session, initial_mode="build")
    events = self.transcript_store.load_events(session.session_id)
    tool_call_events = [item for item in events if item["type"] == "tool_call"]
    assert tool_call_events
    presentation = tool_call_events[0]["payload"]["presentation"]
    assert "tool_label" in presentation
    assert "progress_renderer_key" in presentation
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_session_restore.py -k tool_presentation -q
python -m pytest tests/test_query_engine_refactor.py -k tool_presentation -q
```

Expected:

- both tests fail because `ToolCallRecord` has no `presentation`
- `tool_call` transcript payload has no `presentation` field

- [ ] **Step 3: Add the stable presentation model to session state**

```python
# src/embedagent/session.py
@dataclass
class ToolPresentationSnapshot:
    tool_label: str = ""
    permission_category: str = ""
    supports_diff_preview: bool = False
    progress_renderer_key: str = "default"
    result_renderer_key: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_label": self.tool_label,
            "permission_category": self.permission_category,
            "supports_diff_preview": self.supports_diff_preview,
            "progress_renderer_key": self.progress_renderer_key,
            "result_renderer_key": self.result_renderer_key,
        }


@dataclass
class ToolCallRecord:
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: str = "pending"
    observation: Optional[Observation] = None
    started_at: str = field(default_factory=_utc_now)
    finished_at: str = ""
    progress: List[Dict[str, Any]] = field(default_factory=list)
    presentation: ToolPresentationSnapshot = field(default_factory=ToolPresentationSnapshot)


def record_tool_call(
    self,
    action: Action,
    presentation: Optional[ToolPresentationSnapshot] = None,
) -> ToolCallRecord:
    step = self.current_step() or self.begin_step()
    record = ToolCallRecord(
        call_id=action.call_id,
        tool_name=action.name,
        arguments=dict(action.arguments),
        status="started",
        presentation=presentation or ToolPresentationSnapshot(),
    )
    step.tool_calls.append(record)
    step.actions.append(action)
    return record
```

- [ ] **Step 4: Persist and restore that presentation snapshot**

```python
# src/embedagent/query_engine.py
def _tool_presentation_snapshot(self, tool_name: str) -> ToolPresentationSnapshot:
    entry = self.tools.tool_catalog_entry(tool_name) or {}
    return ToolPresentationSnapshot(
        tool_label=str(entry.get("user_label") or tool_name),
        permission_category=str(entry.get("permission_category") or ""),
        supports_diff_preview=bool(entry.get("supports_diff_preview")),
        progress_renderer_key=str(entry.get("progress_renderer_key") or "default"),
        result_renderer_key=str(entry.get("result_renderer_key") or "default"),
    )


# inside the reply.actions loop where "tool_call" transcript events are appended
presentation = self._tool_presentation_snapshot(action.name)
self._append_transcript_event(
    session,
    "tool_call",
    {
        "turn_id": session.turns[-1].turn_id if session.turns else "",
        "step_id": step_id,
        "call_id": action.call_id,
        "tool_name": action.name,
        "arguments": dict(action.arguments),
        "status": "pending",
        "presentation": presentation.to_dict(),
    },
)
record = session._find_tool_call(action.call_id)
if record is not None:
    record.presentation = presentation

# src/embedagent/session_restore.py
presentation_payload = dict(payload.get("presentation") or {})
presentation = ToolPresentationSnapshot(
    tool_label=str(presentation_payload.get("tool_label") or ""),
    permission_category=str(presentation_payload.get("permission_category") or ""),
    supports_diff_preview=bool(presentation_payload.get("supports_diff_preview")),
    progress_renderer_key=str(presentation_payload.get("progress_renderer_key") or "default"),
    result_renderer_key=str(presentation_payload.get("result_renderer_key") or "default"),
)
if session._find_tool_call(action.call_id) is None:
    session.record_tool_call(action, presentation=presentation)
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_session_restore.py -k tool_presentation -q
python -m pytest tests/test_query_engine_refactor.py -k tool_presentation -q
```

Expected:

- both tests pass
- transcript `tool_call` events include `presentation`
- restored `ToolCallRecord` retains `presentation`

- [ ] **Step 6: Commit**

```powershell
git add src/embedagent/session.py src/embedagent/query_engine.py src/embedagent/session_restore.py tests/test_session_restore.py tests/test_query_engine_refactor.py
git commit -m "refactor: persist stable tool presentation history"
```

### Task 2: Add Session History Assembler and Integrity Contract

**Files:**
- Create: `src/embedagent/session_history.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Write the failing history assembler tests**

```python
# tests/test_inprocess_adapter_frontend_api.py
def test_build_session_history_uses_active_session_state_instead_of_timeline_tail(self):
    adapter = InProcessAdapter(
        client=ToolClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    snapshot = adapter.create_session("build")
    session_id = str(snapshot.get("session_id") or "")
    adapter.submit_user_message(
        session_id=session_id,
        text="读取文件",
        stream=False,
        wait=True,
        permission_resolver=lambda ticket: True,
        event_handler=lambda event_name, current_session_id, payload: None,
    )
    adapter.timeline_store.max_events = 3
    adapter.timeline_store._trim_if_needed(adapter.timeline_store._timeline_path(session_id))
    history = adapter.build_session_history(session_id)
    assert history["integrity"]["status"] == "healthy"
    assert len(history["turns"]) == 1
    assert history["turns"][0]["user_text"] == "读取文件"


def test_build_session_history_marks_partial_restore_without_raw_fallback(self):
    adapter = InProcessAdapter(
        client=ToolClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    session_id = "sess-partial-history"
    adapter.transcript_store.append_event(session_id, "session_meta", {"current_mode": "spec"})
    adapter.transcript_store.append_event(
        session_id,
        "message",
        {"role": "user", "content": "继续", "message_id": "m-user", "turn_id": "t-1", "step_id": ""},
    )
    adapter.transcript_store.append_event(
        session_id,
        "pending_interaction",
        {
            "turn_id": "t-1",
            "step_id": "",
            "kind": "user_input",
            "tool_name": "ask_user",
            "interaction_id": "pi-1",
            "request_payload": {"request": {"question": "继续吗？", "options": []}},
        },
    )
    adapter.transcript_store.append_event(
        session_id,
        "pending_resolution",
        {
            "turn_id": "t-1",
            "step_id": "",
            "interaction_id": "wrong-id",
            "kind": "user_input",
            "tool_name": "ask_user",
            "resolution_payload": {"answer": "继续"},
        },
    )
    history = adapter.build_session_history(session_id)
    assert history["integrity"]["status"] == "partial"
    assert history["integrity"]["restore_stop_reason"] == "pending_resolution_identity_mismatch"
    assert history["turns"]
    assert history["history_source"] == "transcript_restore"
```

- [ ] **Step 2: Run the targeted adapter tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_inprocess_adapter_frontend_api.py -k "session_history or partial_restore" -q
```

Expected:

- failure because `build_session_history()` does not exist
- current adapter still reads replay logs for structured timeline

- [ ] **Step 3: Implement the history assembler and integrity DTO**

```python
# src/embedagent/session_history.py
from __future__ import annotations

from typing import Any, Dict, Optional

from embedagent.session import Session, ToolPresentationSnapshot


def _presentation_dict(presentation: Optional[ToolPresentationSnapshot], tool_name: str) -> Dict[str, Any]:
    current = presentation or ToolPresentationSnapshot()
    return {
        "tool_label": current.tool_label or tool_name,
        "permission_category": current.permission_category or "",
        "supports_diff_preview": bool(current.supports_diff_preview),
        "progress_renderer_key": current.progress_renderer_key or "default",
        "result_renderer_key": current.result_renderer_key or "default",
    }


class SessionHistoryAssembler(object):
    def build(
        self,
        session: Session,
        history_source: str,
        integrity_status: str,
        restore_stop_reason: str = "",
        consumed_event_count: int = 0,
        transcript_event_count: int = 0,
    ) -> Dict[str, Any]:
        turns = []
        for turn in session.turns:
            serialized_steps = []
            for step in turn.steps:
                serialized_steps.append(
                    {
                        "step_id": step.step_id,
                        "step_index": step.step_index,
                        "reasoning": step.reasoning,
                        "assistant_text": step.assistant_message,
                        "status": step.status,
                        "tool_calls": [
                            {
                                "call_id": record.call_id,
                                "tool_name": record.tool_name,
                                "arguments": dict(record.arguments),
                                "status": record.status,
                                "data": record.observation.data if record.observation is not None else None,
                                "error": record.observation.error if record.observation is not None else "",
                                **_presentation_dict(record.presentation, record.tool_name),
                            }
                            for record in step.tool_calls
                        ],
                        "transitions": [
                            {
                                "kind": transition.reason,
                                "display_reason": transition.reason,
                                "message": transition.message,
                                "metadata": dict(transition.metadata),
                            }
                            for transition in turn.transitions
                        ],
                    }
                )
            turns.append(
                {
                    "turn_id": turn.turn_id,
                    "user_text": turn.user_message,
                    "status": turn.transitions[-1].reason if turn.transitions else "completed",
                    "steps": serialized_steps,
                    "transitions": [
                        {
                            "kind": transition.reason,
                            "display_reason": transition.reason,
                            "message": transition.message,
                            "metadata": dict(transition.metadata),
                        }
                        for transition in turn.transitions
                    ],
                }
            )
        return {
            "session_id": session.session_id,
            "history_source": history_source,
            "turns": turns,
            "current_interaction": None,
            "integrity": {
                "status": integrity_status,
                "restore_stop_reason": restore_stop_reason,
                "consumed_event_count": consumed_event_count,
                "transcript_event_count": transcript_event_count,
            },
        }
```

- [ ] **Step 4: Route adapter history reads through materialized session state**

```python
# src/embedagent/inprocess_adapter.py
def _ensure_session_active(self, reference: str, mode: str = "") -> ManagedSession:
    with self._lock:
        existing = self._sessions.get(reference)
    if existing is not None:
        return existing
    snapshot = self.resume_session(reference, mode or DEFAULT_MODE)
    session_id = str(snapshot.get("session_id") or "")
    return self._require_session(session_id)


def build_session_history(self, reference: str, mode: str = "") -> Dict[str, Any]:
    state = self._ensure_session_active(reference, mode)
    assembler = SessionHistoryAssembler()
    restore_stop_reason = str(state.restore_stop_reason or "")
    restore_consumed = int(state.restore_consumed_event_count or 0)
    restore_total = int(state.restore_transcript_event_count or 0)
    integrity_status = "healthy"
    history_source = "session_state"
    if restore_total > 0:
        history_source = "transcript_restore"
        if restore_stop_reason:
            integrity_status = "partial"
    return assembler.build(
        state.session,
        history_source=history_source,
        integrity_status=integrity_status,
        restore_stop_reason=restore_stop_reason,
        consumed_event_count=restore_consumed,
        transcript_event_count=restore_total,
    )
```

- [ ] **Step 5: Run the targeted adapter tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_inprocess_adapter_frontend_api.py -k "session_history or partial_restore" -q
```

Expected:

- trimmed `timeline.jsonl` no longer affects structured history
- partial restore returns `integrity.status == "partial"`
- no test asserts `raw_events` fallback behavior anymore

- [ ] **Step 6: Commit**

```powershell
git add src/embedagent/session_history.py src/embedagent/inprocess_adapter.py tests/test_inprocess_adapter_frontend_api.py
git commit -m "refactor: build gui history from session state"
```

### Task 3: Add Bootstrap API and Replace Split Activation

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Test: `tests/test_gui_backend_api.py`

- [ ] **Step 1: Write the failing bootstrap API tests**

```python
# tests/test_gui_backend_api.py
def test_bootstrap_endpoint_returns_snapshot_history_plan_and_permissions(self):
    backend = GUIBackend(_FakeCoreWithTimeline(), static_dir=self.static_dir)
    client = TestClient(backend.app)
    response = client.get("/api/sessions/sess-1/bootstrap")
    assert response.status_code == 200
    payload = response.json()
    assert "snapshot" in payload
    assert "history" in payload
    assert "plan" in payload
    assert "permission_context" in payload
```

- [ ] **Step 2: Run the backend API test to verify it fails**

Run:

```powershell
python -m pytest tests/test_gui_backend_api.py -k bootstrap -q
```

Expected:

- failure because `/api/sessions/{id}/bootstrap` does not exist

- [ ] **Step 3: Add the bootstrap builder in adapter/core/backend**

```python
# src/embedagent/inprocess_adapter.py
def get_session_bootstrap(self, reference: str, mode: str = "") -> Dict[str, Any]:
    state = self._ensure_session_active(reference, mode)
    return {
        "snapshot": self.get_session_snapshot(state.session.session_id),
        "history": self.build_session_history(state.session.session_id),
        "plan": self.get_session_plan(state.session.session_id),
        "permission_context": self.get_permission_context(state.session.session_id).to_dict(),
        "replay": self.load_session_events_after(state.session.session_id, after_seq=0, limit=0),
    }

# src/embedagent/core/adapter.py
def get_session_bootstrap(self, session_id: str):
    return self._adapter.get_session_bootstrap(session_id)

# src/embedagent/frontend/gui/backend/server.py
@app.get("/api/sessions/{session_id}/bootstrap")
async def get_session_bootstrap(session_id: str):
    return self._call_core(self.core.get_session_bootstrap, session_id)
```

- [ ] **Step 4: Switch the webapp activation flow to bootstrap-only**

```javascript
// src/embedagent/frontend/gui/webapp/src/App.jsx
async function loadSession(sessionId) {
  const payload = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/bootstrap`);
  const snapshot = normalizeSessionPayload(payload.snapshot || {});
  dispatch({
    type: "session_activated",
    sessionId,
    snapshot,
    timeline: timelineFromTurns((payload.history || {}).turns || [], [], {
      projectionSource: (payload.history || {}).history_source || "",
    }),
  });
  replaceSessionEventLog(createRuntimeEventLog(snapshot));
  dispatch({ type: "plan_loaded", plan: payload.plan || null });
  dispatch({ type: "permission_context_loaded", context: payload.permission_context || null });
  await Promise.all([loadTasks(sessionId), loadArtifacts()]);
}
```

- [ ] **Step 5: Run the backend and webapp tests to verify they pass**

Run:

```powershell
python -m pytest tests/test_gui_backend_api.py -k bootstrap -q
node src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

Expected:

- bootstrap endpoint test passes
- webapp tests still pass after activation-flow simplification

- [ ] **Step 6: Commit**

```powershell
git add src/embedagent/inprocess_adapter.py src/embedagent/core/adapter.py src/embedagent/frontend/gui/backend/server.py src/embedagent/frontend/gui/webapp/src/App.jsx tests/test_gui_backend_api.py
git commit -m "refactor: bootstrap gui sessions from one structured payload"
```

### Task 4: Make Bootstrap-to-Live Updates Idempotent and Remove Raw Fallback UI

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`
- Test: `src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs`

- [ ] **Step 1: Write the failing frontend merge tests**

```javascript
// src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs
const duplicateToolRuntime = projectSessionRuntime({
  snapshot: {
    session_id: "sess-1",
    status: "running",
    current_mode: "build",
    pending_interaction: null,
  },
  eventLog: createSessionEventLog(),
  bootstrapTimeline: [
    {
      id: "call-1",
      kind: "tool",
      toolName: "read_file",
      label: "Read File",
      turnId: "turn-1",
      stepId: "step-1",
      stepIndex: 1,
      status: "running",
      projectionSource: "session_state",
    },
  ],
});
assert.equal(
  duplicateToolRuntime.timelineView[0].steps[0].activityItems.filter((item) => item.id === "call-1").length,
  1,
);
```

- [ ] **Step 2: Run the webapp test suite to verify the merge/raw-fallback assertions fail**

Run:

```powershell
node src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

Expected:

- failures around duplicate tool cards or obsolete raw-fallback expectations

- [ ] **Step 3: Add reducer upsert helpers for step and tool updates**

```javascript
// src/embedagent/frontend/gui/webapp/src/store.js
function upsertTimelineItem(timeline, nextItem, match) {
  const index = timeline.findIndex(match);
  if (index < 0) {
    return timeline.concat(nextItem);
  }
  return timeline.map((item, currentIndex) =>
    currentIndex === index ? { ...item, ...nextItem } : item,
  );
}

// inside "tool_started"
timeline: upsertTimelineItem(
  state.timeline,
  {
    id: action.callId,
    kind: "tool",
    toolName: action.toolName,
    label: action.label || action.toolName,
    arguments: action.arguments,
    status: "running",
    turnId: action.turnId || state.activeTurnId,
    stepId: action.stepId || state.activeStepId,
    stepIndex: action.stepIndex || state.activeStepIndex,
    data: null,
    error: "",
    permissionCategory: action.permissionCategory || "",
    supportsDiffPreview: Boolean(action.supportsDiffPreview),
    progressRendererKey: action.progressRendererKey || "",
    resultRendererKey: action.resultRendererKey || "",
    runtimeSource: action.runtimeSource || "",
    resolvedToolRoots: action.resolvedToolRoots || {},
    ...liveProjectionMeta(),
  },
  (item) => item.kind === "tool" && item.id === action.callId,
)
```

- [ ] **Step 4: Remove raw fallback UI paths and add integrity-aware history UI**

```javascript
// src/embedagent/frontend/gui/webapp/src/state-helpers.js
export function describeTimelineProjectionNotice(summary = {}) {
  const source = String(summary?.source || "").trim();
  if (!source || source === "session_state" || source === "transcript_restore") {
    return null;
  }
  return null;
}

// src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx
{historyIntegrity?.status === "partial" ? (
  <div className="system-card context" role="status">
    <strong>history partially restored</strong>: {historyIntegrity.restoreStopReason || "restore stopped early"}
  </div>
) : null}
{historyIntegrity?.status === "unavailable" ? (
  <div className="system-card error" role="alert">
    session history unavailable
  </div>
) : null}
```

- [ ] **Step 5: Run the webapp tests to verify they pass**

Run:

```powershell
node src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

Expected:

- no raw-fallback notice assertions remain
- delayed live events update existing items instead of duplicating them

- [ ] **Step 6: Commit**

```powershell
git add src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/state-helpers.js src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js src/embedagent/frontend/gui/webapp/test/session-runtime.test.mjs
git commit -m "refactor: make gui history bootstrap and live updates idempotent"
```

### Task 5: Delete Replay-Log History Paths and Update Docs

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Test: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Write the failing regression tests that assert the old parser path is gone**

```python
# tests/test_inprocess_adapter_frontend_api.py
def test_session_history_never_returns_raw_event_projection(self):
    adapter = InProcessAdapter(
        client=ToolClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    snapshot = adapter.create_session("build")
    session_id = str(snapshot.get("session_id") or "")
    adapter.submit_user_message(
        session_id=session_id,
        text="读取文件",
        stream=False,
        wait=True,
        permission_resolver=lambda ticket: True,
        event_handler=lambda event_name, current_session_id, payload: None,
    )
    history = adapter.build_session_history(session_id)
    assert history["history_source"] in ("session_state", "transcript_restore")
    assert history["integrity"]["status"] in ("healthy", "partial", "unavailable")
```

- [ ] **Step 2: Run the focused regression test to verify it fails before dead-path cleanup**

Run:

```powershell
python -m pytest tests/test_inprocess_adapter_frontend_api.py -k "never_returns_raw_event_projection" -q
```

Expected:

- failure if any code path still emits raw-event projection semantics

- [ ] **Step 3: Delete the old replay-log history parser and stale API route**

```python
# src/embedagent/inprocess_adapter.py
# delete build_structured_timeline() entirely
# keep load_session_events_after() as transport-only replay API

# src/embedagent/frontend/gui/backend/server.py
# delete:
# @app.get("/api/sessions/{session_id}/timeline")
# async def get_session_timeline(...)
#     ...
```

- [ ] **Step 4: Update current-architecture docs to state the single-source rule**

```markdown
Session history is reconstructed from transcript-backed session state only.
`timeline.jsonl` is transport/replay infrastructure and is not a historical database.
GUI session activation uses a single bootstrap payload rather than separate snapshot/timeline fetches.
```

- [ ] **Step 5: Run the full targeted regression suite**

Run:

```powershell
python -m pytest tests/test_session_restore.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py tests/test_gui_backend_api.py -q
node src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

Expected:

- all targeted Python tests pass
- all targeted webapp tests pass
- no test references raw fallback as supported behavior

- [ ] **Step 6: Commit**

```powershell
git add src/embedagent/inprocess_adapter.py src/embedagent/frontend/gui/backend/server.py README.md AGENTS.md docs/overall-solution-architecture.md docs/frontend-protocol.md docs/tool-contracts.md docs/agent-harness-v2.md docs/development-tracker.md docs/design-change-log.md tests/test_inprocess_adapter_frontend_api.py
git commit -m "refactor: remove replay-log history reconstruction"
```

## Self-Review

**Spec coverage**

- Single durable history source: covered by Tasks 1-2 and Task 5.
- Stable historical tool metadata: covered by Task 1.
- Auto-hydrate read path: covered by Task 2.
- Single bootstrap contract: covered by Task 3.
- Partial / unavailable integrity states: covered by Tasks 2 and 4.
- Idempotent bootstrap-to-live merge: covered by Task 4.
- Dead-path deletion: covered by Task 5.
- Documentation alignment: covered by Task 5.

**Placeholder scan**

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- All test and implementation steps include exact file paths and concrete code snippets.
- All verification steps include concrete commands.

**Type consistency**

- `ToolPresentationSnapshot` is introduced once and reused consistently in session, transcript, restore, and history serialization.
- Integrity vocabulary is consistent: `healthy`, `partial`, `unavailable`.
- Activation contract is consistent: `get_session_bootstrap()` in adapter/core/backend and bootstrap-only `loadSession()` in the webapp.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-07-session-history-single-source-cutover-implementation.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
```
```
```
