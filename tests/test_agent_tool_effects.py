import json
import time
from types import SimpleNamespace

import pytest
from embedagent_core.agent_effects import (
    ExecutePreparedToolBatchEffect,
    FrozenToolAction,
    InteractionSuspended,
    PreparedToolInvocation,
    PrepareToolBatchEffect,
    ToolBatchCompleted,
    ToolBatchPrepared,
)
from embedagent_core.agent_tool_action_service import (
    AgentToolActionService,
    InteractionFactory,
)
from embedagent_core.extensions import ToolResultPatch
from embedagent_core.interaction import UserInputResponse
from embedagent_core.permissions import PermissionPolicy
from embedagent_core.session import Action, Observation, Session
from embedagent_core.tool_contracts import PreparedToolObservation


class FakeExtensionHost(object):
    def allowed_tool_names(self, mode_name, workflow_state=""):
        del mode_name, workflow_state
        return {"read_file", "write_file", "bash", "ask_user"}

    def prepare_tool_call(self, session, action, current_mode, workflow_state):
        del session, current_mode, workflow_state
        return SimpleNamespace(block=False), action

    def apply_tool_result_patch(
        self,
        session,
        action,
        current_mode,
        workflow_state,
        observation,
    ):
        del session, action, current_mode, workflow_state
        return ToolResultPatch(observation=observation)

    def handle_tool_call(self, session, tool_name, current_mode, workflow_state):
        del session, tool_name, current_mode, workflow_state
        return None


class FakeTools(object):
    workspace = "."

    def __init__(self, observations=None):
        self._observations = dict(observations or {})
        self.finalized = []

    def tool_catalog_entry(self, tool_name):
        read_only = tool_name == "read_file"
        return {
            "permission_category": "read" if read_only else "shell_exec",
            "read_only": read_only,
            "concurrency_safe": read_only,
            "user_label": tool_name,
            "progress_renderer_key": "default",
            "result_renderer_key": "default",
            "source_type": "builtin",
            "source_id": tool_name,
        }

    def execute_with_interrupt(self, name, arguments, stop_event):
        del arguments, stop_event
        return self._observations.get(name) or Observation(
            name,
            True,
            None,
            {"path": "README.md"},
        )

    def materialize_observation(self, session_id, action, observation):
        del session_id
        return PreparedToolObservation(
            observation=observation,
            replacements=[],
            commit_token="token:%s" % action.call_id,
        )

    def finalize_observation(self, token):
        self.finalized.append(token)


class RecordingExtensionHost(FakeExtensionHost):
    def __init__(self, calls, allowed=True, blocked=False):
        self.calls = calls
        self.allowed = allowed
        self.blocked = blocked

    def allowed_tool_names(self, mode_name, workflow_state=""):
        del mode_name, workflow_state
        self.calls.append("allowed")
        return {"read_file", "write_file"} if self.allowed else set()

    def prepare_tool_call(self, session, action, current_mode, workflow_state):
        del session, current_mode, workflow_state
        self.calls.append("before:%s" % action.name)
        decision = SimpleNamespace(
            block=self.blocked,
            reason="blocked",
            metadata={},
        )
        return decision, action

    def handle_tool_call(self, session, tool_name, current_mode, workflow_state):
        del session, current_mode, workflow_state
        self.calls.append("extension_dispatch:%s" % tool_name)
        return None


class RecordingPermissionPolicy(object):
    def __init__(self, calls, outcome="allow"):
        self.calls = calls
        self.outcome = outcome

    def remembered_categories_for(self, session_id):
        del session_id
        return []

    def evaluate(self, action, remembered_categories=None):
        del remembered_categories
        category = "workspace_write" if action.name == "write_file" else "read"
        self.calls.append("permission:%s" % category)
        return SimpleNamespace(
            outcome=self.outcome,
            request=None,
            error="denied" if self.outcome == "deny" else None,
            details={"category": category},
        )


class RecordingWritePathPolicy(object):
    def __init__(self, calls, allowed=True):
        self.calls = calls
        self.allowed = allowed

    def is_path_writable(self, mode_name, path, app_config):
        del mode_name, app_config
        self.calls.append("path:%s" % path)
        return self.allowed


class RecordingTools(FakeTools):
    def __init__(self, calls):
        super(RecordingTools, self).__init__()
        self.calls = calls

    def tool_catalog_entry(self, tool_name):
        self.calls.append("catalog:%s" % tool_name)
        read_only = tool_name == "read_file"
        return {
            "name": tool_name,
            "permission_category": "read" if read_only else "workspace_write",
            "read_only": read_only,
            "concurrency_safe": read_only,
            "user_label": tool_name,
            "progress_renderer_key": "default",
            "result_renderer_key": "default",
            "supports_diff_preview": False,
            "source_type": "builtin",
            "source_id": tool_name,
        }

    def execute_with_interrupt(self, name, arguments, stop_event):
        self.calls.append("runtime_execute:%s" % name)
        return super(RecordingTools, self).execute_with_interrupt(
            name,
            arguments,
            stop_event,
        )

    def materialize_observation(self, session_id, action, observation):
        self.calls.append("materialize:%s" % action.name)
        return super(RecordingTools, self).materialize_observation(
            session_id,
            action,
            observation,
        )


def _prepare_effect(actions):
    return PrepareToolBatchEffect(
        "prepare-1",
        "m-assistant-turn-1-step-1-1",
        tuple(FrozenToolAction.from_action(action) for action in actions),
        "build",
        "",
    )


def _recording_service(calls, outcome="", path_allowed=True):
    return AgentToolActionService(
        tools=RecordingTools(calls),
        permission_policy=RecordingPermissionPolicy(
            calls,
            outcome="deny" if outcome == "permission_denied" else "allow",
        ),
        extension_host=RecordingExtensionHost(
            calls,
            allowed=outcome != "mode_tool_blocked",
            blocked=outcome == "extension_blocked",
        ),
        app_config_provider=lambda: None,
        interaction_factory=InteractionFactory(),
        write_path_policy=RecordingWritePathPolicy(calls, allowed=path_allowed),
    )


def _service(policy=None, tools=None):
    return AgentToolActionService(
        tools=tools or FakeTools(),
        permission_policy=policy or PermissionPolicy(auto_approve_all=True),
        extension_host=FakeExtensionHost(),
        app_config_provider=lambda: None,
        interaction_factory=InteractionFactory(),
    )


def _session():
    session = Session(session_id="session-1")
    session.add_user_message("hello", turn_id="turn-1")
    session.begin_step(step_id="step-1")
    return session


def _run_actions(
    service,
    session,
    actions,
    permission_handler=None,
    user_input_handler=None,
):
    prepared = service.prepare(
        _prepare_effect(actions),
        session,
        permission_handler=permission_handler,
        user_input_handler=user_input_handler,
    )
    if not isinstance(prepared, ToolBatchPrepared) or not prepared.invocations:
        return prepared
    return service.execute_prepared(
        ExecutePreparedToolBatchEffect(
            "tools-1",
            prepared.invocations,
            immediate_results=prepared.immediate_results,
        ),
        session,
    )


def test_prepare_checks_permission_and_path_before_any_dispatch():
    calls = []
    service = _recording_service(calls)
    effect = _prepare_effect(
        [Action("write_file", {"path": "generated.c", "content": "x"}, "call-1")]
    )

    result = service.prepare(effect, _session())

    assert isinstance(result, ToolBatchPrepared)
    assert calls == [
        "allowed",
        "before:write_file",
        "permission:workspace_write",
        "path:generated.c",
        "catalog:write_file",
    ]
    assert len(result.invocations) == 1
    invocation = result.invocations[0]
    assert isinstance(invocation, PreparedToolInvocation)
    assert invocation.invocation_id == "tool:m-assistant-turn-1-step-1-1:0"
    assert json.loads(invocation.presentation_json)["tool_label"] == "write_file"
    assert not any(item.startswith("extension_dispatch") for item in calls)
    assert not any(item.startswith("runtime_execute") for item in calls)
    assert not any(item.startswith("materialize") for item in calls)


@pytest.mark.parametrize(
    "outcome, action",
    [
        (
            "mode_tool_blocked",
            Action("write_file", {"path": "generated.c", "content": "x"}, "call-1"),
        ),
        (
            "extension_blocked",
            Action("write_file", {"path": "generated.c", "content": "x"}, "call-1"),
        ),
        (
            "permission_denied",
            Action("write_file", {"path": "generated.c", "content": "x"}, "call-1"),
        ),
        (
            "invalid_arguments",
            Action("write_file", {"content": "x"}, "call-1"),
        ),
        (
            "mode_path_blocked",
            Action("write_file", {"path": "generated.c", "content": "x"}, "call-1"),
        ),
    ],
)
def test_prepare_immediate_outcomes_never_become_ready_invocations(outcome, action):
    calls = []
    service = _recording_service(
        calls,
        outcome=outcome,
        path_allowed=outcome != "mode_path_blocked",
    )

    result = service.prepare(_prepare_effect([action]), _session())

    assert isinstance(result, ToolBatchPrepared)
    assert result.invocations == ()
    assert result.immediate_results[0].observation.data["error_kind"] == outcome
    assert not any(event.event_type == "operation_started" for event in result.events)
    assert not any(item.startswith("extension_dispatch") for item in calls)
    assert not any(item.startswith("runtime_execute") for item in calls)
    assert not any(item.startswith("materialize") for item in calls)


def test_prepare_is_serial_even_when_all_actions_are_parallel_safe():
    calls = []
    service = _recording_service(calls)
    effect = _prepare_effect(
        [
            Action("read_file", {"path": "a.c"}, "call-a"),
            Action("read_file", {"path": "b.c"}, "call-b"),
        ]
    )

    result = service.prepare(effect, _session())

    assert isinstance(result, ToolBatchPrepared)
    assert [item.source_index for item in result.invocations] == [0, 1]
    assert calls == [
        "allowed",
        "before:read_file",
        "permission:read",
        "catalog:read_file",
        "allowed",
        "before:read_file",
        "permission:read",
        "catalog:read_file",
    ]
    assert not any(item.startswith("runtime_execute") for item in calls)


def test_execute_prepared_does_not_repeat_checks_and_uses_invocation_id():
    calls = []
    service = _recording_service(calls)
    session = _session()
    prepared = service.prepare(
        _prepare_effect(
            [
                Action(
                    "write_file",
                    {"path": "generated.c", "content": "x"},
                    "call-1",
                )
            ]
        ),
        session,
    )
    calls[:] = []

    result = service.execute_prepared(
        ExecutePreparedToolBatchEffect("tools-1", prepared.invocations),
        session,
    )

    assert calls == [
        "extension_dispatch:write_file",
        "runtime_execute:write_file",
        "materialize:write_file",
    ]
    finishes = [
        event
        for event in result.events
        if event.event_type in ("operation_finished", "operation_interrupted")
    ]
    assert [event.payload["operation_id"] for event in finishes] == [
        prepared.invocations[0].invocation_id
    ]


def test_execute_prepared_returns_parallel_results_in_source_order():
    class OutOfOrderTools(FakeTools):
        def execute_with_interrupt(self, name, arguments, stop_event):
            del name, stop_event
            path = str(arguments.get("path") or "")
            if path == "a.c":
                time.sleep(0.05)
            return Observation(
                "read_file",
                True,
                None,
                {"path": path},
            )

    service = _service(tools=OutOfOrderTools())
    session = _session()
    prepared = service.prepare(
        _prepare_effect(
            [
                Action("read_file", {"path": "a.c"}, "call-a"),
                Action("read_file", {"path": "b.c"}, "call-b"),
            ]
        ),
        session,
    )

    result = service.execute_prepared(
        ExecutePreparedToolBatchEffect("tools-1", prepared.invocations),
        session,
        max_parallel_tools=2,
    )

    assert [item.data["path"] for item in result.observations] == ["a.c", "b.c"]
    tool_results = [event for event in result.events if event.event_type == "tool_result"]
    assert [event.payload["call_id"] for event in tool_results] == [
        "call-a",
        "call-b",
    ]


def test_normal_action_returns_tool_batch_completed_with_events_and_token():
    service = _service()
    result = _run_actions(
        service,
        _session(),
        [Action("read_file", {"path": "README.md"}, "call-1")],
    )

    assert isinstance(result, ToolBatchCompleted)
    assert result.effect_id == "tools-1"
    assert result.observations[0].success is True
    assert result.commit_tokens == ("token:call-1",)
    assert "tool_result" in [event.event_type for event in result.events]
    assert service.tools.finalized == []

    service.finalize(result.commit_tokens)
    assert service.tools.finalized == ["token:call-1"]


def test_permission_ask_returns_interaction_suspended_without_execution():
    policy = PermissionPolicy(auto_approve_all=False)
    policy.set_category_lookup(lambda tool_name: "workspace_write")
    tools = FakeTools()
    service = _service(policy=policy, tools=tools)
    result = _run_actions(
        service,
        _session(),
        [Action("write_file", {"path": "demo.c", "content": "x"}, "call-1")],
    )

    assert isinstance(result, InteractionSuspended)
    assert result.effect_id == "prepare-1"
    assert result.pending.kind == "permission"
    assert result.pending.tool_name == "write_file"
    assert [event.event_type for event in result.events] == ["pending_interaction"]


def test_nonzero_bash_is_diagnostic_observation_not_effect_failure():
    diagnostic = Observation(
        "bash",
        False,
        "command exited with code 1",
        {
            "exit_code": 1,
            "error_kind": "command_failed",
            "outcome_class": "diagnostic_failure",
        },
    )
    service = _service(tools=FakeTools({"bash": diagnostic}))
    result = _run_actions(
        service,
        _session(),
        [Action("bash", {"command": "false"}, "call-1")],
    )

    assert isinstance(result, ToolBatchCompleted)
    assert result.observations == (diagnostic,)
    assert result.observations[0].data["outcome_class"] == "diagnostic_failure"


def test_user_input_mode_selection_is_a_tool_result_without_session_mutation():
    service = _service()
    session = _session()
    initial_messages = list(session.messages)
    result = _run_actions(
        service,
        session,
        [Action("ask_user", {"question": "switch mode?"}, "call-1")],
        user_input_handler=lambda request: UserInputResponse(
            "yes",
            selected_mode="debug",
        ),
    )

    assert isinstance(result, ToolBatchPrepared)
    observation = result.immediate_results[0].observation
    assert observation.data["selected_mode"] == "debug"
    assert observation.data["mode_changed"] is True
    assert session.messages == initial_messages
