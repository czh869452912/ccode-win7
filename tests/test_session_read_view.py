import json

import pytest
from embedagent_core.session import Action, AssistantReply, Observation, Session
from embedagent_core.session_view import SessionReadView, session_read_view


def _session_with_tool_result():
    session = Session(session_id="session-view")
    session.add_user_message("inspect", turn_id="turn-1")
    action = Action("read_file", {"path": "src/main.c"}, "call-1")
    session.add_assistant_reply(AssistantReply("", actions=[action], finish_reason="tool_calls"))
    session.add_observation(
        action,
        Observation("read_file", True, None, {"path": "src/main.c", "content": "old"}),
    )
    session.workflow_state = {"workflow": {"phase": "build"}}
    return session


def test_session_read_view_detaches_nested_state():
    session = _session_with_tool_result()

    view = session_read_view(session)
    session.messages[0].content = "changed"
    session.turns[0].observations[0].data["content"] = "changed"
    session.workflow_state["workflow"]["phase"] = "verify"

    assert isinstance(view, SessionReadView)
    assert view.messages[0]["content"] == "inspect"
    assert view.turns[0]["observations"][0]["data"]["content"] == "old"
    assert view.workflow_state["workflow"]["phase"] == "build"


def test_session_read_view_records_are_read_only_and_json_safe():
    view = session_read_view(_session_with_tool_result())

    json.dumps(
        {
            "messages": view.messages,
            "turns": view.turns,
            "workflow_state": view.workflow_state,
        }
    )
    with pytest.raises(TypeError):
        view.messages[0]["content"] = "changed"
    with pytest.raises(TypeError):
        view.turns[0]["observations"][0]["data"]["content"] = "changed"


def test_session_read_view_preserves_host_read_helpers_without_session_mutators():
    session = _session_with_tool_result()
    view = session_read_view(session)

    assert view.messages[-1].to_api_dict()["role"] == "tool"
    assert view.turns[0].actions[0].name == "read_file"
    assert view.turns[0].observations[0].to_dict()["success"] is True
    assert not hasattr(view, "add_user_message")
    assert not hasattr(view, "record_tool_call")
