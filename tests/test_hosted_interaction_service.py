from embedagent_host.hosted_interaction_service import (
    HostedPendingInteraction,
    _response_for_answer,
)


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
