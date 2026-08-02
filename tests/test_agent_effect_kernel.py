from dataclasses import FrozenInstanceError

import embedagent_core
import pytest
from embedagent_core.agent_effects import (
    AssembleContextEffect,
    ContextAssembled,
    EffectFailed,
    ExecutePreparedToolBatchEffect,
    FrozenToolAction,
    ImmediateToolResult,
    PreparedToolInvocation,
    PrepareToolBatchEffect,
    ProviderCompleted,
    ToolBatchCompleted,
    ToolBatchPrepared,
)
from embedagent_core.agent_kernel import AgentKernel, KernelCursor
from embedagent_core.session import (
    Action,
    AssistantReply,
    ContextAssemblyResult,
    Observation,
)
from embedagent_core.turn_snapshot import TurnSnapshot


def _assembly():
    return ContextAssemblyResult(
        messages=[{"role": "user", "content": "hello"}],
        used_chars=5,
        approx_tokens=2,
        compacted=False,
        summarized_turns=0,
        recent_turns=1,
        policy=None,
        budget=None,
        stats=None,
    )


def _snapshot():
    return TurnSnapshot(
        snapshot_id="snapshot-1",
        session_id="session-1",
        turn_id="t-1",
        step_id="step-1",
        mode_name="debug",
        workflow_state="",
        messages=[{"role": "user", "content": "hello"}],
        tool_schemas=[],
    )


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


def _prepared_invocation(action, source_index=0):
    frozen_action = FrozenToolAction.from_action(action)
    return PreparedToolInvocation(
        invocation_id="tool:m-assistant-t-1-step-t-1-1-1:%d" % source_index,
        provider_call_id=action.call_id,
        source_index=source_index,
        original_action=frozen_action,
        effective_action=frozen_action,
        permission_category="workspace_read",
        read_only=True,
        concurrency_safe=True,
        presentation_json='{"tool_label":"%s"}' % action.name,
        source_type="builtin",
        source_id=action.name,
        replay_safe=False,
    )


def test_kernel_rejects_result_for_wrong_effect_id():
    kernel = AgentKernel()
    cursor = KernelCursor("provider", "effect-1", 1, 1, False)

    with pytest.raises(ValueError, match="^effect_result_mismatch$"):
        kernel.accept(cursor, ProviderCompleted("effect-2", AssistantReply("done")))


def test_kernel_plans_context_before_provider():
    step = AgentKernel().start("t-1", "debug", "", "user")

    assert step.cursor.phase == "context"
    assert isinstance(step.effect, AssembleContextEffect)
    assert step.effect.turn_id == "t-1"
    assert step.effect.mode_name == "debug"
    assert [event.event_type for event in step.events] == [
        "step_started",
        "operation_started",
        "operation_started",
    ]
    assert step.events[-1].payload["kind"] == "context_assembly"


def test_kernel_plans_tool_preparation_without_starting_tool_operations():
    reply = AssistantReply(
        "",
        actions=[Action("read_file", {"path": "README.md"}, "provider-call")],
        finish_reason="tool_calls",
    )
    _, tool_step = _provider_tool_step(reply)

    assert tool_step.cursor.phase == "tool_prepare"
    assert isinstance(tool_step.effect, PrepareToolBatchEffect)
    assert tool_step.effect.assistant_message_id == "m-assistant-t-1-step-t-1-1-1"
    assert tool_step.effect.provider_truncated is False
    assert tuple(action.to_action() for action in tool_step.effect.actions) == tuple(reply.actions)
    assert [event.event_type for event in tool_step.events].count("tool_call") == 1
    assert not any(
        event.event_type == "operation_started" and event.payload.get("kind") == "tool_call"
        for event in tool_step.events
    )


def test_kernel_accepts_prepared_batch_and_uses_stable_invocation_id():
    action = Action("read_file", {"path": "README.md"}, "provider-call")
    kernel, prepare_step = _provider_tool_step(
        AssistantReply("", actions=[action], finish_reason="tool_calls")
    )
    prepared = _prepared_invocation(action)

    execute_step = kernel.accept(
        prepare_step.cursor,
        ToolBatchPrepared(prepare_step.effect.effect_id, invocations=(prepared,)),
    )

    tool_starts = [
        event
        for event in execute_step.events
        if event.event_type == "operation_started" and event.payload.get("kind") == "tool_call"
    ]
    assert [event.payload["operation_id"] for event in tool_starts] == [prepared.invocation_id]
    assert tool_starts[0].payload["tool_call_id"] == "provider-call"
    assert "arguments" not in tool_starts[0].payload["metadata"]
    assert execute_step.cursor.phase == "tool_execute"
    assert isinstance(execute_step.effect, ExecutePreparedToolBatchEffect)
    assert execute_step.effect.invocations == (prepared,)


def test_kernel_skips_empty_execute_effect_for_immediate_only_batch():
    action = Action("write_file", {"path": "demo.c"}, "provider-call")
    kernel, prepare_step = _provider_tool_step(
        AssistantReply("", actions=[action], finish_reason="tool_calls")
    )
    frozen = FrozenToolAction.from_action(action)
    immediate = ImmediateToolResult(
        source_index=0,
        original_action=frozen,
        effective_action=frozen,
        observation=Observation(
            "write_file",
            False,
            "permission denied",
            {"error_kind": "permission_denied"},
        ),
    )

    next_step = kernel.accept(
        prepare_step.cursor,
        ToolBatchPrepared(
            prepare_step.effect.effect_id,
            immediate_results=(immediate,),
        ),
    )

    assert next_step.cursor.phase == "context"
    assert isinstance(next_step.effect, AssembleContextEffect)
    assert not any(
        event.event_type == "operation_started"
        and event.payload.get("kind") in ("tool_call", "tools")
        for event in next_step.events
    )


def test_kernel_cancellation_before_preparation_does_not_invent_tool_operations():
    kernel, prepare_step = _provider_tool_step(
        AssistantReply(
            "",
            actions=[
                Action("read_file", {"path": "README.md"}, "call-1"),
                Action("read_file", {"path": "AGENTS.md"}, "call-2"),
            ],
            finish_reason="tool_calls",
        )
    )

    cancelled = kernel.accept(
        prepare_step.cursor,
        EffectFailed(
            prepare_step.effect.effect_id,
            "cancelled",
            "stop_event set",
            retryable=False,
        ),
    )

    interrupted_ids = [
        event.payload.get("operation_id")
        for event in cancelled.events
        if event.event_type == "operation_interrupted"
    ]
    assert interrupted_ids == [
        prepare_step.effect.effect_id,
        "step:step-t-1-1",
    ]


def test_kernel_carries_tool_commit_tokens_only_after_result_acceptance():
    kernel = AgentKernel()
    context_step = kernel.start("t-1", "debug", "", "user")
    provider_step = kernel.accept(
        context_step.cursor,
        ContextAssembled(context_step.effect.effect_id, _assembly(), _snapshot()),
    )
    tool_step = kernel.accept(
        provider_step.cursor,
        ProviderCompleted(
            provider_step.effect.effect_id,
            AssistantReply(
                "",
                actions=[Action("read_file", {"path": "README.md"}, "call-1")],
                finish_reason="tool_calls",
            ),
        ),
    )

    prepared = _prepared_invocation(tool_step.effect.actions[0].to_action())
    execute_step = kernel.accept(
        tool_step.cursor,
        ToolBatchPrepared(tool_step.effect.effect_id, invocations=(prepared,)),
    )
    next_step = kernel.accept(
        execute_step.cursor,
        ToolBatchCompleted(
            execute_step.effect.effect_id,
            observations=(Observation("read_file", True, None, {"path": "README.md"}),),
            commit_tokens=("commit-1",),
        ),
    )

    assert next_step.post_commit_tokens == ("commit-1",)
    assert next_step.cursor.phase == "context"
    assert isinstance(next_step.effect, AssembleContextEffect)


def test_kernel_turns_empty_provider_reply_into_guard_stop():
    kernel = AgentKernel()
    context_step = kernel.start("t-1", "debug", "", "user")
    provider_step = kernel.accept(
        context_step.cursor,
        ContextAssembled(context_step.effect.effect_id, _assembly(), _snapshot()),
    )

    completed = kernel.accept(
        provider_step.cursor,
        ProviderCompleted(
            provider_step.effect.effect_id,
            AssistantReply("", actions=[], finish_reason="stop"),
        ),
    )

    assert completed.outcome.reason == "guard_stop"
    assert "empty assistant response" in completed.outcome.message
    transitions = [event for event in completed.events if event.event_type == "loop_transition"]
    assert transitions[-1].payload["reason"] == "guard_stop"


def test_kernel_owns_single_context_limit_compact_retry():
    cursor = KernelCursor(
        "provider",
        "provider-1",
        1,
        1,
        False,
        turn_id="t-1",
        mode_name="debug",
    )

    retry = AgentKernel().accept(
        cursor,
        EffectFailed("provider-1", "context_limit", "too large", retryable=False),
    )

    assert retry.cursor.phase == "context"
    assert retry.cursor.compact_retry_used is True
    assert isinstance(retry.effect, AssembleContextEffect)
    assert retry.effect.force_compact is True
    transition = [event for event in retry.events if event.event_type == "loop_transition"][-1]
    assert transition.payload["reason"] == "compact_retry"
    assert transition.payload["metadata"]["retry_mode"] == "compact"
    context_started = retry.events[-1]
    assert context_started.payload["metadata"]["force_compact"] is True
    assert context_started.payload["metadata"]["mode_name"] == "debug"


def test_effect_types_are_frozen_and_private_to_internal_modules():
    effect = AssembleContextEffect("effect-1", "t-1", "step-1", "debug", "")

    with pytest.raises(FrozenInstanceError):
        effect.mode_name = "verify"
    assert not hasattr(embedagent_core, "AssembleContextEffect")
    assert not hasattr(embedagent_core, "KernelCursor")
