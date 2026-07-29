import pytest
from embedagent_host.hosted_interaction_service import (
    HostedInteractionService,
    HostedPendingInteraction,
    _response_for_answer,
)
from embedagent_host.runtime.session_runtime import ManagedSession


def test_user_input_response_matches_option_value():
    ticket = HostedPendingInteraction(
        interaction_id="ask-1",
        kind="user_input",
        session_id="sess-1",
        tool_name="ask_user",
        payload={
            "questions": [
                {
                    "id": "target",
                    "question": "Choose target?",
                    "options": [
                        {
                            "index": 2,
                            "label": "Python",
                            "value": "python",
                            "mode": "python-build",
                        }
                    ],
                }
            ]
        },
    )

    response = _response_for_answer(ticket, "python")

    assert response.answer == "python"
    assert response.selected_index == 2
    assert response.selected_mode == "python-build"
    assert response.selected_option_text == "Python"


def test_pending_interaction_claim_rejects_duplicate_resolution():
    state = ManagedSession(session_id="sess-1", current_mode="build")
    ticket = HostedPendingInteraction(
        interaction_id="ask-1",
        kind="user_input",
        session_id="sess-1",
        tool_name="ask_user",
        payload={"questions": []},
    )
    state.pending_interaction = ticket
    service = HostedInteractionService(
        require_session=lambda session_id: state,
        run_turn=lambda **kwargs: None,
        get_session_snapshot=lambda session_id: {"status": "running"},
        notify_status=lambda event_handler, current_state: None,
        default_event_handler=lambda: None,
    )

    assert service._claim_pending_interaction(state, ticket) is None
    with pytest.raises(ValueError, match="^interaction_conflict$"):
        service._claim_pending_interaction(state, ticket)
