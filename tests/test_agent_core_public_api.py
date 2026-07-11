from __future__ import unicode_literals

import concurrent.futures
import json
import threading
import time

import pytest

from embedagent_core.api import AgentPorts, InteractionReply, RuntimeDefinition, UserTurn
from embedagent_core.model import ModelClient
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.ports import NoopContextAssembler
from embedagent_core.query_engine import QueryEngine
from embedagent_core.runner import AgentRequest, AgentRuntime, run_agent
from embedagent_core.session import Action, AssistantReply, PendingInteraction
from embedagent_core.session_log import InMemorySessionLog
from embedagent_core.turn_snapshot import TurnSnapshot


class FakeModel(ModelClient):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tools=None):
        del messages, tools
        self.calls += 1
        return AssistantReply(content="done", actions=[], finish_reason="stop")

    def stream(
        self,
        messages,
        tools=None,
        on_text_delta=None,
        on_reasoning_delta=None,
    ):
        del messages, tools, on_reasoning_delta
        self.calls += 1
        reply = AssistantReply(content="done", actions=[], finish_reason="stop")
        if on_text_delta is not None:
            on_text_delta(reply.content)
        return reply


class BlockingModel(FakeModel):
    def __init__(self):
        super(BlockingModel, self).__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def generate(self, messages, tools=None):
        del messages, tools
        self.calls += 1
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError("blocking model was not released")
        return AssistantReply(content="done", actions=[], finish_reason="stop")


class NoopToolRuntime(object):
    workspace = ""

    def schemas_for(self, mode, workflow_state=None, tool_names=None):
        del mode, workflow_state, tool_names
        return []


class CountingExtension(object):
    def __init__(self):
        self.assembly_count = 0

    def extension_capabilities(self):
        self.assembly_count += 1
        return []


class ContextReducerRegistrarExtension(object):
    def __init__(self):
        self.calls = 0
        self._lock = threading.Lock()

    def extension_capabilities(self):
        from embedagent_core.extensions import ExtensionCapability

        return [
            ExtensionCapability(
                "register_context_reducers",
                self.register_context_reducers,
            )
        ]

    def register_context_reducers(self, registry):
        del registry
        with self._lock:
            self.calls += 1
            call_number = self.calls
        time.sleep(0.02)
        if call_number > 1:
            raise RuntimeError("context reducers registered more than once")


class BuildCountingAgentRuntime(AgentRuntime):
    def __init__(self, ports, definition):
        super(BuildCountingAgentRuntime, self).__init__(ports, definition)
        self.build_count = 0

    def build_engine(self):
        self.build_count += 1
        return super(BuildCountingAgentRuntime, self).build_engine()


class RecordingObserver(object):
    def __init__(self):
        self.events = []

    def on_event(self, event_type, payload):
        json.dumps(payload)
        self.events.append((event_type, dict(payload)))
        payload["observer_mutation"] = {"values": ["changed"]}
        if event_type == "step.finished":
            payload["content"] = "changed"


@pytest.fixture
def base_ports():
    session_log = InMemorySessionLog()
    return AgentPorts(
        model=FakeModel(),
        tools=NoopToolRuntime(),
        session_log=session_log,
        context=NoopContextAssembler(),
        permissions=PermissionPolicy(),
    )


@pytest.fixture
def base_runtime(base_ports):
    return AgentRuntime(base_ports, RuntimeDefinition()), base_ports.session_log


def test_standalone_agent_core_public_symbols_are_available():
    from embedagent_core import (
        Agent,
        AgentObserver,
        AgentPorts,
        AgentResult,
        AgentSession,
        AgentSessionView,
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
        AgentSessionView,
        CancelToken,
        InteractionReply,
        RuntimeDefinition,
        UserTurn,
    )

    assert all(symbol is not None for symbol in public_symbols)


def test_agent_facade_submits_and_restores_multiple_turns(base_ports):
    from embedagent_core import Agent

    session = Agent.create(base_ports).open("session-1")

    first = session.submit(UserTurn("hello", stream=False))
    second = session.submit(UserTurn("continue", stream=False))

    assert first.final_text == "done"
    assert first.termination_reason == "completed"
    assert second.session.message_count > first.session.message_count
    assert second.session.turn_count > first.session.turn_count


def test_agent_open_generates_distinct_session_ids_without_touching_log(base_ports):
    from embedagent_core import Agent

    agent = Agent.create(base_ports)

    first = agent.open()
    second = agent.open(" \t ")

    assert first.session_id.startswith("s-")
    assert second.session_id.startswith("s-")
    assert first.session_id != second.session_id
    assert not base_ports.session_log.transcript_exists(first.session_id)
    assert not base_ports.session_log.transcript_exists(second.session_id)


def test_agent_open_generates_full_uuid4_session_id(base_ports):
    from embedagent_core import Agent

    session = Agent.create(base_ports).open()

    assert len(session.session_id) == 34
    assert session.session_id.startswith("s-")
    assert all(character in "0123456789abcdef" for character in session.session_id[2:])


def test_agent_open_trims_explicit_session_id(base_ports):
    from embedagent_core import Agent

    session = Agent.create(base_ports).open("  Session-One  ")

    assert session.session_id == "Session-One"


def test_agent_open_rejects_non_string_session_id(base_ports):
    from embedagent_core import Agent

    with pytest.raises(TypeError, match="^session id must be a string$"):
        Agent.create(base_ports).open(123)


@pytest.mark.parametrize(
    "session_id", ("../escape", "session.jsonl", "CON", "sess\N{LATIN SMALL LETTER E WITH ACUTE}")
)
def test_agent_open_rejects_unsafe_session_id(base_ports, session_id):
    from embedagent_core import Agent

    with pytest.raises(ValueError, match="^session_id is invalid$"):
        Agent.create(base_ports).open(session_id)


def test_agent_session_constructor_validates_and_exposes_read_only_session_id(base_ports):
    from embedagent_core import Agent, AgentSession

    runtime = Agent.create(base_ports)._runtime
    with pytest.raises(ValueError, match="^session_id is invalid$"):
        AgentSession(runtime, "../escape")

    session = AgentSession(runtime, " session-one ")
    assert session.session_id == "session-one"
    with pytest.raises(AttributeError):
        session.session_id = "changed"


def test_agent_create_rejects_invalid_binding_types(base_ports):
    from embedagent_core import Agent

    with pytest.raises(TypeError, match="^ports must be AgentPorts$"):
        Agent.create(object())
    with pytest.raises(TypeError, match="^definition must be RuntimeDefinition$"):
        Agent.create(base_ports, object())


@pytest.mark.parametrize(
    "missing_port", ("model", "tools", "session_log", "context", "permissions")
)
def test_agent_create_rejects_missing_required_port(base_ports, missing_port):
    from embedagent_core import Agent

    values = {
        "model": base_ports.model,
        "tools": base_ports.tools,
        "session_log": base_ports.session_log,
        "context": base_ports.context,
        "permissions": base_ports.permissions,
    }
    values[missing_port] = None
    ports = AgentPorts(**values)

    with pytest.raises(
        ValueError,
        match="^agent port %s is required$" % missing_port,
    ):
        Agent.create(ports)


def test_agent_session_rejects_overlapping_local_submit_and_recovers():
    from embedagent_core import Agent
    from embedagent_core.session_log import SessionLeaseConflict

    model = BlockingModel()
    ports = AgentPorts(
        model=model,
        tools=NoopToolRuntime(),
        session_log=InMemorySessionLog(),
        context=NoopContextAssembler(),
        permissions=PermissionPolicy(),
    )
    session = Agent.create(ports).open("session-local-lock")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        first_result = executor.submit(
            session.submit,
            UserTurn("first", stream=False),
        )
        try:
            assert model.entered.wait(2)
            with pytest.raises(
                SessionLeaseConflict,
                match="^agent session already has an active submit$",
            ):
                session.submit(UserTurn("second", stream=False))
        finally:
            model.release.set()
        first = first_result.result(timeout=5)

    third = session.submit(UserTurn("third", stream=False))

    assert first.final_text == "done"
    assert third.final_text == "done"
    assert third.session.turn_count > first.session.turn_count


def test_agent_sessions_share_one_bound_runtime_and_extension_manager(base_ports):
    from embedagent_core import Agent

    agent = Agent.create(base_ports)
    first = agent.open("session-a")
    second = agent.open("session-b")

    assert first._runtime is agent._runtime
    assert second._runtime is agent._runtime
    assert first._runtime.extension_manager is second._runtime.extension_manager
    assert first.submit(UserTurn("first", stream=False)).final_text == "done"
    assert second.submit(UserTurn("second", stream=False)).final_text == "done"


def test_agent_session_log_lease_rejects_same_session_across_handles():
    from embedagent_core import Agent
    from embedagent_core.session_log import SessionLeaseConflict

    model = BlockingModel()
    session_log = InMemorySessionLog()
    ports = AgentPorts(
        model=model,
        tools=NoopToolRuntime(),
        session_log=session_log,
        context=NoopContextAssembler(),
        permissions=PermissionPolicy(),
    )
    agent = Agent.create(ports)
    first = agent.open("shared-session")
    second = agent.open(" shared-session ")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        first_result = executor.submit(
            first.submit,
            UserTurn("first", stream=False),
        )
        assert model.entered.wait(2)
        try:
            with pytest.raises(SessionLeaseConflict):
                second.submit(UserTurn("second", stream=False))
        finally:
            model.release.set()
        result = first_result.result(timeout=5)

    events = session_log.load_events("shared-session")
    message_contents = [
        event["payload"].get("content") for event in events if "content" in event["payload"]
    ]
    assert result.final_text == "done"
    assert "first" in message_contents
    assert "second" not in message_contents
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))


def test_agent_session_facade_preserves_runner_input_validation(base_ports):
    from embedagent_core import Agent

    with pytest.raises(TypeError, match="^unsupported agent input$"):
        Agent.create(base_ports).open("session-1").submit(object())


def test_agent_facade_keeps_runner_internals_out_of_package_root():
    import embedagent_core

    assert not hasattr(embedagent_core, "AgentRuntime")
    assert not hasattr(embedagent_core, "AgentRequest")
    assert not hasattr(embedagent_core, "run_agent")


def test_user_turn_rejects_empty_text():
    from embedagent_core import UserTurn

    with pytest.raises(ValueError, match="^user turn text is required$"):
        UserTurn("")


def test_user_turn_rejects_non_string_text():
    from embedagent_core import UserTurn

    with pytest.raises(TypeError, match="^user turn text must be a string$"):
        UserTurn(123)


def test_interaction_reply_rejects_empty_interaction_id():
    from embedagent_core import InteractionReply

    with pytest.raises(ValueError, match="^interaction id is required$"):
        InteractionReply("", {})


def test_interaction_reply_rejects_non_string_interaction_id():
    from embedagent_core import InteractionReply

    with pytest.raises(TypeError, match="^interaction id must be a string$"):
        InteractionReply(123, {})


def test_interaction_reply_rejects_non_dict_value():
    from embedagent_core import InteractionReply

    with pytest.raises(TypeError, match="^interaction reply value must be a dict or None$"):
        InteractionReply("interaction-1", [])


def test_interaction_reply_copies_nested_value():
    from embedagent_core import InteractionReply

    value = {"answer": {"choices": ["build"]}}
    reply = InteractionReply("interaction-1", value)

    value["answer"]["choices"].append("verify")

    assert reply.value == {"answer": {"choices": ["build"]}}


def test_runtime_definition_uses_neutral_defaults():
    from embedagent_core import RuntimeDefinition

    definition = RuntimeDefinition()

    assert definition.agent_id == "embedagent.base"
    assert definition.default_mode == ""
    assert definition.workflow_state == ""
    assert definition.extensions == ()


def test_runtime_definition_policy_defaults_are_isolated():
    from embedagent_core import RuntimeDefinition

    first = RuntimeDefinition()
    second = RuntimeDefinition()

    assert first.mode_tool_policy is not second.mode_tool_policy
    assert first.write_path_policy is not second.write_path_policy
    assert first.mode_runtime_policy is not second.mode_runtime_policy


def test_neutral_mode_runtime_policy_is_fail_neutral():
    from embedagent_core.policies import NeutralModeRuntimePolicy

    policy = NeutralModeRuntimePolicy()

    assert policy.default_mode() == ""
    assert policy.require_mode("") == {"slug": ""}
    assert policy.build_system_prompt("build", workspace="C:/workspace") == ""
    assert policy.parse_mode_switch_request("keep working", "spec") == (
        "spec",
        "keep working",
        False,
    )


def test_agent_session_view_copies_nested_workflow_state():
    from embedagent_core import AgentSessionView

    workflow_state = {"workflow": {"tasks": [{"id": "task-1"}]}}
    view = AgentSessionView("session-1", "build", workflow_state, 2, 1)

    workflow_state["workflow"]["tasks"][0]["id"] = "changed"

    assert view.workflow_state["workflow"]["tasks"][0]["id"] == "task-1"


def test_agent_result_copies_pending_interaction_and_turn_snapshot():
    from embedagent_core import AgentResult, AgentSessionView

    pending = PendingInteraction(
        interaction_id="interaction-1",
        request_payload={"choices": [{"id": "approve"}]},
    )
    snapshot = TurnSnapshot(
        snapshot_id="snapshot-1",
        session_id="session-1",
        turn_id="turn-1",
        step_id="step-1",
        mode_name="build",
        workflow_state="active",
        messages=[{"role": "user", "content": {"text": "original"}}],
    )
    result = AgentResult(
        "done",
        AgentSessionView("session-1", "build", {}, 2, 1),
        "completed",
        pending,
        snapshot,
    )

    pending.request_payload["choices"][0]["id"] = "changed"
    snapshot.messages[0]["content"]["text"] = "changed"

    assert result.pending_interaction is not None
    assert result.pending_interaction.request_payload["choices"][0]["id"] == "approve"
    assert result.turn_snapshot.messages[0]["content"]["text"] == "original"


def test_agent_result_copies_session_view():
    from embedagent_core import AgentResult, AgentSessionView

    session = AgentSessionView(
        "session-1",
        "build",
        {"workflow": {"phase": "implement"}},
        2,
        1,
    )
    result = AgentResult("done", session, "completed", None, None)

    session.workflow_state["workflow"]["phase"] = "changed"

    assert result.session.workflow_state["workflow"]["phase"] == "implement"


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


def test_run_agent_executes_user_turn_with_neutral_runtime(base_runtime):
    runtime, session_log = base_runtime

    result = run_agent(
        runtime,
        AgentRequest("session-1", UserTurn("hello", stream=False)),
    )

    assert result.session.session_id == "session-1"
    assert result.session.current_mode == ""
    assert result.final_text == "done"
    assert result.termination_reason == "completed"
    assert session_log.transcript_exists("session-1")


def test_run_agent_restores_and_appends_multiple_turns(base_runtime):
    runtime, session_log = base_runtime
    first = run_agent(
        runtime,
        AgentRequest("session-1", UserTurn("first", stream=False)),
    )
    first_event_count = len(session_log.load_events("session-1"))

    second = run_agent(
        runtime,
        AgentRequest("session-1", UserTurn("second", stream=False)),
    )

    assert second.session.message_count > first.session.message_count
    assert second.session.turn_count > first.session.turn_count
    assert len(session_log.load_events("session-1")) > first_event_count


def test_run_agent_rejects_incomplete_trusted_prefix_before_engine_build(base_runtime):
    from embedagent_core.runner import SessionRecoveryRequired

    runtime, session_log = base_runtime
    guarded_runtime = BuildCountingAgentRuntime(runtime.ports, runtime.definition)
    session_id = "session-invalid"
    session_log.append_event(session_id, "session_meta", {"current_mode": ""})
    session_log.append_event(
        session_id,
        "message",
        {
            "role": "user",
            "content": "first",
            "message_id": "message-1",
            "turn_id": "turn-duplicate",
            "step_id": "",
        },
    )
    session_log.append_event(
        session_id,
        "message",
        {
            "role": "user",
            "content": "duplicate",
            "message_id": "message-2",
            "turn_id": "turn-duplicate",
            "step_id": "",
        },
    )
    event_count = len(session_log.load_events(session_id))

    with pytest.raises(SessionRecoveryRequired) as captured:
        run_agent(
            guarded_runtime,
            AgentRequest(session_id, UserTurn("continue", stream=False)),
        )

    assert captured.value.session_id == session_id
    assert captured.value.stop_reason == "duplicate_turn_id"
    assert session_id in str(captured.value)
    assert "duplicate_turn_id" in str(captured.value)
    assert len(session_log.load_events(session_id)) == event_count
    assert runtime.ports.model.calls == 0
    assert guarded_runtime.build_count == 0


def test_run_agent_rejects_mismatched_interaction_without_appending(base_runtime):
    runtime, session_log = base_runtime
    session_id = "session-pending"
    session_log.append_event(session_id, "session_meta", {"current_mode": ""})
    session_log.append_event(
        session_id,
        "message",
        {
            "role": "user",
            "content": "continue",
            "message_id": "message-1",
            "turn_id": "turn-1",
            "step_id": "",
        },
    )
    session_log.append_event(
        session_id,
        "step_started",
        {"turn_id": "turn-1", "step_id": "step-1", "step_index": 1},
    )
    session_log.append_event(
        session_id,
        "pending_interaction",
        {
            "turn_id": "turn-1",
            "step_id": "step-1",
            "kind": "user_input",
            "tool_name": "ask_user",
            "interaction_id": "interaction-1",
            "request_payload": {"question": "continue?"},
        },
    )
    session_log.append_event(
        session_id,
        "loop_transition",
        {
            "turn_id": "turn-1",
            "step_id": "step-1",
            "reason": "user_input_wait",
            "message": "continue?",
            "next_mode": "",
            "turns_used": 1,
            "metadata": {},
        },
    )
    event_count = len(session_log.load_events(session_id))

    with pytest.raises(ValueError, match="^interaction id does not match$"):
        run_agent(
            runtime,
            AgentRequest(session_id, InteractionReply("wrong", {})),
        )

    assert len(session_log.load_events(session_id)) == event_count


def test_run_agent_rejects_unsupported_input(base_runtime):
    runtime, _session_log = base_runtime

    with pytest.raises(TypeError, match="^unsupported agent input$"):
        run_agent(runtime, AgentRequest("session-1", object()))


def test_agent_runtime_reuses_extension_manager_and_assembles_extensions_once():
    extension = CountingExtension()
    ports = AgentPorts(
        model=FakeModel(),
        tools=NoopToolRuntime(),
        session_log=InMemorySessionLog(),
        context=NoopContextAssembler(),
        permissions=PermissionPolicy(),
    )
    runtime = AgentRuntime(
        ports,
        RuntimeDefinition(extensions=(extension,)),
    )

    first = runtime.build_engine()
    second = runtime.build_engine()

    assert first is not second
    assert first.extension_manager is second.extension_manager
    assert extension.assembly_count == 1


def test_agent_runtime_registers_context_reducers_once_across_concurrent_builds():
    extension = ContextReducerRegistrarExtension()
    ports = AgentPorts(
        model=FakeModel(),
        tools=NoopToolRuntime(),
        session_log=InMemorySessionLog(),
        context=NoopContextAssembler(),
        permissions=PermissionPolicy(),
    )
    runtime = AgentRuntime(
        ports,
        RuntimeDefinition(extensions=(extension,)),
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        engines = list(executor.map(lambda _index: runtime.build_engine(), range(2)))

    assert len(engines) == 2
    assert extension.calls == 1


def test_run_agent_observer_receives_detached_json_safe_events(base_runtime):
    runtime, _session_log = base_runtime
    observer = RecordingObserver()

    result = run_agent(
        runtime,
        AgentRequest("session-observer", UserTurn("hello", stream=True)),
        observer=observer,
    )

    event_types = [event_type for event_type, _payload in observer.events]
    assert "text.delta" in event_types
    assert "step.started" in event_types
    assert "step.finished" in event_types
    assert result.final_text == "done"
    assert result.session.message_count > 0
