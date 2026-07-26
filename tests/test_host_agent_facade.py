from __future__ import unicode_literals

import time
from pathlib import Path

from embedagent_core import AgentResult, AgentSession, InteractionReply, UserTurn
from embedagent_core.hosting import HostedSessionController
from embedagent_core.model import ModelClient
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.runner import SessionRecoveryRequired
from embedagent_core.session import Action, AssistantReply
from embedagent_host.inprocess_adapter import InProcessAdapter
from embedagent_host.runtime.tools import ToolRuntime

ROOT = Path(__file__).resolve().parents[1]


def _wait_for_session_settled(adapter, session_id, timeout=5.0):
    deadline = time.time() + timeout
    snapshot = adapter.get_session_snapshot(session_id)
    while time.time() < deadline:
        snapshot = adapter.get_session_snapshot(session_id)
        if snapshot.get("status") != "running":
            return snapshot
        time.sleep(0.02)
    return snapshot


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


class AskUserClient(DoneClient):
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
                        "ask_user",
                        {
                            "question": "Choose",
                            "option_1": "Continue",
                            "option_2": "Stop",
                        },
                        "ask-host-facade",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")


def _adapter(tmp_path):
    return InProcessAdapter(
        client=DoneClient(),
        tools=ToolRuntime(str(tmp_path)),
    )


def test_host_constructs_agent_facade_not_query_engine():
    text = (ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py").read_text(
        encoding="utf-8"
    )
    assert "Agent.create(" in text
    assert "QueryEngine" not in text
    assert "self.agent._runtime" not in text
    assert "agent_session._runtime" not in text
    assert "_host_last_result" not in text


def test_managed_session_uses_agent_session_handle():
    text = (
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/session_runtime.py"
    ).read_text(encoding="utf-8")
    assert "agent_session" in text
    assert "hosted_session" in text
    assert "engine: Any" not in text


def test_created_and_resumed_sessions_hold_agent_session_handles(tmp_path):
    adapter = _adapter(tmp_path)
    created = adapter.create_session("build")
    state = adapter._require_session(created["session_id"])

    assert isinstance(state.agent_session, AgentSession)
    assert state.agent_session.session_id == created["session_id"]
    assert isinstance(state.hosted_session, HostedSessionController)
    assert state.hosted_session.session_id == created["session_id"]

    resumed_adapter = _adapter(tmp_path)
    resumed_adapter.resume_session(created["session_id"], "build")
    resumed_state = resumed_adapter._require_session(created["session_id"])

    assert isinstance(resumed_state.agent_session, AgentSession)
    assert resumed_state.agent_session.session_id == created["session_id"]

    assert isinstance(resumed_state.hosted_session, HostedSessionController)
    assert resumed_state.hosted_session.session_id == created["session_id"]


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
    _wait_for_session_settled(adapter, session_id)

    assert snapshot.get("status") == "waiting_permission"
    assert len(captured) == 1
    assert isinstance(captured[0], InteractionReply)
    assert captured[0].interaction_id == interaction_id
    assert captured[0].value == {"approved": True}


def test_agent_result_exposes_generic_turn_completion_fields(tmp_path):
    adapter = _adapter(tmp_path)
    created = adapter.create_session("build")
    state = adapter._require_session(created["session_id"])

    result = state.agent_session.submit(UserTurn("hello", mode="build", stream=False))

    assert isinstance(result, AgentResult)
    assert result.termination_reason == "completed"
    assert result.outcome["kind"] == "completed"
    assert result.turns_used == 1
    assert result.termination_message == result.outcome["message"]


def test_sync_post_submit_restore_failure_sets_error_and_emits_session_error(tmp_path):
    adapter = _adapter(tmp_path)
    created = adapter.create_session("build")
    state = adapter._require_session(created["session_id"])
    events = []

    def fail_restore(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("post-submit restore failed")

    adapter.session_restorer.restore = fail_restore
    try:
        adapter.submit_user_message(
            created["session_id"],
            "hello",
            stream=False,
            wait=True,
            event_handler=lambda name, session_id, payload: events.append((name, payload)),
        )
    except RuntimeError as exc:
        assert str(exc) == "post-submit restore failed"
    else:
        raise AssertionError("synchronous restore failure must propagate")

    assert state.status == "error"
    assert state.active_thread is None
    assert state.last_error == "post-submit restore failed"
    assert [name for name, payload in events if name == "session_error"] == ["session_error"]


def test_worker_post_submit_restore_failure_clears_thread_and_reports_error(tmp_path):
    adapter = _adapter(tmp_path)
    created = adapter.create_session("build")
    state = adapter._require_session(created["session_id"])
    events = []

    def fail_restore(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("worker restore failed")

    adapter.session_restorer.restore = fail_restore
    adapter.submit_user_message(
        created["session_id"],
        "hello",
        stream=False,
        wait=False,
        event_handler=lambda name, session_id, payload: events.append((name, payload)),
    )
    deadline = time.time() + 3.0
    while time.time() < deadline and (
        state.status != "error" or not any(name == "session_error" for name, payload in events)
    ):
        time.sleep(0.02)

    assert state.status == "error"
    assert state.active_thread is None
    assert state.last_error == "worker restore failed"
    assert [name for name, payload in events if name == "session_error"] == ["session_error"]


def test_normal_turn_rebuilds_host_extension_projection(tmp_path):
    adapter = _adapter(tmp_path)
    created = adapter.create_session("build")
    state = adapter._require_session(created["session_id"])
    before = dict(state.session.workflow_state.get("extensions") or {})

    adapter.submit_user_message(created["session_id"], "hello", stream=False, wait=True)
    after = dict(state.session.workflow_state.get("extensions") or {})

    assert "project_extensions" in before
    assert "local_resources" in before
    assert after["project_extensions"] == before["project_extensions"]
    assert after["local_resources"] == before["local_resources"]


def test_resumed_turn_rebuilds_resource_projection_from_runtime_config(tmp_path):
    first_adapter = _adapter(tmp_path)
    created = first_adapter.create_session("build")
    session_id = created["session_id"]
    resumed_adapter = _adapter(tmp_path)
    resumed_adapter.resume_session(session_id, "build")
    state = resumed_adapter._require_session(session_id)
    before = dict(state.session.workflow_state.get("extensions") or {})

    resumed_adapter.submit_user_message(session_id, "hello", stream=False, wait=True)
    after = dict(state.session.workflow_state.get("extensions") or {})

    assert "local_resources" in before
    assert after["local_resources"] == before["local_resources"]


def test_interaction_resume_rebuilds_host_extension_projection(tmp_path):
    adapter = InProcessAdapter(
        client=PermissionClient(),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(auto_approve_all=False, workspace=str(tmp_path)),
    )
    created = adapter.create_session("build")
    session_id = created["session_id"]
    state = adapter._require_session(session_id)
    before = dict(state.session.workflow_state.get("extensions") or {})
    adapter.submit_user_message(session_id, "write", stream=False, wait=False)
    deadline = time.time() + 3.0
    snapshot = adapter.get_session_snapshot(session_id)
    while time.time() < deadline and snapshot.get("status") != "waiting_permission":
        time.sleep(0.02)
        snapshot = adapter.get_session_snapshot(session_id)
    interaction_id = (snapshot.get("pending_interaction") or {}).get("interaction_id")

    adapter.respond_to_interaction(session_id, interaction_id, {"decision": "accept"})
    _wait_for_session_settled(adapter, session_id)
    after = dict(state.session.workflow_state.get("extensions") or {})

    assert after["project_extensions"] == before["project_extensions"]
    assert after["local_resources"] == before["local_resources"]


def test_host_recovery_skips_only_previously_confirmed_bad_history(tmp_path):
    adapter = _adapter(tmp_path)
    session_id = "session-bounded-recovery"
    adapter.transcript_store.append_event(
        session_id,
        "session_meta",
        {"current_mode": "build"},
    )
    adapter.transcript_store.append_event(
        session_id,
        "message",
        {
            "role": "system",
            "content": "bad historical record",
            "message_id": "m-old-bad",
            "parent_message_id": "m-never-existed",
        },
    )
    adapter.resume_session(session_id, "build")

    adapter.submit_user_message(session_id, "first", stream=False, wait=True)
    adapter.submit_user_message(session_id, "second", stream=False, wait=True)
    state = adapter._require_session(session_id)
    trusted_history_count = state.best_effort_restore_event_count
    adapter.transcript_store.append_event(
        session_id,
        "message",
        {
            "role": "system",
            "content": "new corruption",
            "message_id": "m-new-bad",
            "parent_message_id": "m-still-missing",
        },
    )

    try:
        adapter.submit_user_message(session_id, "third", stream=False, wait=True)
    except SessionRecoveryRequired:
        pass
    else:
        raise AssertionError("new corruption after the trusted history must fail closed")

    assert trusted_history_count > 0
    assert state.best_effort_restore_event_count == trusted_history_count
    assert state.status == "error"


def test_resource_projection_uses_current_shared_catalog_without_cross_session_rollback(
    tmp_path,
):
    adapter = _adapter(tmp_path)
    first = adapter.create_session("build")["session_id"]
    skill_dir = tmp_path / ".embedagent" / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill = skill_dir / "one.md"
    skill.write_text("---\nname: one\ndescription: one\n---\nbody\n", encoding="utf-8")
    adapter.reload_resources(first, reason="first-catalog")
    second = adapter.create_session("build")["session_id"]
    skill.unlink()
    adapter.reload_resources(second, reason="second-catalog")
    adapter.resume_session(first, "build")

    adapter.submit_user_message(first, "first", stream=False, wait=True)
    adapter.submit_user_message(second, "second", stream=False, wait=True)
    first_state = adapter._require_session(first)
    second_state = adapter._require_session(second)
    first_resources = first_state.session.workflow_state["extensions"]["local_resources"]["state"]
    second_resources = second_state.session.workflow_state["extensions"]["local_resources"]["state"]
    actual = adapter.tools.local_resources()

    assert actual["counts"]["skills"] == 0
    assert first_resources["counts"] == actual["counts"]
    assert second_resources["counts"] == actual["counts"]


def test_permission_wait_emits_final_waiting_status(tmp_path):
    events = []
    adapter = InProcessAdapter(
        client=PermissionClient(),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(auto_approve_all=False, workspace=str(tmp_path)),
    )
    session_id = adapter.create_session("build")["session_id"]
    adapter.submit_user_message(
        session_id,
        "write",
        stream=False,
        wait=False,
        event_handler=lambda name, current_session_id, payload: events.append((name, payload)),
    )
    deadline = time.time() + 3.0
    while time.time() < deadline and not any(
        name == "session_status"
        and (payload.get("session_snapshot") or {}).get("status") == "waiting_permission"
        for name, payload in events
    ):
        time.sleep(0.02)

    statuses = [
        (payload.get("session_snapshot") or {}).get("status")
        for name, payload in events
        if name == "session_status"
    ]
    assert "waiting_permission" in statuses
    permission_events = [payload for name, payload in events if name == "permission_required"]
    assert len(permission_events) == 1
    assert "session_snapshot" not in permission_events[0]


def test_user_input_wait_emits_final_waiting_status(tmp_path):
    events = []
    adapter = InProcessAdapter(
        client=AskUserClient(),
        tools=ToolRuntime(str(tmp_path)),
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=str(tmp_path)),
    )
    session_id = adapter.create_session("spec")["session_id"]
    adapter.submit_user_message(
        session_id,
        "ask",
        stream=False,
        wait=False,
        event_handler=lambda name, current_session_id, payload: events.append((name, payload)),
    )
    deadline = time.time() + 3.0
    while time.time() < deadline and not any(
        name == "session_status"
        and (payload.get("session_snapshot") or {}).get("status") == "waiting_user_input"
        for name, payload in events
    ):
        time.sleep(0.02)

    statuses = [
        (payload.get("session_snapshot") or {}).get("status")
        for name, payload in events
        if name == "session_status"
    ]
    input_events = [payload for name, payload in events if name == "user_input_required"]
    assert "waiting_user_input" in statuses
    assert len(input_events) == 1
    assert "session_snapshot" not in input_events[0]
