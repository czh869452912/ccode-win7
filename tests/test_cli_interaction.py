from __future__ import annotations

from pathlib import Path

import pytest
from embedagent_protocol import InteractionDescriptor, ShellDescriptor


def _shell():
    return ShellDescriptor(
        interactions=[
            InteractionDescriptor(kind="permission", renderer_key="interaction"),
            InteractionDescriptor(kind="user_input", renderer_key="interaction"),
        ]
    )


def test_permission_interaction_resolves_safe_default_choices_and_payload():
    from embedagent.frontend.runtime.interaction_projection import (
        InteractionResponseError,
        build_interaction_response,
        resolve_interaction,
    )

    prompt = resolve_interaction(
        _shell(),
        "approval.requested",
        {
            "interaction_id": "approval-1",
            "reason": "Allow this operation?",
            "category": "custom_category",
            "tool_name": "dynamic_tool",
        },
    )

    assert prompt.descriptor.renderer_key == "interaction"
    assert prompt.interaction_id == "approval-1"
    assert prompt.prompt == "Allow this operation?"
    assert [choice.value for choice in prompt.choices] == [
        "accept",
        "acceptForSession",
        "decline",
        "cancel",
    ]
    assert build_interaction_response(prompt, "1") == {"decision": "accept"}
    assert build_interaction_response(prompt, "yes") == {"decision": "accept"}
    assert build_interaction_response(prompt, "") == {"decision": "decline"}
    with pytest.raises(InteractionResponseError):
        build_interaction_response(prompt, "unsupported")


def test_user_input_resolves_question_options_default_and_custom_answer():
    from embedagent.frontend.runtime.interaction_projection import (
        build_interaction_response,
        resolve_interaction,
    )

    prompt = resolve_interaction(
        _shell(),
        "user-input.requested",
        {
            "interaction_id": "input-1",
            "questions": [
                {
                    "id": "target_mode",
                    "question": "Choose a mode",
                    "default": "build",
                    "options": [
                        {"index": 1, "label": "Build", "value": "build"},
                        {"index": 2, "label": "Verify", "value": "verify"},
                    ],
                }
            ],
        },
    )

    assert prompt.prompt == "Choose a mode"
    assert prompt.answer_key == "target_mode"
    assert prompt.default == "build"
    assert [choice.label for choice in prompt.choices] == ["Build", "Verify"]
    assert build_interaction_response(prompt, "") == {"answers": {"target_mode": "build"}}
    assert build_interaction_response(prompt, "2") == {"answers": {"target_mode": "verify"}}
    assert build_interaction_response(prompt, "custom") == {"answers": {"target_mode": "custom"}}


def test_user_input_without_default_rejects_blank_answer():
    from embedagent.frontend.runtime.interaction_projection import (
        InteractionResponseError,
        build_interaction_response,
        resolve_interaction,
    )

    prompt = resolve_interaction(
        _shell(),
        "user-input.requested",
        {"interaction_id": "input-1", "question": "Answer required"},
    )

    with pytest.raises(InteractionResponseError):
        build_interaction_response(prompt, "")


def test_interaction_requires_registered_descriptor_and_stable_id():
    from embedagent.frontend.runtime.interaction_projection import (
        UnsupportedInteraction,
        resolve_interaction,
    )

    with pytest.raises(UnsupportedInteraction):
        resolve_interaction(
            ShellDescriptor(),
            "approval.requested",
            {"interaction_id": "approval-1"},
        )
    with pytest.raises(UnsupportedInteraction):
        resolve_interaction(_shell(), "custom.requested", {"interaction_id": "custom-1"})
    with pytest.raises(UnsupportedInteraction):
        resolve_interaction(
            ShellDescriptor(
                interactions=[InteractionDescriptor(kind="permission", renderer_key="custom_ui")]
            ),
            "approval.requested",
            {"interaction_id": "approval-1"},
        )
    with pytest.raises(ValueError, match="interaction_id"):
        resolve_interaction(_shell(), "approval.requested", {})


def test_cli_interaction_source_is_application_workflow_and_tool_neutral():
    source = (Path("src/embedagent/frontend/runtime/interaction_projection.py")).read_text(
        encoding="utf-8"
    )

    for forbidden in ("application_id", "workflow_type", "run_recipe", "write_file"):
        assert forbidden not in source
