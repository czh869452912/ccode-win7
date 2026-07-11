from __future__ import unicode_literals

import pytest

from embedagent_core.permissions import PermissionPolicy
from embedagent_core.query_engine import QueryEngine
from embedagent_core.session import Action, PendingInteraction
from embedagent_core.turn_snapshot import TurnSnapshot


def test_standalone_agent_core_public_symbols_are_available():
    from embedagent_core import (
        Agent,
        AgentObserver,
        AgentPorts,
        AgentResult,
        AgentSession,
        AgentSessionView,
        CancelToken,
        InteractionReply,
        RuntimeDefinition,
        UserTurn,
    )

    public_symbols = (
        Agent,
        AgentObserver,
        AgentPorts,
        AgentResult,
        AgentSession,
        AgentSessionView,
        CancelToken,
        InteractionReply,
        RuntimeDefinition,
        UserTurn,
    )

    assert all(symbol is not None for symbol in public_symbols)


def test_user_turn_rejects_empty_text():
    from embedagent_core import UserTurn

    with pytest.raises(ValueError, match="^user turn text is required$"):
        UserTurn("")


def test_user_turn_rejects_non_string_text():
    from embedagent_core import UserTurn

    with pytest.raises(TypeError, match="^user turn text must be a string$"):
        UserTurn(123)


def test_interaction_reply_rejects_empty_interaction_id():
    from embedagent_core import InteractionReply

    with pytest.raises(ValueError, match="^interaction id is required$"):
        InteractionReply("", {})


def test_interaction_reply_rejects_non_string_interaction_id():
    from embedagent_core import InteractionReply

    with pytest.raises(TypeError, match="^interaction id must be a string$"):
        InteractionReply(123, {})


def test_interaction_reply_rejects_non_dict_value():
    from embedagent_core import InteractionReply

    with pytest.raises(TypeError, match="^interaction reply value must be a dict or None$"):
        InteractionReply("interaction-1", [])


def test_interaction_reply_copies_nested_value():
    from embedagent_core import InteractionReply

    value = {"answer": {"choices": ["build"]}}
    reply = InteractionReply("interaction-1", value)

    value["answer"]["choices"].append("verify")

    assert reply.value == {"answer": {"choices": ["build"]}}


def test_runtime_definition_uses_neutral_defaults():
    from embedagent_core import RuntimeDefinition

    definition = RuntimeDefinition()

    assert definition.agent_id == "embedagent.base"
    assert definition.default_mode == ""
    assert definition.workflow_state == ""
    assert definition.extensions == ()


def test_runtime_definition_policy_defaults_are_isolated():
    from embedagent_core import RuntimeDefinition

    first = RuntimeDefinition()
    second = RuntimeDefinition()

    assert first.mode_tool_policy is not second.mode_tool_policy
    assert first.write_path_policy is not second.write_path_policy
    assert first.mode_runtime_policy is not second.mode_runtime_policy


def test_neutral_mode_runtime_policy_is_fail_neutral():
    from embedagent_core.policies import NeutralModeRuntimePolicy

    policy = NeutralModeRuntimePolicy()

    assert policy.default_mode() == ""
    assert policy.require_mode("") == {"slug": ""}
    assert policy.build_system_prompt("build", workspace="C:/workspace") == ""
    assert policy.parse_mode_switch_request("keep working", "spec") == (
        "spec",
        "keep working",
        False,
    )


def test_agent_session_view_copies_nested_workflow_state():
    from embedagent_core import AgentSessionView

    workflow_state = {"workflow": {"tasks": [{"id": "task-1"}]}}
    view = AgentSessionView("session-1", "build", workflow_state, 2, 1)

    workflow_state["workflow"]["tasks"][0]["id"] = "changed"

    assert view.workflow_state["workflow"]["tasks"][0]["id"] == "task-1"


def test_agent_result_copies_pending_interaction_and_turn_snapshot():
    from embedagent_core import AgentResult, AgentSessionView

    pending = PendingInteraction(
        interaction_id="interaction-1",
        request_payload={"choices": [{"id": "approve"}]},
    )
    snapshot = TurnSnapshot(
        snapshot_id="snapshot-1",
        session_id="session-1",
        turn_id="turn-1",
        step_id="step-1",
        mode_name="build",
        workflow_state="active",
        messages=[{"role": "user", "content": {"text": "original"}}],
    )
    result = AgentResult(
        "done",
        AgentSessionView("session-1", "build", {}, 2, 1),
        "completed",
        pending,
        snapshot,
    )

    pending.request_payload["choices"][0]["id"] = "changed"
    snapshot.messages[0]["content"]["text"] = "changed"

    assert result.pending_interaction is not None
    assert result.pending_interaction.request_payload["choices"][0]["id"] == "approve"
    assert result.turn_snapshot.messages[0]["content"]["text"] == "original"


def test_agent_result_copies_session_view():
    from embedagent_core import AgentResult, AgentSessionView

    session = AgentSessionView(
        "session-1",
        "build",
        {"workflow": {"phase": "implement"}},
        2,
        1,
    )
    result = AgentResult("done", session, "completed", None, None)

    session.workflow_state["workflow"]["phase"] = "changed"

    assert result.session.workflow_state["workflow"]["phase"] == "implement"


def test_turn_snapshot_preserves_empty_workflow_state():
    snapshot = TurnSnapshot(
        snapshot_id="snapshot-1",
        session_id="session-1",
        turn_id="turn-1",
        step_id="step-1",
        mode_name="explore",
        workflow_state="",
    )

    assert snapshot.workflow_state == ""


def test_permission_policy_does_not_auto_approve_by_default():
    assert PermissionPolicy().auto_approve_all is False


def test_permission_policy_requires_confirmation_for_unknown_tools():
    decision = PermissionPolicy().evaluate(Action("unknown_tool", {}, "call-1"))

    assert decision.outcome == "ask"
    assert decision.outcome != "allow"


def test_query_engine_does_not_auto_approve_by_default():
    engine = QueryEngine(client=object(), tools=object())

    assert engine.permission_policy.auto_approve_all is False
