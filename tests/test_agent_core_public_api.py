from __future__ import unicode_literals

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
