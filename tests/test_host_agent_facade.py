from __future__ import unicode_literals

import time
from pathlib import Path

from embedagent.tools import ToolRuntime
from embedagent_core import AgentSession, InteractionReply, UserTurn
from embedagent_core.model import ModelClient
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.session import Action, AssistantReply
from embedagent_host.inprocess_adapter import InProcessAdapter

ROOT = Path(__file__).resolve().parents[1]


class DoneClient(ModelClient):
    def generate(self, messages, tools=None):
        del messages, tools
        return AssistantReply(content="done", actions=[], finish_reason="stop")


class PermissionClient(DoneClient):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        del messages, tools
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        "write_file",
                        {"path": "generated.c", "content": "int value;\n", "overwrite": True},
                        "write-host-facade",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(
        self,
        messages,
        tools=None,
        on_text_delta=None,
        on_reasoning_delta=None,
    ):
        del messages, tools, on_reasoning_delta
        if on_text_delta is not None:
            on_text_delta("done")
        return AssistantReply(content="done", actions=[], finish_reason="stop")


def _adapter(tmp_path):
    return InProcessAdapter(
        client=DoneClient(),
        tools=ToolRuntime(str(tmp_path)),
    )


def test_host_constructs_agent_facade_not_query_engine():
    text = (ROOT / "src/embedagent_host/inprocess_adapter.py").read_text(encoding="utf-8")
    assert "Agent.create(" in text
    assert "QueryEngine" not in text
    assert "self.agent._runtime" not in text
    assert "agent_session._runtime" not in text


def test_managed_session_uses_agent_session_handle():
    text = (ROOT / "src/embedagent/session_runtime.py").read_text(encoding="utf-8")
    assert "agent_session" in text
    assert "engine: Any" not in text


def test_created_and_resumed_sessions_hold_agent_session_handles(tmp_path):
    adapter = _adapter(tmp_path)
    created = adapter.create_session("build")
    state = adapter._require_session(created["session_id"])

    assert isinstance(state.agent_session, AgentSession)
    assert state.agent_session.session_id == created["session_id"]

    resumed_adapter = _adapter(tmp_path)
    resumed_adapter.resume_session(created["session_id"], "build")
    resumed_state = resumed_adapter._require_session(created["session_id"])

    assert isinstance(resumed_state.agent_session, AgentSession)
    assert resumed_state.agent_session.session_id == created["session_id"]


def test_all_host_session_handles_share_one_runtime_and_extension_manager(tmp_path):
    adapter = _adapter(tmp_path)
    first = adapter.create_session("build")
    second = adapter.create_session("build")
    first_handle = adapter._require_session(first["session_id"]).agent_session
    second_handle = adapter._require_session(second["session_id"]).agent_session

    assert first_handle._runtime is second_handle._runtime
    assert first_handle._runtime.extension_manager is adapter.extension_manager


def test_host_runtime_lease_nesting_tracks_each_session_independently(tmp_path):
    adapter = _adapter(tmp_path)
    first = adapter.create_session("build")["session_id"]
    second = adapter.create_session("build")["session_id"]
    runtime = adapter.agent._runtime

    with runtime._host_lease(first):
        with runtime._host_lease(second):
            with runtime._host_lease(first):
                pass

    with adapter.transcript_store.acquire_lease(first):
        with adapter.transcript_store.acquire_lease(second):
            pass


def test_normal_host_turn_submits_user_turn_through_agent_session(tmp_path):
    adapter = _adapter(tmp_path)
    created = adapter.create_session("build")
    state = adapter._require_session(created["session_id"])
    captured = []
    original_submit = state.agent_session.submit

    def recording_submit(input_value, observer=None, cancel=None):
        captured.append(input_value)
        return original_submit(input_value, observer=observer, cancel=cancel)

    state.agent_session.submit = recording_submit
    adapter.submit_user_message(created["session_id"], "hello", stream=False, wait=True)

    assert len(captured) == 1
    assert isinstance(captured[0], UserTurn)
    assert captured[0].text == "hello"
    assert captured[0].mode == "build"
    assert captured[0].stream is False


def test_pending_host_interaction_submits_interaction_reply(tmp_path):
    adapter = InProcessAdapter(
        client=PermissionClient(),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(
            auto_approve_all=False,
            workspace=str(tmp_path),
        ),
    )
    created = adapter.create_session("build")
    session_id = created["session_id"]
    adapter.submit_user_message(session_id, "write", stream=False, wait=False)
    deadline = time.time() + 3.0
    snapshot = adapter.get_session_snapshot(session_id)
    while time.time() < deadline and snapshot.get("status") != "waiting_permission":
        time.sleep(0.02)
        snapshot = adapter.get_session_snapshot(session_id)
    interaction_id = (snapshot.get("pending_interaction") or {}).get("interaction_id")
    state = adapter._require_session(session_id)
    captured = []
    original_submit = state.agent_session.submit

    def recording_submit(input_value, observer=None, cancel=None):
        captured.append(input_value)
        return original_submit(input_value, observer=observer, cancel=cancel)

    state.agent_session.submit = recording_submit
    adapter.respond_to_interaction(session_id, interaction_id, {"decision": "accept"})

    assert snapshot.get("status") == "waiting_permission"
    assert len(captured) == 1
    assert isinstance(captured[0], InteractionReply)
    assert captured[0].interaction_id == interaction_id
    assert captured[0].value == {"approved": True}
