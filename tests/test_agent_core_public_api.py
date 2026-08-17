from __future__ import unicode_literals

import concurrent.futures
import dataclasses
import json
import threading
import time

import pytest
from embedagent_core.api import AgentPorts, InteractionReply, RuntimeDefinition, UserTurn
from embedagent_core.interaction import UserInputResponse
from embedagent_core.model import ModelClient, ModelClientError
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.ports import NoopContextAssembler
from embedagent_core.runner import AgentRequest, AgentRuntime, run_agent
from embedagent_core.session import Action, AssistantReply, Observation
from embedagent_core.session_log import InMemorySessionLog
from embedagent_core.tool_contracts import PreparedToolObservation
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

    def tool_catalog_entry(self, tool_name):
        if tool_name != "ask_user":
            return None
        return {
            "permission_category": "read",
            "read_only": True,
            "concurrency_safe": True,
            "user_label": "Ask User",
            "progress_renderer_key": "interaction",
            "result_renderer_key": "interaction",
            "source_type": "builtin",
            "source_id": "embedagent.core",
        }

    def materialize_observation(self, session_id, action, observation):
        del session_id, action
        return PreparedToolObservation(observation=observation)

    def finalize_observation(self, commit_token):
        del commit_token

    def execute_with_interrupt(self, tool_name, arguments, stop_event):
        del arguments, stop_event
        return Observation(
            tool_name,
            False,
            "command failed",
            {
                "error_kind": "command_failed",
                "retryable": False,
                "outcome_class": "diagnostic_failure",
            },
        )


class AskThenDoneModel(FakeModel):
    def generate(self, messages, tools=None):
        del messages, tools
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        "ask_user",
                        {"question": "Continue?", "option_1": "Yes"},
                        "ask-1",
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="done", actions=[], finish_reason="stop")


class AlwaysAskModel(FakeModel):
    def generate(self, messages, tools=None):
        del messages, tools
        self.calls += 1
        return AssistantReply(
            content="",
            actions=[Action("ask_user", {"question": "Continue?"}, "ask-%d" % self.calls)],
            finish_reason="tool_calls",
        )


class FailedToolThenDoneModel(FakeModel):
    def generate(self, messages, tools=None):
        del messages, tools
        self.calls += 1
        if self.calls == 1:
            return AssistantReply(
                content="",
                actions=[Action("missing_tool", {}, "missing-1")],
                finish_reason="tool_calls",
            )
        return AssistantReply(content="recovered", actions=[], finish_reason="stop")


class CompactRetryModel(FakeModel):
    def generate(self, messages, tools=None):
        del messages, tools
        self.calls += 1
        if self.calls == 1:
            raise ModelClientError("context length exceeded")
        return AssistantReply(content="compacted", actions=[], finish_reason="stop")


class SetCancelToken(object):
    def is_set(self):
        return True


class AutoInputObserver(object):
    def on_event(self, event_type, payload):
        del event_type, payload

    def on_user_input_request(self, request):
        del request
        return UserInputResponse(answer="yes")


class CountingExtension(object):
    def __init__(self):
        self.assembly_count = 0

    def extension_capabilities(self):
        self.assembly_count += 1
        return []


class AllowMissingToolPolicy(object):
    def allowed_tools_for(self, mode_name, workflow_state=None):
        del mode_name, workflow_state
        return {"missing_tool"}


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


class RecordingContext(NoopContextAssembler):
    def __init__(self):
        self.workflow_states = []
        self.session_types = []

    def build_messages(
        self,
        session,
        mode_name,
        tools=None,
        workflow_state="",
        force_compact=False,
    ):
        self.workflow_states.append(workflow_state)
        self.session_types.append(type(session))
        return super(RecordingContext, self).build_messages(
            session,
            mode_name,
            tools=tools,
            workflow_state=workflow_state,
            force_compact=force_compact,
        )


class RecordingRestorePolicy(object):
    def __init__(self):
        self.session_ids = []

    def trusted_event_count(self, session_id):
        self.session_ids.append(session_id)
        return 0


class RecordingSessionProjection(object):
    def __init__(self):
        self.calls = []

    def refresh(self, session, current_mode, assembly=None):
        self.calls.append((session, current_mode, assembly))


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
        AgentInteractionRequest,
        AgentModeDescriptor,
        AgentObserver,
        AgentPorts,
        AgentProfile,
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
        AgentInteractionRequest,
        AgentModeDescriptor,
        AgentObserver,
        AgentPorts,
        AgentProfile,
        AgentResult,
        AgentSession,
        AgentSessionView,
        CancelToken,
        InteractionReply,
        RuntimeDefinition,
        UserTurn,
    )

    assert all(symbol is not None for symbol in public_symbols)


def test_standalone_construction_contracts_are_available_from_core_root():
    from embedagent_core import (
        Action,
        AssistantReply,
        ContextAssemblerPort,
        InMemorySessionLog,
        ModelClient,
        ModelClientError,
        NoopContextAssembler,
        NoopSessionProjection,
        Observation,
        PermissionPolicy,
        PreparedToolObservation,
        SessionLeaseConflict,
        SessionLogPort,
        SessionProjectionPort,
        SessionRecoveryRequired,
        SessionRestorePolicyPort,
        StrictSessionRestorePolicy,
        ToolError,
        ToolRuntimePort,
    )

    public_symbols = (
        Action,
        AssistantReply,
        ContextAssemblerPort,
        InMemorySessionLog,
        ModelClient,
        ModelClientError,
        NoopContextAssembler,
        NoopSessionProjection,
        Observation,
        PermissionPolicy,
        PreparedToolObservation,
        SessionLeaseConflict,
        SessionLogPort,
        SessionProjectionPort,
        SessionRecoveryRequired,
        SessionRestorePolicyPort,
        StrictSessionRestorePolicy,
        ToolError,
        ToolRuntimePort,
    )

    assert all(symbol is not None for symbol in public_symbols)


def test_hosting_controller_is_not_exported_from_core_root():
    import embedagent_core

    assert not hasattr(embedagent_core, "HostedSessionController")


def test_agent_facade_submits_and_restores_multiple_turns(base_ports):
    from embedagent_core import Agent

    session = Agent.create(base_ports).open("session-1")

    first = session.submit(UserTurn("hello", stream=False))
    second = session.submit(UserTurn("continue", stream=False))

    assert first.final_text == "done"
    assert first.termination_reason == "completed"
    assert second.session.message_count > first.session.message_count
    assert second.session.turn_count > first.session.turn_count


def test_agent_session_resumes_interaction_through_public_api(base_ports):
    from embedagent_core import Agent

    model = AskThenDoneModel()
    ports = dataclasses.replace(base_ports, model=model)
    session = Agent.create(ports).open("session-resume")

    waiting = session.submit(UserTurn("ask", stream=False))
    assert waiting.termination_reason == "user_input_wait"
    assert waiting.pending_interaction is not None
    from embedagent_core import AgentInteractionRequest

    assert isinstance(waiting.pending_interaction, AgentInteractionRequest)

    resumed = session.submit(
        InteractionReply(
            waiting.pending_interaction.interaction_id,
            {"answer": "yes"},
            stream=False,
        )
    )

    assert resumed.final_text == "done"
    assert resumed.termination_reason == "completed"
    assert model.calls == 2


def test_agent_session_honors_pre_cancel_without_provider_call(base_ports):
    from embedagent_core import Agent

    model = FakeModel()
    ports = dataclasses.replace(base_ports, model=model)

    result = (
        Agent.create(ports)
        .open("session-cancel")
        .submit(
            UserTurn("stop", stream=False),
            cancel=SetCancelToken(),
        )
    )

    assert result.termination_reason == "aborted"
    assert model.calls == 0


def test_agent_session_applies_explicit_turn_fuse_after_tool_result(base_ports):
    from embedagent_core import Agent

    model = AlwaysAskModel()
    ports = dataclasses.replace(base_ports, model=model)
    agent = Agent.create(ports, RuntimeDefinition(max_turns=1))

    result = agent.open("session-fuse").submit(
        UserTurn("loop", stream=False),
        observer=AutoInputObserver(),
    )

    assert result.termination_reason == "max_turns"
    assert result.turns_used == 1
    assert model.calls == 1


def test_agent_session_compacts_and_retries_context_limit(base_ports):
    from embedagent_core import Agent

    model = CompactRetryModel()
    ports = dataclasses.replace(base_ports, model=model)

    result = Agent.create(ports).open("session-compact").submit(UserTurn("retry", stream=False))

    assert result.final_text == "compacted"
    assert result.termination_reason == "completed"
    assert model.calls == 2
    transitions = [
        event["payload"].get("reason")
        for event in ports.session_log.load_events("session-compact")
        if event["type"] == "loop_transition"
    ]
    assert "compact_retry" in transitions


def test_agent_session_keeps_tool_failure_model_visible(base_ports):
    from embedagent_core import Agent

    model = FailedToolThenDoneModel()
    ports = dataclasses.replace(
        base_ports,
        model=model,
        permissions=PermissionPolicy(auto_approve_all=True),
    )
    from embedagent_core import ApplicationRuntimePolicy

    definition = RuntimeDefinition(
        application_policy=ApplicationRuntimePolicy(
            mode_tool_policy=AllowMissingToolPolicy(),
        ),
    )

    result = (
        Agent.create(ports, definition)
        .open("session-tool-failure")
        .submit(UserTurn("use missing", stream=False))
    )

    assert result.final_text == "recovered"
    assert result.termination_reason == "completed"
    assert model.calls == 2
    tool_results = [
        event["payload"]
        for event in ports.session_log.load_events("session-tool-failure")
        if event["type"] == "tool_result"
    ]
    assert tool_results
    assert tool_results[0]["observation"]["success"] is False


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

    assert session.session_id == "session-one"


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

    invalid_manager = AgentPorts(
        model=base_ports.model,
        tools=base_ports.tools,
        session_log=base_ports.session_log,
        context=base_ports.context,
        permissions=base_ports.permissions,
        extension_manager=object(),
    )
    with pytest.raises(TypeError, match="^extension manager must be ExtensionManager$"):
        Agent.create(invalid_manager)


def test_agent_create_rejects_two_extension_assembly_sources(base_ports):
    from embedagent_core import Agent
    from embedagent_core.extensions import ExtensionManager

    manager = ExtensionManager()
    ports = AgentPorts(
        model=base_ports.model,
        tools=base_ports.tools,
        session_log=base_ports.session_log,
        context=base_ports.context,
        permissions=base_ports.permissions,
        extension_manager=manager,
    )

    with pytest.raises(
        ValueError,
        match="^extension_manager and RuntimeDefinition.extensions are mutually exclusive$",
    ):
        Agent.create(ports, RuntimeDefinition(extensions=(object(),)))


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
    assert not hasattr(definition, "default_mode")
    assert not hasattr(definition, "mode_tool_policy")
    assert not hasattr(definition, "mode_runtime_policy")
    assert not hasattr(definition, "write_path_policy")
    assert definition.workflow_state == ""
    assert definition.extensions == ()


def test_user_turn_carries_explicit_workflow_state(base_ports):
    from embedagent_core import Agent

    context = RecordingContext()
    ports = dataclasses.replace(base_ports, context=context)
    Agent.create(ports).open("session-workflow").submit(
        UserTurn("hello", workflow_state="custom", stream=False)
    )

    assert context.workflow_states == ["custom"]
    from embedagent_core.session_view import SessionReadView

    assert context.session_types == [SessionReadView]


def test_runtime_definition_owns_optional_turn_fuse():
    definition = RuntimeDefinition(max_turns=3)

    assert definition.max_turns == 3


def test_agent_uses_focused_restore_policy(base_ports):
    run_agent(
        AgentRuntime(base_ports, RuntimeDefinition()),
        AgentRequest("restore-policy-session", UserTurn("first", stream=False)),
    )
    policy = RecordingRestorePolicy()
    ports = dataclasses.replace(base_ports, restore_policy=policy)
    run_agent(
        AgentRuntime(ports, RuntimeDefinition()),
        AgentRequest("restore-policy-session", UserTurn("second", stream=False)),
    )

    assert policy.session_ids == ["restore-policy-session"]


def test_agent_uses_focused_session_projection(base_ports):
    from embedagent_core import Agent

    projection = RecordingSessionProjection()
    ports = dataclasses.replace(base_ports, session_projection=projection)
    Agent.create(ports).open("projection-session").submit(UserTurn("hello", stream=False))

    assert len(projection.calls) == 1
    from embedagent_core.session_view import SessionReadView

    assert isinstance(projection.calls[0][0], SessionReadView)
    assert (projection.calls[0][0].session_id, projection.calls[0][1]) == ("projection-session", "")


def test_runtime_definition_policy_defaults_are_isolated():
    from embedagent_core import RuntimeDefinition

    first = RuntimeDefinition()
    second = RuntimeDefinition()

    assert first.application_policy is not second.application_policy
    assert first.application_policy.mode_tool_policy is not second.application_policy.mode_tool_policy
    assert first.application_policy.write_path_policy is not second.application_policy.write_path_policy
    assert first.application_policy.mode_runtime_policy is not second.application_policy.mode_runtime_policy


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


def test_agent_result_uses_frozen_public_interaction_request():
    from embedagent_core import AgentInteractionRequest, AgentResult, AgentSessionView

    source = {"choices": [{"id": "approve"}]}
    pending = AgentInteractionRequest(
        interaction_id="interaction-1",
        kind="permission",
        tool_name="write_file",
        request_payload=source,
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

    source["choices"][0]["id"] = "changed"
    snapshot.messages[0]["content"]["text"] = "changed"

    assert result.pending_interaction is not None
    assert result.pending_interaction.request_payload["choices"][0]["id"] == "approve"
    assert result.turn_snapshot.messages[0]["content"]["text"] == "original"
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.pending_interaction.kind = "changed"


def test_agent_interaction_request_copies_nested_payload():
    from embedagent_core import AgentInteractionRequest

    source = {"options": [{"value": "yes"}]}
    request = AgentInteractionRequest("interaction-1", "user_input", "ask_user", source)
    source["options"][0]["value"] = "no"

    assert request.request_payload["options"][0]["value"] == "yes"


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
    guarded_runtime = AgentRuntime(runtime.ports, runtime.definition)
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
    assert guarded_runtime.ports.model.calls == 0


def test_run_agent_rejects_unfinished_side_effect_without_replaying_tool(base_runtime):
    from embedagent_core.runner import SessionRecoveryRequired

    runtime, session_log = base_runtime
    session_id = "session-incomplete-tool"
    session_log.append_event(session_id, "session_meta", {"current_mode": ""})
    session_log.append_event(
        session_id,
        "operation_started",
        {
            "operation_id": "tool:call-write",
            "kind": "tool_call",
            "turn_id": "turn-1",
            "step_id": "step-1",
            "tool_call_id": "call-write",
            "retryable": False,
            "metadata": {
                "tool_name": "write_file",
                "arguments": {"path": "result.txt", "content": "changed"},
            },
        },
    )
    event_count = len(session_log.load_events(session_id))

    with pytest.raises(SessionRecoveryRequired) as captured:
        run_agent(
            runtime,
            AgentRequest(session_id, UserTurn("continue", stream=False)),
        )

    assert captured.value.stop_reason == "incomplete_side_effect"
    assert len(session_log.load_events(session_id)) == event_count
    assert runtime.ports.model.calls == 0


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

    assert not hasattr(runtime, "build_engine")
    assert runtime.transaction is not None
    assert runtime.loop is not None
    assert runtime.kernel is not None
    assert runtime.journal is not None
    assert extension.assembly_count == 1


def test_agent_runtime_registers_context_reducers_once_across_concurrent_sessions():
    extension = ContextReducerRegistrarExtension()
    ports = AgentPorts(
        model=FakeModel(),
        tools=NoopToolRuntime(),
        session_log=InMemorySessionLog(),
        context=NoopContextAssembler(),
        permissions=PermissionPolicy(),
    )
    from embedagent_core import Agent

    agent = Agent.create(ports, RuntimeDefinition(extensions=(extension,)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda index: agent.open("parallel-%d" % index).submit(
                    UserTurn("run", stream=False)
                ),
                range(2),
            )
        )

    assert [result.final_text for result in results] == ["done", "done"]
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
