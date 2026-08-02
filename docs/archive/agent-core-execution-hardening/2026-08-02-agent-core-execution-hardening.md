# Agent Core Execution Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保证工具参数截断时永不执行、所有实际工具 dispatch 都发生在耐久 `operation_started` 提交之后，并以稳定 invocation identity 统一串行/并行/恢复语义，同时收紧 Host 的默认权限。

**Architecture:** 保留 `AgentKernel -> AgentLoop -> AgentToolActionService` 单一状态机，把原有单阶段 tool effect 拆成 prepare 和 execute 两阶段。Prepare 串行冻结 effective action、策略和 catalog 快照；Kernel 提交 immediate results 与 ready invocation 的 execution-start intent；Loop 只有在提交成功后才 dispatch frozen invocation。Provider `call_id` 仅用于协议关联，耐久 operation identity 使用 assistant message id 与 source index。

**Tech Stack:** Python 3.8 dataclasses/typing、pytest/unittest、现有 `SessionJournal`/`SessionReducer`、现有 `StreamingToolExecutor`、uv 测试与六 wheel 构建工具。

---

## Scope Guardrails

- 不增加新发行包，不改变六 wheel 依赖方向。
- 不增加 lane、会话树、多智能体编排、自动 tool replay 或 public async operation handle。
- 不改变 public `AgentObserver`、Protocol DTO、frontend `session_event` shape 或 root SDK exports。
- 不保留 `ExecuteToolBatchEffect` 兼容别名；仓库处于 pre-release，所有内部调用点一次迁移。
- Prepare 可做 active-tool、before hook、permission、write-path、只读 catalog/path 查询；不得调用 extension tool handler、`execute_with_interrupt` 或 result materialization。
- Execute 不得重复 active-tool、before hook、permission 或 write-path 判断。

## Task 1: Define The Two-Phase Effect Contract And Stable Identity

**Files:**

- Modify: `tests/test_agent_effect_kernel.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_effects.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_kernel.py`

- [ ] **Step 1: Write failing Kernel contract tests**

Replace old `ExecuteToolBatchEffect` assertions and add focused tests covering:

```python
def _provider_tool_step(reply):
    kernel = AgentKernel()
    context_step = kernel.start("t-1", "debug", "", "user")
    provider_step = kernel.accept(
        context_step.cursor,
        ContextAssembled(
            context_step.effect.effect_id,
            _assembly(),
            _snapshot(),
        ),
    )
    return kernel, kernel.accept(
        provider_step.cursor,
        ProviderCompleted(provider_step.effect.effect_id, reply),
    )


def test_kernel_plans_tool_preparation_without_starting_tool_operations():
    _, tool_step = _provider_tool_step(
        AssistantReply(
            "",
            actions=[Action("read_file", {"path": "README.md"}, "provider-call")],
            finish_reason="tool_calls",
        )
    )

    assert isinstance(tool_step.effect, PrepareToolBatchEffect)
    assert tool_step.effect.assistant_message_id == "m-assistant-t-1-step-t-1-1-1"
    assert tool_step.effect.provider_truncated is False
    assert [event.event_type for event in tool_step.events].count("tool_call") == 1
    assert not any(
        event.event_type == "operation_started"
        and event.payload.get("kind") == "tool_call"
        for event in tool_step.events
    )


def test_kernel_accepts_prepared_batch_and_uses_stable_invocation_id():
    action = Action("read_file", {"path": "README.md"}, "provider-call")
    kernel, prepare_step = _provider_tool_step(
        AssistantReply(
            "",
            actions=[action],
            finish_reason="tool_calls",
        )
    )
    frozen_action = FrozenToolAction.from_action(action)
    prepared = PreparedToolInvocation(
        invocation_id="tool:m-assistant-t-1-step-t-1-1-1:0",
        provider_call_id="provider-call",
        source_index=0,
        original_action=frozen_action,
        effective_action=frozen_action,
        permission_category="workspace_read",
        read_only=True,
        concurrency_safe=True,
        presentation_json='{"tool_label":"read_file"}',
        source_type="builtin",
        source_id="read_file",
        replay_safe=False,
    )
    execute_step = kernel.accept(
        prepare_step.cursor,
        ToolBatchPrepared(prepare_step.effect.effect_id, invocations=(prepared,)),
    )

    starts = [event for event in execute_step.events if event.event_type == "operation_started"]
    assert [event.payload["operation_id"] for event in starts] == [prepared.invocation_id]
    assert starts[0].payload["tool_call_id"] == "provider-call"
    assert isinstance(execute_step.effect, ExecutePreparedToolBatchEffect)
```

Also assert that an immediate-only `ToolBatchPrepared` transitions directly to the next context effect and does not produce an empty execute effect.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_effect_kernel.py
```

Expected: collection/import failure for missing `PrepareToolBatchEffect`, `PreparedToolInvocation`, `ToolBatchPrepared`, and `ExecutePreparedToolBatchEffect`.

- [ ] **Step 3: Add frozen private contracts**

Replace `ExecuteToolBatchEffect` in `agent_effects.py` with frozen dataclasses shaped as follows:

```python
@dataclass(frozen=True)
class FrozenToolAction:
    name: str
    arguments_json: str
    call_id: str
    raw_arguments: str = ""

    @classmethod
    def from_action(cls, action: Action) -> "FrozenToolAction":
        return cls(
            action.name,
            json.dumps(
                action.arguments,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            action.call_id,
            action.raw_arguments,
        )

    def to_action(self) -> Action:
        return Action(
            self.name,
            json.loads(self.arguments_json),
            self.call_id,
            self.raw_arguments,
        )


@dataclass(frozen=True)
class PreparedToolInvocation:
    invocation_id: str
    provider_call_id: str
    source_index: int
    original_action: FrozenToolAction
    effective_action: FrozenToolAction
    permission_category: str
    read_only: bool
    concurrency_safe: bool
    presentation_json: str
    source_type: str
    source_id: str
    replay_safe: bool


@dataclass(frozen=True)
class ImmediateToolResult:
    source_index: int
    original_action: FrozenToolAction
    effective_action: FrozenToolAction
    observation: Observation


@dataclass(frozen=True)
class PrepareToolBatchEffect:
    effect_id: str
    assistant_message_id: str
    actions: Tuple[FrozenToolAction, ...]
    mode_name: str
    workflow_state: str
    provider_truncated: bool = False
    start_index: int = 0
    prepared_prefix: Tuple[PreparedToolInvocation, ...] = field(default_factory=tuple)
    immediate_prefix: Tuple[ImmediateToolResult, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExecutePreparedToolBatchEffect:
    effect_id: str
    invocations: Tuple[PreparedToolInvocation, ...]
    immediate_results: Tuple[ImmediateToolResult, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ToolBatchPrepared:
    effect_id: str
    invocations: Tuple[PreparedToolInvocation, ...] = field(default_factory=tuple)
    immediate_results: Tuple[ImmediateToolResult, ...] = field(default_factory=tuple)
    events: Tuple[EventIntent, ...] = field(default_factory=tuple)
    commit_tokens: Tuple[Any, ...] = field(default_factory=tuple)
```

Use Python 3.8-compatible annotations and keep all new types private to internal modules.
Canonical JSON snapshots make nested action arguments and presentation data immutable across the commit barrier; decode into fresh `Action`/dict values only at hook or dispatch boundaries. A non-JSON-safe hook result becomes an immediate `invalid_arguments` observation.

- [ ] **Step 4: Split Kernel phases and identity generation**

In `_accept_provider`:

- derive the assistant message id once and pass it both to the assistant event and `PrepareToolBatchEffect`;
- commit `tool_call` planned events only;
- normalize `finish_reason` with `str(result.reply.finish_reason or "").strip().lower() == "length"` into `provider_truncated`;
- start and durably record the non-side-effecting `tool_preparation` operation;
- set cursor phase to `tool_prepare`.

Add the single durable identity helper to `agent_effects.py` so Kernel and tool service cannot drift:

```python
def _tool_invocation_id(assistant_message_id: str, source_index: int) -> str:
    return "tool:%s:%d" % (assistant_message_id, source_index)
```

In `_accept_prepared`, close the preparation operation, emit `operation_started(kind="tool_call")` only for ready invocations, start the aggregate `tools` operation, and plan `ExecutePreparedToolBatchEffect` only when `invocations` is non-empty. An immediate-only batch closes preparation and advances directly to context without an aggregate execute operation. Store invocation ids in the cursor so failure closure never reconstructs ids from provider call ids.
Operation metadata contains invocation id, provider call id, effective tool name, presentation/source/replay snapshots, and only an existing safe argument summary; it must not duplicate raw arguments.

- [ ] **Step 5: Run the focused test and confirm GREEN**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_effect_kernel.py
```

Expected: all tests in the file pass, including frozen/private contract assertions.

- [ ] **Step 6: Commit Task 1**

```bash
git add tests/test_agent_effect_kernel.py packages/embedagent-core/src/embedagent_core/agent_effects.py packages/embedagent-core/src/embedagent_core/agent_kernel.py
git commit -m "refactor(core): split tool preparation from execution"
```

## Task 2: Make Preparation Serial, Complete, And Side-Effect Free

**Files:**

- Modify: `tests/test_agent_tool_effects.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py`
- Modify: `packages/embedagent-core/src/embedagent_core/tool_execution.py`

- [ ] **Step 1: Add failing preparation tests**

Extend fakes with ordered call recording and explicit catalog metadata. Add tests for:

```python
def test_prepare_checks_permission_and_path_before_any_dispatch():
    result = service.prepare(effect, session)

    assert isinstance(result, ToolBatchPrepared)
    assert calls == [
        "allowed:write_file",
        "before:write_file",
        "permission:workspace_write",
        "path:generated.c",
        "catalog:write_file",
    ]
    assert "extension_dispatch" not in calls
    assert "runtime_execute" not in calls
    assert "materialize" not in calls


@pytest.mark.parametrize(
    "outcome",
    ["mode_tool_blocked", "extension_blocked", "permission_denied", "invalid_arguments", "mode_path_blocked"],
)
def test_prepare_immediate_outcomes_never_become_ready_invocations(outcome):
    result = prepare_for(outcome)

    assert result.invocations == ()
    assert result.immediate_results[0].observation.data["error_kind"] == outcome
    assert not any(event.event_type == "operation_started" for event in result.events)
```

Add one test proving two `read_only && concurrency_safe` actions still run preparation serially and both permission checks occur before either dispatch.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_tool_effects.py
```

Expected: `AgentToolActionService.prepare` is missing and old parallel behavior bypasses the asserted permission/path sequence.

- [ ] **Step 3: Implement `prepare` and frozen catalog snapshots**

Introduce one source-ordered preparation loop. Its per-action result is either `PreparedToolInvocation`, `ImmediateToolResult`, or `InteractionSuspended`.

```python
def prepare(self, effect, session, permission_handler=None, user_input_handler=None):
    if not isinstance(effect, PrepareToolBatchEffect):
        raise TypeError("unsupported tool preparation effect")
    prepared = []
    immediate = []
    events = []
    for source_index, frozen_action in enumerate(effect.actions):
        action = frozen_action.to_action()
        outcome = self._prepare_action(
            effect,
            session,
            source_index,
            action,
            permission_handler,
            user_input_handler,
        )
        if isinstance(outcome, InteractionSuspended):
            return self._suspend_preparation(
                effect,
                session,
                source_index,
                outcome,
                tuple(prepared),
                tuple(immediate),
                tuple(events),
            )
        if isinstance(outcome, PreparedToolInvocation):
            prepared.append(outcome)
        else:
            immediate.append(outcome)
            events.extend(self._inline_immediate_result_events(session, outcome))
    return ToolBatchPrepared(
        effect.effect_id,
        invocations=tuple(prepared),
        immediate_results=tuple(immediate),
        events=tuple(events),
    )
```

The exact order inside `_prepare_action` is truncated guard, active-tool check, before hook, permission, write-path, interaction, catalog snapshot. Use `catalog_entry` only as a read-only metadata lookup. Set `replay_safe=False` in this slice because the current catalog has no explicit replay-safety contract; a future opt-in field requires its own design and tests. Do not infer replay safety from read-only or idempotency guesses.

Create inline tool-result intents for immediate synthetic failures without calling `materialize_observation`; these results contain bounded error payloads and no content replacement.

- [ ] **Step 4: Remove parallel pre-dispatch**

Delete `execute_parallel_tool_action` and the old `precomputed_observations` re-entry path. Update `tool_execution.py` to partition `PreparedToolInvocation` values by their frozen `read_only` and `concurrency_safe` fields instead of querying a mutable runtime catalog.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_tool_effects.py
uv run python scripts/test-suite.py tdd tests/test_tool_execution.py
```

Expected: preparation tests pass; existing partition/order/cancellation tests pass using prepared invocations.

- [ ] **Step 6: Commit Task 2**

```bash
git add tests/test_agent_tool_effects.py tests/test_tool_execution.py packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py packages/embedagent-core/src/embedagent_core/tool_execution.py
git commit -m "feat(core): prepare tool actions before dispatch"
```

## Task 3: Enforce The Journal Commit Barrier In AgentLoop

**Files:**

- Modify: `tests/test_agent_loop_driver.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_loop.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py`

- [ ] **Step 1: Add failing commit-order and commit-failure tests**

Make the test kernel produce `PrepareToolBatchEffect`, then `ExecutePreparedToolBatchEffect`. Split the fake action service into `prepare` and `execute_prepared` calls.

```python
def test_driver_commits_prepared_execution_start_before_dispatch():
    calls = []
    result = _loop(calls, kernel=TwoPhaseSequenceKernel()).run(
        Session(session_id="session-1"),
        SessionReducerContext(),
        "turn-1",
        "build",
        "",
    )

    assert calls == [
        "commit:context_started",
        "execute:context",
        "commit:provider_started",
        "execute:provider",
        "commit:tool_planned",
        "prepare:tool",
        "commit:tool_execution_started",
        "execute:tool",
        "commit:completed",
    ]
    assert result.transition.reason == "completed"


def test_driver_does_not_dispatch_when_execution_start_commit_fails():
    calls = []
    journal = FailingJournal(label="tool_execution_started")

    with pytest.raises(IOError, match="append failed"):
        _loop(calls, journal=journal).run(
            Session(session_id="session-1"),
            SessionReducerContext(),
            "turn-1",
            "build",
            "",
        )

    assert "prepare:tool" in calls
    assert "execute:tool" not in calls
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_loop_driver.py
```

Expected: old loop has one tool execution branch and cannot express the prepare/commit/execute ordering.

- [ ] **Step 3: Add explicit loop branches**

In `_execute_effect` dispatch the two internal phases explicitly:

```python
if isinstance(effect, PrepareToolBatchEffect):
    return self._tool_actions.prepare(
        effect,
        session,
        permission_handler=observer.on_permission_request,
        user_input_handler=observer.on_user_input_request,
    )
if isinstance(effect, ExecutePreparedToolBatchEffect):
    return self._tool_actions.execute_prepared(
        effect,
        session,
        stop_event=cancel,
        on_action_start=observer.on_tool_start,
        max_parallel_tools=max_parallel_tools,
    )
```

`ToolBatchCompleted` feeds `ProgressGuard` and tool-finish notifications for mixed or ready batches after observations are merged by source index. An immediate-only `ToolBatchPrepared` feeds the same guard/notification path exactly once after its events commit; a mixed batch defers immediate notifications until `ToolBatchCompleted` to prevent double counting.

- [ ] **Step 4: Implement execution of frozen invocations**

`execute_prepared` may call only:

1. source-aware extension handler using the frozen source identity;
2. `ToolRuntime.execute_with_interrupt` if unhandled;
3. after-tool hook;
4. observation materialization;
5. result/workflow/operation-finish event construction.

Every finish/interruption event must use `prepared.invocation_id`, never `"tool:%s" % action.call_id`.

- [ ] **Step 5: Preserve source order under parallel completion**

Partition only contiguous ready invocations whose frozen flags are both true. Allow observer start/finish callbacks to reflect runtime timing, but sort canonical observations and event groups by `source_index` before returning `ToolBatchCompleted`.

- [ ] **Step 6: Run focused tests and confirm GREEN**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_loop_driver.py
uv run python scripts/test-suite.py tdd tests/test_agent_tool_effects.py
uv run python scripts/test-suite.py tdd tests/test_tool_execution.py
```

Expected: commit order, failure barrier, cancellation, finalization, and source ordering all pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add tests/test_agent_loop_driver.py tests/test_agent_tool_effects.py tests/test_tool_execution.py packages/embedagent-core/src/embedagent_core/agent_loop.py packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py
git commit -m "feat(core): commit tool intent before runtime dispatch"
```

## Task 4: Guard Truncated Provider Tool Calls End To End

**Files:**

- Modify: `tests/test_agent_runtime_integration.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_kernel.py`

- [ ] **Step 1: Add a failing integration test**

Create a client whose first reply has actions and `finish_reason="length"`, then returns a complete answer after receiving tool errors.

```python
def test_truncated_tool_arguments_are_reported_without_dispatch(self):
    transcript_store = TranscriptStore(self.workspace)
    runtime = CountingToolRuntime(self.tools)
    engine = RuntimeDispatcher(
        client=TruncatedToolClient(),
        tools=runtime,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
        transcript_store=transcript_store,
    )
    result = engine.submit_user_turn(
        user_text="run the truncated calls",
        stream=False,
        initial_mode="build",
        session=Session(),
    )

    assert runtime.execute_count == 0
    assert result.transition.reason == "completed"
    events = transcript_store.load_events(result.session.session_id)
    tool_results = [item for item in events if item["type"] == "tool_result"]
    assert [item["payload"]["observation"]["data"]["error_kind"] for item in tool_results] == [
        "truncated_tool_arguments",
        "truncated_tool_arguments",
    ]
    assert not any(
        item["type"] == "operation_started"
        and item["payload"].get("kind") == "tool_call"
        for item in events
    )
```

Assert the next provider request contains standard role=`tool` messages with the original provider call ids.

- [ ] **Step 2: Run the focused node and confirm RED**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_runtime_integration.py::TestRuntimeDispatcherRefactor::test_truncated_tool_arguments_are_reported_without_dispatch
```

Expected: runtime count is non-zero because the current code executes actions regardless of `finish_reason="length"`.

- [ ] **Step 3: Materialize synthetic truncated results in preparation**

For every action in a truncated batch, return a bounded failure observation:

```python
Observation(
    action.name,
    False,
    "provider output ended before tool arguments were complete",
    {
        "error_kind": "truncated_tool_arguments",
        "retryable": True,
        "blocked_by": "provider_finish_reason",
        "synthetic": True,
    },
)
```

Do this before active-tool checks or hooks. Kernel commits the tool results and starts the next context step; it does not stop the turn and does not create an execute effect.

- [ ] **Step 4: Run Kernel and integration tests and confirm GREEN**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_effect_kernel.py
uv run python scripts/test-suite.py tdd tests/test_agent_runtime_integration.py::TestRuntimeDispatcherRefactor::test_truncated_tool_arguments_are_reported_without_dispatch
```

Expected: both pass and runtime dispatch count remains zero.

- [ ] **Step 5: Commit Task 4**

```bash
git add tests/test_agent_runtime_integration.py packages/embedagent-core/src/embedagent_core/agent_tool_action_service.py packages/embedagent-core/src/embedagent_core/agent_kernel.py
git commit -m "fix(core): reject truncated provider tool calls"
```

## Task 5: Migrate Interaction Resume And Direct Tool-Service Callers

**Files:**

- Modify: `packages/embedagent-core/src/embedagent_core/session_input.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_kernel.py`
- Modify: `packages/embedagent-core/src/embedagent_core/agent_loop.py`
- Modify: `tests/test_agent_tool_effects.py`
- Modify: `tests/test_agent_loop_driver.py`
- Modify: `tests/test_agent_runtime_integration.py`
- Modify: `tests/test_capability_extensions.py`
- Modify: `tests/test_dynamic_tool_registration.py`

- [ ] **Step 1: Add failing interaction checkpoint tests**

Extend permission and user-input suspension tests to assert the pending request carries a preparation checkpoint:

```python
checkpoint = result.pending.request_payload["tool_preparation"]
assert checkpoint["assistant_message_id"]
assert checkpoint["continuation"] in ("context", "complete")
assert checkpoint["source_index"] == 0
assert checkpoint["invocation_id"] == "tool:%s:0" % checkpoint["assistant_message_id"]
assert checkpoint["actions"][0]["call_id"] == "call-1"
assert checkpoint["effective_action"]["name"] == "write_file"
```

Also assert the suspension result contains no `operation_started(kind="tool_call")`. Add integration coverage proving that accepting a pending permission writes `operation_started` before resumed runtime dispatch and uses the checkpoint invocation id.

Add Loop-driver tests for a resumed provider batch and a command tool turn. The command test must show that a deterministic assistant action message with provider attempt `0` commits before preparation, and that no second provider request occurs after command completion.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_tool_effects.py::test_permission_ask_returns_interaction_suspended_without_execution
uv run python scripts/test-suite.py tdd tests/test_agent_runtime_integration.py::TestRuntimeDispatcherRefactor::test_adapter_resumes_pending_user_input tests/test_agent_runtime_integration.py::TestRuntimeDispatcherRefactor::test_adapter_resumes_pending_permission
uv run python scripts/test-suite.py tdd tests/test_agent_loop_driver.py::test_driver_continues_preparation_through_commit_barrier tests/test_agent_loop_driver.py::test_driver_completes_command_tool_continuation_without_provider_step
```

Expected: pending payload lacks the checkpoint, resume and command paths call the old single-stage service directly, and the Loop tests fail before dispatch-order assertions.

- [ ] **Step 3: Resume from the frozen checkpoint through the same barrier**

Refactor `AgentLoop.run` so its existing commit-execute-resume body is a private `_drive(initial_step, ...)`. Add an internal `continue_from(initial_step, ...)` entry that delegates to the same driver; it must not duplicate commit or notification logic.

Add Kernel continuation constructors for checkpoint resume and command tool turns. The private cursor records whether a completed tool batch continues to context or completes the command turn, plus the frozen invocation ids used for cancellation closure.

Update `session_input.py` to validate and decode the checkpoint, resolve the pending interaction into a Kernel continuation, and pass that initial step to `AgentLoop.continue_from`. It must not commit tool preparation/execution events or call the action service directly.

For `submit_command_turn`, persist a deterministic assistant action message using provider attempt `0`, create a command-completion Kernel continuation, and run it through the same Loop driver. A denied, invalid, or suspended command action must not receive tool `operation_started`.

Do not regenerate invocation ids from provider call ids. Validate the checkpoint against pending `tool_name`, `call_id`, assistant message id, source index, and continuation target; malformed checkpoints fail closed as recovery-required/invalid interaction data without dispatch.

- [ ] **Step 4: Migrate every direct internal constructor**

Replace direct `ExecuteToolBatchEffect` uses in:

- production command and interaction-resume constructors in `session_input.py`;
- inactive-tool runtime integration test;
- dynamic runtime tool tests;
- extension-owned tool tests;
- capability extension hook tests.

Each service-level test must explicitly call `prepare`, assert the typed result, then call `execute_prepared` only when invocations are ready.

- [ ] **Step 5: Prove the old type is gone**

Run:

```bash
rg "ExecuteToolBatchEffect" packages tests
```

Expected: no matches.

- [ ] **Step 6: Run all affected tests and confirm GREEN**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_agent_tool_effects.py
uv run python scripts/test-suite.py tdd tests/test_agent_loop_driver.py
uv run python scripts/test-suite.py tdd tests/test_agent_runtime_integration.py
uv run python scripts/test-suite.py tdd tests/test_capability_extensions.py
uv run python scripts/test-suite.py tdd tests/test_dynamic_tool_registration.py
```

Expected: command and interaction continuations, dynamic tools, extension hooks, cancellation, and parallel execution all pass through the single Loop driver.

- [ ] **Step 7: Commit Task 5**

```bash
git add packages/embedagent-core/src/embedagent_core/agent_kernel.py packages/embedagent-core/src/embedagent_core/agent_loop.py packages/embedagent-core/src/embedagent_core/session_input.py tests/test_agent_loop_driver.py tests/test_agent_tool_effects.py tests/test_agent_runtime_integration.py tests/test_capability_extensions.py tests/test_dynamic_tool_registration.py
git commit -m "refactor(core): route tool continuations through agent loop"
```

## Task 6: Pin Restore Semantics To Actual Execution Start

**Files:**

- Modify: `tests/test_session_operation_log.py`
- Modify: `tests/test_session_integration.py`
- Modify: `packages/embedagent-core/src/embedagent_core/session_transaction.py` only if the tests expose a mismatch

- [ ] **Step 1: Add restore tests for planned-only versus started tools**

```python
def test_restore_does_not_treat_planned_tool_call_as_incomplete_side_effect():
    append_tool_call(call_id="provider-call")

    restored = restore_transaction()

    assert restored.session.turns[-1].steps[-1].tool_calls[0].call_id == "provider-call"


def test_restore_rejects_unfinished_stable_tool_operation():
    append_tool_call(call_id="provider-call")
    append_operation_started(
        operation_id="tool:m-assistant-t-1-s-1-1:0",
        tool_call_id="provider-call",
    )

    with pytest.raises(SessionRecoveryRequired, match="incomplete_side_effect"):
        restore_transaction()
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_session_operation_log.py
uv run python scripts/test-suite.py tdd tests/test_session_integration.py::TestSessionIntegration::test_restore_does_not_treat_planned_tool_call_as_incomplete_side_effect tests/test_session_integration.py::TestSessionIntegration::test_restore_rejects_unfinished_stable_tool_operation
```

Expected: operation reducer accepts the stable id; planned-only tool calls do not create operation state. If both already pass, record that no production restore change is needed.

- [ ] **Step 3: Make the minimum restore fix if required**

Keep `_has_incomplete_side_effect` based exclusively on explicit unfinished `operation_started(kind="tool_call")`. Do not infer side effects from legacy/planned `tool_call` events and do not add automatic replay.

- [ ] **Step 4: Commit Task 6**

```bash
git add tests/test_session_operation_log.py tests/test_session_integration.py packages/embedagent-core/src/embedagent_core/session_transaction.py
git commit -m "test(core): distinguish planned and started tool restore"
```

Omit an unchanged production file from `git add`.

## Task 7: Make InProcessAdapter Permission Defaults Safe

**Files:**

- Modify: `tests/test_inprocess_adapter_frontend_api.py`
- Modify: `tests/test_permissions.py`
- Modify: `packages/embedagent-host/src/embedagent_host/inprocess_adapter.py`

- [ ] **Step 1: Add a failing default-policy test**

Construct the adapter without `permission_policy` and inspect behavior rather than private flags:

```python
def test_adapter_default_policy_allows_read_and_asks_for_write_and_execution(self):
    adapter = _product_adapter(client=WriteThenDoneClient(), tools=self.tools)
    snapshot = adapter.create_session("build")

    adapter.submit_user_message(
        session_id=snapshot["session_id"],
        text="write a file",
        stream=False,
        wait=True,
        event_handler=lambda envelope: None,
    )

    waiting = adapter.get_session_snapshot(snapshot["session_id"])
    assert waiting["status"] == "waiting_permission"
    assert waiting["pending_interaction"]["kind"] == "permission"
```

Use parameterized policy-level assertions for `workspace_write`, `execution`, `network`, `telemetry`, and `other`; preserve the existing read allow behavior.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_adapter_default_policy_allows_read_and_asks_for_write_and_execution
```

Expected: the write action executes because the adapter currently creates `PermissionPolicy(auto_approve_all=True)`.

- [ ] **Step 3: Change only the implicit default**

```python
self.permission_policy = permission_policy or PermissionPolicy()
```

Do not change hosted runtime construction from explicit `LaunchConfig` and do not couple `WritePathPolicy` to permission approval.

- [ ] **Step 4: Run focused Host tests and confirm GREEN**

Run:

```bash
uv run python scripts/test-suite.py tdd tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_adapter_default_policy_allows_read_and_asks_for_write_and_execution tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendApis::test_snapshot_and_session_history_preserve_permission_wait_transition
uv run python scripts/test-suite.py tdd tests/test_permissions.py
```

Expected: read remains allowed; write/execution/network/telemetry/other ask by default.

- [ ] **Step 5: Commit Task 7**

```bash
git add tests/test_inprocess_adapter_frontend_api.py tests/test_permissions.py packages/embedagent-host/src/embedagent_host/inprocess_adapter.py
git commit -m "fix(host): require explicit approval for side effects"
```

## Task 8: Synchronize Authorities, Run Gates, And Archive The Slice

**Files:**

- Modify: `docs/platform/agent-core.md`
- Modify: `docs/platform/session-runtime.md`
- Modify: `docs/platform/permissions-and-context.md`
- Modify: `docs/current-status.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/references/code-doc-matrix.md` only if ownership paths changed
- Move: `docs/superpowers/specs/2026-08-02-agent-core-execution-hardening-design.md`
- Move: `docs/superpowers/plans/2026-08-02-agent-core-execution-hardening.md`
- Modify: `docs/superpowers/README.md`
- Add/Modify: `docs/archive/agent-core-execution-hardening/README.md`

- [ ] **Step 1: Run architecture guards before documentation closure**

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
```

Expected: all guard tests pass, including no retired `ExecuteToolBatchEffect` references and preserved distribution direction.

- [ ] **Step 2: Update owning authorities in place**

Record only current durable truth:

- `agent-core.md`: prepare/commit/execute Kernel/Loop state machine and stable invocation identity;
- `session-runtime.md`: planned `tool_call` versus actual `operation_started`, and restore outcome-unknown rule;
- `permissions-and-context.md`: serial prepare order shared by serial/parallel execution and safe implicit Host default;
- `current-status.md` / `implementation-roadmap.md`: close this blocker and identify the next Core boundary slice without a completion diary.

Update `code-doc-matrix.md` only when code ownership changed; do not duplicate architecture detail in the matrix.

- [ ] **Step 3: Run the complete regular verification**

```bash
uv run python scripts/test-suite.py full
uv run --locked python scripts/lint.py
```

Expected: full partition and lint pass.

- [ ] **Step 4: Build, check, and isolate-smoke all six distributions**

```bash
uv run python scripts/build-python-distributions.py --dist-dir dist
uv run python scripts/check-python-distributions.py --dist-dir dist
uv run python scripts/smoke-python-distributions.py --dist-dir dist --python .venv/Scripts/python.exe
```

Expected: exactly six wheels are built and validated; all isolated smoke tests pass with wheel-only installation.

- [ ] **Step 5: Archive the closed temporary slice**

Move the approved spec and completed plan into `docs/archive/agent-core-execution-hardening/`, add an archive `README.md` that indexes both files and names the owning active authorities, and remove the slice from `docs/superpowers/README.md`.

Run:

```bash
rg -n "Agent Core Execution Hardening|agent-core-execution-hardening" docs/superpowers docs/archive docs/platform docs/current-status.md docs/implementation-roadmap.md
```

Expected: no active superpowers entry remains; archive and current authorities link consistently.

- [ ] **Step 6: Review the final diff and commit closure**

```bash
git diff --check
git status --short
git diff --stat
git add docs packages tests
git commit -m "docs: record hardened agent execution boundary"
```

- [ ] **Step 7: Record verification evidence in the final handoff**

Report exact commands and pass/fail results. Do not claim Windows 7 release acceptance; this slice does not produce real clean-machine Win7/WebView2 evidence.

## Plan Self-Review Checklist

- [x] Every acceptance item in the approved design maps to at least one test or gate above.
- [x] No step depends on Python 3.9+ syntax or APIs.
- [x] No public package dependency or frontend protocol change is implied.
- [x] Tool dispatch cannot occur before the Kernel-produced start intent commits.
- [x] Immediate and suspended outcomes never receive tool execution-start records.
- [x] Interaction resume preserves the original assistant identity and source index.
- [x] Parallelism operates only on frozen ready invocations and canonical output stays source ordered.
- [x] Restore distinguishes planned tool calls from started side effects without replay.
- [x] Documentation closure updates one owner per fact and archives temporary slice files.
