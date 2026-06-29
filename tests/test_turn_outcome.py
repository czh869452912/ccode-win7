from embedagent.session import LoopTransition, QueryTurnResult, Session, TurnOutcome


def test_completed_transition_maps_to_successful_outcome():
    outcome = TurnOutcome.from_transition(
        LoopTransition(reason="completed", message="done", turns_used=2)
    )

    assert outcome.kind == "completed"
    assert outcome.reason == "completed"
    assert outcome.message == "done"
    assert outcome.exit_code == 0
    assert outcome.is_success is True


def test_guard_stop_transition_maps_to_blocked_outcome():
    outcome = TurnOutcome.from_transition(
        LoopTransition(reason="guard_stop", message="repeated tool calls: bash")
    )

    assert outcome.kind == "blocked"
    assert outcome.reason == "guard_stop"
    assert outcome.message == "repeated tool calls: bash"
    assert outcome.exit_code == 2
    assert outcome.is_success is False


def test_max_turns_transition_maps_to_partial_outcome():
    outcome = TurnOutcome.from_transition(
        LoopTransition(reason="max_turns", message="explicit safety fuse")
    )

    assert outcome.kind == "partial"
    assert outcome.reason == "max_turns"
    assert outcome.exit_code == 2
    assert outcome.is_success is False


def test_aborted_transition_maps_to_aborted_outcome():
    outcome = TurnOutcome.from_transition(LoopTransition(reason="aborted", message="stopped"))

    assert outcome.kind == "aborted"
    assert outcome.reason == "aborted"
    assert outcome.exit_code == 130
    assert outcome.is_success is False


def test_permission_wait_transition_maps_to_waiting_outcome():
    outcome = TurnOutcome.from_transition(
        LoopTransition(reason="permission_wait", message="approval required")
    )

    assert outcome.kind == "waiting"
    assert outcome.reason == "permission_wait"
    assert outcome.exit_code == 2
    assert outcome.is_success is False


def test_query_turn_result_exposes_transition_outcome():
    result = QueryTurnResult(
        "final",
        Session(),
        LoopTransition(reason="guard_stop", message="blocked"),
    )

    assert result.outcome.kind == "blocked"
    assert result.outcome.to_dict()["kind"] == "blocked"
