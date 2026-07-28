from types import SimpleNamespace

from embedagent_core.agent_effects import (
    ExecuteToolBatchEffect,
    InteractionSuspended,
    ToolBatchCompleted,
)
from embedagent_core.agent_tool_action_service import (
    AgentToolActionService,
    InteractionFactory,
)
from embedagent_core.extensions import ToolResultPatch
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


def test_normal_action_returns_tool_batch_completed_with_events_and_token():
    service = _service()
    effect = ExecuteToolBatchEffect(
        "tools-1",
        (Action("read_file", {"path": "README.md"}, "call-1"),),
        "build",
        "",
    )

    result = service.execute(effect, _session())

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
    effect = ExecuteToolBatchEffect(
        "tools-1",
        (Action("write_file", {"path": "demo.c", "content": "x"}, "call-1"),),
        "build",
        "",
    )

    result = service.execute(effect, _session())

    assert isinstance(result, InteractionSuspended)
    assert result.effect_id == "tools-1"
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
    effect = ExecuteToolBatchEffect(
        "tools-1",
        (Action("bash", {"command": "false"}, "call-1"),),
        "build",
        "",
    )

    result = service.execute(effect, _session())

    assert isinstance(result, ToolBatchCompleted)
    assert result.observations == (diagnostic,)
    assert result.observations[0].data["outcome_class"] == "diagnostic_failure"
