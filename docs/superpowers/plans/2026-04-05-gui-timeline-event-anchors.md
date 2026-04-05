# GUI Timeline Event Anchors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GUI timeline events use one stable turn/step anchor contract across slash commands, live updates, structured bootstrap, replay, and pending interactions.

**Architecture:** Introduce a first-class event-anchor contract in the protocol layer, promote slash/workflow commands into formal user turns, preserve turn-level transitions/tool activity in structured timeline projection, and keep frontend live/replay/bootstrap paths semantically aligned.

**Tech Stack:** Python 3.8, unittest, existing in-process adapter/core bridge, FastAPI GUI backend, vanilla JS/React webapp tests.

---

### Task 1: Lock Protocol And Frontend Expectations With Tests

**Files:**
- Modify: `tests/test_architecture.py`
- Modify: `tests/test_gui_sync.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `src/embedagent/frontend/gui/webapp/test/state-helpers.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Add failing protocol/callback expectations**

```python
def test_command_result(self):
    result = CommandResult(
        command_name="help",
        success=True,
        message="ok",
        data={"items": 1},
        turn_id="turn-1",
        step_id="",
        step_index=0,
    )
    self.assertEqual(result.turn_id, "turn-1")
```

```python
def test_callback_bridge_context_compacted_preserves_metadata(self):
    bridge.emit("context_compacted", "session-1", {
        "recent_turns": 2,
        "summarized_turns": 5,
        "approx_tokens_after": 1024,
        "turn_id": "turn-1",
        "step_id": "step-2",
        "step_index": 2,
    })
```

- [ ] **Step 2: Add failing slash-turn and structured projection tests**

```python
def test_slash_help_emits_formal_turn_lifecycle(self):
    event_names = [event_name for event_name, _ in events]
    self.assertIn("turn_start", event_names)
    self.assertIn("turn_end", event_names)
    command_payload = [payload for event_name, payload in events if event_name == "command_result"][0]
    self.assertTrue(command_payload.get("turn_id"))
```

```javascript
test("timelineFromEvents keeps anchors for command/system/compact events", () => {
  const timeline = timelineFromEvents([
    { event_id: "evt-1", event: "command_result", payload: { command_name: "review", success: true, message: "ok", turn_id: "turn-1" } },
    { event_id: "evt-2", event: "session_error", payload: { error: "boom", turn_id: "turn-1", step_id: "step-1", step_index: 1 } },
    { event_id: "evt-3", event: "context_compacted", payload: { recent_turns: 2, summarized_turns: 5, turn_id: "turn-1" } },
  ]);
  assert.equal(timeline[0].turnId, "turn-1");
  assert.equal(timeline[1].stepId, "step-1");
  assert.equal(timeline[2].turnId, "turn-1");
});
```

- [ ] **Step 3: Run focused tests to verify they fail for the expected reasons**

Run:

```powershell
python -m unittest tests.test_architecture tests.test_gui_sync tests.test_inprocess_adapter_frontend_api -v
node src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

Expected:

- Python tests fail because protocol objects and emitted payloads do not carry anchor fields yet.
- Webapp tests fail because replay/bootstrap/reducer paths do not preserve anchors for command/system/compact events.

- [ ] **Step 4: Commit after the red phase**

```bash
git add tests/test_architecture.py tests/test_gui_sync.py tests/test_inprocess_adapter_frontend_api.py src/embedagent/frontend/gui/webapp/test/state-helpers.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "test: cover gui timeline event anchors"
```

### Task 2: Implement Backend Event Anchor Contract

**Files:**
- Modify: `src/embedagent/protocol/__init__.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`

- [ ] **Step 1: Extend protocol dataclasses**

```python
@dataclass
class PermissionRequest:
    permission_id: str
    tool_name: str
    category: str
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0
```

- [ ] **Step 2: Preserve anchors through callback bridge and snapshot conversion**

```python
CommandResult(
    command_name=str(payload.get("command_name") or ""),
    success=bool(payload.get("success", False)),
    message=str(payload.get("message") or ""),
    data=payload.get("data", {}),
    turn_id=str(payload.get("turn_id") or ""),
    step_id=str(payload.get("step_id") or ""),
    step_index=int(payload.get("step_index") or 0),
)
```

- [ ] **Step 3: Promote slash/workflow commands to formal turns**

```python
parsed = parse_slash_command(text)
command_turn_id = "t-" + uuid.uuid4().hex[:12] if parsed is not None else ""
if command_turn_id:
    self._emit(event_handler, "turn_start", session_id, {"turn_id": command_turn_id, "user_text": text})
dispatch = self._dispatch_input(...)
```

```python
self._run_turn_v2(..., turn_id=command_turn_id or None, emit_turn_start=not bool(command_turn_id))
```

- [ ] **Step 4: Carry anchors into command-side tool/interaction/error/compact events**

```python
payload = {
    "command_name": result.command_name,
    "success": result.success,
    "message": result.message,
    "data": result.data,
    "turn_id": turn_id,
    "step_id": step_id,
    "step_index": step_index,
}
```

- [ ] **Step 5: Run focused backend tests**

Run:

```powershell
python -m unittest tests.test_architecture tests.test_gui_sync tests.test_inprocess_adapter_frontend_api -v
```

Expected:

- Protocol and adapter anchor tests pass.
- Slash command lifecycle tests pass.

- [ ] **Step 6: Commit the backend contract changes**

```bash
git add src/embedagent/protocol/__init__.py src/embedagent/core/adapter.py src/embedagent/inprocess_adapter.py src/embedagent/frontend/gui/backend/server.py
git commit -m "fix: anchor gui events to turns and steps"
```

### Task 3: Unify Frontend Replay And Structured Projection

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/store.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/state-helpers.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js`

- [ ] **Step 1: Preserve anchors in live reducer dispatch**

```javascript
dispatch({
  type: "command_result",
  id: makeEventId("cmd"),
  commandName: data.command_name || "",
  success: Boolean(data.success),
  message: data.message || "",
  data: data.data || {},
  turnId: data.turn_id || "",
  stepId: data.step_id || "",
  stepIndex: data.step_index || 0,
});
```

- [ ] **Step 2: Preserve anchors in reducer state**

```javascript
case "context_compacted":
  return {
    ...state,
    timeline: state.timeline.concat({
      id: action.id || makeEventId("context"),
      kind: "compact",
      turnId: action.turnId || resolveTimelineAnchor({ activeTurnId: state.activeTurnId, timeline: state.timeline }),
      stepId: action.stepId || "",
      stepIndex: action.stepIndex || 0,
      ...rawProjectionMeta(),
    }),
  };
```

- [ ] **Step 3: Project turn-level transitions and tool calls from structured turns**

```javascript
for (const tc of turn.tool_calls || []) {
  items.push({
    id: tc.call_id || makeEventId("tool"),
    kind: "tool",
    turnId,
    stepId: "",
    stepIndex: 0,
  });
}

for (const transition of turn.transitions || []) {
  items.push(projectTurnTransition(turnId, transition, projectionSource));
}
```

- [ ] **Step 4: Keep interaction-created local replay payloads structurally aligned**

```javascript
payload: {
  interaction_id: data.permission_id || "",
  kind: "permission",
  tool_name: data.tool_name || "",
  category: data.category || "",
  reason: data.reason || "",
  turn_id: data.turn_id || "",
  step_id: data.step_id || "",
  step_index: data.step_index || 0,
}
```

- [ ] **Step 5: Run webapp tests**

Run:

```powershell
node src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

Expected:

- replay/bootstrap/reducer tests pass with anchored command/system/compact events
- interaction projection remains deduped and grouped correctly

- [ ] **Step 6: Commit frontend projection changes**

```bash
git add src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/store.js src/embedagent/frontend/gui/webapp/src/state-helpers.js src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js
git commit -m "fix: unify gui timeline replay anchors"
```

### Task 4: Reduce Spurious Compaction Notifications And Final Verification

**Files:**
- Modify: `src/embedagent/context.py`
- Modify: `docs/design-change-log.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/issues/GUI_timeline_turnid_binding_analysis.md`

- [ ] **Step 1: Tighten compaction detection**

```python
compacted = bool(reduced_tool_messages) or (used_chars < chars_before)
```

- [ ] **Step 2: Add/adjust regression test for compaction signal**

```python
result = manager.build_messages(session, mode_name="code")
assert not result.compacted
```

- [ ] **Step 3: Run the full focused verification set**

Run:

```powershell
python -m unittest tests.test_architecture tests.test_gui_sync tests.test_inprocess_adapter_frontend_api tests.test_gui_runtime tests.test_gui_backend_api -v
node src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

Expected:

- all targeted Python tests pass
- webapp local tests pass

- [ ] **Step 4: Update docs to record the new event-anchor model**

```markdown
- GUI timeline now uses a unified `turn_id` / `step_id` anchor contract across callback, replay, and bootstrap paths.
- slash/workflow commands now emit formal turn lifecycle events.
```

- [ ] **Step 5: Commit verification and docs**

```bash
git add src/embedagent/context.py docs/design-change-log.md docs/development-tracker.md docs/issues/GUI_timeline_turnid_binding_analysis.md
git commit -m "docs: record gui timeline anchor unification"
```
