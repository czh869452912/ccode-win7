from __future__ import unicode_literals

import pytest

from embedagent_core.permissions import PermissionPolicy
from embedagent_core.query_engine import QueryEngine
from embedagent_core.session import Action
from embedagent_core.turn_snapshot import TurnSnapshot


def test_standalone_agent_core_public_symbols_are_available():
    from embedagent_core import (
        Agent,
        AgentObserver,
        AgentPorts,
        AgentResult,
        AgentSession,
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


def test_interaction_reply_rejects_empty_interaction_id():
    from embedagent_core import InteractionReply

    with pytest.raises(ValueError, match="^interaction id is required$"):
        InteractionReply("", {})


def test_runtime_definition_uses_neutral_defaults():
    from embedagent_core import RuntimeDefinition

    definition = RuntimeDefinition()

    assert definition.agent_id == "embedagent.base"
    assert definition.default_mode == ""
    assert definition.workflow_state == ""
    assert definition.extensions == ()


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
