from dataclasses import FrozenInstanceError

import embedagent_core
import pytest
from embedagent_core.agent_effects import (
    AssembleContextEffect,
    ContextAssembled,
    EffectFailed,
    ExecuteToolBatchEffect,
    ProviderCompleted,
    RequestProviderEffect,
    ToolBatchCompleted,
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


def test_kernel_advances_context_to_provider_and_provider_to_tools():
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

    assert provider_step.cursor.phase == "provider"
    assert isinstance(provider_step.effect, RequestProviderEffect)
    assert provider_step.effect.snapshot is not None

    reply = AssistantReply(
        "",
        actions=[Action("read_file", {"path": "README.md"}, "call-1")],
        finish_reason="tool_calls",
    )
    tool_step = kernel.accept(
        provider_step.cursor,
        ProviderCompleted(provider_step.effect.effect_id, reply),
    )

    assert tool_step.cursor.phase == "tools"
    assert isinstance(tool_step.effect, ExecuteToolBatchEffect)
    assert tool_step.effect.actions == tuple(reply.actions)


def test_kernel_cancellation_closes_unexecuted_tool_operations():
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
                actions=[
                    Action("read_file", {"path": "README.md"}, "call-1"),
                    Action("read_file", {"path": "AGENTS.md"}, "call-2"),
                ],
                finish_reason="tool_calls",
            ),
        ),
    )

    cancelled = kernel.accept(
        tool_step.cursor,
        EffectFailed(
            tool_step.effect.effect_id,
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
        tool_step.effect.effect_id,
        "tool:call-1",
        "tool:call-2",
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

    next_step = kernel.accept(
        tool_step.cursor,
        ToolBatchCompleted(
            tool_step.effect.effect_id,
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
