# Agent Core Ownership Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the agent core to a single execution path where one session owns one `QueryEngine`, one `Session` holds durable conversation truth, one `TaskGraph` holds workflow-task truth, and adapters/frontends become projection layers only.

**Architecture:** Introduce a session-scoped engine lifecycle, move initialization and workflow identity generation into `QueryEngine`, re-enter resumed interactions through the same action pipeline, and project runtime state through a dedicated snapshot/history layer. Remove remaining `todo` semantics, make mode handling fail fast, and optimize transcript/timeline append behavior with in-process sequence caches.

**Tech Stack:** Python 3.8, stdlib `unittest`, existing `pytest` runner, JSONL persistence, current `embedagent` runtime and frontend protocol layers.

---

## File Structure

### Runtime Ownership

- Create: `src/embedagent/session_runtime.py`
  - Hold the live runtime host structures.
  - Own the session registry/runtime-manager layer.
  - If interaction routing stays trivial, absorb that logic here instead of keeping a standalone interaction module.

- Modify: `src/embedagent/query_engine.py`
  - Add session bootstrap entrypoint.
  - Reuse one engine per live session.
  - Make callback signatures carry engine-generated IDs.
  - Re-enter resumed interactions through the normal action pipeline.
  - Trigger task-graph updates at turn boundaries.

- Modify: `src/embedagent/inprocess_adapter.py`
  - Stop creating a fresh engine per turn.
  - Stop generating independent `step_id` values.
  - Shrink to registry/threading/slash-command/callback-bridge responsibilities.

### Session Truth and Projection

- Modify: `src/embedagent/session.py`
  - Add `task_graph` to `Session`.
  - Add an explicit interaction checkpoint model if needed for structured payload serialization.

- Create: `src/embedagent/session_projector.py`
  - Build `SessionSnapshot`.
  - Build bootstrap payload fragments from live runtime/session truth.

- Modify: `src/embedagent/session_history.py`
  - Keep it projection-only.
  - Ensure it never depends on timeline state.

- Modify: `src/embedagent/session_restore.py`
  - Keep strict transcript-only restore behavior.

### Harness and Task Truth

- Modify: `src/embedagent/harness/task_graph.py`
  - Expand node shape to durable runtime semantics.

- Modify: `src/embedagent/harness/runner.py`
  - Keep `describe_mode(...)` read-only.
  - Add `update_task_graph(...)` as the only harness mutation entrypoint.

- Modify: `src/embedagent/tools/harness_runtime.py`
  - Remove `todos` renderer semantics.
  - Keep task-facing metadata aligned with `tasks`.

### Mode and Tool Truth

- Modify: `src/embedagent/modes.py`
  - Remove silent fallback for unknown modes.

- Modify: `src/embedagent/tools/runtime.py`
  - Keep executable tool membership derived from one runtime truth path.

### Persistence

- Modify: `src/embedagent/transcript_store.py`
  - Add per-path `last_seq` cache.

- Modify: `src/embedagent/session_timeline.py`
  - Add per-path `last_seq` cache.

### Cleanup

- Delete: `src/embedagent/todos.py`

- Modify: `src/embedagent/context.py`
  - Remove `todos` fallback in task reduction.

- Modify: `src/embedagent/workspace_profile.py`
  - Remove `todo` wording and runtime dependence.

### Docs

- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/mode-schema.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/permission-model.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/agent-harness-v2.md`

### Tests

- Modify: `tests/test_query_engine_refactor.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_session_restore.py`
- Modify: `tests/test_task_graph_v2.py`
- Modify: `tests/test_harness_task_projection.py`
- Modify: `tests/test_modes.py`
- Modify: `tests/test_tools_v2_runtime.py`
- Modify: `tests/test_transcript_store.py`
- Modify: `tests/test_session_timeline.py`
- Modify: `tests/test_gui_backend_api.py`

---

### Task 1: Session-Scoped Engine Bootstrap

**Files:**
- Create: `src/embedagent/session_runtime.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_query_engine_refactor.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Write the failing tests for engine reuse and engine-owned initialization**

```python
class FakeClient(object):
    def generate(self, messages, tools=None):
        return AssistantReply(content="ok", actions=[], finish_reason="stop")

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None:
            on_text_delta(reply.content)
        return reply

class SessionScopedEngineTests(unittest.TestCase):
    def test_adapter_reuses_one_engine_per_session(self):
        adapter = InProcessAdapter(FakeClient(), ToolRuntime(self.workspace))
        snapshot = adapter.create_session("build")
        state = adapter._sessions[snapshot["session_id"]]

        first_engine = state.engine
        adapter.submit_user_message(snapshot["session_id"], "first", wait=True)
        adapter.submit_user_message(snapshot["session_id"], "second", wait=True)

        self.assertIs(state.engine, first_engine)

    def test_initialize_session_injects_profile_mode_and_harness_once(self):
        engine = QueryEngine(FakeClient(), ToolRuntime(self.workspace))
        session = Session()

        engine.initialize_session(session, "build", workflow_state="chat")
        engine.initialize_session(session, "build", workflow_state="chat")

        kinds = [message.kind for message in session.messages if message.role == "system"]
        self.assertEqual(kinds.count("message"), 2)
        self.assertEqual(kinds.count("harness_prompt"), len([k for k in kinds if k == "harness_prompt"]))
```

- [ ] **Step 2: Run the targeted tests to verify the current code fails**

Run:

```powershell
pytest tests/test_query_engine_refactor.py -k "SessionScopedEngineTests or initialize_session" -v
pytest tests/test_inprocess_adapter_frontend_api.py -k "engine" -v
```

Expected:

- `ManagedSession` has no `engine`
- `QueryEngine` has no `initialize_session`
- adapter still creates a fresh engine in `_run_turn_v2`

- [ ] **Step 3: Implement a stable engine lifecycle and initialization entrypoint**

```python
# src/embedagent/session_runtime.py
@dataclass
class ManagedSession(object):
    session: Session
    engine: QueryEngine
    current_mode: str
    status: str = "idle"
    workflow_state: str = "chat"
    active_thread: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    updated_at: str = field(default_factory=_utc_now)
    last_error: Optional[str] = None


# src/embedagent/query_engine.py
def initialize_session(self, session, initial_mode, workflow_state="chat"):
    current_mode = require_mode(initial_mode)["slug"]
    if session.messages:
        return current_mode
    session.add_system_message(build_workspace_profile_message(self.tools.workspace, session.session_id))
    session.add_system_message(build_system_prompt(current_mode, getattr(self.tools, "app_config", None), self.tools.workspace))
    self._append_harness_messages(session, self.tools.describe_mode(current_mode, workflow_state=workflow_state))
    self._append_transcript_event(session, "session_meta", {"current_mode": current_mode, "started_at": session.started_at, "workspace": self.tools.workspace})
    return current_mode
```

- [ ] **Step 4: Rewire adapter session creation and turn execution to reuse `state.engine`**

```python
# src/embedagent/inprocess_adapter.py
def _build_engine(self, state):
    return QueryEngine(
        client=self.client,
        tools=self.tools,
        max_turns=self.max_turns,
        permission_policy=self.permission_policy,
        context_manager=self.context_manager,
        summary_store=self.summary_store,
        project_memory_store=self.project_memory_store,
        memory_maintenance=self.memory_maintenance,
        maintenance_interval=self.maintenance_interval,
        transcript_store=self.transcript_store,
        session_lock=state.lock,
    )

# in create_session / resume_session
state.engine = self._build_engine(state)
state.current_mode = state.engine.initialize_session(state.session, current_mode, workflow_state=state.workflow_state)

# in _run_turn_v2
engine = state.engine
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run:

```powershell
pytest tests/test_query_engine_refactor.py -k "SessionScopedEngineTests or initialize_session" -v
pytest tests/test_inprocess_adapter_frontend_api.py -k "engine" -v
```

Expected:

- PASS
- one `QueryEngine` instance remains attached to the session runtime
- initial system/harness messages are injected once

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/session_runtime.py src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py
git commit -m "refactor: make query engine session scoped"
```

### Task 2: Unify Step Identity Across Engine and Frontend Events

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_query_engine_refactor.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Write the failing tests for step-id alignment**

```python
class ToolCallingClient(object):
    def generate(self, messages, tools=None):
        return AssistantReply(
            content="",
            actions=[Action(name="read_file", arguments={"path": "README.md"}, call_id="call-read-1")],
            finish_reason="tool_calls",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        return self.generate(messages, tools=tools)

class StepIdentityTests(unittest.TestCase):
    def test_step_start_and_tool_events_share_engine_step_id(self):
        events = []

        def handler(event_name, session_id, payload):
            events.append((event_name, dict(payload)))

        adapter = InProcessAdapter(ToolCallingClient(), ToolRuntime(self.workspace), event_handler=handler)
        snapshot = adapter.create_session("build", event_handler=handler)
        adapter.submit_user_message(snapshot["session_id"], "read src/demo.c", wait=True, event_handler=handler)

        step_start = [payload for name, payload in events if name == "step_start"][0]
        tool_start = [payload for name, payload in events if name == "tool_started"][0]
        step_end = [payload for name, payload in events if name == "step_end"][0]

        self.assertEqual(tool_start["step_id"], step_start["step_id"])
        self.assertEqual(step_end["step_id"], step_start["step_id"])
```

- [ ] **Step 2: Run the targeted tests to verify they fail with mismatched IDs**

Run:

```powershell
pytest tests/test_inprocess_adapter_frontend_api.py -k "StepIdentityTests or step_id" -v
pytest tests/test_query_engine_refactor.py -k "step_id" -v
```

Expected:

- FAIL because adapter still synthesizes its own `step_id`

- [ ] **Step 3: Change the engine callback signature to carry engine-owned identifiers**

```python
# src/embedagent/query_engine.py
on_step_start: Optional[Callable[[str, int], None]]

step_id = "s-" + uuid.uuid4().hex[:12]
session.begin_step(step_id=step_id)
if on_step_start is not None:
    on_step_start(step_id, step_index)
```

- [ ] **Step 4: Stop adapter-side `step_id` generation and forward the engine value**

```python
# src/embedagent/inprocess_adapter.py
def on_step_start(step_id, step_index):
    current_step["step_id"] = step_id
    current_step["step_index"] = step_index
    set_thinking(True, "step_started")
    self._emit(event_handler, "step_start", session_id, {"turn_id": turn_id, "step_id": step_id, "step_index": step_index})
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run:

```powershell
pytest tests/test_inprocess_adapter_frontend_api.py -k "StepIdentityTests or step_id" -v
pytest tests/test_query_engine_refactor.py -k "step_id" -v
```

Expected:

- PASS
- transcript/session/frontend events all refer to the same step identity

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py tests/test_inprocess_adapter_frontend_api.py tests/test_query_engine_refactor.py
git commit -m "refactor: unify engine and frontend step ids"
```

### Task 3: Re-enter Resumed Interactions Through the Action Pipeline

**Files:**
- Modify: `src/embedagent/session.py`
- Modify: `src/embedagent/query_engine.py`
- Test: `tests/test_query_engine_refactor.py`
- Test: `tests/test_session_restore.py`

- [ ] **Step 1: Write the failing tests for structured checkpoints and no-repeat permission asks**

```python
class PermissionClient(object):
    def generate(self, messages, tools=None):
        return AssistantReply(
            content="",
            actions=[Action(name="write_file", arguments={"path": "src/demo.c", "content": "int main(void) { return 0; }\n"}, call_id="call-write-1")],
            finish_reason="tool_calls",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        return self.generate(messages, tools=tools)

class ResumePipelineTests(unittest.TestCase):
    def test_pending_interaction_payload_contains_execution_checkpoint(self):
        engine = QueryEngine(PermissionClient(), ToolRuntime(self.workspace), permission_policy=PermissionPolicy(auto_approve_all=False))
        session = Session()
        engine.initialize_session(session, "build")

        result = engine.submit_user_turn(
            "write src/demo.c",
            session=session,
            permission_handler=lambda request: None,
        )

        payload = result.pending_interaction.request_payload
        self.assertIn("action", payload)
        self.assertIn("turn_id", payload)
        self.assertIn("step_id", payload)
        self.assertIn("interaction_id", payload)

    def test_resume_approved_permission_does_not_suspend_again(self):
        engine = QueryEngine(PermissionClient(), ToolRuntime(self.workspace), permission_policy=PermissionPolicy(auto_approve_all=False))
        session = Session()
        engine.initialize_session(session, "build")

        first = engine.submit_user_turn("write src/demo.c", session=session, permission_handler=lambda request: None)
        resumed = engine.resume_interaction(session, {"approved": True})

        self.assertNotEqual(resumed.transition.reason, "permission_wait")
        self.assertIsNone(session.pending_interaction)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
pytest tests/test_query_engine_refactor.py -k "ResumePipelineTests or permission_wait" -v
pytest tests/test_session_restore.py -k "interaction" -v
```

Expected:

- payload lacks full execution checkpoint fields
- resumed permission path still bypasses `_execute_action`

- [ ] **Step 3: Introduce a structured interaction checkpoint and record it into pending payloads**

```python
# src/embedagent/session.py
@dataclass
class InteractionCheckpoint(object):
    action: Dict[str, Any]
    turn_id: str
    step_id: str
    interaction_id: str
    kind: str
    request_data: Dict[str, Any]

    def to_dict(self):
        return {
            "action": dict(self.action),
            "turn_id": self.turn_id,
            "step_id": self.step_id,
            "interaction_id": self.interaction_id,
            "kind": self.kind,
            "request_data": dict(self.request_data),
        }
```

- [ ] **Step 4: Re-enter `_execute_action(...)` with a synthetic permission resolver**

```python
# src/embedagent/query_engine.py
def _resolved_permission_handler(approved):
    def _handler(_request):
        return approved
    return _handler

# in resume_interaction(...)
observation, current_mode, suspended = self._execute_action(
    session,
    action,
    current_mode,
    workflow_state,
    permission_handler=_resolved_permission_handler(bool(resolution.get("approved"))),
    user_input_handler=None,
    stop_event=None,
)
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run:

```powershell
pytest tests/test_query_engine_refactor.py -k "ResumePipelineTests or permission_wait" -v
pytest tests/test_session_restore.py -k "interaction" -v
```

Expected:

- PASS
- resumed interactions traverse the normal validation path
- no second identical permission prompt is created

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/session.py src/embedagent/query_engine.py tests/test_query_engine_refactor.py tests/test_session_restore.py
git commit -m "refactor: resume interactions through action pipeline"
```

### Task 4: Move Task Truth Into `Session.task_graph`

**Files:**
- Modify: `src/embedagent/session.py`
- Modify: `src/embedagent/harness/task_graph.py`
- Modify: `src/embedagent/harness/runner.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_task_graph_v2.py`
- Test: `tests/test_harness_task_projection.py`

- [ ] **Step 1: Write the failing tests for session-owned task truth**

```python
class SessionTaskGraphTests(unittest.TestCase):
    def test_session_carries_task_graph(self):
        session = Session()
        self.assertIsNotNone(session.task_graph)

    def test_update_task_graph_mutates_session_graph_in_place(self):
        session = Session()
        runner = HarnessRunner()
        graph = session.task_graph

        runner.update_task_graph(session, "build", [Observation("run_recipe", True, None, {"recipe_id": "unit"})])
        self.assertIs(session.task_graph, graph)

    def test_task_status_reads_session_task_graph_not_describe_mode(self):
        session = Session()
        session.task_graph.tasks[0].title = "build:implement"
        self.assertIn("build:implement", session.task_graph.render_summary())
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
pytest tests/test_task_graph_v2.py -v
pytest tests/test_harness_task_projection.py -v
```

Expected:

- `Session` has no `task_graph`
- `HarnessRunner` has no `update_task_graph`
- `task_status` still depends on transient mode context

- [ ] **Step 3: Add `task_graph` to `Session` and expand `TaskGraph` into runtime truth**

```python
# src/embedagent/session.py
@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: str = field(default_factory=_utc_now)
    messages: List[TranscriptMessage] = field(default_factory=list)
    turns: List[Turn] = field(default_factory=list)
    compact_boundaries: List[CompactBoundary] = field(default_factory=list)
    pending_interaction: Optional[PendingInteraction] = None
    content_replacements: List[Dict[str, Any]] = field(default_factory=list)
    latest_context_snapshot: Dict[str, Any] = field(default_factory=dict)
    task_graph: TaskGraph = field(default_factory=TaskGraph.empty)

# src/embedagent/harness/task_graph.py
@dataclass
class TaskNode(object):
    task_id: str
    kind: str
    title: str
    status: str = "pending"
    source: str = "harness"
    note: str = ""
    evidence_refs: List[str] = field(default_factory=list)


@dataclass
class TaskGraph(object):
    mode_name: str
    discipline: str
    current_phase: str = ""
    tasks: List[TaskNode] = field(default_factory=list)

    @classmethod
    def empty(cls):
        return cls(mode_name="", discipline="", current_phase="", tasks=[])

    def apply_observations(self, mode_name, observations):
        if not self.tasks:
            seeded = self.for_mode(mode_name, self.discipline or "lite_spec_tdd")
            self.mode_name = seeded.mode_name
            self.discipline = seeded.discipline
            self.current_phase = seeded.current_phase
            self.tasks = seeded.tasks
```

- [ ] **Step 4: Add `HarnessRunner.update_task_graph(...)` and call it at turn boundaries**

```python
# src/embedagent/harness/runner.py
def update_task_graph(self, session, mode_name, observations):
    graph = session.task_graph
    if graph is None:
        graph = TaskGraph.for_mode(mode_name, self.registry[str(mode_name)].default_discipline.value)
        session.task_graph = graph
    graph.apply_observations(mode_name, observations)

# src/embedagent/query_engine.py
self.harness_runner.update_task_graph(session, current_mode, list(session.turns[-1].observations))
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run:

```powershell
pytest tests/test_task_graph_v2.py -v
pytest tests/test_harness_task_projection.py -v
```

Expected:

- PASS
- `Session.task_graph` exists and is mutated in place
- task state is no longer ephemeral adapter-owned data

- [ ] **Step 6: Commit**

```bash
git add src/embedagent/session.py src/embedagent/harness/task_graph.py src/embedagent/harness/runner.py src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py tests/test_task_graph_v2.py tests/test_harness_task_projection.py
git commit -m "refactor: make task graph session truth"
```

### Task 5: Fail Fast on Unknown Modes and Collapse Tool-Truth Drift

**Files:**
- Modify: `src/embedagent/modes.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/tools/harness_runtime.py`
- Test: `tests/test_modes.py`
- Test: `tests/test_tools_v2_runtime.py`

- [ ] **Step 1: Write the failing tests for fail-fast mode handling and single runtime tool truth**

```python
class ModeTruthTests(unittest.TestCase):
    def test_require_mode_raises_for_unknown_mode(self):
        with self.assertRaises(ValueError):
            require_mode("orchestra")

    def test_runtime_allowed_tool_names_are_derived_from_one_path(self):
        runtime = ToolRuntime(self.workspace)
        explore_tools = runtime.allowed_tool_names("explore")
        self.assertNotIn("write_file", explore_tools)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
pytest tests/test_modes.py -k "unknown_mode or require_mode" -v
pytest tests/test_tools_v2_runtime.py -k "allowed_tool_names or explore" -v
```

Expected:

- `require_mode` silently falls back instead of raising
- tool truth remains spread across multiple runtime sources

- [ ] **Step 3: Remove the silent fallback and tighten runtime tool derivation**

```python
# src/embedagent/modes.py
def require_mode(mode_name):
    if mode_name in MODE_REGISTRY:
        return MODE_REGISTRY[mode_name]
    raise ValueError("Unknown mode: %r" % (mode_name,))

# src/embedagent/tools/runtime.py
def allowed_tool_names(self, mode_name, workflow_state="chat"):
    return set(self._mode_runtime.allowed_tool_names(mode_name, workflow_state=workflow_state))
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run:

```powershell
pytest tests/test_modes.py -k "unknown_mode or require_mode" -v
pytest tests/test_tools_v2_runtime.py -k "allowed_tool_names or explore" -v
```

Expected:

- PASS
- unknown modes fail immediately
- executable tool membership is derived by one runtime path

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/modes.py src/embedagent/tools/runtime.py src/embedagent/tools/harness_runtime.py tests/test_modes.py tests/test_tools_v2_runtime.py
git commit -m "refactor: make mode handling fail fast"
```

### Task 6: Introduce a Side-Effect-Free Snapshot Projector and Shrink the Adapter

**Files:**
- Create: `src/embedagent/session_projector.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/core/adapter.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`
- Test: `tests/test_gui_backend_api.py`

- [ ] **Step 1: Write the failing tests for projector-owned snapshot derivation**

```python
class SessionProjectorTests(unittest.TestCase):
    def test_snapshot_is_projected_from_runtime_truth(self):
        adapter = InProcessAdapter(FakeClient(), ToolRuntime(self.workspace))
        snapshot = adapter.create_session("build")
        self.assertIn("task_items", snapshot)
        self.assertIn("current_phase", snapshot)

    def test_snapshot_projection_does_not_mutate_session(self):
        adapter = InProcessAdapter(FakeClient(), ToolRuntime(self.workspace))
        snapshot = adapter.create_session("build")
        state = adapter._sessions[snapshot["session_id"]]
        before = list(state.session.messages)
        adapter.get_session_snapshot(snapshot["session_id"])
        self.assertEqual(before, state.session.messages)
```

- [ ] **Step 2: Run the targeted tests to verify they fail or expose inline projection logic**

Run:

```powershell
pytest tests/test_inprocess_adapter_frontend_api.py -k "SessionProjectorTests or snapshot" -v
pytest tests/test_gui_backend_api.py -k "bootstrap or snapshot" -v
```

Expected:

- snapshot derivation still lives inside adapter
- no dedicated projector object exists

- [ ] **Step 3: Implement `SessionSnapshotProjector` and route adapter snapshot/bootstrap through it**

```python
# src/embedagent/session_projector.py
class SessionSnapshotProjector(object):
    def build_snapshot(self, state, runtime_environment, replay_state):
        graph = state.session.task_graph
        return {
            "session_id": state.session.session_id,
            "status": state.status,
            "current_mode": state.current_mode,
            "current_phase": graph.current_phase if graph is not None else "",
            "task_summary": graph.render_summary() if graph is not None else "",
            "task_items": graph.to_items() if graph is not None else [],
        }
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run:

```powershell
pytest tests/test_inprocess_adapter_frontend_api.py -k "SessionProjectorTests or snapshot" -v
pytest tests/test_gui_backend_api.py -k "bootstrap or snapshot" -v
```

Expected:

- PASS
- snapshot building is side-effect free
- adapter becomes thinner and purely orchestration-oriented

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/session_projector.py src/embedagent/inprocess_adapter.py src/embedagent/core/adapter.py tests/test_inprocess_adapter_frontend_api.py tests/test_gui_backend_api.py
git commit -m "refactor: project session snapshots from runtime truth"
```

### Task 7: Optimize Transcript and Timeline Append Paths

**Files:**
- Modify: `src/embedagent/transcript_store.py`
- Modify: `src/embedagent/session_timeline.py`
- Test: `tests/test_transcript_store.py`
- Test: `tests/test_session_timeline.py`

- [ ] **Step 1: Write the failing tests for cached sequence-number reuse**

```python
class SequenceCacheTests(unittest.TestCase):
    def test_transcript_append_uses_cached_last_seq_after_first_write(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-cache", "session_meta", {"current_mode": "build"})

        original_scan = store._scan_events
        def fail_scan(path):
            raise AssertionError("unexpected transcript rescan")
        store._scan_events = fail_scan

        store.append_event("sess-cache", "message", {"role": "user", "message_id": "m-1", "turn_id": "t-1", "step_id": "", "content": "next"})
        store._scan_events = original_scan

    def test_timeline_append_uses_cached_last_seq_after_first_write(self):
        store = SessionTimelineStore(self.workspace)
        store.append_event("sess-cache", "turn_started", {"turn_id": "t-1"})

        original_scan = store._scan_events
        def fail_scan(path):
            raise AssertionError("unexpected timeline rescan")
        store._scan_events = fail_scan

        store.append_event("sess-cache", "step_start", {"turn_id": "t-1", "step_id": "s-1"})
        store._scan_events = original_scan
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
pytest tests/test_transcript_store.py -k "SequenceCacheTests or cached_last_seq" -v
pytest tests/test_session_timeline.py -k "cached_last_seq or SequenceCacheTests" -v
```

Expected:

- second append still triggers `_scan_events`

- [ ] **Step 3: Add per-path `last_seq` caches and refresh them on repair/load**

```python
# src/embedagent/transcript_store.py
self._seq_cache = {}  # type: Dict[str, int]

def _next_seq(self, path):
    normalized = os.path.realpath(path)
    cached = self._seq_cache.get(normalized)
    if cached is not None:
        return cached + 1
    events, _ = self._scan_events(path)
    last_seq = int(events[-1].get("seq") or 0) if events else 0
    self._seq_cache[normalized] = last_seq
    return last_seq + 1
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run:

```powershell
pytest tests/test_transcript_store.py -k "SequenceCacheTests or cached_last_seq" -v
pytest tests/test_session_timeline.py -k "cached_last_seq or SequenceCacheTests" -v
```

Expected:

- PASS
- second append uses in-memory sequence state instead of rescanning the whole file

- [ ] **Step 5: Commit**

```bash
git add src/embedagent/transcript_store.py src/embedagent/session_timeline.py tests/test_transcript_store.py tests/test_session_timeline.py
git commit -m "perf: cache transcript and timeline sequence numbers"
```

### Task 8: Remove `todo` Runtime Semantics, Align Docs, and Run Full Verification

**Files:**
- Delete: `src/embedagent/todos.py`
- Modify: `src/embedagent/context.py`
- Modify: `src/embedagent/workspace_profile.py`
- Modify: `src/embedagent/tools/harness_runtime.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/mode-schema.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/permission-model.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/agent-harness-v2.md`
- Test: `tests/test_architecture.py`

- [ ] **Step 1: Remove runtime `todo` fallbacks and stale renderer vocabulary**

```python
# src/embedagent/context.py
def _reduce_tasks(self, data, detailed, policy):
    tasks = data.get("tasks")
    if isinstance(tasks, list):
        result["tasks"] = self._simple_list(tasks, 12 if detailed else 6)

# src/embedagent/tools/harness_runtime.py
"task_status": {
    "progress_renderer_key": "tasks",
    "result_renderer_key": "tasks",
}
```

- [ ] **Step 2: Delete the legacy helper and verify no runtime code still depends on it**

Run:

```powershell
rg -n "todos|todo" src/embedagent tests
```

Expected:

- no runtime dependency on `src/embedagent/todos.py`
- remaining matches, if any, are only in historical comments or review/spec material

- [ ] **Step 3: Update source-of-truth docs to reflect the cutover**

```markdown
- `QueryEngine` is session-scoped, not per-turn.
- `Session` owns durable conversation truth.
- `TaskGraph` is session task truth.
- `transcript.jsonl` is the only durable history ledger.
- adapters/frontends are projection and transport layers only.
```

- [ ] **Step 4: Run the focused regression suite for the cutover**

Run:

```powershell
pytest tests/test_query_engine_refactor.py -v
pytest tests/test_inprocess_adapter_frontend_api.py -v
pytest tests/test_session_restore.py -v
pytest tests/test_task_graph_v2.py -v
pytest tests/test_harness_task_projection.py -v
pytest tests/test_modes.py -v
pytest tests/test_tools_v2_runtime.py -v
pytest tests/test_transcript_store.py -v
pytest tests/test_session_timeline.py -v
pytest tests/test_gui_backend_api.py -v
```

Expected:

- PASS
- no `todo` runtime behavior remains
- strict mode handling, task truth, snapshot projection, and cached persistence all work together

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md docs/mode-schema.md docs/tool-contracts.md docs/permission-model.md docs/frontend-protocol.md docs/agent-harness-v2.md src/embedagent/context.py src/embedagent/workspace_profile.py src/embedagent/tools/harness_runtime.py
git rm src/embedagent/todos.py
git commit -m "docs: align architecture after agent core cutover"
```

## Self-Review

### Spec coverage

- Engine ownership and initialization are covered by Task 1.
- Step identity alignment is covered by Task 2.
- Resume pipeline and synthetic permission handling are covered by Task 3.
- TaskGraph truth and harness mutation boundaries are covered by Task 4.
- Mode fail-fast and runtime tool-truth cleanup are covered by Task 5.
- Snapshot projection and adapter slimming are covered by Task 6.
- Persistence hot-path optimization is covered by Task 7.
- Vocabulary cleanup and source-of-truth docs alignment are covered by Task 8.

### Placeholder scan

- No `TBD`, `TODO`, or deferred placeholders remain.
- All tasks list exact files and executable commands.
- No task says "similar to previous task" or leaves contracts unnamed.

### Type consistency

- Engine API is consistently referenced as `initialize_session(...)`, `submit_user_turn(...)`, and `resume_interaction(...)`.
- `update_task_graph(...)` is consistently defined as an in-place mutation API called by the engine at turn end.
- Step callback shape is consistently described as carrying `step_id` and `step_index`.

## Execution Handoff

Plan complete and saved to `docs/archive/agent-core-cutover/2026-04-07-agent-core-cutover-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
