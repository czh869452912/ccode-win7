from embedagent_core.session import Action, AssistantReply, Observation, Session
from embedagent_core.session_view import session_read_view
from embedagent_host.runtime.workspace_intelligence import WorkingSetProvider


def test_working_set_provider_reads_detached_session_view():
    session = Session(session_id="workspace-intelligence")
    session.add_user_message("edit")
    action = Action("edit_file", {"path": "src/main.c"}, "call-edit")
    session.add_assistant_reply(AssistantReply("", actions=[action], finish_reason="tool_calls"))
    session.add_observation(
        action,
        Observation("edit_file", True, None, {"path": "src/main.c"}),
    )

    evidence = WorkingSetProvider().collect(
        session_read_view(session),
        "build",
        tools=None,
    )

    assert len(evidence) == 1
    assert evidence[0].metadata["paths"] == ["src/main.c"]
